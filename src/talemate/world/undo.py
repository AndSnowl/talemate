"""Undo by source: revert what a set of revisions did, in one new revision.

Nothing is deleted or updated in place. A row the target revisions added is
retired at the undo revision; a row they retired is restored as a copy whose
`rev_added` is the undo revision (facts keep their `fact_id`, and the copy
gets the original's `fact_refs`). The full history stays viewable.

A row changed again by a later revision outside the targets is left alone
and reported as an `UndoConflict`, as is a thing the targets created that a
later revision has since added rows to. Rows already reverted by an earlier
undo are skipped silently, so undoing the same revisions twice is a no-op.

Rows are grouped into slots -- a fact's `fact_id`, or a field value's
`(thing_id, field, valid_from)` -- since at most one row per slot is live at
a time, and a conflict anywhere in a slot leaves the whole slot untouched.
"""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel

if TYPE_CHECKING:
    from .store import Revision

log = structlog.get_logger("talemate.world.undo")

CHANGED_LATER = "changed again in a later revision"
REMOVED_LATER = "removed in a later revision"

Table = Literal["things", "field_values", "facts"]


class UndoConflict(BaseModel):
    table: Table
    row_id: str | int
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

    def __init__(
        self, conn: sqlite3.Connection, targets: set[int], undo_revs: set[int]
    ):
        self.conn = conn
        self.targets = targets
        self.undo_revs = undo_revs
        self.plan = _Plan()
        # things created in the targets: their rows are handled with the
        # thing, never one by one
        self.created: set[str] = set()
        self.retired_things: set[str] = set()
        self.restored_things: set[str] = set()

    def _in(self) -> tuple[str, list[int]]:
        placeholders = ",".join("?" for _ in self.targets)
        return placeholders, sorted(self.targets)

    def _is_later_change(self, rev: int | None) -> bool:
        """A revision outside the targets that isn't itself an undo."""

        return rev is not None and rev not in self.targets and rev not in self.undo_revs

    def _conflict(
        self, table: Table, row: sqlite3.Row, thing_id: str, reason: str, later_rev: int
    ) -> None:
        self.plan.conflicts.append(
            UndoConflict(
                table=table,
                row_id=row["row_id"],
                thing_id=thing_id,
                reason=reason,
                later_rev=later_rev,
            )
        )

    def plan_things(self) -> None:
        """Decide once per thing id, over all of that id's rows, so a thing
        removed and restored several times never ends up with two live
        rows."""

        placeholders, params = self._in()
        ids = self.conn.execute(
            f"SELECT DISTINCT id FROM things WHERE rev_added IN ({placeholders}) "
            f"OR rev_removed IN ({placeholders}) ORDER BY id",
            params + params,
        ).fetchall()

        for (thing_id,) in ids:
            rows = self.conn.execute(
                "SELECT * FROM things WHERE id = ? ORDER BY row_id", (thing_id,)
            ).fetchall()
            if any(r["rev_added"] in self.targets for r in rows):
                # its creation (or a restore of it) is being undone: never
                # restore it, and its rows go with it
                self.created.add(thing_id)
                self._plan_created_thing(rows)
            else:
                self._plan_removed_thing(rows)

    def _plan_created_thing(self, rows: list[sqlite3.Row]) -> None:
        added = [
            r
            for r in rows
            if r["rev_added"] in self.targets and r["rev_removed"] not in self.targets
        ]
        live = next((r for r in added if r["rev_removed"] is None), None)
        if live is None:
            later = [r for r in added if self._is_later_change(r["rev_removed"])]
            if later:
                row = max(later, key=lambda r: r["rev_removed"])
                self._conflict(
                    "things", row, row["id"], REMOVED_LATER, row["rev_removed"]
                )
            # else added and removed within the targets, or already undone
            return

        thing_id = live["id"]
        live_rows = {
            table: self.conn.execute(
                f"SELECT row_id, rev_added FROM {table} "
                "WHERE thing_id = ? AND rev_removed IS NULL",
                (thing_id,),
            ).fetchall()
            for table in ("field_values", "facts")
        }
        later = [
            r["rev_added"]
            for table_rows in live_rows.values()
            for r in table_rows
            if self._is_later_change(r["rev_added"])
        ]
        if later:
            self._conflict("things", live, thing_id, CHANGED_LATER, min(later))
            return

        self.plan.retire.append(("things", live["row_id"]))
        self.retired_things.add(thing_id)
        for table, table_rows in live_rows.items():
            self.plan.retire.extend((table, r["row_id"]) for r in table_rows)

    def _plan_removed_thing(self, rows: list[sqlite3.Row]) -> None:
        if any(r["rev_removed"] is None for r in rows):
            # only an undo can bring a thing back, so it's already restored
            return
        retired = [r for r in rows if r["rev_removed"] in self.targets]
        latest = max(retired, key=lambda r: r["rev_removed"])
        self.plan.restore.append(("things", latest))
        self.restored_things.add(latest["id"])

    def _thing_live_after(self, thing_id: str) -> bool:
        if thing_id in self.restored_things:
            return True
        if thing_id in self.retired_things:
            return False
        row = self.conn.execute(
            "SELECT 1 FROM things WHERE id = ? AND rev_removed IS NULL",
            (thing_id,),
        ).fetchone()
        return row is not None

    def _thing_removed_rev(self, thing_id: str) -> int:
        return self.conn.execute(
            "SELECT MAX(rev_removed) FROM things WHERE id = ?", (thing_id,)
        ).fetchone()[0]

    def plan_rows(self, table: Literal["field_values", "facts"]) -> None:
        placeholders, params = self._in()
        rows = self.conn.execute(
            f"SELECT * FROM {table} WHERE rev_added IN ({placeholders}) "
            f"OR rev_removed IN ({placeholders}) ORDER BY row_id",
            params + params,
        ).fetchall()

        slots: dict[tuple, None] = {}
        for row in rows:
            if row["thing_id"] in self.created:
                continue
            if table == "facts":
                key = (row["fact_id"],)
            else:
                key = (row["thing_id"], row["field"], row["valid_from"])
            slots.setdefault(key, None)

        for key in slots:
            if table == "facts":
                slot_rows = self.conn.execute(
                    "SELECT * FROM facts WHERE fact_id = ? ORDER BY row_id", key
                ).fetchall()
            else:
                slot_rows = self.conn.execute(
                    "SELECT * FROM field_values "
                    "WHERE thing_id = ? AND field = ? AND valid_from IS ? "
                    "ORDER BY row_id",
                    key,
                ).fetchall()
            self._plan_slot(table, slot_rows)

    def _plan_slot(
        self, table: Literal["field_values", "facts"], slot_rows: list[sqlite3.Row]
    ) -> None:
        targets = self.targets
        added = [
            r
            for r in slot_rows
            if r["rev_added"] in targets and r["rev_removed"] not in targets
        ]
        retired = [
            r
            for r in slot_rows
            if r["rev_removed"] in targets and r["rev_added"] not in targets
        ]
        thing_id = slot_rows[0]["thing_id"]
        revs_adding = {r["rev_added"] for r in slot_rows}

        # step 1 and 2: retire what the targets added, unless changed later
        to_retire = []
        conflicted = False
        for row in added:
            removed = row["rev_removed"]
            if removed is None:
                to_retire.append(row)
            elif self._is_later_change(removed):
                reason = CHANGED_LATER if removed in revs_adding else REMOVED_LATER
                self._conflict(table, row, thing_id, reason, removed)
                conflicted = True
            # else retired by an undo already: nothing to do
        if conflicted:
            return
        self.plan.retire.extend((table, r["row_id"]) for r in to_retire)

        # step 3: restore the newest row the targets retired
        if not retired:
            return
        latest = max(retired, key=lambda r: r["rev_removed"])
        retiring = {r["row_id"] for r in to_retire}
        newer = [
            r
            for r in slot_rows
            if r["rev_removed"] is None and r["row_id"] not in retiring
        ]
        if newer:
            later_rev = newer[-1]["rev_added"]
            if self._is_later_change(later_rev):
                self._conflict(table, latest, thing_id, CHANGED_LATER, later_rev)
            # else restored by an undo already
            return
        if not self._thing_live_after(thing_id):
            self._conflict(
                table,
                latest,
                thing_id,
                REMOVED_LATER,
                self._thing_removed_rev(thing_id),
            )
            return
        self.plan.restore.append((table, latest))


