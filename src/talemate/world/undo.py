"""Undo by source: revert what a set of revisions did, in one new revision.

Nothing is deleted or updated in place. A row the target revisions added is
retired at the undo revision; a row they retired is restored as a copy whose
`rev_added` is the undo revision (facts keep their `fact_id`, and the copy
gets the original's `fact_refs`). The full history stays viewable.

Every undo leaves reversal links (the reversing-entry pattern, as in
accounting reversals or `git revert`): its revision records the revisions it
reverses in `revision_reverts`, and each restored copy records the row it
copies in `restored_from`. Planning follows those links and never compares
content, so an unrelated write or undo that happens to bring back the same
text or value is never mistaken for the targets' change:

- a row the targets added is reverted through its current copy (the live
  row whose `restored_from` chain reaches it). With none live, the change
  was already reverted (R5) -- unless a later revision outside the targets,
  not an undo, retired it, which is a conflict;
- a row the targets retired is restored unless an undo already restored a
  copy of it that's still live, or that a later revision has since retired
  (a later, unrelated change). A copy retired by an undo of the undo that
  restored it (a redo) puts the targets' change back in effect.

An undo whose targets both added a row and retired it writes nothing for
it, since the two cancel out. A later undo of just one of them still sees
the pair as reverted, through `revision_reverts`, as long as that earlier
undo is in effect (not redone) and went through for the row's slot and
thing (a conflict would have left one of its targets' rows live).

A row changed again by a later revision outside the targets is left alone
and reported as an `UndoConflict`, as is a thing the targets created that a
later revision has since added rows to or referenced (from a fact, a `thing`
field or a `shares` field). A restored copy counts as the change its origin
(the end of its `restored_from` chain) made.

Rows are grouped into slots -- a fact's `fact_id`, or a field value's
`(thing_id, field, valid_from)` -- since at most one row per slot is live at
a time, and a conflict anywhere in a slot leaves the whole slot untouched.
"""

import json
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel

from .kinds import KINDS

if TYPE_CHECKING:
    from .store import Revision

log = structlog.get_logger("talemate.world.undo")

CHANGED_LATER = "changed again in a later revision"
REMOVED_LATER = "removed in a later revision"
REFERENCED_LATER = "referenced in a later revision"

