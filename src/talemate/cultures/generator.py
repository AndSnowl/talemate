"""Rule-based name generator and "fits" check for cultures/languages.

This module turns the small pattern language used by `Language.categories`
and `GeneratorDef.patterns` into either randomly generated names (`roll`) or
a predicate that tells whether an existing name plausibly belongs to a
language (`fits`). The pattern syntax below is also the culture *import
file format* for these fields, so any change here must stay in sync with
the importer and with Task 7's authoring skill.

Rule syntax
-----------

**Categories** (`Language.categories`): a mapping of single uppercase
letters to a space-separated list of options, e.g.::

    {"C": "k kh t th dh r*2", "V": "a ae e o u i"}

Each option may carry a trailing weight suffix ``*n`` (an integer); options
without a suffix have weight 1. Options may be more than one letter long
(e.g. ``kh``, ``th``).

**Pattern tokens** (`GeneratorDef.patterns`), read left to right:

- an uppercase letter that names a defined category means "one weighted
  pick from that category's options";
- ``(...)`` marks its contents as optional: included with 50% probability,
  and may nest, e.g. ``C(V(C))``;
- ``[a|b|c]`` picks between the alternatives with equal probability; each
  alternative is itself a sub-pattern and may contain categories, optional
  groups and nested choices;
- anything else — lowercase letters, spaces, ``'``, ``-``, digits, and
  uppercase letters that are *not* defined categories — is literal text,
  copied through as-is.

**Pattern weight:** a whole pattern string may end in ``*n`` to weight it
among a generator's other patterns when one pattern is picked to render
(e.g. ``["CVC*3", "CV"]`` favours the first pattern 3:1). The ``*n`` suffix
is stripped before the pattern body is parsed, so it must not collide with
a trailing category/literal that legitimately ends in ``*n`` (it never
does, since ``*`` is not itself a valid category or literal character in
this syntax).

**Output rules**, applied to each candidate produced from a pattern:

- `GeneratorDef.reject` is a list of regexes, matched case-insensitively
  with `re.search` against the full rendered name; any match drops the
  candidate;
- `GeneratorDef.min_length` / `max_length` count *letters only* (so
  spaces, apostrophes and hyphens are free);
- when `GeneratorDef.capitalize` is true, the first letter of each
  space-separated word is uppercased (the rest of the word is left as
  rendered);
- results are de-duplicated case-insensitively, and none of them may equal
  (case-insensitively) an entry of the caller-supplied `exclude` set.

**`fits`:** every pattern of every generator of the language is compiled
into an anchored, case-insensitive regex: a category becomes an
alternation of its options sorted longest-first (so a longer option such
as ``th`` is tried before a prefix like ``t``), ``(...)`` becomes
``(?:...)?``, ``[a|b]`` becomes ``(?:a|b)``, and literal text is
regex-escaped. A name fits the language when, after lowercasing, every
space-separated word of the name fully matches at least one of those
compiled patterns, and no generator's `reject` regex matches the (lowered)
name. A language with no generators has nothing to check against, so
`fits` always returns `True` for it — such languages are never flagged as
having a "foreign" name.

Compiled regexes (and parsed pattern trees) are cached per language,
keyed on a JSON dump of its `categories` and generators, since parsing and
compiling are the expensive part and languages are reused across many
`roll`/`fits` calls.
"""

from __future__ import annotations

import functools
import json
import random
import re
from dataclasses import dataclass, field
from typing import Union

from talemate.cultures.models import GeneratorDef, Language

__all__ = ["GeneratorError", "parse_categories", "roll", "fits"]


class GeneratorError(ValueError):
    """Raised for an unknown generator id or a malformed pattern/category."""


# --------------------------------------------------------------------------
# Pattern tokens
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Literal:
    text: str


@dataclass(frozen=True)
class _Category:
    key: str


@dataclass(frozen=True)
class _Sequence:
    items: tuple["_Token", ...]


@dataclass(frozen=True)
class _Optional:
    inner: "_Token"


@dataclass(frozen=True)
class _Choice:
    options: tuple["_Token", ...]


_Token = Union[_Literal, _Category, _Sequence, _Optional, _Choice]


_WEIGHT_SUFFIX_RE = re.compile(r"^(.*)\*(\d+)$")


def _split_weight(text: str) -> tuple[str, int]:
    """Split a trailing ``*n`` weight suffix off `text`, default weight 1."""
    match = _WEIGHT_SUFFIX_RE.match(text)
    if match:
        return match.group(1), int(match.group(2))
    return text, 1


