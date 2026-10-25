"""Throwaway probe: the owner's spheres session on the real model
(fantasymate spheres, Task 10).

Drives the same path the world screens use -- the real `worlds` router
(`talemate.server.worlds.WorldsPlugin`) and `worldplay` -- with Talemate's
own KoboldCpp client (the `--ai` app's config, as `probe_heritage_play`
sets it up) serving every agent. Nothing is stubbed and no fixed reply is
used (no `TALEMATE_TEST_FIXED_SPHERE`): every create, core, Fill, plan and
turn is the model's.

The session, in a fresh world (present year 1020), following the spec's
"How the owner will judge it":

1. **Owl-folk**, a species, from the owner's plan B prompt naming the
   Tsardom of Moscavia; then **the Tsardom**, expanded from its stub with
   its suggested prompt (`stub_suggestion`) and the owner's words "It has
   a state church." (`TSARDOM_EXTRA`: run 1, without them, named no
   faith).
2. **Its religion:** the stub the Tsardom's facts name for its faith
   (a `sphere` stub guessed as a religion, if the guess worked; else the
   first stub whose name or mention reads as a faith, which the owner
   would "Make it a sphere..." by hand). Recorded either way.
3. **The council first:** a stub the Tsardom names for a council of
   elders (or synod), expanded as its stub's kind -- lore through
   `preview_thing`, a sphere stub through `preview_sphere` -- and its
   `part_of` recorded; then **the religion**, expanded as a religion
   sphere from its stub, and whether the council was adopted.
   If the Tsardom named no council, the owner writes one into the
   Tsardom by hand (`add_fact`, then `make_stub`), and that's recorded.
4. **Fill** the religion's first beliefs drawer and its first practices
   drawer, every item kept (`accept_fill`); its summary before and after.
5. **A character** with ties: Vasha, an owl-folk courier raised in the
   religion who keeps one of its rites but scorns one of its doctrines
   (both named from what the core wrote); the prompt's names are picked
   as the name highlight offers them (`match_names`).
6. **A scene** at the religion's first holy site, planned by the model
   through the router (`plan_scene`, the holy site and Vasha picked),
   started (`start_scene`), loaded through its `world://` target and
   played for two narrator turns (`progress_story`) as
   `probe_heritage_play` plays them. The World block is recorded as
   `context.world_context_block` builds it, and each turn's prompt.

After every step the payloads (the thing, a sphere's drawers and items,
part of, ties, stubs) are recorded, with every call's prompt and reply,
to the output JSON after every call. Judging is by hand from that JSON.

What's approximated: the world index (scene planning's hits) uses the
tests' trigram embedding rather than the app's ChromaDB one; agents run
with their default config; no frontend.

Not a test: it calls the network. The owner approved this plan's Skyfall
tests (one GPU: calls run one after another)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_spheres_flow.py OUT.json \\
        [--label NAME] [--until tsardom] [--replay LABEL]'

`--label` names the run; an existing OUT.json keeps its earlier runs under
`runs`. `--until tsardom` stops after the Tsardom (re-running that step
alone after a wording change). `--replay LABEL` answers every call before
the scene from that run's recorded replies, so only the scene (planning,
its stub previews and the turns) calls the model again. Findings: docs/superpowers/probes/2026-10-22-spheres-flow.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
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
from talemate.worldplay.context import world_context_block  # noqa: E402
from talemate.worldplay.persistence import close_world_scene  # noqa: E402

from conftest import MockMemoryAgent, MockScene, bootstrap_scene  # noqa: E402
from world.embedding import TrigramEmbeddingFunction  # noqa: E402

PRESENT = 1020
SPECIES_PROMPT = (
    "Owl-folk: owl people. Everyone in the Tsardom of Moscavia became this "
    "race suddenly one day 6 years ago."
)
TSARDOM = "Tsardom of Moscavia"
FAITH = re.compile(
    r"church|faith|religio|worship|creed|\bcult\b|temple|priest|\bgods?\b|"
    r"goddess|divine|holy|sacred",
    re.I,
)
# the owner's words added to the Tsardom's suggested prompt: run 1, from
# the suggestion alone, named no faith at all
TSARDOM_EXTRA = " It has a state church."
COUNCIL = re.compile(r"council|elders|synod|conclave", re.I)
SCAN = {
    "religion": None,  # the religion's name, filled in at run time
    "council": r"council|\belders?\b",
    "rite": None,  # the rite the character keeps
    "doctrine": r"\bdoctrine|\bteach",
    "faithful": r"\bfaithful\b|\bbeliever|\bworship|\bpray",
}


class ReplayClient(harness.RecordingClient):
    """The recording client, answering its first calls from an earlier
    run's recorded replies (`replay`: `[(prompt, reply)]`) instead of the
    model, then calling the model as usual. A replayed call is recorded
    with `replayed` and whether its prompt matched the recorded one."""

    replay: list[tuple[str, str]]

    async def send_prompt(self, prompt, kind="conversation", *args, **kwargs):
        if not self.replay:
            return await super().send_prompt(prompt, kind, *args, **kwargs)
        recorded_prompt, response = self.replay.pop(0)
        self.calls.append(
            {
                "kind": kind,
                "prompt": str(prompt),
                "response": response,
                "seconds": 0.0,
                "replayed": True,
                "prompt_matches": str(prompt) == recorded_prompt,
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

    async def send(self, action: str, **data: Any) -> dict:
        """Send `action`, wait for its background task, and return its
        reply's data; a failure reply raises."""

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

    async def stubs(self) -> list[dict]:
        return (await self.send("list_stubs", include_ignored=True))["stubs"]

    async def thing(self, thing_id: str) -> dict:
        return await self.send("get_thing", id=thing_id, at=None)

    def calls_since(self, before: int) -> list[dict]:
        return [
            {"kind": c["kind"], "prompt": c["prompt"], "reply": c["response"]}
            for c in self.client.calls[before:]
        ]


