"""Throwaway probe: languages 4b-2 (spec
docs/superpowers/specs/2026-11-04-fantasymate-languages-4b2-people-names-design.md,
"Probe"). Two stages, on copies of the owner's test-app worlds (read only):

a. *The draft's person block* on the world model (Skyfall on koboldcpp,
   Talemate's own client): 15 labelled person prompts drafted through the
   app's `preview_thing`; the create call's `person` block is scored for
   parsing, sex and rank.
b. *Fill them in for people's names* on the agent route (Claude Code,
   `claude -p`, no tools): each language's naming prose, its rules and the
   schema in; `people_names` and people rules out, checked and built into
   sample names for reading by hand.

Labels: docs/superpowers/probes/raw/2026-11-04-languages-4b2-labels.json
(committed before any call). The owner allowed every AI run of 4b-2::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_4b2.py OUT.json --stage a|b'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_4b1  # noqa: E402  (world copies)
import probe_heritage_play as harness  # noqa: E402  (recording client)

from talemate.languages.check import check_language  # noqa: E402
from talemate.languages.entry import language_of  # noqa: E402
from talemate.languages.models import GENERATOR_USES, GeneratorDef, Language, PeopleNames  # noqa: E402
from talemate.languages.person_names import (  # noqa: E402
    Connection,
    PersonContext,
    build_person_name,
    roll_pet_name,
)
from talemate.world.store import World  # noqa: E402
from talemate.worldplay.create import json_objects, preview_thing  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-11-04-languages-4b2-labels.json"

FILL_PROMPT = """\
You turn a constructed language's naming customs into machine rules for building
people's names. Below are the language's grammar sections (prose, tables,
examples), its current name rules, and the JSON schemas.

Write:
1. "people_names": the choices a person's name depends on ("sex", "rank", and
   any other the customs use, such as "married"; each list's first value is the
   default), the titles the language keeps in its own word (each {{word,
   meaning}}, the meaning in English; only titles the prose says are used in its
   own word), and forms of address ({{kind, roles, uses, default}}: how family,
   friends, strangers... address someone, "uses" naming the name-part labels,
   "title" or "pet name"; exactly one row is the default, for strangers).
2. "generators": the people rules, as composed rules with "shapes" of "parts".
   A part is one of: "rule" (another rule, by id), "word" (a fixed word; set
   "english" to its English writing, such as "of" for "di", unless the prose
   says the native word is used in English text), "meaning", "connection" (a
   part taken from a parent or other connection: "roles" are role words in
   order of preference, such as ["father", "mother"]; "take" the label of the
   connection's own part to take, such as "family"; "rule" the rule rolled when
   there's no such connection), "own" (this person's own part, by "take"; used
   by pet-name rules, "use": "pet names"). Give each part a short "label"
   ("given", "family", "house"...). "person_forms" are forms by who the person
   is: [{{"when": {{"sex": "woman"}}, "changes": [...]}}], changes as in
   name_grammar. "for_person" says who a rule is for: {{"sex": "woman", "rank":
   "noble"}}. Keep rule ids the language already has when you change them; you
   may add a pet-name rule if the prose has pet names or diminutives.
A rule's "use" is one of: {uses}. People rules use "character"; a rule that
is only a piece of a name (given names, family names) may also be "character"
and is used by the full-name rules as a "rule" part; full-name rules carry
"for_person". A change is {{"when", "kind", "text", "drop"}}: "kind" is
"ending" (add `text`), "swap" (take off one of the "|"-listed endings in
`drop`, add `text`), "word_before", "word_after" or "double"; "when" is ""
(always), "after_vowel", "after_consonant", "before_vowel" or "ends:a|o" (the
word ends with one of the listed letters) and nothing else. A pet-name rule
must change the name (an ending meaning small or dear, a clipping), never
give it back as it is.
Every rule must build the examples the prose gives. Reply with the JSON object
only: {{"people_names": {{...}}, "generators": [...]}}.

Schemas:
{schema}

Current name rules:
{rules}

