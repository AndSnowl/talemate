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
from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.scenes import MessageRecord
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen
from talemate.worldplay.characters import character_from_world
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
    preview = _last(plugin, "preview_thing")["data"]
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

    preview = _last(plugin, "preview_thing")["data"]
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

    preview = _last(plugin, "preview_thing")["data"]
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
    ],
)
async def test_model_actions_say_when_no_ai_client_is_configured(
    plugin, monkeypatch, tmp_path, request_data
):
    """As in the browser tests: no client, and the fixed-reply settings
    naming files that aren't there (no test has written one)."""

    monkeypatch.setenv("TALEMATE_TEST_FIXED_SETUP", str(tmp_path / "no-setup.json"))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(tmp_path / "no-preview.json"))
    world, _maren, _harbour = await _open_world_with_maren(plugin)
    scene_id = world.scenes().create("First", WorldDate.of(313))
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))

    data = {
        key: scene_id if value == "SCENE" else value
        for key, value in request_data.items()
    }
    await plugin.handle({"type": "worlds", **data})
    await _drain(plugin)

    failed = {
        "plan_scene": "plan_failed",
        "continue_scene": "continue_failed",
        "preview_thing": "preview_failed",
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

    preview = _last(plugin, "preview_thing")["data"]
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
    a culture stub is left as it is."""

    world, _maren, _harbour = await _open_world_with_maren(plugin)
    with world.revision(Source.manual(note="stubs")) as rev:
        weir = rev.create_thing(
            "place", {"name": "The Weir", "stub": {"ignored": True}}
        )
        salt = rev.create_thing(
            "culture", {"name": "Saltfolk", "stub": {"ignored": False}}
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
        _plain(" in "),
        {"text": "Moscavia", "ref": s.tsardom, "stub": True},
        _plain("."),
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
    with s.world.revision(Source.manual(note="culture")) as rev:
        rite = rev.create_thing(
            "culture", {"name": "Feather Rite", "stub": {"ignored": False}}
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

    # a culture stub can't be expanded yet, but it has a suggestion
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
    preview = _last(plugin, "preview_thing")["data"]
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
    preview = _last(plugin, "preview_thing")["data"]
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

    # a culture stub can't be expanded yet: the preview fails, saying so
    with world.revision(Source.manual(note="culture")) as rev:
        rite = rev.create_thing(
            "culture", {"name": "Feather Rite", "stub": {"ignored": False}}
        )
    async with MockClientContext():
        await plugin.handle(
            {
                "type": "worlds",
                "action": "preview_thing",
                "kind": "culture",
                "prompt": "Feather Rite",
                "fields": {},
                "stub_id": rite,
            }
        )
        await _drain(plugin)
    assert "culture" in _last(plugin, "preview_failed")["message"]


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
            # the facts, then the one prose section they have facts for
            assert len(client.prompt_history) == 2
            preview = _last(plugin, "preview_thing")["data"]
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
        return _last(plugin, "preview_thing")["data"]

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
