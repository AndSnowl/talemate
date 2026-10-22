"""Nearness: which entries are near one entry, from the links between them.

One ranking serves every curation feature that needs "what's near" (the
elsewhere list, repeat detection, same-thing candidates, timeline
gathering, prompt context), so none of them hands a prompt the whole
world. It's computed on demand: every call reads the world's links (a few
set-based queries over `things`, `field_values`, `facts` and `fact_refs`)
and walks them in Python. Curation probe 6 (`scripts/dev/nearness_bench.py`)
measured that well under the 50 ms target at 1,000 entries, so no stored
adjacency list is kept.

A step is one link, followed either way:
- a fact reference: the fact's owner and each thing its text references;
- `part_of`: a thing and the sphere it's part of;
- `parent`: a place and the place it lies in, or a branch sphere and the
  sphere it branches from;
- a tie: a character and a sphere it's tied to;
- heritage: a character's `heritage`, a race's `species`, a mix's
  `parents`.

Each link has a weight (`WEIGHTS`); a path scores the product of its
links' weights and a thing keeps its best path within `reach` steps.

Everything is read as the view sees it: only things live at its revision,
field values in force at its date (`WorldView._fetch_fields`' rule), facts
true at its date and ties that hold then. A removed thing is never near,
and never bridges two others.

`CurationSettings` holds the world's knobs, stored in its `meta` table
(`World.curation`).
"""

import json
from collections.abc import Iterable, Sequence
from typing import Any

import structlog
from pydantic import BaseModel, Field

from .spheres import _part_of, _tie_live, _ties
from .view import ThingState, WorldView

log = structlog.get_logger("talemate.world.nearness")

# the starting weights from the plan, kept: a thing's own structure
# (part of, parent) is as near as it gets, a tie nearly so; a mention is
# looser, and shared heritage looser still (every owl-folk character
# shares a species, which says little about any one of them)
WEIGHTS: dict[str, float] = {
    "part_of": 1.0,
    "parent": 1.0,
    "tie": 0.8,
    "reference": 0.6,
    "heritage": 0.5,
}

# the thing-valued fields read as heritage links
_HERITAGE_FIELDS = ("heritage", "species", "parents")
_LINK_FIELDS = ("name", "part_of", "parent", "ties", *_HERITAGE_FIELDS)


class Near(BaseModel):
    thing_id: str
    score: float
    steps: int


class CurationSettings(BaseModel):
    """The world's curation knobs."""

    # how far out: steps through links
    reach: int = Field(default=2, ge=1, le=3)
    # how many entries a prompt brings in
    entries: int = Field(default=12, ge=0)
    # how many facts per entry
    facts_per_entry: int = Field(default=6, ge=0)
    # word overlap at which a new fact reads as a repeat
    repeat_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    # how far out a timeline gathers lines from
    timeline_reach: int = Field(default=2, ge=0, le=3)


Graph = dict[str, dict[str, float]]


def _state(thing_id: str, kind: str, field: str, value: object) -> ThingState:
    """A bare state holding one field, for the `spheres` readers of
    `part_of` and `ties` (built without validation: it's only read)."""

    return ThingState.model_construct(
        id=thing_id, kind=kind, fields={field: value}, facts=[], created=0
    )


def _link(graph: Graph, a: str, b: str, weight: float, live: dict[str, str]) -> None:
    """Add the link `a`-`b` both ways, keeping the stronger of two links
    between the same pair. Links to or from a thing not in `live` (removed,
    never made), and a thing's link to itself, are skipped."""

    if a == b or a not in live or b not in live:
        return
    for x, y in ((a, b), (b, a)):
        out = graph.setdefault(x, {})
        if out.get(y, 0.0) < weight:
            out[y] = weight


def _rows(view: WorldView, sql: str, params: Sequence[object]) -> list[Any]:
    """The query's rows as plain tuples: cheaper than `sqlite3.Row` when
    a whole table is read, as here."""

    cursor = view._conn.cursor()
    cursor.row_factory = None
    return cursor.execute(sql, params).fetchall()


def _live_things(view: WorldView) -> dict[str, str]:
    """`thing id -> kind` for every thing live at the view's revision."""

    things_filter, params = view._live_things_filter("")
    rows = _rows(view, f"SELECT id, kind FROM things WHERE {things_filter}", params)
    return {thing_id: kind for thing_id, kind in rows}


