"""The name engine (languages 4b-1, Task 2): forms, endings and name
phrases built by a language's grammar for names, with examples from the
owner's own languages."""

from talemate.languages.models import DictionaryEntry, GrammarSection, GrammarTable
from talemate.languages.models import Language
from talemate.languages.name_grammar import (
    Ending,
    FormChange,
    GrammarRow,
    MeaningPhrase,
    NameGrammar,
    OfRule,
    apply_ending,
    apply_form,
    build_phrase,
    grammar_rows,
    lookup_word,
)

VOWELS = frozenset("aeiou")

VAROVNI = NameGrammar(
    describing="before",
    of=OfRule(text="ul", word_side="before"),
    the=[
        FormChange(when="after_vowel", kind="ending", text="k"),
        FormChange(kind="ending", text="ek"),
    ],
    more_than_one=[
        FormChange(when="after_vowel", kind="ending", text="ni"),
        FormChange(kind="ending", text="i"),
    ],
    endings=[Ending(ending="ets", meaning="one from")],
)
TSEVRANI = NameGrammar(
    describing="before",
    joining="describing_first",
    clip_first=True,
    more_than_one=[
        FormChange(when="ends:a|o", kind="swap", drop="a|o", text="y"),
        FormChange(kind="ending", text="y"),
    ],
)
BUMBAGOO = NameGrammar(describing="after", more_than_one=[FormChange(kind="double")])
DRASSONAIS = NameGrammar(
    describing="after",
    the=[
        FormChange(when="before_vowel", kind="word_before", text="l'"),
        FormChange(kind="word_before", text="lo"),
    ],
)
VARSENYK = NameGrammar(
    endings=[
        Ending(
            ending="enya",
            meaning="land of",
            changes=[
                FormChange(when="after_consonant", kind="ending", text="enya"),
                FormChange(when="ends:a", kind="swap", drop="a", text="enya"),
            ],
        )
    ]
)


def _lang(grammar, words=(), sections=()):
    return Language(
        name="L",
        level="full",
        categories={"C": "k v", "V": "a e i o u"},
        name_grammar=grammar,
        dictionary=[DictionaryEntry(**w) for w in words],
        grammar=list(sections),
    )


def test_varovni_the_and_plural():
    assert apply_form(VAROVNI, VOWELS, "skelt", "the") == "skeltek"
    assert apply_form(VAROVNI, VOWELS, "skelt", "more_than_one") == "skelti"
    assert apply_form(VAROVNI, VOWELS, "ulkha", "more_than_one") == "ulkhani"
    plural = apply_form(VAROVNI, VOWELS, "ulkha", "more_than_one")
    assert apply_form(VAROVNI, VOWELS, plural, "the") == "ulkhanik"


def test_tsevrani_swap():
    assert apply_form(TSEVRANI, VOWELS, "zhelva", "more_than_one") == "zhelvy"
    assert apply_form(TSEVRANI, VOWELS, "dervo", "more_than_one") == "dervy"
    assert apply_form(TSEVRANI, VOWELS, "korsh", "more_than_one") == "korshy"


def test_bumbagoo_double():
    assert apply_form(BUMBAGOO, VOWELS, "bumpa", "more_than_one") == "bubumpa"
    assert apply_form(BUMBAGOO, VOWELS, "tok", "more_than_one") == "totok"


def test_a_word_before_elides_and_capitalises():
    assert apply_form(DRASSONAIS, VOWELS, "auvre", "the") == "l'auvre"
    lang = _lang(
        DRASSONAIS,
        [
            {"word": "auvre", "meanings": ["water"]},
            {"word": "chinou", "meanings": ["dog"]},
        ],
    )
    water = build_phrase(
        lang, MeaningPhrase(noun="water", the=True), {"water": "auvre"}
    )
    assert water.text == "L'Auvre"
    dog = build_phrase(lang, MeaningPhrase(noun="dog", the=True), {"dog": "chinou"})
    assert dog.text == "Lo Chinou"


