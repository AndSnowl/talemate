import pytest

from talemate.world.store import World


@pytest.fixture
def world(tmp_path):
    w = World.create("Test World", root=tmp_path)
    yield w
    w.close()
