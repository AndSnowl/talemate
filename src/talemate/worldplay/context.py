"""The scene-level world context: the "World" instruction injected into
narrator and actor prompts, and keeping a scene's active characters built
fresh from the world as its clock moves.

Nothing here is wired into normal scene play yet -- `connect` exists so a
later task can call it, and does nothing to a scene that never gets a
`scene.world_context`.
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

from .characters import character_from_world

log = structlog.get_logger("talemate.worldplay.context")

SECTION_TITLE = "World"


def scene_date(record: SceneRecord, scene_ts: str) -> WorldDate:
    """The in-world date `scene_ts` (an ISO-8601 duration elapsed since the
    scene's start, `scene.ts`) lands on."""

    return record.start.plus(scene_ts)


def world_context_block(world: World, record: SceneRecord, at: WorldDate) -> str:
    """The "World" instruction's content: the scene's goal, its current
    place, and whatever lore has been pulled into it, all as of `at`. The
    place is `record.state["place_thing_id"]`; the lore entries are
    `record.state["pulled_in"]`."""

    view = world.view(at)

    place = None
    place_thing_id = record.state.get("place_thing_id")
    if place_thing_id:
        place_state = view.thing(place_thing_id)
        if place_state is not None:
            place = {
                "name": view.name_of(place_thing_id) or "",
                "facts": [fact.text for fact in place_state.facts],
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
        else (not this) regenerates it."""

        at = scene_date(self.record, scene.ts)
        for actor in scene.actors:
            character = actor.character
            thing_id = getattr(character, "world_thing_id", None)
            if thing_id is None:
                continue

            rebuilt = character_from_world(
                self.world, thing_id, at, is_player=character.is_player
            )
            rebuilt.agent = character.agent
            rebuilt.actor = actor

            actor.character = rebuilt
            if character.name in scene.character_data:
                del scene.character_data[character.name]
            scene.character_data[rebuilt.name] = rebuilt


def connect(scene) -> None:
    """Wire `scene`'s world context into the narrator and conversation
    agents' prompts, and keep its characters fresh across time passage.
    `scene.world_context` is read on every call rather than once here, so
    it can be set (or cleared) after `connect` runs -- a scene that never
    gets one is left exactly as before."""

    async def on_inject_instructions(emission) -> None:
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

    async def on_time_passage(emission) -> None:
        context: WorldSceneContext | None = getattr(scene, "world_context", None)
        if context is None:
            return
        await context.refresh_characters(scene)

    async_signals.get("agent.conversation.inject_instructions").connect(
        on_inject_instructions
    )
    async_signals.get("agent.narrator.inject_instructions").connect(
        on_inject_instructions
    )
    async_signals.get("agent.world_state.time").connect(on_time_passage)
