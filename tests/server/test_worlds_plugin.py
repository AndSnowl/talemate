"""The `worlds` websocket router: worlds, things, facts, prose and create.

Driven through the plugin's `handle`, with a stand-in websocket handler
that collects what the plugin queues.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

import talemate.instance as instance
from talemate.server.worlds import WorldsPlugin
from talemate.scene_message import NarratorMessage
from talemate.tale_mate import Actor
from talemate.world import entries
from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.scenes import MessageRecord
from talemate.world.filing import filings_of
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.create import CreatePreview, PreviewFact
from talemate.worldplay.context import WorldSceneContext
from talemate.worldplay.persistence import WorldSceneRef

from conftest import (
    MockClient,
    MockClientContext,
    MockScene,
    bootstrap_scene,
    client_responses,
)
from world.embedding import TrigramEmbeddingFunction, requires_chromadb


class _Handler:
    """Minimal handler stand-in: no scene, a queue_put collector."""

    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture
def client():
    mock = MockClient("test")
    instance.AGENTS["creator"] = SimpleNamespace(client=mock)
    return mock


@pytest.fixture
def plugin(tmp_path, client):
    handler = _Handler()
    plug = WorldsPlugin(handler)
    plug.worlds_root = tmp_path
    yield plug
    plug.disconnect()


def _replies(plugin, action):
    return [
        m
        for m in plugin.websocket_handler.messages
        if m["type"] == "worlds" and m["action"] == action
    ]


def _last(plugin, action):
    replies = _replies(plugin, action)
    assert replies, f"no {action!r} reply in {plugin.websocket_handler.messages}"
    return replies[-1]


async def _drain(plugin):
    while plugin.tasks:
        await asyncio.gather(*list(plugin.tasks), return_exceptions=True)


async def _open_world_with_maren(plugin):
    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Vael"})
    world = plugin.world
    with world.revision(Source.manual(note="seed")) as rev:
        maren = rev.create_thing("character", {"name": "Maren"})
        rev.add_fact(maren, "appearance", "Tall and grey-eyed.")
        rev.add_fact(
            maren, "appearance", "Lost her left eye.", valid_from=WorldDate.of(314)
        )
        harbour = rev.create_thing("place", {"name": "The Harbour"})
    return world, maren, harbour


async def test_router_list_and_get_thing(plugin):
    world, maren, harbour = await _open_world_with_maren(plugin)
    created = _last(plugin, "create_world")["data"]
    assert created["name"] == "Vael"
    assert created["id"] == world.id

    await plugin.handle({"type": "worlds", "action": "list_worlds"})
    worlds = _last(plugin, "list_worlds")["data"]["worlds"]
    assert [w["name"] for w in worlds] == ["Vael"]

    await plugin.handle(
        {"type": "worlds", "action": "list_things", "kind": "character"}
    )
    listed = _last(plugin, "list_things")["data"]
    assert listed["kind"] == "character"
    assert listed["things"] == [{"id": maren, "kind": "character", "name": "Maren"}]

    scene_id = world.scenes().create(
        "At the harbour", WorldDate.of(313), player_thing_id=maren
    )

    await plugin.handle(
        {
            "type": "worlds",
            "action": "get_thing",
            "id": maren,
            "at": WorldDate.of(313).model_dump(),
        }
    )
    thing = _last(plugin, "get_thing")["data"]
    assert thing["id"] == maren
    assert thing["kind"] == "character"
    assert thing["name"] == "Maren"
    assert thing["fields"]["name"] == "Maren"
    # as of 313 the eye fact hasn't started yet
    assert [f["text"] for f in thing["facts"]] == ["Tall and grey-eyed."]
    assert set(thing["prose"]) == {"description", "personality"}
    assert thing["prose"]["description"] == {
        "text": None,
        "stale": True,
        "edited": False,
    }
    # the timeline is the whole history, not just what's true at 313
    assert {e["text"] for e in thing["timeline"] if e["change"] == "fact_start"} == {
        "Tall and grey-eyed.",
        "Lost her left eye.",
    }
    eye = next(e for e in thing["timeline"] if e["text"] == "Lost her left eye.")
    assert eye["date"]["label"] == "314"
    assert thing["appears_in"] == [
        {
            "id": scene_id,
            "name": "At the harbour",
            "start": thing["appears_in"][0]["start"],
        }
    ]
    assert thing["appears_in"][0]["start"]["label"] == "313"
    # the reply is plain JSON
    json.dumps(plugin.websocket_handler.messages)


async def test_open_world_by_path(plugin, tmp_path):
    other = World.create("Other", root=tmp_path)
    other_path = str(other.path)
    other.close()

    await plugin.handle({"type": "worlds", "action": "open_world", "path": other_path})
    assert _last(plugin, "open_world")["data"]["name"] == "Other"
    assert plugin.world.name == "Other"


async def test_open_world_outside_root_is_refused(plugin, tmp_path_factory):
    elsewhere = World.create("Elsewhere", root=tmp_path_factory.mktemp("elsewhere"))
    path = str(elsewhere.path)
    elsewhere.close()

    await plugin.handle({"type": "worlds", "action": "open_world", "path": path})
    assert _replies(plugin, "open_world") == []
    assert _last(plugin, "operation_done")["error"]
    assert plugin.world is None


async def test_add_fact_schedules_prose(plugin, client):
    world, maren, _ = await _open_world_with_maren(plugin)

    async with MockClientContext():
        client_responses.get().append("Maren is tall, with one eye.")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "add_fact",
                "thing_id": maren,
                "category": "appearance",
                "text": "A heron tattoo on her wrist.",
                "valid_from": None,
            }
        )
        reply = _last(plugin, "add_fact")["data"]
        assert "A heron tattoo on her wrist." in [f["text"] for f in reply["facts"]]
        assert plugin.tasks, "no prose task was scheduled"
        await _drain(plugin)

    assert _last(plugin, "prose_updated")["data"] == {"id": maren}
    cache = world.prose()
    assert cache.get(maren, "description", None).text == "Maren is tall, with one eye."
    assert cache.stale(maren, "description", None) is False
    # personality has no facts: no model call, empty prose
    assert cache.get(maren, "personality", None).text == ""
    assert len(client.prompt_history) == 1


async def test_add_fact_prose_task_skips_quietly_if_thing_deleted(plugin, client):
    """Review-round fix: a thing deleted while its prose task is still
    queued (an edit schedules it in the background; the owner deletes the
    thing before it runs) must not surface "Error generating world prose"
    after a successful delete -- the task is skipped quietly."""

    world, maren, _ = await _open_world_with_maren(plugin)

    async with MockClientContext():
        await plugin.handle(
            {
                "type": "worlds",
                "action": "add_fact",
                "thing_id": maren,
                "category": "appearance",
                "text": "A heron tattoo on her wrist.",
                "valid_from": None,
            }
        )
        assert plugin.tasks, "no prose task was scheduled"

        await plugin.handle({"type": "worlds", "action": "delete_thing", "id": maren})
        await _drain(plugin)

    assert _replies(plugin, "prose_failed") == []
    assert _last(plugin, "thing_deleted")["data"] == {"id": maren, "kind": "character"}
    assert world.view().thing(maren) is None


async def test_remove_fact_makes_prose_stale_and_regenerates(plugin, client):
    world, maren, _ = await _open_world_with_maren(plugin)
    tall = next(
        f.fact_id for f in world.view().thing(maren).facts if f.text.startswith("Tall")
    )

    async with MockClientContext():
        client_responses.get().append("Maren is tall, with one eye.")
        await plugin.handle(
            {"type": "worlds", "action": "regenerate_prose", "id": maren, "at": None}
        )
        await _drain(plugin)
        assert world.prose().get(maren, "description", None).text == (
            "Maren is tall, with one eye."
        )

        client_responses.get().append("Maren is left with one eye.")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "remove_fact",
                "thing_id": maren,
                "fact_id": tall,
            }
        )
        reply = _last(plugin, "remove_fact")["data"]
        assert "Tall and grey-eyed." not in [f["text"] for f in reply["facts"]]
        await _drain(plugin)

    assert (
        world.prose().get(maren, "description", None).text
        == "Maren is left with one eye."
    )
    assert len(_replies(plugin, "prose_updated")) == 2


async def test_regenerate_one_prose_section(plugin, client):
    """`regenerate_prose` with a `section` rewrites only that section; the
    others keep their cached text."""

    world, maren, _ = await _open_world_with_maren(plugin)
    with world.revision(Source.manual()) as rev:
        rev.add_fact(maren, "personality", "Dry and patient.")

    async with MockClientContext():
        client_responses.get().extend(["Maren is tall.", "Maren is patient."])
        await plugin.handle(
            {"type": "worlds", "action": "regenerate_prose", "id": maren}
        )
        await _drain(plugin)

        client_responses.get().append("Maren is patient, and dry with it.")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "regenerate_prose",
                "id": maren,
                "section": "personality",
            }
        )
        await _drain(plugin)

    prose = world.prose()
    assert prose.get(maren, "description", None).text == "Maren is tall."
    assert prose.get(maren, "personality", None).text == (
        "Maren is patient, and dry with it."
    )
    assert _last(plugin, "prose_updated")["data"] == {
        "id": maren,
        "section": "personality",
    }


async def test_regenerate_refuses_a_section_the_kind_lacks(plugin, client):
    world, _, harbour = await _open_world_with_maren(plugin)

    await plugin.handle(
        {
            "type": "worlds",
            "action": "regenerate_prose",
            "id": harbour,
            "section": "personality",
        }
    )

    assert "personality" in _last(plugin, "operation_done")["error"]["message"]
    assert not plugin.tasks


async def test_correct_end_and_set_field(plugin, client):
    world, maren, _ = await _open_world_with_maren(plugin)
    tall = next(
        f.fact_id for f in world.view().thing(maren).facts if f.text.startswith("Tall")
    )

    async with MockClientContext():
        await plugin.handle(
            {
                "type": "worlds",
                "action": "correct_fact",
                "thing_id": maren,
                "fact_id": tall,
                "text": "Tall, grey-eyed and broad.",
            }
        )
        await plugin.handle(
            {
                "type": "worlds",
                "action": "end_fact",
                "thing_id": maren,
                "fact_id": tall,
                "until": WorldDate.of(320).model_dump(),
            }
        )
        await plugin.handle(
            {
                "type": "worlds",
                "action": "set_field",
                "thing_id": maren,
                "field": "name",
                "value": "Maren Vos",
                "valid_from": None,
            }
        )
        await _drain(plugin)

    fact = next(
        f for f in world.view(WorldDate.of(315)).thing(maren).facts if f.fact_id == tall
    )
    assert fact.text == "Tall, grey-eyed and broad."
    assert fact.valid_until == WorldDate.of(320)
    assert _last(plugin, "set_field")["data"]["name"] == "Maren Vos"
    assert len(_replies(plugin, "prose_updated")) == 3


async def test_rename_corrects_the_name_in_effect(plugin, client):
    """A rename is `set_field` "name" at the `valid_from` of the name in
    effect (what the thing page sends): it corrects that value in place,
    leaving an earlier name as it was, and the kind's list shows it."""

    world, maren, _ = await _open_world_with_maren(plugin)
    with world.revision(Source.manual()) as rev:
        rev.set_field(maren, "name", "Maren Holt", WorldDate.of(316))
    timeline = [e for e in world.timeline(maren) if e.field == "name"]
    renamed_at = timeline[-1].date
    assert renamed_at == WorldDate.of(316)

    await plugin.handle(
        {
            "type": "worlds",
            "action": "set_field",
            "thing_id": maren,
            "field": "name",
            "value": "Maren Dell",
            "valid_from": renamed_at.model_dump(),
        }
    )
    await _drain(plugin)

    assert _last(plugin, "set_field")["data"]["name"] == "Maren Dell"
    assert world.view(WorldDate.of(315)).name_of(maren) == "Maren"
    assert [e.value for e in world.timeline(maren) if e.field == "name"] == [
        "Maren",
        "Maren Dell",
    ]
    await plugin.handle(
        {"type": "worlds", "action": "list_things", "kind": "character"}
    )
    names = [t["name"] for t in _last(plugin, "list_things")["data"]["things"]]
    assert names == ["Maren Dell"]


async def test_correct_fact_dates_unset_keeps_null_opens(plugin, client):
    world, maren, _ = await _open_world_with_maren(plugin)
    eye = next(
        f.fact_id for f in world.view().thing(maren).facts if f.text.startswith("Lost")
    )

    def eye_row():
        return next(
            e
            for e in world.timeline(maren)
            if e.fact_id == eye and e.change == "fact_start"
        )

    async with MockClientContext():
        # valid_from left out: kept at 314
        await plugin.handle(
            {
                "type": "worlds",
                "action": "correct_fact",
                "thing_id": maren,
                "fact_id": eye,
                "valid_until": WorldDate.of(330).model_dump(),
            }
        )
        assert eye_row().date == WorldDate.of(314)
        fact = next(
            f
            for f in world.view(WorldDate.of(320)).thing(maren).facts
            if f.fact_id == eye
        )
        assert fact.valid_until == WorldDate.of(330)

        # valid_from sent as null: the start is opened ("always")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "correct_fact",
                "thing_id": maren,
                "fact_id": eye,
                "valid_from": None,
            }
        )
        await _drain(plugin)

    assert eye_row().date is None
    fact = next(
        f for f in world.view(WorldDate.of(320)).thing(maren).facts if f.fact_id == eye
    )
    assert fact.valid_from is None
    # valid_until left out the second time: still 330
    assert fact.valid_until == WorldDate.of(330)


async def test_present_defaults_and_can_be_set(plugin, client):
    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Vael"})
    created = _last(plugin, "create_world")["data"]
    assert created["present"]["label"] == "1000"
    assert created["now"]["label"] == "1000"

    await plugin.handle(
        {"type": "worlds", "action": "create_world", "name": "Old", "present_year": 313}
    )
    assert _last(plugin, "create_world")["data"]["present"]["label"] == "313"

    await plugin.handle({"type": "worlds", "action": "set_present", "year": 320})
    assert _last(plugin, "set_present")["data"]["present"]["label"] == "320"
    await plugin.handle({"type": "worlds", "action": "get_present"})
    got = _last(plugin, "get_present")["data"]
    assert got["present"]["label"] == "320"
    assert got["now"]["label"] == "320"
    assert plugin.world.present() == WorldDate.of(320)


async def test_set_present_moves_preview_now(plugin, client):
    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Vael"})
    await plugin.handle({"type": "worlds", "action": "set_present", "year": 500})
    reply = json.dumps(
        {
            "name": "Tam",
            "age": 60,
            "facts": [{"category": "background", "text": "A ferryman."}],
        }
    )
    async with MockClientContext():
        client_responses.get().append(reply)
        client_responses.get().append("Tam ferries.")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "character",
                "prompt": "an old ferryman",
                "fields": {},
            }
        )
        await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert preview["fields"]["born"] == WorldDate.of(440).model_dump(mode="json")


async def test_preview_then_accept(plugin, client):
    world, _, _ = await _open_world_with_maren(plugin)
    head = world.head_rev()
    reply = json.dumps(
        {
            "name": "Lowmere",
            "facts": [{"category": "description", "text": "Half flooded."}],
        }
    )

    async with MockClientContext():
        client_responses.get().append(reply)
        client_responses.get().append("Lowmere is half under water.")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "place",
                "prompt": "a half-flooded town",
                "fields": {},
            }
        )
        await _drain(plugin)

    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert preview["name"] == "Lowmere"
    assert world.head_rev() == head
    json.dumps(preview)

    await plugin.handle(
        {"type": "worlds", "action": "accept_preview", "preview": preview}
    )
    accepted = _last(plugin, "accept_preview")["data"]
    assert world.head_rev() == head + 1
    assert accepted["name"] == "Lowmere"
    assert accepted["prose"]["description"]["text"] == "Lowmere is half under water."
    assert accepted["prose"]["description"]["stale"] is False


async def test_preview_failure_is_reported(plugin, client):
    await _open_world_with_maren(plugin)
    async with MockClientContext():
        client_responses.get().append("no json here")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "lore",
                "prompt": "a river treaty",
                "fields": {},
            }
        )
        await _drain(plugin)

    failed = _last(plugin, "preview_failed")
    assert "no facts" in failed["message"]


async def test_fixed_preview_setting_answers_without_a_model(
    plugin, client, tmp_path, monkeypatch
):
    """TALEMATE_TEST_FIXED_PREVIEW (e2e only) names a file that
    `preview_thing` answers from, with the request's kind, prompt and
    fields, instead of asking the model."""

    world, _, _ = await _open_world_with_maren(plugin)
    fixed = tmp_path / "fixed-preview.json"
    fixed.write_text(
        json.dumps(
            {
                "name": "Oskar Dell",
                "facts": [{"category": "background", "text": "A ferryman."}],
                "prose": {"description": "A weathered ferryman.", "personality": ""},
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(fixed))
    born = WorldDate.of(270).model_dump(mode="json")

    await plugin.handle(
        {
            "type": "worlds",
            "action": "preview_thing",
            "kind": "character",
            "prompt": "a grizzled ferryman",
            "fields": {"born": born},
        }
    )
    await _drain(plugin)

    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert preview["kind"] == "character"
    assert preview["prompt"] == "a grizzled ferryman"
    assert preview["fields"] == {"born": born}
    assert preview["name"] == "Oskar Dell"
    assert preview["prose"]["description"] == "A weathered ferryman."
    assert client.prompt_history == []

    await plugin.handle(
        {"type": "worlds", "action": "accept_preview", "preview": preview}
    )
    assert _last(plugin, "accept_preview")["data"]["name"] == "Oskar Dell"


async def test_fixed_preview_lists_what_it_inherits(plugin, tmp_path, monkeypatch):
    """The fixed preview carries the inherited facts of its heritage, like
    the real one, so the browser tests can mark one as overridden."""

    h = await _open_heritage_world(plugin)
    fixed = tmp_path / "fixed-preview.json"
    fixed.write_text(
        json.dumps(
            {
                "name": "Gorra",
                "facts": [{"category": "appearance", "text": "Small tusks."}],
                "prose": {"description": "Gorra.", "personality": ""},
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(fixed))

    await plugin.handle(
        {
            "type": "worlds",
            "action": "preview_thing",
            "kind": "character",
            "prompt": "a half-orc smith",
            "fields": {"heritage": h.half_orc},
        }
    )
    await _drain(plugin)

    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert [(row["fact_id"], row["source"]) for row in preview["inherited"]] == [
        (h.short, "Lowlander"),
        (h.bare_skin, "Human"),
        (h.tusks, "Orc"),
    ]

    # an override the owner marked in the preview is written on accept
    preview["facts"][0]["overrides"] = [h.tusks]
    await plugin.handle(
        {"type": "worlds", "action": "accept_preview", "preview": preview}
    )
    gorra = _last(plugin, "accept_preview")["data"]
    tusks = next(row for row in gorra["inherited"] if row["fact_id"] == h.tusks)
    assert tusks["overridden_by"] is not None


async def test_edits_without_a_client_leave_prose_stale(plugin, monkeypatch):
    """With no AI client on the creator agent, an edit stands and its prose
    refresh is skipped; an explicit regenerate is refused."""

    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    world, maren, _ = await _open_world_with_maren(plugin)

    await plugin.handle(
        {
            "type": "worlds",
            "action": "add_fact",
            "thing_id": maren,
            "category": "appearance",
            "text": "A heron tattoo on her wrist.",
        }
    )
    assert _last(plugin, "add_fact")["data"]["prose"]["description"]["stale"]
    assert not plugin.tasks

    await plugin.handle({"type": "worlds", "action": "regenerate_prose", "id": maren})
    assert not plugin.tasks
    assert "client" in _last(plugin, "operation_done")["error"]["message"].lower()


@pytest.mark.parametrize(
    "request_data",
    [
        {"action": "plan_scene", "prompt": "Maren goes", "player": None},
        {"action": "continue_scene", "scene_id": "SCENE", "goal_prompt": "Onward"},
        {"action": "preview_thing", "kind": "character", "prompt": "a smith"},
        {"action": "add_facts", "thing_id": "MAREN", "prompt": "her ship"},
        {"action": "add_event", "thing_id": "MAREN", "prompt": "a storm", "year": 312},
    ],
)
async def test_model_actions_say_when_no_ai_client_is_configured(
    plugin, monkeypatch, tmp_path, request_data
):
    """As in the browser tests: no client, and the fixed-reply settings
    naming files that aren't there (no test has written one)."""

    monkeypatch.setenv("TALEMATE_TEST_FIXED_SETUP", str(tmp_path / "no-setup.json"))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(tmp_path / "no-preview.json"))
    world, maren, _harbour = await _open_world_with_maren(plugin)
    monkeypatch.setenv("TALEMATE_TEST_FIXED_FACTS", str(tmp_path / "no-facts.json"))
    scene_id = world.scenes().create("First", WorldDate.of(313))
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))

    stand_ins = {"SCENE": scene_id, "MAREN": maren}
    data = {
        key: stand_ins.get(value, value) if isinstance(value, str) else value
        for key, value in request_data.items()
    }
    await plugin.handle({"type": "worlds", **data})
    await _drain(plugin)

    failed = {
        "plan_scene": "plan_failed",
        "continue_scene": "continue_failed",
        "preview_thing": "preview_failed",
        "add_facts": "add_facts_failed",
        "add_event": "add_event_failed",
    }[data["action"]]
    message = _last(plugin, failed)["message"]
    assert message == "No AI client is configured for the creator agent"


async def test_thing_actions_need_an_open_world(plugin):
    await plugin.handle({"type": "worlds", "action": "list_things", "kind": "place"})
    assert _replies(plugin, "list_things") == []
    assert "no world" in _last(plugin, "operation_done")["error"]["message"].lower()


# --- delete -------------------------------------------------------------------


async def test_thing_references_lists_what_uses_it(plugin):
    world, maren, harbour = await _open_world_with_maren(plugin)
    world.scenes().create("At the harbour", WorldDate.of(313), player_thing_id=maren)

    await plugin.handle({"type": "worlds", "action": "thing_references", "id": maren})

    reply = _last(plugin, "thing_references")["data"]
    assert reply["id"] == maren
    assert reply["name"] == "Maren"
    assert reply["references"]["scenes"] == [
        {
            "scene_id": world.scenes().list()[0].id,
            "name": "At the harbour",
            "role": "player",
        }
    ]
    assert reply["references"]["facts"] == []
    assert reply["references"]["fields"] == []


async def test_delete_thing_keeps_it_in_history(plugin):
    world, maren, harbour = await _open_world_with_maren(plugin)
    before = world.head_rev()

    await plugin.handle({"type": "worlds", "action": "delete_thing", "id": maren})

    assert _last(plugin, "thing_deleted")["data"] == {"id": maren, "kind": "character"}
    listed = _last(plugin, "list_things")["data"]
    assert listed == {"kind": "character", "things": []}
    assert world.view().thing(maren) is None
    # an ordinary manual revision: the thing is still there before it
    assert world.view(rev=before).thing(maren) is not None
    deleted = world.revisions()[-1]
    assert deleted.source.kind == "manual"
    assert deleted.source.note == "deleted Maren"


async def test_delete_unknown_thing_is_refused(plugin):
    world, *_ = await _open_world_with_maren(plugin)
    before = world.head_rev()

    await plugin.handle({"type": "worlds", "action": "delete_thing", "id": "0" * 32})

    assert _replies(plugin, "thing_deleted") == []
    assert _last(plugin, "operation_done")["error"]["message"]
    assert world.head_rev() == before


# --- heritage -----------------------------------------------------------------


class _Heritage(SimpleNamespace):
    pass


async def _open_heritage_world(plugin):
    """Human and Orc species, the Lowlander race of Human, a Half-orc mix
    of Lowlander and Orc, and Brenna, a Lowlander born 920 whose tattoos
    override Human's bare skin. The world's present is 1000."""

    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Vael"})
    world = plugin.world
    h = _Heritage(world=world)
    with world.revision(Source.manual(note="heritage")) as rev:
        h.human = rev.create_thing(
            "species",
            {
                "name": "Human",
                "lifespan": 75,
                "adult_age": 18,
                "measures": [{"name": "height", "min": 5, "max": 6.5, "unit": "ft"}],
            },
        )
        h.bare_skin = rev.add_fact(h.human, "physical", "Humans have bare skin.")
        h.orc = rev.create_thing(
            "species", {"name": "Orc", "lifespan": 60, "adult_age": 14}
        )
        h.tusks = rev.add_fact(h.orc, "physical", "Orcs have tusks.")
        h.lowlander = rev.create_thing(
            "race", {"name": "Lowlander", "species": h.human}
        )
        h.short = rev.add_fact(h.lowlander, "physical", "Lowlanders are short.")
        h.half_orc = rev.create_thing(
            "mix", {"name": "Half-orc", "parents": [h.lowlander, h.orc]}
        )
        h.brenna = rev.create_thing(
            "character",
            {"name": "Brenna", "born": WorldDate.of(920), "heritage": h.lowlander},
        )
        h.tattoos = rev.add_fact(
            h.brenna, "appearance", "Tattooed all over.", overrides=[h.bare_skin]
        )
    return h


async def _get_thing(plugin, thing_id, at=None):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "get_thing",
            "id": thing_id,
            "at": at.model_dump() if at is not None else None,
        }
    )
    return _last(plugin, "get_thing")["data"]


