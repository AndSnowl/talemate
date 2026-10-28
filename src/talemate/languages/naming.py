"""Naming from a language (languages 3a; part-3 design, "Names in other
languages").

Names are rolled from the language's own rules; the model only defines
them and picks among candidates (probe 1: local models can do those two,
not write a language's words). A word already used as an entry's name
keeps its meaning.
"""

from __future__ import annotations

import random
import re

from pydantic import BaseModel

from talemate.languages.entry import language_of, used_words
from talemate.languages.generator import roll
from talemate.languages.models import GeneratorDef, Language
from talemate.prompts import Prompt
from talemate.world.store import Revision
from talemate.world.view import WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.create import json_objects

__all__ = [
    "NameInResult",
    "add_word",
    "apply_name_in",
    "define",
    "generator_for",
    "name_in",
    "pick",
    "roll_names",
]

PROMPT_KIND = "analyze"

# which bucket names an entry kind when the language has no rules for it
_BUCKETS = {"character": "people", "being": "people", "place": "places"}

# English words a name in another language leaves out
_FUNCTION_WORDS = {"of", "the", "and", "a", "an", "in", "on", "at", "to"}

# candidates rolled for each word a translation needs
_CANDIDATES = 8


class NameInResult(BaseModel):
    name: str
    new_words: list[dict[str, str]] = []


def generator_for(language: Language, kind: str) -> GeneratorDef:
    """The name rules for an entry `kind`: its own, else its bucket's
    (people, places, things), else places, else the first that isn't for
    ordinary words."""

    names = [g for g in language.generators if g.use != "words"]
    for wanted in (kind, _BUCKETS.get(kind, "things"), "places"):
        for generator in names:
            if generator.use == wanted:
                return generator
    if names:
        return names[0]
    raise ValueError("this language has no name rules")


def roll_names(
    language: Language,
    kind: str,
    count: int = 4,
    seed: int | None = None,
    exclude: frozenset[str] = frozenset(),
) -> list[str]:
    """`count` names for a `kind`, none of them in `exclude`."""

    generator = generator_for(language, kind)
    rng = random.Random(seed)
    return roll(language, generator.id, count=count, rng=rng, exclude=set(exclude))


def _reply_object(reply: str) -> dict:
    objects = json_objects(reply)
    return objects[0] if objects else {}


async def define(
    client,
    language: Language,
    names: list[str],
    context: str = "",
    *,
    reply: str | None = None,
) -> dict[str, str]:
    """One plain sentence per name, in one call; a name the reply misses
    gets "". `reply` stands in for the model's (browser tests)."""

    if reply is None:
        reply = await _define_reply(client, language, names, context)
    found = _reply_object(reply).get("definitions") or {}
    return {
        name: " ".join(str(found.get(name, "")).split())
        if isinstance(found, dict)
        else ""
        for name in names
    }


async def _define_reply(
    client, language: Language, names: list[str], context: str
) -> str:
    prose_gen.require_client(client)
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.language-define",
            client,
            PROMPT_KIND,
            vars={
                "language": language.name,
                "sound": language.sound,
                "context": context,
                "words": [e.model_dump() for e in language.dictionary[:40]],
                "names": names,
            },
        )
    return extracted["response"]


async def pick(
    client,
    language: Language,
    candidates: list[str],
    what: str,
    *,
    reply: str | None = None,
) -> tuple[str, str]:
    """The candidate the model picks for `what`, and why; the first
    candidate when it picks something else. `reply` stands in for the
    model's (browser tests)."""

    if reply is None and client is None:
        # no model to choose: the rules made them all, the first will do
        return candidates[0], ""
    if reply is None:
        reply = await _pick_reply(client, language, candidates, what)
    chosen = _reply_object(reply).get("pick")
    if chosen not in candidates:
        return candidates[0], ""
    return chosen, str(_reply_object(reply).get("why") or "")


async def _pick_reply(
    client, language: Language, candidates: list[str], what: str
) -> str:
    prose_gen.require_client(client)
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.language-pick",
            client,
            PROMPT_KIND,
            vars={
                "language": language.name,
                "sound": language.sound,
                "what": what,
                "candidates": candidates,
            },
        )
    return extracted["response"]


def add_word(
    rev: Revision, view: WorldView, language_id: str, word: str, meaning: str
) -> None:
    """Add `word` to the language, or redefine it; a word already used as
    an entry's name keeps its meaning."""

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        raise ValueError("there's no such language")
    word, meaning = word.strip(), " ".join(meaning.split())
    if not word or not meaning:
        raise ValueError("a word needs both the word and its meaning")
    words = [dict(w) for w in state.fields.get("words") or []]
    key = word.lower()
    existing = next((w for w in words if str(w.get("word", "")).lower() == key), None)
    if existing is not None:
        if key in used_words(view, language_id):
            return
        existing["meaning"] = meaning
    else:
        words.append({"word": word, "meaning": meaning})
    rev.set_field(language_id, "words", words, None)


async def name_in(
    view: WorldView,
    client,
    thing_id: str,
    language_id: str,
    *,
    reply: str | None = None,
) -> NameInResult:
    """The entry's name in another language: words the language already
    has stay, English words whose meaning it has are translated, and each
    other word is rolled from its word rules and picked by the model."""

    thing = view.thing(thing_id)
    state = view.thing(language_id)
    if thing is None or state is None or state.kind != "language":
        raise ValueError("there's no such entry or language")
    language = language_of(state)
    by_word = {e.word.lower(): e.word for e in language.dictionary}
    by_meaning = {e.meaning.strip().lower(): e.word for e in language.dictionary}
    word_rules = language.word_generator()
    taken = set(by_word)
    out: list[str] = []
    new_words: list[dict[str, str]] = []
    name = str(thing.fields.get("name") or "")
    for word in re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", name):
        key = word.lower()
        if key in by_word:
            out.append(by_word[key])
        elif key in _FUNCTION_WORDS:
            continue
        elif key in by_meaning:
            out.append(by_meaning[key])
        else:
            if word_rules is None:
                raise ValueError("this language has no word rules to make new words")
            candidates = roll(
                language,
                word_rules.id,
                count=_CANDIDATES,
                rng=random.Random(),
                exclude=taken,
            )
            if not candidates:
                raise ValueError("the language's word rules made no new words")
            chosen, _why = await pick(
                client,
                language,
                candidates,
                f'the word for "{key}" ({name})',
                reply=reply,
            )
            taken.add(chosen.lower())
            new_words.append({"word": chosen.lower(), "meaning": key})
            out.append(chosen)
    return NameInResult(
        name=" ".join(w[:1].upper() + w[1:] for w in out), new_words=new_words
    )


def apply_name_in(
    rev: Revision,
    view: WorldView,
    thing_id: str,
    language_id: str,
    result: NameInResult,
) -> None:
    """Add the name as one of the entry's other names, marked with its
    language, and the new words to the language."""

    thing = view.thing(thing_id)
    if thing is None:
        raise ValueError("there's no such entry")
    aka = [dict(a) for a in thing.fields.get("aka") or []]
    if not any(a.get("name") == result.name for a in aka):
        aka.append(
            {
                "name": result.name,
                "tag": "proper",
                "everyday": False,
                "language": language_id,
            }
        )
        rev.set_field(thing_id, "aka", aka, None)
    for word in result.new_words:
        add_word(rev, view, language_id, word["word"], word["meaning"])
