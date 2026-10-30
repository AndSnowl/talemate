"""Cleaning names in Add facts drafts (languages 4a, Task 8): the entry's
languages (or ones the owner's words name) replace real names in the
drafted facts; accepting saves the new names as words."""

import json

import pytest

import talemate.config.state as config_state
from conftest import MockClient, MockClientContext, client_responses
from talemate.languages.entry import fields_of, language_of
from talemate.languages.models import GeneratorDef, Language
from talemate.world.store import Source
from talemate.worldplay.cleaning import clean_fact_draft
from talemate.worldplay.create import PreviewFact
from talemate.worldplay.facts import FactDraft, accept_facts

PLACES = ["Zizhigrad", "Sovyetsk", "Lezhograd"]
MOSCAVIAN = Language(
    name="Moscavian",
    level="naming",
    categories={"C": "k", "V": "a"},
    generators=[
        GeneratorDef(
            id="places", name="Places", use="place", patterns=[f"[{'|'.join(PLACES)}]"]
        )
    ],
)
PICKS = {"picks": [{"n": 1, "pick": "Sovyetsk", "meaning": "owl town"}]}


@pytest.fixture(autouse=True)
def shipped_lists():
    saved = config_state.get_config().name_lists
    config_state.get_config().name_lists = None
    yield
    config_state.get_config().name_lists = saved


@pytest.fixture
def setup(world):
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing(
            "language", {"name": "Moscavian", **fields_of(MOSCAVIAN)}
        )
        speaking = rev.create_thing(
            "place",
            {"name": "Sorau", "languages": [{"language": lid, "role": "official"}]},
        )
        silent = rev.create_thing("place", {"name": "Thornfield"})
    return lid, speaking, silent


def _draft(thing_id, text="Its traders winter in Novgorod."):
    return FactDraft(
        thing_id=thing_id,
        prompt="its trade",
        facts=[PreviewFact(category="description", text=text)],
    )


async def _clean(world, draft, *replies):
    async with MockClientContext():
        for reply in replies:
            client_responses.get().append(json.dumps(reply))
        return await clean_fact_draft(world, draft, MockClient("t"))


async def test_add_facts_cleans_real_names(world, setup):
    lid, speaking, _ = setup
    cleaned = await _clean(world, _draft(speaking), PICKS)
    assert cleaned.facts[0].text == "Its traders winter in Sovyetsk."
    assert [(m.kind, m.was, m.language_id) for m in cleaned.marks] == [
        ("replaced", "Novgorod", lid)
    ]
    assert [(n.name, n.replaced) for n in cleaned.new_names] == [
        ("Sovyetsk", "Novgorod")
    ]


async def test_add_facts_without_a_language_marks_suspect_only(world, setup):
    _, _, silent = setup
    cleaned = await _clean(world, _draft(silent))
    assert cleaned.facts[0].text == "Its traders winter in Novgorod."
    assert [(m.kind, m.why) for m in cleaned.marks] == [
        ("suspect", "no language picked")
    ]


async def test_the_owners_words_name_a_language(world, setup):
    _, _, silent = setup
    draft = _draft(silent).model_copy(update={"prompt": "its Moscavian traders"})
    cleaned = await _clean(world, draft, PICKS)
    assert cleaned.facts[0].text == "Its traders winter in Sovyetsk."


async def test_accepting_added_facts_saves_the_words(world, setup):
    lid, speaking, _ = setup
    cleaned = await _clean(world, _draft(speaking), PICKS)
    accept_facts(world, cleaned)
    words = {
        e.word: e.meanings for e in language_of(world.view().thing(lid)).dictionary
    }
    assert words == {"Sovyetsk": ["owl town"]}
