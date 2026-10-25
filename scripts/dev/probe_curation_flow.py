"""Throwaway probe: the owner's curation session on the real model
(fantasymate curation, Task 13).

Drives the path the world screens use -- the real `worlds` router
(`talemate.server.worlds.WorldsPlugin`) and `worldplay` -- with Talemate's
own KoboldCpp client serving every agent (the `--ai` app's config, as
`probe_heritage_play` sets it up). Nothing is stubbed and no fixed reply is
used: every create, core, Fill, prose call, verdict, plan and turn is the
model's. Prose refreshes the accepts schedule run too, as in the app.

The session, in a fresh world (present year 1000, as the owner's
2026-10-22 acceptance world), shaped like the owner's run (spec, "How the
owner will judge it"; Task 13's brief):

1. **Owl-folk**, a species, from the owner's prompt naming the Tsardom of
   Moscavia; then **the Tsardom**, a nation sphere from its stub, with its
   suggested prompt and the owner's words "It has a state church."
2. **Its church**, followed from the Tsardom's mention into a religion
   sphere (the sphere stub guessed as a religion, else the first stub that
   reads as a faith).
3. **A doctrine** from the church's beliefs drawer (the Divine Right of
   the Tsar if it's there), expanded from its stub: where its elsewhere
   items go is recorded.
4. **The army:** a regiment the Tsardom names, expanded from its stub; the
   owner names its outer body, "The Tsar's Army" (an order filed where the
   regiment is filed, `add_outer_body`), and ticks the re-file rows of the
   other regiments.
5. **Runic magic:** Runeweaving, a field sphere from a prompt; then its
   children expanded from their stubs: a technique, a site and a codex;
   a Fill of its places drawer; and a more specific place inside the site,
   whose facts may move in from it.
6. **Runeweaving's timeline**, as its page reads it.
7. **A scene** where the church matters, planned by the model through the
   router, with a held fact in play: before it, the owner marks one of the
   doctrine's facts held by the church. Two narrator turns.

Wherever the owner would tick or untick, the defaults are accepted as the
preview sends them (elsewhere ticked, repeats unticked, move-in picks
ticked, same-thing "new"), except where the brief names the owner's act:
the outer body and its re-file rows (step 4) and the one merge.
What an owner would plausibly change is judged by hand afterwards.

**The merge** runs after the session, on the kept world, through the
router (`--merge WORLD_DIR FROM INTO`, same `--label`): one duplicate pair
the session left, picked by hand from the run's `same_pairs` (a pair
picked by code risked merging a god into its church). Runeweaving's
timeline is read again after it.

After every model call the run is written to the output JSON: each step's
previews (facts, elsewhere, same-thing offers, move-in, refile), the
accepted payloads, and every call's prompt and reply. The world is kept
under `--root` for scoring.

`--score WORLD_DIR [--score-out FILE]` scores a world (a copy is opened, the
world is never written): every fact restating another at the world's
untick threshold (0.7, `world.repeats.overlap`), the same-thing pairs
(`world.sameness.same_candidates`) and each thing's facts, for judging by
hand.

Not a test: it calls the network. The owner approved Task 13's Skyfall
session (one GPU: calls run one after another)::

    guix shell -m manifest.scm -- bash -c 'cd scripts/dev && HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        probe_curation_flow.py OUT.json --root DIR [--label NAME] \\
        [--replay LABEL]'

Findings: docs/superpowers/probes/2026-10-23-curation-flow.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

# the heritage play probe's harness: config, recording client, test stand-ins
import probe_heritage_play as harness  # noqa: E402

import talemate.instance as instance  # noqa: E402
from talemate.context import ActiveScene  # noqa: E402
from talemate.scene_message import NarratorMessage  # noqa: E402
from talemate.server.worlds import WorldsPlugin  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.repeats import content_words, overlap  # noqa: E402
from talemate.world.sameness import name_index, same_candidates  # noqa: E402
from talemate.world.store import World  # noqa: E402
from talemate.worldplay.context import world_context_block  # noqa: E402
from talemate.worldplay.persistence import close_world_scene  # noqa: E402

from conftest import MockMemoryAgent, MockScene, bootstrap_scene  # noqa: E402
from world.embedding import TrigramEmbeddingFunction  # noqa: E402

PRESENT = 1000
SPECIES_PROMPT = (
    "Owl-folk: owl people. Everyone in the Tsardom of Moscavia became this "
    "race suddenly one day 6 years ago."
)
TSARDOM = "Tsardom of Moscavia"
TSARDOM_EXTRA = " It has a state church."
FAITH = re.compile(
    r"church|faith|religio|worship|creed|\bcult\b|temple|priest|\bgods?\b|"
    r"goddess|divine|holy|sacred",
    re.I,
)
DOCTRINE = re.compile(r"divine right|\btsar", re.I)
MILITARY = re.compile(
    r"regiment|talon|\bwing\b|guard|legion|\bhost\b|army|brigade|"
    r"battalion|cavalry|riders|sentinel",
    re.I,
)
ARMY = "The Tsar's Army"
RUNEWEAVING_PROMPT = (
    "Runeweaving: runic magic. Runes carved into stone, metal and wood "
    "change what the material is."
)
CODEX = re.compile(r"codex|tome|book|text|scroll|grimoire|canon", re.I)
# the old run's codex, which the owner makes when Runeweaving names none
CODEX_NAME = "The First Codex"
# the drawer types an item can be filed in (`kinds.ENTRY_DRAWER_TYPES`)
ITEM_DRAWERS = ("beliefs", "practices", "knowledge", "structure")


class ReplayClient(harness.RecordingClient):
    """The recording client, answering its first calls from an earlier
    run's recorded replies (`replay`: `[(prompt, reply)]`) instead of the
    model, then calling the model as usual: a run that failed part way is
    resumed without asking the model again. The first prompt that differs
    from the recorded one ends the replay. A replayed call is recorded
    with `replayed`."""

    replay: list[tuple[str, str]]

    async def send_prompt(self, prompt, kind="conversation", *args, **kwargs):
        if not self.replay:
            return await super().send_prompt(prompt, kind, *args, **kwargs)
        recorded_prompt, response = self.replay[0]
        if str(prompt) != recorded_prompt:
            # the run has gone another way: the model from here on
            self.replay = []
            return await super().send_prompt(prompt, kind, *args, **kwargs)
        self.replay.pop(0)
        self.calls.append(
            {
                "kind": kind,
                "prompt": str(prompt),
                "response": response,
                "seconds": 0.0,
                "replayed": True,
            }
        )
        self.on_call()
        return response


class _Handler:
    """The websocket handler stand-in: no scene, replies collected."""

    scene = None

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def queue_put(self, data: dict) -> None:
        self.messages.append(data)


class Session:
    """The router, and what each action answered."""

    def __init__(self, plugin: WorldsPlugin, client: Any) -> None:
        self.plugin = plugin
        self.client = client
        self.failures: list[dict] = []

    async def send(self, action: str, **data: Any) -> dict:
        """Send `action`, wait for its background tasks (prose included),
        and return its reply's data; a failure reply raises."""

        handler = self.plugin.websocket_handler
        seen = len(handler.messages)
        await self.plugin.handle({"type": "worlds", "action": action, **data})
        while self.plugin.tasks:
            await asyncio.gather(*list(self.plugin.tasks), return_exceptions=True)
        new = handler.messages[seen:]
        for message in new:
            if message.get("type") == "worlds" and message.get("action") == action:
                return message["data"]
        raise RuntimeError(f"{action} failed: {new}")

    async def preview(self, action: str, **data: Any) -> dict:
        """A preview, asked again when it fails, as the owner would press
        the button again (up to 3 tries); each failure is recorded."""

        for attempt in range(3):
            try:
                return await self.send(action, **data)
            except RuntimeError as exc:
                self.failures.append(
                    {"action": action, "attempt": attempt + 1, "error": str(exc)}
                )
                if attempt == 2:
                    raise
        raise AssertionError("unreachable")

    async def stubs(self) -> list[dict]:
        return (await self.send("list_stubs", include_ignored=True))["stubs"]

    async def thing(self, thing_id: str) -> dict:
        return await self.send("get_thing", id=thing_id, at=None)

    def calls_since(self, before: int) -> list[dict]:
        return [
            {
                "kind": c["kind"],
                "seconds": c.get("seconds"),
                "prompt": c["prompt"],
                "reply": c["response"],
            }
            for c in self.client.calls[before:]
        ]


