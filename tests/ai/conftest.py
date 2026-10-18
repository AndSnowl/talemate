"""AI (opt-in) test harness.

These tests call a live koboldcpp instance. They never run by accident:
collection marks every test here `ai` (excluded from the default `addopts`
filter), and a session-scoped autouse fixture additionally skips them
unless TALEMATE_AI_TESTS=1 is set -- before anything here that could touch
the network (``ai_app``) runs, since it's an explicit dependency of that
fixture, not just an autouse sibling.

    TALEMATE_AI_TESTS=1 pytest tests/ai -m ai -n0

Reuses the browser fixtures (``browser``, ``browser_page``) and the
failure-artifact folder from tests/e2e/conftest.py rather than duplicating
them.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

from e2e.conftest import (  # noqa: F401  (re-exported as fixtures for tests/ai)
    ARTIFACTS_DIR,
    _stamp,
    browser,
    browser_page,
    chromium_path,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# e2e/conftest.py repeats this same loader; importing it from there instead
# would pull in `browser`'s session-scoped Playwright state before it's needed.
def _load_script(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / "dev" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ai_helpers = _load_script("ai_helpers")
talemate_app = _load_script("talemate_app")
koboldcpp_url = ai_helpers.koboldcpp_url
koboldcpp_model = ai_helpers.koboldcpp_model


def pytest_collection_modifyitems(config, items):
    """Mark every test collected under tests/ai/ as `ai`, automatically."""
    for item in items:
        if "tests/ai" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.ai)


def pytest_report_header(config):
    """Print the koboldcpp model name -- only when the opt-in is set.

    This hook runs before collection, long before any fixture, so it can't
    read ``ai_app``'s result; it does its own (gated) probe instead. Never
    calls koboldcpp when TALEMATE_AI_TESTS isn't "1", same as the fixture.
    """
    if os.environ.get("TALEMATE_AI_TESTS") != "1":
        return None
    url = koboldcpp_url()
    model = koboldcpp_model(url)
    if model is None:
        return f"koboldcpp: unreachable at {url}"
    return f"koboldcpp model: {model}"


@pytest.fixture(scope="session", autouse=True)
def _require_ai_tests_opt_in():
    if os.environ.get("TALEMATE_AI_TESTS") != "1":
        pytest.skip("AI tests need TALEMATE_AI_TESTS=1 (ask the owner first)")


@pytest.fixture(scope="session")
def ai_app(_require_ai_tests_opt_in, tmp_path_factory):
    """Start the isolated app with a KoboldCpp client, skipping if it's unreachable.

    ``_require_ai_tests_opt_in`` is requested explicitly (not relied on as
    an autouse sibling) so it always runs -- and can skip -- before this
    fixture's own koboldcpp probe.
    """
    url = koboldcpp_url()
    model = koboldcpp_model(url)
    if model is None:
        pytest.skip(f"koboldcpp unreachable at {url}")

    out_dir = ARTIFACTS_DIR / _stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model.txt").write_text(model + "\n")

    info = talemate_app.start(root=tmp_path_factory.mktemp("ai-app"), ai=True)
    try:
        yield info
    finally:
        talemate_app.stop(info.root)
