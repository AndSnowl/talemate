"""Tests for the pure post-snapshot detection helpers (plan 2 / task 8):
new place names, new glossary names, and parsing the place and additions
replies."""

from __future__ import annotations

import json
from pathlib import Path

from talemate.character import Character
from talemate.cultures.detect import (
    find_new_names,
    new_place_names,
    parse_additions_reply,
    parse_places_reply,
)
from talemate.cultures.models import (
    CharacterCulture,
    Culture,
    GlossaryEntry,
    GlossaryOrigin,
    Place,
)
from talemate.cultures.scene_context import resolve_scene_cultures
from talemate.scene_message import NarratorMessage

from cultures._fixtures import build_cultures, build_places

FIXTURE_PATH = Path(__file__).parent / "data" / "taelrik.culture.json"


def world_cultures() -> dict[str, Culture]:
    """The fixture cultures, with the full Taelrik culture (generators,
    customs, food, holidays) in place of the bare one."""
    cultures = build_cultures()
    data = json.loads(FIXTURE_PATH.read_text())
    cultures["taelrik"] = Culture.model_validate(data["culture"])
    return cultures


def scene_at(location: str, characters=()):
    return resolve_scene_cultures(
        world_cultures(), build_places(), location, [], list(characters)
    )


def find(**overrides):
    cultures = world_cultures()
    kwargs = dict(
        characters=[],
        items=[],
        places_found=[],
        glossary=[],
        cultures=cultures,
        scene=scene_at("Veldhaer"),
        scene_characters={},
        messages=[],
        offered_spares={},
        story="Ferry",
        places=build_places(),
    )
    kwargs.update(overrides)
    return find_new_names(**kwargs)


def entry(text: str, kind: str = "person") -> GlossaryEntry:
    return GlossaryEntry(
        id=text.lower(),
        text=text,
        language="taelrik",
        kind=kind,
        origin=GlossaryOrigin(by="owner"),
    )


def place_named(name: str) -> Place:
    return Place(id=name.lower(), name=name, kind="building", parent_id="veldhaer")


def test_new_place_names():
    places = build_places()
    assert new_place_names(
        "Kesterholm, a fishing hamlet on the Birch Coast", [], places, []
    ) == ["Kesterholm"]
    assert new_place_names(
        "Kesterholm, a fishing hamlet on the Birch Coast",
        ["the docks", "Kesterholm"],
        places,
        [],
    ) == ["Kesterholm"]
    # character names and known places (any case) are not new places
    assert (
        new_place_names(
            "Brannoch's hut in veldhaer", ["DHUNMOUTH"], places, ["Brannoch"]
        )
        == []
    )
    assert new_place_names(None, ["Kesh Hollow."], places, []) == ["Kesh Hollow"]


def test_snapshot_skips_descriptions_and_normalizes():
    messages = [NarratorMessage(message="They tied up beside the Grey Gull.")]
    findings = find(
        characters=["the old ferryman", "Brannoch.", "Tovrin's"],
        items=["a rusty lantern", "Lantern", "Grey Gull"],
        messages=messages,
    )
    persons = {f.text for f in findings if f.kind == "person"}
    things = {f.text for f in findings if f.kind == "thing"}
    assert persons == {"Brannoch", "Tovrin"}
    assert things == {"Grey Gull"}
    [gull] = [f for f in findings if f.kind == "thing"]
    assert gull.culture_id == "taelrik"
    assert gull.first_used == f"Ferry, message {messages[0].id}"
    assert gull.origin.by == "ai_free"
    brannoch = next(f for f in findings if f.text == "Brannoch")
    assert brannoch.character_name == "Brannoch"
    assert brannoch.first_used == "Ferry"


def test_spare_name_gets_generator_origin():
    [finding] = find(
        characters=["Kethvar"],
        offered_spares={
            "kethvar": {"culture_id": "taelrik", "generator_id": "given_male"}
        },
    )
    assert finding.origin.by == "ai"
    assert finding.origin.generator_id == "given_male"
    # R6: the offered batch isn't retained
    assert finding.origin.candidates == []


def test_known_names_skipped_case_insensitive():
    findings = find(
        characters=["BRANNOCH", "Tovrin"],
        items=["Grey Gull"],
        places_found=[("Kesterholm", "k1")],
        glossary=[entry("brannoch"), entry("grey gull", "thing"), entry("KESTERHOLM")],
        messages=[NarratorMessage(message="They tied up beside the Grey Gull.")],
    )
    assert [f.text for f in findings] == ["Tovrin"]


def test_doesnt_fit_flag():
    [marigold] = find(characters=["Marigold"])
    assert marigold.culture_id == "taelrik"
    assert marigold.doesnt_fit is True


def test_multi_word_person_name_fits_word_by_word():
    # given name (CVC+rek) and family name (C(V)CVC) each fit Taelrik
    by_text = {
        f.text: f for f in find(characters=["Khusrek Thriv", "Khusrek Marigold"])
    }
    assert by_text["Khusrek Thriv"].doesnt_fit is False
    assert by_text["Khusrek Marigold"].doesnt_fit is True


def test_person_keeps_own_culture_and_places_get_place_culture():
    character = Character(
        name="Brannoch",
        culture=CharacterCulture(culture_id="elsiri", set_by="owner"),
    )
    findings = find(
        characters=["Brannoch"],
        scene_characters={"Brannoch": character},
        places_found=[("Ilsara", "ilsara")],
    )
    by_text = {f.text: f for f in findings}
    assert by_text["Brannoch"].culture_id == "elsiri"
    assert by_text["Ilsara"].kind == "place"
    assert by_text["Ilsara"].place_id == "ilsara"
    # Ilsara inherits the Birch Coast mix, mostly Elsiri
    assert by_text["Ilsara"].culture_id == "elsiri"


