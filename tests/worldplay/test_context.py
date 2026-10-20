"""Tests for `talemate.worldplay.context`: the "World" instruction built
from a scene's world record, its injection into narrator/conversation
prompts, and keeping active characters fresh across time passage."""

import pytest

import talemate.emit.async_signals as async_signals
import talemate.instance as instance
from talemate.agents.conversation import ConversationAgentEmission
from talemate.character import Character
from talemate.tale_mate import Actor
from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.context import WorldSceneContext, connect, world_context_block

from conftest import MockScene, bootstrap_scene


def test_world_context_block_has_goal_place_lore(world):
    with world.revision(Source.manual(note="setup")) as rev:
        place_id = rev.create_thing("place", fields={"name": "Veldhaer"})
        rev.add_fact(place_id, "description", "A harbor town built on stilts.")
        lore_id = rev.create_thing("lore", fields={"name": "The River Treaty"})
        rev.add_fact(lore_id, "general", "Signed after the flood of 301.")

    scenes = world.scenes()
    scene_id = scenes.create(
        "Test Scene", WorldDate.of(310), goal="Find the missing envoy"
    )
    scenes.update(scene_id, state={"place_thing_id": place_id, "pulled_in": [lore_id]})
    record = scenes.get(scene_id)

    block = world_context_block(world, record, WorldDate.of(310))

    assert "Find the missing envoy" in block
    assert "Veldhaer" in block
    assert "A harbor town built on stilts." in block
    assert "The River Treaty" in block
    assert "Signed after the flood of 301." in block


@pytest.mark.asyncio
async def test_inject_adds_world_instruction(world):
    with world.revision(Source.manual(note="setup")) as rev:
        place_id = rev.create_thing("place", fields={"name": "Veldhaer"})

    scenes = world.scenes()
    scene_id = scenes.create(
        "Test Scene", WorldDate.of(310), goal="Find the missing envoy"
    )
    scenes.update(scene_id, state={"place_thing_id": place_id})
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)
    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)

    conversation = instance.get_agent("conversation")
    emission = ConversationAgentEmission(
        agent=conversation, character=Character(name="Anyone"), response=""
    )
    await async_signals.get("agent.conversation.inject_instructions").send(emission)

    instructions = [i for i in emission.dynamic_instructions if i.title == "World"]
    assert len(instructions) == 1
    assert "Find the missing envoy" in instructions[0].content
    assert "Veldhaer" in instructions[0].content


@pytest.mark.asyncio
async def test_since_lines_after_time_passage(world):
    """Review Focus 1: a scene at 313-12-15, a time passage of P30D into
    314 crosses the stretch boundary the cached description was generated
    for. `refresh_characters` must still pick up the since line -- and
    must never touch the model to do it."""

    with world.revision(Source.manual(note="create Mira")) as rev:
        thing_id = rev.create_thing(
            "character",
            fields={"name": "Mira", "born": WorldDate.of(280)},
            valid_from=WorldDate.of(280),
        )
        rev.add_fact(
            thing_id,
            "appearance",
            "A scar across her cheek.",
            valid_from=WorldDate.of(314),
        )

    # The real stretch boundaries for this thing are (None, 280), (280,
    # 314) and (314, None) -- cached here for the (280, 314) one (fix
    # round 1 / Critical 2: an earlier version of this test used the
    # fabricated, non-real pair (None, 314), which happened to still
    # match on lookup and so never exercised the cache walk-back bug).
    world.prose().put(
        thing_id,
        "description",
        WorldDate.of(280),
        WorldDate.of(314),
        "A quiet trader with a steady gaze.",
    )

    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(313, 12, 15))
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)

    character = character_from_world(world, thing_id, record.start, is_player=False)
    assert "scar" not in character.description
    character.color = "#abc123"  # a per-scene field refresh must not touch

    conversation = instance.get_agent("conversation")
    actor = Actor(character=character, agent=conversation)
    actor.scene = scene
    scene.actors.append(actor)
    scene.active_characters.append(character.name)
    scene.character_data[character.name] = character

    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)

    world_state = instance.get_agent("world_state")
    await world_state.advance_time("P30D")

    refreshed = scene.get_character("Mira")
    assert refreshed is not character
    assert "Since 314: A scar across her cheek." in refreshed.description

    # fix round 1 / Critical 4: a per-scene field survives the refresh.
    assert refreshed.color == "#abc123"
    # fix round 1 (small fix): the agent's own pointer is updated too.
    assert actor.agent.character is refreshed

    # No queued responses in `scene.mock_client` -- a call to `send_prompt`
    # would have appended to `prompt_history` regardless of what it
    # returned, so an empty history proves the model was never touched.
    assert scene.mock_client.prompt_history == []


