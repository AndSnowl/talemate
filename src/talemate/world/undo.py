"""Undo by source: revert what a set of revisions did, in one new revision.

Nothing is deleted or updated in place. Undo retires live rows and restores
earlier ones as copies whose `rev_added` is the undo revision (facts keep
their `fact_id`, and the copy gets the original's `fact_refs` and
`fact_overrides`). The full history stays viewable.

Every undo leaves reversal links (the reversing-entry pattern, as in
accounting reversals or `git revert`): its revision records the revisions it
reverses in `revision_reverts`, each restored copy records the row it copies
in `restored_from`, and each conflict it left alone is recorded in
`undo_conflicts`. Planning reads those links and never compares content.

An undo is planned as a replay (see `replay.py`): the slots it can affect
are worked out again with the undo added to the links, and the difference
from what's live is written. Those slots are the ones the targets wrote,
the ones written by the revisions an undo among the targets reverses
(recursively, since undoing an undo puts them back in effect), and every
value and fact slot of a thing among them, since a value or fact is only
live while its thing is.

A slot's change is left alone and reported as an `UndoConflict` when a
revision outside the targets, not an undo, wrote it after the last write of
a target that's still in effect there: the targets' change isn't what's
live any more. A write outside the targets that's older than that is just
uncovered (undoing T1 and T2 of T1, N, T2 leaves N's value, quietly). A
value or fact that can't come back because its thing was removed later
counts as removed later. A thing whose creation is being undone is kept,
with its rows, when a later revision outside the targets added rows to it
or referenced it (from a fact, a `thing` field or a `things` field). A
stub's kind change is kept the same way when a later revision outside the
targets gave it a value or fact the other kind has no room for.

An undo that changes nothing writes no revision, so re-undoing an undone
revision is a quiet no-op.
"""

import json
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import structlog
from pydantic import BaseModel

from .kinds import KINDS
from .replay import History, Replay, Slot, Table, Write, thing_slot

if TYPE_CHECKING:
    from .store import Revision

log = structlog.get_logger("talemate.world.undo")

CHANGED_LATER = "changed again in a later revision"
REMOVED_LATER = "removed in a later revision"
REFERENCED_LATER = "referenced in a later revision"

# the names of fields that can hold a thing id (`thing` or `things`) on
# some kind; each row's own kind decides whether its field
# really does
_REF_FIELD_NAMES = sorted(
    {
        spec.name
        for kind in KINDS.values()
        for spec in kind.fields
        if spec.type in ("thing", "things")
    }
)


class UndoConflict(BaseModel):
    table: Table
    row_id: int
    thing_id: str
    reason: str
    later_rev: int


class UndoReport(BaseModel):
    undo_rev: int | None
    reverted: int
    conflicts: list[UndoConflict]


@dataclass
class _Plan:
    retire: list[tuple[Table, int]] = field(default_factory=list)
    restore: list[tuple[Table, sqlite3.Row]] = field(default_factory=list)
    conflicts: list[UndoConflict] = field(default_factory=list)

    @property
    def reverted(self) -> int:
        return len(self.retire) + len(self.restore)


