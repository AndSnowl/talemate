"""Throwaway probe: languages 4c (spec
docs/superpowers/specs/2026-11-06-fantasymate-languages-4c-streamlining-design.md,
"Probe"). On a read-only copy of the owner's test-app world:

1. *Fill them in* on Zhelvan through Claude Code with the app's own names
   brief (`write_brief`, kind "names"): does it write `main` and
   descriptions?
2. On Skyfall (koboldcpp, the app's `preview_thing`), 15 labelled person
   prompts, each drafted twice:
   - A: the draft call itself is asked for the rule (the `create-thing`
     template patched for the run, restored after);
   - B: the plain draft, then a separate pick call (Task 4's prompt).
   Scored: the pick against the labels, today's `pick_rule` on the same
   draft, the other names each draft writes, and the time each takes.

Labels: docs/superpowers/probes/raw/2026-11-06-languages-4c-labels.json
(committed before any call). The owner said yes to this run.

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_4c.py OUT_DIR'
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_heritage_play as harness  # noqa: E402  (recording client)

from talemate.languages.entry import language_of  # noqa: E402
from talemate.languages.importer import export_language  # noqa: E402
from talemate.languages.making import MakeRequest  # noqa: E402
from talemate.languages.models import Language  # noqa: E402
from talemate.languages.person_names import choose, is_main, pick_rule  # noqa: E402
from talemate.world.store import World  # noqa: E402
from talemate.worldplay.create import json_objects, parse_person_block, preview_thing  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-11-06-languages-4c-labels.json"
WORLDS = REPO.parent / "languages-4b2/.superpowers/test-app/worlds"
TEMPLATE = REPO / "src/talemate/prompts/templates/world/create-thing.jinja2"

PICK_PROMPT = """\
You pick the naming rule for a character in an invented language, the way
a careful author would: from who the character is.

The language's naming rules for people:
{rules}

The character:
{character}

