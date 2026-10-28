"""Throwaway probe: can a local instruct model make a language (languages
plan 1, Task 4; spec part 2, probe 1).

Each case in the labels asks the model, through koboldcpp's chat endpoint
(the model's own chat template, `probe_fact_roundtrip.chat`'s request), for
a language as JSON in the `talemate.languages.models.Language` shape, with
categories and generators in the generator's pattern syntax. A `decide`
case asks once; an `ask` case first asks for at most four plain questions,
then answers them with the labels' canned answer and asks for the language.
`daughter` gets version 1 of `russian` from the same run as its parent.

Each reply is scored with `language_probe_metrics.language_checks` (does it
load, what does it roll, how many of its own words fit, which samples are
real Russian words) and, for `ask`, `jargon_hits` over the questions. Then
three small jobs run on version 1 of `russian`: one-sentence definitions for
10 rolled names, a pick among 20 rolled names, and "Free Provinces" coined
in the language.

Labels: docs/superpowers/probes/raw/2026-10-28-language-make-labels.json
(committed before any call). Not a test: it calls koboldcpp, one call at a
time. The owner approved this plan's probes in advance (2026-10-28)::

    guix shell -m manifest.scm -- bash -c 'uv run --no-sync python \\
        scripts/dev/probe_language_make.py OUT.json --label qwen'

``--fake`` swaps the model for canned replies (a dry run, no network).
Findings: docs/superpowers/probes/2026-10-28-language-make.md.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_helpers  # noqa: E402
from language_probe_metrics import jargon_hits, language_checks  # noqa: E402
from probe_fact_roundtrip import _extract_json, _strip_think  # noqa: E402

from talemate.languages.generator import fits, roll  # noqa: E402
from talemate.languages.models import Language  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-28-language-make-labels.json"

SYNTAX = """\
Pattern syntax (the generator rolls names from it):
- "categories" maps ONE uppercase letter to a space-separated list of options,
  e.g. {"C": "k kh t th r*2", "V": "a e o u i"}. An option may be several letters
  ("kh", or a whole word part like "thorn"). A trailing *n weights it (r*2 = twice as likely).
