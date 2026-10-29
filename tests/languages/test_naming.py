"""Naming from a language (languages 3a, Task 7)."""

import json

import pytest

import talemate.languages.naming as naming
from talemate.languages.entry import fields_of, language_of
from talemate.languages.models import (
    DictionaryEntry,
    GeneratorDef,
    Language,
)
from talemate.languages.naming import (
    NameInResult,
    add_word,
    apply_name_in,
    define,
    generator_for,
    name_in,
    pick,
    roll_names,
)
from talemate.world.kinds import get_kind, validate_field
from talemate.world.store import Source

from conftest import MockClient, MockClientContext, client_responses


def _lang(
    gens=("people", "places"), words=(("svoven", "free"), ("sorau", "free land"))
):
    return Language(
        name="Moscavian",
        level="full",
        categories={"C": "k v r s l n", "V": "a o e u"},
        generators=[
            GeneratorDef(id="words", name="Words", use="words", patterns=["CVCVC"]),
            *[
                GeneratorDef(id=g, name=g, use=g, patterns=["CVCVC", "CVCV"])
                for g in gens
            ],
        ],
        dictionary=[DictionaryEntry(word=w, meaning=m) for w, m in words],
    )


def _store(world, lang):
    with world.revision(Source.manual()) as rev:
        return rev.create_thing("language", {"name": lang.name, **fields_of(lang)})


def _queue(*replies):
    for reply in replies:
        client_responses.get().append(reply)


def test_generator_for_kind_falls_back():
    lang = _lang(gens=("people", "places"))
    assert generator_for(lang, "item").id == "places"
    assert generator_for(lang, "character").id == "people"
    assert generator_for(lang, "being").id == "people"
    only_kind = _lang(gens=("place",))
    assert generator_for(only_kind, "place").id == "place"
    assert generator_for(only_kind, "event").id == "place"


def test_generator_for_needs_name_rules():
    lang = _lang(gens=())
    with pytest.raises(ValueError, match="no name rules"):
        generator_for(lang, "place")


def test_roll_names_excludes_used(world):
    lang = _lang()
    first = roll_names(lang, "place", count=3, seed=1)
    assert len(first) == 3
    again = roll_names(lang, "place", count=3, seed=1, exclude=frozenset(first))
    assert not set(again) & set(first)


async def test_define_uses_one_call_and_fills_missing():
    client = MockClient("test")
    async with MockClientContext():
        _queue(
            json.dumps(
                {
                    "definitions": {
                        "Kovar": "A river town.",
                        "Selun": "Named after a saint.",
                    }
                }
            )
        )
        got = await define(client, _lang(), ["Kovar", "Selun", "Ravo"])
    assert got == {
        "Kovar": "A river town.",
        "Selun": "Named after a saint.",
        "Ravo": "",
    }
    assert len(client.prompt_history) == 1


async def test_pick_falls_back_to_first_candidate():
    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps({"pick": "Nowhere", "why": "made up"}))
        assert (await pick(client, _lang(), ["Kovar", "Selun"], "a capital"))[
            0
        ] == "Kovar"
        _queue(json.dumps({"pick": "Selun", "why": "old"}))
        assert await pick(client, _lang(), ["Kovar", "Selun"], "a capital") == (
            "Selun",
            "old",
        )


def test_add_word_adds_a_meaning_and_keeps_the_old(world):
    lid = _store(world, _lang())
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Free Provinces of Sorau"})
    with world.revision(Source.manual()) as rev:
        add_word(rev, world.view(), lid, "sorau", "southern march")
        add_word(rev, world.view(), lid, "Velgarov", "great fort")
    words = {
        e.word: e.meanings for e in language_of(world.view().thing(lid)).dictionary
    }
    assert words["sorau"] == ["free land", "southern march"]
    assert words["Velgarov"] == ["great fort"]


async def test_name_in_translates_known_and_rolls_missing(world, monkeypatch):
    lid = _store(world, _lang())
    with world.revision(Source.manual()) as rev:
        sorau = rev.create_thing("place", {"name": "Free Provinces of Sorau"})

    async def first(client, language, candidates, what, **kwargs):
        return candidates[0], "it fits"

    monkeypatch.setattr(naming, "pick", first)
    result = await name_in(world.view(), MockClient("test"), sorau, lid)
    words = result.name.split()
    assert words[0] == "Svoven" and words[-1] == "Sorau" and len(words) == 3
    assert result.new_words == [{"word": words[1].lower(), "meaning": "provinces"}]

    with world.revision(Source.manual()) as rev:
        apply_name_in(rev, world.view(), sorau, lid, result)
    state = world.view().thing(sorau)
    assert {
        "name": result.name,
        "tag": "proper",
        "everyday": False,
        "language": lid,
    } in state.fields["aka"]
    assert words[1].lower() in {
        e.word for e in language_of(world.view().thing(lid)).dictionary
    }


def test_aka_accepts_language_key():
    validate_field(
        get_kind("place"),
        "aka",
        [
            {
                "name": "Kata Sorau",
                "tag": "proper",
                "everyday": False,
                "language": "a" * 32,
            }
        ],
    )
    with pytest.raises(ValueError):
        validate_field(
            get_kind("place"),
            "aka",
            [{"name": "Kata", "tag": "proper", "everyday": False, "language": "x"}],
        )


def test_name_in_result_shape():
    assert NameInResult(name="X", new_words=[]).name == "X"


async def test_pick_without_a_client_takes_the_first_candidate():
    assert await pick(None, _lang(), ["Kovar", "Selun"], "a capital") == ("Kovar", "")
