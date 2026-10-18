"""E2E: the isolated runner starts a real backend + frontend from a copy."""

import importlib.util
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "talemate_app", _REPO_ROOT / "scripts" / "dev" / "talemate_app.py"
)
talemate_app = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("talemate_app", talemate_app)
_spec.loader.exec_module(talemate_app)


def _snapshot(*paths: Path) -> dict:
    """Map every file under ``paths`` to its (mtime_ns, contents)."""
    snap = {}
    for path in paths:
        files = [path] if path.is_file() else sorted(path.rglob("*"))
        for f in files:
            if f.is_file():
                snap[str(f)] = (f.stat().st_mtime_ns, f.read_bytes())
    return snap


def _pid_gone(pid: int) -> bool:
    return not os.path.exists(f"/proc/{pid}")


def test_runner_starts_isolated_app(tmp_path, page):
    checkout_config = _REPO_ROOT / "config.yaml"
    checkout_scenes = _REPO_ROOT / "scenes"
    before = _snapshot(checkout_config, checkout_scenes)
    config_existed = checkout_config.exists()

    info = talemate_app.start(root=tmp_path / "app")
    try:
        assert info.root == (tmp_path / "app").resolve()
        assert (info.root / "config.yaml").exists()

        page.goto(info.frontend_url)
        page.locator("header.v-app-bar").wait_for(state="visible", timeout=60_000)

        root_lines = [
            line
            for line in (info.log_dir / "backend.log").read_text().splitlines()
            if "talemate root" in line
        ]
        assert root_lines, "backend did not log its TALEMATE_ROOT"
        assert str(info.root) in root_lines[0]
    finally:
        talemate_app.stop(info.root)

    assert _pid_gone(info.backend_pid)
    assert _pid_gone(info.frontend_pid)
    assert talemate_app.status(info.root) is None
    assert checkout_config.exists() == config_existed
    assert _snapshot(checkout_config, checkout_scenes) == before
