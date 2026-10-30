"""Filing end to end, with the mock model, through the real `worlds`
router (Filing plan, Task 11): the owner's own session in a fresh world
(present year 1000), every write a draft the owner ticks and accepts.

1. **The owl-folk**, written with a tag.
2. **The Tsardom**, from its stub, with the nation hint: the hint is
   stored, the agent default comes from it, and the next prompt's "tags
   in use" carries its tag.
3. **Velikoye and the Khorol River**: the river's "In" rows (Skyfall's own
   reply) arrive unticked (ruling F7); the owner ticks both, and it's
   filed in the Tsardom and in Velikoye.
4. **The Night Court**: no office, title or rank stub (ruling F5), and the
   Tsar, an existing name the reply puts "in" the Court, offered under
   "File into this", unticked; the owner gives him the role "presides"
   and ticks him.
5. **Runic Magic** (field hint) and **the Order of the Talon-Scribe**
   (order hint, its belief held by itself); **the Academy**, filed in
   Velikoye and, by the owner's "+ in...", in Runic Magic.
6. **The White Talon** ("Is this X?" asks the model about the Order and
   shows its verdict), then **the Frostwing Host** (the military) from its
   stub: "File into this" offers the White Talon, the owner ticks it, and
   it's filed in the Host.
7. **Plumage Signaling**, a custom, filed in the Night Court and the
   owl-folk: it shows under "Customs" on both pages.
8. **A group synopsis** of Velikoye's institutions: generated, cached,
   shown in `get_thing`'s `connected[].synopsis`, and stale (null) once
   the group gains a member.
9. **A merge** ("Chief Scribe Koroleva", a stub Plumage Signaling made,
   into Anastasiya Koroleva) whose links and filing follow; then **a
   Re-point with a chosen name** (`use_name`: "Grand Hall of the Tsar's
   Palace" onto "The Great Hall"): the links show that name, the stub's
   name taught as an other name.
10. **Regenerate, restore, discard**: version 2, `use_version` 1 brings
    version 1 back, and discard writes nothing (the head revision).
11. **Anastasiya Koroleva and Vasha**, each filed in the Order with a
    "but..." (parked Task 4 item M7), then **a scene** at the Academy:
    the World block holds the touched entries (summary, own facts,
    timeline lines, at most 8 lines each), the role rule (ruling F4)
    touches the Chief Scribe the goal names, told with her filing line
    "..., but: ...", the Order's belief is told as held, and Vasha's sheet
    carries his filing line.

Skyfall's own replies from the filing probe
(docs/superpowers/probes/raw/2026-10-23-filing.json, `calls[i].response`)
are the model's answer where they fit: the Khorol River (call 0), the
Night Court v2 (call 60, its Tsar's names "in" changed to the Court, see
`NIGHT_COURT_REPLY`), the Academy (call 3), the Frostwing Host (call 16),
Plumage Signaling (call 4), Velikoye's institutions synopsis (call 22)
and two Wattles runs (calls 9 and 62). The rest are written here.

Only `MockClient` responses are queued; one client serves the router and
every agent. Prose refreshes the accepts schedule for other entries are
recorded, not run.
"""

import asyncio
import json
import re
from collections import Counter
from pathlib import Path

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
from talemate.worldplay import create
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.context import TOUCHED_LINES, world_context_block
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

RAW = Path(__file__).resolve().parents[2] / (
    "docs/superpowers/probes/raw/2026-10-23-filing.json"
)
_CALLS = json.loads(RAW.read_text())["calls"]


def probe_reply(call: int) -> str:
    """Skyfall's reply in the filing probe's call `call`, as recorded: the
    text after the prepared `{`, which the prompt puts back."""

    return _CALLS[call]["response"]


def _probe_object(call: int) -> dict:
    return json.loads("{" + probe_reply(call))


# --- 1. the owl-folk -------------------------------------------------------------

SPECIES_REPLY = json.dumps(
    {
        "name": "Owl-folk",
        "tag": "people",
        "lifespan": 70,
        "adult_age": 12,
        "facts": [
            {
                "category": "origin",
                "text": "On the Night of Feathers in 994 every person in the "
                "Tsardom of Moscavia awoke as owl-folk.",
            },
            {"category": "physical", "text": "Owl-folk have wings in place of arms."},
            {
                "category": "instinct",
                "text": "Owl-folk wake at dusk and sleep through the day.",
            },
        ],
        "names": [
            {"name": "Tsardom of Moscavia", "kind": "place", "aka": []},
            {"name": "Night of Feathers", "kind": "event", "aka": []},
        ],
    }
)

# --- 2. the Tsardom, with the nation hint --------------------------------------------

TSARDOM_REPLY = json.dumps(
    {
        "name": "Tsardom of Moscavia",
        "tag": "nation",
        "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
        "facts": [
            {
                "category": "description",
                "text": "A northern realm of owl-folk and humans, ruled from Velikoye.",
            },
            {
                "category": "general",
                "text": "Tsar Dmitry IV rules the Tsardom by right of the old dynasty.",
            },
            {"category": "law", "text": "Only owl-folk may hold land."},
        ],
        "names": [
            {
                "name": "Velikoye",
                "kind": "place",
                "tag": "capital",
                "in": "Tsardom of Moscavia",
            },
            {
                "name": "Tsar Dmitry IV",
                "kind": "character",
                "tag": "ruler",
                "in": "Tsardom of Moscavia",
            },
        ],
    }
)

