"""Throwaway probe: the owner's connections session on the real model
(fantasymate connections, Task 10).

Drives the same path the world screens use -- the real `worlds` router
(`talemate.server.worlds.WorldsPlugin`) and `worldplay` -- with Talemate's
own KoboldCpp client (the `--ai` app's config, as `probe_heritage_play`
sets it up) serving the creator agent. Nothing is stubbed: every create is
the create call plus its section prose, as in the app.

The session, in a fresh world (present year 1000):

1. **Owl-folk**, a species, from a prompt naming the Tsardom of Moscavia as
   its origin ("everyone in the Tsardom of Moscavia became this race
   suddenly one day 6 years ago", the owner's own wording from plan B).
   Accepted: the names its facts use become stubs.
2. **The Tsardom**, expanded from its stub with the suggested prompt
   (`stub_suggestion`), accepted into the stub. If the species never named
   it, the script makes the stub the way the owner would (`make_stub` on
   the origin fact) and records that.
3. **Two stubs the Tsardom names**, places first (cities, rivers, lakes,
   mountains), each expanded and accepted the same way.
4. **A place prompt saying "Moscavian Owls"**: `match_names` first; the
   owner's pick of the Owl-folk is passed (what the name highlight offers,
   or what the owner would pick by hand if nothing matched), then the
   preview is accepted.

After every step the stubs (`list_stubs`, ignored ones too) and the
accepted thing's payload (aka, facts as linked segments, named stubs) are
recorded, with each create's prompt and reply, to the output JSON after
every call. Judging (false stubs, duplicates, facts built around the
owl-folk) is done by hand from that JSON.

Not a test: it calls the network. The owner approved this plan's Skyfall
tests (one GPU: calls run one after another)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_connections_flow.py OUT.json'

Findings: docs/superpowers/probes/2026-10-21-connections-flow.md. Its raw
JSON holds two runs of this script (`runs`, before and after the
origin-facts fix in `mentions._key_facts`) and the hand judging
(`judged`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

# the heritage play probe's harness: config, recording client, test stand-ins
import probe_heritage_play as harness  # noqa: E402

import talemate.instance as instance  # noqa: E402
from talemate.server.worlds import WorldsPlugin  # noqa: E402

from conftest import MockScene, bootstrap_scene  # noqa: E402

SPECIES_PROMPT = (
    "Owl-folk: owl people. Everyone in the Tsardom of Moscavia became this "
    "race suddenly one day 6 years ago."
)
TOWN_PROMPT = "a river town where Moscavian Owls trade with barge crews"
TSARDOM = "Tsardom of Moscavia"
# kinds a stub can be expanded as from its own page (not culture, race, mix)
EXPANDABLE = ("place", "character", "event", "item", "lore", "species")


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

    async def create(
        self,
        label: str,
        kind: str,
        prompt: str,
        *,
        stub_id: str | None = None,
        picks: dict[str, str] | None = None,
    ) -> dict:
        """Preview and accept one thing (into `stub_id`, if given); returns
        the step's record."""

        calls_before = len(self.client.calls)
        started = time.monotonic()
        preview = await self.send(
            "preview_thing",
            kind=kind,
            prompt=prompt,
            fields={},
            stub_id=stub_id,
            picks=picks or {},
        )
        calls = self.client.calls[calls_before:]
        thing = await self.send("accept_preview", preview=preview, into_stub=stub_id)
        return {
            "step": label,
            "kind": kind,
            "prompt": prompt,
            "stub_id": stub_id,
            "picks": picks or {},
            "seconds": round(time.monotonic() - started, 1),
            "create_prompt": calls[0]["prompt"] if calls else None,
            "create_reply": calls[0]["response"] if calls else None,
            "preview": {
                "name": preview["name"],
                "aka": preview["aka"],
                "facts": [
                    {"category": f["category"], "text": f["text"]}
                    for f in preview["facts"]
                ],
                "new_names": preview["new_names"],
                "context": preview["context"],
                "prose": preview.get("prose"),
            },
            "thing": summary(thing),
            "stubs_after": await self.stubs(),
        }


def summary(thing: dict) -> dict:
    """A thing payload's name, aka and facts, each fact with its linked
    runs as `[text, ref, stub]`."""

    return {
        "id": thing["id"],
        "kind": thing["kind"],
        "name": thing["fields"].get("name"),
        "aka": thing["aka"],
        "stub": thing["stub"],
        "facts": [
            {
                "category": fact["category"],
                "text": "".join(s["text"] for s in fact["segments"]),
                "links": [
                    [s["text"], s["ref"], s["stub"]]
                    for s in fact["segments"]
                    if s["ref"]
                ],
            }
            for fact in thing["facts"]
        ],
        "named_stubs": thing["named_stubs"],
    }