async def test_thing_payload_inherited_and_numbers(plugin):
    h = await _open_heritage_world(plugin)

    thing = await _get_thing(plugin, h.brenna)

    assert thing["inherited"] == [
        {
            "fact_id": h.short,
            "category": "physical",
            "rendered": "Lowlanders are short.",
            "segments": [{"text": "Lowlanders are short.", "ref": None, "stub": False}],
            "source_id": h.lowlander,
            "source_kind": "race",
            "source_name": "Lowlander",
            "overridden_by": None,
            "held_by": None,
        },
        {
            "fact_id": h.bare_skin,
            "category": "physical",
            "rendered": "Humans have bare skin.",
            "segments": [
                {"text": "Humans have bare skin.", "ref": None, "stub": False}
            ],
            "source_id": h.human,
            "source_kind": "species",
            "source_name": "Human",
            "overridden_by": h.tattoos,
            "held_by": None,
        },
    ]
    # the race sets no numbers: the species' resolve through it
    assert thing["numbers"] == {
        "lifespan": 75,
        "adult_age": 18,
        "measures": {"height": {"min": 5, "max": 6.5, "unit": "ft"}},
    }
    assert [f["overrides"] for f in thing["facts"]] == [[h.bare_skin]]
    # at the world's present (1000) she's 80: elder, and past the lifespan
    assert thing["life_stage"] == {"stage": "elder", "past_lifespan": True}
    json.dumps(thing)

    assert (await _get_thing(plugin, h.brenna, WorldDate.of(940)))["life_stage"] == {
        "stage": "adult",
        "past_lifespan": False,
    }
    assert (await _get_thing(plugin, h.brenna, WorldDate.of(932)))["life_stage"] == {
        "stage": "child",
        "past_lifespan": False,
    }
    # a thing with no `born` has no life stage
    assert (await _get_thing(plugin, h.lowlander))["life_stage"] is None


async def test_thing_payload_stale_follows_lineage(plugin):
    h = await _open_heritage_world(plugin)
    world = h.world
    for section in ("description", "personality"):
        start, end = prose_gen.stretch_containing(world, h.brenna, None)
        world.prose().put(
            h.brenna, section, start, end, "Brenna.", rev=world.head_rev()
        )
    assert (await _get_thing(plugin, h.brenna))["prose"]["description"][
        "stale"
    ] is False

    # a change to her species makes her prose stale
    with world.revision(Source.manual()) as rev:
        rev.add_fact(h.human, "instinct", "Humans seek company.")
    assert (await _get_thing(plugin, h.brenna))["prose"]["description"]["stale"] is True


async def test_thing_payload_with_deleted_ancestor(plugin):
    h = await _open_heritage_world(plugin)
    world = h.world
    start, end = prose_gen.stretch_containing(world, h.brenna, None)
    world.prose().put(
        h.brenna, "description", start, end, "Brenna.", rev=world.head_rev()
    )

    await plugin.handle({"type": "worlds", "action": "delete_thing", "id": h.lowlander})
    thing = await _get_thing(plugin, h.brenna)

    # the race and the species reached through it are gone from her page
    assert thing["inherited"] == []
    assert thing["numbers"] == {"lifespan": None, "adult_age": None, "measures": {}}
    assert thing["life_stage"] is None
    # deleting an ancestor counts as a change to her prose
    assert thing["prose"]["description"]["stale"] is True


async def test_species_payload_lists_races_and_mixes(plugin):
    h = await _open_heritage_world(plugin)

    human = await _get_thing(plugin, h.human)
    assert human["races"] == [{"id": h.lowlander, "name": "Lowlander"}]
    # a mix is listed on every species it descends from
    assert human["mixes"] == [{"id": h.half_orc, "name": "Half-orc"}]

    orc = await _get_thing(plugin, h.orc)
    assert orc["races"] == []
    assert orc["mixes"] == [{"id": h.half_orc, "name": "Half-orc"}]

    lowlander = await _get_thing(plugin, h.lowlander)
    assert lowlander["races"] == [] and lowlander["mixes"] == []

    await plugin.handle({"type": "worlds", "action": "list_things", "kind": "species"})
    listed = _last(plugin, "list_things")["data"]
    assert {t["name"] for t in listed["things"]} == {"Human", "Orc"}
    for kind, name in (("race", "Lowlander"), ("mix", "Half-orc")):
        await plugin.handle({"type": "worlds", "action": "list_things", "kind": kind})
        assert [t["name"] for t in _last(plugin, "list_things")["data"]["things"]] == [
            name
        ]


async def test_override_fact_action(plugin):
    h = await _open_heritage_world(plugin)
    world = h.world
    before = world.head_rev()

    await plugin.handle(
        {
            "type": "worlds",
            "action": "override_fact",
            "thing_id": h.brenna,
            "overridden_fact_id": h.short,
            "text": "Brenna is tall for a Lowlander.",
            "category": "appearance",
            "at": None,
        }
    )

    assert world.head_rev() == before + 1
    reply = _last(plugin, "override_fact")["data"]
    assert reply["id"] == h.brenna
    tall = next(f for f in reply["facts"] if f["text"].startswith("Brenna is tall"))
    assert tall["overrides"] == [h.short]
    short = next(f for f in reply["inherited"] if f["fact_id"] == h.short)
    assert short["overridden_by"] == tall["fact_id"]


async def test_override_fact_refuses_a_fact_not_inherited(plugin):
    h = await _open_heritage_world(plugin)
    world = h.world
    before = world.head_rev()

    # Orc isn't in a Lowlander's lineage
    await plugin.handle(
        {
            "type": "worlds",
            "action": "override_fact",
            "thing_id": h.brenna,
            "overridden_fact_id": h.tusks,
            "text": "No tusks.",
            "category": "appearance",
            "at": None,
        }
    )

    assert _replies(plugin, "override_fact") == []
    assert _last(plugin, "operation_done")["error"]["message"]
    assert world.head_rev() == before


async def test_find_mix_either_order(plugin):
    h = await _open_heritage_world(plugin)

    for parents in ([h.lowlander, h.orc], [h.orc, h.lowlander]):
        await plugin.handle(
            {"type": "worlds", "action": "find_mix", "parents": parents}
        )
        assert _last(plugin, "find_mix")["data"] == {
            "parents": parents,
            "mix_id": h.half_orc,
        }

    await plugin.handle(
        {"type": "worlds", "action": "find_mix", "parents": [h.human, h.orc]}
    )
    assert _last(plugin, "find_mix")["data"]["mix_id"] is None


async def test_list_heritage(plugin):
    h = await _open_heritage_world(plugin)

    await plugin.handle({"type": "worlds", "action": "list_heritage"})

    assert _last(plugin, "list_heritage")["data"] == {
        "things": [
            {
                "id": h.human,
                "kind": "species",
                "name": "Human",
                "species_ids": [h.human],
            },
            {"id": h.orc, "kind": "species", "name": "Orc", "species_ids": [h.orc]},
            {
                "id": h.lowlander,
                "kind": "race",
                "name": "Lowlander",
                "species_ids": [h.human],
            },
            {
                "id": h.half_orc,
                "kind": "mix",
                "name": "Half-orc",
                "species_ids": [h.human, h.orc],
            },
        ]
    }


async def test_member_scenes_in_referenced_in(plugin):
    h = await _open_heritage_world(plugin)
    scenes = h.world.scenes()
    # Brenna is both the player and a character here: listed once
    played = scenes.create(
        "The Ferry",
        WorldDate.of(990),
        player_thing_id=h.brenna,
        state={"characters": [{"thing_id": h.brenna}]},
    )
    scenes.create("Elsewhere", WorldDate.of(991))

    human = await _get_thing(plugin, h.human)

    referenced = human["referenced_in"]
    assert referenced["member_scenes"] == [
        {
            "id": played,
            "name": "The Ferry",
            "start": referenced["member_scenes"][0]["start"],
        }
    ]
    assert referenced["member_scenes"][0]["start"]["label"] == "990"
    # the race that names it as its species
    assert referenced["fields"] == [
        {"thing_id": h.lowlander, "thing_name": "Lowlander", "field": "species"}
    ]
    assert referenced["facts"] == [] and referenced["scenes"] == []


async def test_preview_race_through_router(plugin, client):
    h = await _open_heritage_world(plugin)
    reply = json.dumps(
        {
            "name": "Hillfolk",
            "facts": [{"category": "physical", "text": "Hillfolk are stocky."}],
            "no_longer_true": [],
        }
    )

    async with MockClientContext():
        client_responses.get().append(reply)
        client_responses.get().append("The Hillfolk are stocky humans.")
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "race",
                "prompt": "stocky hill people",
                "fields": {"species": h.human},
            }
        )
        await _drain(plugin)

    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert preview["name"] == "Hillfolk"
    assert preview["fields"]["species"] == h.human

    await plugin.handle(
        {"type": "worlds", "action": "accept_preview", "preview": preview}
    )
    accepted = _last(plugin, "accept_preview")["data"]
    assert accepted["kind"] == "race"
    assert accepted["fields"]["species"] == h.human
    assert [f["fact_id"] for f in accepted["inherited"]] == [h.bare_skin]
    assert accepted["numbers"]["lifespan"] == 75


# --- scenes -------------------------------------------------------------------


SETUP_REPLY = json.dumps(
    {
        "player": "Maren",
        "characters": [{"name": "Daveth", "world": False, "facts": ["A smuggler."]}],
        "place": {"name": "The Harbour", "world": True},
        "goal": "Meet the smuggler.",
        "intro": "Fog rolls over the harbour.",
    }
)


@pytest.fixture
def memory(monkeypatch):
    """A memory agent whose embedding function is the offline fake."""

    monkeypatch.setitem(
        instance.AGENTS,
        "memory",
        SimpleNamespace(embedding_function=TrigramEmbeddingFunction()),
    )


async def test_match_names_and_list_scenes(plugin):
    world, maren, harbour = await _open_world_with_maren(plugin)

    await plugin.handle(
        {
            "type": "worlds",
            "action": "match_names",
            "text": "maren's walk to the harbour",
            "at": None,
        }
    )
    matches = _last(plugin, "match_names")["data"]["matches"]
    assert [(m["text"], m["candidates"][0]["id"]) for m in matches] == [
        ("maren", maren),
        ("the harbour", harbour),
    ]

    # the reply echoes the lookup's text and date, so the screen can tell
    # which lookup it answers
    at = WorldDate.of(313).model_dump(mode="json")
    await plugin.handle(
        {"type": "worlds", "action": "match_names", "text": "Maren", "at": at}
    )
    echoed = _last(plugin, "match_names")["data"]
    assert (echoed["text"], echoed["at"]) == ("Maren", at)

    first = world.scenes().create("First", WorldDate.of(313))
    await plugin.handle({"type": "worlds", "action": "list_scenes"})
    scenes = _last(plugin, "list_scenes")["data"]["scenes"]
    assert [s["id"] for s in scenes] == [first]
    assert scenes[0]["start"]["label"] == "313"
    assert scenes[0]["end"]["label"] == "313"


async def test_scene_end_keeps_the_start_date_when_no_time_passed(plugin):
    """A scene whose messages took no time ends on its start date, to the
    same precision: no midnight stamp in the label, and the world's "now"
    stays a plain year."""

    world, _maren, _harbour = await _open_world_with_maren(plugin)
    scene_id = world.scenes().create("First", WorldDate.of(1313))
    world.scenes().replace_messages(
        scene_id,
        [MessageRecord(id="m1", seq=0, kind="narration", data={}, elapsed="PT0S")],
    )

    await plugin.handle({"type": "worlds", "action": "list_scenes"})
    scene = _last(plugin, "list_scenes")["data"]["scenes"][0]
    assert scene["end"] == scene["start"]
    assert scene["end"]["precision"] == "year"

    await plugin.handle({"type": "worlds", "action": "get_present"})
    now = _last(plugin, "get_present")["data"]["now"]
    assert (now["precision"], now["label"]) == ("year", scene["start"]["label"])


@requires_chromadb
async def test_plan_then_start_scene(plugin, client, memory):
    world, maren, harbour = await _open_world_with_maren(plugin)

    async with MockClientContext():
        client_responses.get().append(SETUP_REPLY)
        await plugin.handle(
            {
                "type": "worlds",
                "action": "plan_scene",
                "prompt": "Maren meets a smuggler at the harbour",
                "picks": {"Maren": maren},
                "player": None,
                "start": WorldDate.of(313).model_dump(),
            }
        )
        await _drain(plugin)

    planned = _last(plugin, "plan_scene")["data"]
    setup = planned["setup"]
    assert setup["player"]["thing_id"] == maren
    assert setup["place"]["thing_id"] == harbour
    assert setup["start"]["label"] == "313"
    assert planned["names"][maren] == "Maren"
    json.dumps(plugin.websocket_handler.messages)

    async with MockClientContext():
        client_responses.get().append("Maren is tall and grey-eyed.")
        await plugin.handle({"type": "worlds", "action": "start_scene", "setup": setup})
        await _drain(plugin)

    started = _last(plugin, "start_scene")["data"]
    scene_id = started["scene_id"]
    assert started["target"] == f"world://{world.path}|{scene_id}"
    record = world.scenes().get(scene_id)
    assert record.start == WorldDate.of(313)
    assert record.player_thing_id == maren
    assert record.state["intro"] == "Fog rolls over the harbour."
    assert started["scene"]["goal"] == "Meet the smuggler."


async def test_continue_scene(plugin, client):
    world, maren, harbour = await _open_world_with_maren(plugin)
    scenes = world.scenes()
    old = scenes.create(
        "First",
        WorldDate.of(313),
        player_thing_id=maren,
        state={
            "characters": [{"thing_id": maren, "active": True}],
            "place_thing_id": harbour,
        },
    )

    scene = MockScene()
    bootstrap_scene(scene)
    async with MockClientContext():
        client_responses.get().append(SETUP_REPLY)
        await plugin.handle(
            {
                "type": "worlds",
                "action": "continue_scene",
                "scene_id": old,
                "goal_prompt": "Find the smuggler again",
            }
        )
        await _drain(plugin)

    setup = _last(plugin, "continue_scene")["data"]["setup"]
    assert setup["continued_from"] == old
    assert setup["player"]["thing_id"] == maren
    assert setup["place"]["thing_id"] == harbour
    assert setup["start"]["label"] == "313"


async def test_fixed_setup_setting_answers_without_a_model(
    plugin, client, tmp_path, monkeypatch
):
    """TALEMATE_TEST_FIXED_SETUP (e2e only) names a file holding a model
    reply that `plan_scene` and `continue_scene` use instead of asking the
    model (no index, no summarizer); the reply's names are still resolved
    against the world, the owner's picks first. `start_scene` then leaves
    the prose as it is."""

    world, _maren, harbour = await _open_world_with_maren(plugin)
    with world.revision(Source.manual(note="seed")) as rev:
        rev.create_thing("character", {"name": "Brin Vos"})
        other = rev.create_thing("character", {"name": "Brin Holt"})
    fixed = tmp_path / "fixed-setup.json"
    fixed.write_text(
        json.dumps(
            {
                "player": "Brin",
                "characters": [{"name": "Daveth", "facts": ["A smuggler."]}],
                "place": {"name": "The Harbour"},
                "goal": "Meet the smuggler.",
                "intro": "Fog rolls over the harbour.",
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SETUP", str(fixed))
    # no AI client at all, as in the browser tests
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))

    await plugin.handle(
        {
            "type": "worlds",
            "action": "plan_scene",
            "prompt": "Brin meets a smuggler",
            "picks": {"Brin": other},
            "player": None,
            "start": WorldDate.of(313).model_dump(),
        }
    )
    await _drain(plugin)
    planned = _last(plugin, "plan_scene")["data"]
    setup = planned["setup"]
    assert setup["player"]["thing_id"] == other
    assert planned["names"][other] == "Brin Holt"
    assert setup["place"]["thing_id"] == harbour
    assert setup["invented"] == ["Daveth"]
    assert setup["intro"] == "Fog rolls over the harbour."

    await plugin.handle({"type": "worlds", "action": "start_scene", "setup": setup})
    await _drain(plugin)
    scene_id = _last(plugin, "start_scene")["data"]["scene_id"]
    assert world.scenes().get(scene_id).player_thing_id == other

    await plugin.handle(
        {
            "type": "worlds",
            "action": "continue_scene",
            "scene_id": scene_id,
            "goal_prompt": "Follow the smuggler",
        }
    )
    await _drain(plugin)
    following = _last(plugin, "continue_scene")["data"]["setup"]
    assert following["continued_from"] == scene_id
    assert following["player"]["thing_id"] == other
    assert following["summary"] == ""
    assert client.prompt_history == []


async def test_setup_carries_stub_previews_and_fills_them_on_start(
    plugin, client, tmp_path, monkeypatch
):
    """The setup payload carries a preview for each stub it uses
    (`stub_previews`); sent back on Start, they fill the stubs, keeping
    their ids. In the browser tests the fixed preview stands in for each;
    a race stub (no species to fill it from) is left as it is."""

    world, _maren, _harbour = await _open_world_with_maren(plugin)
    with world.revision(Source.manual(note="stubs")) as rev:
        weir = rev.create_thing(
            "place", {"name": "The Weir", "stub": {"ignored": True}}
        )
        salt = rev.create_thing(
            "race", {"name": "Saltfolk", "stub": {"ignored": False}}
        )
    setup_file = tmp_path / "fixed-setup.json"
    setup_file.write_text(
        json.dumps(
            {
                "player": "Maren",
                "characters": [],
                "place": {"name": "The Weir"},
                "goal": "Mend the weir.",
                "intro": "Water roars.",
            }
        )
    )
    preview_file = tmp_path / "fixed-preview.json"
    preview_file.write_text(
        json.dumps(
            {
                "name": "ignored: the stub's own name wins",
                "facts": [{"category": "description", "text": "A broken dam."}],
                "prose": {"description": "A broken dam."},
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SETUP", str(setup_file))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(preview_file))
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))

    head = world.head_rev()
    await plugin.handle(
        {
            "type": "worlds",
            "action": "plan_scene",
            "prompt": "Maren mends the Weir among the Saltfolk",
            "picks": {"Saltfolk": salt},
            "player": None,
            "start": WorldDate.of(313).model_dump(),
        }
    )
    await _drain(plugin)
    setup = _last(plugin, "plan_scene")["data"]["setup"]
    assert setup["place"]["thing_id"] == weir
    assert [p["stub_id"] for p in setup["stub_previews"]] == [weir]
    assert setup["stub_previews"][0]["name"] == "The Weir"
    assert world.head_rev() == head

    await plugin.handle({"type": "worlds", "action": "start_scene", "setup": setup})
    await _drain(plugin)
    scene_id = _last(plugin, "start_scene")["data"]["scene_id"]
    view = world.view(None)
    state = view.thing(weir)
    assert not state.is_stub
    assert [fact.text for fact in state.facts] == ["A broken dam."]
    assert view.thing(salt).is_stub
    assert world.scenes().get(scene_id).state["place_thing_id"] == weir
    assert client.prompt_history == []


async def test_plan_scene_owner_choices_win(plugin, tmp_path, monkeypatch):
    """`plan_scene`'s picks beat an exact name match, and its `new_names`
    are invented even when one world thing has that name."""

    world, maren, _harbour = await _open_world_with_maren(plugin)
    with world.revision(Source.manual(note="seed")) as rev:
        holt = rev.create_thing("character", {"name": "Maren Holt"})
    fixed = tmp_path / "fixed-setup.json"
    fixed.write_text(json.dumps({"player": "Maren", "characters": [], "intro": "."}))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SETUP", str(fixed))

    async def plan(**extra):
        await plugin.handle(
            {
                "type": "worlds",
                "action": "plan_scene",
                "prompt": "Maren goes fishing",
                "start": WorldDate.of(313).model_dump(),
                **extra,
            }
        )
        await _drain(plugin)
        return _last(plugin, "plan_scene")["data"]["setup"]

    assert (await plan())["player"]["thing_id"] == maren
    assert (await plan(picks={"Maren": holt}))["player"]["thing_id"] == holt
    treated_new = await plan(new_names=["Maren"])
    assert treated_new["player"] == {
        "thing_id": None,
        "local": {"name": "Maren", "facts": [], "heritage_id": None},
    }
    assert treated_new["invented"] == ["Maren"]


async def _loaded_river_scene(plugin, *, facts=()):
    """A world with Mira (born 290) and a scene "River" at 313 she's in,
    loaded the way `load_world_scene` leaves it: on its own world
    connection, as the handler's scene. Returns `(world, mira, scene_id,
    scene, loaded_world)`; the caller closes `loaded_world`."""

    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Vael"})
    world = plugin.world
    with world.revision(Source.manual(note="seed")) as rev:
        mira = rev.create_thing(
            "character",
            {"name": "Mira", "born": WorldDate.of(290)},
            valid_from=WorldDate.of(290),
        )
        for category, text in facts:
            rev.add_fact(mira, category, text)
    scenes = world.scenes()
    scene_id = scenes.create(
        "River", WorldDate.of(313), state={"characters": [{"thing_id": mira}]}
    )

    loaded_world = World.open(world.path)
    scene = MockScene()
    bootstrap_scene(scene)
    character = character_from_world(
        loaded_world, mira, WorldDate.of(313), is_player=False
    )
    await scene.add_actor(
        Actor(character=character, agent=instance.get_agent("conversation")),
        commit_to_memory=False,
    )
    scene.active_characters.append(character.name)
    scene.world_ref = WorldSceneRef(world_path=str(world.path), scene_id=scene_id)
    scene.world_context = WorldSceneContext(
        world=loaded_world, record=scenes.get(scene_id)
    )
    plugin.websocket_handler.scene = scene
    return world, mira, scene_id, scene, loaded_world


async def _reposition(plugin, scene_id, year):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "reposition_scene",
            "scene_id": scene_id,
            "start": WorldDate.of(year).model_dump(),
        }
    )


async def test_reposition_scene_refreshes_loaded_scene(plugin, monkeypatch):
    """Ruling R4: a scene's start can move after play; nothing has reached
    the world, so only the start changes, and a loaded scene's characters
    follow the new date."""

    world, _mira, scene_id, scene, loaded_world = await _loaded_river_scene(plugin)
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    assert scene.get_character("Mira").base_attributes["age"] == 23

    try:
        await _reposition(plugin, scene_id, 320)

        moved = _last(plugin, "reposition_scene")["data"]
        assert moved["start"]["label"] == "320"
        assert world.scenes().get(scene_id).start == WorldDate.of(320)
        assert scene.world_context.record.start == WorldDate.of(320)
        assert scene.get_character("Mira").base_attributes["age"] == 30
    finally:
        loaded_world.close()


async def test_reposition_scene_emits_the_loaded_scenes_status(plugin, monkeypatch):
    """After the loaded scene's characters are rebuilt, its status goes
    out, so open character sheets show the new date's characters."""

    _world, _mira, scene_id, scene, loaded_world = await _loaded_river_scene(plugin)
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    ages = []
    monkeypatch.setattr(
        scene,
        "emit_status",
        lambda *a, **kw: ages.append(
            scene.get_character("Mira").base_attributes["age"]
        ),
    )

    try:
        await _reposition(plugin, scene_id, 320)
        assert ages == [30]
    finally:
        loaded_world.close()


async def test_reposition_scene_brings_prose_up_to_date(plugin, monkeypatch):
    """The scene's world characters get their prose for the new start in
    the background (as an edit's prose refresh does); the loaded scene is
    rebuilt with it and its status sent again."""

    _world, mira, scene_id, scene, loaded_world = await _loaded_river_scene(
        plugin, facts=[("appearance", "Tall and grey-eyed.")]
    )
    client = scene.mock_client
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=client))
    emitted = []
    monkeypatch.setattr(scene, "emit_status", lambda *a, **kw: emitted.append(1))

    try:
        async with MockClientContext():
            client_responses.get().append("Mira is tall and grey-eyed.")
            await _reposition(plugin, scene_id, 320)
            assert plugin.tasks, "no prose task was scheduled"
            await _drain(plugin)

        assert _last(plugin, "prose_updated")["data"] == {"id": mira}
        cache = loaded_world.prose()
        at = WorldDate.of(320)
        assert cache.get(mira, "description", at).text == "Mira is tall and grey-eyed."
        assert cache.stale(mira, "description", at) is False
        assert scene.get_character("Mira").description == "Mira is tall and grey-eyed."
        # once for the new date, once more with the new prose
        assert len(emitted) == 2
    finally:
        loaded_world.close()


