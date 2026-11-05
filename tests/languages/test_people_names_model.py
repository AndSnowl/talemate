"""People's names in the language file (languages 4b-2, Task 1): parts
from a connection or the person's own name, forms by who the person is,
the English writing of fixed words, and `people_names` (choices, kept
titles, address)."""

from talemate.languages.changes import merge_change
from talemate.languages.check import check_language
from talemate.languages.completeness import completeness
from talemate.languages.entry import fields_of, language_of
from talemate.languages.models import (
    AddressRow,
    GeneratorDef,
    Language,
    NamePart,
    NameShape,
    PeopleNames,
)
from talemate.world.store import Source

GIVEN = GeneratorDef(
    id="given",
    name="Women's given names",
    use="character",
    patterns=["[maelis|ysolde]"],
)
HOUSES = GeneratorDef(
    id="houses", name="Houses", use="place", patterns=["[drassone|sauvaire]"]
)
NOBLE = GeneratorDef(
    id="noble-women",
    name="Noble women",
    use="character",
    for_person={"sex": "woman", "rank": "noble"},
    shapes=[
        NameShape(
            parts=[
                NamePart(kind="rule", rule="given", label="given"),
                NamePart(kind="word", word="di", english="of", label="of"),
                NamePart(
                    kind="connection",
                    roles=["father", "mother"],
                    take="house",
                    rule="houses",
                    label="house",
                ),
            ]
        )
    ],
)
PEOPLE = PeopleNames(
    choices={"sex": ["man", "woman"], "rank": ["common", "noble"]},
    kept_titles=[{"word": "Tsar", "meaning": "emperor"}],
    address=[
        {"kind": "family", "roles": ["mother", "brother"], "uses": ["pet name"]},
        {"kind": "strangers", "uses": ["title", "house"], "default": True},
    ],
)


def _lang(**changes) -> Language:
    fields = {
        "name": "Drassonais",
        "level": "full",
        "categories": {"C": "d r s", "V": "a e o"},
        "generators": [GIVEN, HOUSES, NOBLE],
    }
    return Language(**{**fields, **changes})


def test_old_language_loads_without_people_names():
    lang = Language.model_validate(
        {
            "name": "Old",
            "level": "naming",
            "generators": [
                {"id": "p", "name": "P", "use": "place", "patterns": ["ka"]}
            ],
        }
    )
    assert lang.people_names is None
    assert lang.generators[0].for_person == {}


def test_people_names_round_trip():
    lang = _lang(people_names=PEOPLE)
    again = Language.model_validate(lang.model_dump())
    assert again.people_names.address[1].default is True
    assert again.people_names.kept_titles[0].word == "Tsar"
    assert again.generators[2].shapes[0].parts[1].english == "of"


def test_people_names_round_trip_through_the_entry(world):
    lang = _lang(people_names=PEOPLE)
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "Drassonais", **fields_of(lang)})
    back = language_of(world.view().thing(lid))
    assert back.people_names == PEOPLE
    noble = next(g for g in back.generators if g.id == "noble-women")
    assert noble.for_person == {"sex": "woman", "rank": "noble"}
    assert noble.shapes[0].parts[2].roles == ["father", "mother"]


def test_connection_part_and_person_forms_validate():
    part = NamePart(
        kind="connection",
        roles=["mother", "father"],
        take="family",
        rule="family",
        person_forms=[
            {"when": {"sex": "woman"}, "changes": [{"kind": "ending", "text": "a"}]}
        ],
    )
    assert part.person_forms[0].when == {"sex": "woman"}
    assert part.person_forms[0].changes[0].text == "a"
    own = NamePart(kind="own", take="given")
    assert own.take == "given"


def test_check_warns_on_a_connection_without_roles_and_an_unknown_choice():
    bad = GeneratorDef(
        id="bad",
        name="Bad",
        use="character",
        for_person={"caste": "x"},
        shapes=[NameShape(parts=[NamePart(kind="connection", rule="given")])],
    )
    report = check_language(_lang(generators=[GIVEN, HOUSES, bad], people_names=PEOPLE))
    assert any("roles" in w for w in report.warnings)
    assert any("caste" in w for w in report.warnings)


def test_check_warns_on_an_own_part_without_take_and_an_unknown_use():
    pets = GeneratorDef(
        id="pets",
        name="Pet names",
        use="pet names",
        shapes=[NameShape(parts=[NamePart(kind="own")])],
    )
    people = PEOPLE.model_copy(
        update={"address": [AddressRow(kind="friends", uses=["nickname-thing"])]}
    )
    report = check_language(
        _lang(generators=[GIVEN, HOUSES, NOBLE, pets], people_names=people)
    )
    assert any("take" in w for w in report.warnings)
    assert any("nickname-thing" in w for w in report.warnings)


def test_merge_keeps_the_owners_people_names_edit():
    base = _lang(people_names=PEOPLE)
    current = _lang(
        people_names=PEOPLE.model_copy(update={"kept_titles": []}),
    )
    merged = merge_change(base, _lang(people_names=PEOPLE), current)
    assert merged.language.people_names.kept_titles == []


def test_completeness_counts_people_names():
    assert completeness(_lang()).people_names_missing is True
    assert completeness(_lang(people_names=PEOPLE)).people_names_missing is False
