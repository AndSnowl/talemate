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
    "all_common_words",
    "is_insult_phrase",
    "clean_name",
    "looks_like_name",
    "mid_sentence_occurrence",
    "mid_sentence_matches",
    "is_proper_item_name",
    "first_mention",
    "ends_with_place_word",
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


def _strip_possessive(word: str) -> str:
    """Strip a trailing possessive (`'s`, `’s`, or a bare trailing `'`)
    from a single (already lowercased) `word`."""

    if word.endswith("'s") or word.endswith("’s"):
        return word[:-2]
    if word.endswith("'") or word.endswith("’"):
        return word[:-1]
    return word


def _plural_candidates(word: str) -> list[str]:
    """Candidate singular forms for a plural-looking `word` (already
    lowercased, possessive stripped): always includes `word` itself."""

    candidates = [word]
    if word.endswith("ies") and len(word) > 3:
        candidates.append(word[:-3] + "y")
    if word.endswith("ves") and len(word) > 3:
        candidates.append(word[:-3] + "fe")
        candidates.append(word[:-3] + "f")
    if word.endswith("men") and len(word) > 3:
        candidates.append(word[:-3] + "man")
    if word.endswith("es") and len(word) > 2:
        candidates.append(word[:-2])
    if word.endswith("s") and len(word) > 1:
        candidates.append(word[:-1])
    return candidates


def _is_common_word(word: str) -> bool:
    """Whether `word` is a common word once a trailing possessive and a
    simple plural ending are normalised away."""

    normalised = _strip_possessive(word.lower())
    return any(
        candidate in COMMON_WORDS for candidate in _plural_candidates(normalised)
    )


# Person/role words: when a single-word phrase isn't itself a common
# word, only a plural or possessive stem that's one of these makes it a
# description ("Bargemen", "Fishwives", "Guards"). A bare plural of an
# ordinary, non-role noun that isn't itself a common word stays a name
# ("Rivers", "Hawks", "Fields") — only a multi-word phrase normalises
# those generically ("River Folk").
_ROLE_WORDS: frozenset[str] = frozenset(
    {
        "guard",
        "man",
        "woman",
        "boy",
        "girl",
        "hand",
        "folk",
        "innkeeper",
        "bargeman",
        "fishwife",
        "watchman",
        "sailor",
        "soldier",
        "merchant",
        "farmer",
        "child",
        "elder",
        "priest",
        "monk",
        "servant",
        "slave",
        "worker",
        # added in task 8b for role/occupation labels common in snapshots
        "barman",
        "carter",
        "chandler",
        "crone",
        "deckhand",
        "drover",
        "ferryhand",
        "lad",
        "lass",
        "matron",
        "ostler",
        "stablehand",
        "tollkeeper",
        "urchin",
    }
)


# Geographic/building words (Task 0): a capitalised run ending in one of
# these ("Lowmarsh Docks", "Kesterholm Port") reads as a place, not a
# person's name, even when it isn't yet a known place in the world.
_PLACE_WORDS: tuple[str, ...] = (
    "reach", "mire", "vale", "wastes", "marches", "hold", "ford", "port",
    "harbour", "harbor", "bay", "isle", "island", "hills", "mountains",
    "peak", "river", "lake", "sea", "coast", "woods", "wood", "forest",
    "marsh", "fen", "moor", "keep", "tower", "gate", "bridge", "market",
    "docks", "quay", "square", "street", "lane", "road", "inn", "tavern",
    "hall", "temple", "city", "town", "village", "quarter", "district",
)  # fmt: skip


def ends_with_place_word(name: str) -> bool:
    """Whether `name`'s last word is a geographic/building word
    (`_PLACE_WORDS`), a trailing possessive or simple plural normalised
    away first. False for an empty `name`."""

    words = name.split()
    if not words:
        return False
    normalised = _strip_possessive(words[-1].lower())
    return any(
        candidate in _PLACE_WORDS for candidate in _plural_candidates(normalised)
    )


def _is_single_word_description(word: str) -> bool:
    """Whether a single-word phrase (`word`) is a description (R14):

    1. the word itself, with no normalisation, is a common word
       ("Lantern", "Ferryman", "River", "Tower", "Woods" — the last is a
       literal `COMMON_WORDS` entry on its own, unrelated to plurals); or
    2. otherwise, some possessive/plural-normalised stem is both a common
       word and a person/role word ("Guards", "Bargemen", "Fishwives").

    A bare plural of an ordinary (non-role) noun that isn't itself a
    common word stays a name ("Rivers", "Hawks", "Fields")."""

    lower = word.lower()
    if lower in COMMON_WORDS:
        return True

    normalised = _strip_possessive(lower)
    return any(
        candidate in COMMON_WORDS and candidate in _ROLE_WORDS
        for candidate in _plural_candidates(normalised)
    )


# Insults and abusive adjectives (all also in `COMMON_WORDS`): a phrase of
# common words with one of these in it is abuse ("The Stupid Bitch"), not
# a name, while one without is still a plain common-tongue name ("The Grey
# Gull").
_INSULT_WORDS: frozenset[str] = frozenset(
    "stupid bitch bastard fool idiot damn damned bloody wretch wretched filthy "
    "useless worthless stinking sodding poxy cur swine oaf dolt halfwit "
    "imbecile moron scum whore".split()
)


def _name_words(text: str) -> list[str]:
    """`text`'s words without a leading article and without connectors."""

    words = clean_name(text).split()
    while words and words[0].lower() in _LEADING_STOP_WORDS:
        words = words[1:]
    return [word for word in words if word.lower() not in _CONNECTORS]


def all_common_words(text: str) -> bool:
    """Whether every word of `text`, leaving out a leading article and
    connectors, is a common English word (possessive and simple plural
    allowed): "The Grey Gull", "Fish Market". False for no words."""

    words = _name_words(text)
    return bool(words) and all(_is_common_word(word) for word in words)


def is_insult_phrase(text: str) -> bool:
    """Whether `text` is all common words and includes an insult ("The
    Stupid Bitch"): a description, never a name."""

    return all_common_words(text) and any(
        _strip_possessive(word.lower()) in _INSULT_WORDS for word in _name_words(text)
    )


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

    if len(non_connector_words) == 1:
        # a single word: a direct common-word hit is a description
        # ("Lantern", "Ferryman", "River", "Tower", "Woods"); otherwise
        # only a person/role word's plural or possessive is a
        # description ("Guards", "Bargemen") — an ordinary noun's plural
        # that isn't itself a common word stays a name ("Rivers", "Hawks")
        if _is_single_word_description(non_connector_words[0]):
            return False
    elif all(_is_common_word(word) for word in non_connector_words):
        return False

    return True


def mid_sentence_matches(name: str, text: str):
    """Yield the text preceding each mid-sentence (exact case) occurrence
    of `name` in `text`, in order.

    An occurrence counts only when the text preceding it, with trailing
    spaces stripped, is non-empty and doesn't end in a sentence-ending
    character or a newline. Shared by `mid_sentence_occurrence` and by the
    Culture agent's naming rules, which also need to look at what comes
    right before a match.
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
        yield preceding


def mid_sentence_occurrence(name: str, text: str) -> bool:
    """Return whether `name` occurs mid-sentence (exact case) in `text`."""

    for _ in mid_sentence_matches(name, text):
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