async def test_continue_scene_saves_the_loaded_scene_first(plugin, monkeypatch):
    """Continuing the loaded world scene saves it first, so the summary
    covers messages not saved yet."""

    world, _mira, scene_id, scene, loaded_world = await _loaded_river_scene(plugin)
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    scene.history.append(NarratorMessage(message="The river rose overnight."))
    summarized = []

    async def summarize_events(text, *args, **kwargs):
        summarized.append(text)
        return "The river rose."

    monkeypatch.setattr(
        instance.get_agent("summarizer"), "summarize_events", summarize_events
    )
    fixed = loaded_world.path.parent / "fixed-setup.json"
    fixed.write_text(json.dumps({"player": "Mira", "characters": [], "intro": "."}))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SETUP", str(fixed))

    try:
        await plugin.handle(
            {
                "type": "worlds",
                "action": "continue_scene",
                "scene_id": scene_id,
                "goal_prompt": "Cross the river",
            }
        )
        await _drain(plugin)

        assert [m.data["message"] for m in world.scenes().messages(scene_id)] == [
            "The river rose overnight."
        ]
        assert _last(plugin, "continue_scene")["data"]["setup"]["continued_from"] == (
            scene_id
        )
    finally:
        loaded_world.close()


# --- links, stubs and other names ---------------------------------------------


def _aka(name, tag="common", everyday=False):
    return {"name": name, "tag": tag, "everyday": everyday}


async def _open_stub_world(plugin):
    """Maren and The Harbour, plus two stubs: the place "Tsardom of
    Moscavia" (everyday name "Moscavia"), which Maren's background and
    then, a revision later, The Harbour's history mention, and the ignored
    lore stub "Hope", which Maren's personality mentions."""

    world, maren, harbour = await _open_world_with_maren(plugin)
    s = SimpleNamespace(world=world, maren=maren, harbour=harbour)
    with world.revision(Source.manual(note="stubs")) as rev:
        s.tsardom = rev.create_thing(
            "place",
            {
                "name": "Tsardom of Moscavia",
                "aka": [_aka("Moscavia", everyday=True)],
                "stub": {"ignored": False},
            },
        )
        s.hope = rev.create_thing("lore", {"name": "Hope", "stub": {"ignored": True}})
        s.born = rev.add_fact(
            maren, "background", f"Born in {ref(s.tsardom, 'Moscavia')}."
        )
        s.clings = rev.add_fact(
            maren, "personality", f"Clings to {ref(s.hope, 'Hope')}."
        )
    with world.revision(Source.manual(note="harbour")) as rev:
        s.ships = rev.add_fact(
            harbour, "history", f"Ships from {ref(s.tsardom, 'Moscavia')} dock here."
        )
    return s


def _plain(text):
    return {"text": text, "ref": None, "stub": False}


async def test_payload_segments_and_stub_fields(plugin):
    s = await _open_stub_world(plugin)
    world = s.world
    start, end = prose_gen.stretch_containing(world, s.maren, None)
    world.prose().put(
        s.maren,
        "description",
        start,
        end,
        "Maren sails from The Harbour toward Moscavia, clinging to Hope.",
    )
    head = world.head_rev()

    thing = await _get_thing(plugin, s.maren)
    facts = {f["fact_id"]: f for f in thing["facts"]}
    assert facts[s.born]["segments"] == [
        _plain("Born in "),
        {"text": "Moscavia", "ref": s.tsardom, "stub": True},
        _plain("."),
    ]
    # an ignored stub is hidden: its words stay, as plain text
    assert facts[s.clings]["segments"] == [_plain("Clings to Hope.")]
    # prose is matched by name, never linked to the thing itself, and makes
    # nothing
    assert thing["prose_segments"] == {
        "description": [
            _plain("Maren sails from "),
            {"text": "The Harbour", "ref": s.harbour, "stub": False},
            _plain(" toward "),
            {"text": "Moscavia", "ref": s.tsardom, "stub": True},
            _plain(", clinging to Hope."),
        ],
        "personality": [],
    }
    assert world.head_rev() == head
    assert thing["aka"] == []
    assert thing["stub"] is None
    assert "aka" not in thing["fields"] and "stub" not in thing["fields"]
    assert thing["named_stubs"] == [
        {"id": s.tsardom, "name": "Tsardom of Moscavia", "kind": "place"}
    ]
    assert thing["mentions"] == []
    json.dumps(thing)

    stub = await _get_thing(plugin, s.tsardom)
    assert stub["stub"] == {"ignored": False}
    assert stub["aka"] == [_aka("Moscavia", everyday=True)]
    assert stub["fields"] == {"name": "Tsardom of Moscavia"}
    assert sorted(
        (m["owner_id"], m["fact_id"], m["text"]) for m in stub["mentions"]
    ) == sorted(
        [
            (s.maren, s.born, "Born in Moscavia."),
            (s.harbour, s.ships, "Ships from Moscavia dock here."),
        ]
    )
    assert (await _get_thing(plugin, s.hope))["stub"] == {"ignored": True}

    # kind lists hold stubs, marked, but not ignored ones
    await plugin.handle({"type": "worlds", "action": "list_things", "kind": "place"})
    places = {t["id"]: t for t in _last(plugin, "list_things")["data"]["things"]}
    assert places == {
        s.harbour: {"id": s.harbour, "kind": "place", "name": "The Harbour"},
        s.tsardom: {
            "id": s.tsardom,
            "kind": "place",
            "name": "Tsardom of Moscavia",
            "stub": {"ignored": False},
        },
    }
    await plugin.handle({"type": "worlds", "action": "list_things", "kind": "lore"})
    assert _last(plugin, "list_things")["data"]["things"] == []


async def test_match_names_marks_stubs_and_unknown(plugin):
    s = await _open_stub_world(plugin)
    await plugin.handle(
        {
            "type": "worlds",
            "action": "match_names",
            "text": "Maren rows from Moscavia to Kremova.",
            "at": None,
        }
    )
    data = _last(plugin, "match_names")["data"]
    matches = {m["text"]: m for m in data["matches"]}
    assert matches["Moscavia"]["candidates"][0] == {
        "id": s.tsardom,
        "name": "Tsardom of Moscavia",
        "kind": "place",
        "stub": True,
        "via": "aka",
    }
    assert matches["Maren"]["candidates"][0]["stub"] is False
    assert matches["Maren"]["candidates"][0]["via"] == "name"
    assert data["unknown"] == [{"start": 28, "end": 35, "text": "Kremova"}]


async def test_add_fact_links_known_names_and_picks(plugin, monkeypatch):
    s = await _open_stub_world(plugin)
    world = s.world
    monkeypatch.setattr(plugin, "_client", lambda: None)
    count = len(world.view().things())

    await plugin.handle(
        {
            "type": "worlds",
            "action": "add_fact",
            "thing_id": s.maren,
            "category": "background",
            "text": "Maren left Moscavia for The Harbour with Vasha and the Grey Pier crew.",
            "picks": {"Grey Pier": s.harbour},
        }
    )
    reply = _last(plugin, "add_fact")["data"]
    fact = next(f for f in reply["facts"] if f["text"].startswith("Maren left"))
    # her own name stays plain; the stub, the entry and the pick link,
    # keeping their words; "Vasha" is only a suggestion, never a stub
    assert fact["text"] == (
        f"Maren left {ref(s.tsardom, 'Moscavia')} for "
        f"{ref(s.harbour, 'The Harbour')} with Vasha and the "
        f"{ref(s.harbour, 'Grey Pier')} crew."
    )
    assert fact["rendered"] == (
        "Maren left Moscavia for The Harbour with Vasha and the Grey Pier crew."
    )
    assert len(world.view().things()) == count

    # correcting the text links it again; an existing reference (a re-point
    # keeps its words and swaps the id) is kept as sent
    await plugin.handle(
        {
            "type": "worlds",
            "action": "correct_fact",
            "thing_id": s.maren,
            "fact_id": fact["fact_id"],
            "text": f"Met Vasha at {ref(s.tsardom, 'The Harbour')} by Moscavia.",
            "picks": {"Vasha": s.maren},
        }
    )
    corrected = next(
        f
        for f in _last(plugin, "correct_fact")["data"]["facts"]
        if f["fact_id"] == fact["fact_id"]
    )
    # a pick meaning the thing itself stays plain, like its own name
    assert corrected["text"] == (
        f"Met Vasha at {ref(s.tsardom, 'The Harbour')} by {ref(s.tsardom, 'Moscavia')}."
    )


async def test_fact_edits_leave_names_treated_as_new_plain(plugin, monkeypatch):
    """A name the owner treats as new in a fact form (`new_names`) stays
    plain text, though the world has a thing by that name; a pick still
    links."""

    s = await _open_stub_world(plugin)
    monkeypatch.setattr(plugin, "_client", lambda: None)

    await plugin.handle(
        {
            "type": "worlds",
            "action": "add_fact",
            "thing_id": s.maren,
            "category": "background",
            "text": "Maren left Moscavia for The Harbour.",
            "new_names": ["The Harbour"],
        }
    )
    fact = next(
        f
        for f in _last(plugin, "add_fact")["data"]["facts"]
        if f["rendered"].startswith("Maren left")
    )
    assert fact["text"] == (f"Maren left {ref(s.tsardom, 'Moscavia')} for The Harbour.")

    await plugin.handle(
        {
            "type": "worlds",
            "action": "correct_fact",
            "thing_id": s.maren,
            "fact_id": fact["fact_id"],
            "text": "Maren left Moscavia for The Harbour.",
            "new_names": ["Moscavia"],
            "picks": {"The Harbour": s.harbour},
        }
    )
    corrected = next(
        f
        for f in _last(plugin, "correct_fact")["data"]["facts"]
        if f["fact_id"] == fact["fact_id"]
    )
    assert corrected["text"] == (
        f"Maren left Moscavia for {ref(s.harbour, 'The Harbour')}."
    )


async def test_make_stub_leaves_a_name_treated_as_new_plain(plugin, monkeypatch):
    """Making a stub of one phrase links that phrase only: a known name the
    owner left plain in the same fact (treat as new) stays plain."""

    s = await _open_stub_world(plugin)
    monkeypatch.setattr(plugin, "_client", lambda: None)
    await plugin.handle(
        {
            "type": "worlds",
            "action": "add_fact",
            "thing_id": s.maren,
            "category": "background",
            "text": "Orphaned near The Harbour on the Night of Feathers.",
            "new_names": ["The Harbour"],
        }
    )
    fact = next(
        f
        for f in _last(plugin, "add_fact")["data"]["facts"]
        if f["rendered"].startswith("Orphaned")
    )
    assert fact["text"] == "Orphaned near The Harbour on the Night of Feathers."
    await plugin.handle(
        {
            "type": "worlds",
            "action": "make_stub",
            "thing_id": s.maren,
            "fact_id": fact["fact_id"],
            "text": "Night of Feathers",
            "kind": "event",
        }
    )
    night = next(t for t in s.world.view().things("event"))
    made = next(
        f
        for f in _last(plugin, "make_stub")["data"]["facts"]
        if f["fact_id"] == fact["fact_id"]
    )
    assert made["text"] == (
        f"Orphaned near The Harbour on the {ref(night.id, 'Night of Feathers')}."
    )


async def test_repoint_ref_swaps_one_link_only(plugin, monkeypatch):
    """`repoint_ref` points the n-th reference of a fact at another thing,
    keeping its words, and leaves everything else as it was: a known name
    written plain stays plain."""

    s = await _open_stub_world(plugin)
    world = s.world
    monkeypatch.setattr(plugin, "_client", lambda: None)
    with world.revision(Source.manual(note="fact")) as rev:
        fact_id = rev.add_fact(
            s.maren,
            "background",
            f"Sailed from {ref(s.tsardom, 'Moscavia')} past The Harbour"
            f" to {ref(s.tsardom, 'Moscavia')}.",
        )
    head = world.head_rev()
    await plugin.handle(
        {
            "type": "worlds",
            "action": "repoint_ref",
            "thing_id": s.maren,
            "fact_id": fact_id,
            "occurrence": 1,
            "to_id": s.harbour,
        }
    )
    assert world.head_rev() == head + 1
    fact = next(
        f
        for f in _last(plugin, "repoint_ref")["data"]["facts"]
        if f["fact_id"] == fact_id
    )
    assert fact["text"] == (
        f"Sailed from {ref(s.tsardom, 'Moscavia')} past The Harbour"
        f" to {ref(s.harbour, 'Moscavia')}."
    )

    # no such reference, or a thing that isn't there: refused
    head = world.head_rev()
    for occurrence, to_id in ((5, s.harbour), (0, "f" * 32)):
        await plugin.handle(
            {
                "type": "worlds",
                "action": "repoint_ref",
                "thing_id": s.maren,
                "fact_id": fact_id,
                "occurrence": occurrence,
                "to_id": to_id,
            }
        )
        assert "error" in _last(plugin, "operation_done")
    assert world.head_rev() == head


async def _open_repoint_world(plugin, monkeypatch):
    """The stub world, plus the full place "Moscavy" (other name "Old
    Moscavy") and more links to the stub "Tsardom of Moscavia": one with no
    shown words, one Moscavy's own fact holds, one showing Moscavy's own
    name and one showing another thing's name. Prose scheduling is
    recorded in `s.prose`."""

    s = await _open_stub_world(plugin)
    world = s.world
    s.prose = []
    monkeypatch.setattr(plugin, "_client", lambda: None)
    monkeypatch.setattr(
        plugin, "_schedule_prose", lambda thing_id, at, **kw: s.prose.append(thing_id)
    )
    with world.revision(Source.manual(note="moscavy")) as rev:
        s.moscavy = rev.create_thing(
            "place", {"name": "Moscavy", "aka": [_aka("Old Moscavy", tag="proper")]}
        )
        s.fled = rev.add_fact(s.maren, "background", f"Fled {ref(s.tsardom)} twice.")
        s.once = rev.add_fact(
            s.moscavy, "history", f"Once called {ref(s.tsardom, 'the Tsardom')}."
        )
        s.dreams = rev.add_fact(
            s.maren, "personality", f"Dreams of {ref(s.tsardom, 'moscavy')}."
        )
        s.sailed = rev.add_fact(
            s.harbour, "history", f"Boats sail to {ref(s.tsardom, 'Harbour')}."
        )
    return s


def _fact_text(world, thing_id, fact_id):
    return next(
        f.text for f in world.view().thing(thing_id).facts if f.fact_id == fact_id
    )


async def test_repoint_stub_moves_every_link_and_names_the_target(plugin, monkeypatch):
    """`repoint_stub` points every link to a stub at the target, keeping
    the words; the stub's name and each distinct shown text become the
    target's common other names (not its own name, one it has, or another
    thing's); the stub is removed. One revision, and no prose: the
    rendered text is the same."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=s.moscavy)
    assert not _errors(plugin)
    assert world.head_rev() == head + 1

    texts = {
        (s.maren, s.born): f"Born in {ref(s.moscavy, 'Moscavia')}.",
        (s.harbour, s.ships): f"Ships from {ref(s.moscavy, 'Moscavia')} dock here.",
        (s.maren, s.fled): f"Fled {ref(s.moscavy, 'Tsardom of Moscavia')} twice.",
        # the target's own fact can't link to itself: its words stay, plain
        (s.moscavy, s.once): "Once called the Tsardom.",
        (s.maren, s.dreams): f"Dreams of {ref(s.moscavy, 'moscavy')}.",
        (s.harbour, s.sailed): f"Boats sail to {ref(s.moscavy, 'Harbour')}.",
    }
    for (owner, fact_id), text in texts.items():
        assert _fact_text(world, owner, fact_id) == text
    view = world.view()
    assert view.thing(s.tsardom) is None
    assert view.thing(s.moscavy).fields["aka"] == [
        _aka("Old Moscavy", tag="proper"),
        _aka("Tsardom of Moscavia"),
        _aka("Moscavia"),
        _aka("the Tsardom"),
    ]
    assert s.prose == []

    reply = _last(plugin, "repoint_stub")["data"]
    assert reply["stub_id"] == s.tsardom
    assert reply["stub_name"] == "Tsardom of Moscavia"
    assert reply["target"]["id"] == s.moscavy
    assert reply["links"] == 6
    assert reply["aka_added"] == ["Tsardom of Moscavia", "Moscavia", "the Tsardom"]

    # the stubs listed no longer hold it
    await _act(plugin, "list_stubs")
    assert _last(plugin, "list_stubs")["data"]["stubs"] == []


async def test_repoint_stub_is_undone_in_one_step(plugin, monkeypatch):
    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    facts = [
        (s.maren, s.born),
        (s.harbour, s.ships),
        (s.maren, s.fled),
        (s.moscavy, s.once),
        (s.maren, s.dreams),
        (s.harbour, s.sailed),
    ]
    before = {fact: _fact_text(world, *fact) for fact in facts}
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=s.moscavy)
    assert not _errors(plugin)
    assert all(_fact_text(world, *fact) != before[fact] for fact in facts)

    report = world.undo([world.head_rev()])
    assert report.undo_rev is not None
    view = world.view()
    stub = view.thing(s.tsardom)
    assert stub is not None and stub.is_stub
    assert view.name_of(s.tsardom) == "Tsardom of Moscavia"
    assert stub.fields["aka"] == [_aka("Moscavia", everyday=True)]
    assert {fact: _fact_text(world, *fact) for fact in facts} == before
    assert view.thing(s.moscavy).fields["aka"] == [_aka("Old Moscavy", tag="proper")]


async def test_repoint_stub_refusals_write_nothing(plugin, monkeypatch):
    """Refused, writing nothing: the stub itself, a deleted thing, an
    ignored stub, a full entry as the stub, a field use the target's kind
    can't take, the target's own use of the stub (filed in it), and a
    scene's use. Another live stub is a target like any entry."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    with world.revision(Source.manual(note="gone")) as rev:
        gone = rev.create_thing("place", {"name": "Gone"})
        saltlore = rev.create_thing("lore", {"name": "Saltlore"})
    with world.revision(Source.manual(note="delete")) as rev:
        rev.remove_thing(gone)

    head = world.head_rev()
    for stub_id, target_id, words in (
        (s.tsardom, s.tsardom, "itself"),
        (s.tsardom, gone, "no such thing"),
        (s.tsardom, s.hope, "ignored"),
        (s.harbour, s.moscavy, "not a stub"),
    ):
        await _act(plugin, "repoint_stub", stub_id=stub_id, target_id=target_id)
        assert words in _last(plugin, "operation_done")["error"]["message"]
        assert world.head_rev() == head

    # a character's heritage can't be lore: the use is named
    with world.revision(Source.manual(note="heritage")) as rev:
        rev.set_field(s.maren, "heritage", s.tsardom, None)
    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=saltlore)
    message = _last(plugin, "operation_done")["error"]["message"]
    assert "Maren's heritage" in message and "lore" in message
    assert world.head_rev() == head
    world.undo([head])

    # the target is filed in the stub: it would point at itself
    with world.revision(Source.manual(note="own filing")) as rev:
        rev.set_field(s.moscavy, "filings", [{"target": s.tsardom}], None)
    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=s.moscavy)
    message = _last(plugin, "operation_done")["error"]["message"]
    assert "Moscavy's filings" in message
    assert world.head_rev() == head
    world.undo([head])

    # a scene uses a stub: refused, naming the scene
    with world.revision(Source.manual(note="oskar")) as rev:
        oskar = rev.create_thing(
            "character", {"name": "Oskar", "stub": {"ignored": False}}
        )
    world.scenes().create("Crossing", WorldDate.of(320), player_thing_id=oskar)
    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=oskar, target_id=s.maren)
    message = _last(plugin, "operation_done")["error"]["message"]
    assert "the scene Crossing" in message
    assert world.head_rev() == head

    # another live stub takes the links, and stays a stub
    with world.revision(Source.manual(note="stub")) as rev:
        tsardom2 = rev.create_thing(
            "place", {"name": "The Tsardom", "stub": {"ignored": False}}
        )
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=tsardom2)
    assert len(_errors(plugin)) == 7
    view = world.view()
    assert view.thing(s.tsardom) is None
    assert view.thing(tsardom2).is_stub
    assert _fact_text(world, s.maren, s.born) == f"Born in {ref(tsardom2, 'Moscavia')}."
    # "the Tsardom" is its own name now
    assert [entry["name"] for entry in view.thing(tsardom2).fields["aka"]] == [
        "Tsardom of Moscavia",
        "Moscavia",
    ]


async def test_fact_spans_keep_same_name_links_apart(plugin, monkeypatch):
    """A fact form's `spans` link their words positionally, before picks and
    automatic matching: two links written "Maren" keep their own targets,
    and a third, plain "Maren" follows the name-keyed pick."""

    s = await _open_stub_world(plugin)
    world = s.world
    monkeypatch.setattr(plugin, "_client", lambda: None)
    with world.revision(Source.manual(note="marens")) as rev:
        vos = rev.create_thing("character", {"name": "Maren Vos"})
        holt = rev.create_thing("character", {"name": "Maren Holt"})
        fact_id = rev.add_fact(
            s.harbour,
            "history",
            f"{ref(vos, 'Maren')} rowed with {ref(holt, 'Maren')}.",
        )
    await plugin.handle(
        {
            "type": "worlds",
            "action": "correct_fact",
            "thing_id": s.harbour,
            "fact_id": fact_id,
            "text": "Maren rowed with Maren past Maren's dock, and Maren.",
            "spans": [
                {"start": 0, "end": 5, "ref": vos},
                {"start": 17, "end": 22, "ref": holt},
                {"start": 46, "end": 51, "ref": None},
            ],
            "picks": {"Maren": s.maren},
        }
    )
    fact = next(
        f
        for f in _last(plugin, "correct_fact")["data"]["facts"]
        if f["fact_id"] == fact_id
    )
    # a span with no ref keeps its words plain, whatever the picks say
    assert fact["text"] == (
        f"{ref(vos, 'Maren')} rowed with {ref(holt, 'Maren')}"
        f" past {ref(s.maren, 'Maren')}'s dock, and Maren."
    )


async def test_make_stub_refuses_the_owner_itself(plugin, monkeypatch):
    """A stub of the fact's own thing's name would be a link to itself:
    refused, writing nothing."""

    s = await _open_stub_world(plugin)
    world = s.world
    monkeypatch.setattr(plugin, "_client", lambda: None)
    with world.revision(Source.manual(note="fact")) as rev:
        fact_id = rev.add_fact(s.harbour, "history", "The Harbour flooded once.")
    head = world.head_rev()
    await plugin.handle(
        {
            "type": "worlds",
            "action": "make_stub",
            "thing_id": s.harbour,
            "fact_id": fact_id,
            "text": "The Harbour",
            "kind": "place",
        }
    )
    assert "error" in _last(plugin, "operation_done")
    assert world.head_rev() == head


async def test_make_stub_action(plugin, monkeypatch):
    s = await _open_stub_world(plugin)
    world = s.world
    monkeypatch.setattr(plugin, "_client", lambda: None)
    with world.revision(Source.manual(note="fact")) as rev:
        fact_id = rev.add_fact(
            s.maren, "background", "Orphaned on the Night of Feathers in Moscavia."
        )
    head = world.head_rev()

    await plugin.handle(
        {
            "type": "worlds",
            "action": "make_stub",
            "thing_id": s.maren,
            "fact_id": fact_id,
            "text": "Night of Feathers",
            "kind": "event",
        }
    )
    reply = _last(plugin, "make_stub")["data"]
    assert world.head_rev() == head + 1
    assert reply["id"] == s.maren
    view = world.view()
    night = next(t for t in view.things("event"))
    assert view.name_of(night.id) == "Night of Feathers"
    assert night.is_stub and not night.stub_ignored
    fact = next(f for f in reply["facts"] if f["fact_id"] == fact_id)
    assert fact["segments"] == [
        _plain("Orphaned on the "),
        {"text": "Night of Feathers", "ref": night.id, "stub": True},
        # only the phrase asked for is linked: the rest is left as it was
        _plain(" in Moscavia."),
    ]
    assert {"id": night.id, "name": "Night of Feathers", "kind": "event"} in reply[
        "named_stubs"
    ]

    # a phrase the fact doesn't hold is refused, writing nothing
    head = world.head_rev()
    await plugin.handle(
        {
            "type": "worlds",
            "action": "make_stub",
            "thing_id": s.maren,
            "fact_id": fact_id,
            "text": "Kremova",
            "kind": "place",
        }
    )
    assert "Kremova" in _last(plugin, "operation_done")["error"]["message"]
    assert world.head_rev() == head

    # an ignored stub of that name is reused, and no longer ignored
    with world.revision(Source.manual(note="fact")) as rev:
        prays = rev.add_fact(s.maren, "personality", "Prays for Hope.")
    await plugin.handle(
        {
            "type": "worlds",
            "action": "make_stub",
            "thing_id": s.maren,
            "fact_id": prays,
            "text": "Hope",
            "kind": "lore",
        }
    )
    fact = next(
        f for f in _last(plugin, "make_stub")["data"]["facts"] if f["fact_id"] == prays
    )
    assert fact["text"] == f"Prays for {ref(s.hope, 'Hope')}."
    assert not world.view().thing(s.hope).stub_ignored


