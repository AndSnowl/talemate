"""Isolated local Talemate app runner, for browser tests and manual checks.

``start`` copies the working tree (tracked files with their uncommitted edits,
plus untracked files that aren't ignored) into a temporary root, writes a
``config.yaml`` for the run there and starts the backend and the vite
frontend from that copy. The copy *is* the root: ``PYTHONPATH=<root>/src``
makes the copy's ``talemate`` package shadow the checkout's editable install,
so ``TALEMATE_ROOT`` (and with it config, scenes and logs) resolves to the
copy. The checkout's own ``config.yaml``, ``scenes/`` and friends are never
read or written.

Usage (from the talemate repo root, *inside* the Guix dev shell, because the
children run ``uv`` and ``npx``, which are only on PATH there; this script
does not wrap itself in guix)::

    guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/talemate_app.py \
        start [--ai] [--root DIR] [--backend-port N] [--frontend-port N]
    guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/talemate_app.py status
    guix shell -m manifest.scm -- uv run --no-sync python scripts/dev/talemate_app.py stop

(``uv run --no-sync`` because the runner itself needs the project's ``yaml``
and ``websockets``.)

The default root is ``$TMPDIR/talemate-app`` (``$CLAUDE_SCRATCHPAD/talemate-app``
when ``CLAUDE_SCRATCHPAD`` is set). The run's state lives in
``<root>/.talemate-app.json`` and the child logs in ``<root>/logs/``.

``start`` refuses (``AppStartError``) to start over a live run in the same
root: call ``stop`` first. A stale state file whose processes are gone is
cleaned up. A root that is non-empty and was not made by this runner is never
wiped. ``--ai`` configures a single KoboldCpp client at
``$TALEMATE_TEST_KOBOLDCPP_URL`` (default ``http://192.168.0.5:5001``).

Each child runs in its own process group. ``stop`` sends SIGTERM to the group,
then SIGKILL after 10 s, and only signals PIDs whose ``/proc/<pid>/cmdline``
still contains the root's path (or whose cwd is inside the root), so a
reused PID is never killed.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ".talemate-app.json"
ROOT_MARKER = ".talemate-app-root"
DEFAULT_KOBOLDCPP_URL = "http://192.168.0.5:5001"
STOP_GRACE_SECONDS = 10
LOG_TAIL_LINES = 40


class AppStartError(RuntimeError):
    """The app could not be started (busy port, crashed child, timeout...)."""


@dataclasses.dataclass
class AppInfo:
    root: Path
    backend_port: int
    frontend_port: int
    backend_pid: int
    frontend_pid: int
    frontend_url: str
    backend_ws_url: str
    log_dir: Path


# --- child commands (module-level so tests can monkeypatch them) -----------


def backend_command(copy_root: Path, port: int) -> list[str]:
    # The script path is absolute so the root shows up in /proc/<pid>/cmdline.
    return [
        "uv",
        "run",
        "--no-sync",
        "python",
        str(copy_root / "src" / "talemate" / "server" / "run.py"),
        "runserver",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--backend-only",
    ]


def frontend_command(copy_root: Path, port: int) -> list[str]:
    # --dir puts the root in the cmdline; --strictPort stops vite from
    # silently moving to another port when this one is taken.
    return [
        "npx",
        "--yes",
        "corepack@0.34.0",
        "pnpm",
        "--dir",
        str(copy_root / "talemate_frontend"),
        "run",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--strictPort",
    ]


# --- copy and config --------------------------------------------------------


def _git_paths(src: Path, *args: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(src), "ls-files", "-z", *args],
        check=True,
        capture_output=True,
    ).stdout
    return [p for p in out.decode().split("\0") if p]


def copy_tree(src: Path, dest: Path) -> list[str]:
    """Copy the git working tree of ``src`` into ``dest``; return copied paths."""
    src, dest = Path(src), Path(dest)
    deleted = set(_git_paths(src, "--deleted"))
    copied = []
    for rel in _git_paths(src, "--cached", "--others", "--exclude-standard"):
        if rel in deleted:
            continue
        source = src / rel
        if not os.path.lexists(source) or (source.is_dir() and not source.is_symlink()):
            continue  # gone, or a submodule directory
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
        copied.append(rel)

    if (src / ".venv").exists():
        (dest / ".venv").symlink_to(src / ".venv")

    # node_modules is a real directory whose entries are symlinks, rather than
    # one symlink: vite writes its caches (.vite, .vite-temp) into
    # node_modules, and those must land in the copy, not in the checkout.
    modules = src / "talemate_frontend" / "node_modules"
    if modules.is_dir():
        dest_modules = dest / "talemate_frontend" / "node_modules"
        dest_modules.mkdir(parents=True, exist_ok=True)
        for entry in modules.iterdir():
            if entry.name in (".vite", ".vite-temp"):
                continue
            (dest_modules / entry.name).symlink_to(entry)
    return copied


def render_config(ai: bool, koboldcpp_url: str) -> str:
    """Return the run's config.yaml text, based on config.example.yaml."""
    config = yaml.safe_load((REPO_ROOT / "config.example.yaml").read_text())
    if ai:
        overlay = yaml.safe_load(
            (Path(__file__).parent / "test_config.example.yaml").read_text()
        )
        clients = overlay["clients"]
        clients["KoboldCpp"]["api_url"] = koboldcpp_url
        config["clients"] = clients
    else:
        config["clients"] = {}
    return yaml.safe_dump(config, sort_keys=False)


