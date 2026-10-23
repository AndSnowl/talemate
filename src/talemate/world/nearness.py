"""Nearness: which entries are near one entry, from the links between them.

One ranking serves every curation feature that needs "what's near" (the
elsewhere list, repeat detection, same-thing candidates, timeline
gathering, prompt context), so none of them hands a prompt the whole
world. It's computed on demand: every call reads the world's links (a few
set-based queries over `things`, `field_values`, `facts` and `fact_refs`)
and walks them in Python. Curation probe 6 (`scripts/dev/nearness_bench.py`)
measured that well under the 50 ms target at 1,000 entries, so no stored
adjacency list is kept. One prompt can ask for several things' nearness
(a scene's place and each of its cast), so the last few graphs are kept in
memory (`_GRAPHS`), keyed on the world, its revision and the view's date:
a revision's rows never change once it's written, so neither does its
graph. A view read inside an open revision is never cached, since that
revision can still change or be rolled back.

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

The ranking follows the curation probe's fix
(docs/superpowers/probes/2026-10-22-curation.md, "The ranking"): many
things tie on score (a three-step path of 1.0 x 1.0 x 0.6 ties a direct
reference), so ties are broken by fewer steps, then by more direct
references between the two (fact references either way), and only then by
name. And a thing filed in the same sphere as the one asked about -- a
sibling, reached only through that shared `part_of` parent, with no link
of its own to it -- scores 1.0 x 1.0 and would crowd out everything its
facts name, so at most `SIBLINGS` of them per sphere are kept (the rest
are dropped, not moved down). The probe measured these two at 24 missed
targets down to 15.

Everything is read as the view sees it: only things live at its revision,
field values in force at its date (`WorldView._fetch_fields`' rule), facts
true at its date and ties that hold then. A removed thing is never near,
and never bridges two others.

An ignored stub (the owner chose not to make it) is treated as removed,
as name matching does; a plain stub is near like any other thing.

`CurationSettings` (from `curation`) is re-exported here.
"""

import json
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import BaseModel

from .curation import CurationSettings
from .spheres import _part_of, _tie_live, _ties
from .view import ThingState, WorldView

__all__ = ["SIBLINGS", "WEIGHTS", "CurationSettings", "Near", "near"]

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

# the most siblings (things in the same sphere, reached only through it)
# `near` keeps per sphere
SIBLINGS = 3

# the thing-valued fields read as heritage links
_HERITAGE_FIELDS = ("heritage", "species", "parents")
# `existence` isn't a link: it's read first, so a real being's ties count
_LINK_FIELDS = (
    "name",
    "stub",
    "existence",
    "part_of",
    "parent",
    "ties",
    *_HERITAGE_FIELDS,
)


class Near(BaseModel):
    thing_id: str
    score: float
    steps: int


Graph = dict[str, dict[str, float]]


class _Links(BaseModel):
    """What `near` reads besides the graph: each live thing's name
    (casefolded, for ordering), how many references join each pair of
    things (both orders), and the sphere each thing is part of."""

    names: dict[str, str]
    references: dict[tuple[str, str], int]
    part_of: dict[str, str]


