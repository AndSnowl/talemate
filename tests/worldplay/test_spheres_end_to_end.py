"""Spheres end to end, with the mock model, through the real `worlds`
router: the owner's session from the spheres spec ("How the owner will
judge it"), in a fresh world.

1. The Owl-folk species, whose origin names the Tsardom of Moscavia; then
   the Tsardom, expanded from its stub. Its law names its religion, the
   White Dawn, which the reply lists as a religion sphere: the stub is a
   `sphere` guessed as a religion, so Expand offers that template.
2. The Council of Elders (a lore stub the Tsardom names) is expanded
   first. Its prompt names the White Dawn stub, so it's made part of it
   (unsorted), and the White Dawn is left a bare stub.
3. The White Dawn is expanded from its stub: its one call sees the council
   as "Already part of it", the reply relists it under Hierarchy, and it's
   adopted there rather than made again.
4. Fill Doctrines: a repeat of a held item is dropped, the rest kept; the
   White Dawn's summary stays its core's (a statement feeds no prose).
5. Vasha, an Owl-folk courier, is created: the White Dawn is in her
   prompt's spheres block, and her reply's tie and its "but..." exception
   (rejecting a labelled doctrine) are written.
6. A scene with Vasha at the Pale Spire, a holy site the White Dawn made:
   the scene's World block holds the White Dawn's key facts once (the
   place is in its territory and Vasha is tied to it), the council the
   goal names shows once, as lore, Vasha's sheet has her tie line, and a
   turn's only model call is the narrator's.

Only `MockClient` responses are queued; one client serves the router and
every agent, so its `prompt_history` is the run's record of model calls.
"""

import asyncio
import json
import re
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
from talemate.worldplay.context import world_context_block
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
SPECIES_REPLY = json.dumps(
    {
        "name": "Owl-folk",
        "lifespan": 70,
        "adult_age": 12,
        "facts": [
            {"category": "origin", "text": ORIGIN},
            {"category": "physical", "text": "Owl-folk have wings in place of arms."},
        ],
        "names": [{"name": "Tsardom of Moscavia", "kind": "place", "aka": []}],
    }
)
SPECIES_PROSE = "The Owl-folk are winged."

CHURCH = (
    "The White Dawn is the Tsardom's state church, and teaches that the "
    "Night of Feathers was a purification."
)
COUNCIL_FACT = "The Council of Elders of the White Dawn meets in Kremova."
TSARDOM_REPLY = json.dumps(
    {
        "name": "Tsardom of Moscavia",
        "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
        "facts": [
            {"category": "description", "text": "Its capital is Kremova."},
            {"category": "law", "text": CHURCH},
            {"category": "general", "text": COUNCIL_FACT},
        ],
        "names": [
            {"name": "Kremova", "kind": "place", "aka": []},
            {
                "name": "The White Dawn",
                "kind": "sphere",
                "template": "religion",
                "aka": [],
            },
            {"name": "Council of Elders", "kind": "lore", "aka": []},
        ],
    }
)
TSARDOM_PROSE = "Moscavia is a realm of owl-folk."

COUNCIL_TEXT = "Seven snowy elders who rule the White Dawn from Kremova."
COUNCIL_REPLY = json.dumps(
    {
        "name": "Council of Elders",
        "facts": [{"category": "general", "text": COUNCIL_TEXT}],
        "names": [
            {"name": "White Dawn", "kind": "sphere", "aka": []},
            {"name": "Kremova", "kind": "place", "aka": []},
        ],
    }
)
COUNCIL_PROSE = "Seven elders."

