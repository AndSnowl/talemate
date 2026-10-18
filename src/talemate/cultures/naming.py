"""Naming choices for the Culture agent: culture guesses, generator and
candidate selection, and matching a model's free-text answer back to a
rolled candidate.

These are pure functions; the Culture agent (a later task) is the only
caller that talks to a model or touches scene/world state. Everything
here takes plain data in and returns plain data out.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from talemate.cultures.generator import GeneratorError, name_fits, roll
from talemate.cultures.models import Culture, GeneratorDef, Language
from talemate.cultures.scene_context import SceneCultures
from talemate.cultures.words import clean_name

__all__ = [
    "CultureGuess",
    "guess_culture",
    "guess_culture_for_name",
    "infer_gender",
    "choose_generator",
    "roll_candidates",
    "match_candidate",
]


@dataclass
class CultureGuess:
    culture_id: str | None
    unsure: bool
    reason: str


# Words counted by `infer_gender`, in the exact lists from the brief.
_FEMALE_WORDS = (
    "she her woman girl daughter mother wife lady queen widow sister fishwife priestess"
).split()
_MALE_WORDS = ("he his man boy son father husband lord king brother").split()


def _whole_word_in(candidate: str, text: str) -> bool:
    if not candidate:
        return False
    pattern = re.compile(r"\b" + re.escape(candidate) + r"\b", re.IGNORECASE)
    return pattern.search(text) is not None


def _count_whole_words(text: str, words: list[str]) -> int:
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(word) for word in words) + r")\b",
        re.IGNORECASE,
    )
    return len(pattern.findall(text))


def _weighted_pick(mix, rng: random.Random):
    total = sum(share.share for share in mix)
    threshold = rng.uniform(0, total)
    upto = 0.0
    for share in mix:
        upto += share.share
        if threshold <= upto:
            return share
    return mix[-1]


def _guess_from_characters(scene: SceneCultures) -> CultureGuess:
    """Rules 3 and 4 of `guess_culture`: the most common culture among the
    character cultures in `scene.cultures`, or `None` if there are none."""

    if not scene.cultures:
        return CultureGuess(None, True, "no culture here")

    counts = Counter(culture.id for culture in scene.cultures)
    culture_id, _ = counts.most_common(1)[0]
    return CultureGuess(culture_id, True, "from the people around them")


def guess_culture(
    cultures: dict[str, Culture],
    scene: SceneCultures,
    text: str,
    rng: random.Random,
) -> CultureGuess:
    """Guess the culture of a new character being named, from `text`."""

    for culture in cultures.values():
        if _whole_word_in(culture.name, text) or _whole_word_in(
            culture.language.name, text
        ):
            return CultureGuess(culture.id, False, "named in the description")

    if scene.mix:
        picked = _weighted_pick(scene.mix, rng)
        unsure = picked.share < 70
        reason = f"picked from the {scene.mix_source.name} mix"
        return CultureGuess(picked.culture_id, unsure, reason)

    return _guess_from_characters(scene)


def guess_culture_for_name(
    cultures: dict[str, Culture],
    scene: SceneCultures,
    name: str,
) -> CultureGuess:
    """Guess the culture of a name that already exists.

    Only cultures with generators (among `scene.cultures`) are considered.
    """

    candidates = [culture for culture in scene.cultures if culture.language.generators]
    fitting = [culture for culture in candidates if name_fits(culture.language, name)]

    if len(fitting) == 1:
        return CultureGuess(fitting[0].id, False, "fits its language")

    if scene.mix:
        if fitting:
            fitting_ids = {culture.id for culture in fitting}
            matches = [share for share in scene.mix if share.culture_id in fitting_ids]
            if matches:
                best = max(matches, key=lambda share: share.share)
                return CultureGuess(
                    best.culture_id, True, "fits several; picked by mix share"
                )
            return CultureGuess(fitting[0].id, True, "fits several")

        dominant = max(scene.mix, key=lambda share: share.share)
        return CultureGuess(dominant.culture_id, True, "no language fits the name")

    return _guess_from_characters(scene)


def infer_gender(text: str) -> Literal["female", "male"] | None:
    """Guess a gender from whole-word hits of two fixed word lists."""

    female_count = _count_whole_words(text, _FEMALE_WORDS)
    male_count = _count_whole_words(text, _MALE_WORDS)

    if female_count > male_count:
        return "female"
    if male_count > female_count:
        return "male"
    return None


def _contains(generator: GeneratorDef, word: str) -> bool:
    return word in generator.id.lower() or word in generator.name.lower()


def choose_generator(
    language: Language,
    gender: Literal["female", "male"] | None,
    rng: random.Random,
) -> GeneratorDef | None:
    """Pick a `people`-use generator from `language`, by `gender`."""

    candidates = [
        generator
        for generator in language.generators
        if generator.use == "people"
        and not _contains(generator, "family")
        and not _contains(generator, "surname")
    ]
    if not candidates:
        return None

    female = [generator for generator in candidates if _contains(generator, "female")]
    male = [
        generator
        for generator in candidates
        if _contains(generator, "male") and not _contains(generator, "female")
    ]
    neutral = [
        generator
        for generator in candidates
        if not _contains(generator, "male") and not _contains(generator, "female")
    ]

    if gender == "female":
        if female:
            return female[0]
        if neutral:
            return neutral[0]
        return None

    if gender == "male":
        if male:
            return male[0]
        if neutral:
            return neutral[0]
        return None

    if neutral:
        return neutral[0]
    return rng.choice(candidates)


def roll_candidates(
    language: Language,
    generator: GeneratorDef,
    count: int,
    exclude: set[str],
    rng: random.Random,
) -> list[str]:
    """Roll up to `count` candidate names, or `[]` on a `GeneratorError`."""

    try:
        return roll(language, generator.id, count=count, rng=rng, exclude=exclude)
    except GeneratorError:
        return []


def match_candidate(response: str, candidates: list[str]) -> str | None:
    """Match a model's free-text `response` to one of `candidates`.

    Returns the candidate's own spelling, or `None`.
    """

    first_line = response.splitlines()[0] if response else ""
    cleaned = clean_name(first_line)
    if cleaned:
        for candidate in candidates:
            if cleaned.lower() == candidate.lower():
                return candidate

    best_candidate: str | None = None
    best_pos: int | None = None
    for candidate in candidates:
        pattern = re.compile(r"\b" + re.escape(candidate) + r"\b", re.IGNORECASE)
        match = pattern.search(response)
        if match is not None and (best_pos is None or match.start() < best_pos):
            best_pos = match.start()
            best_candidate = candidate

    return best_candidate
