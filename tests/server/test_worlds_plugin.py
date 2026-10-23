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
from talemate.world import spheres
from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.scenes import MessageRecord
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
        {"action": "preview_sphere", "template": "order", "prompt": "a guild"},
        {"action": "fill_drawer", "sphere_id": "SPHERE", "drawer_id": "DRAWER"},
        {"action": "preview_branch", "parent_id": "SPHERE", "prompt": "a schism"},
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
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SPHERE", str(tmp_path / "no-sphere.json"))
    scene_id = world.scenes().create("First", WorldDate.of(313))
    with world.revision(Source.manual(note="sphere")) as rev:
        sphere_id = rev.create_thing(
            "sphere",
            {
                "name": "The Guild",
                "template": "order",
                "drawers": [{"id": "0dd5ea11", "type": "beliefs", "title": "Tenets"}],
            },
        )
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))

    stand_ins = {"SCENE": scene_id, "SPHERE": sphere_id, "DRAWER": "0dd5ea11"}
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
        "preview_sphere": "preview_sphere_failed",
        "fill_drawer": "fill_failed",
        "preview_branch": "preview_branch_failed",
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
    can't take, the target's own use of the stub, and a scene's use.
    Another live stub is a target like any entry."""

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

    # a place's parent can't be lore: the use is named
    with world.revision(Source.manual(note="parent")) as rev:
        rev.set_field(s.harbour, "parent", s.tsardom, None)
    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=saltlore)
    message = _last(plugin, "operation_done")["error"]["message"]
    assert "The Harbour's parent" in message and "lore" in message
    assert world.head_rev() == head
    world.undo([head])

    # the target's own parent is the stub: it would be its own parent
    with world.revision(Source.manual(note="own parent")) as rev:
        rev.set_field(s.moscavy, "parent", s.tsardom, None)
    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=s.moscavy)
    message = _last(plugin, "operation_done")["error"]["message"]
    assert "Moscavy's parent" in message
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
                # the stub's own kind decides, whatever is asked
                "kind": "lore",
                "prompt": "Feather Rite",
                "fields": {},
                "stub_id": rite,
            }
        )
        await _drain(plugin)
    assert "a culture stub can't be expanded" in str(_last(plugin, "preview_failed"))


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

    # a culture stub can't be expanded, fixed preview or not
    with s.world.revision(Source.manual(note="culture")) as rev:
        rite = rev.create_thing(
            "culture", {"name": "Feather Rite", "stub": {"ignored": False}}
        )
    await plugin.handle(
        {
            "type": "worlds",
            "action": "preview_thing",
            "kind": "lore",
            "prompt": "a rite",
            "fields": {},
            "stub_id": rite,
        }
    )
    await _drain(plugin)
    assert "a culture stub can't be expanded" in str(_last(plugin, "preview_failed"))
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


# --- spheres -----------------------------------------------------------------

DOCTRINES, RITES, SITES, LANDS = "d0c7a1e5", "a1e5d0c7", "5175e5ab", "1a4d5ab0"


def _drawer(drawer_id, type_, title):
    return {"id": drawer_id, "type": type_, "title": title}


def _text(segments):
    return "".join(run["text"] for run in segments)


async def _open_sphere_world(plugin):
    """Present 1020. The White Dawn, a religion with Doctrines, Rites and
    Holy Sites: the Dawn Vigil (lore) in Rites, Dawn Peak (a place) in
    Holy Sites, a statement in Doctrines, an `about` fact and a dated
    timeline fact naming the Peak. The Reformed Dawn, its branch. The
    Tsardom, a place that's a nation sphere. Vasha, a practitioner of the
    Dawn since 1010 who skips the Vigil; Maren, tied to nothing."""

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
            "sphere",
            {
                "name": "The White Dawn",
                "template": "religion",
                "agent": True,
                "drawers": [
                    _drawer(DOCTRINES, "beliefs", "Doctrines"),
                    _drawer(RITES, "practices", "Rites"),
                    _drawer(SITES, "places", "Holy Sites"),
                ],
            },
        )
        s.vigil = rev.create_thing(
            "lore",
            {"name": "Dawn Vigil", "part_of": {"sphere": s.dawn, "drawer": RITES}},
        )
        rev.add_fact(s.vigil, "general", "A nightly prayer at first light.")
        s.peak = rev.create_thing(
            "place",
            {"name": "Dawn Peak", "part_of": {"sphere": s.dawn, "drawer": SITES}},
        )
        rev.add_fact(s.peak, "description", "A white mountain.")
        s.unblessed = rev.add_fact(
            s.dawn,
            "statement",
            "The unchanged are unblessed.",
            origin={"drawer": DOCTRINES},
        )
        rev.add_fact(s.dawn, "about", "The state church.")
        s.synod = rev.add_fact(
            s.dawn,
            "timeline",
            f"The First Synod meets on {ref(s.peak, 'Dawn Peak')}.",
            valid_from=WorldDate.of(996),
        )
        s.reformed = rev.create_thing(
            "sphere",
            {"name": "The Reformed Dawn", "template": "religion", "parent": s.dawn},
        )
        s.tsardom = rev.create_thing(
            "place",
            {
                "name": "Tsardom",
                "kind": "country",
                "template": "nation",
                "drawers": [_drawer(LANDS, "places", "Lands")],
            },
        )
        rev.add_fact(s.tsardom, "description", "A northern realm.")
        s.vasha = rev.create_thing(
            "character",
            {
                "name": "Vasha",
                "ties": [
                    {
                        "sphere": s.dawn,
                        "role": "practitioner",
                        "since": WorldDate.of(1010).model_dump(mode="json"),
                        "until": None,
                    }
                ],
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


async def test_payload_sphere_part_of_ties(plugin):
    s = await _open_sphere_world(plugin)

    dawn = await _get_thing(plugin, s.dawn)
    sphere = dawn["sphere"]
    assert (sphere["template"], sphere["agent"]) == ("religion", True)
    assert [(d["id"], d["type"], d["title"]) for d in sphere["drawers"]] == [
        (DOCTRINES, "beliefs", "Doctrines"),
        (RITES, "practices", "Rites"),
        (SITES, "places", "Holy Sites"),
    ]
    doctrines, rites, sites = sphere["drawers"]
    assert doctrines["items"] == [
        {
            "thing_id": None,
            "fact_id": s.unblessed,
            "name": "The unchanged are unblessed.",
            "segments": [_plain("The unchanged are unblessed.")],
            "inherited": False,
            "stub": False,
            # a statement in a religion's beliefs drawer: the Dawn holds it
            "held_by": {"id": s.dawn, "name": "The White Dawn"},
        }
    ]
    assert rites["items"] == [
        {
            "thing_id": s.vigil,
            "fact_id": None,
            "name": "Dawn Vigil",
            "segments": [_plain("A nightly prayer at first light.")],
            "inherited": False,
            "stub": False,
            "held_by": None,
        }
    ]
    assert [i["thing_id"] for i in sites["items"]] == [s.peak]
    assert sphere["people"] == [
        {
            "character_id": s.vasha,
            "name": "Vasha",
            "role": "practitioner",
            "since": sphere["people"][0]["since"],
            "until": None,
            "within": None,
            "within_name": None,
        }
    ]
    assert sphere["people"][0]["since"]["label"] == "1010"
    assert sphere["territory"] == [{"id": s.peak, "name": "Dawn Peak"}]
    (synod,) = sphere["timeline"]
    assert synod["fact_id"] == s.synod
    assert synod["date"]["label"] == "996"
    assert synod["segments"][1] == {"text": "Dawn Peak", "ref": s.peak, "stub": False}
    assert "[[thing:" not in json.dumps(sphere)
    assert sphere["branches"] == [{"id": s.reformed, "name": "The Reformed Dawn"}]
    assert sphere["parent"] is None
    assert dawn["part_of"] is None
    assert dawn["ties"] == []

    # a branch: its parent, and what it inherits
    reformed = (await _get_thing(plugin, s.reformed))["sphere"]
    assert reformed["parent"] == {"id": s.dawn, "name": "The White Dawn"}
    assert reformed["agent"] is True
    assert reformed["people"] == []
    inherited = [i for d in reformed["drawers"] for i in d["items"]]
    assert inherited and all(i["inherited"] for i in inherited)

    # an item: the sphere and drawer it's part of
    vigil = await _get_thing(plugin, s.vigil)
    assert vigil["sphere"] is None
    assert vigil["part_of"] == {
        "sphere_id": s.dawn,
        "sphere_name": "The White Dawn",
        "drawer_id": RITES,
        "drawer_title": "Rites",
    }

    # a character: its ties, each with its exceptions
    vasha = await _get_thing(plugin, s.vasha)
    assert vasha["sphere"] is None
    (tie,) = vasha["ties"]
    assert {k: tie[k] for k in ("sphere_id", "sphere_name", "role", "until")} == {
        "sphere_id": s.dawn,
        "sphere_name": "The White Dawn",
        "role": "practitioner",
        "until": None,
    }
    assert tie["since"]["label"] == "1010"
    (skips,) = tie["exceptions"]
    assert skips["fact_id"] == s.skips
    assert _text(skips["segments"]) == "Skips the vigil. Departs from Dawn Vigil"
    assert skips["segments"][-1]["ref"] == s.vigil

    # a place that's a sphere has both
    tsardom = await _get_thing(plugin, s.tsardom)
    assert tsardom["kind"] == "place"
    assert tsardom["fields"]["kind"] == "country"
    assert tsardom["sphere"]["template"] == "nation"
    assert tsardom["sphere"]["agent"] is True
    assert tsardom["sphere"]["territory"] == [{"id": s.tsardom, "name": "Tsardom"}]
    assert tsardom["sphere"]["parent"] is None

    # a part-of drawer that's gone shows as Unsorted
    with s.world.revision(Source.manual(note="move")) as rev:
        rev.set_field(s.peak, "part_of", {"sphere": s.dawn, "drawer": "0badd0e5"}, None)
    peak = await _get_thing(plugin, s.peak)
    assert peak["part_of"]["drawer_id"] == "0badd0e5"
    assert peak["part_of"]["drawer_title"] == "Unsorted"
    json.dumps(plugin.websocket_handler.messages)


async def test_list_things_spheres_by_template(plugin):
    s = await _open_sphere_world(plugin)
    await _act(plugin, "list_things", kind="sphere")
    listed = _last(plugin, "list_things")["data"]
    assert listed["kind"] == "sphere"
    by_id = {t["id"]: t for t in listed["things"]}
    # the place sphere is listed with the spheres, as its kind
    assert set(by_id) == {s.dawn, s.reformed, s.tsardom}
    assert by_id[s.tsardom]["kind"] == "place"
    assert by_id[s.dawn]["template"] == "religion"
    assert [
        (group["template"], [t["id"] for t in group["things"]])
        for group in listed["groups"]
    ] == [("religion", [s.dawn, s.reformed]), ("nation", [s.tsardom])]


CORE_SYNOD = json.dumps(
    {
        "name": "The Iron Synod",
        "summary": "A council of smiths who keep the forges.",
        "aka": [],
        "timeline": [{"year": 1001, "text": "The Synod was founded."}],
        "drawers": [{"type": "beliefs", "title": "Tenets"}],
        "items": [{"drawer": "Tenets", "name": "", "text": "Iron is holy."}],
        "names": [],
    }
)


async def test_preview_sphere_then_accept(plugin, client):
    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    async with MockClientContext():
        client_responses.get().append(CORE_SYNOD)
        await _act(
            plugin,
            "preview_sphere",
            template="order",
            prompt="a council of smiths",
            fields={},
        )
        await _drain(plugin)
    preview = _last(plugin, "preview_sphere")["data"]
    assert preview["name"] == "The Iron Synod"
    assert preview["template"] == "order"
    assert s.world.head_rev() == head
    json.dumps(preview)

    await _act(plugin, "accept_sphere", preview=preview)
    assert not _errors(plugin)
    accepted = _last(plugin, "accept_sphere")["data"]
    assert accepted["kind"] == "sphere"
    assert accepted["name"] == "The Iron Synod"
    assert accepted["sphere"]["template"] == "order"
    tenets = next(d for d in accepted["sphere"]["drawers"] if d["title"] == "Tenets")
    assert [i["name"] for i in tenets["items"]] == ["Iron is holy."]
    assert accepted["prose"]["description"]["text"] == (
        "A council of smiths who keep the forges."
    )
    # the summary is its own fact (ruling P21): named in the payload, so
    # the page shows it as the summary, not as an about row
    summary_id = accepted["sphere"]["summary_fact_id"]
    (summary,) = [f for f in accepted["facts"] if f["fact_id"] == summary_id]
    assert (summary["category"], summary["rendered"]) == (
        "about",
        "A council of smiths who keep the forges.",
    )
    assert not plugin.tasks


async def test_preview_sphere_promotes(plugin, client):
    """`promote_id` reaches `preview_sphere`: the place stays a place."""

    s = await _open_sphere_world(plugin)
    async with MockClientContext():
        client_responses.get().append(CORE_SYNOD)
        await _act(
            plugin,
            "preview_sphere",
            template="order",
            prompt="the peak as an order",
            promote_id=s.peak,
        )
        await _drain(plugin)
    preview = _last(plugin, "preview_sphere")["data"]
    assert preview["promote_id"] == s.peak
    assert preview["kind"] == "place"


FILL_RITES = json.dumps(
    {
        "new_items": [
            {"name": "", "text": "Smiths sing to the anvil when the bells ring."}
        ],
        "names": [],
    }
)


async def test_fill_drawer_then_accept(plugin, client):
    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    async with MockClientContext():
        client_responses.get().append(FILL_RITES)
        await _act(plugin, "fill_drawer", sphere_id=s.dawn, drawer_id=RITES)
        await _drain(plugin)
        filled = _last(plugin, "fill_drawer")["data"]
        assert (filled["sphere_id"], filled["drawer_id"]) == (s.dawn, RITES)
        assert [i["text"] for i in filled["items"]] == [
            "Smiths sing to the anvil when the bells ring."
        ]
        # the whole Fill preview, to send back as it is (curation Task 7)
        assert (filled["new_names"], filled["refile"]) == ([], [])
        assert s.world.head_rev() == head

        await _act(plugin, "accept_fill", **filled)
        assert not _errors(plugin)
        dawn = _last(plugin, "accept_fill")["data"]
        rites = next(d for d in dawn["sphere"]["drawers"] if d["id"] == RITES)
        assert [i["name"] for i in rites["items"]] == [
            "Dawn Vigil",
            "Smiths sing to the anvil when the bells ring.",
        ]
        # a statement feeds no prose (ruling P19): nothing is scheduled
        assert not plugin.tasks


async def test_fill_failure_is_reported(plugin, client):
    s = await _open_sphere_world(plugin)
    await _act(plugin, "fill_drawer", sphere_id=s.dawn, drawer_id="0badd0e5")
    await _drain(plugin)
    failed = _last(plugin, "fill_failed")
    assert "no drawer" in failed["message"]
    assert client.prompt_history == []


async def _fresh_prose(world, thing_id):
    start, end = prose_gen.stretch_containing(world, thing_id, None)
    for section in prose_gen.sections_for(world.view().thing(thing_id).kind):
        world.prose().put(thing_id, section, start, end, "Prose.")


def _prose_fresh(world, thing_id):
    kind = world.view().thing(thing_id).kind
    return all(
        world.prose().stale(thing_id, section, None) is False
        for section in prose_gen.sections_for(kind)
    )


async def test_set_drawers(plugin, client):
    s = await _open_sphere_world(plugin)
    await _fresh_prose(s.world, s.dawn)
    await _fresh_prose(s.world, s.vigil)

    # retitle Doctrines, put Holy Sites first, add a drawer, drop Rites
    await _act(
        plugin,
        "set_drawers",
        sphere_id=s.dawn,
        drawers=[
            _drawer(SITES, "places", "Holy Sites"),
            _drawer(DOCTRINES, "beliefs", "Teachings"),
            {"type": "structure", "title": "Hierarchy"},
        ],
    )
    assert not _errors(plugin)
    sphere = _last(plugin, "set_drawers")["data"]["sphere"]
    assert [(d["type"], d["title"]) for d in sphere["drawers"]] == [
        ("places", "Holy Sites"),
        ("beliefs", "Teachings"),
        ("structure", "Hierarchy"),
        ("knowledge", "Unsorted"),
    ]
    hierarchy = sphere["drawers"][2]
    assert len(hierarchy["id"]) == 8 and hierarchy["items"] == []
    # the dropped drawer's item shows under Unsorted
    unsorted = sphere["drawers"][3]
    assert unsorted["id"] == "unsorted"
    assert [i["thing_id"] for i in unsorted["items"]] == [s.vigil]
    vigil = await _get_thing(plugin, s.vigil)
    assert vigil["part_of"]["drawer_title"] == "Unsorted"
    # no rendered text changed
    assert not plugin.tasks
    assert _prose_fresh(s.world, s.dawn)
    assert _prose_fresh(s.world, s.vigil)

    head = s.world.head_rev()
    for drawers in (
        [{"type": "rites", "title": "Rites"}],
        [{"type": "beliefs", "title": "  "}],
        [_drawer(SITES, "places", "A"), _drawer(SITES, "places", "B")],
        [{"id": "unsorted", "type": "beliefs", "title": "No"}],
    ):
        await _act(plugin, "set_drawers", sphere_id=s.dawn, drawers=drawers)
        assert _errors(plugin)
    await _act(plugin, "set_drawers", sphere_id=s.vigil, drawers=[])
    assert "not a sphere" in _errors(plugin)[-1]["error"]["message"]
    assert s.world.head_rev() == head


async def test_set_part_of(plugin, client):
    s = await _open_sphere_world(plugin)
    await _fresh_prose(s.world, s.peak)

    await _act(
        plugin, "set_part_of", thing_id=s.peak, sphere_id=s.tsardom, drawer_id=LANDS
    )
    assert not _errors(plugin)
    peak = _last(plugin, "set_part_of")["data"]
    assert peak["part_of"]["drawer_title"] == "Lands"
    assert not plugin.tasks
    assert _prose_fresh(s.world, s.peak)
    await _act(
        plugin, "set_part_of", thing_id=s.vigil, sphere_id=s.dawn, drawer_id=DOCTRINES
    )
    assert _last(plugin, "set_part_of")["data"]["part_of"]["drawer_title"] == (
        "Doctrines"
    )
    # the Tsardom (a place sphere) in the Dawn's Holy Sites
    await _act(
        plugin, "set_part_of", thing_id=s.tsardom, sphere_id=s.dawn, drawer_id=SITES
    )

    # into another sphere's unsorted, then out of every sphere
    await _act(
        plugin,
        "set_part_of",
        thing_id=s.peak,
        sphere_id=s.tsardom,
        drawer_id="unsorted",
    )
    assert _last(plugin, "set_part_of")["data"]["part_of"] == {
        "sphere_id": s.tsardom,
        "sphere_name": "Tsardom",
        "drawer_id": "unsorted",
        "drawer_title": "Unsorted",
    }
    await _act(plugin, "set_part_of", thing_id=s.peak, sphere_id=None)
    assert _last(plugin, "set_part_of")["data"]["part_of"] is None
    assert not _errors(plugin)

    head = s.world.head_rev()
    refused = [
        # a character joins by ties
        dict(thing_id=s.vasha, sphere_id=s.dawn, drawer_id=DOCTRINES),
        # not a sphere
        dict(thing_id=s.peak, sphere_id=s.vigil, drawer_id="unsorted"),
        # no such drawer
        dict(thing_id=s.peak, sphere_id=s.dawn, drawer_id="0badd0e5"),
        # itself
        dict(thing_id=s.reformed, sphere_id=s.reformed, drawer_id="unsorted"),
        # a sphere inside it: its branch (parent), and the Tsardom (part_of)
        dict(thing_id=s.dawn, sphere_id=s.reformed, drawer_id="unsorted"),
        dict(thing_id=s.dawn, sphere_id=s.tsardom, drawer_id="unsorted"),
        # drawer types, as creation files things: lore isn't a place, a
        # place goes in a places drawer
        dict(thing_id=s.vigil, sphere_id=s.dawn, drawer_id=SITES),
        dict(thing_id=s.peak, sphere_id=s.dawn, drawer_id=DOCTRINES),
    ]
    for data in refused:
        before = len(_errors(plugin))
        await _act(plugin, "set_part_of", **data)
        assert len(_errors(plugin)) == before + 1, data
    assert s.world.head_rev() == head


async def test_set_ties(plugin, client):
    s = await _open_sphere_world(plugin)
    await _fresh_prose(s.world, s.maren)
    since = WorldDate.of(1015).model_dump(mode="json")

    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[
            {"sphere_id": s.dawn, "role": "priest", "since": since, "until": None},
            {"sphere_id": s.tsardom, "role": "subject"},
        ],
    )
    assert not _errors(plugin)
    maren = _last(plugin, "set_ties")["data"]
    assert [(t["sphere_name"], t["role"]) for t in maren["ties"]] == [
        ("The White Dawn", "priest"),
        ("Tsardom", "subject"),
    ]
    assert maren["ties"][0]["since"]["label"] == "1015"
    assert maren["ties"][1]["since"] is None
    assert not plugin.tasks
    assert _prose_fresh(s.world, s.maren)
    dawn = await _get_thing(plugin, s.dawn)
    assert [p["name"] for p in dawn["sphere"]["people"]] == ["Vasha", "Maren"]

    # replaced, not added to
    await _act(plugin, "set_ties", character_id=s.maren, ties=[])
    assert _last(plugin, "set_ties")["data"]["ties"] == []

    head = s.world.head_rev()
    for data in (
        dict(character_id=s.maren, ties=[{"sphere_id": s.vigil, "role": "x"}]),
        dict(character_id=s.maren, ties=[{"sphere_id": "f" * 32, "role": "x"}]),
        dict(character_id=s.peak, ties=[]),
    ):
        before = len(_errors(plugin))
        await _act(plugin, "set_ties", **data)
        assert len(_errors(plugin)) == before + 1, data
    assert s.world.head_rev() == head


async def test_set_ties_on_beings(plugin, client):
    """A real being holds ties as a character does; a believed or
    undecided one can't be tied, and a real one that becomes believed
    keeps its ties hidden (curation Task 4, ruling Q2)."""

    s = await _open_sphere_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        spirit = rev.create_thing(
            "being", fields={"name": "The River Spirit", "existence": "real"}
        )
        light = rev.create_thing("being", fields={"name": "The Eternal Light"})

    await _act(
        plugin,
        "set_ties",
        character_id=spirit,
        ties=[{"sphere_id": s.dawn, "role": "patron"}],
    )
    assert not _errors(plugin)
    assert [t["role"] for t in _last(plugin, "set_ties")["data"]["ties"]] == ["patron"]

    head = s.world.head_rev()
    before = len(_errors(plugin))
    await _act(
        plugin,
        "set_ties",
        character_id=light,
        ties=[{"sphere_id": s.dawn, "role": "god"}],
    )
    assert len(_errors(plugin)) == before + 1
    assert s.world.head_rev() == head

    with s.world.revision(Source.manual()) as rev:
        rev.set_field(spirit, "existence", "believed", None)
    thing = await _get_thing(plugin, spirit)
    assert thing["ties"] == []
    assert s.world.view().thing(spirit).fields["ties"][0]["role"] == "patron"


async def test_set_ties_within(plugin, client):
    """A tie can be within a part of its sphere (curation Task 7): a live
    thing filed in it. A tie sent without `within` keeps the part its
    sphere's tie had."""

    s = await _open_sphere_world(plugin)
    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[{"sphere_id": s.dawn, "role": "keeper", "within": s.vigil}],
    )
    assert not _errors(plugin)
    (tie,) = _last(plugin, "set_ties")["data"]["ties"]
    assert (tie["within"], tie["within_name"]) == (s.vigil, "Dawn Vigil")
    dawn = await _get_thing(plugin, s.dawn)
    keeper = [p for p in dawn["sphere"]["people"] if p["name"] == "Maren"]
    assert keeper[0]["within_name"] == "Dawn Vigil"

    # left out: kept; sent as null: the sphere as a whole
    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[{"sphere_id": s.dawn, "role": "elder keeper"}],
    )
    assert _last(plugin, "set_ties")["data"]["ties"][0]["within"] == s.vigil
    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[{"sphere_id": s.dawn, "role": "keeper", "within": None}],
    )
    assert _last(plugin, "set_ties")["data"]["ties"][0]["within"] is None
    assert "within" not in s.world.view().thing(s.maren).fields["ties"][0]

    # each tie keeps its own part: two ties to one sphere
    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[
            {"sphere_id": s.dawn, "role": "keeper", "within": s.vigil},
            {"sphere_id": s.dawn, "role": "pilgrim", "within": s.peak},
        ],
    )
    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[
            {"sphere_id": s.dawn, "role": "pilgrim"},
            {"sphere_id": s.dawn, "role": "keeper"},
        ],
    )
    assert [
        (t["role"], t["within"]) for t in _last(plugin, "set_ties")["data"]["ties"]
    ] == [("pilgrim", s.peak), ("keeper", s.vigil)]
    # a renamed role keeps the part at its place in the list
    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[
            {"sphere_id": s.dawn, "role": "elder pilgrim"},
            {"sphere_id": s.dawn, "role": "keeper"},
        ],
    )
    assert [t["within"] for t in _last(plugin, "set_ties")["data"]["ties"]] == [
        s.peak,
        s.vigil,
    ]

    head = s.world.head_rev()
    # the Tsardom isn't part of the Dawn; Maren is no part of anything
    for within in (s.tsardom, s.maren, "f" * 32):
        before = len(_errors(plugin))
        await _act(
            plugin,
            "set_ties",
            character_id=s.maren,
            ties=[{"sphere_id": s.dawn, "role": "keeper", "within": within}],
        )
        assert len(_errors(plugin)) == before + 1, within
    assert s.world.head_rev() == head


