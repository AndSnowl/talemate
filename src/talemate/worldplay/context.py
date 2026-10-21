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

import structlog

import talemate.emit.async_signals as async_signals
from talemate.agents.base import DynamicInstruction
from talemate.prompts import Prompt
from talemate.world import heritage
from talemate.world.dates import WorldDate
from talemate.world.kinds import HERITAGE_KINDS
from talemate.world.scenes import SceneRecord
from talemate.world.store import World
from talemate.world.view import WorldView

from .characters import WORLD_DERIVED_FIELDS, character_from_world

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
    `Owl-folk, a species`: a heritage thing as a cast line names it."""

    state = view.thing(heritage_id)
    name = view.name_of(heritage_id) or ""
    if state is None:
        return name
    if state.kind == "race":
        species = state.fields.get("species")
        species_name = view.name_of(species) if isinstance(species, str) else None
        return f"{name}, a race of {species_name}" if species_name else name
    if state.kind == "mix":
        parents = [
            view.name_of(parent) or "" for parent in state.fields.get("parents") or []
        ]
        return f"{name}, a mix of {' and '.join(parents)}"
    return f"{name}, a {state.kind}"


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
    entries = [
        entry
        for entry in record.state.get("characters") or []
        if isinstance(entry, dict)
    ]
    if record.player_thing_id and not any(
        entry.get("thing_id") == record.player_thing_id for entry in entries
    ):
        entries.insert(0, {"thing_id": record.player_thing_id, "active": True})

    cast: list[dict] = []
    for entry in entries:
        if not entry.get("active", True):
            continue
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


def world_context_block(world: World, record: SceneRecord, at: WorldDate) -> str:
    """The "World" instruction's content: the scene's goal, its current
    place, whatever lore has been pulled into it, and who is here by
    heritage (`_cast`), all as of `at`. The
    place is the world thing `record.state["place_thing_id"]` or, when the
    scene invented its place, the scene-local place thing
    `record.state["place_local_id"]` (its name and facts); the lore entries
    are `record.state["pulled_in"]`."""

    view = world.view(at)

    place = None
    place_thing_id = record.state.get("place_thing_id")
    place_local_id = record.state.get("place_local_id")
    if place_thing_id:
        place_state = view.thing(place_thing_id)
        if place_state is not None:
            place = {
                "name": view.name_of(place_thing_id) or "",
                "facts": [fact.text for fact in place_state.facts],
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
                "facts": [str(fact) for fact in data.get("facts") or []],
            }

    lore = []
    for lore_thing_id in record.state.get("pulled_in") or []:
        lore_state = view.thing(lore_thing_id)
        if lore_state is None:
            continue
        lore.append(
            {
                "name": view.name_of(lore_thing_id) or "",
                "facts": [fact.text for fact in lore_state.facts],
            }
        )

    return str(
        Prompt.get(
            "world.scene-context",
            vars={
                "goal": record.goal,
                "place": place,
                "lore": lore,
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
