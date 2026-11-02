"""The name engine (languages 4b-1): a language's grammar for names
applied to words. It builds a name from words and a meaning's structure,
in the language's order and forms; no model is ever asked. The rules'
models live in `talemate.languages.models` and are re-exported here."""

from __future__ import annotations

from collections.abc import Callable

from talemate.languages.models import (
    Ending,
    FormChange,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)

__all__ = [
    "Ending",
    "FormChange",
    "NameGrammar",
    "NamePart",
    "NameShape",
    "OfRule",
    "parse_condition",
]

Condition = Callable[[str, frozenset[str]], bool]


def parse_condition(when: str) -> Condition:
    """`when` as a test of a word and the language's vowels: "" always,
    "after_vowel" and "after_consonant" (the word's end), "before_vowel"
    (its start), "ends:a|o" (it ends with one of those letters). Raises
    `ValueError` for anything else."""

    when = (when or "").strip()
    if not when:
        return lambda word, vowels: True
    if when == "after_vowel":
        return lambda word, vowels: bool(word) and word[-1].lower() in vowels
    if when == "after_consonant":
        return lambda word, vowels: bool(word) and word[-1].lower() not in vowels
    if when == "before_vowel":
        return lambda word, vowels: bool(word) and word[0].lower() in vowels
    if when.startswith("ends:"):
        endings = tuple(e.strip().lower() for e in when[5:].split("|") if e.strip())
        if endings:
            return lambda word, vowels: word.lower().endswith(endings)
    raise ValueError(f"unknown condition: {when!r}")