Grammar:
{grammar}
"""


def _json(text: str) -> dict:
    found = re.search(r"\{.*\}", text, re.S)
    return json.loads(found.group(0)) if found else {}


def _person_block(response: str) -> dict:
    for obj in json_objects(response):
        if isinstance(obj.get("person"), dict):
            return obj["person"]
    return {}


async def stage_a(run: dict, save) -> None:
    labels = json.loads(LABELS.read_text())
    copies = probe_4b1._copies()
    client = harness.RecordingClient(name="KoboldCpp")
    await client.status()
    run["model"] = client.model_name
    run["person"] = []
    for item in labels["person"]:
        with tempfile.TemporaryDirectory() as tmp:
            # a fresh copy per prompt: the draft writes nothing, but be safe
            folder = Path(tmp) / "w"
            import shutil

            shutil.copytree(copies[item["world"]], folder)
            world = World.open(folder)
            client.calls = []
            entry: dict[str, Any] = {**item}
            try:
                await preview_thing(world, "character", item["prompt"], {}, client, ask_same=False)
            except Exception as exc:  # a bad reply is a finding
                entry["error"] = repr(exc)
            create = next((c for c in client.calls if '"person"' in c["prompt"]), None)
            reply = create["response"] if create else ""
            block = _person_block(reply)
            entry["reply_head"] = reply[:600]
            entry["seconds"] = create["seconds"] if create else None
            entry["block"] = block
            entry["parsed"] = bool(block)
            sex = str(block.get("sex") or "").lower()
            entry["sex_ok"] = item["sex"] == "any" or sex == item["sex"]
            entry["rank_ok"] = str(block.get("rank") or "").lower() in item["ranks"]
            run["person"].append(entry)
            save()
            print(item["prompt"][:40], block, flush=True)
    rows = run["person"]
    run["score"] = {
        "parsed": sum(r["parsed"] for r in rows),
        "sex": sum(r["sex_ok"] for r in rows),
        "rank": sum(r["rank_ok"] for r in rows),
        "of": len(rows),
    }
    print(run["score"])


def _schema() -> str:
    return json.dumps(
        {
            "people_names": PeopleNames.model_json_schema(),
            "generator": GeneratorDef.model_json_schema(),
        },
        indent=1,
    )


def _samples(language: Language) -> list[dict]:
    """Names built for each choice, with a parent built first (a father,
    then a mother), for reading by hand."""

    out = []
    choices = language.people_names.choices if language.people_names else {}
    sexes = choices.get("sex") or ["man", "woman"]
    ranks = choices.get("rank") or [""]
    rng = random.Random(7)
    for rank in ranks:
        father = build_person_name(
            language, PersonContext(built_as={"sex": "man", "rank": rank}), rng=rng
        )
        parent = Connection(
            role="child of",
            thing_id="f" * 32,
            name=father.name,
            parts={p.label: p.text for p in father.parts},
            built_as=father.built_as,
        )
        for sex in sexes:
            child = build_person_name(
                language,
                PersonContext(built_as={"sex": sex, "rank": rank}, connections=[parent]),
                rng=rng,
            )
            pet = roll_pet_name(language, {p.label: p.text for p in child.parts}, rng)
            out.append(
                {
                    "rank": rank,
                    "sex": sex,
                    "father": father.name,
                    "child": child.name,
                    "rule": child.rule_id,
                    "parts": [(p.label, p.text, p.source) for p in child.parts],
                    "pet": pet[0] if pet else None,
                    "orphan_missing": [
                        m.model_dump()
                        for m in build_person_name(
                            language, PersonContext(built_as={"sex": sex, "rank": rank}), rng=rng
                        ).missing
                    ],
                }
            )
    return out


def stage_b(run: dict, save) -> None:
    run["fill"] = {}
    for world_name, folder in probe_4b1._copies().items():
        world = World.open(folder)
        view = world.view()
        for state in view.things("language", facts=False):
            language = language_of(view.thing(state.id))
            prompt = FILL_PROMPT.format(
                uses=", ".join(sorted(GENERATOR_USES)),
                schema=_schema(),
                rules=json.dumps([g.model_dump() for g in language.generators], ensure_ascii=False),
                grammar=json.dumps([s.model_dump(mode="json") for s in language.grammar], ensure_ascii=False),
            )
            done = subprocess.run(
                ["claude", "-p", prompt, "--model", "opus", "--tools", "",
                 "--no-session-persistence", "--output-format", "text"],
                capture_output=True, text=True, timeout=1200,
            )  # fmt: skip
            entry: dict[str, Any] = {"world": world_name, "reply": done.stdout}
            try:
                got = _json(done.stdout)
                new = {g["id"]: g for g in got.get("generators") or []}
                generators = [new.pop(g.id, g.model_dump()) for g in language.generators]
                generators += list(new.values())
                filled = Language.model_validate(
                    {**language.model_dump(), "generators": generators, "people_names": got.get("people_names")}
                )
                report = check_language(filled, samples=3)
                entry["blocking"] = report.blocking
                entry["warnings"] = [w for w in report.warnings if "rule" in w or "address" in w or "choice" in w]
                entry["people_names"] = filled.people_names.model_dump() if filled.people_names else None
                entry["samples"] = _samples(filled)
            except Exception as exc:
                entry["error"] = repr(exc)
            run["fill"][language.name] = entry
            save()
            print(language.name, entry.get("error") or entry.get("blocking"), flush=True)
            for sample in entry.get("samples", [])[:6]:
                print("  ", sample["rank"], sample["sex"], "|", sample["father"], "->", sample["child"], "| pet", sample["pet"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--stage", choices=["a", "b"], required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    run: dict = json.loads(out.read_text()) if out.exists() else {}

    def save() -> None:
        out.write_text(json.dumps(run, indent=1, ensure_ascii=False, default=str) + "\n")

    os.chdir(tempfile.mkdtemp(prefix="probe4b2-"))
    if args.stage == "a":
        asyncio.run(stage_a(run, save))
    else:
        stage_b(run, save)
    save()


if __name__ == "__main__":
    main()
