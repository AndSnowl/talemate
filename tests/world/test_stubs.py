"""The stub marker, and changing a stub's kind."""

import pytest

from talemate.world.replay import History, Replay
from talemate.world.store import Source


def _check_replay(world) -> None:
    """Every slot's live row is the one a full replay says it holds."""

    history = History(world._conn)
    history.load()
    replay = Replay(history)
    for slot in history.slots():
        want = replay.live(slot)
        have = history.live_origin(slot)
        assert (None if want is None else want["row_id"]) == (
            None if have is None else have["row_id"]
        ), slot


def _lore_stub(world):
    with world.revision(Source.manual()) as rev:
        stub = rev.create_thing(
            "lore",
            fields={
                "name": "Frosthollow",
                "aka": [{"name": "the Hollow", "tag": "common", "everyday": True}],
                "stub": {"ignored": False},
            },
        )
        fact = rev.add_fact(stub, "general", "A cold valley.")
        entry = rev.create_thing("lore", fields={"name": "The Owl Guard"})
    return stub, fact, entry


def test_stub_marker_and_kind_change(world):
    stub, fact, entry = _lore_stub(world)

    view = world.view()
    assert view.thing(stub).is_stub
    assert not view.thing(stub).stub_ignored
    assert not view.thing(entry).is_stub

    with world.revision(Source.manual()) as rev:
        rev.change_stub_kind(stub, "place")
        kind_rev = rev.rev

    state = world.view().thing(stub)
    assert state.kind == "place"
    assert state.is_stub
    assert state.fields["name"] == "Frosthollow"
    assert state.fields["aka"] == [
        {"name": "the Hollow", "tag": "common", "everyday": True}
    ]
    assert [f.fact_id for f in state.facts] == [fact]
    # the old revision still sees the lore kind
    assert world.view(rev=kind_rev - 1).thing(stub).kind == "lore"
    _check_replay(world)

    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind(entry, "place")

    report = world.undo([kind_rev])
    assert report.conflicts == []
    state = world.view().thing(stub)
    assert state.kind == "lore"
    assert [f.fact_id for f in state.facts] == [fact]
    _check_replay(world)

    # redo (undo the undo) brings the place back
    world.undo([report.undo_rev])
    assert world.view().thing(stub).kind == "place"
    _check_replay(world)


def test_stub_ignored_flag(world):
    with world.revision(Source.manual()) as rev:
        stub = rev.create_thing(
            "character", fields={"name": "Aldric", "stub": {"ignored": True}}
        )
    state = world.view().thing(stub)
    assert state.is_stub
    assert state.stub_ignored


def test_change_stub_kind_refuses_bad_changes(world):
    stub, _, _ = _lore_stub(world)
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind(stub, "magic")
    # a lore "general" fact has nowhere to go on a character
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind(stub, "character")
    with pytest.raises(KeyError):
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind("0" * 32, "place")
    assert world.view().thing(stub).kind == "lore"


def test_change_stub_kind_no_longer_a_stub(world):
    stub, _, _ = _lore_stub(world)
    with world.revision(Source.manual()) as rev:
        rev.remove_field_value(stub, "stub", None)
    assert not world.view().thing(stub).is_stub
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind(stub, "place")


def test_undo_creation_after_kind_change_is_a_conflict(world):
    with world.revision(Source.manual()) as rev:
        stub = rev.create_thing(
            "lore", fields={"name": "Frosthollow", "stub": {"ignored": False}}
        )
        create_rev = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.change_stub_kind(stub, "place")

    report = world.undo([create_rev])
    assert [c.table for c in report.conflicts] == ["things"]
    assert world.view().thing(stub).kind == "place"
    _check_replay(world)


def test_undo_kind_change_kept_when_later_rows_need_the_new_kind(world):
    stub, _, entry = _lore_stub(world)
    with world.revision(Source.manual()) as rev:
        rev.change_stub_kind(stub, "place")
        kind_rev = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.add_fact(stub, "description", "Snow all year.")
        fact_rev = rev.rev

    # a lore can't hold a "description" fact, so the place kind stays
    report = world.undo([kind_rev])
    assert [(c.table, c.later_rev) for c in report.conflicts] == [("things", fact_rev)]
    assert world.view().thing(stub).kind == "place"
    _check_replay(world)

    # undoing both together reverses both
    world.undo([kind_rev, fact_rev])
    state = world.view().thing(stub)
    assert state.kind == "lore"
    assert [f.category for f in state.facts] == ["general"]
    _check_replay(world)


def test_undo_kind_change_kept_when_a_later_field_needs_the_new_kind(world):
    stub, _, _ = _lore_stub(world)
    with world.revision(Source.manual()) as rev:
        parent = rev.create_thing("place", fields={"name": "The North"})
    with world.revision(Source.manual()) as rev:
        rev.change_stub_kind(stub, "place")
        kind_rev = rev.rev
    with world.revision(Source.manual()) as rev:
        rev.set_field(stub, "parent", parent, None)

    report = world.undo([kind_rev])
    assert [c.thing_id for c in report.conflicts] == [stub]
    assert world.view().thing(stub).kind == "place"
    _check_replay(world)
