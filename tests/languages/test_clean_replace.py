"""Replacing bad names, and the marks (languages 4a, Task 4). The test
language's rules can only roll a few known names, so tests know the
candidates."""

import json

import pytest

from conftest import MockClient, MockClientContext, client_responses
from talemate.languages.cleaning.lists import NameLists
from talemate.languages.cleaning.replace import apply_mark, clean_texts
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
                id="people",
                name="People",
                use="character",
                patterns=["[Dorovan|Kolvey|Tivamon] [Strazhin|Kolvesky]"],
            ),
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
        lid = rev.create_thing(
            "language", {"name": "Moscavian", **fields_of(_language())}
        )
    return lid


def _rows(lid):
    return [{"language": lid, "role": "official"}]


async def _clean(world, lid, texts, listed=(), replies=(), lists=None, prompt=""):
    async with MockClientContext():
        for reply in replies:
            client_responses.get().append(json.dumps(reply))
        cleaned = await clean_texts(
            MockClient("t"), world.view(), texts, list(listed), prompt,
            _rows(lid) if lid else [], lists or NameLists(real=["Novgorod"]),
        )  # fmt: skip
        client_responses.get().clear()
    return cleaned


def _picks(*picks):
    return {
        "picks": [
            {"n": i + 1, "pick": p, "meaning": m} for i, (p, m) in enumerate(picks)
        ]
    }


async def test_a_real_place_is_swapped_in_every_text_with_one_mark(world, moscavia):
    texts = ["Fur goes to Novgorod.", "Trade with Novgorod's merchants."]
    cleaned = await _clean(
        world, moscavia, texts, replies=[_picks(("Sovyetsk", "owl town"))]
    )
    assert cleaned.texts == [
        "Fur goes to Sovyetsk.",
        "Trade with Sovyetsk's merchants.",
    ]
    [mark] = cleaned.marks
    assert (mark.kind, mark.name, mark.was, mark.language_id) == (
        "replaced",
        "Sovyetsk",
        "Novgorod",
        moscavia,
    )
    assert set(mark.spares) == {"Zizhigrad", "Lezhograd"}


async def test_a_pick_outside_the_candidates_falls_back_to_the_first(world, moscavia):
    cleaned = await _clean(
        world, moscavia, ["Trade with Novgorod."], replies=[_picks(("Troegegrad", ""))]
    )
    assert cleaned.marks[0].name in PLACES
    assert "Troegegrad" not in cleaned.texts[0]


async def test_candidates_never_reuse_an_entry_or_an_earlier_pick(world, moscavia):
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Zizhigrad"})
    lists = NameLists(real=["Novgorod", "Smolensk"])
    cleaned = await _clean(
        world, moscavia, ["Trade with Novgorod and Smolensk."],
        replies=[_picks(("Sovyetsk", ""), ("Sovyetsk", ""))], lists=lists,
    )  # fmt: skip
    names = [m.name for m in cleaned.marks]
    assert sorted(names) == ["Lezhograd", "Sovyetsk"]
    assert all("Zizhigrad" not in m.spares for m in cleaned.marks)


async def test_the_pick_brings_a_meaning(world, moscavia):
    cleaned = await _clean(
        world,
        moscavia,
        ["Trade with Novgorod."],
        replies=[_picks(("Sovyetsk", "owl town"))],
    )
    assert cleaned.marks[0].meaning == "owl town"


async def test_a_persons_given_name_is_one_word(world, moscavia):
    cleaned = await _clean(
        world, moscavia, ["Tsar Dmitri II rules."], listed=[("Tsar Dmitri II", "character")],
        replies=[_picks(("Kolvey", ""))], lists=NameLists(real=["Dmitri"]),
    )  # fmt: skip
    assert cleaned.texts == ["Tsar Kolvey II rules."]