def _text(segments: list[dict]) -> str:
    return "".join(s["text"] for s in segments)


def summary(thing: dict) -> dict:
    """A thing payload as the owner reads it."""

    out: dict[str, Any] = {
        "id": thing["id"],
        "kind": thing["kind"],
        "name": thing["name"],
        "stub": thing["stub"] is not None,
        "aka": [a["name"] for a in thing.get("aka") or []],
        "part_of": thing.get("part_of"),
        "facts": [
            {
                "fact_id": f["fact_id"],
                "category": f["category"],
                "text": _text(f["segments"]),
                "held_by": (f.get("held_by") or {}).get("name"),
                "since": (f.get("valid_from") or {}).get("label")
                if isinstance(f.get("valid_from"), dict)
                else None,
            }
            for f in thing["facts"]
        ],
        "entry_timeline": [
            {
                "date": (line["date"] or {}).get("label"),
                "from": line["owner_name"],
                "here": line["here"],
                "text": _text(line["segments"]),
                "disagrees_with": line["disagrees_with"],
            }
            for line in thing.get("entry_timeline") or []
        ],
    }
    sphere = thing.get("sphere")
    if sphere:
        out["sphere"] = {
            "template": sphere["template"],
            "drawers": [
                {
                    "id": d["id"],
                    "type": d["type"],
                    "title": d["title"],
                    "items": [
                        {
                            "thing_id": i["thing_id"],
                            "name": i["name"],
                            "text": _text(i["segments"]),
                            "stub": i["stub"],
                        }
                        for i in d["items"]
                    ],
                }
                for d in sphere["drawers"]
            ],
        }
    return out


