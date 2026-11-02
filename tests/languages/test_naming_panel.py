"""Names for the Name it… panel (languages 4a revised, Task 3): a batch
from a rule or one of its patterns, meanings where a name is built from
dictionary words, and names made from a meaning."""

import random

import pytest

from talemate.languages.entry import fields_of
from talemate.languages.generator import roll
from talemate.languages.models import DictionaryEntry, GeneratorDef, Language
from talemate.languages.naming_panel import batch, from_meaning, meaning_of, rules_of
from talemate.world.store import Source

LANG = Language(
    name="Otsyenyan",
    level="full",
    categories={"C": "k v r s l d z n", "V": "a o e i u"},
    generators=[
        GeneratorDef(id="words", name="Words", use="words", patterns=["CVCV"]),
        GeneratorDef(
            id="places",
            name="Place names",
            use="place",
            patterns=["CVCV[grad|gorsk]", "[kolva|syev][vets|insk]*3"],
        ),
        GeneratorDef(id="tiny", name="Tiny", use="item", patterns=["[ark|bel|cor]"]),
    ],
    dictionary=[
        DictionaryEntry(word="kolva", meanings=["hill"]),
        DictionaryEntry(word="syev", meanings=["grey"]),
        DictionaryEntry(word="voda", meanings=["water"]),
    ],
)


@pytest.fixture
def otsyenyan(world):
    with world.revision(Source.manual()) as rev:
        return rev.create_thing("language", {"name": "Otsyenyan", **fields_of(LANG)})


def test_roll_from_one_pattern_only():
    names = roll(LANG, "places", count=20, rng=random.Random(1), pattern=1)
    assert names and all(n.startswith(("Kolva", "Syev")) for n in names)


def test_rules_list_their_patterns_without_weights():
    rules = {r.id: r for r in rules_of(LANG)}
    assert rules["places"].patterns == ["CVCV[grad|gorsk]", "[kolva|syev][vets|insk]"]
    assert rules["places"].name == "Place names"


def test_batch_gives_ten_with_meanings_where_built_from_words():
    got = batch(LANG, "places", pattern=1, count=10, seed=3)
    assert 1 <= len(got) <= 4  # two times two literal choices
    kolva = [g for g in got if g["name"].startswith("Kolva")]
    assert all(g["meaning"].startswith("kolva “hill”") for g in kolva)
    full = batch(LANG, "places", count=10, seed=3)
    assert len(full) == 10


def test_a_small_rule_gives_what_it_has():
    got = batch(LANG, "tiny", count=10, seed=1)
    assert sorted(g["name"] for g in got) == ["Ark", "Bel", "Cor"]


def test_batch_leaves_out_entry_names():
    got = batch(LANG, "tiny", count=10, seed=1, exclude=frozenset({"bel"}))
    assert sorted(g["name"] for g in got) == ["Ark", "Cor"]


def test_meaning_of_splits_into_dictionary_words():
    assert meaning_of(LANG, "Syevvoda") == "syev “grey” + voda “water”"
    assert meaning_of(LANG, "Kolvagorsk") == "kolva “hill” + -gorsk"
    assert meaning_of(LANG, "Dorovan") == ""


async def test_from_meaning_translates_and_coins_without_saving(world, otsyenyan):
    view = world.view()
    got = await from_meaning(view, None, otsyenyan, "grey lake")
    names = [c["name"] for c in got]
    # "grey" is translated; "lake" is coined from the word rules
    assert names[0].startswith("Syev")
    parts = got[0]["built_from"]
    assert parts[0] == {"word": "syev", "meaning": "grey", "new": False}
    assert parts[1]["meaning"] == "lake" and parts[1]["new"] is True
    # nothing saved
    from talemate.languages.entry import language_of

    assert [e.word for e in language_of(world.view().thing(otsyenyan)).dictionary] == [
        "kolva",
        "syev",
        "voda",
    ]


async def test_a_coined_word_comes_with_other_rolls(world, otsyenyan):
    """Owner's run (Test3): each new word shows several rolls to pick
    from, the model's pick first."""

    got = await from_meaning(world.view(), None, otsyenyan, "grey lake")
    lake = got[0]["built_from"][1]
    assert lake["options"][0] == lake["word"]
    assert len(lake["options"]) > 3 and len(set(lake["options"])) == len(
        lake["options"]
    )
    assert all(o.islower() and len(o) == 4 for o in lake["options"])
    # a word the language has comes alone
    assert "options" not in got[0]["built_from"][0]