# --- 3. Velikoye -------------------------------------------------------------------

VELIKOYE_REPLY = json.dumps(
    {
        "name": "Velikoye",
        "tag": "capital",
        "aka": [{"name": "the capital", "tag": "common", "everyday": False}],
        "facts": [
            {
                "category": "description",
                "text": "Velikoye is the fortified capital of the Tsardom, built "
                "on both banks of the Khorol River.",
            },
            {
                "category": "general",
                "text": "Its streets were refitted with roosting ledges after "
                "the Night of Feathers.",
                "since": 995,
            },
        ],
        "names": [{"name": "Khorol River", "kind": "place", "tag": "river"}],
    }
)

# --- 4. the Night Court (probe call 60, adapted) --------------------------------------

_night_court = _probe_object(60)
# the one change to Skyfall's reply: its Tsar is listed "in" the Tsardom;
# here the reply puts him "in" the Night Court, the names-"in" path
# (ruling F7) that the probe's Frostwing Host case recorded for the White
# Talon -- no recorded Night Court reply has it
for _name in _night_court["names"]:
    if _name["name"] == "Tsar Dmitry IV":
        _name["in"] = "The Night Court"
NIGHT_COURT_REPLY = json.dumps(_night_court)
SENIOR_ADVISOR = "Senior Advisor"

# --- 5. Runic Magic, the Order and the Academy (call 3) --------------------------------

RUNIC_REPLY = json.dumps(
    {
        "name": "Runic Magic of the Tsardom",
        "tag": "field",
        "facts": [
            {
                "category": "general",
                "text": "Runic Magic of the Tsardom is the craft of carving runes "
                "into stone so that they bind frost and wind.",
            },
            {
                "category": "general",
                "text": "The oldest known rune circle stands at the mouth of the "
                "Khorol.",
            },
        ],
        "names": [],
    }
)

ORDER_BELIEF = "Every true rune binds a promise to the earth itself."
ORDER_HELD = (
    "Order of the Talon-Scribe holds that every true rune binds a promise "
    "to the earth itself."
)
ORDER_SUMMARY = (
    "The Order of the Talon-Scribe keeps, approves and teaches the Tsardom's runes."
)
ORDER_REPLY = json.dumps(
    {
        "name": "Order of the Talon-Scribe",
        "tag": "order",
        "facts": [
            {"category": "belief", "text": ORDER_BELIEF},
            {"category": "general", "text": ORDER_SUMMARY},
            {
                "category": "general",
                "text": "Every scribe of the Order swears the Oath of the "
                "Steady Talon.",
            },
        ],
        "names": [],
        "in": [{"entry": "Runic Magic of the Tsardom", "role": "keepers"}],
    }
)

ACADEMY_REPLY = probe_reply(3)
ACADEMY = "The Academy of the Chiseled Moon"

# --- 6. the White Talon, then the Frostwing Host (call 16) ----------------------------

WHITE_TALON_REPLY = json.dumps(
    {
        "name": "White Talon",
        "tag": "regiment",
        "facts": [
            {
                "category": "general",
                "text": "The White Talon is the Frostwing Host's heavy regiment "
                "of Snowy Owl-folk lancers.",
            },
            {
                "category": "general",
                "text": "It guards the Frostwing Host's banners on parade.",
            },
        ],
        "names": [{"name": "Frostwing Host", "kind": "lore", "tag": "military"}],
        "in": [{"entry": "Tsardom of Moscavia", "role": "regiment"}],
    }
)
TALON_WHY = "A regiment of the Host is not the order of rune scribes."
TALON_VERDICT = json.dumps({"verdict": "different", "why": TALON_WHY})
HOST_REPLY = probe_reply(16)

# --- 7. a custom (call 4) ---------------------------------------------------------------

PLUMAGE_REPLY = probe_reply(4)

# --- 8. a group synopsis (call 22) -------------------------------------------------------

SYNOPSIS_REPLY = probe_reply(22)
SYNOPSIS = _probe_object(22)["synopsis"]

# --- 10. regenerate and discard: two Wattles runs (calls 9 and 62) -------------------

WATTLES_V1 = probe_reply(9)
WATTLES_V2 = probe_reply(62)

# --- 11. the Chief Scribe, Vasha and the scene -------------------------------------------

KOROLEVA_BUT = "She still carves the old pre-Blinding runes in secret."
KOROLEVA_REPLY = {
    "name": "Anastasiya Koroleva",
    "age": 48,
    "tag": "official",
    "facts": [
        {
            "category": "appearance",
            "text": "Anastasiya Koroleva is a tawny-brown eared owl with "
            "burnt-orange eyes and one drooping ear tuft.",
        },
        {
            "category": "background",
            "text": "She was appointed Chief Scribe in 997.",
            "since": 997,
        },
        {
            "category": "personality",
            "text": "She is exacting, dry-witted and slow to trust.",
        },
    ],
    "names": [],
    # the exception's "rejects" label is filled in from the prompt's homes
    # block (see `_label_of`), as the model would read it
    "in": [
        {
            "entry": "Order of the Talon-Scribe",
            "role": "Chief Scribe",
            "exceptions": [{"text": KOROLEVA_BUT, "rejects": None}],
        }
    ],
}

