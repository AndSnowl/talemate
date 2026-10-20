"""`world`: a fresh `World` in a temp directory, same as `tests/world/conftest.py`
(not shared across directories by pytest's fixture scoping, so repeated here)."""

import pytest

from talemate.world.store import World


@pytest.fixture
def world(tmp_path):
    w = World.create("Test World", root=tmp_path)
    yield w
    w.close()
