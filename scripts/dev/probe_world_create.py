"""Create-from-prompt probe against a local model (Phase 2a, Task 2).

Throwaway probe: for each ``{"kind", "prompt"}`` entry in ``--prompts``
(default ``scripts/dev/probe_data/world_prompts.json``'s ``create_prompts``),
asks the model to create a thing of that kind from the owner's short prompt
-- treating the prompt as intent and inventing plausible detail generously,
the way Talemate's `@` action expands rough input -- then write prose from
the resulting facts, then (a second chat call) check which phrases of the
prompt's intent the facts carried through and which facts have no basis in
the prompt at all.

The create prompt (``CREATE_SYSTEM``) is the seed for Task 7's
create-from-prompt template; keep its wording here, not duplicated
elsewhere.

Writes ``report.json``/``report.md`` (rewritten after every step -- create,
prose or intent-check -- so a killed or hung run loses at most the step in
flight) into ``--out``.

Makes real model calls, so it needs ``TALEMATE_AI_TESTS=1`` (ask the owner
first)::

    TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync \\
        python scripts/dev/probe_world_create.py [--prompts PATH] [--out DIR]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_helpers  # noqa: E402
import talemate_app  # noqa: E402
from probe_fact_roundtrip import _extract_json, chat  # noqa: E402

from talemate.world.kinds import get_kind  # noqa: E402

DEFAULT_PROMPTS = Path(__file__).resolve().parent / "probe_data" / "world_prompts.json"

CREATE_SYSTEM = (
    "You create a new {kind} for a fantasy world from the owner's short "
    "prompt. Treat the prompt as intent, not a spec: invent plausible "
    "detail generously to fill it out, the way Talemate's `@` action "
    "expands a rough action into a fleshed-out one. Reply with only a "
    'JSON list of facts, each shaped {{"category", "text", "since"}} '
    '("since" optional, a bare year, only when the fact is dated), where '
    "category is one of: {categories}. One fact per claim. No commentary, "
    "no markdown fences, just the JSON list."
)

PROSE_SYSTEM = (
    "You write a short passage of prose from a list of facts, each shaped "
    '{"category", "text"}, optionally with a "since" year. Write using '
    "only the given facts -- invent nothing further -- and keep each "
    "fact's exact wording where it reads naturally. Reply with only the "
    "prose, no commentary."
)

INTENT_CHECK_SYSTEM = (
    "You compare a short creation prompt against a JSON list of facts "
    'generated from it, each shaped {"category", "text", "since"}. Reply '
    'with only a JSON object shaped {"kept_intent": [{"phrase", "kept"}], '
    '"invented": [...]}: kept_intent lists the distinct phrases of intent '
    "in the prompt with whether the facts carry that intent through "
    "(true/false), and invented lists facts with no basis in the prompt, "
    "in the facts' own wording. No commentary, no markdown fences."
)


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def run_prompt(
    url: str,
    entry: dict,
    *,
    on_step: Callable[[dict], None] | None = None,
) -> dict:
    """Create facts for ``entry``, write prose from them, then check intent.

    Returns ``{"kind", "prompt", "facts", "prose", "kept_intent",
    "invented", "errors"}``. ``errors`` (step one of "create", "prose",
    "intent_check") is for the caller to fold into the run's overall error
    list. On any step's failure, this prompt stops there -- the caller
    moves on to the next prompt.

    ``on_step``, if given, is called with the result dict built so far
    after every step (including the failing one, if any).
    """
    kind_name = entry.get("kind")
    prompt_text = entry.get("prompt", "")
    result = {
        "kind": kind_name,
        "prompt": prompt_text,
        "facts": None,
        "prose": None,
        "kept_intent": None,
        "invented": None,
        "errors": [],
    }

    def notify() -> None:
        if on_step is not None:
            on_step(result)

    def fail(step: str, exc: Exception) -> dict:
        result["errors"].append(
            {
                "prompt": prompt_text,
                "step": step,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        notify()
        return result

    kind = get_kind(kind_name)
    categories = ", ".join(kind.categories)

    try:
        reply = chat(
            url,
            CREATE_SYSTEM.format(kind=kind_name, categories=categories),
            prompt_text,
        )
        facts = _extract_json(reply, "[", "]")
        if not isinstance(facts, list):
            raise ValueError(f"no JSON list found in create reply: {reply!r}")
    except Exception as exc:
        return fail("create", exc)
    result["facts"] = facts
    notify()

    try:
        prose = chat(url, PROSE_SYSTEM, f"Facts:\n{json.dumps(facts, indent=2)}")
    except Exception as exc:
        return fail("prose", exc)
    result["prose"] = prose
    notify()

    try:
        reply = chat(
            url,
            INTENT_CHECK_SYSTEM,
            f"Prompt:\n{prompt_text}\n\nFacts:\n{json.dumps(facts, indent=2)}",
        )
        data = _extract_json(reply, "{", "}")
        if not isinstance(data, dict):
            raise ValueError(f"no JSON object found in intent-check reply: {reply!r}")
    except Exception as exc:
        return fail("intent_check", exc)
    result["kept_intent"] = list(data.get("kept_intent") or [])
    result["invented"] = len(data.get("invented") or [])
    notify()
    return result


# --- report bookkeeping -------------------------------------------------------


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _render_markdown(results: dict) -> str:
    out = [
        "# World create-from-prompt probe",
        "",
        f"- **Model:** {results.get('model') or 'n/a'}",
        f"- **Started:** {results.get('started') or 'n/a'}",
        f"- **Finished:** {results.get('finished') or 'not finished (partial report)'}",
        "",
    ]
    for prompt_result in results.get("prompts") or []:
        out += [
            f"## {prompt_result.get('kind')}: {prompt_result.get('prompt')}",
            "",
        ]
        facts = prompt_result.get("facts") or []
        out.append(f"- **Facts:** {len(facts)}")
        out.append(f"- **Invented:** {prompt_result.get('invented')}")
        kept_intent = prompt_result.get("kept_intent") or []
        kept = sum(1 for item in kept_intent if item.get("kept"))
        out.append(f"- **Kept intent:** {kept}/{len(kept_intent)}")
        out.append("")
        if facts:
            out += ["### Facts", ""]
            for fact in facts:
                since = f" (since {fact.get('since')})" if fact.get("since") else ""
                out.append(f"- [{fact.get('category')}] {fact.get('text')}{since}")
            out.append("")
        if prompt_result.get("prose"):
            out += ["### Prose", "", prompt_result["prose"], ""]
        if kept_intent:
            out += ["### Kept intent", ""]
            for item in kept_intent:
                mark = "yes" if item.get("kept") else "no"
                out.append(f"- {item.get('phrase')}: {mark}")
            out.append("")

    errors = results.get("errors") or []
    if errors:
        out += ["## Errors", ""]
        for error in errors:
            out.append(
                f"- {error.get('prompt')!r} ({error.get('step')}): {error.get('error')}"
            )
        out.append("")

    return "\n".join(out)


def _write_report(out_dir: Path, results: dict) -> None:
    _write_atomic(
        out_dir / "report.json", json.dumps(results, indent=2, ensure_ascii=False)
    )
    _write_atomic(out_dir / "report.md", _render_markdown(results))


def default_out() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / ".test-artifacts" / f"world-create-probe-{stamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe a local model's create-from-prompt behaviour. Needs "
            "TALEMATE_AI_TESTS=1 (ask the owner first)."
        )
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=DEFAULT_PROMPTS,
        help=(
            "JSON file with a 'create_prompts' list of {'kind', 'prompt'} "
            f"(default {DEFAULT_PROMPTS})"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder (default .test-artifacts/world-create-probe-<YYYYmmdd-HHMMSS>/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if os.environ.get("TALEMATE_AI_TESTS") != "1":
        print(talemate_app.AI_GATE_MESSAGE, file=sys.stderr)
        return 2

    url = ai_helpers.koboldcpp_url()
    model = ai_helpers.koboldcpp_model(url)
    if model is None:
        print(
            f"koboldcpp is unreachable at {url} (or has no model loaded)",
            file=sys.stderr,
        )
        return 3

    data = json.loads(args.prompts.read_text(encoding="utf-8"))
    prompts = data["create_prompts"]

    out_dir = (args.out or default_out()).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "model": model,
        "koboldcpp_url": url,
        "started": _now(),
        "finished": None,
        "prompts": [],
        "errors": [],
    }
    _write_report(out_dir, results)

    for entry in prompts:
        index = len(results["prompts"])
        results["prompts"].append(
            {"kind": entry.get("kind"), "prompt": entry.get("prompt")}
        )

        def on_step(partial: dict, index: int = index) -> None:
            results["prompts"][index] = {
                k: v for k, v in partial.items() if k != "errors"
            }
            _write_report(out_dir, results)

        prompt_result = run_prompt(url, entry, on_step=on_step)
        results["errors"].extend(prompt_result.pop("errors"))
        results["prompts"][index] = prompt_result
        _write_report(out_dir, results)

    results["finished"] = _now()
    _write_report(out_dir, results)
    print(f"done: {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