class _Planner:
    """Works out the whole undo before anything is written, so an undo that
    reverts nothing doesn't consume a revision number."""

    def __init__(self, conn: sqlite3.Connection, targets: set[int]):
        self.conn = conn
        self.targets = targets
        self.plan = _Plan()

        self.history = History(conn)
        self.closure = self.history.closure(targets)
        slots = self.history.touched_slots(self.closure)
        things = [cast(str, slot[1]) for slot in slots if slot[0] == "things"]
        slots.update(self.history.child_slots(things))
        self.slots = list(slots)
        self.history.load(self.slots)

        # the state now, and with this undo in effect everywhere
        self.before = Replay(self.history)
        self.after = Replay(self.history, targets)
        # the row each slot should stand for once the undo is written
        self.final: dict[Slot, sqlite3.Row | None] = {}
        self.blocked_things: set[str] = set()
        self._rows: dict[tuple[Table, int], sqlite3.Row] = {}

    # -- conflicts -----------------------------------------------------------

    def _conflict(self, slot: Slot, reason: str, later_rev: int) -> None:
        """Report `slot`, keyed by its live row, or by the latest row a
        target wrote there when nothing is live."""

        table = cast(Table, slot[0])
        row = self.history.live_row(slot)
        if row is None:
            row = max(
                (
                    r
                    for r in self.history.rows[slot]
                    if r["rev_added"] in self.targets
                    or r["rev_removed"] in self.targets
                ),
                key=lambda r: r["row_id"],
            )
        self.plan.conflicts.append(
            UndoConflict(
                table=table,
                row_id=row["row_id"],
                thing_id=self.history.thing_id(slot),
                reason=reason,
                later_rev=later_rev,
            )
        )

    def _changed_later(self, slot: Slot, latest: Write | None) -> bool:
        """Report `slot` if `latest`, the write it would hold, is a later
        change: by a revision outside the targets, after the last write a
        target still in effect there made. A slot no target in effect wrote
        isn't the targets' change (the undo only uncovers it, or it's already
        reverted), so it's never a conflict."""

        mine = [
            rev
            for rev in self.history.touched(slot)
            if rev in self.targets and self.before.in_effect(rev, slot)
        ]
        if not mine or latest is None or latest.rev in self.targets:
            return False
        if latest.rev < max(mine):
            return False
        reason = REMOVED_LATER if latest.row is None else CHANGED_LATER
        self._conflict(slot, reason, latest.rev)
        return True

    def _row(self, table: Table, row_id: int) -> sqlite3.Row:
        key = (table, row_id)
        if key not in self._rows:
            self._rows[key] = self.conn.execute(
                f"SELECT * FROM {table} WHERE row_id = ?", (row_id,)
            ).fetchone()
        return self._rows[key]

    def _later_write(self, table: Table, row: sqlite3.Row, since: int) -> int | None:
        """The revision behind live `row` when that's a later change after
        `since`: the row's own `rev_added`, or for a restored copy its
        origin's (an undo only ever brings a change back, it never makes
        one). `None` for a row a target added."""

        if row["rev_added"] in self.targets:
            return None
        while row["restored_from"] is not None:
            row = self._row(table, row["restored_from"])
        rev = cast(int, row["rev_added"])
        if rev <= since or rev in self.targets or rev in self.history.undo_revs:
            return None
        return rev

    def _later_reference(self, thing_id: str, since: int) -> int | None:
        """The earliest later change after `since` (see `_later_write`)
        behind a live reference to `thing_id`: a fact mentioning it, a
        `thing` field holding its id, or a `things` field listing it. A
        reference an undo restored counts by its
        origin, so a redo brings back its power to keep the thing."""

        revs = [
            self._later_write("facts", row, since)
            for row in self.conn.execute(
                "SELECT f.row_id, f.rev_added, f.restored_from FROM fact_refs fr "
                "JOIN facts f ON f.row_id = fr.row_id "
                "WHERE fr.thing_id = ? AND f.rev_removed IS NULL",
                (thing_id,),
            )
        ]

        placeholders = ",".join("?" for _ in _REF_FIELD_NAMES)
        rows = self.conn.execute(
            "SELECT fv.row_id, fv.field, fv.value_json, fv.rev_added, "
            "fv.restored_from, "
            "(SELECT kind FROM things t WHERE t.id = fv.thing_id "
            " ORDER BY t.row_id DESC LIMIT 1) AS kind "
            f"FROM field_values fv WHERE fv.field IN ({placeholders}) "
            "AND fv.rev_removed IS NULL AND instr(fv.value_json, ?) > 0",
            (*_REF_FIELD_NAMES, thing_id),
        ).fetchall()
        for row in rows:
            spec = next(f for f in KINDS[row["kind"]].fields if f.name == row["field"])
            value = json.loads(row["value_json"])
            if (spec.type == "thing" and value == thing_id) or (
                spec.type == "things" and thing_id in value
            ):
                revs.append(self._later_write("field_values", row, since))

        later = [rev for rev in revs if rev is not None]
        return min(later) if later else None

    def _keeps_creation(self, slot: Slot) -> bool:
        """For a live thing this undo would remove: report it if a later
        revision outside the targets added a row that's live on it now (R6)
        or a live reference to it (F1). Later counts from the first target
        that wrote the thing, or for a thing only an undo of an undo puts
        back, from the first revision behind that."""

        thing_id = cast(str, slot[1])
        touched = self.history.touched(slot)
        since = min((touched & self.targets) or (touched & self.closure))

        later = [
            rev
            for table in ("field_values", "facts")
            for row in self.conn.execute(
                f"SELECT * FROM {table} WHERE thing_id = ? AND rev_removed IS NULL",
                (thing_id,),
            )
            if (rev := self._later_write(table, row, since)) is not None
        ]
        if later:
            self._conflict(slot, CHANGED_LATER, min(later))
            return True
        # removing it would leave a later reference dangling; one older than
        # the targets' write (left behind by a removal, say) doesn't count
        referenced = self._later_reference(thing_id, since)
        if referenced is not None:
            self._conflict(slot, REFERENCED_LATER, referenced)
            return True
        return False

    def _keeps_kind(self, slot: Slot, live: sqlite3.Row, want: sqlite3.Row) -> bool:
        """For a stub whose kind change is being undone (`live` and `want`
        differ in kind): report it if a later revision outside the targets
        added a live value or fact that `want`'s kind has no room for, such
        as a character's `born` on what would go back to being lore."""

        if live["kind"] == want["kind"]:
            return False
        kind = KINDS[want["kind"]]
        types = {spec.name: spec.type for spec in kind.fields}
        old_types = {spec.name: spec.type for spec in KINDS[live["kind"]].fields}
        thing_id = cast(str, slot[1])
        since = min(self.history.touched(slot) & self.closure)

        misfits: list[tuple[Table, sqlite3.Row]] = [
            ("field_values", row)
            for row in self.conn.execute(
                "SELECT * FROM field_values WHERE thing_id = ? AND rev_removed IS NULL",
                (thing_id,),
            )
            if types.get(row["field"]) != old_types[row["field"]]
        ]
        misfits += [
            ("facts", row)
            for row in self.conn.execute(
                "SELECT * FROM facts WHERE thing_id = ? AND rev_removed IS NULL",
                (thing_id,),
            )
            if row["category"] not in kind.categories
        ]
        later = [
            rev
            for table, row in misfits
            if (rev := self._later_write(table, row, since)) is not None
        ]
        if later:
            self._conflict(slot, CHANGED_LATER, min(later))
            return True
        return False

    # -- planning ------------------------------------------------------------

    def plan_thing(self, slot: Slot) -> None:
        live = self.history.live_row(slot)
        want = self.after.state(slot)
        if (
            (live is not None and want is None and self._keeps_creation(slot))
            or self._changed_later(slot, self.after.latest(slot))
            or (
                live is not None
                and want is not None
                and self._keeps_kind(slot, live, want)
            )
        ):
            # kept as it is, along with all its values and facts
            self.blocked_things.add(cast(str, slot[1]))
            self.final[slot] = self.history.live_origin(slot)
            return
        self.final[slot] = want

    def plan_child(self, slot: Slot) -> None:
        thing_id = self.history.thing_id(slot)
        if thing_id in self.blocked_things:
            self.final[slot] = self.history.live_origin(slot)
            return

        own = thing_slot(thing_id)
        thing_now = self.history.live_row(own) is not None
        thing_after = (
            self.final[own] if own in self.final else self.after.state(own)
        ) is not None
        want = self.after.state(slot) if thing_after else None
        if thing_now and not thing_after:
            # it goes with its thing, whatever its own history
            self.final[slot] = None
            return

        latest = self.after.latest(slot)
        if not thing_after:
            # a removal of its thing counts as a later write of nothing
            removal = self.after.latest(own)
            if removal is not None and (latest is None or removal.rev > latest.rev):
                latest = removal
        if not self._changed_later(slot, latest):
            self.final[slot] = want
        elif not thing_after:
            self.final[slot] = None
        elif thing_now:
            self.final[slot] = self.history.live_origin(slot)
        else:
            # kept as it'd be without this undo, now that its thing is back
            self.final[slot] = self.before.state(slot)

    def run(self) -> _Plan:
        for slot in self.slots:
            if slot[0] == "things":
                self.plan_thing(slot)
        for slot in self.slots:
            if slot[0] != "things":
                self.plan_child(slot)

        order = {"things": 0, "field_values": 1, "facts": 2}
        self.plan.conflicts.sort(key=lambda c: order[c.table])
        for slot in sorted(self.slots, key=lambda slot: order[cast(str, slot[0])]):
            live = self.history.live_row(slot)
            want = self.final[slot]
            have = self.history.live_origin(slot)
            if (have is None) == (want is None) and (
                want is None or (have is not None and have["row_id"] == want["row_id"])
            ):
                continue
            table = cast(Table, slot[0])
            if live is not None:
                self.plan.retire.append((table, live["row_id"]))
            if want is not None:
                self.plan.restore.append((table, want))
        return self.plan


