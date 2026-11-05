"""The shared check every language goes through, whatever made it: an
import, the in-app model, the language-design skill or a hand edit
(languages part 3 design, "The file format and import").

- **Blocking:** an invalid file, or a name rule (generator) that can't be
  read. Nothing else stops an import.
- **Fit (a warning):** the dictionary's words against the language's word
  generator. A word made of two or more of the language's own fitting
  words (vel + garo) counts as fitting. Skipped for English-part naming
  styles (their parts are real English on purpose) and for a language with
  no word rules.
- **Real words (a warning):** for a `russian` flavour, the dictionary and
  the sample names, word by word, against the real Russian list (stemmed,
  as the probe did); for an English-part style, whole sample names against
  the real English place names; any other flavour is skipped.

Plain words throughout: the report is read by the owner and pasted back to
whichever assistant made the language.
"""

from __future__ import annotations

import random
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from talemate.languages.completeness import Completeness, completeness
from talemate.languages.generator import fits, roll, validate_language
from talemate.languages.name_grammar import parse_condition
from talemate.languages.models import Language

__all__ = [
    "CheckReport",
    "check_language",
    "is_part_style",
    "needs_repair",
    "repair_note",
    "stem",
]

_DATA = Path(__file__).resolve().parent / "data" / "real_words"
_LONG_ENDINGS = ("ov", "ev", "in")
_VOWELS = "aoyieu"


class CheckReport(BaseModel):
    blocking: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fit_share: float | None = None
    fit_skipped_reason: str | None = None
    real_hits: list[str] = Field(default_factory=list)
    real_skipped_reason: str | None = None
    unfit_words: list[str] = Field(default_factory=list)
    dictionary_size: int = 0
    samples: dict[str, list[str]] = Field(default_factory=dict)
    # what a full language is still missing (never blocks or repairs)
    completeness: Completeness | None = None

    @property
    def ok(self) -> bool:
        """Nothing blocks it."""
        return not self.blocking


def stem(word: str) -> str:
    """`word` lower-cased, with one crude ending cut: "ov"/"ev"/"in" from a
    word of five letters or more, else a final vowel from one of four or
    more (the language probe's stemming)."""
    word = word.lower()
    if len(word) >= 5 and word.endswith(_LONG_ENDINGS):
        return word[:-2]
    if len(word) >= 4 and word[-1] in _VOWELS:
        return word[:-1]
    return word


@lru_cache(maxsize=None)
def _real_words(flavour: str) -> tuple[str, ...] | None:
    path = _DATA / f"{flavour}.txt"
    if not flavour or not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    return tuple(
        line.strip() for line in lines if line.strip() and not line.startswith("#")
    )


def is_part_style(language: Language) -> bool:
    """A naming style made of English word parts (Duskhollow)."""
    return language.flavour == "english"


