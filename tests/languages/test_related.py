"""The entries a change to a language should fit (languages 3b-2b, Task 2)."""

from talemate.languages.entry import fields_of
from talemate.languages.models import DictionaryEntry, GeneratorDef, Language
from talemate.languages.related import related_entries
from talemate.world.store import Source


def _setup(world):
    lang = Language(
        name="Moscavian",
        level="full",
        categories={"C": "k d r v s n", "V": "a o"},
        generators=[
            GeneratorDef(id="words", name="Words", use="words", patterns=["CVC"])
        ],
        dictionary=[
            DictionaryEntry(word="dov", meanings=["shrine"]),
            DictionaryEntry(word="zorin", meanings=["bright"]),
            DictionaryEntry(word="on", meanings=["he"]),
        ],
    )
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": lang.name, **fields_of(lang)})
        sorau = rev.create_thing(
            "place",
            {"name": "Sorau", "languages": [{"language": lid, "role": "official"}]},
        )
        town = rev.create_thing(
            "place", {"name": "Thornfield", "filings": [{"target": sorau}]}
        )
        synod = rev.create_thing("lore", {"name": "Owl Synod"})
        rev.add_fact(synod, "general", "Every dov keeps a zorin lamp.")
        walker = rev.create_thing("character", {"name": "Walker"})
        rev.add_fact(walker, "appearance", "He walks on the road.")
    return lid, sorau, town, synod, walker


def test_speakers_come_first_with_their_role(world):
    lid, sorau, *_ = _setup(world)
    first = related_entries(world.view(), lid)[0]
    assert (first.id, first.why) == (sorau, "speaks it (official)")


def test_entries_filed_in_a_speaker_follow(world):
    lid, sorau, town, *_ = _setup(world)
    got = {e.id: e.why for e in related_entries(world.view(), lid)}
    assert got[town] == "filed in Sorau"


def test_entries_whose_facts_use_its_words_are_suggested(world):
    lid, _sorau, _town, synod, walker = _setup(world)
    got = {e.id: e.why for e in related_entries(world.view(), lid)}
    assert got[synod] == 'its facts use "dov", "zorin"'
    assert walker not in got  # "on" is too short to count


def test_each_entry_once_and_at_most_the_limit(world):
    lid, *_ = _setup(world)
    got = related_entries(world.view(), lid, limit=2)
    assert len(got) == 2
    assert len({e.id for e in related_entries(world.view(), lid)}) == len(
        related_entries(world.view(), lid)
    )
