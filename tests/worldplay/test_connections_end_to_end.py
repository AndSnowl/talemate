"""Connections end to end, with the mock model, through the real `worlds`
router: the owner's session from the connections spec ("How the owner will
judge it"), then a scene that fills the stubs it uses.

1. The Owl-folk species is created; its origin fact names the Tsardom of
   Moscavia, which becomes a stub on accept.
2. The Tsardom is expanded from its stub: its prompt carries the origin
   fact that mentions it, the stub's id is kept, and its own facts name
   the city of Kalmara, a new stub.
3. Vasha, an Owl-folk character, is created; her relationship fact names
   her brother Aldric, another stub.
4. A place prompt saying "Moscavian Owls" (one of the Owl-folk's other
   names) matches the species; the place's facts link the phrase to it and
   no "Moscavian Owls" stub is made.
5. A scene with Vasha in Kalmara: the setup names Kalmara as the place and
   Aldric (pulled in from Vasha's facts) as a character, so both stubs get
   a preview at planning and are filled at start under their own ids.
6. The scene is loaded and played for one turn: that turn's only model call
   is the conversation (name-finding is code, never a model call), and the
   router's lookups (`match_names`, `list_stubs`, `get_thing`) make none.

Only `MockClient` responses are queued; one client serves the router and
every agent, so its `prompt_history` is the run's record of model calls.
"""

import asyncio
import json
from collections import Counter

import pytest

import talemate.instance as instance
from talemate.config import Config, get_config
from talemate.config.schema import RecentScenes
from talemate.context import ActiveScene
from talemate.load import load_scene
from talemate.server.worlds import WorldsPlugin
from talemate.tale_mate import Scene
from talemate.world.dates import WorldDate
from talemate.worldplay.persistence import close_world_scene, world_target

from conftest import (
    MockClient,
    MockClientContext,
    MockMemoryAgent,
    MockScene,
    bootstrap_scene,
    client_responses,
)
from world.embedding import TrigramEmbeddingFunction, requires_chromadb

ORIGIN = (
    "In 994, every person in the Tsardom of Moscavia awoke as owl-folk "
    "overnight, in what Moscavians call the Night of Feathers."
)
WINGS = "Owl-folk have broad wings in place of arms."
DUSK = "Owl-folk are crepuscular: drowsy at midday, most alert at dusk."

SPECIES_REPLY = json.dumps(
    {
        "name": "Owl-folk",
        "lifespan": 70,
        "adult_age": 12,
        "aka": [
            {"name": "Moscavian Owls", "tag": "common", "everyday": False},
            {"name": "Owls", "tag": "common", "everyday": True},
        ],
        "facts": [
            {"category": "origin", "text": ORIGIN},
            {"category": "physical", "text": WINGS},
            {"category": "instinct", "text": DUSK},
        ],
        "names": [{"name": "Tsardom of Moscavia", "kind": "place", "aka": []}],
    }
)
SPECIES_PROSE = "The Owl-folk are winged and crepuscular."

KALMARA_FACT = "Its capital, Kalmara, holds court only at dusk."
PERCHES = "Moscavian law requires every doorway to be round, for wingspans."
TSARDOM_REPLY = json.dumps(
    {
        "name": "Tsardom of Moscavia",
        "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
        "facts": [
            {"category": "description", "text": KALMARA_FACT},
            {"category": "law", "text": PERCHES},
        ],
        # the model lists the world's Owl-folk too: never a new stub
        "names": [
            {"name": "Kalmara", "kind": "place", "aka": []},
            {"name": "Owl-folk", "kind": "species", "aka": []},
        ],
    }
)
TSARDOM_PROSE = "Moscavia is a dusk realm of round doors."

ALDRIC_FACT = "Vasha's brother Aldric keeps the ferry at Kalmara."
VASHA_REPLY = json.dumps(
    {
        "name": "Vasha",
        "facts": [
            {"category": "relationship", "text": ALDRIC_FACT},
            {"category": "background", "text": "A courier of the dusk court."},
        ],
        "names": [
            {"name": "Aldric", "kind": "character", "aka": []},
            {"name": "Kalmara", "kind": "place", "aka": []},
        ],
    }
)
VASHA_PROSE = "Vasha is an owl-folk courier."

TOWN_PROMPT = "a river town where Moscavian Owls trade with barge crews"
TOWN_FACT = "Moscavian Owls trade amber here at dusk with the barge crews."
TOWN_REPLY = json.dumps(
    {
        "name": "Barrowford",
        "facts": [{"category": "description", "text": TOWN_FACT}],
        # the model names them as a species: they're the world's Owl-folk
        "names": [{"name": "Moscavian Owls", "kind": "species", "aka": []}],
    }
)
TOWN_PROSE = "Barrowford is a river town of amber traders."

