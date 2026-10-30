"""What a language is still missing (languages 3b-2): core meanings,
phrase categories and grammar topics. It's reported as "Still to fill in",
never blocks and never sends a language back for repair."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from talemate.languages.models import GRAMMAR_TOPICS, Language

__all__ = [
    "CORE_MEANINGS",
    "PHRASE_CATEGORIES",
    "Completeness",
    "completeness",
    "fill_step",
]

PHRASE_CATEGORIES: tuple[str, ...] = (
    "greeting",
    "farewell",
    "blessing",
    "curse",
    "oath",
    "saying",
    "toast",
    "insult",
    "endearment",
)

# a note in brackets after a meaning: "you (singular)", "fire (n.)"
_NOTE = re.compile(r"\s*\([^)]*\)\s*$")
# meanings a language may show by how its nouns change, not as words
_NOUN_FORMS = ("the", "a")

_CORE_FILE = Path(__file__).resolve().parent / "data" / "core_meanings.txt"


def _read_core() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    current: list[str] | None = None
    for raw in _CORE_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("# ") and line[2:] in ("structural", "everyday"):
            current = groups.setdefault(line[2:], [])
        elif line and not line.startswith("#") and current is not None:
            current.append(line.lower())
    return groups


# the meanings a full language covers, by group ("structural", "everyday")
CORE_MEANINGS: dict[str, list[str]] = _read_core()


class Completeness(BaseModel):
    meanings_total: int
    meanings_missing: list[str]
    structural_missing: list[str]
    phrase_categories_missing: list[str]
    grammar_topics_missing: list[str]


def _key(meaning: str) -> str:
    """A meaning as compared: lower case, a leading "to " dropped ("to be"
    is "be")."""

    key = " ".join(_NOTE.sub("", meaning).lower().split())
    return key[3:] if key.startswith("to ") else key


def completeness(language: Language) -> Completeness:
    """The core meanings, phrase categories and grammar topics `language`
    has no word, phrase or section for. A meaning counts only when a
    dictionary meaning is exactly it ("great fort" isn't "fort")."""

    have = {_key(m) for entry in language.dictionary for m in entry.meanings}
    if any(section.topic == "nouns" for section in language.grammar):
        # "the" and "a" may be endings: the nouns section says how
        have.update(_NOUN_FORMS)
    structural = [m for m in CORE_MEANINGS["structural"] if _key(m) not in have]
    everyday = [m for m in CORE_MEANINGS["everyday"] if _key(m) not in have]
    categories = {p.category.strip().lower() for p in language.phrases}
    topics = {section.topic for section in language.grammar}
    return Completeness(
        meanings_total=len(CORE_MEANINGS["structural"])
        + len(CORE_MEANINGS["everyday"]),
        meanings_missing=structural + everyday,
        structural_missing=structural,
        phrase_categories_missing=[c for c in PHRASE_CATEGORIES if c not in categories],
        grammar_topics_missing=[
            title for topic, title in GRAMMAR_TOPICS if topic not in topics
        ],
    )


def fill_step(language: Language) -> str | None:
    """What "Fill in next" adds: "words", "phrases" or "grammar", the first
    with something missing; None when nothing is (or for a language that
    isn't full)."""

    if language.level != "full":
        return None
    found = completeness(language)
    if found.meanings_missing:
        return "words"
    if found.phrase_categories_missing:
        return "phrases"
    if found.grammar_topics_missing:
        return "grammar"
    return None
