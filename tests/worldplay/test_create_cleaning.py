"""Cleaning names in the new-entry draft (languages 4a, Task 5): a draft
with a language in reach arrives cleaned, finds its languages from the
owner's words, and has no description until accept."""

import json

import pytest

import talemate.config.state as config_state
from conftest import MockClient, MockClientContext, client_responses
from talemate.languages.entry import fields_of
from talemate.languages.models import GeneratorDef, Language
from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay.cleaning import clean_preview, unclean_preview
from talemate.worldplay.create import preview_thing

PLACES = ["Zizhigrad", "Sovyetsk", "Lezhograd"]
MOSCAVIAN = Language(
    name="Moscavian",
    level="naming",
    categories={"C": "k v", "V": "a"},
    generators=[
        GeneratorDef(
            id="people",
            name="People",
            use="character",
            patterns=["[Dorovan|Kolvey|Tivamon]"],
        ),
        GeneratorDef(
            id="places", name="Places", use="place", patterns=[f"[{'|'.join(PLACES)}]"]
        ),
    ],
)
REPLY = json.dumps(
    {
        "name": "Tsardom of Moscavia",
        "facts": [
            {"category": "description", "text": "Fur caravans trade with Novgorod."},
            {
                "category": "history",
                "text": "The tsars once ruled from Novgorod's walls.",
                "since": 300,
            },
        ],
        "names": [],
    }
)


@pytest.fixture(autouse=True)
def shipped_lists():
    saved = config_state.get_config().name_lists
    config_state.get_config().name_lists = None
    yield
    config_state.get_config().name_lists = saved


@pytest.fixture
def moscavian(world):
    world.scenes().create("Opening", WorldDate.of(313))
    with world.revision(Source.manual()) as rev:
        return rev.create_thing(
            "language", {"name": "Moscavian", **fields_of(MOSCAVIAN)}
        )


def _queue(*replies):
    for reply in replies:
        client_responses.get().append(
            reply if isinstance(reply, str) else json.dumps(reply)
        )


ROLES = {"languages": [{"language": "Moscavian", "role": "official"}]}
PICKS = {"picks": [{"n": 1, "pick": "Sovyetsk", "meaning": "owl town"}]}


async def _preview(world, prompt="Tsardom of Moscavia, a cold realm", *replies):
    client = MockClient("test")
    async with MockClientContext():
        _queue(REPLY, *replies)
        preview = await preview_thing(world, "place", prompt, {}, client)
        left = list(client_responses.get())
        client_responses.get().clear()
    return preview, left


async def test_a_draft_with_a_language_in_reach_arrives_cleaned(world, moscavian):
    preview, left = await _preview(
        world, "Tsardom of Moscavia, a cold realm", ROLES, PICKS
    )
    assert left == []
    assert [f.text for f in preview.facts] == [
        "Fur caravans trade with Sovyetsk.",
        "The tsars once ruled from Sovyetsk's walls.",
    ]
    [mark] = preview.marks
    assert (mark.kind, mark.name, mark.was, mark.meaning) == (
        "replaced",
        "Sovyetsk",
        "Novgorod",
        "owl town",
    )
    assert [(n.name, n.kind, n.replaced) for n in preview.new_names] == [
        ("Sovyetsk", "place", "Novgorod")
    ]


async def test_the_draft_finds_its_language_from_the_prompt(world, moscavian):
    preview, _ = await _preview(
        world, "Tsardom of Moscavia, a cold realm", ROLES, PICKS
    )
    assert preview.languages == [
        {"language": moscavian, "role": "official", "from_words": True}
    ]


async def test_no_language_named_or_in_reach_replaces_nothing(world, moscavian):
    preview, left = await _preview(world, "a cold northern realm")
    assert left == []
    assert "Novgorod" in preview.facts[0].text
    assert [(m.kind, m.why) for m in preview.marks] == [
        ("suspect", "no language picked")
    ]
    assert preview.languages == []


async def test_a_world_without_languages_is_not_cleaned(world):
    world.scenes().create("Opening", WorldDate.of(313))
    preview, left = await _preview(world, "a cold northern realm")
    assert left == [] and preview.marks == []


async def test_the_draft_has_no_prose(world, moscavian):
    preview, _ = await _preview(
        world, "Tsardom of Moscavia, a cold realm", ROLES, PICKS
    )
    assert preview.prose == {}


async def test_changing_the_drafts_languages_cleans_it_again(world, moscavian):
    preview, _ = await _preview(world, "a cold northern realm")
    async with MockClientContext():
        _queue(PICKS)
        again = await clean_preview(
            world, unclean_preview(preview), MockClient("t"),
            rows=[{"language": moscavian, "role": "official"}],
        )  # fmt: skip
        client_responses.get().clear()
    assert "Sovyetsk" in again.facts[0].text
    assert again.languages == [{"language": moscavian, "role": "official"}]
    assert [m.kind for m in again.marks] == ["replaced"]


async def test_unclean_puts_back_every_old_name(world, moscavian):
    preview, _ = await _preview(
        world, "Tsardom of Moscavia, a cold realm", ROLES, PICKS
    )
    back = unclean_preview(preview)
    assert back.facts[0].text == "Fur caravans trade with Novgorod."
    assert back.marks == [] and back.new_names == []


# --- accepting (Task 6) ------------------------------------------------------

from talemate.languages.entry import language_of  # noqa: E402
from talemate.worldplay.create import accept_preview  # noqa: E402


async def _cleaned(world):
    preview, _ = await _preview(
        world, "Tsardom of Moscavia, a cold realm", ROLES, PICKS
    )
    return preview


def _words(world, lid):
    return {e.word: e.meanings for e in language_of(world.view().thing(lid)).dictionary}


async def test_accept_writes_the_drafts_languages(world, moscavian):
    thing_id = accept_preview(world, await _cleaned(world))
    rows = world.view().thing(thing_id).fields["languages"]
    assert [(r["language"], r["role"]) for r in rows] == [(moscavian, "official")]
    assert "from_words" not in rows[0]


async def test_accept_saves_each_new_name_as_a_word(world, moscavian):
    accept_preview(world, await _cleaned(world))
    assert _words(world, moscavian) == {"Sovyetsk": ["owl town"]}


async def test_a_name_edited_out_before_accept_is_not_saved(world, moscavian):
    preview = await _cleaned(world)
    facts = [
        f.model_copy(update={"text": "Fur caravans trade widely."})
        for f in preview.facts
    ]
    preview = preview.model_copy(update={"facts": facts, "new_names": []})
    accept_preview(world, preview)
    assert _words(world, moscavian) == {}


async def test_the_description_is_scheduled_on_accept(world, moscavian):
    prose: list[str] = []
    thing_id = accept_preview(world, await _cleaned(world), prose=prose)
    assert prose == [thing_id]


async def test_accept_is_one_revision(world, moscavian):
    head = world.head_rev()
    accept_preview(world, await _cleaned(world))
    assert world.head_rev() == head + 1