async def test_add_outer_body(plugin, client):
    """`add_outer_body` puts the owner's outer body around a part of a
    preview, with no model call and nothing written; a Fill accept takes
    its new names and re-file rows (curation Task 7, ruling C10)."""

    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    preview = CreatePreview(
        kind="character",
        prompt="A keeper of the Vigil Watch.",
        name="Olya",
        facts=[PreviewFact(category="background", text="Olya keeps the Vigil Watch.")],
        prose={},
        new_names=[{"name": "Vigil Watch", "kind": "lore"}],
    )
    await _act(
        plugin,
        "add_outer_body",
        preview_type="create",
        preview=preview.model_dump(mode="json"),
        row_name="Vigil Watch",
        outer={
            "name": "Order of the Dawn",
            "template": "order",
            "part_of": {"sphere": s.dawn, "drawer": RITES},
        },
    )
    assert not _errors(plugin)
    reply = _last(plugin, "add_outer_body")["data"]
    assert reply["preview_type"] == "create"
    rows = {n["name"]: n for n in reply["preview"]["new_names"]}
    assert rows["Vigil Watch"]["part_of"] == {
        "name": "Order of the Dawn",
        "drawer": "unsorted",
    }
    assert rows["Order of the Dawn"]["kind"] == "sphere"
    assert [(r["thing_id"], r["ticked"]) for r in reply["preview"]["refile"]] == [
        (s.vigil, False)
    ]
    assert s.world.head_rev() == head
    assert client.prompt_history == []

    # ticked and accepted: the Vigil moves into the order
    accepted = CreatePreview.model_validate(reply["preview"])
    accepted.refile[0]["ticked"] = True
    await _act(plugin, "accept_preview", preview=accepted.model_dump(mode="json"))
    assert not _errors(plugin)
    view = s.world.view()
    order = next(
        t for t in view.things("sphere") if t.fields["name"] == "Order of the Dawn"
    )
    assert order.fields["part_of"] == {"sphere": s.dawn, "drawer": RITES}
    assert view.thing(s.vigil).fields["part_of"]["sphere"] == order.id

    # Fill: the item goes inside a new body in the drawer it was for
    fill = {
        "sphere_id": s.dawn,
        "drawer_id": DOCTRINES,
        "items": [
            {
                "drawer_id": DOCTRINES,
                "name": "Dawn Catechism",
                "text": "The first teachings.",
                "kind": "lore",
                "names": [],
                "ticked": True,
            }
        ],
    }
    await _act(
        plugin,
        "add_outer_body",
        preview_type="fill",
        preview=fill,
        row_name="Dawn Catechism",
        outer={"name": "Dawn Teachings", "template": "field"},
    )
    filled = _last(plugin, "add_outer_body")["data"]["preview"]
    assert filled["items"][0]["part_of"]["name"] == "Dawn Teachings"
    await _act(
        plugin,
        "accept_fill",
        sphere_id=s.dawn,
        drawer_id=DOCTRINES,
        items=filled["items"],
        elsewhere=filled["elsewhere"],
        new_names=filled["new_names"],
        refile=filled["refile"],
    )
    assert not _errors(plugin)
    view = s.world.view()
    teachings = next(
        t for t in view.things("sphere") if t.fields["name"] == "Dawn Teachings"
    )
    assert teachings.fields["part_of"] == {"sphere": s.dawn, "drawer": DOCTRINES}

    before = len(_errors(plugin))
    await _act(
        plugin,
        "add_outer_body",
        preview_type="scene",
        preview={},
        row_name="x",
        outer={"name": "y", "template": "order"},
    )
    assert len(_errors(plugin)) == before + 1


