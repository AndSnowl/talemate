"""World-level AI calls must work with no scene active, or an inactive
one -- the owner hit this from the World tab, before any scene was
playing: `preview_thing` raised `SceneInactiveError` instead of asking the
model.

`MockClient` (the fixture used everywhere else in this package's tests)
overrides `send_prompt` and skips `ClientBase._send_prompt` entirely, so
it never exercises the active-scene check and couldn't have caught this.
These tests drive a plain `ClientBase` subclass instead, stubbing only
`generate` (the actual network call), so the real check runs."""

import json
from collections import deque

import pytest

import talemate.instance as instance
from talemate.agents.context import active_agent
from talemate.agents.creator import CreatorAgent
from talemate.client.base import ClientBase
from talemate.client.context import ClientContext
from talemate.context import ActiveScene
from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay.create import preview_thing
from talemate.worldplay.prose_gen import generate_section
from talemate.worldplay.setup import plan_scene

from conftest import MockScene

START = WorldDate.of(313, 6, 1)


@pytest.fixture
def creator_agent():
    """A real `creator` agent, registered the way `server/worlds.py`
    expects to find one (`instance.get_agent("creator")`). Restored by the
    autouse `restore_global_registries` fixture."""

    agent = CreatorAgent()
    instance.AGENTS["creator"] = agent
    return agent


class _RealCheckClient(ClientBase):
    """A `ClientBase` subclass whose `send_prompt` is the real one --
    unlike `MockClient`'s override, this runs `_send_prompt`'s active-scene
    check. `generate` (the actual network call) is stubbed to pop replies
    off a queue, and records the active-agent context seen on each call so
    tests can confirm which agent the call ran as."""

    client_type = "test-real-check"

    def __init__(self, name: str, replies: list[str]):
        super().__init__(name=name)
        self._replies = deque(replies)
        self.seen_agents: list = []

    @property
    def enabled(self) -> bool:
        return True

    async def status(self) -> None:
        self.connected = True

    async def get_model_name(self) -> str | None:
        return self.remote_model_name

    async def generate(self, prompt: str, parameters: dict, kind: str) -> str:
        context = active_agent.get()
        self.seen_agents.append(context.agent if context else None)
        return self._replies.popleft()


LOWMERE_REPLY = json.dumps(
    {
        "name": "Lowmere",
        "facts": [
            {"category": "description", "text": "Half its streets are flooded."},
        ],
    }
)


async def test_preview_thing_with_no_active_scene(world, creator_agent):
    client = _RealCheckClient(
        "rc-preview-none", [LOWMERE_REPLY, "Lowmere is half under water."]
    )
    with ClientContext():
        preview = await preview_thing(world, "place", "a half-flooded town", {}, client)

    assert preview.name == "Lowmere"
    assert preview.prose == {"description": "Lowmere is half under water."}
    # ran as the creator agent, not a generic stand-in -- its own
    # generation settings (e.g. prompt-caching) apply, same as any other
    # call on its client
    assert client.seen_agents == [creator_agent, creator_agent]


async def test_preview_thing_with_an_inactive_scene(world, creator_agent):
    client = _RealCheckClient(
        "rc-preview-dead", [LOWMERE_REPLY, "Lowmere is half under water."]
    )
    scene = MockScene()  # MockScene.active defaults to False, same as a dead scene
    with ClientContext():
        with ActiveScene(scene):
            preview = await preview_thing(
                world, "place", "a half-flooded town", {}, client
            )

    assert preview.name == "Lowmere"
    assert client.seen_agents == [creator_agent, creator_agent]


async def test_preview_thing_falls_back_with_no_creator_agent(world):
    """No `creator` agent instantiated at all (e.g. a fresh app that
    hasn't touched the engine yet) still works -- the neutral stand-in
    takes over rather than crashing."""

    client = _RealCheckClient(
        "rc-preview-nocreator", [LOWMERE_REPLY, "Lowmere is half under water."]
    )
    with ClientContext():
        preview = await preview_thing(world, "place", "a half-flooded town", {}, client)

    assert preview.name == "Lowmere"
    assert all(agent.agent_type == "world" for agent in client.seen_agents)


async def test_generate_section_with_no_active_scene(world, creator_agent):
    with world.revision(Source.manual(note="setup")) as rev:
        lowmere = rev.create_thing("place", fields={"name": "Lowmere"})
        rev.add_fact(lowmere, "description", "Half its streets are flooded.")

    client = _RealCheckClient("rc-section-none", ["Lowmere is half under water."])
    with ClientContext():
        text = await generate_section(world, lowmere, "description", None, client)

    assert text == "Lowmere is half under water."
    assert client.seen_agents == [creator_agent]


async def test_plan_scene_with_an_inactive_scene(world, creator_agent):
    with world.revision(Source.manual(note="setup")) as rev:
        tobin = rev.create_thing("character", fields={"name": "Tobin"})
        stag = rev.create_thing("place", fields={"name": "The Drowned Stag"})

    reply = json.dumps(
        {
            "player": "Tobin",
            "characters": [],
            "place": {"name": "The Drowned Stag", "world": True},
            "goal": "Settle the toll dispute.",
            "intro": "Water laps at the floorboards.",
        }
    )
    client = _RealCheckClient("rc-plan-dead", [reply])
    scene = MockScene()
    with ClientContext():
        with ActiveScene(scene):
            setup = await plan_scene(
                world,
                "Tobin argues about the river tolls",
                {},
                tobin,
                START,
                client,
            )

    assert setup.player.thing_id == tobin
    assert setup.place.thing_id == stag
    assert setup.goal == "Settle the toll dispute."
    assert client.seen_agents == [creator_agent]
