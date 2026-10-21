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
from typing import cast

import structlog
from pydantic import BaseModel

from .dates import Precision, WorldDate
from .kinds import KindSpec, _field_spec, get_kind
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
    try:
        spec = _field_spec(kind_spec, field)
    except ValueError:
        raise KeyError(f"{kind_spec.name!r} has no field {field!r}") from None
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
    overrides: list[str] = []


class ThingState(BaseModel):
    id: str
    kind: str
    fields: dict[str, object]
    facts: list[FactState]

    @property
    def is_stub(self) -> bool:
        """Whether the thing carries the stub marker at this view."""

        return "stub" in self.fields

    @property
    def stub_ignored(self) -> bool:
        """Whether the thing is a stub the owner chose to ignore."""

        marker = self.fields.get("stub")
        return isinstance(marker, dict) and marker.get("ignored") is True


class Segment(BaseModel):
    """A run of rendered text: plain (`ref` is `None`) or a link to the
    thing `ref`."""

    text: str
    ref: str | None


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
        return cast(str, json.loads(row["value_json"]))

    def _live_things_filter(
        self, prefix: str, *, kind: str | None = None, thing_id: str | None = None
    ) -> tuple[str, list[object]]:
        """A SQL condition (columns named with `prefix`, e.g. `"t."`) and
        its params that picks out things live at `self.rev`, optionally
        narrowed to one `kind` or one `thing_id`. Used to join against
        `things` instead of binding one placeholder per id, so callers
        aren't bounded by SQLite's bound-variable limit."""

        clauses = [
            f"{prefix}rev_added <= ?",
            f"({prefix}rev_removed IS NULL OR {prefix}rev_removed > ?)",
        ]
        params: list[object] = [self.rev, self.rev]
        if kind is not None:
            clauses.append(f"{prefix}kind = ?")
            params.append(kind)
        if thing_id is not None:
            clauses.append(f"{prefix}id = ?")
            params.append(thing_id)
        return " AND ".join(clauses), params

    def _fetch_fields(
        self,
        thing_ids: list[str],
        *,
        kind: str | None = None,
        thing_id: str | None = None,
    ) -> dict[str, dict[str, object]]:
        """`thing_id -> {field: decoded value}`, one row per (thing_id,
        field): the live row with the greatest `valid_from <= at`, NULL
        sorting lowest. Joined against `things` (narrowed to `kind` or
        `thing_id` when given) rather than an `IN (...)` list of
        `thing_ids`, which is only used here to seed the empty result for
        things with no field values."""

        result: dict[str, dict[str, object]] = {tid: {} for tid in thing_ids}
        if not thing_ids:
            return result

        things_filter, things_params = self._live_things_filter(
            "t.", kind=kind, thing_id=thing_id
        )
        rows = self._conn.execute(
            f"""
            SELECT thing_id, field, value_json, thing_kind FROM (
                SELECT fv.thing_id, fv.field, fv.value_json, t.kind AS thing_kind,
                       ROW_NUMBER() OVER (
                           PARTITION BY fv.thing_id, fv.field
                           ORDER BY fv.valid_from DESC, fv.row_id DESC
                       ) AS rn
                FROM field_values fv
                JOIN things t ON t.id = fv.thing_id AND {things_filter}
                WHERE fv.rev_added <= ? AND (fv.rev_removed IS NULL OR fv.rev_removed > ?)
                  AND (fv.valid_from IS NULL OR fv.valid_from <= ?)
            )
            WHERE rn = 1
            """,
            (*things_params, self.rev, self.rev, self._at_instant()),
        ).fetchall()

        for row in rows:
            kind_spec = get_kind(row["thing_kind"])
            result.setdefault(row["thing_id"], {})[row["field"]] = _decode_field_value(
                kind_spec, row["field"], row["value_json"]
            )
        return result

    def _fetch_facts(
        self,
        thing_ids: list[str],
        *,
        kind: str | None = None,
        thing_id: str | None = None,
    ) -> dict[str, list[FactState]]:
        """`thing_id -> [FactState, ...]`, ordered by `valid_from` (NULL
        first), then `fact_id`. Joined against `things` (narrowed to
        `kind` or `thing_id` when given) rather than an `IN (...)` list of
        `thing_ids`, which is only used here to seed the empty result for
        things with no facts."""

        result: dict[str, list[FactState]] = {tid: [] for tid in thing_ids}
        if not thing_ids:
            return result

        things_filter, things_params = self._live_things_filter(
            "t.", kind=kind, thing_id=thing_id
        )
        at_instant = self._at_instant()
        rows = self._conn.execute(
            f"""
            SELECT f.row_id, f.thing_id, f.fact_id, f.category, f.text, f.valid_from,
                   f.from_precision, f.valid_until, f.until_precision, f.rev_added,
                   fo.fact_id AS override_fact_id
            FROM facts f
            JOIN things t ON t.id = f.thing_id AND {things_filter}
            LEFT JOIN fact_overrides fo ON fo.row_id = f.row_id
            WHERE f.rev_added <= ? AND (f.rev_removed IS NULL OR f.rev_removed > ?)
              AND (f.valid_from IS NULL OR f.valid_from <= ?)
              AND (f.valid_until IS NULL OR f.valid_until > ?)
            ORDER BY f.thing_id, f.valid_from ASC, f.fact_id ASC, fo.rowid ASC
            """,
            (*things_params, self.rev, self.rev, at_instant, at_instant),
        ).fetchall()

        facts_by_row: dict[int, FactState] = {}
        for row in rows:
            state = facts_by_row.get(row["row_id"])
            if state is None:
                state = _fact_state_from_row(row)
                facts_by_row[row["row_id"]] = state
                result.setdefault(row["thing_id"], []).append(state)
            if row["override_fact_id"] is not None:
                state.overrides.append(row["override_fact_id"])
        return result

    def thing(self, thing_id: str) -> ThingState | None:
        """The thing's state at `(at, rev)`, or `None` if it doesn't exist
        at `rev` (never created yet, or already removed)."""

        things_filter, things_params = self._live_things_filter("", thing_id=thing_id)
        row = self._conn.execute(
            f"SELECT kind FROM things WHERE {things_filter}", things_params
        ).fetchone()
        if row is None:
            return None

        kind = row["kind"]
        fields = self._fetch_fields([thing_id], thing_id=thing_id)[thing_id]
        facts = self._fetch_facts([thing_id], thing_id=thing_id)[thing_id]
        return ThingState(id=thing_id, kind=kind, fields=fields, facts=facts)

    def things(self, kind: str | None = None) -> list[ThingState]:
        """Every thing that exists at `rev`, optionally restricted to one
        `kind`, ordered by id."""

        things_filter, things_params = self._live_things_filter("", kind=kind)
        rows = self._conn.execute(
            f"SELECT id, kind FROM things WHERE {things_filter} ORDER BY id",
            things_params,
        ).fetchall()

        kinds = {row["id"]: row["kind"] for row in rows}
        fields_by_id = self._fetch_fields(list(kinds), kind=kind)
        facts_by_id = self._fetch_facts(list(kinds), kind=kind)

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

    def _is_live(self, thing_id: str) -> bool:
        things_filter, things_params = self._live_things_filter("", thing_id=thing_id)
        row = self._conn.execute(
            f"SELECT 1 FROM things WHERE {things_filter}", things_params
        ).fetchone()
        return row is not None

    def _main_names(self, thing_id: str) -> set[str]:
        """Every main name the thing has had up to `rev`, whatever story
        date it holds from, casefolded. Retired rows count too: a rename
        made as a correction (same `valid_from`) retires the old name, and
        a link written with it should still follow. A name whose revision
        was undone counts as well, which at worst makes a link written with
        it read as the current name."""

        rows = self._conn.execute(
            "SELECT value_json FROM field_values "
            "WHERE thing_id = ? AND field = 'name' AND rev_added <= ?",
            (thing_id, self.rev),
        ).fetchall()
        return {cast(str, json.loads(row["value_json"])).casefold() for row in rows}

    def _resolve(self, match: re.Match[str]) -> Segment:
        """What one reference renders as, and the thing it links to (`None`
        when its target doesn't exist at `rev`)."""

        thing_id, shown = match.group(1), match.group(2)
        live = self._is_live(thing_id)
        if shown is not None:
            if not live:
                return Segment(text=shown, ref=None)
            if shown.casefold() not in self._main_names(thing_id):
                return Segment(text=shown, ref=thing_id)

        name = self._name_at(thing_id, self._at_instant())
        if name is None:
            name = self._name_at(thing_id, _FAR_FUTURE)
        if name is None:
            return Segment(text=shown or UNKNOWN_NAME, ref=None)
        return Segment(text=name, ref=thing_id if live else None)

    def render(self, text: str) -> str:
        """Replace each reference in `text` with the words it reads as.

        `[[thing:<id>]]` reads as that thing's name: at `at` if it has one
        there, otherwise its latest name visible at `rev`, otherwise
        `⟨unknown⟩`. `[[thing:<id>|<shown>]]` reads as its shown text,
        unless that is (ignoring case) a main name the thing has ever had on
        its timeline, when it reads as the name, so a link written with the
        full name follows a rename; a target that doesn't exist at `rev`
        reads as the shown text."""

        return REF_PATTERN.sub(lambda match: self._resolve(match).text, text)

    def segments(self, text: str) -> list[Segment]:
        """`text` rendered as `render` does, split into plain runs and runs
        that link to a live thing, in order; adjacent plain runs are
        merged."""

        result: list[Segment] = []

        def add(segment: Segment) -> None:
            if not segment.text:
                return
            if result and segment.ref is None and result[-1].ref is None:
                result[-1] = Segment(text=result[-1].text + segment.text, ref=None)
            else:
                result.append(segment)

        end = 0
        for match in REF_PATTERN.finditer(text):
            add(Segment(text=text[end : match.start()], ref=None))
            add(self._resolve(match))
            end = match.end()
        add(Segment(text=text[end:], ref=None))
        return result

    def referencing(
        self, thing_id: str, *, any_date: bool = False
    ) -> list[tuple[str, FactState]]:
        """The `(owner thing id, fact)` pairs for visible facts that
        reference `thing_id`, ordered by `valid_from` (NULL first), then
        `fact_id`. With `any_date`, every fact live at `rev` counts,
        whatever story dates it's true between (ended facts too)."""

        at_instant = self._at_instant()
        dated = (
            ""
            if any_date
            else "AND (f.valid_from IS NULL OR f.valid_from <= :at) "
            "AND (f.valid_until IS NULL OR f.valid_until > :at)"
        )
        rows = self._conn.execute(
            f"""
            SELECT f.thing_id, f.fact_id, f.category, f.text, f.valid_from,
                   f.from_precision, f.valid_until, f.until_precision, f.rev_added
            FROM facts f
            JOIN fact_refs fr ON fr.row_id = f.row_id
            WHERE fr.thing_id = :thing_id
              AND f.rev_added <= :rev AND (f.rev_removed IS NULL OR f.rev_removed > :rev)
              {dated}
            ORDER BY f.valid_from ASC, f.fact_id ASC
            """,
            {"thing_id": thing_id, "rev": self.rev, "at": at_instant},
        ).fetchall()

        return [(row["thing_id"], _fact_state_from_row(row)) for row in rows]