# --- process helpers ----------------------------------------------------


def default_root() -> Path:
    base = os.environ.get("CLAUDE_SCRATCHPAD") or tempfile.gettempdir()
    return Path(base) / "talemate-app"


def _resolve_root(root: Path | None) -> Path:
    return Path(root).resolve() if root is not None else default_root().resolve()


def _owned(pid: int, root: Path) -> bool:
    """True if ``pid`` is alive and was started by this runner for ``root``.

    That is: its cmdline mentions ``root``, or its working directory is inside
    ``root``. The cwd fallback is needed because npx rewrites its process
    title and redacts uuid-like path segments (as in a scratchpad path), so
    the frontend leader's cmdline may not show the root at all.
    """
    prefix = str(root) + "/"
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        cwd = os.readlink(f"/proc/{pid}/cwd") + "/"
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return False  # gone, or a zombie (whose cwd can't be read)
    return prefix.encode() in cmdline or cwd.startswith(prefix)


def _wait_exit(pid: int, timeout: float) -> bool:
    """Wait for ``pid`` to exit (or become a zombie); True if it did."""
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return True
    try:
        ready, _, _ = select.select([fd], [], [], timeout)
        return bool(ready)
    finally:
        os.close(fd)


def _reap(pid: int) -> None:
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass  # not our child; its own parent reaps it


def _kill_group(pid: int, root: Path) -> None:
    """SIGTERM the process group led by ``pid``, then SIGKILL after a grace."""
    if not _owned(pid, root):
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    _wait_exit(pid, STOP_GRACE_SECONDS)
    try:
        os.killpg(pid, signal.SIGKILL)  # the leader or any straggler
    except ProcessLookupError:
        pass
    _wait_exit(pid, STOP_GRACE_SECONDS)
    _reap(pid)


def _port_free(port: int) -> bool:
    with socket.socket() as sock:
        # Like the servers themselves: a port held only by TIME_WAIT sockets
        # from a previous run is free; a live listener still fails the bind.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _pick_port(explicit: int | None, name: str) -> int:
    if explicit is not None:
        if not _port_free(explicit):
            raise AppStartError(f"{name} port {explicit} is already in use")
        return explicit
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _tail(path: Path, lines: int = LOG_TAIL_LINES) -> str:
    try:
        text = path.read_text(errors="replace")
    except FileNotFoundError:
        return ""
    return "\n".join(text.splitlines()[-lines:])


async def _ws_handshake(url: str) -> None:
    import websockets

    async with websockets.connect(url, open_timeout=2, close_timeout=2):
        pass


def _backend_ready(url: str) -> bool:
    try:
        asyncio.run(_ws_handshake(url))
    except Exception:  # refused, reset, handshake timeout, ...
        return False
    return True


def _frontend_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


# --- state ------------------------------------------------------------------


def _read_state(root: Path) -> AppInfo | None:
    try:
        data = json.loads((root / STATE_FILE).read_text())
    except FileNotFoundError:
        return None
    data["root"] = Path(data["root"])
    data["log_dir"] = Path(data["log_dir"])
    return AppInfo(**data)


def _write_state(info: AppInfo) -> None:
    data = dataclasses.asdict(info)
    data["root"] = str(info.root)
    data["log_dir"] = str(info.log_dir)
    (info.root / STATE_FILE).write_text(json.dumps(data, indent=2) + "\n")


# --- public API -----------------------------------------------------------


def status(root: Path | None = None) -> AppInfo | None:
    """Return the live run in ``root``, or None (removing a stale state file)."""
    root = _resolve_root(root)
    info = _read_state(root)
    if info is None:
        return None
    if _owned(info.backend_pid, root) or _owned(info.frontend_pid, root):
        return info
    (root / STATE_FILE).unlink(missing_ok=True)
    return None


def stop(root: Path | None = None) -> None:
    """Stop the run in ``root``, if any, and remove its state file."""
    root = _resolve_root(root)
    info = _read_state(root)
    if info is None:
        return
    for pid in (info.frontend_pid, info.backend_pid):
        _kill_group(pid, root)
    (root / STATE_FILE).unlink(missing_ok=True)


def _prepare_root(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        if not (root / ROOT_MARKER).exists():
            raise AppStartError(
                f"{root} is not empty and was not created by this runner; "
                "refusing to wipe it"
            )
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / ROOT_MARKER).write_text("created by scripts/dev/talemate_app.py\n")


def backend_env(root: Path) -> dict:
    """Environment for the backend: the copy's code, all writes inside root."""
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)  # the copy's .venv is the project env
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(root / "src"), os.environ.get("PYTHONPATH")) if p
    )
    # .venv is a symlink into the checkout; keep bytecode caches out of it.
    env["PYTHONPYCACHEPREFIX"] = str(root / "pycache")
    env["NLTK_DATA"] = str(root / "nltk_data")  # keep downloads in root
    return env


