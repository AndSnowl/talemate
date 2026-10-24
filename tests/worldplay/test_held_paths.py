"""Held facts reach every prompt worded as held ("<Holder> holds that ..."),
never as world truth: the remaining prompt paths of the final re-review
(group synopsis stubs, the same-thing check, "+ Add facts" on an entry
and on a draft, a section's prose background, the homes block)."""

import json
from types import SimpleNamespace

import pytest

from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.worldplay import decide, facts, groups, prose_gen
from talemate.worldplay.create import CreatePreview, homes_block

from conftest import MockClient, MockClientContext, client_responses

CHURCH = "Church of the Deep"


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


@pytest.fixture
def deep(world):
    """The Church of the Deep (a faith) and its beliefs, one naming the
    stub Veles, who is filed in the Pantheon as a god and whose own fact
    the church holds; the Rite of Rain filed in the church, its first fact
    the church's belief; Brother Oren, whose background the church holds."""

    s = SimpleNamespace()
    with world.revision(Source.manual(note="setup")) as rev:
        s.pantheon = rev.create_thing("lore", {"name": "The Pantheon"})
        s.veles = rev.create_thing(
            "being",
            {
                "name": "Veles",
                "tag": "god",
                "stub": {"ignored": False},
                "filings": [{"target": s.pantheon}],
            },
        )
        s.church = rev.create_thing(
            "lore", {"name": CHURCH, "tag": "faith", "hint": "religion"}
        )
        rev.add_fact(s.church, "belief", "The drowned are reborn.")
        rev.add_fact(
            s.church, "belief", f"{ref(s.veles, 'Veles')} wept the rivers into being."
        )
        rev.add_fact(s.church, "general", "Its priests wear green.")
        rev.add_fact(
            s.veles,
            "nature",
            "Veles sleeps beneath the lake.",
            origin={"held_by": s.church},
        )
        s.rite = rev.create_thing(
            "lore",
            {"name": "Rite of Rain", "tag": "rite", "filings": [{"target": s.church}]},
        )
        rev.add_fact(
            s.rite, "general", "Rain answers the rite.", origin={"held_by": s.church}
        )
        s.oren = rev.create_thing("character", {"name": "Brother Oren"})
        rev.add_fact(
            s.oren,
            "background",
            "His touch healed a blind child.",
            origin={"held_by": s.church},
        )
        rev.add_fact(s.oren, "personality", "Gentle and slow to anger.")
    s.world = world
    return s


def _prompt(client, index: int = 0) -> str:
    return str(client.prompt_history[index]["prompt"])


async def test_group_synopsis_stub_mentions_are_held(deep):
    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps({"synopsis": "The Pantheon's gods."}))
        await groups.group_synopsis(deep.world, deep.pantheon, "god", client)
    prompt = _prompt(client)
    assert (
        f"(stub) mentioned by {CHURCH}: {CHURCH} holds that Veles wept the "
        "rivers into being." in prompt
    )
    assert f"{CHURCH}: Veles wept" not in prompt


async def test_same_thing_candidate_facts_are_held(deep):
    client = MockClient("test")
    label = decide.preview_label("The Deep Faith", "lore")
    async with MockClientContext():
        _queue('{"verdict": "different", "why": "no"}')
        await decide.same_thing(
            deep.world, label, ["A faith of the rivers."], deep.church, client
        )
    prompt = _prompt(client)
    assert f"{CHURCH} holds that the drowned are reborn." in prompt
    assert "Its priests wear green." in prompt
    assert "- The drowned are reborn." not in prompt


async def test_add_facts_known_facts_are_held(deep):
    client = MockClient("test")
    async with MockClientContext():
        _queue(
            json.dumps(
                {"facts": [{"category": "general", "text": "Its bells are bronze."}]}
            )
        )
        await facts.draft_facts(deep.world, deep.church, "its bells", client)
    prompt = _prompt(client)
    assert f"{CHURCH} holds that the drowned are reborn." in prompt
    assert "The drowned are reborn." not in prompt.replace(
        f"{CHURCH} holds that the drowned are reborn.", ""
    )


async def test_add_facts_on_a_stubs_draft_knows_its_facts_as_held(deep):
    preview = CreatePreview(
        kind="being",
        prompt="the river god",
        name="Veles",
        facts=[],
        prose={},
        stub_id=deep.veles,
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps({"facts": [{"category": "nature", "text": "He has horns."}]}))
        await facts.draft_facts_for(deep.world, preview, "his horns", client)
    prompt = _prompt(client)
    assert f"{CHURCH} holds that Veles sleeps beneath the lake." in prompt


async def test_prose_background_facts_are_held(deep):
    client = MockClient("test")
    async with MockClientContext():
        _queue("Brother Oren is gentle.")
        await prose_gen.generate_section(
            deep.world, deep.oren, "personality", None, client
        )
    prompt = _prompt(client)
    assert f"{CHURCH} holds that his touch healed a blind child." in prompt
    assert "His touch healed a blind child." not in prompt


async def test_homes_block_filed_entry_line_is_held(deep):
    view = deep.world.view()
    (block,), _labels = homes_block(view, [deep.church])
    lines = [line for _label, line in block[2]]
    # "holds:" -- the text has no subject of its own (`held_text`, ruling C6)
    assert f"Rite of Rain (rite): {CHURCH} holds: Rain answers the rite." in lines
