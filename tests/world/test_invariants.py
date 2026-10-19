"""Randomised invariant checks over the world store, with fixed seeds.

Each seed drives a short random history of creations, facts, corrections,
field writes, references, removals and undos (an undo of an undo revision
is a redo), checking after every step that:

- at most one row per thing id, `fact_id` and field slot is live;
- no fact or field value is live on a thing that isn't;
- `index_documents` and `timeline` don't raise.

A revision only ever adds rows or retires live ones, so a view at an older
revision never changes once written; checking the head after each step
covers every revision.

Each seed then undoes a random target revision (trying a few until one
undoes without a conflict), redoes it (undoes the undo) and undoes it again, and checks that the slots the target touched
end up as the first undo left them, and, when nothing touched them between
the target and that undo, as they were just before the target.
"""

import random
import sqlite3

import pytest

from talemate.world.dates import WorldDate
from talemate.world.index import index_documents
from talemate.world.refs import ref
from talemate.world.store import Source, World

SEEDS = range(40)
STEPS = 25
# targets tried per seed until one undoes cleanly (no conflict, not a no-op)
TARGET_TRIES = 5
DATES = [None] + [WorldDate.of(year) for year in (290, 300, 310)]

_LIVE = "rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)"


def _check_invariants(world: World) -> None:
    conn = world._conn
    head = world.head_rev()
    at_head = (head, head)

    for table, key in (
        ("things", "id"),
        ("facts", "fact_id"),
        ("field_values", "thing_id, field, valid_from"),
    ):
        duplicates = conn.execute(
            f"SELECT {key} FROM {table} WHERE {_LIVE} "
            f"GROUP BY {key} HAVING COUNT(*) > 1",
            at_head,
        ).fetchall()
        assert not duplicates, (
            f"two live {table} rows",
            [tuple(r) for r in duplicates],
        )

    for table in ("facts", "field_values"):
        orphans = conn.execute(
            f"SELECT x.row_id FROM {table} x "
            f"WHERE x.rev_added <= ? AND (x.rev_removed IS NULL OR x.rev_removed > ?) "
            "AND NOT EXISTS (SELECT 1 FROM things t WHERE t.id = x.thing_id "
            "AND t.rev_added <= ? AND (t.rev_removed IS NULL OR t.rev_removed > ?))",
            at_head + at_head,
        ).fetchall()
        assert not orphans, (f"{table} rows live on a thing that isn't", orphans)

    index_documents(world, head)
    for thing in world.view(rev=head).things():
        world.timeline(thing.id, head)


def _touched_slots(conn: sqlite3.Connection, rev: int) -> dict[str, set]:
    """Every slot `rev` added a row to or retired a row from."""

    changed = "rev_added = ? OR rev_removed = ?"
    return {
        "things": {
            row[0]
            for row in conn.execute(
                f"SELECT id FROM things WHERE {changed}", (rev, rev)
            )
        },
        "facts": {
            row[0]
            for row in conn.execute(
                f"SELECT fact_id FROM facts WHERE {changed}", (rev, rev)
            )
        },
        "field_values": {
            tuple(row)
            for row in conn.execute(
                f"SELECT thing_id, field, valid_from FROM field_values WHERE {changed}",
                (rev, rev),
            )
        },
    }


def _slot_state(conn: sqlite3.Connection, slots: dict[str, set], rev: int) -> dict:
    """What each slot holds at `rev`: whether the thing is live, and the
    live fact's or field value's content (`None` when nothing is live)."""

    state = {}
    for thing_id in slots["things"]:
        row = conn.execute(
            f"SELECT kind FROM things WHERE id = ? AND {_LIVE}", (thing_id, rev, rev)
        ).fetchone()
        state[("things", thing_id)] = None if row is None else row[0]
    for fact_id in slots["facts"]:
        row = conn.execute(
            "SELECT thing_id, category, text, valid_from, valid_until FROM facts "
            f"WHERE fact_id = ? AND {_LIVE}",
            (fact_id, rev, rev),
        ).fetchone()
        state[("facts", fact_id)] = None if row is None else tuple(row)
    for thing_id, field, valid_from in slots["field_values"]:
        row = conn.execute(
            "SELECT value_json, from_precision FROM field_values "
            f"WHERE thing_id = ? AND field = ? AND valid_from IS ? AND {_LIVE}",
            (thing_id, field, valid_from, rev, rev),
        ).fetchone()
        state[("field_values", thing_id, field, valid_from)] = (
            None if row is None else tuple(row)
        )
    return state