async def test_a_stock_title_keeps_its_frame(world, moscavia):
    lists = NameLists(title=["Iron Council"])
    reply = {"titles": [{"n": 1, "title": "the Iron Bench of {name}"}]}
    cleaned = await _clean(
        world,
        moscavia,
        ["The Iron Council judges."],
        listed=[("Iron Council", "lore")],
        replies=[reply],
        lists=lists,
    )
    [mark] = cleaned.marks
    assert mark.kind == "replaced" and mark.was == "Iron Council"
    assert mark.name.startswith("Iron Bench of ") and mark.name.split()[-1] in PLACES
    assert cleaned.texts == [f"The {mark.name} judges."]


async def test_a_rewrite_without_a_slot_stays_suspect(world, moscavia):
    lists = NameLists(title=["Iron Council"])
    reply = {"titles": [{"n": 1, "title": "the Iron Bench"}]}
    cleaned = await _clean(
        world,
        moscavia,
        ["The Iron Council judges."],
        listed=[("Iron Council", "lore")],
        replies=[reply],
        lists=lists,
    )
    assert [(m.kind, m.why) for m in cleaned.marks] == [("suspect", "a stock title")]
    assert cleaned.texts == ["The Iron Council judges."]


async def test_a_language_without_name_rules_leaves_names_suspect(world):
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing(
            "language",
            {"name": "Hushtongue", **fields_of(_language("Hushtongue", generators=[]))},
        )
    cleaned = await _clean(
        world, lid, ["Trade with Novgorod."], replies=[{"names": []}]
    )
    assert [(m.kind, m.why) for m in cleaned.marks] == [
        ("suspect", "Hushtongue has no name rules for this")
    ]
    assert cleaned.texts == ["Trade with Novgorod."]


async def test_the_named_language_in_a_sentence_wins(world, moscavia):
    with world.revision(Source.manual()) as rev:
        sid = rev.create_thing(
            "language",
            {
                "name": "Sorauan",
                **fields_of(
                    _language(
                        "Sorauan",
                        generators=[
                            GeneratorDef(
                                id="p",
                                name="Places",
                                use="place",
                                patterns=["[Kessau]"],
                            )
                        ],
                    )
                ),
            },
        )
    rows = [
        {"language": moscavia, "role": "official"},
        {"language": sid, "role": "spoken", "share": 20},
    ]
    async with MockClientContext():
        client_responses.get().append(json.dumps(_picks(("Kessau", ""))))
        cleaned = await clean_texts(
            MockClient("t"),
            world.view(),
            ["The Sorauan town of Novgorod."],
            [],
            "",
            rows,
            NameLists(real=["Novgorod"]),
        )
        client_responses.get().clear()
    assert cleaned.marks[0].language_id == sid
    assert cleaned.texts == ["The Sorauan town of Kessau."]


async def test_a_failed_pick_call_takes_the_first_candidate(world, moscavia):
    cleaned = await _clean(world, moscavia, ["Trade with Novgorod."], replies=[])
    assert cleaned.marks[0].kind == "replaced"
    assert cleaned.marks[0].name in PLACES
    assert cleaned.marks[0].meaning == ""


async def test_a_suspect_mark_carries_spares(world, moscavia):
    cleaned = await _clean(
        world,
        moscavia,
        ["Trade with Velkora."],
        replies=[{"names": []}],
        lists=NameLists(),
    )
    [mark] = cleaned.marks
    assert (mark.kind, mark.name, mark.was) == ("suspect", "Velkora", "Velkora")
    assert set(mark.spares) <= set(PLACES) and mark.spares


async def test_a_world_without_languages_is_left_alone(world):
    cleaned = await _clean(world, None, ["Trade with Novgorod."], replies=[])
    assert cleaned.texts == ["Trade with Novgorod."] and cleaned.marks == []


def test_apply_mark_keeps_possessives():
    from talemate.languages.cleaning.replace import Mark

    mark = Mark(
        id="m",
        kind="replaced",
        name="Sovyetsk",
        was="Novgorod",
        why="",
        entry_kind="place",
    )
    assert apply_mark(["Sovyetsk's walls; Sovyetskaya"], mark, "Lezhograd") == [
        "Lezhograd's walls; Sovyetskaya"
    ]