def _text(segments: list[dict]) -> str:
    return "".join(s["text"] for s in segments)


def summary(thing: dict) -> dict:
    """A thing payload as the owner reads it: name, kind, facts as text
    with their links, its sphere (drawers and items, timeline, people),
    what it's part of, and its ties."""

    out: dict[str, Any] = {
        "id": thing["id"],
        "kind": thing["kind"],
        "name": thing["fields"].get("name"),
        "stub": thing["stub"],
        "aka": [a["name"] for a in thing.get("aka") or []],
        "facts": [
            {
                "category": fact["category"],
                "text": _text(fact["segments"]),
                "links": [
                    [s["text"], s["ref"], s["stub"]]
                    for s in fact["segments"]
                    if s["ref"]
                ],
            }
            for fact in thing["facts"]
        ],
        "part_of": thing.get("part_of"),
    }
    sphere = thing.get("sphere")
    if sphere:
        out["sphere"] = {
            "template": sphere["template"],
            "agent": sphere["agent"],
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
            "people": [
                {"name": p["name"], "role": p["role"]} for p in sphere["people"]
            ],
            "timeline": [
                {
                    "date": (t["date"] or {}).get("label"),
                    "text": _text(t["segments"]),
                }
                for t in sphere["timeline"]
            ],
        }
    if thing.get("ties"):
        out["ties"] = [
            {
                "sphere": tie["sphere_name"],
                "role": tie["role"],
                "since": (tie["since"] or {}).get("label"),
                "exceptions": [_text(e["segments"]) for e in tie["exceptions"]],
            }
            for tie in thing["ties"]
        ]
    return out


def _named_stubs(thing: dict, stubs: list[dict]) -> list[dict]:
    """The live stubs the thing's facts name, in fact order."""

    live = {stub["id"]: stub for stub in stubs if not stub["ignored"]}
    return [live[s["id"]] for s in thing["named_stubs"] if s["id"] in live]


def _mention_of(thing: dict, stub_id: str) -> str | None:
    for fact in thing["facts"]:
        if any(s["ref"] == stub_id for s in fact["segments"]):
            return _text(fact["segments"])
    return None