async def test_beings_filed_and_given_exceptions(plugin, client):
    """A being can be filed in a beliefs, practices or structure drawer (a
    god in its faith's Doctrines), not in a places drawer. A real being
    can be given an exception to its tie; a believed one can't (ruling
    C4)."""

    s = await _open_sphere_world(plugin)
    with s.world.revision(Source.manual()) as rev:
        spirit = rev.create_thing(
            "being",
            fields={
                "name": "The River Spirit",
                "existence": "real",
                "ties": [
                    {"sphere": s.dawn, "role": "patron", "since": None, "until": None}
                ],
            },
        )
        light = rev.create_thing(
            "being", fields={"name": "The Eternal Light", "existence": "believed"}
        )

    await _act(
        plugin, "set_part_of", thing_id=light, sphere_id=s.dawn, drawer_id=DOCTRINES
    )
    assert not _errors(plugin)
    assert _last(plugin, "set_part_of")["data"]["part_of"]["drawer_title"] == (
        "Doctrines"
    )
    before = len(_errors(plugin))
    await _act(plugin, "set_part_of", thing_id=light, sphere_id=s.dawn, drawer_id=SITES)
    assert len(_errors(plugin)) == before + 1

    errors = len(_errors(plugin))
    async with MockClientContext():
        await _act(
            plugin,
            "add_exception",
            character_id=spirit,
            sphere_id=s.dawn,
            text="Never answers a priest",
            rejects=None,
        )
        await _drain(plugin)
    assert len(_errors(plugin)) == errors
    exceptions = _last(plugin, "add_exception")["data"]["ties"][0]["exceptions"]
    assert len(exceptions) == 1

    head = s.world.head_rev()
    before = len(_errors(plugin))
    await _act(
        plugin,
        "add_exception",
        character_id=light,
        sphere_id=s.dawn,
        text="Shines on heretics too",
        rejects=None,
    )
    assert len(_errors(plugin)) == before + 1
    assert "only a real being" in _last(plugin, "operation_done")["error"]["message"]
    assert s.world.head_rev() == head


