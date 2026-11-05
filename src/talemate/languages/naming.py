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

from talemate.languages.entry import language_of
from talemate.languages.generator import roll
from talemate.languages.models import DictionaryEntry, GeneratorDef, Language
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
    # each word of the name: `{word, meaning, new}` (languages 4a revised)
    parts: list[dict] = []


def generator_for(
    language: Language, kind: str, person: dict[str, str] | None = None
) -> GeneratorDef:
    """The name rules for an entry `kind`: its own, else its bucket's
    (people, places, things), else places, else the first that isn't for
    ordinary words. With `person` (who a person is built as, languages
    4b-2), the people rule for them (`person_names.pick_rule`)."""

    if person is not None:
        from talemate.languages.person_names import pick_rule

        return pick_rule(language, person)
    names = [g for g in language.generators if g.use != "words"]
    for wanted in (kind, _BUCKETS.get(kind, "things"), "places"):
        # a plain rule first: a composed one (languages 4b-1) is used when
        # it's picked, or when it's the only one
        found = [g for g in names if g.use == wanted]
        for generator in sorted(found, key=lambda g: bool(g.shapes)):
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
    """Add `word` to the language, or add `meaning` to its meanings (a word
    has several: "wind", "breath"). A blank meaning adds the word alone, as
    a name with no meaning; nothing already there is replaced."""

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        raise ValueError("there's no such language")
    word, meaning = word.strip(), " ".join(meaning.split())
    if not word:
        raise ValueError("a word can't be blank")
    words = [
        DictionaryEntry.model_validate(w).model_dump(exclude_defaults=True)
        | {"meanings": DictionaryEntry.model_validate(w).meanings}
        for w in state.fields.get("words") or []
    ]
    key = word.lower()
    existing = next((w for w in words if str(w.get("word", "")).lower() == key), None)
    if existing is None:
        words.append({"word": word, "meanings": [meaning] if meaning else []})
    elif meaning and meaning.lower() not in {m.lower() for m in existing["meanings"]}:
        existing["meanings"] = [*existing["meanings"], meaning]
    else:
        return
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
    name = str(thing.fields.get("name") or "")
    return await translate_text(client, language, name, what=name, reply=reply)


async def translate_text(
    client, language: Language, text: str, *, what: str = "", reply: str | None = None
) -> NameInResult:
    """`text` in `language`, word by word: words the language already has
    stay, English words whose meaning it has are translated, function
    words are dropped, and each other word is rolled from its word rules
    and picked by the model (its new words in `new_words`). Nothing is
    saved."""

    if language.name_grammar is not None and not re.search(r"\s(of)\s", text.lower()):
        # a language with grammar for names builds it (languages 4b-1):
        # "white lake" in its order and forms; "X of Y" keeps the old way
        built = await _translate_built(client, language, text, what=what, reply=reply)
        if built is not None:
            return built
    by_word = {e.word.lower(): e.word for e in language.dictionary}
    by_meaning = {m.lower(): e.word for e in language.dictionary for m in e.meanings}
    meaning_of_word = {
        e.word.lower(): (e.meanings[0] if e.meanings else "")
        for e in language.dictionary
    }
    word_rules = language.word_generator()
    taken = set(by_word)
    out: list[str] = []
    parts: list[dict] = []
    new_words: list[dict[str, str]] = []
    for word in re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", text):
        key = word.lower()
        if key in by_word:
            out.append(by_word[key])
            parts.append(
                {
                    "word": by_word[key].lower(),
                    "meaning": meaning_of_word[key],
                    "new": False,
                }
            )
        elif key in _FUNCTION_WORDS:
            continue
        elif key in by_meaning:
            out.append(by_meaning[key])
            parts.append(
                {"word": by_meaning[key].lower(), "meaning": key, "new": False}
            )
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
                f'the word for "{key}" ({what or text})',
                reply=reply,
            )
            taken.add(chosen.lower())
            new_words.append({"word": chosen.lower(), "meaning": key})
            # the other rolls too, the pick first: the owner may pick
            # another (owner, Test3)
            options = [chosen.lower()] + [
                c.lower() for c in candidates if c.lower() != chosen.lower()
            ]
            parts.append(
                {
                    "word": chosen.lower(),
                    "meaning": key,
                    "new": True,
                    "options": options,
                }
            )
            out.append(chosen)
    return NameInResult(
        name=" ".join(w[:1].upper() + w[1:] for w in out),
        new_words=new_words,
        parts=parts,
    )


async def _translate_built(
    client, language: Language, text: str, *, what: str, reply: str | None
) -> NameInResult | None:
    from talemate.languages.name_grammar import build_phrase
    from talemate.languages.naming_meaning import read_english, resolve_words

    phrase = read_english(text)
    if not phrase.noun:
        return None
    meanings = [*phrase.describing, phrase.noun]
    words, new, options = await resolve_words(
        client, language, meanings, what=what or text, reply=reply
    )
    built = build_phrase(language, phrase, words, frozenset(new))
    return NameInResult(
        name=built.text,
        new_words=[{"word": w, "meaning": m} for m, w in words.items() if w in new],
        parts=[
            {**p, **({"options": options[p["word"]]} if p["word"] in options else {})}
            for p in built.parts
        ],
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
