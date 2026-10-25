"""Throwaway probe: do "+ Add facts" drafts propose stubs for the new
names their facts write? (hubs round 2, hiccup 2, ruling H8).

The owner's case: "+ Add facts" on the Tsardom of Moscavia wrote "Tsar
Ivan III" and "Tsar Alexei II" as plain words. `--world` is a COPY of the
owner's acceptance world (made with the sqlite backup API; never the live
one). It is copied again into a temp dir with the backup API, the owner's
add-facts revision and the hand stubs after it are undone (the labels'
`undo_revs`), and the labels' prompt is drafted through the app's own
`worldplay.facts.draft_facts`, `calls_per_run` times, one call at a time.
Each draft's facts (with `names.unknown_proper_phrases` per fact, a
starting list for the hand count) and its proposed new names (none before
the change) are recorded with the template's names lines, so a run says
which wording it used.

Labels: docs/superpowers/probes/raw/2026-10-25-add-facts-names-labels.json
(committed before any call). Not a test: it calls Skyfall, one call at a
time (owner's approval)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_add_facts_names.py OUT.json --world COPY --label before'

Findings: docs/superpowers/probes/2026-10-25-add-facts-names.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_heritage_play as harness  # noqa: E402  (config, recording client)

from talemate.world.names import unknown_proper_phrases  # noqa: E402
from talemate.world.store import World  # noqa: E402
from talemate.worldplay import facts as facts_mod  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-25-add-facts-names-labels.json"
TEMPLATE = REPO / "src/talemate/prompts/templates/world/add-facts.jinja2"


def copy_world(source: Path, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("assets", "index"):
        (root / sub).mkdir(exist_ok=True)
    src = sqlite3.connect(f"file:{source / 'world.sqlite'}?mode=ro", uri=True)
    dst = sqlite3.connect(root / "world.sqlite")
    src.backup(dst)
    dst.close()
    src.close()
    return root


async def main(out: Path, world_copy: Path, label: str) -> None:
    labels = json.loads(LABELS.read_text())
    harness._quiet_loading(False)
    results: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {"probe": "add-facts-names", "runs": {}}
    )
    names_lines = [
        line
        for line in TEMPLATE.read_text().splitlines()
        if line.startswith('- "names":') or line.startswith("- Only named things")
    ]
    run: dict[str, Any] = {"template_names_lines": names_lines, "rows": [], "calls": []}
    results["runs"][label] = run

    def save() -> None:
        out.write_text(
            json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n"
        )

    entry = labels["entry"]["id"]
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        world = World.open(copy_world(world_copy, Path(tmp) / "world"))
        try:
            world.undo(labels["undo_revs"], note="probe: as it was")
            client = harness.RecordingClient(name="KoboldCpp")
            await client.status()
            results["model"] = client.model_name
            client.calls = run["calls"]
            client.on_call = save
            for call in range(1, labels["calls_per_run"] + 1):
                before = len(client.calls)
                error = None
                draft = None
                try:
                    draft = await facts_mod.draft_facts(
                        world, entry, labels["prompt"], client
                    )
                except Exception as exc:  # a bad reply is a finding
                    error = repr(exc)
                view = world.view()
                facts = [
                    {
                        "text": f.text,
                        "category": f.category,
                        "unknown_phrases": [
                            u.text for u in unknown_proper_phrases(view, f.text)
                        ],
                    }
                    for f in (draft.facts if draft is not None else [])
                ]
                new_names = [
                    {
                        "name": n.name,
                        "kind": n.kind,
                        "tag": n.tag,
                        "written": n.written,
                        "aka": n.aka,
                        "filing": n.filing.model_dump() if n.filing else None,
                        "same_as": [o.name for o in n.same_as],
                    }
                    for n in (getattr(draft, "new_names", None) or [])
                ]
                row = {
                    "call": call,
                    "facts": facts,
                    "new_names": new_names,
                    "seconds": client.calls[before]["seconds"]
                    if len(client.calls) > before
                    else None,
                    "error": error,
                }
                run["rows"].append(row)
                save()
                print(label, call, json.dumps(row, ensure_ascii=False), flush=True)
        finally:
            world.close()
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.out.resolve(), args.world.resolve(), args.label))
