"""The person-name engine (languages 4b-2, Task 2): parts inherited from
real connections, forms by sex and rank, the rule picked for who the
person is, missing parents offered with a full name, pet names, address
rows and kept titles. No model anywhere."""

import random

from talemate.languages.composed import roll_parts
from _people_names_helpers import DRASSONAIS, EILHAUD, VAROVNI, _composed, _rule
from talemate.languages.models import Language, NamePart
from talemate.languages.person_names import (
    Connection,
    PersonContext,
    address_row,
    build_person_name,
    choose,
    connections_of,
    kept_title,
    parent_for,
    pick_rule,
    roll_pet_name,
)
from talemate.world.store import Source


def _ctx(sex="woman", rank="noble", parent_parts=None, connections=None):
    if connections is None:
        connections = []
        if parent_parts is not None:
            connections = [
                Connection(
                    role="daughter of",
                    thing_id=EILHAUD,
                    name=" ".join(parent_parts.values()),
                    parts=parent_parts,
                    built_as={"sex": "man"},
                )
            ]
    return PersonContext(
        thing_id=None, built_as={"sex": sex, "rank": rank}, connections=connections
    )


def test_inherited_part_comes_from_the_real_parent():
    ctx = _ctx(
        connections=[
            Connection(
                role="daughter of",
                thing_id=EILHAUD,
                name="Eilhaud of Drassone",
                parts={"given": "Eilhaud", "house": "Drassone"},
                built_as={"sex": "man"},
            )
        ]
    )
    named = build_person_name(DRASSONAIS, ctx, rng=random.Random(1))
    assert named.rule_id == "noble-women"
    assert named.parts[2].text == "Drassone" and named.parts[2].source == "inherited"
    assert named.parts[2].from_id == EILHAUD
    assert named.name.endswith(" of Drassone")
    assert named.missing == []


def test_a_parent_without_parts_gives_its_last_word():
    ctx = _ctx(
        connections=[
            Connection(role="daughter of", thing_id=EILHAUD, name="Eilhaud of Drassone")
        ]
    )
    named = build_person_name(DRASSONAIS, ctx, rng=random.Random(1))
    assert named.parts[2].text == "Drassone"


def test_woman_form_applies_to_the_inherited_family_part():
    named = build_person_name(
        VAROVNI,
        _ctx(sex="woman", parent_parts={"given": "Dorvak", "family": "Kesterovsk"}),
        rule_id="people",
        rng=random.Random(1),
    )
    assert named.parts[1].text == "Kesterovska"
    assert "Kesterovska" in named.name


def test_rank_picks_the_rule():
    assert (
        pick_rule(DRASSONAIS, {"sex": "woman", "rank": "common"}).id == "common-women"
    )
    assert pick_rule(DRASSONAIS, {"sex": "woman", "rank": "noble"}).id == "noble-women"
    assert pick_rule(DRASSONAIS, {"sex": "man", "rank": "noble"}).id == "noble-men"


def test_mother_then_father_by_role_words_then_built_as_then_first():
    mother = Connection(
        role="child of", thing_id="m" * 32, name="Aurande", built_as={"sex": "woman"}
    )
    father = Connection(
        role="child of", thing_id="f" * 32, name="Eilhaud", built_as={"sex": "man"}
    )
    part = NamePart(kind="connection", roles=["mother", "father"])
    assert parent_for(part, _ctx(connections=[father, mother])).name == "Aurande"
    worded = Connection(role="Her father, Gaspard", thing_id="g" * 32, name="Gaspard")
    assert parent_for(part, _ctx(connections=[mother, worded])).name == "Aurande"
    assert (
        parent_for(
            NamePart(kind="connection", roles=["father"]),
            _ctx(connections=[mother, worded]),
        ).name
        == "Gaspard"
    )
    plain = Connection(role="child of", thing_id="x" * 32, name="Someone")
    assert parent_for(part, _ctx(connections=[plain])).name == "Someone"
    lord = NamePart(kind="connection", roles=["lord"])
    assert parent_for(lord, _ctx(connections=[plain])) is None


