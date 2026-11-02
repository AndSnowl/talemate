"""Throwaway probe: languages 4b-1 (spec
docs/superpowers/specs/2026-11-02-fantasymate-languages-4b1-grammar-engine-design.md,
"Probe 4b-1"). Two stages:

a. *Fill them in.* Each language in the owner's test-app worlds (read
   only) goes to Claude Code (`claude -p`, no tools) with its grammar
   sections and tables and the `NameGrammar` schema; the reply's grammar is
   scored by whether the engine (`apply_form`) rebuilds the language's own
   nouns table (one / more than one, a / the).
b. *Split and suggest* on the world model (koboldcpp): 20 labelled
   meanings split into `MeaningPhrase`s, and Suggest on 10 Test3 entries'
   facts with an owl-name rule's hint, recorded for scoring by hand.

Labels: docs/superpowers/probes/raw/2026-11-02-languages-4b1-labels.json
(committed before any call). Not a test; ask the owner first::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_4b1.py OUT.json --stage a|b'

``--fake`` swaps both models for canned replies (a dry run).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_helpers  # noqa: E402
from probe_language_make import chat_messages  # noqa: E402

from talemate.languages.entry import language_of  # noqa: E402
from talemate.languages.models import Language, NameGrammar  # noqa: E402
from talemate.languages.name_grammar import (  # noqa: E402
    MeaningPhrase,
    apply_form,
    vowels_of,
)
from talemate.world.store import World  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-11-02-languages-4b1-labels.json"
WORLDS = (
    REPO.parent
    / "languages-4a/.superpowers/sdd/2026-11-01-fantasymate-languages-4a-revised-name-it/app/worlds"
)

FILL_PROMPT = """\
You turn a constructed language's grammar into machine rules for building names.
Below are the language's grammar sections (prose, tables, examples) and a JSON
schema for "name_grammar". Write the name_grammar this language's grammar
describes: where describing words go, how "of" is said, how joined words go,
how "the" and "more than one" are formed (each a list of changes tried in
order; the first whose condition holds wins), and the meaningful endings from
its word-building table. Conditions: "" (always), "after_vowel",
"after_consonant", "before_vowel", "ends:a|o". Change kinds: "ending" (add
text), "swap" (drop one of the "|"-listed endings in `drop`, add text),
"word_before", "word_after", "double" (double the first syllable). Every rule
must rebuild the examples the tables give. Reply with the JSON object only.

Schema:
{schema}

Grammar:
{grammar}
"""

SPLIT_SYSTEM = """\
You read a short English meaning that will become a name in an invented
language, and say how it's built. Reply with JSON only:
{"noun": "<the main noun, singular, lower case>",
 "describing": ["<describing words, lower case, in English order>"],
 "of": <true if it says "of X">, "the": <true if it says "the">,
 "more_than_one": <true if the noun is plural>,
 "joined": <true if it's written as one word, like Blackwater>,
 "ending": "<'land of' when it means the land of something, else ''>"}"""

SUGGEST_SYSTEM = """\
You name things in an invented fantasy world. A name rule has a part that
takes a meaning: {hint}. Read the entry's facts and choose the meaning that
fits this entry best, as a short English phrase (one to three words).
Reply with JSON only: {{"noun": "<main noun, singular>", "describing": [],
"more_than_one": <true|false>, "why": "<a few words>"}}"""


def _json(text: str) -> dict:
    found = re.search(r"\{.*\}", text, re.S)
    return json.loads(found.group(0)) if found else {}


_COPIES: dict[str, Path] = {}


def _copies() -> dict[str, Path]:
    """Read-only backups of the test app's worlds in a temp folder (the
    app is running on the originals): world name -> copy's folder."""

    import sqlite3
    import tempfile

    if _COPIES:
        return _COPIES
    root = Path(tempfile.mkdtemp(prefix="probe4b1-"))
    for folder in sorted(WORLDS.iterdir()):
        if not (folder / "world.sqlite").exists():
            continue
        copy = root / folder.name
        copy.mkdir()
        source = sqlite3.connect(f"file:{folder / 'world.sqlite'}?mode=ro", uri=True)
        target = sqlite3.connect(copy / "world.sqlite")
        source.backup(target)
        target.close()
        source.close()
        _COPIES[_name(copy)] = copy
    return _COPIES


def _languages() -> list[tuple[str, Language]]:
    out = []
    for name, folder in _copies().items():
        world = World.open(folder)
        view = world.view()
        for state in view.things("language", facts=False):
            out.append((name, language_of(view.thing(state.id))))
    return out


