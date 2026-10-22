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
- the stub's own facts, moved to the target with their ids, dates and
  origin (a category the target's kind lacks becomes its catch-all one);
- the stub's own filing (`part_of`): the target is filed where the stub
  was, unless it's filed already (it stays where it is, and a note says
  so) or can't be (a note says why);
- the stub's other own fields the target has none of;
- its names: the stub's name, its other names and each distinct shown
  text become the target's common other names, unless the target or
  another thing already has that name.

Then the stub is removed. Refused before anything is written (a
`ValueError` naming every use that blocks it): a use by a scene, a field
whose kind of thing the target isn't (a place's parent can't be lore), a
filing or tie when the target isn't a sphere, a filing that would put a
thing inside itself, and a use by the target itself.
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
from talemate.world.store import Source, World
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


def repoint_stub(world: World, stub_id: str, target_id: str) -> RepointResult:
    """Point everything that names the stub `stub_id` at `target_id`, and
    remove the stub, in one revision (see the module docstring). Raises
    `KeyError` for a missing thing and `ValueError` for what's refused,
    writing nothing."""

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
    target_kind = get_kind(target.kind)

    blocked = [
        f"the scene {scene['name']}"
        for scene in thing_references(world, stub_id)["scenes"]
    ]
    notes: list[str] = []
    uses = _field_uses(world, view, stub, target, blocked, notes)
    if blocked:
        raise ValueError(
            f"{stub_name} can't be re-pointed to {target_name}:"
            f" {'; '.join(dict.fromkeys(blocked))}"
        )

    # facts: fact id -> what changes (text, owner, category, origin)
    shown_texts: list[str] = []
    rewrite = _rewriter(view, stub_id, target_id, shown_texts)
    changes: dict[str, dict] = {}
    links = 0
    for owner, fact in view.referencing(stub_id, any_date=True):
        if owner == stub_id or fact.fact_id in changes:
            continue
        text, moved = rewrite(fact.text or "", owner, True)
        links += moved
        changes[fact.fact_id] = {"text": text}
    for character in view.things("character"):
        for fact in world.live_facts(character.id):
            if (fact.origin or {}).get("tie") == stub_id:
                changes.setdefault(fact.fact_id, {})["origin"] = {
                    **(fact.origin or {}),
                    "tie": target_id,
                }
    own_facts = world.live_facts(stub_id)
    recategorised = 0
    for fact in own_facts:
        text, _moved = rewrite(fact.text or "", target_id, False)
        change: dict = {"text": text, "thing_id": target_id}
        if fact.category not in target_kind.categories:
            change["category"] = next(
                (c for c in _CATCH_ALL if c in target_kind.categories),
                target_kind.categories[0],
            )
            recategorised += 1
        changes[fact.fact_id] = change
    if recategorised:
        notes.append(
            f"{recategorised} of {stub_name}'s facts moved under another"
            f" category: a {target.kind} has no such category"
        )

    # the stub's own filing
    filing: tuple[dict, object] | None = None
    own = stub.fields.get("part_of")
    if isinstance(own, dict) and isinstance(own.get("sphere"), str):
        sphere_id, drawer_id = own["sphere"], str(own.get("drawer"))
        held = target.fields.get("part_of")
        if view.thing(sphere_id) is None:
            pass
        elif isinstance(held, dict) and isinstance(held.get("sphere"), str):
            if (held["sphere"], held.get("drawer")) != (sphere_id, drawer_id):
                notes.append(
                    f"{target_name} stays in"
                    f" {_where(view, held['sphere'], str(held.get('drawer')))};"
                    f" {stub_name} was in {_where(view, sphere_id, drawer_id)}"
                )
        elif target.kind not in PART_OF_KINDS:
            notes.append(
                f"{target_name} isn't filed in {_where(view, sphere_id, drawer_id)}:"
                f" a {target.kind} is never part of a sphere"
            )
        elif spheres.sits_in(view, sphere_id, target_id):
            notes.append(
                f"{target_name} isn't filed in {_where(view, sphere_id, drawer_id)}:"
                " it would be inside itself"
            )
        else:
            drawer = _drawer_for(view, sphere_id, drawer_id, target.kind)
            if drawer != drawer_id:
                notes.append(
                    f"{target_name} is filed in {_where(view, sphere_id, drawer)}:"
                    f" a {target.kind} doesn't go in"
                    f" {_where(view, sphere_id, drawer_id)}"
                )
            filing = (
                {"sphere": sphere_id, "drawer": drawer},
                part_of_since(world, target_id, strict=False),
            )

    # the stub's other own fields, where the target has none
    carried: dict[str, object] = {}
    target_fields = {spec.name for spec in target_kind.fields}
    for field, value in stub.fields.items():
        if field in _OWN_HANDLED or value is None:
            continue
        if field in target_fields and target.fields.get(field) is None:
            carried[field] = value
        else:
            notes.append(f"{stub_name}'s {field} isn't carried over")

    # the names
    aka = list(target.fields.get("aka") or [])
    held_keys = {name_key(target_name)} | {
        name_key(entry["name"]) for entry in aka if isinstance(entry, dict)
    }
    taken = _other_name_keys(view, {stub_id, target_id})
    stub_aka = [
        entry["name"]
        for entry in stub.fields.get("aka") or []
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    ]
    added: list[str] = []
    for name in [stub_name, *stub_aka, *shown_texts]:
        name = " ".join(name.split())
        key = name_key(name)
        if not key or key in held_keys or key in taken:
            continue
        held_keys.add(key)
        added.append(name)
        aka.append({"name": name, "tag": "common", "everyday": False})

    with world.revision(
        Source.manual(note=f"re-pointed {stub_name} to {target_name}")
    ) as rev:
        for use in uses:
            rev.set_field(use.thing_id, use.field, use.value, use.date)
        for fact_id, change in changes.items():
            rev.correct_fact(fact_id, **change)
        if added:
            rev.set_field(target_id, "aka", aka, None)
        if filing is not None:
            rev.set_field(target_id, "part_of", filing[0], filing[1])
        for field, value in carried.items():
            rev.set_field(target_id, field, value, None)
        rev.remove_thing(stub_id)

    log.info(
        "worlds.stub_repointed",
        stub=stub_id,
        target=target_id,
        links=links,
        uses=len(uses),
        facts_moved=len(own_facts),
        aka_added=added,
    )
    return RepointResult(
        stub_name=stub_name,
        target_name=target_name,
        links=links,
        aka_added=added,
        facts_moved=len(own_facts),
        notes=notes,
    )
