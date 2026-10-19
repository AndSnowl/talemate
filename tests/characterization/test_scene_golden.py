"""
Golden scene test, ahead of the phase-2 rewrite.

Plays a short, scripted scene through the real agents and the mock LLM
client (``tests/conftest.py``'s ``MockClient``/``MockScene``/
``bootstrap_scene``/``client_responses``), and records both what the AI is
sent (``MockClient.prompt_history``) and what the scene saves
(``scene.serialize``) into a single committed recording,
``tests/data/characterization/scene_golden.json``.

Phase 2 is expected to change scene/context code on purpose. When it does,
the recording is regenerated with ``--update-baselines`` and the diff is
reviewed in the same commit as the code change — that diff is the point of
this test.

The script:
  1. A character's dialogue turn, from the conversation agent
     (``ConversationAgent.converse``).
  2. A narrator "progress story" turn (``NarratorAgent.progress_story``).
  3. A time passage of ``P1D`` (``WorldStateAgent.advance_time``), with a
     ``narrative`` set so the narrator's time-passage auto-narration fires
     too (see the substitution note below) — this is the recording's 4th
     prompt.
  4. A second dialogue turn after the time passage, so the elapsed time and
     the richer history show up in its prompt.

Substitution (websocket server step replaced by an agent-level call):
Step 3's auto-narration is normally wired up when a scene loads over the
websocket (``websocket_server.py`` calls ``agent.connect(scene)`` for every
agent). There's no websocket server here, so the nearest agent-level call,
``narrator.connect(scene)``, is used instead — just for narrator, since
that's the only agent whose listener this script needs (its
``on_time_passage`` handler, connected to the ``agent.world_state.time``
signal that ``advance_time`` sends).

Normalisation (``normalise``) drops, from any dict at any depth:
  - the brief's keys: ``id``, ``memory_id``, ``memory_session_id``,
    ``saved_memory_session_id``.
  - any key whose value looks like a wall-clock Unix timestamp (no such
    key appears in this script's recording today, but the rule is kept
    general per the brief rather than narrowed to today's shape).
No keys beyond the brief's list are dropped.
It also replaces 8+ character hex runs (scene/message/memory ids,
asset hashes) with ``<id>``, and sorts dict keys everywhere.
"""

import json
import re
import shutil
from pathlib import Path

import pytest

import talemate.emit.async_signals
import talemate.instance as instance
from talemate import save
from talemate.character import Character
from talemate.context import ActiveScene
from talemate.scene_message import NarratorMessage
from talemate.tale_mate import Actor, Player

from conftest import MockClientContext, MockScene, bootstrap_scene

BASE_DIR = Path(__file__).resolve().parent.parent
GOLDEN_PATH = BASE_DIR / "data" / "characterization" / "scene_golden.json"
FIXTURE_SCENES_DIR = BASE_DIR / "data" / "scenes"

_HEX_ID_RE = re.compile(r"\b[0-9a-fA-F]{8,}\b")
_DROP_KEYS = {"id", "memory_id", "memory_session_id", "saved_memory_session_id"}

# Unix timestamps in this range cover roughly year 2001 to year 5138 in
# seconds, or 1970 to 1973 in milliseconds — wide enough to catch a
# wall-clock value without also catching small counters (message ids,
# revision numbers) that this scene's data actually contains.
_TIMESTAMP_MIN = 1_000_000_000
_TIMESTAMP_MAX = 99_999_999_999


def _looks_like_timestamp(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and _TIMESTAMP_MIN <= value <= _TIMESTAMP_MAX
    )


def normalise(obj):
    """Strip non-deterministic noise from a recorded scene/prompt structure.

    See the module docstring for exactly which keys are dropped and why.
    """
    if isinstance(obj, dict):
        return {
            key: normalise(value)
            for key, value in sorted(obj.items())
            if key not in _DROP_KEYS and not _looks_like_timestamp(value)
        }
    if isinstance(obj, list):
        return [normalise(item) for item in obj]
    if isinstance(obj, str):
        return _HEX_ID_RE.sub("<id>", obj)
    return obj


def _setup_lab_scene(scene: MockScene, tmp_path: Path) -> None:
    """Point ``scene`` at a private copy of the laboratory fixture scene,
    the way ``tests/test_graphs.py``'s ``mock_scene_with_assets`` fixture
    does: copy ``tests/data/scenes`` so the asset library write doesn't hit
    the git-tracked original, then wire ``scenes_dir``/``project_name`` and
    rebuild ``library.json`` from the fixture's asset entries.
    """
    test_scene_path = FIXTURE_SCENES_DIR / "talemate-laboratory" / "talemate-lab.json"
    with open(test_scene_path, "r") as f:
        test_scene_data = json.load(f)

    test_scenes_dir = tmp_path / "scenes"
    shutil.copytree(FIXTURE_SCENES_DIR, test_scenes_dir)
    scene.scenes_dir = lambda: str(test_scenes_dir)
    scene.project_name = "talemate-laboratory"

    assets_dict = test_scene_data["assets"]["assets"]
    assets_dir = test_scenes_dir / "talemate-laboratory" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    with open(assets_dir / "library.json", "w") as f:
        json.dump({"assets": assets_dict}, f, indent=2)


