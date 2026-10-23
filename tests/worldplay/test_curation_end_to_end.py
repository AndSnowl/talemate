"""Curation end to end, with the mock model, through the real `worlds`
router: the owner's session from the curation spec ("How the owner will
judge it"), in a fresh world (present year 1000).

1. **Owl-folk**, whose origin names the Tsardom of Moscavia; then **the
   Tsardom**, a nation sphere made from its stub. Its core files the White
   Talon and the Frosted Wing in Military, Moskov in Lands, and names its
   state church, the Church of the Eternal Light, as a religion stub.
2. **The White Talon**, expanded from its stub: its facts say "regiments
   such as the White Talon". The owner names the outer body, the Tsar's
   Army (an order filed in the Tsardom's Military, `add_outer_body`), and
   ticks the Frosted Wing's re-file row: on accept the army is a stub in
   Military, and both regiments are inside it.
3. **The Church**, a religion sphere from its stub: a Doctrines statement
   and the Divine Right of the Tsar, a doctrine item.
4. **The Divine Right**, expanded from its stub: its own facts stay on it,
   and its elsewhere items land on Moskov, the army and the Tsardom (a
   law). The owner marks one of its own facts held by the Church.
5. **Runeweaving**, a field sphere, made from a prompt; **Ashenmere**, its
   site, expanded with the 947 rediscovery; **the First Codex**, whose
   reply names "the Ashenmere Caves" (offered as the same as Ashenmere:
   the owner says yes, so no second entry is made) and "the Conclave"
   (offered as the same as Runeweavers' Conclave: left new).
6. **The Deep Galleries**, a place inside Ashenmere: the fact about them
   moves in from Ashenmere (moved, not copied).
7. **A merge:** the Conclave into Runeweavers' Conclave; the Codex's link
   follows.
8. **Runeweaving's timeline** gathers the 947 rediscovery from Ashenmere,
   once, beside its own dated facts.
9. **A scene** at the Cathedral of the Eternal Light, a holy site of the
   Church: the World block and the narrator's prompt tell the Church's
   doctrine and the Divine Right's held fact as what the Church holds,
   never as plain truth.

Only `MockClient` responses are queued; one client serves the router and
every agent. Prose refreshes the accepts schedule for other entries are
recorded, not run (the router tests' `_record_prose`).
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
SPECIES_PROSE = "The Owl-folk are winged."

TSARDOM_SUMMARY = (
    "The Tsardom of Moscavia is a northern realm of owl-folk ruled by a Tsar "
    "from Moskov."
)
TALON_LINE = "An elite regiment of snowy owl-folk."
TSARDOM_CORE = json.dumps(
    {
        "name": "Tsardom of Moscavia",
        "summary": TSARDOM_SUMMARY,
        "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
        "timeline": [
            {"year": 994, "text": "Every Moscavian awoke as owl-folk."},
        ],
        "drawers": [
            {"type": "beliefs", "title": "Laws"},
            {"type": "structure", "title": "Military"},
            {"type": "places", "title": "Lands"},
        ],
        "items": [
            {"drawer": "Laws", "text": "Only owl-folk may hold land."},
            {
                "drawer": "Military",
                "name": "White Talon",
                "text": TALON_LINE,
                "kind": "lore",
            },
            {
                "drawer": "Military",
                "name": "Frosted Wing",
                "text": "A regiment of eared owl-folk scouts.",
                "kind": "lore",
            },
            {
                "drawer": "Lands",
                "name": "Moskov",
                "text": "The capital, where the Moskva meets the Volga.",
                "kind": "place",
            },
            {
                "drawer": "Laws",
                "text": "The Church of the Eternal Light is the state church.",
            },
        ],
        "names": [
            {
                "name": "Church of the Eternal Light",
                "kind": "sphere",
                "template": "religion",
                "aka": [],
            }
        ],
    }
)

# --- 2. the White Talon and its army ------------------------------------------

TALON_OWN = "The White Talon recruits only pure-line snowy owl-folk of proven courage."
TALON_REPLY = json.dumps(
    {
        "name": "White Talon",
        "facts": [
            {
                "category": "general",
                "text": "The Tsardom fields regiments such as the White Talon "
                "and the Frosted Wing.",
            },
            {"category": "general", "text": TALON_OWN},
            {
                "category": "general",
                "text": "Its insignia is a white talon clutching a golden sword.",
            },
        ],
        "names": [{"name": "Frosted Wing", "kind": "lore", "aka": []}],
        "elsewhere": [],
    }
)
TALON_PROSE = "An elite regiment."
ARMY = "The Tsar's Army"

# --- 3. the Church --------------------------------------------------------------

CHURCH_SUMMARY = (
    "The Church of the Eternal Light is the state church of Moscavia, which "
    "teaches that the Light chose the Tsar."
)
DOCTRINE = "The Light speaks through the Tsar alone."
# as a scene tells them: a Doctrines statement of a religion is held by
# it, and so is the Divine Right's fact the owner marked
HELD_DOCTRINE = (
    "Church of the Eternal Light holds that the Light speaks through the Tsar alone."
)
RIGHT_LINE = "The Tsar rules as the Light's steward."
CATHEDRAL_LINE = "The Patriarch's seat in Moskov, lit by ten thousand candles."
CHURCH_CORE = json.dumps(
    {
        "name": "Church of the Eternal Light",
        "summary": CHURCH_SUMMARY,
        "aka": [],
        "timeline": [{"year": 412, "text": "Founded by the first Tsar."}],
        "drawers": [
            {"type": "beliefs", "title": "Doctrines"},
            {"type": "practices", "title": "Rites"},
            {"type": "places", "title": "Holy Sites"},
        ],
        "items": [
            {"drawer": "Doctrines", "text": DOCTRINE},
            {
                "drawer": "Doctrines",
                "name": "The Divine Right of the Tsar",
                "text": RIGHT_LINE,
                "kind": "lore",
            },
            {
                "drawer": "Rites",
                "name": "Baptism by Candlelight",
                "text": "Young owls enter the Church in candlelit water.",
                "kind": "rite",
            },
            {
                "drawer": "Holy Sites",
                "name": "The Cathedral of the Eternal Light",
                "text": CATHEDRAL_LINE,
                "kind": "place",
            },
        ],
        "names": [{"name": "Moskov", "kind": "place", "aka": []}],
    }
)

# --- 4. the Divine Right, its facts sent elsewhere ------------------------------

RIGHT_OWN = "The Divine Right holds that the Tsar is the Light's steward on earth."
RIGHT_HELD = "The Light crowned the first Tsar with a ray of dawn."
TO_MOSKOV = "Moskov's onion domes are gilded so the Light can find the Tsar."
TO_ARMY = "The Tsar's Army swears its oath to the Tsar and the Light."
TO_TSARDOM = "The Zakonnik makes doubting the Tsar's right a crime."
RIGHT_REPLY = json.dumps(
    {
        "name": "The Divine Right of the Tsar",
        "facts": [
            {"category": "general", "text": RIGHT_OWN},
            {"category": "general", "text": RIGHT_HELD},
        ],
        "names": [{"name": "Moskov", "kind": "place", "aka": []}],
        "elsewhere": [
            {"entry": "Moskov", "text": TO_MOSKOV, "held_by": None},
            {"entry": ARMY, "text": TO_ARMY, "held_by": None},
            {"entry": "Tsardom of Moscavia", "text": TO_TSARDOM, "held_by": None},
        ],
        "move_in": [],
    }
)
HELD_CROWNING = (
    "Church of the Eternal Light holds that the Light crowned the first Tsar "
    "with a ray of dawn."
)
RIGHT_PROSE = "A doctrine of the Tsar's rule."

# --- 5. Runeweaving, Ashenmere and the Codex -----------------------------------

RUNEWEAVING_CORE = json.dumps(
    {
        "name": "Runeweaving",
        "summary": "Runeweaving is the art of carving runes that change what "
        "a material is.",
        "aka": [],
        "timeline": [
            {"year": 217, "text": "The First Codex of Aelberth is compiled."},
            {"year": 642, "text": "Runeweavers' Conclave founded in Stonehold."},
        ],
        "drawers": [
            {"type": "practices", "title": "Techniques"},
            {"type": "places", "title": "Sites"},
            {"type": "beliefs", "title": "Texts"},
        ],
        "items": [
            {
                "drawer": "Techniques",
                "name": "Deepcarving",
                "text": "Runes cut deep below the surface last for centuries.",
                "kind": "lore",
            },
            {
                "drawer": "Sites",
                "name": "Ashenmere",
                "text": "Caves holding the oldest runes.",
                "kind": "place",
            },
            {
                "drawer": "Texts",
                "name": "First Codex of Aelberth",
                "text": "The founding text of the art.",
                "kind": "item",
            },
        ],
        "names": [
            {
                "name": "Runeweavers' Conclave",
                "kind": "sphere",
                "template": "order",
                "aka": [],
            },
            {"name": "Stonehold", "kind": "place", "aka": []},
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
        "move_in": [],
    }
)
ASHENMERE_PROSE = "Pale caves."

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
            {"name": "The Conclave", "kind": "sphere", "template": "order", "aka": []},
        ],
        "elsewhere": [],
        "move_in": [],
    }
)
CODEX_PROSE = "The founding text."

# --- 6. the Deep Galleries: a fact moves in -------------------------------------

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
        # Ashenmere's facts, in the order written: M1 its drawer line, M2
        # its description, M3 the 947 rediscovery, M4 the galleries'
        # inscriptions (the prompt is checked below)
        "move_in": ["M4"],
    }
)
GALLERIES_PROSE = "Deep chambers."

# --- 9. the scene ---------------------------------------------------------------

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
        "place": {"name": "The Cathedral of the Eternal Light", "world": True},
        "goal": "Hear the Patriarch's sermon on the Divine Right of the Tsar.",
        "intro": "Candles burn in the Cathedral as Vasha slips inside.",
    }
)
CATHEDRAL_PREVIEW = json.dumps(
    {
        "name": "The Cathedral of the Eternal Light",
        "facts": [{"category": "description", "text": "Its domes are gilded."}],
        "names": [],
    }
)
CATHEDRAL_PROSE = "A candlelit cathedral."
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


async def _stubs(plugin) -> dict[str, dict]:
    listed = await _send(plugin, "list_stubs", include_ignored=True)
    return {stub["name"]: stub for stub in listed["stubs"]}


async def _thing(plugin, thing_id: str) -> dict:
    return await _send(plugin, "get_thing", id=thing_id, at=None)


def _text(segments: list[dict]) -> str:
    return "".join(s["text"] for s in segments)


def _facts(thing: dict) -> list[str]:
    return [_text(f["segments"]) for f in thing["facts"]]


def _drawer(sphere: dict, title: str) -> dict:
    return next(d for d in sphere["sphere"]["drawers"] if d["title"] == title)


def _item_id(sphere: dict, title: str, name: str) -> str:
    return next(
        i["thing_id"] for i in _drawer(sphere, title)["items"] if i["name"] == name
    )


async def _expand(plugin, stub_id: str, kind: str, *responses: str, **extra):
    """A stub's preview from its suggested prompt (`preview_thing`)."""

    suggestion = await _send(plugin, "stub_suggestion", id=stub_id)
    return await _send(
        plugin,
        "preview_thing",
        *responses,
        kind=kind,
        prompt=suggestion["prompt"],
        fields={},
        stub_id=stub_id,
        **extra,
    )


