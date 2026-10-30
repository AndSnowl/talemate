"""Heritage end to end, with the mock model: species, race and character
created through the real `worlds` router, a scene planned and started
through it with an invented owl-folk innkeeper, then played the way plan
A's slice test plays (`test_slice_end_to_end.py`): loaded through its
`world://` target, with `@` action turns and time passing.

What it checks:

- a Snowy character's sheet carries what she inherits (Snowy plumage, the
  owl-folk body) but not the yellow eyes her own black eyes override, and
  has a life stage worked out from the species' numbers;
- the invented innkeeper, given only the species as his heritage, starts
  the scene with the owl-folk body in his description and the species'
  instincts as his personality;
- a species fact dated "since 500", added after the character's prose
  was written, reaches her sheet as a since line once the scene's clock
  passes 500 -- with no model call for the time passage.

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
from talemate.worldplay.create import preview_inherited
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

WINGS = "Owl-folk have broad wings in place of arms."
TALONS = "Owl-folk grip and handle things with the talons of their feet."
YELLOW_EYES = "Owl-folk have large yellow eyes."
DUSK = "Owl-folk are crepuscular: most awake at dusk and dawn."
HEAD_TURN = "Owl-folk turn their whole head to look, rather than their eyes."

SPECIES_REPLY = json.dumps(
    {
        "name": "Owl-folk",
        "lifespan": 60,
        "adult_age": 16,
        "facts": [
            {"category": "physical", "text": WINGS},
            {"category": "physical", "text": TALONS},
            {"category": "physical", "text": YELLOW_EYES},
            {"category": "instinct", "text": DUSK},
            {"category": "instinct", "text": HEAD_TURN},
        ],
    }
)

PLUMAGE = "Snowy owl-folk have white plumage flecked with black."
RACE_REPLY = json.dumps(
    {
        "name": "Snowy",
        "facts": [{"category": "variation", "text": PLUMAGE}],
        "no_longer_true": [],
    }
)

BLACK_EYES = "Eira's eyes are a deep, glossy black."


def _character_reply(yellow_eyes_label: str) -> str:
    """The character's create reply, its black eyes overriding the
    inherited fact the prompt labels `yellow_eyes_label`."""

    return json.dumps(
        {
            "name": "Eira",
            "facts": [
                {
                    "category": "appearance",
                    "text": BLACK_EYES,
                    "overrides": [yellow_eyes_label],
                },
                {
                    "category": "background",
                    "text": "Carries letters between river towns.",
                },
                {"category": "personality", "text": "Dry-humoured and curious."},
            ],
        }
    )


# added after Eira's prose was written: it reaches her sheet as a since
# line, prefixed with the species' name
RUFF = "Owl-folk grow a ruff of winter down."
RUFF_PROSE = "The Owl-folk are winged and taloned, with a winter ruff."

INNKEEPER_FACT = "Keeps the Hollow Oak inn."
SETUP_REPLY = json.dumps(
    {
        "player": "Ilse",
        "characters": [
            {"name": "Ilse", "facts": ["A young traveller."]},
            {"name": "Eira"},
            {"name": "Brannoc", "facts": [INNKEEPER_FACT], "heritage": "Owl-folk"},
        ],
        "place": {"name": "The Hollow Oak", "facts": ["An inn inside a hollow oak."]},
        "goal": "Find a courier for the letter.",
        "intro": "Dusk settles over the Hollow Oak.",
    }
)
# Eira's prose for the scene's start, 499: before the ruff
PROSE_499 = "Eira is a Snowy courier with white, black-flecked plumage."
PERSONALITY_499 = "Eira is dry-humoured and curious, most awake at dusk."

TURN_EIRA = "Eira: I can fly it north by dawn."
TURN_EIRA_2 = "Eira: Another winter, and the river towns still want letters."
TURN_BRANNOC = "Brannoc: Rooms are up the trunk. Mind the perches."


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

    mock = MockClient("heritage")
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
    """What loading a world scene needs from a test (as in the slice
    test), plus the offline embedding function for the setup's index."""

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


async def _create(plugin, kind, prompt, fields, *responses) -> dict:
    """Preview then accept a `kind` thing; returns the accepted thing."""

    await _send(
        plugin,
        "preview_thing",
        *responses,
        kind=kind,
        prompt=prompt,
        fields=fields,
    )
    # the draft page's data to accept (Filing, Task 6)
    preview = _last(plugin, "preview_thing")["preview"]
    await _send(plugin, "accept_preview", preview=preview)
    return _last(plugin, "accept_preview")