VASHA_BUT = "He never carves a rune himself."
VASHA_REPLY = {
    "name": "Vasha",
    "age": 19,
    "tag": "courier",
    "facts": [
        {
            "category": "appearance",
            "text": "Vasha is a small, quick barn owl with a satchel strapped "
            "across his chest.",
        },
        {
            "category": "background",
            "text": "Vasha carries sealed letters for the Order.",
        },
        {
            "category": "personality",
            "text": "Vasha is eager, chatty and easily startled.",
        },
    ],
    "names": [],
    "in": [
        {
            "entry": "Order of the Talon-Scribe",
            "role": "courier",
            "exceptions": [{"text": VASHA_BUT, "rejects": None}],
        }
    ],
}

GOAL = (
    "Vasha must deliver a sealed letter to the Chief Scribe of the Order of "
    "the Talon-Scribe."
)
SETUP_REPLY = json.dumps(
    {
        "player": "Vasha",
        "characters": [{"name": "Vasha"}],
        "place": {"name": ACADEMY, "world": True},
        "goal": GOAL,
        "intro": "Vasha lands in the Academy's frosted courtyard.",
    }
)
TURN = "Vasha shakes the frost from his wings and asks for the Chief Scribe."


def _queue(*responses) -> None:
    for response in responses:
        client_responses.get().append(response)


def _reading(write):
    """A queued reply written from the prompt it answers (`write(prompt
    text) -> reply`), as the model reads the labels a prompt gives."""

    write.reads_prompt = True
    return write


def _label_of(prompt: str, text: str) -> str:
    """The homes block's label ("S3") of the item that opens with `text`."""

    [label] = re.findall(r"^- (S\d+): " + re.escape(text), prompt, re.MULTILINE)
    return label


def _with_exception(reply: dict, home_fact: str):
    """`reply` (a character's), its one "in" row's exception rejecting the
    homes block's item `home_fact`, by the label the prompt gives it."""

    def write(prompt: str) -> str:
        filled = json.loads(json.dumps(reply))
        [row] = filled["in"]
        row["exceptions"][0]["rejects"] = _label_of(prompt, home_fact)
        return json.dumps(filled)

    return _reading(write)


async def _noop(self, *args, **kwargs):
    pass


class _Handler:
    """Minimal websocket handler stand-in: no scene, a queue_put collector."""

    scene = None

    def __init__(self):
        self.messages: list[dict] = []

    def queue_put(self, data):
        self.messages.append(data)


class _ReadingClient(MockClient):
    """`MockClient` that also takes a `_reading` reply, written from the
    prompt it's sent."""

    async def send_prompt(self, prompt, kind="conversation", **kwargs):
        stack = client_responses.get()
        if stack and getattr(stack[0], "reads_prompt", False):
            stack[0] = stack[0](str(prompt))
        return await super().send_prompt(prompt, kind=kind, **kwargs)


@pytest.fixture
def client():
    """One `MockClient` for every agent, so the router's creator-agent
    client and the scene's agents are the same."""

    mock = _ReadingClient("filing")
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
    test, as in the curation end-to-end test."""

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


async def _send(plugin, action: str, *responses, **data) -> dict:
    """Send `action` through the router with `responses` queued, wait for
    its background task (if any), and return its reply's data. Every
    queued response must have been asked for."""

    seen = len(plugin.websocket_handler.messages)
    async with MockClientContext():
        _queue(*responses)
        await plugin.handle({"type": "worlds", "action": action, **data})
        await _drain(plugin)
        left = list(client_responses.get())
        client_responses.get().clear()
    new = plugin.websocket_handler.messages[seen:]
    assert not [m for m in new if m in _errors(plugin)], new
    assert not left, f"{action}: {len(left)} queued responses never asked for"
    return _last(plugin, action)


async def _draft(plugin, kind: str, reply, *, then=(), **data) -> dict:
    """A draft page (`preview_thing`) from the model's `reply` (a draft
    writes no prose), then `then` (a same-thing verdict, asked last)."""

    return await _send(plugin, "preview_thing", reply, *then, kind=kind, **data)


async def _picks(plugin, prompt: str) -> dict[str, str]:
    """The picks the create box sends for `prompt` (`match_names`, then
    `nameHighlights.pickedId` untouched by the owner): each name it
    matches in full, stubs included, to its first candidate; a mere
    suggestion is left new."""

    found = await _send(plugin, "match_names", text=prompt, at=None)
    return {
        match["text"]: match["candidates"][0]["id"]
        for match in found["matches"]
        if not match["suggested"] and match["candidates"]
    }


async def _new(plugin, kind: str, reply, prompt: str, **extra) -> dict:
    """A new entry's draft page from `prompt`, sent with the create box's
    picks."""

    return await _draft(
        plugin,
        kind,
        reply,
        prompt=prompt,
        fields=extra.pop("fields", {}),
        picks=await _picks(plugin, prompt),
        **extra,
    )


async def _expand(plugin, stub_id: str, kind: str, reply, **extra) -> dict:
    """A stub's draft page from its suggested prompt."""

    suggestion = await _send(plugin, "stub_suggestion", id=stub_id)
    return await _draft(
        plugin,
        kind,
        reply,
        prompt=suggestion["prompt"],
        fields=extra.pop("fields", {}),
        stub_id=stub_id,
        **extra,
    )


