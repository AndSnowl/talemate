"""Per-slot replay: which revisions are in effect, and what each slot holds.

A slot is where at most one row is live at a time: a thing id, a field
value's `(thing_id, field, valid_from)` (a NULL `valid_from` equal to NULL)
or a fact's `fact_id`. A revision *writes* a slot when it adds or retires a
row there. What a non-undo revision writes is the row it left live there, or
nothing (a retirement, including the values and facts a `remove_thing`
retires along with the thing).

Whether a revision is in effect is decided per (revision, slot), from the
reversal links alone: a revision is in effect for a slot unless an undo that
is itself in effect for that slot reverts it (`revision_reverts`) and didn't
record a conflict blocking that slot (`undo_conflicts`). A conflict on a
thing blocks the thing's slot and the slots of all its values and facts.

A slot then holds the latest write, by rev, among the non-undo revisions in
effect for it. Undo revisions never count as writes of their own: they only
change what's in effect, and a row they restore is a copy whose
`restored_from` chain leads back to the write it stands for. A value or fact
is only live while its thing is.

`undo.py` plans an undo by replaying the slots it can affect with the new
undo added, and the invariant tests check every slot of a world against a
full replay.
"""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import structlog

log = structlog.get_logger("talemate.world.replay")

Table = Literal["things", "field_values", "facts"]
TABLES: tuple[Table, ...] = ("things", "field_values", "facts")

# ("things", id) | ("field_values", thing_id, field, valid_from) |
# ("facts", fact_id)
Slot = tuple

# SQLite's default limit on bound parameters is 999 in older builds
_CHUNK = 500


def slot_of(table: Table, row: sqlite3.Row) -> Slot:
    if table == "things":
        return ("things", row["id"])
    if table == "facts":
        return ("facts", row["fact_id"])
    return ("field_values", row["thing_id"], row["field"], row["valid_from"])


def thing_slot(thing_id: str) -> Slot:
    return ("things", thing_id)


def _chunks(values: list) -> Iterable[list]:
    for start in range(0, len(values), _CHUNK):
        yield values[start : start + _CHUNK]


@dataclass(frozen=True)
class Write:
    """What one non-undo revision left in a slot: `row`, or nothing."""

    rev: int
    row: sqlite3.Row | None


