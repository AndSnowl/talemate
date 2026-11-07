"""Marking bad names (languages 4a revised, Task 1): cleaning finds and
marks, and never changes the text (owner, 2026-11-01)."""

import json

import pytest

from conftest import MockClient, MockClientContext, client_responses
from talemate.languages.cleaning.lists import NameLists
from talemate.languages.cleaning.mark import mark_texts
from talemate.languages.entry import fields_of
from talemate.languages.models import GeneratorDef, Language
from talemate.world.store import Source

PLACES = ["Zizhigrad", "Sovyetsk", "Lezhograd"]


def _language(name="Moscavian", generators=None):
    return Language(
        name=name,
        level="naming",
        flavour="russian",
        categories={"C": "k v", "V": "a"},
        generators=generators
        if generators is not None
        else [
            GeneratorDef(
                id="places",
                name="Places",
                use="place",
                patterns=[f"[{'|'.join(PLACES)}]"],
            ),
        ],
    )


@pytest.fixture
def moscavia(world):
    with world.revision(Source.manual()) as rev:
        return rev.create_thing(
            "language", {"name": "Moscavian", **fields_of(_language())}
        )


async def _mark(world, lid, texts, listed=(), replies=(), lists=None, keep=frozenset()):
    rows = [{"language": lid, "role": "official"}] if lid else []
    async with MockClientContext():
        for reply in replies:
            client_responses.get().append(json.dumps(reply))
        marks = await mark_texts(
            MockClient("t"), world.view(), list(texts), list(listed), "", rows,
            lists or NameLists(real=["Novgorod"]), keep,
        )  # fmt: skip
    return marks


async def test_a_real_place_is_marked_not_changed(world, moscavia):
    texts = ["Fur goes to Novgorod.", "Trade with Novgorod's merchants."]
    marks = await _mark(world, moscavia, texts)
    assert texts == ["Fur goes to Novgorod.", "Trade with Novgorod's merchants."]
    assert [(m.name, m.why, m.language_id) for m in marks] == [
        ("Novgorod", "a real name, on the Real names list", moscavia)
    ]


async def test_a_stock_title_is_marked_not_rewritten(world, moscavia):
    marks = await _mark(
        world, moscavia, ["The Iron Council judges."], listed=[("Iron Council", "lore")],
        lists=NameLists(title=["Iron Council"]),
    )  # fmt: skip
    assert [(m.name, m.why) for m in marks] == [("Iron Council", "a stock title")]


async def test_a_misfit_is_marked(world, moscavia):
    marks = await _mark(
        world,
        moscavia,
        ["Trade with Velkora."],
        replies=[{"names": []}],
        lists=NameLists(),
    )
    assert [(m.name, m.why) for m in marks] == [
        ("Velkora", "doesn't sound like Moscavian")
    ]


async def test_no_language_marks_list_hits_only(world, moscavia):
    marks = await _mark(world, None, ["Trade with Novgorod and Velkora."])
    assert [(m.name, m.why) for m in marks] == [("Novgorod", "no language picked")]


async def test_a_kept_name_is_not_marked(world, moscavia):
    marks = await _mark(world, moscavia, ["Trade with Novgorod."], keep={"Novgorod"})
    assert marks == []


async def test_a_world_without_languages_marks_nothing(world):
    marks = await _mark(world, None, ["Trade with Novgorod."])
    assert marks == []


async def test_a_framed_name_is_marked_whole(world, moscavia):
    """The mark covers the name as written ("White Sea"), so the card and
    Name it… get the whole thing."""

    marks = await _mark(
        world,
        moscavia,
        ["The shores of the White Sea freeze."],
        lists=NameLists(real=["White Sea"]),
    )
    assert [m.name for m in marks] == ["White Sea"]


# --- whole names (languages 4c, Task 6) --------------------------------------


def test_proper_part_leaves_narrator_words_and_epithets():
    from talemate.languages.cleaning.find import proper_part

    assert proper_part("Tsar Aleksi Romanov III") == "Aleksi Romanov"
    assert proper_part("Zochar the White") == "Zochar"
    assert proper_part("Maëlis of Sauvaire") == "Maëlis"
    assert proper_part("Aleksi") == "Aleksi"


async def test_a_persons_mark_covers_the_whole_proper_part(world, moscavia):
    marks = await _mark(
        world,
        moscavia,
        ["Tsar Aleksi Romanov III rules from the north."],
        listed=[("Tsar Aleksi Romanov III", "character")],
        lists=NameLists(real=["Aleksi", "Romanov"]),
    )
    assert [(m.name, m.part) for m in marks] == [("Aleksi Romanov", "Aleksi Romanov")]


async def test_keep_and_never_flag_stick_for_a_whole_person_name(world, moscavia):
    """Final review C2: a person's mark is the whole proper part; Keep it
    (keep) and Never flag it (the keep list) skip it next time."""

    texts = ["Tsar Aleksi Romanov III rules from the north."]
    listed = [("Tsar Aleksi Romanov III", "character")]
    kept = await _mark(
        world,
        moscavia,
        texts,
        listed=listed,
        lists=NameLists(real=["Aleksi", "Romanov"]),
        keep={"Aleksi Romanov"},
    )
    assert kept == []
    never = await _mark(
        world,
        moscavia,
        texts,
        listed=listed,
        lists=NameLists(real=["Aleksi", "Romanov"], keep=["Aleksi Romanov"]),
    )
    assert never == []
