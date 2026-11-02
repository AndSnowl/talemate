"""The name engine (languages 4b-1): a language's grammar for names
applied to words. It builds a name from words and a meaning's structure,
in the language's order and forms; no model is ever asked. The rules'
models live in `talemate.languages.models` and are re-exported here."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

from talemate.languages.models import (
    DictionaryEntry,
    Ending,
    FormChange,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)

__all__ = [
    "Built",
    "Ending",
    "FormChange",
    "GrammarRow",
    "MeaningPhrase",
    "NameGrammar",
    "NamePart",
    "NameShape",
    "OfRule",
    "apply_ending",
    "apply_form",
    "build_phrase",
    "grammar_rows",
    "lookup_word",
    "parse_condition",
    "real_words",
    "vowels_of",
]

Form = Literal["the", "more_than_one"]
_FORM_LABELS = {"the": "the", "more_than_one": "more than one"}

# a condition tests a word, the language's vowels, and whether the word
# was made more than one ("plural")
Condition = Callable[..., bool]


def parse_condition(when: str) -> Condition:
    """`when` as a test of a word, the language's vowels and whether the
    word was made more than one: "" always, "after_vowel" and
    "after_consonant" (the word's end), "before_vowel" (its start),
    "plural" (it was made more than one: Drassonais lou, not lo),
    "ends:a|o" (it ends with one of those letters). Raises `ValueError`
    for anything else."""

    when = (when or "").strip()
    if not when:
        return lambda word, vowels, plural=False: True
    if when == "after_vowel":
        return lambda word, vowels, plural=False: (
            bool(word) and word[-1].lower() in vowels
        )
    if when == "after_consonant":
        return lambda word, vowels, plural=False: (
            bool(word) and word[-1].lower() not in vowels
        )
    if when == "before_vowel":
        return lambda word, vowels, plural=False: (
            bool(word) and word[0].lower() in vowels
        )
    if when == "plural":
        return lambda word, vowels, plural=False: plural
    if when.startswith("ends:"):
        endings = tuple(e.strip().lower() for e in when[5:].split("|") if e.strip())
        if endings:
            return lambda word, vowels, plural=False: word.lower().endswith(endings)
    raise ValueError(f"unknown condition: {when!r}")


class MeaningPhrase(BaseModel):
    """What a meaning part says, in English meanings: its main noun, its
    describing words, and whether it's "of" it, "the", more than one,
    joined into one word, or takes a meaningful ending."""

    noun: str
    describing: list[str] = Field(default_factory=list)
    of: bool = False
    the: bool = False
    more_than_one: bool = False
    joined: bool = False
    ending: str = ""


class Built(BaseModel):
    """A name the engine built, with its working: each word, its meaning,
    whether it's new, and the steps applied ("-i more than one")."""

    text: str
    parts: list[dict] = Field(default_factory=list)


class GrammarRow(BaseModel):
    """One rule of a grammar for names in plain words, with an example
    built from it (`error` when it can't build)."""

    key: str
    label: str
    rule: str
    example: str = ""
    error: str = ""


def vowels_of(language: Language) -> frozenset[str]:
    """The language's vowels: its "V" sound group, else a e i o u y."""

    group = (language.categories or {}).get("V", "")
    letters = {
        ch.lower()
        for option in group.split()
        for ch in re.sub(r"\*\d+$", "", option)
        if ch.isalpha()
    }
    return frozenset(letters) or frozenset("aeiouy")


def _first_syllable(word: str, vowels: frozenset[str], coda: bool = False) -> str:
    """The word up to its first vowels ("bu" from bumpa, for doubling);
    with `coda`, one consonant after them too ("bel" from belesh, for a
    clipped first word)."""

    i = 0
    while i < len(word) and word[i].lower() not in vowels:
        i += 1
    while i < len(word) and word[i].lower() in vowels:
        i += 1
    if coda and i < len(word):
        i += 1
    return word[:i]


def _apply_change(change: FormChange, word: str, vowels: frozenset[str]) -> str:
    if change.kind == "ending":
        if not change.text:
            raise ValueError("an ending needs its letters")
        return word + change.text
    if change.kind == "swap":
        for drop in (d for d in change.drop.split("|") if d):
            if word.lower().endswith(drop.lower()):
                return word[: len(word) - len(drop)] + change.text
        return word + change.text
    if change.kind == "word_before":
        if not change.text:
            raise ValueError("a word before needs its letters")
        joined = change.text.endswith(("'", "’", "-"))
        return change.text + word if joined else f"{change.text} {word}"
    if change.kind == "word_after":
        if not change.text:
            raise ValueError("a word after needs its letters")
        return f"{word} {change.text}"
    if change.kind == "double":
        return _first_syllable(word, vowels) + word
    raise ValueError(f"unknown change: {change.kind!r}")


def _apply_changes(
    changes: list[FormChange], vowels: frozenset[str], word: str, plural: bool = False
) -> str:
    """The first change whose condition holds, applied; none: as it is."""

    for change in changes:
        if parse_condition(change.when)(word, vowels, plural):
            return _apply_change(change, word, vowels)
    return word


def apply_form(
    grammar: NameGrammar,
    vowels: frozenset[str],
    word: str,
    form: Form,
    *,
    plural: bool = False,
) -> str:
    """`word` in `form` ("the" or "more_than_one") by `grammar`; `plural`:
    the word was made more than one (for "the" that differs then)."""

    return _apply_changes(getattr(grammar, form), vowels, word, plural)


def _ending(grammar: NameGrammar, meaning: str) -> Ending:
    for ending in grammar.endings:
        if ending.meaning.strip().lower() == meaning.strip().lower():
            return ending
    raise KeyError(meaning)


def apply_ending(
    grammar: NameGrammar, vowels: frozenset[str], word: str, meaning: str
) -> str:
    """`word` with the ending that means `meaning` ("land of")."""

    ending = _ending(grammar, meaning)
    changes = ending.changes or [FormChange(kind="ending", text=ending.ending)]
    return _apply_changes(changes, vowels, word)


def lookup_word(language: Language, meaning: str) -> DictionaryEntry | None:
    """The dictionary entry for `meaning`: a word spelled so first, else
    the first entry (in dictionary order) with that meaning."""

    key = meaning.strip().lower()
    for entry in language.dictionary:
        if entry.word.lower() == key:
            return entry
    for entry in language.dictionary:
        if any(m.strip().lower() == key for m in entry.meanings):
            return entry
    return None


def _capitalise(text: str) -> str:
    def cap(word: str) -> str:
        out = word[:1].upper() + word[1:]
        # an elided word keeps both capitals: L'Auvre
        return re.sub(r"(['’])(\w)", lambda m: m.group(1) + m.group(2).upper(), out)

    return " ".join(cap(w) for w in text.split())


def build_phrase(
    language: Language,
    phrase: MeaningPhrase,
    words: dict[str, str],
    new: frozenset[str] = frozenset(),
) -> Built:
    """`phrase` in `language`, from `words` (each English meaning's word)
    by its grammar for names: the noun's ending and forms ("the" after
    "more than one"), describing words before or after it (or joined into
    it), and "of" as its word or ending. With no grammar, the words go in
    the given order, as in 4a. The of-phrase's `place` isn't used inside
    one part: a composed rule orders its parts."""

    grammar = language.name_grammar
    vowels = vowels_of(language)
    noun = words[phrase.noun]
    noun_part = {"word": noun, "meaning": phrase.noun, "new": noun in new, "steps": []}
    describing = [
        {"word": words[d], "meaning": d, "new": words[d] in new, "steps": []}
        for d in phrase.describing
    ]
    if grammar is None:
        words_in_order = [*(d["word"] for d in describing), noun]
        text = "".join(words_in_order) if phrase.joined else " ".join(words_in_order)
        return Built(text=_capitalise(text), parts=[*describing, noun_part])

    head = noun
    known = {e.meaning.strip().lower() for e in grammar.endings}
    if phrase.ending and phrase.ending.strip().lower() in known:
        head = apply_ending(grammar, vowels, head, phrase.ending)
        noun_part["steps"].append(
            f"-{_ending(grammar, phrase.ending).ending} {phrase.ending}"
        )
    if phrase.joined and describing:
        pieces = [d["word"] for d in describing]
        if grammar.clip_first:
            pieces[0] = _first_syllable(pieces[0], vowels, coda=True)
        joined = "".join(pieces)
        head = joined + head if grammar.joining == "describing_first" else head + joined
        noun_part["steps"].append("joined")
    forms: list[Form] = []
    if phrase.more_than_one:
        forms.append("more_than_one")
    # with "of", "the" is the language's (its of-rule), not the English
    # idiom's: "of the Stars" is Ul Zveski in Varovni
    the = (
        (grammar.of.the if grammar.of is not None else phrase.the)
        if phrase.of
        else phrase.the
    )
    if the:
        forms.append("the")
    for form in forms:
        before = head
        head = apply_form(
            grammar,
            vowels,
            head,
            form,
            plural=form == "the" and phrase.more_than_one,
        )
        if head != before:
            if head.startswith(before):
                step = f"-{head[len(before) :]}"
            elif head.endswith(before):
                step = f"{head[: -len(before)].strip()} before"
            else:
                step = head
            noun_part["steps"].append(f"{step} {_FORM_LABELS[form]}")
    if phrase.joined or not describing:
        text_words = [head]
    elif grammar.describing == "before":
        text_words = [*(d["word"] for d in describing), head]
    else:
        text_words = [head, *(d["word"] for d in describing)]
    parts = (
        [noun_part]
        if phrase.joined
        else (
            [*describing, noun_part]
            if grammar.describing == "before"
            else [noun_part, *describing]
        )
    )
    if phrase.of and grammar.of is not None:
        of = grammar.of
        if of.how == "ending":
            text_words[-1] = text_words[-1] + of.text
            noun_part["steps"].append(f"-{of.text} of")
        else:
            of_part = {"word": of.text, "meaning": "of", "new": False, "steps": []}
            if of.word_side == "before":
                text_words.insert(0, of.text)
                parts.insert(0, of_part)
            else:
                text_words.append(of.text)
                parts.append(of_part)
    return Built(text=_capitalise(" ".join(text_words)), parts=parts)


def _example_noun(language: Language) -> str:
    """A noun for examples: the nouns section's first table caption's
    word ("skelt (stone)"), else the first noun in the dictionary."""

    for section in language.grammar:
        if section.topic == "nouns":
            for table in section.tables:
                found = re.match(r"\s*([^\W\d_][\w'’-]*)", table.caption or "")
                if found:
                    return found.group(1).lower()
    for entry in real_words(language, "noun"):
        return entry.word.lower()
    return ""


def real_words(language: Language, part: str) -> list[DictionaryEntry]:
    """Dictionary words of `part` that are words of their own: one word
    with a meaning (a picked name is saved with none); words marked so
    first, then unmarked ones (final review I4)."""

    words = [e for e in language.dictionary if e.meanings and " " not in e.word.strip()]
    marked = [e for e in words if e.part == part]
    return marked or [e for e in words if not e.part]


def _change_words(changes: list[FormChange]) -> str:
    said = {
        "": "",
        "after_vowel": " after a vowel",
        "after_consonant": " after a consonant",
        "before_vowel": " before a vowel",
    }

    def one(change: FormChange) -> str:
        when = said.get(
            change.when,
            f" after -{change.when[5:].replace('|', '/-')}"
            if change.when.startswith("ends:")
            else f" ({change.when})",
        )
        if change.kind == "ending":
            what = f"-{change.text}"
        elif change.kind == "swap":
            what = f"-{change.drop.replace('|', '/-')} becomes -{change.text}"
        elif change.kind == "word_before":
            what = f"“{change.text}” before"
        elif change.kind == "word_after":
            what = f"“{change.text}” after"
        else:
            what = "the first part doubled"
        return what + when

    return "; ".join(one(c) for c in changes) or "no change"


def grammar_rows(language: Language) -> list[GrammarRow]:
    """The grammar for names in plain words, one row a rule, each with an
    example built from it; a row that can't build says why. No grammar:
    no rows."""

    grammar = language.name_grammar
    if grammar is None:
        return []
    vowels = vowels_of(language)
    noun = _example_noun(language)
    adjective = next(
        (e.word.lower() for e in language.dictionary if e.part == "adjective"), ""
    )
    rows: list[GrammarRow] = []

    def row(key: str, label: str, rule: str, build: Callable[[], str]) -> None:
        try:
            example = build()
            rows.append(GrammarRow(key=key, label=label, rule=rule, example=example))
        except Exception as exc:  # a rule the engine can't apply
            rows.append(GrammarRow(key=key, label=label, rule=rule, error=str(exc)))

    row(
        "describing",
        "Describing words",
        f"{grammar.describing} the noun",
        lambda: (
            (
                f"{adjective} {noun}"
                if grammar.describing == "before"
                else f"{noun} {adjective}"
            )
            if adjective and noun
            else ""
        ),
    )
    if grammar.of is not None:
        of = grammar.of
        rule = (
            f"the word “{of.text}”, {of.word_side} its noun"
            if of.how == "word"
            else f"the ending -{of.text}"
        )
        row(
            "of",
            '"of"',
            rule,
            lambda: (
                (
                    f"{of.text} {noun}"
                    if of.word_side == "before"
                    else f"{noun} {of.text}"
                )
                if of.how == "word"
                else noun + of.text
            )
            if noun
            else "",
        )
    row(
        "joining",
        "Joined words",
        "describing word first"
        if grammar.joining == "describing_first"
        else "main word first",
        lambda: "",
    )
    for form in ("the", "more_than_one"):
        changes = getattr(grammar, form)
        if not changes:
            continue
        label = '"the"' if form == "the" else "More than one"
        row(
            form,
            label,
            _change_words(changes),
            lambda form=form: f"{noun} → {apply_form(grammar, vowels, noun, form)}"
            if noun
            else "",
        )
    for ending in grammar.endings:
        row(
            f"ending:{ending.ending}",
            f"-{ending.ending}",
            ending.meaning,
            lambda ending=ending: f"{noun} → {apply_ending(grammar, vowels, noun, ending.meaning)}"
            if noun
            else "",
        )
    return rows