def _table_checks(language: Language) -> list[dict]:
    """(form, base, expected) from the nouns section's first table: columns
    one / more than one, rows a / the."""

    checks = []
    for section in language.grammar:
        if section.topic != "nouns" or not section.tables:
            continue
        table = section.tables[0]
        base = re.match(r"\s*(\S+)", table.caption or "")
        if not base or len(table.rows) < 2:
            continue
        base = base.group(1).lower()
        plain, the = table.rows[0], table.rows[1]
        if len(plain) >= 3:
            checks.append({"form": ["more_than_one"], "want": plain[2]})
        if len(the) >= 2:
            checks.append({"form": ["the"], "want": the[1]})
        if len(the) >= 3:
            checks.append({"form": ["more_than_one", "the"], "want": the[2]})
        for check in checks:
            check["base"] = base
        break
    return checks


def _score(language: Language, grammar: NameGrammar) -> dict:
    vowels = vowels_of(language)
    hits, rows = 0, []
    checks = _table_checks(language)
    for check in checks:
        word = check["base"]
        try:
            for form in check["form"]:
                word = apply_form(grammar, vowels, word, form)
        except Exception as exc:  # a rule the engine can't apply
            word = f"error: {exc}"
        ok = word.lower() == check["want"].strip().lower()
        hits += ok
        rows.append({**check, "got": word, "ok": ok})
    return {"hits": hits, "of": len(checks), "rows": rows}


def stage_a(run: dict, fake: bool, save) -> None:
    schema = json.dumps(NameGrammar.model_json_schema(), indent=1)
    run["fill"] = {}
    for world, language in _languages():
        grammar_text = json.dumps(
            [s.model_dump(mode="json") for s in language.grammar], ensure_ascii=False
        )
        prompt = FILL_PROMPT.format(schema=schema, grammar=grammar_text)
        if fake:
            reply = json.dumps({"describing": "before"})
        else:
            done = subprocess.run(
                ["claude", "-p", prompt, "--model", "opus", "--tools", "",
                 "--no-session-persistence", "--output-format", "text"],
                capture_output=True, text=True, timeout=900,
            )  # fmt: skip
            reply = done.stdout
        entry: dict[str, Any] = {"world": world, "reply": reply}
        try:
            grammar = NameGrammar.model_validate(_json(reply))
            entry["grammar"] = grammar.model_dump(mode="json")
            entry["score"] = _score(language, grammar)
        except Exception as exc:
            entry["error"] = str(exc)
        run["fill"][language.name] = entry
        save()
        print(language.name, entry.get("score", {}).get("hits"), "/",
              entry.get("score", {}).get("of"), entry.get("error", ""))  # fmt: skip


def _same(got: dict, want: dict) -> bool:
    phrase = MeaningPhrase(**{"noun": "", **got})
    goal = MeaningPhrase(**want)
    return phrase.model_dump() == goal.model_dump()


def stage_b(run: dict, fake: bool, save) -> None:
    labels = json.loads(LABELS.read_text())
    if fake:
        send = lambda messages: '{"noun": "star", "of": true}'  # noqa: E731
    else:
        url = ai_helpers.koboldcpp_url()
        run["model"] = ai_helpers.koboldcpp_model(url)
        send = lambda messages: chat_messages(url, messages, max_tokens=600)  # noqa: E731
    run["split"] = []
    for item in labels["split"]:
        reply = send(
            [{"role": "system", "content": SPLIT_SYSTEM},
             {"role": "user", "content": item["text"]}]
        )  # fmt: skip
        got = _json(reply)
        wants = [item["want"], *item.get("any_of", [])]
        ok = any(_same(got, want) for want in wants) if got else False
        run["split"].append({"text": item["text"], "got": got, "ok": ok})
        save()
    run["split_score"] = sum(r["ok"] for r in run["split"])
    print("split", run["split_score"], "/", len(run["split"]))

    run["suggest"] = []
    if "Test3" not in _copies():
        return
    test3 = World.open(_copies()["Test3"])
    view = test3.view()
    hint = labels["suggest_rule"]["parts"][2].split("hint: ", 1)[1]
    for state in view.things(facts=False):
        name = view.name_of(state.id) or ""
        if name not in labels["suggest"]:
            continue
        facts = [f.text for f in view.thing(state.id).facts][:12]
        reply = send(
            [{"role": "system", "content": SUGGEST_SYSTEM.format(hint=hint)},
             {"role": "user", "content": f"{name}:\n" + "\n".join(f"- {f}" for f in facts)}]
        )  # fmt: skip
        run["suggest"].append({"entry": name, "got": _json(reply)})
        save()


def _name(folder: Path) -> str:
    import sqlite3

    con = sqlite3.connect(f"file:{folder / 'world.sqlite'}?mode=ro", uri=True)
    try:
        row = con.execute("select value from meta where key='name'").fetchone()
        return row[0] if row else ""
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--stage", choices=["a", "b"], required=True)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    results = json.loads(out.read_text()) if out.exists() else {}
    run: dict[str, Any] = results.setdefault(args.stage, {})

    def save() -> None:
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))

    (stage_a if args.stage == "a" else stage_b)(run, args.fake, save)
    save()


if __name__ == "__main__":
    main()
