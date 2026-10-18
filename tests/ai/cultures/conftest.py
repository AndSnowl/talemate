"""Fixtures for the cultures AI tests.

``session`` gives each test its own websocket connection to the running
``ai_app`` (the backend allows one frontend connection at a time; this is
function-scoped so the previous test's connection is already closed).
``load_cultures`` reads a seeded world's cultures straight off disk, typed
as `Culture`, for checks (``fits(culture.language, name)``,
``culture.additions``) that need the model, not a raw dict.

Every test seeds its own project (``seed_scenario``'s ``project``), so
tests never share a world and nothing here needs to clean up between them.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from talemate.cultures.models import Culture
from talemate.cultures.store import WorldStore

REPO_ROOT = Path(__file__).resolve().parents[3]


# tests/ai/conftest.py repeats this same loader, for the same reason: the
# driver isn't on sys.path, and importing it from a sibling conftest would
# load it before it's needed.
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


talemate_ws = _load_script("talemate_ws")
BackendSession = talemate_ws.BackendSession


@pytest.fixture
def session(ai_app):
    """A fresh `BackendSession` to the running `ai_app`, closed after the test."""
    with BackendSession(ai_app.backend_ws_url) as backend_session:
        yield backend_session


def load_cultures(world) -> dict[str, Culture]:
    """Read `world`'s cultures straight off disk (`world` is a `SeededWorld`)."""
    return WorldStore(world.world_dir).load_cultures()
