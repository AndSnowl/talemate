"""Building a scene's foreign-word lexicon for story highlights.

Turns the phrases and single-/multi-word glossary entries of the scene's
present cultures into a flat list of `LexiconEntry`, ready for the frontend
to match (whole-word, case-insensitive) against story text. Pure, no model
calls, no I/O: the Culture agent and the cultures plugin pass in the
already-loaded cultures and glossary.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .models import Culture, GlossaryEntry
from .words import _is_common_word

__all__ = [
    "MIN_WORD_LETTERS",
    "MAX_LEXICON_ENTRIES",
    "word_tokens",
    "can_highlight",
    "phrase_kind",
    "LexiconEntry",
    "normalize_key",
    "build_scene_lexicon",
]

# A single-word highlight candidate needs at least this many letters
# (apostrophes and hyphens don't count), and a scene's lexicon is capped at
# this many entries. The frontend matches every entry through one regex on
# every story message, and past roughly 1,000 alternatives that regex gets
# dramatically slower (seconds per re-render), so the cap stays well below
# that, with room left for name mentions. Phrases come first, so a big
# world loses glossary words from the tail, never its curses or sayings.
MIN_WORD_LETTERS = 4
MAX_LEXICON_ENTRIES = 600

# A run of letters, which may contain an inner apostrophe (straight or
# curly) or hyphen joining more letters ("tal'dun", "co-op").
_WORD_TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")

# The first letter-run of a phrase category ("Sayings & blessings" -> "Sayings").
_CATEGORY_WORD_RE = re.compile(r"[^\W\d_]+")

# Stripped out of a token before counting its letters.
_INNER_PUNCT_RE = re.compile(r"['’-]")

# Stripped from both ends of a normalized key.
_KEY_STRIP_CHARS = " .,;:!?…\"“”‘'()"


def word_tokens(text: str) -> list[str]:
    """Return the runs of letters in `text` (see `_WORD_TOKEN_RE`)."""

    return _WORD_TOKEN_RE.findall(text)


def _qualifies(token: str) -> bool:
    """Whether `token` alone is enough to make a highlight: long enough and
    not a common word."""

    letters = _INNER_PUNCT_RE.sub("", token)
    return len(letters) >= MIN_WORD_LETTERS and not _is_common_word(token)


def can_highlight(text: str, *, phrase: bool = False) -> bool:
    """Whether `text` qualifies for a foreign-word/name highlight.

    - no tokens: False
    - one token: whether it qualifies (`_qualifies`)
    - several tokens, `phrase=True` (a stored phrase): any token qualifies
    - several tokens, `phrase=False` (a multi-word glossary entry): no
      token is a common word, and any token qualifies
    """

    tokens = word_tokens(text)
    if not tokens:
        return False
    if len(tokens) == 1:
        return _qualifies(tokens[0])
    if phrase:
        return any(_qualifies(token) for token in tokens)
    return all(not _is_common_word(token) for token in tokens) and any(
        _qualifies(token) for token in tokens
    )


def phrase_kind(category: str) -> str:
    """Return a short highlight "kind" from a phrase's free-text category.

    The first letter-run of `category`, lowercased, with a trailing `s`
    dropped when the word is longer than 3 letters. `"phrase"` when
    `category` has no letters at all.
    """

    match = _CATEGORY_WORD_RE.search(category)
    if not match:
        return "phrase"
    word = match.group(0).lower()
    if len(word) > 3 and word.endswith("s"):
        word = word[:-1]
    return word


def normalize_key(text: str) -> str:
    """Return a dedupe key for `text`: lowercase, curly apostrophe folded to
    straight, inner whitespace collapsed, leading/trailing punctuation and
    spaces stripped."""

    folded = text.lower().replace("’", "'")
    collapsed = re.sub(r"\s+", " ", folded)
    return collapsed.strip(_KEY_STRIP_CHARS)


class LexiconEntry(BaseModel):
    """One foreign phrase or word the frontend may highlight in the story."""

    id: str
    text: str
    kind: str
    culture_id: str
    culture_name: str
    language_name: str
    color: str
    translation: str
    breakdown: list[list[str]] = Field(default_factory=list)
    usage: str = ""
    target: dict


def build_scene_lexicon(
    present: list[Culture], glossary: list[GlossaryEntry]
) -> list[LexiconEntry]:
    """Return the highlightable phrases and glossary words of `present`
    cultures, in culture order, deduplicated (first entry per normalized
    text wins, so phrases beat glossary words), capped at
    `MAX_LEXICON_ENTRIES`."""

    entries: list[LexiconEntry] = []
    seen: set[str] = set()

    def add(entry: LexiconEntry) -> None:
        key = normalize_key(entry.text)
        if key in seen:
            return
        seen.add(key)
        entries.append(entry)

    for culture in present:
        for phrase in culture.language.phrases:
            if not phrase.original:
                continue
            if not can_highlight(phrase.original, phrase=True):
                continue
            add(
                LexiconEntry(
                    id=f"phrase:{culture.id}:{phrase.id}",
                    text=phrase.original,
                    kind=phrase_kind(phrase.category),
                    culture_id=culture.id,
                    culture_name=culture.name,
                    language_name=culture.language.name,
                    color=culture.color,
                    translation=phrase.translation,
                    breakdown=[list(pair) for pair in phrase.breakdown],
                    usage=phrase.usage,
                    target={
                        "type": "phrase",
                        "culture_id": culture.id,
                        "phrase_id": phrase.id,
                    },
                )
            )

        # First entry for a given word wins (matches this function's own
        # dedupe-by-text rule), rather than the last one silently
        # overriding it.
        dictionary_by_word: dict = {}
        for dict_entry in culture.language.dictionary:
            dictionary_by_word.setdefault(dict_entry.word.lower(), dict_entry)

        for entry in glossary:
            if entry.language != culture.id:
                continue
            if entry.kind not in ("word", "thing"):
                continue
            if entry.origin.by == "ai_free" and not entry.meaning:
                continue
            if not can_highlight(entry.text):
                continue

            dict_entry = dictionary_by_word.get(entry.text.lower())
            translation = entry.meaning
            if not translation and dict_entry is not None:
                translation = dict_entry.meaning
            # `usage` always comes from the matching dictionary entry's
            # notes when one exists, even when the glossary entry already
            # has its own `meaning`.
            usage = dict_entry.notes if dict_entry is not None else ""

            add(
                LexiconEntry(
                    id=f"glossary:{entry.id}",
                    text=entry.text,
                    kind="word",
                    culture_id=culture.id,
                    culture_name=culture.name,
                    language_name=culture.language.name,
                    color=culture.color,
                    translation=translation,
                    breakdown=[],
                    usage=usage,
                    target={"type": "glossary", "entry_id": entry.id},
                )
            )

    return entries[:MAX_LEXICON_ENTRIES]
