"""Browser (e2e) test harness.

These tests drive a real headless Chromium via Playwright against an isolated
Talemate app (scripts/dev/talemate_app.py). They only run inside the
project's Guix dev shell (which supplies Node + Chromium):

    guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n 4 -v

(`-n 4`: one isolated app per worker; 4 fits in 31 GB, 8 does not.)

Outside that shell (no Chromium on PATH and no TALEMATE_CHROMIUM), every e2e
test is skipped, so the plain suite stays runnable without a browser.

Fixtures:

- ``app`` (session): one isolated app for the whole run, stopped at the end.
  Its backend answers the `worlds` router's ``preview_thing`` from
  ``<root>/e2e-fixed-preview.json``, its ``plan_scene`` and
  ``continue_scene`` from ``<root>/e2e-fixed-setup.json``, and its
  ``preview_sphere``, ``fill_drawer`` and ``preview_branch`` from
  ``<root>/e2e-fixed-sphere.json``, never a model.
- ``fixed_preview``: a function that writes that file (``seed.set_fixed_preview``);
  it's removed after the test, so no later test sees a stale preview.
- ``fixed_setup``: the same for the scene setup (``seed.set_fixed_setup``).
- ``fixed_sphere``: the same for the sphere replies (``preview_sphere``,
  ``fill_drawer``, ``preview_branch``; ``seed.set_fixed_sphere``).
- ``browser_page``: a fresh browser context and blank page, closed after the test.
- ``page``: ``browser_page`` opened on the app, onboarding wizard dismissed,
  with ``page.console_errors`` collecting console messages of type ``error``.

When a test that used a page fails, a full-page screenshot and the tail of
the app's backend log are saved to
``.test-artifacts/<YYYYmmdd-HHMMSS>/<test-name>/``.
"""

import importlib.util
import re
import sys
import time
from pathlib import Path

import pytest

from e2e.seed import (
    FIXED_PREVIEW_FILE,
    FIXED_SETUP_FILE,
    FIXED_SPHERE_FILE,
    SOCKET_HOOK_JS,
    dismiss_onboarding,
    set_fixed_preview,
    set_fixed_setup,
    set_fixed_sphere,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = REPO_ROOT / ".test-artifacts"
LOG_TAIL_LINES = 200


# seed._load_talemate_app repeats this; seed can't import conftest (circular).
def _load_script(name: str):
    """Import scripts/dev/<name>.py once, under the module name ``name``."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / "dev" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


browser_mod = _load_script("browser")
talemate_app = _load_script("talemate_app")
ensure_driver_node = browser_mod.ensure_driver_node


def pytest_collection_modifyitems(config, items):
    """Mark every test collected under tests/e2e/ as `e2e`, automatically."""
    for item in items:
        if "tests/e2e" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def chromium_path() -> str:
    path = browser_mod.chromium_path()
    if not path:
        pytest.skip("No Chromium — run inside `guix shell -m manifest.scm`")
    return path


@pytest.fixture(scope="session")
def browser(chromium_path):
    ensure_driver_node()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = browser_mod.launch(pw, chromium_path)
        try:
            yield b
        finally:
            b.close()


@pytest.fixture(scope="session")
def app(tmp_path_factory, chromium_path):
    # chromium_path first: without a browser, skip before starting an app.
    root = tmp_path_factory.mktemp("app")
    # The backend's `preview_thing`, scene setups and sphere replies answer
    # from these files instead of a model (seed.set_fixed_preview,
    # set_fixed_setup and set_fixed_sphere write them).
    # Set only for the backend's start: it inherits the environment then.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(root / FIXED_PREVIEW_FILE))
        mp.setenv("TALEMATE_TEST_FIXED_SETUP", str(root / FIXED_SETUP_FILE))
        mp.setenv("TALEMATE_TEST_FIXED_SPHERE", str(root / FIXED_SPHERE_FILE))
        info = talemate_app.start(root=root)
    try:
        yield info
    finally:
        talemate_app.stop(info.root)


@pytest.fixture()
def fixed_preview(app):
    path = Path(app.root) / FIXED_PREVIEW_FILE
    try:
        yield lambda preview: set_fixed_preview(app.root, preview)
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture()
def fixed_setup(app):
    path = Path(app.root) / FIXED_SETUP_FILE
    try:
        yield lambda reply: set_fixed_setup(app.root, reply)
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture()
def fixed_sphere(app):
    path = Path(app.root) / FIXED_SPHERE_FILE
    try:
        yield lambda replies: set_fixed_sphere(app.root, replies)
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture()
def browser_page(browser):
    context = browser.new_context()
    context.add_init_script(SOCKET_HOOK_JS)
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.fixture()
def page(app, browser_page):
    browser_page.console_errors = []

    def on_console(msg):
        if msg.type == "error":
            browser_page.console_errors.append(msg.text)

    browser_page.on("console", on_console)
    browser_page.goto(app.frontend_url)
    # Skips the onboarding wizard if it opens (it does when no AI client).
    dismiss_onboarding(browser_page)
    return browser_page


# --- failure artifacts ------------------------------------------------------

_session_stamp = None


def _stamp() -> str:
    global _session_stamp
    if _session_stamp is None:
        _session_stamp = time.strftime("%Y%m%d-%H%M%S")
    return _session_stamp


def save_failure_artifacts(
    page, log_dir: Path | None, test_name: str, base: Path, stamp: str
) -> Path:
    """Save a full-page screenshot and the backend log's tail; return the folder."""
    out = Path(base) / stamp / re.sub(r"[^A-Za-z0-9_.-]", "_", test_name)
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / "screenshot.png"), full_page=True)
    if log_dir is not None:
        log = Path(log_dir) / "backend.log"
        if log.exists():
            lines = log.read_text(errors="replace").splitlines()[-LOG_TAIL_LINES:]
            (out / "backend.log.tail").write_text("\n".join(lines) + "\n")
    return out


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when not in ("setup", "call") or not report.failed:
        return
    funcargs = getattr(item, "funcargs", {})
    page = funcargs.get("page") or funcargs.get("browser_page")
    if page is None:
        return
    app = funcargs.get("app")
    try:
        out = save_failure_artifacts(
            page,
            getattr(app, "log_dir", None),
            item.name,
            base=ARTIFACTS_DIR,
            stamp=_stamp(),
        )
    except Exception as exc:  # never mask the test's own failure
        report.sections.append(("e2e artifacts", f"could not save: {exc!r}"))
    else:
        report.sections.append(("e2e artifacts", str(out)))
