"""Re-pointing a stub onto an entry: the stub was a name for something the
world already has.

`repoint_stub` moves everything that names the stub to the target, in one
revision, so one undo restores it all:

- every fact link to it, keeping its words (a link in the target's own
  facts becomes those words, plain: a thing never links to itself);
- every field that points at it (`thing`, `things`, `shares`), every
  thing filed in it (`part_of`) and every tie to it or `within` it
  (`ties`), at each story date the field holds it, and the exceptions filed under such a
  tie (their origin `tie`);
- the stub's own facts, moved to the target (`copy_facts`: copied as
  new facts with their dates and origin, a category the target's kind
  lacks becoming `default_category`'s, every override of one pointed at
  its copy, the original removed); a fact never changes thing, since
  replay and undo key a fact by its id;
- the stub's own filing (`part_of`): the target is filed where the stub
  was, unless it's filed already (it stays where it is, and a note says
  so) or can't be (a note says why);
- the stub's other own fields the target has none of (never one naming
  the target or a thing inside it, nor a sphere's template, agent or
  drawers onto a target that isn't a sphere);
- its names: the stub's name, its other names and each distinct shown
  text become the target's common other names, unless the target or
  another thing already has that name.

Then the stub is removed. Refused before anything is written (a
`ValueError` naming every use that blocks it): a use by a scene, a field
whose kind of thing the target isn't (a place's parent can't be lore), a
filing or tie when the target isn't a sphere, a parent or filing that
would put a thing inside itself, a mix's parents or shares that would name
the target twice, and a use by the target itself. Prose is refreshed only
where its input changed (`RepointResult.prose`).

`plan_repoint` reads and decides it all without writing, and its
`RepointPlan.write` writes it into a revision, so another writer can
re-point a stub in its own revision (`create.accept_preview` with a same
target, for the stub it expanded).

The same mover folds any thing into another of its kind, or a place and
a sphere either way (ruling C17), for `worldplay.merge` (`plan_merge`):
the same refusals, and a thing merged into itself; a sphere with parts
filed in it or people tied to it can't fold into a thing that isn't a
sphere, and a full entry doesn't fold into a stub (re-point the stub
instead). The target's own fields naming the stub aren't refused but
redirected: the merged entry sits where the stub sat (its parent and
filing take the stub's, cleared when the stub has none or they'd make a
loop; a list drops the stub), each with a note. A sphere merged into a
sphere keeps its drawers (ruling C15): each is the target's of that id,
else the target's of that type and title, else added to the target's, and
the parts and statements filed in it follow. It differs from a re-point
in what the owner picks:
- only the facts named move (`fact_ids`, the owner's ticks); the rest go
  with the thing;
- the main name (`main_name`, either side's): the other becomes a common
  other name, and both sides' other names carry over (each keeping its
  tag), one of the into-side's that is now the main name dropped;
- a character's or real being's ties are combined, one per sphere and
  role, the into-side's kept; a tie re-pointed `within` the into-side to a
  sphere it won't be inside after the merge is within no part (noted);
- of the links' words, only `link_akas` become other names;
- the into-side's prose is always refreshed.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Mapping, Sequence

import structlog
from pydantic import BaseModel

from talemate.world import spheres
from talemate.world.kinds import (
    HERITAGE_KINDS,
    PART_OF_KINDS,
    UNSORTED_DRAWER_ID,
    get_kind,
)
from talemate.world.refs import REF_PATTERN, ref
from talemate.world.prose import UNRENDERED_FIELDS
from talemate.world.store import Revision, Source, World
from talemate.world.view import FactState, ThingState, WorldView
from talemate.worldplay.create import (
    default_category,
    drawer_types_for,
    part_of_since,
    prose_reads,
)
from talemate.worldplay.links import name_key
from talemate.worldplay.references import thing_references

log = structlog.get_logger("talemate.worldplay.repoint")

__all__ = [
    "RepointPlan",
    "RepointResult",
    "copy_facts",
    "move_fact",
    "plan_merge",
    "plan_repoint",
    "repoint_stub",
]

# the kinds a field may point at, where that isn't the stub's own kind
FIELD_TARGET_KINDS: dict[str, tuple[str, ...]] = {
    "heritage": HERITAGE_KINDS,
    "parents": HERITAGE_KINDS,
    "species": ("species",),
    "culture": ("sphere", "culture"),
    "cultures": ("sphere", "culture"),
    "drops": PART_OF_KINDS,
}

# the stub's own fields that aren't carried over as they are
_OWN_HANDLED = ("name", "aka", "stub", "part_of")

# a sphere's own fields, never carried onto a target that isn't one
_SPHERE_FIELDS = ("template", "agent", "drawers")

# a moved fact's category, when the target's kind lacks its own
_CATCH_ALL = ("general", "about")


class RepointResult(BaseModel):
    stub_name: str
    target_name: str
    # fact links moved
    links: int
    # the other names the target took
    aka_added: list[str]
    # the stub's own facts the target took
    facts_moved: int
    # what didn't carry over as the stub had it, for the owner
    notes: list[str]
    # the things whose prose input changed (facts, rendered fields)
    prose: list[str]


class _FieldUse(BaseModel):
    thing_id: str
    field: str
    date: object
    value: object
    # the value at `date` is retired, not replaced (a merge's redirect)
    clear: bool = False


def _where(view: WorldView, sphere_id: str, drawer_id: str) -> str:
    sphere = view.name_of(sphere_id) or sphere_id
    drawer = next(
        (d for d in spheres.drawers(view, sphere_id) if d.id == drawer_id),
        spheres.UNSORTED,
    )
    return f"{sphere} · {drawer.title}"


def _drawer_for(view: WorldView, sphere_id: str, drawer_id: str, kind: str) -> str:
    """`drawer_id` if the sphere has it and a `kind` thing goes in it,
    else Unsorted."""

    drawer = next(
        (d for d in spheres.drawers(view, sphere_id) if d.id == drawer_id), None
    )
    if drawer is None or drawer.type not in drawer_types_for(kind):
        return UNSORTED_DRAWER_ID
    return drawer_id


def _repointed_tie(tie: object, stub_id: str, target_id: str) -> object:
    """A stored tie with the stub, as its sphere or the part it's
    `within`, made the target. A tie whose part would become its sphere
    is within no part."""

    if not isinstance(tie, dict):
        return tie
    moved = dict(tie)
    if moved.get("sphere") == stub_id:
        moved["sphere"] = target_id
    if moved.get("within") == stub_id:
        moved["within"] = target_id
    if "within" in moved and moved["within"] == moved.get("sphere"):
        moved["within"] = None
    return moved


def _field_uses(
    world: World,
    view: WorldView,
    stub: ThingState,
    target: ThingState,
    blocked: list[str],
    notes: list[str],
    *,
    drawer: Callable[[str, str], str] | None = None,
    skip_target: bool = False,
) -> list[_FieldUse]:
    """Every field value of another thing naming the stub, rewritten to
    name the target, at its date. What can't be is added to `blocked`.
    `drawer` (a merge's) gives the drawer a part filed in the stub at
    `(drawer id, kind)` goes in; with `skip_target`, the target's own
    values are left to the caller (a merge redirects them)."""

    uses: list[_FieldUse] = []
    is_sphere = spheres.is_sphere(target)
    for state in view.things():
        if state.id == stub.id or (skip_target and state.id == target.id):
            continue
        name = view.name_of(state.id) or state.id
        types = {spec.name: spec.type for spec in get_kind(state.kind).fields}
        for entry in world.timeline(state.id):
            if entry.change != "field" or entry.field is None:
                continue
            field, value = entry.field, entry.value
            label = f"{name}'s {field.replace('_', ' ')}"
            new: object = None
            if field == "part_of":
                if not (isinstance(value, dict) and value.get("sphere") == stub.id):
                    continue
                if not is_sphere:
                    blocked.append(f"{label} needs a sphere")
                    continue
                if spheres.sits_in(view, target.id, state.id):
                    blocked.append(f"{label} would put it inside itself")
                    continue
                new = {
                    "sphere": target.id,
                    "drawer": (
                        drawer(str(value.get("drawer")), state.kind)
                        if drawer is not None
                        else _drawer_for(
                            view, target.id, str(value.get("drawer")), state.kind
                        )
                    ),
                }
            elif field == "ties":
                if not isinstance(value, list):
                    continue
                to_stub = any(
                    isinstance(tie, dict) and tie.get("sphere") == stub.id
                    for tie in value
                )
                within_stub = any(
                    isinstance(tie, dict) and tie.get("within") == stub.id
                    for tie in value
                )
                if not (to_stub or within_stub):
                    continue
                if to_stub and not is_sphere:
                    blocked.append(f"{label} needs a sphere")
                    continue
                tied = to_stub and any(
                    isinstance(tie, dict) and tie.get("sphere") == target.id
                    for tie in value
                )
                if tied:
                    notes.append(
                        f"{name} was tied to both; the tie to"
                        f" {view.name_of(target.id)} is kept"
                    )
                new = [
                    _repointed_tie(tie, stub.id, target.id)
                    for tie in value
                    if not (
                        tied and isinstance(tie, dict) and tie.get("sphere") == stub.id
                    )
                ]
            else:
                kind = types.get(field)
                if kind == "thing" and value == stub.id:
                    new = target.id
                elif kind == "things" and isinstance(value, list) and stub.id in value:
                    if field == "parents" and target.id in value:
                        blocked.append(
                            f"{label} would name {view.name_of(target.id)} twice"
                        )
                        continue
                    new = []
                    for thing_id in value:
                        swapped = target.id if thing_id == stub.id else thing_id
                        if swapped not in new:
                            new.append(swapped)
                elif (
                    kind == "shares"
                    and isinstance(value, list)
                    and any(
                        isinstance(share, dict) and share.get("thing_id") == stub.id
                        for share in value
                    )
                ):
                    if any(
                        isinstance(share, dict) and share.get("thing_id") == target.id
                        for share in value
                    ):
                        blocked.append(
                            f"{label} would name {view.name_of(target.id)} twice"
                        )
                        continue
                    new = [
                        {**share, "thing_id": target.id}
                        if isinstance(share, dict) and share.get("thing_id") == stub.id
                        else share
                        for share in value
                    ]
                else:
                    continue
                allowed = FIELD_TARGET_KINDS.get(field, (stub.kind,))
                if target.kind not in allowed:
                    blocked.append(f"{label} can't be a {target.kind}")
                    continue
                if (
                    field == "parent"
                    and state.id != target.id
                    and spheres.sits_in(view, target.id, state.id)
                ):
                    blocked.append(f"{label} would put it inside itself")
                    continue
            if state.id == target.id:
                blocked.append(f"{label} would point at itself")
                continue
            uses.append(
                _FieldUse(thing_id=state.id, field=field, date=entry.date, value=new)
            )
    return uses


def _rewriter(
    view: WorldView, stub_id: str, target_id: str, shown_texts: list[str]
) -> Callable[[str, str, bool], tuple[str, int]]:
    """A function `(text, owner after, count) -> (text, links moved)`:
    links to the stub point at the target (their words, plain, in the
    target's own facts), and in the target's own facts its links to itself
    become words too. Each moved link's words go in `shown_texts`."""

    def rewrite(text: str, owner: str, count: bool) -> tuple[str, int]:
        moved = 0

        def one(found: re.Match[str]) -> str:
            nonlocal moved
            linked = found.group(1)
            if linked not in (stub_id, target_id):
                return found.group(0)
            shown = found.group(2) or "".join(
                seg.text for seg in view.segments(found.group(0))
            )
            if linked == stub_id:
                if count:
                    moved += 1
                    shown_texts.append(shown)
                return shown if owner == target_id else ref(target_id, shown)
            return shown if owner == target_id else found.group(0)

        return REF_PATTERN.sub(one, text), moved

    return rewrite


def _other_name_keys(view: WorldView, skip: set[str]) -> set[str]:
    keys: set[str] = set()
    for state in view.things():
        if state.id in skip:
            continue
        keys.add(name_key(view.name_of(state.id) or ""))
        for entry in state.fields.get("aka") or []:
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                keys.add(name_key(entry["name"]))
    keys.discard("")
    return keys


class _Job(BaseModel):
    """What one re-point reads and decides, before it writes."""

    model_config = {"arbitrary_types_allowed": True}

    world: World
    view: WorldView
    stub: ThingState
    target: ThingState
    stub_name: str
    target_name: str
    notes: list[str] = []
    # a merge (`plan_merge`): any thing, not a stub, into any thing
    merge: bool = False
    # a merge's facts to move (the owner's ticks); `None`, all of them
    fact_ids: list[str] | None = None
    # a merge's main name, either side's; `None`, the target's own
    main_name: str | None = None
    # a merge's link words to add as other names; `None`, every one
    link_akas: list[str] | None = None
    # a sphere merge's drawers (ruling C15): the stub's drawer id -> the
    # target's, the drawers the target has after (its own, those it
    # inherits), and its own list to write when it grew (else `None`)
    drawer_map: dict[str, str] = {}
    available: list[spheres.Drawer] = []
    drawers: list[dict[str, object]] | None = None
    # the target's own fields that named the stub, redirected
    redirected: set[str] = set()
    # a merge's other names added from the links' words
    link_names: list[str] = []

    @property
    def verb(self) -> str:
        return "merged into" if self.merge else "re-pointed to"


def _fact_changes(
    job: _Job, shown_texts: list[str]
) -> tuple[dict[str, dict], int, list]:
    """`(changes, links, own facts)`: each other fact's changes (`text`, its
    links to the stub pointed at the target; `origin`, a tie to the stub
    filed under the target, a belief the stub held held by the target),
    the fact links moved, and the stub's own
    facts (`FactState`s), which `copy_facts` moves to the target."""

    view, stub_id, target_id = job.view, job.stub.id, job.target.id
    rewrite = _rewriter(view, stub_id, target_id, shown_texts)
    changes: dict[str, dict] = {}
    links = 0
    for owner, fact in view.referencing(stub_id, any_date=True):
        if owner == stub_id or fact.fact_id in changes:
            continue
        text, moved = rewrite(fact.text or "", owner, True)
        links += moved
        changes[fact.fact_id] = {"text": text}
    # a character's exception filed under a tie to the stub, and any fact
    # the stub holds as a belief, go over to the target
    own_ids = {fact.fact_id for fact in job.world.live_facts(stub_id)}
    for fact in job.world.live_facts():
        origin = fact.origin or {}
        keys = [key for key in ("tie", "held_by") if origin.get(key) == stub_id]
        if fact.fact_id in own_ids:
            continue
        if keys:
            changes.setdefault(fact.fact_id, {})["origin"] = {
                **origin,
                **{key: target_id for key in keys},
            }
    own = job.world.live_facts(stub_id)
    if job.fact_ids is not None:
        wanted = set(job.fact_ids)
        own = [fact for fact in own if fact.fact_id in wanted]
    return changes, links, own


def _relinked(
    view: WorldView, text: str, same: set[str], target_id: str, plain: bool
) -> str:
    """`text` with its links to `same` (the target, and what stands for it)
    pointed at the target: as their words, plain, when `plain` (a thing
    never links to itself)."""

    def one(found: re.Match[str]) -> str:
        if found.group(1) not in same:
            return str(found.group(0))
        shown = str(
            found.group(2) or "".join(seg.text for seg in view.segments(found.group(0)))
        )
        return shown if plain else ref(target_id, shown)

    return REF_PATTERN.sub(one, text)


def _moved_category(kind: str, category: str, dated: bool) -> str:
    """`category`, if a `kind` thing has it; else `default_category`'s, a
    catch-all one, or its kind's first."""

    categories = get_kind(kind).categories
    if category in categories:
        return category
    fallback = default_category(kind, dated)
    if fallback in categories:
        return fallback
    return next((c for c in _CATCH_ALL if c in categories), categories[0])


def copy_facts(
    rev: Revision,
    view: WorldView,
    fact_ids: Sequence[str],
    target_id: str,
    *,
    plain_self_links: bool,
    standing_for: Sequence[str] = (),
    drawer_map: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Move the facts `fact_ids` (of any owners) onto `target_id`, in `rev`,
    the way a fact changes thing (ruling R1): each is copied as a new fact
    and the original removed, since replay and undo key a fact by its id.
    Returns `old id -> new id`. `view` is the revision's own
    (`world.view()` inside it), so what `rev` wrote is seen.

    Each copy keeps its dates and origin; a category the target's kind
    lacks becomes `default_category`'s (`_moved_category`). Its holder
    stays its holder, and one its old owner held implicitly (a beliefs
    drawer's statement, `spheres.held_by`) is written into its origin, so
    it stays a belief away from the drawer; a statement's drawer the target
    has none of (by id) is dropped from its origin. Links to the target, and to
    `standing_for` (a stub being re-pointed onto it, whose holdings become
    the target's too), point at the target: as plain words, with
    `plain_self_links`. An override among the moved facts points at its
    copy, the copies' own and every other live fact's, on any date; so
    does an exception's `rejects_fact` (its origin). With `drawer_map`
    (a sphere merged into a sphere: the old drawer id -> the target's), a
    statement's drawer is mapped first.

    A `KeyError` for a fact or target that isn't live."""

    target = view.thing(target_id)
    if target is None:
        raise KeyError(f"no such thing: {target_id}")
    same = {target_id, *standing_for}
    found: list[tuple[str, FactState]] = []
    for fact_id in dict.fromkeys(fact_ids):
        hit = view.fact(fact_id)
        if hit is None:
            raise KeyError(f"no such fact: {fact_id}")
        found.append(hit)
    moving = {fact.fact_id for _owner, fact in found}
    copies: dict[str, str] = {}
    # each copy's origin, as written
    origins: dict[str, dict[str, object] | None] = {}
    for owner_id, fact in found:
        origin = dict(fact.origin) if fact.origin is not None else None
        owner = view.thing(owner_id)
        if owner is not None and "held_by" not in (origin or {}):
            holder = spheres.held_by(view, fact, owner)
            if holder is not None:
                origin = spheres.with_held_by(origin, holder)
        if origin is not None and origin.get("held_by") in standing_for:
            origin["held_by"] = target_id
        if origin is not None and drawer_map and origin.get("drawer") in drawer_map:
            origin["drawer"] = drawer_map[str(origin["drawer"])]
        # a statement's drawer, when the target has none of that id
        if (
            origin is not None
            and "drawer" in origin
            and origin["drawer"] not in {d.id for d in spheres.drawers(view, target_id)}
        ):
            del origin["drawer"]
        origins[fact.fact_id] = origin
        copies[fact.fact_id] = rev.add_fact(
            target_id,
            _moved_category(target.kind, fact.category, fact.valid_from is not None),
            _relinked(view, fact.text, same, target_id, plain_self_links),
            valid_from=fact.valid_from,
            valid_until=fact.valid_until,
            origin=origin,
            overrides=[o for o in fact.overrides if o not in moving] or None,
        )
    for _owner, fact in found:
        if any(o in moving for o in fact.overrides):
            rev.correct_fact(
                copies[fact.fact_id],
                overrides=[copies.get(o, o) for o in fact.overrides],
            )
    for _owner, fact in view.overriding(list(moving)):
        if fact.fact_id not in moving:
            rev.correct_fact(
                fact.fact_id, overrides=[copies.get(o, o) for o in fact.overrides]
            )
    for _owner, fact in found:
        rejected = (fact.origin or {}).get("rejects_fact")
        if rejected in moving:
            origin = dict(origins[fact.fact_id] or {})
            origin["rejects_fact"] = copies[str(rejected)]
            rev.correct_fact(copies[fact.fact_id], origin=origin)
    copied = set(copies.values())
    for _owner, fact in view.rejecting(list(moving)):
        if fact.fact_id in moving or fact.fact_id in copied:
            continue
        origin = dict(fact.origin or {})
        origin["rejects_fact"] = copies[str(origin["rejects_fact"])]
        rev.correct_fact(fact.fact_id, origin=origin)
    for fact_id in moving:
        rev.remove_fact(fact_id)
    return copies


def _own_filing(job: _Job) -> tuple[dict, object] | None:
    """`(part_of, since)` filing the target where the stub was, or `None`
    (with a note when it stays elsewhere or can't be filed there)."""

    view, target = job.view, job.target
    own = job.stub.fields.get("part_of")
    if "part_of" in job.redirected:
        # the target was filed in the stub: it takes the stub's filing
        # there (`_self_uses`)
        return None
    if not (isinstance(own, dict) and isinstance(own.get("sphere"), str)):
        return None
    sphere_id, drawer_id = own["sphere"], str(own.get("drawer"))
    if view.thing(sphere_id) is None:
        return None
    held = target.fields.get("part_of")
    there = _where(view, sphere_id, drawer_id)
    if isinstance(held, dict) and isinstance(held.get("sphere"), str):
        if (held["sphere"], held.get("drawer")) != (sphere_id, drawer_id):
            job.notes.append(
                f"{job.target_name} stays in"
                f" {_where(view, held['sphere'], str(held.get('drawer')))};"
                f" {job.stub_name} was in {there}"
            )
        return None
    if target.kind not in PART_OF_KINDS:
        job.notes.append(
            f"{job.target_name} isn't filed in {there}:"
            f" a {target.kind} is never part of a sphere"
        )
        return None
    if spheres.sits_in(view, sphere_id, target.id):
        job.notes.append(
            f"{job.target_name} isn't filed in {there}: it would be inside itself"
        )
        return None
    drawer = _drawer_for(view, sphere_id, drawer_id, target.kind)
    if drawer != drawer_id:
        job.notes.append(
            f"{job.target_name} is filed in {_where(view, sphere_id, drawer)}:"
            f" a {target.kind} doesn't go in {there}"
        )
    return (
        {"sphere": sphere_id, "drawer": drawer},
        part_of_since(job.world, target.id, strict=False),
    )


def _names_target(job: _Job, value: object) -> bool:
    """Whether a carried value names the target, or a thing inside it."""

    ids = (
        [value] if isinstance(value, str) else value if isinstance(value, list) else []
    )
    return any(
        isinstance(thing_id, str)
        and (
            thing_id == job.target.id
            or spheres.sits_in(job.view, thing_id, job.target.id)
        )
        for thing_id in ids
    )


def _carried_fields(job: _Job) -> dict[str, object]:
    """The stub's other own fields the target takes: those its kind has
    and it has no value for, never one naming the target (or a thing
    inside it), nor a sphere's template, agent or drawers onto a target
    that isn't a sphere. The rest are noted, unless the target holds the
    same value."""

    target = job.target
    types = {spec.name: spec.type for spec in get_kind(target.kind).fields}
    is_sphere = spheres.is_sphere(target)
    carried: dict[str, object] = {}
    for field, value in job.stub.fields.items():
        if field in _OWN_HANDLED or value is None:
            continue
        if job.merge and field in ("ties", "drawers"):
            # combined: one tie per sphere and role (`_merged_ties`), the
            # drawers matched or added (`_drawer_plan`)
            continue
        if field in job.redirected:
            # the target's own value named the stub: redirected
            # (`_self_uses`)
            continue
        held = target.fields.get(field)
        if held == value:
            continue
        if field in _SPHERE_FIELDS and not is_sphere:
            job.notes.append(
                f"{job.stub_name}'s {field} isn't carried over:"
                f" {job.target_name} isn't a sphere"
            )
        elif types.get(field) in ("thing", "things") and _names_target(job, value):
            job.notes.append(
                f"{job.stub_name}'s {field} isn't carried over:"
                f" it names {job.target_name}, or a place inside it"
            )
        elif field in types and held is None:
            carried[field] = value
        else:
            job.notes.append(f"{job.stub_name}'s {field} isn't carried over")
    return carried


def _names(job: _Job, shown_texts: list[str]) -> tuple[list[dict], list[str]]:
    """`(aka, added)`: the target's other names with the stub's name, its
    other names and the links' shown texts added (common, not everyday),
    unless the target or another thing has that name already."""

    view, target = job.view, job.target
    aka = list(target.fields.get("aka") or [])
    held = {name_key(job.target_name)} | {
        name_key(entry["name"]) for entry in aka if isinstance(entry, dict)
    }
    taken = _other_name_keys(view, {job.stub.id, target.id})
    stub_aka = [
        entry["name"]
        for entry in job.stub.fields.get("aka") or []
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    ]
    added: list[str] = []
    for name in [job.stub_name, *stub_aka, *shown_texts]:
        name = " ".join(name.split())
        key = name_key(name)
        if not key or key in held or key in taken:
            continue
        held.add(key)
        added.append(name)
        aka.append({"name": name, "tag": "common", "everyday": False})
    return aka, added


def _merge_names(job: _Job, shown_texts: list[str]) -> tuple[list[dict], list[str]]:
    """A merge's `(aka, added)`: the target's other names, less one that is
    now the main name, then the side's name that isn't the main name, the
    stub's other names (each keeping its tag) and the links' shown texts,
    added unless the main name, the list or another thing has that name
    already. None is everyday but the target's own."""

    view, target = job.view, job.target
    main = job.main_name or job.target_name
    main_key = name_key(main)
    aka = [
        entry
        for entry in target.fields.get("aka") or []
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("name"), str)
            and name_key(entry["name"]) == main_key
        )
    ]
    held = {main_key} | {
        name_key(entry["name"])
        for entry in aka
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    taken = _other_name_keys(view, {job.stub.id, target.id})
    other = job.stub_name if main_key != name_key(job.stub_name) else job.target_name
    wanted: list[tuple[str, str]] = [(other, "common")]
    for entry in job.stub.fields.get("aka") or []:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            tag = entry.get("tag")
            wanted.append((entry["name"], tag if isinstance(tag, str) else "common"))
    if job.link_akas is not None:
        allowed = {name_key(name) for name in job.link_akas}
        shown_texts = [text for text in shown_texts if name_key(text) in allowed]
    names_first = len(wanted)
    wanted += [(text, "common") for text in shown_texts]
    added: list[str] = []
    job.link_names = []
    for index, (name, tag) in enumerate(wanted):
        name = " ".join(name.split())
        key = name_key(name)
        if not key or key in held or key in taken:
            continue
        held.add(key)
        added.append(name)
        if index >= names_first:
            job.link_names.append(name)
        aka.append({"name": name, "tag": tag, "everyday": False})
    return aka, added


def _tie_key(tie: object) -> tuple[object, object]:
    return (tie.get("sphere"), tie.get("role")) if isinstance(tie, dict) else ("", "")


def _merged_ties(job: _Job) -> list[dict] | None:
    """The target's ties with the stub's added, one per sphere and role
    (the target's kept), when the stub has ties; `None` when there's
    nothing to write. A tie to the target itself, or onto a target that
    can't be tied, is noted instead."""

    own = [t for t in job.stub.fields.get("ties") or [] if isinstance(t, dict)]
    if not own or not spheres.acts_in_world(job.stub):
        return None
    if not spheres.acts_in_world(job.target):
        job.notes.append(
            f"{job.stub_name}'s ties aren't carried over:"
            f" {job.target_name} can't be tied"
        )
        return None
    ties = [t for t in job.target.fields.get("ties") or [] if isinstance(t, dict)]
    have = {_tie_key(tie) for tie in ties}
    added = False
    for tie in own:
        if tie.get("sphere") == job.target.id:
            job.notes.append(
                f"{job.stub_name}'s tie to {job.target_name} isn't carried over"
            )
            continue
        if _tie_key(tie) in have:
            continue
        have.add(_tie_key(tie))
        ties.append(tie)
        added = True
    return ties if added else None


def _holders(world: World, view: WorldView, sphere_id: str) -> list[str]:
    """The names of the things filed in the sphere, or tied to it, at any
    story date."""

    found: list[str] = []
    for state in view.things():
        for entry in world.timeline(state.id):
            value = entry.value
            if entry.change != "field":
                continue
            if (
                entry.field == "part_of"
                and isinstance(value, dict)
                and value.get("sphere") == sphere_id
            ) or (
                entry.field == "ties"
                and isinstance(value, list)
                and any(
                    isinstance(tie, dict) and tie.get("sphere") == sphere_id
                    for tie in value
                )
            ):
                found.append(view.name_of(state.id) or state.id)
                break
    return found


def _within_checked(job: _Job, uses: list[_FieldUse], filing: object) -> None:
    """A merge's ties re-pointed `within` the target: within no part when
    the target won't be inside that tie's sphere (filed there already, or
    taking the stub's `filing` there), with a note."""

    view, target_id = job.view, job.target.id
    for use in uses:
        if use.field != "ties" or not isinstance(use.value, list):
            continue
        fixed: list[object] = []
        for tie in use.value:
            if isinstance(tie, dict) and tie.get("within") == target_id:
                sphere = str(tie.get("sphere"))
                inside = spheres.within_sphere(view, target_id, sphere) or (
                    filing is not None
                    and spheres.within_sphere(view, job.stub.id, sphere)
                )
                if not inside:
                    tie = {**tie, "within": None}
                    job.notes.append(
                        f"{view.name_of(use.thing_id)}'s tie to"
                        f" {view.name_of(sphere)} is within no part:"
                        f" {job.target_name} isn't inside it"
                    )
            fixed.append(tie)
        use.value = fixed


def _norm_title(title: str) -> str:
    return " ".join(title.split()).casefold()


def _drawer_plan(job: _Job) -> None:
    """A sphere merged into a sphere (ruling C15): each of the stub's own
    drawers is the target's of the same id, else one of the same type and
    title (case and spaces aside), else a copy added to the target's own
    drawers (a fresh id when its id is taken). The target's drawers after
    count its own and those it inherits from its parent after the merge
    (the stub's parent, when its parent was the stub)."""

    view, stub, target = job.view, job.stub, job.target
    if not (spheres.is_sphere(stub) and spheres.is_sphere(target)):
        return
    own = [d for d in target.fields.get("drawers") or [] if isinstance(d, dict)]
    available = list(spheres._own_drawers(target))
    parent = target.fields.get("parent")
    if parent == stub.id:
        parent = stub.fields.get("parent")
    if (
        isinstance(parent, str)
        and parent not in (stub.id, target.id)
        and not spheres.sits_in(view, parent, target.id)
    ):
        ids = {d.id for d in available}
        available += [d for d in spheres.drawers(view, parent) if d.id not in ids]
    grown = list(own)
    added: list[str] = []
    for raw in stub.fields.get("drawers") or []:
        try:
            drawer = spheres.Drawer.model_validate(raw)
        except ValueError:
            continue
        same = next((d for d in available if d.id == drawer.id), None) or next(
            (
                d
                for d in available
                if d.type == drawer.type
                and _norm_title(d.title) == _norm_title(drawer.title)
            ),
            None,
        )
        if same is not None:
            job.drawer_map[drawer.id] = same.id
            continue
        new_id = drawer.id
        taken = {d.id for d in available}
        while new_id in taken:
            new_id = secrets.token_hex(4)
        copy = drawer.model_copy(update={"id": new_id})
        grown.append(copy.model_dump())
        available.append(copy)
        job.drawer_map[drawer.id] = new_id
        added.append(drawer.title)
    job.available = available
    if added:
        job.drawers = grown
        job.notes.append(
            f"{job.target_name} takes {job.stub_name}'s drawers: {', '.join(added)}"
        )


def _merge_drawer(job: _Job) -> Callable[[str, str], str]:
    """The drawer of the target a part filed in the stub's `drawer id`
    goes in, for its `kind`: the mapped one (`_drawer_plan`), when a
    `kind` thing goes in it, else Unsorted; one the map lacks (an
    inherited drawer, Unsorted) as a re-point files it."""

    def pick(drawer_id: str, kind: str) -> str:
        mapped = job.drawer_map.get(drawer_id)
        if mapped is None:
            return _drawer_for(job.view, job.target.id, drawer_id, kind)
        drawer = next((d for d in job.available if d.id == mapped), None)
        if drawer is None or drawer.type not in drawer_types_for(kind):
            return UNSORTED_DRAWER_ID
        return mapped

    return pick


def _inside_either(job: _Job, thing_id: str) -> bool:
    """Whether `thing_id` is, or sits inside, the target or the stub (which
    becomes the target)."""

    return spheres.sits_in(job.view, thing_id, job.target.id) or spheres.sits_in(
        job.view, thing_id, job.stub.id
    )


def _self_uses(job: _Job) -> list[_FieldUse]:
    """A merge's target values naming the stub, redirected rather than
    refused: the merged entry sits where the stub sat. Its parent (or any
    single thing field) and its filing take the stub's own value (a filing
    in a drawer the target goes in), cleared when the stub has none, or
    when its value would name the target or make a loop; a list drops the
    stub; a tie to the stub goes, one within it is within no part. Each
    one is noted."""

    view, stub, target = job.view, job.stub, job.target
    types = {spec.name: spec.type for spec in get_kind(target.kind).fields}
    uses: list[_FieldUse] = []
    for entry in job.world.timeline(target.id):
        if entry.change != "field" or entry.field is None:
            continue
        field, value = entry.field, entry.value
        kind = types.get(field)
        new: object = None
        if field == "part_of":
            if not (isinstance(value, dict) and value.get("sphere") == stub.id):
                continue
            own = stub.fields.get("part_of")
            sphere = own.get("sphere") if isinstance(own, dict) else None
            if (
                isinstance(own, dict)
                and isinstance(sphere, str)
                and view.thing(sphere) is not None
                and target.kind in PART_OF_KINDS
                and not _inside_either(job, sphere)
            ):
                new = {
                    "sphere": sphere,
                    "drawer": _drawer_for(
                        view, sphere, str(own.get("drawer")), target.kind
                    ),
                }
        elif field == "ties" and isinstance(value, list):
            if not any(
                isinstance(tie, dict)
                and stub.id in (tie.get("sphere"), tie.get("within"))
                for tie in value
            ):
                continue
            new = [
                {**tie, "within": None} if tie.get("within") == stub.id else tie
                for tie in value
                if isinstance(tie, dict) and tie.get("sphere") != stub.id
            ]
        elif kind == "thing" and value == stub.id:
            own_value = stub.fields.get(field)
            other = view.thing(own_value) if isinstance(own_value, str) else None
            allowed = FIELD_TARGET_KINDS.get(field, (target.kind,))
            if (
                other is not None
                and other.kind in allowed
                and not _inside_either(job, other.id)
            ):
                new = other.id
        elif kind == "things" and isinstance(value, list) and stub.id in value:
            new = [thing_id for thing_id in value if thing_id != stub.id] or None
        elif (
            kind == "shares"
            and isinstance(value, list)
            and any(
                isinstance(share, dict) and share.get("thing_id") == stub.id
                for share in value
            )
        ):
            new = [
                share
                for share in value
                if not (isinstance(share, dict) and share.get("thing_id") == stub.id)
            ] or None
        else:
            continue
        label = field.replace("_", " ")
        if new is None:
            job.notes.append(
                f"{job.target_name}'s {label} was {job.stub_name}: it's cleared"
            )
        elif field in ("part_of", "parent") or kind == "thing":
            where = (
                view.name_of(str(new["sphere"])) if isinstance(new, dict) else None
            ) or view.name_of(str(new))
            job.notes.append(
                f"{job.target_name}'s {label} was {job.stub_name}: it takes"
                f" {job.stub_name}'s, {where}"
            )
        else:
            job.notes.append(
                f"{job.target_name}'s {label} named {job.stub_name}: it no longer does"
            )
        job.redirected.add(field)
        uses.append(
            _FieldUse(
                thing_id=target.id,
                field=field,
                date=entry.date,
                value=new,
                clear=new is None,
            )
        )
    return uses


def _job(world: World, stub_id: str, target_id: str, *, merge: bool = False) -> _Job:
    view = world.view()
    stub = view.thing(stub_id)
    if stub is None:
        raise KeyError(f"no such thing: {stub_id}")
    stub_name = view.name_of(stub_id) or stub_id
    if not merge and not stub.is_stub:
        raise ValueError(f"not a stub: {stub_name}")
    if target_id == stub_id:
        raise ValueError(
            "a thing can't be merged into itself"
            if merge
            else "a stub can't be re-pointed onto itself"
        )
    target = view.thing(target_id)
    if target is None:
        raise KeyError(f"no such thing: {target_id}")
    target_name = view.name_of(target_id) or target_id
    if target.stub_ignored:
        raise ValueError(f"{target_name} is an ignored stub")
    if (
        merge
        and stub.kind != target.kind
        and {stub.kind, target.kind}
        != {
            "place",
            "sphere",
        }
    ):
        raise ValueError(
            f"{stub_name} is a {stub.kind} and {target_name} a {target.kind}:"
            " only entries of one kind merge (or a place and a sphere)"
        )
    if merge and target.is_stub and not stub.is_stub:
        raise ValueError(
            f"{target_name} is a stub: re-point it onto {stub_name} instead"
        )
    if merge and spheres.is_sphere(stub) and not spheres.is_sphere(target):
        held = _holders(world, view, stub_id)
        if held:
            raise ValueError(
                f"{stub_name} has parts or ties ({', '.join(held)}), and"
                f" {target_name} isn't a sphere: merge {target_name} into"
                f" {stub_name} instead, or re-file and untie them first"
            )
    return _Job(
        world=world,
        view=view,
        stub=stub,
        target=target,
        stub_name=stub_name,
        target_name=target_name,
        notes=[],
        merge=merge,
    )


class RepointPlan:
    """A re-point read and decided (`plan_repoint`), not yet written:
    `write` writes it into a revision, which may be another writer's own
    (an accept that is "the same thing" re-points the stub it expanded in
    its revision), and `result` reports it once written."""

    def __init__(
        self,
        job: _Job,
        uses: list[_FieldUse],
        changes: dict[str, dict],
        links: int,
        own: list,
        filing: tuple[dict, object] | None,
        carried: dict[str, object],
        aka: list[dict],
        added: list[str],
        ties: list[dict] | None = None,
    ) -> None:
        self._job = job
        self._uses = uses
        self._changes = changes
        self._links = links
        self._own = own
        self._filing = filing
        self._carried = carried
        self._aka = aka
        self._added = added
        self._ties = ties
        # old fact id -> its copy's, once written
        self.copies: dict[str, str] = {}

    @property
    def stub_id(self) -> str:
        return self._job.stub.id

    @property
    def target_id(self) -> str:
        return self._job.target.id

    @property
    def notes(self) -> list[str]:
        return self._job.notes

    @property
    def aka_added(self) -> list[str]:
        """The names the target takes as other names."""

        return list(self._added)

    @property
    def link_akas(self) -> list[str]:
        """A merge's other names that come from the words of links to the
        stub (not its names), for the owner to untick."""

        return list(self._job.link_names)

    @property
    def uses(self) -> int:
        """How many field values that point at the stub are re-pointed."""

        return len(self._uses)

    @property
    def links(self) -> int:
        """How many fact links to the stub are pointed at the target."""

        return self._links

    @property
    def use_counts(self) -> dict[str, int]:
        """The field values re-pointed, by what they are: `filings`
        (`part_of`), `ties` and the other `fields`."""

        counts = {"fields": 0, "filings": 0, "ties": 0}
        for use in self._uses:
            key = {"part_of": "filings", "ties": "ties"}.get(use.field, "fields")
            counts[key] += 1
        return counts

    @property
    def note(self) -> str:
        """The revision note a re-point (or merge) of its own writes."""

        job = self._job
        if job.merge:
            return f"merged {job.stub_name} into {job.target_name}"
        return f"re-pointed {job.stub_name} to {job.target_name}"

    def write(self, rev: Revision) -> None:
        """Every change, in `rev`; the stub is removed last. Written again
        into a fresh revision (the first rolled back), it writes the
        same."""

        job, target_id = self._job, self.target_id
        changes = {fact_id: dict(change) for fact_id, change in self._changes.items()}
        if job.drawers is not None:
            # first: the parts and statements filed in them need them
            rev.set_field(
                target_id,
                "drawers",
                job.drawers,
                job.view.field_since(target_id, "drawers"),
            )
        for use in self._uses:
            if use.clear:
                rev.remove_field_value(use.thing_id, use.field, use.date)
            else:
                rev.set_field(use.thing_id, use.field, use.value, use.date)
        recategorised = sum(
            1
            for fact in self._own
            if fact.category not in get_kind(job.target.kind).categories
        )
        if recategorised:
            job.notes.append(
                f"{recategorised} of {job.stub_name}'s facts moved under another"
                f" category: a {job.target.kind} has no such category"
            )
        # the stub's own facts, copied to the target (the stub's links in
        # them its words), then everyone else's changes
        self.copies = copy_facts(
            rev,
            job.world.view(),
            [fact.fact_id for fact in self._own],
            target_id,
            plain_self_links=True,
            standing_for=[self.stub_id],
            drawer_map=job.drawer_map,
        )
        for fact_id, change in changes.items():
            rev.correct_fact(fact_id, **change)
        if self._added or (
            job.merge and self._aka != (job.target.fields.get("aka") or [])
        ):
            rev.set_field(target_id, "aka", self._aka, None)
        if job.merge and job.main_name not in (None, job.target_name):
            # a correction of the name it holds now, at that value's date
            rev.set_field(
                target_id,
                "name",
                job.main_name,
                job.view.field_since(target_id, "name"),
            )
        if self._ties is not None:
            rev.set_field(
                target_id, "ties", self._ties, job.view.field_since(target_id, "ties")
            )
        if self._filing is not None:
            rev.set_field(target_id, "part_of", self._filing[0], self._filing[1])
        for field, value in self._carried.items():
            rev.set_field(target_id, field, value, None)
        rev.remove_thing(self.stub_id)

    def result(self) -> RepointResult:
        """What was re-pointed, once `write`n. Prose is refreshed only
        where its input changed: the target's facts and rendered fields,
        and the rendered fields that pointed at the stub."""

        target_id = self.target_id
        prose = list(
            dict.fromkeys(
                [
                    *(
                        [target_id]
                        if self._job.merge
                        or self._own
                        or set(self._carried) - set(UNRENDERED_FIELDS)
                        else []
                    ),
                    *(
                        use.thing_id
                        for use in self._uses
                        if use.field not in UNRENDERED_FIELDS
                    ),
                ]
            )
        )
        return RepointResult(
            stub_name=self._job.stub_name,
            target_name=self._job.main_name or self._job.target_name,
            links=self._links,
            aka_added=self._added,
            facts_moved=len(self._own),
            notes=list(dict.fromkeys(self._job.notes)),
            prose=prose,
        )


def plan_repoint(
    world: World, stub_id: str, target_id: str, *, as_kind: str | None = None
) -> RepointPlan:
    """Read and decide a re-point of the stub `stub_id` onto `target_id`
    (see the module docstring), writing nothing. Raises `KeyError` for a
    missing thing and `ValueError` for what's refused. With `as_kind`, the
    target is taken to be that kind (a stub whose kind changes in the same
    revision, before the plan is written): fields, filing and the moved
    facts' categories are decided for it."""

    job = _job(world, stub_id, target_id)
    if as_kind is not None and as_kind != job.target.kind:
        job.target = job.target.model_copy(update={"kind": as_kind})
    return _plan(job)


def _plan(job: _Job) -> RepointPlan:
    world = job.world
    blocked = [
        f"the scene {scene['name']}"
        for scene in thing_references(world, job.stub.id)["scenes"]
    ]
    if job.merge:
        _drawer_plan(job)
        uses = _self_uses(job)
        uses += _field_uses(
            world,
            job.view,
            job.stub,
            job.target,
            blocked,
            job.notes,
            drawer=_merge_drawer(job),
            skip_target=True,
        )
    else:
        uses = _field_uses(world, job.view, job.stub, job.target, blocked, job.notes)
    if blocked:
        raise ValueError(
            f"{job.stub_name} can't be {job.verb} {job.target_name}:"
            f" {'; '.join(dict.fromkeys(blocked))}"
        )

    shown_texts: list[str] = []
    changes, links, own = _fact_changes(job, shown_texts)
    filing = _own_filing(job)
    carried = _carried_fields(job)
    if not job.merge:
        aka, added = _names(job, shown_texts)
        return RepointPlan(job, uses, changes, links, own, filing, carried, aka, added)
    _within_checked(job, uses, filing)
    aka, added = _merge_names(job, shown_texts)
    ties = _merged_ties(job)
    return RepointPlan(
        job, uses, changes, links, own, filing, carried, aka, added, ties
    )


def plan_merge(
    world: World,
    from_id: str,
    into_id: str,
    *,
    fact_ids: Sequence[str] | None = None,
    main_name: str | None = None,
    link_akas: Sequence[str] | None = None,
) -> RepointPlan:
    """Read and decide a merge of the thing `from_id` into `into_id` (any
    two things; see the module docstring), writing nothing: the facts
    `fact_ids` of `from_id` move (`None`, all of them), and `into_id`
    takes `main_name` (either side's name; `None`, its own) and, of the
    links' words, only `link_akas` as other names (`None`, all). Raises
    `KeyError` for a missing thing and `ValueError` for what's refused."""

    job = _job(world, from_id, into_id, merge=True)
    if main_name is not None:
        names = {name_key(name): name for name in (job.stub_name, job.target_name)}
        if name_key(main_name) not in names:
            raise ValueError(
                f"the main name is {job.target_name} or {job.stub_name},"
                f" not {' '.join(main_name.split())}"
            )
        main_name = names[name_key(main_name)]
    job.main_name = main_name
    job.fact_ids = list(fact_ids) if fact_ids is not None else None
    job.link_akas = list(link_akas) if link_akas is not None else None
    return _plan(job)


def repoint_stub(world: World, stub_id: str, target_id: str) -> RepointResult:
    """Point everything that names the stub `stub_id` at `target_id`, and
    remove the stub, in one revision (see the module docstring). Raises
    `KeyError` for a missing thing and `ValueError` for what's refused,
    writing nothing."""

    plan = plan_repoint(world, stub_id, target_id)
    with world.revision(Source.manual(note=plan.note)) as rev:
        plan.write(rev)
    result = plan.result()
    log.info(
        "worlds.stub_repointed",
        stub=stub_id,
        target=target_id,
        links=result.links,
        uses=plan.uses,
        facts_moved=result.facts_moved,
        aka_added=result.aka_added,
    )
    return result


def move_fact(
    world: World,
    fact_id: str,
    target_id: str,
    *,
    notes: list[str] | None = None,
    prose: list[str] | None = None,
) -> str:
    """Move one fact onto another entry (a fact row's "Move to..."), in
    one revision (`copy_facts`, ruling R1): a new fact on the target with
    its dates, origin and holder, the original removed, every override of
    it pointed at the copy, its links to the target made words. Returns
    the copy's id.

    Refused with `ValueError`, writing nothing: a fact that isn't live
    (removed, or never was), a sphere's summary, a target that's gone or
    an ignored stub, and the fact's own entry. A category the target's kind lacks becomes
    `default_category`'s, with a note in `notes`. `prose` gains each of
    the two entries whose prose is written from the fact's category (the
    old owner's, the copy's)."""

    view = world.view()
    found = view.fact(fact_id)
    if found is None:
        raise ValueError(f"no such fact, or it was removed: {fact_id}")
    owner_id, fact = found
    if spheres.is_summary_fact(fact):
        raise ValueError("a sphere's summary stays its own: it can't be moved")
    target = view.thing(target_id)
    if target is None or target.stub_ignored:
        raise ValueError(f"no such entry to move it to: {target_id}")
    owner = view.thing(owner_id)
    assert owner is not None
    owner_name = view.name_of(owner_id) or owner_id
    target_name = view.name_of(target_id) or target_id
    if owner_id == target_id:
        raise ValueError(f"the fact is already {target_name}'s")
    category = _moved_category(target.kind, fact.category, fact.valid_from is not None)
    if category != fact.category and notes is not None:
        notes.append(
            f"a {target.kind} has no {fact.category} facts:"
            f" it's under {category} on {target_name}"
        )
    note = f"moved a fact from {owner_name} to {target_name}"
    with world.revision(Source.manual(note=note)) as rev:
        new_id = copy_facts(
            rev, world.view(), [fact_id], target_id, plain_self_links=True
        )[fact_id]
    if prose is not None:
        for thing_id, kind, read in (
            (owner_id, owner.kind, fact.category),
            (target_id, target.kind, category),
        ):
            if prose_reads(kind, read) and thing_id not in prose:
                prose.append(thing_id)
    log.info(
        "worlds.fact_moved",
        fact=fact_id,
        copy=new_id,
        owner=owner_id,
        target=target_id,
        category=category,
    )
    return new_id