async def test_list_stubs_counts_and_ignored(plugin):
    s = await _open_stub_world(plugin)

    await plugin.handle({"type": "worlds", "action": "list_stubs"})
    assert _last(plugin, "list_stubs")["data"] == {
        "stubs": [
            {
                "id": s.tsardom,
                "name": "Tsardom of Moscavia",
                "kind": "place",
                # Maren's fact was written first
                "first_mentioned": {"thing_id": s.maren, "name": "Maren"},
                "mentions": 2,
                "ignored": False,
            }
        ]
    }

    await plugin.handle(
        {"type": "worlds", "action": "list_stubs", "include_ignored": True}
    )
    stubs = _last(plugin, "list_stubs")["data"]["stubs"]
    assert [stub["name"] for stub in stubs] == ["Hope", "Tsardom of Moscavia"]
    assert stubs[0] == {
        "id": s.hope,
        "name": "Hope",
        "kind": "lore",
        "first_mentioned": {"thing_id": s.maren, "name": "Maren"},
        "mentions": 1,
        "ignored": True,
    }


async def test_ignore_and_change_kind(plugin):
    s = await _open_stub_world(plugin)
    world = s.world

    await plugin.handle(
        {"type": "worlds", "action": "ignore_stub", "id": s.tsardom, "ignored": True}
    )
    assert _last(plugin, "ignore_stub")["data"]["stub"] == {"ignored": True}
    assert world.view().thing(s.tsardom).stub_ignored
    await plugin.handle({"type": "worlds", "action": "list_things", "kind": "place"})
    assert [t["id"] for t in _last(plugin, "list_things")["data"]["things"]] == [
        s.harbour
    ]
    born = next(
        f
        for f in (await _get_thing(plugin, s.maren))["facts"]
        if f["fact_id"] == s.born
    )
    assert born["segments"] == [_plain("Born in Moscavia.")]

    await plugin.handle(
        {"type": "worlds", "action": "ignore_stub", "id": s.tsardom, "ignored": False}
    )
    assert not world.view().thing(s.tsardom).stub_ignored

    await plugin.handle(
        {"type": "worlds", "action": "change_stub_kind", "id": s.hope, "kind": "item"}
    )
    changed = _last(plugin, "change_stub_kind")["data"]
    assert (changed["id"], changed["kind"]) == (s.hope, "item")
    assert world.view().thing(s.hope).kind == "item"

    # a full entry is no stub: neither action applies to it
    head = world.head_rev()
    await plugin.handle(
        {"type": "worlds", "action": "ignore_stub", "id": s.harbour, "ignored": True}
    )
    assert _last(plugin, "operation_done")["error"]
    await plugin.handle(
        {
            "type": "worlds",
            "action": "change_stub_kind",
            "id": s.harbour,
            "kind": "lore",
        }
    )
    assert _last(plugin, "operation_done")["error"]
    assert world.head_rev() == head


async def test_stub_suggestion(plugin):
    s = await _open_stub_world(plugin)
    with s.world.revision(Source.manual(note="rite")) as rev:
        rite = rev.create_thing(
            "lore", {"name": "Feather Rite", "stub": {"ignored": False}}
        )
        rev.add_fact(s.harbour, "general", f"Keeps the {ref(rite, 'Feather Rite')}.")

    await plugin.handle(
        {"type": "worlds", "action": "stub_suggestion", "id": s.tsardom}
    )
    data = _last(plugin, "stub_suggestion")["data"]
    assert data["id"] == s.tsardom
    assert data["prompt"] == (
        "Tsardom of Moscavia: Born in Moscavia. Ships from Moscavia dock here."
    )
    assert data["context"] == [
        [
            "Maren (character)",
            [
                "Born in Moscavia.",
                "Tall and grey-eyed.",
                "Lost her left eye.",
                "Clings to Hope.",
            ],
        ],
        [
            "The Harbour (place)",
            ["Ships from Moscavia dock here.", "Keeps the Feather Rite."],
        ],
    ]

    # a stub only mentioned has a suggestion too
    await plugin.handle({"type": "worlds", "action": "stub_suggestion", "id": rite})
    assert _last(plugin, "stub_suggestion")["data"]["prompt"] == (
        "Feather Rite: Keeps the Feather Rite."
    )


async def test_preview_with_stub_id_and_accept_into_stub(plugin, client):
    s = await _open_stub_world(plugin)
    world = s.world
    reply = json.dumps(
        {
            "name": "Tsardom of Moscavia",
            "facts": [{"category": "description", "text": "A realm of pine forest."}],
        }
    )

    async with MockClientContext():
        client_responses.get().extend([reply, "Pines, everywhere."])
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "lore",
                "prompt": "the northern realm Maren came from",
                "fields": {},
                "stub_id": s.tsardom,
                "picks": {"Maren": s.maren},
            }
        )
        await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert (preview["kind"], preview["stub_id"]) == ("place", s.tsardom)
    assert preview["picks"] == {"Maren": s.maren}
    assert preview["context"][0][0] == "Maren (character)"

    await plugin.handle(
        {"type": "worlds", "action": "accept_preview", "preview": preview}
    )
    accepted = _last(plugin, "accept_preview")["data"]
    assert accepted["id"] == s.tsardom
    assert accepted["stub"] is None
    assert accepted["aka"] == [_aka("Moscavia", everyday=True)]

    # a preview made without a stub fills one with `into_stub`
    lore_reply = json.dumps(
        {
            "name": "Hope",
            "facts": [{"category": "general", "text": "A sailor's creed."}],
        }
    )
    async with MockClientContext():
        client_responses.get().extend([lore_reply, "A creed."])
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "lore",
                "prompt": "a sailor's creed",
                "fields": {},
            }
        )
        await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    await plugin.handle(
        {
            "type": "worlds",
            "action": "accept_preview",
            "preview": preview,
            "into_stub": s.hope,
        }
    )
    filled = _last(plugin, "accept_preview")["data"]
    assert filled["id"] == s.hope
    assert filled["stub"] is None
    assert not world.view().thing(s.hope).is_stub


async def test_preview_names_treated_as_new(plugin, client):
    """A matched name the owner treats as new is never context or a link
    to the entry: listed by the model, it becomes a stub of its own;
    unlisted, it stays plain text."""

    s = await _open_stub_world(plugin)
    world = s.world
    reply = json.dumps(
        {
            "name": "Ilse",
            "facts": [
                {"category": "background", "text": "Sister of Maren, from Moscavia."}
            ],
            "names": [{"name": "Maren", "kind": "character", "aka": []}],
        }
    )

    async def preview_and_accept(model_reply):
        client.prompt_history.clear()
        async with MockClientContext():
            client_responses.get().extend([model_reply, "Ilse."])
            await plugin.handle(
                {
                    "type": "worlds",
                    "action": "preview_thing",
                    "kind": "character",
                    "prompt": "Maren's sister",
                    "fields": {},
                    "picks": {"Maren": s.maren},
                    "new_names": ["Maren"],
                }
            )
            await _drain(plugin)
            # the facts, then the one prose section they have facts for (the
            # second time, the first Ilse is a same-thing candidate with
            # facts: its verdict is asked after them)
            asked = [
                p
                for p in client.prompt_history
                if p["prompt"].uid != "world.same-thing"
            ]
            assert len(asked) == 2 and client.prompt_history[:2] == asked
            preview = _last(plugin, "preview_thing")["data"]["preview"]
            prompt = str(client.prompt_history[0]["prompt"])
        await plugin.handle(
            {"type": "worlds", "action": "accept_preview", "preview": preview}
        )
        return preview, prompt, _last(plugin, "accept_preview")["data"]

    preview, prompt, accepted = await preview_and_accept(reply)
    assert "Named in this prompt" not in prompt
    assert "Tall and grey-eyed." not in prompt
    assert preview["picks"] == {}
    assert [n["name"] for n in preview["new_names"]] == ["Maren"]
    view = world.view()
    marens = [t.id for t in view.things("character") if view.name_of(t.id) == "Maren"]
    stub = next(t for t in marens if t != s.maren)
    assert view.thing(stub).is_stub
    assert accepted["facts"][0]["text"] == (
        f"Sister of {ref(stub, 'Maren')}, from {ref(s.tsardom, 'Moscavia')}."
    )

    # not listed by the model: the name stays plain
    unlisted = json.dumps(
        {
            "name": "Ilse",
            "facts": [{"category": "background", "text": "Sister of Maren."}],
        }
    )
    _preview, _prompt, accepted = await preview_and_accept(unlisted)
    assert accepted["facts"][0]["text"] == "Sister of Maren."


async def test_fixed_preview_expands_and_offers_stubs(plugin, tmp_path, monkeypatch):
    """The browser tests' fixed preview acts like a real one for stubs: a
    `stub_id` gives the stub's kind, name and mention context, and a
    preview named like a stub offers it as `matching_stub_id`."""

    s = await _open_stub_world(plugin)
    fixed = tmp_path / "fixed-preview.json"
    fixed.write_text(
        json.dumps(
            {
                "name": "Tsardom of Moscavia",
                "facts": [{"category": "description", "text": "Pine forest."}],
                "prose": {"description": "Pines."},
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(fixed))

    async def preview(**extra):
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "place",
                "prompt": "a northern realm",
                "fields": {},
                **extra,
            }
        )
        await _drain(plugin)
        return _last(plugin, "preview_thing")["data"]["preview"]

    expanded = await preview(kind="lore", stub_id=s.tsardom)
    assert (expanded["kind"], expanded["stub_id"]) == ("place", s.tsardom)
    assert expanded["matching_stub_id"] is None
    assert [heading for heading, _facts in expanded["context"]] == [
        "Maren (character)",
        "The Harbour (place)",
    ]

    offered = await preview()
    assert (offered["stub_id"], offered["matching_stub_id"]) == (None, s.tsardom)

    await plugin.handle(
        {
            "type": "worlds",
            "action": "accept_preview",
            "preview": offered,
            "into_stub": s.tsardom,
        }
    )
    assert _last(plugin, "accept_preview")["data"]["id"] == s.tsardom


async def test_link_and_other_name_edits_schedule_no_prose(plugin, client):
    """Making a stub of a phrase, re-pointing a link and teaching an other
    name change no rendered text: no prose is scheduled, and the thing's
    prose stays fresh."""

    s = await _open_stub_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="fact")) as rev:
        fact_id = rev.add_fact(
            s.maren,
            "background",
            f"Sailed from {ref(s.tsardom, 'Moscavia')} on the Night of Feathers.",
        )
    start, end = prose_gen.stretch_containing(world, s.maren, None)
    for section in prose_gen.sections_for("character"):
        world.prose().put(s.maren, section, start, end, "Maren.")

    async def edit(action, **data):
        await plugin.handle(
            {"type": "worlds", "action": action, "thing_id": s.maren, **data}
        )
        assert not [m for m in _replies(plugin, "operation_done") if "error" in m]
        assert _last(plugin, action)
        assert not plugin.tasks, f"{action} scheduled prose"

    await edit("make_stub", fact_id=fact_id, text="Night of Feathers", kind="event")
    await edit("repoint_ref", fact_id=fact_id, occurrence=0, to_id=s.harbour)
    await edit("set_field", field="aka", value=[_aka("Mara")], valid_from=None)

    assert client.prompt_history == []
    for section in prose_gen.sections_for("character"):
        assert world.prose().stale(s.maren, section, None) is False


# --- a faith and what's filed in it -----------------------------------------


def _text(segments):
    return "".join(run["text"] for run in segments)


async def _open_sphere_world(plugin):
    """Present 1020. The White Dawn, religion lore and an agent: the Dawn
    Vigil (lore) and Dawn Peak (a place) filed in it, a belief it holds,
    a plain fact and a dated one naming the Peak. The Reformed Dawn, filed
    in it as a branch. The Tsardom, a place written with the nation hint.
    Vasha, a practitioner of the Dawn since 1010 who skips the Vigil;
    Maren, filed in nothing."""

    def filed(target, role=None, since=None):
        return [
            {
                "target": target,
                "role": role,
                "since": since.model_dump(mode="json") if since else None,
                "until": None,
                "within": None,
                "exceptions": [],
            }
        ]

    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Vael",
            "present_year": 1020,
        }
    )
    world = plugin.world
    s = SimpleNamespace(world=world)
    with world.revision(Source.manual(note="seed")) as rev:
        s.dawn = rev.create_thing(
            "lore", {"name": "The White Dawn", "hint": "religion", "agent": True}
        )
        s.vigil = rev.create_thing(
            "lore", {"name": "Dawn Vigil", "filings": filed(s.dawn)}
        )
        rev.add_fact(s.vigil, "general", "A nightly prayer at first light.")
        s.peak = rev.create_thing(
            "place", {"name": "Dawn Peak", "filings": filed(s.dawn)}
        )
        rev.add_fact(s.peak, "description", "A white mountain.")
        s.unblessed = rev.add_fact(
            s.dawn,
            "belief",
            "The unchanged are unblessed.",
            origin={"held_by": s.dawn},
        )
        rev.add_fact(s.dawn, "general", "The state church.")
        s.synod = rev.add_fact(
            s.dawn,
            "general",
            f"The First Synod meets on {ref(s.peak, 'Dawn Peak')}.",
            valid_from=WorldDate.of(996),
        )
        s.reformed = rev.create_thing(
            "lore",
            {
                "name": "The Reformed Dawn",
                "hint": "religion",
                "filings": filed(s.dawn, "branch of"),
            },
        )
        s.tsardom = rev.create_thing(
            "place", {"name": "Tsardom", "tag": "country", "hint": "nation"}
        )
        rev.add_fact(s.tsardom, "description", "A northern realm.")
        s.vasha = rev.create_thing(
            "character",
            {
                "name": "Vasha",
                "filings": filed(s.dawn, "practitioner", WorldDate.of(1010)),
            },
        )
        s.skips = rev.add_fact(
            s.vasha,
            "ties",
            f"Skips the vigil. Departs from {ref(s.vigil, 'Dawn Vigil')}",
        )
        s.maren = rev.create_thing("character", {"name": "Maren"})
    return s


def _errors(plugin):
    return [m for m in _replies(plugin, "operation_done") if "error" in m]


async def _act(plugin, action, **data):
    await plugin.handle({"type": "worlds", "action": action, **data})


async def _fresh_prose(world, thing_id):
    start, end = prose_gen.stretch_containing(world, thing_id, None)
    for section in prose_gen.sections_for(world.view().thing(thing_id).kind):
        world.prose().put(thing_id, section, start, end, "Prose.")


async def test_accept_preview_carries_filings(plugin, client):
    """A character preview's "In" rows round-trip through accept_preview,
    as the owner left them: the ticked ones filed (one with its
    exception, written as a `ties` fact), the unticked one not."""

    s = await _open_sphere_world(plugin)
    preview = {
        "kind": "character",
        "prompt": "a smith",
        "name": "Oskar",
        "facts": [{"category": "background", "text": "A smith."}],
        "prose": {},
        "filings": [
            {
                "target_id": s.dawn,
                "target_name": "The White Dawn",
                "role": "deacon",
                "ticked": True,
            },
            {
                "target_id": s.tsardom,
                "target_name": "Tsardom",
                "role": "subject",
                "exceptions": [
                    {"text": "Pays no tithe", "item": "Tsardom", "thing_id": None}
                ],
                "ticked": True,
            },
            {"target_id": s.peak, "target_name": "Dawn Peak", "ticked": False},
        ],
    }
    await _act(plugin, "accept_preview", preview=preview)
    assert not _errors(plugin)
    oskar = _last(plugin, "accept_preview")["data"]
    view = s.world.view()
    filings = filings_of(view, oskar["id"])
    assert [(f.target, f.role) for f in filings] == [
        (s.dawn, "deacon"),
        (s.tsardom, "subject"),
    ]
    assert filings[0].exceptions == []
    (tithe,) = filings[1].exceptions
    assert view.render(view.fact(tithe)[1].text).startswith("Pays no tithe.")


async def test_fixed_preview_carries_tag_in_and_file_into(
    plugin, tmp_path, monkeypatch
):
    """The browser tests' fixed preview gives the file's `tag`, its `in`
    and `file_into` rows (resolved by name, unticked) after the owner's
    own filing (ticked), as a real preview does."""

    s = await _open_sphere_world(plugin)
    fixed = tmp_path / "fixed-preview.json"
    fixed.write_text(
        json.dumps(
            {
                "name": "Ilya",
                "tag": "Elder, priest",
                "facts": [{"category": "background", "text": "An elder."}],
                "prose": {},
                "in": [
                    {"entry": "The White Dawn", "role": "elder"},
                    {"entry": "Nowhere Hall", "role": "guest"},
                ],
                "file_into": [{"entry": "Dawn Peak", "role": None}],
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(fixed))

    await _act(
        plugin,
        "preview_thing",
        kind="character",
        prompt="an elder",
        fields={"filings": [{"target": s.tsardom, "role": "subject"}]},
    )
    await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert preview["tag"] == "elder"
    assert [(f["target_id"], f["role"], f["ticked"]) for f in preview["filings"]] == [
        (s.tsardom, "subject", True),
        (s.dawn, "elder", False),
    ]
    assert [(r["thing_id"], r["ticked"]) for r in preview["file_into"]] == [
        (s.peak, False)
    ]
    for key in ("ties", "part_of", "move_in", "refile"):
        assert key not in preview


@pytest.mark.parametrize(
    ("thing", "unread", "read"),
    [
        # a place: described from its place facts, never its timeline
        ("tsardom", "timeline", "description"),
    ],
)
async def test_unread_fact_leaves_place_prose_fresh(
    plugin, client, thing, unread, read
):
    """Ruling P19 through the generic fact actions ("Add to the timeline",
    editing a statement): a fact of a category the place's description
    doesn't read (P18) leaves its prose fresh -- no regeneration, and the
    payload doesn't call it stale; one it reads makes it stale."""

    s = await _open_sphere_world(plugin)
    thing_id = getattr(s, thing)
    await _fresh_prose(s.world, thing_id)
    at = WorldDate.of(1019).model_dump(mode="json")
    async with MockClientContext():
        await _act(
            plugin,
            "add_fact",
            thing_id=thing_id,
            category=unread,
            text="Declared the Night of Feathers holy.",
            valid_from=at,
        )
        await _drain(plugin)
        assert not _errors(plugin)
        assert [c["kind"] for c in client.prompt_history] == []
        payload = await _get_thing(plugin, thing_id)
        assert payload["prose"]["description"]["stale"] is False
        kind = s.world.view().thing(thing_id).kind
        assert not s.world.prose().stale(
            thing_id,
            "description",
            None,
            ignore_categories=prose_gen.unread_categories(kind, "description"),
        )

        await _act(
            plugin,
            "add_fact",
            thing_id=thing_id,
            category=read,
            text="Its faithful keep the dawn hours.",
        )
        assert not _errors(plugin)
        payload = _last(plugin, "add_fact")["data"]
        assert payload["prose"]["description"]["stale"] is True
        await _drain(plugin)
        assert [c["kind"] for c in client.prompt_history] == ["analyze"]


@pytest.mark.parametrize(
    "field, value, action",
    [
        # filings are written only by the filing actions (rulings F11,
        # F14), the tag by its own
        ("filings", [], "add_filing, edit_filing or remove_filing"),
        ("tag", "river", "set_tag"),
    ],
)
async def test_set_field_refuses_guarded_fields(plugin, field, value, action):
    """`set_field` never writes filings nor the tag: it refuses them,
    naming what does, writing nothing."""

    s = await _open_sphere_world(plugin)
    thing_id = s.vigil
    head = s.world.head_rev()
    await _act(plugin, "set_field", thing_id=thing_id, field=field, value=value)
    (error,) = _errors(plugin)
    assert action in error["error"]["message"]
    assert s.world.head_rev() == head


# --- repoint_stub: what a stub carries over ----------------------------------


async def test_repoint_stub_carries_fields_filings_and_exceptions(plugin, client):
    """Every use of the stub moves to the target at the dates it holds: a
    place filed in a place stub (its undated filing, not a dated one into
    another place), a lore entry filed in a lore stub, a character's
    filing in it and the exception filed under that filing."""

    s = await _open_sphere_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="uses")) as rev:
        north = rev.create_thing(
            "place", {"name": "Northreach", "stub": {"ignored": False}}
        )
        mark = rev.create_thing("place", {"name": "Northmark"})
        south = rev.create_thing("place", {"name": "Southmark"})
        harbour = rev.create_thing(
            "place", {"name": "The Harbour", "filings": [{"target": north}]}
        )
        rev.set_field(harbour, "filings", [{"target": south}], WorldDate.of(1015))
        faith = rev.create_thing(
            "lore", {"name": "Old Faith", "stub": {"ignored": False}}
        )
        lore = rev.create_thing("lore", {"name": "The Old Ways"})
        ember = rev.create_thing(
            "lore", {"name": "Ember Rite", "filings": [{"target": faith}]}
        )
        doubt = rev.add_fact(
            s.maren,
            "ties",
            f"Doubts {ref(faith, 'the Old Faith')}.",
            origin={"tie": faith},
        )
        rev.set_field(
            s.maren,
            "filings",
            [{"target": faith, "role": "keeper", "exceptions": [doubt]}],
            None,
        )

    await _act(plugin, "repoint_stub", stub_id=north, target_id=mark)
    await _act(plugin, "repoint_stub", stub_id=faith, target_id=lore)
    assert not _errors(plugin)
    targets = lambda at, thing: [  # noqa: E731
        f.target for f in filings_of(world.view(at), thing)
    ]
    assert targets(WorldDate.of(1010), harbour) == [mark]
    assert targets(WorldDate.of(1020), harbour) == [south]
    assert targets(None, ember) == [lore]
    (filing,) = filings_of(world.view(), s.maren)
    assert (filing.target, filing.role, filing.exceptions) == (lore, "keeper", [doubt])
    exception = next(f for f in world.live_facts(s.maren) if f.fact_id == doubt)
    assert exception.origin == {"tie": lore}


async def test_repoint_stub_redo_keeps_the_moved_facts(plugin, monkeypatch):
    """Undoing the undo of a re-point gives the target the stub's facts
    again; a fact overriding one of the stub's overrides the moved copy."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    with world.revision(Source.manual(note="own")) as rev:
        lore = rev.add_fact(s.tsardom, "general", "A cold realm.")
        warmer = rev.add_fact(
            s.harbour, "general", "Warmer than they say.", overrides=[lore]
        )
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=s.moscavy)
    assert not _errors(plugin)
    [moved] = [f for f in world.live_facts(s.moscavy) if f.text == "A cold realm."]
    [over] = [f for f in world.live_facts(s.harbour) if f.fact_id == warmer]
    assert over.overrides == [moved.fact_id]
    assert s.prose == [s.moscavy]

    repointed = world.head_rev()
    undone = world.undo([repointed]).undo_rev
    assert world.view().thing(s.tsardom) is not None
    assert "A cold realm." not in [f.text for f in world.live_facts(s.moscavy)]
    assert [
        f.overrides for f in world.live_facts(s.harbour) if f.fact_id == warmer
    ] == [[lore]]
    report = world.undo([undone])
    assert not report.conflicts
    assert world.view().thing(s.tsardom) is None
    assert "A cold realm." in [f.text for f in world.live_facts(s.moscavy)]
    assert [
        f.overrides for f in world.live_facts(s.harbour) if f.fact_id == warmer
    ] == [[moved.fact_id]]


async def test_repoint_stub_never_makes_a_filing_cycle(plugin, monkeypatch):
    """A place stub filed in the target leaves the target unfiled there
    (it can't be filed in itself; noted); a filing that would close a
    loop (Region in the stub, Bay in Region, the stub onto Bay) is
    refused."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    with world.revision(Source.manual(note="places")) as rev:
        cove = rev.create_thing(
            "place",
            {
                "name": "Cove",
                "stub": {"ignored": False},
                "filings": [{"target": s.moscavy}],
            },
        )
        region = rev.create_thing(
            "place", {"name": "Region", "filings": [{"target": s.tsardom}]}
        )
        bay = rev.create_thing(
            "place", {"name": "Bay", "filings": [{"target": region}]}
        )

    await _act(plugin, "repoint_stub", stub_id=cove, target_id=s.moscavy)
    assert not _errors(plugin)
    assert filings_of(world.view(), s.moscavy) == []
    notes = _last(plugin, "repoint_stub")["data"]["notes"]
    assert any("isn't filed in itself" in note for note in notes)

    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=bay)
    message = _last(plugin, "operation_done")["error"]["message"]
    assert "Region's filings" in message and "inside itself" in message
    assert world.head_rev() == head


async def test_repoint_stub_more_refusals(plugin, client):
    """Refused, naming the use: a filing that would loop and a mix whose
    two parents would be one. Any entry takes filings now: a lore target
    isn't refused for them."""

    s = await _open_sphere_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="uses")) as rev:
        faith = rev.create_thing(
            "lore", {"name": "Old Faith", "stub": {"ignored": False}}
        )
        rev.create_thing("lore", {"name": "Ember Rite", "filings": [{"target": faith}]})
        plain = rev.create_thing("lore", {"name": "Plain Lore"})
        order = rev.create_thing(
            "lore", {"name": "The Order", "filings": [{"target": faith}]}
        )
        chapter = rev.create_thing(
            "lore", {"name": "The Chapter", "filings": [{"target": order}]}
        )
        orc = rev.create_thing("species", {"name": "Orc"})
        elf = rev.create_thing("species", {"name": "Elf", "stub": {"ignored": False}})
        rev.create_thing("mix", {"name": "Half-elf", "parents": [orc, elf]})
    head = world.head_rev()
    for stub_id, target_id, words in (
        (faith, chapter, ("The Order's filings", "inside itself")),
        (elf, orc, ("Half-elf's parents",)),
    ):
        await _act(plugin, "repoint_stub", stub_id=stub_id, target_id=target_id)
        message = _last(plugin, "operation_done")["error"]["message"]
        assert all(word in message for word in words), message
        assert world.head_rev() == head

    errors = len(_errors(plugin))
    await _act(plugin, "repoint_stub", stub_id=faith, target_id=plain)
    assert len(_errors(plugin)) == errors
    assert _last(plugin, "repoint_stub")["data"]["stub_id"] == faith