async def _accept(plugin, draft: dict, **extra) -> dict:
    return await _send(
        plugin,
        "accept_preview",
        preview=draft["preview"],
        draft_key=draft["draft_key"],
        **extra,
    )


async def _stubs(plugin) -> dict[str, dict]:
    listed = await _send(plugin, "list_stubs", include_ignored=True)
    return {stub["name"]: stub for stub in listed["stubs"]}


async def _thing(plugin, thing_id: str) -> dict:
    return await _send(plugin, "get_thing", id=thing_id, at=None)


def _text(segments: list[dict]) -> str:
    return "".join(s["text"] for s in segments)


def _facts(thing: dict) -> list[str]:
    return [_text(f["segments"]) for f in thing["facts"]]


def _links(thing: dict) -> dict[str, str]:
    """Each linked run's words -> the thing it links to, over the facts."""

    return {
        s["text"]: s["ref"] for f in thing["facts"] for s in f["segments"] if s["ref"]
    }


def _group(thing: dict, tag: str | None) -> dict:
    [group] = [g for g in thing["connected"] if g["tag"] == tag]
    return group


def _rows(thing: dict, tag: str | None) -> dict[str, dict]:
    return {row["id"]: row for row in _group(thing, tag)["rows"]}


def _filed(world, thing_id: str) -> dict[str, str | None]:
    """Where `thing_id` is filed now: target id -> role."""

    return {f.target: f.role for f in filings_of(world.view(), thing_id)}


def _prompt_since(client, before: int, uid: str = "world.create-thing") -> str:
    [call] = [c for c in client.prompt_history[before:] if c["prompt"].uid == uid]
    return str(call["prompt"])


def _touched(block: str) -> dict[str, list[str]]:
    """The World block's touched entries: heading -> its lines, in order."""

    lead = "What this scene touches:"
    body = block.split(lead, 1)[1].split("\n", 1)[1] if lead in block else ""
    found: dict[str, list[str]] = {}
    heading = None
    for line in body.splitlines():
        if line.startswith("[end of world]") or line.startswith("Who is here"):
            break
        if line.startswith("- ") and heading is not None:
            found[heading].append(line[2:])
        elif line.strip():
            heading = line
            found[heading] = []
    return found


