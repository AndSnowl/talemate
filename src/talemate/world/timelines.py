"""Entry timelines: every dated fact of an entry, in date order, and for a
sphere the dated facts it gathers (curation spec, goal 6).

`World.timeline` (`timeline.py`) is something else: every change made to
one thing. This is the page's Timeline section and the timeline lines a
prompt is given: a view of dated facts, never a place facts are copied to.

An entry's own lines are its facts with a start date (`valid_from`), of
any category: a "since 947" state and an "in 947" event are both a line at
947. A `timeline` fact with no date has no place on it. A fact that has
ended at the view's date is history and still shows, at its start; one
that starts after the view's date hasn't happened yet, and a removed fact
never shows.

A sphere also gathers (the spec's "What a sphere gathers"):
- **its parts:** things filed in it (`part_of`, any drawer), the things
  filed in those, and, for a place, the places inside it (`parent`), up
  to `reach` steps down;
- **facts naming it:** any dated fact anywhere that references the sphere
  or one of those parts;
- **its members, narrowly:** a tied character's (or real being's) dated
  facts only when they name it -- the rule above, so its births and
  postings stay its own;
- **a branch's past:** its parent's `timeline` facts from before it
  branched off, as `spheres.timeline` gives them.

Nearness alone never adds a line: an entry its facts merely mention feeds
nothing unless one of its facts names the sphere or a part.

Two lines that say much the same with different years disagree
(`repeats.disagreeing_dates`); that's worked out each time the timeline is
read and never stored, so nothing needs undoing.

Lines are rendered plain here (`text`). `world/` knows nothing of how a
held fact reads in a scene, so each line keeps its fact (`fact`, not
dumped) for worldplay to word a held one as belief."""

import json
from collections.abc import Collection, Sequence

from pydantic import BaseModel, Field

from .dates import WorldDate
from .repeats import disagreeing_dates
from .spheres import _chain, _part_of, acts_in_world, is_sphere, timeline
from .view import FactState, ThingState, WorldView, _fact_state_from_row

__all__ = ["TimelineLine", "entry_timeline", "prompt_timeline"]


class TimelineLine(BaseModel):
    """One dated fact on an entry's timeline: whose it is (`here` when it's
    the entry's own), its start date, its end when it has ended by the
    view's date (`until`, ruling C18: it's shown as a span), its text as it
    reads, and the other lines on the same timeline it disagrees with on
    the year."""

    fact_id: str
    owner_id: str
    date: WorldDate
    until: WorldDate | None = None
    text: str
    here: bool
    disagrees_with: list[str] = []
    # the fact as the view read it (`overrides` left empty), so a held one
    # can be worded as belief, or linked, by the reader; never dumped, so
    # a line read back from a dump has none
    fact: FactState | None = Field(default=None, exclude=True)


def _parts(
    view: WorldView, sphere_id: str, reach: int, things: Sequence[ThingState]
) -> list[str]:
    """The ids of the sphere's parts within `reach` steps down, nearest
    first, each once: things filed in it (`part_of`) and in those and, for
    a place sphere, the places inside it and inside any place among them
    (`parent`). A thing that acts in the world (a character, a real being)
    is a member, never a part: its births and postings stay its own."""

    if reach <= 0:
        return []
    filed: dict[str, list[str]] = {}
    inside: dict[str, list[str]] = {}
    kinds = {state.id: state.kind for state in things}
    root = next((state for state in things if state.id == sphere_id), None)
    place_tree = root is not None and root.kind == "place"
    for state in sorted(things, key=lambda thing: thing.created):
        if acts_in_world(state):
            continue
        link = _part_of(state)
        if link is not None:
            filed.setdefault(link[0], []).append(state.id)
        parent = state.fields.get("parent")
        if state.kind == "place" and isinstance(parent, str):
            inside.setdefault(parent, []).append(state.id)

    found: list[str] = []
    seen = {sphere_id}
    frontier = [sphere_id]
    for _ in range(reach):
        below: list[str] = []
        for thing_id in frontier:
            children = filed.get(thing_id, [])
            if place_tree and kinds.get(thing_id) == "place":
                children = children + inside.get(thing_id, [])
            for child in children:
                if child not in seen:
                    seen.add(child)
                    below.append(child)
        found += below
        frontier = below
        if not frontier:
            break
    return found


