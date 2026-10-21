"""Throwaway probe: heritage in play (fantasymate phase 2 plan B, Task 12).

Builds a small world in a temp dir -- the Owl-folk species (wings in place
of arms, talons used as hands, yellow eyes, crepuscular and head-turning
instincts), its Snowy race, Eira (a Snowy whose own black eyes override
the yellow ones) -- then plans and starts a scene in 499 with an invented
owl-folk innkeeper, Brannoc, through `setup.plan_scene` (a fixed setup
reply, no index) and `setup.start_scene`. Eira's prose for 499 is written
by the model through `prose_gen`, as the app does at scene start.

The scene is then loaded through its `world://` target and played with
Talemate's own agents on Talemate's own KoboldCpp client (the one the
`--ai` app configures, with its detected prompt template and presets):
three narrator turns (`progress_story` twice, `narrate_character` once)
and three conversation turns (`ConversationAgent.converse`), each after a
player line from Ilse that invites hands, gloves or night-time sleep. So
the prompts are the real narrator and conversation templates, with the
"World" instruction (`context.world_context_block`) and the character
sheets (`characters.character_from_world`, and `start_scene`'s invented
description) exactly as play sees them. The memory agent is the app's
ChromaDB one, on its default local embeddings (all-MiniLM-L6-v2, from the
local Hugging Face cache: run with `HF_HUB_OFFLINE=1`), with long-term
memory on as the app has it; `--no-memory` swaps in the tests' stub with
long-term memory off. What's approximated: agents run with their default
config rather than the owner's, no world-state agent updates or director
run between turns, and no frontend.

Every model call's kind, prompt and reply goes to the output JSON after
each call, with the sheets and World block the scene started with, and a
keyword scan of each turn (hands, fingers, gloves, arms; wings, talons).
Not a test: it calls the network. The owner granted koboldcpp access for
this plan's probes (one GPU: calls run one after another)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_heritage_play.py OUT.json \\
        [--no-memory]'

Findings: docs/superpowers/probes/2026-10-20-heritage-play.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
# the tests' stand-ins for the memory agent and the scene (no database)
sys.path.insert(0, str(REPO_ROOT / "tests"))

import talemate_app  # noqa: E402

import talemate.config.state as config_state  # noqa: E402
from talemate.config.schema import Config, RecentScenes  # noqa: E402

KOBOLDCPP_URL = "http://192.168.0.5:5001"
# the `--ai` app's config: one KoboldCpp client, the example agent config
config_state.CONFIG = Config.model_validate(
    yaml.safe_load(talemate_app.render_config(True, KOBOLDCPP_URL))
)

import talemate.instance as instance  # noqa: E402
from talemate.agents.memory import ChromaDBMemoryAgent  # noqa: E402
from talemate.client.koboldcpp import KoboldCppClient  # noqa: E402
from talemate.context import ActiveScene  # noqa: E402
from talemate.load import load_scene  # noqa: E402
from talemate.scene_message import CharacterMessage, NarratorMessage  # noqa: E402
from talemate.tale_mate import Scene  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.store import Source, World  # noqa: E402
from talemate.worldplay.characters import character_from_world  # noqa: E402
from talemate.worldplay.context import world_context_block  # noqa: E402
from talemate.worldplay.persistence import (  # noqa: E402
    close_world_scene,
    world_target,
)
from talemate.worldplay.setup import plan_scene, start_scene  # noqa: E402

from conftest import MockMemoryAgent, MockScene, bootstrap_scene  # noqa: E402

START = WorldDate.of(499)

SPECIES_FACTS = [
    ("physical", "Owl-folk have broad feathered wings in place of arms."),
    (
        "physical",
        "Owl-folk use the talons of their feet as hands: to grip, carry, "
        "write and eat.",
    ),
    ("physical", "Owl-folk have large, forward-facing yellow eyes."),
    ("physical", "Owl-folk have a hooked beak and soft, silent feathers."),
    (
        "instinct",
        "Owl-folk are crepuscular: drowsy at midday, most alert at dusk and dawn.",
    ),
    (
        "instinct",
        "Owl-folk turn their whole head to look at something, rather than "
        "moving their eyes.",
    ),
    ("instinct", "Owl-folk go utterly still and silent when startled."),
]
RACE_FACTS = [
    ("variation", "Snowy owl-folk have white plumage flecked with black."),
    (
        "physical",
        "Snowy owl-folk are feathered down to their talons and shrug off cold.",
    ),
]
EIRA_FACTS = [
    ("appearance", "Eira's eyes are a deep, glossy black."),
    ("appearance", "A courier's satchel hangs across her chest."),
    ("background", "Carries letters between the river towns."),
    ("personality", "Dry-humoured and curious."),
    ("speech", "Speaks in short, clipped sentences."),
]

SETUP = {
    "player": "Ilse",
    "characters": [
        {
            "name": "Ilse",
            "facts": ["A young human traveller with a letter to send north."],
        },
        {"name": "Eira"},
        {
            "name": "Brannoc",
            "facts": [
                "Keeps the Hollow Oak inn.",
                "Old and broad, with a voice like a creaking branch.",
            ],
            "heritage": "Owl-folk",
        },
    ],
    "place": {
        "name": "The Hollow Oak",
        "facts": ["An inn built inside a vast hollow oak by the river."],
    },
    "goal": "Find a courier to carry Ilse's letter north before the snows.",
    "intro": "Dusk settles over the Hollow Oak as Ilse steps in out of the rain.",
}

# (kind, who, player line before it, direction or instruction)
TURNS: list[tuple[str, str, str | None, str | None]] = [
    (
        "narrator",
        "progress_story",
        None,
        "Ilse hands Eira the sealed letter and a pen to sign the courier's "
        "ledger. Describe how Eira takes them and signs.",
    ),
    (
        "conversation",
        "Eira",
        "Ilse: It's bitter up north. Would you put these riding gloves on "
        "before you go?",
        None,
    ),
    (
        "narrator",
        "narrate_character:Brannoc",
        None,
        "Brannoc brings two mugs of hot cider to the table.",
    ),
    (
        "conversation",
        "Brannoc",
        "Ilse: Thank you, Brannoc. Shall we shake hands on the room, then?",
        None,
    ),
    (
        "narrator",
        "progress_story",
        None,
        "Full night falls outside. Describe how the owl-folk in the inn "
        "respond as the dark deepens, and a door bangs in the wind.",
    ),
    (
        "conversation",
        "Eira",
        "Ilse: You both look wide awake. Don't you ever sleep at night?",
        None,
    ),
]

_SCAN = {
    "hands": r"\bhands?\b",
    "fingers": r"\bfingers?\b",
    "gloves": r"\bgloves?\b",
    "arms": r"\barms?\b",
    "palms": r"\bpalms?\b",
    "wings": r"\bwings?\b|\bwingtips?\b",
    "talons": r"\btalons?\b|\bclaws?\b",
    "head_turn": r"\bhead\b[^.]{0,40}\b(turn|swivel|rotat)|\b(turn|swivel|rotat)\w*\b[^.]{0,40}\bhead\b",
    "dusk_night": r"\bdusk\b|\bnight\b|\bdawn\b|\bawake\b|\balert\b",
    "yellow": r"\byellow\b",
}


def scan(text: str) -> dict[str, int]:
    lowered = text.lower()
    return {key: len(re.findall(pattern, lowered)) for key, pattern in _SCAN.items()}


class RecordingClient(KoboldCppClient):
    """Talemate's KoboldCpp client, recording every call's kind, prompt and
    reply into `calls`."""

    calls: list[dict[str, Any]]

    async def send_prompt(self, prompt, kind="conversation", *args, **kwargs):
        started = time.monotonic()
        response = await super().send_prompt(prompt, kind, *args, **kwargs)
        self.calls.append(
            {
                "kind": kind,
                "prompt": str(prompt),
                "response": response,
                "seconds": round(time.monotonic() - started, 1),
            }
        )
        self.on_call()
        return response

    def on_call(self) -> None:
        pass


def build_world(root: Path) -> tuple[World, dict[str, str]]:
    world = World.create("Probe", root=root)
    world.set_present(WorldDate.of(520))
    ids: dict[str, str] = {}
    with world.revision(Source.manual(note="probe")) as rev:
        owl = rev.create_thing(
            "species", {"name": "Owl-folk", "lifespan": 60, "adult_age": 16}
        )
        for category, text in SPECIES_FACTS:
            fact_id = rev.add_fact(owl, category, text)
            if "yellow eyes" in text:
                ids["yellow_eyes"] = fact_id
        snowy = rev.create_thing("race", {"name": "Snowy", "species": owl})
        for category, text in RACE_FACTS:
            rev.add_fact(snowy, category, text)
        eira = rev.create_thing(
            "character",
            {"name": "Eira", "born": WorldDate.of(470), "heritage": snowy},
        )
        for category, text in EIRA_FACTS:
            overrides = [ids["yellow_eyes"]] if "black" in text else []
            rev.add_fact(eira, category, text, overrides=overrides)
    ids.update(owl_folk=owl, snowy=snowy, eira=eira)
    return world, ids


async def _noop(self, *args, **kwargs):
    pass


def _quiet_loading(memory: bool) -> None:
    """What loading a world scene needs with no app around it: no recent
    scenes, no config save and, without `memory`, no memory database (as
    in the slice test)."""

    if not memory:
        MockMemoryAgent.set_db = _noop
        MockMemoryAgent._get_document = lambda self, id: {}
        Scene.commit_to_memory = _noop
    Config.set_dirty = _noop
    config_state.CONFIG.recent_scenes = RecentScenes(scenes=[])


async def _load(world: World, scene_id: str, client, memory: bool) -> Scene:
    """Load the scene with every agent on `client`. With `memory`, the
    memory agent is the app's ChromaDB one (its default local embeddings,
    a database in the working directory) and long-term memory stays on,
    as the app runs it; otherwise it's the tests' stub, with long-term
    memory off."""

    scene = MockScene()
    bootstrap_scene(scene)
    if memory:
        agent = ChromaDBMemoryAgent()
        agent.scene = scene
        instance.AGENTS["memory"] = agent
    for agent in instance.AGENTS.values():
        agent.client = client
        long_term_memory = getattr(agent, "actions", {}).get("use_long_term_memory")
        if long_term_memory is not None and not memory:
            long_term_memory.enabled = False
    scene = await load_scene(scene, world_target(str(world.path), scene_id))
    # set up by the game loop, which the probe doesn't run
    scene.active = True
    scene.rag_cache = {}
    return scene


def _actor(scene: Scene, name: str):
    return next(a for a in scene.actors if a.character.name == name)


async def play(scene: Scene, results: dict, save) -> None:
    narrator = instance.get_agent("narrator")
    conversation = instance.get_agent("conversation")
    with ActiveScene(scene):
        for kind, who, player_line, direction in TURNS:
            if player_line:
                await scene.push_history(
                    [CharacterMessage(player_line, source="player")]
                )
            if kind == "narrator":
                if who.startswith("narrate_character:"):
                    character = _actor(scene, who.split(":", 1)[1]).character
                    text = await narrator.narrate_character(
                        character, narrative_direction=direction
                    )
                else:
                    text = await narrator.progress_story(narrative_direction=direction)
                await scene.push_history([NarratorMessage(text, source="ai")])
                output = text
            else:
                messages = await conversation.converse(_actor(scene, who))
                await scene.push_history(messages)
                output = "\n".join(str(m) for m in messages)
            results["turns"].append(
                {
                    "kind": kind,
                    "who": who,
                    "player_line": player_line,
                    "direction": direction,
                    "output": output,
                    "scan": scan(output),
                }
            )
            save()


async def main(out: Path, memory: bool) -> None:
    _quiet_loading(memory)
    client = RecordingClient(name="KoboldCpp")
    client.calls = []
    await client.status()

    results: dict[str, Any] = {
        "model": client.model_name,
        "memory": "chromadb" if memory else "off",
        "prompt_template": client.prompt_template_example()[1],
        "calls": client.calls,
        "turns": [],
    }

    def save() -> None:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    client.on_call = save

    with tempfile.TemporaryDirectory() as root:
        # the memory agent's ChromaDB lands in the working directory
        os.chdir(root)
        world, ids = build_world(Path(root) / "worlds")
        setup = await plan_scene(
            world,
            "Ilse looks for a courier at the Hollow Oak",
            {"Eira": ids["eira"]},
            None,
            START,
            None,
            reply=SETUP,
        )
        # writes Eira's prose for 499 through the model, as the app does
        scene_id = await start_scene(world, setup, client)
        record = world.scenes().get(scene_id)
        assert record is not None

        eira = character_from_world(world, ids["eira"], START, is_player=False)
        brannoc = next(
            thing["data"]
            for thing in world.scenes().local_things(scene_id)
            if thing["data"].get("name") == "Brannoc"
        )
        results["sheets"] = {
            "Eira": {
                "description": eira.description,
                "base_attributes": eira.base_attributes,
                "dialogue_instructions": eira.dialogue_instructions,
            },
            "Brannoc": {
                "description": brannoc["description"],
                "base_attributes": brannoc["base_attributes"],
            },
        }
        results["world_block"] = world_context_block(world, record, START)
        save()

        scene = await _load(world, scene_id, client, memory)
        try:
            await play(scene, results, save)
        finally:
            close_world_scene(scene)
            world.close()
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="the tests' memory stub, long-term memory off",
    )
    args = parser.parse_args()
    asyncio.run(main(args.out.resolve(), not args.no_memory))