def _random_step(world: World, rnd: random.Random, step: int) -> None:
    view = world.view()
    things = [thing.id for thing in view.things()]
    facts = [fact.fact_id for thing in view.things() for fact in thing.facts]
    source = Source.scene("s", rnd.choice("EF"), f"m{step}")
    op = rnd.random()

    if op < 0.25 or not things:
        with world.revision(source) as rev:
            rev.create_thing(
                "character", {"name": f"n{step}"}, valid_from=rnd.choice(DATES)
            )
    elif op < 0.42:
        with world.revision(source) as rev:
            text = f"fact {step}"
            if rnd.random() < 0.3:
                text += f" {ref(rnd.choice(things))}"
            rev.add_fact(rnd.choice(things), "appearance", text, rnd.choice(DATES[:2]))
    elif op < 0.50 and facts:
        with world.revision(source) as rev:
            rev.correct_fact(rnd.choice(facts), text=f"corrected {step}")
    elif op < 0.58:
        with world.revision(source) as rev:
            rev.set_field(rnd.choice(things), "name", f"x{step}", rnd.choice(DATES))
    elif op < 0.63:
        with world.revision(source) as rev:
            rev.set_field(rnd.choice(things), "culture", rnd.choice(things), None)
    elif op < 0.70 and facts:
        with world.revision(source) as rev:
            rev.remove_fact(rnd.choice(facts))
    elif op < 0.78:
        with world.revision(source) as rev:
            rev.remove_thing(rnd.choice(things))
    else:
        head = world.head_rev()
        revs = rnd.sample(range(1, head + 1), min(rnd.choice([1, 2, 3]), head))
        if rnd.random() < 0.3:
            revs = [r.rev for r in world.revisions(branch_id=rnd.choice("EF"))]
        world.undo(revs)


def _check_undo_redo_undo(world: World, target: int) -> bool:
    """Undo, redo and undo `target` again. Returns `False`, checking
    nothing more, when the first undo reverts nothing or lists a
    conflict."""

    conn = world._conn
    slots = _touched_slots(conn, target)

    first = world.undo([target])
    _check_invariants(world)
    if first.undo_rev is None or first.conflicts:
        return False
    before_undo = _slot_state(conn, slots, first.undo_rev - 1)
    after_undo = _slot_state(conn, slots, first.undo_rev)

    redo = world.undo([first.undo_rev])
    _check_invariants(world)
    assert redo.conflicts == []
    assert _slot_state(conn, slots, world.head_rev()) == before_undo

    again = world.undo([target])
    _check_invariants(world)
    assert again.conflicts == []
    assert again.undo_rev is not None
    assert _slot_state(conn, slots, world.head_rev()) == after_undo

    untouched_since = _slot_state(conn, slots, target) == before_undo
    if untouched_since:
        assert after_undo == _slot_state(conn, slots, target - 1)
    return True


@pytest.mark.parametrize("seed", SEEDS)
def test_random_history_keeps_invariants(tmp_path, seed):
    rnd = random.Random(seed)
    world = World.create("fuzz", root=tmp_path)
    try:
        for step in range(STEPS):
            _random_step(world, rnd, step)
            _check_invariants(world)
        candidates = [r.rev for r in world.revisions() if r.source.kind != "undo"]
        for target in rnd.sample(candidates, min(TARGET_TRIES, len(candidates))):
            if _check_undo_redo_undo(world, target):
                break
    finally:
        world.close()