async def _load(world, scene_id: str, client: MockClient) -> Scene:
    """Load a world scene through `load_scene` and its `world://` target,
    with every agent on `client` and long-term memory off (as in the
    slice test)."""

    scene = MockScene()
    bootstrap_scene(scene)
    for agent in instance.AGENTS.values():
        agent.client = client
        long_term_memory = getattr(agent, "actions", {}).get("use_long_term_memory")
        if long_term_memory is not None:
            long_term_memory.enabled = False
    scene.mock_client = client
    return await load_scene(scene, world_target(str(world.path), scene_id))


async def _turn(scene: Scene, client: MockClient, name: str, reply: str) -> str:
    """One `@` action turn for `name`; returns the conversation prompt,
    after checking it was the turn's only model call."""

    actor = next(a for a in scene.actors if a.character.name == name)
    before = len(client.prompt_history)
    with ActiveScene(scene):
        async with MockClientContext():
            _queue(reply)
            messages = await instance.get_agent("conversation").converse(
                actor, instruction=f"{name} answers Ilse."
            )
            await scene.push_history(messages)

    calls = client.prompt_history[before:]
    assert [call["kind"] for call in calls] == ["conversation"]
    return str(calls[0]["prompt"])


def _cast_lines(prompt: str) -> dict[str, str]:
    """The World block's cast lines in `prompt`, by character name."""

    return {
        line[2:].split(" (", 1)[0]: line
        for line in prompt.splitlines()
        if line.startswith("- ") and " (" in line and "): " in line
    }


def _character(scene: Scene, name: str):
    return next(a.character for a in scene.actors if a.character.name == name)


