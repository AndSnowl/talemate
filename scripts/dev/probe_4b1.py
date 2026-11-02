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


FUNCTION = {"the", "of", "a", "an"}

COMPOUND_SYSTEM = """\
You split an English compound word into its parts, for naming. Reply with JSON
only: {"noun": "<the main noun, singular, lower case>",
"describing": ["<the other parts, lower case>"]}.
Examples: Blackwater -> {"noun": "water", "describing": ["black"]};
lakeland -> {"noun": "land", "describing": ["lake"]}."""

SUGGEST_V2 = """\
You name things in an invented fantasy world. One part of this entry's name
means something: {hint}. Read the entry's facts and choose ONE common English
noun for that part (like star, frost, pine, ember, river). Never a proper
name, never the entry's own name, never a phrase. Reply with JSON only:
{{"noun": "<one common noun, singular, lower case>", "why": "<a few words>"}}"""


def singular(word: str) -> str:
    """A plural English noun made singular, simply (stars, woods, hills,
    moons; berries; foxes)."""

    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ches", "shes", "xes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def split_text(text: str, compound=None) -> dict:
    """A meaning's structure read from the English: "of", "the", plural
    and joined from the words; the last word is the noun, the rest
    describing; a one-word compound goes to `compound` (the model)."""

    words = [w for w in re.split(r"[\s\-]+", text.strip()) if w]
    lower = [w.lower() for w in words]
    of = bool(lower) and lower[0] == "of" or "of" in lower[1:-1]
    the = "the" in lower
    content = [w for w in lower if w not in FUNCTION]
    ending = ""
    if (
        content
        and content[-1] == "land"
        or (content and content[0] == "land" and "of" in lower)
    ):
        ending = "land of"
        content = [w for w in content if w != "land"]
        of = False
    if len(content) == 1 and len(words) == 1 and compound is not None and not ending:
        got = compound(content[0])
        if got.get("describing"):
            return {
                "noun": singular(got.get("noun", "")),
                "describing": got["describing"],
                "joined": True,
            }
    if "of" in lower[1:-1]:
        # "Owl-of-Frost": what follows "of" is its noun
        at = lower.index("of", 1)
        content = [w for w in lower[at + 1 :] if w not in FUNCTION]
    if not content:
        return {"noun": ""}
    noun = content[-1]
    out = {
        "noun": singular(noun),
        "describing": content[:-1],
        "of": of,
        "the": the,
        "more_than_one": singular(noun) != noun,
        "ending": ending,
    }
    return out


def stage_c(run: dict, fake: bool, save) -> None:
    """Round 2: the deterministic split (the model only for one-word
    compounds), and Suggest with a tighter prompt."""

    labels = json.loads(LABELS.read_text())
    if fake:
        send = lambda messages: '{"noun": "water", "describing": ["black"]}'  # noqa: E731
    else:
        url = ai_helpers.koboldcpp_url()
        run["model"] = ai_helpers.koboldcpp_model(url)
        send = lambda messages: chat_messages(url, messages, max_tokens=300)  # noqa: E731

    def compound(word: str) -> dict:
        return _json(send([{"role": "system", "content": COMPOUND_SYSTEM},
                           {"role": "user", "content": word}]))  # fmt: skip

    run["split"] = []
    for item in labels["split"]:
        got = split_text(item["text"], compound)
        wants = [item["want"], *item.get("any_of", [])]
        ok = any(_same(got, want) for want in wants)
        run["split"].append({"text": item["text"], "got": got, "ok": ok})
    run["split_score"] = sum(r["ok"] for r in run["split"])
    save()
    print("split v2", run["split_score"], "/", len(run["split"]))
    run["suggest"] = []
    if "Test3" not in _copies():
        return
    view = World.open(_copies()["Test3"]).view()
    hint = labels["suggest_rule"]["parts"][2].split("hint: ", 1)[1]
    for state in view.things(facts=False):
        name = view.name_of(state.id) or ""
        if name not in labels["suggest"]:
            continue
        facts = [f.text for f in view.thing(state.id).facts][:12]
        reply = send(
            [{"role": "system", "content": SUGGEST_V2.format(hint=hint)},
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
    parser.add_argument("--stage", choices=["a", "b", "c"], required=True)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    results = json.loads(out.read_text()) if out.exists() else {}
    run: dict[str, Any] = results.setdefault(args.stage, {})

    def save() -> None:
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))

    {"a": stage_a, "b": stage_b, "c": stage_c}[args.stage](run, args.fake, save)
    save()


if __name__ == "__main__":
    main()