DAWN_SUMMARY = (
    "The White Dawn is the state church of Moscavia. It teaches that the "
    "Night of Feathers was a purification."
)
PURITY = "Snowy owl-folk are the purest of the folk."
# as a scene is told it: a Doctrines statement is held by the White Dawn
HELD_PURITY = "The White Dawn holds: Snowy owl-folk are the purest of the folk."
SEPARATION = "The faithful may not marry humans."
VIGIL = "The faithful watch the first light in silence on high galleries."
SPIRE = "A white tower in Kremova where pilgrims climb at midwinter."
DAWN_CORE = json.dumps(
    {
        "name": "The White Dawn",
        "summary": DAWN_SUMMARY,
        "aka": [],
        "timeline": [
            {"year": 994, "text": "Declared the Night of Feathers a purification."},
            {"year": 1001, "text": "Seated the Council of Elders in Kremova."},
        ],
        "drawers": [
            {"type": "beliefs", "title": "Doctrines"},
            {"type": "practices", "title": "Rites and Ceremonies"},
            {"type": "places", "title": "Holy Sites"},
            {"type": "structure", "title": "Hierarchy"},
        ],
        "items": [
            {"drawer": "Doctrines", "text": PURITY},
            {
                "drawer": "Doctrines",
                "name": "Doctrine of Separation",
                "text": SEPARATION,
                "kind": "lore",
            },
            {
                "drawer": "Rites and Ceremonies",
                "name": "The Dawn Vigil",
                "text": VIGIL,
                "kind": "rite",
            },
            {
                "drawer": "Holy Sites",
                "name": "The Pale Spire",
                "text": SPIRE,
                "kind": "place",
            },
            # relisted, though it's already part of it: adopted, not made
            {
                "drawer": "Hierarchy",
                "name": "The Council of Elders",
                "text": "Seven elders who rule on doctrine.",
                "kind": "lore",
            },
            {
                "drawer": "Hierarchy",
                "text": "Dawn-priests lead each parish under the Elders.",
            },
        ],
        "names": [
            {"name": "Kremova", "kind": "place", "aka": []},
            {"name": "Council of Elders", "kind": "sphere", "template": "council"},
        ],
    }
)

FEATHER = "Every believer offers a moulted feather at the altar each spring."
FILL_REPLY = json.dumps(
    {
        "new_items": [
            # a repeat of what Doctrines holds: dropped
            {"name": "Doctrine of Separation", "text": SEPARATION, "kind": "lore"},
            {"text": FEATHER},
            {
                "name": "The Silent Hour",
                "text": "No word is spoken from dusk until the first star.",
                "kind": "lore",
            },
        ],
        "names": [],
    }
)

VASHA_PROMPT = (
    "Vasha, an owl-folk courier raised in the White Dawn, who keeps the "
    "vigils but thinks the snowy-purity talk is nonsense"
)
DOUBT = "Thinks the talk of snowy owl-folk being purer is nonsense."
VASHA_PROSE = "Vasha is a sharp-eyed courier."

SETUP_REPLY = json.dumps(
    {
        "player": "Vasha",
        "characters": [
            {"name": "Vasha", "world": True},
            {
                "name": "Brother Oren",
                "facts": ["A dawn-priest of the Pale Spire."],
                "heritage": "Owl-folk",
            },
        ],
        "place": {"name": "The Pale Spire", "world": True},
        "goal": "Deliver a letter to the Council of Elders.",
        "intro": "Before dawn, Vasha climbs the last stair of the Pale Spire.",
    }
)
SPIRE_PREVIEW = json.dumps(
    {
        "name": "The Pale Spire",
        "facts": [
            {"category": "description", "text": "Its stair has a thousand steps."}
        ],
        "names": [],
    }
)
SPIRE_PROSE = "A pale tower."
TURN = "First light touches the gallery; the faithful fall silent."

SPHERES_LEAD = (
    "Spheres this scene touches (faiths, nations, orders, cultures): keep "
    "what they hold true, and bring it in only where the scene calls for it."
)


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

    mock = MockClient("spheres")
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
    test, as in the connections end-to-end test."""

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


async def _send(plugin, action: str, *responses: str, **data) -> dict:
    """Send `action` through the router with `responses` queued, wait for
    its background task (if any), and return its reply's data."""

    async with MockClientContext():
        _queue(*responses)
        await plugin.handle({"type": "worlds", "action": action, **data})
        await _drain(plugin)
    return _last(plugin, action)