def _apply(
    conn: sqlite3.Connection, undo_rev: int, targets: set[int], plan: _Plan
) -> None:
    conn.executemany(
        "INSERT INTO revision_reverts (undo_rev, target_rev) VALUES (?, ?)",
        [(undo_rev, rev) for rev in sorted(targets)],
    )
    conn.executemany(
        "INSERT INTO undo_conflicts (undo_rev, table_name, row_id) VALUES (?, ?, ?)",
        [(undo_rev, c.table, c.row_id) for c in plan.conflicts],
    )

    for table, row_id in plan.retire:
        cur = conn.execute(
            f"UPDATE {table} SET rev_removed = ? "
            "WHERE row_id = ? AND rev_removed IS NULL",
            (undo_rev, row_id),
        )
        if cur.rowcount != 1:
            # the plan no longer matches the database; the revision rolls back
            raise RuntimeError(f"undo: {table} row {row_id} is no longer live")

    for table, row in plan.restore:
        if table == "things":
            conn.execute(
                "INSERT INTO things (id, kind, rev_added, restored_from) "
                "VALUES (?, ?, ?, ?)",
                (row["id"], row["kind"], undo_rev, row["row_id"]),
            )
        elif table == "field_values":
            conn.execute(
                "INSERT INTO field_values "
                "(thing_id, field, value_json, valid_from, from_precision, rev_added, "
                " restored_from) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["thing_id"],
                    row["field"],
                    row["value_json"],
                    row["valid_from"],
                    row["from_precision"],
                    undo_rev,
                    row["row_id"],
                ),
            )
        else:
            cur = conn.execute(
                "INSERT INTO facts "
                "(fact_id, thing_id, category, text, valid_from, from_precision, "
                " valid_until, until_precision, origin_json, rev_added, restored_from) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["fact_id"],
                    row["thing_id"],
                    row["category"],
                    row["text"],
                    row["valid_from"],
                    row["from_precision"],
                    row["valid_until"],
                    row["until_precision"],
                    row["origin_json"],
                    undo_rev,
                    row["row_id"],
                ),
            )
            conn.execute(
                "INSERT INTO fact_refs (row_id, thing_id) "
                "SELECT ?, thing_id FROM fact_refs WHERE row_id = ?",
                (cur.lastrowid, row["row_id"]),
            )
            conn.execute(
                "INSERT INTO fact_overrides (row_id, fact_id) "
                "SELECT ?, fact_id FROM fact_overrides WHERE row_id = ?",
                (cur.lastrowid, row["row_id"]),
            )


