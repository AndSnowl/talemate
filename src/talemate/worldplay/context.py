"""The scene-level world context: the "World" instruction injected into
narrator and actor prompts, and keeping a scene's active characters built
fresh from the world as its clock moves.

The World instruction names who is here by heritage, with each one's body
and instincts (`_cast`), resolved in code as of the scene's date. The
narrator's prompts carry no character sheets -- only what long-term memory
happens to retrieve -- and the heritage play probe
(docs/superpowers/probes/2026-10-20-heritage-play.md) found it writing
owl-folk with hands, fingers and hair when nothing reminded it.

Loading a world scene (`talemate.load.load_world_scene`) attaches the
context and calls `connect`; a scene that never gets a
`scene.world_context` is left alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

import talemate.emit.async_signals as async_signals
from talemate.agents.base import DynamicInstruction
from talemate.prompts import Prompt
from talemate.world import heritage, spheres
from talemate.world.dates import WorldDate
from talemate.world.kinds import HERITAGE_KINDS, SPHERE_CATEGORIES
from talemate.world.names import everyday_name
from talemate.world.scenes import SceneRecord
from talemate.world.store import World
from talemate.world.view import ThingState, WorldView

from .characters import (
    WORLD_DERIVED_FIELDS,
    _cached_section,
    character_from_world,
    mid_sentence_name,
)

log = structlog.get_logger("talemate.worldplay.context")

# the scene-local thing kinds of a place and a character invented for a
# scene (`persistence` re-exports the character's)
LOCAL_PLACE_KIND = "place"
LOCAL_CHARACTER_KIND = "character"

# the heritage fact categories the cast lines carry: the body, then how
# the kind behaves
_BODY_CATEGORIES = ("physical", "variation")
_INSTINCT_CATEGORIES = ("instinct",)

SECTION_TITLE = "World"


def scene_date(record: SceneRecord, scene_ts: str) -> WorldDate:
    """The in-world date `scene_ts` (an ISO-8601 duration elapsed since the
    scene's start, `scene.ts`) lands on."""

    return record.start.plus(scene_ts)


def _heritage_name(view: WorldView, heritage_id: str) -> str:
    """`Snowy, a race of Owl-folk`, `Half-orc, a mix of Lowlander and Orc`,
    `Owl-folk, a species`: a heritage thing as a cast line names it. A
    name missing at the view's date (a deleted parent, a heritage not yet
    named) is left out rather than shown blank."""

    state = view.thing(heritage_id)
    name = view.name_of(heritage_id) or ""
    if state is None:
        return name
    if state.kind == "race":
        species = state.fields.get("species")
        species_name = view.name_of(species) if isinstance(species, str) else None
        kind = f"a race of {species_name}" if species_name else ""
    elif state.kind == "mix":
        parents = [
            parent_name
            for parent in state.fields.get("parents") or []
            if isinstance(parent, str) and (parent_name := view.name_of(parent))
        ]
        kind = f"a mix of {' and '.join(parents)}" if parents else ""
    else:
        kind = f"a {state.kind}"
    return ", ".join(part for part in (name, kind) if part)


def _traits(
    view: WorldView, thing_id: str, character: bool
) -> tuple[list[str], list[str]]:
    """`(body, instincts)` fact texts as of `view`, overrides applied, in
    layer order: of the heritage `thing_id` itself and what it inherits
    or, for a `character`, of its heritage layers, led by the character's
    own facts that override one of them (her black eyes, in place of her
    kind's yellow ones)."""

    body: list[str] = []
    instincts: list[str] = []
    for fact, layer in heritage.effective_facts(view, thing_id):
        if character and layer.depth == 0:
            if fact.overrides:
                body.append(view.render(fact.text))
            continue
        if layer.kind not in HERITAGE_KINDS:
            continue
        if fact.category in _BODY_CATEGORIES:
            body.append(view.render(fact.text))
        elif fact.category in _INSTINCT_CATEGORIES:
            instincts.append(view.render(fact.text))
    return body, instincts


def _present(record: SceneRecord) -> list[dict[str, Any]]:
    """The scene's character entries that are here: the player (first,
    when the characters don't list them) and every active character."""

    entries = [
        entry
        for entry in record.state.get("characters") or []
        if isinstance(entry, dict)
    ]
    if record.player_thing_id and not any(
        entry.get("thing_id") == record.player_thing_id for entry in entries
    ):
        entries.insert(0, {"thing_id": record.player_thing_id, "active": True})
    return [entry for entry in entries if entry.get("active", True)]


def _cast(world: World, record: SceneRecord, view: WorldView) -> list[dict]:
    """The scene's player and active characters that have a heritage, each
    as `{"name", "heritage", "body", "instincts"}`, all as of `view`: a
    world character's heritage, with its own overrides, or an invented
    one's `world_heritage_id`, from the heritage alone (as
    `setup.start_scene` described it). A heritage that's gone from the
    world leaves its character out."""

    local = {
        thing["local_id"]: thing["data"]
        for thing in world.scenes().local_things(record.id)
        if thing["kind"] == LOCAL_CHARACTER_KIND and isinstance(thing["data"], dict)
    }

    cast: list[dict] = []
    for entry in _present(record):
        thing_id = entry.get("thing_id")
        if thing_id:
            state = view.thing(thing_id)
            heritage_id = state.fields.get("heritage") if state is not None else None
            name = view.name_of(thing_id) or ""
            source, character = thing_id, True
        else:
            data = local.get(entry.get("local_id") or "", {})
            heritage_id = data.get("world_heritage_id")
            name = str(data.get("name") or "")
            source, character = heritage_id, False
        if not isinstance(heritage_id, str) or view.thing(heritage_id) is None:
            continue
        body, instincts = _traits(view, source, character)
        if not body and not instincts:
            continue
        cast.append(
            {
                "name": name,
                "heritage": _heritage_name(view, heritage_id),
                "body": body,
                "instincts": instincts,
            }
        )
    return cast


def _touched_spheres(
    view: WorldView,
    record: SceneRecord,
    place_thing_id: str | None,
    things: list[ThingState],
) -> list[str]:
    """The spheres the scene touches, each once: those whose territory
    holds the scene's place (`spheres.holders`, in the order they were
    made), those the prompt or setup named (pulled in), then those a
    character here has a live tie to (Global Constraints, "Context").
    `things` is one snapshot of the view's things."""

    sphere_ids = {state.id for state in things if spheres.is_sphere(state)}
    touched: list[str] = []

    def touch(sphere_id: str) -> None:
        if sphere_id in sphere_ids and sphere_id not in touched:
            touched.append(sphere_id)

    if place_thing_id:
        for sphere_id in spheres.holders(view, place_thing_id, things):
            touch(sphere_id)
    for thing_id in record.state.get("pulled_in") or []:
        touch(thing_id)
    for entry in _present(record):
        thing_id = entry.get("thing_id")
        if isinstance(thing_id, str):
            for tie in spheres.ties_of(view, thing_id, live=True):
                touch(tie.sphere_id)
    return touched


def _sphere_summary(world: World, view: WorldView, sphere_id: str) -> str:
    """The sphere's summary (ruling P1): its cached description prose as
    of the view's date, else its first `about` fact, rendered."""

    cached = _cached_section(world, sphere_id, "description", view.at)
    if cached is not None and cached.text:
        return str(view.render(cached.text))
    state = view.thing(sphere_id)
    about = [
        fact
        for fact in sorted(state.facts if state else [], key=lambda f: f.created)
        if fact.category == "about"
    ]
    return view.render(about[0].text) if about else ""


def _sphere_parent(view: WorldView, state: ThingState) -> str | None:
    """The sphere a sphere sits in: a branch's `parent`, else the sphere
    it's part of (the Council of Elders in the White Dawn's Hierarchy);
    `None` when neither is a live sphere."""

    candidates: list[object] = []
    if state.kind == "sphere":
        candidates.append(state.fields.get("parent"))
    part_of = state.fields.get("part_of")
    if isinstance(part_of, dict):
        candidates.append(part_of.get("sphere"))
    for candidate in candidates:
        if not isinstance(candidate, str) or candidate == state.id:
            continue
        parent = view.thing(candidate)
        if parent is not None and spheres.is_sphere(parent):
            return candidate
    return None


def _sphere_entries(
    world: World,
    view: WorldView,
    sphere_ids: list[str],
    shown: set[str],
    things: list[ThingState],
    as_lore: set[str],
) -> list[dict[str, Any]]:
    """The spheres block, one entry per sphere in `sphere_ids`: its key
    facts (`spheres.key_facts`, with its summary, less the items shown
    `as_lore` in the block already) and, for a nested sphere whose parent
    isn't `shown` in the block already, the parent's summary alone."""

    entries: list[dict[str, Any]] = []
    for sphere_id in sphere_ids:
        state = view.thing(sphere_id)
        if state is None:
            continue
        template = state.fields.get("template")
        entry: dict[str, Any] = {
            "name": view.name_of(sphere_id) or "",
            "template": template if isinstance(template, str) else "sphere",
            "everyday": everyday_name(state),
            "parent_name": "",
            "parent_summary": "",
            "key_facts": spheres.key_facts(
                view,
                sphere_id,
                _sphere_summary(world, view, sphere_id) or None,
                world.calendar,
                things,
                as_lore,
            ),
        }
        parent_id = _sphere_parent(view, state)
        if parent_id is not None and parent_id not in shown:
            entry["parent_name"] = mid_sentence_name(view.name_of(parent_id) or "")
            entry["parent_summary"] = _sphere_summary(world, view, parent_id)
        entries.append(entry)
    return entries


def world_context_block(world: World, record: SceneRecord, at: WorldDate) -> str:
    """The "World" instruction's content: the scene's goal, its current
    place, whatever lore has been pulled into it, and who is here by
    heritage (`_cast`), all as of `at`. The
    place is the world thing `record.state["place_thing_id"]` or, when the
    scene invented its place, the scene-local place thing
    `record.state["place_local_id"]` (its name and facts); the lore entries
    are `record.state["pulled_in"]`.

    The spheres the scene touches (`_touched_spheres`) follow the lore,
    one block each under one lead line (the spheres probe's (d)), with
    their key facts; a pulled-in sphere shows there, not as lore, and a
    pulled-in item of a sphere shows as lore, not again in its key facts.
    When the
    scene's place is itself a sphere, it shows once, as the place: its own
    place facts, then its key facts (summary from its `about` fact, since
    its description prose retells those place facts), never again as a
    sphere block.

    A place or lore entry with an everyday name is shown "<main> (usually
    called <everyday>)", and the block then opens with a line asking for
    everyday names in narration and dialogue: the connections probe
    (docs/superpowers/probes/2026-10-21-connections.md, probe 4) found the
    plain heading kept the full name every time."""

    view = world.view(at)
    # one snapshot of the world's things for every sphere lookup below
    things = view.things()

    lore = []
    # a sphere's item pulled in as lore shows once, there, in full: the
    # sphere's key facts leave it out
    as_lore: set[str] = set()
    for lore_thing_id in record.state.get("pulled_in") or []:
        lore_state = view.thing(lore_thing_id)
        if lore_state is None or spheres.is_sphere(lore_state):
            continue
        as_lore.add(lore_thing_id)
        lore.append(
            {
                "name": view.name_of(lore_thing_id) or "",
                "everyday": everyday_name(lore_state),
                "facts": [view.render(fact.text) for fact in lore_state.facts],
            }
        )

    place = None
    place_thing_id = record.state.get("place_thing_id")
    place_local_id = record.state.get("place_local_id")
    if place_thing_id:
        place_state = view.thing(place_thing_id)
        if place_state is not None:
            facts = [view.render(fact.text) for fact in place_state.facts]
            if spheres.is_sphere(place_state):
                facts = [
                    view.render(fact.text)
                    for fact in place_state.facts
                    if fact.category not in SPHERE_CATEGORIES
                ] + spheres.key_facts(
                    view, place_thing_id, None, world.calendar, things, as_lore
                )
            place = {
                "name": view.name_of(place_thing_id) or "",
                "everyday": everyday_name(place_state),
                "facts": facts,
            }
    elif place_local_id:
        local = next(
            (
                thing
                for thing in world.scenes().local_things(record.id)
                if thing["local_id"] == place_local_id
                and thing["kind"] == LOCAL_PLACE_KIND
            ),
            None,
        )
        if local is not None:
            data = local["data"]
            place = {
                "name": str(data.get("name") or ""),
                "everyday": None,
                "facts": [str(fact) for fact in data.get("facts") or []],
            }

    touched = _touched_spheres(view, record, place_thing_id, things)
    in_block = [sphere_id for sphere_id in touched if sphere_id != place_thing_id]
    sphere_entries = _sphere_entries(
        world, view, in_block, set(touched), things, as_lore
    )

    return str(
        Prompt.get(
            "world.scene-context",
            vars={
                "goal": record.goal,
                "place": place,
                "lore": lore,
                "spheres": sphere_entries,
                "everyday": any(
                    entry["everyday"]
                    for entry in [*([place] if place else []), *lore, *sphere_entries]
                ),
                "cast": _cast(world, record, view),
            },
        )
    )


@dataclass
class WorldSceneContext:
    """Attached as `scene.world_context` for a scene played against a
    shared world. `connect` reads it to build the "World" instruction and
    to refresh characters after time passage."""

    world: World
    record: SceneRecord

    async def refresh_characters(self, scene) -> None:
        """Rebuild every active character from the world at the scene's
        current date (`scene_date(self.record, scene.ts)`), replacing it on
        the scene but keeping the actor binding. Never calls the model --
        characters whose prose has gone stale stay stale until something
        else (not this) regenerates it.

        A character whose world thing has since been deleted is left as
        it is, with a warning logged -- the same thing
        `persistence._character_data` does on load -- rather than failing
        every time-passage signal from here on.

        Only the world-derived fields (name, description, base attributes,
        dialogue instructions, example dialogue) are replaced --
        `character.model_copy(update=...)` keeps everything per-scene
        (color, avatar, voice, details, greeting text, ...) exactly as it
        was."""

        at = scene_date(self.record, scene.ts)
        for actor in scene.actors:
            character = actor.character
            thing_id = getattr(character, "world_thing_id", None)
            if thing_id is None:
                continue

            try:
                rebuilt = character_from_world(
                    self.world, thing_id, at, is_player=character.is_player
                )
            except KeyError:
                log.warning("world scene character not in the world", thing_id=thing_id)
                continue
            updated = character.model_copy(
                update={
                    field: getattr(rebuilt, field) for field in WORLD_DERIVED_FIELDS
                }
            )

            actor.character = updated
            if actor.agent is not None:
                actor.agent.character = updated

            if character.name in scene.active_characters:
                index = scene.active_characters.index(character.name)
                scene.active_characters[index] = updated.name

            if character.name in scene.character_data:
                del scene.character_data[character.name]
            scene.character_data[updated.name] = updated


async def _on_inject_instructions(emission) -> None:
    scene = emission.agent.scene
    context: WorldSceneContext | None = getattr(scene, "world_context", None)
    if context is None:
        return

    at = scene_date(context.record, scene.ts)
    content = world_context_block(context.world, context.record, at)
    if not content.strip():
        return

    emission.dynamic_instructions.append(
        DynamicInstruction(title=SECTION_TITLE, content=content)
    )


async def _on_time_passage(emission) -> None:
    scene = emission.agent.scene
    context: WorldSceneContext | None = getattr(scene, "world_context", None)
    if context is None:
        return
    await context.refresh_characters(scene)


def connect(scene) -> None:
    """Wire the "World" instruction into the narrator and conversation
    agents' prompts, and keep a scene's characters fresh across time
    passage.

    The handlers are module-level, not closures over `scene`: each one
    resolves *its own* scene from `emission.agent.scene` at call time --
    the same pattern `CultureAgent` uses
    (`agents/culture/__init__.py:246-252`) -- rather than from this call's
    `scene` argument. A closure bound to one scene would leak: nothing
    ever disconnects it, so a scene loaded after this one would keep
    getting *this* scene's "World" block and time-passage refresh instead
    of its own. `scene` is accepted (and otherwise unused) only so this
    has the same `connect(scene)` shape every other agent's scene-load
    hook does.

    `AsyncSignal.connect` already dedupes a repeat of the exact same
    function object, so calling this once per scene load -- the normal
    thing to do -- never double-connects. Acting only on a scene that has
    `scene.world_context` set means a non-world scene, or one whose world
    context hasn't loaded yet, is left exactly as before."""

    async_signals.get("agent.conversation.inject_instructions").connect(
        _on_inject_instructions
    )
    async_signals.get("agent.narrator.inject_instructions").connect(
        _on_inject_instructions
    )
    async_signals.get("agent.world_state.time").connect(_on_time_passage)
