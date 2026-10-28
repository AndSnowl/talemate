"""Unit tests for the language probes' scoring
(scripts/dev/language_probe_metrics.py). No model, no network."""

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "language_probe_metrics",
    _REPO_ROOT / "scripts" / "dev" / "language_probe_metrics.py",
)
metrics = importlib.util.module_from_spec(_spec)
sys.modules["language_probe_metrics"] = metrics
_spec.loader.exec_module(metrics)

real_word_hits = metrics.real_word_hits
jargon_hits = metrics.jargon_hits
language_checks = metrics.language_checks


def test_real_word_hits_exact_and_case():
    assert real_word_hits(["Moskva", "Velgarov"], ["moskva"]) == ["Moskva"]


def test_real_word_hits_strips_endings():
    # a final a/o/y/i/e/u, or "ov"/"ev"/"in", is stripped on both sides
    assert real_word_hits(["Volgi", "Novgoroda"], ["volga", "novgorod"]) == [
        "Volgi",
        "Novgoroda",
    ]
    assert real_word_hits(["Sorau"], ["volga"]) == []


def test_real_word_hits_checks_each_word_of_a_name():
    assert real_word_hits(["Free Provinces of Volga"], ["volga"]) == [
        "Free Provinces of Volga"
    ]


def test_jargon_hits_whole_words_only():
    assert jargon_hits("Harsh or soft? Any phonemes you dislike?", ["phoneme"]) == [
        "phoneme"
    ]
    assert jargon_hits("A codable onsetter", ["coda", "onset"]) == []


def test_language_checks_valid_language():
    data = {
        "name": "T",
        "level": "naming",
        "categories": {"C": "k t r m n s v", "V": "a o e i u"},
        "generators": [
            {"id": "p", "name": "places", "use": "places", "patterns": ["CVCV"]}
        ],
        "dictionary": [
            {"word": "kata", "meaning": "hill"},
            {"word": "xyz", "meaning": "?"},
        ],
    }
    out = language_checks(data, rolls=20, seed=1)
    assert out["valid"] and out["error"] is None
    assert len(out["samples"]["p"]) == 20
    assert out["dictionary_fit"] == 0.5


def test_language_checks_reports_invalid():
    out = language_checks(
        {
            "name": "T",
            "level": "naming",
            "generators": [
                {
                    "id": "p",
                    "name": "x",
                    "use": "places",
                    "patterns": ["CV"],
                    "reject": ["("],
                }
            ],
        }
    )
    assert not out["valid"] and out["error"]
