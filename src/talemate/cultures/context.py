"""The "Cultures and names" prompt section builder.

This module turns a scene's resolved cultures (`SceneCultures`), its
glossary and its present characters into the single `DynamicInstruction`
text handed to the narrator and actors: where the scene is, how to
handle unwritable languages, a couple of characters' language quirks,
spare names to offer when a new one is needed, names already in use that
must not be reinvented, and a short note per culture.

Everything here is pure: no model calls, no disk access. `build_culture_section`
is the only entry point a later task (the Culture agent) calls; everything
else is exported mainly so tests can exercise it directly.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Callable

from talemate.cultures.models import Culture, GlossaryEntry, Phrase
from talemate.cultures.naming import choose_generator, roll_candidates
from talemate.cultures.scene_context import SceneCultures
from talemate.util import count_tokens

__all__ = [
    "SECTION_TITLE",
    "SPARE_NAMES_PREFIX",
    "TRAIT_VERBS",
    "LanguageTrait",
    "SpareName",
    "CultureSection",
    "language_traits",
    "pick_phrases",
    "build_culture_section",
]

SECTION_TITLE = "Cultures and names"
SPARE_NAMES_PREFIX = "If you need a new name, use one of these:"

# Verbs/words scanned for in free text to spot a character's language
# quirk. The regex alternation below also includes "speaks"/"speak",
# which map to `stem=None` (plain "speaks <language>" mentions) rather
# than one of these stems.
TRAIT_VERBS: dict[str, tuple[str, ...]] = {
    "curse": (
        "curse",
        "curses",
        "cursing",
        "swear",
        "swears",
        "swearing",
        "cuss",
        "cusses",
    ),
    "saying": (
        "bless",
        "blesses",
        "pray",
        "prays",
        "proverb",
        "proverbs",
        "saying",
        "sayings",
    ),
    "greet": ("greet", "greets", "greeting", "greetings"),
}

# Words that mean "food or a meal is being discussed", for the culture
# notes part.
_FOOD_WORDS = (
    "eat",
    "ate",
    "food",
    "meal",
    "dish",
    "drink",
    "supper",
    "breakfast",
    "feast",
    "tavern",
    "inn",
    "kitchen",
)

_FOOD_WORDS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in _FOOD_WORDS) + r")\b",
    re.IGNORECASE,
)


@dataclass
class LanguageTrait:
    character_name: str
    culture_id: str
    stem: str | None
    verb: str


@dataclass
class SpareName:
    text: str
    culture_id: str
    generator_id: str


@dataclass
class CultureSection:
    text: str
    tokens: int
    spares: list[SpareName] = field(default_factory=list)


def _first_sentence(text: str) -> str:
    """Return the first sentence of `text` (up to and including its
    terminating `.`, `!` or `?`), or the whole (stripped) text if it has
    none."""

    stripped = text.strip()
    match = re.search(r"[^.!?]*[.!?]", stripped)
    if match:
        return match.group(0).strip()
    return stripped


def _verb_stem(verb: str) -> str | None:
    lowered = verb.lower()
    for stem, verbs in TRAIT_VERBS.items():
        if lowered in verbs:
            return stem
    return None


def _name_alternation(cultures: dict[str, Culture]) -> tuple[str, dict[str, str]]:
    """Build a regex alternation of every culture's language and own name.

    Returns the alternation string and a mapping of lowercased name to the
    culture's id.
    """

    name_to_culture: dict[str, str] = {}
    for culture in cultures.values():
        for name in (culture.language.name, culture.name):
            if name:
                name_to_culture[name.lower()] = culture.id

    name_alt = "|".join(re.escape(name) for name in name_to_culture)
    return name_alt, name_to_culture


def language_traits(character, cultures: dict[str, Culture]) -> list[LanguageTrait]:
    """Scan `character`'s text fields for language quirk mentions.

    Looks across `description`, `dialogue_instructions`, and the values of
    `base_attributes` and `details`. Two independent patterns are tried:
    a verb (one of `TRAIT_VERBS`) followed by "in <language or culture
    name>" gives that verb's stem; a plain "speaks <language or culture
    name>" (no verb from `TRAIT_VERBS`) gives `stem=None`.
    """

    if not cultures:
        return []

    name_alt, name_to_culture = _name_alternation(cultures)
    if not name_alt:
        return []

    verbs: list[str] = []
    for group in TRAIT_VERBS.values():
        verbs.extend(group)
    verb_alt = "|".join(re.escape(verb) for verb in verbs)

    general_pattern = re.compile(
        rf"\b({verb_alt})\b[^.\n]{{0,24}}?\bin ({name_alt})\b",
        re.IGNORECASE,
    )
    speak_pattern = re.compile(rf"\bspeaks?\s+({name_alt})\b", re.IGNORECASE)

    texts: list[str] = [
        character.description or "",
        character.dialogue_instructions or "",
    ]
    texts.extend(str(value) for value in character.base_attributes.values())
    texts.extend(str(value) for value in character.details.values())

    traits: list[LanguageTrait] = []
    for text in texts:
        if not text:
            continue

        for match in general_pattern.finditer(text):
            verb = match.group(1).lower()
            name = match.group(2).lower()
            culture_id = name_to_culture.get(name)
            if culture_id is None:
                continue
            traits.append(
                LanguageTrait(
                    character_name=character.name,
                    culture_id=culture_id,
                    stem=_verb_stem(verb),
                    verb=verb,
                )
            )

        for match in speak_pattern.finditer(text):
            name = match.group(1).lower()
            culture_id = name_to_culture.get(name)
            if culture_id is None:
                continue
            traits.append(
                LanguageTrait(
                    character_name=character.name,
                    culture_id=culture_id,
                    stem=None,
                    verb="speaks",
                )
            )

    return traits


def pick_phrases(culture: Culture, stem: str | None, limit: int = 3) -> list[Phrase]:
    """Pick up to `limit` phrases from `culture`'s language for `stem`.

    With a `stem`, phrases whose `category.lower()` starts with it (so
    "curse" matches both "curse" and "curses"). With `stem=None`, the
    first phrase of each distinct category, up to `limit`.
    """

    phrases = culture.language.phrases

    if stem is None:
        seen: set[str] = set()
        picked: list[Phrase] = []
        for phrase in phrases:
            category = phrase.category.lower()
            if category in seen:
                continue
            seen.add(category)
            picked.append(phrase)
            if len(picked) >= limit:
                break
        return picked

    stem_lower = stem.lower()
    matching = [
        phrase for phrase in phrases if phrase.category.lower().startswith(stem_lower)
    ]
    return matching[:limit]


def _join_and(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _build_place_part(scene: SceneCultures) -> list[str]:
    if scene.place is not None:
        text = f"The scene is in {scene.place.name}."
        if scene.description:
            text += f" {scene.description}"
        return [text]

    if scene.cultures:
        names = _join_and([culture.name for culture in scene.cultures])
        return [f"Cultures here: {names}."]

    return []


def _build_unwritable_part(
    scene: SceneCultures, glossary: list[GlossaryEntry]
) -> list[str]:
    if not scene.cultures:
        return []

    local_culture = scene.cultures[0]
    lines: list[str] = []

    for culture in scene.cultures:
        if culture.language.writable:
            continue

        sound = _first_sentence(culture.language.sound)
        lines.append(
            f"{culture.name} speech can't be written in letters. "
            f"Describe how it sounds ({sound}) and never spell it out."
        )

        renderings: list[str] = []
        for entry in glossary:
            if entry.language != culture.id:
                continue
            rendering = entry.renderings.get(local_culture.id)
            if not rendering:
                continue
            label = entry.true_name or entry.text
            renderings.append(f"{label} → {rendering}")

        if renderings:
            lines.append(
                f"Call {culture.name} things by these names: "
                + ", ".join(renderings)
                + "."
            )

    return lines


def _build_traits_part(
    scene: SceneCultures, characters: list, cultures: dict[str, Culture]
) -> list[str]:
    lines: list[str] = []

    for character in characters:
        if len(lines) >= 2:
            break

        traits = language_traits(character, cultures)
        if not traits:
            continue

        trait = traits[0]
        culture = cultures.get(trait.culture_id)
        if culture is None:
            continue

        phrases = pick_phrases(culture, trait.stem, limit=3)
        line = f"{character.name} {trait.verb} in {culture.language.name}."
        if phrases:
            phrase_text = "; ".join(
                f"“{phrase.original}” ({phrase.translation})" for phrase in phrases
            )
            line += f" Use these exact phrases: {phrase_text}."
        lines.append(line)

    return lines


def _build_spares_part(
    scene: SceneCultures,
    cultures: dict[str, Culture],
    glossary: list[GlossaryEntry],
    rng: random.Random,
) -> tuple[list[str], list[SpareName]]:
    exclude = {entry.text.lower() for entry in glossary}

    shares = sorted(scene.mix, key=lambda share: -share.share)
    qualifying = [share for share in shares if share.share >= 25][:2]

    lines = [SPARE_NAMES_PREFIX]
    spares: list[SpareName] = []

    for share in qualifying:
        culture = cultures.get(share.culture_id)
        if culture is None:
            continue

        segments: list[str] = []

        people_generator = choose_generator(culture.language, None, rng)
        if people_generator is not None:
            names = roll_candidates(culture.language, people_generator, 3, exclude, rng)
            if names:
                segments.append(f"People ({culture.name}): {', '.join(names)}.")
                spares.extend(
                    SpareName(
                        text=name,
                        culture_id=culture.id,
                        generator_id=people_generator.id,
                    )
                    for name in names
                )

        places_generator = next(
            (gen for gen in culture.language.generators if gen.use == "places"), None
        )
        if places_generator is not None:
            names = roll_candidates(culture.language, places_generator, 3, exclude, rng)
            if names:
                segments.append(f"Places ({culture.name}): {', '.join(names)}.")
                spares.extend(
                    SpareName(
                        text=name,
                        culture_id=culture.id,
                        generator_id=places_generator.id,
                    )
                    for name in names
                )

        if segments:
            lines.append(" ".join(segments))

    if len(lines) == 1:
        # Nothing but the prefix: no culture had a usable generator.
        return [], []

    return lines, spares


def _build_names_in_use_part(
    scene: SceneCultures,
    cultures: dict[str, Culture],
    glossary: list[GlossaryEntry],
    characters: list,
) -> list[str]:
    character_names = {character.name for character in characters}

    # `scene.place`'s id plus every ancestor up to the root, so a place
    # between the matched place and the one that supplied the culture mix
    # (which may have no cultures of its own) is still covered.
    place_ids: set[str] = set(scene.ancestor_ids)

    entries: list[GlossaryEntry] = []
    for entry in glossary:
        if entry.character_name and entry.character_name in character_names:
            entries.append(entry)
        elif entry.place_id and entry.place_id in place_ids:
            entries.append(entry)

        if len(entries) >= 12:
            break

    if not entries:
        return []

    labels: list[str] = []
    for entry in entries:
        if entry.kind == "place":
            labels.append(f"{entry.text} (place)")
            continue

        culture = cultures.get(entry.language) if entry.language else None
        language_name = culture.name if culture is not None else entry.language
        labels.append(f"{entry.text} ({language_name}, {entry.kind})")

    return [f"Names already in use, keep them exactly: {', '.join(labels)}."]


def _top_customs(customs: list[str], recent_text: str, limit: int = 2) -> list[str]:
    recent_words = set(re.findall(r"\w+", recent_text.lower()))

    scored = []
    for index, custom in enumerate(customs):
        custom_words = set(re.findall(r"\w+", custom.lower()))
        overlap = len(custom_words & recent_words)
        scored.append((-overlap, index, custom))
    scored.sort()

    return [custom for _, _, custom in scored[:limit]]


def _build_notes_part(scene: SceneCultures, recent_text: str) -> list[str]:
    lines: list[str] = []
    recent_lower = recent_text.lower()

    for culture in scene.cultures:
        description = _first_sentence(culture.description)
        sound = _first_sentence(culture.language.sound)
        lines.append(
            f"{culture.name}: {description} Their language, {culture.language.name}, {sound}"
        )

        for custom in _top_customs(culture.customs, recent_text):
            lines.append(custom)

        if culture.food and _FOOD_WORDS_RE.search(recent_text):
            lines.append(culture.food)

        for holiday in culture.holidays:
            name_hit = bool(holiday.name) and holiday.name.lower() in recent_lower
            when_hit = bool(holiday.when) and holiday.when.lower() in recent_lower
            if not (name_hit or when_hit):
                continue
            if holiday.when:
                lines.append(f"{holiday.name} ({holiday.when}): {holiday.description}")
            else:
                lines.append(f"{holiday.name}: {holiday.description}")

    return lines


def _cut_to_budget_by_words(
    text: str, budget: int, count_tokens_fn: Callable[[str], int]
) -> str:
    words = text.split()
    while words and count_tokens_fn(" ".join(words)) > budget:
        words.pop()
    return " ".join(words)


def _fit_part(
    existing_lines: list[str],
    part_lines: list[str],
    budget: int,
    count_tokens_fn: Callable[[str], int],
) -> list[str]:
    remaining = list(part_lines)
    while remaining:
        candidate = "\n".join(existing_lines + remaining)
        if count_tokens_fn(candidate) <= budget:
            return remaining
        remaining = remaining[:-1]
    return []


def build_culture_section(
    *,
    scene: SceneCultures,
    cultures: dict[str, Culture],
    glossary: list[GlossaryEntry],
    characters: list,
    recent_text: str,
    budget: int,
    rng: random.Random,
    count_tokens=count_tokens,
) -> CultureSection:
    """Build the "Cultures and names" prompt section text, trimmed to `budget`."""

    if not scene.cultures:
        return CultureSection("", 0, [])

    lines: list[str] = []

    place_lines = _build_place_part(scene)
    place_text = place_lines[0] if place_lines else ""
    if count_tokens(place_text) > budget:
        place_text = _cut_to_budget_by_words(place_text, budget, count_tokens)
    lines.append(place_text)

    spares_part, spare_candidates = _build_spares_part(scene, cultures, glossary, rng)

    for part_lines in (
        _build_unwritable_part(scene, glossary),
        _build_traits_part(scene, characters, cultures),
        spares_part,
        _build_names_in_use_part(scene, cultures, glossary, characters),
        _build_notes_part(scene, recent_text),
    ):
        fitted = _fit_part(lines, part_lines, budget, count_tokens)
        if fitted:
            lines.extend(fitted)

    # Collect the spares that actually made it into the final text, now
    # that every part has been trimmed.
    text = "\n".join(lines)
    included_spares = [
        spare
        for spare in spare_candidates
        if re.search(r"\b" + re.escape(spare.text) + r"\b", text)
    ]

    return CultureSection(text=text, tokens=count_tokens(text), spares=included_spares)