def preview_record(preview: dict) -> dict:
    """What a create preview showed the owner, in its sections."""

    return {
        "name": preview.get("name"),
        "part_of": preview.get("part_of"),
        "facts": [
            {
                "category": f["category"],
                "text": f["text"],
                "ticked": f.get("ticked"),
                "repeat_of": f.get("repeat_of"),
                "held_by": f.get("held_by_name"),
            }
            for f in preview.get("facts", [])
        ],
        "elsewhere": [
            {
                "target": e["target_name"],
                "target_id": e["target_id"],
                "new": (e.get("new") or {}).get("kind") if e.get("new") else None,
                "same_as": [
                    o.get("name") for o in (e.get("new") or {}).get("same_as") or []
                ],
                "category": e["category"],
                "text": e["text"],
                "ticked": e["ticked"],
                "repeat_of": e.get("repeat_of"),
            }
            for e in preview.get("elsewhere", [])
        ],
        "new_names": [
            {
                "name": n["name"],
                "kind": n["kind"],
                "template": n.get("template"),
                "same_as": [
                    {"name": o.get("name"), "reason": o.get("reason")}
                    for o in n.get("same_as") or []
                ],
                "part_of": n.get("part_of"),
            }
            for n in preview.get("new_names", [])
        ],
        "same_as": preview.get("same_as"),
        "verdict": preview.get("verdict"),
        "move_in": preview.get("move_in"),
        "refile": preview.get("refile"),
    }


def sphere_preview_record(preview: dict) -> dict:
    return {
        "name": preview["name"],
        "summary": (preview.get("prose") or {}).get("description"),
        "timeline": [
            {"category": f["category"], "text": f["text"], "since": f.get("since")}
            for f in preview["facts"]
        ],
        "drawers": preview["drawers"],
        "items": preview["items"],
        "adopted": preview.get("adopted"),
        "new_names": preview_record(preview)["new_names"],
        "elsewhere": preview_record(preview)["elsewhere"],
        "same_as": preview.get("same_as"),
        "refile": preview.get("refile"),
    }


async def expand(
    session: Session, label: str, stub_id: str, kind: str, extra: str = ""
) -> tuple[dict, dict]:
    """A stub's preview from its suggested prompt (plus the owner's
    `extra` words), accepted as it came. Returns the step and the preview."""

    suggestion = await session.send("stub_suggestion", id=stub_id)
    prompt = suggestion["prompt"] + extra
    before = len(session.client.calls)
    started = time.monotonic()
    preview = await session.preview(
        "preview_thing", kind=kind, prompt=prompt, fields={}, stub_id=stub_id, picks={}
    )
    step = {
        "step": label,
        "action": "preview_thing",
        "kind": kind,
        "prompt": prompt,
        "preview": preview_record(preview),
    }
    return step, preview | {"_before": before, "_started": started}


async def accept(session: Session, step: dict, preview: dict, **extra: Any) -> dict:
    before, started = preview.pop("_before"), preview.pop("_started")
    thing = await session.send("accept_preview", preview=preview, **extra)
    step["notes"] = thing.get("notes")
    step["seconds"] = round(time.monotonic() - started, 1)
    step["calls"] = session.calls_since(before)
    step["thing"] = summary(thing)
    return thing


async def make_sphere(
    session: Session,
    label: str,
    template: str,
    prompt: str,
    stub_id: str | None = None,
) -> tuple[dict, dict]:
    before = len(session.client.calls)
    started = time.monotonic()
    preview = await session.preview(
        "preview_sphere",
        template=template,
        prompt=prompt,
        fields={},
        stub_id=stub_id,
        picks={},
    )
    sphere = await session.send("accept_sphere", preview=preview)
    step = {
        "step": label,
        "action": "preview_sphere",
        "template": template,
        "prompt": prompt,
        "seconds": round(time.monotonic() - started, 1),
        "preview": sphere_preview_record(preview),
        "notes": sphere.get("notes"),
        "calls": session.calls_since(before),
        "thing": summary(sphere),
    }
    return step, sphere


def drawers(thing: dict, type_: str) -> list[dict]:
    return [d for d in thing["sphere"]["drawers"] if d["type"] == type_]


def named_items(thing: dict, type_: str | None = None) -> list[tuple[dict, dict]]:
    """`(drawer, item)` for each item with an entry of its own."""

    return [
        (d, i)
        for d in thing["sphere"]["drawers"]
        if type_ is None or d["type"] == type_
        for i in d["items"]
        if i["thing_id"]
    ]


async def snapshot(session: Session) -> dict[str, list[str]]:
    """Each live thing's facts as they read: to see what a step changed."""

    world = session.plugin.world
    view = world.view()
    return {t.id: sorted(view.render(f.text) for f in t.facts) for t in view.things()}


