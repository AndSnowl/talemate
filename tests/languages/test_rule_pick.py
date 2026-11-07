"""Picking a person's rule (languages 4c, Task 4): the model picks one of
the language's main people rules from their descriptions; a bad answer
falls back to today's matching on sex and rank."""

from talemate.languages.models import (
    GeneratorDef,
    Language,
    NamePart,
    NameShape,
    PeopleNames,
)
from talemate.languages.person_names import choose, pick_rule
from talemate.languages.rule_pick import pick_person_rule, pick_prompt_rules

LANG = Language(
    name="Zhelvan",
    level="full",
    categories={"C": "zh v k", "V": "a o"},
    generators=[
        GeneratorDef(
            id="given", name="Given names", use="character", patterns=["[zakan|vekhal]"]
        ),
        GeneratorDef(
            id="men",
            name="Men's names",
            use="character",
            for_person={"sex": "man"},
            description="ordinary Zhelvan men",
            shapes=[
                NameShape(parts=[NamePart(kind="rule", rule="given", label="given")])
            ],
        ),
        GeneratorDef(
            id="sovereign",
            name="The sovereign",
            use="character",
            for_person={"sex": "man", "rank": "sovereign"},
            description="the tsar and his heirs",
            shapes=[
                NameShape(
                    parts=[
                        NamePart(kind="word", word="Gosmar", label="title"),
                        NamePart(kind="rule", rule="given", label="given"),
                    ]
                )
            ],
        ),
    ],
    people_names=PeopleNames(
        choices={"sex": ["man", "woman"], "rank": ["common", "noble", "sovereign"]}
    ),
)


async def test_the_model_picks_a_main_rule_with_built_as():
    pick = await pick_person_rule(
        None,
        LANG,
        "the tsar's youngest son",
        reply='{"rule": "sovereign", "sex": "man", "rank": "sovereign"}',
    )
    assert (pick.rule_id, pick.built_as["sex"], pick.fallback) == (
        "sovereign",
        "man",
        False,
    )
    assert pick.why == "the tsar and his heirs"


async def test_a_rule_given_by_name_counts():
    pick = await pick_person_rule(
        None,
        LANG,
        "a smith",
        reply='{"rule": "Men\'s names — ordinary Zhelvan men", "sex": "man"}',
    )
    assert pick.rule_id == "men" and pick.fallback is False


async def test_a_bad_pick_falls_back_to_matching():
    for reply in (
        '{"rule": "nobody", "sex": "man"}',
        '{"rule": "given", "sex": "man"}',
        "no json",
    ):
        pick = await pick_person_rule(None, LANG, "a smith", reply=reply)
        assert pick.fallback is True
        assert pick.rule_id == pick_rule(LANG, pick.built_as).id


async def test_a_reply_without_its_opening_brace_is_read():
    pick = await pick_person_rule(
        None, LANG, "the heir", reply=' "rule": "sovereign", "sex": "man"}'
    )
    assert pick.rule_id == "sovereign"


def test_the_prompt_lists_main_people_rules_with_descriptions():
    lines = pick_prompt_rules(LANG)
    assert lines == [
        "men: Men's names — ordinary Zhelvan men [for: man]",
        "sovereign: The sovereign — the tsar and his heirs [for: man, sovereign]",
    ]
