"""Re-pointing a stub onto an entry: the stub was a name for something the
world already has.

`repoint_stub` moves everything that names the stub to the target, in one
revision, so one undo restores it all:

- every fact link to it, keeping its words (a link in the target's own
  facts becomes those words, plain: a thing never links to itself);
- every field that points at it (`thing`, `things`, `shares`), every
  thing filed in it (`part_of`) and every tie to it (`ties`), at each
  story date the field holds it, and the exceptions filed under such a
  tie (their origin `tie`);
- the stub's own facts, copied to the target as new facts with their
  dates and origin (a category the target's kind lacks becomes its
  catch-all one), every override of one pointed at its copy; a fact never
  changes thing, since replay and undo key a fact by its id;
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
"""

from __future__ import annotations

import re
from collections.abc import Callable

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
from talemate.world.view import ThingState, WorldView
from talemate.worldplay.create import drawer_types_for, part_of_since
from talemate.worldplay.links import name_key
from talemate.worldplay.references import thing_references

log = structlog.get_logger("talemate.worldplay.repoint")

__all__ = ["RepointResult", "repoint_stub"]

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


def _field_uses(
    world: World,
    view: WorldView,
    stub: ThingState,
    target: ThingState,
    blocked: list[str],
    notes: list[str],
) -> list[_FieldUse]:
    """Every field value of another thing naming the stub, rewritten to
    name the target, at its date. What can't be is added to `blocked`."""

    uses: list[_FieldUse] = []
    is_sphere = spheres.is_sphere(target)
    for state in view.things():
        if state.id == stub.id:
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
                    "drawer": _drawer_for(
                        view, target.id, str(value.get("drawer")), state.kind
                    ),
                }
            elif field == "ties":
                if not isinstance(value, list) or not any(
                    isinstance(tie, dict) and tie.get("sphere") == stub.id
                    for tie in value
                ):
                    continue
                if not is_sphere:
                    blocked.append(f"{label} needs a sphere")
                    continue
                tied = any(
                    isinstance(tie, dict) and tie.get("sphere") == target.id
                    for tie in value
                )
                if tied:
                    notes.append(
                        f"{name} was tied to both; the tie to"
                        f" {view.name_of(target.id)} is kept"
                    )
                new = [
                    {**tie, "sphere": target.id}
                    if isinstance(tie, dict) and tie.get("sphere") == stub.id
                    else tie
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


def _fact_changes(
    job: _Job, shown_texts: list[str]
) -> tuple[dict[str, dict], int, list]:
    """`(changes, links, own facts)`: each other fact's changes (`text`, its
    links to the stub pointed at the target; `origin`, a tie to the stub
    filed under the target, a belief the stub held held by the target),
    the fact links moved, and the stub's own
    facts (`FactState`s), which `_move_facts` copies to the target."""

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
    return changes, links, job.world.live_facts(stub_id)


def _move_facts(job: _Job, rev: Revision, own: list, changes: dict[str, dict]) -> None:
    """Copy the stub's own facts to the target as new facts (text with
    self-links made words, a category its kind has, dates, origin), and
    point every override of one at its copy, in `rev`. The stub's facts go
    with the stub (`remove_thing`). A fact never changes thing: replay and
    undo key a fact by its id."""

    view, stub_id, target_id = job.view, job.stub.id, job.target.id
    rewrite = _rewriter(view, stub_id, target_id, [])
    categories = get_kind(job.target.kind).categories
    copies: dict[str, str] = {}
    recategorised = 0
    own_ids = {fact.fact_id for fact in own}
    for fact in own:
        text, _moved = rewrite(fact.text or "", target_id, False)
        category = fact.category
        if category not in categories:
            category = next((c for c in _CATCH_ALL if c in categories), categories[0])
            recategorised += 1
        copies[fact.fact_id] = rev.add_fact(
            target_id,
            category,
            text,
            valid_from=fact.valid_from,
            valid_until=fact.valid_until,
            # a belief the stub held of itself is the target's now
            origin=(
                {**fact.origin, "held_by": target_id}
                if fact.origin and fact.origin.get("held_by") == stub_id
                else fact.origin
            ),
            overrides=[o for o in fact.overrides if o not in own_ids] or None,
        )
    if recategorised:
        job.notes.append(
            f"{recategorised} of {job.stub_name}'s facts moved under another"
            f" category: a {job.target.kind} has no such category"
        )
    # overrides of the stub's facts: the copies' own, then everyone else's
    for fact in own:
        if any(o in own_ids for o in fact.overrides):
            rev.correct_fact(
                copies[fact.fact_id],
                overrides=[copies.get(o, o) for o in fact.overrides],
            )
    for fact in job.world.live_facts():
        if fact.fact_id in own_ids or not any(o in own_ids for o in fact.overrides):
            continue
        changes.setdefault(fact.fact_id, {})["overrides"] = [
            copies.get(o, o) for o in fact.overrides
        ]


def _own_filing(job: _Job) -> tuple[dict, object] | None:
    """`(part_of, since)` filing the target where the stub was, or `None`
    (with a note when it stays elsewhere or can't be filed there)."""

    view, target = job.view, job.target
    own = job.stub.fields.get("part_of")
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


def _job(world: World, stub_id: str, target_id: str) -> _Job:
    view = world.view()
    stub = view.thing(stub_id)
    if stub is None:
        raise KeyError(f"no such thing: {stub_id}")
    stub_name = view.name_of(stub_id) or stub_id
    if not stub.is_stub:
        raise ValueError(f"not a stub: {stub_name}")
    if target_id == stub_id:
        raise ValueError("a stub can't be re-pointed onto itself")
    target = view.thing(target_id)
    if target is None:
        raise KeyError(f"no such thing: {target_id}")
    target_name = view.name_of(target_id) or target_id
    if target.stub_ignored:
        raise ValueError(f"{target_name} is an ignored stub")
    return _Job(
        world=world,
        view=view,
        stub=stub,
        target=target,
        stub_name=stub_name,
        target_name=target_name,
        notes=[],
    )


def repoint_stub(world: World, stub_id: str, target_id: str) -> RepointResult:
    """Point everything that names the stub `stub_id` at `target_id`, and
    remove the stub, in one revision (see the module docstring). Raises
    `KeyError` for a missing thing and `ValueError` for what's refused,
    writing nothing."""

    job = _job(world, stub_id, target_id)
    blocked = [
        f"the scene {scene['name']}"
        for scene in thing_references(world, stub_id)["scenes"]
    ]
    uses = _field_uses(world, job.view, job.stub, job.target, blocked, job.notes)
    if blocked:
        raise ValueError(
            f"{job.stub_name} can't be re-pointed to {job.target_name}:"
            f" {'; '.join(dict.fromkeys(blocked))}"
        )

    shown_texts: list[str] = []
    changes, links, own = _fact_changes(job, shown_texts)
    filing = _own_filing(job)
    carried = _carried_fields(job)
    aka, added = _names(job, shown_texts)

    with world.revision(
        Source.manual(note=f"re-pointed {job.stub_name} to {job.target_name}")
    ) as rev:
        for use in uses:
            rev.set_field(use.thing_id, use.field, use.value, use.date)
        _move_facts(job, rev, own, changes)
        for fact_id, change in changes.items():
            rev.correct_fact(fact_id, **change)
        if added:
            rev.set_field(target_id, "aka", aka, None)
        if filing is not None:
            rev.set_field(target_id, "part_of", filing[0], filing[1])
        for field, value in carried.items():
            rev.set_field(target_id, field, value, None)
        rev.remove_thing(stub_id)

    # prose reads facts and rendered fields: only those changed
    prose = list(
        dict.fromkeys(
            [
                *([target_id] if own or set(carried) - set(UNRENDERED_FIELDS) else []),
                *(use.thing_id for use in uses if use.field not in UNRENDERED_FIELDS),
            ]
        )
    )
    log.info(
        "worlds.stub_repointed",
        stub=stub_id,
        target=target_id,
        links=links,
        uses=len(uses),
        facts_moved=len(own),
        aka_added=added,
    )
    return RepointResult(
        stub_name=job.stub_name,
        target_name=job.target_name,
        links=links,
        aka_added=added,
        facts_moved=len(own),
        notes=job.notes,
        prose=prose,
    )