SETUP_REPLY = json.dumps(
    {
        "player": "Vasha",
        "characters": [
            {"name": "Vasha", "world": True},
            {"name": "Aldric", "world": True},
        ],
        "place": {"name": "Kalmara", "world": True},
        "goal": "Find who sank the ferry.",
        "intro": "Dusk settles over Kalmara's round doors.",
    }
)
# the stub previews at planning, in setup order: Aldric (a character), then
# Kalmara (the place); each its create reply, then its prose
ALDRIC_PREVIEW = json.dumps(
    {
        "name": "Aldric",
        "facts": [{"category": "background", "text": "Ferryman of Kalmara."}],
        "names": [{"name": "Kalmara", "kind": "place", "aka": []}],
    }
)
ALDRIC_PROSE = "Aldric is a weathered owl-folk ferryman."
KALMARA_PREVIEW = json.dumps(
    {
        "name": "Kalmara",
        "facts": [
            {
                "category": "description",
                "text": "A river capital of round towers and dusk markets.",
            }
        ],
        "names": [],
    }
)
KALMARA_PROSE = "Kalmara is a capital of round towers."

TURN_ALDRIC = "Aldric: The ferry went down at midday, while we slept."


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


async def _noop(self, *args, **kwargs):
    pass


class _Handler:
    """Minimal websocket handler stand-in: no scene, a queue_put collector."""

    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


@pytest.fixture
def client():
    """One `MockClient` for every agent, so the router's creator-agent
    client and the scene's agents are the same."""

    mock = MockClient("connections")
    bootstrap_scene(MockScene())
    for agent in instance.AGENTS.values():
        agent.client = mock
    return mock


@pytest.fixture
def plugin(tmp_path, client):
    plug = WorldsPlugin(_Handler())
    plug.worlds_root = tmp_path
    yield plug
    plug.disconnect()


@pytest.fixture
def loadable(monkeypatch):
    """What planning (the index) and loading a world scene need from a
    test, as in the heritage end-to-end test."""

    embedding = TrigramEmbeddingFunction()
    monkeypatch.setattr(
        MockMemoryAgent, "embedding_function", property(lambda self: embedding)
    )
    monkeypatch.setattr(MockMemoryAgent, "set_db", _noop)
    monkeypatch.setattr(MockMemoryAgent, "_get_document", lambda self, id: {})
    monkeypatch.setattr(Scene, "commit_to_memory", _noop)
    monkeypatch.setattr(Config, "set_dirty", _noop)
    monkeypatch.setattr(get_config(), "recent_scenes", RecentScenes(scenes=[]))


def _last(plugin, action):
    replies = [
        m
        for m in plugin.websocket_handler.messages
        if m["type"] == "worlds" and m["action"] == action
    ]
    assert replies, f"no {action!r} reply in {plugin.websocket_handler.messages}"
    return replies[-1]["data"]


async def _drain(plugin):
    while plugin.tasks:
        await asyncio.gather(*list(plugin.tasks), return_exceptions=True)


async def _send(plugin, action: str, *responses: str, **data):
    """Send `action` through the router with `responses` queued, waiting
    for its background task (if any) to finish."""

    async with MockClientContext():
        _queue(*responses)
        await plugin.handle({"type": "worlds", "action": action, **data})
        await _drain(plugin)


async def _preview(plugin, client, *responses: str, **data) -> tuple[dict, str]:
    """Preview through the router; returns the preview and its create
    prompt (the first model call it made)."""

    before = len(client.prompt_history)
    await _send(plugin, "preview_thing", *responses, **data)
    return _last(plugin, "preview_thing"), str(client.prompt_history[before]["prompt"])


async def _accept(plugin, preview: dict, into_stub: str | None = None) -> dict:
    await _send(plugin, "accept_preview", preview=preview, into_stub=into_stub)
    return _last(plugin, "accept_preview")


async def _stubs(plugin) -> dict[str, dict]:
    await _send(plugin, "list_stubs", include_ignored=True)
    return {stub["name"]: stub for stub in _last(plugin, "list_stubs")["stubs"]}


def _linked(thing: dict, text: str) -> list[tuple[str, str | None, bool]]:
    """The `(text, ref, stub)` runs of `thing`'s fact that renders as `text`
    (a linked fact's own text holds its references)."""

    runs = [
        [(s["text"], s["ref"], s["stub"]) for s in fact["segments"]]
        for fact in thing["facts"]
    ]
    return next(r for r in runs if "".join(run[0] for run in r) == text)


async def _load(world, scene_id: str, client: MockClient) -> Scene:
    """Load a world scene through `load_scene` and its `world://` target,
    with every agent on `client` and long-term memory off."""

    scene = MockScene()
    bootstrap_scene(scene)
    for agent in instance.AGENTS.values():
        agent.client = client
        long_term_memory = getattr(agent, "actions", {}).get("use_long_term_memory")
        if long_term_memory is not None:
            long_term_memory.enabled = False
    scene.mock_client = client
    return await load_scene(scene, world_target(str(world.path), scene_id))


