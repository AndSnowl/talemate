"""Merging a change onto a language as it is now (languages 3b-2b,
Task 1): the change applies where the owner did nothing; the owner's own
edits made meanwhile are kept; used words and the name never change."""

from talemate.languages.changes import merge_change
from talemate.languages.entry import fields_of
from talemate.languages.importer import preview_import
from talemate.languages.models import (
    DictionaryEntry,
    GeneratorDef,
    GrammarSection,
    Language,
    LanguageFile,
    Phrase,
)
from talemate.world.store import Source


def _lang(
    words=(("kor", ["river"]), ("dov", ["shrine"])), phrases=None, grammar=None, **kw
):
    return Language(
        name=kw.pop("name", "Moscavian"),
        level="full",
        sound=kw.pop("sound", "Hard and cold."),
        categories={"C": "k d r v s l", "V": "a o u"},
        generators=kw.pop(
            "generators",
            [
                GeneratorDef(id="words", name="Words", use="words", patterns=["CVC"]),
                GeneratorDef(
                    id="people", name="People", use="people", patterns=["CVCVC"]
                ),
            ],
        ),
        dictionary=[DictionaryEntry(word=w, meanings=list(m)) for w, m in words],
        phrases=phrases
        if phrases is not None
        else [
            Phrase(id="greet", category="greeting", original="Kor", translation="Hello")
        ],
        grammar=grammar
        if grammar is not None
        else [GrammarSection(title="Nouns", topic="nouns", text="Plain.")],
        **kw,
    )


def _words(lang):
    return {e.word: e.meanings for e in lang.dictionary}


def test_a_change_applies_where_the_owner_did_nothing():
    base = _lang()
    change = _lang(
        words=(("kor", ["river"]), ("dov", ["shrine"]), ("torg", ["trade"])),
        phrases=[
            Phrase(
                id="greet",
                category="greeting",
                original="Kor vel",
                translation="Hello friend",
            )
        ],
    )
    got = merge_change(base, change, current=base)
    assert _words(got.language)["torg"] == ["trade"]
    assert got.language.phrases[0].translation == "Hello friend"
    assert got.kept_edits == []


def test_the_owners_edit_is_kept_where_both_changed():
    base = _lang()
    change = _lang(words=(("kor", ["river", "road"]), ("dov", ["shrine"])))
    current = _lang(words=(("kor", ["river", "stream"]), ("dov", ["shrine"])))
    got = merge_change(base, change, current)
    assert _words(got.language)["kor"] == ["river", "stream"]
    assert got.kept_edits == ["word kor"]


def test_the_owners_new_word_survives_a_change():
    base = _lang()
    current = _lang(words=(("kor", ["river"]), ("dov", ["shrine"]), ("sel", ["free"])))
    change = _lang(words=(("kor", ["river"]), ("dov", ["shrine"]), ("torg", ["trade"])))
    words = _words(merge_change(base, change, current).language)
    assert {"sel", "torg", "kor", "dov"} <= set(words)


def test_a_removal_in_the_change_lands_only_if_the_owner_left_it_alone():
    base = _lang()
    change = _lang(words=(("kor", ["river"]),))
    assert "dov" not in _words(merge_change(base, change, base).language)
    edited = _lang(words=(("kor", ["river"]), ("dov", ["shrine", "temple"])))
    got = merge_change(base, change, edited)
    assert _words(got.language)["dov"] == ["shrine", "temple"]
    assert got.kept_edits == ["word dov"]


def test_the_name_stays_the_entrys_own():
    got = merge_change(_lang(), _lang(name="Moskvan"), _lang())
    assert got.language.name == "Moscavian"


def test_grammar_and_sound_and_rules_merge_by_key():
    base = _lang()
    change = _lang(
        sound="Soft and warm.",
        grammar=[
            GrammarSection(title="Nouns", topic="nouns", text="Changed."),
            GrammarSection(title="Verbs", topic="verbs"),
        ],
        generators=[
            GeneratorDef(id="words", name="Words", use="words", patterns=["CVC"])
        ],
    )
    got = merge_change(base, change, base).language
    assert got.sound == "Soft and warm."
    assert [s.title for s in got.grammar] == ["Nouns", "Verbs"]
    assert got.grammar[0].text == "Changed."
    assert [g.id for g in got.generators] == ["words"]


def _store(world, lang):
    with world.revision(Source.manual()) as rev:
        return rev.create_thing("language", {"name": lang.name, **fields_of(lang)})


def _text(lang):
    return LanguageFile(language=lang).model_dump_json()


def test_dropped_rule_sets_and_other_differences_show_in_the_diff(world):
    base = _lang()
    lid = _store(world, base)
    change = _lang(
        sound="Soft and warm.",
        grammar=[
            GrammarSection(title="Nouns", topic="nouns", text="Changed."),
            GrammarSection(title="Verbs", topic="verbs"),
        ],
        generators=[
            GeneratorDef(id="words", name="Words", use="words", patterns=["CVC"])
        ],
    )
    diff = preview_import(world.view(), _text(change), lid, base_text=_text(base)).diff
    assert diff.rules_removed == ["People"]
    assert diff.grammar_added == ["Verbs"] and diff.grammar_changed == ["Nouns"]
    assert (diff.sound_before, diff.sound_after) == ("Hard and cold.", "Soft and warm.")


def test_a_preview_lists_the_owners_kept_edits(world):
    base = _lang()
    lid = _store(world, base)
    with world.revision(Source.manual()) as rev:
        edited = _lang(words=(("kor", ["river", "stream"]), ("dov", ["shrine"])))
        rev.set_field(lid, "words", fields_of(edited)["words"], None)
    change = _lang(words=(("kor", ["river", "road"]), ("dov", ["shrine"])))
    preview = preview_import(world.view(), _text(change), lid, base_text=_text(base))
    assert preview.diff.kept_edits == ["word kor"]
    assert _words(preview.file.language)["kor"] == ["river", "stream"]


def test_used_words_still_win_over_a_change(world):
    base = _lang()
    lid = _store(world, base)
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Dov"})
    change = _lang(words=(("kor", ["river"]), ("dov", ["cave"])))
    preview = preview_import(world.view(), _text(change), lid, base_text=_text(base))
    assert _words(preview.file.language)["dov"][0] == "shrine"
    assert preview.diff.kept_used == ["dov"]


def test_duplicate_words_and_titles_survive_a_change():
    base = _lang(
        words=(("kor", ["stone"]), ("kor", ["strike"]), ("tal", ["night"])),
        grammar=[
            GrammarSection(title="Notes", text="One."),
            GrammarSection(title="Notes", text="Two."),
        ],
    )
    change = _lang(
        words=(("kor", ["stone"]), ("kor", ["strike"]), ("tal", ["night", "day"])),
        grammar=[
            GrammarSection(title="Notes", text="One."),
            GrammarSection(title="Notes", text="Two."),
        ],
    )
    got = merge_change(base, change, base).language
    assert [(e.word, e.meanings) for e in got.dictionary] == [
        ("kor", ["stone"]), ("kor", ["strike"]), ("tal", ["night", "day"]),
    ]  # fmt: skip
    assert [s.text for s in got.grammar] == ["One.", "Two."]
