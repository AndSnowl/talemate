"""Browser (e2e) test harness.

These tests drive a real headless Chromium via Playwright. They only run
inside the project's Guix dev shell (which supplies Node + Chromium):

    guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0 -v

Outside that shell (no Chromium on PATH and no TALEMATE_CHROMIUM), every e2e
test is skipped, so the plain suite stays runnable without a browser.
"""

import glob
import os
import pathlib
import shutil
import subprocess

import pytest


def pytest_collection_modifyitems(config, items):
    """Mark every test collected under tests/e2e/ as `e2e`, automatically."""
    for item in items:
        if "tests/e2e" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


def ensure_driver_node() -> None:
    """Point Playwright's driver at the Guix node if its bundled one can't run."""
    node = shutil.which("node")
    if not node:
        return
    for d in glob.glob(".venv/lib/python*/site-packages/playwright/driver/node"):
        runnable = False
        try:
            runnable = (
                subprocess.run([d, "--version"], capture_output=True).returncode == 0
            )
        except OSError:
            runnable = False
        if not runnable:
            p = pathlib.Path(d)
            p.unlink(missing_ok=True)
            p.symlink_to(node)


@pytest.fixture(scope="session")
def chromium_path() -> str:
    path = os.environ.get("TALEMATE_CHROMIUM") or shutil.which("chromium")
    if not path:
        pytest.skip("No Chromium — run inside `guix shell -m manifest.scm`")
    return path


@pytest.fixture(scope="session")
def browser(chromium_path):
    ensure_driver_node()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(
            executable_path=chromium_path,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            yield b
        finally:
            b.close()


@pytest.fixture()
def page(browser):
    yield browser.new_page()
