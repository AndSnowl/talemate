"""The 4b-1 final review's findings (languages 4b-1, fix pass)."""

import random

from talemate.languages.check import check_language
from talemate.languages.composed import roll_parts
from talemate.languages.entry import fields_of
from talemate.languages.generator import name_fits
from talemate.languages.models import (
    DictionaryEntry,
    FormChange,
    GeneratorDef,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)
from talemate.languages.name_grammar import MeaningPhrase, build_phrase
from talemate.languages.naming import translate_text
from talemate.languages.naming_meaning import give_meaning, read_english, split_meaning
from talemate.world.store import Source

GRAMMAR = NameGrammar(
    of=OfRule(text="dez", word_side="before"),
    the=[FormChange(kind="word_before", text="lo")],
    more_than_one=[FormChange(kind="ending", text="i")],
)


def _lang(**changes):
    fields = {
        "name": "L",
        "level": "full",
        "categories": {"C": "k v d z", "V": "a e i o u"},
        "generators": [
            GeneratorDef(id="words", name="Words", use="words", patterns=["CVCV"]),
            GeneratorDef(id="men", name="Men", use="character", patterns=["[dorvak]"]),
        ],
        "dictionary": [
            DictionaryEntry(word="korvo", meanings=["court"], part="noun"),
            DictionaryEntry(word="zeva", meanings=["lake"], part="noun"),
            DictionaryEntry(word="drassa", meanings=["owl"], part="noun"),
            DictionaryEntry(word="nolok", meanings=["black"], part="adjective"),
            DictionaryEntry(word="lakeland", meanings=["a marsh"], part="noun"),
        ],
        "name_grammar": GRAMMAR,
    }
    return Language(**{**fields, **changes})


async def _give(world, lang, text, **kwargs):
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "L", **fields_of(lang)})
    return await give_meaning(world.view(), None, lid, text, **kwargs)


async def test_x_of_y_keeps_both_nouns(world):
    """Review I1: "Court of Lakes" with no rule meant only "(of) lakes"."""

    found = await _give(world, _lang(), "Court of Lakes")
    meanings = [p["meaning"] for p in found["candidates"][0]["built_from"]]
    assert "court" in meanings and "lake" in meanings


async def test_x_of_y_is_shared_across_two_meaning_parts():
    parts = [NamePart(kind="meaning"), NamePart(kind="meaning", of=True)]
    phrases = await split_meaning(None, _lang(), "Owl of Frost", parts)
    assert [p.noun for p in phrases] == ["owl", "frost"]


def test_land_is_a_word_when_the_grammar_has_no_land_ending():
    """Review I2: "The Black Land" raised KeyError: 'land of'."""

    lang = _lang()
    phrase = read_english("The Black Land", language=lang)
    assert (
        phrase.noun == "land" and phrase.describing == ["black"] and not phrase.ending
    )
    built = build_phrase(
        lang, MeaningPhrase(noun="owl", ending="land of"), {"owl": "drassa"}
    )
    assert built.text == "Drassa"


def test_a_part_with_an_unknown_ending_does_not_break_rolling():
    owl = GeneratorDef(
        id="owl",
        name="Owl",
        use="character",
        shapes=[NameShape(parts=[NamePart(kind="meaning", ending="gone")])],
    )
    lang = _lang(generators=[*_lang().generators, owl])
    _shape, parts = roll_parts(lang, "owl", rng=random.Random(1))
    assert parts[0].rolls
    assert any("gone" in p for p in check_language(lang).blocking)


def test_bad_grammar_keeps_every_rules_samples():
    """Review I3: one unreadable condition emptied every rule's samples."""

    lang = _lang(
        name_grammar=GRAMMAR.model_copy(
            update={"the": [FormChange(when="ends:", text="x")]}
        )
    )
    report = check_language(lang)
    assert report.blocking and report.samples["men"]


def test_random_meanings_take_only_real_nouns():
    """Review I4: picked names saved as words (no meaning) were rolled as
    nouns."""

    lang = _lang(
        dictionary=[
            DictionaryEntry(word="zeva", meanings=["lake"], part="noun"),
            DictionaryEntry(word="Dorvak Ul Zveski"),
            DictionaryEntry(word="zemol"),
        ],
        generators=[
            *_lang().generators,
            GeneratorDef(
                id="m",
                name="M",
                use="place",
                shapes=[NameShape(parts=[NamePart(kind="meaning")])],
            ),
        ],
    )
    _shape, parts = roll_parts(lang, "m", rng=random.Random(3))
    assert {r.text for r in parts[0].rolls} == {"Zeva"}


def test_reading_the_english_drops_punctuation_and_and_and_possessives():
    """Review M2 (re-graded): junk words coined for "stars!", "and", "owl's"."""

    assert read_english("Stars!") == MeaningPhrase(noun="star", more_than_one=True)
    assert read_english("Old, Grey") == MeaningPhrase(noun="grey", describing=["old"])
    assert read_english("Sun and Moon") == MeaningPhrase(
        noun="moon", describing=["sun"]
    )
    assert read_english("Owl's Rest") == MeaningPhrase(noun="rest", describing=["owl"])
    assert read_english("7 Hills") == MeaningPhrase(noun="hill", more_than_one=True)


async def test_a_dictionary_word_is_not_split_by_the_model():
    """Review M3 (re-graded): "lakeland" is a word of its own."""

    asked = []

    class Spy:
        pass

    phrases = await split_meaning(
        Spy(), _lang(), "lakeland", [], reply=None, ask=lambda w: asked.append(w) or {}
    )
    assert asked == [] and phrases[0].noun == "lakeland"


def test_article_and_of_words_fit():
    """Review M5 (re-graded): "Lo Drassa", "Dez Zevai" were flagged."""

    lang = _lang()
    assert name_fits(lang, "Lo Drassa") is True
    assert name_fits(lang, "Dorvak Dez Zevai") is True


async def test_name_in_x_of_y_still_works():
    found = await translate_text(None, _lang(), "Court of Lakes")
    assert "Korvo" in found.name


def test_rows_read_plainly_as_the_acceptance_run_wrote_them():
    """Acceptance run (Drassonais, Tsevrani): "--ov", "before before a
    vowel" and "(plural)" in the Names chapter's rows."""

    from talemate.languages.models import Ending
    from talemate.languages.name_grammar import apply_ending, grammar_rows

    grammar = NameGrammar(
        the=[
            FormChange(when="plural", kind="word_before", text="lou"),
            FormChange(when="before_vowel", kind="word_before", text="l'"),
            FormChange(kind="word_before", text="lo"),
        ],
        endings=[Ending(ending="-ov", meaning="one who does")],
    )
    lang = _lang(name_grammar=grammar)
    rows = {r.key: r for r in grammar_rows(lang)}
    assert rows["the"].rule == (
        "“lou” in front for more than one; “l'” in front before a vowel; “lo” in front"
    )
    ending = next(r for k, r in rows.items() if k.startswith("ending:"))
    assert ending.label == "-ov"
    assert apply_ending(grammar, frozenset("aeiou"), "dyesh", "one who does") == "dyeshov"