async def _picks(session: Session, text: str) -> dict[str, str]:
    """The names in `text` as the name highlight offers them: each match
    that's no mere suggestion, its first candidate."""

    matched = await session.send("match_names", text=text, at=None)
    return {
        m["text"]: m["candidates"][0]["id"]
        for m in matched["matches"]
        if m["candidates"] and not m.get("suggested")
    }


async def expand_lore(
    session: Session, label: str, stub: dict, kind: str, extra: str = ""
) -> dict:
    """Expand a stub with `preview_thing` (its suggested prompt, plus the
    owner's `extra` words) and accept it into the stub."""

    suggestion = await session.send("stub_suggestion", id=stub["id"])
    suggestion["prompt"] += extra
    before = len(session.client.calls)
    started = time.monotonic()
    preview = await session.send(
        "preview_thing",
        kind=kind,
        prompt=suggestion["prompt"],
        fields={},
        stub_id=stub["id"],
        picks={},
    )
    thing = await session.send("accept_preview", preview=preview, into_stub=stub["id"])
    return {
        "step": label,
        "action": "preview_thing",
        "kind": kind,
        "prompt": suggestion["prompt"],
        "suggestion_context": suggestion["context"],
        "seconds": round(time.monotonic() - started, 1),
        "calls": session.calls_since(before),
        "preview": {
            "name": preview["name"],
            "facts": [
                {"category": f["category"], "text": f["text"]} for f in preview["facts"]
            ],
            "new_names": preview["new_names"],
            "part_of": preview.get("part_of"),
            "ties": preview.get("ties"),
        },
        "thing": summary(thing),
        "stubs_after": await session.stubs(),
    }


async def expand_sphere(
    session: Session, label: str, stub: dict, template: str
) -> dict:
    """Expand a stub as a sphere of `template` (`preview_sphere`, its
    suggested prompt) and accept it."""

    suggestion = await session.send("stub_suggestion", id=stub["id"])
    before = len(session.client.calls)
    started = time.monotonic()
    preview = await session.send(
        "preview_sphere",
        template=template,
        prompt=suggestion["prompt"],
        fields={},
        stub_id=stub["id"],
        picks={},
    )
    thing = await session.send("accept_sphere", preview=preview)
    return {
        "step": label,
        "action": "preview_sphere",
        "template": template,
        "prompt": suggestion["prompt"],
        "suggestion_context": suggestion["context"],
        "seconds": round(time.monotonic() - started, 1),
        "calls": session.calls_since(before),
        "preview": {
            "name": preview["name"],
            "summary": preview["prose"].get("description"),
            "timeline": [
                {"category": f["category"], "text": f["text"]} for f in preview["facts"]
            ],
            "drawers": preview["drawers"],
            "items": preview["items"],
            "adopted": preview["adopted"],
            "new_names": preview["new_names"],
            "context": preview["context"],
        },
        "thing": summary(thing),
        "stubs_after": await session.stubs(),
    }


def _first(sphere: dict, type_: str) -> dict | None:
    return next((d for d in sphere["sphere"]["drawers"] if d["type"] == type_), None)


def _item_phrase(drawer: dict | None, fallback: str) -> str:
    """A drawer's first named item, as the owner would write it."""

    for item in (drawer or {}).get("items", []):
        if item["thing_id"]:
            return item["name"]
    return fallback


