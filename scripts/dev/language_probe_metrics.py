"""Scoring for the language probes (languages plan 1, Tasks 4 and 6).

Pure functions, no model: `real_word_hits` (names that are real words
once a crude ending is stripped), `jargon_hits` (linguistics terms in
plain-language questions) and `language_checks` (does a model-written
language load, roll and fit its own words). Tested in
`tests/dev/test_language_probe_metrics.py`.
"""

from __future__ import annotations

import random
import re

from talemate.languages.generator import fits, roll, validate_language
from talemate.languages.models import Language

_LONG_ENDINGS = ("ov", "ev", "in")
_VOWELS = "aoyieu"


def _stem(word: str) -> str:
    """`word` lower-cased, with one crude ending cut: "ov"/"ev"/"in" from a
    word of five letters or more, else a final vowel from one of four or
    more."""
    word = word.lower()
    if len(word) >= 5 and word.endswith(_LONG_ENDINGS):
        return word[:-2]
    if len(word) >= 4 and word[-1] in _VOWELS:
        return word[:-1]
    return word


def real_word_hits(names: list[str], real: list[str]) -> list[str]:
    """The names, in order, any of whose words is a real word: equal to one
    of `real` (case-insensitive), or equal once both are stemmed."""
    exact = {w.lower() for w in real}
    stems = {_stem(w) for w in real}
    hits = []
    for name in names:
        words = re.findall(r"[^\W\d_]+", name)
        if any(w.lower() in exact or _stem(w) in stems for w in words):
            hits.append(name)
    return hits


def jargon_hits(text: str, jargon: list[str]) -> list[str]:
    """The `jargon` terms that occur in `text` as whole words (a plural "s"
    allowed), case-insensitive, in `jargon`'s order."""
    return [
        term
        for term in jargon
        if re.search(rf"\b{re.escape(term)}s?\b", text, re.IGNORECASE)
    ]


def language_checks(
    data: dict, rolls: int = 50, seed: int = 0, real: list[str] = ()
) -> dict:
    """Load `data` as a `Language` and try it: `valid` and `error`, `rolls`
    samples per generator, the share of its dictionary words that `fits`,
    and the samples and dictionary words that are real words."""
    out = {
        "valid": False,
        "error": None,
        "samples": {},
        "dictionary_fit": 0.0,
        "real_hits": [],
    }
    try:
        language = Language.model_validate(data)
        validate_language(language)
        rng = random.Random(seed)
        out["samples"] = {
            g.id: roll(language, g.id, count=rolls, rng=rng)
            for g in language.generators
        }
        words = [entry.word for entry in language.dictionary]
        if words:
            out["dictionary_fit"] = sum(fits(language, w) for w in words) / len(words)
        sampled = [name for names in out["samples"].values() for name in names]
        out["real_hits"] = real_word_hits(sampled + words, list(real))
        out["valid"] = True
    except Exception as exc:  # a model's language can be wrong in any way
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


FLAG_CLASSES = ("real", "stock-title")


def flag_scores(labels: dict[str, str], flagged: dict[str, str]) -> dict:
    """Precision and recall per flag class (`real`, `stock-title`) for a
    model's `flagged` labels against the `labels` (both name -> "real",
    "stock-title" or "ok"; a name missing from `flagged` counts as "ok").
    `missed`: labelled names given another class; `false_flags`: names
    flagged with a class that isn't theirs. Precision is None when nothing
    was flagged with that class."""
    scores: dict = {}
    for cls in FLAG_CLASSES:
        said = [n for n in labels if flagged.get(n, "ok") == cls]
        truly = [n for n in labels if labels[n] == cls]
        right = [n for n in said if labels[n] == cls]
        scores[cls] = {
            "precision": len(right) / len(said) if said else None,
            "recall": len(right) / len(truly) if truly else None,
        }
    scores["missed"] = [
        n for n, cls in labels.items() if cls != "ok" and flagged.get(n, "ok") != cls
    ]
    scores["false_flags"] = [
        n
        for n, cls in labels.items()
        if flagged.get(n, "ok") != "ok" and flagged.get(n) != cls
    ]
    return scores
