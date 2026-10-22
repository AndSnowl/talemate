import asyncio
import sqlite3

import pytest

from talemate.world.calendar import Calendar, Era
from talemate.world.dates import WorldDate
from talemate.world.store import Source, World


def _raw_connect(world) -> sqlite3.Connection:
    conn = sqlite3.connect(world.path / "world.sqlite")
    conn.row_factory = sqlite3.Row
    return conn


def test_create_and_reopen(tmp_path):
    calendar = Calendar(eras=[Era(name="First Age", start_year=1)])
    world = World.create("Maren's World", root=tmp_path, calendar=calendar)

    world_id = world.id
    name = world.name
    path = world.path
    world.close()

    reopened = World.open(path)
    try:
        assert reopened.id == world_id
        assert reopened.name == name
        assert reopened.calendar.eras[0].name == "First Age"
        assert reopened.head_rev() == 0
    finally:
        reopened.close()


def test_list_skips_non_worlds(tmp_path):
    world = World.create("A World", root=tmp_path)
    world.close()

    (tmp_path / "not-a-world").mkdir()
    (tmp_path / "also-not-a-world.txt").write_text("hello")

    infos = World.list(root=tmp_path)
    assert len(infos) == 1
    assert infos[0].name == "A World"
    assert infos[0].head_rev == 0


def test_open_rejects_newer_schema(tmp_path):
    world = World.create("A World", root=tmp_path)
    path = world.path
    world.close()

    conn = sqlite3.connect(path / "world.sqlite")
    conn.execute("PRAGMA user_version = 99")
    conn.close()

    with pytest.raises(ValueError):
        World.open(path)


def test_revision_numbers_increase_and_record_source(world):
    with world.revision(Source.manual(note="first")) as rev1:
        assert rev1.rev == 1

    with world.revision(
        Source.scene(scene_id="sc1", branch_id="br1", message_id="msg1")
    ) as rev2:
        assert rev2.rev == 2

    assert world.head_rev() == 2

    conn = _raw_connect(world)
    try:
        row = conn.execute(
            "SELECT source_kind, scene_id, branch_id, message_id FROM revisions "
            "WHERE rev = 2"
        ).fetchone()
    finally:
        conn.close()

    assert row["source_kind"] == "scene"
    assert row["scene_id"] == "sc1"
    assert row["message_id"] == "msg1"


