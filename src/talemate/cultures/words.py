"""Word-level rules for telling proper names from descriptions.

These are plain text heuristics used by the Culture agent (and its
tests) to decide whether a bit of text looks like a name, whether a
name actually turns up as a proper noun mid-sentence in the scene's
messages, and to find a name's first mention.
"""

from __future__ import annotations

import re
from importlib import resources

__all__ = [
    "COMMON_WORDS",
    "clean_name",
    "looks_like_name",
    "mid_sentence_occurrence",
    "is_proper_item_name",
    "first_mention",
]


def _load_common_words() -> frozenset[str]:
    text = (
        resources.files("talemate.cultures")
        .joinpath("data", "common_words.txt")
        .read_text(encoding="utf-8")
    )
    return frozenset(line.strip().lower() for line in text.splitlines() if line.strip())


COMMON_WORDS: frozenset[str] = _load_common_words()

# Words that can't start a name (articles, demonstratives, possessives).
_LEADING_STOP_WORDS = {
    "the",
    "a",
    "an",
    "some",
    "his",
    "her",
    "their",
    "my",
    "our",
    "your",
    "this",
    "that",
    "these",
    "those",
}

# Lowercase connectors allowed mid-name without needing a capital letter
# ("Ilsa of the Birches", "Anne de la Croix").
_CONNECTORS = {"of", "the", "de", "du", "van", "von", "al", "el", "la", "le"}

# Characters stripped from both ends of a name: quotes (straight and
# curly) and whitespace.
_STRIP_CHARS = "\"'‘’“” \t\n\r"

# Trailing punctuation stripped from a name.
_TRAILING_PUNCT = ".,;:!?"

# Sentence-ending characters that, found right before a name's
# occurrence, mean the name isn't really mid-sentence (it opens a new
# sentence instead).
_SENTENCE_ENDERS = {".", "!", "?", ":", '"', "“", "”", "‘", "'"}


def clean_name(text: str) -> str:
    """Strip whitespace, quotes, trailing punctuation and a possessive `'s`."""

    cleaned = text.strip(_STRIP_CHARS)
    cleaned = cleaned.rstrip(_TRAILING_PUNCT)
    cleaned = cleaned.strip(_STRIP_CHARS)
    if cleaned.endswith("'s") or cleaned.endswith("’s"):
        cleaned = cleaned[:-2]
        cleaned = cleaned.strip(_STRIP_CHARS)
    return cleaned


def looks_like_name(text: str) -> bool:
    """Return whether `text` (after cleaning) looks like a proper name."""

    cleaned = clean_name(text)
    if not cleaned:
        return False

    words = cleaned.split()
    if not (1 <= len(words) <= 4):
        return False

    if words[0].lower() in _LEADING_STOP_WORDS:
        return False

    non_connector_words: list[str] = []
    for index, word in enumerate(words):
        if index > 0 and word.lower() in _CONNECTORS:
            continue
        if not word[:1].isupper():
            return False
        non_connector_words.append(word)

    if not non_connector_words:
        return False

    if all(word.lower() in COMMON_WORDS for word in non_connector_words):
        return False

    return True


def mid_sentence_occurrence(name: str, text: str) -> bool:
    """Return whether `name` occurs mid-sentence (exact case) in `text`.

    An occurrence counts only when the text preceding it, with trailing
    spaces stripped, is non-empty and doesn't end in a sentence-ending
    character or a newline.
    """

    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for match in pattern.finditer(text):
        preceding = text[: match.start()].rstrip(" ")
        if not preceding:
            continue
        if preceding.endswith("\n"):
            continue
        if preceding[-1] in _SENTENCE_ENDERS:
            continue
        return True
    return False


def is_proper_item_name(name: str, texts: list[str]) -> bool:
    """Return whether `name` reads as a proper item name across `texts`.

    True when `name` occurs mid-sentence in any of `texts`, and `name`
    isn't a single common word.
    """

    words = name.split()
    if len(words) == 1 and name.lower() in COMMON_WORDS:
        return False

    return any(mid_sentence_occurrence(name, text) for text in texts)


def first_mention(name: str, messages: list) -> object | None:
    """Return the first message whose `.message` contains `name` as a
    case-sensitive whole word, or `None`."""

    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for message in messages:
        text = getattr(message, "message", None)
        if text and pattern.search(text):
            return message
    return None
