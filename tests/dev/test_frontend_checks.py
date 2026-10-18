"""Runs the frontend's node-only logic checks (talemate_frontend/checks/)
through pytest, so the plain suite covers them without a browser or a JS
test runner. Skips outside an environment with node and the frontend's
installed dependencies.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "talemate_frontend"


def _frontend_deps_installed() -> bool:
    return (_FRONTEND_DIR / "node_modules" / "marked").exists()


@pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")
@pytest.mark.skipif(
    not _frontend_deps_installed(),
    reason="talemate_frontend/node_modules/marked is missing (pnpm install)",
)
def test_cultures_story_checks():
    result = subprocess.run(
        ["node", "checks/culturesStory.check.mjs"],
        cwd=_FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    )
    assert "ok " in result.stdout, (
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    )