def frontend_env(backend_port: int) -> dict:
    env = dict(os.environ)
    env["VITE_TALEMATE_BACKEND_WEBSOCKET_URL"] = f"ws://127.0.0.1:{backend_port}"
    env["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
    # pnpm's pre-run deps check keys node_modules state by the checkout's
    # path, so in the copy it would always decide to reinstall (purging
    # node_modules, whose entries point into the checkout). Turn it off.
    env["pnpm_config_verify_deps_before_run"] = "false"
    return env


def _launch(cmd: list[str], cwd: Path, env: dict, log_file: Path) -> subprocess.Popen:
    with open(log_file, "wb") as log:
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def start(
    root: Path | None = None,
    ai: bool = False,
    backend_port: int | None = None,
    frontend_port: int | None = None,
    timeout: float = 180,
) -> AppInfo:
    """Copy the tree into ``root``, start backend + frontend, wait until ready."""
    root = _resolve_root(root)
    live = status(root)
    if live is not None:
        raise AppStartError(
            f"a run is already live in {root} (backend pid {live.backend_pid}, "
            f"frontend pid {live.frontend_pid}); stop it first"
        )
    bp = _pick_port(backend_port, "backend")
    fp = _pick_port(frontend_port, "frontend")

    _prepare_root(root)
    copy_tree(REPO_ROOT, root)
    koboldcpp_url = os.environ.get("TALEMATE_TEST_KOBOLDCPP_URL", DEFAULT_KOBOLDCPP_URL)
    (root / "config.yaml").write_text(render_config(ai, koboldcpp_url))
    log_dir = root / "logs"
    log_dir.mkdir(exist_ok=True)
    (root / "nltk_data").mkdir(exist_ok=True)

    backend_log = log_dir / "backend.log"
    frontend_log = log_dir / "frontend.log"
    procs: list[tuple[str, subprocess.Popen, Path]] = []
    try:
        procs.append(
            (
                "backend",
                _launch(
                    backend_command(root, bp), root, backend_env(root), backend_log
                ),
                backend_log,
            )
        )
        procs.append(
            (
                "frontend",
                _launch(
                    frontend_command(root, fp),
                    root / "talemate_frontend",
                    frontend_env(bp),
                    frontend_log,
                ),
                frontend_log,
            )
        )
    except BaseException:
        for _, proc, _ in procs:
            _kill_group(proc.pid, root)
        raise

    info = AppInfo(
        root=root,
        backend_port=bp,
        frontend_port=fp,
        backend_pid=procs[0][1].pid,
        frontend_pid=procs[1][1].pid,
        frontend_url=f"http://127.0.0.1:{fp}/",
        backend_ws_url=f"ws://127.0.0.1:{bp}/ws",
        log_dir=log_dir,
    )
    _write_state(info)

    try:
        _wait_ready(info, procs, timeout)
    except BaseException:
        stop(root)
        raise
    return info


def _wait_ready(
    info: AppInfo, procs: list[tuple[str, subprocess.Popen, Path]], timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    backend_ok = frontend_ok = False
    while True:
        for name, proc, log in procs:
            if proc.poll() is not None:
                raise AppStartError(
                    f"{name} exited with code {proc.returncode} before the app "
                    f"was ready; last {LOG_TAIL_LINES} lines of {log}:\n{_tail(log)}"
                )
        backend_ok = backend_ok or _backend_ready(info.backend_ws_url)
        frontend_ok = frontend_ok or _frontend_ready(info.frontend_url)
        if backend_ok and frontend_ok:
            return
        if time.monotonic() >= deadline:
            tails = "\n".join(
                f"--- {name} ({log}):\n{_tail(log)}" for name, _, log in procs
            )
            raise AppStartError(
                f"app not ready after {timeout:.0f}s "
                f"(backend ready: {backend_ok}, frontend ready: {frontend_ok})\n"
                f"{tails}"
            )
        # Pause between polls by waiting on the backend's exit, so a crash
        # is noticed at once rather than after a fixed sleep.
        try:
            procs[0][1].wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            pass


# --- CLI --------------------------------------------------------------------


def _print_info(info: AppInfo) -> None:
    print(f"root:      {info.root}")
    print(f"frontend:  {info.frontend_url} (pid {info.frontend_pid})")
    print(f"backend:   {info.backend_ws_url} (pid {info.backend_pid})")
    print(f"logs:      {info.log_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["start", "stop", "status"])
    parser.add_argument("--ai", action="store_true", help="configure KoboldCpp")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--backend-port", type=int, default=None)
    parser.add_argument("--frontend-port", type=int, default=None)
    args = parser.parse_args(argv)

    if args.command == "start":
        try:
            info = start(
                root=args.root,
                ai=args.ai,
                backend_port=args.backend_port,
                frontend_port=args.frontend_port,
            )
        except AppStartError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _print_info(info)
        return 0
    if args.command == "stop":
        stop(args.root)
        print("stopped")
        return 0
    info = status(args.root)
    if info is None:
        print("not running")
        return 1
    _print_info(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
