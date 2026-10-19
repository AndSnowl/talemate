"""Reading the world on both clocks.

Every row carries a source clock (`rev_added`/`rev_removed`: what the story
tool has committed) and facts and field values additionally carry a story
clock (`valid_from`/`valid_until`: when the thing is true in-world).
`World.view(at, rev)` resolves both at once into a `WorldView`: a snapshot
of things, their current field values, and the facts visible at that point
on both clocks.

`at=None` means "the latest telling" -- +infinity on the story clock, so
every field takes its most recent value and only facts with no end date are
visible. `rev=None` means the head revision at the moment `view()` was
called; `World.view` resolves it to a concrete revision number before
building the `WorldView`, so the view stays pinned even as later revisions
are written.
"""

import json
import re
import sqlite3

import structlog
from pydantic import BaseModel

from .dates import Precision, WorldDate
from .kinds import KindSpec, get_kind
from .refs import REF_PATTERN, parse_refs

log = structlog.get_logger("talemate.world.view")

# the string a reference renders as when its target can't be resolved on
# either clock
UNKNOWN_NAME = "⟨unknown⟩"

# an instant past the proleptic-Gregorian range (years 1-9999), used as
# "+infinity" for at=None so the ordinary <=/> comparisons just work
_FAR_FUTURE = 10**15


def _decode_date(instant: int | None, precision: str | None) -> WorldDate | None:
    if instant is None:
        return None
    return WorldDate(instant=instant, precision=Precision(precision))


def _decode_field_value(kind_spec: KindSpec, field: str, value_json: str) -> object:
    spec = next(f for f in kind_spec.fields if f.name == field)
    if spec.type == "date":
        return WorldDate.model_validate_json(value_json)
    return json.loads(value_json)


def _fact_state_from_row(row: sqlite3.Row) -> "FactState":
    return FactState(
        fact_id=row["fact_id"],
        category=row["category"],
        text=row["text"],
        valid_from=_decode_date(row["valid_from"], row["from_precision"]),
        valid_until=_decode_date(row["valid_until"], row["until_precision"]),
        source_rev=row["rev_added"],
        refs=parse_refs(row["text"]),
    )


class FactState(BaseModel):
    fact_id: str
    category: str
    text: str
    valid_from: WorldDate | None
    valid_until: WorldDate | None
    source_rev: int
    refs: list[str]


class ThingState(BaseModel):
    id: str
    kind: str
    fields: dict[str, object]
    facts: list[FactState]


