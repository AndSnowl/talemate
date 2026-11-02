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
  ``<root>/e2e-fixed-preview.json``, and its ``plan_scene`` and
  ``continue_scene`` from ``<root>/e2e-fixed-setup.json``, never a model.
- ``fixed_preview``: a function that writes that file (``seed.set_fixed_preview``);
  it's removed after the test, so no later test sees a stale preview.
- ``fixed_setup``: the same for the scene setup (``seed.set_fixed_setup``).
- ``fixed_facts``, ``fixed_group_synopsis``, ``fixed_group_add``: the same
  for "+ Add facts…"/"+ Add event…", a group's synopsis and a group's
  "+ Add" (``seed.set_fixed_reply``), each the model's reply.
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
    FIXED_CLEAN_FILE,
    FIXED_FACTS_FILE,
    FIXED_GROUP_ADD_FILE,
    FIXED_GROUP_SYNOPSIS_FILE,
    FIXED_LANGUAGE_FILE,
    FIXED_PREVIEW_FILE,
    FIXED_SETUP_FILE,
    SOCKET_HOOK_JS,
    dismiss_onboarding,
    set_fixed_preview,
    set_fixed_reply,
    set_fixed_setup,
)

# the stand-in for Claude Code (languages 3b-1), and the file its mode is in
FAKE_CLAUDE = Path(__file__).resolve().parents[1] / "languages" / "data" / "fake-claude"
FAKE_CLAUDE_MODE_FILE = "e2e-fake-claude-mode"

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
    # The backend's `preview_thing` and scene setups answer from these
    # files instead of a model (seed.set_fixed_preview and set_fixed_setup
    # write them).
    # Set only for the backend's start: it inherits the environment then.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(root / FIXED_PREVIEW_FILE))
        mp.setenv("TALEMATE_TEST_FIXED_SETUP", str(root / FIXED_SETUP_FILE))
        mp.setenv("TALEMATE_TEST_FIXED_FACTS", str(root / FIXED_FACTS_FILE))
        mp.setenv(
            "TALEMATE_TEST_FIXED_GROUP_SYNOPSIS", str(root / FIXED_GROUP_SYNOPSIS_FILE)
        )
        mp.setenv("TALEMATE_TEST_FIXED_GROUP_ADD", str(root / FIXED_GROUP_ADD_FILE))
        mp.setenv("TALEMATE_TEST_FIXED_LANGUAGE", str(root / FIXED_LANGUAGE_FILE))
        mp.setenv("TALEMATE_TEST_FIXED_CLEAN", str(root / FIXED_CLEAN_FILE))
        # Claude Code is a fake that writes the sample language; its mode per
        # test comes from a file (`fake_claude_mode`)
        mp.setenv("TALEMATE_TEST_CLAUDE_COMMAND", str(FAKE_CLAUDE))
        mp.setenv("FAKE_CLAUDE_MODE_FILE", str(root / FAKE_CLAUDE_MODE_FILE))
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


def _fixed_reply_fixture(file_name: str):
    """A fixture writing the app's fixed reply file `file_name`
    (`seed.set_fixed_reply`), removed after the test."""

    @pytest.fixture()
    def fixture(app):
        path = Path(app.root) / file_name
        try:
            yield lambda reply: set_fixed_reply(app.root, file_name, reply)
        finally:
            path.unlink(missing_ok=True)

    return fixture


fixed_facts = _fixed_reply_fixture(FIXED_FACTS_FILE)
fixed_group_synopsis = _fixed_reply_fixture(FIXED_GROUP_SYNOPSIS_FILE)
fixed_group_add = _fixed_reply_fixture(FIXED_GROUP_ADD_FILE)
fixed_language = _fixed_reply_fixture(FIXED_LANGUAGE_FILE)
fixed_clean = _fixed_reply_fixture(FIXED_CLEAN_FILE)


@pytest.fixture()
def fake_claude_mode(app):
    """Sets the fake Claude Code's mode (`ok`, `reply-only`, `error`,
    `slow`) for this test; `ok` again after it."""

    path = Path(app.root) / FAKE_CLAUDE_MODE_FILE
    try:
        yield lambda mode: path.write_text(mode)
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