# the names of fields that can hold a thing id (`thing` or `shares`) on
# some kind; each row's own kind decides whether its field really does
_REF_FIELD_NAMES = sorted(
    {
        spec.name
        for kind in KINDS.values()
        for spec in kind.fields
        if spec.type in ("thing", "shares")
    }
)

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
        self._rows: dict[tuple[Table, int], sqlite3.Row] = {}
        # the reversal links, both ways: what each undo reverted, and which
        # undos reverted each revision
        self._reverts: dict[int, set[int]] = {}
        self._reverted_in: dict[int, set[int]] = {}
        for undo_rev, target_rev in conn.execute(
            "SELECT undo_rev, target_rev FROM revision_reverts"
        ):
            self._reverts.setdefault(undo_rev, set()).add(target_rev)
            self._reverted_in.setdefault(target_rev, set()).add(undo_rev)
        self._in_effect: dict[int, bool] = {}
        self._things: dict[str, list[sqlite3.Row]] = {}

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

    def _row(self, table: Table, row_id: int) -> sqlite3.Row:
        key = (table, row_id)
        if key not in self._rows:
            self._rows[key] = self.conn.execute(
                f"SELECT * FROM {table} WHERE row_id = ?", (row_id,)
            ).fetchone()
        return self._rows[key]

    def _origin(self, table: Table, row: sqlite3.Row) -> sqlite3.Row:
        """The row `row` is ultimately a copy of: `restored_from`, followed
        until it's NULL (`row` itself when it isn't a copy)."""

        while row["restored_from"] is not None:
            row = self._row(table, row["restored_from"])
        return row

    def _undo_in_effect(self, undo_rev: int) -> bool:
        """An undo outside the targets that no later undo in effect has
        reverted (a redo)."""

        if undo_rev in self.targets:
            return False
        if undo_rev not in self._in_effect:
            self._in_effect[undo_rev] = not any(
                self._undo_in_effect(later)
                for later in self._reverted_in.get(undo_rev, ())
            )
        return self._in_effect[undo_rev]

    def _thing_rows(self, thing_id: str) -> list[sqlite3.Row]:
        if thing_id not in self._things:
            self._things[thing_id] = self.conn.execute(
                "SELECT * FROM things WHERE id = ? ORDER BY row_id", (thing_id,)
            ).fetchall()
        return self._things[thing_id]

    def _blocked(self, table: Table, rows: list[sqlite3.Row], undo_rev: int) -> bool:
        """Whether `undo_rev` left a change of its own targets in effect
        among `rows` (one slot, or one thing's rows): a row whose origin one
        of them added stayed live across it. That's what a conflict leaves
        behind, since an undo that went through retired every such row."""

        reverted = self._reverts[undo_rev]
        return any(
            r["rev_added"] < undo_rev
            and (r["rev_removed"] is None or r["rev_removed"] > undo_rev)
            and self._origin(table, r)["rev_added"] in reverted
            for r in rows
        )

    def _netted_out(
        self, table: Table, row: sqlite3.Row, slot_rows: list[sqlite3.Row]
    ) -> bool:
        """Whether an undo in effect reverted both the revision behind
        retired `row` (its origin's) and the one that retired it, and went
        through for `row`'s slot and thing. The two cancel out, so that undo
        wrote nothing for `row`, yet the change is already reverted (R5)."""

        added = self._origin(table, row)["rev_added"]
        removed = row["rev_removed"]
        for undo_rev in self._reverted_in.get(added, ()):
            if removed not in self._reverts[undo_rev]:
                continue
            if not self._undo_in_effect(undo_rev):
                continue
            if self._blocked(table, slot_rows, undo_rev):
                continue
            if table != "things" and self._blocked(
                "things", self._thing_rows(row["thing_id"]), undo_rev
            ):
                continue
            return True
        return False

    @staticmethod
    def _latest_copy(
        row: sqlite3.Row, slot_rows: list[sqlite3.Row]
    ) -> sqlite3.Row | None:
        """The newest row in the slot that's a copy of `row`, directly or
        through other copies. A copy always comes after the row it copies,
        and `slot_rows` is in `row_id` order."""

        reached = {row["row_id"]}
        latest = None
        for r in slot_rows:
            if r["restored_from"] in reached:
                reached.add(r["row_id"])
                latest = r
        return latest

    def _restorable(self, table: Table, row: sqlite3.Row) -> bool:
        """A row the targets retired but didn't add, either directly or as
        the copy of a row they added (that retirement just nets out)."""

        return (
            row["rev_removed"] in self.targets
            and row["rev_added"] not in self.targets
            and self._origin(table, row)["rev_added"] not in self.targets
        )

    def _still_retired(
        self,
        table: Table,
        row: sqlite3.Row,
        slot_rows: list[sqlite3.Row],
        retiring: set[int],
    ) -> bool:
        """Whether the targets' retirement of `row` is still in effect. It
        isn't once an undo netted it out (see `_netted_out`) or restored a
        copy of it (R5: already reverted), unless that copy was itself undone (a redo), is being retired by
        this undo, or was retired by a target that this undo reverts in its
        own right. A copy retired by anything else stands for a later,
        unrelated change, so `row` stays retired."""

        if self._netted_out(table, row, slot_rows):
            return False
        copy = self._latest_copy(row, slot_rows)
        if copy is None:
            return True
        removed = copy["rev_removed"]
        if removed is None:
            return copy["row_id"] in retiring
        if removed in self.targets:
            # restored in its own right when it can be
            return not self._restorable(table, copy)
        return removed in self.undo_revs and copy["rev_added"] in self._reverts.get(
            removed, ()
        )

    def _later_write(self, table: Table, row: sqlite3.Row, since: int) -> int | None:
        """The revision behind live `row` when that's a later change after
        `since`: the row's own `rev_added`, or for a restored copy its
        origin's (an undo only ever brings a change back, it never makes
        one). `None` for a row the targets added."""

        if row["rev_added"] in self.targets:
            return None
        rev = self._origin(table, row)["rev_added"]
        return rev if rev > since and self._is_later_change(rev) else None

    def _later_reference(self, thing_id: str, since: int) -> int | None:
        """The earliest later change after `since` (see `_later_write`)
        behind a live reference to `thing_id`: a fact mentioning it, a
        `thing` field holding its id, or a `shares` field naming it. A
        reference an undo restored counts by its origin, so a redo brings
        back its power to keep the thing (Review Focus 4)."""

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
                spec.type == "shares"
                and any(share["thing_id"] == thing_id for share in value)
            ):
                revs.append(self._later_write("field_values", row, since))

        later = [rev for rev in revs if rev is not None]
        return min(later) if later else None

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
        # the live row now standing for a row the targets added, and the
        # earliest such added row (later changes count from there)
        live = None
        since = None
        removed_later = []
        for row in rows:
            if row["rev_added"] not in self.targets:
                continue
            current = self._latest_copy(row, rows) or row
            if current["rev_removed"] is None:
                live = current
                since = row["rev_added"] if since is None else since
            elif self._is_later_change(current["rev_removed"]) and not self._netted_out(
                "things", current, rows
            ):
                removed_later.append(current)
            # else already reverted: retired by an undo or within the
            # targets, or netted out (see `_netted_out`)

        if live is None:
            if removed_later:
                row = max(removed_later, key=lambda r: r["rev_removed"])
                self._conflict(
                    "things", row, row["id"], REMOVED_LATER, row["rev_removed"]
                )
            return

        thing_id = live["id"]
        live_rows = {
            table: self.conn.execute(
                f"SELECT * FROM {table} WHERE thing_id = ? AND rev_removed IS NULL",
                (thing_id,),
            ).fetchall()
            for table in ("field_values", "facts")
        }
        later = [
            rev
            for table, table_rows in live_rows.items()
            for r in table_rows
            if (rev := self._later_write(table, r, since)) is not None
        ]
        if later:
            self._conflict("things", live, thing_id, CHANGED_LATER, min(later))
            return
        # retiring it would leave a later reference dangling; one older
        # than the targets' row (left behind by a removal, say) doesn't count
        referenced = self._later_reference(thing_id, since)
        if referenced is not None:
            self._conflict("things", live, thing_id, REFERENCED_LATER, referenced)
            return

        self.plan.retire.append(("things", live["row_id"]))
        self.retired_things.add(thing_id)
        for table, table_rows in live_rows.items():
            self.plan.retire.extend((table, r["row_id"]) for r in table_rows)

    def _plan_removed_thing(self, rows: list[sqlite3.Row]) -> None:
        if any(r["rev_removed"] is None for r in rows):
            # only an undo can bring a thing back, so it's already restored
            return
        retired = [
            r
            for r in rows
            if self._restorable("things", r)
            and self._still_retired("things", r, rows, set())
        ]
        if not retired:
            return
        latest = max(retired, key=lambda r: (r["rev_removed"], r["row_id"]))
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
        thing_id = slot_rows[0]["thing_id"]
        revs_adding = {r["rev_added"] for r in slot_rows}

        # rule 1: retire the live row now standing for each row the targets
        # added, unless a later change retired it
        to_retire: dict[int, sqlite3.Row] = {}
        conflicted = False
        for row in slot_rows:
            if row["rev_added"] not in self.targets:
                continue
            current = self._latest_copy(row, slot_rows) or row
            removed = current["rev_removed"]
            if removed is None:
                to_retire[current["row_id"]] = current
            elif self._is_later_change(removed) and not self._netted_out(
                table, current, slot_rows
            ):
                reason = CHANGED_LATER if removed in revs_adding else REMOVED_LATER
                self._conflict(table, current, thing_id, reason, removed)
                conflicted = True
            # else already reverted: retired by an undo or within the
            # targets, or netted out (see `_netted_out`)
        if conflicted:
            return
        self.plan.retire.extend((table, row_id) for row_id in to_retire)

        # rule 2: restore the newest row the targets retired, if that's
        # still in effect
        retiring = set(to_retire)
        retired = [
            r
            for r in slot_rows
            if self._restorable(table, r)
            and self._still_retired(table, r, slot_rows, retiring)
        ]
        if not retired:
            return
        latest = max(retired, key=lambda r: (r["rev_removed"], r["row_id"]))
        newer = [
            r
            for r in slot_rows
            if r["rev_removed"] is None and r["row_id"] not in retiring
        ]
        if newer:
            origin = self._origin(table, newer[-1])
            if origin["row_id"] != self._origin(table, latest)["row_id"] and (
                self._is_later_change(origin["rev_added"])
            ):
                self._conflict(
                    table, latest, thing_id, CHANGED_LATER, origin["rev_added"]
                )
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


def _apply(
    conn: sqlite3.Connection, undo_rev: int, targets: set[int], plan: _Plan
) -> None:
    conn.executemany(
        "INSERT INTO revision_reverts (undo_rev, target_rev) VALUES (?, ?)",
        [(undo_rev, rev) for rev in sorted(targets)],
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
