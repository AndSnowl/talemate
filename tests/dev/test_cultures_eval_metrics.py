"""Unit tests for the cultures evaluation metrics (scripts/dev/cultures_eval_metrics.py).

Pure functions only: no backend, no model, no network. The languages come
from the AI fixture cultures in tests/ai/data/.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from talemate.cultures.generator import fits
from talemate.cultures.models import Language

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "cultures_eval_metrics", _REPO_ROOT / "scripts" / "dev" / "cultures_eval_metrics.py"
)
metrics = importlib.util.module_from_spec(_spec)
sys.modules["cultures_eval_metrics"] = metrics
_spec.loader.exec_module(metrics)

DATA = _REPO_ROOT / "tests" / "ai" / "data"


def _language_dict(culture_id: str) -> dict:
    data = json.loads((DATA / f"{culture_id}.culture.json").read_text())
    return data["culture"]["language"]


@pytest.fixture(scope="module")
def taelrik() -> Language:
    return Language.model_validate(_language_dict("taelrik"))


@pytest.fixture(scope="module")
def elsiri() -> Language:
    return Language.model_validate(_language_dict("elsiri"))


def test_culture_distance():
    assert metrics.culture_distance(
        {"taelrik": 9, "elsiri": 1}, {"elsiri": 90, "taelrik": 10}
    ) == pytest.approx(0.8)
    assert metrics.culture_distance(
        {"taelrik": 6, "elsiri": 4}, {"taelrik": 60, "elsiri": 40}
    ) == pytest.approx(0.0)
    # a culture the place doesn't have counts fully against it
    assert metrics.culture_distance({"elsiri": 2}, {"taelrik": 100}) == pytest.approx(
        1.0
    )


def test_narration_name_use(taelrik):
    result = metrics.narration_name_use(
        prompt="The scene is the Quillister inn. If you need a new name, use one of these: Kethvar.",
        response="Kethvar the smith waved to Zorblax.",
        spares=["Kethvar"],
        language=taelrik,
    )
    assert result["used_spare"] is True
    assert result["new_names"] == ["Zorblax"]
    assert result["invented_fit"] + result["invented_misfit"] == 1


def test_narration_name_use_ignores_known_and_common_words(taelrik):
    result = metrics.narration_name_use(
        prompt="Hadrik works the docks of Veldhaer.",
        response=(
            "Rain fell. Then Hadrik cursed, and the River swallowed the crate "
            "in Veldhaer. That's just Tuesday."
        ),
        spares=["Kethvar"],
        language=taelrik,
    )
    assert result["used_spare"] is False
    # Hadrik and Veldhaer are in the prompt; "River" is a common word;
    # "Rain" and "Then" start a sentence; "Tuesday" is a weekday
    assert result["new_names"] == []


def test_narration_name_use_counts_fit_and_misfit(taelrik):
    fitting = next(
        name for name in ("Ratrek", "Kodrin", "Bormar") if fits(taelrik, name)
    )
    assert not fits(taelrik, "Zorblax")
    result = metrics.narration_name_use(
        prompt="",
        response=f"A man called {fitting} greeted Zorblax and then {fitting} left.",
        spares=[],
        language=[taelrik],
    )
    assert result["new_names"] == [fitting, "Zorblax"]
    assert result["invented_fit"] == 1
    assert result["invented_misfit"] == 1


def test_verbatim_phrases_normalises_quotes():
    assert metrics.verbatim_phrases("He swore, “Rhok tal’dun!”", ["Rhok tal'dun!"]) == 1
    assert (
        metrics.verbatim_phrases(
            "rhok TAL'DUN, he said. Dhaer tal'skev.",
            ["Rhok tal'dun!", "Dhaer tal'skev.", "Vel'dhaer ossa tae."],
        )
        == 2
    )
    assert metrics.verbatim_phrases("Nothing here.", ["Rhok tal'dun!"]) == 0


def _entry(text, language, by="ai", generator_id="given_male"):
    return {
        "text": text,
        "language": language,
        "kind": "person",
        "origin": {"by": by, "generator_id": generator_id, "candidates": []},
        "doesnt_fit": False,
    }


def test_share_from_generator_and_fitting(taelrik, elsiri):
    fitting = next(
        name for name in ("Ratrek", "Kodrin", "Bormar") if fits(taelrik, name)
    )
    npcs = [
        # right culture's generator, fits
        {
            "name": fitting,
            "culture_id": "taelrik",
            "language": taelrik,
            "entry": _entry(fitting, "taelrik"),
        },
        # a free (not generator) name that doesn't fit
        {
            "name": "Zorblax",
            "culture_id": "taelrik",
            "language": taelrik,
            "entry": _entry("Zorblax", "taelrik", by="ai_free", generator_id=None),
        },
        # generator from the other culture (language mismatch)
        {
            "name": fitting,
            "culture_id": "elsiri",
            "language": elsiri,
            "entry": _entry(fitting, "taelrik"),
        },
        # no glossary entry at all; language given as a plain dict
        {
            "name": fitting,
            "culture_id": "taelrik",
            "language": _language_dict("taelrik"),
            "entry": None,
        },
    ]
    assert metrics.share_from_generator(npcs) == pytest.approx(0.25)
    # fitting: 1st and 4th fit taelrik; Zorblax doesn't; the taelrik
    # name doesn't fit elsiri
    assert not fits(elsiri, fitting)
    assert metrics.share_fitting(npcs) == pytest.approx(0.5)
    assert metrics.share_from_generator([]) == 0.0
    assert metrics.share_fitting([]) == 0.0


def _results():
    """A tiny results dict, shaped like eval_cultures_ai.py writes it."""
    return {
        "model": "test-model",
        "started": "2026-10-18T22:00:00",
        "cultures": {
            "taelrik": {"name": "Taelrik", "language": _language_dict("taelrik")},
            "elsiri": {"name": "Elsiri", "language": _language_dict("elsiri")},
        },
        "trait_phrases": {
            "curse": ["Rhok tal'dun!", "Dhaer tal'skev."],
            "saying": ["Vel'dhaer ossa tae."],
        },
        "scenarios": {
            "taelrik_town": {
                "expected": {"taelrik": 100},
                "runs": [
                    {
                        "run": 1,
                        "npcs": [
                            {
                                "role": "the ferryman",
                                "name": "Ratrek",
                                "culture_id": "taelrik",
                                "event": {
                                    "name": "Ratrek",
                                    "culture_id": "taelrik",
                                    "generator_id": "given_male",
                                    "candidates": ["Ratrek", "Kodrin"],
                                    "by_model": True,
                                    "ms": 13500,
                                },
                                "wall_s": 61.0,
                                "culture_prompt_s": 17.0,
                                "pick_prompt_s": 13.5,
                                "entry": _entry("Ratrek", "taelrik"),
                            }
                        ],
                        "narrations": [
                            {
                                "index": 0,
                                "action": "progress",
                                "context": {
                                    "tokens": 200,
                                    "spares": [{"text": "Kethvar"}],
                                },
                                "prompt_tokens": 4000,
                                "prompt": "Hadrik is here.",
                                "response": "Hadrik roared “Rhok tal’dun!” at Kethvar.",
                            }
                        ],
                        "snapshots": [
                            {
                                "data": {
                                    "new_names": [
                                        {
                                            "text": "Brannoch",
                                            "kind": "person",
                                            "culture_id": "taelrik",
                                            "doesnt_fit": False,
                                            "origin": "ai_free",
                                        },
                                        {
                                            "text": "Ratrek",
                                            "kind": "person",
                                            "culture_id": "elsiri",
                                            "doesnt_fit": False,
                                            "origin": "ai_free",
                                        },
                                    ],
                                    "ms": 9000,
                                },
                                "wall_s": 40.0,
                            }
                        ],
                        "characters": [
                            {"name": "Ratrek", "culture": {"culture_id": "taelrik"}}
                        ],
                        "glossary_new": [_entry("Ratrek", "taelrik")],
                    }
                ],
            }
        },
        "errors": [],
    }


def test_summarise_numbers():
    summary = metrics.summarise(_results())
    scenario = summary["scenarios"]["taelrik_town"]
    assert scenario["naming"]["share_from_generator"] == pytest.approx(1.0)
    assert scenario["culture_guess"]["observed"] == {"taelrik": 1}
    assert scenario["culture_guess"]["distance"] == pytest.approx(0.0)
    assert scenario["narration"]["used_spare"] == 1
    assert scenario["verbatim"]["with_curse"] == 1
    assert scenario["verbatim"]["hadrik_present"] == 1
    assert scenario["section"]["mean_ratio"] == pytest.approx(0.05)
    assert scenario["latency"]["mean_hook_ms"] == pytest.approx(13500)
    snap = scenario["snapshots"]
    assert snap["mean_new_names"] == pytest.approx(2)
    # Brannoch: not a character, fits -> correct; Ratrek: language elsiri
    # but the character is taelrik -> wrong
    assert snap["attributed_share"] == pytest.approx(0.5)
    assert snap["recall"]["Brannoch"] == pytest.approx(1.0)
    assert snap["recall"]["Grey Gull"] == pytest.approx(0.0)
    assert "overall" in summary


def test_render_markdown_has_all_metric_headings():
    text = metrics.render_markdown(metrics.summarise(_results()), "test-model")
    for heading in (
        "Name generator accuracy",
        "Names that fit their culture",
        "Culture guesses vs the place mix",
        "Narrator spare-name use",
        "Curses and sayings used verbatim",
        "Culture section size",
        "Latency added per creation",
        "Snapshot glossary yield",
    ):
        assert f"## {heading}" in text, heading
    assert "test-model" in text
    assert "Ratrek" in text  # the samples are in the report


def test_summarise_empty_results_renders():
    results = {
        "model": "m",
        "started": "",
        "cultures": {},
        "scenarios": {},
        "errors": [{"scenario": "x", "run": 1, "step": "seed", "error": "boom"}],
    }
    text = metrics.render_markdown(metrics.summarise(results), "m")
    assert "boom" in text


def test_render_only_rewrites_reports_from_raw_results(tmp_path):
    """``eval_cultures_ai.py --render-only DIR`` re-renders, starting nothing."""
    stale = {**_results(), "summary": {"stale": True}}
    (tmp_path / "report.json").write_text(json.dumps(stale))
    env = {k: v for k, v in os.environ.items() if k != "TALEMATE_AI_TESTS"}
    done = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "dev" / "eval_cultures_ai.py"),
            "--render-only",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    report = json.loads((tmp_path / "report.json").read_text())
    assert "stale" not in report["summary"]
    assert report["summary"]["scenarios"]["taelrik_town"]["naming"]["npcs"] == 1
    assert report["scenarios"] == stale["scenarios"]  # raw results kept
    markdown = (tmp_path / "report.md").read_text()
    assert "## Latency added per creation" in markdown
    assert "(n=1)" in markdown


def test_narration_name_use_ignores_contractions_and_i(taelrik):
    result = metrics.narration_name_use(
        prompt="",
        response=(
            "Hadrik said, and then I'll go, and I'm sure, and so I said that "
            "We're done, They've left, I'd stay, Don't move, That's it, and "
            "then Zorblax's boat sank."
        ),
        spares=[],
        language=taelrik,
    )
    # only the invented name counts, through its possessive
    assert result["new_names"] == ["Zorblax"]
