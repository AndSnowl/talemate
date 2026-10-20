"""The scene-level world context: the "World" instruction injected into
narrator and actor prompts, and keeping a scene's active characters built
fresh from the world as its clock moves.

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
from talemate.world.dates import WorldDate
from talemate.world.scenes import SceneRecord
from talemate.world.store import World

from .characters import WORLD_DERIVED_FIELDS, character_from_world

log = structlog.get_logger("talemate.worldplay.context")

# the scene-local thing kind of a place invented for a scene
LOCAL_PLACE_KIND = "place"

SECTION_TITLE = "World"


def scene_date(record: SceneRecord, scene_ts: str) -> WorldDate:
    """The in-world date `scene_ts` (an ISO-8601 duration elapsed since the
    scene's start, `scene.ts`) lands on."""

    return record.start.plus(scene_ts)


def world_context_block(world: World, record: SceneRecord, at: WorldDate) -> str:
    """The "World" instruction's content: the scene's goal, its current
    place, and whatever lore has been pulled into it, all as of `at`. The
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
            vars={"goal": record.goal, "place": place, "lore": lore},
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
                log.warning(
                    "world scene character not in the world", thing_id=thing_id
                )
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
