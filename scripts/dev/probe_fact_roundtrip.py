"""Fact round-trip probe against a local model (Phase 0 of the world-store work).

Throwaway probe: for each source description in ``--samples`` (default
``scripts/dev/probe_data/characters.json``), extracts facts, then repeats
``--rounds`` times: write a paragraph of prose from the current facts,
check the prose against those facts for invented or dropped claims, then
re-extract facts from the prose for the next round. The final re-extraction
is also kept, with no prose of its own, so the last round reflects the
facts after going all the way through every round-trip. Metrics on the
raw results are in ``fact_probe_metrics.py`` (Task 1); this script only
drives the model and writes ``report.json``/``report.md`` (rewritten after
every sample) into ``--out``.

Makes real model calls, so it needs ``TALEMATE_AI_TESTS=1`` (ask the owner
first)::

    TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync \\
        python scripts/dev/probe_fact_roundtrip.py [--rounds 3] \\
        [--samples PATH] [--out DIR]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_helpers  # noqa: E402
import fact_probe_metrics as metrics  # noqa: E402

AI_GATE_MESSAGE = "AI runs need TALEMATE_AI_TESTS=1 — ask the owner first"

DEFAULT_SAMPLES = Path(__file__).resolve().parent / "probe_data" / "characters.json"

CATEGORIES = "appearance, personality, background, ability, relationship, speech"

EXTRACT_SYSTEM = (
    "You extract discrete facts from a character description. Reply with "
    'only a JSON list of objects, each shaped {"category", "text"}, '
    f"where category is one of: {CATEGORIES}. One fact per claim. No "
    "commentary, no markdown fences, just the JSON list."
)

PROSE_SYSTEM = (
    "You write a character description from a list of facts, each shaped "
    '{"category", "text"}. Write one paragraph per category present, '
    "using only the given facts -- invent nothing -- and keep each fact's "
    "exact wording where it reads naturally. Reply with only the prose, no "
    "commentary."
)

CHECK_SYSTEM = (
    'You compare a list of facts, each shaped {"category", "text"}, '
    "against a prose description written from them. Reply with only a "
    'JSON object shaped {"invented": [...], "dropped": [...]}, where '
    "invented lists claims the prose makes that no fact supports, and "
    "dropped lists facts the prose leaves out. Use the facts' own wording "
    "in each list. No commentary, no markdown fences."
)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _strip_think(text: str) -> str:
    return _THINK_BLOCK.sub("", text).strip()


def chat(
    url: str, system: str, user: str, *, max_tokens: int = 1024, timeout: float = 600
) -> str:
    """POST to koboldcpp's OpenAI-compatible chat endpoint; return the reply text.

    Any ``<think>...</think>`` block in the reply is stripped before
    returning.
    """
    payload = json.dumps(
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())
    content = data["choices"][0]["message"]["content"]
    return _strip_think(content)


def _extract_json(text: str, open_char: str, close_char: str):
    """Parse the first balanced ``open_char ... close_char`` JSON value in text.

    Scans for a matching close bracket at depth 0, ignoring brackets inside
    quoted strings, so prose or commentary around the JSON doesn't confuse
    it. Returns None if no valid JSON value is found.
    """
    start = text.find(open_char)
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except ValueError:
                        break
        start = text.find(open_char, start + 1)
    return None


def extract_facts(url: str, text: str) -> list[dict]:
    """Ask the model for a JSON list of {"category", "text"} facts in ``text``."""
    reply = chat(url, EXTRACT_SYSTEM, text)
    facts = _extract_json(reply, "[", "]")
    if not isinstance(facts, list):
        raise ValueError(f"no JSON list found in extraction reply: {reply!r}")
    return facts


def write_prose(url: str, facts: list[dict]) -> str:
    """Ask the model to write prose using only the given facts."""
    user = f"Facts:\n{json.dumps(facts, indent=2)}"
    return chat(url, PROSE_SYSTEM, user)


def check_prose(url: str, facts: list[dict], prose: str) -> tuple[list[str], list[str]]:
    """Ask the model which claims in ``prose`` are invented or which facts are dropped."""
    user = f"Facts:\n{json.dumps(facts, indent=2)}\n\nProse:\n{prose}"
    reply = chat(url, CHECK_SYSTEM, user)
    data = _extract_json(reply, "{", "}")
    if not isinstance(data, dict):
        raise ValueError(f"no JSON object found in check reply: {reply!r}")
    return list(data.get("invented") or []), list(data.get("dropped") or [])


def run_sample(url: str, sample: dict, rounds: int) -> dict:
    """Extract, then (prose, check, re-extract) ``rounds`` times.

    Returns ``{"name", "rounds", "errors"}``: ``rounds`` matches the shape
    ``fact_probe_metrics`` expects, and ``errors`` (step one of "extract",
    "prose", "check", "reextract") is for the caller to fold into the run's
    overall error list. On any step's failure, this sample stops there --
    the caller moves on to the next sample.
    """
    name = sample.get("name")
    result = {"name": name, "rounds": [], "errors": []}

    def fail(round_index: int, step: str, exc: Exception) -> dict:
        result["errors"].append(
            {
                "sample": name,
                "round": round_index,
                "step": step,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return result

    try:
        facts = extract_facts(url, sample.get("text", ""))
    except Exception as exc:
        return fail(0, "extract", exc)

    for round_index in range(rounds):
        try:
            prose = write_prose(url, facts)
        except Exception as exc:
            return fail(round_index, "prose", exc)
        try:
            invented, dropped = check_prose(url, facts, prose)
        except Exception as exc:
            return fail(round_index, "check", exc)
        result["rounds"].append(
            {"facts": facts, "prose": prose, "invented": invented, "dropped": dropped}
        )
        try:
            facts = extract_facts(url, prose)
        except Exception as exc:
            return fail(round_index, "reextract", exc)

    result["rounds"].append(
        {"facts": facts, "prose": None, "invented": [], "dropped": []}
    )
    return result


# --- report bookkeeping -------------------------------------------------------


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_report(out_dir: Path, results: dict) -> None:
    summary = metrics.summarise(results)
    markdown = metrics.render_markdown(results, summary)
    _write_atomic(
        out_dir / "report.json",
        json.dumps({**results, "summary": summary}, indent=2, ensure_ascii=False),
    )
    _write_atomic(out_dir / "report.md", markdown)


def default_out() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / ".test-artifacts" / f"fact-probe-{stamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe a local model's description -> facts -> prose round trips. "
            "Needs TALEMATE_AI_TESTS=1 (ask the owner first)."
        )
    )
    parser.add_argument(
        "--rounds", type=int, default=3, help="round trips per sample (default 3)"
    )
    parser.add_argument(
        "--samples",
        type=Path,
        default=DEFAULT_SAMPLES,
        help=f"JSON file of [{{'name', 'text'}}, ...] (default {DEFAULT_SAMPLES})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder (default .test-artifacts/fact-probe-<YYYYmmdd-HHMMSS>/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if os.environ.get("TALEMATE_AI_TESTS") != "1":
        print(AI_GATE_MESSAGE, file=sys.stderr)
        return 2

    url = ai_helpers.koboldcpp_url()
    model = ai_helpers.koboldcpp_model(url)
    if model is None:
        print(
            f"koboldcpp is unreachable at {url} (or has no model loaded)",
            file=sys.stderr,
        )
        return 3

    samples = json.loads(args.samples.read_text(encoding="utf-8"))

    out_dir = (args.out or default_out()).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "model": model,
        "koboldcpp_url": url,
        "started": _now(),
        "finished": None,
        "samples": [],
        "errors": [],
    }
    _write_report(out_dir, results)

    for sample in samples:
        sample_result = run_sample(url, sample, args.rounds)
        results["errors"].extend(sample_result.pop("errors"))
        results["samples"].append(sample_result)
        _write_report(out_dir, results)

    results["finished"] = _now()
    _write_report(out_dir, results)
    print(f"done: {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
