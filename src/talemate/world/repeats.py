"""Repeats and dates that disagree: plain code over word overlap, no model.

The fact placement probe (`docs/superpowers/probes/2026-10-22-fact-placement.md`,
"Code instead of model") found that a token-overlap detector catches
restatements better than a model call: at 0.4 it caught 43 of 45 labelled
restatements with 1 false flag in 34 clean facts. The measure here is the
probe's own, ported unchanged from `scripts/dev/probe_fact_placement_score.py`:
- `STOP` is the probe's `STOP`;
- `content_words` is the probe's `tokens` (with its `_stem`): lower-cased
  `[a-z0-9]+` runs, stop words and one-letter words dropped, then a crude
  stem (`ing`, `ed`, `es`, `s` cut from a word that keeps four letters or
  more);
- `overlap` is the probe's `containment`: the share of the first text's
  content words the second text holds. It reads one way, the way the
  probe ran it: a new fact against an existing one.

Facts are compared as they read (`WorldView.render`), so a reference counts
as the name it shows, as in the probe. Every fact not removed at the
view's revision counts, whatever its story dates (a fact that ended, or
holds only from later, is still something the world says).

`disagreeing_dates` uses the same words both ways: two dated facts disagree
when either one's words are mostly in the other (the higher of the two
`overlap`s, which is `|A∩B| / min(|A|, |B|)`) and their start years differ,
as with the Codex's compiling, given as 217 on Runeweaving's timeline and
312 on the Codex.
"""

import json
import re
import sqlite3
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

from .view import WorldView, _decode_date

__all__ = [
    "STOP",
    "Disagreement",
    "Repeat",
    "content_words",
    "disagreeing_dates",
    "fact_texts",
    "find_repeats",
    "overlap",
    "word_share",
]

# the probe's stop list, as it is
STOP = set(
    """a an the of and or in on at to for from by with as is are was were be been
    its it their his her this that these those which who whom into over under
    than then so such not no nor but if all any each every some most more many
    much one two can could may might would will shall should has have had do does
    did also only even both either very own same other another within without
    through about after before since while where when there here what how""".split()
)

_WORDS = re.compile(r"[a-z0-9]+")
_SUFFIXES = ("ing", "ed", "es", "s")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def content_words(text: str) -> set[str]:
    """The text's content words: lower-cased, stop words and one-letter
    words out, each crudely stemmed (the probe's `tokens`)."""

    return {
        _stem(word)
        for word in _WORDS.findall(text.lower())
        if word not in STOP and len(word) > 1
    }


def word_share(new: set[str], old: set[str]) -> float:
    """The share of the content words `new` that `old` holds, 0 to 1 (0
    when `new` is empty): `overlap` on words already found."""

    return len(new & old) / len(new) if new else 0.0


def overlap(a: str, b: str) -> float:
    """The share of `a`'s content words that `b` holds, 0 to 1 (the probe's
    `containment`); 0 when `a` has none."""

    return word_share(content_words(a), content_words(b))


class Repeat(BaseModel):
    """A new text that says again what a live fact says: the text's index,
    the fact, its owner, the overlap, and the fact's text as it reads."""

    index: int
    fact_id: str
    owner_id: str
    score: float
    text: str = ""


def find_repeats(
    view: WorldView, texts: list[str], owner_ids: list[str], threshold: float
) -> list[Repeat]:
    """For each text, the fact of `owner_ids` that holds most of its
    words, when that overlap is at least `threshold`; in text order, a
    text with no such fact left out. Every fact not removed at the view's
    revision counts, whatever its story dates: a fact that has ended, or
    holds only from a later date, is still in the world. On a tie the
    first owner given, then its first fact (by start date, undated first,
    then id), wins. An owner that isn't live at the view has no facts."""

    rows = _live_facts(view, "thing_id", owner_ids)
    by_owner: dict[str, list[tuple[str, str, set[str]]]] = {}
    for row in rows:
        rendered = view.render(row["text"])
        by_owner.setdefault(row["thing_id"], []).append(
            (row["fact_id"], rendered, content_words(rendered))
        )
    facts = [
        (owner_id, fact_id, rendered, words)
        for owner_id in dict.fromkeys(owner_ids)
        for fact_id, rendered, words in by_owner.get(owner_id, [])
    ]

    found: list[Repeat] = []
    for index, text in enumerate(texts):
        words = content_words(view.render(text))
        best: Repeat | None = None
        for owner_id, fact_id, rendered, old in facts:
            score = word_share(words, old)
            if score >= threshold and (best is None or score > best.score):
                best = Repeat(
                    index=index,
                    fact_id=fact_id,
                    owner_id=owner_id,
                    score=score,
                    text=rendered,
                )
        if best is not None:
            found.append(best)
    return found