def test_varovni_of_the_stars():
    lang = _lang(VAROVNI, [{"word": "zvesk", "meanings": ["star"]}])
    built = build_phrase(
        lang,
        MeaningPhrase(noun="star", of=True, more_than_one=True),
        {"star": "zvesk"},
    )
    assert built.text == "Ul Zveski"
    star = next(p for p in built.parts if p["meaning"] == "star")
    assert star["word"] == "zvesk" and star["new"] is False
    assert star["steps"] == ["-i more than one"]


def test_describing_order():
    varovni = _lang(VAROVNI)
    built = build_phrase(
        varovni,
        MeaningPhrase(noun="owl", describing=["white"]),
        {"owl": "ulkha", "white": "ilvo"},
    )
    assert built.text == "Ilvo Ulkha"
    drassonais = _lang(DRASSONAIS)
    built = build_phrase(
        drassonais,
        MeaningPhrase(noun="lake", describing=["white"]),
        {"lake": "aunfoimtte", "white": "blanchic"},
    )
    assert built.text == "Aunfoimtte Blanchic"


def test_joined_with_clip():
    built = build_phrase(
        _lang(TSEVRANI),
        MeaningPhrase(noun="road", describing=["white"], joined=True),
        {"road": "dorvesh", "white": "belesh"},
    )
    assert built.text == "Beldorvesh"


def test_ending_by_meaning():
    assert apply_ending(VARSENYK, VOWELS, "varsa", "land of") == "varsenya"
    assert apply_ending(VARSENYK, VOWELS, "khuvel", "land of") == "khuvelenya"


def test_a_new_word_is_marked_new():
    built = build_phrase(
        _lang(VAROVNI),
        MeaningPhrase(noun="frost"),
        {"frost": "mraz"},
        new=frozenset({"mraz"}),
    )
    assert built.parts == [
        {"word": "mraz", "meaning": "frost", "new": True, "steps": []}
    ]


def test_no_grammar_builds_in_the_given_order():
    built = build_phrase(
        _lang(None),
        MeaningPhrase(noun="lake", describing=["white"], more_than_one=True),
        {"lake": "aunfoimtte", "white": "blanchic"},
    )
    assert built.text == "Blanchic Aunfoimtte"


def test_meaning_lookup_is_stable_and_word_first():
    lang = _lang(
        None,
        [
            {"word": "sol", "meanings": ["sun"]},
            {"word": "aster", "meanings": ["sun", "star"]},
            {"word": "star", "meanings": ["a heap"]},
        ],
    )
    assert {lookup_word(lang, "sun").word for _ in range(20)} == {"sol"}
    assert lookup_word(lang, "STAR").word == "star"
    assert lookup_word(lang, "moon") is None


def test_grammar_rows_build_examples():
    lang = _lang(
        VAROVNI,
        [{"word": "ilvo", "meanings": ["white"], "part": "adjective"}],
        [
            GrammarSection(
                title="Nouns",
                topic="nouns",
                tables=[GrammarTable(caption="skelt (stone)", columns=[], rows=[])],
            )
        ],
    )
    rows = grammar_rows(lang)
    the = next(r for r in rows if r.key == "the")
    assert the == GrammarRow(
        key="the", label='"the"', rule=the.rule, example="skelt → skeltek"
    )
    assert next(r for r in rows if r.key == "more_than_one").example == "skelt → skelti"
    ending = next(r for r in rows if r.key == "ending:ets")
    assert ending.example == "skelt → skeltets" and "one from" in ending.rule
    assert grammar_rows(_lang(None)) == []


def test_the_can_differ_for_more_than_one():
    """Probe 4b-1: Drassonais "the" is lo for one and lou for more than
    one (the `plural` condition)."""

    grammar = NameGrammar(
        describing="after",
        more_than_one=[FormChange(kind="ending", text="s")],
        the=[
            FormChange(when="plural", kind="word_before", text="lou"),
            FormChange(when="before_vowel", kind="word_before", text="l'"),
            FormChange(kind="word_before", text="lo"),
        ],
    )
    assert apply_form(grammar, VOWELS, "chinou", "the") == "lo chinou"
    assert apply_form(grammar, VOWELS, "chinous", "the", plural=True) == "lou chinous"
    built = build_phrase(
        _lang(grammar),
        MeaningPhrase(noun="dog", the=True, more_than_one=True),
        {"dog": "chinou"},
    )
    assert built.text == "Lou Chinous"
