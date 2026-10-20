"""Thing timelines: every dated change to one thing, in story-time order.

A `TimelineEntry` is one field value or fact boundary that's live for a
thing at a given revision, each carrying the `Source` of the revision that
added it. `World.timeline` (in `store.py`) is the public entry point;
`build_timeline` does the actual reading, kept here to keep `store.py`
focused on writes.
"""

import sqlite3
from typing import Literal

import structlog
from pydantic import BaseModel

from .dates import WorldDate
from .kinds import get_kind
from .store import Source, _source_from_revision_row
from .view import _decode_date, _decode_field_value

log = structlog.get_logger("talemate.world.timeline")

# field < fact_start < fact_end, for same-date tie-breaking
_CHANGE_RANK = {"field": 0, "fact_start": 1, "fact_end": 2}


class TimelineEntry(BaseModel):
    date: WorldDate | None
    change: Literal["field", "fact_start", "fact_end"]
    field: str | None = None
    value: object | None = None
    fact_id: str | None = None
    text: str | None = None
    # the fact's category, for `change in ("fact_start", "fact_end")`;
    # `None` for a `"field"` entry, which has no category
    category: str | None = None
    source_rev: int
    source: Source


def _sort_key(entry: TimelineEntry) -> tuple[tuple[int, ...], int, int, str | None]:
    date_key = (0,) if entry.date is None else (1, entry.date.instant)
    name_key = entry.field if entry.change == "field" else entry.fact_id
    return (date_key, _CHANGE_RANK[entry.change], entry.source_rev, name_key)


def build_timeline(
    conn: sqlite3.Connection, thing_id: str, rev: int
) -> list[TimelineEntry]:
    """Every field value and fact start/end live for `thing_id` at `rev`,
    sorted by date (`None` first), then change kind, then `source_rev`, then
    field name or `fact_id`. Raises `KeyError` if the thing doesn't exist at
    `rev`."""

    thing_row = conn.execute(
        "SELECT kind FROM things WHERE id = ? "
        "AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)",
        (thing_id, rev, rev),
    ).fetchone()
    if thing_row is None:
        raise KeyError(f"no such thing: {thing_id}")
    kind_spec = get_kind(thing_row["kind"])

    sources: dict[int, Source] = {}

    def source_for(source_rev: int) -> Source:
        if source_rev not in sources:
            row = conn.execute(
                "SELECT * FROM revisions WHERE rev = ?", (source_rev,)
            ).fetchone()
            sources[source_rev] = _source_from_revision_row(row)
        return sources[source_rev]

    entries: list[TimelineEntry] = []

    field_rows = conn.execute(
        "SELECT field, value_json, valid_from, from_precision, rev_added "
        "FROM field_values WHERE thing_id = ? "
        "AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)",
        (thing_id, rev, rev),
    ).fetchall()
    for row in field_rows:
        entries.append(
            TimelineEntry(
                date=_decode_date(row["valid_from"], row["from_precision"]),
                change="field",
                field=row["field"],
                value=_decode_field_value(kind_spec, row["field"], row["value_json"]),
                source_rev=row["rev_added"],
                source=source_for(row["rev_added"]),
            )
        )

    fact_rows = conn.execute(
        "SELECT fact_id, category, text, valid_from, from_precision, "
        "valid_until, until_precision, rev_added "
        "FROM facts WHERE thing_id = ? "
        "AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)",
        (thing_id, rev, rev),
    ).fetchall()
    for row in fact_rows:
        source = source_for(row["rev_added"])
        entries.append(
            TimelineEntry(
                date=_decode_date(row["valid_from"], row["from_precision"]),
                change="fact_start",
                fact_id=row["fact_id"],
                text=row["text"],
                category=row["category"],
                source_rev=row["rev_added"],
                source=source,
            )
        )
        if row["valid_until"] is not None:
            entries.append(
                TimelineEntry(
                    date=_decode_date(row["valid_until"], row["until_precision"]),
                    change="fact_end",
                    fact_id=row["fact_id"],
                    text=row["text"],
                    category=row["category"],
                    source_rev=row["rev_added"],
                    source=source,
                )
            )

    entries.sort(key=_sort_key)
    return entries