async def test_repoint_stub_notes_and_prose(plugin, monkeypatch):
    """A stub's field the target holds the same value of carries no note.
    Prose is refreshed for a thing whose rendered field was rewritten (a
    species' origin), not for an unrendered one (a filing)."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    with world.revision(Source.manual(note="uses")) as rev:
        owls = rev.create_thing("species", {"name": "Owl-folk", "origin": s.tsardom})
        rev.set_field(s.harbour, "filings", [{"target": s.tsardom}], None)
        rev.set_field(s.moscavy, "hint", "nation", None)
        rev.set_field(s.tsardom, "hint", "nation", None)

    s.prose.clear()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=s.moscavy)
    assert not _errors(plugin)
    assert not any(
        "hint" in note for note in _last(plugin, "repoint_stub")["data"]["notes"]
    )
    assert owls in s.prose
    assert s.harbour not in s.prose


async def test_accept_preview_onto_target_schedules_its_prose(plugin, monkeypatch):
    """Accept with a same-thing target ("Is this X?" -- yes): the
    preview's facts go onto X, and X's prose is scheduled again."""

    world, maren, _harbour = await _open_world_with_maren(plugin)
    scheduled: list[str] = []
    monkeypatch.setattr(
        plugin, "_schedule_prose", lambda thing_id, at, **kw: scheduled.append(thing_id)
    )
    preview = CreatePreview(
        kind="character",
        prompt="Maren of Vael",
        name="Maren of Vael",
        facts=[PreviewFact(category="background", text="Sails at dawn.")],
        prose={},
    )
    things = len(list(world.view().things()))
    await plugin.handle(
        {
            "type": "worlds",
            "action": "accept_preview",
            "preview": preview.model_dump(mode="json"),
            "same_target_id": maren,
        }
    )

    assert _last(plugin, "accept_preview")["data"]["id"] == maren
    view = world.view()
    assert len(list(view.things())) == things
    assert "Sails at dawn." in [f.text for f in view.thing(maren).facts]
    assert scheduled == [maren]


async def test_move_fact_moves_one_fact(plugin, monkeypatch):
    """`move_fact` moves one fact onto another entry in one revision: a new
    fact, the original gone, prose for both sides. A refusal writes
    nothing."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    head = world.head_rev()
    await _act(plugin, "move_fact", fact_id=s.ships, target_id=s.moscavy)
    assert not _errors(plugin)
    assert world.head_rev() == head + 1
    reply = _last(plugin, "move_fact")["data"]
    assert reply["fact_id"] != s.ships
    assert reply["target"]["id"] == s.moscavy
    assert reply["notes"] == []
    assert s.ships not in [f.fact_id for f in world.live_facts(s.harbour)]
    moved = next(
        f for f in world.live_facts(s.moscavy) if f.fact_id == reply["fact_id"]
    )
    assert moved.text == f"Ships from {ref(s.tsardom, 'Moscavia')} dock here."
    assert s.prose == [s.harbour, s.moscavy]

    head = world.head_rev()
    await _act(plugin, "move_fact", fact_id=reply["fact_id"], target_id=s.moscavy)
    assert "already" in _last(plugin, "operation_done")["error"]["message"]
    assert world.head_rev() == head


async def test_preview_and_accept_merge(plugin, monkeypatch):
    """`preview_merge` writes nothing and answers the preview;
    `accept_merge` folds The Harbour into Moscavy in one revision as the
    owner picked, answers with Moscavy's payload and refreshes its prose.
    A refusal writes nothing."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    head = world.head_rev()
    await _act(plugin, "preview_merge", from_id=s.harbour, into_id=s.moscavy)
    assert not _errors(plugin)
    assert world.head_rev() == head
    preview = _last(plugin, "preview_merge")["data"]["preview"]
    assert preview["names"] == ["Moscavy", "The Harbour"]
    assert {f["fact_id"] for f in preview["facts"] if f["side"] == "from"} >= {
        s.ships,
        s.sailed,
    }

    await _act(
        plugin,
        "accept_merge",
        preview=preview,
        main_name="The Harbour",
        keep={},
        lose="end",
    )
    assert not _errors(plugin)
    assert world.head_rev() == head + 1
    reply = _last(plugin, "accept_merge")["data"]
    assert reply["from_id"] == s.harbour
    assert reply["into"]["id"] == s.moscavy
    assert reply["main_name"] == "The Harbour"
    view = world.view()
    assert view.thing(s.harbour) is None
    assert view.name_of(s.moscavy) == "The Harbour"
    assert s.prose[0] == s.moscavy

    await _act(plugin, "preview_merge", from_id=s.maren, into_id=s.maren)
    assert "itself" in _last(plugin, "operation_done")["error"]["message"]
    assert world.head_rev() == head + 1


def _page(thing: dict) -> tuple:
    """What a thing's page shows of it: name, other names, facts."""

    return (
        thing["name"],
        [a["name"] for a in thing["aka"]],
        sorted((f["fact_id"], f["rendered"]) for f in thing["facts"]),
    )


async def test_undo_after_a_merge(plugin, monkeypatch):
    """A merge through the router is one revision, undone in one step:
    both entries' pages read as before, the from-side back."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    before = {t: _page(await _get_thing(plugin, t)) for t in (s.harbour, s.moscavy)}
    await _act(plugin, "preview_merge", from_id=s.harbour, into_id=s.moscavy)
    preview = _last(plugin, "preview_merge")["data"]["preview"]
    await _act(
        plugin,
        "accept_merge",
        preview=preview,
        main_name="The Harbour",
        keep={},
        lose="end",
    )
    assert not _errors(plugin)
    assert world.view().thing(s.harbour) is None

    report = world.undo([world.head_rev()])
    assert report.undo_rev is not None and report.conflicts == []
    after = {t: _page(await _get_thing(plugin, t)) for t in (s.harbour, s.moscavy)}
    assert after == before


async def test_undo_after_a_move_fact(plugin, monkeypatch):
    """`move_fact` through the router, undone: the fact is back where it
    was, under its own id, and the copy is gone."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    before = {t: _page(await _get_thing(plugin, t)) for t in (s.harbour, s.moscavy)}
    await _act(plugin, "move_fact", fact_id=s.ships, target_id=s.moscavy)
    assert not _errors(plugin)
    moved = _last(plugin, "move_fact")["data"]["fact_id"]

    report = world.undo([world.head_rev()])
    assert report.undo_rev is not None and report.conflicts == []
    after = {t: _page(await _get_thing(plugin, t)) for t in (s.harbour, s.moscavy)}
    assert after == before
    assert s.ships in [f.fact_id for f in world.live_facts(s.harbour)]
    assert moved not in [f.fact_id for f in world.live_facts(s.moscavy)]


# --- curation (Task 11): the router's actions and payloads -------------------


def _record_prose(plugin, monkeypatch):
    scheduled: list[str] = []
    monkeypatch.setattr(
        plugin, "_schedule_prose", lambda thing_id, at, **kw: scheduled.append(thing_id)
    )
    return scheduled


async def _timeline_world(plugin):
    """The sphere world with dated facts on every kind: Vasha's vows (she
    joined the Dawn, a line the Dawn gathers), an ended posting and a
    belief the Dawn holds of her; Dawn Peak's first climb and a Synod line
    that disagrees with the Dawn's own (998 against 996, the Dawn's
    belief); the Vigil's
    start; the Tsardom's founding; and an undated timeline fact on the
    Dawn."""

    s = await _open_sphere_world(plugin)
    with s.world.revision(Source.manual(note="dated")) as rev:
        s.joined = rev.add_fact(
            s.vasha,
            "background",
            f"Vasha joined {ref(s.dawn, 'the White Dawn')}.",
            valid_from=WorldDate.of(1010),
        )
        s.posted = rev.add_fact(
            s.vasha,
            "background",
            "Vasha kept the gate at the harbour.",
            valid_from=WorldDate.of(1005),
            valid_until=WorldDate.of(1009),
        )
        s.chosen = rev.add_fact(
            s.vasha,
            "background",
            "Vasha was chosen by the Light.",
            valid_from=WorldDate.of(1012),
            origin={"held_by": s.dawn},
        )
        s.climbed = rev.add_fact(
            s.peak,
            "general",
            "Pilgrims first climbed the white slopes.",
            valid_from=WorldDate.of(990),
            origin={"held_by": s.dawn},
        )
        s.met = rev.add_fact(
            s.peak,
            "general",
            "The First Synod met on Dawn Peak.",
            valid_from=WorldDate.of(998),
            origin={"held_by": s.dawn},
        )
        s.began = rev.add_fact(
            s.vigil,
            "general",
            "The Vigil was first kept by hermits.",
            valid_from=WorldDate.of(995),
        )
        s.founded = rev.add_fact(
            s.tsardom,
            "history",
            "The Tsardom was founded by the first Tsar.",
            valid_from=WorldDate.of(900),
        )
        s.undated = rev.add_fact(s.dawn, "general", "The Dawn keeps no calendar.")
    return s


async def test_payload_timeline_every_kind(plugin):
    """Every kind's payload has `entry_timeline`: its dated facts and,
    for any entry that doesn't act in the world, what it gathers (what's
    filed in it, and facts naming it or those), each line `{fact_id, owner_id, owner_name,
    date, until, segments, here, disagrees_with}` -- an ended fact with its
    `until`, a held one worded as belief."""

    s = await _timeline_world(plugin)
    keys = {
        "fact_id",
        "owner_id",
        "owner_name",
        "date",
        "until",
        "segments",
        "here",
        "disagrees_with",
    }

    vasha = await _get_thing(plugin, s.vasha)
    lines = vasha["entry_timeline"]
    assert all(set(line) == keys for line in lines)
    assert [line["fact_id"] for line in lines] == [s.posted, s.joined, s.chosen]
    assert all(line["here"] and line["owner_id"] == s.vasha for line in lines)
    assert lines[0]["date"]["label"].startswith("1005")
    assert lines[0]["until"]["instant"] == WorldDate.of(1009).instant
    assert lines[1]["until"] is None
    joined = lines[1]["segments"]
    assert _text(joined) == "Vasha joined the White Dawn."
    assert [run["ref"] for run in joined if run["ref"]] == [s.dawn]
    chosen = lines[2]["segments"]
    assert _text(chosen) == "The White Dawn holds that Vasha was chosen by the Light."
    assert chosen[0] == {"text": "The White Dawn", "ref": s.dawn, "stub": False}

    peak = await _get_thing(plugin, s.peak)
    # the Dawn's Synod line names the Peak, so the Peak gathers it too
    assert [line["fact_id"] for line in peak["entry_timeline"]] == [
        s.climbed,
        s.synod,
        s.met,
    ]
    vigil = await _get_thing(plugin, s.vigil)
    assert [line["fact_id"] for line in vigil["entry_timeline"]] == [s.began]
    tsardom = await _get_thing(plugin, s.tsardom)
    assert [line["fact_id"] for line in tsardom["entry_timeline"]] == [s.founded]
    maren = await _get_thing(plugin, s.maren)
    assert maren["entry_timeline"] == []

    dawn = await _get_thing(plugin, s.dawn)
    gathered = {line["fact_id"]: line for line in dawn["entry_timeline"]}
    assert list(gathered) == [s.climbed, s.began, s.synod, s.met, s.joined]
    assert gathered[s.climbed]["owner_name"] == "Dawn Peak"
    assert not gathered[s.climbed]["here"] and gathered[s.synod]["here"]
    assert gathered[s.synod]["disagrees_with"] == [s.met]
    assert gathered[s.met]["disagrees_with"] == [s.synod]
    # held, mid-sentence: the text's first letter lowered after "holds that"
    assert gathered[s.met]["segments"] == [
        {"text": "The White Dawn", "ref": s.dawn, "stub": False},
        {
            "text": " holds that the First Synod met on Dawn Peak.",
            "ref": None,
            "stub": False,
        },
    ]
    assert gathered[s.synod]["segments"][1]["ref"] == s.peak
    # held, no subject of its own: the "holds:" form (ruling C6)
    assert _text(gathered[s.climbed]["segments"]) == (
        "The White Dawn holds: Pilgrims first climbed the white slopes."
    )
    assert gathered[s.climbed]["segments"][0]["ref"] == s.dawn
    # an undated timeline fact has no place on the timeline
    assert s.undated not in gathered

    # a branch is filed in its parent now: the parent's dated lines are
    # one link away, no longer inherited
    reformed = await _get_thing(plugin, s.reformed)
    assert reformed["entry_timeline"] == []

    # the change history keeps its own key
    assert any(e["change"] == "fact_start" for e in vasha["timeline"])


async def test_fact_rows_carry_held_by(plugin):
    """Each fact row carries `held_by: {id, name}` or null: a fact's own
    holder (a statement is held only when marked, as the Doctrines
    statement is)."""

    s = await _timeline_world(plugin)
    vasha = await _get_thing(plugin, s.vasha)
    rows = {f["fact_id"]: f for f in vasha["facts"]}
    assert rows[s.chosen]["held_by"] == {"id": s.dawn, "name": "The White Dawn"}
    assert rows[s.joined]["held_by"] is None

    dawn = await _get_thing(plugin, s.dawn)
    rows = {f["fact_id"]: f for f in dawn["facts"]}
    assert rows[s.unblessed]["held_by"] == {"id": s.dawn, "name": "The White Dawn"}
    assert rows[s.synod]["held_by"] is None


async def test_set_held_by(plugin, monkeypatch):
    """`set_held_by` sets or clears one fact's holder in one revision and
    answers with the thing. Held-ness feeds description prose (ruling
    C3): a character's fact schedules its prose, and so does a faith's
    belief. Any entry may hold one. Refused, writing nothing:
    a holder that isn't there, another thing's fact."""

    s = await _timeline_world(plugin)
    scheduled = _record_prose(plugin, monkeypatch)
    world = s.world
    head = world.head_rev()

    await _act(
        plugin, "set_held_by", thing_id=s.vasha, fact_id=s.joined, holder_id=s.dawn
    )
    assert not _errors(plugin)
    assert world.head_rev() == head + 1
    reply = _last(plugin, "set_held_by")["data"]
    row = next(f for f in reply["facts"] if f["fact_id"] == s.joined)
    assert row["held_by"] == {"id": s.dawn, "name": "The White Dawn"}
    assert scheduled == [s.vasha]

    await _act(
        plugin, "set_held_by", thing_id=s.vasha, fact_id=s.joined, holder_id=None
    )
    row = next(
        f
        for f in _last(plugin, "set_held_by")["data"]["facts"]
        if f["fact_id"] == s.joined
    )
    assert row["held_by"] is None
    assert scheduled == [s.vasha, s.vasha]

    # the implicit holder of a belief can be cleared too; a belief feeds
    # its faith's description
    await _act(
        plugin, "set_held_by", thing_id=s.dawn, fact_id=s.unblessed, holder_id=None
    )
    assert not _errors(plugin)
    row = next(
        f
        for f in _last(plugin, "set_held_by")["data"]["facts"]
        if f["fact_id"] == s.unblessed
    )
    assert row["held_by"] is None
    assert scheduled == [s.vasha, s.vasha, s.dawn]

    # any entry can hold a belief: a faith is lore now
    await _act(
        plugin, "set_held_by", thing_id=s.vasha, fact_id=s.joined, holder_id=s.vigil
    )
    assert not _errors(plugin)

    head = world.head_rev()
    for thing_id, fact_id, holder_id in (
        (s.vasha, s.joined, "0" * 32),  # no such thing
        (s.dawn, s.joined, s.dawn),  # not the Dawn's fact
    ):
        before = len(_errors(plugin))
        await _act(
            plugin,
            "set_held_by",
            thing_id=thing_id,
            fact_id=fact_id,
            holder_id=holder_id,
        )
        assert len(_errors(plugin)) == before + 1
    assert world.head_rev() == head


async def test_pick_date(plugin, monkeypatch):
    """`pick_date` settles a timeline disagreement: "end" ends the dropped
    fact at the world's now, "remove" removes it, each in one revision,
    with prose for the dropped fact's entry. Two facts that aren't a
    disagreeing pair now are refused, writing nothing."""

    s = await _timeline_world(plugin)
    scheduled = _record_prose(plugin, monkeypatch)
    world = s.world
    head = world.head_rev()

    for keep, drop in ((s.synod, s.began), (s.synod, s.synod), (s.synod, "f" * 32)):
        before = len(_errors(plugin))
        await _act(
            plugin, "pick_date", keep_fact_id=keep, drop_fact_id=drop, mode="end"
        )
        assert len(_errors(plugin)) == before + 1
    assert world.head_rev() == head
    assert scheduled == []
    errors = len(_errors(plugin))

    await _act(
        plugin,
        "pick_date",
        keep_fact_id=s.synod,
        drop_fact_id=s.met,
        mode="end",
        thing_id=s.dawn,
    )
    assert len(_errors(plugin)) == errors
    assert world.head_rev() == head + 1
    reply = _last(plugin, "pick_date")["data"]
    assert (reply["keep_fact_id"], reply["drop_fact_id"], reply["mode"]) == (
        s.synod,
        s.met,
        "end",
    )
    assert reply["owner_id"] == s.peak
    assert reply["notes"] == []
    assert reply["thing"]["id"] == s.dawn
    _owner, ended = world.view().fact(s.met)
    assert ended.valid_until == WorldDate.of(1020)
    assert scheduled == [s.peak]
    # no longer a disagreement: the timeline shows the span
    line = next(
        line for line in reply["thing"]["entry_timeline"] if line["fact_id"] == s.met
    )
    assert line["until"] is not None
    # ruling C22: an ended fact disagrees with nothing, on either side
    assert line["disagrees_with"] == []
    assert all(
        s.met not in other["disagrees_with"]
        for other in reply["thing"]["entry_timeline"]
    )

    # ended already: no longer a pair, so refused, writing nothing
    head = world.head_rev()
    await _act(
        plugin, "pick_date", keep_fact_id=s.synod, drop_fact_id=s.met, mode="end"
    )
    assert len(_errors(plugin)) == errors + 1
    assert world.head_rev() == head
    errors += 1

    # a fact on the Tsardom restating its founding, ten years out: removed
    with world.revision(Source.manual(note="again")) as rev:
        again = rev.add_fact(
            s.tsardom,
            "history",
            "The Tsardom was founded by the first Tsar.",
            valid_from=WorldDate.of(910),
        )
    head = world.head_rev()
    await _act(
        plugin, "pick_date", keep_fact_id=s.founded, drop_fact_id=again, mode="remove"
    )
    assert len(_errors(plugin)) == errors
    assert world.head_rev() == head + 1
    assert world.view().fact(again) is None
    assert "thing" not in _last(plugin, "pick_date")["data"]
    assert scheduled[-1] == s.tsardom


async def test_pick_date_remove_repoints_overrides(plugin):
    """Final review minor 5: "remove" takes the dropped fact out, so a
    fact overriding it, or an exception rejecting it (`rejects_fact`),
    points at the kept fact instead, in the same revision (merge's
    re-pointing)."""

    s = await _timeline_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="leans")) as rev:
        again = rev.add_fact(
            s.tsardom,
            "history",
            "The Tsardom was founded by the first Tsar.",
            valid_from=WorldDate.of(910),
        )
        waived = rev.add_fact(
            s.peak,
            "general",
            "On the Peak the founding is told otherwise.",
            overrides=[again],
        )
        departs = rev.add_fact(
            s.vasha,
            "ties",
            "Doubts the founding.",
            origin={"rejects_fact": again},
        )
    head = world.head_rev()
    await _act(
        plugin, "pick_date", keep_fact_id=s.founded, drop_fact_id=again, mode="remove"
    )
    assert not _errors(plugin)
    assert world.head_rev() == head + 1
    view = world.view()
    assert view.fact(again) is None
    assert view.fact(waived)[1].overrides == [s.founded]
    assert view.fact(departs)[1].origin == {"rejects_fact": s.founded}
    assert _last(plugin, "pick_date")["data"]["notes"] == []


# the old acceptance world's texts (final review I1): the Conclave's 642
# founding against the 947 rediscovery is a false pair at 0.4 (overlap
# 0.43), the Codex's compiling in 217 against 312 a true one (0.63)
CONCLAVE_642 = (
    "The Runeweavers' Conclave is founded in Stonehold to regulate and teach the art."
)
REDISCOVERY_947 = (
    "In the year 947, a party of Runeweavers from the Conclave in Stonehold "
    "rediscovered the Ashenmere rune dialect after following a trail of "
    "fragments preserved in marginal notes of surviving texts."
)
CODEX_217 = (
    "The First Codex of Aelberth is compiled, standardizing 24 foundational runes."
)
CODEX_312 = (
    "The First Codex of Aelberth is the foundational compendium of "
    "Runeweaving, compiled to standardize the art and codify its governing "
    "principles."
)


async def test_timeline_disagreements_use_date_threshold(plugin):
    """Ruling C31: a timeline's disagreements, and `pick_date`, are worked
    out at the world's `date_threshold` (default 0.5), not the repeat
    threshold: the Conclave's 642 founding isn't flagged against the 947
    rediscovery, the Codex's 217 compiling still is against 312. Lowered
    to 0.4, the Conclave pair is back."""

    s = await _open_sphere_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="runes")) as rev:
        founded = rev.add_fact(
            s.tsardom, "history", CONCLAVE_642, valid_from=WorldDate.of(642)
        )
        found = rev.add_fact(
            s.tsardom, "history", REDISCOVERY_947, valid_from=WorldDate.of(947)
        )
        c217 = rev.add_fact(
            s.tsardom, "history", CODEX_217, valid_from=WorldDate.of(217)
        )
        c312 = rev.add_fact(
            s.tsardom, "history", CODEX_312, valid_from=WorldDate.of(312)
        )
    assert world.curation().date_threshold == 0.5
    assert world.curation().repeat_threshold == 0.4

    lines = {
        line["fact_id"]: line["disagrees_with"]
        for line in (await _get_thing(plugin, s.tsardom))["entry_timeline"]
    }
    assert lines[founded] == [] and lines[found] == []
    assert lines[c217] == [c312] and lines[c312] == [c217]

    head = world.head_rev()
    errors = len(_errors(plugin))
    await _act(
        plugin, "pick_date", keep_fact_id=found, drop_fact_id=founded, mode="end"
    )
    assert len(_errors(plugin)) == errors + 1
    assert world.head_rev() == head

    await _act(plugin, "set_curation", settings={"date_threshold": 0.4})
    lines = {
        line["fact_id"]: line["disagrees_with"]
        for line in (await _get_thing(plugin, s.tsardom))["entry_timeline"]
    }
    assert lines[founded] == [found]
    await _act(
        plugin, "pick_date", keep_fact_id=found, drop_fact_id=founded, mode="end"
    )
    assert len(_errors(plugin)) == errors + 1
    assert world.head_rev() == head + 1


async def test_get_and_set_curation(plugin):
    """`get_curation` answers the world's curation knobs; `set_curation`
    changes the ones given, validated by `CurationSettings`, and answers
    the same way. Out of range or unknown knobs are refused."""

    s = await _open_sphere_world(plugin)
    await _act(plugin, "get_curation")
    got = _last(plugin, "get_curation")["data"]
    assert got["settings"] == {
        "reach": 1,
        "entries": 12,
        "facts_per_entry": 6,
        "repeat_threshold": 0.4,
        "repeat_untick_threshold": 0.7,
        "date_threshold": 0.5,
        "timeline_reach": 2,
    }
    assert got["defaults"] == got["settings"]

    await _act(plugin, "set_curation", settings={"reach": 2, "timeline_reach": 3})
    assert not _errors(plugin)
    changed = _last(plugin, "set_curation")["data"]["settings"]
    assert (changed["reach"], changed["timeline_reach"], changed["entries"]) == (
        2,
        3,
        12,
    )
    assert s.world.curation().reach == 2

    await _act(plugin, "set_curation", settings={"date_threshold": 0.6})
    assert not _errors(plugin)
    assert s.world.curation().date_threshold == 0.6

    for bad in (
        {"reach": 4},
        {"repeat_threshold": 1.5},
        {"date_threshold": -0.1},
        {"nearness": 1},
    ):
        before = len(_errors(plugin))
        await _act(plugin, "set_curation", settings=bad)
        assert len(_errors(plugin)) == before + 1
    assert s.world.curation().reach == 2


