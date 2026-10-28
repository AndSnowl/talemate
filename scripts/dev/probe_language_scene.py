"""Throwaway probe: does the scene model act on a language note (languages
plan 1, Task 8; spec part 2, probe 3).

Two strangers meet at a border inn: Mira (the player, a Sorauan) and Ivan
(an invented AI character, a Moscavian). Their sheets say nothing about
language, so the note is the only place the scene learns it. The same scene is played three times, each in a fresh scratch world, with
Talemate's own narrator and conversation agents on Talemate's KoboldCpp
client (`probe_heritage_play`'s loading and play loop, its turns swapped
for this probe's):

- `none`: no language note;
- `barrier`: "Ivan and Mira share no language: they can't simply talk.";
- `similar`: "Ivan's Moscavian is close to Mira's Sorauan: they understand
  each other with effort."

The note is added where part 4's note would go: appended to the World
block (`worldplay.context.world_context_block`, wrapped for the run). Each
turn is scanned for cues of misunderstanding (`_CUES`); the owner judges
the turns. Not a test: it calls koboldcpp, one call at a time; the owner
approved this plan's probes in advance (2026-10-28)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib uv run --no-sync python \\
        scripts/dev/probe_language_scene.py OUT.json'

Findings: docs/superpowers/probes/2026-10-28-language-scene.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_heritage_play as harness  # noqa: E402

import talemate.worldplay.context as worldplay_context  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.store import World  # noqa: E402
from talemate.worldplay.persistence import close_world_scene  # noqa: E402
from talemate.worldplay.setup import plan_scene, start_scene  # noqa: E402

START = WorldDate.of(1412)

NOTES = {
    "none": None,
    "barrier": "Ivan and Mira share no language: they can't simply talk.",
    "similar": (
        "Ivan's Moscavian is close to Mira's Sorauan: they understand each "
        "other with effort."
    ),
}

SETUP = {
    "player": "Mira",
    "characters": [
        {
            "name": "Mira",
            "facts": [
                "A young Sorauan herb-seller travelling north.",
            ],
        },
        {
            "name": "Ivan",
            "facts": [
                "A Moscavian border guard, off duty, with a broken cart wheel.",
                "Gruff but fair.",
            ],
        },
    ],
    "place": {
        "name": "The Ford Inn",
        "facts": ["A smoky inn at the river ford on the Sorau-Moscavia border."],
    },
    "goal": "Mira needs a ride north; Ivan needs help mending his cart wheel.",
    "intro": "Rain drums on the roof of the Ford Inn as Mira sits down across from Ivan.",
}

# (kind, who, player line before it, direction)
TURNS: list[tuple[str, str, str | None, str | None]] = [
    ("narrator", "progress_story", None, "Mira and Ivan size each other up."),
    (
        "conversation",
        "Ivan",
        "Mira: Excuse me, are you heading north? I can pay for a ride.",
        None,
    ),
    (
        "conversation",
        "Ivan",
        "Mira: I saw your cart outside. The wheel is cracked. I know a little about mending.",
        None,
    ),
    (
        "narrator",
        "progress_story",
        None,
        "They try to agree on a deal: her help with the wheel for a ride north.",
    ),
    (
        "conversation",
        "Ivan",
        "Mira: So we have a deal? We leave at dawn?",
        None,
    ),
    (
        "narrator",
        "progress_story",
        None,
        "The innkeeper brings bread and the evening winds down.",
    ),
]

_CUES = {
    "understand": r"understand|understood|comprehend|make out|meaning",
    "gesture": r"gestur|point(s|ed|ing)?\b|mime|pantomim|nod(s|ded)?\b|sign(s|ed)?\b",
    "repeat_slow": r"\brepeat|\bslowly\b|\bagain\b",
    "foreign": r"foreign|tongue|language|accent|dialect|words? (he|she) (doesn't|does not|didn't)",
    "puzzled": r"frown|blank|puzzl|confus|shrug|tilt",
}


def _with_note(note: str | None):
    """`world_context_block` with `note` appended (unchanged for None)."""
    original = worldplay_context.world_context_block

    def block(*args, **kwargs) -> str:
        text = original(*args, **kwargs)
        return f"{text}\n{note}" if note else text

    return original, block


async def play_variant(key: str, note: str | None, client, root: Path, run: dict, save):
    """One variant: a fresh world, the scene planned from SETUP and started,
    then the turns played with the note in the World block."""
    world = World.create(f"Language {key}", root=root / key)
    world.set_present(START)
    setup = await plan_scene(
        world, "Mira meets Ivan at the Ford Inn", {}, None, START, None, reply=SETUP
    )
    scene_id = await start_scene(world, setup, client)
    original, block = _with_note(note)
    worldplay_context.world_context_block = block
    record = world.scenes().get(scene_id)
    run["world_block"] = block(world, record, START)
    scene = await harness._load(world, scene_id, client, memory=False)
    try:
        await harness.play(scene, run, save)
    finally:
        worldplay_context.world_context_block = original
        close_world_scene(scene)
        world.close()


async def main(out: Path) -> None:
    harness._quiet_loading(False)
    harness.TURNS = TURNS
    harness._SCAN = _CUES
    client = harness.RecordingClient(name="KoboldCpp")
    client.calls = []
    await client.status()
    results: dict[str, Any] = {"model": client.model_name, "variants": {}}

    def save() -> None:
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")

    client.on_call = save
    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        for key, note in NOTES.items():
            run: dict[str, Any] = {"note": note, "turns": []}
            results["variants"][key] = run
            try:
                await play_variant(key, note, client, Path(root), run, save)
            except Exception as exc:  # a failure is a finding
                run["error"] = repr(exc)
            save()
    results["calls"] = len(client.calls)
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.out.resolve()))
