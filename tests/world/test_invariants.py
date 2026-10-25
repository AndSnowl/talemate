"""Randomised invariant checks over the world store, with fixed seeds.

Each seed drives a short random history of creations, facts, corrections,
field writes, references, removals, undos (an undo of an undo revision is a
redo) and manual writes that bring back a value or text the same slot held
before (so identical content keeps turning up in unrelated revisions),
checking after every step that:

- at most one row per thing id, `fact_id` and field slot is live;
- no fact or field value is live on a thing that isn't;
- every slot holds what a full replay says (`talemate.world.replay`): the
  latest write among the non-undo revisions in effect for it, by the
  reversal links and the conflicts each undo recorded, and a value or fact
  only while its thing is live. A live restored copy counts as the row its
  `restored_from` chain leads back to;
- `index_documents` and `timeline` don't raise.

A revision only ever adds rows or retires live ones, so a view at an older
revision never changes once written; checking the head after each step
covers every revision.

Each seed then re-undoes the targets of every undo that wrote a revision,
unless an undo of one of them has since been redone, and checks that this
changes no live row outside the slots and things that undo recorded a
conflict on: everywhere else the targets' changes are already reverted,
whatever has happened since.

Each seed then undoes a random target revision (trying a few until one
undoes without a conflict), redoes it (undoes the undo) and undoes it
again, and checks that the slots the target touched end up as the first
undo left them, and as they were before the first undo after the redo.

Thing and fact ids come from `uuid4`, and things are picked from a list in
id order, so the test seeds `uuid4` too: each seed replays exactly.
"""

import json
import random
import sqlite3
import uuid

import pytest

from talemate.world.dates import WorldDate
from talemate.world.index import index_documents
from talemate.world.refs import ref
from talemate.world.replay import History, Replay
from talemate.world import store
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

    _check_replay(world)

    index_documents(world, head)
    for thing in world.view(rev=head).things():
        world.timeline(thing.id, head)


def _check_replay(world: World) -> None:
    """Every slot's live row stands for the write a full replay says it
    should hold (compared by row, never by content). The replay trusts the
    conflicts each undo recorded in `undo_conflicts`, so this can't catch an
    undo that reports more conflicts than it should: only the unit tests in
    `test_undo.py` catch over-reporting."""

    history = History(world._conn)
    history.load()
    replay = Replay(history)
    wrong = []
    for slot in history.slots():
        want = replay.live(slot)
        have = history.live_origin(slot)
        want_id = None if want is None else want["row_id"]
        have_id = None if have is None else have["row_id"]
        if want_id != have_id:
            wrong.append((slot, "want", want_id, "have", have_id))
    assert not wrong, ("slots that differ from a replay", wrong)


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


def _live_rows(conn: sqlite3.Connection) -> set[tuple[str, int]]:
    return {
        (table, row[0])
        for table in ("things", "field_values", "facts")
        for row in conn.execute(f"SELECT row_id FROM {table} WHERE rev_removed IS NULL")
    }


def _rewrite_earlier_content(world: World, rnd: random.Random, source) -> None:
    """A hand write of a value or text its slot held at some earlier
    revision: a live fact gets an earlier version's text back, or a live
    field value an earlier value."""

    conn = world._conn
    if rnd.random() < 0.5:
        rows = conn.execute(
            "SELECT DISTINCT live.fact_id, old.text FROM facts live "
            "JOIN facts old ON old.fact_id = live.fact_id "
            "WHERE live.rev_removed IS NULL AND old.text != live.text"
        ).fetchall()
        if rows:
            fact_id, text = rnd.choice(rows)
            try:
                with world.revision(source) as rev:
                    rev.correct_fact(fact_id, text=text)
            except ValueError:
                # the old text references a thing that's gone now
                pass
            return
    rows = conn.execute(
        "SELECT DISTINCT live.thing_id, live.valid_from, live.from_precision, "
        "old.value_json FROM field_values live "
        "JOIN field_values old ON old.thing_id = live.thing_id "
        "AND old.field = live.field AND old.valid_from IS live.valid_from "
        "WHERE live.field = 'name' AND live.rev_removed IS NULL "
        "AND old.value_json != live.value_json"
    ).fetchall()
    if rows:
        thing_id, instant, precision, value_json = rnd.choice(rows)
        valid_from = (
            None if instant is None else WorldDate(instant=instant, precision=precision)
        )
        with world.revision(source) as rev:
            rev.set_field(thing_id, "name", json.loads(value_json), valid_from)