def _ember_preview(s, **extra):
    from talemate.worldplay.create import ElsewhereFact

    return CreatePreview(
        kind="lore",
        prompt="the ember rite",
        name="Ember Rite",
        facts=[PreviewFact(category="general", text="Embers are carried uphill.")],
        prose={},
        elsewhere=[
            ElsewhereFact(
                target_id=s.vasha,
                target_name="Vasha",
                category="background",
                text="Vasha once carried the embers.",
            ),
            ElsewhereFact(
                target_id=s.tsardom,
                target_name="Tsardom",
                category="timeline",
                text="The Ember Rite began.",
                since=WorldDate.of(1001),
            ),
            ElsewhereFact(
                target_id=s.peak,
                target_name="Dawn Peak",
                category="general",
                text="Embers glow on the summit.",
                ticked=False,
            ),
        ],
        **extra,
    )


async def test_accepts_schedule_prose_for_elsewhere_targets(plugin, monkeypatch):
    """An accept schedules prose for each entry its elsewhere facts went
    onto when its prose reads them: Vasha's background does, the
    Tsardom's timeline doesn't (P18, P19), and an unticked one isn't
    written."""

    s = await _open_sphere_world(plugin)
    scheduled = _record_prose(plugin, monkeypatch)
    await _act(
        plugin,
        "accept_preview",
        preview=_ember_preview(s).model_dump(mode="json"),
    )
    assert not _errors(plugin)
    assert scheduled == [s.vasha]


async def test_accept_payloads_validate_shapes(plugin):
    """The accepts validate the rows the owner sends back: an "In" row
    names its entry and its tick is a tick. A bad shape is refused,
    writing nothing."""

    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    bad = [
        (
            "accept_preview",
            {
                "preview": {
                    **_ember_preview(s).model_dump(mode="json"),
                    "filings": [{"target_id": s.vigil, "ticked": "maybe"}],
                }
            },
        ),
    ]
    for action, data in bad:
        before = len(_errors(plugin))
        await _act(plugin, action, **data)
        assert len(_errors(plugin)) == before + 1, action
    assert s.world.head_rev() == head


def _fixed_preview_file(tmp_path, monkeypatch, **fixed):
    path = tmp_path / "fixed-preview.json"
    path.write_text(json.dumps(fixed))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(path))
    return path


async def test_preview_payload_curation_fields(plugin, tmp_path, monkeypatch):
    """A create preview carries what curation and filing add -- each
    fact's `ticked`, `repeat_of` and `held_by` (with `held_by_name`); the
    elsewhere facts (category, held_by, ticked, repeat_of, a new entry's
    row with `same_as`); its "In" rows; the facts that could move here
    (`move_here`, with `from_name`) -- and `accept_preview` takes the
    owner's edits to them. The browser tests' fixed preview reads its
    `held_by` and `elsewhere` through the real parsers, and finds "Could
    move here" as the real one does."""

    s = await _open_sphere_world(plugin)
    _fixed_preview_file(
        tmp_path,
        monkeypatch,
        name="Ember Keeper",
        facts=[
            {
                "category": "general",
                "text": "The keeper tends the embers.",
                "held_by": "the White Dawn",
            },
            {"category": "general", "text": "The keeper walks the peak."},
        ],
        prose={"description": "A keeper of embers."},
        elsewhere=[
            {
                "entry": "Vasha",
                "text": "Vasha trained the Ember Keeper.",
                "held_by": "The White Dawn",
            },
            {"entry": "Ashen Gate", "text": "The Ashen Gate opens at dawn."},
            {"entry": "Dawn Vigils", "text": "The Dawn Vigils end with embers."},
        ],
        move_in=["M2"],
    )
    with s.world.revision(Source.manual(note="names it")) as rev:
        tends = rev.add_fact(s.dawn, "general", "The Ember Keeper tends the coals.")
    await _act(
        plugin,
        "preview_thing",
        kind="lore",
        prompt="a keeper of embers",
        fields={"filings": [{"target": s.dawn}]},
    )
    await _drain(plugin)
    assert not _replies(plugin, "preview_failed")
    preview = _last(plugin, "preview_thing")["data"]["preview"]

    held, plain = preview["facts"]
    assert (held["held_by"], held["held_by_name"]) == (s.dawn, "The White Dawn")
    assert (plain["held_by"], plain["held_by_name"]) == (None, None)
    assert all({"ticked", "repeat_of"} <= set(f) for f in preview["facts"])

    to_vasha, gate, vigils = preview["elsewhere"]
    assert (to_vasha["target_id"], to_vasha["category"]) == (s.vasha, "background")
    assert (to_vasha["held_by"], to_vasha["held_by_name"]) == (
        s.dawn,
        "The White Dawn",
    )
    assert to_vasha["ticked"] is True and "repeat_of" in to_vasha
    assert gate["target_id"] is None and gate["new"]["name"] == "Ashen Gate"
    assert {"same_as", "same_target_id", "tag", "filing"} <= set(gate["new"])
    assert s.vigil in [offer["thing_id"] for offer in vigils["new"]["same_as"]]

    # the owner's filing is a ticked "In" row; the Dawn's fact naming it
    # could move here, unticked (the file's `move_in` labels are ignored)
    assert [(f["target_id"], f["ticked"]) for f in preview["filings"]] == [
        (s.dawn, True)
    ]
    [row] = preview["move_here"]
    assert (row["fact_id"], row["from_id"], row["from_name"], row["ticked"]) == (
        tends,
        s.dawn,
        "The White Dawn",
        False,
    )
    for key in ("same_as", "verdict", "filings", "file_into", "new_names"):
        assert key in preview
    assert "move_in" not in preview and "refile" not in preview

    # the owner's edits: the Ashen Gate unticked, the Vigils are the Dawn
    # Vigil, the plain fact held by Vasha, the Dawn's fact ticked to move
    gate["ticked"] = False
    vigils["new"]["same_target_id"] = s.vigil
    plain["held_by"] = s.vasha
    row["ticked"] = True
    head = s.world.head_rev()
    await _act(plugin, "accept_preview", preview=preview)
    assert not _errors(plugin)
    assert s.world.head_rev() == head + 1
    data = _last(plugin, "accept_preview")["data"]
    assert data["notes"] == []
    view = s.world.view()
    keeper = view.thing(data["id"])
    assert [f.target for f in filings_of(view, data["id"])] == [s.dawn]
    by_text = {f.text: f for f in keeper.facts}
    assert entries.held_by(view, by_text["The keeper walks the peak."], keeper) == (
        s.vasha
    )
    assert "The Ember Keeper tends the coals." in by_text
    assert tends not in [f.fact_id for f in view.thing(s.dawn).facts]
    vasha_fact = next(
        f for f in view.thing(s.vasha).facts if "trained" in view.render(f.text)
    )
    assert vasha_fact.origin["held_by"] == s.dawn
    assert "The Dawn Vigils end with embers." in [
        view.render(f.text) for f in view.thing(s.vigil).facts
    ]
    assert not [t for t in view.things() if view.name_of(t.id) == "Ashen Gate"]


async def test_preview_merge_payload_and_akas(plugin, monkeypatch):
    """`preview_merge` answers the names, both sides' facts, the pairs that
    may disagree, the counts of what moves and the links' words (`akas`);
    `accept_merge` adds only the `akas` the owner kept."""

    s = await _open_repoint_world(plugin, monkeypatch)
    with s.world.revision(Source.manual(note="harbour link")) as rev:
        rev.add_fact(
            s.maren, "background", f"Grew up at {ref(s.harbour, 'the docks')}."
        )
        built_a = rev.add_fact(
            s.harbour,
            "history",
            "Fishers built the first stone quay.",
            valid_from=WorldDate.of(300),
        )
        built_b = rev.add_fact(
            s.moscavy,
            "history",
            "Fishers built the first stone quay.",
            valid_from=WorldDate.of(310),
        )
    await _act(plugin, "preview_merge", from_id=s.harbour, into_id=s.moscavy)
    preview = _last(plugin, "preview_merge")["data"]["preview"]
    assert (preview["from_id"], preview["into_id"]) == (s.harbour, s.moscavy)
    assert preview["names"] == ["Moscavy", "The Harbour"]
    (pair,) = [p for p in preview["pairs"] if (p["a"], p["b"]) == (built_a, built_b)]
    assert pair["key"] == f"{built_a}:{built_b}"
    assert pair["years"] == [300, 310]
    assert pair["a_text"] == "Fishers built the first stone quay."
    assert preview["moves"]["links"] >= 1 and "facts" in preview["moves"]
    assert preview["akas"] == ["the docks"]
    sides = {f["fact_id"]: f["side"] for f in preview["facts"]}
    assert (sides[built_a], sides[built_b]) == ("from", "into")

    await _act(
        plugin,
        "accept_merge",
        preview=preview,
        main_name="Moscavy",
        keep={pair["key"]: "b"},
        akas=[],
    )
    assert not _errors(plugin)
    reply = _last(plugin, "accept_merge")["data"]
    assert "the docks" not in [a["name"] for a in reply["into"]["aka"]]
    texts = [f["fact_id"] for f in reply["into"]["facts"]]
    assert built_b in texts and built_a not in texts


async def test_forged_move_here_rows_are_dropped(plugin, monkeypatch):
    """`accept_preview` moves here only a fact of an entry near the one
    being written (worked out again from its ticked "In" rows, picks and
    stub), still that entry's, no summary, and naming the entry: a forged
    row for a fact that doesn't name it, one from an entry that isn't
    near, and a summary are each dropped with a note, the fact staying;
    a real one moves."""

    from talemate.worldplay.create import MoveHereFact, PreviewFiling

    s = await _open_sphere_world(plugin)
    _record_prose(plugin, monkeypatch)
    with s.world.revision(Source.manual(note="names it")) as rev:
        lore = rev.add_fact(s.dawn, "general", "The Dawn keeps the Ember Lore.")
        far = rev.add_fact(s.maren, "background", "Maren reads the Ember Lore.")
    with s.world.revision(Source.manual(note="summary")) as rev:
        # a place's summary, filed in the Dawn beside the new entry
        own_summary = rev.add_fact(
            s.peak,
            "about",
            "The Ember Lore is kept on Dawn Peak.",
            origin={"summary": True},
        )

    def row(fact_id, from_id):
        return MoveHereFact(fact_id=fact_id, from_id=from_id, text="x", ticked=True)

    preview = CreatePreview(
        kind="lore",
        prompt="ember lore",
        name="Ember Lore",
        facts=[PreviewFact(category="general", text="Embers glow.")],
        prose={},
        filings=[
            PreviewFiling(target_id=s.dawn, target_name="The White Dawn", ticked=True)
        ],
        move_here=[
            row(lore, s.dawn),
            # Vasha is filed in the Dawn (near), but this doesn't name it
            row(s.skips, s.vasha),
            # Maren is near nothing
            row(far, s.maren),
            # a summary is its entry's own
            row(own_summary, s.peak),
        ],
    )
    await _act(plugin, "accept_preview", preview=preview.model_dump(mode="json"))
    assert not _errors(plugin)
    data = _last(plugin, "accept_preview")["data"]
    view = s.world.view()
    assert lore not in [f.fact_id for f in view.thing(s.dawn).facts]
    assert "The Dawn keeps the Ember Lore." in [f["rendered"] for f in data["facts"]]
    assert s.skips in [f.fact_id for f in view.thing(s.vasha).facts]
    assert far in [f.fact_id for f in view.thing(s.maren).facts]
    assert own_summary in [f.fact_id for f in view.thing(s.peak).facts]
    notes = data["notes"]
    assert any("Vasha" in note and "doesn't name" in note for note in notes)
    assert any("Maren" in note and "isn't near" in note for note in notes)
    assert any("summary" in note for note in notes)


async def test_fixed_preview_offers_same_and_verdict(plugin, tmp_path, monkeypatch):
    """The browser tests' fixed preview offers what the entry may already
    be, as the real preview does (`same_as`, never the matching stub), and
    the file's `verdict` stands in for the model's hint on the top
    candidate -- only when both sides have facts."""

    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Ash"})
    world = plugin.world
    with world.revision(Source.manual(note="seed")) as rev:
        ash = rev.create_thing("place", {"name": "Ashenmere"})
        rev.add_fact(ash, "description", "A lake of grey water.")
    hint = {"verdict": "same", "why": "Both are the lake's caves."}
    _fixed_preview_file(
        tmp_path,
        monkeypatch,
        name="The Ashenmere Caves",
        facts=[{"category": "description", "text": "Caves under the lake."}],
        prose={"description": "Caves."},
        verdict=hint,
    )
    await _act(plugin, "preview_thing", kind="place", prompt="the caves")
    await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert [offer["thing_id"] for offer in preview["same_as"]] == [ash]
    assert preview["same_as"][0]["kind"] == "place"
    assert preview["verdict"] == {ash: {**hint, "confidence": None}}

    # no facts on the preview's side: no hint
    _fixed_preview_file(
        tmp_path,
        monkeypatch,
        name="The Ashenmere Caves",
        facts=[],
        prose={"description": "Caves."},
        verdict=hint,
    )
    await _act(plugin, "preview_thing", kind="place", prompt="the caves")
    await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert [offer["thing_id"] for offer in preview["same_as"]] == [ash]
    assert preview["verdict"] is None


async def test_list_things_beings_carry_existence(plugin):
    """A being's listing carries its `existence` (undecided when unset),
    so the scene pickers offer only real beings."""

    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Gods"})
    with plugin.world.revision(Source.manual(note="seed")) as rev:
        rev.create_thing("being", {"name": "The River Spirit", "existence": "real"})
        rev.create_thing("being", {"name": "The Eternal Light"})
    await _act(plugin, "list_things", kind="being")
    things = _last(plugin, "list_things")["data"]["things"]
    assert {t["name"]: t["existence"] for t in things} == {
        "The River Spirit": "real",
        "The Eternal Light": "undecided",
    }


async def test_same_offers_say_whether_a_stub(plugin, tmp_path, monkeypatch):
    """Each same-thing offer says whether it's a stub (`SameOffer.stub`),
    so the screen offers a stub "Make it a sphere…" without reading its
    line -- a full entry whose summary says "stub" is no stub."""

    await plugin.handle({"type": "worlds", "action": "create_world", "name": "Sh"})
    with plugin.world.revision(Source.manual(note="seed")) as rev:
        lake = rev.create_thing("place", {"name": "Ashenmere"})
        rev.add_fact(lake, "description", "A stub of land juts into the lake.")
        shore = rev.create_thing(
            "place", {"name": "Ashenmere Shore", "stub": {"ignored": False}}
        )
    _fixed_preview_file(
        tmp_path,
        monkeypatch,
        name="The Ashenmere Caves",
        facts=[{"category": "description", "text": "Caves under the lake."}],
        prose={"description": "Caves."},
    )
    await _act(plugin, "preview_thing", kind="place", prompt="the caves")
    await _drain(plugin)
    offers = _last(plugin, "preview_thing")["data"]["preview"]["same_as"]
    assert {offer["thing_id"]: offer["stub"] for offer in offers} == {
        lake: False,
        shore: True,
    }
    assert "stub" in next(o["line"] for o in offers if o["thing_id"] == lake)


async def test_set_field_event_place_and_item_owner_are_filings(plugin, monkeypatch):
    """`set_field` of an event's `place` or an item's `owner` files the
    thing ("took place in", "owned by"; filing spec, "Other fields") and
    never writes the field: another value replaces that filing, its other
    filings kept, and null takes it away."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    with world.revision(Source.manual(note="things")) as rev:
        flood = rev.create_thing(
            "event", {"name": "The Flood", "filings": [{"target": s.moscavy}]}
        )
        lantern = rev.create_thing("item", {"name": "Lantern"})

    def filed(thing_id):
        return [(f.target, f.role) for f in filings_of(world.view(), thing_id)]

    await _act(plugin, "set_field", thing_id=flood, field="place", value=s.harbour)
    await _act(plugin, "set_field", thing_id=lantern, field="owner", value=s.maren)
    assert not _errors(plugin)
    assert filed(flood) == [(s.moscavy, None), (s.harbour, "took place in")]
    assert filed(lantern) == [(s.maren, "owned by")]
    assert "place" not in world.view().thing(flood).fields
    assert "owner" not in world.view().thing(lantern).fields

    await _act(plugin, "set_field", thing_id=flood, field="place", value=s.moscavy)
    assert filed(flood) == [(s.moscavy, "took place in")]
    await _act(plugin, "set_field", thing_id=lantern, field="owner", value=None)
    assert filed(lantern) == []
    assert not _errors(plugin)


# --- filing, tags and drafts (Filing, Task 6) -----------------------------------


def _filed(target, role=None, since=None, until=None, within=None, exceptions=()):
    return {
        "target": target,
        "role": role,
        "since": WorldDate.of(since).model_dump(mode="json") if since else None,
        "until": WorldDate.of(until).model_dump(mode="json") if until else None,
        "within": within,
        "exceptions": list(exceptions),
    }


async def _open_filing_world(plugin):
    """The Tsardom (a nation) with Velikoye in it since 412, the Khorol
    River in both, the Night Court and the stub Wattle Row in Velikoye;
    the White Dawn with its custom the Dawn Vigil; Tsar Dmitry IV filed in
    the Tsardom, the Night Court, Velikoye and the White Dawn (with a
    "but..."); and the Owl-folk, whose fact names Velikoye without being
    filed in it."""

    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Moscavia",
            "present_year": 1020,
        }
    )
    world = plugin.world
    s = SimpleNamespace(world=world)
    with world.revision(Source.manual(note="seed")) as rev:
        s.tsardom = rev.create_thing(
            "place", {"name": "Tsardom of Moscavia", "tag": "nation"}
        )
        rev.add_fact(s.tsardom, "description", "The realm of the owl-folk.")
        s.velikoye = rev.create_thing(
            "place",
            {
                "name": "Velikoye",
                "tag": "capital",
                "filings": [_filed(s.tsardom, since=412)],
            },
        )
        s.capital = rev.add_fact(
            s.velikoye,
            "about",
            "The fortified capital.",
            origin={"summary": True},
        )
        s.khorol = rev.create_thing(
            "place",
            {
                "name": "Khorol River",
                "tag": "river",
                "filings": [
                    _filed(s.tsardom),
                    _filed(s.velikoye, "runs through"),
                ],
            },
        )
        rev.add_fact(s.khorol, "description", "A wide, cold river.")
        s.court = rev.create_thing(
            "lore",
            {
                "name": "The Night Court",
                "tag": "institution",
                "filings": [_filed(s.velikoye)],
            },
        )
        rev.add_fact(s.court, "general", "The nocturnal council.")
        s.wattle = rev.create_thing(
            "place",
            {
                "name": "Wattle Row",
                "tag": "district",
                "stub": {"ignored": False},
                "filings": [_filed(s.velikoye)],
            },
        )
        s.dawn = rev.create_thing("lore", {"name": "The White Dawn", "tag": "faith"})
        rev.add_fact(s.dawn, "general", "The state church.")
        s.vigil = rev.create_thing(
            "lore",
            {"name": "Dawn Vigil", "tag": "custom", "filings": [_filed(s.dawn)]},
        )
        s.dmitry = rev.create_thing(
            "character", {"name": "Tsar Dmitry IV", "tag": "ruler"}
        )
        s.skips = rev.add_fact(
            s.dmitry,
            "ties",
            "Keeps the Dawn Vigil only on feast days.",
        )
        rev.set_field(
            s.dmitry,
            "filings",
            [
                _filed(s.tsardom, "sovereign", since=979),
                _filed(s.court, "presides", since=995),
                _filed(s.velikoye, "rules from here"),
                _filed(s.dawn, "practitioner", since=960, exceptions=[s.skips]),
            ],
            None,
        )
        s.owls = rev.create_thing("species", {"name": "Owl-folk"})
        rev.add_fact(
            s.owls, "origin", f"First nested at {ref(s.velikoye, 'Velikoye')}."
        )
    return s


def _group(page, tag):
    return next(group for group in page["connected"] if group["tag"] == tag)


async def test_payload_in_connected_mentioned(plugin):
    s = await _open_filing_world(plugin)

    velikoye = await _get_thing(plugin, s.velikoye)
    # the sphere-era keys are gone
    assert not {"sphere", "part_of", "ties"} & set(velikoye)
    assert velikoye["tag"] == "capital"
    assert velikoye["hint"] is None
    assert [(row["target_id"], row["since"]["label"]) for row in velikoye["in"]] == [
        (s.tsardom, "412")
    ]
    assert velikoye["in"][0] == {
        "target_id": s.tsardom,
        "target_name": "Tsardom of Moscavia",
        "role": None,
        "since": velikoye["in"][0]["since"],
        "until": None,
        "within_id": None,
        "within_name": None,
        "exceptions": [],
    }
    # Connected: grouped by tag, headed by the plural, an entry's own line
    headings = {group["tag"]: group["heading"] for group in velikoye["connected"]}
    assert headings == {
        "river": "Rivers",
        "institution": "Institutions",
        "district": "Districts",
        "ruler": "Rulers",
    }
    river = _group(velikoye, "river")
    assert river["synopsis"] is None
    assert river["rows"] == [
        {
            "id": s.khorol,
            "name": "Khorol River",
            "stub": False,
            "line_segments": [_plain("A wide, cold river.")],
            "role": "runs through",
            "since": None,
            "until": None,
        }
    ]
    assert _group(velikoye, "district")["rows"][0]["stub"] is True
    assert _group(velikoye, "ruler")["rows"][0]["role"] == "rules from here"
    # named, not filed: Mentioned in
    assert velikoye["mentioned_in"] == [{"id": s.owls, "name": "Owl-folk"}]

    # a character's "In": every filing, with roles, dates and its "but..."
    dmitry = await _get_thing(plugin, s.dmitry)
    rows = {row["target_id"]: row for row in dmitry["in"]}
    assert [row["role"] for row in dmitry["in"]] == [
        "sovereign",
        "presides",
        "rules from here",
        "practitioner",
    ]
    assert rows[s.dawn]["exceptions"] == [
        {
            "fact_id": s.skips,
            "segments": [_plain("Keeps the Dawn Vigil only on feast days.")],
        }
    ]
    assert rows[s.court]["since"]["label"] == "995"
    # a summary is the line; with none, the first fact
    tsardom = await _get_thing(plugin, s.tsardom)
    assert _group(tsardom, "capital")["rows"][0]["line_segments"] == [
        _plain("The fortified capital.")
    ]
    json.dumps(plugin.websocket_handler.messages)


async def test_add_filing(plugin):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()

    await _act(
        plugin,
        "add_filing",
        thing_id=s.court,
        target_id=s.tsardom,
        role="advises",
        since=WorldDate.of(990).model_dump(),
    )
    court = _last(plugin, "add_filing")["data"]
    assert s.world.head_rev() == head + 1
    row = next(r for r in court["in"] if r["target_id"] == s.tsardom)
    assert (row["role"], row["since"]["label"]) == ("advises", "990")
    tsardom = await _get_thing(plugin, s.tsardom)
    assert s.court in [r["id"] for r in _group(tsardom, "institution")["rows"]]

    # a new name is a stub made on the spot, of the kind and tag given
    await _act(
        plugin,
        "add_filing",
        thing_id=s.court,
        new_name="Council of Elders",
        kind="lore",
        tag="council",
        role="answers to",
    )
    court = _last(plugin, "add_filing")["data"]
    row = next(r for r in court["in"] if r["target_name"] == "Council of Elders")
    elders = s.world.view().thing(row["target_id"])
    assert elders.is_stub and elders.kind == "lore"
    assert elders.fields["tag"] == "council"
    assert s.world.head_rev() == head + 2


async def test_add_filing_refusals_write_nothing(plugin):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()
    refused = [
        # filed there already: that's edit_filing
        {"thing_id": s.court, "target_id": s.velikoye},
        # a cycle: the Tsardom in Velikoye, which is in the Tsardom
        {"thing_id": s.tsardom, "target_id": s.velikoye},
        # into itself
        {"thing_id": s.court, "target_id": s.court},
        # a target that isn't there
        {"thing_id": s.court, "target_id": "0" * 32},
        # an end before the start
        {
            "thing_id": s.vigil,
            "target_id": s.tsardom,
            "since": WorldDate.of(900).model_dump(),
            "until": WorldDate.of(800).model_dump(),
        },
        # a `within` that isn't a part of the target
        {"thing_id": s.vigil, "target_id": s.tsardom, "within": s.dawn},
        # a new name and a target both
        {"thing_id": s.vigil, "target_id": s.tsardom, "new_name": "Elders"},
        # a new name cycle made of a stub of an entry's own name
        {"thing_id": s.tsardom, "new_name": "Velikoye"},
    ]
    for data in refused:
        before = len(_errors(plugin))
        await _act(plugin, "add_filing", **data)
        assert len(_errors(plugin)) == before + 1, data
    assert s.world.head_rev() == head
    assert _replies(plugin, "add_filing") == []


async def test_edit_filing(plugin):
    s = await _open_filing_world(plugin)

    # a role changed; the rest kept
    await _act(
        plugin, "edit_filing", thing_id=s.dmitry, target_id=s.dawn, role="patron"
    )
    row = next(
        r
        for r in _last(plugin, "edit_filing")["data"]["in"]
        if r["target_id"] == s.dawn
    )
    assert (row["role"], row["since"]["label"]) == ("patron", "960")
    assert [e["fact_id"] for e in row["exceptions"]] == [s.skips]

    # "End this": an until ends it
    head = s.world.head_rev()
    await _act(
        plugin,
        "edit_filing",
        thing_id=s.dmitry,
        target_id=s.velikoye,
        until=WorldDate.of(1015).model_dump(),
    )
    assert s.world.head_rev() == head + 1
    row = next(
        r
        for r in _last(plugin, "edit_filing")["data"]["in"]
        if r["target_id"] == s.velikoye
    )
    assert row["until"]["label"] == "1015"
    # Velikoye lists him still, ended (Connected shows ended filings)
    velikoye = await _get_thing(plugin, s.velikoye)
    assert _group(velikoye, "ruler")["rows"][0]["until"]["label"] == "1015"
    later = await _get_thing(plugin, s.velikoye, WorldDate.of(1018))
    assert "ruler" not in [group["tag"] for group in later["connected"]]
    # still there before it ended
    then = await _get_thing(plugin, s.velikoye, WorldDate.of(1010))
    assert _group(then, "ruler")["rows"][0]["id"] == s.dmitry

    # within: a part of the target
    await _act(
        plugin,
        "edit_filing",
        thing_id=s.dmitry,
        target_id=s.tsardom,
        within=s.velikoye,
    )
    row = next(
        r
        for r in _last(plugin, "edit_filing")["data"]["in"]
        if r["target_id"] == s.tsardom
    )
    assert (row["within_id"], row["within_name"]) == (s.velikoye, "Velikoye")

    # refused: no such filing, a part that isn't one, an end before start
    head = s.world.head_rev()
    for data in (
        {"thing_id": s.court, "target_id": s.dawn, "role": "x"},
        {"thing_id": s.dmitry, "target_id": s.court, "within": s.dawn},
        {
            "thing_id": s.dmitry,
            "target_id": s.court,
            "until": WorldDate.of(900).model_dump(),
        },
    ):
        before = len(_errors(plugin))
        await _act(plugin, "edit_filing", **data)
        assert len(_errors(plugin)) == before + 1, data
    assert s.world.head_rev() == head


async def test_remove_filing(plugin):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()

    await _act(plugin, "remove_filing", thing_id=s.dmitry, target_id=s.dawn)
    dmitry = _last(plugin, "remove_filing")["data"]
    assert s.dawn not in [row["target_id"] for row in dmitry["in"]]
    # its "but..." went with it, in the same revision
    assert s.skips not in [fact["fact_id"] for fact in dmitry["facts"]]
    assert s.world.head_rev() == head + 1
    s.world.undo([s.world.head_rev()])
    assert s.dawn in [f.target for f in filings_of(s.world.view(), s.dmitry)]
    assert s.world.view().fact(s.skips) is not None

    before = len(_errors(plugin))
    await _act(plugin, "remove_filing", thing_id=s.court, target_id=s.dawn)
    assert len(_errors(plugin)) == before + 1


async def test_add_exception_to_a_filing(plugin):
    s = await _open_filing_world(plugin)

    await _act(
        plugin,
        "add_exception",
        character_id=s.dmitry,
        target_id=s.dawn,
        text="Never fasts.",
        rejects={"thing_id": s.vigil},
    )
    dmitry = _last(plugin, "add_exception")["data"]
    row = next(r for r in dmitry["in"] if r["target_id"] == s.dawn)
    assert len(row["exceptions"]) == 2
    text = "".join(seg["text"] for seg in row["exceptions"][1]["segments"])
    assert text.startswith("Never fasts.")

    head = s.world.head_rev()
    for data in (
        # not filed there
        {"character_id": s.dmitry, "target_id": s.vigil, "text": "x"},
        # not a character
        {"character_id": s.court, "target_id": s.velikoye, "text": "x"},
        # what it departs from isn't filed in the target
        {
            "character_id": s.dmitry,
            "target_id": s.dawn,
            "text": "x",
            "rejects": {"thing_id": s.court},
        },
    ):
        before = len(_errors(plugin))
        await _act(plugin, "add_exception", **data)
        assert len(_errors(plugin)) == before + 1, data
    assert s.world.head_rev() == head


async def test_set_tag(plugin):
    s = await _open_filing_world(plugin)

    await _act(plugin, "set_tag", thing_id=s.court, tag="Council, of sorts")
    court = _last(plugin, "set_tag")["data"]
    assert court["tag"] == "council"
    velikoye = await _get_thing(plugin, s.velikoye)
    assert _group(velikoye, "council")["heading"] == "Councils"
    assert "institution" not in [g["tag"] for g in velikoye["connected"]]

    # cleared: an untagged entry sits under Other
    await _act(plugin, "set_tag", thing_id=s.court, tag=None)
    assert _last(plugin, "set_tag")["data"]["tag"] is None
    velikoye = await _get_thing(plugin, s.velikoye)
    assert _group(velikoye, None)["heading"] == "Other"
    # no prose for a tag
    assert not plugin.tasks

    # set_field never writes it
    before = len(_errors(plugin))
    await _act(plugin, "set_field", thing_id=s.court, field="tag", value="x")
    assert "set_tag" in _errors(plugin)[-1]["error"]["message"]
    assert len(_errors(plugin)) == before + 1


async def test_rename_tag_regroups_everywhere(plugin):
    """An entry filed in ten places, its tag renamed: every page regroups
    it at once, under the new heading, and no group is left empty."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual(note="ten")) as rev:
        places = [
            rev.create_thing("place", {"name": f"Town {i}", "tag": "town"})
            for i in range(10)
        ]
        dance = rev.create_thing(
            "lore",
            {
                "name": "Feather Dance",
                "tag": "school",
                "filings": [_filed(place) for place in places],
            },
        )
        # dated: an older value holds it too
        rev.set_field(dance, "tag", "school", WorldDate.of(900))
        other = rev.create_thing(
            "lore",
            {"name": "Rune School", "tag": "school", "filings": [_filed(places[0])]},
        )
    head = s.world.head_rev()

    await _act(plugin, "rename_tag", old="School", new="academy")
    reply = _last(plugin, "rename_tag")["data"]
    assert s.world.head_rev() == head + 1
    assert set(reply["changed"]) == {dance, other}
    assert {"tag": "academy", "heading": "Academies", "count": 2} in reply["tags"]
    assert "school" not in [t["tag"] for t in reply["tags"]]
    for place in places:
        page = await _get_thing(plugin, place)
        assert [group["tag"] for group in page["connected"]] == ["academy"]
        assert all(group["rows"] for group in page["connected"])
    then = await _get_thing(plugin, places[3], WorldDate.of(950))
    assert [group["heading"] for group in then["connected"]] == ["Academies"]

    # renamed into a tag in use: that's a merge
    before = len(_errors(plugin))
    await _act(plugin, "rename_tag", old="academy", new="river")
    assert "merge" in _errors(plugin)[-1]["error"]["message"]
    await _act(plugin, "rename_tag", old="nothing", new="else")
    assert len(_errors(plugin)) == before + 2
    assert s.world.head_rev() == head + 1