@requires_chromadb
async def test_connections_end_to_end(plugin, client, loadable):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Moscavia",
            "present_year": 1020,
        }
    )
    world = plugin.world

    # 1. the species: its origin names the Tsardom, which becomes a stub
    preview, _ = await _preview(
        plugin,
        client,
        SPECIES_REPLY,
        SPECIES_PROSE,
        kind="species",
        prompt="owl people who were once human, in a Russian-flavoured realm",
        fields={},
    )
    assert [(n["name"], n["kind"]) for n in preview["new_names"]] == [
        ("Tsardom of Moscavia", "place")
    ]
    owl_folk = await _accept(plugin, preview)
    assert [a["name"] for a in owl_folk["aka"]] == ["Moscavian Owls", "Owls"]
    stubs = await _stubs(plugin)
    assert list(stubs) == ["Tsardom of Moscavia"]
    tsardom_id = stubs["Tsardom of Moscavia"]["id"]
    assert stubs["Tsardom of Moscavia"]["kind"] == "place"
    assert stubs["Tsardom of Moscavia"]["first_mentioned"] == {
        "thing_id": owl_folk["id"],
        "name": "Owl-folk",
    }
    # the origin fact keeps its words, the Tsardom linked as a stub
    assert ("Tsardom of Moscavia", tsardom_id, True) in _linked(owl_folk, ORIGIN)

    # 2. the Tsardom, expanded from its stub with its suggested prompt: the
    # origin fact and the Owl-folk's body and instincts are in its prompt
    await _send(plugin, "stub_suggestion", id=tsardom_id)
    suggestion = _last(plugin, "stub_suggestion")
    assert suggestion["prompt"].startswith("Tsardom of Moscavia: In 994,")
    assert suggestion["context"] == [
        ["Owl-folk (species, usually called Owls)", [ORIGIN, WINGS, DUSK]]
    ]
    preview, prompt = await _preview(
        plugin,
        client,
        TSARDOM_REPLY,
        TSARDOM_PROSE,
        kind="place",
        prompt=suggestion["prompt"],
        fields={},
        stub_id=tsardom_id,
    )
    assert f"- Owl-folk (species, origin; usually called Owls): {ORIGIN}" in prompt
    assert WINGS in prompt and DUSK in prompt
    assert preview["stub_id"] == tsardom_id
    # the world's Owl-folk isn't new; Kalmara is
    assert [n["name"] for n in preview["new_names"]] == ["Kalmara"]
    tsardom = await _accept(plugin, preview, into_stub=tsardom_id)
    assert tsardom["id"] == tsardom_id
    assert tsardom["stub"] is None
    assert tsardom["fields"]["name"] == "Tsardom of Moscavia"
    stubs = await _stubs(plugin)
    assert list(stubs) == ["Kalmara"]
    kalmara_id = stubs["Kalmara"]["id"]
    assert ("Kalmara", kalmara_id, True) in _linked(tsardom, KALMARA_FACT)
    # the Owl-folk's origin now links to a full entry, its words unchanged
    await _send(plugin, "get_thing", id=owl_folk["id"], at=None)
    owl_folk = _last(plugin, "get_thing")
    assert ("Tsardom of Moscavia", tsardom_id, False) in _linked(owl_folk, ORIGIN)

    # 3. Vasha, whose relationship fact names her brother Aldric (a new
    # stub) and the Kalmara stub (linked, not stubbed again)
    preview, _ = await _preview(
        plugin,
        client,
        VASHA_REPLY,
        VASHA_PROSE,
        kind="character",
        prompt="an owl-folk courier of Kalmara",
        fields={"name": "Vasha", "heritage": owl_folk["id"]},
        picks={"Kalmara": kalmara_id},
    )
    assert [n["name"] for n in preview["new_names"]] == ["Aldric"]
    vasha = await _accept(plugin, preview)
    stubs = await _stubs(plugin)
    assert sorted(stubs) == ["Aldric", "Kalmara"]
    aldric_id = stubs["Aldric"]["id"]
    assert stubs["Kalmara"]["mentions"] == 2
    assert _linked(vasha, ALDRIC_FACT) == [
        ("Vasha's brother ", None, False),
        ("Aldric", aldric_id, True),
        (" keeps the ferry at ", None, False),
        ("Kalmara", kalmara_id, True),
        (".", None, False),
    ]

    # 4. "Moscavian Owls" in a place prompt matches the Owl-folk by their
    # other name; picked, it reaches the prompt as the species, and the
    # place's fact links it there -- no duplicate stub
    before = len(client.prompt_history)
    await _send(plugin, "match_names", text=TOWN_PROMPT, at=None)
    matched = _last(plugin, "match_names")
    owls = next(m for m in matched["matches"] if m["text"] == "Moscavian Owls")
    assert owls["candidates"][0]["id"] == owl_folk["id"]
    assert owls["candidates"][0]["via"] == "aka"
    preview, prompt = await _preview(
        plugin,
        client,
        TOWN_REPLY,
        TOWN_PROSE,
        kind="place",
        prompt=TOWN_PROMPT,
        fields={},
        picks={"Moscavian Owls": owl_folk["id"]},
    )
    assert '"Moscavian Owls" means Owl-folk (species, usually called Owls):' in prompt
    assert preview["new_names"] == []
    town = await _accept(plugin, preview)
    assert _linked(town, TOWN_FACT)[0] == ("Moscavian Owls", owl_folk["id"], False)
    assert sorted(await _stubs(plugin)) == ["Aldric", "Kalmara"]
    # the lookups were code: two creates' calls only (create, prose)
    assert len(client.prompt_history) - before == 2

    # 5. a scene with Vasha in Kalmara: the setup names Kalmara and Aldric
    # (from Vasha's relationship fact); each stub gets a preview at
    # planning and is filled at start, keeping its id
    await _send(
        plugin,
        "plan_scene",
        SETUP_REPLY,
        ALDRIC_PREVIEW,
        ALDRIC_PROSE,
        KALMARA_PREVIEW,
        KALMARA_PROSE,
        prompt="Vasha looks into the sunken ferry in Kalmara",
        picks={"Vasha": vasha["id"], "Kalmara": kalmara_id},
        player=vasha["id"],
        start=WorldDate.of(1020).model_dump(),
    )
    setup = _last(plugin, "plan_scene")["setup"]
    assert {"thing_id": aldric_id, "local": None} in setup["characters"]
    assert setup["place"] == {"thing_id": kalmara_id, "local": None}
    assert [p["stub_id"] for p in setup["stub_previews"]] == [aldric_id, kalmara_id]
    aldric_preview = setup["stub_previews"][0]
    assert aldric_preview["kind"] == "character"
    assert aldric_preview["name"] == "Aldric"
    # each was written knowing what mentions it: Aldric from Vasha's
    # relationship fact, Kalmara from the Tsardom and Vasha
    assert aldric_preview["context"] == [
        ["Vasha (character)", [ALDRIC_FACT, "A courier of the dusk court."]]
    ]
    assert [heading for heading, _ in setup["stub_previews"][1]["context"]] == [
        "Tsardom of Moscavia (place, usually called Moscavia)",
        "Vasha (character)",
    ]
    # the Kalmara stub Aldric's facts name is linked, not stubbed again
    assert aldric_preview["new_names"] == []
    # planning wrote nothing: both are still stubs
    assert sorted(await _stubs(plugin)) == ["Aldric", "Kalmara"]

    await _send(plugin, "start_scene", setup=setup)
    scene_id = _last(plugin, "start_scene")["scene_id"]
    assert await _stubs(plugin) == {}
    for thing_id, name in ((aldric_id, "Aldric"), (kalmara_id, "Kalmara")):
        await _send(plugin, "get_thing", id=thing_id, at=None)
        filled = _last(plugin, "get_thing")
        assert filled["id"] == thing_id
        assert filled["stub"] is None
        assert filled["fields"]["name"] == name
        assert filled["facts"]
    # Vasha's fact still names them in its own words, now as entries
    await _send(plugin, "get_thing", id=vasha["id"], at=None)
    assert ("Aldric", aldric_id, False) in _linked(
        _last(plugin, "get_thing"), ALDRIC_FACT
    )

    # 6. an ordinary turn: one model call, the conversation's
    scene = await _load(world, scene_id, client)
    try:
        actor = next(a for a in scene.actors if a.character.name == "Aldric")
        before = len(client.prompt_history)
        with ActiveScene(scene):
            async with MockClientContext():
                _queue(TURN_ALDRIC)
                messages = await instance.get_agent("conversation").converse(
                    actor, instruction="Aldric answers Vasha."
                )
                await scene.push_history(messages)
        calls = client.prompt_history[before:]
        assert [call["kind"] for call in calls] == ["conversation"]
        assert "A river capital of round towers and dusk markets." in str(
            calls[0]["prompt"]
        )
    finally:
        close_world_scene(scene)

    # the whole run's model calls: creates, planning and the one turn --
    # nothing for lookups, linking or making stubs
    kinds = Counter(call["kind"] for call in client.prompt_history)
    assert kinds == {
        # species, Tsardom, Vasha, the town; the scene's plan; Aldric's and
        # Kalmara's stub previews
        "creative_instruction_2048": 7,
        # one section each, two for Vasha (her species' instincts give her
        # a personality); none at start, the previews' prose is current
        "analyze": 7,
        "conversation": 1,
    }
