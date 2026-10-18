"""Overnight evaluation of the Culture agent against a live model.

Runs the three cultures AI scenarios (``tests/ai/cultures/scenarios.py``)
several times against koboldcpp, through an isolated local app
(``talemate_app.py``) driven over its websocket (``talemate_ws.py``), and
writes ``report.json`` (every raw result, plus the summary) and
``report.md`` (a plain-language report) into the output folder. Both are
rewritten after every step, so a crash keeps what was done so far.

Per run and scenario: seed a fresh world, create ``--npcs`` characters,
ask for ``--narrations`` narrations (alternating "progress" with a fixed
direction and "narrate environment"), then request two snapshots. The
metrics are in ``cultures_eval_metrics.py``.

Makes real model calls, so it needs ``TALEMATE_AI_TESTS=1`` (ask the owner
first)::

    TALEMATE_AI_TESTS=1 guix shell -m manifest.scm -- uv run --no-sync \\
        python scripts/dev/eval_cultures_ai.py [--runs 3] [--npcs 5] \\
        [--narrations 3] [--out DIR]

At full size (3 runs x 3 scenarios, 5 characters, 3 narrations) this takes
roughly 1 to 2 hours on Skyfall-31B (about 8-12 minutes per scenario
run): a character creation takes 60-75 s, a narration 10-60 s and a
snapshot 20-60 s.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_helpers  # noqa: E402
import cultures_eval_metrics as metrics  # noqa: E402
import talemate_app  # noqa: E402
from talemate_ws import BackendSession  # noqa: E402

from ai.cultures.scenarios import (  # noqa: E402
    ADDITION_MESSAGE,
    CULTURE_FILES,
    KNOWN_NAMES_MESSAGE,
    NPC_ROLES,
    SCENARIOS,
    seed_scenario,
)
from talemate.cultures.store import WorldStore  # noqa: E402

PROGRESS_DIRECTION = "Hadrik drops a crate on his foot."
SNAPSHOTS = 2
SECTION_TITLE = "Cultures and names"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def default_out() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / ".test-artifacts" / f"cultures-eval-{stamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Overnight evaluation of the Culture agent against the live model. "
            "Needs TALEMATE_AI_TESTS=1 (ask the owner first)."
        )
    )
    parser.add_argument(
        "--runs", type=int, default=3, help="runs of each scenario (default 3)"
    )
    parser.add_argument(
        "--npcs",
        type=int,
        default=5,
        help=f"characters created per run (default 5, at most {len(NPC_ROLES)})",
    )
    parser.add_argument(
        "--narrations", type=int, default=3, help="narrations per run (default 3)"
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=sorted(SCENARIOS),
        default=list(SCENARIOS),
        help="scenarios to run (default: all three)",
    )
    parser.add_argument(
        "--render-only",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "don't run anything: reload DIR/report.json, recompute the summary "
            "with the current metrics code and rewrite DIR/report.json and "
            "DIR/report.md (no app, no model, no TALEMATE_AI_TESTS needed)"
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output folder (default .test-artifacts/cultures-eval-<YYYYmmdd-HHMMSS>/)",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.npcs <= len(NPC_ROLES):
        parser.error(f"--npcs must be between 1 and {len(NPC_ROLES)}")
    return args


# --- results bookkeeping -------------------------------------------------------


def culture_info() -> tuple[dict, dict]:
    """``{culture_id: {name, language}}`` and Taelrik's curses and sayings."""
    cultures, phrases = {}, {"curse": [], "saying": []}
    for path in CULTURE_FILES:
        culture = json.loads(path.read_text())["culture"]
        cultures[culture["id"]] = {
            "name": culture["name"],
            "language": culture["language"],
        }
        if culture["id"] == "taelrik":
            for phrase in culture["language"].get("phrases") or []:
                category = phrase.get("category", "").lower()
                for stem in phrases:
                    if category.startswith(stem):
                        phrases[stem].append(phrase["original"])
    return cultures, phrases