async def test_add_exception(plugin, client):
    s = await _open_sphere_world(plugin)
    async with MockClientContext():
        # departing from a thing item, linked as written
        await _act(
            plugin,
            "add_exception",
            character_id=s.vasha,
            sphere_id=s.dawn,
            text="Never climbs Dawn Peak",
            rejects={"thing_id": s.peak},
        )
        assert not _errors(plugin)
        vasha = _last(plugin, "add_exception")["data"]
        # an exception is a fact: the character's prose is refreshed
        assert plugin.tasks
        await _drain(plugin)

        # departing from a statement
        await _act(
            plugin,
            "add_exception",
            character_id=s.vasha,
            sphere_id=s.dawn,
            text="Thinks the unchanged are blessed",
            rejects={"fact_id": s.unblessed},
        )
        await _drain(plugin)
    assert not _errors(plugin)
    vasha = _last(plugin, "add_exception")["data"]
    texts = [_text(e["segments"]) for e in vasha["ties"][0]["exceptions"]]
    assert texts[0] == "Skips the vigil. Departs from Dawn Vigil"
    # text that links the item already is kept as written
    climbs = next(
        e
        for e in vasha["ties"][0]["exceptions"]
        if _text(e["segments"]).startswith("Never")
    )
    assert climbs["segments"] == [
        _plain("Never climbs "),
        {"text": "Dawn Peak", "ref": s.peak, "stub": False},
    ]
    assert (
        "Thinks the unchanged are blessed. Departs from a teaching of The White Dawn"
        in texts
    )
    # the same facts spheres.exceptions finds
    view = s.world.view()
    found = spheres.exceptions(view, s.vasha, s.dawn)
    assert {f.fact_id for f in found} == {
        e["fact_id"] for e in vasha["ties"][0]["exceptions"]
    }
    teaching = next(f for f in found if (f.origin or {}).get("rejects_fact"))
    # filed under its tie (ruling P22), and the statement it rejects (P3)
    assert teaching.origin == {"tie": s.dawn, "rejects_fact": s.unblessed}
    assert teaching.category == "ties"
    climbing = next(f for f in found if "climbs" in f.text)
    assert climbing.origin == {"tie": s.dawn}

    head = s.world.head_rev()
    refused = [
        # not an item of the Dawn
        dict(character_id=s.vasha, sphere_id=s.dawn, rejects={"thing_id": s.tsardom}),
        dict(character_id=s.vasha, sphere_id=s.dawn, rejects={"fact_id": s.synod}),
        # both, or neither
        dict(
            character_id=s.vasha,
            sphere_id=s.dawn,
            rejects={"thing_id": s.peak, "fact_id": s.unblessed},
        ),
        # Maren has no tie to the Dawn
        dict(character_id=s.maren, sphere_id=s.dawn, rejects={"thing_id": s.peak}),
    ]
    for data in refused:
        before = len(_errors(plugin))
        await _act(plugin, "add_exception", text="No.", **data)
        assert len(_errors(plugin)) == before + 1, data
    assert s.world.head_rev() == head


BRANCH_SMITHS = json.dumps(
    {
        "name": "The Forge Dawn",
        "summary": "Smiths who keep the Dawn at the anvil.",
        "aka": [],
        "timeline": [],
        "drawers": [],
        "drops": ["F1"],
        "items": [{"drawer": "Doctrines", "text": "The forge is a dawn too."}],
        "names": [],
    }
)


async def test_preview_branch_then_accept(plugin, client):
    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    async with MockClientContext():
        client_responses.get().append(BRANCH_SMITHS)
        await _act(
            plugin, "preview_branch", parent_id=s.dawn, prompt="the smiths' Dawn"
        )
        await _drain(plugin)
    preview = _last(plugin, "preview_branch")["data"]
    assert preview["fields"] == {"parent": s.dawn}
    assert [row["label"] for row in preview["parent_items"]][:1] == ["F1"]
    assert s.world.head_rev() == head

    await _act(plugin, "accept_sphere", preview=preview)
    assert not _errors(plugin)
    branch = _last(plugin, "accept_sphere")["data"]
    assert branch["name"] == "The Forge Dawn"
    assert branch["sphere"]["parent"] == {"id": s.dawn, "name": "The White Dawn"}
    dawn = await _get_thing(plugin, s.dawn)
    assert {b["name"] for b in dawn["sphere"]["branches"]} == {
        "The Reformed Dawn",
        "The Forge Dawn",
    }


async def test_end_item(plugin, client):
    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    async with MockClientContext():
        await _act(
            plugin,
            "end_item",
            sphere_id=s.dawn,
            thing_id=s.vigil,
            at=WorldDate.of(1015).model_dump(mode="json"),
            by=s.tsardom,
        )
        assert not _errors(plugin)
        dawn = _last(plugin, "end_item")["data"]
        assert dawn["id"] == s.dawn
        items = [i["thing_id"] for d in dawn["sphere"]["drawers"] for i in d["items"]]
        assert s.vigil not in items
        assert s.world.head_rev() == head + 1
        # the Vigil got a fact: its prose is refreshed; the Tsardom's
        # timeline fact feeds no prose (ruling P19)
        assert len(plugin.tasks) == 1
        await _drain(plugin)

        await _act(
            plugin,
            "end_item",
            sphere_id=s.dawn,
            fact_id=s.unblessed,
            at=WorldDate.of(1016).model_dump(mode="json"),
        )
        await _drain(plugin)
    assert not _errors(plugin)
    dawn = _last(plugin, "end_item")["data"]
    assert s.unblessed not in [
        i["fact_id"] for d in dawn["sphere"]["drawers"] for i in d["items"]
    ]
    tsardom = await _get_thing(plugin, s.tsardom)
    # the Vigil's own note names the Tsardom, so its timeline gathers it
    # (curation goal 6), beside the Tsardom's own line
    assert [_text(t["segments"]) for t in tsardom["sphere"]["timeline"]] == [
        "Ended in 1015 by Tsardom",
        "Ended Dawn Vigil",
    ]

    head = s.world.head_rev()
    at = WorldDate.of(1017).model_dump(mode="json")
    for data in (
        # not an item of the Dawn
        dict(sphere_id=s.dawn, thing_id=s.tsardom, at=at),
        # inherited: ended in the sphere it comes from
        dict(sphere_id=s.reformed, thing_id=s.peak, at=at),
        # neither
        dict(sphere_id=s.dawn, at=at),
    ):
        before = len(_errors(plugin))
        await _act(plugin, "end_item", **data)
        assert len(_errors(plugin)) == before + 1, data
    assert s.world.head_rev() == head


async def test_accept_preview_carries_ties(plugin, client):
    """A character preview's ties round-trip through accept_preview, as the
    owner left them: here with one tie's exception dropped."""

    s = await _open_sphere_world(plugin)
    preview = {
        "kind": "character",
        "prompt": "a smith",
        "name": "Oskar",
        "facts": [{"category": "background", "text": "A smith."}],
        "prose": {},
        "ties": [
            {
                "sphere_id": s.dawn,
                "sphere": "The White Dawn",
                "role": "deacon",
                "since": None,
                "exceptions": [],
            },
            {
                "sphere_id": s.tsardom,
                "sphere": "Tsardom",
                "role": "subject",
                "since": None,
                "exceptions": [
                    {"text": "Pays no tithe", "item": "Tsardom", "thing_id": None}
                ],
            },
        ],
    }
    await _act(plugin, "accept_preview", preview=preview)
    assert not _errors(plugin)
    oskar = _last(plugin, "accept_preview")["data"]
    assert [(t["sphere_name"], t["role"]) for t in oskar["ties"]] == [
        ("The White Dawn", "deacon"),
        ("Tsardom", "subject"),
    ]
    assert oskar["ties"][0]["exceptions"] == []
    (tithe,) = oskar["ties"][1]["exceptions"]
    assert _text(tithe["segments"]).startswith("Pays no tithe.")


async def test_set_part_of_refiles_an_ended_item(plugin, client):
    """`end_item` ends the link at a date; filing the item again holds from
    the date viewed (else now), so the dated end doesn't keep winning."""

    s = await _open_sphere_world(plugin)
    await _act(
        plugin,
        "end_item",
        sphere_id=s.dawn,
        thing_id=s.vigil,
        at=WorldDate.of(1015).model_dump(mode="json"),
    )
    await _drain(plugin)
    assert (await _get_thing(plugin, s.vigil))["part_of"] is None

    # before the end: refused, it would change nothing
    await _act(
        plugin,
        "set_part_of",
        thing_id=s.vigil,
        sphere_id=s.dawn,
        drawer_id=RITES,
        at=WorldDate.of(1012).model_dump(mode="json"),
    )
    assert "1015" in _errors(plugin)[-1]["error"]["message"]

    await _act(
        plugin, "set_part_of", thing_id=s.vigil, sphere_id=s.dawn, drawer_id=RITES
    )
    assert len(_errors(plugin)) == 1
    vigil = _last(plugin, "set_part_of")["data"]
    assert vigil["part_of"]["drawer_title"] == "Rites"
    view = s.world.view()
    assert view.field_since(s.vigil, "part_of") == WorldDate.of(1020)
    assert s.vigil in {
        i.thing_id for i in spheres.items(view, s.dawn) if i.drawer_id == RITES
    }
    # its time out of the Dawn stays told
    assert s.vigil not in {
        i.thing_id for i in spheres.items(s.world.view(WorldDate.of(1017)), s.dawn)
    }


async def test_set_drawers_keeps_a_branchs_inherited_drawers(plugin, client):
    """The full drawer list a branch's page shows, sent back as it is,
    leaves its own `drawers` field alone; an inherited drawer sent back
    changed is a deliberate override, kept as its own."""

    s = await _open_sphere_world(plugin)
    shown = (await _get_thing(plugin, s.reformed))["sphere"]["drawers"]
    assert {d["id"] for d in shown} == {DOCTRINES, RITES, SITES}

    sent = [{k: d[k] for k in ("id", "type", "title")} for d in shown]
    await _act(plugin, "set_drawers", sphere_id=s.reformed, drawers=sent)
    assert not _errors(plugin)
    assert s.world.view().thing(s.reformed).fields.get("drawers") == []

    sent[1] = {**sent[1], "title": "Reformed Rites"}
    sent.append({"type": "beliefs", "title": "Reforms"})
    await _act(plugin, "set_drawers", sphere_id=s.reformed, drawers=sent)
    own = s.world.view().thing(s.reformed).fields["drawers"]
    assert [(d["id"], d["title"]) for d in own][:1] == [(RITES, "Reformed Rites")]
    assert [d["title"] for d in own] == ["Reformed Rites", "Reforms"]
    titles = [
        d["title"] for d in _last(plugin, "set_drawers")["data"]["sphere"]["drawers"]
    ]
    assert titles == ["Reformed Rites", "Reforms", "Doctrines", "Holy Sites"]


async def test_set_ties_keeps_a_tie_to_a_deleted_sphere(plugin, client):
    """Ruling P12: a tie to a deleted sphere is hidden, so a UI save never
    sends it; it's kept, and undoing the delete brings it back."""

    s = await _open_sphere_world(plugin)
    since = WorldDate.of(1010).model_dump(mode="json")
    await _act(
        plugin,
        "set_ties",
        character_id=s.vasha,
        ties=[
            {"sphere_id": s.dawn, "role": "practitioner", "since": since},
            {"sphere_id": s.tsardom, "role": "subject"},
        ],
    )
    await _act(plugin, "delete_thing", id=s.dawn)
    deleted = s.world.head_rev()
    vasha = await _get_thing(plugin, s.vasha)
    assert [t["sphere_name"] for t in vasha["ties"]] == ["Tsardom"]

    await _act(
        plugin,
        "set_ties",
        character_id=s.vasha,
        ties=[{"sphere_id": s.tsardom, "role": "loyal subject"}],
    )
    assert not _errors(plugin)
    s.world.undo([deleted])

    vasha = await _get_thing(plugin, s.vasha)
    assert [(t["sphere_name"], t["role"]) for t in vasha["ties"]] == [
        ("Tsardom", "loyal subject"),
        ("The White Dawn", "practitioner"),
    ]
    assert vasha["ties"][1]["since"]["label"] == "1010"
    assert [t.character_id for t in spheres.people(s.world.view(), s.dawn)] == [s.vasha]


