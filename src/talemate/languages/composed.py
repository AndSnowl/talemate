"""Composed name rules (languages 4b-1): a rule made of parts (another
rule, a fixed word, a meaning part), rolled part by part. A meaning part
rolls random dictionary words and the name engine builds them; no model
is asked. Pins keep a part through a reroll."""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from talemate.languages.models import GeneratorDef, Language, NamePart, NameShape
from talemate.languages.name_grammar import (
    Built,
    MeaningPhrase,
    build_phrase,
    lookup_word,
    real_words,
)

__all__ = [
    "MISSING_RULE",
    "PartRoll",
    "random_phrase",
    "roll_composed",
    "roll_parts",
]

# what a part naming a rule that doesn't exist (or loops) shows
MISSING_RULE = "(missing rule)"
# how deep composed rules may name each other before a part is "missing"
MAX_DEPTH = 4
ROLLS = 8


class PartRoll(BaseModel):
    """One part of a composed rule, with its rolls (a pinned part's only
    roll is its text)."""

    index: int
    kind: str
    label: str
    rolls: list[Built] = Field(default_factory=list)
    pinned: bool = False


def _generator(language: Language, rule_id: str) -> GeneratorDef | None:
    return next((g for g in language.generators if g.id == rule_id), None)


def _pick_shape(generator: GeneratorDef, rng: random.Random) -> int:
    weights = [max(1, shape.weight) for shape in generator.shapes]
    return rng.choices(range(len(generator.shapes)), weights=weights)[0]


def _label(language: Language, part: NamePart) -> str:
    if part.label:
        return part.label
    if part.kind == "word":
        return "fixed"
    if part.kind == "rule":
        target = _generator(language, part.rule)
        return target.name if target is not None else MISSING_RULE
    label = "a description" if part.slot == "describing_noun" else "a meaning"
    if part.of:
        label += " · of"
    if "more_than_one" in part.forms:
        label += " · plural"
    if "the" in part.forms:
        label += " · the"
    if part.ending:
        label += f" · {part.ending}"
    return label


def random_phrase(
    language: Language, part: NamePart, rng: random.Random
) -> tuple[MeaningPhrase, dict[str, str]] | None:
    """A random meaning for `part` from the dictionary: a noun (a word
    marked noun, or not marked), with a describing word for a
    `describing_noun` slot; the part's forms, "of", joining and ending
    set. None when the dictionary has no such words."""

    def meaning(entry) -> str:
        return (entry.meanings[0] if entry.meanings else entry.word).strip().lower()

    nouns = real_words(language, "noun")
    if not nouns:
        return None
    noun = rng.choice(nouns)
    words = {meaning(noun): noun.word}
    describing: list[str] = []
    if part.slot == "describing_noun":
        adjectives = [
            e for e in real_words(language, "adjective") if e.part == "adjective"
        ]
        if adjectives:
            adjective = rng.choice(adjectives)
            describing = [meaning(adjective)]
            words[describing[0]] = adjective.word
    phrase = MeaningPhrase(
        noun=meaning(noun),
        describing=describing,
        of=part.of,
        the="the" in part.forms,
        more_than_one="more_than_one" in part.forms,
        joined=part.joined,
        ending=part.ending,
    )
    return phrase, words


def _roll_rule(
    language: Language,
    rule_id: str,
    count: int,
    rng: random.Random,
    exclude: frozenset[str],
    depth: int,
) -> list[str]:
    """Names from another rule; a missing rule, or one too deep (a loop),
    gives `MISSING_RULE`."""

    from talemate.languages.generator import roll

    target = _generator(language, rule_id)
    if target is None or depth >= MAX_DEPTH:
        return [MISSING_RULE]
    if target.shapes:
        return roll_composed(language, target, count, rng, exclude, depth=depth + 1)
    return roll(language, rule_id, count=count, rng=rng, exclude=set(exclude))


def _roll_part(
    language: Language,
    part: NamePart,
    count: int,
    rng: random.Random,
    exclude: frozenset[str],
    depth: int,
) -> list[Built]:
    if part.kind == "word":
        entry = lookup_word(language, part.word)
        meaning = entry.meanings[0] if entry is not None and entry.meanings else ""
        said = [
            {"word": part.word.lower(), "meaning": meaning, "new": False, "steps": []}
        ]
        return [Built(text=part.word, parts=said if meaning else [])]
    if part.kind == "rule":
        names = _roll_rule(language, part.rule, count, rng, exclude, depth)
        return [Built(text=name) for name in names]
    built: dict[str, Built] = {}
    for _ in range(count * 6):
        if len(built) >= count:
            break
        found = random_phrase(language, part, rng)
        if found is None:
            break
        phrase, words = found
        name = build_phrase(language, phrase, words)
        built.setdefault(name.text.lower(), name)
    return list(built.values())


def roll_parts(
    language: Language,
    rule_id: str,
    *,
    count: int = ROLLS,
    pinned: dict[int, str] | None = None,
    shape: int | None = None,
    rng: random.Random | None = None,
    exclude: frozenset[str] = frozenset(),
) -> tuple[int, list[PartRoll]]:
    """The rule's shape (picked by weight unless given) and each part's
    rolls. A pinned (or typed) part's only roll is its text; a pin holds
    only where the shape has a part, not a fixed word, at its index. A
    plain pattern rule is one part, itself."""

    rng = rng if rng is not None else random.Random()
    generator = _generator(language, rule_id)
    if generator is None:
        raise ValueError(f"no name rule {rule_id!r}")
    if generator.shapes:
        if shape is None or not 0 <= shape < len(generator.shapes):
            shape = _pick_shape(generator, rng)
        parts = generator.shapes[shape].parts
    else:
        shape = 0
        parts = [NamePart(kind="rule", rule=rule_id, label=generator.name)]
    out: list[PartRoll] = []
    for index, part in enumerate(parts):
        text = (pinned or {}).get(index)
        label = _label(language, part)
        if text and part.kind != "word":
            out.append(
                PartRoll(
                    index=index,
                    kind=part.kind,
                    label=label,
                    rolls=[Built(text=text)],
                    pinned=True,
                )
            )
            continue
        rolls = _roll_part(language, part, count, rng, exclude, 0)
        out.append(PartRoll(index=index, kind=part.kind, label=label, rolls=rolls))
    return shape, out


def _shape_name(
    language: Language,
    shape: NameShape,
    rng: random.Random,
    exclude: frozenset[str],
    depth: int,
) -> str:
    texts: list[str] = []
    for part in shape.parts:
        if part.optional and rng.random() < 0.5:
            continue
        rolls = _roll_part(language, part, 1, rng, exclude, depth)
        if rolls:
            texts.append(rolls[0].text)
    return " ".join(t for t in texts if t)


def roll_composed(
    language: Language,
    generator: GeneratorDef,
    count: int,
    rng: random.Random,
    exclude: frozenset[str] | set[str] = frozenset(),
    depth: int = 0,
) -> list[str]:
    """Up to `count` whole names from a composed rule: each part's first
    roll, optional parts kept half the time, none of them in `exclude`."""

    taken = {name.lower() for name in exclude}
    names: list[str] = []
    seen: set[str] = set()
    for _ in range(count * 20):
        if len(names) >= count:
            break
        shape = generator.shapes[_pick_shape(generator, rng)]
        name = _shape_name(language, shape, rng, frozenset(exclude), depth)
        key = name.lower()
        if not name or key in seen or key in taken:
            continue
        seen.add(key)
        names.append(name)
    return names
