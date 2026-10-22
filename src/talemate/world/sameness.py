"""Same-thing candidates: the things a name could be the same as, found by
its words in plain code, no model.

The fact placement probe (`docs/superpowers/probes/2026-10-22-fact-placement.md`,
"Same-thing check" and "Code instead of model") found that pairs of names
sharing a content word find every true "same" pair, and that a name's words
inside another's isn't enough to call them the same ("Eternal Light" and
"Church of the Eternal Light" aren't). So code offers candidates and the
model, or the owner, judges.

A thing is a candidate for a name, by the best of three reasons:
- `aka`: the name is one of the thing's names, its main name or another
  name (`aka`), bar case, spacing, a possessive (`'s`, or a plural's
  `s'`, so "Runeweaver's Conclave" is "Runeweavers' Conclave"),
  punctuation and a leading article;
- `inside`: one of its names is inside the name, or the name inside it,
  as whole words in order ("Conclave" in "Runeweavers' Conclave");
- `word`: one of its names shares a content word with the name.

Name words are the probe's (`same_thing`'s `words`): letter runs of the
name, normalised as `names` does (`_norm`), and for sharing, the stop words
of `repeats.STOP` (the articles among them) and words of 2 letters or fewer
dropped.

A common word never makes a candidate: the stop words, and in a world of
at least `COMMON_MIN_NAMES` things, any word in the names of more than
`COMMON_SHARE` of them and of at least `COMMON_MIN_THINGS`, so "Tsar" or
"Moskov" doesn't tie a name to everything named after it. A word counts
once per thing, across its main and other names, so a thing's own other
names ("Ashenmere Caverns") don't make its word common. A name inside
another counts only when the inside one has a word that isn't common.

The world's names (main and other names of live things) and its common
words are read into a `NameIndex` (`name_index`): one query over
`field_values`, as nearness reads links. `same_candidates` reads one per
call unless given one, so a preview with several new names reads the
world once.

Only live things are candidates, and an ignored stub never is (as for
`names` and `nearness`). The score orders them: the reason first (`aka`,
then `inside`, then `word`), then nearness (`near_ids`, nearest first).
"""

import re
from collections import Counter
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

from .names import ARTICLES, _aka_entries, _norm
from .nearness import _field_values, _live_things, _state
from .repeats import STOP
from .view import WorldView

__all__ = [
    "COMMON_MIN_NAMES",
    "COMMON_MIN_THINGS",
    "COMMON_SHARE",
    "NameIndex",
    "SameCandidate",
    "name_index",
    "same_candidates",
]

Reason = Literal["word", "inside", "aka"]

# a word in the names of more than this share of the world's things is
# common...
COMMON_SHARE = 0.05
# ...and of at least this many things...
COMMON_MIN_THINGS = 6
# ...once the world has this many named things
COMMON_MIN_NAMES = 20

# the score: a base by reason, plus up to `_NEAR_BONUS` for a near thing
# (the nearest gets it all), so the reason always comes first
_BASE: dict[str, float] = {"aka": 0.75, "inside": 0.5, "word": 0.25}
_NEAR_BONUS = 0.2

_LETTERS = re.compile(r"[^\W\d_]+")
# a possessive: "Runeweaver's" or "Runeweavers'", both read "runeweaver"
_POSSESSIVE = re.compile(r"(?:['’]s|s['’])(?!\w)")

Words = tuple[str, ...]


class SameCandidate(BaseModel):
    """A thing a name could be the same as, why, and how strongly (0 to
    1; higher is a better candidate)."""

    thing_id: str
    reason: Reason
    score: float


def _words(name: str) -> Words:
    """The name's words, normalised, without a possessive (`'s`, `s'`)
    or a leading article."""

    words = _LETTERS.findall(_POSSESSIVE.sub("", _norm(name)))
    if words and words[0] in ARTICLES:
        words = words[1:]
    return tuple(words)


def _content(words: Words) -> set[str]:
    return {word for word in words if word not in STOP and len(word) > 2}


def _within(short: Words, long: Words) -> bool:
    """Whether `short` is a run of `long`'s words, and shorter."""

    n = len(short)
    return 0 < n < len(long) and any(
        long[i : i + n] == short for i in range(len(long) - n + 1)
    )