def changed(before: dict, after: dict) -> dict:
    view = {}
    for thing_id in set(before) | set(after):
        old, new = set(before.get(thing_id, [])), set(after.get(thing_id, []))
        if old != new:
            view[thing_id] = {"added": sorted(new - old), "removed": sorted(old - new)}
    return view


async def run(session: Session, results: dict, save) -> None:
    steps = results["steps"]
    world = session.plugin.world
    names = lambda: {t.id: world.view().name_of(t.id) for t in world.view().things()}  # noqa: E731

    # 1. owl-folk, then the Tsardom as a nation sphere from its stub
    before = len(session.client.calls)
    preview = await session.preview(
        "preview_thing", kind="species", prompt=SPECIES_PROMPT, fields={}, picks={}
    )
    owl = await session.send("accept_preview", preview=preview)
    steps.append(
        {
            "step": "owl-folk",
            "preview": preview_record(preview),
            "calls": session.calls_since(before),
            "thing": summary(owl),
        }
    )
    save()
    tsardom_stub = next(
        (
            s
            for s in await session.stubs()
            if s["name"].casefold() == TSARDOM.casefold()
        ),
        None,
    )
    if tsardom_stub is None:
        raise RuntimeError(f"no {TSARDOM} stub: judge by hand")
    suggestion = await session.send("stub_suggestion", id=tsardom_stub["id"])
    step, tsardom = await make_sphere(
        session,
        "tsardom",
        "nation",
        suggestion["prompt"] + TSARDOM_EXTRA,
        stub_id=tsardom_stub["id"],
    )
    steps.append(step)
    save()
    tsardom_id = tsardom["id"]

    # 2. the church: the stub the Tsardom's church mention names (any
    # kind but a place or person: the owner makes it a sphere), else a
    # sphere stub guessed as a religion, else a stub that reads as a faith
    stubs = {s["id"]: s for s in await session.stubs() if not s["ignored"]}
    church_id = None
    for stub_id, stub in stubs.items():
        if re.search(r"\bchurch\b", stub["name"], re.I) and stub["kind"] not in (
            "place",
            "character",
        ):
            church_id = stub_id
            results["church_guess"] = f"the church mention: a {stub['kind']} stub"
            break
    if church_id is None:
        for stub_id, stub in stubs.items():
            payload = await session.thing(stub_id)
            if (
                stub["kind"] == "sphere"
                and (payload.get("sphere") or {}).get("template") == "religion"
            ):
                church_id = stub_id
                results["church_guess"] = "sphere stub guessed as a religion"
                break
    if church_id is None:
        for stub_id, stub in stubs.items():
            if FAITH.search(stub["name"]) and stub["kind"] not in (
                "place",
                "character",
            ):
                church_id = stub_id
                results["church_guess"] = f"a {stub['kind']} stub, made a sphere"
                break
    if church_id is None:
        raise RuntimeError("the Tsardom names no church: judge by hand")
    results["religion_stubs"] = [
        s["name"] for s in stubs.values() if s["kind"] == "sphere"
    ]
    suggestion = await session.send("stub_suggestion", id=church_id)
    step, church = await make_sphere(
        session, "church", "religion", suggestion["prompt"], stub_id=church_id
    )
    steps.append(step)
    save()

    # 3. a doctrine: the Divine Right from the church's beliefs drawer, or,
    # when the church has none, made there by the owner from a prompt
    beliefs = named_items(church, "beliefs")
    pick = next(((d, i) for d, i in beliefs if DOCTRINE.search(i["name"])), None)
    snap = await snapshot(session)
    if pick is not None:
        doctrine_id = pick[1]["thing_id"]
        doctrine_kind = (await session.thing(doctrine_id))["kind"]
        results["doctrine"] = {"name": pick[1]["name"], "how": "expanded"}
        step, preview = await expand(session, "doctrine", doctrine_id, doctrine_kind)
        doctrine = await accept(session, step, preview, into_stub=doctrine_id)
    else:
        drawer = next(iter(drawers(church, "beliefs")), None)
        if drawer is None:
            raise RuntimeError("the church has no beliefs drawer: judge by hand")
        prompt = (
            f"The Divine Right of the Tsar: the doctrine of {church['name']} "
            "that the Tsar rules by divine will."
        )
        results["doctrine"] = {"name": "The Divine Right of the Tsar", "how": prompt}
        before = len(session.client.calls)
        started = time.monotonic()
        preview = await session.preview(
            "preview_thing",
            kind="lore",
            prompt=prompt,
            fields={"part_of": {"sphere": church_id, "drawer": drawer["id"]}},
            picks={church["name"]: church_id},
        )
        step = {
            "step": "doctrine",
            "action": "preview_thing",
            "kind": "lore",
            "prompt": prompt,
            "preview": preview_record(preview),
        }
        preview |= {"_before": before, "_started": started}
        doctrine = await accept(session, step, preview)
        doctrine_id = doctrine["id"]
    step["world_changes"] = changed(snap, await snapshot(session))
    step["names"] = names()
    steps.append(step)
    save()

    # 4. the army: a regiment the Tsardom names; the owner names its outer
    # body and ticks the other regiments' re-file rows
    tsardom = await session.thing(tsardom_id)
    # a regiment: a named item of a structure drawer, by its name
    regiments = [
        (d, i)
        for d, i in named_items(tsardom, "structure")
        if MILITARY.search(i["name"])
    ]
    results["regiments"] = [[d["title"], i["name"]] for d, i in regiments]
    if not regiments:
        # the owner writes the old run's line into the Tsardom by hand,
        # makes its two regiments stubs and files them in its structure
        # drawer, where the old run's regiments sat
        structure = next(iter(drawers(tsardom, "structure")), None)
        if structure is None:
            raise RuntimeError("the Tsardom has no structure drawer: judge by hand")
        text = (
            "The Tsardom keeps a standing army of owl-folk, organized into "
            "regiments such as the White Talon and the Frosted Wing."
        )
        await session.send(
            "add_fact", thing_id=tsardom_id, category="general", text=text, picks={}
        )
        tsardom = await session.thing(tsardom_id)
        fact = next(f for f in tsardom["facts"] if _text(f["segments"]) == text)
        for phrase in ("White Talon", "Frosted Wing"):
            await session.send(
                "make_stub",
                thing_id=tsardom_id,
                fact_id=fact["fact_id"],
                text=phrase,
                kind="lore",
            )
            stub = next(s for s in await session.stubs() if s["name"] == phrase)
            await session.send(
                "set_part_of",
                thing_id=stub["id"],
                sphere_id=tsardom_id,
                drawer_id=structure["id"],
            )
        results["notes"].append(
            f"the Tsardom named no regiment: written by hand ({text}); both "
            f"stubs filed in {structure['title']}"
        )
        tsardom = await session.thing(tsardom_id)
        regiments = [
            (d, i)
            for d, i in named_items(tsardom)
            if i["name"] in ("White Talon", "Frosted Wing")
        ]
        results["regiments"] = [[d["title"], i["name"]] for d, i in regiments]
    drawer, regiment = regiments[0]
    regiment_kind = (await session.thing(regiment["thing_id"]))["kind"]
    snap = await snapshot(session)
    step, preview = await expand(
        session, "regiment", regiment["thing_id"], regiment_kind
    )
    framed = await session.send(
        "add_outer_body",
        preview_type="create",
        preview={k: v for k, v in preview.items() if not k.startswith("_")},
        row_name=preview["name"],
        outer={
            "name": ARMY,
            "template": "order",
            "part_of": {"sphere": tsardom_id, "drawer": drawer["id"]},
        },
    )
    framed_preview = framed["preview"]
    step["outer_body"] = {
        "part_of": framed_preview.get("part_of"),
        "refile": framed_preview.get("refile"),
        "new_names": preview_record(framed_preview)["new_names"],
    }
    for row in framed_preview.get("refile") or []:
        name = world.view().name_of(row["thing_id"]) or ""
        row["ticked"] = bool(MILITARY.search(name))
    framed_preview["_before"], framed_preview["_started"] = (
        preview["_before"],
        preview["_started"],
    )
    await accept(session, step, framed_preview, into_stub=regiment["thing_id"])
    step["world_changes"] = changed(snap, await snapshot(session))
    army = next((s for s in await session.stubs() if s["name"] == ARMY), None)
    step["army"] = summary(await session.thing(army["id"])) if army else None
    step["tsardom_after"] = summary(await session.thing(tsardom_id))
    steps.append(step)
    save()

    # 5. runic magic, and its children
    step, rune = await make_sphere(session, "runeweaving", "field", RUNEWEAVING_PROMPT)
    steps.append(step)
    save()
    rune_id = rune["id"]
    results["runeweaving_id"] = rune_id
    children: list[tuple[str, dict]] = []
    practices = named_items(rune, "practices")
    places = named_items(rune, "places")
    texts = [(d, i) for d, i in named_items(rune) if CODEX.search(i["name"])]
    for label, found in (("technique", practices), ("site", places), ("codex", texts)):
        if found:
            children.append((label, found[0][1]))
        else:
            results["notes"].append(f"Runeweaving has no {label} item")
    if not texts:
        # the owner makes the codex: a stub filed in its knowledge drawer
        # (else its first drawer an item goes in), expanded like the others
        home = next(
            iter(
                drawers(rune, "knowledge")
                or [d for d in rune["sphere"]["drawers"] if d["type"] in ITEM_DRAWERS]
            ),
            None,
        )
        text = f"{CODEX_NAME} is the oldest book of the art, where its runes were first written down."
        await session.send(
            "add_fact", thing_id=rune_id, category="about", text=text, picks={}
        )
        rune = await session.thing(rune_id)
        fact = next(f for f in rune["facts"] if _text(f["segments"]) == text)
        await session.send(
            "make_stub",
            thing_id=rune_id,
            fact_id=fact["fact_id"],
            text=CODEX_NAME,
            kind="item",
        )
        stub = next(s for s in await session.stubs() if s["name"] == CODEX_NAME)
        await session.send(
            "set_part_of", thing_id=stub["id"], sphere_id=rune_id, drawer_id=home["id"]
        )
        results["notes"].append(
            f"no codex item: the owner wrote {text!r} on Runeweaving, made "
            f"{CODEX_NAME} a stub and filed it in {home['title']}"
        )
        children.append(("codex", {"thing_id": stub["id"], "name": CODEX_NAME}))
    site_id = None
    for label, item in children:
        kind = (await session.thing(item["thing_id"]))["kind"]
        snap = await snapshot(session)
        step, preview = await expand(session, label, item["thing_id"], kind)
        await accept(session, step, preview, into_stub=item["thing_id"])
        step["world_changes"] = changed(snap, await snapshot(session))
        step["names"] = names()
        steps.append(step)
        save()
        if label == "site":
            site_id = item["thing_id"]

    # a Fill of its places drawer: same-thing offers on its new items
    rune = await session.thing(rune_id)
    places_drawer = next(iter(drawers(rune, "places")), None)
    if places_drawer is not None:
        before = len(session.client.calls)
        snap = await snapshot(session)
        filled = await session.preview(
            "fill_drawer", sphere_id=rune_id, drawer_id=places_drawer["id"]
        )
        after = await session.send(
            "accept_fill",
            sphere_id=rune_id,
            drawer_id=places_drawer["id"],
            items=filled["items"],
            elsewhere=filled.get("elsewhere") or [],
            new_names=filled.get("new_names") or [],
            refile=filled.get("refile") or [],
        )
        steps.append(
            {
                "step": f"fill {places_drawer['title']}",
                "items": filled["items"],
                "elsewhere": preview_record(filled)["elsewhere"],
                "new_names": preview_record(filled)["new_names"],
                "notes": after.get("notes"),
                "calls": session.calls_since(before),
                "world_changes": changed(snap, await snapshot(session)),
                "thing": summary(after),
            }
        )
        save()

    # a more specific place inside the site: its facts may move in
    if site_id is not None:
        site = await session.thing(site_id)
        prompt = (
            f"The deepest inscription chambers inside {site['name']}, where "
            "the oldest runes are carved"
        )
        before = len(session.client.calls)
        started = time.monotonic()
        snap = await snapshot(session)
        preview = await session.preview(
            "preview_thing",
            kind="place",
            prompt=prompt,
            fields={"parent": site_id},
            picks={site["name"]: site_id},
        )
        step = {
            "step": "inner place",
            "prompt": prompt,
            "preview": preview_record(preview),
        }
        preview |= {"_before": before, "_started": started}
        await accept(session, step, preview)
        step["world_changes"] = changed(snap, await snapshot(session))
        step["site_after"] = summary(await session.thing(site_id))
        steps.append(step)
        save()

    # the merge runs after the session (`--merge`), on a pair picked by
    # hand from these candidates: a pair picked by code risked merging a
    # god into its church
    view = world.view()
    index = name_index(view)
    results["same_pairs"] = [
        [view.name_of(state.id), view.name_of(found.thing_id), found.reason]
        for state in view.things()
        for found in same_candidates(
            view,
            view.name_of(state.id) or "",
            near_ids=[],
            exclude=[state.id],
            index=index,
        )
    ]
    save()

    # 6. Runeweaving's timeline
    rune = await session.thing(rune_id)
    steps.append({"step": "timeline", "thing": summary(rune)})
    save()

    # 7. a scene where the church matters, with a held fact in play
    church = await session.thing(church_id)
    doctrine = await session.thing(doctrine_id)
    own = [f for f in doctrine["facts"] if f["category"] != "summary"]
    belief = next(
        (
            f
            for f in own
            if re.search(r"light|divine|god|chosen|blessed", _text(f["segments"]), re.I)
        ),
        own[0] if own else None,
    )
    if belief is not None:
        await session.send(
            "set_held_by",
            thing_id=doctrine_id,
            fact_id=belief["fact_id"],
            holder_id=church_id,
        )
        results["held"] = _text(belief["segments"])
    holy = next(iter(named_items(church, "places")), None)
    place_phrase = f" at {holy[1]['name']}" if holy else ""
    scene_prompt = (
        f"A young runeweaver is summoned{place_phrase}, where a priest of "
        f"{church['name']} questions her about {doctrine['name']}"
    )
    matched = await session.send("match_names", text=scene_prompt, at=None)
    picks = {
        m["text"]: m["candidates"][0]["id"]
        for m in matched["matches"]
        if m["candidates"] and not m.get("suggested")
    }
    before = len(session.client.calls)
    plan = await session.preview(
        "plan_scene",
        prompt=scene_prompt,
        picks=picks,
        start=WorldDate.of(PRESENT).model_dump(),
    )
    setup = plan["setup"]
    snap = await snapshot(session)
    started = await session.send("start_scene", setup=setup)
    scene_id = started["scene_id"]
    record = world.scenes().get(scene_id)
    block = world_context_block(world, record, WorldDate.of(PRESENT))
    scene_step: dict[str, Any] = {
        "step": "scene",
        "prompt": scene_prompt,
        "picks": picks,
        "setup": setup,
        "calls": session.calls_since(before),
        "start_changes": changed(snap, await snapshot(session)),
        "world_block": block,
        "turns": [],
    }
    steps.append(scene_step)
    save()
    directions = [
        "The priest opens with the church's teaching and asks the runeweaver "
        "whether she accepts it.",
        "The runeweaver answers carefully; the priest presses her on the "
        "Tsar's right to rule.",
    ]
    scene = await harness._load(world, scene_id, session.client, memory=False)
    narrator = instance.get_agent("narrator")
    try:
        with ActiveScene(scene):
            for direction in directions:
                before = len(session.client.calls)
                text = await narrator.progress_story(narrative_direction=direction)
                await scene.push_history([NarratorMessage(text, source="ai")])
                scene_step["turns"].append(
                    {
                        "direction": direction,
                        "output": text,
                        "calls": session.calls_since(before),
                    }
                )
                save()
    finally:
        close_world_scene(scene)

    results["final"] = [
        summary(await session.thing(t.id)) for t in world.view().things()
    ]


