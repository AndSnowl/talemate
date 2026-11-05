"""Shared people's-names languages for the 4b-2 tests: a Drassonais-like
language (noble and common women's rules, a house from the father, "di"
written "of", a pet-name rule, choices, kept titles, address rows) and a
Varovni-like one (a family name with a woman's form)."""

from talemate.languages.models import (
    GeneratorDef,
    Language,
    NamePart,
    NameShape,
    PeopleNames,
)

EILHAUD = "e" * 32


def _rule(id_, use, patterns):
    return GeneratorDef(id=id_, name=id_, use=use, patterns=patterns)


HOUSE_PART = NamePart(
    kind="connection",
    roles=["father", "mother"],
    take="house",
    rule="houses",
    label="house",
)
OF = NamePart(kind="word", word="di", english="of", label="of")


def _composed(id_, for_person, parts):
    return GeneratorDef(
        id=id_,
        name=id_,
        use="character",
        for_person=for_person,
        shapes=[NameShape(parts=parts)],
    )


DRASSONAIS = Language(
    name="Drassonais",
    level="full",
    categories={"C": "d r s l", "V": "a e o i"},
    generators=[
        _rule("women-given", "people", ["[maelis|ysolde|aurande]"]),
        _rule("men-given", "people", ["[eilhaud|tiboud|gaspard]"]),
        _rule("houses", "place", ["[sauvaire|morlaix|vesonne]"]),
        _composed(
            "noble-women",
            {"sex": "woman", "rank": "noble"},
            [NamePart(kind="rule", rule="women-given", label="given"), OF, HOUSE_PART],
        ),
        _composed(
            "noble-men",
            {"sex": "man", "rank": "noble"},
            [NamePart(kind="rule", rule="men-given", label="given"), OF, HOUSE_PART],
        ),
        _composed(
            "common-women",
            {"sex": "woman", "rank": "common"},
            [
                NamePart(kind="rule", rule="women-given", label="given"),
                NamePart(
                    kind="word",
                    word="filha",
                    english="daughter of",
                    label="daughter of",
                ),
                NamePart(
                    kind="connection",
                    roles=["father"],
                    take="given",
                    rule="men-given",
                    label="father",
                ),
            ],
        ),
        GeneratorDef(
            id="pets",
            name="Pet names",
            use="pet names",
            shapes=[
                NameShape(
                    parts=[
                        NamePart(
                            kind="own",
                            take="given",
                            person_forms=[
                                {"changes": [{"kind": "ending", "text": "ette"}]}
                            ],
                        )
                    ]
                )
            ],
        ),
    ],
    people_names=PeopleNames(
        choices={"sex": ["man", "woman"], "rank": ["common", "noble"]},
        kept_titles=[{"word": "Tsar", "meaning": "emperor"}],
        address=[
            {"kind": "family", "roles": ["mother", "brother"], "uses": ["pet name"]},
            {"kind": "strangers", "uses": ["title", "house"], "default": True},
        ],
    ),
)

VAROVNI = Language(
    name="Varovni",
    level="full",
    categories={"C": "k v s", "V": "a o e"},
    generators=[
        _rule("men", "people", ["[dorvak|zemol]"]),
        _rule("women", "people", ["[zvesta|mira]"]),
        _rule("family", "people", ["[brovsk|zelovsk]"]),
        _composed(
            "people",
            {},
            [
                NamePart(kind="rule", rule="women", label="given"),
                NamePart(
                    kind="connection",
                    roles=["mother", "father"],
                    take="family",
                    rule="family",
                    label="family",
                    person_forms=[
                        {
                            "when": {"sex": "woman"},
                            "changes": [{"kind": "ending", "text": "a"}],
                        }
                    ],
                ),
            ],
        ),
    ],
)
