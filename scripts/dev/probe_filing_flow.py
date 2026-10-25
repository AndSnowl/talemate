"""Throwaway probe: filing in a real session on the real model (Filing
plan, Task 12).

Runs Task 11's session (`tests/worldplay/test_filing_end_to_end.py`) on
Skyfall through the real `worlds` router (`talemate.server.worlds.
WorldsPlugin`), with Talemate's own KoboldCpp client serving every agent
(the `--ai` app's config, as `probe_heritage_play` sets it up, so every
call goes at the app's own kind and preset). A fresh world (present year
1000) under `--root`. Nothing is stubbed and no fixed reply is used.

Where the owner ticks, unticks or picks, a fixed policy is followed, from
the hand labels committed before any model call
(`docs/superpowers/probes/raw/2026-10-24-filing-flow-labels.json`,
`owner_policy`): every create draft is generated twice (v1, then
Regenerate: v2), both are recorded, v1 is restored and accepted; "In" rows
are ticked only when "expected", and an expected home the model missed is
added with "+ in..."; "File into this" rows ticked only when "expected";
the rest as the draft arrives. Each choice is recorded in the step.

The session (Task 11's, plus the unprobed items Task 12 measures):

1. the owl-folk; 2. the Tsardom (nation hint); 3. Velikoye and the Khorol
River; 4. the Night Court; 5. Runic Magic (field hint), the Order (order
hint) and the Academy; 6. the White Talon, the Frosted Wing (ruling F6's
sibling case: its prompt never names the Host) and the Frostwing Host;
7. Plumage Signaling; then "+ Add facts" on Velikoye and "+ Add event"
(997) on the Tsardom, twice each; group "+ Add" with no tag on Velikoye
(its rows' tags cleared by the owner, for the "other entries" group) and
on the Order, twice each; 8. group synopses (each asked twice), and one
going stale; 10. Wattles: regenerate, restore, discard; 11. Anastasiya
Koroleva and Vasha, then the scene at the Academy: its World block, and
two narrator directions, each run twice.

Merge and Re-point (Task 11's step 9) ask the model nothing, so they are
left to the MockClient test.

Every model call is serialised (one lock around the client: the router's
prose refreshes for different entries would otherwise overlap) and
recorded with its template uid, kind, seconds and KoboldCpp's own token
counts (`/api/extra/perf` after the call), and the raw JSON is written
after every call.

`--fake` answers every call with a minimal canned reply instead of the
model (no network), to check the harness end to end.

`--score RAW.json` computes the code scores (tags, "In", "File into this",
F4, F6, thin-stub candidates, repeats, duplicates) from a run and its kept
world, into the raw JSON's `scores`.

Not a test: it calls the network. The owner approved Skyfall for this
task ("you have permissions to use skyfall for any tasks")::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_filing_flow.py OUT.json --root DIR [--label L] [--fake]'

Findings: docs/superpowers/probes/2026-10-24-filing-flow.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

# the heritage play probe's harness: the `--ai` config, test stand-ins
import probe_heritage_play as harness  # noqa: E402

import talemate.instance as instance  # noqa: E402
from talemate.client.koboldcpp import KoboldCppClient  # noqa: E402
from talemate.context import ActiveScene  # noqa: E402
from talemate.scene_message import NarratorMessage  # noqa: E402
from talemate.server.worlds import WorldsPlugin  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.filing import filings_of  # noqa: E402
from talemate.world.repeats import overlap  # noqa: E402
from talemate.world.sameness import name_index, same_candidates  # noqa: E402
from talemate.world.store import World  # noqa: E402
from talemate.worldplay.context import (  # noqa: E402
    role_named,
    touched_entries,
    world_context_block,
)
from talemate.worldplay.create import _homes  # noqa: E402
from talemate.worldplay.mentions import gather_mentions  # noqa: E402
from talemate.worldplay.persistence import close_world_scene  # noqa: E402

from conftest import MockMemoryAgent, MockScene, bootstrap_scene  # noqa: E402
from world.embedding import TrigramEmbeddingFunction  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-24-filing-flow-labels.json"
PERF_URL = harness.KOBOLDCPP_URL + "/api/extra/perf"
PRESENT = 1000

L = json.loads(LABELS.read_text())
# keys checked most specific first: "Runic Magic of the Tsardom" is Runic
# Magic, "Tsar Dmitry IV" the Tsar, never the Tsardom
KEY_ORDER = [k for k in L["entries"] if k not in ("tsardom",)] + ["tsardom"]
PATTERNS = {k: re.compile(L["entries"][k], re.I) for k in KEY_ORDER}


def key_of(name: str | None) -> str | None:
    for key in KEY_ORDER:
        if name and PATTERNS[key].search(name):
            return key
    return None


# --- the client -----------------------------------------------------------------


def _perf() -> dict | None:
    try:
        with urllib.request.urlopen(PERF_URL, timeout=30) as response:
            return json.loads(response.read())
    except Exception:  # a count is nice to have
        return None


def replay_key(prompt: str) -> tuple[str, ...]:
    """A prompt as the replay matches it: its lines, sorted, each line's
    words sorted (the facts of one revision come in no fixed order in some
    context blocks, even within a line), with fix 1's tag rule left out (it shows on more
    prompts now). Only the harness reads this: a replayed reply answers a
    prompt that says the same things."""

    lines = []
    for line in prompt.splitlines():
        if line.startswith('- "tag": one or two words'):
            continue
        lines.append(" ".join(sorted(line.split())))
    return tuple(sorted(lines))


class Recorder(KoboldCppClient):
    """Talemate's KoboldCpp client, one call at a time (`lock`), each
    recorded with its uid, kind, prompt, reply, seconds and KoboldCpp's
    token counts. With `fake`, a canned reply instead of the model."""

    calls: list[dict[str, Any]]
    fake: bool = False
    lock: asyncio.Lock
    # an earlier run's `(prompt, reply)` pairs: a prompt recorded there is
    # answered with its recorded reply (`replay_by_prompt`); any other goes
    # to the model (or, with `fake`, the canned reply)
    replay: list[tuple[str, str]] = []

    def replay_by_prompt(self) -> dict[str, list[str]]:
        """The replay as prompt -> its recorded replies, in order: calls
        that run concurrently (prose refreshes) may come in another order,
        so a recorded reply answers the same prompt wherever it comes."""

        if not hasattr(self, "_by_prompt"):
            self._by_prompt: dict[str, list[str]] = {}
            for recorded_prompt, response in self.replay:
                self._by_prompt.setdefault(replay_key(recorded_prompt), []).append(
                    response
                )
        return self._by_prompt

    async def send_prompt(self, prompt, kind="conversation", *args, **kwargs):
        async with self.lock:
            recorded = (
                None
                if getattr(self, "live", False)
                else self.replay_by_prompt().get(replay_key(str(prompt)))
            )
            forced = getattr(self, "forced", None)
            if (
                not recorded
                and not getattr(self, "live", False)
                and forced
                and getattr(prompt, "uid", None) == "world.create-thing"
            ):
                # a draft whose prompt the fixes changed: answered with the
                # run's own recorded reply, so the world goes on as it did
                recorded = [forced.pop(0)]
            if recorded:
                response = recorded.pop(0)
                self.calls.append(
                    {
                        "uid": getattr(prompt, "uid", None),
                        "kind": kind,
                        "prompt": str(prompt),
                        "response": response,
                        "seconds": 0.0,
                        "replayed": True,
                    }
                )
                self.on_call()
                return response
            if self.replay and getattr(self, "replay_missed_at", None) is None:
                self.replay_missed_at = len(self.calls)
            started = time.monotonic()
            if self.fake:
                response = fake_reply(str(prompt))
            else:
                response = await super().send_prompt(prompt, kind, *args, **kwargs)
            seconds = round(time.monotonic() - started, 1)
            perf = None if self.fake else _perf()
            self.calls.append(
                {
                    "uid": getattr(prompt, "uid", None),
                    "kind": kind,
                    "prompt": str(prompt),
                    "response": response,
                    "seconds": seconds,
                    "prompt_tokens": (perf or {}).get("last_input_count"),
                    "reply_tokens": (perf or {}).get("last_token_count"),
                    "stop_reason": (perf or {}).get("stop_reason"),
                }
            )
            self.on_call()
            return response

    def on_call(self) -> None:
        pass


def _guess_name(prompt: str) -> str:
    match = re.search(r"Owner's prompt[^\n]*\n(.+)", prompt)
    text = match.group(1) if match else "Thing"
    return re.split(r"[,:]", text)[0].strip() or "Thing"


def fake_reply(prompt: str) -> str:
    """A minimal reply for each template (the `--fake` harness check)."""

    if "Write the synopsis of one group" in prompt:
        return json.dumps({"synopsis": "A group."})
    if "You add new entries" in prompt:
        return json.dumps(
            {
                "entries": [
                    {
                        "name": "The Fake Tavern",
                        "kind": "place",
                        "tag": "tavern",
                        "line": "A tavern.",
                    }
                ]
            }
        )
    if "You add a few facts" in prompt:
        return json.dumps(
            {"facts": [{"category": "general", "text": "A fake fact here."}]}
        )
    if "Decide how the new entry A relates to B" in prompt:
        return json.dumps({"verdict": "different", "why": "fake"})
    if "You plan the opening of a roleplay scene" in prompt:
        return json.dumps(
            {
                "player": "Vasha",
                "characters": [{"name": "Vasha", "world": True}],
                "place": {"name": "The Academy of the Chiseled Moon", "world": True},
                "extras": [],
                "goal": "Vasha must deliver a sealed letter to the Chief Scribe of the Order of the Talon-Scribe.",
                "intro": "Vasha lands.",
            }
        )
    if "reference profile" in prompt:
        return "Fake prose."
    if '"names"' in prompt and "JSON" in prompt:
        name = _guess_name(prompt)
        return json.dumps(
            {
                "name": name,
                "tag": "thing",
                "facts": [
                    {
                        "category": "general",
                        "text": f"{name} is a fake thing of the world.",
                    },
                    {
                        "category": "general",
                        "text": f"{name} was made by the harness check.",
                    },
                ],
                "names": [],
                "in": [],
                "file_into": [],
            }
        )
    return "Vasha looks around."


# --- the router -------------------------------------------------------------------


class _Handler:
    scene = None

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def queue_put(self, data: dict) -> None:
        self.messages.append(data)


class Session:
    def __init__(self, plugin: WorldsPlugin, client: Recorder) -> None:
        self.plugin = plugin
        self.client = client
        self.failures: list[dict] = []

    async def send(self, action: str, **data: Any) -> dict:
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

    async def retry(self, action: str, **data: Any) -> dict:
        """As the owner presses the button again (up to 3 tries)."""

        for attempt in range(3):
            try:
                return await self.send(action, **data)
            except RuntimeError as exc:
                self.failures.append(
                    {"action": action, "attempt": attempt + 1, "error": str(exc)[:2000]}
                )
                if attempt == 2:
                    raise
        raise AssertionError("unreachable")

    async def stubs(self) -> list[dict]:
        return (await self.send("list_stubs", include_ignored=False))["stubs"]

    async def thing(self, thing_id: str) -> dict:
        return await self.send("get_thing", id=thing_id, at=None)

    async def picks(self, text: str) -> dict[str, str]:
        found = await self.send("match_names", text=text, at=None)
        return {
            m["text"]: m["candidates"][0]["id"]
            for m in found["matches"]
            if not m["suggested"] and m["candidates"]
        }


def _text(segments: list[dict]) -> str:
    return "".join(s["text"] for s in segments)


def thing_record(thing: dict) -> dict:
    return {
        "id": thing["id"],
        "kind": thing["kind"],
        "name": thing["name"],
        "tag": thing.get("tag"),
        "hint": thing.get("hint"),
        "stub": thing.get("stub") is not None,
        "facts": [
            {
                "fact_id": f["fact_id"],
                "category": f["category"],
                "text": _text(f["segments"]),
                "held_by": (f.get("held_by") or {}).get("name"),
            }
            for f in thing["facts"]
        ],
        "in": [
            {
                "target_id": f.get("target_id"),
                "target": f.get("target_name") or f.get("name"),
                "role": f.get("role"),
                "exceptions": [
                    _text(e.get("segments") or []) for e in f.get("exceptions") or []
                ],
            }
            for f in thing.get("in") or []
        ],
        "connected": [
            {
                "tag": g["tag"],
                "heading": g.get("heading"),
                "synopsis": g.get("synopsis"),
                "rows": [
                    {"id": r["id"], "name": r.get("name"), "role": r.get("role")}
                    for r in g["rows"]
                ],
            }
            for g in thing.get("connected") or []
        ],
    }


def draft_record(draft: dict) -> dict:
    p = draft["preview"]
    return {
        "draft_key": draft["draft_key"],
        "version": draft["version"],
        "name": p["name"],
        "kind": p["kind"],
        "tag": p.get("tag"),
        "hint": p.get("hint"),
        "summary": p.get("summary"),
        "facts": [
            {
                "category": f["category"],
                "text": f["text"],
                "since": f.get("since"),
                "ticked": f.get("ticked"),
                "repeat_of": (f.get("repeat_of") or {}).get("text"),
                "held_by": f.get("held_by"),
            }
            for f in p.get("facts", [])
        ],
        "filings": [
            {
                "target_id": r.get("target_id"),
                "target_name": r.get("target_name"),
                "new_name": (r.get("new_name") or {}).get("name"),
                "role": r.get("role"),
                "ticked": r.get("ticked"),
                "exceptions": r.get("exceptions") or [],
            }
            for r in p.get("filings", [])
        ],
        "file_into": [
            {
                "thing_id": r["thing_id"],
                "name": r["name"],
                "role": r.get("role"),
                "ticked": r.get("ticked"),
            }
            for r in p.get("file_into", [])
        ],
        "move_here": [
            {"from_id": r["from_id"], "text": r["text"], "ticked": r.get("ticked")}
            for r in p.get("move_here", [])
        ],
        "new_names": [
            {
                "name": n["name"],
                "kind": n["kind"],
                "tag": n.get("tag"),
                "filing": n.get("filing"),
                "same_as": [o.get("name") for o in n.get("same_as") or []],
            }
            for n in p.get("new_names", [])
        ],
        "elsewhere": [
            {
                "target": e["target_name"],
                "target_id": e.get("target_id"),
                "new": bool(e.get("new")),
                "text": e["text"],
                "ticked": e.get("ticked"),
                "repeat_of": (e.get("repeat_of") or {}).get("text"),
            }
            for e in p.get("elsewhere", [])
        ],
        "same_as": [
            {
                "thing_id": o.get("thing_id"),
                "name": o.get("name"),
                "reason": o.get("reason"),
            }
            for o in p.get("same_as") or []
        ],
        "verdict": p.get("verdict"),
        "matching_stub_id": p.get("matching_stub_id"),
    }


def near_lines(prompt: str) -> list[str]:
    """The create prompt's "Entries near this one" list."""

    if "Entries near this one in the world:" not in prompt:
        return []
    body = prompt.split("Entries near this one in the world:", 1)[1].lstrip("\n")
    lines = []
    for line in body.splitlines():
        if not line.startswith("- "):
            break
        lines.append(line[2:])
    return lines


