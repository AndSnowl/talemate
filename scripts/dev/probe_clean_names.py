"""Throwaway probe: cleaning names in drafts (languages part 4, probe 4;
spec docs/superpowers/specs/2026-10-30-fantasymate-languages-4-design.md).

Stages (probe 4's 1 to 4; its 5, composed rules on Claude Code, is 4b's
and runs later):

1. *Baseline.* probe 2's five Moscavia create prompts, three times each,
   through the app's own `create.preview_thing` (no prose) in a fresh
   scratch world. Unlike probe 2, the facts' text is kept: the owner sees
   real places (Novgorod, Moscow) inside facts. Every capitalised run in
   the facts and every proposed name is recorded with its real-word hits
   and whether it fits Moscavian.
2. *Flag.* The 41 labelled names (26 real places, people and real words
   used as names; 15 invented, 12 of them rolled from Moscavian) go to the
   model with probe 2's prompt and a V2 that also names real words and real
   given names and surnames. Scored with `flag_scores`. The fit check
   (`name_fits` against Moscavian) is scored on the same names, no model.
3. *Swap.* Ten sentences with a real name: the model gets six names rolled
   from Moscavian for that kind, picks one and rewrites the sentence. The
   plain substitution of its pick is kept beside it, to compare.
4. *Languages from the prompt.* Ten prompts naming zero, one or two of four
   world languages; the model proposes Languages rows (language, role,
   share). A stem match, no model, is kept beside it.

Labels: docs/superpowers/probes/raw/2026-10-30-clean-names-labels.json
(committed before any call). Not a test: it calls koboldcpp one call at a
time; ask the owner first::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_clean_names.py OUT.json --label skyfall'

``--fake`` swaps the model for canned replies (a dry run, no network; the
baseline stage is skipped).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
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
from probe_name_flags import FLAG_SYSTEM  # noqa: E402

import talemate.worldplay.create as create  # noqa: E402
from talemate.languages.generator import name_fits  # noqa: E402
from talemate.languages.models import Language  # noqa: E402
from talemate.languages.naming import roll_names  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.kinds import LANGUAGE_ROLES  # noqa: E402
from talemate.world.store import World  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-30-clean-names-labels.json"
REAL = REPO / "docs/superpowers/probes/raw/2026-10-28-language-make-labels.json"
BATCH = 14

FLAG_SYSTEM_V2 = """\
You check names written for an invented fantasy world. The world must not use
real-world names. For each name, say which it is:
- "real": a real-world place, person, river or institution; OR a real word of a
  real language used as a name (a Russian word like "Kholodnaya", 'cold', or a
  city name built from real words like "Velikograd", 'great city'); OR a real
  given name or surname (Dmitri, Yelena, Ivanov);
- "stock-title": a generic, overused fantasy title anyone could have written;
- "ok": an invented name that isn't any of the above.
Reply with JSON only: {"names": [{"name": "<as given>", "label": "real"|"stock-title"|"ok", "why": "<a few words>"}]}"""

SWAP_SYSTEM = """\
A sentence written for an invented fantasy world uses a real-world name. Replace
that name with one of the given invented names: pick the one that suits the
sentence best, and change nothing else unless the grammar needs it (an article,
a possessive). Reply with JSON only: {"pick": "<one of the given names>", "sentence": "<the sentence with it>"}"""

LANGUAGES_SYSTEM = f"""\
The owner describes a new place, group or person for their fantasy world. From
their words only, say which of the world's languages it uses, if any. For each,
give a role ({", ".join(LANGUAGE_ROLES)}) and a share (0 to 1, the shares adding
to about 1; most entries have one main language). Name no language their words
don't point to; an empty list is fine.
Reply with JSON only: {{"languages": [{{"language": "<name>", "role": "<role>", "share": <number>}}]}}"""

_CAPS = re.compile(r"\b[A-Z][\w'’-]*(?:\s+(?:of\s+the\s+|of\s+|the\s+)?[A-Z][\w'’-]*)*")


def fake_chat(messages: list[dict]) -> str:
    system = messages[0]["content"]
    if system in (FLAG_SYSTEM, FLAG_SYSTEM_V2):
        names = [
            line.split(" -- ")[0].lstrip("- ")
            for line in messages[1]["content"].splitlines()
            if line.startswith("- ")
        ]
        return json.dumps({"names": [{"name": n, "label": "ok"} for n in names]})
    if system == SWAP_SYSTEM:
        return json.dumps({"pick": "X", "sentence": "fake"})
    return json.dumps({"languages": []})


def _moscavian(labels: dict) -> Language:
    data = json.loads((REPO / labels["language_file"]).read_text())
    return Language.model_validate(data.get("language", data))


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


async def baseline(
    labels: dict, language: Language, real: list[str], run: dict, save: Callable
) -> None:
    """Stage 1: real names in today's drafts, facts included."""
    prompts = json.loads((REPO / labels["baseline_prompts_from"]).read_text())[
        "baseline_prompts"
    ]
    create._preview_prose = _no_prose
    client = harness.RecordingClient(name="KoboldCpp")
    await client.status()
    run["baseline_model"] = client.model_name
    client.calls = run.setdefault("baseline_calls", [])
    client.on_call = save
    rows = run.setdefault("baseline", [])
    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        for i, item in enumerate(prompts):
            for version in range(1, labels["baseline_runs"] + 1):
                world = World.create(
                    f"Clean {i}-{version}", root=Path(root) / f"{i}-{version}"
                )
                world.set_present(WorldDate.of(1000))
                row: dict[str, Any] = {"prompt": item["prompt"], "version": version}
                try:
                    preview = await create.preview_thing(
                        world, item["kind"], item["prompt"], {}, client,
                        ask_same=False, hint=item.get("hint"),
                    )  # fmt: skip
                    facts = [f.text for f in preview.facts]
                    names = [preview.name] + [n.name for n in preview.new_names]
                    in_text = sorted(
                        {m.group(0) for t in facts for m in _CAPS.finditer(t)}
                    )
                    row.update(
                        facts=facts,
                        names=names,
                        caps_in_facts=in_text,
                        real_hits_names=real_word_hits(names, real),
                        real_hits_facts=real_word_hits(in_text, real),
                        unfit=[n for n in in_text if not name_fits(language, n)],
                    )
                except Exception as exc:  # a bad reply is a finding
                    row["error"] = repr(exc)
                rows.append(row)
                save()


