"""The name lists cleaning uses (languages 4a, Task 1): the app's, shipped
and kept in the config, and each world's own additions and turned-off
rows."""

import pytest

import talemate.config.state as config_state
from talemate.languages.cleaning import lists
from talemate.world.store import World


@pytest.fixture(autouse=True)
def app_config(monkeypatch):
    """The app lists start from the shipped file; saving is a no-op."""

    saved = config_state.get_config().name_lists
    config_state.get_config().name_lists = None
    monkeypatch.setattr(lists, "save_config", lambda: None)
    yield
    config_state.get_config().name_lists = saved


@pytest.fixture
def world(tmp_path):
    return World.create("Lists", root=tmp_path / "w")


def test_app_lists_ship_with_the_probes_names():
    app = lists.app_lists()
    assert "Novgorod" in app.real
    assert "Elara" in app.cliche
    assert "Free Cities of the *" in app.title
    assert app.keep == []


def test_match_ignores_case_article_and_possessive():
    names = lists.NameLists(real=["Volga"])
    assert lists.match(names, "real", "the volga's")
    assert not lists.match(names, "real", "Volgarov")


def test_title_shapes_match_with_a_wildcard():
    names = lists.NameLists(title=["Free Cities of the *"])
    assert lists.match(names, "title", "Free Cities of the Southern Coast")
    assert not lists.match(names, "title", "Free Provinces of Sorau")


def test_a_world_row_adds_and_an_off_row_hides(world):
    lists.edit(world, "add", "real", "Yelena")
    lists.edit(world, "turn_off", "real", "Moscow")
    names = lists.effective(world)
    assert "Yelena" in names.real
    assert "Moscow" not in names.real
    assert "Novgorod" in names.real
    rows = {(r.name, r.scope, r.off) for r in lists.rows(world) if r.kind == "real"}
    assert ("Yelena", "world", False) in rows
    assert ("Moscow", "app", True) in rows


def test_make_global_moves_a_world_row_to_the_app(world):
    lists.edit(world, "add", "keep", "Kiev")
    lists.edit(world, "make_global", "keep", "Kiev")
    assert "Kiev" in lists.app_lists().keep
    assert "Kiev" not in world.name_lists().keep
    assert [r.scope for r in lists.rows(world) if r.name == "Kiev"] == ["app"]


def test_remove_everywhere_drops_an_app_row_and_its_off_marks(world):
    lists.edit(world, "turn_off", "real", "Moscow")
    lists.edit(world, "remove_everywhere", "real", "Moscow")
    assert "Moscow" not in lists.app_lists().real
    assert world.name_lists().off == []


def test_an_unknown_action_or_kind_is_refused(world):
    with pytest.raises(ValueError):
        lists.edit(world, "explode", "real", "Moscow")
    with pytest.raises(ValueError):
        lists.edit(world, "add", "fruit", "Apple")
    assert world.name_lists() == lists.WorldNameLists()