@pytest.mark.asyncio
async def test_refresh_characters_keeps_existing_when_thing_deleted(world):
    """Review-round fix: `agent.world_state.time` fires `refresh_characters`
    for every active character on every time skip (and
    `server/worlds.py`'s `_refresh_loaded` calls it directly from
    `reposition_scene`). A character whose world thing has since been
    deleted must not blow up that signal -- `character_from_world` raises
    KeyError for it, so the actor keeps its last-built character, with a
    warning logged (the same pattern `persistence._character_data` uses
    on load)."""

    with world.revision(Source.manual(note="create Mira")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Mira"})

    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(313, 12, 15))
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)

    character = character_from_world(world, thing_id, record.start, is_player=False)

    conversation = instance.get_agent("conversation")
    actor = Actor(character=character, agent=conversation)
    actor.scene = scene
    scene.actors.append(actor)
    scene.active_characters.append(character.name)
    scene.character_data[character.name] = character

    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)

    with world.revision(Source.manual(note="deleted Mira")) as rev:
        rev.remove_thing(thing_id)

    world_state = instance.get_agent("world_state")
    await world_state.advance_time("P30D")  # must not raise

    assert actor.character is character
    assert actor.agent.character is character
    assert scene.get_character("Mira") is character


@pytest.mark.asyncio
async def test_connect_does_not_leak_between_scenes(world):
    """Fix round 1 / Critical 3: `connect` used to add a per-scene closure
    that was never disconnected, so a second scene's signal traffic would
    still carry the first scene's "World" block. The handlers are
    module-level now, resolved from `emission.agent.scene` -- which is
    whichever scene most recently claimed the (process-wide) agent
    instance, the same as real scene loading."""

    scenes = world.scenes()
    scene_id = scenes.create(
        "Scene A", WorldDate.of(310), goal="Find the missing envoy"
    )
    record = scenes.get(scene_id)

    scene_a = MockScene()
    bootstrap_scene(scene_a)
    scene_a.world_context = WorldSceneContext(world=world, record=record)
    connect(scene_a)

    scene_b = MockScene()
    bootstrap_scene(scene_b)  # re-points every agent's `.scene` at scene_b
    connect(scene_b)  # scene_b never gets a `world_context`

    conversation = instance.get_agent("conversation")

    emission_b = ConversationAgentEmission(
        agent=conversation, character=Character(name="Anyone"), response=""
    )
    await async_signals.get("agent.conversation.inject_instructions").send(emission_b)
    assert emission_b.dynamic_instructions == []

    # make the (shared) agent "live" in scene A again, the way loading a
    # scene would, and fire the same signal: exactly one "World"
    # instruction, not two, even though `connect` ran twice.
    conversation.scene = scene_a
    emission_a = ConversationAgentEmission(
        agent=conversation, character=Character(name="Anyone"), response=""
    )
    await async_signals.get("agent.conversation.inject_instructions").send(emission_a)
    world_instructions = [
        i for i in emission_a.dynamic_instructions if i.title == "World"
    ]
    assert len(world_instructions) == 1