async def main(out: Path, label: str, root: Path, replay: str | None) -> None:
    harness._quiet_loading(False)
    embedding = TrigramEmbeddingFunction()
    MockMemoryAgent.embedding_function = property(lambda self: embedding)
    doc: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {"probe": "curation-flow", "runs": []}
    )
    client = ReplayClient(name="KoboldCpp")
    client.calls = []
    client.replay = (
        [
            (c["prompt"], c["response"])
            for c in next(r for r in doc["runs"] if r["label"] == replay)["calls"]
        ]
        if replay
        else []
    )
    await client.status()
    results: dict[str, Any] = {
        "label": label,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "model": client.model_name,
        "world_root": str(root),
        "replayed_from": replay,
        "notes": [],
        "steps": [],
        "calls": client.calls,
    }
    doc["runs"] = [r for r in doc["runs"] if r.get("label") != label] + [results]

    def save() -> None:
        out.write_text(
            json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n"
        )

    client.on_call = save
    bootstrap_scene(MockScene())
    for agent in instance.AGENTS.values():
        agent.client = client

    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    plugin = WorldsPlugin(_Handler())
    plugin.worlds_root = root
    session = Session(plugin, client)
    created = await session.send(
        "create_world", name="Moscavia curation", present_year=PRESENT
    )
    results["world_id"] = created.get("id") if isinstance(created, dict) else None
    started = time.monotonic()
    try:
        await run(session, results, save)
    except Exception as exc:
        results["error"] = repr(exc)
        raise
    finally:
        results["minutes"] = round((time.monotonic() - started) / 60, 1)
        results["failures"] = session.failures
        save()
        plugin.disconnect()