async def test_merge_tag(plugin):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()

    await _act(plugin, "merge_tag", **{"from": "district", "into": "institution"})
    reply = _last(plugin, "merge_tag")["data"]
    assert (reply["from"], reply["into"], reply["changed"]) == (
        "district",
        "institution",
        [s.wattle],
    )
    velikoye = await _get_thing(plugin, s.velikoye)
    assert {r["id"] for r in _group(velikoye, "institution")["rows"]} == {
        s.court,
        s.wattle,
    }
    assert s.world.head_rev() == head + 1

    before = len(_errors(plugin))
    await _act(plugin, "merge_tag", **{"from": "river", "into": "nowhere"})
    await _act(plugin, "merge_tag", **{"from": "river", "into": "river"})
    assert len(_errors(plugin)) == before + 2
    assert s.world.head_rev() == head + 1


async def test_list_tags(plugin):
    s = await _open_filing_world(plugin)
    await _act(plugin, "list_tags")
    tags = _last(plugin, "list_tags")["data"]["tags"]
    assert {"tag": "river", "heading": "Rivers", "count": 1} in tags
    assert len(tags) == 8
    assert s.world.head_rev()


async def test_group_synopsis(plugin, client):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()
    reply = json.dumps({"synopsis": "The Khorol River runs through Velikoye."})

    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(plugin, "group_synopsis", thing_id=s.velikoye, tag="river")
        await _drain(plugin)
    assert s.world.head_rev() == head
    out = _last(plugin, "group_synopsis")["data"]
    assert out == {
        "thing_id": s.velikoye,
        "tag": "river",
        "synopsis": "The Khorol River runs through Velikoye.",
    }
    prompt = str(client.prompt_history[-1]["prompt"])
    assert "Khorol River" in prompt

    # cached: a second ask queues no reply and still answers, no new call
    async with MockClientContext():
        await _act(plugin, "group_synopsis", thing_id=s.velikoye, tag="river")
        await _drain(plugin)
    assert len(client.prompt_history) == 1
    assert _last(plugin, "group_synopsis")["data"]["synopsis"] == out["synopsis"]


async def test_group_synopsis_unknown_entry_fails(plugin, client):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()
    await _act(plugin, "group_synopsis", thing_id="f" * 32, tag="river")
    assert "no such entry" in _errors(plugin)[-1]["error"]["message"]
    assert s.world.head_rev() == head


async def test_group_add_and_accept(plugin, client):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()
    reply = json.dumps(
        {
            "entries": [
                {
                    "name": "The Icewrights' Circle",
                    "kind": "lore",
                    "tag": "guild",
                    "line": "A guild of ice-road pilots.",
                }
            ]
        }
    )

    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(
            plugin,
            "group_add",
            thing_id=s.velikoye,
            tag="guild",
            prompt="a guild of ice-road pilots",
        )
        await _drain(plugin)
    assert s.world.head_rev() == head
    drafted = _last(plugin, "group_add")["data"]
    assert drafted["thing_id"] == s.velikoye
    assert drafted["tag"] == "guild"
    assert drafted["rows"] == [
        {
            "name": "The Icewrights' Circle",
            "kind": "lore",
            "tag": "guild",
            "line": "A guild of ice-road pilots.",
            "ticked": True,
        }
    ]

    await _act(plugin, "accept_group_add", thing_id=s.velikoye, rows=drafted["rows"])
    accepted = _last(plugin, "accept_group_add")["data"]
    assert s.world.head_rev() == head + 1
    assert len(accepted["thing_ids"]) == 1
    new_id = accepted["thing_ids"][0]
    new_state = s.world.view().thing(new_id)
    assert new_state.fields["name"] == "The Icewrights' Circle"
    assert new_state.fields["tag"] == "guild"
    assert filings_of(s.world.view(), new_id)[0].target == s.velikoye


async def test_group_add_top_level_has_no_tag_preset(plugin, client):
    s = await _open_filing_world(plugin)
    reply = json.dumps(
        {
            "entries": [
                {
                    "name": "The Frozen Market",
                    "kind": "lore",
                    "tag": "custom",
                    "line": "A winter market.",
                }
            ]
        }
    )

    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(
            plugin,
            "group_add",
            thing_id=s.velikoye,
            tag=None,
            prompt="a winter custom",
        )
        await _drain(plugin)
    drafted = _last(plugin, "group_add")["data"]
    assert drafted["tag"] is None
    assert drafted["rows"][0]["tag"] == "custom"


async def test_group_add_unknown_entry_fails(plugin, client):
    await _open_filing_world(plugin)
    await _act(plugin, "group_add", thing_id="f" * 32, tag="guild", prompt="anything")
    assert "no such entry" in _errors(plugin)[-1]["error"]["message"]


async def test_connected_synopsis_from_cache(plugin, client):
    """I3: after `group_synopsis`, `get_thing`'s `connected` shows the
    cached synopsis with no model call; it goes back to null once a
    member changes and the cache no longer matches."""

    s = await _open_filing_world(plugin)
    velikoye = await _get_thing(plugin, s.velikoye)
    assert _group(velikoye, "river")["synopsis"] is None

    reply = json.dumps({"synopsis": "The Khorol River runs through Velikoye."})
    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(plugin, "group_synopsis", thing_id=s.velikoye, tag="river")
        await _drain(plugin)
    calls = len(client.prompt_history)

    velikoye = await _get_thing(plugin, s.velikoye)
    assert _group(velikoye, "river")["synopsis"] == (
        "The Khorol River runs through Velikoye."
    )
    # reading it back made no model call
    assert len(client.prompt_history) == calls

    with s.world.revision(Source.manual(note="edit")) as rev:
        rev.add_fact(s.khorol, "description", "Something changed.")
    velikoye = await _get_thing(plugin, s.velikoye)
    assert _group(velikoye, "river")["synopsis"] is None


async def test_group_synopsis_force_regenerates(plugin, client):
    s = await _open_filing_world(plugin)
    reply = json.dumps({"synopsis": "First telling."})
    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(plugin, "group_synopsis", thing_id=s.velikoye, tag="river")
        await _drain(plugin)
    assert _last(plugin, "group_synopsis")["data"]["synopsis"] == "First telling."

    async with MockClientContext():
        # no reply queued: without force, it would answer from the cache
        client_responses.get().append(json.dumps({"synopsis": "Forced telling."}))
        await _act(
            plugin, "group_synopsis", thing_id=s.velikoye, tag="river", force=True
        )
        await _drain(plugin)
    assert _last(plugin, "group_synopsis")["data"]["synopsis"] == "Forced telling."
    assert len(client.prompt_history) == 2


async def test_group_synopsis_unusable_reply_fails(plugin, client):
    s = await _open_filing_world(plugin)
    async with MockClientContext():
        client_responses.get().append(json.dumps({"nonsense": True}))
        await _act(plugin, "group_synopsis", thing_id=s.velikoye, tag="river")
        await _drain(plugin)
    assert "synopsis" in _last(plugin, "group_synopsis_failed")["message"]


async def test_fixed_group_synopsis_answer_without_a_model(
    plugin, tmp_path, monkeypatch
):
    s = await _open_filing_world(plugin)
    path = tmp_path / "fixed-group-synopsis.json"
    path.write_text(json.dumps({"synopsis": "A fixed telling of Velikoye's rivers."}))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_GROUP_SYNOPSIS", str(path))
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    await _act(plugin, "group_synopsis", thing_id=s.velikoye, tag="river")
    await _drain(plugin)
    out = _last(plugin, "group_synopsis")["data"]
    assert out["synopsis"] == "A fixed telling of Velikoye's rivers."


async def test_fixed_group_add_answer_without_a_model(plugin, tmp_path, monkeypatch):
    s = await _open_filing_world(plugin)
    path = tmp_path / "fixed-group-add.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "name": "The Icewrights",
                        "kind": "lore",
                        "tag": "guild",
                        "line": "A guild of ice-road pilots.",
                    }
                ]
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_GROUP_ADD", str(path))
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    await _act(plugin, "group_add", thing_id=s.velikoye, tag="guild", prompt="a guild")
    await _drain(plugin)
    drafted = _last(plugin, "group_add")["data"]
    assert drafted["rows"] == [
        {
            "name": "The Icewrights",
            "kind": "lore",
            "tag": "guild",
            "line": "A guild of ice-road pilots.",
            "ticked": True,
        }
    ]


async def test_add_facts(plugin, client):
    s = await _open_filing_world(plugin)
    tower = "The Court meets in the old observatory tower."
    with s.world.revision(Source.manual()) as rev:
        rev.add_fact(s.court, "general", tower)
    head = s.world.head_rev()
    reply = json.dumps(
        {
            "facts": [
                {"category": "general", "text": "It meets after moonrise."},
                {"category": "general", "text": "It meets in the Khorol River."},
                {"category": "nonsense", "text": tower},
            ]
        }
    )
    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(plugin, "add_facts", thing_id=s.court, prompt="when it meets")
        await _drain(plugin)
    assert s.world.head_rev() == head
    prompt = str(client.prompt_history[-1]["prompt"])
    assert "when it meets" in prompt and "The nocturnal council." in prompt
    drafted = _last(plugin, "add_facts")["data"]
    assert [f["rendered"] for f in drafted["facts"]] == [
        "It meets after moonrise.",
        "It meets in the Khorol River.",
        tower,
    ]
    # a link as it would be written, and a repeat arrives unticked
    assert drafted["facts"][1]["segments"][1]["ref"] == s.khorol
    assert drafted["facts"][2]["repeat_of"] is not None
    assert [f["ticked"] for f in drafted["facts"]] == [True, True, False]

    draft = drafted["draft"]
    draft["facts"][0]["ticked"] = False
    await _act(plugin, "accept_facts", draft=draft)
    accepted = _last(plugin, "accept_facts")["data"]
    assert s.world.head_rev() == head + 1
    assert len(accepted["fact_ids"]) == 1
    texts = [f["text"] for f in accepted["facts"]]
    assert f"It meets in the {ref(s.khorol, 'Khorol River')}." in texts
    assert "It meets after moonrise." not in texts


async def test_add_event(plugin, client):
    s = await _open_filing_world(plugin)
    reply = json.dumps(
        {"facts": [{"category": "general", "text": "The Court was founded."}]}
    )
    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(
            plugin, "add_event", thing_id=s.court, prompt="its founding", year=880
        )
        await _drain(plugin)
    assert "880" in str(client.prompt_history[-1]["prompt"])
    drafted = _last(plugin, "add_event")["data"]
    assert drafted["facts"][0]["since"]["label"] == "880"
    await _act(plugin, "accept_facts", draft=drafted["draft"])
    court = _last(plugin, "accept_facts")["data"]
    line = next(
        line for line in court["entry_timeline"] if line["date"]["label"] == "880"
    )
    assert line["segments"] == [_plain("The Court was founded.")]


async def test_fact_draft_failure_is_reported(plugin, client):
    s = await _open_filing_world(plugin)
    async with MockClientContext():
        client_responses.get().append("no json here")
        await _act(plugin, "add_facts", thing_id=s.court, prompt="anything")
        await _drain(plugin)
    assert "no facts" in _last(plugin, "add_facts_failed")["message"]


async def test_make_stub_from_text(plugin):
    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        fact = rev.add_fact(
            s.court,
            "general",
            f"It sits in the Hall of Dusk near {ref(s.khorol, 'the river')}.",
        )
    head = s.world.head_rev()
    rendered = "It sits in the Hall of Dusk near the river."
    start = rendered.index("Hall of Dusk")

    await _act(
        plugin,
        "make_stub_from_text",
        fact_id=fact,
        start=start - 1,
        end=start + len("Hall of Dusk"),
        kind="place",
        tag="hall",
        filing={"target_id": s.velikoye, "role": "stands in"},
    )
    reply = _last(plugin, "make_stub_from_text")["data"]
    assert s.world.head_rev() == head + 1
    stub = s.world.view().thing(reply["stub_id"])
    assert stub.is_stub and stub.kind == "place" and stub.fields["tag"] == "hall"
    assert [(f.target, f.role) for f in filings_of(s.world.view(), stub.id)] == [
        (s.velikoye, "stands in")
    ]
    text = next(f["text"] for f in reply["facts"] if f["fact_id"] == fact)
    assert text == (
        f"It sits in the {ref(stub.id, 'Hall of Dusk')} near"
        f" {ref(s.khorol, 'the river')}."
    )

    # cutting through a link, or taking one in, is refused
    river = rendered.index("the river")
    for start_, end_ in ((river + 2, river + 6), (0, len(rendered))):
        before = len(_errors(plugin))
        await _act(
            plugin,
            "make_stub_from_text",
            fact_id=fact,
            start=start_,
            end=end_,
            kind="place",
        )
        assert len(_errors(plugin)) == before + 1
    assert s.world.head_rev() == head + 1


async def test_link_text(plugin):
    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        fact = rev.add_fact(
            s.dawn, "general", f"Its {ref(s.vigil, 'vigil')} is kept in the capital."
        )
    rendered = "Its vigil is kept in the capital."
    start = rendered.index("the capital")

    await _act(
        plugin,
        "link_text",
        fact_id=fact,
        start=start,
        end=start + len("the capital"),
        target_id=s.velikoye,
    )
    dawn = _last(plugin, "link_text")["data"]
    text = next(f["text"] for f in dawn["facts"] if f["fact_id"] == fact)
    assert text == (
        f"Its {ref(s.vigil, 'vigil')} is kept in {ref(s.velikoye, 'the capital')}."
    )

    head = s.world.head_rev()
    before = len(_errors(plugin))
    # inside a link; the fact's own entry; a target that isn't there
    await _act(plugin, "link_text", fact_id=fact, start=4, end=6, target_id=s.court)
    await _act(plugin, "link_text", fact_id=fact, start=0, end=3, target_id=s.dawn)
    await _act(plugin, "link_text", fact_id=fact, start=0, end=3, target_id="0" * 32)
    assert len(_errors(plugin)) == before + 3
    assert s.world.head_rev() == head


async def test_copy_fact(plugin):
    s = await _open_filing_world(plugin)
    original = next(
        f.fact_id
        for f in s.world.view().thing(s.court).facts
        if f.category == "general"
    )
    head = s.world.head_rev()

    await _act(plugin, "copy_fact", fact_id=original, target_id=s.dawn)
    reply = _last(plugin, "copy_fact")["data"]
    assert s.world.head_rev() == head + 1
    assert reply["fact_id"] != original
    assert "The nocturnal council." in [f["text"] for f in reply["target"]["facts"]]
    # the original stays
    assert s.world.view().fact(original)[0] == s.court

    before = len(_errors(plugin))
    await _act(plugin, "copy_fact", fact_id=original, target_id=s.court)
    await _act(plugin, "copy_fact", fact_id="0" * 32, target_id=s.dawn)
    assert len(_errors(plugin)) == before + 2
    assert s.world.head_rev() == head + 1