- A pattern is read left to right: an uppercase letter that is a category means
  "one pick from it"; (...) means optional (50%); [a|b] picks one alternative;
  anything else (lowercase letters, spaces, ' and -) is copied as-is.
  Example patterns: "CV(C)CVC", "[C|CC]VCV(n)", "AB".
- A whole pattern may end in *n to weight it among the generator's patterns.
- Each generator: {"id", "name", "use": "people"|"places"|"things", "patterns": [...],
  "reject": [regexes that drop a candidate], "min_length", "max_length"}."""

SHAPE = """\
Reply with ONE JSON object and nothing else:
{"name": "<the language's name>", "level": "full" or "naming",
 "sound": "<two or three plain sentences on how it sounds, for a layperson>",
 "categories": {...}, "generators": [ at least a "people" and a "places" generator ],
 "dictionary": [{"word", "meaning"} ... at least 25 words],
 "phrases": [{"id", "category": "curse"|"saying"|"blessing"|"greeting",
              "original", "translation"} ... at least 6]}"""

PARTS_NOTE = """\
This is a naming style made of English word parts, not a language with its own
sounds. Put the word parts in categories as whole-word options (e.g.
"A": "dusk thorn ash raven", "B": "hollow field mere ford wick") and give every
part's meaning in "dictionary" (e.g. {"word": "mere", "meaning": "a lake"})."""

SYSTEM = f"""\
You design languages and naming styles for a fantasy world. The person you work
for is not a linguist: write everything they read in plain everyday words, never
in linguistics terms. Never use real words from a real language: a language can
sound like one, but its words are invented.

{SYNTAX}

{SHAPE}"""

ASK_SYSTEM = """\
You design languages and naming styles for a fantasy world. The person you work
for is not a linguist. Before you design anything, ask them at most four short
questions about what they want it to sound and feel like, in plain everyday
words (never linguistics terms). Reply with the numbered questions only."""


def chat_messages(
    url: str,
    messages: list[dict],
    max_tokens: int = 6000,
    timeout: float = 1200,
    thinking: bool | None = None,
) -> str:
    """POST `messages` to koboldcpp's OpenAI-compatible chat endpoint (as
    `probe_fact_roundtrip.chat` does, with a whole message list); return the
    reply with any think block stripped. `thinking` False switches a
    thinking model's reasoning off (`chat_template_kwargs.enable_thinking`);
    None leaves the model's default."""
    body: dict = {"messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    if thinking is not None:
        body["chat_template_kwargs"] = {"enable_thinking": thinking}
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    return _strip_think(data["choices"][0]["message"]["content"])


_FAKE_LANGUAGE = {
    "name": "Fakeish",
    "level": "naming",
    "sound": "Short and hard.",
    "categories": {"C": "k t r m n s v", "V": "a o e i u"},
    "generators": [
        {"id": "people", "name": "People", "use": "people", "patterns": ["CVCV"]},
        {"id": "places", "name": "Places", "use": "places", "patterns": ["CVCVC"]},
    ],
    "dictionary": [{"word": "kata", "meaning": "hill"}],
    "phrases": [],
}


def fake_chat(messages: list[dict]) -> str:
    """Canned replies for `--fake`: questions for the ask step, a small
    valid language for a design call, and JSON shaped for each small job."""
    system = messages[0]["content"]
    if system == ASK_SYSTEM and len(messages) == 2:
        return "1. Harsh or soft?\n2. Long names or short?"
    if "JOB:definitions" in system:
        return json.dumps({"definitions": {"Kato": "A hill town."}})
    if "JOB:pick" in system:
        return json.dumps({"pick": "Kato", "why": "It sounds old."})
    if "JOB:coin" in system:
        return json.dumps(
            {"name": "Vora Tamun", "words": [{"word": "vora", "meaning": "free"}]}
        )
    return json.dumps(_FAKE_LANGUAGE)


def language_messages(case: dict, parent: dict | None) -> list[dict]:
    """The design request for a `decide` case (or an `ask` case's second
    step, which appends to these)."""
    user = f"Make: {case['prompt']}."
    if case.get("style") == "parts":
        user += "\n\n" + PARTS_NOTE
    if parent is not None:
        user += (
            "\n\nThe parent language (keep its roots, change them by the drift "
            "described, so the two sound related):\n" + json.dumps(parent)
        )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def _places_generator(language: Language) -> str:
    for g in language.generators:
        if g.use == "places":
            return g.id
    return language.generators[0].id


def small_jobs(send: Callable, parent: dict, labels: dict, record: Callable) -> dict:
    """The three small jobs on `parent` (version 1 of `russian`)."""
    jobs = labels["small_jobs"]
    out: dict = {}
    try:
        language = Language.model_validate(parent)
        gen = _places_generator(language)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    rng = random.Random(7)
    brief = json.dumps(
        {
            "name": language.name,
            "sound": language.sound,
            "dictionary": [e.model_dump() for e in language.dictionary],
        }
    )

    names = roll(language, gen, count=jobs["definitions"]["count"], rng=rng)
    system = (
        "JOB:definitions. You write definitions for names in an invented "
        "language. For each name give ONE plain sentence: it may just be what "
        "it names, be named after someone, or be built from the language's "
        "words. Reply with JSON only: "
        '{"definitions": {"<name>": "<sentence>", ...}}'
    )
    user = f"The language:\n{brief}\n\nThe names: {', '.join(names)}"
    reply = send(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    record()
    out["definitions"] = {"names": names, "reply": _extract_json(reply, "{", "}")}

    names = roll(language, gen, count=jobs["pick"]["count"], rng=rng)
    system = (
        "JOB:pick. From the candidate names, pick the one that best fits what "
        "is being named, and say why in one sentence. Reply with JSON only: "
        '{"pick": "<name>", "why": "<sentence>"}'
    )
    user = (
        f"The language:\n{brief}\n\nWhat is being named: {jobs['pick']['what']}"
        f"\n\nCandidates: {', '.join(names)}"
    )
    reply = send(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    record()
    picked = _extract_json(reply, "{", "}") or {}
    out["pick"] = {
        "names": names,
        "reply": picked,
        "pick_in_candidates": picked.get("pick") in names,
    }

    system = (
        "JOB:coin. Give the English phrase in the invented language. Use its "
        "dictionary words where they exist; coin any missing word so it sounds "
        "like the language, with a one-sentence meaning. Reply with JSON only: "
        '{"name": "<the phrase in the language>", "words": [{"word", "meaning"}]}'
    )
    user = (
        f"The language:\n{json.dumps(parent)}\n\nThe English phrase: "
        f"{jobs['coin']['english']}"
    )
    reply = send(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    record()
    coined = _extract_json(reply, "{", "}") or {}
    words = [w.get("word", "") for w in coined.get("words", []) if isinstance(w, dict)]
    out["coin"] = {
        "reply": coined,
        "coined_fit": {w: fits(language, w) for w in words if w},
    }
    return out


def run(
    send: Callable, labels: dict, versions: int, save: Callable, result: dict
) -> dict:
    """Every case `versions` times, then the small jobs, into `result` (the
    saved run, so a crash keeps what was done); `save()` after each call."""
    result.update({"cases": {}, "calls": 0})

    def record():
        result["calls"] += 1
        save()

    real = labels["real_words"]
    for key, case in labels["cases"].items():
        result["cases"][key] = []
        for version in range(1, versions + 1):
            entry: dict = {"version": version}
            result["cases"][key].append(entry)
            parent = None
            if case.get("parent"):
                first = result["cases"].get(case["parent"], [{}])[0]
                parent = first.get("language")
                if parent is None:
                    entry["error"] = "parent has no language"
                    save()
                    continue
            messages = language_messages(case, parent)
            started = time.monotonic()
            try:
                if case["mode"] == "ask":
                    ask = [
                        {"role": "system", "content": ASK_SYSTEM},
                        {"role": "user", "content": f"Make: {case['prompt']}."},
                    ]
                    questions = send(ask)
                    record()
                    entry["questions"] = questions
                    entry["jargon"] = jargon_hits(questions, labels["jargon"])
                    messages = messages + [
                        {"role": "assistant", "content": questions},
                        {"role": "user", "content": case["answer"]},
                    ]
                reply = send(messages)
                record()
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                save()
                continue
            entry["seconds"] = round(time.monotonic() - started, 1)
            entry["reply"] = reply
            language = _extract_json(reply, "{", "}")
            entry["language"] = language
            entry["checks"] = (
                language_checks(language, rolls=50, seed=version, real=real)
                if isinstance(language, dict)
                else {"valid": False, "error": "no JSON object in the reply"}
            )
            text = json.dumps(language or {})
            entry["jargon_in_language"] = jargon_hits(text, labels["jargon"])
            save()

    first = (result["cases"].get("russian") or [{}])[0]
    if first.get("language"):
        result["small_jobs"] = small_jobs(send, first["language"], labels, record)
    else:
        result["small_jobs"] = {"error": "russian has no language"}
    save()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--versions", type=int, default=2)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument(
        "--no-think",
        action="store_true",
        help="switch a thinking model's reasoning off",
    )
    args = parser.parse_args()

    labels = json.loads(LABELS.read_text())
    results = json.loads(args.out.read_text()) if args.out.exists() else {"runs": {}}

    if args.fake:
        model = "fake"
        send = fake_chat
    else:
        url = ai_helpers.koboldcpp_url()
        model = ai_helpers.koboldcpp_model(url)
        thinking = False if args.no_think else None
        send = lambda messages: chat_messages(  # noqa: E731
            url, messages, max_tokens=args.max_tokens, thinking=thinking
        )

    run_result: dict = {
        "model": model,
        "max_tokens": args.max_tokens,
        "thinking": "off" if args.no_think else "default",
    }
    results["runs"][args.label] = run_result

    def save():
        args.out.write_text(json.dumps(results, indent=1, ensure_ascii=False))

    run(send, labels, args.versions, save, run_result)
    save()
    print(f"{args.label}: {model}, {run_result['calls']} calls -> {args.out}")


if __name__ == "__main__":
    main()
