"""The `worlds` websocket router: worlds, things, facts, prose and create.

Driven through the plugin's `handle`, with a stand-in websocket handler
that collects what the plugin queues.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

import talemate.instance as instance
from talemate.world.dates import WorldDate
from talemate.world.store import Source, World
from talemate.server.worlds import WorldsPlugin

from conftest import MockClient, MockClientContext, client_responses


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

        client_responses.get().append("Maren has one eye.")
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

    assert world.prose().get(maren, "description", None).text == "Maren has one eye."
    assert len(_replies(plugin, "prose_updated")) == 2


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

    preview = _last(plugin, "preview_thing")["data"]
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


async def test_thing_actions_need_an_open_world(plugin):
    await plugin.handle({"type": "worlds", "action": "list_things", "kind": "place"})
    assert _replies(plugin, "list_things") == []
    assert "no world" in _last(plugin, "operation_done")["error"]["message"].lower()
