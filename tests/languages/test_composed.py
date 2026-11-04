"""Composed name rules roll part by part (languages 4b-1, Task 3)."""

import random
import re
import time

from talemate.languages.check import check_language
from talemate.languages.composed import roll_parts
from talemate.languages.generator import name_fits, roll
from talemate.languages.models import (
    DictionaryEntry,
    FormChange,
    GeneratorDef,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
)
from talemate.languages.naming import generator_for

MEN = GeneratorDef(
    id="men", name="Men's names", use="character", patterns=["[dorvak|zemol]"]
)
OWL_PARTS = [
    NamePart(kind="rule", rule="men"),
    NamePart(kind="word", word="Ul"),
    NamePart(kind="meaning", forms=["more_than_one"]),
]
OWL = GeneratorDef(
    id="owl", name="Owl-names", use="character", shapes=[NameShape(parts=OWL_PARTS)]
)
GRAMMAR = NameGrammar(
    more_than_one=[
        FormChange(when="after_vowel", kind="ending", text="ni"),
        FormChange(kind="ending", text="i"),
    ]
)
WORDS = [
    DictionaryEntry(word="zvesk", meanings=["star"], part="noun"),
    DictionaryEntry(word="skelt", meanings=["stone"], part="noun"),
]


def _lang(*generators, grammar=GRAMMAR):
    return Language(
        name="Varovni",
        level="full",
        categories={"C": "k v", "V": "a e i o u"},
        generators=list(generators) or [MEN, OWL],
        name_grammar=grammar,
        dictionary=WORDS,
    )


def test_owl_names_roll_from_parts():
    names = roll(_lang(), "owl", 5, rng=random.Random(1))
    assert names
    assert all(re.fullmatch(r"(Dorvak|Zemol) Ul (Zveski|Skelti)", n) for n in names)


def test_a_pin_keeps_its_part():
    shape, parts = roll_parts(
        _lang(), "owl", pinned={0: "Dorvak"}, rng=random.Random(2)
    )
    assert shape == 0
    assert [b.text for b in parts[0].rolls] == ["Dorvak"] and parts[0].pinned
    assert parts[1].kind == "word" and [b.text for b in parts[1].rolls] == ["Ul"]
    texts = [b.text for b in parts[2].rolls]
    assert texts and len(texts) == len(set(texts)) <= 8
    assert set(texts) <= {"Zveski", "Skelti"}
    assert parts[2].label == "a meaning · plural"


def test_pins_survive_only_where_the_shape_has_that_part():
    two = GeneratorDef(
        id="owl",
        name="Owl-names",
        use="character",
        shapes=[
            NameShape(parts=OWL_PARTS),
            NameShape(parts=[NamePart(kind="meaning")]),
        ],
    )
    shape, parts = roll_parts(_lang(MEN, two), "owl", pinned={2: "Zveski"}, shape=1)
    assert shape == 1 and len(parts) == 1
    assert not any(p.pinned for p in parts)
    shape, parts = roll_parts(_lang(MEN, two), "owl", pinned={2: "Zveski"}, shape=0)
    assert parts[2].pinned and [b.text for b in parts[2].rolls] == ["Zveski"]


def test_a_part_naming_a_missing_or_looping_rule_does_not_hang():
    a = GeneratorDef(
        id="a",
        name="A",
        use="place",
        shapes=[NameShape(parts=[NamePart(kind="rule", rule="b")])],
    )
    b = GeneratorDef(
        id="b",
        name="B",
        use="place",
        shapes=[NameShape(parts=[NamePart(kind="rule", rule="a")])],
    )
    gone = GeneratorDef(
        id="g",
        name="G",
        use="item",
        shapes=[NameShape(parts=[NamePart(kind="rule", rule="gone")])],
    )
    lang = _lang(a, b, gone)
    started = time.monotonic()
    names = roll(lang, "a", 3)
    assert time.monotonic() - started < 1
    assert names == ["(missing rule)"]
    _shape, parts = roll_parts(lang, "g")
    assert [r.text for r in parts[0].rolls] == ["(missing rule)"]


def test_the_plain_rule_stays_the_default():
    assert generator_for(_lang(OWL, MEN), "character").id == "men"
    assert (
        generator_for(
            _lang(MEN.model_copy(update={"use": "place"}), OWL), "character"
        ).id
        == "owl"
    )


def test_a_built_name_fits():
    lang = _lang()
    assert name_fits(lang, "Dorvak Ul Zveski") is True
    assert name_fits(lang, "Dorvak Ul Xqzt") is False


def test_samples_include_composed_rules():
    assert check_language(_lang()).samples["owl"]


def test_a_fixed_word_says_what_it_means():
    """Round 4: the builder shows "always · owl-of" for Ul."""

    lang = _lang().model_copy(
        update={"dictionary": [*WORDS, DictionaryEntry(word="ul", meanings=["owl-of"])]}
    )
    _shape, parts = roll_parts(lang, "owl", rng=random.Random(1))
    assert parts[1].rolls[0].parts == [
        {"word": "ul", "meaning": "owl-of", "new": False, "steps": []}
    ]
