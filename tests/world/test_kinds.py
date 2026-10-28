import pytest

from talemate.world.dates import WorldDate

from talemate.world.kinds import (
    HERITAGE_KINDS,
    KIND_ORDER,
    KINDS,
    get_kind,
    validate_field,
)
from talemate.world.refs import parse_refs, ref

_HERITAGE_CATEGORIES = ["origin", "physical", "instinct", "variation", "general"]


def test_kinds_table():
    character = get_kind("character")
    assert [f.name for f in character.fields] == [
        "name",
        "born",
        "voice",
        "color",
        "heritage",
        "aka",
        "stub",
        "tag",
        "filings",
        "hint",
        "agent",
        "languages",
    ]
    assert [f.type for f in character.fields] == [
        "text",
        "date",
        "json",
        "text",
        "thing",
        "json",
        "json",
        "text",
        "json",
        "text",
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
        assert types["agent"] == "json", kind.name
        assert types["tag"] == "text", kind.name
        assert types["filings"] == "json", kind.name
        assert types["hint"] == "text", kind.name


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
        "tag",
        "filings",
        "hint",
        "agent",
        "languages",
    ]
    assert [f.type for f in species.fields] == [
        "text",
        "thing",
        "number",
        "number",
        "json",
        "json",
        "json",
        "text",
        "json",
        "text",
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
        "tag",
        "filings",
        "hint",
        "agent",
        "languages",
    ]
    assert [f.type for f in race.fields] == [
        "text",
        "thing",
        "number",
        "number",
        "json",
        "json",
        "json",
        "text",
        "json",
        "text",
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
        "tag",
        "filings",
        "hint",
        "agent",
        "languages",
    ]
    assert [f.type for f in mix.fields] == [
        "text",
        "things",
        "number",
        "number",
        "json",
        "json",
        "json",
        "text",
        "json",
        "text",
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


def test_agent_is_unrendered():
    """An entry's agent flag is no input to its prose (ruling P21)."""

    from talemate.world.prose import UNRENDERED_FIELDS

    assert "agent" in UNRENDERED_FIELDS


def test_agent_is_a_bool_field_on_every_kind():
    """`agent` is a plain field any entry can have (Filing): a bool."""

    for kind in KINDS.values():
        validate_field(kind, "agent", True)
        validate_field(kind, "agent", False)
        with pytest.raises(ValueError):
            validate_field(kind, "agent", "true")
        with pytest.raises(ValueError):
            validate_field(kind, "agent", 1)


def test_the_old_structure_is_gone():
    """No sphere or culture kind, and none of the fields filing replaced.
    The old single `language` field is gone too; the `language` kind and
    the plural `languages` field (languages 3a) are new."""

    assert "sphere" not in KINDS
    assert "culture" not in KINDS
    gone = {"part_of", "ties", "parent", "cultures", "culture", "language"}
    gone |= {"template", "drawers", "owner", "place", "drops"}
    for kind in KINDS.values():
        assert not gone & {f.name for f in kind.fields}, kind.name
    # the tag says what a place is: no `kind` text field of its own
    assert "kind" not in {f.name for f in get_kind("place").fields}


def test_language_kind_fields():
    names = {f.name for f in get_kind("language").fields}
    assert {
        "depth",
        "flavour",
        "sound",
        "rules",
        "words",
        "phrases",
        "descends_from",
        "similar",
        "languages",
    } <= names
    assert "language" in KIND_ORDER


def test_every_kind_has_languages_field():
    for kind in KINDS.values():
        assert "languages" in {f.name for f in kind.fields}, kind.name


def test_languages_field_validates_rows():
    k = get_kind("place")
    validate_field(
        k,
        "languages",
        [
            {"language": "a" * 32, "role": "spoken", "share": 70},
            {"language": "b" * 32, "role": "official", "since": WorldDate.of(1412)},
        ],
    )
    for bad in (
        [{"language": "x", "role": "spoken"}],
        [{"language": "a" * 32, "role": "official", "share": 50}],
        [{"language": "a" * 32, "role": "sung"}],
        [{"language": "a" * 32, "role": "spoken", "share": 120}],
        [{"language": "a" * 32, "role": "spoken", "fluency": "perfect"}],
        [
            {"language": "a" * 32, "role": "spoken"},
            {"language": "a" * 32, "role": "spoken"},
        ],
    ):
        with pytest.raises(ValueError):
            validate_field(k, "languages", bad)


def test_rules_field_rejects_bad_pattern():
    with pytest.raises(ValueError):
        validate_field(
            get_kind("language"),
            "rules",
            {
                "categories": {"C": "k"},
                "generators": [
                    {
                        "id": "g",
                        "name": "g",
                        "use": "words",
                        "patterns": ["CV"],
                        "reject": ["("],
                    }
                ],
            },
        )


def test_words_phrases_similar_and_depth_validate():
    k = get_kind("language")
    validate_field(k, "words", [{"word": "vel", "meaning": "great"}])
    validate_field(
        k,
        "phrases",
        [
            {
                "id": "p1",
                "category": "curse",
                "original": "Vel!",
                "translation": "Great!",
            }
        ],
    )
    validate_field(k, "similar", [{"target": "a" * 32, "degree": "close"}])
    for field, bad in (
        ("words", [{"word": "", "meaning": "x"}]),
        (
            "phrases",
            [{"id": "p1", "category": "", "original": "x", "translation": "y"}],
        ),
        ("similar", [{"target": "a" * 32, "degree": "kinda"}]),
        ("depth", "deep"),
    ):
        with pytest.raises(ValueError):
            validate_field(k, field, bad)


def test_languages_rows_store_dates_as_plain_data():
    from talemate.world.kinds import normalise_field

    rows = normalise_field(
        "languages",
        [{"language": "a" * 32, "role": "official", "since": WorldDate.of(1412)}],
    )
    assert rows[0]["since"] == WorldDate.of(1412).model_dump(mode="json")