def tags_in_use(prompt: str) -> list[str]:
    lead = "Tags in use in the world (each entry has one tag saying what it is), with how many entries carry each:"
    if lead not in prompt:
        return []
    line = prompt.split(lead, 1)[1].lstrip("\n").splitlines()[0]
    return [re.sub(r"\s*\(\d+\)$", "", part).strip() for part in line.split(", ")]


# --- the session --------------------------------------------------------------------


class StopSession(Exception):
    """The session stops after `--stop-after`'s step (fix round 1)."""


class Run:
    def __init__(self, session: Session, results: dict, save) -> None:
        self.s = session
        self.r = results
        self.save = save
        self.ids: dict[str, str] = {}
        self.world = session.plugin.world
        # fix round 1 (`--retry`): the steps re-asked of the model, live,
        # before the source run's recorded versions are replayed
        self.retry_keys: set[str] = set()
        self.source: dict | None = None
        self.stop_after: str | None = None

    # the owner's acts -----------------------------------------------------------

    def _calls(self, before: int) -> list[int]:
        return list(range(before, len(self.s.client.calls)))

    async def find_stub(self, key: str) -> dict | None:
        for stub in await self.s.stubs():
            if key_of(stub["name"]) == key:
                return stub
        return None

    async def draft(
        self,
        key: str,
        *,
        kind: str | None = None,
        prompt: str | None = None,
        hint: str | None = None,
        extra: str = "",
        accept: bool = True,
        discard: bool = False,
    ) -> dict:
        """The entry `key`: from its stub when one matches, else from its
        prompt; two versions; v1 restored, ticked by the policy, accepted."""

        step: dict[str, Any] = {"step": key, "versions": []}
        stub = await self.find_stub(key)
        data: dict[str, Any] = {"fields": {}}
        if stub is not None and prompt is None:
            suggestion = await self.s.send("stub_suggestion", id=stub["id"])
            text = suggestion["prompt"] + extra
            # a stub draft sends no picks (Task 11's `_expand`), except
            # where the owner wrote words of their own: the create box's
            # picks for them (`match_names`)
            data.update(
                kind=stub["kind"],
                prompt=text,
                stub_id=stub["id"],
                picks=(await self.s.picks(text)) if extra else {},
            )
            step["from"] = f"stub ({stub['kind']}, tag {stub.get('tag')})"
            self.ids[key] = stub["id"]
        else:
            if prompt is None:
                kind, prompt = L["fallback_prompts"][key]
                step["from"] = "fallback prompt (no stub)"
            else:
                step["from"] = "prompt"
            prompt = prompt + (extra if step["from"] != "prompt" else "")
            data.update(kind=kind, prompt=prompt, picks=await self.s.picks(prompt))
        if hint:
            data["hint"] = hint
        step["request"] = {k: v for k, v in data.items()}
        started = time.monotonic()
        if key in self.retry_keys:
            await self.live_versions(key, data, step)
        draft_key = None
        for version in (1, 2):
            before = len(self.s.client.calls)
            got = await self.s.retry(
                "preview_thing",
                **data,
                **({"draft_key": draft_key} if draft_key else {}),
            )
            draft_key = got["draft_key"]
            record = draft_record(got)
            record["calls"] = self._calls(before)
            create = [
                i
                for i in record["calls"]
                if self.s.client.calls[i]["uid"] == "world.create-thing"
            ]
            if create:
                prompt_text = self.s.client.calls[create[-1]]["prompt"]
                record["near"] = near_lines(prompt_text)
                record["tags_in_use"] = tags_in_use(prompt_text)
            record["ids_at"] = dict(self.ids)
            step["versions"].append(record)
            self.r["steps"].append(step) if version == 1 else None
            self.save()
        if discard:
            restored = await self.s.send("use_version", draft_key=draft_key, version=1)
            step["restored_same"] = (
                restored["preview"]["name"] == step["versions"][0]["name"]
            )
            head = self.world.head_rev()
            await self.s.send("discard_preview", draft_key=draft_key)
            step["discarded_head_same"] = self.world.head_rev() == head
            step["seconds"] = round(time.monotonic() - started, 1)
            self.save()
            return step
        restored = await self.s.send("use_version", draft_key=draft_key, version=1)
        preview = restored["preview"]
        step["choices"] = self.tick(key, preview)
        # "fill the stub instead": a live stub of the same kind and name
        # is the entry the owner means, never a second one
        if not data.get("stub_id") and preview.get("matching_stub_id"):
            data["stub_id"] = preview["matching_stub_id"]
            step["choices"].append("filled the matching stub instead")
        if not accept:
            return step
        before = len(self.s.client.calls)
        thing = await self.s.send(
            "accept_preview",
            preview=preview,
            draft_key=draft_key,
            **({"into_stub": data["stub_id"]} if data.get("stub_id") else {}),
        )
        step["accept_calls"] = self._calls(before)
        step["notes"] = thing.get("notes")
        step["thing"] = thing_record(thing)
        step["seconds"] = round(time.monotonic() - started, 1)
        self.ids[key] = thing["id"]
        await self.register()
        self.save()
        if key == self.stop_after:
            raise StopSession(key)
        return step

    async def live_versions(self, key: str, data: dict, step: dict) -> None:
        """Two versions of the draft from the model with the current code
        (`step["retry"]`), then discarded; the source run's recorded
        replies for this step are queued to answer the replayed versions."""

        client = self.s.client
        step["retry"] = []
        client.live = True
        try:
            retry_key = None
            for _version in (1, 2):
                before = len(client.calls)
                got = await self.s.retry(
                    "preview_thing",
                    **data,
                    **({"draft_key": retry_key} if retry_key else {}),
                )
                retry_key = got["draft_key"]
                record = draft_record(got)
                record["calls"] = self._calls(before)
                create = [
                    i
                    for i in record["calls"]
                    if client.calls[i]["uid"] == "world.create-thing"
                ]
                if create:
                    text = client.calls[create[-1]]["prompt"]
                    record["near"] = near_lines(text)
                    record["tags_in_use"] = tags_in_use(text)
                step["retry"].append(record)
                self.save()
            await self.s.send("discard_preview", draft_key=retry_key)
        finally:
            client.live = False
        source_step = next(
            s for s in (self.source or {}).get("steps", []) if s.get("step") == key
        )
        calls = self.source["calls"]
        client.forced = [
            calls[i]["response"]
            for version in source_step["versions"]
            for i in version["calls"]
            if calls[i]["uid"] == "world.create-thing"
        ]

    def tick(self, key: str, preview: dict) -> list[str]:
        """The owner's ticks (the policy), each recorded."""

        choices: list[str] = []
        expected = L["in"].get(key, {}).get("expected", [])
        found: set[str] = set()
        for row in preview.get("filings", []):
            target = self.target_key(row.get("target_id"), row.get("target_name"))
            want = target in expected
            if want:
                found.add(target)
            if row.get("ticked") != want:
                choices.append(
                    f"In {row.get('target_name')!r}: {'ticked' if want else 'unticked'}"
                )
            row["ticked"] = want
        for target in expected:
            if target in found:
                continue
            target_id = self.ids.get(target)
            if target_id is None or self.world.view().thing(target_id) is None:
                choices.append(f"+ in {target}: no such entry yet")
                continue
            role = L["owner_roles"].get(f"{key}>{target}")
            preview.setdefault("filings", []).append(
                {
                    "target_id": target_id,
                    "target_name": self.world.view().name_of(target_id),
                    "role": role,
                    "ticked": True,
                }
            )
            choices.append(f"+ in {self.world.view().name_of(target_id)!r} ({role})")
        into_expected = L["file_into"].get(key, {}).get("expected", [])
        for row in preview.get("file_into", []):
            target = self.target_key(row["thing_id"], row["name"])
            want = target in into_expected
            if want:
                row["role"] = row.get("role") or L["owner_roles"].get(f"{key}<{target}")
                choices.append(f"File into {row['name']!r}: ticked ({row['role']})")
            row["ticked"] = want
        return choices

    def target_key(self, thing_id: str | None, name: str | None) -> str | None:
        for key, known in self.ids.items():
            if thing_id is not None and known == thing_id:
                return key
        return None

    async def register(self) -> None:
        """Keys not yet seen, from the live entries' names (stubs too)."""

        view = self.world.view()
        for state in view.things():
            key = key_of(view.name_of(state.id))
            if key is not None and key not in self.ids:
                self.ids[key] = state.id

    async def run(self) -> None:
        r = self.r
        sp = L["session_prompts"]

        kind, prompt = sp["owlfolk"]
        await self.draft("owlfolk", kind=kind, prompt=prompt)
        await self.register()

        await self.draft("tsardom", hint=L["hints"]["tsardom"])
        await self.draft("velikoye")
        await self.draft("khorol")
        kind, prompt = sp["nightcourt"]
        await self.draft("nightcourt", kind=kind, prompt=prompt)
        await self.draft("runic", hint=L["hints"]["runic"])
        await self.draft("order", hint=L["hints"]["order"])
        kind, prompt = sp["academy"]
        await self.draft("academy", kind=kind, prompt=prompt)
        kind, prompt = sp["whitetalon"]
        await self.draft("whitetalon", kind=kind, prompt=prompt)
        kind, prompt = sp["frostedwing"]
        await self.draft("frostedwing", kind=kind, prompt=prompt)

        # F6: how the Frosted Wing stands to the Host's draft context
        r["f6_before_host"] = self.f6_paths()
        await self.draft("host")
        self.save()
        await self.draft("plumage")

        # "+ Add facts" and "+ Add event", twice each; run 1 accepted
        await self.add_facts("velikoye", L["add_facts"]["velikoye"]["prompt"], None)
        event = L["add_facts"]["tsardom_event"]
        await self.add_facts("tsardom", event["prompt"], event["year"])

        # group "+ Add" with no tag, twice each
        await self.group_add(
            "velikoye", L["group_add"]["velikoye_none"]["prompt"], clear_tags=True
        )
        await self.group_add("order", L["group_add"]["order_none"]["prompt"])

        # 8. synopses
        await self.synopses()

        # 10. Wattles: regenerate, restore, discard
        kind, prompt = sp["wattles"]
        await self.draft("wattles", kind=kind, prompt=prompt, discard=True)

        # 11. the characters
        await self.draft("koroleva", extra=sp["koroleva_extra"])
        kind, prompt = sp["vasha"]
        await self.draft("vasha", kind=kind, prompt=prompt)
        await self.scene()
        r["final"] = [
            thing_record(await self.s.thing(t.id)) for t in self.world.view().things()
        ]
        r["ids"] = dict(self.ids)
        self.save()

    def f6_paths(self) -> dict:
        """Where the Frosted Wing stands to the Host stub's seeds (the stub,
        where it's filed, what mentions it): linked, or only a sibling."""

        view = self.world.view()
        host = self.ids.get("host")
        wing = self.ids.get("frostedwing")
        out: dict[str, Any] = {"host": host, "frostedwing": wing}
        if not host or not wing or view.thing(host) is None:
            out["note"] = "no Host stub or no Frosted Wing"
            return out
        gathered = gather_mentions(view, host)
        seeds = [host, *_homes(view, host), *(m.owner_id for m in gathered.mentioned)]
        out["seeds"] = [view.name_of(s) for s in seeds]
        wing_state = view.thing(wing)
        links = []
        for seed in seeds:
            if seed in _homes(view, wing):
                links.append(f"filed in {view.name_of(seed)}")
            if wing in _homes(view, seed):
                links.append(f"{view.name_of(seed)} filed in it")
            if any(seed in f.refs for f in wing_state.facts):
                links.append(f"its facts name {view.name_of(seed)}")
            seed_state = view.thing(seed)
            if seed_state and any(wing in f.refs for f in seed_state.facts):
                links.append(f"{view.name_of(seed)}'s facts name it")
        out["links"] = links
        out["sibling_of"] = [
            view.name_of(s)
            for s in seeds
            if set(_homes(view, s)) & set(_homes(view, wing))
        ]
        out["wing_homes"] = [view.name_of(t) for t in _homes(view, wing)]
        out["host_named_in_wing_facts"] = any(host in f.refs for f in wing_state.facts)
        return out

    async def add_facts(self, key: str, prompt: str, year: int | None) -> None:
        thing_id = self.ids.get(key)
        step: dict[str, Any] = {
            "step": f"add_{'event' if year else 'facts'} {key}",
            "prompt": prompt,
            "year": year,
            "runs": [],
        }
        self.r["steps"].append(step)
        if thing_id is None:
            step["note"] = "no such entry"
            return
        action = "add_event" if year else "add_facts"
        first = None
        for _ in range(2):
            before = len(self.s.client.calls)
            got = await self.s.retry(
                action,
                thing_id=thing_id,
                prompt=prompt,
                **({"year": year} if year else {}),
            )
            step["runs"].append(
                {
                    "calls": self._calls(before),
                    "facts": [
                        {
                            "category": f["category"],
                            "text": f["rendered"],
                            "since": f.get("since"),
                            "ticked": f["ticked"],
                            "repeat_of": (f.get("repeat_of") or {}).get("text"),
                        }
                        for f in got["facts"]
                    ],
                }
            )
            first = first or got
            self.save()
        done = await self.s.send("accept_facts", draft=first["draft"])
        step["accepted"] = done.get("fact_ids")
        self.save()

    async def group_add(self, key: str, prompt: str, clear_tags: bool = False) -> None:
        thing_id = self.ids.get(key)
        step: dict[str, Any] = {
            "step": f"group_add {key} (no tag)",
            "prompt": prompt,
            "runs": [],
        }
        self.r["steps"].append(step)
        if thing_id is None:
            step["note"] = "no such entry"
            return
        first = None
        for _ in range(2):
            before = len(self.s.client.calls)
            got = await self.s.retry(
                "group_add", thing_id=thing_id, tag=None, prompt=prompt
            )
            step["runs"].append({"calls": self._calls(before), "rows": got["rows"]})
            first = first or got
            self.save()
        view = self.world.view()
        index = name_index(view)
        rows = []
        for row in json.loads(json.dumps(first["rows"])):
            dup = same_candidates(
                view, row["name"], near_ids=[], exclude=[], index=index
            )
            exact = [
                c
                for c in dup
                if (view.name_of(c.thing_id) or "").casefold() == row["name"].casefold()
            ]
            row["ticked"] = not exact
            if clear_tags:
                row["tag"] = None
            rows.append(row)
        step["choices"] = [
            f"{r['name']}: {'ticked' if r['ticked'] else 'unticked (in the world)'}{', tag cleared' if clear_tags else ''}"
            for r in rows
        ]
        done = await self.s.send("accept_group_add", thing_id=thing_id, rows=rows)
        step["accepted"] = done.get("thing_ids")
        step["notes"] = done.get("notes")
        step["page"] = thing_record(done)
        self.save()

    async def synopses(self) -> None:
        step: dict[str, Any] = {"step": "synopses", "groups": []}
        self.r["steps"].append(step)
        for key in ("velikoye", "tsardom"):
            thing_id = self.ids.get(key)
            if thing_id is None:
                continue
            page = await self.s.thing(thing_id)
            groups = [
                g
                for g in page["connected"]
                if g["tag"] is not None and len(g["rows"]) >= 2
            ][:3]
            if key == "velikoye":
                groups += [
                    g for g in page["connected"] if g["tag"] is None and g["rows"]
                ]
            for group in groups:
                entry: dict[str, Any] = {
                    "page": key,
                    "tag": group["tag"],
                    "members": [r.get("name") for r in group["rows"]],
                    "runs": [],
                }
                step["groups"].append(entry)
                for force in (False, True):
                    before = len(self.s.client.calls)
                    got = await self.s.retry(
                        "group_synopsis",
                        thing_id=thing_id,
                        tag=group["tag"],
                        force=force,
                    )
                    entry["runs"].append(
                        {"calls": self._calls(before), "synopsis": got["synopsis"]}
                    )
                    self.save()
        # a group gains a member: stale, no model call (Task 11's step 8)
        velikoye, court = self.ids.get("velikoye"), self.ids.get("nightcourt")
        if velikoye and court:
            before = len(self.s.client.calls)
            await self.s.send(
                "add_filing", thing_id=court, target_id=velikoye, role="convenes here"
            )
            page = await self.s.thing(velikoye)
            step["stale_after_add"] = [
                {
                    "tag": g["tag"],
                    "synopsis": g.get("synopsis"),
                    "rows": [r.get("name") for r in g["rows"]],
                }
                for g in page["connected"]
            ]
            step["stale_calls"] = self._calls(before)
        self.save()

    async def scene(self, setup: dict | None = None, prompt: str | None = None) -> None:
        sp = L["session_prompts"]
        prompt = prompt or sp["scene"]
        picks = await self.s.picks(prompt)
        before = len(self.s.client.calls)
        if setup is None:
            plan = await self.s.retry(
                "plan_scene",
                prompt=prompt,
                picks=picks,
                start=WorldDate.of(PRESENT).model_dump(),
            )
            setup = plan["setup"]
        started = await self.s.send("start_scene", setup=setup)
        scene_id = started["scene_id"]
        world = self.world
        record = world.scenes().get(scene_id)
        block = world_context_block(world, record, WorldDate.of(PRESENT))
        view = world.view(WorldDate.of(PRESENT))
        touched = touched_entries(view, record, reach=world.curation().timeline_reach)
        setup_text = "\n".join(p for p in (record.goal, record.premise) if p)
        roles = []
        for state in view.things():
            for filing in filings_of(view, state.id):
                if not filing.role:
                    continue
                roles.append(
                    {
                        "who": view.name_of(state.id),
                        "in": view.name_of(filing.target),
                        "role": filing.role,
                        "whole_word": role_named(filing.role, setup_text),
                        "substring": filing.role.casefold() in setup_text.casefold(),
                    }
                )
        step: dict[str, Any] = {
            "step": "scene",
            "prompt": prompt,
            "picks": picks,
            "setup": setup,
            "goal": record.goal,
            "premise": record.premise,
            "plan_calls": self._calls(before),
            "touched": [view.name_of(t) for t in touched],
            "world_block": block,
            "roles": roles,
            "turns": [],
        }
        self.r["steps"].append(step)
        self.save()
        scene = await harness._load(world, scene_id, self.s.client, memory=False)
        narrator = instance.get_agent("narrator")
        try:
            with ActiveScene(scene):
                for direction in L["scene"]["directions"]:
                    outputs = []
                    for _ in range(2):
                        before = len(self.s.client.calls)
                        text = await narrator.progress_story(
                            narrative_direction=direction
                        )
                        outputs.append({"output": text, "calls": self._calls(before)})
                        self.save()
                    await scene.push_history(
                        [NarratorMessage(outputs[0]["output"], source="ai")]
                    )
                    step["turns"].append({"direction": direction, "runs": outputs})
                    self.save()
        finally:
            close_world_scene(scene)


