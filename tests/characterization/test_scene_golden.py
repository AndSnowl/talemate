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
  - any key whose *name* denotes time (contains "time"/"timestamp", or is
    "ts"/ends "_ts"/"_at") *and* whose value is a large-enough int/float to
    be a wall-clock Unix timestamp. Neither condition alone is enough: a
    large plain count or id number under an unrelated key is real content
    and must survive (no such timestamp key appears in this script's
    recording today, but the rule is kept general per the brief rather
    than narrowed to today's shape).
No keys beyond the brief's list are dropped.
It also replaces id-shaped runs with ``<id>``, redacting the whole match:
  - a full dashed uuid (``8-4-4-4-12`` hex digits);
  - the 10-character scene/memory id shape, ``str(uuid.uuid4())[:10]``
    (8 hex digits, a dash, 1 hex digit — see tale_mate.py:157,168,170);
  - a 32-character undashed hex world id.
These three fixed shapes are redacted whatever digits they happen to
contain — a decimal-looking uuid is still a uuid. Any other 8+ character
hex run is redacted only if it actually contains a hex letter (a-f); a
pure-digit run of 8+ digits (a year, a count) is real content, not an id,
and is left alone. Dict keys are sorted everywhere.
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
REPO_ROOT = BASE_DIR.parent
GOLDEN_PATH = BASE_DIR / "data" / "characterization" / "scene_golden.json"
FIXTURE_SCENES_DIR = BASE_DIR / "data" / "scenes"
# Gitignored (see .gitignore's ``.test-artifacts/``). Written only on a
# mismatch, so a `diff` against the committed baseline shows exactly what
# changed instead of pytest's dict diff of the whole structure.
ACTUAL_RECORDING_PATH = REPO_ROOT / ".test-artifacts" / "scene_golden.actual.json"

# Three fixed id shapes, tried first (longest/most specific first so a
# short shape can't win a partial match inside a longer one), plus a
# catch-all free-length hex run for anything else. Named groups let the
# substitution callback below tell a fixed shape (always redacted) from
# the free-length fallback (redacted only if it contains a hex letter —
# see _looks_like_id).
_ID_RE = re.compile(
    r"\b(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b"
    r"|\b(?P<short_uuid>[0-9a-fA-F]{8}-[0-9a-fA-F])\b"
    r"|\b(?P<world_id>[0-9a-fA-F]{32})\b"
    r"|\b(?P<hex_run>[0-9a-fA-F]{8,})\b"
)
_DROP_KEYS = {"id", "memory_id", "memory_session_id", "saved_memory_session_id"}

# Unix timestamps in this range cover roughly year 2001 to year 5138 in
# seconds, or 1970 to 1973 in milliseconds — wide enough to catch a
# wall-clock value without also catching small counters (message ids,
# revision numbers) that this scene's data actually contains.
_TIMESTAMP_MIN = 1_000_000_000
_TIMESTAMP_MAX = 99_999_999_999


def _looks_like_id(hex_run: str) -> bool:
    """A free-length hex run (the ``hex_run`` fallback group, not one of the
    three fixed id shapes) is an id, not a plain decimal count, only if it
    actually uses a hex letter. A pure-digit run of 8+ characters — a year
    range, a count, a duration in milliseconds — is real narration/data
    content and must survive normalisation unchanged, not get redacted to
    ``<id>``.
    """
    return any(c in "abcdefABCDEF" for c in hex_run)


def _redact_id(match: re.Match) -> str:
    """Redact a fixed id shape (uuid, the 10-char scene/memory id shape, or
    a 32-char world id) unconditionally. The free-length ``hex_run``
    fallback is redacted only if ``_looks_like_id`` says it's one."""

    if match.group("hex_run") is not None:
        return "<id>" if _looks_like_id(match.group()) else match.group()
    return "<id>"


def _looks_like_timestamp(key: str, value) -> bool:
    """A wall-clock Unix timestamp: a large-enough int/float *and* a key
    name that actually denotes time. The magnitude check alone would also
    drop any plain large count or id number under an unrelated key, which
    is real content, not noise — so both have to hold.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    if not (_TIMESTAMP_MIN <= value <= _TIMESTAMP_MAX):
        return False
    lowered = key.lower()
    return (
        "time" in lowered
        or "timestamp" in lowered
        or lowered == "ts"
        or lowered.endswith("_ts")
        or lowered.endswith("_at")
    )


def normalise(obj):
    """Strip non-deterministic noise from a recorded scene/prompt structure.

    See the module docstring for exactly which keys are dropped and why.
    """
    if isinstance(obj, dict):
        return {
            key: normalise(value)
            for key, value in sorted(obj.items())
            if key not in _DROP_KEYS and not _looks_like_timestamp(key, value)
        }
    if isinstance(obj, list):
        return [normalise(item) for item in obj]
    if isinstance(obj, str):
        return _ID_RE.sub(_redact_id, obj)
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

    scene.description = "Two rivermen wait out a storm in a flooded tavern."
    scene.world_state.location = "The Drowned Stag tavern"

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

    alice = Character(
        name="Alice",
        description="A riverboat pilot waiting out the storm, calloused hands wrapped around a tankard.",
        is_player=False,
        base_attributes={"occupation": "riverboat pilot", "age": "34"},
        dialogue_instructions="Speaks in short, practical sentences; rarely jokes.",
    )
    bob = Character(
        name="Bob",
        description="A traveling merchant stranded by the flood, counting his coin by candlelight.",
        is_player=True,
    )

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


def _fail_on_golden_mismatch(
    recording: dict, expected: dict, golden_path: Path, actual_path: Path
) -> None:
    """Compare `recording` against the committed `expected` baseline. On a
    mismatch, write `recording` to `actual_path` and fail with a message
    that names it and suggests a `diff` against `golden_path`, instead of
    only pytest's dict diff of the whole structure. A no-op when they
    match (`actual_path` isn't written, so a stale copy from an earlier
    failing run doesn't linger as a false lead)."""

    if recording == expected:
        return
    actual_path.parent.mkdir(parents=True, exist_ok=True)
    with open(actual_path, "w") as f:
        json.dump(recording, f, indent=2, sort_keys=True)
        f.write("\n")
    pytest.fail(
        f"Golden scene recording does not match {golden_path}.\n"
        f"The actual recording was written to {actual_path} — diff it "
        f"against the baseline for exactly what changed:\n"
        f"  diff {golden_path} {actual_path}\n"
        "If this change is an intentional part of the phase-2 rework, "
        "regenerate the baseline with --update-baselines and review the diff."
    )


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

    _fail_on_golden_mismatch(recording, expected, GOLDEN_PATH, ACTUAL_RECORDING_PATH)


@pytest.mark.asyncio
async def test_golden_scene_is_deterministic(tmp_path):
    """Running the script twice, in two fresh scenes, gives identical
    normalised recordings — no timestamps, uuids or dict-order noise.

    Comparing the two runs against each other is this test's whole job;
    comparing either of them against the committed recording is
    ``test_golden_scene_matches_recording``'s.
    """
    first = normalise(await _play_golden_scene(tmp_path / "first"))
    second = normalise(await _play_golden_scene(tmp_path / "second"))
    assert first == second


def test_fail_on_golden_mismatch_writes_actual_and_names_it(tmp_path):
    golden_path = tmp_path / "golden.json"
    actual_path = tmp_path / "actual.json"

    with pytest.raises(pytest.fail.Exception) as exc_info:
        _fail_on_golden_mismatch({"a": 1}, {"a": 2}, golden_path, actual_path)

    assert json.loads(actual_path.read_text()) == {"a": 1}
    message = str(exc_info.value)
    assert str(golden_path) in message
    assert str(actual_path) in message
    assert "diff" in message


def test_fail_on_golden_mismatch_is_noop_when_equal(tmp_path):
    actual_path = tmp_path / "actual.json"

    _fail_on_golden_mismatch({"a": 1}, {"a": 1}, tmp_path / "golden.json", actual_path)

    assert not actual_path.exists()


# ---------------------------------------------------------------------------
# normalise() unit tests
# ---------------------------------------------------------------------------


def test_normalise_keeps_decimal_runs_but_redacts_real_ids():
    """A pure-digit run of 8+ digits (a year, a count) is real content and
    must survive; a real id — 10 hex characters, the shape
    ``str(uuid.uuid4())[:10]`` produces at tale_mate.py:157,168,170 — is
    redacted. A fixed id (rather than a freshly generated uuid) keeps this
    test from being the rare uuid whose first 10 characters are all
    digits.
    """
    real_id = "a1b2c3d4e5"
    data = {"year_span": "12345678", "scene_id": f"scene-{real_id}-done"}

    result = normalise(data)

    assert result["year_span"] == "12345678"
    assert real_id not in result["scene_id"]
    assert result["scene_id"] == "scene-<id>-done"


def test_normalise_redacts_fixed_id_shapes_whole():
    """Each of the three fixed id shapes is redacted whole, regardless of
    whether it happens to contain a hex letter — unlike the free-length
    ``hex_run`` fallback, which ``test_normalise_keeps_decimal_runs_but_redacts_real_ids``
    covers. "12345678" (8 plain digits, too short and undashed for any
    fixed shape) still survives.
    """
    data = {
        "full_uuid": "scene-1b4e28ba-9d2e-4331-9f5a-abc123456789-done",
        "short_uuid": "scene-1b4e28ba-2-done",
        "world_id": "scene-" + "0123456789abcdef" * 2 + "-done",
        "decimal_run": "12345678",
    }

    result = normalise(data)

    assert result["full_uuid"] == "scene-<id>-done"
    assert result["short_uuid"] == "scene-<id>-done"
    assert result["world_id"] == "scene-<id>-done"
    assert result["decimal_run"] == "12345678"


def test_normalise_scopes_timestamp_drop_to_time_like_keys():
    """The magnitude check alone isn't enough to call something a
    timestamp: a large int under an unrelated key is content and is kept;
    the same magnitude under a key that actually denotes time is dropped."""
    large_int = 1_700_000_000
    data = {"revision_count": large_int, "created_at": large_int}

    result = normalise(data)

    assert result["revision_count"] == large_int
    assert "created_at" not in result