async def _play_golden_scene(tmp_path: Path) -> dict:
    """Run the scripted scene end to end and return the raw (unnormalised)
    recording: ``{"prompts": [...], "scene": scene.serialize}``.
    """
    scene = MockScene()
    bootstrap_scene(scene)
    _setup_lab_scene(scene, tmp_path)

    conversation = instance.get_agent("conversation")
    narrator = instance.get_agent("narrator")
    world_state = instance.get_agent("world_state")

    # See the module docstring's "Substitution" note. ``connect`` attaches a
    # process-wide signal receiver bound to this narrator instance, so it's
    # undone in the ``finally`` below — otherwise a second script run in the
    # same test (``test_golden_scene_is_deterministic``) would leave two
    # receivers live and double up the time-passage narration.
    narrator.connect(scene)
    time_passage_signal = talemate.emit.async_signals.get("agent.world_state.time")

    # MockMemoryAgent only stubs persistence (add_many/delete); its search
    # path is the real MemoryAgent's, which has no backend here and raises
    # NotImplementedError. Long-term memory retrieval isn't part of this
    # script, so it's switched off on every agent that has it, the same way
    # any other optional action would be toggled for a test.
    for agent in instance.AGENTS.values():
        long_term_memory = getattr(agent, "actions", {}).get("use_long_term_memory")
        if long_term_memory is not None:
            long_term_memory.enabled = False

    alice = Character(name="Alice", description="A lab assistant.", is_player=False)
    bob = Character(name="Bob", description="A visiting researcher.", is_player=True)

    alice_actor = Actor(character=alice, agent=conversation)
    alice_actor.scene = scene
    scene.actors.append(alice_actor)
    scene.active_characters.append(alice.name)
    scene.character_data[alice.name] = alice

    bob_actor = Player(character=bob, agent=None)
    bob_actor.scene = scene
    scene.actors.append(bob_actor)
    scene.active_characters.append(bob.name)
    scene.character_data[bob.name] = bob

    prompts = []

    try:
        with ActiveScene(scene):
            async with MockClientContext() as responses:
                # Step 1: a character's dialogue turn, from the conversation agent.
                responses.append("Good morning. The readings look stable today.")
                messages = await conversation.converse(alice_actor)
                await scene.push_history(messages)
                prompts.append(
                    ("character_dialogue", scene.mock_client.prompt_history[-1])
                )

                # Step 2: a narrator "progress story" turn.
                responses.append(
                    "A faint hum rises from the containment field as the data syncs."
                )
                narration = await narrator.progress_story()
                await scene.push_history(
                    NarratorMessage(narration, source="progress_story")
                )
                prompts.append(("progress_story", scene.mock_client.prompt_history[-1]))

                # Step 3: a time passage of P1D. ``advance_time`` pushes the
                # TimePassageMessage itself; passing ``narrative`` fires
                # narrator's time-passage auto-narration (wired by
                # ``narrator.connect(scene)`` above), which pushes its own
                # NarratorMessage and is this recording's 4th prompt.
                responses.append(
                    "A full day passes in the quiet hum of the laboratory."
                )
                await world_state.advance_time("P1D", narrative="A day passes quietly.")
                prompts.append(("time_passage", scene.mock_client.prompt_history[-1]))

                # Step 4: a second dialogue turn after the time passage, so the
                # elapsed time and the new history show up in its prompt.
                responses.append("It's been a long day. Let's review the results.")
                messages = await conversation.converse(alice_actor)
                await scene.push_history(messages)
                prompts.append(
                    (
                        "character_dialogue_after_time_passage",
                        scene.mock_client.prompt_history[-1],
                    )
                )
    finally:
        time_passage_signal.disconnect(narrator.on_time_passage)
        talemate.emit.async_signals.get("game_loop_start").disconnect(
            narrator.on_game_loop_start
        )

    recorded_prompts = [
        {"step": step, "kind": entry["kind"], "prompt": str(entry["prompt"])}
        for step, entry in prompts
    ]

    scene_data = json.loads(save.scene_data_dumps(scene.serialize))

    return {"prompts": recorded_prompts, "scene": scene_data}


@pytest.mark.asyncio
async def test_golden_scene_matches_recording(tmp_path, update_baselines):
    recording = normalise(await _play_golden_scene(tmp_path))

    if update_baselines:
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GOLDEN_PATH, "w") as f:
            json.dump(recording, f, indent=2, sort_keys=True)
            f.write("\n")
        return

    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(
            f"Golden recording not found: {GOLDEN_PATH}\n"
            "Run with --update-baselines to create it."
        )

    with open(GOLDEN_PATH, "r") as f:
        expected = json.load(f)

    assert recording == expected, (
        f"Golden scene recording does not match {GOLDEN_PATH}.\n"
        "If this change is an intentional part of the phase-2 rework, "
        "regenerate it with --update-baselines and review the diff."
    )


@pytest.mark.asyncio
async def test_golden_scene_is_deterministic(tmp_path):
    """Running the script twice, in two fresh scenes, gives identical
    normalised recordings — no timestamps, uuids or dict-order noise."""
    first = normalise(await _play_golden_scene(tmp_path / "first"))
    second = normalise(await _play_golden_scene(tmp_path / "second"))
    assert first == second