def test_missing_parent_is_rolled_and_offered_as_a_full_name():
    named = build_person_name(DRASSONAIS, _ctx(), rng=random.Random(2))
    assert named.parts[2].source == "rolled"
    assert named.missing and named.missing[0].role == "father"
    assert named.missing[0].sex == "man"
    assert named.missing[0].text == named.parts[2].text
    assert named.missing[0].name.endswith(f"of {named.parts[2].text}")


def test_a_bad_parent_falls_back_to_a_roll(world):
    with world.revision(Source.manual()) as rev:
        me = rev.create_thing("character", {"name": "Maëlis"})
        gone = rev.create_thing("character", {"name": "Gone"})
        stub = rev.create_thing(
            "character", {"name": "Old Eilhaud", "stub": {"ignored": False}}
        )
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(gone)
    view = world.view()
    conns = connections_of(
        view,
        me,
        [(me, "daughter of"), (gone, "daughter of"), (stub, "daughter of")],
        [],
    )
    assert [c.thing_id for c in conns] == [stub]
    conns = connections_of(view, me, [(me, "daughter of"), (gone, "daughter of")], [])
    named = build_person_name(
        DRASSONAIS,
        PersonContext(
            thing_id=me, built_as={"sex": "woman", "rank": "noble"}, connections=conns
        ),
        rng=random.Random(3),
    )
    assert named.parts[2].source == "rolled"


def test_connections_read_relationship_facts_and_parts(world):
    with world.revision(Source.manual()) as rev:
        father = rev.create_thing(
            "character",
            {
                "name": "Eilhaud of Drassone",
                "name_parts": {
                    "language": "a" * 32,
                    "rule": "noble-men",
                    "shape": 0,
                    "built_as": {"sex": "man", "rank": "noble"},
                    "parts": [
                        {"label": "given", "text": "Eilhaud", "source": "rolled"},
                        {"label": "of", "text": "di", "source": "word"},
                        {"label": "house", "text": "Drassone", "source": "typed"},
                    ],
                },
            },
        )
    conns = connections_of(
        world.view(), None, [], [("Daughter of Eilhaud, her father", [father])]
    )
    assert conns[0].role == "Daughter of Eilhaud, her father"
    assert conns[0].parts["house"] == "Drassone"
    assert conns[0].built_as == {"sex": "man", "rank": "noble"}


def test_unknown_choices_fall_back_to_the_first():
    assert choose(DRASSONAIS, {"sex": "female", "rank": "duke"}) == {
        "sex": "man",
        "rank": "common",
    }
    assert choose(DRASSONAIS, {"sex": "Woman", "rank": "noble"}) == {
        "sex": "woman",
        "rank": "noble",
    }
    assert choose(VAROVNI, {"sex": "woman"}) == {"sex": "woman"}


def test_pet_name_address_and_kept_title():
    pet = roll_pet_name(DRASSONAIS, {"given": "Maëlis"}, random.Random(1))
    assert pet == ("Maëlisette", "pets")
    assert roll_pet_name(VAROVNI, {"given": "Mira"}, random.Random(1)) is None
    assert address_row(DRASSONAIS, "her mother").kind == "family"
    assert address_row(DRASSONAIS, "a passing guard").kind == "strangers"
    assert address_row(VAROVNI, "her mother") is None
    assert kept_title(DRASSONAIS, "Emperor").word == "Tsar"
    assert kept_title(DRASSONAIS, "King") is None


def test_a_meaning_fills_the_first_meaning_part():
    lang = Language.model_validate(
        {
            **DRASSONAIS.model_dump(),
            "dictionary": [{"word": "sol", "meanings": ["sun"], "part": "noun"}],
            "generators": [
                *DRASSONAIS.generators,
                _composed(
                    "sun-names",
                    {"sex": "man", "rank": "common"},
                    [
                        NamePart(kind="rule", rule="men-given", label="given"),
                        NamePart(kind="meaning", label="owl-name"),
                    ],
                ),
            ],
        }
    )
    named = build_person_name(
        lang,
        _ctx(sex="man", rank="common"),
        rule_id="sun-names",
        meaning="sun",
        rng=random.Random(1),
    )
    assert named.parts[1].text == "Sol" and named.parts[1].source == "meaning"


def test_old_rules_roll_as_before():
    a = roll_parts(VAROVNI, "people", rng=random.Random(5))
    b = roll_parts(VAROVNI, "people", rng=random.Random(5), person=None)
    assert a == b