def test_set_field_same_date_replaces(world):
    born = WorldDate.of(300)
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        rev.set_field(thing_id, "name", "Maren", born)
        rev.set_field(thing_id, "name", "Maren the Elder", born)

    conn = _raw_connect(world)
    try:
        rows = conn.execute(
            "SELECT value_json FROM field_values "
            "WHERE thing_id = ? AND field = 'name' AND rev_removed IS NULL",
            (thing_id,),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["value_json"] == '"Maren the Elder"'


def test_remove_field_value_retires_live_row(world):
    born = WorldDate.of(300)
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        rev.set_field(thing_id, "name", "Maren", born)

    with world.revision(Source.manual()) as rev:
        rev.remove_field_value(thing_id, "name", born)

    conn = _raw_connect(world)
    try:
        row = conn.execute(
            "SELECT rev_removed FROM field_values "
            "WHERE thing_id = ? AND field = 'name'",
            (thing_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row["rev_removed"] is not None


def test_remove_field_value_rejects_unknown_field(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        with pytest.raises(ValueError):
            rev.remove_field_value(thing_id, "nope", None)


def test_failed_revision_rolls_back(world):
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            thing_id = rev.create_thing("character")
            rev.add_fact(thing_id, "background", "Born in the hills.")
            rev.add_fact(thing_id, "nope", "This should fail.")

    assert world.head_rev() == 0

    conn = _raw_connect(world)
    try:
        count = conn.execute("SELECT COUNT(*) FROM things").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_add_fact_rejects_unknown_reference(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        with pytest.raises(ValueError):
            rev.add_fact(
                thing_id,
                "background",
                "Friends with [[thing:" + "0" * 32 + "]].",
            )


def test_add_fact_rejects_reference_to_removed_thing(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        gone = rev.create_thing("character")
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(gone)

    with world.revision(Source.manual()) as rev:
        with pytest.raises(ValueError):
            rev.add_fact(thing_id, "background", f"Friends with [[thing:{gone}]].")


def test_end_fact_hides_it_from_the_end_date(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        fact_id = rev.add_fact(
            thing_id, "background", "Warden.", valid_from=WorldDate.of(300)
        )
    with world.revision(Source.manual()) as rev:
        rev.end_fact(fact_id, WorldDate.of(310))

    def visible(year):
        state = world.view(at=WorldDate.of(year)).thing(thing_id)
        return fact_id in {f.fact_id for f in state.facts}

    assert visible(309)
    assert not visible(310)
    assert not visible(320)
    assert world.view().thing(thing_id).facts == []


def test_correct_fact_reopens_an_ended_fact(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        fact_id = rev.add_fact(
            thing_id,
            "background",
            "Warden.",
            valid_from=WorldDate.of(300),
            valid_until=WorldDate.of(310),
        )
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(fact_id, valid_until=None)

    facts = world.view().thing(thing_id).facts
    assert [(f.fact_id, f.valid_until) for f in facts] == [(fact_id, None)]
    assert facts[0].valid_from == WorldDate.of(300)
    live = world._conn.execute(
        "SELECT COUNT(*) FROM facts WHERE fact_id = ? AND rev_removed IS NULL",
        (fact_id,),
    ).fetchone()[0]
    assert live == 1


def test_add_fact_rejects_until_before_from(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        with pytest.raises(ValueError):
            rev.add_fact(
                thing_id,
                "background",
                "Had a title.",
                valid_from=WorldDate.of(300),
                valid_until=WorldDate.of(200),
            )


def test_correct_fact_keeps_fact_id(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character")
        fact_id = rev.add_fact(thing_id, "background", "Born in the hills.")

    with world.revision(Source.manual()) as rev:
        rev.correct_fact(fact_id, text="Born in the valley.")

    conn = _raw_connect(world)
    try:
        rows = conn.execute(
            "SELECT text, rev_removed FROM facts WHERE fact_id = ? ORDER BY row_id",
            (fact_id,),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert rows[0]["text"] == "Born in the hills."
    assert rows[0]["rev_removed"] is not None
    assert rows[1]["text"] == "Born in the valley."
    assert rows[1]["rev_removed"] is None


def test_remove_thing_retires_children(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Maren"})
        fact_id = rev.add_fact(thing_id, "background", "Born in the hills.")

    with world.revision(Source.manual()) as rev:
        rev.remove_thing(thing_id)

    conn = _raw_connect(world)
    try:
        field_row = conn.execute(
            "SELECT rev_removed FROM field_values WHERE thing_id = ? AND field = 'name'",
            (thing_id,),
        ).fetchone()
        fact_row = conn.execute(
            "SELECT rev_removed FROM facts WHERE fact_id = ?", (fact_id,)
        ).fetchone()
    finally:
        conn.close()

    assert field_row["rev_removed"] is not None
    assert fact_row["rev_removed"] is not None


def test_revision_rolls_back_on_base_exception(world):
    """A `BaseException` (CancelledError, KeyboardInterrupt, ...) raised
    inside a revision must still roll back the transaction and leave the
    connection free for the next revision, not just an `Exception`."""

    with pytest.raises(asyncio.CancelledError):
        with world.revision(Source.manual()) as rev:
            rev.create_thing("character")
            raise asyncio.CancelledError()

    assert world.head_rev() == 0

    # a later revision must succeed -- it would raise
    # "cannot start a transaction within a transaction" if the first one's
    # BEGIN IMMEDIATE was never rolled back
    with world.revision(Source.manual()) as rev:
        rev.create_thing("character")

    assert world.head_rev() == 1

    conn = _raw_connect(world)
    try:
        count = conn.execute("SELECT COUNT(*) FROM things").fetchone()[0]
    finally:
        conn.close()

    # only the second revision's thing made it in; the first left nothing
    assert count == 1


def test_revision_handle_closed_after_block_raises(world):
    with world.revision(Source.manual()) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Maren"})

    with pytest.raises(RuntimeError):
        rev.set_field(thing_id, "name", "Too late", None)

    conn = _raw_connect(world)
    try:
        rows = conn.execute(
            "SELECT value_json FROM field_values "
            "WHERE thing_id = ? AND field = 'name' AND rev_removed IS NULL",
            (thing_id,),
        ).fetchall()
    finally:
        conn.close()

    # the rejected call didn't sneak a row in outside the transaction
    assert len(rows) == 1
    assert rows[0]["value_json"] == '"Maren"'


def test_present_defaults_to_year_one_and_round_trips(tmp_path):
    world = World.create("Present", root=tmp_path)
    try:
        assert world.present() == WorldDate.of(1)
        world.set_present(WorldDate.of(1000))
        assert world.present() == WorldDate.of(1000)
    finally:
        world.close()

    reopened = World.open(world.path)
    try:
        assert reopened.present() == WorldDate.of(1000)
    finally:
        reopened.close()


def test_correct_fact_moves_a_fact_to_another_thing(world):
    """`correct_fact(thing_id=...)` moves a fact, keeping its id, dates and
    overrides; `origin` replaces its origin. Undo moves it back."""

    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("lore", {"name": "A"})
        b = rev.create_thing("place", {"name": "B"})
        fact_id = rev.add_fact(
            a,
            "general",
            "Ended once.",
            valid_from=WorldDate.of(10),
            valid_until=WorldDate.of(20),
            origin={"drawer": "x"},
        )
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(fact_id, thing_id=b, origin={"tie": a})
    moved = world.live_facts(b)
    assert [(f.fact_id, f.category, f.text) for f in moved] == [
        (fact_id, "general", "Ended once.")
    ]
    assert (moved[0].valid_from, moved[0].valid_until) == (
        WorldDate.of(10),
        WorldDate.of(20),
    )
    assert moved[0].origin == {"tie": a}
    assert world.live_facts(a) == []

    # a category the new thing's kind lacks is refused
    with world.revision(Source.manual()) as rev:
        c = rev.create_thing("character", {"name": "C"})
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(fact_id, thing_id=c)

    world.undo([world.head_rev() - 1])
    assert [f.fact_id for f in world.live_facts(a)] == [fact_id]
    assert world.live_facts(a)[0].origin == {"drawer": "x"}


def test_live_facts_lists_every_date(world):
    with world.revision(Source.manual()) as rev:
        a = rev.create_thing("lore", {"name": "A"})
        rev.add_fact(a, "general", "Now.")
        rev.add_fact(a, "general", "Then.", valid_until=WorldDate.of(5))
        rev.add_fact(a, "general", "Later.", valid_from=WorldDate.of(500))
    assert sorted(f.text for f in world.live_facts(a)) == ["Later.", "Now.", "Then."]
    assert len(world.view(WorldDate.of(100)).thing(a).facts) == 1
