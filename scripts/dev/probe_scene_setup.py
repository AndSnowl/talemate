"""Scene-setup probe against a local model (Phase 2a, Task 2).

Throwaway probe: for each storyline prompt in ``--prompts`` (default
``scripts/dev/probe_data/world_prompts.json``'s ``scene_prompts``), asks
the model to plan the opening of a scene -- player, characters, place,
goal and intro -- given the prompt plus a tiny world (also in that file,
under ``tiny_world``: a couple of characters, a place, a lore entry)
rendered as plain text. The model is asked to flag, for each named
character and the place, whether it matches one of those world things or
was invented for the prompt; the report also rolls that up into
``world_used``/``invented`` name lists.

The setup prompt (``SETUP_SYSTEM``) is the seed for Task 8's scene-setup
template; keep its wording here, not duplicated elsewhere.

Writes ``report.json``/``report.md`` (rewritten after every prompt) into
``--out``.

Makes real model calls, so it needs ``TALEMATE_AI_TESTS=1`` (ask the owner
first)::

    TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync \\
        python scripts/dev/probe_scene_setup.py [--prompts PATH] [--out DIR]
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

DEFAULT_PROMPTS = Path(__file__).resolve().parent / "probe_data" / "world_prompts.json"

SETUP_SYSTEM = (
    "You plan the opening of a roleplay scene from a short storyline "
    "prompt and the world things already established. Reuse a named "
    "world thing whenever the prompt fits it, and invent only what the "
    "prompt needs beyond them -- flag each one honestly. Reply with only "
    'a JSON object shaped {"player", "characters": [{"name", "world": '
    'true|false}], "place": {"name", "world": true|false}, "goal", '
    '"intro"}, where "world" is true only for a character or place that '
    "matches one of the world things given, and false for one you "
    "invented. No commentary, no markdown fences."
)


def render_world(tiny_world: dict) -> str:
    """Render ``tiny_world`` (``characters``, ``places``, ``lore`` lists of
    ``{"name", "summary"}``) as plain text for the model."""
    lines = []
    for label, key in (
        ("Characters", "characters"),
        ("Places", "places"),
        ("Lore", "lore"),
    ):
        things = tiny_world.get(key) or []
        if not things:
            continue
        lines.append(f"{label}:")
        for thing in things:
            lines.append(f"- {thing.get('name')}: {thing.get('summary', '')}")
    return "\n".join(lines)


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def run_prompt(
    url: str,
    prompt_text: str,
    tiny_world: dict,
    *,
    on_step: Callable[[dict], None] | None = None,
) -> dict:
    """Ask the model to plan a scene for ``prompt_text`` against ``tiny_world``.

    Returns ``{"prompt", "scene", "world_used", "invented", "errors"}``.
    ``scene`` is the model's parsed JSON reply as-is; ``world_used`` and
    ``invented`` are the names of its characters/place with ``world`` true
    or false, respectively. ``errors`` (step "setup") is for the caller to
    fold into the run's overall error list.

    ``on_step``, if given, is called once with the result dict built so
    far (including on failure).
    """
    result = {
        "prompt": prompt_text,
        "scene": None,
        "world_used": None,
        "invented": None,
        "errors": [],
    }

    def notify() -> None:
        if on_step is not None:
            on_step(result)

    user = f"Storyline prompt:\n{prompt_text}\n\nWorld:\n{render_world(tiny_world)}"
    try:
        reply = chat(url, SETUP_SYSTEM, user)
        scene = _extract_json(reply, "{", "}")
        if not isinstance(scene, dict):
            raise ValueError(f"no JSON object found in setup reply: {reply!r}")
    except Exception as exc:
        result["errors"].append(
            {
                "prompt": prompt_text,
                "step": "setup",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        notify()
        return result

    result["scene"] = scene
    named = list(scene.get("characters") or [])
    place = scene.get("place")
    if isinstance(place, dict):
        named = named + [place]
    result["world_used"] = [n.get("name") for n in named if n.get("world")]
    result["invented"] = [n.get("name") for n in named if not n.get("world")]
    notify()
    return result


# --- report bookkeeping -------------------------------------------------------


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _render_markdown(results: dict) -> str:
    out = [
        "# Scene-setup probe",
        "",
        f"- **Model:** {results.get('model') or 'n/a'}",
        f"- **Started:** {results.get('started') or 'n/a'}",
        f"- **Finished:** {results.get('finished') or 'not finished (partial report)'}",
        "",
    ]
    for prompt_result in results.get("prompts") or []:
        out += [f"## {prompt_result.get('prompt')}", ""]
        scene = prompt_result.get("scene")
        out.append(f"- **World used:** {prompt_result.get('world_used')}")
        out.append(f"- **Invented:** {prompt_result.get('invented')}")
        out.append("")
        if scene:
            out += ["### Scene", "", "```json", json.dumps(scene, indent=2), "```", ""]

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
    return REPO_ROOT / ".test-artifacts" / f"scene-setup-probe-{stamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe a local model's scene-setup behaviour. Needs "
            "TALEMATE_AI_TESTS=1 (ask the owner first)."
        )
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=DEFAULT_PROMPTS,
        help=(
            "JSON file with 'scene_prompts' (a list of strings) and "
            f"'tiny_world' (default {DEFAULT_PROMPTS})"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder (default .test-artifacts/scene-setup-probe-<YYYYmmdd-HHMMSS>/)",
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
    prompts = data["scene_prompts"]
    tiny_world = data["tiny_world"]

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

    for prompt_text in prompts:
        index = len(results["prompts"])
        results["prompts"].append({"prompt": prompt_text})

        def on_step(partial: dict, index: int = index) -> None:
            results["prompts"][index] = {
                k: v for k, v in partial.items() if k != "errors"
            }
            _write_report(out_dir, results)

        prompt_result = run_prompt(url, prompt_text, tiny_world, on_step=on_step)
        results["errors"].extend(prompt_result.pop("errors"))
        results["prompts"][index] = prompt_result
        _write_report(out_dir, results)

    results["finished"] = _now()
    _write_report(out_dir, results)
    print(f"done: {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
