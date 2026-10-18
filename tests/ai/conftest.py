"""AI (opt-in) test harness.

These tests call a live koboldcpp instance. They never run by accident:
collection marks every test here `ai` (excluded from the default `addopts`
filter), and an autouse fixture additionally skips them unless
TALEMATE_AI_TESTS=1 is set.

    TALEMATE_AI_TESTS=1 pytest tests/ai -m ai -n0
"""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Mark every test collected under tests/ai/ as `ai`, automatically."""
    for item in items:
        if "tests/ai" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.ai)


@pytest.fixture(autouse=True)
def _require_ai_tests_opt_in():
    if os.environ.get("TALEMATE_AI_TESTS") != "1":
        pytest.skip("AI tests need TALEMATE_AI_TESTS=1 (ask the owner first)")
