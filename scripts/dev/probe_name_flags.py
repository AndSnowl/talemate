"""Throwaway probe: catching bad names in drafts (languages plan 1, Task 6;
spec part 2, probe 2).

Three stages:

1. *Baseline.* Each of the labels' five create prompts goes twice through
   the app's own `create.preview_thing` (prose skipped, `ask_same=False`) in
   a fresh scratch world, on Talemate's KoboldCpp client
   (`probe_heritage_play.RecordingClient`), as `probe_tags_kind_names.py`
   does. Every name the preview proposes (its own name, its other names and
   its new names) is recorded with `real_word_hits` against probe 1's real
   word list: how often real names leak into a draft today.
2. *Flag.* The 60 labelled names go to the model in batches of 15, each
   with its one-line context; the model labels each "real", "stock-title"
   or "ok" and says why. Scored with `language_probe_metrics.flag_scores`.
3. *Rewrite.* Each name labelled `stock-title` goes to the model for a
   fresher, more specific title with a `{name}` slot; the slot is filled
   with a name rolled from the labels' small test language, for the owner
   to judge.

Stages 2 and 3 use koboldcpp's chat endpoint (`probe_language_make.
chat_messages`). Labels: docs/superpowers/probes/raw/
2026-10-28-name-flags-labels.json (committed before any call). Not a test:
it calls koboldcpp, one call at a time; the owner approved this plan's
probes in advance (2026-10-28)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_name_flags.py OUT.json --label skyfall'

``--fake`` swaps the model for canned replies (a dry run, no network; the
baseline stage is skipped). Findings:
docs/superpowers/probes/2026-10-28-name-flags.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_helpers  # noqa: E402
import probe_heritage_play as harness  # noqa: E402
from language_probe_metrics import flag_scores, real_word_hits  # noqa: E402
from probe_fact_roundtrip import _extract_json  # noqa: E402
from probe_language_make import chat_messages  # noqa: E402

import talemate.worldplay.create as create  # noqa: E402
from talemate.languages.generator import roll  # noqa: E402
from talemate.languages.models import Language  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.store import World  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-28-name-flags-labels.json"
REAL = REPO / "docs/superpowers/probes/raw/2026-10-28-language-make-labels.json"
BATCH = 15

FLAG_SYSTEM = """\
You check names written for an invented fantasy world. For each name, say which
it is:
- "real": a real-world place, person, river, institution or event (or a thin
  disguise of one), which doesn't belong in an invented world;
- "stock-title": a generic, overused fantasy title anyone could have written
  ("the Northern Kingdom", "the Dark Forest"), with nothing specific in it;
- "ok": an invented name, or a title with something specific in it.
Reply with JSON only: {"names": [{"name": "<as given>", "label": "real"|"stock-title"|"ok", "why": "<a few words>"}]}"""

REWRITE_SYSTEM = """\
You rewrite generic fantasy titles into fresher, more specific ones for an
invented world. Keep what the thing is (a league of cities stays a league of
cities) but make the title its own. Put {name} where the place's or people's
own name goes; the name is filled in later from the world's language. Reply
with JSON only: {"title": "<the new title with {name}>", "why": "<a few words>"}"""


def fake_chat(messages: list[dict]) -> str:
    """Canned replies for `--fake`."""
    system = messages[0]["content"]
    if system == FLAG_SYSTEM:
        names = [
            line.split(" -- ")[0].lstrip("- ")
            for line in messages[1]["content"].splitlines()
            if line.startswith("- ")
        ]
        return json.dumps(
            {"names": [{"name": n, "label": "ok", "why": "fake"} for n in names]}
        )
    return json.dumps({"title": "Free Provinces of {name}", "why": "fake"})


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


async def baseline(labels: dict, real: list[str], run: dict, save: Callable) -> None:
    """Stage 1: what names a draft proposes today."""
    create._preview_prose = _no_prose
    client = harness.RecordingClient(name="KoboldCpp")
    await client.status()
    run["baseline_model"] = client.model_name
    client.calls = run.setdefault("baseline_calls", [])
    client.on_call = save
    rows = run.setdefault("baseline", [])
    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        for i, item in enumerate(labels["baseline_prompts"]):
            for version in (1, 2):
                world = World.create(
                    f"Flags {i}-{version}", root=Path(root) / f"{i}-{version}"
                )
                world.set_present(WorldDate.of(1000))
                row: dict[str, Any] = {"prompt": item["prompt"], "version": version}
                try:
                    preview = await create.preview_thing(
                        world,
                        item["kind"],
                        item["prompt"],
                        {},
                        client,
                        ask_same=False,
                        hint=item.get("hint"),
                    )
                    names = [preview.name]
                    names += [a.get("name", "") for a in preview.aka if a.get("name")]
                    names += [n.name for n in preview.new_names]
                    row["names"] = names
                    row["real_hits"] = real_word_hits(names, real)
                except Exception as exc:  # a bad reply is a finding
                    row["error"] = repr(exc)
                rows.append(row)
                save()


def flag(send: Callable, labels: dict, run: dict, save: Callable) -> None:
    """Stage 2: the model labels the labelled names."""
    names = labels["names"]
    flagged: dict[str, str] = {}
    replies = run.setdefault("flag_replies", [])
    for start in range(0, len(names), BATCH):
        batch = names[start : start + BATCH]
        user = "\n".join(f"- {n['name']} -- {n['context']}" for n in batch)
        reply = send(
            [
                {"role": "system", "content": FLAG_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        parsed = _extract_json(reply, "{", "}") or {}
        replies.append({"reply": reply, "parsed": parsed})
        for row in parsed.get("names", []):
            if isinstance(row, dict) and row.get("name"):
                flagged[row["name"]] = row.get("label", "ok")
        save()
    run["flagged"] = flagged
    run["scores"] = flag_scores({n["name"]: n["label"] for n in names}, flagged)
    save()


def rewrite(send: Callable, labels: dict, run: dict, save: Callable) -> None:
    """Stage 3: stock titles rewritten with a {name} slot, filled from the
    test language."""
    language = Language.model_validate(labels["test_language"])
    rng = random.Random(11)
    rows = run.setdefault("rewrites", [])
    for n in labels["names"]:
        if n["label"] != "stock-title":
            continue
        reply = send(
            [
                {"role": "system", "content": REWRITE_SYSTEM},
                {"role": "user", "content": f"{n['name']} -- {n['context']}"},
            ]
        )
        parsed = _extract_json(reply, "{", "}") or {}
        title = parsed.get("title", "")
        name = roll(language, "places", count=1, rng=rng)[0]
        rows.append(
            {
                "original": n["name"],
                "title": title,
                "has_slot": "{name}" in title,
                "filled": title.replace("{name}", name) if title else "",
                "why": parsed.get("why"),
            }
        )
        save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()

    labels = json.loads(LABELS.read_text())
    real = json.loads(REAL.read_text())["real_words"]
    results = json.loads(out.read_text()) if out.exists() else {"runs": {}}
    run: dict[str, Any] = {}
    results["runs"][args.label] = run

    def save() -> None:
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))

    if args.fake:
        run["model"] = "fake"
        send = fake_chat
    else:
        harness._quiet_loading(False)
        url = ai_helpers.koboldcpp_url()
        run["model"] = ai_helpers.koboldcpp_model(url)
        send = lambda messages: chat_messages(url, messages, max_tokens=3000)  # noqa: E731
        asyncio.run(baseline(labels, real, run, save))
    flag(send, labels, run, save)
    rewrite(send, labels, run, save)
    save()
    print(f"{args.label}: {run['model']} -> {out}")


if __name__ == "__main__":
    main()