Reply with only one JSON object: {{"rule": "<one rule id from the list>",
"sex": "man" or "woman", "rank": "<one word for their standing>"}}"""


def _copy() -> Path:
    folder = next(f for f in WORLDS.iterdir() if (f / "world.sqlite").exists())
    root = Path(tempfile.mkdtemp(prefix="probe4c-")) / folder.name
    root.mkdir(parents=True)
    for sub in ("assets", "index"):
        (root / sub).mkdir()
    src = sqlite3.connect(f"file:{folder / 'world.sqlite'}?mode=ro", uri=True)
    dst = sqlite3.connect(root / "world.sqlite")
    src.backup(dst)
    dst.close()
    src.close()
    return root


def _json(text: str) -> dict:
    found = re.search(r"\{.*\}", text, re.S)
    return json.loads(found.group(0)) if found else {}


def _people_rules(language: Language) -> list:
    return [
        g
        for g in language.generators
        if g.use in ("character", "people") and is_main(language, g)
    ]


def _rules_text(language: Language) -> str:
    lines = []
    for g in _people_rules(language):
        hint = f" [for: {', '.join(g.for_person.values())}]" if g.for_person else ""
        lines.append(f"- {g.id}: {g.name} — {g.description or '(no description)'}{hint}")
    return "\n".join(lines)


def category(generator) -> str:
    text = " ".join(
        [generator.id, generator.name, generator.description, *generator.for_person.values()]
    ).lower()
    if re.search(r"tsar|gosmar|sovereign|throne|royal|ruler|king|queen|heir", text):
        return "sovereign"
    if "owl" in text:
        return "owl"
    if re.search(r"noble|boyar|lord|lady|house|duke", text):
        return "noble"
    return "common"


def score(language: Language, rule_id: str, label: dict) -> bool:
    generator = next((g for g in language.generators if g.id == rule_id), None)
    if generator is None:
        return False
    sex = generator.for_person.get("sex")
    return category(generator) == label["kind"] and (
        label["sex"] == "any" or sex is None or sex == label["sex"]
    )


def fill(world_dir: Path, out: Path, run: dict) -> Language:
    world = World.open(world_dir)
    view = world.view()
    state = next(
        s for s in view.things("language", facts=False) if view.name_of(s.id) == "Zhelvan"
    )
    current = export_language(view, state.id)
    cached = out / "fill-reply.txt"
    t0 = time.time()
    if cached.exists():
        reply = cached.read_text()
    else:
        # the app's own route: Claude Code in a scratch folder, with the
        # check command and its repairs (`making.make_language`)
        from talemate.languages.making import MakeSettings, make_language
        from talemate.languages.entry import used_words

        reply = asyncio.run(
            make_language(
                view,
                MakeRequest(kind="names", target_id=state.id, text=""),
                MakeSettings(route="claude_code", claude_model="opus"),
                None,
                lambda line: print("  fill:", line[:120], flush=True),
                current=current,
                used=sorted(used_words(view, state.id)),
            )
        )
        cached.write_text(reply)
    run["fill"] = {"seconds": int(time.time() - t0), "reply": reply[:2000]}
    got, _ = json.JSONDecoder().raw_decode(reply[reply.index("{"):])
    data = got.get("language", got)
    filled = Language.model_validate({**language_of(view.thing(state.id)).model_dump(), **data})
    run["fill"]["rules"] = [
        {"id": g.id, "name": g.name, "main": is_main(filled, g), "description": g.description,
         "for_person": g.for_person, "category": category(g)}
        for g in filled.generators
    ]  # fmt: skip
    (out / "probe-4c.json").write_text(json.dumps(run, indent=1, ensure_ascii=False))
    print("fill", run["fill"]["seconds"], "s;", sum(1 for r in run["fill"]["rules"] if r["description"]), "descriptions", flush=True)
    return filled


def _patch_template(rules: str) -> str:
    original = TEMPLATE.read_text()
    patched = original.replace(
        '"title": ""}, {% endif %}"aka":',
        '"title": "", "rule": ""}, {% endif %}"aka":',
    ).replace(
        'such as "Lady" or "Captain", else "".',
        'such as "Lady" or "Captain", else ""; "rule" is the id of the naming rule '
        "that fits them, from:\n" + rules.replace("{", "(").replace("}", ")") + "\n",
    )
    assert patched != original, "the person block wasn't found"
    TEMPLATE.write_text(patched)
    return original


async def drafts(world_dir: Path, language: Language, out: Path, run: dict) -> None:
    labels = json.loads(LABELS.read_text())["person"]
    client = harness.RecordingClient(name="KoboldCpp")
    await client.status()
    run["model"] = client.model_name
    rules = _rules_text(language)
    run["rules_shown"] = rules
    run["person"] = []

    async def draft(prompt: str) -> tuple[Any, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "w"
            shutil.copytree(world_dir, copy)
            world = World.open(copy)
            client.calls = []
            preview = await preview_thing(world, "character", prompt, {}, client, ask_same=False)
            create = next((c for c in client.calls if '"person"' in c["prompt"]), None)
            return preview, create or {}

    for label in labels:
        row: dict[str, Any] = {**label}
        # B: the plain draft, then the pick call
        preview, create = await draft(label["prompt"])
        person = parse_person_block(create.get("response", ""))
        row["b_draft_seconds"] = create.get("seconds")
        row["b_aka"] = [a.get("name") for a in preview.aka]
        row["b_name"] = preview.name
        baseline = pick_rule(language, choose(language, person))
        row["baseline"] = baseline.id
        row["baseline_ok"] = score(language, baseline.id, label)
        character = label["prompt"] + "\n" + "\n".join(f"- {f.text}" for f in preview.facts)
        from probe_language_make import chat_messages  # noqa: E402
        import ai_helpers  # noqa: E402

        url = ai_helpers.koboldcpp_url()
        t0 = time.time()
        reply = chat_messages(
            url,
            [{"role": "user", "content": PICK_PROMPT.format(rules=rules, character=character)}],
            max_tokens=200,
        )
        row["b_pick_seconds"] = round(time.time() - t0, 1)
        got = _json(reply)
        row["b_pick"] = got.get("rule", "")
        row["b_ok"] = score(language, row["b_pick"], label)
        run["person"].append(row)
        (out / "probe-4c.json").write_text(json.dumps(run, indent=1, ensure_ascii=False))
        print(label["prompt"][:40], "| base", row["baseline"], row["baseline_ok"], "| B", row["b_pick"], row["b_ok"], flush=True)

    original = _patch_template(rules)
    try:
        for row in run["person"]:
            preview, create = await draft(row["prompt"])
            objects = [o for o in json_objects(create.get("response", "")) if "rule" in o]
            row["a_pick"] = str(objects[0].get("rule", "")) if objects else ""
            row["a_ok"] = score(language, row["a_pick"], row)
            row["a_draft_seconds"] = create.get("seconds")
            row["a_aka"] = [a.get("name") for a in preview.aka]
            row["a_name"] = preview.name
            (out / "probe-4c.json").write_text(json.dumps(run, indent=1, ensure_ascii=False))
            print(row["prompt"][:40], "| A", row["a_pick"], row["a_ok"], flush=True)
    finally:
        TEMPLATE.write_text(original)

    rows = run["person"]
    run["score"] = {
        "baseline": sum(r["baseline_ok"] for r in rows),
        "a": sum(r.get("a_ok", False) for r in rows),
        "b": sum(r["b_ok"] for r in rows),
        "of": len(rows),
        "a_aka": sum(len(r.get("a_aka", [])) for r in rows),
        "b_aka": sum(len(r["b_aka"]) for r in rows),
    }
    (out / "probe-4c.json").write_text(json.dumps(run, indent=1, ensure_ascii=False))
    print(run["score"], flush=True)


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    run: dict = {}
    world_dir = _copy()
    language = fill(world_dir, out, run)
    asyncio.run(drafts(world_dir, language, out, run))


if __name__ == "__main__":
    main()