async def _expand_sphere(plugin, stub_id: str, template: str, *responses: str):
    suggestion = await _send(plugin, "stub_suggestion", id=stub_id)
    preview = await _send(
        plugin,
        "preview_sphere",
        *responses,
        template=template,
        prompt=suggestion["prompt"],
        fields={},
        stub_id=stub_id,
    )
    return await _send(plugin, "accept_sphere", preview=preview)


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

    # 1. owl-folk, then the Tsardom from its stub, as a nation sphere
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
    await _send(plugin, "accept_preview", preview=preview)
    tsardom_id = (await _stubs(plugin))["Tsardom of Moscavia"]["id"]
    tsardom = await _expand_sphere(plugin, tsardom_id, "nation", TSARDOM_CORE)
    assert tsardom["id"] == tsardom_id and tsardom["stub"] is None
    military = _drawer(tsardom, "Military")
    assert [i["name"] for i in military["items"]] == ["White Talon", "Frosted Wing"]
    talon_id = _item_id(tsardom, "Military", "White Talon")
    wing_id = _item_id(tsardom, "Military", "Frosted Wing")
    moskov_id = _item_id(tsardom, "Lands", "Moskov")
    church_id = (await _stubs(plugin))["Church of the Eternal Light"]["id"]

    # 2. the White Talon from its stub; the owner names the army around it
    preview = await _expand(plugin, talon_id, "lore", TALON_REPLY, TALON_PROSE)
    # the owner names the army around it, filed in the Tsardom's Military;
    # the Frosted Wing, filed there too, gets an unticked re-file row
    before = len(client.prompt_history)
    framed = await _send(
        plugin,
        "add_outer_body",
        preview_type="create",
        preview=preview,
        row_name="White Talon",
        outer={
            "name": ARMY,
            "template": "order",
            "part_of": {"sphere": tsardom_id, "drawer": military["id"]},
        },
    )
    assert client.prompt_history[before:] == []
    preview = framed["preview"]
    assert preview["part_of"] == {"name": ARMY, "drawer": "unsorted"}
    [army_row] = [n for n in preview["new_names"] if n["name"] == ARMY]
    assert (army_row["kind"], army_row["template"]) == ("sphere", "order")
    assert army_row["part_of"] == {"sphere": tsardom_id, "drawer": military["id"]}
    [refile] = preview["refile"]
    assert (refile["thing_id"], refile["ticked"]) == (wing_id, False)
    refile["ticked"] = True
    talon = await _send(plugin, "accept_preview", preview=preview, into_stub=talon_id)
    army_id = (await _stubs(plugin))[ARMY]["id"]
    assert talon["part_of"]["sphere_id"] == army_id
    army = await _thing(plugin, army_id)
    assert army["part_of"]["sphere_id"] == tsardom_id
    assert army["part_of"]["drawer_title"] == "Military"
    assert sorted(
        i["thing_id"] for d in army["sphere"]["drawers"] for i in d["items"]
    ) == sorted([talon_id, wing_id])
    tsardom = await _thing(plugin, tsardom_id)
    assert [i["thing_id"] for i in _drawer(tsardom, "Military")["items"]] == [army_id]

    # 3. the Church, from the Tsardom's stub, as a religion
    church = await _expand_sphere(plugin, church_id, "religion", CHURCH_CORE)
    right_id = _item_id(church, "Doctrines", "The Divine Right of the Tsar")
    cathedral_id = _item_id(church, "Holy Sites", "The Cathedral of the Eternal Light")

    # 4. the Divine Right: its own facts stay, the rest goes elsewhere
    preview = await _expand(plugin, right_id, "lore", RIGHT_REPLY, RIGHT_PROSE)
    assert [f["text"] for f in preview["facts"]] == [RIGHT_OWN, RIGHT_HELD]
    assert {(e["target_id"], e["text"], e["ticked"]) for e in preview["elsewhere"]} == {
        (moskov_id, TO_MOSKOV, True),
        (army_id, TO_ARMY, True),
        (tsardom_id, TO_TSARDOM, True),
    }
    right = await _send(plugin, "accept_preview", preview=preview, into_stub=right_id)
    # its drawer line, and its own two
    assert sorted(_facts(right)) == sorted([RIGHT_LINE, RIGHT_OWN, RIGHT_HELD])
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

    # 5. Runeweaving from a prompt; Ashenmere, its site, from its stub
    preview = await _send(
        plugin,
        "preview_sphere",
        RUNEWEAVING_CORE,
        template="field",
        prompt="Runeweaving: runic magic, carved into stone and steel.",
        fields={},
    )
    runeweaving = await _send(plugin, "accept_sphere", preview=preview)
    runeweaving_id = runeweaving["id"]
    ashenmere_id = _item_id(runeweaving, "Sites", "Ashenmere")
    codex_id = _item_id(runeweaving, "Texts", "First Codex of Aelberth")
    conclave_id = (await _stubs(plugin))["Runeweavers' Conclave"]["id"]
    preview = await _expand(
        plugin, ashenmere_id, "place", ASHENMERE_REPLY, ASHENMERE_PROSE
    )
    ashenmere = await _send(
        plugin, "accept_preview", preview=preview, into_stub=ashenmere_id
    )
    [rediscovery] = [
        f for f in ashenmere["facts"] if _text(f["segments"]) == REDISCOVERY
    ]

    # the Codex: the Caves are Ashenmere (the owner says so); the Conclave
    # is left new, a duplicate for the merge below
    preview = await _expand(plugin, codex_id, "item", CODEX_REPLY, CODEX_PROSE)
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

    # 6. the Deep Galleries, inside Ashenmere: the fact about them moves in
    preview = await _send(
        plugin,
        "preview_thing",
        GALLERIES_REPLY,
        GALLERIES_PROSE,
        kind="place",
        prompt="The Deep Galleries, the lowest chambers of Ashenmere",
        fields={"parent": ashenmere_id},
        picks={"Ashenmere": ashenmere_id},
    )
    create_prompt = str(client.prompt_history[-2]["prompt"])
    assert "Ashenmere is the broader entry this place is part of" in create_prompt
    assert f"- M4: {GALLERIES_FACT}" in create_prompt
    moving = [row for row in preview["move_in"] if row["ticked"]]
    assert [row["text"] for row in moving] == [GALLERIES_FACT]
    galleries = await _send(plugin, "accept_preview", preview=preview)
    assert GALLERIES_FACT in _facts(galleries)
    ashenmere = await _thing(plugin, ashenmere_id)
    assert GALLERIES_FACT not in _facts(ashenmere)

    # 7. merge the Conclave into Runeweavers' Conclave: the link follows
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

    # 8. Runeweaving's timeline gathers the 947 rediscovery, once, from
    # Ashenmere, beside its own dated facts
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

    # 9. a scene at the Cathedral, a holy site of the Church: its doctrine
    # and the Divine Right's held fact are told as what the Church holds
    plan = await _send(
        plugin,
        "plan_scene",
        SETUP_REPLY,
        CATHEDRAL_PREVIEW,
        CATHEDRAL_PROSE,
        prompt="Vasha hears the Patriarch preach on the Divine Right of the Tsar",
        picks={
            "the Divine Right of the Tsar": right_id,
        },
        start=WorldDate.of(PRESENT).model_dump(),
    )
    setup = plan["setup"]
    assert setup["place"] == {"thing_id": cathedral_id, "local": None}
    started = await _send(plugin, "start_scene", setup=setup)
    record = world.scenes().get(started["scene_id"])
    block = world_context_block(world, record, WorldDate.of(PRESENT))
    held_lines = (HELD_DOCTRINE, HELD_CROWNING)
    for line in held_lines:
        assert block.count(line) == 1, line
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

    # the run's model calls: nothing for add_outer_body, the same-thing
    # offers (a stub row asks no model), move-in, the merge or timelines
    kinds = Counter(call["kind"] for call in client.prompt_history)
    assert kinds == {
        # species, the White Talon, the Divine Right, Ashenmere, the Codex,
        # the Deep Galleries, and the Cathedral's stub preview at planning
        "creative_instruction_3072": 7,
        # the Tsardom's, the Church's and Runeweaving's cores; the plan
        "creative_instruction_2048": 4,
        # each create's prose (7), and the same-thing verdict the
        # Cathedral's stub preview asks at planning (the Church shares its
        # name words and both have facts)
        "analyze": 8,
        "narrate_512": 1,
    }
