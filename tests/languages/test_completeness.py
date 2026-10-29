"""What a language is still missing (languages 3b-2a, Task 2)."""

import time

from talemate.languages.check import check_language, needs_repair, repair_note
from talemate.languages.completeness import (
    CORE_MEANINGS,
    PHRASE_CATEGORIES,
    completeness,
)
from talemate.languages.models import (
    GRAMMAR_TOPICS,
    DictionaryEntry,
    GeneratorDef,
    GrammarSection,
    Language,
    Phrase,
)


def _language(words=(), phrases=(), grammar=(), level="full"):
    return Language(
        name="Moscavian",
        level=level,
        categories={"C": "k s r d v l n t", "V": "a o u e i"},
        generators=[
            GeneratorDef(id="w", name="Words", use="words", patterns=["CVC", "CVCV"])
        ],
        dictionary=[DictionaryEntry(word=w, meanings=m) for w, m in words],
        phrases=list(phrases),
        grammar=list(grammar),
    )


def test_the_core_list_has_both_groups():
    assert {"the", "be", "have", "with", "ten"} <= set(CORE_MEANINGS["structural"])
    assert {"water", "hand", "tree", "red", "sleep"} <= set(CORE_MEANINGS["everyday"])
    assert not set(CORE_MEANINGS["structural"]) & set(CORE_MEANINGS["everyday"])
    assert len(CORE_MEANINGS["everyday"]) >= 150


def test_a_word_with_the_meaning_counts():
    got = completeness(_language(words=[("vod", ["Water"]), ("byt", ["to be"])]))
    assert "water" not in got.meanings_missing
    assert "be" not in got.meanings_missing
    assert "be" not in got.structural_missing


def test_a_second_meaning_counts():
    got = completeness(_language(words=[("ruk", ["arm", "hand"])]))
    assert "hand" not in got.meanings_missing


def test_a_multi_word_meaning_does_not_count_for_its_parts():
    got = completeness(_language(words=[("veltasun", ["great fort"])]))
    assert "big" in got.meanings_missing
    assert got.meanings_total == len(CORE_MEANINGS["structural"]) + len(
        CORE_MEANINGS["everyday"]
    )


def test_missing_phrase_categories_and_grammar_topics():
    got = completeness(
        _language(
            phrases=[
                Phrase(id="g", category="Greeting", original="Zor", translation="Hi")
            ],
            grammar=[GrammarSection(title="Nouns", topic="nouns")],
        )
    )
    assert got.phrase_categories_missing == [
        c for c in PHRASE_CATEGORIES if c != "greeting"
    ]
    titles = [title for topic, title in GRAMMAR_TOPICS if topic != "nouns"]
    assert got.grammar_topics_missing == titles


def test_completeness_never_blocks_or_repairs():
    report = check_language(_language())
    assert report.completeness is not None
    assert report.ok and not needs_repair(report)


def test_the_repair_note_lists_still_to_fill_in():
    note = repair_note(check_language(_language(words=[("vod", ["water"])])))
    assert "Still to fill in:" in note
    assert "everyday" in note.lower() and "missing" in note


def test_a_naming_style_has_no_completeness():
    assert check_language(_language(level="naming")).completeness is None


def test_a_full_size_language_checks_quickly():
    words = [
        (f"w{i:03d}".replace("0", "a").replace("1", "o"), [f"m{i}"]) for i in range(400)
    ]
    phrases = [
        Phrase(
            id=f"p{i}",
            category=PHRASE_CATEGORIES[i % 9],
            original="Zor",
            translation="x",
        )
        for i in range(40)
    ]
    grammar = [GrammarSection(title=t, topic=k) for k, t in GRAMMAR_TOPICS] + [
        GrammarSection(title="Odd", topic="other")
    ]
    lang = _language(words=words, phrases=phrases, grammar=grammar)
    started = time.monotonic()
    check_language(lang)
    assert time.monotonic() - started < 2.0


# --- final review fixes ------------------------------------------------------

from talemate.languages.brief import write_brief  # noqa: E402
from talemate.languages.making import MakeRequest  # noqa: E402

BASICS = ("water", "fire", "sun", "eat", "drink", "see", "come")


def test_the_quick_core_has_the_basics():
    quick = CORE_MEANINGS["everyday"][:40]
    assert all(b in quick for b in BASICS)
    brief = write_brief(None, MakeRequest(text="x"), size="quick")
    part = brief.split("## What to make", 1)[1].split("\n## ", 1)[0]
    assert all(f" {b}," in part or f" {b}\n" in part for b in BASICS)


def test_a_note_in_brackets_is_ignored():
    got = completeness(_language(words=[("ty", ["you (singular)"]), ("ogn", ["fire (n.)"])]))
    assert "you" not in got.meanings_missing and "fire" not in got.meanings_missing


def test_forms_of_be_and_have_are_not_words_of_their_own():
    for form in ("am", "are", "is", "was", "were", "has", "had"):
        assert form not in CORE_MEANINGS["structural"]
    assert {"be", "have"} <= set(CORE_MEANINGS["structural"])


def test_the_and_a_are_covered_by_a_nouns_section():
    # "the" as an ending on the noun: the nouns section says how
    got = completeness(_language(grammar=[GrammarSection(title="Nouns", topic="nouns")]))
    assert "the" not in got.meanings_missing and "a" not in got.meanings_missing
    assert "the" in completeness(_language()).meanings_missing


def test_the_brief_says_forms_live_in_the_grammar():
    brief = write_brief(None, MakeRequest(text="x"), size="full")
    assert "forms of be and have" in brief
    assert '"the" and "a"' in brief