def _field_values(
    view: WorldView, live: dict[str, str]
) -> Iterable[tuple[str, str, object]]:
    """`(thing id, field, decoded value)` for the link fields of live
    things, each the value in force at the view's date: of the rows live
    at the revision and from no later than the date, the one with the
    greatest `valid_from` (NULL lowest), then `row_id` -- the rule of
    `WorldView._fetch_fields`, picked here in Python rather than with a
    window function, which costs three times as much over a whole table."""

    placeholders = ", ".join("?" for _ in _LINK_FIELDS)
    rows = _rows(
        view,
        f"""
        SELECT thing_id, field, value_json, valid_from, row_id FROM field_values
        WHERE field IN ({placeholders})
          AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)
          AND (valid_from IS NULL OR valid_from <= ?)
        """,
        (*_LINK_FIELDS, view.rev, view.rev, view._at_instant()),
    )
    best: dict[tuple[str, str], tuple[tuple[bool, int, int], str]] = {}
    for thing_id, field, value_json, valid_from, row_id in rows:
        if thing_id not in live:
            continue
        key = (valid_from is not None, valid_from or 0, row_id)
        slot = (thing_id, field)
        current = best.get(slot)
        if current is None or current[0] < key:
            best[slot] = (key, value_json)
    for (thing_id, field), (_, value_json) in best.items():
        yield thing_id, field, json.loads(value_json)


def _references(view: WorldView) -> Iterable[tuple[str, str]]:
    """`(owner, referenced thing)` for each reference in a fact live at the
    view's revision and true at its date (`WorldView._fetch_facts`' rule).
    A pair can come more than once."""

    at = view._at_instant()
    rows = _rows(
        view,
        """
        SELECT f.thing_id, fr.thing_id
        FROM fact_refs fr
        JOIN facts f ON f.row_id = fr.row_id
        WHERE f.rev_added <= ? AND (f.rev_removed IS NULL OR f.rev_removed > ?)
          AND (f.valid_from IS NULL OR f.valid_from <= ?)
          AND (f.valid_until IS NULL OR f.valid_until > ?)
        """,
        (view.rev, view.rev, at, at),
    )
    for owner, target in rows:
        yield owner, target


def _graph(view: WorldView) -> tuple[Graph, dict[str, str]]:
    """Every link at the view, and each live thing's name (casefolded, for
    ordering)."""

    live = _live_things(view)
    graph: Graph = {}
    names: dict[str, str] = {}

    for thing_id, field, value in _field_values(view, live):
        if field == "name":
            if isinstance(value, str):
                names[thing_id] = value.casefold()
        elif field == "part_of":
            state = _state(thing_id, live[thing_id], field, value)
            link = _part_of(state)
            if link is not None:
                _link(graph, thing_id, link[0], WEIGHTS["part_of"], live)
        elif field == "parent":
            if isinstance(value, str):
                _link(graph, thing_id, value, WEIGHTS["parent"], live)
        elif field == "ties":
            state = _state(thing_id, live[thing_id], field, value)
            for tie in _ties(state):
                if _tie_live(tie, view.at):
                    _link(graph, thing_id, tie.sphere_id, WEIGHTS["tie"], live)
        else:
            targets = value if isinstance(value, list) else [value]
            for target in targets:
                if isinstance(target, str):
                    _link(graph, thing_id, target, WEIGHTS["heritage"], live)

    for owner, target in _references(view):
        _link(graph, owner, target, WEIGHTS["reference"], live)

    return graph, names


def _walk(graph: Graph, start: str, reach: int) -> dict[str, tuple[float, int]]:
    """`thing id -> (best score, steps of that path)` for every thing
    within `reach` steps of `start`: a hop-limited best-product search
    (Bellman-Ford by layers), so a two-step path of strong links beats a
    one-step weak one, and on a tie the shorter path is kept."""

    best: dict[str, tuple[float, int]] = {start: (1.0, 0)}
    frontier = {start: 1.0}
    for step in range(1, reach + 1):
        improved: dict[str, float] = {}
        for node, score in frontier.items():
            for neighbour, weight in graph.get(node, {}).items():
                candidate = score * weight
                if candidate > best.get(neighbour, (0.0, 0))[0] and candidate > (
                    improved.get(neighbour, 0.0)
                ):
                    improved[neighbour] = candidate
        for node, score in improved.items():
            best[node] = (score, step)
        frontier = improved
        if not frontier:
            break
    del best[start]
    return best


def near(
    view: WorldView, thing_id: str, *, reach: int = 2, limit: int = 20
) -> list[Near]:
    """The live things near `thing_id` at the view, best first (score
    descending, then name, then id), at most `limit` of them, never
    `thing_id` itself. A thing that isn't live at the view has nothing
    near it."""

    if limit <= 0 or reach <= 0:
        return []
    graph, names = _graph(view)
    if thing_id not in graph:
        return []
    found = _walk(graph, thing_id, reach)
    ranked = sorted(
        found.items(),
        key=lambda item: (-item[1][0], names.get(item[0], ""), item[0]),
    )
    return [
        Near(thing_id=other, score=score, steps=steps)
        for other, (score, steps) in ranked[:limit]
    ]