class WorldView:
    """A snapshot of a world as of `(at, rev)`. Built by `World.view`; not
    meant to be constructed directly."""

    def __init__(
        self, conn: sqlite3.Connection, at: WorldDate | None, rev: int
    ) -> None:
        self._conn = conn
        self.at = at
        self.rev = rev

    def _at_instant(self) -> int:
        return self.at.instant if self.at is not None else _FAR_FUTURE

    def _name_at(self, thing_id: str, at_instant: int) -> str | None:
        row = self._conn.execute(
            "SELECT value_json FROM field_values "
            "WHERE thing_id = ? AND field = 'name' "
            "AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?) "
            "AND (valid_from IS NULL OR valid_from <= ?) "
            "ORDER BY valid_from DESC, row_id DESC LIMIT 1",
            (thing_id, self.rev, self.rev, at_instant),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value_json"])

    def _fetch_fields(self, kinds: dict[str, str]) -> dict[str, dict[str, object]]:
        """`thing_id -> {field: decoded value}`, one row per (thing_id,
        field): the live row with the greatest `valid_from <= at`, NULL
        sorting lowest."""

        result: dict[str, dict[str, object]] = {thing_id: {} for thing_id in kinds}
        if not kinds:
            return result

        placeholders = ",".join("?" for _ in kinds)
        rows = self._conn.execute(
            f"""
            SELECT thing_id, field, value_json FROM (
                SELECT thing_id, field, value_json,
                       ROW_NUMBER() OVER (
                           PARTITION BY thing_id, field
                           ORDER BY valid_from DESC, row_id DESC
                       ) AS rn
                FROM field_values
                WHERE thing_id IN ({placeholders})
                  AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)
                  AND (valid_from IS NULL OR valid_from <= ?)
            )
            WHERE rn = 1
            """,
            (*kinds, self.rev, self.rev, self._at_instant()),
        ).fetchall()

        for row in rows:
            thing_id = row["thing_id"]
            kind_spec = get_kind(kinds[thing_id])
            result[thing_id][row["field"]] = _decode_field_value(
                kind_spec, row["field"], row["value_json"]
            )
        return result

    def _fetch_facts(self, thing_ids: list[str]) -> dict[str, list[FactState]]:
        """`thing_id -> [FactState, ...]`, ordered by `valid_from` (NULL
        first), then `fact_id`."""

        result: dict[str, list[FactState]] = {thing_id: [] for thing_id in thing_ids}
        if not thing_ids:
            return result

        placeholders = ",".join("?" for _ in thing_ids)
        at_instant = self._at_instant()
        rows = self._conn.execute(
            f"""
            SELECT thing_id, fact_id, category, text, valid_from, from_precision,
                   valid_until, until_precision, rev_added
            FROM facts
            WHERE thing_id IN ({placeholders})
              AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)
              AND (valid_from IS NULL OR valid_from <= ?)
              AND (valid_until IS NULL OR valid_until > ?)
            ORDER BY thing_id, valid_from ASC, fact_id ASC
            """,
            (*thing_ids, self.rev, self.rev, at_instant, at_instant),
        ).fetchall()

        for row in rows:
            result[row["thing_id"]].append(_fact_state_from_row(row))
        return result

    def thing(self, thing_id: str) -> ThingState | None:
        """The thing's state at `(at, rev)`, or `None` if it doesn't exist
        at `rev` (never created yet, or already removed)."""

        row = self._conn.execute(
            "SELECT kind FROM things WHERE id = ? "
            "AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)",
            (thing_id, self.rev, self.rev),
        ).fetchone()
        if row is None:
            return None

        kind = row["kind"]
        fields = self._fetch_fields({thing_id: kind})[thing_id]
        facts = self._fetch_facts([thing_id])[thing_id]
        return ThingState(id=thing_id, kind=kind, fields=fields, facts=facts)

    def things(self, kind: str | None = None) -> list[ThingState]:
        """Every thing that exists at `rev`, optionally restricted to one
        `kind`, ordered by id."""

        if kind is None:
            rows = self._conn.execute(
                "SELECT id, kind FROM things "
                "WHERE rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?) "
                "ORDER BY id",
                (self.rev, self.rev),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, kind FROM things "
                "WHERE kind = ? AND rev_added <= ? "
                "AND (rev_removed IS NULL OR rev_removed > ?) "
                "ORDER BY id",
                (kind, self.rev, self.rev),
            ).fetchall()

        kinds = {row["id"]: row["kind"] for row in rows}
        fields_by_id = self._fetch_fields(kinds)
        facts_by_id = self._fetch_facts(list(kinds))

        return [
            ThingState(
                id=thing_id,
                kind=thing_kind,
                fields=fields_by_id[thing_id],
                facts=facts_by_id[thing_id],
            )
            for thing_id, thing_kind in kinds.items()
        ]

    def name_of(self, thing_id: str) -> str | None:
        """The thing's `name` field at `at`, or `None` if it has none."""

        return self._name_at(thing_id, self._at_instant())

    def render(self, text: str) -> str:
        """Replace each `[[thing:<id>]]` reference in `text` with that
        thing's name: at `at` if it has one there, otherwise its latest name
        visible at `rev`, otherwise `⟨unknown⟩`."""

        def replace(match: re.Match[str]) -> str:
            thing_id = match.group(1)
            name = self._name_at(thing_id, self._at_instant())
            if name is None:
                name = self._name_at(thing_id, _FAR_FUTURE)
            return name if name is not None else UNKNOWN_NAME

        return REF_PATTERN.sub(replace, text)

    def referencing(self, thing_id: str) -> list[tuple[str, FactState]]:
        """The `(owner thing id, fact)` pairs for visible facts that
        reference `thing_id`, ordered by `valid_from` (NULL first), then
        `fact_id`."""

        at_instant = self._at_instant()
        rows = self._conn.execute(
            """
            SELECT f.thing_id, f.fact_id, f.category, f.text, f.valid_from,
                   f.from_precision, f.valid_until, f.until_precision, f.rev_added
            FROM facts f
            JOIN fact_refs fr ON fr.row_id = f.row_id
            WHERE fr.thing_id = ?
              AND f.rev_added <= ? AND (f.rev_removed IS NULL OR f.rev_removed > ?)
              AND (f.valid_from IS NULL OR f.valid_from <= ?)
              AND (f.valid_until IS NULL OR f.valid_until > ?)
            ORDER BY f.valid_from ASC, f.fact_id ASC
            """,
            (thing_id, self.rev, self.rev, at_instant, at_instant),
        ).fetchall()

        return [(row["thing_id"], _fact_state_from_row(row)) for row in rows]
