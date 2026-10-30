"""Curation end to end, with the mock model, through the real `worlds`
router, on filings and drafts (Filing, Task 6 fix round 1, ruling F17:
the non-sphere steps of the curation session, rewritten without
spheres). A fresh world (present year 1000):

1. **Owl-folk**, whose origin names the Tsardom of Moscavia; **the
   Tsardom**, expanded from its stub, names Moskov (filed in it) and its
   state church, the Church of the Eternal Light.
2. **The Church**, from its stub with the religion hint: a `belief`
   doctrine (held by the Church), and the Divine Right of the Tsar and the
   Cathedral, filed in it.
3. **The Divine Right**, expanded from its stub: its own facts stay on it,
   and its elsewhere facts land on Moskov, the Tsardom and a new stub for
   the Tsar's Army. The owner marks one of its own facts held by the
   Church.
4. **Runeweaving** from a prompt, filing Ashenmere and the First Codex in
   it; **Ashenmere**, expanded with the 947 rediscovery; **the Codex**,
   whose reply names "the Ashenmere Caves" (offered as the same as
   Ashenmere: the owner says yes) and "the Conclave" (left new).
5. **The Deep Galleries**, filed in Ashenmere: Ashenmere's fact naming
   them could move here, found by code, unticked; ticked, it moves (moved,
   not copied).
6. **A merge:** the Conclave into the Runeweavers' Conclave; the Codex's
   link follows. **"Is this X?"**: the Ashenmere Hollows has Ashenmere
   (with facts) as its top candidate, so the model's verdict is asked and
   shown; the owner says yes and the material goes onto Ashenmere.
7. **Runeweaving's timeline** gathers the 947 rediscovery once, through
   Ashenmere's filing in it.
8. **A scene** at the Cathedral, filed in the Church: the World block and
   the narrator's prompt tell the Church's doctrine and the Divine Right's
   held fact as what the Church holds, never as plain truth.

Only `MockClient` responses are queued; one client serves the router and
every agent. Prose refreshes the accepts schedule for other entries are
recorded, not run.
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
from talemate.world.filing import filings_of
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

PRESENT = 1000

# --- 1. owl-folk and the Tsardom ---------------------------------------------

SPECIES_REPLY = json.dumps(
    {
        "name": "Owl-folk",
        "lifespan": 70,
        "adult_age": 12,
        "facts": [
            {
                "category": "origin",
                "text": "In 994 every person in the Tsardom of Moscavia awoke "
                "as owl-folk.",
            },
            {"category": "physical", "text": "Owl-folk have wings in place of arms."},
        ],
        "names": [{"name": "Tsardom of Moscavia", "kind": "place", "aka": []}],
    }
)

TSARDOM_REPLY = json.dumps(
    {
        "name": "Tsardom of Moscavia",
        "tag": "nation",
        "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
        "facts": [
            {
                "category": "description",
                "text": "A northern realm of owl-folk ruled by a Tsar from Moskov.",
            },
            {"category": "law", "text": "Only owl-folk may hold land."},
            {
                "category": "general",
                "text": "The Church of the Eternal Light is the state church.",
            },
        ],
        "names": [
            {
                "name": "Moskov",
                "kind": "place",
                "tag": "capital",
                "in": "Tsardom of Moscavia",
            },
            {"name": "Church of the Eternal Light", "kind": "lore", "tag": "faith"},
        ],
    }
)

# --- 2. the Church --------------------------------------------------------------

DOCTRINE = "The Light speaks through the Tsar alone."
HELD_DOCTRINE = (
    "Church of the Eternal Light holds that the Light speaks through the Tsar alone."
)
CHURCH_REPLY = json.dumps(
    {
        "name": "Church of the Eternal Light",
        "tag": "faith",
        "facts": [
            {"category": "belief", "text": DOCTRINE},
            {
                "category": "general",
                "text": "It teaches the Divine Right of the Tsar.",
            },
            {
                "category": "general",
                "text": "Its seat is the Cathedral of the Eternal Light in Moskov.",
            },
        ],
        "names": [
            {
                "name": "Divine Right of the Tsar",
                "kind": "lore",
                "tag": "doctrine",
                "in": "Church of the Eternal Light",
            },
            {
                "name": "Cathedral of the Eternal Light",
                "kind": "place",
                "tag": "cathedral",
                "in": "Church of the Eternal Light",
            },
        ],
    }
)

# --- 3. the Divine Right, its facts sent elsewhere ------------------------------

RIGHT_OWN = "The Divine Right holds that the Tsar is the Light's steward on earth."
RIGHT_HELD = "The Light crowned the first Tsar with a ray of dawn."
TO_MOSKOV = "Moskov's onion domes are gilded so the Light can find the Tsar."
ARMY = "The Tsar's Army"
TO_ARMY = "The Tsar's Army swears its oath to the Tsar and the Light."
TO_TSARDOM = "The Zakonnik makes doubting the Tsar's right a crime."
RIGHT_REPLY = json.dumps(
    {
        "name": "Divine Right of the Tsar",
        "facts": [
            {"category": "general", "text": RIGHT_OWN},
            {"category": "general", "text": RIGHT_HELD},
        ],
        "names": [],
        "elsewhere": [
            {"entry": "Moskov", "text": TO_MOSKOV, "held_by": None},
            {"entry": ARMY, "text": TO_ARMY, "held_by": None},
            {"entry": "Tsardom of Moscavia", "text": TO_TSARDOM, "held_by": None},
        ],
    }
)
HELD_CROWNING = (
    "Church of the Eternal Light holds that the Light crowned the first Tsar "
    "with a ray of dawn."
)

# --- 4. Runeweaving, Ashenmere and the Codex -----------------------------------

RUNEWEAVING_REPLY = json.dumps(
    {
        "name": "Runeweaving",
        "tag": "field",
        "facts": [
            {
                "category": "general",
                "text": "Runeweaving is the art of carving runes that change "
                "what a material is.",
            },
            {
                "category": "general",
                "text": "The First Codex of Aelberth was compiled.",
                "since": 217,
            },
            {
                "category": "general",
                "text": "The Runeweavers' Conclave was founded.",
                "since": 642,
            },
            {"category": "general", "text": "Its oldest runes are in Ashenmere."},
        ],
        "names": [
            {"name": "Ashenmere", "kind": "place", "tag": "caves", "in": "Runeweaving"},
            {
                "name": "First Codex of Aelberth",
                "kind": "item",
                "tag": "codex",
                "in": "Runeweaving",
            },
            {"name": "Runeweavers' Conclave", "kind": "lore", "tag": "order"},
        ],
    }
)

REDISCOVERY = (
    "A party of Runeweavers rediscovered the Ashenmere rune dialect in its "
    "deepest gallery."
)
GALLERIES_FACT = (
    "The Deep Galleries of Ashenmere hold inscriptions no lamp has lit in "
    "two thousand years."
)
ASHENMERE_REPLY = json.dumps(
    {
        "name": "Ashenmere",
        "facts": [
            {
                "category": "description",
                "text": "Ashenmere is a maze of pale limestone caves under the "
                "Greymarch Mountains.",
            },
            {"category": "history", "text": REDISCOVERY, "since": 947},
            {"category": "general", "text": GALLERIES_FACT},
        ],
        "names": [],
        "elsewhere": [],
    }
)

CODEX_REPLY = json.dumps(
    {
        "name": "First Codex of Aelberth",
        "facts": [
            {
                "category": "general",
                "text": "The Codex standardizes twenty-four foundational runes.",
            },
            {
                "category": "general",
                "text": "Its oldest copy was found in the Ashenmere Caves.",
            },
            {
                "category": "general",
                "text": "The Conclave keeps every copy under lock.",
            },
        ],
        "names": [
            {"name": "Ashenmere Caves", "kind": "place", "aka": []},
            {"name": "The Conclave", "kind": "lore", "aka": []},
        ],
        "elsewhere": [],
    }
)

# --- 5. the Deep Galleries: a fact moves here ------------------------------------

GALLERIES_REPLY = json.dumps(
    {
        "name": "The Deep Galleries",
        "facts": [
            {
                "category": "description",
                "text": "The Deep Galleries are the lowest chambers of the "
                "caves, reached by rope.",
            }
        ],
        "names": [],
        "elsewhere": [],
    }
)

# --- 6. "Is this X?" with the model's verdict ---------------------------------

HOLLOWS_FACT = "Bats roost in the Hollows by the thousand."
HOLLOWS_REPLY = json.dumps(
    {
        "name": "The Ashenmere Hollows",
        "facts": [{"category": "description", "text": HOLLOWS_FACT}],
        "names": [],
        "elsewhere": [],
    }
)
HOLLOWS_WHY = "Both are the pale caves under the Greymarch."
VERDICT_REPLY = json.dumps({"verdict": "same", "why": HOLLOWS_WHY})

# --- 8. the scene ---------------------------------------------------------------

SETUP_REPLY = json.dumps(
    {
        "player": "Vasha",
        "characters": [
            {
                "name": "Vasha",
                "facts": ["A courier who carries the Patriarch's letters."],
                "heritage": "Owl-folk",
            },
            {
                "name": "Father Ilya",
                "facts": ["A priest of the Cathedral."],
                "heritage": "Owl-folk",
            },
        ],
        "place": {"name": "Cathedral of the Eternal Light", "world": True},
        "goal": "Hear the Patriarch's sermon on the Divine Right of the Tsar.",
        "intro": "Candles burn in the Cathedral as Vasha slips inside.",
    }
)
CATHEDRAL_PREVIEW = json.dumps(
    {
        "name": "Cathedral of the Eternal Light",
        "facts": [{"category": "description", "text": "Its domes are gilded."}],
        "names": [],
    }
)
TURN = "Father Ilya lifts a candle and speaks of the Tsar's right."


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

    mock = MockClient("curation")
    bootstrap_scene(MockScene())
    for agent in instance.AGENTS.values():
        agent.client = mock
    return mock


@pytest.fixture
def plugin(tmp_path, client, monkeypatch):
    plug = WorldsPlugin(_Handler())
    plug.worlds_root = tmp_path
    # the prose refreshes accepts schedule for other entries: recorded
    plug.scheduled_prose = []
    monkeypatch.setattr(
        plug,
        "_schedule_prose",
        lambda thing_id, at, **kw: plug.scheduled_prose.append(thing_id),
    )
    yield plug
    plug.disconnect()


@pytest.fixture
def loadable(monkeypatch):
    """What planning (the index) and loading a world scene need from a
    test, as in the spheres end-to-end test."""

    embedding = TrigramEmbeddingFunction()
    monkeypatch.setattr(
        MockMemoryAgent, "embedding_function", property(lambda self: embedding)
    )
    monkeypatch.setattr(MockMemoryAgent, "set_db", _noop)
    monkeypatch.setattr(MockMemoryAgent, "_get_document", lambda self, id: {})
    monkeypatch.setattr(Scene, "commit_to_memory", _noop)
    monkeypatch.setattr(Config, "set_dirty", _noop)
    monkeypatch.setattr(get_config(), "recent_scenes", RecentScenes(scenes=[]))


def _errors(plugin) -> list[dict]:
    return [
        m
        for m in plugin.websocket_handler.messages
        if m.get("type") == "worlds"
        and (m.get("action") or "").endswith("failed")
        or (m.get("action") == "operation_done" and m.get("error"))
    ]


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

    seen = len(plugin.websocket_handler.messages)
    async with MockClientContext():
        _queue(*responses)
        await plugin.handle({"type": "worlds", "action": action, **data})
        await _drain(plugin)
    new = plugin.websocket_handler.messages[seen:]
    assert not [m for m in new if m in _errors(plugin)], new
    return _last(plugin, action)


async def _draft(plugin, action: str, *responses: str, **data) -> dict:
    """A draft's data to accept (`preview_thing` answers the draft page,
    Filing Task 6)."""

    return (await _send(plugin, action, *responses, **data))["preview"]


async def _stubs(plugin) -> dict[str, dict]:
    listed = await _send(plugin, "list_stubs", include_ignored=True)
    return {stub["name"]: stub for stub in listed["stubs"]}


async def _thing(plugin, thing_id: str) -> dict:
    return await _send(plugin, "get_thing", id=thing_id, at=None)


def _text(segments: list[dict]) -> str:
    return "".join(s["text"] for s in segments)


def _facts(thing: dict) -> list[str]:
    return [_text(f["segments"]) for f in thing["facts"]]


async def _expand(plugin, stub_id: str, kind: str, *responses: str, **extra):
    """A stub's draft from its suggested prompt (`preview_thing`): the data
    to accept (the draft page's `preview`)."""

    suggestion = await _send(plugin, "stub_suggestion", id=stub_id)
    return await _draft(
        plugin,
        "preview_thing",
        *responses,
        kind=kind,
        prompt=suggestion["prompt"],
        fields={},
        stub_id=stub_id,
        **extra,
    )


async def _load(world, scene_id: str, client: MockClient) -> Scene:
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
async def test_curation_end_to_end(plugin, client, loadable):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Moscavia",
            "present_year": PRESENT,
        }
    )
    world = plugin.world

    # 1. owl-folk, then the Tsardom from its stub, naming Moskov (filed in
    # it) and its church
    preview = await _draft(
        plugin,
        "preview_thing",
        SPECIES_REPLY,
        kind="species",
        prompt="Owl-folk: owl people. Everyone in the Tsardom of Moscavia "
        "became this race suddenly one day.",
        fields={},
    )
    await _send(plugin, "accept_preview", preview=preview)
    tsardom_id = (await _stubs(plugin))["Tsardom of Moscavia"]["id"]
    preview = await _expand(plugin, tsardom_id, "place", TSARDOM_REPLY)
    tsardom = await _send(plugin, "accept_preview", preview=preview)
    assert tsardom["id"] == tsardom_id and tsardom["stub"] is None
    stubs = await _stubs(plugin)
    moskov_id = stubs["Moskov"]["id"]
    church_id = stubs["Church of the Eternal Light"]["id"]
    assert [r["id"] for g in tsardom["connected"] for r in g["rows"]] == [moskov_id]

    # 2. the Church, from its stub with the religion hint: its doctrine is
    # a belief (held by it); the Divine Right and the Cathedral filed in it
    preview = await _expand(plugin, church_id, "lore", CHURCH_REPLY, hint="religion")
    church = await _send(plugin, "accept_preview", preview=preview)
    assert church["hint"] == "religion"
    doctrine = next(f for f in church["facts"] if f["text"] == DOCTRINE)
    assert doctrine["held_by"] == {
        "id": church_id,
        "name": "Church of the Eternal Light",
    }
    stubs = await _stubs(plugin)
    right_id = stubs["Divine Right of the Tsar"]["id"]
    cathedral_id = stubs["Cathedral of the Eternal Light"]["id"]
    assert {r["id"] for g in church["connected"] for r in g["rows"]} == {
        right_id,
        cathedral_id,
    }

    # 3. the Divine Right: its own facts stay, the rest goes elsewhere
    preview = await _expand(plugin, right_id, "lore", RIGHT_REPLY)
    assert [f["text"] for f in preview["facts"]] == [RIGHT_OWN, RIGHT_HELD]
    # the army is no entry yet: its fact goes onto a new stub
    assert {(e["target_id"], e["text"], e["ticked"]) for e in preview["elsewhere"]} == {
        (moskov_id, TO_MOSKOV, True),
        (None, TO_ARMY, True),
        (tsardom_id, TO_TSARDOM, True),
    }
    right = await _send(plugin, "accept_preview", preview=preview, into_stub=right_id)
    army_id = (await _stubs(plugin))[ARMY]["id"]
    assert sorted(_facts(right)) == sorted([RIGHT_OWN, RIGHT_HELD])
    for target_id, text in (
        (moskov_id, TO_MOSKOV),
        (army_id, TO_ARMY),
        (tsardom_id, TO_TSARDOM),
    ):
        assert text in _facts(await _thing(plugin, target_id)), target_id
    # the owner marks the crowning legend held by the Church
    held = next(f for f in right["facts"] if _text(f["segments"]) == RIGHT_HELD)
    right = await _send(
        plugin,
        "set_held_by",
        thing_id=right_id,
        fact_id=held["fact_id"],
        holder_id=church_id,
    )
    [held] = [f for f in right["facts"] if f["fact_id"] == held["fact_id"]]
    assert held["held_by"]["id"] == church_id

    # 4. Runeweaving from a prompt, filing Ashenmere and the Codex in it;
    # Ashenmere, expanded from its stub, with the 947 rediscovery
    preview = await _draft(
        plugin,
        "preview_thing",
        RUNEWEAVING_REPLY,
        kind="lore",
        prompt="Runeweaving: runic magic, carved into stone and steel.",
        fields={},
        hint="field",
    )
    runeweaving = await _send(plugin, "accept_preview", preview=preview)
    runeweaving_id = runeweaving["id"]
    stubs = await _stubs(plugin)
    ashenmere_id = stubs["Ashenmere"]["id"]
    codex_id = stubs["First Codex of Aelberth"]["id"]
    conclave_id = stubs["Runeweavers' Conclave"]["id"]
    preview = await _expand(plugin, ashenmere_id, "place", ASHENMERE_REPLY)
    ashenmere = await _send(
        plugin, "accept_preview", preview=preview, into_stub=ashenmere_id
    )
    [rediscovery] = [
        f for f in ashenmere["facts"] if _text(f["segments"]) == REDISCOVERY
    ]
    assert [row["target_id"] for row in ashenmere["in"]] == [runeweaving_id]

    # the Codex: the Caves are Ashenmere (the owner says so); the Conclave
    # is left new, a duplicate for the merge below
    preview = await _expand(plugin, codex_id, "item", CODEX_REPLY)
    rows = {n["name"]: n for n in preview["new_names"]}
    caves, conclave_row = rows["Ashenmere Caves"], rows["The Conclave"]
    assert [o["thing_id"] for o in caves["same_as"]] == [ashenmere_id]
    assert conclave_id in [o["thing_id"] for o in conclave_row["same_as"]]
    assert caves["same_target_id"] is None  # the default is "new"
    caves["same_target_id"] = ashenmere_id
    codex = await _send(plugin, "accept_preview", preview=preview, into_stub=codex_id)
    stubs = await _stubs(plugin)
    assert "Ashenmere Caves" not in stubs
    the_conclave_id = stubs["The Conclave"]["id"]
    links = {
        s["text"]: s["ref"] for f in codex["facts"] for s in f["segments"] if s["ref"]
    }
    assert links["Ashenmere Caves"] == ashenmere_id
    assert links["The Conclave"] == the_conclave_id

    # 5. the Deep Galleries, filed in Ashenmere (the owner's pick, ticked):
    # Ashenmere's fact naming them could move here, found by code and
    # unticked; the owner ticks it and it moves, never copied
    preview = await _draft(
        plugin,
        "preview_thing",
        GALLERIES_REPLY,
        kind="place",
        prompt="The Deep Galleries, the lowest chambers of Ashenmere",
        fields={"filings": [{"target": ashenmere_id}]},
        picks={"Ashenmere": ashenmere_id},
    )
    assert [(f["target_id"], f["ticked"]) for f in preview["filings"]] == [
        (ashenmere_id, True)
    ]
    assert [
        (row["text"], row["from_id"], row["from_name"], row["ticked"])
        for row in preview["move_here"]
    ] == [(GALLERIES_FACT, ashenmere_id, "Ashenmere", False)]
    preview["move_here"][0]["ticked"] = True
    galleries = await _send(plugin, "accept_preview", preview=preview)
    assert GALLERIES_FACT in _facts(galleries)
    ashenmere = await _thing(plugin, ashenmere_id)
    assert GALLERIES_FACT not in _facts(ashenmere)
    assert [f.target for f in filings_of(world.view(), galleries["id"])] == [
        ashenmere_id
    ]

    # 6. merge the Conclave into the Runeweavers' Conclave: the link follows
    merge = await _send(
        plugin, "preview_merge", from_id=the_conclave_id, into_id=conclave_id
    )
    merged = await _send(
        plugin,
        "accept_merge",
        preview=merge["preview"],
        main_name="Runeweavers' Conclave",
    )
    assert merged["into"]["id"] == conclave_id
    assert world.view().thing(the_conclave_id) is None
    codex = await _thing(plugin, codex_id)
    links = {
        s["text"]: s["ref"] for f in codex["facts"] for s in f["segments"] if s["ref"]
    }
    assert links["The Conclave"] == conclave_id

    # "Is this X?": the Ashenmere Hollows' top candidate, Ashenmere, has
    # facts, and so does the draft: the model's verdict is asked once,
    # after the draft's own calls, and shown as a hint -- the owner says
    # yes, so the material goes onto Ashenmere and nothing new is made
    before = len(client.prompt_history)
    preview = await _draft(
        plugin,
        "preview_thing",
        HOLLOWS_REPLY,
        VERDICT_REPLY,
        kind="place",
        prompt="The Ashenmere Hollows, pale caves under the Greymarch",
        fields={},
    )
    assert [c["kind"] for c in client.prompt_history[before:]] == [
        "creative_instruction_3072",
        "analyze",
    ]
    verdict_call = client.prompt_history[-1]["prompt"]
    assert verdict_call.uid == "world.same-thing"
    assert "Ashenmere" in str(verdict_call)
    assert preview["same_as"][0]["thing_id"] == ashenmere_id
    assert preview["verdict"] == {
        ashenmere_id: {"verdict": "same", "why": HOLLOWS_WHY, "confidence": None}
    }
    hollows = await _send(
        plugin, "accept_preview", preview=preview, same_target_id=ashenmere_id
    )
    assert hollows["id"] == ashenmere_id
    assert HOLLOWS_FACT in _facts(hollows)
    assert "The Ashenmere Hollows" in [a["name"] for a in hollows["aka"]]
    assert not [
        t
        for t in world.view().things()
        if world.view().name_of(t.id) == "The Ashenmere Hollows"
    ]

    # 7. Runeweaving's timeline gathers the 947 rediscovery, once, through
    # Ashenmere's filing in it, beside its own dated facts
    runeweaving = await _thing(plugin, runeweaving_id)
    lines = runeweaving["entry_timeline"]
    assert [(line["date"]["label"], line["owner_id"]) for line in lines] == [
        ("217", runeweaving_id),
        ("642", runeweaving_id),
        ("947", ashenmere_id),
    ]
    assert lines[2]["fact_id"] == rediscovery["fact_id"]
    assert _text(lines[2]["segments"]) == REDISCOVERY
    assert not any(line["disagrees_with"] for line in lines)

    # 8. a scene at the Cathedral, filed in the Church: its doctrine and
    # the Divine Right's held fact are told as what the Church holds
    plan = await _send(
        plugin,
        "plan_scene",
        SETUP_REPLY,
        CATHEDRAL_PREVIEW,
        prompt="Vasha hears the Patriarch preach on the Divine Right of the Tsar",
        picks={"the Divine Right of the Tsar": right_id},
        start=WorldDate.of(PRESENT).model_dump(),
    )
    setup = plan["setup"]
    assert setup["place"] == {"thing_id": cathedral_id, "local": None}
    started = await _send(plugin, "start_scene", setup=setup)
    record = world.scenes().get(started["scene_id"])
    block = world_context_block(world, record, WorldDate.of(PRESENT))
    held_lines = (HELD_DOCTRINE, HELD_CROWNING)
    for line in held_lines:
        assert block.count(line) == 1, (line, block)
    # never told as plain truth
    assert block.count(DOCTRINE) == 0
    assert block.count(RIGHT_HELD) == 0
    assert "[[thing:" not in block

    scene = await _load(world, started["scene_id"], client)
    try:
        before = len(client.prompt_history)
        with ActiveScene(scene):
            async with MockClientContext():
                _queue(TURN)
                await instance.get_agent("narrator").progress_story(
                    narrative_direction="The Patriarch begins his sermon."
                )
        calls = client.prompt_history[before:]
        assert [call["kind"] for call in calls] == ["narrate_512"]
        turn_prompt = str(calls[0]["prompt"])
        for line in held_lines:
            assert turn_prompt.count(line) == 1, line
        assert turn_prompt.count(DOCTRINE) == 0
    finally:
        close_world_scene(scene)

    # the run's model calls: nothing for the same-thing offers, "Could move
    # here", the merge or timelines
    kinds = Counter(call["kind"] for call in client.prompt_history)
    assert kinds == KINDS_ASKED, kinds


# species, the Tsardom, the Church, the Divine Right, Runeweaving,
# Ashenmere, the Codex, the Galleries, the Hollows and the Cathedral's stub
# preview at planning (a draft writes no prose); the Hollows' verdict; the
# plan; the narrator's turn
KINDS_ASKED = {
    "creative_instruction_3072": 10,
    "creative_instruction_2048": 1,
    "analyze": 1,
    "narrate_512": 1,
}