def undo_revisions(
    conn: sqlite3.Connection,
    revs: list[int],
    open_revision: "Callable[[], AbstractContextManager[Revision]]",
) -> UndoReport:
    """Plan the undo of `revs`, then, if it changes anything, apply it
    inside the revision `open_revision()` opens (an `undo` revision).
    Raises `KeyError` for a revision that doesn't exist."""

    targets = set(revs)
    known = {row[0] for row in conn.execute("SELECT rev FROM revisions")}
    missing = targets - known
    if missing:
        raise KeyError(f"no such revision: {sorted(missing)}")
    if not targets:
        return UndoReport(undo_rev=None, reverted=0, conflicts=[])

    plan = _Planner(conn, targets).run()

    if not plan.reverted:
        log.info(
            "world.undo.nothing", revs=sorted(targets), conflicts=len(plan.conflicts)
        )
        return UndoReport(undo_rev=None, reverted=0, conflicts=plan.conflicts)

    with open_revision() as revision:
        _apply(conn, revision.rev, targets, plan)

    log.info(
        "world.undo",
        revs=sorted(targets),
        undo_rev=revision.rev,
        reverted=plan.reverted,
        conflicts=len(plan.conflicts),
    )
    return UndoReport(
        undo_rev=revision.rev, reverted=plan.reverted, conflicts=plan.conflicts
    )
