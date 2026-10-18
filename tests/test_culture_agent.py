"""Tests for the Culture agent (plan 2 / task 6): registration and config,
the "Cultures and names" prompt section injected into narrator and
conversation prompts, the `cultures.event` signal, and the guarantee that a
scene without a usable shared world is left exactly as before.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import talemate.emit.async_signals as async_signals
import talemate.instance as instance
from talemate.agents.conversation import ConversationAgentEmission
from talemate.agents.creator.character import CharacterNamingEmission
from talemate.agents.narrator import NarratorAgentEmission
from talemate.character import Character
from talemate.cultures.context import SPARE_NAMES_PREFIX
from talemate.cultures.exchange import apply_import
from talemate.cultures.store import WorldStore, world_dir_for_scene
from talemate.shared_context import SharedContext

from conftest import MockScene, bootstrap_scene, connect_recorder
from cultures._fixtures import build_places

FIXTURE_PATH = Path(__file__).parent / "cultures" / "data" / "taelrik.culture.json"
LOCATION = "The Quillister inn in Veldhaer"


def _link_world(scene, tmp_path) -> WorldStore:
    world_path = tmp_path / "shared-context" / "world.json"
    scene.shared_context = SharedContext(filepath=world_path)
    store = WorldStore(world_dir_for_scene(scene))
    store.root.mkdir(parents=True, exist_ok=True)
    return store


@pytest.fixture
def scene():
    scene = MockScene()
    bootstrap_scene(scene)
    return scene


@pytest.fixture
def world(scene, tmp_path) -> WorldStore:
    store = _link_world(scene, tmp_path)
    apply_import(store, FIXTURE_PATH.read_text(), today="2026-10-18")
    store.save_places(build_places())
    scene.world_state.location = LOCATION
    return store


@pytest.fixture
def agent(scene):
    return instance.get_agent("culture")


def _instructions(emission):
    return [i for i in emission.dynamic_instructions if i.title == "Cultures and names"]


def test_agent_registered_and_defaults(agent):
    assert agent is not None
    assert agent.agent_type == "culture"
    assert agent.context_budget == 400
    assert agent.candidate_count == 20
    assert agent.has_toggle is True
    assert agent.enabled is True


@pytest.mark.asyncio
async def test_narrator_emission_gets_section(scene, world, agent):
    narrator = instance.get_agent("narrator")
    emission = NarratorAgentEmission(agent=narrator)

    await agent.on_inject_instructions(emission)

    assert len(emission.dynamic_instructions) == 1
    instruction = emission.dynamic_instructions[0]
    assert instruction.title == "Cultures and names"
    assert "Veldhaer" in instruction.content
    assert SPARE_NAMES_PREFIX in instruction.content

    spares = agent.get_scene_state("offered_spares")
    assert spares
    first = next(iter(spares.values()))
    assert first["culture_id"] == "taelrik"
    assert first["generator_id"]
    assert agent.get_scene_state("current_place_id") == "veldhaer"


@pytest.mark.asyncio
async def test_conversation_emission_uses_speaker_traits(scene, world, agent):
    char = Character(name="Hadrik", description="He curses in Taelrik when angry.")
    conv = instance.get_agent("conversation")
    emission = ConversationAgentEmission(
        agent=conv, actor=None, character=char, response=""
    )

    await agent.on_inject_instructions(emission)

    [instruction] = _instructions(emission)
    assert "Rhok tal'dun!" in instruction.content or (
        "Dhaer tal'skev." in instruction.content
    )


async def _assert_noop(scene, agent):
    narrator = instance.get_agent("narrator")
    emission = NarratorAgentEmission(agent=narrator)
    await agent.on_inject_instructions(emission)
    assert emission.dynamic_instructions == []

    naming = CharacterNamingEmission(
        agent=instance.get_agent("creator"), name="the ferryman"
    )
    await agent.on_before_name_character(naming)
    assert naming.chosen_name is None

    assert scene.agent_state.get("culture", {}) == {}


@pytest.mark.asyncio
async def test_hooks_noop_without_world(scene, agent, tmp_path, isolate_signals):
    events = connect_recorder(isolate_signals("cultures.event"))
    scene.world_state.location = LOCATION

    # no shared context
    assert scene.shared_context is None
    await _assert_noop(scene, agent)

    # a world with zero cultures (places only)
    store = _link_world(scene, tmp_path)
    store.save_places(build_places())
    await _assert_noop(scene, agent)

    # the only culture file is corrupt
    apply_import(store, FIXTURE_PATH.read_text(), today="2026-10-18")
    (store.cultures_dir / "taelrik.json").write_text("{")
    await _assert_noop(scene, agent)

    assert events == []


@pytest.mark.asyncio
async def test_disabled_agent_does_nothing(scene, world, agent, isolate_signals):
    events = connect_recorder(isolate_signals("cultures.event"))
    agent.is_enabled = False

    await _assert_noop(scene, agent)
    assert events == []


@pytest.mark.asyncio
async def test_context_injected_event_sent(scene, world, agent, isolate_signals):
    events = connect_recorder(isolate_signals("cultures.event"))

    emission = NarratorAgentEmission(agent=instance.get_agent("narrator"))
    await agent.on_inject_instructions(emission)

    assert len(events) == 1
    event = events[0]
    assert event.kind == "context_injected"
    assert event.world_dir == str(world.root)
    assert event.changed is False
    assert event.data["agent"] == "narrator"
    assert event.data["tokens"] > 0
    assert event.data["text"] == emission.dynamic_instructions[0].content
    assert event.data["spares"]


@pytest.mark.asyncio
async def test_offered_spares_capped(scene, world, agent):
    narrator = instance.get_agent("narrator")
    for _ in range(30):
        await agent.on_inject_instructions(NarratorAgentEmission(agent=narrator))

    spares = agent.get_scene_state("offered_spares")
    assert 0 < len(spares) <= 60


@pytest.mark.asyncio
async def test_connect_wires_signals(scene, agent, isolate_signals):
    names = [
        "agent.narrator.inject_instructions",
        "agent.conversation.inject_instructions",
        "agent.creator.before_name_character",
        "agent.director.character_management.after_persist_character",
        "world_state.snapshot.after",
    ]
    isolate_signals(*names)

    agent.connect(scene)

    assert agent.on_inject_instructions in async_signals.get(names[0]).receivers
    assert agent.on_inject_instructions in async_signals.get(names[1]).receivers
    assert agent.on_before_name_character in async_signals.get(names[2]).receivers
    assert agent.on_after_persist_character in async_signals.get(names[3]).receivers
    assert agent.on_snapshot_after in async_signals.get(names[4]).receivers


@pytest.mark.asyncio
async def test_handler_errors_are_swallowed(scene, world, agent, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "scene_cultures", boom)
    emission = NarratorAgentEmission(agent=instance.get_agent("narrator"))

    await agent.on_inject_instructions(emission)

    assert emission.dynamic_instructions == []


def _spy_loads(monkeypatch) -> dict:
    calls = {"cultures": 0, "places": 0, "glossary": 0}
    for name in calls:
        original = getattr(WorldStore, f"load_{name}")

        def spy(self, _original=original, _name=name):
            calls[_name] += 1
            return _original(self)

        monkeypatch.setattr(WorldStore, f"load_{name}", spy)
    return calls


def test_load_world_cached_while_files_unchanged(scene, world, agent, monkeypatch):
    calls = _spy_loads(monkeypatch)

    first = agent.load_world()
    second = agent.load_world()

    assert first is not None and second is not None
    assert calls == {"cultures": 1, "places": 1, "glossary": 1}
    assert second.cultures.keys() == first.cultures.keys()
    # callers get their own containers, so mutating one can't poison the cache
    second.glossary.append("x")
    assert "x" not in agent.load_world().glossary


def test_load_world_cache_invalidated_by_glossary_change(
    scene, world, agent, monkeypatch
):
    calls = _spy_loads(monkeypatch)
    before = agent.load_world()

    # a write (as from the Cultures tab) changes size and mtime
    world.save_glossary(before.glossary[:-1])
    after = agent.load_world()
    assert calls["glossary"] == 2
    assert len(after.glossary) == len(before.glossary) - 1

    # a bare touch with a new mtime also invalidates
    import os

    stat = world.glossary_path.stat()
    os.utime(world.glossary_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
    agent.load_world()
    assert calls["glossary"] == 3


def test_load_world_cache_invalidated_by_corrupt_culture(scene, world, agent):
    assert agent.load_world() is not None
    (world.cultures_dir / "taelrik.json").write_text("{")
    assert agent.load_world() is None