def parse_categories(categories: dict[str, str]) -> dict[str, list[tuple[str, int]]]:
    """Parse `Language.categories` into options with resolved weights.

    Each category's value is a space-separated list of options; an option
    may end in ``*n`` for an integer weight (default 1). Returns a mapping
    of category key to a list of `(option_text, weight)` tuples, in the
    order the options were declared.
    """
    parsed: dict[str, list[tuple[str, int]]] = {}
    for key, value in categories.items():
        options: list[tuple[str, int]] = []
        for token in value.split():
            text, weight = _split_weight(token)
            if not text:
                raise GeneratorError(f"empty option in category {key!r}: {value!r}")
            options.append((text, weight))
        if not options:
            raise GeneratorError(f"category {key!r} has no options")
        parsed[key] = options
    return parsed


class _PatternParser:
    """Recursive-descent parser for a single pattern string."""

    def __init__(self, pattern: str, category_keys: frozenset[str]):
        self.pattern = pattern
        self.category_keys = category_keys
        self.pos = 0

    def parse(self) -> _Sequence:
        result = self._parse_sequence(stop_chars="")
        if self.pos != len(self.pattern):
            raise GeneratorError(
                f"unexpected {self.pattern[self.pos]!r} in pattern {self.pattern!r}"
            )
        return result

    def _parse_sequence(self, stop_chars: str) -> _Sequence:
        items: list[_Token] = []
        literal_buf: list[str] = []

        def flush() -> None:
            if literal_buf:
                items.append(_Literal("".join(literal_buf)))
                literal_buf.clear()

        while self.pos < len(self.pattern) and self.pattern[self.pos] not in stop_chars:
            ch = self.pattern[self.pos]
            if ch == "(":
                flush()
                self.pos += 1
                inner = self._parse_sequence(stop_chars=")")
                if self.pos >= len(self.pattern) or self.pattern[self.pos] != ")":
                    raise GeneratorError(
                        f"unterminated '(' in pattern {self.pattern!r}"
                    )
                self.pos += 1
                items.append(_Optional(inner))
            elif ch == "[":
                flush()
                self.pos += 1
                options = [self._parse_sequence(stop_chars="|]")]
                while self.pos < len(self.pattern) and self.pattern[self.pos] == "|":
                    self.pos += 1
                    options.append(self._parse_sequence(stop_chars="|]"))
                if self.pos >= len(self.pattern) or self.pattern[self.pos] != "]":
                    raise GeneratorError(
                        f"unterminated '[' in pattern {self.pattern!r}"
                    )
                self.pos += 1
                items.append(_Choice(tuple(options)))
            elif ch == ")" or ch == "]":
                raise GeneratorError(f"unmatched {ch!r} in pattern {self.pattern!r}")
            elif ch.isupper() and ch in self.category_keys:
                flush()
                items.append(_Category(ch))
                self.pos += 1
            else:
                literal_buf.append(ch)
                self.pos += 1
        flush()
        return _Sequence(tuple(items))


def _parse_pattern(pattern: str, category_keys: frozenset[str]) -> _Sequence:
    return _PatternParser(pattern, category_keys).parse()


# --------------------------------------------------------------------------
# Rendering (for `roll`)
# --------------------------------------------------------------------------


def _weighted_choice(options, rng: random.Random):
    total = sum(weight for _, weight in options)
    threshold = rng.uniform(0, total)
    upto = 0.0
    for item, weight in options:
        upto += weight
        if threshold <= upto:
            return item
    return options[-1][0]


def _render(
    token: _Token,
    categories: dict[str, list[tuple[str, int]]],
    rng: random.Random,
) -> str:
    if isinstance(token, _Literal):
        return token.text
    if isinstance(token, _Category):
        return _weighted_choice(categories[token.key], rng)
    if isinstance(token, _Sequence):
        return "".join(_render(item, categories, rng) for item in token.items)
    if isinstance(token, _Optional):
        if rng.random() < 0.5:
            return _render(token.inner, categories, rng)
        return ""
    if isinstance(token, _Choice):
        chosen = rng.choice(token.options)
        return _render(chosen, categories, rng)
    raise GeneratorError(f"unknown pattern token: {token!r}")


def _capitalize_words(name: str) -> str:
    def cap(word: str) -> str:
        return word[:1].upper() + word[1:] if word else word

    return " ".join(cap(word) for word in name.split(" "))


# --------------------------------------------------------------------------
# Regex compilation (for `fits`)
# --------------------------------------------------------------------------


def _to_regex(token: _Token, category_options: dict[str, list[str]]) -> str:
    if isinstance(token, _Literal):
        return re.escape(token.text)
    if isinstance(token, _Category):
        options = category_options[token.key]
        return "(?:" + "|".join(re.escape(option) for option in options) + ")"
    if isinstance(token, _Sequence):
        return "".join(_to_regex(item, category_options) for item in token.items)
    if isinstance(token, _Optional):
        return "(?:" + _to_regex(token.inner, category_options) + ")?"
    if isinstance(token, _Choice):
        return (
            "(?:"
            + "|".join(_to_regex(option, category_options) for option in token.options)
            + ")"
        )
    raise GeneratorError(f"unknown pattern token: {token!r}")