async def test_repoint_ref_teaches_the_target_its_names(plugin):
    """The hover card's single-link "Re-point...": the target learns the
    link's words and the stub's names as other names, as `repoint_stub`
    teaches them."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        tsar = rev.create_thing(
            "character",
            {
                "name": "The Old Tsar",
                "aka": [_aka("Grandfather Owl")],
                "stub": {"ignored": False},
            },
        )
        fact = rev.add_fact(s.court, "general", f"Founded by {ref(tsar, 'the Tsar')}.")
    head = s.world.head_rev()

    await _act(
        plugin,
        "repoint_ref",
        thing_id=s.court,
        fact_id=fact,
        occurrence=0,
        to_id=s.dmitry,
    )
    reply = _last(plugin, "repoint_ref")["data"]
    assert s.world.head_rev() == head + 1
    assert reply["aka_added"] == ["the Tsar", "The Old Tsar", "Grandfather Owl"]
    aka = s.world.view().thing(s.dmitry).fields["aka"]
    assert [entry["name"] for entry in aka] == [
        "the Tsar",
        "The Old Tsar",
        "Grandfather Owl",
    ]
    assert all(entry["tag"] == "common" for entry in aka)
    s.world.undo([s.world.head_rev()])
    assert "aka" not in s.world.view().thing(s.dmitry).fields


async def test_change_stub_kind_notes_dropped_fields(plugin):
    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        rev.change_stub_kind(s.wattle, "event")
        rev.set_field(s.wattle, "when", WorldDate.of(412).model_dump(), None)

    await _act(plugin, "change_stub_kind", id=s.wattle, kind="lore")
    reply = _last(plugin, "change_stub_kind")["data"]
    assert reply["kind"] == "lore"
    assert reply["notes"] == ["a lore has no when: it was dropped"]
    # its tag and filing stay
    assert reply["tag"] == "district"
    assert [row["target_id"] for row in reply["in"]] == [s.velikoye]


def _draft_reply(name, *facts, tag="military", **extra):
    return json.dumps(
        {
            "name": name,
            "tag": tag,
            "facts": [{"category": "general", "text": text} for text in facts],
            **extra,
        }
    )


async def _preview(plugin, client, reply, **data):
    async with MockClientContext():
        client_responses.get().append(reply)
        client_responses.get().append("The prose.")
        await _act(plugin, "preview_thing", **{"kind": "lore", "fields": {}, **data})
        await _drain(plugin)
    return _last(plugin, "preview_thing")["data"]


async def test_preview_thing_answers_a_draft_page(plugin, client):
    s = await _open_filing_world(plugin)
    head = s.world.head_rev()
    reply = _draft_reply(
        "The Frostwing Host",
        "The Host guards the Khorol River.",
        **{"in": [{"entry": "Tsardom of Moscavia", "role": "the realm's army"}]},
    )
    draft = await _preview(
        plugin,
        client,
        reply,
        prompt="the army of the Tsardom of Moscavia",
        picks={"Tsardom of Moscavia": s.tsardom},
        hint="order",
    )
    assert s.world.head_rev() == head
    assert draft["draft"] is True and draft["id"] is None
    assert (draft["name"], draft["kind"], draft["tag"], draft["hint"]) == (
        "The Frostwing Host",
        "lore",
        "military",
        "order",
    )
    assert (draft["version"], draft["draft_key"]) == (1, "new:lore:frostwing host")
    assert draft["versions"] == [
        {
            "version": 1,
            "name": "The Frostwing Host",
            "prompt": "the army of the Tsardom of Moscavia",
        }
    ]
    fact = draft["facts"][0]
    assert (fact["draft"], fact["ticked"]) == (True, True)
    assert fact["segments"][1] == {
        "text": "Khorol River",
        "ref": s.khorol,
        "stub": False,
    }
    assert draft["in"] == [
        {
            "target_id": s.tsardom,
            "target_name": "Tsardom of Moscavia",
            "role": "the realm's army",
            "since": None,
            "until": None,
            "within_id": None,
            "within_name": None,
            "exceptions": [],
            "draft": True,
            "ticked": False,
        }
    ]
    assert draft["prose"]["description"]["text"].endswith("The prose.")
    assert draft["connected"] == [] and draft["mentioned_in"] == []
    assert draft["preview"]["name"] == "The Frostwing Host"
    json.dumps(draft)

    # accepted: the hint is stored on the entry, the draft is done
    await _act(
        plugin,
        "accept_preview",
        preview=draft["preview"],
        draft_key=draft["draft_key"],
    )
    host = _last(plugin, "accept_preview")["data"]
    assert (host["hint"], host["tag"]) == ("order", "military")
    assert plugin._drafts == {}


async def test_versions_restore(plugin, client):
    s = await _open_filing_world(plugin)
    first = await _preview(
        plugin, client, _draft_reply("Frostwing Host", "One."), prompt="an army"
    )
    key = first["draft_key"]
    # a regeneration keeps its draft's key whatever the model names it
    second = await _preview(
        plugin,
        client,
        _draft_reply("The White Wing", "Two."),
        prompt="an army of owls",
        draft_key=key,
    )
    assert (second["draft_key"], second["version"]) == (key, 2)
    assert [v["name"] for v in second["versions"]] == [
        "Frostwing Host",
        "The White Wing",
    ]

    await _act(plugin, "use_version", draft_key=key, version=1)
    restored = _last(plugin, "use_version")["data"]
    assert (restored["version"], restored["name"]) == (1, "Frostwing Host")
    assert restored["preview"]["facts"][0]["text"] == "One."
    assert len(restored["versions"]) == 2

    # at most five are kept, the oldest dropped first
    for index in range(4):
        last = await _preview(
            plugin,
            client,
            _draft_reply(f"Host {index}", "More."),
            prompt="again",
            draft_key=key,
        )
    assert last["version"] == 5
    assert [v["name"] for v in last["versions"]] == [
        "The White Wing",
        "Host 0",
        "Host 1",
        "Host 2",
        "Host 3",
    ]
    before = len(_errors(plugin))
    await _act(plugin, "use_version", draft_key=key, version=6)
    await _act(plugin, "use_version", draft_key="new:lore:nothing", version=1)
    assert len(_errors(plugin)) == before + 2
    assert s.world.head_rev()


async def test_discard_writes_nothing(plugin, client):
    """Discard after Regenerate: no stub, filing or fact is written, and
    the earlier versions are gone."""

    s = await _open_filing_world(plugin)
    head = s.world.head_rev()
    reply = _draft_reply(
        "Frostwing Host",
        "The Host drills on the Frosted Field.",
        names=[{"name": "Frosted Field", "kind": "place", "tag": "field"}],
        **{
            "in": [{"entry": "Velikoye", "role": "garrisoned here"}],
            "file_into": [{"entry": "Dawn Vigil", "role": None}],
        },
    )
    first = await _preview(plugin, client, reply, prompt="an army", stub_id=None)
    await _preview(
        plugin, client, reply, prompt="an army", draft_key=first["draft_key"]
    )
    things = len(s.world.view().things())

    await _act(plugin, "discard_preview", draft_key=first["draft_key"])
    assert _last(plugin, "discard_preview")["data"] == {"draft_key": first["draft_key"]}
    assert s.world.head_rev() == head
    assert len(s.world.view().things()) == things
    assert plugin._drafts == {}
    before = len(_errors(plugin))
    await _act(plugin, "use_version", draft_key=first["draft_key"], version=1)
    assert len(_errors(plugin)) == before + 1


async def test_stub_draft_starts_from_its_page(plugin, client):
    s = await _open_filing_world(plugin)
    reply = _draft_reply("Wattle Row", "Wattlemakers work here.", tag="street")
    draft = await _preview(
        plugin, client, reply, kind="place", prompt="the street", stub_id=s.wattle
    )
    assert (draft["id"], draft["draft_key"]) == (s.wattle, f"stub:{s.wattle}")
    # its filing so far, then the draft's own rows
    assert [row["target_id"] for row in draft["in"]] == [s.velikoye]
    assert "draft" not in draft["in"][0]
    # a stub's own tag stands
    assert draft["tag"] == "district"


async def test_forged_filing_rows_refused(plugin, client):
    """The rows a client sends back on accept are checked, never trusted:
    an "In" row into a target that's gone or never was, one that would
    make a cycle, one `within` a part that isn't the target's, an
    exception departing from a fact that isn't the target's, and a "File
    into this" row naming a forged thing id, file nothing as sent."""

    s = await _open_filing_world(plugin)
    draft = await _preview(
        plugin,
        client,
        _draft_reply("Frostwing Host", "The Host guards the capital."),
        kind="character",
        prompt="a host",
    )
    preview = draft["preview"]
    with s.world.revision(Source.manual()) as rev:
        gone = rev.create_thing("lore", {"name": "Gone Order"})
    with s.world.revision(Source.manual()) as rev:
        rev.remove_thing(gone)

    def row(target, **extra):
        return {
            "target_id": target,
            "target_name": "x",
            "role": None,
            "ticked": True,
            **extra,
        }

    preview["filings"] = [
        row(gone),
        row("0" * 32),
        row(s.court, within=s.dawn),
        row(
            s.dawn,
            exceptions=[
                {"text": "Skips it.", "item": "x", "fact_id": s.capital},
                {"text": "Skips the vigil.", "item": "x", "thing_id": s.court},
            ],
        ),
    ]
    preview["file_into"] = [
        {"thing_id": "0" * 32, "name": "Forged", "ticked": True},
        {"thing_id": gone, "name": "Gone Order", "ticked": True},
    ]
    await _act(plugin, "accept_preview", preview=preview)
    host = _last(plugin, "accept_preview")["data"]
    rows = {r["target_id"]: r for r in host["in"]}
    # the dead and unknown targets are left out, with notes
    assert set(rows) == {s.court, s.dawn}
    assert any("isn't filed" in n or "is gone" in n for n in host["notes"])
    # within a part that isn't the target's: filed in the target whole
    assert rows[s.court]["within_id"] is None
    # an exception from a fact not the target's, or an entry not filed in
    # it, is dropped
    assert rows[s.dawn]["exceptions"] == []
    # nothing was filed into the new entry from forged rows
    assert host["connected"] == []

    # a cycle: an entry filed in the Night Court, then a draft of the
    # Court's own target filed into that entry
    draft = await _preview(
        plugin,
        client,
        _draft_reply("Moon Hall", "A hall."),
        kind="place",
        prompt="a hall",
    )
    preview = draft["preview"]
    preview["file_into"] = [
        {"thing_id": s.velikoye, "name": "Velikoye", "ticked": True}
    ]
    preview["filings"] = [row(s.court)]
    await _act(plugin, "accept_preview", preview=preview)
    hall = _last(plugin, "accept_preview")["data"]
    # filed in the Court (in Velikoye), so Velikoye can't be filed in it
    assert [r["target_id"] for r in hall["in"]] == [s.court]
    assert hall["connected"] == []
    assert any("inside itself" in note for note in hall["notes"])

    # the filing actions check what they're sent the same way: a forged
    # thing id is refused, writing nothing
    head = s.world.head_rev()
    before = len(_errors(plugin))
    await _act(plugin, "add_filing", thing_id="f" * 32, target_id=s.court)
    await _act(plugin, "add_filing", thing_id=s.court, target_id=gone)
    assert len(_errors(plugin)) == before + 2
    assert s.world.head_rev() == head


async def test_fixed_preview_carries_names_with_tag_and_filing(
    plugin, tmp_path, monkeypatch
):
    s = await _open_filing_world(plugin)
    _fixed_preview_file(
        tmp_path,
        monkeypatch,
        name="Frostwing Host",
        tag="military",
        facts=[{"category": "general", "text": "It drills on the Frosted Field."}],
        prose={"description": "A host."},
        names=[
            {
                "name": "Frosted Field",
                "kind": "place",
                "tag": "field",
                "in": "Frostwing Host",
            },
            {"name": "Dawn Vigil", "kind": "lore", "in": "Frostwing Host"},
        ],
        **{"in": [{"entry": "Velikoye", "role": "garrisoned here"}]},
    )
    await _act(plugin, "preview_thing", kind="lore", prompt="a host", fields={})
    await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]["preview"]
    assert preview["tag"] == "military"
    assert [r["target_id"] for r in preview["filings"]] == [s.velikoye]
    (name,) = preview["new_names"]
    assert (name["name"], name["tag"]) == ("Frosted Field", "field")
    assert name["filing"]["this_entry"] is True
    assert [r["thing_id"] for r in preview["file_into"]] == [s.vigil]


async def test_fixed_facts_answer_without_a_model(plugin, tmp_path, monkeypatch):
    s = await _open_filing_world(plugin)
    path = tmp_path / "fixed-facts.json"
    path.write_text(
        json.dumps({"facts": [{"category": "general", "text": "It meets at dusk."}]})
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_FACTS", str(path))
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    await _act(plugin, "add_facts", thing_id=s.court, prompt="when")
    await _drain(plugin)
    drafted = _last(plugin, "add_facts")["data"]
    assert [f["rendered"] for f in drafted["facts"]] == ["It meets at dusk."]


async def test_copy_of_a_summary_is_a_plain_fact(plugin):
    s = await _open_filing_world(plugin)
    await _act(plugin, "copy_fact", fact_id=s.capital, target_id=s.tsardom)
    copy_id = _last(plugin, "copy_fact")["data"]["fact_id"]
    _owner, copy = s.world.view().fact(copy_id)
    assert not entries.is_summary_fact(copy)
    assert entries.is_summary_fact(s.world.view().fact(s.capital)[1])


# --- Task 6 fix round 1 ---------------------------------------------------------


async def test_connected_shows_ended_filings_with_their_dates(plugin):
    """At the latest telling Connected lists what was filed in the entry
    and has ended, with its dates ("in Velikoye from 900 to 1015"); at a
    date, only what holds then. Mentioned in leaves out the same set."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        dance = rev.create_thing(
            "lore",
            {
                "name": "The Feather Dance",
                "tag": "custom",
                "filings": [_filed(s.velikoye, since=900, until=1015)],
            },
        )
        rev.add_fact(
            dance, "general", f"Danced in winter in {ref(s.velikoye, 'Velikoye')}."
        )

    velikoye = await _get_thing(plugin, s.velikoye)
    (row,) = _group(velikoye, "custom")["rows"]
    assert (row["id"], row["since"]["label"], row["until"]["label"]) == (
        dance,
        "900",
        "1015",
    )
    assert dance not in [m["id"] for m in velikoye["mentioned_in"]]
    # a dated view: only what holds then
    then = await _get_thing(plugin, s.velikoye, WorldDate.of(950))
    assert [r["id"] for r in _group(then, "custom")["rows"]] == [dance]
    later = await _get_thing(plugin, s.velikoye, WorldDate.of(1018))
    assert "custom" not in [g["tag"] for g in later["connected"]]


async def test_repoint_ref_between_full_entries_teaches_nothing(plugin):
    """A link re-pointed from one full entry to another: the other names
    a live entry goes by are never taught to the target."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        fact = rev.add_fact(
            s.court, "general", f"It meets by {ref(s.khorol, 'Khorol River')}."
        )
    await _act(
        plugin,
        "repoint_ref",
        thing_id=s.court,
        fact_id=fact,
        occurrence=0,
        to_id=s.velikoye,
    )
    assert _last(plugin, "repoint_ref")["data"]["aka_added"] == []
    assert "aka" not in s.world.view().thing(s.velikoye).fields


async def test_repoint_ref_keeps_a_stub_still_named_its_names(plugin):
    """A stub still referenced elsewhere keeps its names: only the link's
    words, which no other entry goes by, are taught."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        tsar = rev.create_thing(
            "character", {"name": "The Old Tsar", "stub": {"ignored": False}}
        )
        fact = rev.add_fact(s.court, "general", f"Founded by {ref(tsar, 'the Tsar')}.")
        rev.add_fact(s.dawn, "general", f"Blessed by {ref(tsar, 'The Old Tsar')}.")
    await _act(
        plugin,
        "repoint_ref",
        thing_id=s.court,
        fact_id=fact,
        occurrence=0,
        to_id=s.dmitry,
    )
    assert _last(plugin, "repoint_ref")["data"]["aka_added"] == ["the Tsar"]


async def test_remove_filing_notes_the_exceptions_it_removed(plugin):
    s = await _open_filing_world(plugin)
    await _act(plugin, "remove_filing", thing_id=s.dmitry, target_id=s.dawn)
    assert _last(plugin, "remove_filing")["data"]["notes"] == [
        'Removed the "but..." "Keeps the Dawn Vigil only on feast days.":'
        " it was an exception to The White Dawn"
    ]
    await _act(plugin, "remove_filing", thing_id=s.dmitry, target_id=s.court)
    assert _last(plugin, "remove_filing")["data"]["notes"] == []


async def test_add_exception_needs_a_real_being(plugin):
    """Ruling C4: a being takes a "but..." only while it's real."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        light = rev.create_thing(
            "being",
            {
                "name": "The Light",
                "existence": "real",
                "filings": [_filed(s.dawn, "patron")],
            },
        )
        spirit = rev.create_thing(
            "being",
            {
                "name": "The Spirit",
                "existence": "believed",
                "filings": [_filed(s.dawn, "patron")],
            },
        )
    await _act(
        plugin,
        "add_exception",
        character_id=light,
        target_id=s.dawn,
        text="Shines at night too.",
    )
    row = next(
        r
        for r in _last(plugin, "add_exception")["data"]["in"]
        if r["target_id"] == s.dawn
    )
    assert len(row["exceptions"]) == 1
    head = s.world.head_rev()
    before = len(_errors(plugin))
    await _act(plugin, "add_exception", character_id=spirit, target_id=s.dawn, text="x")
    assert len(_errors(plugin)) == before + 1
    assert s.world.head_rev() == head


async def test_retag_reaches_deleted_entries_and_past_tags(plugin):
    """A rename reaches a deleted entry's tag, so undoing the delete
    brings it back retagged, and a tag that only holds at a past date
    can be renamed and merged. list_tags leaves ignored stubs out."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        school = rev.create_thing("lore", {"name": "Rune School", "tag": "school"})
        old = rev.create_thing("lore", {"name": "Old School", "tag": "school"})
        guild = rev.create_thing("lore", {"name": "Scribes", "tag": "guild"})
        rev.set_field(guild, "tag", "order", WorldDate.of(1000))
        rev.create_thing(
            "lore", {"name": "Hush", "tag": "secret", "stub": {"ignored": True}}
        )
    with s.world.revision(Source.manual(note="deleted")) as rev:
        rev.remove_thing(old)
    deleted = s.world.head_rev()

    await _act(plugin, "rename_tag", old="school", new="academy")
    assert not _errors(plugin)
    s.world.undo([deleted])
    assert s.world.view().thing(old).fields["tag"] == "academy"
    assert s.world.view().thing(school).fields["tag"] == "academy"

    # "guild" holds only before 1000
    await _act(plugin, "rename_tag", old="guild", new="brotherhood")
    assert not _errors(plugin)
    assert s.world.view(WorldDate.of(950)).thing(guild).fields["tag"] == "brotherhood"
    await _act(plugin, "merge_tag", **{"from": "brotherhood", "into": "academy"})
    assert not _errors(plugin)
    assert s.world.view(WorldDate.of(950)).thing(guild).fields["tag"] == "academy"

    await _act(plugin, "list_tags")
    tags = [t["tag"] for t in _last(plugin, "list_tags")["data"]["tags"]]
    assert "secret" not in tags


async def test_accept_with_a_folded_stub_within_files_the_entry_whole(plugin):
    """M7: an "In" row `within` the bare stub folded into the one being
    filled ("Is this X?" onto a stub) is within the entry itself, so the
    entry is filed in the target whole."""

    s = await _open_filing_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        watch = rev.create_thing(
            "lore",
            {
                "name": "Night Watch",
                "stub": {"ignored": False},
                "filings": [_filed(s.court)],
            },
        )
        captain = rev.create_thing(
            "lore", {"name": "Watch Captaincy", "stub": {"ignored": False}}
        )
        rev.add_fact(s.dawn, "general", f"Guarded by {ref(captain, 'the Captaincy')}.")
    preview = {
        "kind": "lore",
        "prompt": "the watch",
        "name": "Watch Captaincy",
        "stub_id": captain,
        "facts": [{"category": "general", "text": "It keeps the night."}],
        "prose": {},
        "filings": [
            {
                "target_id": s.court,
                "target_name": "The Night Court",
                "within": watch,
                "ticked": True,
            }
        ],
    }
    await _act(plugin, "accept_preview", preview=preview, same_target_id=watch)
    assert not _errors(plugin)
    page = _last(plugin, "accept_preview")["data"]
    assert page["id"] == captain
    (row,) = [r for r in page["in"] if r["target_id"] == s.court]
    assert row["within_id"] is None
    assert s.world.view().thing(watch) is None


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


async def test_selection_offsets_are_utf16_code_units(plugin):
    """Ruling F18: `start`/`end` count UTF-16 code units, as the page's
    JavaScript does; an emoji is two. An offset inside one is refused."""

    s = await _open_filing_world(plugin)
    rendered = "🦉 Owls nest in the Hall of Dusk."
    with s.world.revision(Source.manual()) as rev:
        fact = rev.add_fact(s.court, "general", rendered)
    start = _utf16(rendered[: rendered.index("Hall of Dusk")])
    await _act(
        plugin,
        "link_text",
        fact_id=fact,
        start=start,
        end=start + _utf16("Hall of Dusk"),
        target_id=s.velikoye,
    )
    court = _last(plugin, "link_text")["data"]
    text = next(f["text"] for f in court["facts"] if f["fact_id"] == fact)
    assert text == f"🦉 Owls nest in the {ref(s.velikoye, 'Hall of Dusk')}."

    before = len(_errors(plugin))
    await _act(plugin, "link_text", fact_id=fact, start=1, end=6, target_id=s.velikoye)
    assert len(_errors(plugin)) == before + 1


async def test_drafts_are_bounded_and_a_late_result_after_discard_is_dropped(
    plugin, client
):
    s = await _open_filing_world(plugin)
    keys = []
    for index in range(21):
        draft = await _preview(
            plugin, client, _draft_reply(f"Host {index}", "One."), prompt="a host"
        )
        keys.append(draft["draft_key"])
    # the oldest draft is forgotten once there are more than 20
    assert len(plugin._drafts) == 20
    before = len(_errors(plugin))
    await _act(plugin, "use_version", draft_key=keys[0], version=1)
    assert len(_errors(plugin)) == before + 1
    await _act(plugin, "use_version", draft_key=keys[1], version=1)
    assert len(_errors(plugin)) == before + 1

    # Regenerate, then Discard before the reply comes: it's dropped
    replies = len(_replies(plugin, "preview_thing"))
    async with MockClientContext():
        client_responses.get().append(_draft_reply("Late Host", "Two."))
        client_responses.get().append("Prose.")
        await _act(
            plugin,
            "preview_thing",
            kind="lore",
            fields={},
            prompt="again",
            draft_key=keys[5],
        )
        await _act(plugin, "discard_preview", draft_key=keys[5])
        await _drain(plugin)
    assert len(_replies(plugin, "preview_thing")) == replies
    assert keys[5] not in plugin._drafts
    assert s.world.head_rev()


async def test_add_facts_and_event_on_a_draft(plugin, client):
    """Ruling F16: on a draft page, "+ Add facts..." and "+ Add event..."
    append to the draft's current version on the server, writing nothing,
    and answer with the updated draft; the accept writes them."""

    s = await _open_filing_world(plugin)
    draft = await _preview(
        plugin,
        client,
        _draft_reply("Frostwing Host", "It flies at night."),
        prompt="a host",
    )
    head = s.world.head_rev()
    key = draft["draft_key"]
    async with MockClientContext():
        client_responses.get().append(
            json.dumps(
                {"facts": [{"category": "general", "text": "It drills at dawn."}]}
            )
        )
        await _act(plugin, "add_facts", draft_key=key, prompt="its drills")
        await _drain(plugin)
    assert "Frostwing Host" in str(client.prompt_history[-1]["prompt"])
    added = _last(plugin, "add_facts")["data"]
    assert (added["draft_key"], added["version"]) == (key, 1)
    assert [f["text"] for f in added["facts"]] == [
        "It flies at night.",
        "It drills at dawn.",
    ]
    assert [f["text"] for f in added["preview"]["facts"]] == [
        "It flies at night.",
        "It drills at dawn.",
    ]
    async with MockClientContext():
        client_responses.get().append(
            json.dumps({"facts": [{"category": "general", "text": "It was raised."}]})
        )
        await _act(plugin, "add_event", draft_key=key, prompt="its raising", year=990)
        await _drain(plugin)
    evented = _last(plugin, "add_event")["data"]
    assert evented["preview"]["facts"][-1]["since"] == WorldDate.of(990).model_dump(
        mode="json"
    )
    assert [line["date"]["label"] for line in evented["entry_timeline"]] == ["990"]
    assert s.world.head_rev() == head

    await _act(plugin, "accept_preview", preview=evented["preview"], draft_key=key)
    host = _last(plugin, "accept_preview")["data"]
    assert {"It drills at dawn.", "It was raised."} <= {
        f["text"] for f in host["facts"]
    }


async def test_accept_facts_waits_for_a_stub_draft(plugin, client):
    """A stub being drafted takes facts through its draft: `accept_facts`
    on it is refused, writing nothing, until the draft is accepted or
    discarded."""

    s = await _open_filing_world(plugin)
    draft = await _preview(
        plugin,
        client,
        _draft_reply("Wattle Row", "Wattlemakers work here."),
        kind="place",
        prompt="the street",
        stub_id=s.wattle,
    )
    head = s.world.head_rev()
    fact_draft = {
        "thing_id": s.wattle,
        "prompt": "x",
        "facts": [{"category": "general", "text": "It floods."}],
    }
    before = len(_errors(plugin))
    await _act(plugin, "accept_facts", draft=fact_draft)
    assert "draft" in _errors(plugin)[-1]["error"]["message"]
    assert len(_errors(plugin)) == before + 1
    assert s.world.head_rev() == head
    await _act(plugin, "discard_preview", draft_key=draft["draft_key"])
    await _act(plugin, "accept_facts", draft=fact_draft)
    assert s.world.head_rev() == head + 1


async def test_selection_on_a_draft_names_and_links_by_name(plugin, client):
    """Ruling F16: on a draft fact (by its `index`), "Make a stub" adds a
    new name with its kind and tag, and "Link to..." a pick, both keyed by
    name: every occurrence of the words is linked on accept."""

    s = await _open_filing_world(plugin)
    draft = await _preview(
        plugin,
        client,
        _draft_reply(
            "Frostwing Host",
            "It drills on the Frost Field by the Old Bridge.",
            "The Old Bridge stands.",
        ),
        prompt="a host",
    )
    key = draft["draft_key"]
    head = s.world.head_rev()
    text = "It drills on the Frost Field by the Old Bridge."
    start = text.index("Frost Field")
    await _act(
        plugin,
        "make_stub_from_text",
        draft_key=key,
        index=0,
        start=start,
        end=start + len("Frost Field"),
        kind="place",
        tag="field",
    )
    named = _last(plugin, "make_stub_from_text")["data"]
    (new,) = named["preview"]["new_names"]
    assert (new["name"], new["kind"], new["tag"]) == ("Frost Field", "place", "field")
    start = text.index("Old Bridge")
    await _act(
        plugin,
        "link_text",
        draft_key=key,
        index=0,
        start=start,
        end=start + len("Old Bridge"),
        target_id=s.khorol,
    )
    linked = _last(plugin, "link_text")["data"]
    assert linked["preview"]["picks"] == {"Old Bridge": s.khorol}
    # both occurrences show linked on the draft page
    refs = [
        seg["ref"]
        for fact in linked["facts"]
        for seg in fact["segments"]
        if seg["text"] == "Old Bridge"
    ]
    assert refs == [s.khorol, s.khorol]
    assert s.world.head_rev() == head

    await _act(plugin, "accept_preview", preview=linked["preview"], draft_key=key)
    host = _last(plugin, "accept_preview")["data"]
    texts = [f["text"] for f in host["facts"]]
    field = next(
        t.id
        for t in s.world.view().things("place")
        if t.fields["name"] == "Frost Field"
    )
    assert s.world.view().thing(field).fields["tag"] == "field"
    assert (
        f"It drills on the {ref(field, 'Frost Field')} by the"
        f" {ref(s.khorol, 'Old Bridge')}."
    ) in texts
    assert f"The {ref(s.khorol, 'Old Bridge')} stands." in texts