def _names(view: WorldView) -> dict[str, list[Words]]:
    """`thing id -> the words of each of its names` (main name first, each
    once) for every live thing with a main name that isn't an ignored
    stub."""

    live = _live_things(view)
    main: dict[str, str] = {}
    others: dict[str, list[str]] = {}
    ignored: set[str] = set()
    for thing_id, field, value in _field_values(view, live, ("name", "aka", "stub")):
        if field == "name":
            if isinstance(value, str) and value.strip():
                main[thing_id] = value
        elif field == "aka":
            state = _state(thing_id, live[thing_id], field, value)
            others[thing_id] = [
                other
                for entry in _aka_entries(state)
                if isinstance(other := entry.get("name"), str)
            ]
        elif isinstance(value, dict) and value.get("ignored") is True:
            ignored.add(thing_id)

    names: dict[str, list[Words]] = {}
    for thing_id, name in main.items():
        if thing_id in ignored:
            continue
        found: list[Words] = []
        for written in [name, *others.get(thing_id, [])]:
            words = _words(written)
            if words and words not in found:
                found.append(words)
        if found:
            names[thing_id] = found
    return names


def _common(names: dict[str, list[Words]]) -> set[str]:
    """The words in the names of more than `COMMON_SHARE` of the world's
    things and of at least `COMMON_MIN_THINGS`, once there are
    `COMMON_MIN_NAMES` things; each word counted once per thing."""

    if len(names) < COMMON_MIN_NAMES:
        return set()
    counts: Counter[str] = Counter()
    for found in names.values():
        words_of_thing: set[str] = set()
        for words in found:
            words_of_thing |= _content(words)
        counts.update(words_of_thing)
    return {
        word
        for word, n in counts.items()
        if n > COMMON_SHARE * len(names) and n >= COMMON_MIN_THINGS
    }


class NameIndex:
    """The world's names and common words, as read at one view."""

    def __init__(self, names: dict[str, list[Words]], common: set[str]) -> None:
        self.names = names
        self.common = common


def name_index(view: WorldView) -> NameIndex:
    """The names (`thing id -> each name's words`, main name first) of
    every live thing at the view that isn't an ignored stub, and the
    world's common words."""

    names = _names(view)
    return NameIndex(names, _common(names))


def _reason(
    query: Words, uncommon: set[str], names: list[Words], common: set[str]
) -> Reason | None:
    """The best reason one thing's names give for being `query`, if any."""

    if query in names:
        return "aka"
    for words in names:
        inner = (
            words if _within(words, query) else query if _within(query, words) else None
        )
        if inner is not None and _content(inner) - common:
            return "inside"
    if any(_content(words) & uncommon for words in names):
        return "word"
    return None


def same_candidates(
    view: WorldView,
    name: str,
    *,
    near_ids: Sequence[str],
    limit: int = 5,
    exclude: Sequence[str] = (),
    index: NameIndex | None = None,
) -> list[SameCandidate]:
    """The live things `name` could be the same as at the view, best first
    (score descending, then main name, then id), at most `limit` of them,
    none of `exclude` (the thing being filled, say). Every thing matching
    by name counts, near or not; `near_ids` (nearest first, say from
    `near()`) only lifts the near ones. `index` (from `name_index`, at
    this view) saves reading the world's names again."""

    query = _words(name)
    if limit <= 0 or not query:
        return []
    if index is None:
        index = name_index(view)
    names, common = index.names, index.common
    skip = set(exclude)
    uncommon = _content(query) - common
    rank = {thing_id: i for i, thing_id in reversed(list(enumerate(near_ids)))}

    found: list[tuple[float, str, str, Reason]] = []
    for thing_id, words in names.items():
        if thing_id in skip:
            continue
        reason = _reason(query, uncommon, words, common)
        if reason is None:
            continue
        score = _BASE[reason]
        if thing_id in rank:
            score += _NEAR_BONUS * (1 - rank[thing_id] / len(near_ids))
        found.append((score, " ".join(words[0]), thing_id, reason))
    found.sort(key=lambda f: (-f[0], f[1], f[2]))
    return [
        SameCandidate(thing_id=thing_id, reason=reason, score=round(score, 6))
        for score, _, thing_id, reason in found[:limit]
    ]