async def main(
    out: Path,
    label: str,
    root: Path,
    fake: bool,
    replay: str | None = None,
    retry: Sequence[str] = (),
    stop_after: str | None = None,
) -> None:
    harness._quiet_loading(False)
    embedding = TrigramEmbeddingFunction()
    MockMemoryAgent.embedding_function = property(lambda self: embedding)
    doc: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {"probe": "filing-flow", "runs": []}
    )
    client = Recorder(name="KoboldCpp")
    client.calls = []
    client.fake = fake
    client.lock = asyncio.Lock()
    client.replay = (
        [
            (c["prompt"], c["response"])
            for c in next(r for r in doc["runs"] if r["label"] == replay)["calls"]
        ]
        if replay
        else []
    )
    if not fake:
        await client.status()
    results: dict[str, Any] = {
        "label": label,
        "replayed_from": replay,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "model": getattr(client, "model_name", None),
        "fake": fake,
        "world_root": str(root),
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
        "create_world", name="Moscavia filing", present_year=PRESENT
    )
    results["world_id"] = created.get("id") if isinstance(created, dict) else None
    results["world_path"] = str(plugin.world.path)
    started = time.monotonic()
    run = Run(session, results, save)
    run.retry_keys = set(retry)
    run.stop_after = stop_after
    run.source = next((r for r in doc["runs"] if r["label"] == replay), None)
    results["retry"] = list(retry)
    try:
        await run.run()
    except StopSession as stop:
        results["stopped_after"] = str(stop)
    except Exception as exc:
        results["error"] = repr(exc)
        raise
    finally:
        results["ids"] = dict(run.ids)
        results["replay_missed_at"] = getattr(client, "replay_missed_at", None)
        results["replay_missed"] = sum(
            1 for c in client.calls if client.replay and not c.get("replayed")
        )
        results["minutes"] = round((time.monotonic() - started) / 60, 1)
        results["failures"] = session.failures
        save()
        plugin.disconnect()