def _state(thing_id: str, kind: str, fields: dict[str, object]) -> ThingState:
    """A bare state holding `fields`, for the `spheres` readers of
    `part_of` and `ties` (built without validation: it's only read)."""

    return ThingState.model_construct(
        id=thing_id, kind=kind, fields=fields, facts=[], created=0
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
    view: WorldView, live: dict[str, str], fields: Sequence[str] = _LINK_FIELDS
) -> Iterable[tuple[str, str, object]]:
    """`(thing id, field, decoded value)` for `fields` (the link fields
    unless told) of live things, each the value in force at the view's
    date: of the rows live at the revision and from no later than the
    date, the one with the greatest `valid_from` (NULL lowest), then
    `row_id` -- the rule of `WorldView._fetch_fields`, picked here in
    Python rather than with a window function, which costs three times as
    much over a whole table."""

    placeholders = ", ".join("?" for _ in fields)
    rows = _rows(
        view,
        f"""
        SELECT thing_id, field, value_json, valid_from, row_id FROM field_values
        WHERE field IN ({placeholders})
          AND rev_added <= ? AND (rev_removed IS NULL OR rev_removed > ?)
          AND (valid_from IS NULL OR valid_from <= ?)
        """,
        (*fields, view.rev, view.rev, view._at_instant()),
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


def _graph(view: WorldView) -> tuple[Graph, _Links]:
    """Every link at the view, and the `_Links` `near` orders by."""

    live = _live_things(view)
    graph: Graph = {}
    names: dict[str, str] = {}
    part_of: dict[str, str] = {}
    references: dict[tuple[str, str], int] = {}

    values = list(_field_values(view, live))
    existence: dict[str, object] = {}
    for thing_id, field, value in values:
        if field == "stub" and isinstance(value, dict) and value.get("ignored") is True:
            live.pop(thing_id, None)
        elif field == "existence":
            existence[thing_id] = value

    for thing_id, field, value in values:
        if thing_id not in live or field in ("stub", "existence"):
            continue
        if field == "name":
            if isinstance(value, str) and value.strip():
                names[thing_id] = value.casefold()
        elif field == "part_of":
            state = _state(thing_id, live[thing_id], {field: value})
            link = _part_of(state)
            if link is not None:
                _link(graph, thing_id, link[0], WEIGHTS["part_of"], live)
                if link[0] in live and link[0] != thing_id:
                    part_of[thing_id] = link[0]
        elif field == "parent":
            if isinstance(value, str):
                _link(graph, thing_id, value, WEIGHTS["parent"], live)
        elif field == "ties":
            fields = {field: value}
            if thing_id in existence:
                fields["existence"] = existence[thing_id]
            state = _state(thing_id, live[thing_id], fields)
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
        if owner != target and owner in live and target in live:
            for pair in ((owner, target), (target, owner)):
                references[pair] = references.get(pair, 0) + 1

    return graph, _Links(names=names, references=references, part_of=part_of)


# the most graphs kept: a prompt's few views, and a world or two open
GRAPH_CACHE_SIZE = 8
_GraphKey = tuple[str, str, int, int | None, tuple[tuple[str, float], ...]]
_GRAPHS: "OrderedDict[_GraphKey, tuple[Graph, _Links]]" = OrderedDict()


def _graph_key(view: WorldView) -> _GraphKey | None:
    """What a view's graph is cached under: its world's database file and
    id, its revision, its date's instant (`None`: the latest telling) and
    the `WEIGHTS` it was built with (a probe script tries others); `None`
    (not cached) inside an open transaction, or for a revision that isn't
    written (yet, or any more)."""

    conn = view._conn
    if conn.in_transaction:
        return None
    written = conn.execute("SELECT 1 FROM revisions WHERE rev = ?", (view.rev,))
    if written.fetchone() is None:
        return None
    world = conn.execute("SELECT value FROM meta WHERE key = 'id'").fetchone()
    path = conn.execute("PRAGMA database_list").fetchone()
    return (
        str(path[2]) if path is not None else "",
        str(world[0]) if world is not None else "",
        view.rev,
        view.at.instant if view.at is not None else None,
        tuple(sorted(WEIGHTS.items())),
    )


def _cached_graph(view: WorldView) -> tuple[Graph, _Links]:
    """`_graph(view)`, from the cache when the same world, revision and
    date were read lately (`_graph_key`). The graph is shared: never
    changed by its readers."""

    key = _graph_key(view)
    if key is None:
        return _graph(view)
    found = _GRAPHS.get(key)
    if found is not None:
        _GRAPHS.move_to_end(key)
        return found
    found = _graph(view)
    _GRAPHS[key] = found
    while len(_GRAPHS) > GRAPH_CACHE_SIZE:
        _GRAPHS.popitem(last=False)
    return found


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
    view: WorldView,
    thing_id: str,
    *,
    reach: int = 2,
    limit: int = 20,
    siblings: int | None = SIBLINGS,
) -> list[Near]:
    """The live things near `thing_id` at the view, best first, at most
    `limit` of them, never `thing_id` itself. Best first is: score
    descending, then fewer steps, then more references joining the two
    (fact references either way), then name (unnamed things last), then
    id. At most `siblings` things per sphere that are part of the same
    sphere as `thing_id` and have no link of their own to it are kept
    (`None`: no cap). A thing that isn't live at the view, or is an
    ignored stub, has nothing near it."""

    if limit <= 0 or reach <= 0:
        return []
    graph, links = _cached_graph(view)
    if thing_id not in graph:
        return []
    found = _walk(graph, thing_id, reach)
    ranked = sorted(
        found.items(),
        key=lambda item: (
            # rounded: two paths of the same links multiplied in another
            # order can differ in the last bits
            -round(item[1][0], 9),
            item[1][1],
            -links.references.get((thing_id, item[0]), 0),
            item[0] not in links.names,
            links.names.get(item[0], ""),
            item[0],
        ),
    )
    home = links.part_of.get(thing_id)
    direct = graph[thing_id]
    kept: list[Near] = []
    per_sphere: dict[str, int] = {}
    for other, (score, steps) in ranked:
        sphere = links.part_of.get(other)
        if (
            siblings is not None
            and home is not None
            and sphere == home
            and other not in direct
        ):
            if per_sphere.get(sphere, 0) >= siblings:
                continue
            per_sphere[sphere] = per_sphere.get(sphere, 0) + 1
        kept.append(Near(thing_id=other, score=score, steps=steps))
        if len(kept) == limit:
            break
    return kept