def _apply(conn: sqlite3.Connection, undo_rev: int, plan: _Plan) -> None:
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
                "INSERT INTO things (id, kind, rev_added) VALUES (?, ?, ?)",
                (row["id"], row["kind"], undo_rev),
            )
        elif table == "field_values":
            conn.execute(
                "INSERT INTO field_values "
                "(thing_id, field, value_json, valid_from, from_precision, rev_added) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["thing_id"],
                    row["field"],
                    row["value_json"],
                    row["valid_from"],
                    row["from_precision"],
                    undo_rev,
                ),
            )
        else:
            cur = conn.execute(
                "INSERT INTO facts "
                "(fact_id, thing_id, category, text, valid_from, from_precision, "
                " valid_until, until_precision, origin_json, rev_added) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                ),
            )
            conn.execute(
                "INSERT INTO fact_refs (row_id, thing_id) "
                "SELECT ?, thing_id FROM fact_refs WHERE row_id = ?",
                (cur.lastrowid, row["row_id"]),
            )


def undo_revisions(
    conn: sqlite3.Connection,
    revs: list[int],
    open_revision: "Callable[[], AbstractContextManager[Revision]]",
) -> UndoReport:
    """Plan the undo of `revs`, then, if it reverts anything, apply it
    inside the revision `open_revision()` opens (an `undo` revision).
    Raises `KeyError` for a revision that doesn't exist."""

    targets = set(revs)
    kinds = dict(conn.execute("SELECT rev, source_kind FROM revisions").fetchall())
    missing = targets - kinds.keys()
    if missing:
        raise KeyError(f"no such revision: {sorted(missing)}")
    if not targets:
        return UndoReport(undo_rev=None, reverted=0, conflicts=[])

    undo_revs = {rev for rev, kind in kinds.items() if kind == "undo"}
    planner = _Planner(conn, targets, undo_revs)
    planner.plan_things()
    planner.plan_rows("field_values")
    planner.plan_rows("facts")
    plan = planner.plan

    if not plan.reverted:
        log.info(
            "world.undo.nothing", revs=sorted(targets), conflicts=len(plan.conflicts)
        )
        return UndoReport(undo_rev=None, reverted=0, conflicts=plan.conflicts)

    with open_revision() as revision:
        _apply(conn, revision.rev, plan)

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
