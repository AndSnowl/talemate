"""Unit tests for the isolated local app runner (scripts/dev/talemate_app.py).

No browser and no real backend/frontend: the child commands are
monkeypatched where a launch would otherwise happen.
"""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "talemate_app", _REPO_ROOT / "scripts" / "dev" / "talemate_app.py"
)
talemate_app = importlib.util.module_from_spec(_spec)
sys.modules["talemate_app"] = talemate_app
_spec.loader.exec_module(talemate_app)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


def _pid_alive(pid: int) -> bool:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


def test_copy_includes_uncommitted_and_untracked_files_but_not_ignored(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q")
    (src / ".gitignore").write_text("config.yaml\n")
    (src / "committed.txt").write_text("committed\n")
    (src / "modified.txt").write_text("old\n")
    (src / "gone.txt").write_text("deleted later\n")
    _git(src, "add", ".")
    _git(src, "commit", "-q", "-m", "init")
    (src / "modified.txt").write_text("new\n")
    (src / "sub").mkdir()
    (src / "sub" / "untracked.txt").write_text("untracked\n")
    (src / "config.yaml").write_text("secret: 1\n")
    (src / "gone.txt").unlink()

    dest = tmp_path / "dest"
    copied = talemate_app.copy_tree(src, dest)

    assert (dest / "committed.txt").read_text() == "committed\n"
    assert (dest / "modified.txt").read_text() == "new\n"
    assert (dest / "sub" / "untracked.txt").read_text() == "untracked\n"
    assert not (dest / "config.yaml").exists()
    assert not (dest / "gone.txt").exists()
    assert "sub/untracked.txt" in copied
    assert "config.yaml" not in copied
    assert "gone.txt" not in copied


def test_copy_symlinks_venv_and_node_modules(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q")
    (src / ".gitignore").write_text(".venv/\nnode_modules/\n")
    (src / ".venv" / "bin").mkdir(parents=True)
    modules = src / "talemate_frontend" / "node_modules"
    (modules / ".pnpm" / "vue").mkdir(parents=True)
    (modules / "vue").symlink_to(".pnpm/vue")
    (src / "talemate_frontend" / "package.json").write_text("{}\n")

    dest = tmp_path / "dest"
    talemate_app.copy_tree(src, dest)

    assert (dest / ".venv").is_symlink()
    assert (dest / ".venv").resolve() == (src / ".venv").resolve()
    dest_modules = dest / "talemate_frontend" / "node_modules"
    # node_modules is a real directory of symlinks, so tool caches that get
    # created inside it (vite's .vite, .vite-temp) stay in the copy.
    assert dest_modules.is_dir() and not dest_modules.is_symlink()
    for name in (".pnpm", "vue"):
        assert (dest_modules / name).is_symlink()
        assert (dest_modules / name).resolve() == (modules / name).resolve()


def test_render_config_without_ai_has_no_clients():
    config = yaml.safe_load(talemate_app.render_config(False, "http://x:1"))
    assert config["clients"] == {}
    example = yaml.safe_load((_REPO_ROOT / "config.example.yaml").read_text())
    assert config["creator"] == example["creator"]


def test_render_config_with_ai_has_only_koboldcpp():
    url = "http://127.0.0.1:9999"
    config = yaml.safe_load(talemate_app.render_config(True, url))
    assert config["clients"] == {
        "KoboldCpp": {
            "type": "koboldcpp",
            "name": "KoboldCpp",
            "api_url": url,
            "max_token_length": 16384,
        }
    }


def test_stop_ignores_pid_not_started_by_runner(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outsider = subprocess.Popen(["sleep", "60"], start_new_session=True)
    try:
        state = {
            "root": str(root),
            "backend_port": 1,
            "frontend_port": 2,
            "backend_pid": outsider.pid,
            "frontend_pid": outsider.pid,
            "frontend_url": "http://127.0.0.1:2/",
            "backend_ws_url": "ws://127.0.0.1:1/ws",
            "log_dir": str(root / "logs"),
        }
        (root / ".talemate-app.json").write_text(json.dumps(state))

        talemate_app.stop(root)

        assert outsider.poll() is None
        assert _pid_alive(outsider.pid)
    finally:
        outsider.kill()
        outsider.wait()


def test_stop_kills_group_whose_cmdline_hides_the_root(tmp_path):
    # npx rewrites its process title and redacts uuid-like path segments, so
    # the frontend leader's cmdline may not show the root; its cwd does.
    root = tmp_path / "root"
    (root / "talemate_frontend").mkdir(parents=True)
    child = subprocess.Popen(
        ["sleep", "60"], cwd=root / "talemate_frontend", start_new_session=True
    )
    try:
        state = {
            "root": str(root),
            "backend_port": 1,
            "frontend_port": 2,
            "backend_pid": child.pid,
            "frontend_pid": child.pid,
            "frontend_url": "http://127.0.0.1:2/",
            "backend_ws_url": "ws://127.0.0.1:1/ws",
            "log_dir": str(root / "logs"),
        }
        (root / ".talemate-app.json").write_text(json.dumps(state))

        talemate_app.stop(root)

        assert child.wait(timeout=5) is not None
    finally:
        child.kill()
        child.wait()


def test_start_replaces_stale_state(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    dead = subprocess.Popen(["true"])
    dead.wait()
    state_file = root / ".talemate-app.json"
    state_file.write_text(
        json.dumps(
            {
                "root": str(root),
                "backend_port": 1,
                "frontend_port": 2,
                "backend_pid": dead.pid,
                "frontend_pid": dead.pid,
                "frontend_url": "http://127.0.0.1:2/",
                "backend_ws_url": "ws://127.0.0.1:1/ws",
                "log_dir": str(root / "logs"),
            }
        )
    )

    assert talemate_app.status(root) is None
    assert not state_file.exists()


def _never_run(copy_root, port):
    raise AssertionError("no process should be launched")


def test_explicit_busy_port_errors_fast(tmp_path, monkeypatch):
    monkeypatch.setattr(talemate_app, "backend_command", _never_run)
    monkeypatch.setattr(talemate_app, "frontend_command", _never_run)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        began = time.monotonic()
        with pytest.raises(talemate_app.AppStartError, match=str(port)):
            talemate_app.start(root=tmp_path / "root", backend_port=port)
        assert time.monotonic() - began < 5


def test_start_reports_backend_crash_with_log_tail(tmp_path, monkeypatch):
    monkeypatch.setattr(
        talemate_app,
        "backend_command",
        lambda copy_root, port: [
            sys.executable,
            "-c",
            "import sys; print('boom'); sys.exit(3)",
        ],
    )
    # A stand-in frontend that never becomes ready; start must clean it up.
    # Its argv carries a path under the root, so the runner's ownership
    # check matches it by cmdline (as for the real backend), not by cwd.
    monkeypatch.setattr(
        talemate_app,
        "frontend_command",
        lambda copy_root, port: [
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            str(copy_root / "talemate_frontend"),
        ],
    )
    launched = []
    real_launch = talemate_app._launch

    def recording_launch(cmd, cwd, env, log_file):
        proc = real_launch(cmd, cwd, env, log_file)
        launched.append(proc)
        return proc

    monkeypatch.setattr(talemate_app, "_launch", recording_launch)
    root = tmp_path / "root"
    with pytest.raises(talemate_app.AppStartError, match="boom"):
        talemate_app.start(root=root, timeout=60)
    assert not (root / ".talemate-app.json").exists()
    assert len(launched) == 2
    frontend = launched[1]
    assert str(root.resolve() / "talemate_frontend") in frontend.args
    assert not _pid_alive(frontend.pid)


def test_port_free_after_closed_connection_in_time_wait():
    # The side that closes first keeps the port in TIME_WAIT; a fresh
    # server can still bind it (with SO_REUSEADDR), so it counts as free.
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]
    client = socket.create_connection(("127.0.0.1", port))
    conn, _ = server.accept()
    conn.close()  # server side closes first -> TIME_WAIT on `port`
    client.recv(1)  # wait for the FIN
    client.close()
    server.close()

    assert talemate_app._port_free(port)


def test_backend_env_keeps_writes_in_root(tmp_path):
    env = talemate_app.backend_env(tmp_path)
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(tmp_path / "src")
    assert env["PYTHONPYCACHEPREFIX"] == str(tmp_path / "pycache")
    assert env["NLTK_DATA"] == str(tmp_path / "nltk_data")
    assert "VIRTUAL_ENV" not in env


def test_backend_env_puts_ffmpeg_libs_on_library_path(tmp_path, monkeypatch):
    """torchcodec (loaded by the memory agent's embeddings) dlopens FFmpeg's
    libraries; on Guix they're only found through LD_LIBRARY_PATH."""
    store = tmp_path / "ffmpeg-8"
    (store / "bin").mkdir(parents=True)
    (store / "lib").mkdir()
    (store / "bin" / "ffmpeg").touch()
    profile_bin = tmp_path / "profile" / "bin"
    profile_bin.mkdir(parents=True)
    (profile_bin / "ffmpeg").symlink_to(store / "bin" / "ffmpeg")
    monkeypatch.setattr(
        talemate_app.shutil,
        "which",
        lambda name: str(profile_bin / name) if name == "ffmpeg" else None,
    )
    monkeypatch.setenv("LD_LIBRARY_PATH", "/existing")

    env = talemate_app.backend_env(tmp_path)

    assert env["LD_LIBRARY_PATH"].split(os.pathsep) == [str(store / "lib"), "/existing"]


def test_vite_config_allows_checkout_node_modules(tmp_path):
    """node_modules entries are symlinks into the checkout; vite serves them
    by their real path, which its default fs.allow (the copy) refuses with
    403 (e.g. the icon font). The run's vite config must allow them."""
    (tmp_path / "talemate_frontend").mkdir()

    config = talemate_app.write_vite_config(tmp_path)

    assert config.parent == tmp_path / "talemate_frontend"
    text = config.read_text()
    assert 'from "./vite.config.mjs"' in text
    assert json.dumps(str(tmp_path)) in text
    modules = (_REPO_ROOT / "talemate_frontend" / "node_modules").resolve()
    assert json.dumps(str(modules)) in text
    cmd = talemate_app.frontend_command(tmp_path, 4000)
    assert cmd[cmd.index("--config") + 1] == str(config)
