import pytest

from talemate.world.kinds import HERITAGE_KINDS, get_kind, validate_field
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
    ]
    assert [f.type for f in character.fields] == [
        "text",
        "date",
        "thing",
        "json",
        "text",
        "thing",
    ]
    assert character.categories == [
        "appearance",
        "personality",
        "background",
        "ability",
        "relationship",
        "speech",
    ]

    with pytest.raises(KeyError):
        get_kind("magic")


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
    ]
    assert [f.type for f in species.fields] == [
        "text",
        "thing",
        "number",
        "number",
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
    ]
    assert [f.type for f in race.fields] == [
        "text",
        "thing",
        "number",
        "number",
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
    ]
    assert [f.type for f in mix.fields] == [
        "text",
        "things",
        "number",
        "number",
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