class History:
    """The reversal links of a world, plus the rows of the slots loaded into
    it, read once from the database."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.undo_revs: set[int] = {
            row[0]
            for row in conn.execute(
                "SELECT rev FROM revisions WHERE source_kind = 'undo'"
            )
        }

        self.reverts: dict[int, set[int]] = {}
        self.reverted_by: dict[int, set[int]] = {}
        for undo_rev, target_rev in conn.execute(
            "SELECT undo_rev, target_rev FROM revision_reverts"
        ):
            self.reverts.setdefault(undo_rev, set()).add(target_rev)
            self.reverted_by.setdefault(target_rev, set()).add(undo_rev)

        # the slots, and things, each undo recorded a conflict on
        self.blocked_slots: dict[int, set[Slot]] = {}
        self.blocked_things: dict[int, set[str]] = {}
        for table in TABLES:
            for row in conn.execute(
                f"SELECT uc.undo_rev AS conflict_undo_rev, x.* FROM undo_conflicts uc "
                f"JOIN {table} x ON x.row_id = uc.row_id WHERE uc.table_name = ?",
                (table,),
            ):
                undo_rev = row["conflict_undo_rev"]
                self.blocked_slots.setdefault(undo_rev, set()).add(slot_of(table, row))
                if table == "things":
                    self.blocked_things.setdefault(undo_rev, set()).add(row["id"])

        self.rows: dict[Slot, list[sqlite3.Row]] = {}
        self._thing_ids: dict[Slot, str] = {}
        self._writes: dict[Slot, list[Write]] = {}

    # -- which slots ---------------------------------------------------------

    def closure(self, revs: Iterable[int]) -> set[int]:
        """`revs`, plus every revision an undo among them reverts,
        recursively: the revisions whose being in effect an undo of `revs`
        can change."""

        result: set[int] = set()
        pending = list(revs)
        while pending:
            rev = pending.pop()
            if rev in result:
                continue
            result.add(rev)
            pending.extend(self.reverts.get(rev, ()))
        return result

    def touched_slots(self, revs: Iterable[int]) -> dict[Slot, None]:
        """Every slot one of `revs` added a row to or retired a row from,
        in `row_id` order per table."""

        revs = sorted(set(revs))
        slots: dict[Slot, None] = {}
        for table in TABLES:
            for chunk in _chunks(revs):
                placeholders = ",".join("?" for _ in chunk)
                for row in self.conn.execute(
                    f"SELECT * FROM {table} WHERE rev_added IN ({placeholders}) "
                    f"OR rev_removed IN ({placeholders}) ORDER BY row_id",
                    chunk + chunk,
                ):
                    slots.setdefault(slot_of(table, row), None)
        return slots

    def child_slots(self, thing_ids: Iterable[str]) -> dict[Slot, None]:
        """Every field value and fact slot that belongs to one of
        `thing_ids`."""

        thing_ids = sorted(set(thing_ids))
        slots: dict[Slot, None] = {}
        for table in ("field_values", "facts"):
            for chunk in _chunks(thing_ids):
                placeholders = ",".join("?" for _ in chunk)
                for row in self.conn.execute(
                    f"SELECT * FROM {table} WHERE thing_id IN ({placeholders}) "
                    "ORDER BY row_id",
                    chunk,
                ):
                    slots.setdefault(slot_of(table, row), None)
        return slots

    # -- loading -------------------------------------------------------------

    def _add(self, table: Table, row: sqlite3.Row) -> None:
        slot = slot_of(table, row)
        self.rows.setdefault(slot, []).append(row)
        self._thing_ids[slot] = row["id"] if table == "things" else row["thing_id"]

    def load(self, slots: Iterable[Slot] | None = None) -> None:
        """Read the rows of `slots`, and of the things they belong to, or of
        every slot when `slots` is `None`."""

        self.rows.clear()
        self._thing_ids.clear()
        self._writes.clear()
        if slots is None:
            for table in TABLES:
                for row in self.conn.execute(f"SELECT * FROM {table} ORDER BY row_id"):
                    self._add(table, row)
            return

        wanted = set(slots)
        facts = sorted({slot[1] for slot in wanted if slot[0] == "facts"})
        for chunk in _chunks(facts):
            placeholders = ",".join("?" for _ in chunk)
            for row in self.conn.execute(
                f"SELECT * FROM facts WHERE fact_id IN ({placeholders}) "
                "ORDER BY row_id",
                chunk,
            ):
                self._add("facts", row)

        values = sorted({slot[1] for slot in wanted if slot[0] == "field_values"})
        for chunk in _chunks(values):
            placeholders = ",".join("?" for _ in chunk)
            for row in self.conn.execute(
                f"SELECT * FROM field_values WHERE thing_id IN ({placeholders}) "
                "ORDER BY row_id",
                chunk,
            ):
                if slot_of("field_values", row) in wanted:
                    self._add("field_values", row)

        things = {slot[1] for slot in wanted if slot[0] == "things"}
        things |= {self._thing_ids[slot] for slot in self.rows}
        for chunk in _chunks(sorted(things)):
            placeholders = ",".join("?" for _ in chunk)
            for row in self.conn.execute(
                f"SELECT * FROM things WHERE id IN ({placeholders}) ORDER BY row_id",
                chunk,
            ):
                self._add("things", row)

    # -- reading a loaded slot -----------------------------------------------

    def slots(self) -> list[Slot]:
        return list(self.rows)

    def thing_id(self, slot: Slot) -> str:
        return self._thing_ids[slot]

    def touched(self, slot: Slot) -> set[int]:
        """The revisions that added or retired a row in `slot`."""

        rows = self.rows[slot]
        return {r["rev_added"] for r in rows} | {
            r["rev_removed"] for r in rows if r["rev_removed"] is not None
        }

    def writes(self, slot: Slot) -> list[Write]:
        """Each non-undo revision's write to `slot`, oldest first."""

        if slot not in self._writes:
            rows = self.rows[slot]
            writes = []
            for rev in sorted(self.touched(slot) - self.undo_revs):
                left = [
                    r for r in rows if r["rev_added"] == rev and r["rev_removed"] != rev
                ]
                writes.append(Write(rev, left[-1] if left else None))
            self._writes[slot] = writes
        return self._writes[slot]

    def live_row(self, slot: Slot) -> sqlite3.Row | None:
        live = [r for r in self.rows.get(slot, ()) if r["rev_removed"] is None]
        return live[-1] if live else None

    def origin(self, slot: Slot, row: sqlite3.Row) -> sqlite3.Row:
        """The row `row` is ultimately a copy of: `restored_from`, followed
        until it's NULL. A copy is always in the same slot as its source."""

        by_id = {r["row_id"]: r for r in self.rows[slot]}
        while row["restored_from"] is not None:
            row = by_id[row["restored_from"]]
        return row

    def live_origin(self, slot: Slot) -> sqlite3.Row | None:
        """The write the live row in `slot` stands for, or `None`."""

        live = self.live_row(slot)
        return None if live is None else self.origin(slot, live)