def _random_step(
    world: World, rnd: random.Random, step: int, undos: dict[int, list[int]]
) -> None:
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
            rev.set_field(rnd.choice(things), "heritage", rnd.choice(things), None)
    elif op < 0.70 and facts:
        with world.revision(source) as rev:
            rev.remove_fact(rnd.choice(facts))
    elif op < 0.76:
        with world.revision(source) as rev:
            rev.remove_thing(rnd.choice(things))
    elif op < 0.84:
        _rewrite_earlier_content(world, rnd, Source.manual())
    else:
        head = world.head_rev()
        revs = rnd.sample(range(1, head + 1), min(rnd.choice([1, 2, 3]), head))
        if rnd.random() < 0.3:
            revs = [r.rev for r in world.revisions(branch_id=rnd.choice("EF"))]
        report = world.undo(revs)
        if report.undo_rev is not None:
            undos[report.undo_rev] = revs


def _slot_of(conn: sqlite3.Connection, table: str, row_id: int) -> tuple:
    """`(slot key, thing id)` for one row."""

    if table == "things":
        (thing_id,) = conn.execute(
            "SELECT id FROM things WHERE row_id = ?", (row_id,)
        ).fetchone()
        return ("things", thing_id), thing_id
    if table == "facts":
        fact_id, thing_id = conn.execute(
            "SELECT fact_id, thing_id FROM facts WHERE row_id = ?", (row_id,)
        ).fetchone()
        return ("facts", fact_id), thing_id
    thing_id, field, valid_from = conn.execute(
        "SELECT thing_id, field, valid_from FROM field_values WHERE row_id = ?",
        (row_id,),
    ).fetchone()
    return ("field_values", thing_id, field, valid_from), thing_id


def _check_reundo_is_noop(world: World, undos: dict[int, list[int]]) -> None:
    """Re-undo each undo's targets, unless an undo of any of them has since
    been redone (which puts that target's change back in effect). Only the
    slots, and things, the undo recorded a conflict on may change."""

    conn = world._conn
    reverts = conn.execute("SELECT undo_rev, target_rev FROM revision_reverts")
    undone_in: dict[int, set[int]] = {}
    for undo_rev, target_rev in reverts:
        undone_in.setdefault(target_rev, set()).add(undo_rev)
    for undo_rev, revs in undos.items():
        undos_of = set().union(*(undone_in.get(rev, set()) for rev in revs))
        if any(other in undone_in for other in undos_of):
            continue
        exempt_slots, exempt_things = set(), set()
        for table, row_id in conn.execute(
            "SELECT table_name, row_id FROM undo_conflicts WHERE undo_rev = ?",
            (undo_rev,),
        ).fetchall():
            slot, thing_id = _slot_of(conn, table, row_id)
            exempt_slots.add(slot)
            if table == "things":
                exempt_things.add(thing_id)

        live = _live_rows(conn)
        report = world.undo(revs)
        _check_replay(world)
        for table, row_id in live ^ _live_rows(conn):
            slot, thing_id = _slot_of(conn, table, row_id)
            assert slot in exempt_slots or thing_id in exempt_things, (
                undo_rev,
                revs,
                report,
                slot,
            )


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
    return True


@pytest.mark.parametrize("seed", SEEDS)
def test_random_history_keeps_invariants(tmp_path, monkeypatch, seed):
    ids = random.Random(-seed - 1)
    monkeypatch.setattr(
        store.uuid, "uuid4", lambda: uuid.UUID(int=ids.getrandbits(128))
    )
    rnd = random.Random(seed)
    world = World.create("fuzz", root=tmp_path)
    try:
        undos: dict[int, list[int]] = {}
        for step in range(STEPS):
            _random_step(world, rnd, step, undos)
            _check_invariants(world)
        _check_reundo_is_noop(world, undos)
        candidates = [r.rev for r in world.revisions() if r.source.kind != "undo"]
        for target in rnd.sample(candidates, min(TARGET_TRIES, len(candidates))):
            if _check_undo_redo_undo(world, target):
                break
    finally:
        world.close()