async def scene_again(out: Path, label: str, source: str) -> None:
    """Run `source`'s scene again, on a copy of its kept world, with the
    same setup (no new plan): the World block and the narrator directions,
    each twice, as `label` -- the before/after of a fix on the same case."""

    harness._quiet_loading(False)
    embedding = TrigramEmbeddingFunction()
    MockMemoryAgent.embedding_function = property(lambda self: embedding)
    doc = json.loads(out.read_text())
    before_run = next(r for r in doc["runs"] if r["label"] == source)
    old_scene = next(s for s in before_run["steps"] if s.get("step") == "scene")
    client = Recorder(name="KoboldCpp")
    client.calls = []
    client.lock = asyncio.Lock()
    await client.status()
    results: dict[str, Any] = {
        "label": label,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "model": getattr(client, "model_name", None),
        "scene_of": source,
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
    tmp = Path(tempfile.mkdtemp(prefix="filing-scene-"))
    world_dir = tmp / Path(before_run["world_path"]).name
    shutil.copytree(before_run["world_path"], world_dir)
    os.chdir(tmp)
    plugin = WorldsPlugin(_Handler())
    plugin.worlds_root = tmp
    session = Session(plugin, client)
    await session.send("open_world", path=str(world_dir))
    results["world_path"] = str(world_dir)
    run = Run(session, results, save)
    run.ids = dict(before_run["ids"])
    try:
        await run.scene(setup=old_scene["setup"], prompt=old_scene["prompt"])
    finally:
        save()
        plugin.disconnect()


# --- code scores ---------------------------------------------------------------------


def _first_tag(tag: str | None) -> str | None:
    return tag.split(",")[0].strip().lower() if tag else None


def score(raw: Path, label: str) -> dict:
    doc = json.loads(raw.read_text())
    run = next(r for r in doc["runs"] if r["label"] == label)
    ids = run["ids"]
    by_id = {v: k for k, v in ids.items()}
    out: dict[str, Any] = {"drafts": {}, "totals": {}}
    t = {
        k: 0
        for k in (
            "in_expected",
            "in_found",
            "in_offered",
            "in_false_either",
            "in_false_strict",
            "in_unkeyed",
            "into_expected",
            "into_found",
            "into_offered",
            "into_false",
            "into_unkeyed",
            "tag_right",
            "tag_all",
            "reuse_cases",
            "reused",
        )
    }
    unkeyed: list[dict] = []
    for step in run["steps"]:
        if "versions" not in step:
            continue
        key = step["step"]
        rows = []
        for v in step["versions"]:
            lab_in = L["in"].get(key, {"expected": [], "either": []})
            lab_into = L["file_into"].get(key, {"expected": [], "either": []})
            offered = {}
            for f in v["filings"]:
                k = by_id.get(f["target_id"]) if f["target_id"] else None
                offered[f["target_id"] or f["new_name"]] = (
                    k,
                    f["target_name"],
                    f["role"],
                )
            got = {k for k, _, _ in offered.values() if k}
            found = [e for e in lab_in["expected"] if e in got]
            false_either, false_strict, unk = [], [], []
            for tid, (k, name, role) in offered.items():
                if k is None:
                    unk.append(name)
                    unkeyed.append(
                        {
                            "draft": key,
                            "version": v["version"],
                            "measure": "in",
                            "target": name,
                            "role": role,
                        }
                    )
                elif k in lab_in["expected"]:
                    continue
                elif k in lab_in["either"]:
                    false_strict.append(name)
                else:
                    false_either.append(name)
                    false_strict.append(name)
            into = {}
            for f in v["file_into"]:
                into[f["thing_id"]] = (by_id.get(f["thing_id"]), f["name"], f["role"])
            into_got = {k for k, _, _ in into.values() if k}
            into_found = [e for e in lab_into["expected"] if e in into_got]
            into_false, into_unk = [], []
            for tid, (k, name, role) in into.items():
                if k is None:
                    into_unk.append(name)
                    unkeyed.append(
                        {
                            "draft": key,
                            "version": v["version"],
                            "measure": "file_into",
                            "target": name,
                            "role": role,
                        }
                    )
                elif k not in lab_into["expected"] and k not in lab_into["either"]:
                    into_false.append(name)
            tag = _first_tag(v["tag"])
            ok = tag in L["tag"]["acceptable"].get(key, [])
            in_use = [
                x
                for x in v.get("tags_in_use", [])
                if x in L["tag"]["acceptable"].get(key, [])
            ]
            rows.append(
                {
                    "version": v["version"],
                    "name": v["name"],
                    "tag": v["tag"],
                    "tag_ok": ok,
                    "fitting_in_use": in_use,
                    "reused": bool(in_use) and tag in in_use,
                    "in_offered": [f"{n} ({r})" for _, n, r in offered.values()],
                    "in_found": found,
                    "in_missed": [e for e in lab_in["expected"] if e not in got],
                    "in_false_either": false_either,
                    "in_false_strict": false_strict,
                    "in_unkeyed": unk,
                    "into_offered": [f"{n} ({r})" for _, n, r in into.values()],
                    "into_found": into_found,
                    "into_false": into_false,
                    "into_unkeyed": into_unk,
                    "near_count": len(v.get("near", [])),
                    "new_names": [
                        f"{n['name']} ({n['kind']}, {n['tag']})" for n in v["new_names"]
                    ],
                }
            )
            t["in_expected"] += len(lab_in["expected"])
            t["in_found"] += len(found)
            t["in_offered"] += len(offered)
            t["in_false_either"] += len(false_either)
            t["in_false_strict"] += len(false_strict)
            t["in_unkeyed"] += len(unk)
            t["into_expected"] += len(lab_into["expected"])
            t["into_found"] += len(into_found)
            t["into_offered"] += len(into)
            t["into_false"] += len(into_false)
            t["into_unkeyed"] += len(into_unk)
            t["tag_all"] += 1
            t["tag_right"] += ok
            if in_use:
                t["reuse_cases"] += 1
                t["reused"] += tag in in_use
        out["drafts"][key] = rows
    out["totals"] = t
    out["unkeyed"] = unkeyed
    # F6: the Frosted Wing in the Host's near list
    host = next((s for s in run["steps"] if s.get("step") == "host"), None)
    if host:
        out["f6"] = {
            "paths": run.get("f6_before_host"),
            "versions": [
                {
                    "version": v["version"],
                    "near_count": len(v.get("near", [])),
                    "frosted_wing_rank": next(
                        (
                            i + 1
                            for i, line in enumerate(v.get("near", []))
                            if PATTERNS["frostedwing"].search(line.split(" (")[0])
                        ),
                        None,
                    ),
                }
                for v in host["versions"]
            ],
        }
    scene = next((s for s in run["steps"] if s.get("step") == "scene"), None)
    if scene:
        out["f4"] = {
            "goal": scene["goal"],
            "premise": scene["premise"],
            "touched": scene["touched"],
            "koroleva_touched": any(
                PATTERNS["koroleva"].search(n or "") for n in scene["touched"]
            ),
            "roles_whole_word": [r for r in scene["roles"] if r["whole_word"]],
            "roles_substring_only": [
                r for r in scene["roles"] if r["substring"] and not r["whole_word"]
            ],
        }
    # repeats and duplicates over the kept world (a temp copy)
    world_path = Path(run["world_path"])
    if world_path.exists():
        out["world"] = world_scores(world_path)
    # cost by uid
    cost: dict[str, dict] = {}
    for c in run["calls"]:
        entry = cost.setdefault(
            c.get("uid") or c["kind"],
            {"n": 0, "seconds": [], "prompt_tokens": [], "reply_tokens": []},
        )
        entry["n"] += 1
        entry["seconds"].append(c.get("seconds"))
        entry["prompt_tokens"].append(c.get("prompt_tokens"))
        entry["reply_tokens"].append(c.get("reply_tokens"))
    for entry in cost.values():
        for field in ("seconds", "prompt_tokens", "reply_tokens"):
            values = [x for x in entry[field] if isinstance(x, (int, float))]
            entry[field] = {
                "mean": round(sum(values) / len(values), 1) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
            }
    out["cost"] = cost
    out["calls"] = len(run["calls"])
    out["model_minutes"] = round(
        sum(c.get("seconds") or 0 for c in run["calls"]) / 60, 1
    )
    run["scores"] = out
    raw.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n")
    return out


def world_scores(world_dir: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "world"
        shutil.copytree(world_dir, target)
        world = World.open(target)
        view = world.view()
        facts = [
            {
                "id": f.fact_id,
                "owner": view.name_of(s.id),
                "owner_id": s.id,
                "text": view.render(f.text),
            }
            for s in view.things()
            for f in s.facts
        ]
        flagged = {}
        for threshold in (0.7, 0.5, 0.4):
            hits = []
            for a in facts:
                best = max(
                    (
                        (overlap(a["text"], b["text"]), b)
                        for b in facts
                        if b["id"] != a["id"]
                    ),
                    key=lambda x: x[0],
                    default=(0, None),
                )
                if best[0] >= threshold:
                    hits.append(
                        {
                            "fact": a["text"],
                            "owner": a["owner"],
                            "restates": best[1]["text"],
                            "restates_owner": best[1]["owner"],
                            "score": round(best[0], 2),
                        }
                    )
            flagged[str(threshold)] = {
                "count": len(hits),
                "facts": hits if threshold == 0.7 else hits[:0],
            }
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
                pairs.add(
                    (
                        tuple(
                            sorted(
                                [view.name_of(state.id), view.name_of(found.thing_id)]
                            )
                        ),
                        found.reason,
                    )
                )
        things = [
            {
                "name": view.name_of(t.id),
                "kind": t.kind,
                "tag": t.fields.get("tag"),
                "stub": t.is_stub,
                "filings": [
                    f"{view.name_of(f.target)} ({f.role})"
                    for f in filings_of(view, t.id)
                ],
                "facts": len(t.facts),
            }
            for t in view.things()
        ]
        world.close()
    return {
        "facts": len(facts),
        "things": len(things),
        "stubs": [t["name"] for t in things if t["stub"]],
        "repeats": flagged,
        "same_pairs": sorted([list(p) + [r] for p, r in pairs]),
        "world": things,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--label", default="run 1")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--score", action="store_true", help="score run --label of OUT")
    parser.add_argument("--replay", default=None, metavar="LABEL")
    parser.add_argument("--scene-of", default=None, metavar="LABEL")
    parser.add_argument("--retry", nargs="*", default=[], metavar="STEP")
    parser.add_argument("--stop-after", default=None, metavar="STEP")
    args = parser.parse_args()
    if args.scene_of:
        asyncio.run(scene_again(args.out.resolve(), args.label, args.scene_of))
    elif args.score:
        print(
            json.dumps(
                score(args.out.resolve(), args.label),
                indent=1,
                ensure_ascii=False,
                default=str,
            )[:20000]
        )
    else:
        if args.root is None:
            parser.error("a session needs --root")
        asyncio.run(
            main(
                args.out.resolve(),
                args.label,
                args.root.resolve(),
                args.fake,
                args.replay,
                args.retry,
                args.stop_after,
            )
        )
