"""Throwaway probe: do untagged lore and event stubs come back tagged with
their kind's name? (hubs round 1, Task 2 follow-up).

A fresh scratch world (`world` in the labels) with six untagged stubs, each
named in one fact; each stub is expanded through the app's own
`create.preview_thing` with its suggested prompt (`mentions.
suggested_prompt`, as Expand starts the box), `ask_same=False` and the
prose skipped (it asks nothing about the tag). Two versions per stub. The
raw reply's "tag" (before `clean_tag`) and the preview's tag are recorded
with the template's tag-rule lines, so a run says which wording it used.

Labels: docs/superpowers/probes/raw/2026-10-24-tags-kind-names-labels.json
(committed before any call). Not a test: it calls Skyfall, one call at a
time (owner's standing permission)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_tags_kind_names.py OUT.json --label before'

Findings: docs/superpowers/probes/2026-10-24-tags-kind-names.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_heritage_play as harness  # noqa: E402  (config, recording client)

import talemate.worldplay.create as create  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.kinds import AKA_TAGS, KINDS  # noqa: E402
from talemate.world.refs import ref  # noqa: E402
from talemate.world.store import Source, World  # noqa: E402
from talemate.worldplay.mentions import suggested_prompt  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-24-tags-kind-names-labels.json"
TEMPLATE = REPO / "src/talemate/prompts/templates/world/create-thing.jinja2"


def build(root: Path, labels: dict) -> tuple[World, dict[str, str]]:
    world = World.create("Tags probe", root=root)
    world.set_present(WorldDate.of(1000))
    cases = labels["cases"]
    ids: dict[str, str] = {}
    with world.revision(Source.manual(note="probe")) as rev:
        for case in cases.values():
            ids[case["name"]] = rev.create_thing(
                case["kind"], {"name": case["name"], "stub": {"ignored": False}}
            )
        for key, entry in labels["world"].items():
            fields: dict[str, Any] = {"name": entry["name"], "tag": entry["tag"]}
            if entry.get("in"):
                fields["filings"] = [
                    {"target": ids[labels["world"][entry["in"]]["name"]], "role": None}
                ]
            ids[entry["name"]] = thing = rev.create_thing(entry["kind"], fields)
            for text in entry["facts"]:
                for case in cases.values():
                    name = case["name"]
                    bare = name.removeprefix("The ")
                    for written in (name, bare):
                        if written in text:
                            text = text.replace(written, ref(ids[name], written), 1)
                            break
                rev.add_fact(thing, "general", text)
    return world, ids


def raw_tag(reply: str) -> object:
    objects = create.json_objects(reply)
    for obj in objects:
        if isinstance(obj.get("facts"), list):
            return obj.get("tag")
    return create._cut_off_tag(reply)


def score(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip(" ."):
        return "none"
    first = raw.split(",")[0].strip(" .").lower()
    return "kind" if first in KINDS or first in AKA_TAGS else "tagged"


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


async def main(out: Path, label: str, runs: int) -> None:
    labels = json.loads(LABELS.read_text())
    harness._quiet_loading(False)
    results: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {"probe": "tags-kind-names", "runs": {}}
    )
    rule_lines = [
        line
        for line in TEMPLATE.read_text().splitlines()
        if line.startswith('- "tag":') or "kind's own name" in line
    ]
    run: dict[str, Any] = {"template_tag_lines": rule_lines, "rows": [], "calls": []}
    results["runs"][label] = run

    def save() -> None:
        out.write_text(
            json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n"
        )

    create._preview_prose = _no_prose
    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        client = harness.RecordingClient(name="KoboldCpp")
        await client.status()
        results["model"] = client.model_name
        client.calls = run["calls"]
        client.on_call = save
        for key, case in labels["cases"].items():
            for version in range(1, runs + 1):
                world, ids = build(Path(root) / f"{key}-{version}", labels)
                try:
                    stub = ids[case["name"]]
                    prompt = suggested_prompt(world.view(), stub)
                    before = len(client.calls)
                    error = None
                    preview = None
                    try:
                        preview = await create.preview_thing(
                            world,
                            case["kind"],
                            prompt,
                            {},
                            client,
                            stub_id=stub,
                            ask_same=False,
                        )
                    except Exception as exc:  # a bad reply is a finding
                        error = repr(exc)
                    reply = (
                        client.calls[before]["response"]
                        if len(client.calls) > before
                        else ""
                    )
                    raw = raw_tag(reply)
                    row = {
                        "case": key,
                        "kind": case["kind"],
                        "version": version,
                        "prompt_text": prompt,
                        "raw_tag": raw,
                        "score": score(raw),
                        "tag": preview.tag if preview is not None else None,
                        "fits": (preview.tag in case["fits"])
                        if preview is not None and preview.tag
                        else False,
                        "seconds": client.calls[before]["seconds"]
                        if len(client.calls) > before
                        else None,
                        "error": error,
                    }
                    run["rows"].append(row)
                    save()
                    print(
                        label,
                        key,
                        version,
                        repr(raw),
                        row["score"],
                        row["tag"],
                        error,
                        flush=True,
                    )
                finally:
                    world.close()
    rows = run["rows"]
    run["counts"] = {
        kind: {
            s: sum(1 for r in rows if r["kind"] == kind and r["score"] == s)
            for s in ("kind", "none", "tagged")
        }
        for kind in ("lore", "event")
    }
    save()
    print(json.dumps(run["counts"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()
    asyncio.run(main(args.out.resolve(), args.label, args.runs))