# --------------------------------------------------------------------------
# Per-language compilation cache
# --------------------------------------------------------------------------


@dataclass
class _CompiledLanguage:
    categories: dict[str, list[tuple[str, int]]]
    generator_patterns: dict[str, list[tuple[_Sequence, int]]] = field(
        default_factory=dict
    )
    generator_reject: dict[str, list[re.Pattern]] = field(default_factory=dict)
    fits_patterns: tuple[re.Pattern, ...] = ()
    fits_rejects: tuple[re.Pattern, ...] = ()


def _language_cache_key(language: Language) -> str:
    payload = {
        "categories": language.categories,
        "generators": [
            {"id": gen.id, "patterns": gen.patterns, "reject": gen.reject}
            for gen in language.generators
        ],
    }
    return json.dumps(payload, sort_keys=True)


@functools.lru_cache(maxsize=256)
def _compile_language(cache_key: str) -> _CompiledLanguage:
    data = json.loads(cache_key)
    category_keys = frozenset(data["categories"].keys())
    categories = parse_categories(data["categories"])
    category_options = {
        key: sorted((option for option, _ in opts), key=len, reverse=True)
        for key, opts in categories.items()
    }

    compiled = _CompiledLanguage(categories=categories)
    fits_patterns: list[re.Pattern] = []
    fits_rejects: list[re.Pattern] = []

    for gen in data["generators"]:
        parsed_patterns: list[tuple[_Sequence, int]] = []
        for pattern_text in gen["patterns"]:
            text, weight = _split_weight(pattern_text)
            tree = _parse_pattern(text, category_keys)
            parsed_patterns.append((tree, weight))
            fits_patterns.append(
                re.compile(f"^{_to_regex(tree, category_options)}$", re.IGNORECASE)
            )
        compiled.generator_patterns[gen["id"]] = parsed_patterns

        reject_regexes = [
            re.compile(pattern, re.IGNORECASE) for pattern in gen.get("reject", [])
        ]
        compiled.generator_reject[gen["id"]] = reject_regexes
        fits_rejects.extend(reject_regexes)

    compiled.fits_patterns = tuple(fits_patterns)
    compiled.fits_rejects = tuple(fits_rejects)
    return compiled


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def roll(
    language: Language,
    generator_id: str,
    count: int = 20,
    rng: random.Random | None = None,
    exclude: set[str] = frozenset(),
) -> list[str]:
    """Generate up to `count` unique candidate names.

    Raises `GeneratorError` if `generator_id` is not one of
    `language.generators`. Attempts are capped at `count * 50`, so the
    result may have fewer than `count` names when the generator's pattern
    space is smaller than that (or reject rules/length bounds are tight).
    """
    generator: GeneratorDef | None = next(
        (gen for gen in language.generators if gen.id == generator_id), None
    )
    if generator is None:
        raise GeneratorError(f"unknown generator id: {generator_id!r}")

    rng = rng if rng is not None else random.Random()
    compiled = _compile_language(_language_cache_key(language))
    categories = compiled.categories
    patterns = compiled.generator_patterns[generator.id]
    rejects = compiled.generator_reject[generator.id]

    exclude_lower = {value.lower() for value in exclude}
    seen: set[str] = set()
    results: list[str] = []
    attempts = 0
    max_attempts = count * 50

    while len(results) < count and attempts < max_attempts:
        attempts += 1
        tree = _weighted_choice(patterns, rng)
        name = _render(tree, categories, rng)
        if generator.capitalize:
            name = _capitalize_words(name)

        letters = sum(1 for ch in name if ch.isalpha())
        if letters < generator.min_length or letters > generator.max_length:
            continue
        if any(reject.search(name) for reject in rejects):
            continue

        key = name.lower()
        if key in seen or key in exclude_lower:
            continue
        seen.add(key)
        results.append(name)

    return results


def fits(language: Language, name: str) -> bool:
    """Return whether `name` plausibly belongs to `language`.

    Languages with no generators have no shape to check against, so this
    always returns `True` for them.
    """
    if not language.generators:
        return True

    compiled = _compile_language(_language_cache_key(language))
    lowered = name.lower()

    for reject in compiled.fits_rejects:
        if reject.search(lowered):
            return False

    words = lowered.split()
    if not words:
        return False

    for word in words:
        if not any(pattern.match(word) for pattern in compiled.fits_patterns):
            return False
    return True