async def test_set_ties_refuses_an_end_before_the_start(plugin, client):
    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    await _act(
        plugin,
        "set_ties",
        character_id=s.maren,
        ties=[
            {
                "sphere_id": s.dawn,
                "role": "novice",
                "since": WorldDate.of(1015).model_dump(mode="json"),
                "until": WorldDate.of(1012).model_dump(mode="json"),
            }
        ],
    )
    assert "end before" in _errors(plugin)[-1]["error"]["message"]
    assert s.world.head_rev() == head


async def test_list_things_unknown_template_groups_as_other(plugin, monkeypatch):
    from talemate.world import kinds

    s = await _open_sphere_world(plugin)
    # a template no longer offered, written when it still was
    monkeypatch.setattr(kinds, "SPHERE_TEMPLATES", (*kinds.SPHERE_TEMPLATES, "cult"))
    with s.world.revision(Source.manual(note="old")) as rev:
        odd = rev.create_thing("sphere", {"name": "The Old Way", "template": "cult"})
    monkeypatch.undo()
    await _act(plugin, "list_things", kind="sphere")
    groups = {
        g["template"]: [t["id"] for t in g["things"]]
        for g in _last(plugin, "list_things")["data"]["groups"]
    }
    assert groups["other"] == [odd]


async def test_add_exception_from_the_whole_sphere(plugin, client):
    """`rejects` null: a departure from the sphere's teaching as a whole,
    linking the sphere, with no origin."""

    s = await _open_sphere_world(plugin)
    async with MockClientContext():
        await _act(
            plugin,
            "add_exception",
            character_id=s.vasha,
            sphere_id=s.dawn,
            text="Doubts it all",
            rejects=None,
        )
        await _drain(plugin)
    assert not _errors(plugin)
    exceptions = _last(plugin, "add_exception")["data"]["ties"][0]["exceptions"]
    doubts = exceptions[-1]
    assert _text(doubts["segments"]) == (
        "Doubts it all. Departs from a teaching of The White Dawn"
    )
    assert doubts["segments"][-1]["ref"] == s.dawn
    fact = next(
        f for f in s.world.view().thing(s.vasha).facts if f.fact_id == doubts["fact_id"]
    )
    # filed under its tie alone: it rejects no item (ruling P22)
    assert fact.origin == {"tie": s.dawn}


async def test_preview_branch_failure_is_reported(plugin, client):
    s = await _open_sphere_world(plugin)
    async with MockClientContext():
        client_responses.get().append("no json here")
        await _act(plugin, "preview_branch", parent_id=s.dawn, prompt="smiths")
        await _drain(plugin)
    assert "no items" in _last(plugin, "preview_branch_failed")["message"]


async def test_end_item_refuses_a_malformed_date(plugin, client):
    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    for at in ({"instant": "soon"}, None, "1015"):
        before = len(_errors(plugin))
        await _act(plugin, "end_item", sphere_id=s.dawn, thing_id=s.vigil, at=at)
        assert len(_errors(plugin)) == before + 1, at
    assert s.world.head_rev() == head


def _fixed_sphere_file(tmp_path, monkeypatch, **replies):
    path = tmp_path / "fixed-sphere.json"
    path.write_text(json.dumps(replies))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SPHERE", str(path))
    # no client at all: the fixed replies must not need one
    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))


async def test_fixed_sphere_preview_answers_without_a_model(
    plugin, tmp_path, monkeypatch
):
    await _open_sphere_world(plugin)
    _fixed_sphere_file(tmp_path, monkeypatch, sphere=json.loads(CORE_SYNOD))
    await _act(plugin, "preview_sphere", template="order", prompt="a council of smiths")
    await _drain(plugin)
    assert not _replies(plugin, "preview_sphere_failed")
    preview = _last(plugin, "preview_sphere")["data"]
    # read through the real parsing: drawers given ids, app drawers added
    assert preview["name"] == "The Iron Synod"
    assert preview["template"] == "order"
    assert [d["title"] for d in preview["drawers"]][:1] == ["Tenets"]
    assert all(len(d["id"]) == 8 for d in preview["drawers"])
    assert "Members" in [d["title"] for d in preview["drawers"]]
    await _act(plugin, "accept_sphere", preview=preview)
    assert _last(plugin, "accept_sphere")["data"]["name"] == "The Iron Synod"


async def test_fixed_fill_answers_without_a_model(plugin, tmp_path, monkeypatch):
    s = await _open_sphere_world(plugin)
    _fixed_sphere_file(
        tmp_path,
        monkeypatch,
        fill=[
            {"name": "Dawn Vigil", "text": "A nightly prayer at first light."},
            {"name": "The Ember Rite", "text": "Coals are carried up the peak."},
        ],
    )
    await _act(plugin, "fill_drawer", sphere_id=s.dawn, drawer_id=RITES)
    await _drain(plugin)
    items = _last(plugin, "fill_drawer")["data"]["items"]
    # the real parsing: the repeat of the Dawn Vigil comes last, unticked
    assert [(i["name"], i["ticked"]) for i in items] == [
        ("The Ember Rite", True),
        ("Dawn Vigil", False),
    ]
    assert items[0]["drawer_id"] == RITES
    assert items[0]["kind"] == "lore"


async def test_fixed_branch_answers_without_a_model(plugin, tmp_path, monkeypatch):
    s = await _open_sphere_world(plugin)
    _fixed_sphere_file(tmp_path, monkeypatch, branch=json.loads(BRANCH_SMITHS))
    await _act(plugin, "preview_branch", parent_id=s.dawn, prompt="the smiths' Dawn")
    await _drain(plugin)
    assert not _replies(plugin, "preview_branch_failed")
    preview = _last(plugin, "preview_branch")["data"]
    assert preview["name"] == "The Forge Dawn"
    assert preview["fields"] == {"parent": s.dawn}
    # F1, the first parent item (the Dawn Vigil), mapped back to its thing
    first = preview["parent_items"][0]
    assert (first["label"], first["thing_id"]) == ("F1", s.vigil)
    assert preview["drops"] == [s.vigil]


async def test_fixed_sphere_file_missing_asks_the_model(
    plugin, client, tmp_path, monkeypatch
):
    await _open_sphere_world(plugin)
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SPHERE", str(tmp_path / "none.json"))
    async with MockClientContext():
        client_responses.get().append(CORE_SYNOD)
        await _act(plugin, "preview_sphere", template="order", prompt="smiths")
        await _drain(plugin)
    assert len(client.prompt_history) == 1
    assert _last(plugin, "preview_sphere")["data"]["name"] == "The Iron Synod"


async def test_fixed_sphere_file_without_the_key_asks_the_model(
    plugin, client, tmp_path, monkeypatch
):
    """A fixed file holding only a core reply: Fill and branches still go
    to the model (or say there's no client)."""

    s = await _open_sphere_world(plugin)
    path = tmp_path / "fixed-sphere.json"
    path.write_text(json.dumps({"sphere": json.loads(CORE_SYNOD)}))
    monkeypatch.setenv("TALEMATE_TEST_FIXED_SPHERE", str(path))
    async with MockClientContext():
        client_responses.get().append(FILL_RITES)
        await _act(plugin, "fill_drawer", sphere_id=s.dawn, drawer_id=RITES)
        await _drain(plugin)
    assert len(client.prompt_history) == 1
    items = _last(plugin, "fill_drawer")["data"]["items"]
    assert [i["text"] for i in items] == [
        "Smiths sing to the anvil when the bells ring."
    ]

    monkeypatch.setitem(instance.AGENTS, "creator", SimpleNamespace(client=None))
    await _act(plugin, "preview_branch", parent_id=s.dawn, prompt="a schism")
    await _drain(plugin)
    assert _last(plugin, "preview_branch_failed")["message"] == (
        "No AI client is configured for the creator agent"
    )


async def test_fixed_preview_carries_ties_and_part_of(plugin, tmp_path, monkeypatch):
    """The browser tests' fixed preview gives a character the file's
    `ties`, and an expanded stub that belongs in a sphere its `part_of`,
    as a real preview does."""

    s = await _open_sphere_world(plugin)
    with s.world.revision(Source.manual(note="stub")) as rev:
        council = rev.create_thing(
            "lore", {"name": "Council of Dawn", "stub": {"ignored": False}}
        )
    tie = {
        "sphere_id": s.dawn,
        "sphere": "The White Dawn",
        "role": "elder",
        "exceptions": [
            {"text": "Skips the vigil.", "item": "Dawn Vigil", "thing_id": s.vigil}
        ],
    }
    fixed = tmp_path / "fixed-preview.json"
    fixed.write_text(
        json.dumps(
            {
                "name": "Ilya",
                "facts": [{"category": "background", "text": "An elder."}],
                "prose": {},
                "ties": [tie],
            }
        )
    )
    monkeypatch.setenv("TALEMATE_TEST_FIXED_PREVIEW", str(fixed))

    await _act(plugin, "preview_thing", kind="character", prompt="an elder")
    await _drain(plugin)
    preview = _last(plugin, "preview_thing")["data"]
    assert [t["role"] for t in preview["ties"]] == ["elder"]
    assert preview["ties"][0]["exceptions"][0]["thing_id"] == s.vigil

    await _act(
        plugin,
        "preview_thing",
        kind="lore",
        prompt="The council of The White Dawn",
        stub_id=council,
        picks={"The White Dawn": s.dawn},
    )
    await _drain(plugin)
    expanded = _last(plugin, "preview_thing")["data"]
    assert expanded["ties"] == []
    # the White Dawn is no stub: a prompt naming it files nothing
    assert expanded["part_of"] is None

    with s.world.revision(Source.manual(note="sphere stub")) as rev:
        church = rev.create_thing(
            "sphere",
            {
                "name": "The Old Church",
                "template": "religion",
                "stub": {"ignored": False},
            },
        )
    await _act(
        plugin,
        "preview_thing",
        kind="lore",
        prompt="The council of The Old Church",
        stub_id=council,
        picks={"The Old Church": church},
    )
    await _drain(plugin)
    expanded = _last(plugin, "preview_thing")["data"]
    assert expanded["part_of"] == {"sphere": church, "drawer": "unsorted"}