async def merge_main(
    out: Path, label: str, world_dir: Path, from_name: str, into_name: str
) -> None:
    """Merge `from_name` into `into_name` in the run's kept world, through
    the router as the merge screen does (the defaults: every pair keeps
    both, every link's words added as other names), and record it, with
    Runeweaving's timeline after, as steps of run `label`. The prose
    refresh the merge schedules asks the model."""

    harness._quiet_loading(False)
    doc = json.loads(out.read_text())
    results = next(r for r in doc["runs"] if r["label"] == label)
    client = harness.RecordingClient(name="KoboldCpp")
    client.calls = []
    await client.status()

    def save() -> None:
        out.write_text(
            json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n"
        )

    client.on_call = save
    bootstrap_scene(MockScene())
    for agent in instance.AGENTS.values():
        agent.client = client
    os.chdir(world_dir.parent)
    plugin = WorldsPlugin(_Handler())
    plugin.worlds_root = world_dir.parent
    session = Session(plugin, client)
    await session.send("open_world", path=str(world_dir))
    try:
        view = plugin.world.view()
        ids = {view.name_of(t.id): t.id for t in view.things()}
        from_id, into_id = ids[from_name], ids[into_name]
        merge = await session.send("preview_merge", from_id=from_id, into_id=into_id)
        merged = await session.send(
            "accept_merge", preview=merge["preview"], main_name=into_name
        )
        results["steps"].append(
            {
                "step": "merge",
                "from": from_name,
                "into": into_name,
                "preview": merge["preview"],
                "notes": merged.get("notes"),
                "links": merged.get("links"),
                "aka_added": merged.get("aka_added"),
                "facts_moved": merged.get("facts_moved"),
                "calls": session.calls_since(0),
                "thing": summary(merged["into"]),
            }
        )
        rune_id = results.get("runeweaving_id")
        if rune_id:
            results["steps"].append(
                {
                    "step": "timeline after merge",
                    "thing": summary(await session.thing(rune_id)),
                }
            )
        results["final"] = [
            summary(await session.thing(t.id)) for t in plugin.world.view().things()
        ]
    finally:
        save()
        plugin.disconnect()