async def run(session: Session, results: dict, save) -> None:
    steps = results["steps"]
    world = session.plugin.world

    # 1. the species, then the Tsardom from its stub
    before = len(session.client.calls)
    preview = await session.send(
        "preview_thing", kind="species", prompt=SPECIES_PROMPT, fields={}, picks={}
    )
    owl = await session.send("accept_preview", preview=preview)
    steps.append(
        {
            "step": "owl-folk",
            "calls": session.calls_since(before),
            "thing": summary(owl),
            "stubs_after": await session.stubs(),
        }
    )
    save()
    tsardom = next(
        (
            s
            for s in await session.stubs()
            if s["name"].casefold() == TSARDOM.casefold()
        ),
        None,
    )
    if tsardom is None:
        fact = next(f for f in owl["facts"] if "Moscavia" in _text(f["segments"]))
        phrase = TSARDOM if TSARDOM in _text(fact["segments"]) else "Moscavia"
        await session.send(
            "make_stub",
            thing_id=owl["id"],
            fact_id=fact["fact_id"],
            text=phrase,
            kind="place",
        )
        results["notes"].append(f"no {TSARDOM} stub: made by hand from {phrase!r}")
        tsardom = next(s for s in await session.stubs() if s["name"] == phrase)
    step = await expand_lore(session, "tsardom", tsardom, "place", TSARDOM_EXTRA)
    steps.append(step)
    save()
    tsardom_thing = await session.thing(tsardom["id"])
    named = _named_stubs(tsardom_thing, step["stubs_after"])
    results["tsardom_named_stubs"] = []
    for stub in named:
        payload = await session.thing(stub["id"])
        results["tsardom_named_stubs"].append(
            {
                "name": stub["name"],
                "kind": stub["kind"],
                "template": (payload.get("sphere") or {}).get("template"),
                "mention": _mention_of(tsardom_thing, stub["id"]),
            }
        )
    save()
    if results["until"] == "tsardom":
        return

    # 2. its religion: the sphere stub guessed as a religion, else the
    # first stub that reads as a faith
    religion = next(
        (
            s
            for s, seen in zip(named, results["tsardom_named_stubs"])
            if s["kind"] == "sphere" and seen["template"] == "religion"
        ),
        None,
    )
    if religion is not None:
        results["religion_guess"] = "sphere stub guessed as a religion"
    else:
        religion = next(
            (
                s
                for s in named
                if s["kind"] not in ("place", "character", "species", "race")
                and not COUNCIL.search(s["name"])
                and (
                    FAITH.search(s["name"])
                    or FAITH.search(_mention_of(tsardom_thing, s["id"]) or "")
                )
            ),
            None,
        )
        results["religion_guess"] = (
            f"not guessed as a religion: a {religion['kind']} stub"
            if religion
            else "no stub for the religion"
        )
    if religion is None:
        raise RuntimeError("the Tsardom names no religion: judge by hand")
    results["religion"] = {"id": religion["id"], "name": religion["name"]}
    save()

    # 3. the council first, then the religion
    # the religion's own council: one a fact names together with it
    def together(stub_id: str) -> bool:
        return any(
            {religion["id"], stub_id}
            <= {seg["ref"] for seg in fact["segments"] if seg["ref"]}
            for fact in tsardom_thing["facts"]
        )

    council = next(
        (
            s
            for s in named
            if s["id"] != religion["id"]
            and COUNCIL.search(s["name"])
            and together(s["id"])
        ),
        None,
    )
    if council is None:
        text = (
            f"The Council of Elders of {religion['name']} rules on its "
            "doctrine from the capital."
        )
        await session.send(
            "add_fact",
            thing_id=tsardom["id"],
            category="general",
            text=text,
            picks={religion["name"]: religion["id"]},
        )
        tsardom_thing = await session.thing(tsardom["id"])
        fact = next(
            f
            for f in tsardom_thing["facts"]
            if "Council of Elders" in _text(f["segments"])
        )
        await session.send(
            "make_stub",
            thing_id=tsardom["id"],
            fact_id=fact["fact_id"],
            text="Council of Elders",
            kind="lore",
        )
        council = next(
            s for s in await session.stubs() if s["name"] == "Council of Elders"
        )
        results["notes"].append(
            f"no council of the religion named by the Tsardom: written by hand: {text}"
        )
    results["council"] = {
        "id": council["id"],
        "name": council["name"],
        "kind": council["kind"],
    }
    save()
    if council["kind"] == "sphere":
        payload = await session.thing(council["id"])
        template = (payload.get("sphere") or {}).get("template") or "order"
        step = await expand_sphere(session, "council", council, template)
    else:
        step = await expand_lore(session, "council", council, council["kind"])
    step["religion_after"] = summary(await session.thing(religion["id"]))
    steps.append(step)
    save()

    step = await expand_sphere(session, "religion", religion, "religion")
    step["council_after"] = summary(await session.thing(council["id"]))
    steps.append(step)
    save()
    dawn = await session.thing(religion["id"])

    # 4. Fill a beliefs drawer and a practices drawer
    for type_ in ("beliefs", "practices"):
        drawer = _first(dawn, type_)
        if drawer is None:
            results["notes"].append(f"no {type_} drawer to fill")
            continue
        summary_before = world.prose().get(religion["id"], "description", None)
        before = len(session.client.calls)
        filled = await session.send(
            "fill_drawer", sphere_id=religion["id"], drawer_id=drawer["id"]
        )
        dawn = await session.send(
            "accept_fill",
            sphere_id=religion["id"],
            drawer_id=drawer["id"],
            items=filled["items"],
        )
        summary_after = world.prose().get(religion["id"], "description", None)
        steps.append(
            {
                "step": f"fill {drawer['title']}",
                "calls": session.calls_since(before),
                "items": filled["items"],
                "summary_before": summary_before.text if summary_before else None,
                "summary_after": summary_after.text if summary_after else None,
                "thing": summary(dawn),
                "stubs_after": await session.stubs(),
            }
        )
        save()

    # 5. a character with ties
    dawn = await session.thing(religion["id"])
    rite = _item_phrase(_first(dawn, "practices"), "its rites")
    doctrine = _item_phrase(_first(dawn, "beliefs"), "its doctrines")
    prompt = (
        f"Vasha, an owl-folk courier raised in {religion['name']}, who keeps "
        f"{rite} faithfully but thinks {doctrine} is nonsense"
    )
    picks = await _picks(session, prompt)
    before = len(session.client.calls)
    preview = await session.send(
        "preview_thing",
        kind="character",
        prompt=prompt,
        fields={"name": "Vasha", "heritage": owl["id"]},
        picks=picks,
    )
    vasha = await session.send("accept_preview", preview=preview)
    results["rite"], results["doctrine"] = rite, doctrine
    steps.append(
        {
            "step": "vasha",
            "prompt": prompt,
            "picks": picks,
            "calls": session.calls_since(before),
            "preview_ties": preview.get("ties"),
            "thing": summary(vasha),
            "religion_after": summary(await session.thing(religion["id"])),
        }
    )
    save()

    # 6. a scene at a holy site
    dawn = await session.thing(religion["id"])
    holy = next(
        (
            item
            for d in dawn["sphere"]["drawers"]
            if d["type"] == "places"
            for item in d["items"]
            if item["thing_id"]
        ),
        None,
    )
    if holy is None:
        raise RuntimeError("the religion has no holy site: judge by hand")
    scene_prompt = (
        f"Vasha brings a sealed letter to {holy['name']} at dawn, as the "
        f"faithful gather for {rite}"
    )
    picks = await _picks(session, scene_prompt)
    picks.setdefault("Vasha", vasha["id"])
    before = len(session.client.calls)
    plan = await session.send(
        "plan_scene",
        prompt=scene_prompt,
        picks=picks,
        player=vasha["id"],
        start=WorldDate.of(PRESENT).model_dump(),
    )
    setup = plan["setup"]
    place_note = None
    if (setup.get("place") or {}).get("thing_id") != holy["thing_id"]:
        place_note = f"the plan's place was {setup.get('place')}: set to the holy site"
        setup["place"] = {"thing_id": holy["thing_id"], "local": None}
        results["notes"].append(place_note)
    started = await session.send("start_scene", setup=setup)
    scene_id = started["scene_id"]
    record = world.scenes().get(scene_id)
    block = world_context_block(world, record, WorldDate.of(PRESENT))
    scene_step: dict[str, Any] = {
        "step": "scene",
        "prompt": scene_prompt,
        "picks": picks,
        "setup": setup,
        "place_note": place_note,
        "calls": session.calls_since(before),
        "world_block": block,
        "holy_site_after": summary(await session.thing(holy["thing_id"])),
        "turns": [],
    }
    steps.append(scene_step)
    save()

    scan = dict(SCAN)
    scan["religion"] = re.escape(
        re.sub(r"^the ", "", religion["name"], flags=re.I).lower()
    )
    scan["rite"] = re.escape(re.sub(r"^the ", "", rite, flags=re.I).lower())
    directions = [
        f"Dawn breaks and the faithful begin {rite}. Describe it as Vasha "
        "watches from the edge.",
        "An elder notices Vasha and asks whether she still keeps the faith.",
    ]
    scene = await harness._load(world, scene_id, session.client, memory=False)
    narrator = instance.get_agent("narrator")
    try:
        scene_step["sheet_ties"] = scene.get_character("Vasha").base_attributes.get(
            "ties"
        )
        with ActiveScene(scene):
            for direction in directions:
                before = len(session.client.calls)
                text = await narrator.progress_story(narrative_direction=direction)
                await scene.push_history([NarratorMessage(text, source="ai")])
                calls = session.calls_since(before)
                lowered = text.lower()
                scene_step["turns"].append(
                    {
                        "direction": direction,
                        "output": text,
                        "words": len(text.split()),
                        "calls": calls,
                        "scan": {
                            key: len(re.findall(pattern, lowered))
                            for key, pattern in scan.items()
                        },
                    }
                )
                save()
    finally:
        close_world_scene(scene)

    results["things"] = {}
    for kind in ("species", "place", "character", "event", "item", "lore", "sphere"):
        listed = await session.send("list_things", kind=kind)
        results["things"][kind] = [
            {"id": t["id"], "name": t["name"], "stub": t.get("stub")}
            for t in listed["things"]
        ]
    results["stubs_final"] = await session.stubs()