async def _stubs(plugin) -> dict[str, dict]:
    listed = await _send(plugin, "list_stubs", include_ignored=True)
    return {stub["name"]: stub for stub in listed["stubs"]}


async def _thing(plugin, thing_id: str) -> dict:
    return await _send(plugin, "get_thing", id=thing_id, at=None)


def _text(segments: list[dict]) -> str:
    return "".join(s["text"] for s in segments)


def _drawer(sphere: dict, title: str) -> dict:
    return next(d for d in sphere["sphere"]["drawers"] if d["title"] == title)


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
async def test_spheres_end_to_end(plugin, client, loadable):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Moscavia",
            "present_year": 1020,
        }
    )
    world = plugin.world

    # 1. the species, then the Tsardom from its stub: its religion is a
    # sphere stub guessed as a religion
    preview = await _send(
        plugin,
        "preview_thing",
        SPECIES_REPLY,
        SPECIES_PROSE,
        kind="species",
        prompt="Owl-folk: owl people. Everyone in the Tsardom of Moscavia "
        "became this race suddenly one day.",
        fields={},
    )
    owl_folk = await _send(plugin, "accept_preview", preview=preview)
    tsardom_id = (await _stubs(plugin))["Tsardom of Moscavia"]["id"]
    suggestion = await _send(plugin, "stub_suggestion", id=tsardom_id)
    preview = await _send(
        plugin,
        "preview_thing",
        TSARDOM_REPLY,
        TSARDOM_PROSE,
        kind="place",
        prompt=suggestion["prompt"],
        fields={},
        stub_id=tsardom_id,
    )
    await _send(plugin, "accept_preview", preview=preview, into_stub=tsardom_id)
    stubs = await _stubs(plugin)
    assert {name: stub["kind"] for name, stub in stubs.items()} == {
        "Council of Elders": "lore",
        "Kremova": "place",
        "The White Dawn": "sphere",
    }
    dawn_id = stubs["The White Dawn"]["id"]
    council_id = stubs["Council of Elders"]["id"]
    dawn = await _thing(plugin, dawn_id)
    assert dawn["stub"] is not None
    assert dawn["sphere"]["template"] == "religion"
    assert dawn["sphere"]["agent"] is True

    # 2. the council first: its prompt names the White Dawn stub, so it's
    # made part of it, unsorted -- and the White Dawn stays a bare stub
    suggestion = await _send(plugin, "stub_suggestion", id=council_id)
    assert "White Dawn" in suggestion["prompt"]
    preview = await _send(
        plugin,
        "preview_thing",
        COUNCIL_REPLY,
        COUNCIL_PROSE,
        kind="lore",
        prompt=suggestion["prompt"],
        fields={},
        stub_id=council_id,
    )
    assert preview["part_of"] == {"sphere": dawn_id, "drawer": "unsorted"}
    council = await _send(
        plugin, "accept_preview", preview=preview, into_stub=council_id
    )
    assert council["part_of"]["sphere_id"] == dawn_id
    assert council["part_of"]["drawer_title"] == "Unsorted"
    dawn = await _thing(plugin, dawn_id)
    assert dawn["stub"] is not None
    assert dawn["facts"] == []
    assert [i["thing_id"] for d in dawn["sphere"]["drawers"] for i in d["items"]] == [
        council_id
    ]

    # 3. the White Dawn, written around the council: one call, which sees
    # it as already part of it; relisted under Hierarchy, it's adopted
    # there and never made again
    suggestion = await _send(plugin, "stub_suggestion", id=dawn_id)
    before = len(client.prompt_history)
    preview = await _send(
        plugin,
        "preview_sphere",
        DAWN_CORE,
        template="religion",
        prompt=suggestion["prompt"],
        fields={},
        stub_id=dawn_id,
    )
    [call] = client.prompt_history[before:]
    assert call["kind"] == "creative_instruction_2048"
    core_prompt = str(call["prompt"])
    assert "Already part of it" in core_prompt
    assert COUNCIL_TEXT in core_prompt
    assert CHURCH in core_prompt  # the Tsardom's mention
    hierarchy_id = next(
        d["id"] for d in preview["drawers"] if d["title"] == "Hierarchy"
    )
    assert preview["adopted"] == [{"thing_id": council_id, "drawer_id": hierarchy_id}]
    dawn = await _send(plugin, "accept_sphere", preview=preview)
    assert dawn["id"] == dawn_id
    assert dawn["stub"] is None
    assert [d["title"] for d in dawn["sphere"]["drawers"]] == [
        "Doctrines",
        "Rites and Ceremonies",
        "Holy Sites",
        "Hierarchy",
        "People",
        "Timeline",
        "Branches",
    ]
    hierarchy = _drawer(dawn, "Hierarchy")["items"]
    assert [i["thing_id"] for i in hierarchy][0] == council_id
    assert [i["name"] for i in hierarchy] == [
        "Council of Elders",
        "Dawn-priests lead each parish under the Elders.",
    ]
    doctrines = _drawer(dawn, "Doctrines")["items"]
    assert [i["name"] for i in doctrines] == ["Doctrine of Separation", PURITY]
    [spire] = _drawer(dawn, "Holy Sites")["items"]
    assert spire["name"] == "The Pale Spire" and spire["stub"]
    spire_id = spire["thing_id"]
    stubs = await _stubs(plugin)
    assert not [name for name in stubs if "Council" in name]

    # 4. Fill Doctrines: the repeat comes unticked (and isn't written); a
    # statement and a new named item are kept, and written on accept
    doctrines_id = _drawer(dawn, "Doctrines")["id"]
    filled = await _send(
        plugin, "fill_drawer", FILL_REPLY, sphere_id=dawn_id, drawer_id=doctrines_id
    )
    assert [(i["name"], i["text"]) for i in filled["items"] if i["ticked"]] == [
        ("", FEATHER),
        ("The Silent Hour", "No word is spoken from dusk until the first star."),
    ]
    # a statement is no input to the summary (rulings P18, P19): no prose
    dawn = await _send(
        plugin,
        "accept_fill",
        sphere_id=dawn_id,
        drawer_id=doctrines_id,
        items=filled["items"],
    )
    assert [i["name"] for i in _drawer(dawn, "Doctrines")["items"]] == [
        "Doctrine of Separation",
        "The Silent Hour",
        PURITY,
        FEATHER,
    ]
    assert world.prose().get(dawn_id, "description", None).text == DAWN_SUMMARY

    # 5. Vasha: the White Dawn is in her prompt's spheres block, its items
    # labelled; her tie rejects the purity doctrine by its label
    before = len(client.prompt_history)
    # the block labels the White Dawn's items in `spheres.items` order
    # (thing items, then statements): the purity statement is S5, as the
    # prompt shows (checked below)
    purity_label = "S5"
    vasha_reply = json.dumps(
        {
            "name": "Vasha",
            "age": 26,
            "facts": [
                {"category": "background", "text": "Carries letters for the Tsar."},
                {"category": "personality", "text": "Dry-humoured and quick."},
            ],
            "names": [],
            "ties": [
                {
                    "sphere": "The White Dawn",
                    "role": "practitioner",
                    "since": 1004,
                    "exceptions": [{"text": DOUBT, "rejects": purity_label}],
                }
            ],
        }
    )
    preview = await _send(
        plugin,
        "preview_thing",
        vasha_reply,
        VASHA_PROSE,
        VASHA_PROSE,
        kind="character",
        prompt=VASHA_PROMPT,
        fields={"heritage": owl_folk["id"]},
    )
    create_prompt = str(client.prompt_history[before]["prompt"])
    assert "Spheres in the world" in create_prompt
    assert f"- {purity_label} (Doctrines): {PURITY}" in create_prompt
    [tie] = preview["ties"]
    assert (tie["sphere_id"], tie["role"]) == (dawn_id, "practitioner")
    assert [e["text"] for e in tie["exceptions"]] == [DOUBT]
    vasha = await _send(plugin, "accept_preview", preview=preview)
    [tie] = vasha["ties"]
    assert (tie["sphere_id"], tie["role"]) == (dawn_id, "practitioner")
    assert tie["since"]["label"].startswith("1004")
    [exception] = tie["exceptions"]
    assert _text(exception["segments"]).startswith(DOUBT)
    # the White Dawn's people drawer is built from the tie
    dawn = await _thing(plugin, dawn_id)
    assert [p["name"] for p in dawn["sphere"]["people"]] == ["Vasha"]

    # 6. a scene with Vasha at the Pale Spire, a holy site: the stub is
    # previewed at planning and filled at start, staying a holy site
    plan = await _send(
        plugin,
        "plan_scene",
        SETUP_REPLY,
        SPIRE_PREVIEW,
        SPIRE_PROSE,
        prompt="Vasha brings a letter to the Pale Spire",
        picks={"Vasha": vasha["id"], "the Pale Spire": spire_id},
        player=vasha["id"],
        start=WorldDate.of(1020).model_dump(),
    )
    setup = plan["setup"]
    assert setup["place"] == {"thing_id": spire_id, "local": None}
    started = await _send(plugin, "start_scene", setup=setup)
    scene_id = started["scene_id"]
    spire = await _thing(plugin, spire_id)
    assert spire["stub"] is None
    assert spire["part_of"]["sphere_id"] == dawn_id
    assert spire["part_of"]["drawer_title"] == "Holy Sites"

    record = world.scenes().get(scene_id)
    block = world_context_block(world, record, WorldDate.of(1020))
    assert block.count(SPHERES_LEAD) == 1
    assert block.count("The White Dawn (religion)") == 1
    # the council, named by the goal, is pulled in as lore: there in full,
    # and left out of the White Dawn's key facts
    assert block.index(f"Council of Elders\n- {COUNCIL_TEXT}") < block.index(
        SPHERES_LEAD
    )
    # the key facts, each once: summary, top items, latest timeline
    for line in (
        DAWN_SUMMARY,
        COUNCIL_TEXT,
        HELD_PURITY,
        SEPARATION,
        VIGIL,
        "In 994: Declared the Night of Feathers a purification.",
        "In 1001: Seated the Council of Elders in Kremova.",
    ):
        assert block.count(line) == 1, line
    # one block of at most 8 lines
    sphere_part = block[block.index(SPHERES_LEAD) : block.index("Who is here")]
    assert len(re.findall(r"^- ", sphere_part, re.M)) <= 8
    assert "[[thing:" not in block

    scene = await _load(world, scene_id, client)
    try:
        sheet = scene.get_character("Vasha")
        assert sheet.base_attributes["ties"].startswith(
            "Practitioner of the White Dawn (since 1004), but: "
        )
        assert "purer is nonsense" in sheet.base_attributes["ties"]
        before = len(client.prompt_history)
        with ActiveScene(scene):
            async with MockClientContext():
                _queue(TURN)
                await instance.get_agent("narrator").progress_story(
                    narrative_direction="Dawn breaks over the gallery."
                )
        calls = client.prompt_history[before:]
        assert [call["kind"] for call in calls] == ["narrate_512"]
        turn_prompt = str(calls[0]["prompt"])
        assert turn_prompt.count(DAWN_SUMMARY) == 1
        assert turn_prompt.count(HELD_PURITY) == 1
    finally:
        close_world_scene(scene)

    # the whole run's model calls: nothing for lookups, linking, stubs,
    # adoption, ties or the World block
    kinds = Counter(call["kind"] for call in client.prompt_history)
    assert kinds == {
        # species, Tsardom, council, Vasha and the Pale Spire's stub preview
        "creative_instruction_3072": 5,
        # the scene's plan; the White Dawn's core
        "creative_instruction_2048": 2,
        # the creates' prose (two sections for Vasha) and the Pale Spire's;
        # none for the White Dawn, whose summary is its core's
        "analyze": 6,
        # Fill
        "creative_instruction_1024": 1,
        # the one turn
        "narrate_512": 1,
    }


