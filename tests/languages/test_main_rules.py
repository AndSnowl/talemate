"""Main rules and pieces (languages 4c, Task 1): a rule other rules use as
a part, an ordinary-words rule or a pet-name rule is a piece unless the
file says otherwise; main rules carry a one-line description, and the
rule list puts them first."""

from talemate.languages.models import GeneratorDef, Language, NamePart, NameShape
from talemate.languages.naming_panel import rules_of
from talemate.languages.person_names import is_main


def _zhelvan() -> Language:
    return Language(
        name="Zhelvan",
        level="full",
        categories={"C": "zh v k", "V": "a o"},
        generators=[
            GeneratorDef(
                id="given",
                name="Given names",
                use="character",
                patterns=["[zakan|vekhal]"],
            ),
            GeneratorDef(
                id="men",
                name="Men's names",
                use="character",
                description="ordinary men of the towns",
                shapes=[
                    NameShape(
                        parts=[NamePart(kind="rule", rule="given", label="given")]
                    )
                ],
            ),
            GeneratorDef(id="words", name="Words", use="words", patterns=["CVC"]),
            GeneratorDef(
                id="pet",
                name="Pet names",
                use="pet names",
                shapes=[NameShape(parts=[NamePart(kind="own", take="given")])],
            ),
            GeneratorDef(id="places", name="Places", use="place", patterns=["CVCsk"]),
        ],
    )


def test_a_building_block_is_a_piece_and_can_be_overridden():
    lang = _zhelvan()
    assert [is_main(lang, g) for g in lang.generators] == [
        False,
        True,
        False,
        False,
        True,
    ]
    lang.generators[0].main = True
    assert is_main(lang, lang.generators[0]) is True
    lang.generators[4].main = False
    assert is_main(lang, lang.generators[4]) is False


def test_rules_of_puts_main_rules_first_with_descriptions():
    infos = rules_of(_zhelvan())
    assert [i.id for i in infos] == ["men", "places", "given", "words", "pet"]
    assert [i.main for i in infos] == [True, True, False, False, False]
    assert infos[0].description == "ordinary men of the towns"


def test_rules_of_never_leaves_people_without_a_main_rule():
    only_pieces = _zhelvan()
    for g in only_pieces.generators:
        g.main = False
    infos = rules_of(only_pieces)
    assert len(infos) == 5
    assert any(i.use in ("character", "people") for i in infos)


def test_main_and_description_round_trip():
    lang = _zhelvan()
    lang.generators[0].main = True
    again = Language.model_validate(lang.model_dump())
    assert again.generators[0].main is True
    assert again.generators[1].description == "ordinary men of the towns"
    assert (
        Language.model_validate(
            {
                "name": "Old",
                "level": "naming",
                "generators": [
                    {"id": "p", "name": "P", "use": "place", "patterns": ["ka"]}
                ],
            }
        )
        .generators[0]
        .main
        is None
    )


def test_check_warns_on_a_long_description():
    from talemate.languages.check import check_language

    lang = _zhelvan()
    lang.generators[1].description = "x" * 130
    assert any("description" in w for w in check_language(lang).warnings)