def _replay_calls(doc: dict, label: str) -> list[tuple[str, str]]:
    """The calls of run `label` before its scene step, as `(prompt,
    reply)`: all of its calls (prose refreshes a step's own record
    misses too) but the scene's and its turns'."""

    run = next(r for r in doc["runs"] if r["label"] == label)
    scene = next(step for step in run["steps"] if step["step"] == "scene")
    live = len(scene["calls"]) + sum(len(t["calls"]) for t in scene["turns"])
    return [
        (c["prompt"], c["response"]) for c in run["calls"][: len(run["calls"]) - live]
    ]


async def main(out: Path, label: str, until: str | None, replay: str | None) -> None:
    harness._quiet_loading(False)
    # the world index for scene planning: the tests' offline embedding
    embedding = TrigramEmbeddingFunction()
    MockMemoryAgent.embedding_function = property(lambda self: embedding)
    doc: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {"probe": "spheres-flow", "runs": []}
    )
    client = ReplayClient(name="KoboldCpp")
    client.calls = []
    client.replay = _replay_calls(doc, replay) if replay else []
    await client.status()
    results: dict[str, Any] = {
        "label": label,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "model": client.model_name,
        "prompt_template": client.prompt_template_example()[1],
        "until": until,
        "replayed_from": replay,
        "notes": [],
        "steps": [],
        "calls": client.calls,
    }
    doc["runs"] = [r for r in doc["runs"] if r.get("label") != label] + [results]

    def save() -> None:
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")

    client.on_call = save

    bootstrap_scene(MockScene())
    for agent in instance.AGENTS.values():
        agent.client = client

    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        plugin = WorldsPlugin(_Handler())
        plugin.worlds_root = Path(root)
        session = Session(plugin, client)
        await session.send(
            "create_world", name="Moscavia spheres", present_year=PRESENT
        )
        try:
            await run(session, results, save)
        except Exception as exc:
            results["error"] = repr(exc)
            raise
        finally:
            save()
            plugin.disconnect()
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--label", default="run 1")
    parser.add_argument("--until", choices=["tsardom"], default=None)
    parser.add_argument(
        "--replay",
        metavar="LABEL",
        default=None,
        help="answer the steps before the scene from that run's replies",
    )
    args = parser.parse_args()
    asyncio.run(main(args.out.resolve(), args.label, args.until, args.replay))
