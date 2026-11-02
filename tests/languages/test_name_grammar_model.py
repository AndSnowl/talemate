"""Grammar for names and composed rules in the language file (languages
4b-1, Task 1)."""

import pytest

from talemate.languages.changes import merge_change
from talemate.languages.check import check_language
from talemate.languages.completeness import completeness
from talemate.languages.entry import fields_of, language_of
from talemate.languages.models import (
    FormChange,
    GeneratorDef,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)
from talemate.languages.name_grammar import parse_condition
from talemate.world.store import Source

VOWELS = frozenset("aeiou")

OWL = GeneratorDef(
    id="owl",
    name="Owl-names",
    use="character",
    patterns=[],
    shapes=[
        NameShape(
            parts=[
                NamePart(kind="rule", rule="men"),
                NamePart(kind="word", word="Ul"),
                NamePart(kind="meaning", forms=["more_than_one"]),
            ]
        )
    ],
)
MEN = GeneratorDef(
    id="men", name="Men's names", use="character", patterns=["[dorvak|zemol]"]
)
GRAMMAR = NameGrammar(
    of=OfRule(text="dez"),
    the=[
        FormChange(when="after_vowel", kind="ending", text="k"),
        FormChange(kind="ending", text="ek"),
    ],
)


def _varovni(**changes) -> Language:
    fields = {
        "name": "Varovni",
        "level": "full",
        "categories": {"C": "k v", "V": "a o"},
        "generators": [MEN, OWL],
        "name_grammar": GRAMMAR,
    }
    return Language(**{**fields, **changes})


def test_a_language_round_trips_name_grammar_and_shapes(world):
    lang = _varovni()
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "Varovni", **fields_of(lang)})
    back = language_of(world.view().thing(lid))
    assert back.name_grammar == GRAMMAR
    owl = next(g for g in back.generators if g.id == "owl")
    assert [p.kind for p in owl.shapes[0].parts] == ["rule", "word", "meaning"]
    assert owl.shapes[0].parts[2].forms == ["more_than_one"]


def test_an_old_language_loads_without_them():
    lang = Language.model_validate(
        {
            "name": "Old",
            "level": "naming",
            "generators": [
                {"id": "p", "name": "P", "use": "place", "patterns": ["ka"]}
            ],
        }
    )
    assert lang.name_grammar is None
    assert lang.generators[0].shapes == []


def test_conditions_parse():
    assert parse_condition("after_vowel")("zvesta", VOWELS) is True
    assert parse_condition("after_consonant")("zvesta", VOWELS) is False
    assert parse_condition("before_vowel")("auvre", VOWELS) is True
    assert parse_condition("ends:a|o")("dervo", VOWELS) is True
    assert parse_condition("ends:a|o")("korsh", VOWELS) is False
    assert parse_condition("")("anything", VOWELS) is True
    with pytest.raises(ValueError, match="unknown condition"):
        parse_condition("sideways")


def test_check_reports_a_part_naming_no_rule():
    owl = OWL.model_copy(
        update={"shapes": [NameShape(parts=[NamePart(kind="rule", rule="nobody")])]}
    )
    report = check_language(_varovni(generators=[MEN, owl]))
    assert any("nobody" in problem for problem in report.blocking)


def test_check_reports_a_bad_condition():
    grammar = NameGrammar(the=[FormChange(when="sideways", kind="ending", text="k")])
    report = check_language(_varovni(name_grammar=grammar))
    assert any("sideways" in problem for problem in report.blocking)


def test_merge_keeps_the_owners_name_grammar_edit():
    base = _varovni()
    current = _varovni(name_grammar=GRAMMAR.model_copy(update={"describing": "after"}))
    change = _varovni()
    merged = merge_change(base, change, current)
    assert merged.language.name_grammar.describing == "after"


def test_still_to_fill_in_lists_grammar_for_names():
    assert completeness(_varovni(name_grammar=None)).name_grammar_missing is True
    assert completeness(_varovni()).name_grammar_missing is False