def _dated_facts(
    view: WorldView, owner_ids: Sequence[str], named: Sequence[str]
) -> list[tuple[str, FactState]]:
    """`(owner id, fact)` for every fact not removed at the view's
    revision, of a live owner, with a start date no later than the view's
    date (ended ones too), that is one of `owner_ids`' or references one
    of `named`."""

    if not owner_ids and not named:
        return []
    things_filter, params = view._live_things_filter("t.")
    rows = view._conn.execute(
        f"""
        SELECT f.row_id, f.thing_id, f.fact_id, f.category, f.text, f.valid_from,
               f.from_precision, f.valid_until, f.until_precision, f.rev_added,
               f.origin_json,
               (SELECT MIN(f0.row_id) FROM facts f0
                WHERE f0.fact_id = f.fact_id) AS created
        FROM facts f
        JOIN things t ON t.id = f.thing_id AND {things_filter}
        WHERE f.rev_added <= ? AND (f.rev_removed IS NULL OR f.rev_removed > ?)
          AND f.valid_from IS NOT NULL AND f.valid_from <= ?
          AND (
            f.thing_id IN (SELECT value FROM json_each(?))
            OR f.row_id IN (
              SELECT fr.row_id FROM fact_refs fr
              WHERE fr.thing_id IN (SELECT value FROM json_each(?))
            )
          )
        """,
        (
            *params,
            view.rev,
            view.rev,
            view._at_instant(),
            json.dumps(list(owner_ids)),
            json.dumps(list(named)),
        ),
    ).fetchall()
    return [(row["thing_id"], _fact_state_from_row(row)) for row in rows]


def _branch_past(view: WorldView, state: ThingState) -> list[tuple[str, FactState]]:
    """`(owner id, fact)` for a branch's inherited timeline facts: those
    `spheres.timeline` gives that aren't its own (its parents', from before
    it branched off), each with the parent it's from."""

    owners = {
        fact.fact_id: other.id
        for other in _chain(view, state.id)[1:]
        for fact in other.facts
    }
    return [
        (owners[fact.fact_id], fact)
        for fact in timeline(view, state.id)
        if fact.fact_id in owners
    ]


def entry_timeline(
    view: WorldView,
    thing_id: str,
    *,
    reach: int,
    threshold: float,
    things: Sequence[ThingState] | None = None,
    disagreements: bool = True,
) -> list[TimelineLine]:
    """The entry's timeline at the view, in date order (then the order the
    facts were written): its own dated facts and, for a sphere, what it
    gathers from its parts within `reach` steps, from facts naming it or a
    part, and from before it branched off (module docstring). Each line's
    `disagrees_with` is the other lines whose words overlap it by at least
    `threshold` with another start year (left empty, and not worked out,
    without `disagreements`). `things`, a snapshot of the
    view's things, saves a sphere a scan. An entry that isn't live at the
    view has no timeline."""

    state = view.thing(thing_id)
    if state is None:
        return []

    found: list[tuple[str, FactState]]
    if is_sphere(state):
        snapshot = view.things() if things is None else things
        parts = _parts(view, thing_id, reach, snapshot)
        found = _dated_facts(view, [thing_id, *parts], [thing_id, *parts])
        found += _branch_past(view, state)
    else:
        found = _dated_facts(view, [thing_id], [])

    unique: dict[str, tuple[str, WorldDate, FactState]] = {}
    for owner_id, fact in found:
        if fact.valid_from is not None:
            unique.setdefault(fact.fact_id, (owner_id, fact.valid_from, fact))
    ordered = sorted(
        unique.values(),
        key=lambda line: (line[1].instant, line[2].created, line[2].fact_id),
    )

    pairs = (
        disagreeing_dates(view, [fact.fact_id for _, _, fact in ordered], threshold)
        if disagreements
        else []
    )
    at = view._at_instant()
    disagrees: dict[str, list[str]] = {}
    for pair in pairs:
        disagrees.setdefault(pair.a, []).append(pair.b)
        disagrees.setdefault(pair.b, []).append(pair.a)

    return [
        TimelineLine(
            fact_id=fact.fact_id,
            owner_id=owner_id,
            date=date,
            until=(
                fact.valid_until
                if fact.valid_until is not None and fact.valid_until.instant <= at
                else None
            ),
            text=view.render(fact.text),
            here=owner_id == thing_id,
            disagrees_with=disagrees.get(fact.fact_id, []),
            fact=fact,
        )
        for owner_id, date, fact in ordered
    ]


def prompt_timeline(
    view: WorldView,
    thing_id: str,
    shown: Collection[str] = (),
    *,
    reach: int,
    threshold: float,
    things: Sequence[ThingState] | None = None,
) -> list[TimelineLine]:
    """The entry's timeline (`entry_timeline`) as a prompt is given it,
    less what the prompt already shows another way: the entry's own dated
    facts that aren't `timeline` facts (a sphere's summary and statements,
    a place sphere's place facts: shown as themselves), and the lines of
    the things in `shown` (given in full elsewhere). A prompt never asks
    which dates disagree, so that isn't worked out."""

    return [
        line
        for line in entry_timeline(
            view,
            thing_id,
            reach=reach,
            threshold=threshold,
            things=things,
            disagreements=False,
        )
        if (
            line.fact is not None and line.fact.category == "timeline"
            if line.here
            else line.owner_id not in shown
        )
    ]