class Replay:
    """The state of loaded slots with the revisions in effect that the
    reversal links say, optionally adding a not-yet-written undo of
    `undo_targets` that's in effect for every slot."""

    def __init__(self, history: History, undo_targets: Iterable[int] = ()):
        self.history = history
        self.targets = set(undo_targets)
        self._in_effect: dict[tuple[int | None, Slot], bool] = {}

    def _blocked(self, undo_rev: int | None, slot: Slot) -> bool:
        """Whether `undo_rev` recorded a conflict on `slot` or its thing.
        `None` is the undo being planned, which has recorded nothing."""

        if undo_rev is None:
            return False
        history = self.history
        if slot in history.blocked_slots.get(undo_rev, ()):
            return True
        return slot[0] != "things" and history.thing_id(
            slot
        ) in history.blocked_things.get(undo_rev, ())

    def _reverting(self, rev: int | None, slot: Slot) -> list[int | None]:
        """The undos that revert `rev` and count for `slot`: not blocked
        there. `None` is the undo being planned."""

        reverting: list[int | None] = list(self.history.reverted_by.get(rev, ()))
        if rev in self.targets:
            reverting.append(None)
        return [u for u in reverting if not self._blocked(u, slot)]

    def in_effect(self, rev: int | None, slot: Slot) -> bool:
        """Whether `rev` (`None` for the undo being planned) is in effect for
        `slot`: no undo in effect for `slot` reverts it, leaving aside undos
        that recorded a conflict on `slot` or its thing.

        Walked with an explicit stack rather than by recursion, since an undo
        of an undo of an undo... can be any number of levels deep. An undo
        only ever reverts earlier revisions, so the walk always ends."""

        memo = self._in_effect
        stack = [rev]
        while stack:
            current = stack[-1]
            if (current, slot) in memo:
                stack.pop()
                continue
            reverting = self._reverting(current, slot)
            pending = [u for u in reverting if (u, slot) not in memo]
            if pending:
                stack.extend(pending)
                continue
            memo[(current, slot)] = not any(memo[(u, slot)] for u in reverting)
            stack.pop()
        return memo[(rev, slot)]

    def latest(self, slot: Slot) -> Write | None:
        """The latest write to `slot` by a revision in effect for it."""

        for write in reversed(self.history.writes(slot)):
            if self.in_effect(write.rev, slot):
                return write
        return None

    def state(self, slot: Slot) -> sqlite3.Row | None:
        """The row `slot` holds, by its own writes alone."""

        write = self.latest(slot)
        return None if write is None else write.row

    def live(self, slot: Slot) -> sqlite3.Row | None:
        """The row that should be live in `slot`: its own state, for a value
        or fact only while its thing is live."""

        if slot[0] != "things":
            if self.state(thing_slot(self.history.thing_id(slot))) is None:
                return None
        return self.state(slot)
