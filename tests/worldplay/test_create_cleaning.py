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
from talemate.worldplay.cleaning import clean_preview
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


async def _preview(world, prompt="Tsardom of Moscavia, a cold realm", *replies):
    client = MockClient("test")
    async with MockClientContext():
        _queue(REPLY, *replies)
        preview = await preview_thing(world, "place", prompt, {}, client)
        left = list(client_responses.get())
        client_responses.get().clear()
    return preview, left


async def test_a_draft_arrives_unchanged_with_marks(world, moscavian):
    """4a revised: the text is exactly the model's; Novgorod is marked."""

    preview, left = await _preview(world, "Tsardom of Moscavia, a cold realm", ROLES)
    assert left == []
    assert [f.text for f in preview.facts] == [
        "Fur caravans trade with Novgorod.",
        "The tsars once ruled from Novgorod's walls.",
    ]
    assert [(m.name, m.why) for m in preview.marks] == [
        ("Novgorod", "a real name, on the Real names list")
    ]
    assert preview.new_names == []


async def test_the_draft_finds_its_language_from_the_prompt(world, moscavian):
    preview, _ = await _preview(world, "Tsardom of Moscavia, a cold realm", ROLES)
    assert preview.languages == [
        {"language": moscavian, "role": "official", "from_words": True}
    ]


async def test_no_language_named_or_in_reach_marks_list_hits(world, moscavian):
    preview, left = await _preview(world, "a cold northern realm")
    assert left == []
    assert [(m.name, m.why) for m in preview.marks] == [
        ("Novgorod", "no language picked")
    ]
    assert preview.languages == []


async def test_a_world_without_languages_is_not_cleaned(world):
    world.scenes().create("Opening", WorldDate.of(313))
    preview, left = await _preview(world, "a cold northern realm")
    assert left == [] and preview.marks == []


async def test_the_draft_has_no_prose(world, moscavian):
    preview, _ = await _preview(world, "Tsardom of Moscavia, a cold realm", ROLES)
    assert preview.prose == {}


async def test_changing_languages_remarks_and_keeps_kept_names(world, moscavian):
    preview, _ = await _preview(world, "a cold northern realm")
    async with MockClientContext():
        again = await clean_preview(
            world, preview, MockClient("t"),
            rows=[{"language": moscavian, "role": "official"}], keep={"Novgorod"},
        )  # fmt: skip
    assert again.marks == []
    assert again.languages == [{"language": moscavian, "role": "official"}]


# --- accepting (Task 6) ------------------------------------------------------

from talemate.languages.entry import language_of  # noqa: E402
from talemate.worldplay.create import accept_preview  # noqa: E402


async def _cleaned(world):
    preview, _ = await _preview(world, "Tsardom of Moscavia, a cold realm", ROLES)
    return preview


def _words(world, lid):
    return {e.word: e.meanings for e in language_of(world.view().thing(lid)).dictionary}


async def test_accept_writes_the_drafts_languages(world, moscavian):
    thing_id = accept_preview(world, await _cleaned(world))
    rows = world.view().thing(thing_id).fields["languages"]
    assert [(r["language"], r["role"]) for r in rows] == [(moscavian, "official")]
    assert "from_words" not in rows[0]


async def test_accept_saves_no_words(world, moscavian):
    """Words go into the language when the owner names something (Name
    it…), not on accept."""

    accept_preview(world, await _cleaned(world))
    assert _words(world, moscavian) == {}


async def test_the_description_is_scheduled_on_accept(world, moscavian):
    prose: list[str] = []
    thing_id = accept_preview(world, await _cleaned(world), prose=prose)
    assert prose == [thing_id]


async def test_accept_is_one_revision(world, moscavian):
    head = world.head_rev()
    accept_preview(world, await _cleaned(world))
    assert world.head_rev() == head + 1