class Report:
    """The results dict, and writing it (and its summary) after each step."""

    def __init__(self, out_dir: Path, results: dict):
        self.out_dir = out_dir
        self.results = results

    def error(self, scenario: str, run: int, step: str, exc: BaseException) -> None:
        self.results["errors"].append(
            {
                "scenario": scenario,
                "run": run,
                "step": step,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "at": _now(),
            }
        )
        log(f"  ERROR in {scenario} run {run}, {step}: {type(exc).__name__}: {exc}")

    def write(self) -> None:
        try:
            summary = metrics.summarise(self.results)
            markdown = metrics.render_markdown(summary, self.results["model"])
        except Exception as exc:  # a metrics bug must not lose the raw data
            summary = {
                "error": f"summarise failed: {exc}",
                "traceback": traceback.format_exc(),
            }
            markdown = f"# Cultures AI evaluation\n\nThe summary failed: {exc}\n"
        # a failed write (disk full, a bad value) is logged; the run goes on
        # and the next step's write tries again
        try:
            _write_atomic(
                self.out_dir / "report.json",
                json.dumps(
                    {**self.results, "summary": summary},
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),
            )
        except Exception as exc:
            log(f"  could not write report.json: {type(exc).__name__}: {exc}")
        try:
            _write_atomic(self.out_dir / "report.md", markdown)
        except Exception as exc:
            log(f"  could not write report.md: {type(exc).__name__}: {exc}")


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


_STARTED = time.monotonic()


def log(text: str) -> None:
    elapsed = int(time.monotonic() - _STARTED)
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    print(
        f"[{stamp} +{elapsed // 3600}:{elapsed // 60 % 60:02d}:{elapsed % 60:02d}] {text}",
        flush=True,
    )


class Progress:
    """Counts steps and estimates the time left from the average step."""

    def __init__(self, total: int):
        self.total = total
        self.done = 0
        self.started = time.monotonic()

    def step(self) -> str:
        self.done += 1
        spent = time.monotonic() - self.started
        left = (self.total - self.done) * spent / self.done
        return f"[{self.done}/{self.total}, about {left / 60:.0f} min left]"


# --- one scenario run ----------------------------------------------------------


def _characters(session: BackendSession) -> list[dict]:
    return session.get_world().get("characters") or []


def _glossary(world) -> list[dict]:
    return [
        e.model_dump(mode="json") for e in WorldStore(world.world_dir).load_glossary()
    ]


def create_npc(session: BackendSession, world, hint: str, content: str) -> dict:
    before = {c["name"] for c in _characters(session)}
    mark = session.mark()
    started = time.monotonic()
    session.persist_character(hint, content)
    wall = time.monotonic() - started

    characters = _characters(session)
    events = session.events("name_chosen", mark)
    pick = next(
        (e for e in events if e.get("generator_id")), events[0] if events else None
    )
    new = [c for c in characters if c["name"] not in before]
    name = pick.get("name") if pick else (new[0]["name"] if new else None)
    character = next((c for c in characters if c["name"] == name), None)
    if character is None and new:
        character, name = new[0], new[0]["name"]
    culture = (character or {}).get("culture") or {}

    culture_prompts = [
        {"action": p.get("agent_action"), "time": p.get("time")}
        for p in session.prompts("culture", mark)
    ]
    entry = next(
        (e for e in _glossary(world) if name and e["text"].lower() == name.lower()),
        None,
    )
    return {
        "role": hint,
        "content": content,
        "name": name,
        "culture_id": culture.get("culture_id") or (pick or {}).get("culture_id"),
        "character_culture": culture or None,
        "event": pick,
        "name_events": events,
        "wall_s": round(wall, 2),
        "culture_prompts": culture_prompts,
        "culture_prompt_s": round(sum(p["time"] or 0 for p in culture_prompts), 2),
        "pick_prompt_s": round(
            sum(p["time"] or 0 for p in culture_prompts if p["action"] == "pick_name"),
            2,
        )
        if any(p["action"] == "pick_name" for p in culture_prompts)
        else None,
        "entry": entry,
    }


