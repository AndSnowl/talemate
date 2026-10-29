"""A word's several meanings, and its uses as a name (languages 3a,
acceptance: "Soru" means wind and names a character)."""

import json
from pathlib import Path

import pytest

from talemate.languages.entry import fields_of, language_of, word_uses
from talemate.languages.importer import preview_import
from talemate.languages.models import DictionaryEntry, Language, LanguageFile
from talemate.languages.naming import add_word, define
from talemate.world.kinds import get_kind, validate_field
from talemate.world.store import Source

from conftest import MockClient, MockClientContext, client_responses


def test_an_old_single_meaning_still_loads():
    e = DictionaryEntry.model_validate({"word": "kor", "meaning": "river"})
    assert e.meanings == ["river"]
    assert "meaning" not in e.model_dump()


def test_a_word_holds_several_meanings():
    e = DictionaryEntry(word="soru", meanings=["wind", "breath"])
    assert e.model_dump()["meanings"] == ["wind", "breath"]


def test_words_field_takes_meanings_lists_or_none():
    k = get_kind("language")
    validate_field(k, "words", [{"word": "soru", "meanings": ["wind", "breath"]}])
    validate_field(k, "words", [{"word": "soru", "meanings": []}])
    validate_field(k, "words", [{"word": "kor", "meaning": "river"}])
    with pytest.raises(ValueError):
        validate_field(k, "words", [{"word": "soru", "meanings": ["wind", ""]}])


def _store(world, words):
    lang = Language(
        name="Moscavian",
        level="full",
        categories={"C": "k s r", "V": "a o u"},
        dictionary=[DictionaryEntry(word=w, meanings=m) for w, m in words],
    )
    with world.revision(Source.manual()) as rev:
        return rev.create_thing("language", {"name": lang.name, **fields_of(lang)})


def test_add_word_appends_a_meaning(world):
    lid = _store(world, [("soru", ["wind"])])
    with world.revision(Source.manual()) as rev:
        add_word(rev, world.view(), lid, "Soru", "breath")
        add_word(rev, world.view(), lid, "soru", "wind")  # already there
        add_word(rev, world.view(), lid, "Kassa", "")  # a name with no meaning
    words = {
        e.word.lower(): e.meanings
        for e in language_of(world.view().thing(lid)).dictionary
    }
    assert words["soru"] == ["wind", "breath"]
    assert words["kassa"] == []


def test_word_uses_names_the_entries_a_word_names(world):
    lid = _store(world, [("soru", ["wind"]), ("kor", ["river"])])
    with world.revision(Source.manual()) as rev:
        soru = rev.create_thing("character", {"name": "Soru"})
    uses = word_uses(world.view(), lid)
    assert uses == {"soru": [{"id": soru, "name": "Soru", "kind": "character"}]}


def test_a_new_version_adding_a_meaning_is_a_change_not_a_loss(world):
    lid = _store(world, [("soru", ["wind"])])
    new = Language(
        name="Moscavian",
        level="full",
        categories={"C": "k s r", "V": "a o u"},
        dictionary=[DictionaryEntry(word="soru", meanings=["wind", "breath"])],
    )
    diff = preview_import(
        world.view(), LanguageFile(language=new).model_dump_json(), lid
    ).diff
    assert diff.words_changed == ["soru"]


async def test_definitions_are_short_meanings():
    client = MockClient("test")
    async with MockClientContext():
        client_responses.get().append(json.dumps({"definitions": {"Soru": "wind"}}))
        got = await define(client, Language(name="Moscavian", level="full"), ["Soru"])
    assert got == {"Soru": "wind"}
    template = Path("src/talemate/prompts/templates/world/language-define.jinja2")
    text = template.read_text()
    assert "one to three words" in text and "Never write a sentence" in text


def _new_version(world, lid, entry):
    new = Language(
        name="Moscavian",
        level="full",
        categories={"C": "k s r", "V": "a o u"},
        dictionary=[entry],
    )
    return preview_import(
        world.view(), LanguageFile(language=new).model_dump_json(), lid
    )


def _named_soru(world):
    with world.revision(Source.manual()) as rev:
        rev.create_thing("character", {"name": "Soru"})


def test_a_new_version_adds_a_meaning_to_a_used_word(world):
    # adding a meaning appends, even to a word the world uses as a name
    lid = _store(world, [("soru", ["wind"])])
    _named_soru(world)
    preview = _new_version(
        world, lid, DictionaryEntry(word="soru", meanings=["wind", "breath"], part="noun")
    )
    soru = preview.file.language.dictionary[0]
    assert soru.meanings == ["wind", "breath"]
    assert soru.part == "noun"
    assert preview.diff.kept_used == []
    assert preview.diff.words_changed == ["soru"]


def test_a_used_word_keeps_the_meanings_a_new_version_drops(world):
    lid = _store(world, [("soru", ["wind"])])
    _named_soru(world)
    preview = _new_version(world, lid, DictionaryEntry(word="soru", meanings=["breath"]))
    assert preview.file.language.dictionary[0].meanings == ["wind", "breath"]
    assert preview.diff.kept_used == ["soru"]


def test_reordered_or_recased_meanings_are_not_a_change(world):
    lid = _store(world, [("soru", ["wind", "breath"])])
    _named_soru(world)
    preview = _new_version(
        world, lid, DictionaryEntry(word="soru", meanings=["Breath", "wind"])
    )
    assert preview.diff.words_changed == []
    assert preview.diff.kept_used == []