# --- scoring (code only, no model) ---------------------------------------------


def score(world_dir: Path, threshold: float) -> dict:
    """Restatements at `threshold` and same-thing pairs in a world (a temp
    copy is opened), with every thing's facts, for judging by hand."""

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "world"
        shutil.copytree(world_dir, target)
        world = World.open(target)
        view = world.view()
        facts = []
        for state in view.things():
            for fact in state.facts:
                facts.append(
                    {
                        "fact_id": fact.fact_id,
                        "owner": view.name_of(state.id),
                        "owner_id": state.id,
                        "category": fact.category,
                        "text": view.render(fact.text),
                        "words": len(content_words(view.render(fact.text))),
                    }
                )
        repeats = []
        for a in facts:
            best = None
            for b in facts:
                if a["fact_id"] == b["fact_id"]:
                    continue
                s = overlap(a["text"], b["text"])
                if s >= threshold and (best is None or s > best[0]):
                    best = (s, b)
            if best is not None:
                repeats.append(
                    {
                        "fact": a["text"],
                        "owner": a["owner"],
                        "category": a["category"],
                        "same_owner": best[1]["owner_id"] == a["owner_id"],
                        "restates": best[1]["text"],
                        "restates_owner": best[1]["owner"],
                        "score": round(best[0], 2),
                    }
                )
        # groups of facts that say the same thing: linked when either one's
        # words are mostly in the other; each group past its first fact is
        # a redundant copy
        parent = {f["fact_id"]: f["fact_id"] for f in facts}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i, a in enumerate(facts):
            for b in facts[i + 1 :]:
                if (
                    max(overlap(a["text"], b["text"]), overlap(b["text"], a["text"]))
                    >= threshold
                ):
                    parent[find(a["fact_id"])] = find(b["fact_id"])
        groups: dict[str, list[dict]] = {}
        for f in facts:
            groups.setdefault(find(f["fact_id"]), []).append(f)
        clusters = [
            [
                {"owner": f["owner"], "category": f["category"], "text": f["text"]}
                for f in g
            ]
            for g in groups.values()
            if len(g) > 1
        ]
        index = name_index(view)
        pairs = set()
        for state in view.things():
            for found in same_candidates(
                view,
                view.name_of(state.id) or "",
                near_ids=[],
                exclude=[state.id],
                index=index,
            ):
                pair = tuple(
                    sorted([view.name_of(state.id), view.name_of(found.thing_id)])
                )
                pairs.add((pair, found.reason))
        things = [
            {
                "name": view.name_of(t.id),
                "kind": t.kind,
                "template": t.fields.get("template"),
                "stub": t.is_stub,
                "part_of": view.name_of(
                    (t.fields.get("part_of") or {}).get("sphere") or ""
                )
                if t.fields.get("part_of")
                else None,
                "facts": [view.render(f.text) for f in t.facts],
            }
            for t in view.things()
        ]
        world.close()
    return {
        "threshold": threshold,
        "facts": len(facts),
        "things": len(things),
        "stubs": sum(1 for t in things if t["stub"]),
        "restating_facts": len(repeats),
        "redundant_copies": sum(len(c) - 1 for c in clusters),
        "clusters": sorted(clusters, key=len, reverse=True),
        "repeats": repeats,
        "same_pairs": sorted([list(p) + [r] for p, r in pairs]),
        "world": things,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path, nargs="?")
    parser.add_argument("--label", default="run 1")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--replay",
        metavar="LABEL",
        default=None,
        help="answer the first calls from that run's recorded replies",
    )
    parser.add_argument("--score", type=Path, default=None, metavar="WORLD_DIR")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument(
        "--merge",
        nargs=3,
        metavar=("WORLD_DIR", "FROM", "INTO"),
        default=None,
        help="merge FROM into INTO in run --label's kept world",
    )
    args = parser.parse_args()
    if args.merge is not None:
        world_dir, from_name, into_name = args.merge
        asyncio.run(
            merge_main(
                args.out.resolve(),
                args.label,
                Path(world_dir).resolve(),
                from_name,
                into_name,
            )
        )
    elif args.score is not None:
        result = score(args.score.resolve(), args.threshold)
        text = json.dumps(result, indent=1, ensure_ascii=False, default=str)
        if args.out is not None:
            args.out.write_text(text + "\n")
        else:
            print(text)
    else:
        if args.out is None or args.root is None:
            parser.error("a session needs OUT.json and --root")
        asyncio.run(
            main(args.out.resolve(), args.label, args.root.resolve(), args.replay)
        )