class Disagreement(BaseModel):
    """Two dated facts that say much the same with different start years:
    `a` before `b` in the order given, and their years in that order."""

    a: str
    b: str
    years: tuple[int, int]


def _live_facts(
    view: WorldView, column: Literal["thing_id", "fact_id"], ids: Sequence[str]
) -> list[sqlite3.Row]:
    """The fact rows (`thing_id`, `fact_id`, `text`, `valid_from`,
    `from_precision`, `valid_until`) not removed at the view's revision, of a live owner,
    whose `column` (`thing_id` or `fact_id`) is one of `ids`, whatever
    their story dates; ordered by start date (undated first), then id."""

    if not ids:
        return []
    things_filter, params = view._live_things_filter("t.")
    return view._conn.execute(
        f"""
        SELECT f.thing_id, f.fact_id, f.text, f.valid_from, f.from_precision,
               f.valid_until
        FROM facts f
        JOIN things t ON t.id = f.thing_id AND {things_filter}
        WHERE f.{column} IN (SELECT value FROM json_each(?))
          AND f.rev_added <= ? AND (f.rev_removed IS NULL OR f.rev_removed > ?)
        ORDER BY f.valid_from ASC, f.fact_id ASC
        """,
        (*params, json.dumps(list(ids)), view.rev, view.rev),
    ).fetchall()


def fact_texts(view: WorldView, owner_ids: Sequence[str]) -> list[tuple[str, str, str]]:
    """`(owner id, fact id, text as it reads)` for every fact of `owner_ids`
    not removed at the view's revision, of a live owner, whatever its story
    dates (as `find_repeats` reads them); ordered by start date (undated
    first), then id."""

    return [
        (row["thing_id"], row["fact_id"], view.render(row["text"]))
        for row in _live_facts(view, "thing_id", owner_ids)
    ]


def _dated_facts(
    view: WorldView, fact_ids: Sequence[str], include_ended: bool = False
) -> dict[str, tuple[int, str]]:
    """`fact id -> (start year, text as it reads)` for each of `fact_ids`
    not removed at the view's revision, with a live owner and a start
    date, that hasn't ended at the view (ruling C22: `valid_until` on or
    before its date, as `timelines.entry_timeline` reads `until`; with no
    date, any end) -- or ended too, with `include_ended` (a merge, ruling
    C23). Its start isn't checked: the caller picked these facts (a
    timeline's lines)."""

    at = view._at_instant()
    found: dict[str, tuple[int, str]] = {}
    for row in _live_facts(view, "fact_id", fact_ids):
        if (
            not include_ended
            and row["valid_until"] is not None
            and row["valid_until"] <= at
        ):
            continue
        start = _decode_date(row["valid_from"], row["from_precision"])
        if start is not None:
            found[row["fact_id"]] = (start.to_datetime().year, row["text"])
    return found


def disagreeing_dates(
    view: WorldView,
    fact_ids: list[str],
    threshold: float,
    *,
    include_ended: bool = False,
) -> list[Disagreement]:
    """The pairs among `fact_ids` that say much the same (either one's
    `overlap` with the other at least `threshold`) with different start
    years (`valid_from`), in the order given. A fact with no start date,
    not live at the view's revision, or ended at the view (ruling C22: a
    pick that ends one settles the pair) is never in a pair; an id given
    twice counts once. `include_ended` keeps ended facts in (a merge
    reconciles two histories, so an ended claim still conflicts, ruling
    C23)."""

    dated = _dated_facts(view, fact_ids, include_ended)
    ordered = [fact_id for fact_id in dict.fromkeys(fact_ids) if fact_id in dated]
    words = {
        fact_id: content_words(view.render(dated[fact_id][1])) for fact_id in ordered
    }
    found: list[Disagreement] = []
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            year_a, year_b = dated[a][0], dated[b][0]
            if year_a == year_b:
                continue
            score = max(word_share(words[a], words[b]), word_share(words[b], words[a]))
            if score >= threshold:
                # built unchecked (ruling C19): a timeline of templated
                # lines can make thousands of pairs
                found.append(
                    Disagreement.model_construct(a=a, b=b, years=(year_a, year_b))
                )
    return found
