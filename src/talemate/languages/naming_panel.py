"""Names for the Name it… panel (languages 4a revised): a batch from a
rule, or from one of its patterns, with no model call; what a name means
where it's built from the dictionary's words; and names made from a
meaning the owner types (`naming.translate_text`). Nothing is saved here:
a picked word is added to the language by the caller."""

from __future__ import annotations

import random
import re

from pydantic import BaseModel

from talemate.languages.entry import language_of
from talemate.languages.generator import roll
from talemate.languages.composed import _label
from talemate.languages.models import Language
from talemate.languages.naming import translate_text
from talemate.world.view import WorldView

__all__ = ["RuleInfo", "batch", "from_meaning", "meaning_of", "rules_of"]

BATCH = 10
# the longest ending left over after the dictionary's words that still
# reads as a rule's ending ("-gorsk")
MAX_ENDING = 6
_WEIGHT = re.compile(r"\*\d+(?:\.\d+)?\s*$")


class RuleInfo(BaseModel):
    id: str
    name: str
    use: str
    patterns: list[str]
    # a composed rule's parts, as labels (languages 4b-1); [] for a plain one
    parts: list[str] = []


def rules_of(language: Language) -> list[RuleInfo]:
    """The language's rules, each with its patterns (weights left off)."""

    return [
        RuleInfo(
            id=g.id,
            name=g.name,
            use=g.use,
            patterns=[_WEIGHT.sub("", p).strip() for p in g.patterns],
            parts=[
                part.word if part.kind == "word" else _label(language, part)
                for part in (g.shapes[0].parts if g.shapes else [])
            ],
        )
        for g in language.generators
    ]


def meaning_of(language: Language, name: str) -> str:
    """What `name` means when it's built from the dictionary's words, as
    `syev “grey” + voda “water”`, with a short leftover ending shown as
    `-gorsk`; "" when it isn't."""

    words = {
        e.word.lower(): (e.meanings[0] if e.meanings else "")
        for e in language.dictionary
    }
    key = re.sub(r"[^\w]", "", name.lower())

    def split(rest: str) -> list[str] | None:
        if not rest:
            return []
        for end in range(len(rest), 1, -1):
            head = rest[:end]
            if head in words:
                tail = split(rest[end:])
                if tail is not None:
                    return [head, *tail]
        return None

    for cut in range(len(key), 0, -1):
        found = split(key[:cut])
        ending = key[cut:]
        if found and len(ending) <= MAX_ENDING:
            parts = [f"{w} “{words[w]}”" if words[w] else w for w in found]
            if ending:
                parts.append(f"-{ending}")
            return " + ".join(parts)
    return ""


def batch(
    language: Language,
    rule_id: str,
    *,
    pattern: int | None = None,
    count: int = BATCH,
    exclude: frozenset[str] = frozenset(),
    seed: int | None = None,
) -> list[dict]:
    """Up to `count` names from the rule (or one of its patterns), each
    `{name, meaning}`; fewer when the rule can't make more. No model."""

    names = roll(
        language,
        rule_id,
        count=count,
        rng=random.Random(seed),
        exclude=set(exclude),
        pattern=pattern,
    )
    return [{"name": n, "meaning": meaning_of(language, n)} for n in names]


async def from_meaning(
    view: WorldView, client, language_id: str, text: str, *, reply: str | None = None
) -> list[dict]:
    """Names for a meaning ("grey lake"): the words as one name
    ("Syevozera") and, with more than one, as separate words ("Syev
    Ozera"), each `{name, built_from: [{word, meaning, new}]}`. New words
    are coined from the word rules; nothing is saved."""

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        raise ValueError("there's no such language")
    language = language_of(state)
    result = await translate_text(client, language, text, reply=reply)
    words = [p["word"] for p in result.parts]
    if not words:
        return []
    joined = "".join(words)
    found = [{"name": joined[:1].upper() + joined[1:], "built_from": result.parts}]
    if len(words) > 1:
        found.append({"name": result.name, "built_from": result.parts})
    return found
