"""AI tests: a world-state snapshot grows the glossary, places and cultures.

Opt-in (see tests/ai/conftest.py); every test here is auto-marked `ai`.
These check outcomes (what ended up on disk), never wording.
"""

from __future__ import annotations

from ai.cultures.conftest import load_cultures
from ai.cultures.scenarios import (
    ADDITION_MESSAGE,
    KNOWN_NAMES_MESSAGE,
    SCENARIOS,
    seed_scenario,
)
from talemate.cultures.store import WorldStore

# Not one of scenarios.py's premade messages (those are for taelrik_town):
# a short, neutral arrival line that names no person, only the place.
KESTERHOLM_ARRIVAL_MESSAGE = (
    "The ferry ties up at Kesterholm, a fishing hamlet on the Birch Coast, "
    "nets drying along its jetties."
)


def test_snapshot_adds_new_names(ai_app, session):
    world = seed_scenario(
        ai_app.root,
        "ai-snapshot-names",
        SCENARIOS["taelrik_town"],
        messages=[KNOWN_NAMES_MESSAGE],
    )
    session.wait_client_ready()
    session.load_scene(world.scene_path)

    session.request_snapshot()

    glossary = WorldStore(world.world_dir).load_glossary()
    person_texts = {entry.text.lower() for entry in glossary if entry.kind == "person"}
    thing_texts = {entry.text.lower() for entry in glossary if entry.kind == "thing"}

    # "any case, kind person/thing" -- a found name's text may carry an
    # honorific or article ("Old Brannoch"), so this checks containment,
    # not equality.
    assert any("brannoch" in text for text in person_texts), [e.text for e in glossary]
    assert any("grey gull" in text for text in thing_texts), [e.text for e in glossary]


def test_snapshot_creates_unknown_place(ai_app, session):
    world = seed_scenario(
        ai_app.root,
        "ai-snapshot-place",
        SCENARIOS["elsiri_pocket"],
        location="Kesterholm, a fishing hamlet on the Birch Coast",
        messages=[KESTERHOLM_ARRIVAL_MESSAGE],
    )
    session.wait_client_ready()
    session.load_scene(world.scene_path)

    session.request_snapshot()

    places = WorldStore(world.world_dir).load_places()
    kesterholm = next((p for p in places if p.name == "Kesterholm"), None)
    assert kesterholm is not None, [p.name for p in places]
    assert kesterholm.set_by == "ai"
    assert kesterholm.parent_id in {"birch", "ilsara"}


def test_snapshot_records_culture_addition(ai_app, session):
    world = seed_scenario(
        ai_app.root,
        "ai-snapshot-addition",
        SCENARIOS["taelrik_town"],
        messages=[ADDITION_MESSAGE],
    )
    session.wait_client_ready()
    session.load_scene(world.scene_path)

    session.request_snapshot()

    taelrik = load_cultures(world)["taelrik"]
    unreviewed_customs = [
        addition
        for addition in taelrik.additions
        if addition.status == "unreviewed" and addition.section == "customs"
    ]
    assert unreviewed_customs, [a.model_dump() for a in taelrik.additions]