async def test_add_statement(plugin, client):
    """A statement written by hand into a drawer: a `statement` fact of
    the sphere with the drawer as its origin, linked like `add_fact`'s
    text, shown in that drawer. A statement feeds no prose (ruling P19):
    none is scheduled."""

    s = await _open_sphere_world(plugin)
    async with MockClientContext():
        await _act(
            plugin,
            "add_statement",
            sphere_id=s.dawn,
            drawer_id=DOCTRINES,
            text="Light is purity, as seen from Dawn Peak.",
        )
        assert not _errors(plugin)
        assert not plugin.tasks, "a prose task was scheduled"
    dawn = _last(plugin, "add_statement")["data"]
    assert dawn["id"] == s.dawn
    doctrines = next(d for d in dawn["sphere"]["drawers"] if d["id"] == DOCTRINES)
    item = doctrines["items"][-1]
    assert item["name"] == "Light is purity, as seen from Dawn Peak."
    assert any(seg["ref"] == s.peak for seg in item["segments"])
    fact = next(
        f for f in s.world.view().thing(s.dawn).facts if f.fact_id == item["fact_id"]
    )
    assert (fact.category, fact.origin, fact.valid_from) == (
        "statement",
        {"drawer": DOCTRINES},
        None,
    )
    assert any(
        i.fact_id == fact.fact_id and i.drawer_id == DOCTRINES
        for i in spheres.items(s.world.view(), s.dawn)
    )


async def test_add_statement_to_a_branchs_inherited_drawer(plugin):
    s = await _open_sphere_world(plugin)
    await _act(
        plugin,
        "add_statement",
        sphere_id=s.reformed,
        drawer_id=DOCTRINES,
        text="All owls are equal.",
    )
    assert not _errors(plugin)
    reformed = _last(plugin, "add_statement")["data"]
    doctrines = next(d for d in reformed["sphere"]["drawers"] if d["id"] == DOCTRINES)
    assert doctrines["inherited"] is True
    own = [i for i in doctrines["items"] if not i["inherited"]]
    assert [i["name"] for i in own] == ["All owls are equal."]


@pytest.mark.parametrize(
    "drawer, sphere",
    [
        ("people", "dawn"),
        ("events", "dawn"),
        ("0badd0e5", "dawn"),
        ("unsorted", "dawn"),
        ("doctrines", "peak"),
    ],
)
async def test_add_statement_refusals(plugin, drawer, sphere):
    s = await _open_sphere_world(plugin)
    people, events = "9e091e00", "e0e47500"
    with s.world.revision(Source.manual(note="drawers")) as rev:
        rev.set_field(
            s.dawn,
            "drawers",
            [
                _drawer(DOCTRINES, "beliefs", "Doctrines"),
                _drawer(RITES, "practices", "Rites"),
                _drawer(SITES, "places", "Holy Sites"),
                _drawer(people, "people", "People"),
                _drawer(events, "events", "Timeline"),
            ],
            None,
        )
    drawer_id = {"people": people, "events": events, "doctrines": DOCTRINES}.get(
        drawer, drawer
    )
    sphere_id = {"dawn": s.dawn, "peak": s.peak}[sphere]
    head = s.world.head_rev()
    await _act(
        plugin, "add_statement", sphere_id=sphere_id, drawer_id=drawer_id, text="X."
    )
    assert _errors(plugin)
    assert not _replies(plugin, "add_statement")
    assert s.world.head_rev() == head


@pytest.mark.parametrize(
    ("thing", "unread", "read"),
    [
        # a religion: its summary reads its `about` facts, never its timeline
        ("dawn", "timeline", "about"),
        # a place sphere: described from its place facts
        ("tsardom", "timeline", "description"),
    ],
)
async def test_unread_fact_leaves_sphere_prose_fresh(
    plugin, client, thing, unread, read
):
    """Ruling P19 through the generic fact actions ("Add to the timeline",
    editing a statement): a fact of a category the sphere's description
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


async def test_part_of_a_deleted_sphere_is_none(plugin):
    """A thing whose sphere was deleted shows no "Part of" line: the
    sphere's items never list it either."""

    s = await _open_sphere_world(plugin)
    await _act(plugin, "delete_thing", id=s.dawn)
    assert not _errors(plugin)
    vigil = await _get_thing(plugin, s.vigil)
    assert vigil["part_of"] is None
    # undone, it's back
    with s.world.revision(Source.manual(note="back")) as rev:
        rev.set_field(s.vigil, "part_of", {"sphere": s.reformed, "drawer": RITES}, None)
    vigil = await _get_thing(plugin, s.vigil)
    assert vigil["part_of"]["sphere_id"] == s.reformed


@pytest.mark.parametrize(
    "field, value, action",
    [
        ("part_of", None, "set_part_of"),
        ("ties", [], "set_ties"),
        ("drawers", [], "set_drawers"),
    ],
)
async def test_set_field_refuses_guarded_fields(plugin, field, value, action):
    """`part_of`, `ties` and `drawers` have actions of their own, with
    their guards: `set_field` refuses them, naming that action."""

    s = await _open_sphere_world(plugin)
    thing_id = s.vasha if field == "ties" else s.dawn if field == "drawers" else s.vigil
    head = s.world.head_rev()
    await _act(plugin, "set_field", thing_id=thing_id, field=field, value=value)
    (error,) = _errors(plugin)
    assert action in error["error"]["message"]
    assert s.world.head_rev() == head


# --- repoint_stub: what a stub carries over ----------------------------------


async def test_repoint_stub_carries_a_fill_stubs_filing_and_facts(plugin, client):
    """A stub Fill made (filed in its drawer, with its item fact) re-pointed
    onto an unfiled entry: the entry is filed where the stub was and takes
    its facts, a link to itself made plain words. Onto an entry filed
    elsewhere, the entry keeps its own filing and the reply says so."""

    s = await _open_sphere_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="noon")) as rev:
        noon = rev.create_thing("lore", {"name": "Noon Bells"})
    await _act(
        plugin,
        "accept_fill",
        sphere_id=s.dawn,
        drawer_id=RITES,
        items=[{"name": "Bell Rite", "kind": "lore", "text": "Rung at noon."}],
    )
    await _act(
        plugin,
        "accept_fill",
        sphere_id=s.dawn,
        drawer_id=DOCTRINES,
        items=[{"name": "Ash Rite", "kind": "lore", "text": "Ash on the brow."}],
    )
    assert not _errors(plugin)
    view = world.view()
    bell = next(t.id for t in view.things("lore") if view.name_of(t.id) == "Bell Rite")
    ash = next(t.id for t in view.things("lore") if view.name_of(t.id) == "Ash Rite")
    assert view.thing(bell).is_stub
    with world.revision(Source.manual(note="echo")) as rev:
        echo = rev.add_fact(
            bell,
            "general",
            f"Echoes {ref(noon, 'the Noon Bells')}.",
            valid_from=WorldDate.of(1001),
            valid_until=WorldDate.of(1015),
        )

    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=bell, target_id=noon)
    assert not _errors(plugin)
    assert world.head_rev() == head + 1
    view = world.view()
    assert view.thing(noon).fields["part_of"] == {"sphere": s.dawn, "drawer": RITES}
    moved = {f.text: f for f in world.live_facts(noon)}
    assert set(moved) == {"Rung at noon.", "Echoes the Noon Bells."}
    # a new fact of Noon's, with the category and dates; its link to Noon
    # is words
    echoed = moved["Echoes the Noon Bells."]
    assert echoed.fact_id != echo
    assert echoed.category == "general"
    assert (echoed.valid_from, echoed.valid_until) == (
        WorldDate.of(1001),
        WorldDate.of(1015),
    )
    dawn = await _get_thing(plugin, s.dawn)
    rites = next(d for d in dawn["sphere"]["drawers"] if d["id"] == RITES)
    assert "Noon Bells" in [i["name"] for i in rites["items"]]
    assert "Bell Rite" not in [i["name"] for i in rites["items"]]

    # onto the Vigil, filed already (in Rites, not Doctrines): it stays put
    await _act(plugin, "repoint_stub", stub_id=ash, target_id=s.vigil)
    assert not _errors(plugin)
    reply = _last(plugin, "repoint_stub")["data"]
    assert any(
        "Dawn Vigil stays in The White Dawn · Rites" in note and "Doctrines" in note
        for note in reply["notes"]
    )
    assert world.view().thing(s.vigil).fields["part_of"] == {
        "sphere": s.dawn,
        "drawer": RITES,
    }
    assert "Ash on the brow." in [f.text for f in world.live_facts(s.vigil)]


async def test_repoint_stub_carries_fields_filings_and_ties(plugin, client):
    """Every use of the stub moves to the target at the dates it holds: a
    place's parent (its undated value, not a dated one naming another
    place), a lore entry filed in a sphere stub, a character's tie to it
    and the exception filed under that tie."""

    s = await _open_sphere_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="uses")) as rev:
        north = rev.create_thing(
            "place", {"name": "Northreach", "stub": {"ignored": False}}
        )
        mark = rev.create_thing("place", {"name": "Northmark"})
        south = rev.create_thing("place", {"name": "Southmark"})
        harbour = rev.create_thing("place", {"name": "The Harbour", "parent": north})
        rev.set_field(harbour, "parent", south, WorldDate.of(1015))
        faith = rev.create_thing(
            "sphere",
            {"name": "Old Faith", "template": "religion", "stub": {"ignored": False}},
        )
        ember = rev.create_thing(
            "lore",
            {"name": "Ember Rite", "part_of": {"sphere": faith, "drawer": "unsorted"}},
        )
        rev.set_field(
            s.maren,
            "ties",
            [{"sphere": faith, "role": "keeper", "since": None, "until": None}],
            None,
        )
        doubt = rev.add_fact(
            s.maren,
            "ties",
            f"Doubts {ref(faith, 'the Old Faith')}.",
            origin={"tie": faith},
        )

    await _act(plugin, "repoint_stub", stub_id=north, target_id=mark)
    await _act(plugin, "repoint_stub", stub_id=faith, target_id=s.dawn)
    assert not _errors(plugin)
    assert world.view(WorldDate.of(1010)).thing(harbour).fields["parent"] == mark
    assert world.view(WorldDate.of(1020)).thing(harbour).fields["parent"] == south
    assert world.view().thing(ember).fields["part_of"] == {
        "sphere": s.dawn,
        "drawer": "unsorted",
    }
    assert [t.sphere_id for t in spheres.ties_of(world.view(), s.maren)] == [s.dawn]
    exceptions = spheres.exceptions(world.view(), s.maren, s.dawn)
    assert [f.fact_id for f in exceptions] == [doubt]


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


