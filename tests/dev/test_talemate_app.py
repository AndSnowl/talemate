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
import types
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


@pytest.fixture()
def tiny_checkout(tmp_path, monkeypatch):
    """Make ``start`` copy a tiny temp git repo instead of the live checkout."""
    repo = tmp_path / "checkout"
    (repo / "talemate_frontend").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "talemate_frontend" / "package.json").write_text("{}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    real_copy_tree = talemate_app.copy_tree
    copies = []

    def copy_tiny(src, dest):
        assert Path(src) == talemate_app.REPO_ROOT
        copies.append(dest)
        return real_copy_tree(repo, dest)

    monkeypatch.setattr(talemate_app, "copy_tree", copy_tiny)
    return copies


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


def test_copy_skips_file_deleted_before_its_copy(tmp_path, monkeypatch):
    # Something else (an mkdocs build writing site/, say) deletes a file
    # after git listed it and after the existence check, just before copy2.
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q")
    (src / "keep.txt").write_text("keep\n")
    (src / "site").mkdir()
    (src / "site" / "vanishing.html").write_text("<p>soon gone</p>\n")
    real_copy2 = talemate_app.shutil.copy2

    def racing_copy2(source, target, **kwargs):
        if Path(source).name == "vanishing.html":
            Path(source).unlink()
        return real_copy2(source, target, **kwargs)

    monkeypatch.setattr(talemate_app.shutil, "copy2", racing_copy2)
    dest = tmp_path / "dest"
    copied = talemate_app.copy_tree(src, dest)

    assert copied == ["keep.txt"]
    assert (dest / "keep.txt").read_text() == "keep\n"
    assert not (dest / "site" / "vanishing.html").exists()


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


def test_start_reports_backend_crash_with_log_tail(
    tmp_path, monkeypatch, tiny_checkout
):
    monkeypatch.setattr(
        talemate_app,
        "backend_command",
        lambda copy_root, port, *_: [
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
        lambda copy_root, port, *_: [
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
    assert tiny_checkout == [root.resolve()]  # never the live checkout
    assert len(launched) == 2
    frontend = launched[1]
    assert str(root.resolve() / "talemate_frontend") in frontend.args
    assert not _pid_alive(frontend.pid)


class _LowestFreePortSocket:
    """A stand-in socket whose bind(0) hands out the lowest port not held.

    Like a kernel that reuses a port as soon as its socket closes: two
    auto-picks that don't overlap get the same port.
    """

    held: set = set()

    def __init__(self, *args):
        self.port = None

    def setsockopt(self, *args):
        pass

    def bind(self, address):
        port = address[1]
        if port == 0:
            port = min(p for p in range(50001, 50010) if p not in self.held)
        if port in self.held:
            raise OSError("in use")
        self.held.add(port)
        self.port = port

    def getsockname(self):
        return ("127.0.0.1", self.port)

    def close(self):
        self.held.discard(self.port)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_auto_picked_ports_in_one_start_are_distinct(
    tmp_path, monkeypatch, tiny_checkout
):
    _LowestFreePortSocket.held = set()
    fake_socket = types.SimpleNamespace(
        socket=_LowestFreePortSocket,
        SOL_SOCKET=socket.SOL_SOCKET,
        SO_REUSEADDR=socket.SO_REUSEADDR,
    )
    monkeypatch.setattr(talemate_app, "socket", fake_socket)
    monkeypatch.setattr(
        talemate_app, "_launch", lambda cmd, cwd, env, log: types.SimpleNamespace(pid=0)
    )
    monkeypatch.setattr(talemate_app, "_wait_ready", lambda info, procs, timeout: None)

    info = talemate_app.start(root=tmp_path / "root")

    assert info.backend_port != info.frontend_port
    assert _LowestFreePortSocket.held == set()  # both released again


def test_start_ai_refused_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    monkeypatch.setattr(talemate_app, "backend_command", _never_run)
    monkeypatch.setattr(talemate_app, "frontend_command", _never_run)
    root = tmp_path / "root"
    with pytest.raises(talemate_app.AppStartError) as excinfo:
        talemate_app.start(root=root, ai=True)
    assert str(excinfo.value) == (
        "AI runs need TALEMATE_AI_TESTS=1 — ask the owner first"
    )
    assert not root.exists()  # refused before anything was copied


def test_cli_start_ai_refused_without_opt_in(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TALEMATE_AI_TESTS", raising=False)
    monkeypatch.setattr(talemate_app, "backend_command", _never_run)
    monkeypatch.setattr(talemate_app, "frontend_command", _never_run)
    code = talemate_app.main(["start", "--ai", "--root", str(tmp_path / "root")])
    assert code == 1
    assert "AI runs need TALEMATE_AI_TESTS=1 — ask the owner first" in (
        capsys.readouterr().err
    )


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


def test_backend_env_never_uses_the_os_keyring(tmp_path, monkeypatch):
    # The names src/talemate/util/encryption.py reads.
    monkeypatch.delenv("TALEMATE_DISABLE_KEYRING", raising=False)
    monkeypatch.setenv("TALEMATE_ENCRYPTION_KEY_DIR", "/owner/secrets")
    env = talemate_app.backend_env(tmp_path)
    assert env["TALEMATE_DISABLE_KEYRING"] == "1"
    assert env["TALEMATE_ENCRYPTION_KEY_DIR"] == str(tmp_path / "secrets")


def test_backend_env_puts_ffmpeg_libs_on_library_path(tmp_path, monkeypatch):
    """torchcodec (loaded by the memory agent's embeddings) dlopens FFmpeg's
    libraries; on Guix they're only found through LD_LIBRARY_PATH."""
    # Isolate from the real shell's GUIX_ENVIRONMENT (set when this test
    # itself runs under `guix shell`), which backend_env also appends to
    # LD_LIBRARY_PATH and would otherwise leak into this assertion.
    monkeypatch.delenv("GUIX_ENVIRONMENT", raising=False)
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


def test_backend_env_adds_guix_environment_lib(tmp_path, monkeypatch):
    """chromadb (via numpy) dlopens libz.so.1; on Guix that's only found
    through LD_LIBRARY_PATH, under the active shell's profile."""
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    monkeypatch.setattr(talemate_app.shutil, "which", lambda name: None)
    guix_env = tmp_path / "guix-profile"
    (guix_env / "lib").mkdir(parents=True)
    monkeypatch.setenv("GUIX_ENVIRONMENT", str(guix_env))

    env = talemate_app.backend_env(tmp_path)

    assert str(guix_env / "lib") in env["LD_LIBRARY_PATH"].split(os.pathsep)


def test_backend_env_without_guix_environment_unchanged(tmp_path, monkeypatch):
    """Without GUIX_ENVIRONMENT, LD_LIBRARY_PATH holds only what it held
    before: the ffmpeg-derived value, and nothing GUIX_ENVIRONMENT-derived."""
    monkeypatch.delenv("GUIX_ENVIRONMENT", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    monkeypatch.setattr(talemate_app.shutil, "which", lambda name: None)

    env = talemate_app.backend_env(tmp_path)

    assert "LD_LIBRARY_PATH" not in env


def test_backend_command_binds_loopback_by_default():
    cmd = talemate_app.backend_command(Path("/root"), 1234)
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"


def test_backend_command_lan_binds_all_interfaces():
    cmd = talemate_app.backend_command(Path("/root"), 1234, host="0.0.0.0")
    assert cmd[cmd.index("--host") + 1] == "0.0.0.0"


def test_frontend_command_binds_loopback_by_default():
    cmd = talemate_app.frontend_command(Path("/root"), 1234)
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"


def test_frontend_command_lan_binds_all_interfaces():
    cmd = talemate_app.frontend_command(Path("/root"), 1234, host="0.0.0.0")
    assert cmd[cmd.index("--host") + 1] == "0.0.0.0"


def test_frontend_env_websocket_host_defaults_to_loopback():
    env = talemate_app.frontend_env(5050)
    assert env["VITE_TALEMATE_BACKEND_WEBSOCKET_URL"] == "ws://127.0.0.1:5050"


def test_frontend_env_websocket_host_follows_lan_host():
    # The frontend (TalemateApp.vue) already swaps a 0.0.0.0 backend URL for
    # the page's own hostname, so a browser on another machine connects to
    # the right backend.
    env = talemate_app.frontend_env(5050, host="0.0.0.0")
    assert env["VITE_TALEMATE_BACKEND_WEBSOCKET_URL"] == "ws://0.0.0.0:5050"


def test_vite_config_allows_any_host_when_lan_requested(tmp_path):
    (tmp_path / "talemate_frontend").mkdir()
    config = talemate_app.write_vite_config(tmp_path, allow_lan=True)
    assert "config.server.allowedHosts = true;" in config.read_text()


def test_vite_config_leaves_allowed_hosts_alone_without_lan(tmp_path):
    (tmp_path / "talemate_frontend").mkdir()
    config = talemate_app.write_vite_config(tmp_path)
    assert "allowedHosts" not in config.read_text()


def test_pick_ports_probes_the_requested_host(monkeypatch):
    recorded_hosts = []

    class _RecordingSocket:
        _next_port = 60001

        def __init__(self, *args):
            self._port = None

        def setsockopt(self, *args):
            pass

        def bind(self, address):
            recorded_hosts.append(address[0])
            port = address[1] or _RecordingSocket._next_port
            _RecordingSocket._next_port += 1
            self._port = port

        def getsockname(self):
            return ("x", self._port)

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    fake_socket = types.SimpleNamespace(
        socket=_RecordingSocket,
        SOL_SOCKET=socket.SOL_SOCKET,
        SO_REUSEADDR=socket.SO_REUSEADDR,
    )
    monkeypatch.setattr(talemate_app, "socket", fake_socket)

    talemate_app._pick_ports(None, None, host="0.0.0.0")

    assert recorded_hosts == ["0.0.0.0", "0.0.0.0"]


def test_lan_address_returns_the_routed_local_address(monkeypatch):
    class _FakeUdpSocket:
        def __init__(self, *args):
            pass

        def connect(self, address):
            pass

        def getsockname(self):
            return ("10.9.8.7", 0)

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    fake_socket = types.SimpleNamespace(
        socket=lambda *a: _FakeUdpSocket(),
        AF_INET=socket.AF_INET,
        SOCK_DGRAM=socket.SOCK_DGRAM,
    )
    monkeypatch.setattr(talemate_app, "socket", fake_socket)

    assert talemate_app._lan_address() == "10.9.8.7"


def test_lan_address_falls_back_without_a_route(monkeypatch):
    class _RaisingSocket:
        def __init__(self, *args):
            raise OSError("no route")

    fake_socket = types.SimpleNamespace(
        socket=_RaisingSocket,
        AF_INET=socket.AF_INET,
        SOCK_DGRAM=socket.SOCK_DGRAM,
    )
    monkeypatch.setattr(talemate_app, "socket", fake_socket)

    assert talemate_app._lan_address() == "0.0.0.0"


def test_start_lan_binds_all_interfaces_and_shows_lan_address(
    tmp_path, monkeypatch, tiny_checkout
):
    calls = {}

    def fake_backend_command(copy_root, port, host="127.0.0.1"):
        calls["backend_host"] = host
        return [sys.executable, "-c", "pass"]

    def fake_frontend_command(copy_root, port, host="127.0.0.1"):
        calls["frontend_host"] = host
        return [sys.executable, "-c", "pass"]

    real_frontend_env = talemate_app.frontend_env

    def wrapped_frontend_env(backend_port, host="127.0.0.1"):
        calls["frontend_env_host"] = host
        return real_frontend_env(backend_port, host)

    real_write_vite_config = talemate_app.write_vite_config

    def wrapped_write_vite_config(copy_root, allow_lan=False):
        calls["allow_lan"] = allow_lan
        return real_write_vite_config(copy_root, allow_lan)

    monkeypatch.setattr(talemate_app, "backend_command", fake_backend_command)
    monkeypatch.setattr(talemate_app, "frontend_command", fake_frontend_command)
    monkeypatch.setattr(talemate_app, "frontend_env", wrapped_frontend_env)
    monkeypatch.setattr(talemate_app, "write_vite_config", wrapped_write_vite_config)
    monkeypatch.setattr(talemate_app, "_lan_address", lambda: "10.9.8.7")
    monkeypatch.setattr(talemate_app, "_wait_ready", lambda info, procs, timeout: None)

    info = talemate_app.start(root=tmp_path / "root", lan=True)

    assert calls["backend_host"] == "0.0.0.0"
    assert calls["frontend_host"] == "0.0.0.0"
    assert calls["frontend_env_host"] == "0.0.0.0"
    assert calls["allow_lan"] is True
    assert info.frontend_url == f"http://10.9.8.7:{info.frontend_port}/"
    assert info.backend_ws_url == f"ws://10.9.8.7:{info.backend_port}/ws"


def test_cli_start_passes_lan_flag_through(tmp_path, monkeypatch):
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return talemate_app.AppInfo(
            root=tmp_path,
            backend_port=1,
            frontend_port=2,
            backend_pid=0,
            frontend_pid=0,
            frontend_url="http://10.9.8.7:2/",
            backend_ws_url="ws://10.9.8.7:1/ws",
            log_dir=tmp_path,
        )

    monkeypatch.setattr(talemate_app, "start", fake_start)

    code = talemate_app.main(["start", "--lan", "--root", str(tmp_path)])

    assert code == 0
    assert captured["lan"] is True


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