def pick_two(thing: dict, stubs: list[dict]) -> list[dict]:
    """Two stubs the thing's facts name, in fact order, places first."""

    live = {stub["id"]: stub for stub in stubs if not stub["ignored"]}
    named = [
        live[s["id"]]
        for s in thing["named_stubs"]
        if s["id"] in live and live[s["id"]]["kind"] in EXPANDABLE
    ]
    places = [s for s in named if s["kind"] == "place"]
    others = [s for s in named if s["kind"] != "place"]
    return (places + others)[:2]


async def run(session: Session, results: dict, save) -> None:
    steps = results["steps"]

    # 1. the species, its origin naming the Tsardom
    step = await session.create("owl-folk", "species", SPECIES_PROMPT)
    steps.append(step)
    save()
    owl_folk = step["thing"]
    tsardom = next(
        (s for s in step["stubs_after"] if s["name"].casefold() == TSARDOM.casefold()),
        None,
    )
    if tsardom is None:
        # the owner makes it from the origin fact by hand
        origin = next(
            (f for f in owl_folk["facts"] if "Moscavia" in f["text"]),
            None,
        )
        results["notes"].append(
            f"no {TSARDOM} stub from the species; origin fact: {origin}"
        )
        thing = await session.send("get_thing", id=owl_folk["id"], at=None)
        fact = next(f for f in thing["facts"] if "Moscavia" in f["text"])
        phrase = TSARDOM if TSARDOM in fact["text"] else "Moscavia"
        await session.send(
            "make_stub",
            thing_id=owl_folk["id"],
            fact_id=fact["fact_id"],
            text=phrase,
            kind="place",
        )
        tsardom = next(s for s in await session.stubs() if s["name"] == phrase)
        save()

    # 2. the Tsardom, from its stub
    suggestion = await session.send("stub_suggestion", id=tsardom["id"])
    step = await session.create(
        "tsardom", "place", suggestion["prompt"], stub_id=tsardom["id"]
    )
    step["suggestion"] = suggestion
    steps.append(step)
    save()

    # 3. two stubs the Tsardom names
    for stub in pick_two(step["thing"], step["stubs_after"]):
        suggestion = await session.send("stub_suggestion", id=stub["id"])
        expanded = await session.create(
            f"stub: {stub['name']}",
            stub["kind"],
            suggestion["prompt"],
            stub_id=stub["id"],
        )
        expanded["suggestion"] = suggestion
        steps.append(expanded)
        save()

    # 4. "Moscavian Owls" in a place prompt
    matched = await session.send("match_names", text=TOWN_PROMPT, at=None)
    results["town_match"] = matched
    found = next(
        (
            m
            for m in matched["matches"]
            if "Moscavian Owls" in m["text"] or m["text"] in "Moscavian Owls"
        ),
        None,
    )
    auto = bool(found and found["candidates"][0]["id"] == owl_folk["id"])
    results["notes"].append(
        "Moscavian Owls matched the Owl-folk automatically"
        if auto
        else "Moscavian Owls not matched to the Owl-folk: the owner picks it"
    )
    step = await session.create(
        "town",
        "place",
        TOWN_PROMPT,
        picks={"Moscavian Owls": owl_folk["id"]},
    )
    steps.append(step)
    save()

    # the end state: every thing in the world, stubs included
    results["things"] = {}
    for kind in ("species", "place", "character", "event", "item", "lore", "culture"):
        listed = await session.send("list_things", kind=kind)
        results["things"][kind] = [
            {"id": t["id"], "name": t["name"], "stub": t.get("stub")}
            for t in listed["things"]
        ]
    results["stubs_final"] = await session.stubs()


async def main(out: Path) -> None:
    harness._quiet_loading(False)
    client = harness.RecordingClient(name="KoboldCpp")
    client.calls = []
    await client.status()

    results: dict[str, Any] = {
        "probe": "connections-flow",
        "date": "2026-10-21",
        "model": client.model_name,
        "prompt_template": client.prompt_template_example()[1],
        "notes": [],
        "steps": [],
        "calls": client.calls,
    }

    def save() -> None:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    client.on_call = save

    bootstrap_scene(MockScene())
    for agent in instance.AGENTS.values():
        agent.client = client

    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        plugin = WorldsPlugin(_Handler())
        plugin.worlds_root = Path(root)
        session = Session(plugin, client)
        await session.send("create_world", name="Moscavia probe", present_year=1000)
        try:
            await run(session, results, save)
        finally:
            plugin.disconnect()
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.out.resolve()))
