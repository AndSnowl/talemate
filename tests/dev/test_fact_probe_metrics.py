"""Unit tests for the fact-probe metrics (scripts/dev/fact_probe_metrics.py).

Pure functions only: no backend, no model, no network. These test the
summary numbers and the rendered report from a hand-built ``results`` dict,
shaped the way a probe script (Task 2) would produce it.
"""

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "fact_probe_metrics", _REPO_ROOT / "scripts" / "dev" / "fact_probe_metrics.py"
)
metrics = importlib.util.module_from_spec(_spec)
sys.modules["fact_probe_metrics"] = metrics
_spec.loader.exec_module(metrics)


def _fact(text: str, category: str = "appearance") -> dict:
    return {"category": category, "text": text}


def _results(samples: list[dict], errors: list[dict] | None = None) -> dict:
    return {
        "model": "test-model",
        "started": "2026-10-18T22:00:00",
        "finished": "2026-10-18T22:05:00",
        "samples": samples,
        "errors": errors or [],
    }


def test_summarise_counts_per_round():
    sample_a = {
        "name": "A",
        "rounds": [
            {
                "facts": [_fact("f1"), _fact("f2")],
                "prose": "f1 and f2.",
                "invented": ["x"],
                "dropped": [],
            },
            {
                "facts": [_fact("f1")],
                "prose": "f1.",
                "invented": [],
                "dropped": ["f2"],
            },
        ],
    }
    sample_b = {
        "name": "B",
        "rounds": [
            {
                "facts": [_fact("g1")],
                "prose": "g1.",
                "invented": ["y", "z"],
                "dropped": [],
            },
            {
                "facts": [_fact("g1"), _fact("g2")],
                "prose": "g1 and g2.",
                "invented": [],
                "dropped": [],
            },
        ],
    }

    summary = metrics.summarise(_results([sample_a, sample_b]))

    assert summary["samples"]["A"]["facts_per_round"] == [2, 1]
    assert summary["samples"]["A"]["invented_per_round"] == [1, 0]
    assert summary["samples"]["A"]["dropped_per_round"] == [0, 1]

    assert summary["samples"]["B"]["facts_per_round"] == [1, 2]
    assert summary["samples"]["B"]["invented_per_round"] == [2, 0]
    assert summary["samples"]["B"]["dropped_per_round"] == [0, 0]

    assert summary["totals"]["facts_per_round"] == [3, 3]
    assert summary["totals"]["invented_per_round"] == [3, 0]
    assert summary["totals"]["dropped_per_round"] == [0, 1]


def test_drift_ignores_case_and_whitespace():
    matching = _results(
        [
            {
                "name": "A",
                "rounds": [
                    {
                        "facts": [_fact("Has a  heron tattoo")],
                        "prose": "...",
                        "invented": [],
                        "dropped": [],
                    },
                    {
                        "facts": [_fact("has a heron tattoo")],
                        "prose": "...",
                        "invented": [],
                        "dropped": [],
                    },
                ],
            }
        ]
    )
    summary = metrics.summarise(matching)
    assert summary["samples"]["A"]["drift"] == 0.0

    missing = _results(
        [
            {
                "name": "A",
                "rounds": [
                    {
                        "facts": [_fact("Has a  heron tattoo")],
                        "prose": "...",
                        "invented": [],
                        "dropped": [],
                    },
                    {
                        "facts": [],
                        "prose": "...",
                        "invented": [],
                        "dropped": ["Has a  heron tattoo"],
                    },
                ],
            }
        ]
    )
    summary = metrics.summarise(missing)
    assert summary["samples"]["A"]["drift"] == 1.0


def test_render_lists_invented_claims_verbatim():
    results = _results(
        [
            {
                "name": "A",
                "rounds": [
                    {
                        "facts": [_fact("f1")],
                        "prose": "f1 and a dragon.",
                        "invented": ["the character has a dragon"],
                        "dropped": [],
                    }
                ],
            }
        ]
    )
    summary = metrics.summarise(results)
    text = metrics.render_markdown(results, summary)

    assert "test-model" in text
    assert "the character has a dragon" in text
    assert "Errors" not in text

    results_with_errors = _results(
        [
            {
                "name": "A",
                "rounds": [
                    {
                        "facts": [_fact("f1")],
                        "prose": "f1.",
                        "invented": [],
                        "dropped": [],
                    }
                ],
            }
        ],
        errors=[{"sample": "A", "round": 0, "step": "facts", "error": "boom"}],
    )
    summary_with_errors = metrics.summarise(results_with_errors)
    text_with_errors = metrics.render_markdown(results_with_errors, summary_with_errors)
    assert "Errors" in text_with_errors
    assert "boom" in text_with_errors
