"""A `language` entry as a `Language`, and back, and which of its words
already name something in the world (languages 3a).

The entry's technical part lives in its own fields (`kinds.py`'s
`language` kind): `depth`, `flavour`, `sound`, `rules` (categories, name
rules and the notes a full language carries), `words`, `phrases`,
`descends_from` and `similar`. A file names other languages; an entry
holds their ids, so `similar` round-trips by name only when a view is
given to resolve them.
"""

from __future__ import annotations

import re

from talemate.languages.models import (
    DictionaryEntry,
    GeneratorDef,
    Language,
    Phrase,
    SimilarLink,
)
from talemate.world.view import ThingState, WorldView

__all__ = ["fields_of", "language_of", "languages", "used_words", "word_uses"]


def fields_of(language: Language) -> dict[str, object]:
    """The entry fields for `language` (its name is the caller's)."""

    rules: dict[str, object] = {
        "categories": dict(language.categories),
        "generators": [g.model_dump() for g in language.generators],
    }
    if language.syllable_notes:
        rules["syllable_notes"] = list(language.syllable_notes)
    if language.grammar:
        rules["grammar"] = language.grammar
    if not language.writable:
        rules["writable"] = False
    return {
        "depth": language.level,
        "flavour": language.flavour,
        "sound": language.sound,
        "rules": rules,
        "words": [e.model_dump() for e in language.dictionary],
        "phrases": [p.model_dump(mode="json") for p in language.phrases],
    }


def language_of(state: ThingState, view: WorldView | None = None) -> Language:
    """`state` (a `language` entry) as a `Language`; with `view`, its
    similar-language links come back by name."""

    fields = state.fields
    rules = fields.get("rules") or {}
    similar: list[SimilarLink] = []
    if view is not None:
        for link in fields.get("similar") or []:
            other = view.thing(link["target"])
            if other is not None:
                similar.append(
                    SimilarLink(
                        name=str(other.fields.get("name", "")), degree=link["degree"]
                    )
                )
    return Language(
        name=str(fields.get("name", "")),
        level=fields.get("depth") or "naming",
        flavour=str(fields.get("flavour") or ""),
        sound=str(fields.get("sound") or ""),
        writable=bool(rules.get("writable", True)),
        categories=dict(rules.get("categories") or {}),
        syllable_notes=list(rules.get("syllable_notes") or []),
        generators=[GeneratorDef(**g) for g in rules.get("generators") or []],
        grammar=str(rules.get("grammar") or ""),
        dictionary=[DictionaryEntry(**w) for w in fields.get("words") or []],
        phrases=[Phrase(**p) for p in fields.get("phrases") or []],
        similar=similar,
    )


def languages(view: WorldView) -> list[ThingState]:
    """The world's live `language` entries."""

    return view.things("language", facts=False)


def _names(state: ThingState) -> list[str]:
    names = [str(state.fields.get("name") or "")]
    names += [str(a.get("name", "")) for a in state.fields.get("aka") or []]
    return [n for n in names if n]


def word_uses(view: WorldView, language_id: str) -> dict[str, list[dict[str, str]]]:
    """For each of the language's words that names something, the live
    entries whose name or other names use it (`{id, name, kind}`), keyed
    by the word in lower case: worked out each time, never stored."""

    state = view.thing(language_id)
    if state is None:
        return {}
    words = {str(w.get("word", "")).lower() for w in state.fields.get("words") or []}
    words.discard("")
    uses: dict[str, list[dict[str, str]]] = {}
    for thing in view.things(facts=False):
        if thing.id == language_id:
            continue
        found = set()
        for name in _names(thing):
            found |= words & {w.lower() for w in re.findall(r"[^\W\d_]+", name)}
        for word in sorted(found):
            uses.setdefault(word, []).append(
                {
                    "id": thing.id,
                    "name": str(thing.fields.get("name") or ""),
                    "kind": thing.kind,
                }
            )
    return uses


def used_words(view: WorldView, language_id: str) -> set[str]:
    """The language's words (lower-case) that some live entry's name or
    other name uses as a whole word, stubs included: these are fixed."""

    state = view.thing(language_id)
    if state is None:
        return set()
    words = {str(w.get("word", "")).lower() for w in state.fields.get("words") or []}
    words.discard("")
    used: set[str] = set()
    for thing in view.things(facts=False):
        if thing.id == language_id:
            continue
        for name in _names(thing):
            used |= words & {w.lower() for w in re.findall(r"[^\W\d_]+", name)}
    return used