TSARDOM_SPHERE_COUNCIL_REPLY = json.dumps(
    {
        **json.loads(TSARDOM_REPLY),
        "names": [
            {"name": "Kremova", "kind": "place", "aka": []},
            {
                "name": "The White Dawn",
                "kind": "sphere",
                "template": "religion",
                "aka": [],
            },
            # guessed an order sphere ("council" maps to order)
            {"name": "Council of Elders", "kind": "sphere", "template": "council"},
        ],
    }
)
COUNCIL_CORE = json.dumps(
    {
        "name": "Council of Elders",
        "summary": COUNCIL_TEXT,
        "aka": [],
        "timeline": [],
        "drawers": [{"type": "structure", "title": "Seats"}],
        "items": [{"drawer": "Seats", "text": "Seven seats, one for each elder."}],
        "names": [],
    }
)
# the White Dawn's core, leaving the council out of its items
DAWN_CORE_WITHOUT_COUNCIL = json.dumps(
    {
        **json.loads(DAWN_CORE),
        "items": [
            item
            for item in json.loads(DAWN_CORE)["items"]
            if item.get("name") != "The Council of Elders"
        ],
    }
)


async def test_council_sphere_first_then_dawn_files_it(plugin, client):
    """Minor 5, end to end: the Tsardom's reply guesses the Council of
    Elders an order sphere; it's expanded first, as a sphere whose prompt
    names the White Dawn stub, so it's part of it (unsorted). The White
    Dawn's core then leaves it out of its items -- and it still lands in
    Hierarchy, a body of people filed in the structure drawer."""

    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Moscavia",
            "present_year": 1020,
        }
    )
    preview = await _send(
        plugin,
        "preview_thing",
        TSARDOM_SPHERE_COUNCIL_REPLY,
        TSARDOM_PROSE,
        kind="place",
        prompt="The Tsardom of Moscavia, a northern realm",
        fields={},
    )
    await _send(plugin, "accept_preview", preview=preview)
    stubs = await _stubs(plugin)
    assert stubs["Council of Elders"]["kind"] == "sphere"
    dawn_id = stubs["The White Dawn"]["id"]
    council_id = stubs["Council of Elders"]["id"]
    council = await _thing(plugin, council_id)
    assert council["sphere"]["template"] == "order"

    # the council first, as an order sphere: part of the White Dawn stub
    suggestion = await _send(plugin, "stub_suggestion", id=council_id)
    assert "White Dawn" in suggestion["prompt"]
    preview = await _send(
        plugin,
        "preview_sphere",
        COUNCIL_CORE,
        template="order",
        prompt=suggestion["prompt"],
        fields={},
        stub_id=council_id,
    )
    assert preview["part_of"] == {"sphere": dawn_id, "drawer": "unsorted"}
    council = await _send(plugin, "accept_sphere", preview=preview)
    assert council["part_of"]["drawer_title"] == "Unsorted"

    # the White Dawn, whose core never relists it: guessed into Hierarchy
    suggestion = await _send(plugin, "stub_suggestion", id=dawn_id)
    preview = await _send(
        plugin,
        "preview_sphere",
        DAWN_CORE_WITHOUT_COUNCIL,
        template="religion",
        prompt=suggestion["prompt"],
        fields={},
        stub_id=dawn_id,
    )
    hierarchy_id = next(
        d["id"] for d in preview["drawers"] if d["title"] == "Hierarchy"
    )
    assert preview["adopted"] == [{"thing_id": council_id, "drawer_id": hierarchy_id}]
    dawn = await _send(plugin, "accept_sphere", preview=preview)
    hierarchy = _drawer(dawn, "Hierarchy")["items"]
    assert hierarchy[0]["thing_id"] == council_id
    # a nested sphere reads as its summary
    assert _text(hierarchy[0]["segments"]) == COUNCIL_TEXT
    assert "Unsorted" not in [d["title"] for d in dawn["sphere"]["drawers"]]
