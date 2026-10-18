"""Tests for culture-aware character naming (plan 2 / task 7): the Culture
agent's pre-naming hook (culture guess, generator roll, one model pick),
the glossary record it leaves, and the after-persist step that sets the
new character's culture.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

import talemate.emit.async_signals as async_signals
import talemate.instance as instance
from talemate.agents.creator.character import CharacterNamingEmission
from talemate.agents.director.character_management import (
    PersistCharacterEmission,
    PersistCharacterRequest,
)
from talemate.agents.world_state.snapshot import WorldStateSnapshotEmission
from talemate.character import Character
from talemate.cultures.exchange import apply_import
from talemate.cultures.models import CharacterCulture, GlossaryEntry, GlossaryOrigin
from talemate.cultures.store import WorldStore, world_dir_for_scene
from talemate.prompts.base import Prompt
from talemate.scene_message import NarratorMessage
from talemate.shared_context import SharedContext

from _director_test_helpers import add_character_to_scene, patch_prompt_request_in
from conftest import MockScene, bootstrap_scene, connect_recorder
from cultures._fixtures import build_places

FIXTURE_PATH = Path(__file__).parent / "cultures" / "data" / "taelrik.culture.json"
LOCATION = "The Quillister inn in Veldhaer"
PICK = "culture.pick-name"


@pytest.fixture
def scene():
    scene = MockScene()
    bootstrap_scene(scene)
    return scene


@pytest.fixture
def world(scene, tmp_path) -> WorldStore:
    scene.shared_context = SharedContext(
        filepath=tmp_path / "shared-context" / "world.json"
    )
    store = WorldStore(world_dir_for_scene(scene))
    store.root.mkdir(parents=True, exist_ok=True)
    apply_import(store, FIXTURE_PATH.read_text(), today="2026-10-18")
    store.save_places(build_places())
    scene.world_state.location = LOCATION
    return store


@pytest.fixture
def agent(scene):
    agent = instance.get_agent("culture")
    agent.rng = random.Random(7)
    return agent


@pytest.fixture
def events(isolate_signals):
    return connect_recorder(isolate_signals("cultures.event"))


def install_picker(monkeypatch, pick):
    """Stub `Prompt.request`: `culture.pick-name` answers `pick(vars)`; every
    other template answers `("", {})`. Returns the recorded calls."""

    calls: list[dict] = []

    async def _request(cls, uid, client, kind, vars=None, **kwargs):
        calls.append({"template": uid, "kind": kind, "vars": vars or {}})
        if uid == PICK:
            return pick(vars)
        return "", {}

    monkeypatch.setattr(Prompt, "request", classmethod(_request), raising=True)
    return calls


def pick_index(index: int, why: str = "sounds old"):
    return lambda vars: ("Tovrin", {"name": vars["candidates"][index], "why": why})


def ferryman(content: str = "a gruff old man") -> CharacterNamingEmission:
    return CharacterNamingEmission(
        agent=instance.get_agent("creator"), name="the ferryman", content=content
    )


def ai_entries(store: WorldStore) -> list[GlossaryEntry]:
    return [e for e in store.load_glossary() if e.origin.by != "import"]


@pytest.mark.asyncio
async def test_description_name_gets_generator_pick(
    scene, world, agent, monkeypatch, events
):
    calls = install_picker(monkeypatch, pick_index(3))
    emission = ferryman()

    await agent.on_before_name_character(emission)

    [call] = calls
    candidates = call["vars"]["candidates"]
    assert call["kind"] == "analyze_freeform_medium_short"
    assert emission.chosen_name == candidates[3]

    [entry] = ai_entries(world)
    assert entry.text == emission.chosen_name
    assert entry.kind == "person"
    assert entry.language == "taelrik"
    assert entry.origin.by == "ai"
    assert entry.origin.generator_id == "given_male"
    assert entry.text in entry.origin.candidates
    assert len(entry.origin.candidates) == 20
    assert entry.status == "unreviewed"
    assert entry.character_name == emission.chosen_name
    assert entry.first_used.endswith(", character creation")

    assert emission.dynamic_instructions[0].title == "Culture"
    assert emission.dynamic_instructions[0].content.startswith(
        f"{emission.chosen_name} is Taelrik. River-folk of the grey river valleys."
    )
    assert "Their language is Taelrik: " in emission.dynamic_instructions[0].content
    # the original descriptive request is restated so the role survives
    assert any(
        "the ferryman" in i.content and "a gruff old man" in i.content
        for i in emission.dynamic_instructions
    )

    [event] = events
    assert event.kind == "name_chosen"
    assert event.changed is True
    assert event.data["name"] == emission.chosen_name
    assert event.data["culture_id"] == "taelrik"
    assert event.data["generator_id"] == "given_male"
    assert event.data["candidates"] == candidates
    assert event.data["by_model"] is True
    assert event.data["why"] == "sounds old"
    assert event.data["ms"] >= 0


@pytest.mark.asyncio
async def test_existing_name_not_replaced(scene, world, agent, monkeypatch, events):
    calls = install_picker(monkeypatch, pick_index(0))

    emission = CharacterNamingEmission(
        agent=instance.get_agent("creator"), name="Marigold"
    )
    await agent.on_before_name_character(emission)
    assert emission.chosen_name is None

    scene.history.append(NarratorMessage(message="'Pay up,' said the Rook."))
    emission = CharacterNamingEmission(
        agent=instance.get_agent("creator"), name="the Rook"
    )
    await agent.on_before_name_character(emission)
    assert emission.chosen_name is None

    assert calls == []
    assert ai_entries(world) == []
    assert events == []


@pytest.mark.asyncio
async def test_pick_off_list_uses_first_candidate(
    scene, world, agent, monkeypatch, events
):
    calls = install_picker(monkeypatch, lambda vars: ("Bob", {"name": "Bob"}))
    emission = ferryman()

    await agent.on_before_name_character(emission)

    candidates = calls[0]["vars"]["candidates"]
    assert emission.chosen_name == candidates[0]
    [event] = events
    assert event.data["by_model"] is False
    assert event.data["why"] == ""


@pytest.mark.asyncio
async def test_pick_error_uses_first_candidate(scene, world, agent, monkeypatch):
    seen: dict = {}

    def boom(vars):
        seen["candidates"] = vars["candidates"]
        raise RuntimeError("model down")

    install_picker(monkeypatch, boom)
    emission = ferryman()

    await agent.on_before_name_character(emission)

    assert emission.chosen_name == seen["candidates"][0]


@pytest.mark.asyncio
async def test_candidates_exclude_glossary_and_scene_names(
    scene, world, agent, monkeypatch
):
    calls = install_picker(monkeypatch, pick_index(0))
    await agent.on_before_name_character(ferryman())
    first_roll = calls[0]["vars"]["candidates"]

    # names the same seed would roll again
    in_glossary = first_roll[1]
    in_scene = first_roll[2]
    entries = world.load_glossary()
    entries.append(
        GlossaryEntry(
            id="seeded",
            text=in_glossary.upper(),
            language="taelrik",
            kind="person",
            origin=GlossaryOrigin(by="owner"),
        )
    )
    world.save_glossary(entries)
    await add_character_to_scene(scene, in_scene)

    agent.rng = random.Random(7)
    await agent.on_before_name_character(ferryman("a gruff old man, tired"))

    second_roll = calls[1]["vars"]["candidates"]
    for name in (first_roll[0], in_glossary, in_scene):
        assert name not in second_roll
    [entry] = [e for e in ai_entries(world) if e.text == second_roll[0]]
    for name in (first_roll[0], in_glossary, in_scene):
        assert name not in entry.origin.candidates


@pytest.mark.asyncio
async def test_repeated_hook_for_same_creation_decides_once(
    scene, world, agent, monkeypatch, events
):
    calls = install_picker(monkeypatch, pick_index(2))

    first = ferryman()
    await agent.on_before_name_character(first)
    second = ferryman()
    await agent.on_before_name_character(second)

    assert len(calls) == 1
    assert second.chosen_name == first.chosen_name
    assert len(ai_entries(world)) == 1
    assert len(events) == 1


@pytest.mark.asyncio
async def test_repeated_hook_remembers_no_name_decision(
    scene, world, agent, monkeypatch
):
    calls = install_picker(monkeypatch, pick_index(0))
    # no generator for the guessed culture: the first call decides "no name"
    culture = world.load_cultures()["taelrik"]
    culture.language.generators = [
        g for g in culture.language.generators if g.use != "people"
    ]
    world.save_culture(culture)

    first = ferryman()
    await agent.on_before_name_character(first)
    assert first.chosen_name is None

    # the generator comes back, but the same creation keeps its decision
    apply_import(world, FIXTURE_PATH.read_text(), today="2026-10-18")
    second = ferryman()
    await agent.on_before_name_character(second)
    assert second.chosen_name is None
    assert calls == []


@pytest.mark.asyncio
async def test_after_persist_sets_pending_culture(scene, world, agent, monkeypatch):
    install_picker(monkeypatch, pick_index(0))
    emission = ferryman()
    await agent.on_before_name_character(emission)
    name = emission.chosen_name

    character = Character(name=name)
    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )

    assert character.culture.culture_id == "taelrik"
    assert character.culture.set_by == "ai"
    assert name.lower() not in agent._pending
    # the hook's glossary entry is not duplicated
    assert len([e for e in world.load_glossary() if e.text == name]) == 1


@pytest.mark.asyncio
async def test_after_persist_existing_name_recorded_with_fit_flag(
    scene, world, agent, events
):
    character = Character(name="Marigold")
    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )

    [entry] = ai_entries(world)
    assert entry.text == "Marigold"
    assert entry.language == "taelrik"
    assert entry.doesnt_fit is True
    assert entry.origin.by == "ai_free"
    assert entry.character_name == "Marigold"
    assert entry.status == "unreviewed"
    assert entry.first_used.endswith(", character creation")
    assert character.culture.culture_id == "taelrik"
    assert character.culture.set_by == "ai"
    assert [e.kind for e in events] == ["name_chosen"]
    assert events[0].changed is True


@pytest.mark.asyncio
async def test_after_persist_multi_word_kept_name_fits(scene, world, agent):
    # "Khusrek" (given) and "Thriv" (family) each fit Taelrik
    character = Character(name="Khusrek Thriv")
    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )

    [entry] = ai_entries(world)
    assert entry.text == "Khusrek Thriv"
    assert entry.doesnt_fit is False


@pytest.mark.asyncio
async def test_after_persist_first_used_from_first_mention(scene, world, agent):
    scene.history.append(NarratorMessage(message="Nothing happens.", id=4))
    scene.history.append(NarratorMessage(message="Then Marigold walks in.", id=5))

    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=Character(name="Marigold")
        )
    )

    [entry] = ai_entries(world)
    assert entry.first_used.endswith(", message 5")


@pytest.mark.asyncio
async def test_owner_culture_kept_on_persist(scene, world, agent, events):
    character = Character(
        name="Marigold",
        culture=CharacterCulture(culture_id="elsiri", set_by="owner"),
    )
    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )

    assert character.culture.culture_id == "elsiri"
    assert character.culture.set_by == "owner"
    assert ai_entries(world) == []
    assert events == []


def snapshot_emission(scene) -> WorldStateSnapshotEmission:
    return WorldStateSnapshotEmission(
        agent=instance.get_agent("world_state"), world_state=scene.world_state
    )


@pytest.mark.asyncio
async def test_snapshot_culture_first_then_persist_still_glossaries_kept_name(
    scene, world, agent, monkeypatch
):
    # task 8c: a background snapshot can set the character's culture before
    # after-persist runs; the kept name must still reach the glossary
    install_picker(monkeypatch, lambda vars: ("", {}))
    scene.world_state.location = "A room at Quillister House in Veldhaer"
    character = await add_character_to_scene(scene, "Marigold")

    await agent.on_snapshot_after(snapshot_emission(scene))
    assert character.culture is not None
    assert character.culture.culture_id == "taelrik"
    assert character.culture.set_by == "ai"

    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )

    [entry] = [e for e in ai_entries(world) if e.text == "Marigold"]
    assert entry.origin.by == "ai_free"
    assert entry.language == "taelrik"
    assert entry.doesnt_fit is True


@pytest.mark.asyncio
async def test_persist_then_snapshot_still_one_glossary_entry(
    scene, world, agent, monkeypatch
):
    install_picker(monkeypatch, lambda vars: ("", {}))
    scene.world_state.location = "A room at Quillister House in Veldhaer"
    character = await add_character_to_scene(scene, "Marigold")

    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )
    assert character.culture.culture_id == "taelrik"

    await agent.on_snapshot_after(snapshot_emission(scene))

    entries = [e for e in ai_entries(world) if e.text == "Marigold"]
    assert len(entries) == 1
    assert entries[0].origin.by == "ai_free"
    # the snapshot step left the persist-time culture alone
    assert character.culture.culture_id == "taelrik"
    assert character.culture.set_by == "ai"


@pytest.mark.asyncio
async def test_kept_name_glossary_entry_never_duplicated(
    scene, world, agent, monkeypatch
):
    install_picker(monkeypatch, lambda vars: ("", {}))
    scene.world_state.location = "A room at Quillister House in Veldhaer"
    entries = world.load_glossary()
    entries.append(
        GlossaryEntry(
            id="seeded",
            text="Marigold",
            language="taelrik",
            kind="person",
            origin=GlossaryOrigin(by="owner"),
        )
    )
    world.save_glossary(entries)
    character = await add_character_to_scene(scene, "Marigold")

    await agent.on_snapshot_after(snapshot_emission(scene))
    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )

    assert len([e for e in world.load_glossary() if e.text == "Marigold"]) == 1


@pytest.mark.asyncio
async def test_pending_is_capped(scene, world, agent, monkeypatch):
    install_picker(monkeypatch, pick_index(0))
    for index in range(40):
        await agent.on_before_name_character(ferryman(f"a gruff old man, no. {index}"))

    assert 0 < len(agent._pending) <= 20


@pytest.mark.asyncio
async def test_end_to_end_through_persist_character(
    scene, world, agent, monkeypatch, isolate_signals
):
    isolate_signals(
        "agent.narrator.inject_instructions",
        "agent.conversation.inject_instructions",
        "agent.creator.before_name_character",
        "agent.director.character_management.after_persist_character",
        "world_state.snapshot.after",
        "game_loop_start",
    )
    agent.connect(scene)
    creator = instance.get_agent("creator")
    assert creator.cc_fast is False  # split mode

    stub = patch_prompt_request_in(monkeypatch)(
        {
            PICK: [("", {"name": "nobody-on-the-list", "why": ""})],
            "creator.determine-character-description": [
                ("", {"response": "A gruff old ferryman."})
            ],
            "creator.determine-character-dialogue-instructions": [
                ("", {"response": "Speaks in grunts."})
            ],
        }
    )

    director = instance.get_agent("director")
    character = await director.persist_character(
        PersistCharacterRequest(
            name="the ferryman",
            content="a gruff old man",
            narrate_entry=False,
            assign_voice=False,
            generate_attributes=False,
        )
    )

    [pick_call] = [c for c in stub.calls if c["template"] == PICK]
    candidates = pick_call["vars"]["candidates"]
    assert character is not None
    assert character.name == candidates[0]
    assert character.culture.culture_id == "taelrik"
    assert character.culture.set_by == "ai"
    assert character.description == "A gruff old ferryman."
    assert "creator.determine-character-name" not in [c["template"] for c in stub.calls]
    assert len([e for e in world.load_glossary() if e.text == character.name]) == 1
    assert agent.on_before_name_character in (
        async_signals.get("agent.creator.before_name_character").receivers
    )


@pytest.mark.asyncio
async def test_lowercase_description_mentioned_in_scene_still_named(
    scene, world, agent, monkeypatch
):
    calls = install_picker(monkeypatch, pick_index(0))
    scene.history.append(NarratorMessage(message="'Pay up,' said the ferryman."))

    emission = ferryman()
    await agent.on_before_name_character(emission)

    assert len(calls) == 1
    assert emission.chosen_name == calls[0]["vars"]["candidates"][0]


@pytest.mark.asyncio
async def test_culture_instruction_skips_empty_parts(scene, world, agent, monkeypatch):
    culture = world.load_cultures()["taelrik"]
    culture.description = ""
    culture.language.sound = ""
    world.save_culture(culture)
    install_picker(monkeypatch, pick_index(0))

    emission = ferryman()
    await agent.on_before_name_character(emission)

    content = emission.dynamic_instructions[0].content
    assert content == f"{emission.chosen_name} is Taelrik. Their language is Taelrik."
    assert "  " not in content
    assert not content.rstrip().endswith(",")


@pytest.mark.asyncio
async def test_pending_kept_when_glossary_save_fails(scene, world, agent, monkeypatch):
    install_picker(monkeypatch, pick_index(0))

    def fail(self, entries):
        raise OSError("disk full")

    monkeypatch.setattr(WorldStore, "save_glossary", fail)
    emission = ferryman()
    await agent.on_before_name_character(emission)

    assert emission.chosen_name
    assert agent._pending[emission.chosen_name.lower()].culture_id == "taelrik"


def test_pick_name_template_renders(scene, world):
    culture = world.load_cultures()["taelrik"]
    vars = {
        "scene": scene,
        "max_tokens": 4096,
        "candidates": ["Tovrin", "Kaeth"],
        "culture": culture,
        "language": culture.language,
        "character_hint": "the ferryman",
        "content": "a gruff old man",
        "description": "",
        "recent_text": "The river is high.",
        "place": "Veldhaer",
        "decensor": False,
    }
    text = Prompt.get("culture.pick-name", vars).render()

    assert "Requested as: the ferryman" in text
    assert "Place: Veldhaer" in text
    assert "best fits this character's role, age and gender" in text
    assert "Tovrin, Kaeth" in text
    assert 'long open "ae" vowels.' in text

    culture.language.sound = ""
    vars["language"] = culture.language
    text = Prompt.get("culture.pick-name", vars).render()
    assert "sounds like" not in text


def requested(content: str) -> CharacterNamingEmission:
    return CharacterNamingEmission(
        agent=instance.get_agent("creator"), name="", content=content
    )


@pytest.mark.asyncio
async def test_name_in_content_is_kept(scene, world, agent, monkeypatch, events):
    calls = install_picker(monkeypatch, pick_index(0))

    emission = requested("a baker named Bob Harl")
    await agent.on_before_name_character(emission)

    assert emission.chosen_name is None
    assert emission.dynamic_instructions == []
    assert calls == []
    assert ai_entries(world) == []

    # the decision is remembered: a second hook for the creation agrees
    again = requested("a baker named Bob Harl")
    await agent.on_before_name_character(again)
    assert again.chosen_name is None
    assert calls == []

    # the creator's own name is recorded on persist, as a kept name
    character = Character(name="Bob Harl")
    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"), character=character
        )
    )
    [entry] = ai_entries(world)
    assert entry.text == "Bob Harl"
    assert entry.origin.by == "ai_free"


@pytest.mark.asyncio
async def test_known_place_or_culture_in_content_still_named(
    scene, world, agent, monkeypatch
):
    calls = install_picker(monkeypatch, pick_index(0))

    emission = requested("a baker who works in Veldhaer")
    await agent.on_before_name_character(emission)
    assert len(calls) == 1
    assert emission.chosen_name == calls[0]["vars"]["candidates"][0]

    emission = requested("a gruff Taelrik Ferryman from the Taelrik Reach")
    await agent.on_before_name_character(emission)
    assert len(calls) == 2
    assert emission.chosen_name == calls[1]["vars"]["candidates"][0]


@pytest.mark.asyncio
async def test_unknown_place_in_content_does_not_block_naming(
    scene, world, agent, monkeypatch
):
    """Task 0: an unrecognised place mention ("from Kesterholm", "at the
    Lowmarsh Docks") isn't mistaken for the content naming the character,
    so culture naming still rolls a candidate."""
    calls = install_picker(monkeypatch, pick_index(0))

    emission = requested("a Taelrik ferryman from Kesterholm")
    await agent.on_before_name_character(emission)
    assert len(calls) == 1
    assert emission.chosen_name == calls[0]["vars"]["candidates"][0]

    emission = requested("a stallkeeper who sells fish at the Lowmarsh Docks")
    await agent.on_before_name_character(emission)
    assert len(calls) == 2
    assert emission.chosen_name == calls[1]["vars"]["candidates"][0]


@pytest.mark.asyncio
async def test_explicit_naming_still_wins_over_an_unknown_place(
    scene, world, agent, monkeypatch
):
    """Task 0 rule 3: explicit naming phrases ("called Varn") still keep
    the content's own name, even when another unknown place is mentioned
    right next to it."""
    calls = install_picker(monkeypatch, pick_index(0))

    emission = requested("a sailor called Varn from Kesterholm")
    await agent.on_before_name_character(emission)

    assert emission.chosen_name is None
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    ["a ranger named Vale", "a ferryman called Port", "a clerk known as Lane"],
)
async def test_explicit_naming_keeps_a_name_that_is_also_a_place_word(
    scene, world, agent, monkeypatch, content
):
    """A name that is also a common place word ("Vale", "Port", "Lane") is
    still the content naming the character when it is explicitly named."""
    calls = install_picker(monkeypatch, pick_index(0))

    emission = requested(content)
    await agent.on_before_name_character(emission)

    assert emission.chosen_name is None
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    ["a Taelrik ferryman from Kesterholm", "a Taelrik ferryman who works the Port"],
)
async def test_a_place_without_explicit_naming_is_not_a_name(
    scene, world, agent, monkeypatch, content
):
    """Without explicit naming, an unknown place or a common place word
    isn't the content naming the character, so culture naming still rolls
    a candidate."""
    calls = install_picker(monkeypatch, pick_index(0))

    emission = requested(content)
    await agent.on_before_name_character(emission)

    assert len(calls) == 1
    assert emission.chosen_name == calls[0]["vars"]["candidates"][0]


@pytest.mark.asyncio
async def test_overlapping_creations_keep_their_own_decisions(
    scene, world, agent, monkeypatch
):
    calls = install_picker(monkeypatch, pick_index(0))
    first = ferryman("a gruff old man")
    second = ferryman("a young deckhand")
    await agent.on_before_name_character(first)
    await agent.on_before_name_character(second)
    assert len(calls) == 2
    assert first.chosen_name != second.chosen_name

    # the first creation is saved while the second is still in flight
    await agent.on_after_persist_character(
        PersistCharacterEmission(
            agent=instance.get_agent("director"),
            character=Character(name=first.chosen_name),
        )
    )

    # the second creation's retry still gets its own name, without a roll
    retry = ferryman("a young deckhand")
    await agent.on_before_name_character(retry)
    assert retry.chosen_name == second.chosen_name
    assert len(calls) == 2
