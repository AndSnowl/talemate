"""Tests for the core culture hooks (plan 2 / task 5):

- the creator agent's pre-naming signal (`agent.creator.before_name_character`),
  which lets a listener (the Culture agent) pre-supply a culture-appropriate
  name before the creator invents one
- the world-state agent's post-snapshot signal (`world_state.snapshot.after`),
  sent once a snapshot update has been merged successfully

Both hooks must be complete no-ops when nothing is connected - the existing
creator / world-state suites (test_creator_character.py,
test_director_character_management.py, test_world_state_agent.py,
test_creator_nodes.py) assert that unchanged behaviour on their own, so these
tests focus on the hook wiring itself.
"""

from __future__ import annotations

import pytest

import talemate.instance as instance
from talemate.agents.base import DynamicInstruction
from talemate.agents.creator.character import CharacterGenerationRequest
from talemate.world_state import WorldStateResponse

from conftest import MockScene, bootstrap_scene, connect_recorder
from _director_test_helpers import patch_prompt_request_in


@pytest.fixture
def culture_scene():
    scene = MockScene()
    bootstrap_scene(scene)
    return scene


@pytest.fixture
def creator(culture_scene):
    return instance.get_agent("creator")


@pytest.fixture
def prompt_stub(monkeypatch):
    """Returns the ``install(responses) -> stub`` callable (see
    _director_test_helpers.patch_prompt_request_in)."""
    return patch_prompt_request_in(monkeypatch, "talemate.agents.creator.character")


# ---------------------------------------------------------------------------
# generate_character_aspects pre-naming hook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_split_name_presupplied_skips_llm(creator, isolate_signals, prompt_stub):
    signal = isolate_signals("agent.creator.before_name_character")

    async def set_name(emission):
        emission.chosen_name = "Tovrin"

    signal.connect(set_name)

    stub = prompt_stub({})

    result = await creator.generate_character_aspects(
        CharacterGenerationRequest(aspects=["name"], name="the ferryman", unified=False)
    )

    assert result.name == "Tovrin"
    assert not any(
        c["template"] == "creator.determine-character-name" for c in stub.calls
    )


@pytest.mark.asyncio
async def test_fast_name_presupplied_removes_name_aspect(
    creator, isolate_signals, prompt_stub
):
    signal = isolate_signals("agent.creator.before_name_character")

    async def set_name(emission):
        emission.chosen_name = "Tovrin"
        emission.dynamic_instructions.append(
            DynamicInstruction(title="Culture", content="Use local naming.")
        )

    signal.connect(set_name)

    stub = prompt_stub(
        {
            "creator.generate-character": [
                ("", {"description": "A quiet ferryman."}),
            ],
        }
    )

    result = await creator.generate_character_aspects(
        CharacterGenerationRequest(
            aspects=["name", "description"], name="the ferryman", unified=True
        )
    )

    assert result.name == "Tovrin"

    calls = [c for c in stub.calls if c["template"] == "creator.generate-character"]
    assert len(calls) == 1
    assert calls[0]["vars"]["aspects"] == ["description"]
    assert calls[0]["vars"]["character_name"] == "Tovrin"
    assert any(di.title == "Culture" for di in calls[0]["vars"]["dynamic_instructions"])


@pytest.mark.asyncio
async def test_no_receiver_keeps_existing_behaviour(
    creator, isolate_signals, prompt_stub
):
    isolate_signals("agent.creator.before_name_character")

    stub = prompt_stub(
        {
            "creator.determine-character-name": [("", {"name": "Fallback"})],
        }
    )

    result = await creator.generate_character_aspects(
        CharacterGenerationRequest(aspects=["name"], name="the ferryman", unified=False)
    )

    assert result.name == "Fallback"
    assert any(c["template"] == "creator.determine-character-name" for c in stub.calls)


# ---------------------------------------------------------------------------
# determine_character_name hook + opt-outs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_determine_character_name_hook_and_opt_out(
    creator, isolate_signals, prompt_stub
):
    signal = isolate_signals("agent.creator.before_name_character")
    prompt_stub({})

    async def set_name(emission):
        emission.chosen_name = "Tovrin"

    signal.connect(set_name)

    name = await creator.determine_character_name("the ferryman")
    assert name == "Tovrin"

    signal.disconnect(set_name)
    received = connect_recorder(signal)

    await creator.determine_character_name("the ferryman", allowed_names=["A"])
    assert received == []

    await creator.determine_character_name("the ferryman", group=True)
    assert received == []

    await creator.determine_character_name("the ferryman", culture_hook=False)
    assert received == []


@pytest.mark.asyncio
async def test_fill_aspect_name_does_not_rehook(creator, isolate_signals, prompt_stub):
    signal = isolate_signals("agent.creator.before_name_character")
    received = connect_recorder(signal)

    prompt_stub(
        {
            "creator.determine-character-name": [("", {"name": "Fallback"})],
        }
    )

    result = await creator.generate_character_aspects(
        CharacterGenerationRequest(aspects=["name"], name="the ferryman", unified=False)
    )

    assert result.name == "Fallback"
    assert len(received) == 1


# ---------------------------------------------------------------------------
# apply_snapshot_update post-snapshot signal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_after_signal_sent_on_success_only(
    culture_scene, isolate_signals, monkeypatch
):
    signal = isolate_signals("world_state.snapshot.after")
    received = connect_recorder(signal)

    agent = instance.get_agent("world_state")
    world_state = culture_scene.world_state

    async def ok_response(*args, **kwargs):
        return WorldStateResponse(
            world_state={
                "characters": {},
                "items": {},
                "places": {},
                "location": "Veldhaer",
            },
            anchor_message_ids=[1],
        )

    monkeypatch.setattr(agent, "request_world_state", ok_response)
    await agent.apply_snapshot_update(world_state)

    assert len(received) == 1
    assert received[0].world_state.location == "Veldhaer"

    received.clear()

    async def failing_response(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "request_world_state", failing_response)
    await agent.apply_snapshot_update(world_state)

    assert received == []