async def test_repoint_stub_never_makes_a_parent_cycle(plugin, monkeypatch):
    """A place stub whose own parent is the target leaves the target
    without that parent (noted); a parent use that would close a loop
    (Region in the stub, Bay in Region, the stub onto Bay) is refused."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    with world.revision(Source.manual(note="places")) as rev:
        cove = rev.create_thing(
            "place", {"name": "Cove", "stub": {"ignored": False}, "parent": s.moscavy}
        )
        region = rev.create_thing("place", {"name": "Region", "parent": s.tsardom})
        bay = rev.create_thing("place", {"name": "Bay", "parent": region})

    await _act(plugin, "repoint_stub", stub_id=cove, target_id=s.moscavy)
    assert not _errors(plugin)
    assert world.view().thing(s.moscavy).fields.get("parent") is None
    notes = _last(plugin, "repoint_stub")["data"]["notes"]
    assert any("parent" in note for note in notes)

    head = world.head_rev()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=bay)
    message = _last(plugin, "operation_done")["error"]["message"]
    assert "Region's parent" in message
    assert world.head_rev() == head


async def test_repoint_stub_more_refusals(plugin, client):
    """Refused, naming the use: a filing and a tie when the target isn't
    a sphere, a filing that would loop, a mix whose two parents would be
    one, and shares naming the target twice."""

    s = await _open_sphere_world(plugin)
    world = s.world
    with world.revision(Source.manual(note="uses")) as rev:
        faith = rev.create_thing(
            "sphere",
            {"name": "Old Faith", "template": "religion", "stub": {"ignored": False}},
        )
        rev.create_thing(
            "lore",
            {"name": "Ember Rite", "part_of": {"sphere": faith, "drawer": "unsorted"}},
        )
        rev.set_field(
            s.maren,
            "ties",
            [{"sphere": faith, "role": "keeper", "since": None, "until": None}],
            None,
        )
        plain = rev.create_thing("lore", {"name": "Plain Lore"})
        order = rev.create_thing(
            "sphere",
            {
                "name": "The Order",
                "template": "order",
                "part_of": {"sphere": faith, "drawer": "unsorted"},
            },
        )
        chapter = rev.create_thing(
            "sphere",
            {
                "name": "The Chapter",
                "template": "order",
                "part_of": {"sphere": order, "drawer": "unsorted"},
            },
        )
        orc = rev.create_thing("species", {"name": "Orc"})
        elf = rev.create_thing("species", {"name": "Elf", "stub": {"ignored": False}})
        rev.create_thing("mix", {"name": "Half-elf", "parents": [orc, elf]})
        rev.create_thing(
            "place",
            {
                "name": "Borderland",
                "cultures": [
                    {"thing_id": faith, "share": 50},
                    {"thing_id": s.dawn, "share": 50},
                ],
            },
        )
    head = world.head_rev()
    for stub_id, target_id, words in (
        (faith, plain, ("Ember Rite's part of", "Maren's ties", "a sphere")),
        (faith, chapter, ("The Order's part of", "inside itself")),
        (elf, orc, ("Half-elf's parents",)),
        (faith, s.dawn, ("Borderland's cultures",)),
    ):
        await _act(plugin, "repoint_stub", stub_id=stub_id, target_id=target_id)
        message = _last(plugin, "operation_done")["error"]["message"]
        assert all(word in message for word in words), message
        assert world.head_rev() == head


async def test_repoint_stub_sphere_fields_and_prose(plugin, monkeypatch):
    """A sphere stub's template, agent and drawers stay off a target that
    isn't a sphere (noted); an equal value carries no note. Prose is
    refreshed for a thing whose rendered field was rewritten (a parent),
    not for an unrendered one (a filing)."""

    s = await _open_repoint_world(plugin, monkeypatch)
    world = s.world
    with world.revision(Source.manual(note="faith")) as rev:
        faith = rev.create_thing(
            "sphere",
            {
                "name": "Old Faith",
                "template": "religion",
                "agent": True,
                "stub": {"ignored": False},
            },
        )
        shrine = rev.create_thing("place", {"name": "Shrine"})
        rev.set_field(s.harbour, "parent", s.tsardom, None)
        rev.set_field(s.moscavy, "kind", "country", None)
        rev.set_field(s.tsardom, "kind", "country", None)

    await _act(plugin, "repoint_stub", stub_id=faith, target_id=shrine)
    assert not _errors(plugin)
    shrine_state = world.view().thing(shrine)
    assert "template" not in shrine_state.fields
    notes = " ".join(_last(plugin, "repoint_stub")["data"]["notes"])
    assert "template" in notes and "agent" in notes

    s.prose.clear()
    await _act(plugin, "repoint_stub", stub_id=s.tsardom, target_id=s.moscavy)
    assert not _errors(plugin)
    assert not any(
        "kind" in note for note in _last(plugin, "repoint_stub")["data"]["notes"]
    )
    assert s.harbour in s.prose


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
        s.undated = rev.add_fact(s.dawn, "timeline", "The Dawn keeps no calendar.")
    return s


async def test_payload_timeline_every_kind(plugin):
    """Every kind's payload has `entry_timeline`: its dated facts and, for
    a sphere, what it gathers, each line `{fact_id, owner_id, owner_name,
    date, until, segments, here, disagrees_with}` -- an ended fact with its
    `until`, a held one worded as belief. The sphere page's
    `sphere.timeline` reads the same lines, keeping an undated timeline
    fact and a branch's inherited lines."""

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
    assert [line["fact_id"] for line in peak["entry_timeline"]] == [
        s.climbed,
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
    # the sphere page: the same lines, the undated timeline fact first
    page = dawn["sphere"]["timeline"]
    assert [line["fact_id"] for line in page] == [s.undated, *gathered]
    assert page[0]["date"] is None and page[0]["here"]
    assert set(page[0]) == keys

    # a branch keeps its parent's timeline (an undated parent link: all of it)
    reformed = await _get_thing(plugin, s.reformed)
    inherited = {line["fact_id"]: line for line in reformed["sphere"]["timeline"]}
    assert s.synod in inherited and s.undated in inherited
    assert inherited[s.synod]["owner_id"] == s.dawn
    assert not inherited[s.synod]["here"]

    # the change history keeps its own key
    assert any(e["change"] == "fact_start" for e in vasha["timeline"])


async def test_fact_rows_carry_held_by(plugin):
    """Each fact row, and a statement item, carries `held_by: {id, name}`
    or null: a fact's own holder, and the implicit holder of a statement
    in a religion's beliefs drawer."""

    s = await _timeline_world(plugin)
    vasha = await _get_thing(plugin, s.vasha)
    rows = {f["fact_id"]: f for f in vasha["facts"]}
    assert rows[s.chosen]["held_by"] == {"id": s.dawn, "name": "The White Dawn"}
    assert rows[s.joined]["held_by"] is None

    dawn = await _get_thing(plugin, s.dawn)
    rows = {f["fact_id"]: f for f in dawn["facts"]}
    assert rows[s.unblessed]["held_by"] == {"id": s.dawn, "name": "The White Dawn"}
    assert rows[s.synod]["held_by"] is None
    doctrines = next(d for d in dawn["sphere"]["drawers"] if d["id"] == DOCTRINES)
    (item,) = doctrines["items"]
    assert item["held_by"] == {"id": s.dawn, "name": "The White Dawn"}
    rites = next(d for d in dawn["sphere"]["drawers"] if d["id"] == RITES)
    assert rites["items"][0]["held_by"] is None


async def test_set_held_by(plugin, monkeypatch):
    """`set_held_by` sets or clears one fact's holder in one revision and
    answers with the thing. Held-ness feeds description prose (ruling
    C3): a character's fact schedules its prose, a sphere's statement
    doesn't (P18, P19). Refused, writing nothing: a holder that can't
    hold a belief, one that isn't there, another thing's fact."""

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

    # the implicit holder of a beliefs statement can be cleared too; a
    # statement feeds no prose
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
    assert scheduled == [s.vasha, s.vasha]

    head = world.head_rev()
    for thing_id, fact_id, holder_id in (
        (s.vasha, s.joined, s.vigil),  # lore holds nothing
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

    for bad in ({"reach": 4}, {"repeat_threshold": 1.5}, {"nearness": 1}):
        before = len(_errors(plugin))
        await _act(plugin, "set_curation", settings=bad)
        assert len(_errors(plugin)) == before + 1
    assert s.world.curation().reach == 2


async def test_accept_sphere_answers_notes(plugin, client):
    """`accept_sphere` answers with the sphere and `notes`, like the other
    accepts: an item marked the same as an entry that's gone since becomes
    a stub, and says so."""

    s = await _open_sphere_world(plugin)
    reply = json.dumps(
        {
            "name": "The Iron Synod",
            "summary": "A council of smiths who keep the forges.",
            "aka": [],
            "timeline": [],
            "drawers": [{"type": "practices", "title": "Rites"}],
            "items": [
                {"drawer": "Rites", "name": "Anvil Song", "text": "Sung at noon."}
            ],
            "names": [],
        }
    )
    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(plugin, "preview_sphere", template="order", prompt="smiths")
        await _drain(plugin)
    preview = _last(plugin, "preview_sphere")["data"]
    with s.world.revision(Source.manual(note="song")) as rev:
        song = rev.create_thing("lore", {"name": "Old Anvil Song"})
        rev.add_fact(song, "general", "An old song.")
    with s.world.revision(Source.manual(note="gone")) as rev:
        rev.remove_thing(song)
    item = next(i for i in preview["items"] if i.get("name") == "Anvil Song")
    item["same_target_id"] = song

    await _act(plugin, "accept_sphere", preview=preview)
    assert not _errors(plugin)
    data = _last(plugin, "accept_sphere")["data"]
    assert data["name"] == "The Iron Synod"
    assert any("Anvil Song" in note for note in data["notes"])


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
                target_id=s.dawn,
                target_name="The White Dawn",
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
    onto when its prose reads them: Vasha's background does, the Dawn's
    timeline doesn't (P18, P19), and an unticked one isn't written. Fill
    does the same, and for an item's text written onto an entry the world
    has."""

    s = await _open_sphere_world(plugin)
    scheduled = _record_prose(plugin, monkeypatch)
    await _act(
        plugin,
        "accept_preview",
        preview=_ember_preview(s).model_dump(mode="json"),
    )
    assert not _errors(plugin)
    assert scheduled == [s.vasha]

    scheduled.clear()
    await _act(
        plugin,
        "accept_fill",
        sphere_id=s.dawn,
        drawer_id=RITES,
        items=[
            {
                "drawer_id": RITES,
                "name": "Dawn Vigil",
                "thing_id": s.vigil,
                "kind": "lore",
                "text": "It is sung in the cold.",
                "names": [],
                "ticked": True,
            }
        ],
        elsewhere=[
            {
                "target_id": s.vasha,
                "target_name": "Vasha",
                "category": "background",
                "text": "Vasha sings the vigil.",
            }
        ],
    )
    assert not _errors(plugin)
    assert sorted(scheduled) == sorted([s.vasha, s.vigil])


async def test_accept_payloads_validate_shapes(plugin):
    """The accepts validate the rows the owner sends back: a re-file row
    names its thing and where it goes; an item has its text. A bad shape
    is refused, writing nothing."""

    s = await _open_sphere_world(plugin)
    head = s.world.head_rev()
    bad = [
        (
            "accept_fill",
            {
                "sphere_id": s.dawn,
                "drawer_id": RITES,
                "items": [],
                "refile": [{"to": {"sphere": s.dawn, "drawer": RITES}}],
            },
        ),
        (
            "accept_fill",
            {
                "sphere_id": s.dawn,
                "drawer_id": RITES,
                "items": [{"name": "Dawn Rite", "ticked": True}],
            },
        ),
        (
            "accept_preview",
            {
                "preview": {
                    **_ember_preview(s).model_dump(mode="json"),
                    "refile": [{"thing_id": s.vigil, "ticked": "maybe"}],
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
    """A create preview carries what curation adds -- each fact's
    `ticked`, `repeat_of` and `held_by` (with `held_by_name`); the
    elsewhere facts (category, held_by, ticked, repeat_of, a new entry's
    row with `same_as`); the facts that may move in (`move_in`, with
    `from_name`) -- and `accept_preview` takes the owner's edits to them.
    The browser tests' fixed preview reads its `held_by`, `elsewhere` and
    `move_in` through the real parsers."""

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
    await _act(
        plugin,
        "preview_thing",
        kind="lore",
        prompt="a keeper of embers",
        fields={"part_of": {"sphere": s.dawn, "drawer": RITES}},
    )
    await _drain(plugin)
    assert not _replies(plugin, "preview_failed")
    preview = _last(plugin, "preview_thing")["data"]

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
    assert {"same_as", "same_target_id", "part_of"} <= set(gate["new"])
    assert s.vigil in [offer["thing_id"] for offer in vigils["new"]["same_as"]]

    # the pick first, marked, and unticked like the rest (ruling C24)
    rows = preview["move_in"]
    assert rows[0]["from_id"] == s.dawn and rows[0]["picked"]
    assert rows[0]["from_name"] == "The White Dawn"
    assert rows[0]["text"] == "The state church."
    assert not any(row["ticked"] for row in rows)
    assert not any(row["picked"] for row in rows[1:])
    for key in ("same_as", "verdict", "refile", "new_names"):
        assert key in preview

    # the owner's edits: the Ashen Gate unticked, the Vigils are the Dawn
    # Vigil, the plain fact held by Vasha, the pick ticked to move in
    gate["ticked"] = False
    vigils["new"]["same_target_id"] = s.vigil
    plain["held_by"] = s.vasha
    rows[0]["ticked"] = True
    head = s.world.head_rev()
    await _act(plugin, "accept_preview", preview=preview)
    assert not _errors(plugin)
    assert s.world.head_rev() == head + 1
    data = _last(plugin, "accept_preview")["data"]
    assert data["notes"] == []
    view = s.world.view()
    keeper = view.thing(data["id"])
    by_text = {f.text: f for f in keeper.facts}
    assert spheres.held_by(view, by_text["The keeper walks the peak."], keeper) == (
        s.vasha
    )
    assert "The state church." in by_text
    assert "The state church." not in [f.text for f in view.thing(s.dawn).facts]
    vasha_fact = next(
        f for f in view.thing(s.vasha).facts if "trained" in view.render(f.text)
    )
    assert vasha_fact.origin["held_by"] == s.dawn
    assert "The Dawn Vigils end with embers." in [
        view.render(f.text) for f in view.thing(s.vigil).facts
    ]
    assert not [t for t in view.things() if view.name_of(t.id) == "Ashen Gate"]


async def test_fixed_fill_carries_elsewhere(plugin, tmp_path, monkeypatch):
    """A fixed Fill reply given as an object keeps its `elsewhere`, read
    through the real parser (with `held_by`)."""

    s = await _open_sphere_world(plugin)
    _fixed_sphere_file(
        tmp_path,
        monkeypatch,
        fill={
            "new_items": [{"name": "Ember Rite", "text": "Coals go up the peak."}],
            "elsewhere": [
                {
                    "entry": "Vasha",
                    "text": "Vasha carries the coals.",
                    "held_by": "The White Dawn",
                }
            ],
        },
    )
    await _act(plugin, "fill_drawer", sphere_id=s.dawn, drawer_id=RITES)
    await _drain(plugin)
    filled = _last(plugin, "fill_drawer")["data"]
    assert [i["name"] for i in filled["items"]] == ["Ember Rite"]
    (elsewhere,) = filled["elsewhere"]
    assert (elsewhere["target_id"], elsewhere["held_by"]) == (s.vasha, s.dawn)
    assert elsewhere["held_by_name"] == "The White Dawn"


async def test_preview_rows_carry_names(plugin, client):
    """`add_outer_body`'s re-file rows name the entry they move and the
    bodies they move between."""

    s = await _open_sphere_world(plugin)
    preview = CreatePreview(
        kind="character",
        prompt="A keeper of the Vigil Watch.",
        name="Olya",
        facts=[PreviewFact(category="background", text="Olya keeps the Vigil Watch.")],
        prose={},
        new_names=[{"name": "Vigil Watch", "kind": "lore"}],
    )
    await _act(
        plugin,
        "add_outer_body",
        preview_type="create",
        preview=preview.model_dump(mode="json"),
        row_name="Vigil Watch",
        outer={
            "name": "Order of the Dawn",
            "template": "order",
            "part_of": {"sphere": s.dawn, "drawer": RITES},
        },
    )
    (row,) = _last(plugin, "add_outer_body")["data"]["preview"]["refile"]
    assert (row["name"], row["from_name"], row["to_name"]) == (
        "Dawn Vigil",
        "The White Dawn",
        "Order of the Dawn",
    )


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


async def test_forged_move_in_rows_are_dropped(plugin, monkeypatch):
    """`accept_preview` moves in only facts of the entries the server
    offers them from (the broader entry, or C13's): a forged row naming
    another entry's fact is dropped with a note, and that fact stays."""

    from talemate.worldplay.create import MoveInFact

    s = await _open_sphere_world(plugin)
    _record_prose(plugin, monkeypatch)
    about = next(f for f in s.world.view().thing(s.dawn).facts if f.category == "about")
    forged = MoveInFact(
        fact_id=s.skips, from_id=s.vasha, text="Skips the vigil.", ticked=True
    )

    # no broader entry at all: nothing may move in
    lone = CreatePreview(
        kind="lore",
        prompt="ash lore",
        name="Ash Lore",
        facts=[PreviewFact(category="general", text="Ash falls in spring.")],
        prose={},
        move_in=[forged],
    )
    await _act(plugin, "accept_preview", preview=lone.model_dump(mode="json"))
    assert not _errors(plugin)
    data = _last(plugin, "accept_preview")["data"]
    assert any("Vasha" in note and "move in" in note for note in data["notes"])
    assert s.skips in [f.fact_id for f in s.world.view().thing(s.vasha).facts]

    # filed in the Dawn: the Dawn's fact moves, Vasha's still doesn't
    filed = CreatePreview(
        kind="lore",
        prompt="ember lore",
        name="Ember Lore",
        fields={"part_of": {"sphere": s.dawn, "drawer": RITES}},
        facts=[PreviewFact(category="general", text="Embers glow.")],
        prose={},
        move_in=[
            MoveInFact(fact_id=about.fact_id, from_id=s.dawn, text="x", ticked=True),
            forged,
        ],
    )
    await _act(plugin, "accept_preview", preview=filed.model_dump(mode="json"))
    assert not _errors(plugin)
    data = _last(plugin, "accept_preview")["data"]
    view = s.world.view()
    assert about.fact_id not in [f.fact_id for f in view.thing(s.dawn).facts]
    assert "The state church." in [f["rendered"] for f in data["facts"]]
    assert s.skips in [f.fact_id for f in view.thing(s.vasha).facts]
    assert any("Vasha" in note for note in data["notes"])


async def test_forged_refile_rows_are_refused(plugin, monkeypatch):
    """A re-file row moves an entry only into an outer body the preview
    names, from where that body goes: `to` naming a sphere the world has
    is refused outright (nothing written), and a row moving an entry from
    elsewhere is dropped with a note, the entry left where it is."""

    s = await _open_sphere_world(plugin)
    _record_prose(plugin, monkeypatch)
    head = s.world.head_rev()
    preview = CreatePreview(
        kind="lore",
        prompt="a watch",
        name="Vigil Watch",
        facts=[PreviewFact(category="general", text="It keeps watch.")],
        prose={},
        new_names=[
            {
                "name": "Order of the Dawn",
                "kind": "sphere",
                "template": "order",
                "part_of": {"sphere": s.dawn, "drawer": RITES},
            }
        ],
    )
    peak_home = {"sphere": s.dawn, "drawer": SITES}
    forged = preview.model_dump(mode="json")
    forged["refile"] = [
        {
            "thing_id": s.peak,
            "from": peak_home,
            "to": {"sphere": s.tsardom, "drawer": LANDS},
            "ticked": True,
        }
    ]
    before = len(_errors(plugin))
    await _act(plugin, "accept_preview", preview=forged)
    assert len(_errors(plugin)) == before + 1
    assert s.world.head_rev() == head

    forged["refile"] = [
        {
            "thing_id": s.peak,
            "from": peak_home,
            "to": {"name": "Order of the Dawn", "drawer": "unsorted"},
            "ticked": True,
        }
    ]
    await _act(plugin, "accept_preview", preview=forged)
    assert not _errors(plugin)[before + 1 :]
    data = _last(plugin, "accept_preview")["data"]
    assert s.world.view().thing(s.peak).fields["part_of"] == peak_home
    assert any("Dawn Peak" in note for note in data["notes"])


async def test_accept_sphere_schedules_prose_for_linked_entries(
    plugin, client, monkeypatch
):
    """`accept_sphere` schedules prose for an entry the world has whose
    prose reads the text an item wrote onto it (the Dawn Vigil's), never
    for the new sphere (its summary is cached) or a statement."""

    s = await _open_sphere_world(plugin)
    reply = json.dumps(
        {
            "name": "The Iron Synod",
            "summary": "A council of smiths.",
            "aka": [],
            "timeline": [],
            "drawers": [{"type": "practices", "title": "Rites"}],
            "items": [
                {"drawer": "Rites", "name": "", "text": "Iron is sung to."},
                {"drawer": "Rites", "name": "Night Watch", "text": "Kept by smiths."},
            ],
            "names": [],
        }
    )
    async with MockClientContext():
        client_responses.get().append(reply)
        await _act(plugin, "preview_sphere", template="order", prompt="smiths")
        await _drain(plugin)
    preview = _last(plugin, "preview_sphere")["data"]
    item = next(i for i in preview["items"] if i.get("name") == "Night Watch")
    item.update(name="Dawn Vigil", thing_id=s.vigil, kind="lore")
    scheduled = _record_prose(plugin, monkeypatch)
    await _act(plugin, "accept_sphere", preview=preview)
    assert not _errors(plugin)
    synod = _last(plugin, "accept_sphere")["data"]["id"]
    assert "Kept by smiths." in [f.text for f in s.world.view().thing(s.vigil).facts]
    assert scheduled == [s.vigil]
    assert synod not in scheduled


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
    preview = _last(plugin, "preview_thing")["data"]
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
    preview = _last(plugin, "preview_thing")["data"]
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
    offers = _last(plugin, "preview_thing")["data"]["same_as"]
    assert {offer["thing_id"]: offer["stub"] for offer in offers} == {
        lake: False,
        shore: True,
    }
    assert "stub" in next(o["line"] for o in offers if o["thing_id"] == lake)
