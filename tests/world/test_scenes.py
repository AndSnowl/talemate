import sqlite3

import pytest

from talemate.world import schema
from talemate.world.dates import WorldDate
from talemate.world.scenes import MessageRecord


def _v1_connection() -> sqlite3.Connection:
    """A database stuck at schema version 1, built from the first
    migration's own statements (not a saved fixture file, since the DDL is
    right here and small)."""

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("BEGIN IMMEDIATE")
    for statement in schema._statements(schema.MIGRATIONS[0]):
        conn.execute(statement)
    conn.execute("PRAGMA user_version = 1")
    conn.execute("COMMIT")
    return conn


def test_migration_2_from_v1():
    conn = _v1_connection()

    schema.apply(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    for table in ("scenes", "scene_messages", "scene_things", "prose_cache"):
        # raises if the table doesn't exist
        conn.execute(f"SELECT * FROM {table}")


def test_scene_create_get_list(world):
    scenes = world.scenes()

    id1 = scenes.create(
        "First Scene", WorldDate.of(300), premise="A storm", goal="Reach the keep"
    )
    id2 = scenes.create("Second Scene", WorldDate.of(305))

    got = scenes.get(id1)
    assert got is not None
    assert got.id == id1
    assert got.name == "First Scene"
    assert got.start == WorldDate.of(300)
    assert got.premise == "A storm"
    assert got.goal == "Reach the keep"
    assert got.player_thing_id is None
    assert got.state == {}
    assert got.continued_from is None

    assert scenes.get("no-such-scene") is None

    before_rename = scenes.get(id1)
    scenes.update(id1, name="Renamed Scene", state={"turn": 2})
    after_rename = scenes.get(id1)
    assert after_rename is not None
    assert after_rename.name == "Renamed Scene"
    assert after_rename.state == {"turn": 2}
    assert after_rename.updated_at > before_rename.updated_at

    listed = scenes.list()
    assert [s.id for s in listed] == [id1, id2]

    with pytest.raises(ValueError):
        scenes.update(id1, start=WorldDate.of(310))

    with pytest.raises(KeyError):
        scenes.update("no-such-scene", name="x")


def test_replace_messages_is_atomic(world):
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(320))

    first = [
        MessageRecord(id="m1", seq=0, kind="narration", data={"text": "It begins."}),
        MessageRecord(id="m2", seq=1, kind="say", data={"text": "Hello."}),
    ]
    scenes.replace_messages(scene_id, first)
    assert [m.id for m in scenes.messages(scene_id)] == ["m1", "m2"]

    # a record whose `kind` is missing at the DB level (NOT NULL) should
    # roll back the whole batch, leaving the earlier messages untouched
    bad = [
        MessageRecord(id="m3", seq=0, kind="narration", data={"text": "Redo."}),
        MessageRecord.model_construct(
            id="m4", seq=1, kind=None, data={"text": "boom"}, elapsed="PT0S"
        ),
    ]
    with pytest.raises(sqlite3.IntegrityError):
        scenes.replace_messages(scene_id, bad)

    assert [m.id for m in scenes.messages(scene_id)] == ["m1", "m2"]


def test_scene_local_things(world):
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(320))

    assert scenes.local_things(scene_id) == []

    things = [
        {"local_id": "l1", "kind": "npc", "data": {"name": "A guard"}},
        {"local_id": "l2", "kind": "prop", "data": {"name": "A lantern"}},
    ]
    scenes.set_local_things(scene_id, things)
    assert scenes.local_things(scene_id) == things

    # replaces wholesale
    scenes.set_local_things(scene_id, things[:1])
    assert scenes.local_things(scene_id) == things[:1]


def test_latest_end(world):
    scenes = world.scenes()
    assert scenes.latest_end() is None

    id1 = scenes.create("A", WorldDate.of(300))
    scenes.replace_messages(
        id1,
        [MessageRecord(id="m1", seq=0, kind="narration", data={}, elapsed="P1D")],
    )

    id2 = scenes.create("B", WorldDate.of(290))
    scenes.replace_messages(
        id2,
        [MessageRecord(id="m2", seq=0, kind="narration", data={}, elapsed="P10D")],
    )

    # scene A starts later than scene B even accounting for B's longer
    # elapsed time, so A's end is the latest
    assert scenes.latest_end() == WorldDate.of(300).plus("P1D")


def test_save_writes_all_or_nothing_and_keeps_other_local_kinds(world):
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(320))
    scenes.set_local_things(
        scene_id,
        [
            {"local_id": "c" * 32, "kind": "character", "data": {"name": "Old"}},
            {"local_id": "p" * 32, "kind": "place", "data": {"name": "A shed"}},
        ],
    )

    scenes.save(
        scene_id,
        fields={"name": "Renamed", "state": {"k": 1}},
        messages=[MessageRecord(id="m1", seq=0, kind="narrator", data={})],
        local_things=[
            {"local_id": "d" * 32, "kind": "character", "data": {"name": "New"}}
        ],
        local_kinds={"character"},
    )

    record = scenes.get(scene_id)
    assert (record.name, record.state) == ("Renamed", {"k": 1})
    assert [m.id for m in scenes.messages(scene_id)] == ["m1"]
    assert [(t["local_id"], t["kind"]) for t in scenes.local_things(scene_id)] == [
        ("d" * 32, "character"),
        ("p" * 32, "place"),
    ]

    # a bad message rolls back the field update and the local things too
    bad = MessageRecord.model_construct(
        id="m2", seq=0, kind=None, data={}, elapsed="PT0S"
    )
    with pytest.raises(sqlite3.IntegrityError):
        scenes.save(
            scene_id,
            fields={"name": "Never"},
            messages=[bad],
            local_things=[],
            local_kinds={"character"},
        )
    assert scenes.get(scene_id).name == "Renamed"
    assert [m.id for m in scenes.messages(scene_id)] == ["m1"]
    assert len(scenes.local_things(scene_id)) == 2

    # a local thing of a kind that isn't being replaced is refused
    with pytest.raises(ValueError):
        scenes.save(
            scene_id,
            fields={},
            messages=[],
            local_things=[{"local_id": "x" * 32, "kind": "place", "data": {}}],
            local_kinds={"character"},
        )