def flag(
    send: Callable, labels: dict, run: dict, save: Callable, system: str, key: str
) -> None:
    """Stage 2: the model labels the names."""
    names = labels["names"]
    flagged: dict[str, str] = {}
    replies = run.setdefault(f"{key}_replies", [])
    for start in range(0, len(names), BATCH):
        batch = names[start : start + BATCH]
        user = "\n".join(f"- {n['name']} -- {n['context']}" for n in batch)
        reply = send(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        parsed = _extract_json(reply, "{", "}") or {}
        replies.append({"reply": reply, "parsed": parsed})
        for row in parsed.get("names", []):
            if isinstance(row, dict) and row.get("name"):
                flagged[row["name"]] = row.get("label", "ok")
        save()
    run[key] = flagged
    run[f"{key}_scores"] = flag_scores({n["name"]: n["label"] for n in names}, flagged)
    save()


def fit_scores(labels: dict, language: Language) -> dict:
    """The fit check on the labelled names: a real name that doesn't fit is
    caught; an ok one that doesn't fit is a false alarm."""
    real = [n["name"] for n in labels["names"] if n["label"] == "real"]
    ok = [n["name"] for n in labels["names"] if n["label"] == "ok"]
    return {
        "real_caught": [n for n in real if not name_fits(language, n)],
        "real_missed": [n for n in real if name_fits(language, n)],
        "ok_false_alarms": [n for n in ok if not name_fits(language, n)],
    }


def swap(
    send: Callable, labels: dict, language: Language, run: dict, save: Callable
) -> None:
    """Stage 3: a real name in a sentence swapped for a rolled one."""
    rows = run.setdefault("swaps", [])
    for i, item in enumerate(labels["swaps"]):
        candidates = roll_names(language, item["kind"], count=6, seed=100 + i)
        user = (
            f"Sentence: {item['sentence']}\nReal name: {item['name']}\n"
            f"Invented names: {', '.join(candidates)}"
        )
        reply = send(
            [
                {"role": "system", "content": SWAP_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        parsed = _extract_json(reply, "{", "}") or {}
        pick = parsed.get("pick", "")
        rows.append(
            {
                **item,
                "candidates": candidates,
                "pick": pick,
                "pick_is_candidate": pick in candidates,
                "model_sentence": parsed.get("sentence", ""),
                "plain_sentence": item["sentence"].replace(item["name"], pick)
                if pick
                else "",
                "reply": reply,
            }
        )
        save()


def _stem_match(prompt: str, names: list[str]) -> list[str]:
    """The languages whose name, or its first five letters (Moscavian ->
    Mosca, matching Moscavia), appear in the prompt."""
    low = prompt.lower()
    return [n for n in names if n.lower() in low or n.lower()[:5] in low]


def languages(send: Callable, labels: dict, run: dict, save: Callable) -> None:
    """Stage 4: Languages rows from the owner's words."""
    world = "\n".join(
        f"- {lang['name']}: {lang['about']}" for lang in labels["world_languages"]
    )
    names = [lang["name"] for lang in labels["world_languages"]]
    rows = run.setdefault("languages", [])
    for item in labels["language_prompts"]:
        user = f"The world's languages:\n{world}\n\nThe owner's words: {item['prompt']}"
        reply = send(
            [
                {"role": "system", "content": LANGUAGES_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        parsed = _extract_json(reply, "{", "}") or {}
        got = [r for r in parsed.get("languages", []) if isinstance(r, dict)]
        expected = {e["language"] for e in item["expected"]}
        rows.append(
            {
                **item,
                "model": got,
                "model_languages_right": {r.get("language") for r in got} == expected,
                "stem_match": _stem_match(item["prompt"], names),
                "stem_right": set(_stem_match(item["prompt"], names)) == expected,
                "reply": reply,
            }
        )
        save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--skip-baseline", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()

    labels = json.loads(LABELS.read_text())
    real = json.loads(REAL.read_text())["real_words"]
    language = _moscavian(labels)
    results = json.loads(out.read_text()) if out.exists() else {"runs": {}}
    run: dict[str, Any] = {}
    results["runs"][args.label] = run

    def save() -> None:
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))

    run["fit"] = fit_scores(labels, language)
    if args.fake:
        run["model"] = "fake"
        send = fake_chat
    else:
        harness._quiet_loading(False)
        url = ai_helpers.koboldcpp_url()
        run["model"] = ai_helpers.koboldcpp_model(url)
        send = lambda messages: chat_messages(url, messages, max_tokens=3000)  # noqa: E731
        if not args.skip_baseline:
            asyncio.run(baseline(labels, language, real, run, save))
    flag(send, labels, run, save, FLAG_SYSTEM, "flag_v1")
    flag(send, labels, run, save, FLAG_SYSTEM_V2, "flag_v2")
    swap(send, labels, language, run, save)
    languages(send, labels, run, save)
    save()
    print(f"{args.label}: {run['model']} -> {out}")


if __name__ == "__main__":
    main()