def test_parse_places_reply():
    places = build_places()
    cultures = world_cultures()
    current = next(p for p in places if p.id == "veldhaer")

    [place] = parse_places_reply(
        "Kesterholm | village | Birch Coast | inherit | sure",
        ["Kesterholm"],
        places,
        cultures,
        current,
    )
    assert place.name == "Kesterholm"
    assert place.kind == "village"
    assert place.parent_id == "birch"
    assert place.cultures == []
    assert place.set_by == "ai"
    assert place.unsure is False

    [place] = parse_places_reply(
        "Kesterholm | castle | Nowhere | Elsiri 70, Taelrik 30 | sure",
        ["Kesterholm"],
        places,
        cultures,
        current,
    )
    assert place.kind == "poi"
    assert place.parent_id == "veldhaer"
    assert {(cs.culture_id, cs.share) for cs in place.cultures} == {
        ("elsiri", 70),
        ("taelrik", 30),
    }
    assert place.set_by == "ai"
    assert place.unsure is True

    [place] = parse_places_reply("", ["Kesterholm"], places, cultures, current)
    assert place.name == "Kesterholm"
    assert place.parent_id == "veldhaer"
    assert place.cultures == []
    assert place.set_by == "ai"
    assert place.unsure is True

    # lines for names not asked about are ignored; ids are new
    found = parse_places_reply(
        "Oakford | village | Birch Coast | inherit | sure\n"
        "Kesterholm | village | Birch Coast | inherit | sure",
        ["Kesterholm"],
        places,
        cultures,
        current,
    )
    assert [p.name for p in found] == ["Kesterholm"]
    assert found[0].id not in {p.id for p in places}


def test_parse_additions_reply_dedupes():
    cultures = world_cultures()
    taelrik = cultures["taelrik"]
    reply = (
        "Taelrik | customs | Every crossing ends with a coin dropped in the river.\n"
        "taelrik | food | Smoked eel\n"
        "Taelrik | holidays | Lantern Night is held at first frost.\n"
        "Taelrik | customs | Ferrymen spit over the rail before landing.\n"
        "Nobody | customs | Strangers bow twice."
    )
    found = parse_additions_reply(reply, [taelrik], "Ferry, message 4")
    assert len(found) == 1
    culture_id, addition = found[0]
    assert culture_id == "taelrik"
    assert addition.section == "customs"
    assert addition.text == "Ferrymen spit over the rail before landing."
    assert addition.source == "Ferry, message 4"
    assert addition.status == "unreviewed"
    assert addition.id

    assert parse_additions_reply("NONE", [taelrik], "s") == []
    assert parse_additions_reply("", [taelrik], "s") == []


def test_parse_additions_reply_limit():
    taelrik = world_cultures()["taelrik"]
    reply = "\n".join(
        f"Taelrik | customs | Custom number {word} is kept."
        for word in ("one", "two", "three", "four")
    )
    assert len(parse_additions_reply(reply, [taelrik], "s")) == 3


def test_the_names_inn_and_ship():
    places = build_places()
    assert new_place_names(
        "A room at The Dhaer's Rest in Veldhaer", ["The Dhaer's Rest"], places, []
    ) == ["The Dhaer's Rest"]
    # known without the article: not new
    known = places + [place_named("Dhaer's Rest")]
    assert new_place_names("At The Dhaer's Rest", [], known, []) == []

    messages = [NarratorMessage(message="They tied up beside the Grey Gull.")]
    [ship] = find(items=["the Grey Gull"], messages=messages)
    assert ship.kind == "thing"
    assert ship.text == "The Grey Gull"
    assert (
        find(
            items=["the Grey Gull"],
            messages=messages,
            glossary=[entry("Grey Gull", "thing")],
        )
        == []
    )
    # a lowercase description after "the" is still not a name
    assert find(items=["the rusty lantern"], messages=messages) == []


def test_reused_spare_takes_its_culture():
    # Veldhaer is Taelrik, and the name fits Taelrik, but it was offered as Elsiri
    [finding] = find(
        characters=["Tovrin"],
        offered_spares={"tovrin": {"culture_id": "elsiri", "generator_id": "given"}},
    )
    assert finding.culture_id == "elsiri"
    assert finding.origin.by == "ai"


def test_place_keys_are_not_persons():
    findings = find(
        characters=["Veldhaer", "The Birch Coast", "Kesterholm", "Tovrin"],
        places_found=[("Kesterholm", "k1")],
    )
    assert [(f.text, f.kind) for f in findings] == [
        ("Tovrin", "person"),
        ("Kesterholm", "place"),
    ]


def test_messy_replies_parse():
    places = build_places()
    cultures = world_cultures()
    current = next(p for p in places if p.id == "veldhaer")
    [place] = parse_places_reply(
        "Sure! Here you go:\n1. **Kesterholm** | Village | The Birch Coast | inherit | Sure.\n",
        ["Kesterholm"],
        places,
        cultures,
        current,
    )
    assert place.kind == "village"
    assert place.parent_id == "birch"
    assert place.unsure is False

    [(culture_id, addition)] = parse_additions_reply(
        "- **Taelrik** | Customs | Ferrymen spit over the rail.\nNONE.",
        [cultures["taelrik"]],
        "s",
    )
    assert culture_id == "taelrik"
    assert addition.section == "customs"
    assert addition.text == "Ferrymen spit over the rail."
    assert parse_additions_reply("NONE.", [cultures["taelrik"]], "s") == []
