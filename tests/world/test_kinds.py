import pytest

from talemate.world.kinds import HERITAGE_KINDS, KINDS, get_kind, validate_field
from talemate.world.refs import parse_refs, ref

_HERITAGE_CATEGORIES = ["origin", "physical", "instinct", "variation", "general"]


def test_kinds_table():
    character = get_kind("character")
    assert [f.name for f in character.fields] == [
        "name",
        "born",
        "culture",
        "voice",
        "color",
        "heritage",
        "ties",
        "aka",
        "stub",
        "part_of",
    ]
    assert [f.type for f in character.fields] == [
        "text",
        "date",
        "thing",
        "json",
        "text",
        "thing",
        "json",
        "json",
        "json",
        "json",
    ]
    assert character.categories == [
        "appearance",
        "personality",
        "background",
        "ability",
        "relationship",
        "speech",
        "ties",
    ]

    with pytest.raises(KeyError):
        get_kind("magic")


def test_every_kind_has_aka_and_stub():
    for kind in KINDS.values():
        types = {f.name: f.type for f in kind.fields}
        assert types["aka"] == "json", kind.name
        assert types["stub"] == "json", kind.name
        assert types["part_of"] == "json", kind.name


def test_aka_shape_validated():
    place = get_kind("place")
    validate_field(place, "aka", [])
    validate_field(
        place,
        "aka",
        [
            {"name": "Moscavia", "tag": "common", "everyday": True},
            {"name": "the Tsardom", "tag": "common", "everyday": False},
            {"name": "Grand Tsardom", "tag": "proper", "everyday": False},
        ],
    )

    bad = [
        # two everyday names
        [
            {"name": "Moscavia", "tag": "common", "everyday": True},
            {"name": "the Tsardom", "tag": "common", "everyday": True},
        ],
        # an everyday name must be common
        [{"name": "Grand Tsardom", "tag": "proper", "everyday": True}],
        # unknown tag
        [{"name": "Moscavia", "tag": "nickname", "everyday": False}],
        # not a list, missing keys, wrong types, extra keys, blank name
        {"name": "Moscavia", "tag": "common", "everyday": False},
        [{"name": "Moscavia", "tag": "common"}],
        [{"name": "Moscavia", "tag": "common", "everyday": "yes"}],
        [{"name": 3, "tag": "common", "everyday": False}],
        [{"name": "Moscavia", "tag": "common", "everyday": False, "x": 1}],
        [{"name": "  ", "tag": "common", "everyday": False}],
        ["Moscavia"],
    ]
    for value in bad:
        with pytest.raises(ValueError):
            validate_field(place, "aka", value)


def test_stub_shape_validated():
    lore = get_kind("lore")
    validate_field(lore, "stub", {"ignored": False})
    validate_field(lore, "stub", {"ignored": True})
    for value in (True, {}, {"ignored": 1}, {"ignored": False, "x": 1}, None):
        with pytest.raises(ValueError):
            validate_field(lore, "stub", value)


def test_parse_refs_dedupes_in_order():
    a = "11111111111111111111111111111111"
    b = "22222222222222222222222222222222"
    text = f"{ref(a)} met {ref(b)} again, then {ref(a)} left."
    assert parse_refs(text) == [a, b]


def test_species_race_mix_kinds():
    assert HERITAGE_KINDS == ("species", "race", "mix")

    species = get_kind("species")
    assert [f.name for f in species.fields] == [
        "name",
        "origin",
        "lifespan",
        "adult_age",
        "measures",
        "aka",
        "stub",
        "part_of",
    ]
    assert [f.type for f in species.fields] == [
        "text",
        "thing",
        "number",
        "number",
        "json",
        "json",
        "json",
        "json",
    ]
    assert species.categories == _HERITAGE_CATEGORIES

    race = get_kind("race")
    assert [f.name for f in race.fields] == [
        "name",
        "species",
        "lifespan",
        "adult_age",
        "measures",
        "aka",
        "stub",
        "part_of",
    ]
    assert [f.type for f in race.fields] == [
        "text",
        "thing",
        "number",
        "number",
        "json",
        "json",
        "json",
        "json",
    ]
    assert race.categories == _HERITAGE_CATEGORIES

    mix = get_kind("mix")
    assert [f.name for f in mix.fields] == [
        "name",
        "parents",
        "lifespan",
        "adult_age",
        "measures",
        "aka",
        "stub",
        "part_of",
    ]
    assert [f.type for f in mix.fields] == [
        "text",
        "things",
        "number",
        "number",
        "json",
        "json",
        "json",
        "json",
    ]
    assert mix.categories == _HERITAGE_CATEGORIES


def test_number_field_rejects_bool_and_negative():
    species = get_kind("species")
    validate_field(species, "lifespan", 400)
    validate_field(species, "lifespan", 400.5)

    with pytest.raises(ValueError):
        validate_field(species, "lifespan", True)
    with pytest.raises(ValueError):
        validate_field(species, "lifespan", -1)


def test_parents_needs_two_distinct():
    mix = get_kind("mix")
    a = "11111111111111111111111111111111"
    b = "22222222222222222222222222222222"
    c = "33333333333333333333333333333333"

    validate_field(mix, "parents", [a, b])

    with pytest.raises(ValueError):
        validate_field(mix, "parents", [a])
    with pytest.raises(ValueError):
        validate_field(mix, "parents", [a, b, c])
    with pytest.raises(ValueError):
        validate_field(mix, "parents", [a, a])


def test_measures_shape():
    species = get_kind("species")
    validate_field(
        species,
        "measures",
        [{"name": "height", "min": 1.5, "max": 2.1, "unit": "m"}],
    )

    with pytest.raises(ValueError):
        validate_field(
            species,
            "measures",
            [{"name": "height", "min": 1.5, "unit": "m"}],
        )


def test_drawer_type_constants():
    """One set of drawer-type constants, mirrored in the frontend's
    worldKinds.js (pinned there by checks/worlds.check.mjs)."""

    from talemate.world.kinds import (
        DRAWER_TYPES,
        ENTRY_DRAWER_TYPES,
        PART_OF_KINDS,
        WRITTEN_DRAWER_TYPES,
    )

    assert WRITTEN_DRAWER_TYPES == (
        "places",
        "practices",
        "beliefs",
        "knowledge",
        "structure",
    )
    entries = ("practices", "beliefs", "knowledge", "structure")
    assert ENTRY_DRAWER_TYPES == {
        "lore": entries,
        "place": ("places",),
        "item": entries,
        "event": entries,
        "sphere": entries,
        "being": ("beliefs", "practices", "structure"),
    }
    assert PART_OF_KINDS == ("lore", "place", "item", "event", "sphere", "being")
    assert set(WRITTEN_DRAWER_TYPES) < set(DRAWER_TYPES)


def test_agent_is_unrendered():
    """A sphere's agent flag is no input to its prose (ruling P21)."""

    from talemate.world.prose import UNRENDERED_FIELDS

    assert "agent" in UNRENDERED_FIELDS
