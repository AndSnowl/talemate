"""Shared headless-Chromium setup for the e2e tests and ``look.py``.

Both only work inside the project's Guix dev shell, which supplies Node and
Chromium (``guix shell -m manifest.scm``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Chromium in a container/sandboxed shell: no setuid sandbox, small /dev/shm.
LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]


def chromium_path() -> str | None:
    """Return the Chromium to drive: ``$TALEMATE_CHROMIUM``, else ``chromium`` on PATH."""
    return os.environ.get("TALEMATE_CHROMIUM") or shutil.which("chromium")


def ensure_driver_node() -> None:
    """Point Playwright's driver at the Guix node if its bundled one can't run."""
    node = shutil.which("node")
    if not node:
        return
    pattern = "lib/python*/site-packages/playwright/driver/node"
    for p in (REPO_ROOT / ".venv").glob(pattern):
        try:
            check = subprocess.run([p, "--version"], capture_output=True)
            runnable = check.returncode == 0
        except OSError:
            runnable = False
        if not runnable:
            p.unlink(missing_ok=True)
            p.symlink_to(node)


def launch(playwright, executable_path: str):
    """Launch headless Chromium from ``executable_path`` with the shared args."""
    return playwright.chromium.launch(executable_path=executable_path, args=LAUNCH_ARGS)