def narrate(session: BackendSession, index: int, timeout: float = 900) -> dict:
    # Even-numbered (from 0) narrations progress the story with Hadrik's
    # mishap, so he has a reason to curse; odd ones narrate the scene.
    action = "narrate_environment" if index % 2 == 1 else "progress"
    direction = "" if action == "narrate_environment" else PROGRESS_DIRECTION
    mark = session.mark()
    started = time.monotonic()
    session.send(
        {"type": "narrator", "action": action, "narrative_direction": direction}
    )

    # Not session.narrate(): loading a scene can push a stray untagged
    # narrator message (the intro). Only a narrator message after this
    # request's narrator prompt is the answer.
    seen_prompt = {"value": False}

    def done(message: dict) -> bool:
        if (
            message.get("type") == "prompt_sent"
            and (message.get("data") or {}).get("agent_type") == "narrator"
        ):
            seen_prompt["value"] = True
            return False
        return (
            seen_prompt["value"]
            and message.get("type") == "narrator"
            and not message.get("action")
        )

    def failed(message: dict) -> bool:
        return (
            not seen_prompt["value"]
            and message.get("type") == "narrator"
            and message.get("action") == "operation_done"
        )

    message = session.wait_for(done, timeout, error=failed)
    wall = time.monotonic() - started

    contexts = [
        e
        for e in session.events("context_injected", mark)
        if e.get("agent") == "narrator"
    ]
    prompts = session.prompts("narrator", mark)
    prompt = next(
        (p for p in reversed(prompts) if SECTION_TITLE in (p.get("prompt") or "")),
        prompts[-1] if prompts else {},
    )
    return {
        "index": index,
        "action": action,
        "direction": direction,
        "context": contexts[-1] if contexts else None,
        "prompt_tokens": prompt.get("prompt_tokens"),
        "prompt": prompt.get("prompt") or "",
        "raw_response": prompt.get("response"),
        "response": message.get("message", ""),
        "wall_s": round(wall, 2),
    }


def snapshot(session: BackendSession) -> dict:
    started = time.monotonic()
    data = session.request_snapshot()
    return {"data": data, "wall_s": round(time.monotonic() - started, 2)}


def run_scenario(
    report: Report, info, key: str, run: int, args, progress: Progress
) -> None:
    scenario = SCENARIOS[key]
    record = {
        "run": run,
        "project": f"eval-{key}-{run}",
        "started": _now(),
        "npcs": [],
        "narrations": [],
        "snapshots": [],
        "characters": [],
        "glossary_new": [],
    }
    report.results["scenarios"][key]["runs"].append(record)
    label = f"{key} run {run}/{args.runs}"
    steps_left = args.npcs + args.narrations + SNAPSHOTS

    def skip_rest():
        for _ in range(steps_left):
            progress.step()

    try:
        world = seed_scenario(
            info.root,
            record["project"],
            scenario,
            with_trait_character=True,
            messages=[KNOWN_NAMES_MESSAGE, ADDITION_MESSAGE],
        )
    except Exception as exc:
        report.error(key, run, "seed", exc)
        report.write()
        skip_rest()
        return

    try:
        session_cm = BackendSession(info.backend_ws_url)
        session = session_cm.__enter__()
    except Exception as exc:
        report.error(key, run, "connect", exc)
        report.write()
        skip_rest()
        return

    try:
        try:
            session.wait_client_ready()
            session.load_scene(world.scene_path)
        except Exception as exc:
            report.error(key, run, "load_scene", exc)
            report.write()
            skip_rest()
            return
        log(f"{label}: scene loaded")

        offset = ((run - 1) * args.npcs) % len(NPC_ROLES)
        roles = [NPC_ROLES[(offset + i) % len(NPC_ROLES)] for i in range(args.npcs)]
        for i, (hint, content) in enumerate(roles, 1):
            steps_left -= 1
            try:
                npc = create_npc(session, world, hint, content)
                record["npcs"].append(npc)
                event = npc["event"] or {}
                log(
                    f"{label}: character {i}/{args.npcs} {hint!r} -> {npc['name']} "
                    f"({npc['culture_id']}, {event.get('generator_id') or 'no generator'}) "
                    f"in {npc['wall_s']:.0f} s {progress.step()}"
                )
            except Exception as exc:
                report.error(key, run, f"character {i} ({hint})", exc)
                progress.step()
            report.write()

        for i in range(args.narrations):
            steps_left -= 1
            try:
                narration = narrate(session, i)
                narration["hadrik_present"] = metrics.hadrik_present(narration)
                record["narrations"].append(narration)
                spares = [
                    s["text"] for s in (narration["context"] or {}).get("spares") or []
                ]
                log(
                    f"{label}: narration {i + 1}/{args.narrations} ({narration['action']}) "
                    f"in {narration['wall_s']:.0f} s, section "
                    f"{(narration['context'] or {}).get('tokens', 'none')} tokens, "
                    f"spares {', '.join(spares) or 'none'} {progress.step()}"
                )
            except Exception as exc:
                report.error(key, run, f"narration {i + 1}", exc)
                progress.step()
            report.write()

        for i in range(SNAPSHOTS):
            steps_left -= 1
            try:
                snap = snapshot(session)
                record["snapshots"].append(snap)
                names = [n.get("text") for n in snap["data"].get("new_names") or []]
                log(
                    f"{label}: snapshot {i + 1}/{SNAPSHOTS} in {snap['wall_s']:.0f} s, "
                    f"new names: {', '.join(names) or 'none'} {progress.step()}"
                )
            except Exception as exc:
                report.error(key, run, f"snapshot {i + 1}", exc)
                progress.step()
            report.write()

        try:
            record["characters"] = _characters(session)
            record["glossary_new"] = [
                e
                for e in _glossary(world)
                if (e.get("origin") or {}).get("by") != "import"
            ]
            # every snapshot the backend reported, including background ones
            # (the requested ones are in "snapshots")
            record["all_snapshot_events"] = session.events("snapshot_processed")
        except Exception as exc:
            report.error(key, run, "collect", exc)
    finally:
        record["finished"] = _now()
        report.write()
        try:
            session_cm.__exit__(None, None, None)
        except Exception:
            pass


