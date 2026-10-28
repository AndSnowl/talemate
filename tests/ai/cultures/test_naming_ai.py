"""AI tests: the Culture agent names new NPCs to fit the scene's culture.

Opt-in (see tests/ai/conftest.py); every test here is auto-marked `ai`.
These check outcomes (which name ended up where, with what provenance),
never wording.
"""

from __future__ import annotations

from ai.cultures.conftest import load_cultures
from ai.cultures.scenarios import NPC_ROLES, SCENARIOS, seed_scenario
from talemate.languages.generator import fits
from talemate.cultures.store import WorldStore

ROLE_CONTENT = dict(NPC_ROLES)


def test_new_npc_in_taelrik_town_gets_fitting_name(ai_app, session):
    world = seed_scenario(ai_app.root, "ai-naming-taelrik", SCENARIOS["taelrik_town"])
    session.wait_client_ready()
    session.load_scene(world.scene_path)

    session.persist_character("the ferryman", ROLE_CONTENT["the ferryman"])

    glossary = WorldStore(world.world_dir).load_glossary()
    new_person_entries = [
        entry
        for entry in glossary
        if entry.kind == "person" and entry.origin.by == "ai"
    ]
    assert len(new_person_entries) == 1, [e.model_dump() for e in new_person_entries]
    entry = new_person_entries[0]

    assert entry.language == "taelrik"
    assert entry.status == "unreviewed"
    assert entry.origin.generator_id == "given_male"
    assert len(entry.origin.candidates) >= 10
    assert entry.text in entry.origin.candidates

    taelrik = load_cultures(world)["taelrik"]
    assert fits(taelrik.language, entry.text)

    characters = session.get_world()["characters"]
    character = next((c for c in characters if c["name"] == entry.text), None)
    assert character is not None, [c["name"] for c in characters]
    assert character["culture"]["culture_id"] == "taelrik"


def test_npc_in_elsiri_pocket_named_from_its_culture(ai_app, session):
    world = seed_scenario(ai_app.root, "ai-naming-elsiri", SCENARIOS["elsiri_pocket"])
    session.wait_client_ready()
    session.load_scene(world.scene_path)

    session.persist_character("the fishwife", ROLE_CONTENT["the fishwife"])

    glossary = WorldStore(world.world_dir).load_glossary()
    new_person_entries = [
        entry
        for entry in glossary
        if entry.kind == "person" and entry.origin.by == "ai"
    ]
    assert len(new_person_entries) == 1, [e.model_dump() for e in new_person_entries]
    entry = new_person_entries[0]

    assert entry.language in ("elsiri", "taelrik")
    assert entry.origin.generator_id == "given_female"

    culture = load_cultures(world)[entry.language]
    assert fits(culture.language, entry.text)


def test_typed_name_is_kept(ai_app, session):
    world = seed_scenario(ai_app.root, "ai-naming-typed", SCENARIOS["taelrik_town"])
    session.wait_client_ready()
    session.load_scene(world.scene_path)

    session.persist_character("Marigold", "A halfling baker.")

    characters = session.get_world()["characters"]
    character = next((c for c in characters if c["name"] == "Marigold"), None)
    assert character is not None, [c["name"] for c in characters]

    glossary = WorldStore(world.world_dir).load_glossary()
    entry = next((e for e in glossary if e.text == "Marigold"), None)
    assert entry is not None, [e.text for e in glossary]
    assert entry.origin.by == "ai_free"
    assert entry.doesnt_fit is True