def _words_of(name: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", name)


def _compound(word: str, parts: frozenset[str]) -> bool:
    """Whether `word` splits into two or more of `parts`."""
    n = len(word)
    # ways[i]: the fewest parts word[:i] splits into (0 for the empty start)
    ways: list[int | None] = [0] + [None] * n
    for i in range(1, n + 1):
        for j in range(i):
            if ways[j] is not None and word[j:i] in parts:
                count = ways[j] + 1
                if ways[i] is None or count > ways[i]:
                    ways[i] = count
    return ways[n] is not None and ways[n] >= 2


def _check_fit(language: Language, report: CheckReport) -> None:
    if is_part_style(language):
        report.fit_skipped_reason = "a naming style made of English words"
        return
    word_gen = language.word_generator()
    if word_gen is None:
        report.fit_skipped_reason = "no word rules"
        return
    words_only = language.model_copy(update={"generators": [word_gen]})
    words = [entry.word for entry in language.dictionary]
    if not words:
        return
    fitting = {w.lower() for w in words if fits(words_only, w)}
    parts = frozenset(fitting)
    unfit = [
        w
        for w in words
        if w.lower() not in fitting and not _compound(w.lower(), parts - {w.lower()})
    ]
    report.unfit_words = unfit
    report.fit_share = (len(words) - len(unfit)) / len(words)
    if unfit:
        shown = ", ".join(unfit[:12]) + (" …" if len(unfit) > 12 else "")
        report.warnings.append(
            f"{len(unfit)} of {len(words)} words don't follow the language's own "
            f"word rules: {shown}"
        )


def _check_real(language: Language, report: CheckReport) -> None:
    real = _real_words(language.flavour)
    if real is None:
        report.real_skipped_reason = (
            "no list of real words for this flavour"
            if language.flavour
            else "no flavour set"
        )
        return
    samples = [name for names in report.samples.values() for name in names]
    if is_part_style(language):
        places = {name.lower() for name in real}
        hits = [name for name in samples if name.lower() in places]
        what = "sample names are real places"
    else:
        exact = {w.lower() for w in real}
        stems = {stem(w) for w in real}

        def is_real(text: str) -> bool:
            return any(w.lower() in exact or stem(w) in stems for w in _words_of(text))

        words = [entry.word for entry in language.dictionary]
        examples = [
            example.original
            for section in language.grammar
            for example in section.examples
        ]
        hits = [text for text in words + examples + samples if is_real(text)]
        what = "words or sample names are real"
    report.real_hits = list(dict.fromkeys(hits))
    if report.real_hits:
        shown = ", ".join(report.real_hits[:12]) + (
            " …" if len(report.real_hits) > 12 else ""
        )
        report.warnings.append(f"{len(report.real_hits)} {what}: {shown}")


def _name_grammar_problems(language: Language) -> list[str]:
    """What can't be read in the grammar for names and the composed rules
    (languages 4b-1): a condition no one knows, a part naming no rule, a
    rule with neither patterns nor parts."""

    problems: list[str] = []
    grammar = language.name_grammar
    if grammar is not None:
        changes = [*grammar.the, *grammar.more_than_one]
        changes += [c for ending in grammar.endings for c in ending.changes]
        for change in changes:
            try:
                parse_condition(change.when)
            except ValueError as exc:
                problems.append(f"The grammar for names can't be read: {exc}")
    ids = {g.id for g in language.generators}
    endings = (
        {e.meaning.strip().lower() for e in grammar.endings}
        if grammar is not None
        else set()
    )
    for generator in language.generators:
        if not generator.patterns and not generator.shapes:
            problems.append(f"The name rule {generator.id!r} has no patterns or parts")
        for shape in generator.shapes:
            for part in shape.parts:
                if part.ending and part.ending.strip().lower() not in endings:
                    problems.append(
                        f"The name rule {generator.id!r} uses an ending the "
                        f"grammar for names doesn't have: {part.ending!r}"
                    )
                if part.kind == "rule" and part.rule not in ids:
                    problems.append(
                        f"The name rule {generator.id!r} uses a rule that "
                        f"doesn't exist: {part.rule!r}"
                    )
    return problems


def _people_names_problems(language: Language) -> list[str]:
    """What's off in people's names (languages 4b-2), as warnings: a
    connection part with no role words, an own part taking nothing, a
    choice the language doesn't list, an address row using a part no
    people rule has."""

    problems: list[str] = []
    choices = language.people_names.choices if language.people_names else {}
    labels: set[str] = set()

    def unknown(where: str, wanted: dict[str, str]) -> None:
        if not choices:
            return
        for key, value in wanted.items():
            if key not in choices:
                problems.append(
                    f"{where} is for a choice the language doesn't list: {key!r}"
                )
            elif value not in choices[key]:
                problems.append(
                    f"{where} is for {key} {value!r}, which isn't one of {choices[key]}"
                )

    for generator in language.generators:
        unknown(f"The name rule {generator.id!r}", generator.for_person)
        for shape in generator.shapes:
            for part in shape.parts:
                if part.label:
                    labels.add(part.label)
                if part.kind == "connection" and not part.roles:
                    problems.append(
                        f"The name rule {generator.id!r} takes from a connection "
                        "but names no roles"
                    )
                if part.kind == "own" and not part.take:
                    problems.append(
                        f"The name rule {generator.id!r} has an own part that "
                        "doesn't say which part to take"
                    )
                for form in part.person_forms:
                    unknown(f"A form in the name rule {generator.id!r}", form.when)
    if language.people_names is not None:
        known = labels | {"title", "pet name"}
        for row in language.people_names.address:
            for use in row.uses:
                if use not in known:
                    problems.append(
                        f"The address row {row.kind!r} uses {use!r}, which no "
                        "people rule has"
                    )
    return problems


def check_language(
    language: Language, *, samples: int = 20, seed: int = 0
) -> CheckReport:
    """Check `language`: what blocks it, what's worth fixing, and sample
    names per generator."""
    report = CheckReport(dictionary_size=len(language.dictionary))
    # problems in the grammar for names block, but every rule's samples
    # are still rolled (final review I3)
    grammar_problems = _name_grammar_problems(language)
    try:
        validate_language(language)
    except Exception as exc:  # GeneratorError, or a bad regex reaching it
        report.blocking.append(f"A name rule can't be read: {exc}")
        return report
    rng = random.Random(seed)
    for generator in language.generators:
        try:
            report.samples[generator.id] = roll(
                language, generator.id, count=samples, rng=rng
            )
        except Exception as exc:
            report.blocking.append(
                f"The name rule {generator.id!r} can't make names: {exc}"
            )
    report.blocking.extend(grammar_problems)
    report.warnings.extend(_people_names_problems(language))
    if report.blocking:
        return report
    _check_fit(language, report)
    _check_real(language, report)
    if language.level == "full":
        report.completeness = completeness(language)
    return report


def needs_repair(report: CheckReport) -> bool:
    """Worth sending back: something blocks, or more than a third of the
    words don't follow the language's own rules."""
    if report.blocking:
        return True
    return bool(report.dictionary_size) and (
        len(report.unfit_words) > report.dictionary_size / 3
    )


def repair_note(report: CheckReport) -> str:
    """A plain note on what's wrong, to read or paste back to the assistant
    that made the language: blocking problems first."""
    lines: list[str] = []
    if report.blocking:
        lines.append("These must be fixed before the language can be imported:")
        lines += [f"- {problem}" for problem in report.blocking]
    if report.warnings:
        if lines:
            lines.append("")
        lines.append("Worth fixing:")
        lines += [f"- {warning}" for warning in report.warnings]
    if not lines:
        lines.append("No problems found.")
    lines += _still_to_fill_in(report.completeness)
    return "\n".join(lines)


def _still_to_fill_in(found: Completeness | None) -> list[str]:
    if found is None:
        return []
    parts = []
    if found.meanings_missing:
        shown = ", ".join(found.meanings_missing[:12])
        more = " …" if len(found.meanings_missing) > 12 else ""
        parts.append(
            f"- Everyday and structural words: {len(found.meanings_missing)} of "
            f"{found.meanings_total} missing ({shown}{more})"
        )
    if found.phrase_categories_missing:
        parts.append(f"- Phrases: no {', '.join(found.phrase_categories_missing)}")
    if found.grammar_topics_missing:
        parts.append(
            f"- Grammar: {', '.join(found.grammar_topics_missing)} not written"
        )
    return ["", "Still to fill in:", *parts] if parts else []