# --- main --------------------------------------------------------------------------


def ensure_app(info, root: Path):
    """Restart the app if its backend died during the previous scenario."""
    if info is not None and talemate_app.status(root) is not None:
        return info
    if info is not None:
        log("the app is not running any more; restarting it")
        talemate_app.stop(root)
    return talemate_app.start(root=root, ai=True)


def render_only(out_dir: Path) -> int:
    """Re-render ``out_dir``'s report from its raw results; start nothing."""
    path = out_dir / "report.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 1
    data.pop("summary", None)
    Report(out_dir, data).write()
    print(f"re-rendered {out_dir / 'report.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.render_only is not None:
        return render_only(args.render_only.resolve())
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
        return 1

    out_dir = (args.out or default_out()).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model.txt").write_text(model + "\n")

    cultures, phrases = culture_info()
    results = {
        "model": model,
        "koboldcpp_url": url,
        "started": _now(),
        "finished": None,
        "config": {
            "runs": args.runs,
            "npcs": args.npcs,
            "narrations": args.narrations,
            "snapshots": SNAPSHOTS,
            "scenarios": args.scenarios,
            "progress_direction": PROGRESS_DIRECTION,
        },
        "cultures": cultures,
        "trait_phrases": phrases,
        "scenarios": {
            key: {"expected": SCENARIOS[key].expected, "runs": []}
            for key in args.scenarios
        },
        "errors": [],
    }
    report = Report(out_dir, results)
    report.write()
    log(f"model {model}; writing to {out_dir}")

    total = args.runs * len(args.scenarios) * (args.npcs + args.narrations + SNAPSHOTS)
    progress = Progress(total)
    root = Path(tempfile.mkdtemp(prefix="cultures-eval-app-"))
    info = None
    try:
        for run in range(1, args.runs + 1):
            for key in args.scenarios:
                try:
                    info = ensure_app(info, root)
                except Exception as exc:
                    report.error(key, run, "start app", exc)
                    report.write()
                    info = None
                    for _ in range(args.npcs + args.narrations + SNAPSHOTS):
                        progress.step()
                    continue
                log(f"{key} run {run}/{args.runs}: start")
                try:
                    run_scenario(report, info, key, run, args, progress)
                except Exception as exc:  # backstop: never lose the other runs
                    report.error(key, run, "scenario run", exc)
                    report.write()
        results["finished"] = _now()
    except KeyboardInterrupt:
        log("interrupted; writing what was done so far")
        results["errors"].append(
            {
                "scenario": "-",
                "run": "-",
                "step": "interrupted",
                "error": "KeyboardInterrupt",
                "at": _now(),
            }
        )
    finally:
        report.write()
        talemate_app.stop(root)
    log(f"done: {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
