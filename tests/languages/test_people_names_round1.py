"""Owner's first round on 4b-2 (2026-11-05): a typed meaning keeps the
part's own ending, every new word in a phrase rerolls, and an ending on an
own (or rule) part is applied (Zhelvan's pet names)."""

import random

import pytest

from talemate.languages.models import (
    DictionaryEntry,
    Ending,
    GeneratorDef,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)
from talemate.languages.name_grammar import MeaningPhrase
from talemate.languages.naming_meaning import _phrase_rolls, part_meaning
from talemate.languages.person_names import roll_pet_name
from talemate.languages.entry import fields_of
from talemate.world.store import Source

ZHELVAN = Language(
    name="Zhelvan",
    level="full",
    categories={"C": "zh v s k r", "V": "a o e"},
    generators=[
        GeneratorDef(id="words", name="Words", use="words", patterns=["CVC"]),
        GeneratorDef(
            id="places-of",
            name="Places named for a thing",
            use="place",
            shapes=[NameShape(parts=[NamePart(kind="meaning", ending="town of")])],
        ),
        GeneratorDef(
            id="pet",
            name="Pet names",
            use="pet names",
            shapes=[
                NameShape(
                    parts=[
                        NamePart(
                            kind="own",
                            take="given",
                            ending="small, dear",
                            label="pet name",
                        )
                    ]
                )
            ],
        ),
    ],
    dictionary=[DictionaryEntry(word="zhves", meanings=["iron"], part="noun")],
    name_grammar=NameGrammar(
        of=OfRule(text="dov"),
        endings=[
            Ending(ending="sk", meaning="town of"),
            Ending(ending="ka", meaning="small, dear"),
        ],
    ),
)


@pytest.mark.parametrize("typed", ["town of iron", "iron town", "iron"])
async def test_a_typed_meaning_keeps_the_parts_ending(world, typed):
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "Zhelvan", **fields_of(ZHELVAN)})
    found = await part_meaning(world.view(), None, lid, "places-of", 0, 0, typed)
    assert found["rolls"][0]["text"] == "Zhvessk"


def test_every_new_word_in_a_phrase_rerolls():
    phrase = MeaningPhrase(noun="palace", describing=["grand"])
    words = {"grand": "lyodvas", "palace": "dyolyuch"}
    options = {
        "lyodvas": ["lyodvas", "akakh", "rone"],
        "dyolyuch": ["dyolyuch", "zhavor", "kesk"],
    }
    rolls = _phrase_rolls(ZHELVAN, phrase, words, {"lyodvas", "dyolyuch"}, options)
    seconds = {r.text.split()[-1] for r in rolls}
    firsts = {r.text.split()[0] for r in rolls}
    assert len(seconds) > 1 and len(firsts) > 1


def test_an_ending_on_an_own_part_makes_the_pet_name():
    assert roll_pet_name(ZHELVAN, {"given": "Mira"}, random.Random(1)) == (
        "Miraka",
        "pet",
    )


def test_an_ending_on_a_rule_part_is_applied_to_its_rolls():
    from talemate.languages.composed import roll_parts

    lang = ZHELVAN.model_copy(
        update={
            "generators": [
                *ZHELVAN.generators,
                GeneratorDef(
                    id="given", name="Given", use="people", patterns=["[mira]"]
                ),
                GeneratorDef(
                    id="little",
                    name="Little ones",
                    use="character",
                    shapes=[
                        NameShape(
                            parts=[
                                NamePart(
                                    kind="rule", rule="given", ending="small, dear"
                                )
                            ]
                        )
                    ],
                ),
            ]
        }
    )
    _, parts = roll_parts(lang, "little", rng=random.Random(1))
    assert parts[0].rolls[0].text == "Miraka"
