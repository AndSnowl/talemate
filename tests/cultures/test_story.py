"""Tests for the scene story data builder (plan 3 / task 2)."""

from pathlib import Path

from talemate.character import Character
from talemate.cultures.exchange import CultureFile
from talemate.cultures.models import (
    CharacterCulture,
    Culture,
    GlossaryEntry,
    GlossaryOrigin,
)
from talemate.cultures.story import build_story, scene_name_keys

from ._fixtures import build_cultures, build_places

FIXTURE_PATH = Path(__file__).parent / "data" / "taelrik.culture.json"


def load_taelrik() -> Culture:
    return CultureFile.model_validate_json(FIXTURE_PATH.read_text()).culture


def cultures_with_real_taelrik() -> dict[str, Culture]:
    cultures = build_cultures()
    cultures["taelrik"] = load_taelrik()
    ghun = cultures["ghun"]
    cultures["ghun"] = ghun.model_copy(
        update={
            "language": ghun.language.model_copy(update={"writable": False}),
        }
    )
    return cultures


def test_names_scoped_to_scene():
    cultures = cultures_with_real_taelrik()
    glossary = [
        GlossaryEntry(
            id="g-kethrun",
            text="Kethrun",
            language="taelrik",
            kind="person",
            origin=GlossaryOrigin(by="import"),
        ),
        GlossaryEntry(
            id="g-veldhaer",
            text="Veldhaer",
            language="taelrik",
            kind="place",
            origin=GlossaryOrigin(by="import"),
        ),
        GlossaryEntry(
            id="g-brannoch",
            text="Brannoch",
            language="taelrik",
            kind="person",
            origin=GlossaryOrigin(by="import"),
        ),
        GlossaryEntry(
            id="g-saervik",
            text="saervik",
            language="taelrik",
            kind="thing",
            meaning="river-runner; a flat ferry boat",
            origin=GlossaryOrigin(by="import"),
        ),
        GlossaryEntry(
            id="g-tovrin",
            text="Tovrin",
            language="taelrik",
            kind="person",
            origin=GlossaryOrigin(by="import"),
        ),
    ]
    scene_names = scene_name_keys(["Kethrun", "Veldhaer", "Tovrin's"])
    assert scene_names == {"kethrun", "veldhaer", "tovrin"}

    story = build_story(
        cultures=cultures,
        places=[],
        glossary=glossary,
        characters=[],
        scene_names=scene_names,
    )

    assert {n["text"] for n in story["names"]} == {"Kethrun", "Veldhaer", "Tovrin"}


def test_name_info_fields():
    cultures = cultures_with_real_taelrik()
    entry = GlossaryEntry(
        id="g-kethrun",
        text="Kethrun",
        language="taelrik",
        kind="person",
        meaning="ford-born",
        status="unreviewed",
        origin=GlossaryOrigin(by="ai", generator_id="given_male"),
    )
    scene_names = scene_name_keys(["Kethrun"])

    story = build_story(
        cultures=cultures,
        places=[],
        glossary=[entry],
        characters=[],
        scene_names=scene_names,
    )

    [info] = story["names"]
    assert info["generator_name"] == "Given names (male)"
    assert info["culture_name"] == "Taelrik"
    assert info["language_name"] == "Taelrik"
    assert info["color"] == "#FF8A65"
    assert info["writable"] is True


def test_unwritable_name_info_matched_by_rendering():
    cultures = cultures_with_real_taelrik()
    entry = GlossaryEntry(
        id="g-mountain",
        text="the north mountain",
        language="ghun",
        kind="place",
        true_name="three falling hums",
        renderings={"taelrik": "Khaz-Rull", "nowhere": "X"},
        origin=GlossaryOrigin(by="ai"),
    )
    scene_names = {"khaz-rull"}

    story = build_story(
        cultures=cultures,
        places=[],
        glossary=[entry],
        characters=[],
        scene_names=scene_names,
    )

    [info] = story["names"]
    assert info["writable"] is False
    assert info["renderings"] == [
        {"culture_id": "taelrik", "culture_name": "Taelrik", "text": "Khaz-Rull"},
        {"culture_id": "nowhere", "culture_name": "nowhere", "text": "X"},
    ]


def test_character_infos():
    cultures = cultures_with_real_taelrik()
    characters = [
        Character(
            name="Kethrun",
            description="",
            culture=CharacterCulture(
                culture_id="taelrik", set_by="ai", unsure=True, reason="speech"
            ),
        ),
        Character(
            name="Alder",
            description="",
            culture=CharacterCulture(culture_id=None, set_by="owner"),
        ),
        Character(name="Brannoch", description="", culture=None),
    ]

    story = build_story(
        cultures=cultures,
        places=[],
        glossary=[],
        characters=characters,
        scene_names=set(),
    )

    by_name = {c["name"]: c for c in story["characters"]}
    assert [c["name"] for c in story["characters"]] == ["Alder", "Brannoch", "Kethrun"]
    assert by_name["Kethrun"]["culture_name"] == "Taelrik"
    assert by_name["Kethrun"]["unsure"] is True
    assert by_name["Kethrun"]["reason"] == "speech"
    assert by_name["Alder"]["set_by"] == "owner"
    assert by_name["Alder"]["culture_id"] is None
    assert by_name["Brannoch"]["set_by"] is None


def test_place_infos_inherit_and_mix():
    cultures = cultures_with_real_taelrik()
    places = build_places()

    story = build_story(
        cultures=cultures,
        places=places,
        glossary=[],
        characters=[],
        scene_names=set(),
    )

    by_id = {p["id"]: p for p in story["places"]}

    veldhaer = by_id["veldhaer"]
    assert veldhaer["own"] is False
    assert veldhaer["source_name"] == "The Taelrik Reach"
    assert veldhaer["mix"] == [
        {
            "culture_id": "taelrik",
            "culture_name": "Taelrik",
            "color": "#FF8A65",
            "share": 100,
        }
    ]

    dhunmouth = by_id["dhunmouth"]
    assert dhunmouth["own"] is True
    assert [cs["culture_id"] for cs in dhunmouth["mix"]] == [
        "taelrik",
        "elsiri",
        "vaskari",
    ]