def _fact_id(world, thing_id: str, text: str) -> str:
    view = world.view()
    [fact_id] = [
        f.fact_id for f in view.thing(thing_id).facts if view.render(f.text) == text
    ]
    return fact_id


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
async def test_filing_end_to_end(plugin, client, loadable):
    await plugin.handle(
        {
            "type": "worlds",
            "action": "create_world",
            "name": "Moscavia",
            "present_year": PRESENT,
        }
    )
    world = plugin.world

    # 1. the owl-folk, written with a tag; they name the Tsardom
    draft = await _new(
        plugin,
        "species",
        SPECIES_REPLY,
        "Owl-folk: owl people. Everyone in the Tsardom of Moscavia "
        "became this race suddenly one day.",
    )
    assert draft["tag"] == "people"
    owlfolk = await _accept(plugin, draft)
    owlfolk_id = owlfolk["id"]
    assert owlfolk["tag"] == "people"
    stubs = await _stubs(plugin)
    tsardom_id = stubs["Tsardom of Moscavia"]["id"]

    # 2. the Tsardom, from its stub, with the nation hint
    before = len(client.prompt_history)
    draft = await _expand(plugin, tsardom_id, "place", TSARDOM_REPLY, hint="nation")
    assert create.hint_text("nation") in _prompt_since(client, before)
    tsardom = await _accept(plugin, draft, into_stub=tsardom_id)
    assert (tsardom["id"], tsardom["stub"]) == (tsardom_id, None)
    assert tsardom["hint"] == "nation"
    assert tsardom["tag"] == "nation"
    # the agent default comes from the hint: a nation acts
    assert world.view().thing(tsardom_id).fields["agent"] is True
    stubs = await _stubs(plugin)
    velikoye_id = stubs["Velikoye"]["id"]
    tsar_id = stubs["Tsar Dmitry IV"]["id"]
    # the names' own "in" (ticked): both filed in the Tsardom
    assert set(_rows(tsardom, "capital")) == {velikoye_id}
    assert set(_rows(tsardom, "ruler")) == {tsar_id}

    # 3. Velikoye: its prompt's "tags in use" carry the Tsardom's tag
    before = len(client.prompt_history)
    draft = await _expand(plugin, velikoye_id, "place", VELIKOYE_REPLY)
    prompt = _prompt_since(client, before)
    tags_line = prompt.split("Tags in use in the world", 1)[1].split("\n")[1]
    assert "nation (1)" in tags_line.split(", "), tags_line
    assert "people (1)" in tags_line.split(", "), tags_line
    velikoye = await _accept(plugin, draft, into_stub=velikoye_id)
    assert _filed(world, velikoye_id) == {tsardom_id: None}
    khorol_id = (await _stubs(plugin))["Khorol River"]["id"]

    # the Khorol River, from its stub: Skyfall's "In" rows, unticked
    # (F7); the owner ticks both
    draft = await _expand(plugin, khorol_id, "place", probe_reply(0))
    rows = {row["target_id"]: row for row in draft["preview"]["filings"]}
    assert {k: (r["role"], r["ticked"]) for k, r in rows.items()} == {
        tsardom_id: ("principal river", False),
        velikoye_id: ("bisects the city", False),
    }
    for row in draft["preview"]["filings"]:
        row["ticked"] = True
    khorol = await _accept(plugin, draft, into_stub=khorol_id)
    assert _filed(world, khorol_id) == {
        tsardom_id: "principal river",
        velikoye_id: "bisects the city",
    }
    assert khorol["tag"] == "river"
    for page_id in (tsardom_id, velikoye_id):
        assert khorol_id in _rows(await _thing(plugin, page_id), "river")

    # 4. the Night Court: Skyfall's v2 reply lists "Senior Advisor" (an
    # office) among its names; it never becomes a stub (F5)
    assert SENIOR_ADVISOR in [n["name"] for n in _night_court["names"]]
    draft = await _new(
        plugin,
        "lore",
        NIGHT_COURT_REPLY,
        "The Night Court, the council that governs the Tsardom of Moscavia after dark",
    )
    assert draft["tag"] == "institution"
    new_names = {n["name"]: n for n in draft["preview"]["new_names"]}
    assert SENIOR_ADVISOR not in new_names
    assert not [
        n
        for n in new_names.values()
        if {n["kind"], n["tag"]} & {"office", "title", "rank"}
    ]
    # "In": the Tsardom, unticked (F7); the owner ticks it
    [row] = draft["preview"]["filings"]
    assert (row["target_id"], row["role"], row["ticked"]) == (
        tsardom_id,
        "primary governing body",
        False,
    )
    row["ticked"] = True
    # "File into this": the Tsar, whose names "in" is this entry, unticked;
    # the owner gives him the role "presides" and ticks him
    assert [
        (r["thing_id"], r["role"], r["ticked"]) for r in draft["preview"]["file_into"]
    ] == [(tsar_id, None, False)]
    draft["preview"]["file_into"][0].update(role="presides", ticked=True)
    court = await _accept(plugin, draft)
    court_id = court["id"]
    assert _filed(world, court_id) == {tsardom_id: "primary governing body"}
    assert _filed(world, tsar_id) == {tsardom_id: None, court_id: "presides"}
    assert _rows(court, "ruler")[tsar_id]["role"] == "presides"
    stubs = await _stubs(plugin)
    assert SENIOR_ADVISOR not in stubs
    plumage_id = stubs["Plumage Signaling"]["id"]
    great_hall_id = stubs["The Great Hall"]["id"]
    runic_id = stubs["Runic Magic of the Tsardom"]["id"]
    order_id = stubs["Order of the Talon-Scribe"]["id"]
    host_id = stubs["Frostwing Host"]["id"]
    # the Court's facts link the Order as written, "Talon-Scribe Order"
    assert _links(court)["Talon-Scribe Order"] == order_id

    # 5. Runic Magic, from its stub (the Khorol's elsewhere fact made it),
    # with the field hint: a field doesn't act
    draft = await _expand(plugin, runic_id, "lore", RUNIC_REPLY, hint="field")
    runic = await _accept(plugin, draft, into_stub=runic_id)
    assert (runic["hint"], runic["tag"]) == ("field", "field")
    assert world.view().thing(runic_id).fields["agent"] is False
    # the Order, from its stub, with the order hint: its belief is held by
    # itself; the owner ticks its "In" row
    draft = await _expand(plugin, order_id, "lore", ORDER_REPLY, hint="order")
    [row] = draft["preview"]["filings"]
    assert (row["target_id"], row["ticked"]) == (runic_id, False)
    row["ticked"] = True
    order = await _accept(plugin, draft, into_stub=order_id)
    [belief] = [f for f in order["facts"] if f["text"] == ORDER_BELIEF]
    assert belief["held_by"] == {"id": order_id, "name": "Order of the Talon-Scribe"}
    assert _filed(world, order_id) == {runic_id: "keepers"}

    # the Academy (Skyfall's reply): "In" the Order and Velikoye, never in
    # Runic Magic (probe 1's miss); the owner ticks Velikoye and files it
    # in Runic Magic with "+ in...", a row of the owner's, ticked
    draft = await _new(
        plugin,
        "place",
        ACADEMY_REPLY,
        "The Academy of the Chiseled Moon, where the Order of the "
        "Talon-Scribe trains its scribes in Velikoye",
    )
    rows = {row["target_id"]: row for row in draft["preview"]["filings"]}
    assert {k: (r["role"], r["ticked"]) for k, r in rows.items()} == {
        order_id: ("central administration", False),
        velikoye_id: ("located in", False),
    }
    rows[velikoye_id]["ticked"] = True
    draft["preview"]["filings"].append(
        {
            "target_id": runic_id,
            "target_name": "Runic Magic of the Tsardom",
            "role": "taught here",
            "ticked": True,
        }
    )
    academy = await _accept(plugin, draft)
    academy_id = academy["id"]
    assert academy["name"] == ACADEMY and academy["tag"] == "institution"
    assert _filed(world, academy_id) == {
        velikoye_id: "located in",
        runic_id: "taught here",
    }
    assert academy_id in _rows(await _thing(plugin, velikoye_id), "institution")
    assert academy_id in _rows(await _thing(plugin, runic_id), "institution")
    stubs = await _stubs(plugin)
    koroleva_id = stubs["Anastasiya Koroleva"]["id"]

    # 6. the White Talon, naming the Frostwing Host (a stub the Khorol's
    # reply made, tagged "military")
    draft = await _new(
        plugin,
        "lore",
        WHITE_TALON_REPLY,
        "The White Talon, the heavy regiment of the Frostwing Host",
        then=[TALON_VERDICT],
    )
    # "Is this X?": the Order shares a word, and has facts, so the model's
    # verdict is asked, last, and shown as a hint; the owner leaves it new
    [offer] = draft["preview"]["same_as"]
    assert (offer["thing_id"], offer["has_facts"]) == (order_id, True)
    assert draft["preview"]["verdict"] == {
        order_id: {"verdict": "different", "why": TALON_WHY, "confidence": None}
    }
    [row] = draft["preview"]["filings"]
    assert row["target_id"] == tsardom_id
    row["ticked"] = True
    talon = await _accept(plugin, draft)
    talon_id = talon["id"]
    assert _filed(world, talon_id) == {tsardom_id: "regiment"}
    # the Frostwing Host, made after it (Skyfall's reply): "File into this"
    # offers the White Talon -- the model's row, with its role; its facts
    # name the Host too -- unticked. The reply's other rows name entries
    # the world hasn't, so they're dropped; code adds the near entries
    # whose facts name the Host (the Khorol River, the Night Court), also
    # unticked (F7), which the owner leaves
    draft = await _expand(plugin, host_id, "lore", HOST_REPLY)
    assert [
        (r["thing_id"], r["role"], r["ticked"]) for r in draft["preview"]["file_into"]
    ] == [
        (talon_id, "heavy regiment", False),
        (khorol_id, None, False),
        (court_id, None, False),
    ]
    draft["preview"]["file_into"][0]["ticked"] = True
    [row] = draft["preview"]["filings"]
    assert (row["target_id"], row["ticked"]) == (tsardom_id, False)
    row["ticked"] = True
    host = await _accept(plugin, draft, into_stub=host_id)
    assert host["tag"] == "military"
    assert _filed(world, talon_id) == {
        tsardom_id: "regiment",
        host_id: "heavy regiment",
    }
    assert _rows(host, "regiment")[talon_id]["role"] == "heavy regiment"
    assert _filed(world, host_id) == {tsardom_id: "the realm's armed forces"}

    # 7. a custom in two places: Plumage Signaling (Skyfall's reply), "In"
    # the Night Court; the owner ticks it and adds the owl-folk ("+ in...")
    draft = await _expand(plugin, plumage_id, "lore", PLUMAGE_REPLY)
    [row] = draft["preview"]["filings"]
    assert (row["target_id"], row["ticked"]) == (court_id, False)
    row["ticked"] = True
    draft["preview"]["filings"].append(
        {
            "target_id": owlfolk_id,
            "target_name": "Owl-folk",
            "role": "practised by",
            "ticked": True,
        }
    )
    plumage = await _accept(plugin, draft, into_stub=plumage_id)
    assert plumage["tag"] == "custom"
    assert _filed(world, plumage_id) == {
        court_id: "a communication practice used during its formal sessions",
        owlfolk_id: "practised by",
    }
    for page_id in (court_id, owlfolk_id):
        group = _group(await _thing(plugin, page_id), "custom")
        assert group["heading"] == "Customs"
        assert plumage_id in {row["id"] for row in group["rows"]}
    stubs = await _stubs(plugin)
    chief_id = stubs["Chief Scribe Koroleva"]["id"]
    grand_hall_id = stubs["Grand Hall of the Tsar's Palace"]["id"]

    # 8. a group synopsis: Velikoye's institutions, generated, cached and
    # shown on the page (Skyfall's reply for that group in the probe's
    # world, where it had three members; here it has the Academy)
    before = len(client.prompt_history)
    answer = await _send(
        plugin,
        "group_synopsis",
        SYNOPSIS_REPLY,
        thing_id=velikoye_id,
        tag="institution",
    )
    assert answer["synopsis"] == SYNOPSIS
    assert [c["kind"] for c in client.prompt_history[before:]] == ["analyze"]
    assert _group(await _thing(plugin, velikoye_id), "institution")["synopsis"] == (
        SYNOPSIS
    )
    # asked again with nothing changed: the cache answers, no model call
    before = len(client.prompt_history)
    answer = await _send(
        plugin, "group_synopsis", thing_id=velikoye_id, tag="institution"
    )
    assert answer["synopsis"] == SYNOPSIS
    assert len(client.prompt_history) == before
    # the group gains a member (the Night Court, an institution, convenes
    # in Velikoye): the synopsis is stale, so the page shows none
    await _send(
        plugin,
        "add_filing",
        thing_id=court_id,
        target_id=velikoye_id,
        role="convenes here",
    )
    group = _group(await _thing(plugin, velikoye_id), "institution")
    assert {row["id"] for row in group["rows"]} == {academy_id, court_id}
    assert group["synopsis"] is None

    # 9. a merge: Plumage Signaling made "Chief Scribe Koroleva" a stub of
    # its own, filed (its names "in") in the Night Court; the owner merges
    # it into Anastasiya Koroleva, and its links and filing follow
    assert _filed(world, chief_id) == {court_id: None}
    assert _links(plumage)["Chief Scribe Koroleva"] == chief_id
    merge = await _send(plugin, "preview_merge", from_id=chief_id, into_id=koroleva_id)
    merged = await _send(
        plugin,
        "accept_merge",
        preview=merge["preview"],
        main_name="Anastasiya Koroleva",
    )
    assert merged["into"]["id"] == koroleva_id
    assert "Chief Scribe Koroleva" in merged["aka_added"]
    assert world.view().thing(chief_id) is None
    assert _links(await _thing(plugin, plumage_id))["Chief Scribe Koroleva"] == (
        koroleva_id
    )
    assert _filed(world, koroleva_id) == {court_id: None}
    assert koroleva_id in _rows(await _thing(plugin, court_id), "official")

    # Re-point with a chosen name: "Grand Hall of the Tsar's Palace" (from
    # Plumage Signaling) is the Night Court's "The Great Hall"; every link
    # then reads that name, its article fitted to the text ("held in the
    # Great Hall's gallery"), and the Great Hall learns the stub's name
    assert _links(await _thing(plugin, plumage_id))["Grand Hall"] == grand_hall_id
    done = await _send(
        plugin,
        "repoint_stub",
        stub_id=grand_hall_id,
        target_id=great_hall_id,
        use_name="The Great Hall",
    )
    assert done["links"] == 1
    assert world.view().thing(grand_hall_id) is None
    plumage = await _thing(plugin, plumage_id)
    assert _links(plumage)["Great Hall"] == great_hall_id
    [gallery] = [f for f in _facts(plumage) if "gallery" in f]
    assert "held in the Great Hall's gallery" in gallery
    assert done["aka_added"] == ["Grand Hall of the Tsar's Palace"]
    assert [a["name"] for a in done["target"]["aka"]] == [
        "Grand Hall of the Tsar's Palace"
    ]

    # 10. regenerate, restore, discard: two of Skyfall's Wattles runs as
    # versions 1 and 2; restoring version 1 gives its facts back; discard
    # writes nothing
    head, things = world.head_rev(), len(world.view().things())
    first = await _new(
        plugin, "lore", WATTLES_V1, "Wattles, a custom of Velikoye's owl-folk"
    )
    assert (first["version"], len(first["versions"])) == (1, 1)
    key = first["draft_key"]
    second = await _new(
        plugin,
        "lore",
        WATTLES_V2,
        "Wattles, a custom of Velikoye's owl-folk",
        draft_key=key,
    )
    assert (second["draft_key"], second["version"]) == (key, 2)
    assert [v["version"] for v in second["versions"]] == [1, 2]
    v1_facts = [f["text"] for f in first["facts"]]
    assert v1_facts != [f["text"] for f in second["facts"]]
    restored = await _send(plugin, "use_version", draft_key=key, version=1)
    assert restored["version"] == 1
    assert [f["text"] for f in restored["facts"]] == v1_facts
    assert restored["preview"] == first["preview"]
    assert await _send(plugin, "discard_preview", draft_key=key) == {"draft_key": key}
    assert world.head_rev() == head
    assert len(world.view().things()) == things
    assert not [
        t for t in world.view().things() if world.view().name_of(t.id) == "Wattles"
    ]

    # 11. Anastasiya Koroleva, from her stub: the Chief Scribe, filed in
    # the Order with a "but..." that rejects one of its items, by the label
    # the prompt's homes block gives it (M7); the owner ticks the row
    oath = "Every scribe of the Order swears the Oath of the Steady Talon."
    order_pick = {"Order of the Talon-Scribe": order_id}
    suggestion = await _send(plugin, "stub_suggestion", id=koroleva_id)
    before = len(client.prompt_history)
    draft = await _draft(
        plugin,
        "character",
        _with_exception(KOROLEVA_REPLY, oath),
        prompt=suggestion["prompt"] + " Chief Scribe of the Order of the Talon-Scribe.",
        fields={},
        stub_id=koroleva_id,
        picks=order_pick,
    )
    label = _label_of(_prompt_since(client, before), oath)
    [row] = draft["preview"]["filings"]
    assert (row["target_id"], row["role"], row["ticked"]) == (
        order_id,
        "Chief Scribe",
        False,
    )
    assert [(e["text"], e["fact_id"]) for e in row["exceptions"]] == [
        (KOROLEVA_BUT, _fact_id(world, order_id, oath))
    ], label
    row["ticked"] = True
    koroleva = await _accept(plugin, draft, into_stub=koroleva_id)
    [filing] = [f for f in koroleva["in"] if f["target_id"] == order_id]
    assert filing["role"] == "Chief Scribe"
    [but] = filing["exceptions"]
    assert _text(but["segments"]).startswith(KOROLEVA_BUT)

    # Vasha, a courier of the Order, from a prompt, with his own "but..."
    prompt = "Vasha, a young courier who carries sealed letters for the Order of the Talon-Scribe"
    draft = await _new(plugin, "character", _with_exception(VASHA_REPLY, oath), prompt)
    [row] = draft["preview"]["filings"]
    assert (row["target_id"], row["role"]) == (order_id, "courier")
    assert [(e["text"], e["fact_id"]) for e in row["exceptions"]] == [
        (VASHA_BUT, _fact_id(world, order_id, oath))
    ]
    row["ticked"] = True
    vasha = await _accept(plugin, draft)

    vasha_id = vasha["id"]

    # the scene: Vasha brings a sealed letter to the Chief Scribe at the
    # Academy (probe 5's scene)
    prompt = (
        "Vasha brings a sealed letter to the Chief Scribe at The Academy of "
        "the Chiseled Moon"
    )
    plan = await _send(
        plugin,
        "plan_scene",
        SETUP_REPLY,
        prompt=prompt,
        picks=await _picks(plugin, prompt),
        start=WorldDate.of(PRESENT).model_dump(),
    )
    setup = plan["setup"]
    assert setup["place"] == {"thing_id": academy_id, "local": None}
    assert setup["player"] == {"thing_id": vasha_id, "local": None}
    before = len(client.prompt_history)
    started = await _send(plugin, "start_scene", setup=setup)
    # a draft has no prose (languages 4a) and this test only records the
    # prose accept schedules: the player's two sections are written at
    # start
    assert [c["prompt"].uid for c in client.prompt_history[before:]] == [
        "world.thing-prose",
        "world.thing-prose",
    ]
    record = world.scenes().get(started["scene_id"])
    block = world_context_block(world, record, WorldDate.of(PRESENT))
    touched = _touched(block)
    # what the Academy is filed in, followed up two steps (Velikoye, Runic
    # Magic, then the Tsardom); what Vasha is filed in (the Order, which
    # the goal names too); and, by the role rule (F4), the Order's Chief
    # Scribe -- never Vasha himself, the place, or the Tsar (filed in the
    # Tsardom with no role, and in the untouched Night Court)
    assert list(touched) == [
        "Velikoye (capital)",
        "Runic Magic of the Tsardom (field)",
        "Tsardom of Moscavia (nation, usually called Moscavia)",
        "Order of the Talon-Scribe (order, usually called Talon-Scribe Order)",
        "Anastasiya Koroleva (official)",
    ]
    for heading, lines in touched.items():
        assert 0 < len(lines) <= TOUCHED_LINES, heading
    # each opens with its summary, then its own facts, then its latest
    # timeline lines ("In <year>: ...")
    velikoye = touched["Velikoye (capital)"]
    assert velikoye[0] == (
        "Velikoye is the fortified capital of the Tsardom, built on both banks "
        "of the Khorol River."
    )
    assert re.match(r"In 99\d: ", velikoye[-1]), velikoye
    assert any(
        re.match(r"In 99\d: ", line)
        for line in touched["Tsardom of Moscavia (nation, usually called Moscavia)"]
    )
    # the Order's belief, told as held, once, never as plain truth
    assert block.count(ORDER_HELD) == 1
    # its summary is its first plain fact, never the belief (ruling F28)
    assert (
        touched["Order of the Talon-Scribe (order, usually called Talon-Scribe Order)"][
            0
        ]
        == ORDER_SUMMARY
    )
    assert ORDER_BELIEF not in block
    # M7: the Chief Scribe's "but..." reaches the block as her filing line
    koroleva_lines = touched["Anastasiya Koroleva (official)"]
    assert koroleva_lines[1] == (
        "Chief Scribe of Order of the Talon-Scribe, but: she still carves the "
        "old pre-Blinding runes in secret"
    )
    assert "Departs from" not in block
    assert "[[thing:" not in block

    # Vasha's sheet carries his filing line with its "but..." (M7)
    vasha_line = (
        "Courier of Order of the Talon-Scribe, but: he never carves a rune himself"
    )
    sheet = character_from_world(world, vasha_id, WorldDate.of(PRESENT), is_player=True)
    assert sheet.base_attributes["ties"] == vasha_line

    # the narrator's turn is told the block
    scene = await _load(world, started["scene_id"], client)
    try:
        before = len(client.prompt_history)
        with ActiveScene(scene):
            async with MockClientContext():
                _queue(TURN)
                await instance.get_agent("narrator").progress_story(
                    narrative_direction="Vasha lands in the courtyard."
                )
        calls = client.prompt_history[before:]
        assert [call["kind"] for call in calls] == ["narrate_512"]
        turn_prompt = str(calls[0]["prompt"])
        assert turn_prompt.count(ORDER_HELD) == 1
        assert ORDER_BELIEF not in turn_prompt
        assert koroleva_lines[1] in turn_prompt
        # the loaded scene's own sheet for Vasha carries it too
        assert scene.get_character("Vasha").base_attributes["ties"] == vasha_line
    finally:
        close_world_scene(scene)

    # every model call of the session: no verdict asked but the White
    # Talon's, nothing for "File into this", "Could move here", the merge,
    # the Re-point, the restore, the discard or the World block
    asked = Counter(call["prompt"].uid for call in client.prompt_history)
    assert asked == ASKED, asked


# the fifteen drafts (the owl-folk, the Tsardom, Velikoye, the Khorol,
# the Night Court, Runic Magic, the Order, the Academy, the White Talon,
# the Host, Plumage Signaling, two Wattles versions, the Chief Scribe,
# Vasha); Vasha's prose, written at the scene's start (drafts have none
# since languages 4a, and this test only records the prose accept
# schedules); the White Talon's verdict; the synopsis (asked once: then
# cached); the plan; the narrator's turn
ASKED = {
    "world.create-thing": 15,
    "world.thing-prose": 2,
    "world.same-thing": 1,
    "world.group-synopsis": 1,
    "world.scene-setup": 1,
    "narrator.narrate-progress": 1,
}