@requires_chromadb
async def test_heritage_end_to_end(plugin, client, loadable):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Vael",
            "present_year": 520,
        }
    )
    world = plugin.world

    # 1. the species, its race, and a Snowy character whose own black
    # eyes override the species' yellow ones
    owl_folk = await _create(plugin, "species", "owl people", {}, SPECIES_REPLY)
    assert owl_folk["numbers"]["lifespan"] == 60
    assert owl_folk["numbers"]["adult_age"] == 16
    snowy = await _create(
        plugin,
        "race",
        "white owl-folk of the north",
        {"species": owl_folk["id"]},
        RACE_REPLY,
    )
    yellow_eyes = next(
        f["fact_id"] for f in owl_folk["facts"] if f["text"] == YELLOW_EYES
    )
    # the prompt labels what a Snowy inherits F1...Fn, in the order the
    # preview lists it
    fields = {
        "name": "Eira",
        "born": WorldDate.of(470).model_dump(),
        "heritage": snowy["id"],
    }
    shown = preview_inherited(world.view(), "character", fields)
    label = f"F{[row.fact_id for row in shown].index(yellow_eyes) + 1}"

    eira = await _create(
        plugin,
        "character",
        "a Snowy courier",
        fields,
        _character_reply(label),
    )
    eyes = next(f for f in eira["facts"] if f["text"] == BLACK_EYES)
    assert eyes["overrides"] == [yellow_eyes]
    overridden = next(f for f in eira["inherited"] if f["fact_id"] == yellow_eyes)
    assert overridden["overridden_by"] == eyes["fact_id"]

    # 2. a dated species fact, since 500, added through the router after
    # Eira's prose was written; the species' own prose is refreshed
    await _send(
        plugin,
        "add_fact",
        RUFF_PROSE,
        thing_id=owl_folk["id"],
        category="physical",
        text=RUFF,
        valid_from=WorldDate.of(500).model_dump(),
        at=None,
    )
    assert any(f["text"] == RUFF for f in _last(plugin, "add_fact")["facts"])

    # 3. plan and start a scene in 499 with an invented owl-folk innkeeper
    await _send(
        plugin,
        "plan_scene",
        SETUP_REPLY,
        prompt="Ilse looks for a courier at the Hollow Oak",
        picks={"Eira": eira["id"]},
        player=None,
        start=WorldDate.of(499).model_dump(),
    )
    setup = _last(plugin, "plan_scene")["setup"]
    brannoc = next(
        c["local"]
        for c in setup["characters"]
        if c["local"] and c["local"]["name"] == "Brannoc"
    )
    assert brannoc["heritage_id"] == owl_folk["id"]

    before = len(client.prompt_history)
    await _send(plugin, "start_scene", PROSE_499, PERSONALITY_499, setup=setup)
    scene_id = _last(plugin, "start_scene")["scene_id"]
    # Eira's prose for 499 is written fresh (her stretch now ends at 500),
    # from what she inherits as of 499: plumage and the owl-folk body, not
    # the yellow eyes she overrides nor the ruff that's still to come
    started = client.prompt_history[before:]
    assert [c["kind"] for c in started] == ["analyze"] * 2
    description_prompt = str(started[0]["prompt"])
    assert PLUMAGE in description_prompt
    assert WINGS in description_prompt
    assert BLACK_EYES in description_prompt
    assert YELLOW_EYES not in description_prompt
    assert RUFF not in description_prompt
    assert DUSK in str(started[1]["prompt"])

    scene = await _load(world, scene_id, client)
    try:
        # 4. Eira's sheet at 499: her prose, the own-traits line and an
        # adult's life stage (29, with the species adult at 16)
        sheet = _character(scene, "Eira")
        assert PROSE_499 in sheet.description
        assert "Eira's own traits hold." in sheet.description
        assert "Since 500" not in sheet.description
        assert YELLOW_EYES not in sheet.description
        assert sheet.base_attributes["age"] == 29
        assert sheet.base_attributes["life_stage"] == "adult"
        assert sheet.base_attributes["personality"] == PERSONALITY_499
        prompt_eira = await _turn(scene, client, "Eira", TURN_EIRA)
        assert PROSE_499 in prompt_eira
        assert "Find a courier for the letter." in prompt_eira
        assert "The Hollow Oak" in prompt_eira
        # the World block names who is here by heritage, for the narrator
        # (whose prompts carry no character sheets) as much as the actors
        cast = _cast_lines(prompt_eira)
        assert cast["Eira"].startswith("- Eira (Snowy, a race of Owl-folk): ")
        assert BLACK_EYES in cast["Eira"] and WINGS in cast["Eira"]
        assert YELLOW_EYES not in cast["Eira"]
        assert cast["Brannoc"].startswith("- Brannoc (Owl-folk, a species): ")
        assert TALONS in cast["Brannoc"] and DUSK in cast["Brannoc"]
        assert "Ilse" not in cast

        # 5. the invented innkeeper has the owl-folk body and instincts
        innkeeper = _character(scene, "Brannoc")
        assert innkeeper.world_heritage_id == owl_folk["id"]
        assert INNKEEPER_FACT in innkeeper.description
        assert WINGS in innkeeper.description
        assert TALONS in innkeeper.description
        assert DUSK in innkeeper.base_attributes["personality"]
        prompt_brannoc = await _turn(scene, client, "Brannoc", TURN_BRANNOC)
        assert WINGS in prompt_brannoc
        assert TALONS in prompt_brannoc

        # 6. a year passes, from 499 into 500, across the dated species
        # fact: no model call for that, and Eira's next turn sees the ruff
        # through a since line (her stretch's prose predates it)
        before = len(client.prompt_history)
        with ActiveScene(scene):
            await instance.get_agent("world_state").advance_time("P1Y")
        assert client.prompt_history[before:] == []
        since = f"Since 500: Owl-folk: {RUFF}"
        assert since in _character(scene, "Eira").description
        prompt_eira_2 = await _turn(scene, client, "Eira", TURN_EIRA_2)
        assert since in prompt_eira_2
        # the cast follows the clock: the ruff is in Eira's line now (the
        # innkeeper's heritage is resolved as of the scene's date too)
        assert all(RUFF in line for line in _cast_lines(prompt_eira_2).values())
        # the yellow eyes stay overridden: no since line for them (the
        # prompt does show them, in the innkeeper's description)
        assert YELLOW_EYES not in _character(scene, "Eira").description
    finally:
        close_world_scene(scene)

    # 7. the whole run's model calls, by kind: three turns, the rest only
    # at creation, the species edit and the scene's setup and start
    kinds = Counter(call["kind"] for call in client.prompt_history)
    assert kinds == {
        # species, race, character
        "creative_instruction_3072": 3,
        # the scene's plan
        "creative_instruction_2048": 1,
        # after each accept (a draft writes none, languages 4a): the
        # species, the race and Eira's two; then the species after the
        # ruff, and Eira's two at 499
        "analyze": 7,
        "conversation": 3,
    }
