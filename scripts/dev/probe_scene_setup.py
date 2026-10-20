"""Scene-setup probe against a local model (Phase 2a, Task 2).

Throwaway probe: for each storyline prompt in ``--prompts`` (default
``scripts/dev/probe_data/world_prompts.json``'s ``scene_prompts``), asks
the model to plan the opening of a scene -- player, characters, place,
goal and intro -- given the prompt plus a tiny world (also in that file,
under ``tiny_world``: a couple of characters, a place, a lore entry)
rendered as plain text. The model is asked to flag, for each named
character and the place, whether it matches one of those world things or
was invented for the prompt; the probe does not just take that self-report
on faith -- it checks each name against ``tiny_world``'s own names (case-
and whitespace-normalised) and records both the model's claim and whether
that claim was right (``named``, with ``self_report``/``in_world``/
``self_report_correct`` per name), alongside the simpler ``world_used``/
``invented`` name lists.

A malformed reply shape (e.g. a character given as a bare string instead
of ``{"name", "world"}``) fails just that prompt, recorded as a "shape"
error, rather than aborting the run.

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
import re
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


def _normalize_name(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def world_names(tiny_world: dict) -> list[str]:
    """``tiny_world``'s character and place names -- the ground truth a
    scene's named things are checked against (lore isn't a nameable scene
    thing, so it's left out)."""
    names = []
    for key in ("characters", "places"):
        for thing in tiny_world.get(key) or []:
            name = thing.get("name")
            if name:
                names.append(name)
    return names


def _named_entries(scene: dict) -> list[dict]:
    """The scene's named characters plus its place, as a flat list of
    ``{"name", "world"}`` dicts.

    Raises ``ValueError`` if an entry isn't shaped as asked for (e.g. a
    character given as a bare string) -- the caller turns that into a
    recorded error for just this prompt instead of crashing the run.
    """
    named = []
    for character in scene.get("characters") or []:
        if not isinstance(character, dict):
            raise ValueError(f"character entry is not an object: {character!r}")
        named.append(character)
    place = scene.get("place")
    if place is not None:
        if not isinstance(place, dict):
            raise ValueError(f"place entry is not an object: {place!r}")
        named.append(place)
    return named


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

    Returns ``{"prompt", "scene", "tiny_world_names", "named", "world_used",
    "invented", "errors"}``. ``scene`` is the model's parsed JSON reply
    as-is. ``tiny_world_names`` is the ground truth (``world_names``)
    checked against. ``named`` lists, per character and the place,
    ``{"name", "self_report", "in_world", "self_report_correct"}`` --
    ``self_report`` is the model's own ``world`` flag, ``in_world`` is the
    normalised-name match against ``tiny_world_names``, and
    ``self_report_correct`` is whether the two agree. ``world_used`` and
    ``invented`` are the simpler names-only lists (by ``self_report``, for
    convenience). ``errors`` (step "setup" for a bad/unparsable reply,
    "shape" for a parsed reply whose inner shape isn't as asked for) is
    for the caller to fold into the run's overall error list. Either way,
    this prompt stops there -- the caller moves on to the next prompt.

    ``on_step``, if given, is called once with the result dict built so
    far (including on failure).
    """
    result = {
        "prompt": prompt_text,
        "scene": None,
        "tiny_world_names": None,
        "named": None,
        "world_used": None,
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

    user = f"Storyline prompt:\n{prompt_text}\n\nWorld:\n{render_world(tiny_world)}"
    try:
        reply = chat(url, SETUP_SYSTEM, user)
        scene = _extract_json(reply, "{", "}")
        if not isinstance(scene, dict):
            raise ValueError(f"no JSON object found in setup reply: {reply!r}")
    except Exception as exc:
        return fail("setup", exc)
    result["scene"] = scene
    notify()

    try:
        named = _named_entries(scene)
    except Exception as exc:
        return fail("shape", exc)

    known = {_normalize_name(name) for name in world_names(tiny_world)}
    checked = []
    for thing in named:
        name = thing.get("name")
        self_report = bool(thing.get("world"))
        in_world = bool(name) and _normalize_name(name) in known
        checked.append(
            {
                "name": name,
                "self_report": self_report,
                "in_world": in_world,
                "self_report_correct": self_report == in_world,
            }
        )
    result["tiny_world_names"] = world_names(tiny_world)
    result["named"] = checked
    result["world_used"] = [c["name"] for c in checked if c["self_report"]]
    result["invented"] = [c["name"] for c in checked if not c["self_report"]]
    notify()
    return result


# --- report bookkeeping -------------------------------------------------------


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _table(header: list[str], rows: list[list]) -> list[str]:
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    lines += [
        "| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |"
        for row in rows
    ]
    return lines


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
        out.append(f"- **Tiny world names:** {prompt_result.get('tiny_world_names')}")
        out.append(f"- **World used (self-report):** {prompt_result.get('world_used')}")
        out.append(f"- **Invented (self-report):** {prompt_result.get('invented')}")
        out.append("")
        named = prompt_result.get("named") or []
        if named:
            out += ["### Self-report vs. ground truth", ""]
            out += _table(
                ["Name", "Self-report", "In world", "Correct"],
                [
                    [
                        n["name"],
                        n["self_report"],
                        n["in_world"],
                        n["self_report_correct"],
                    ]
                    for n in named
                ],
            )
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
