"""Merge one entry into another, for when two entries for one thing slip
through (curation spec goal 5): "Merge into..." folds a full entry into
another the way Re-point folds a stub, and the owner picks the outcome.

`preview_merge` reads it all, writing nothing and asking no model (ruling
C14: the curation probe's probe 3 fell back to code):

- **the names:** both, for the owner to pick the main one;
- **the facts:** the from-side's, each ticked to move, beside the
  into-side's. One that restates an into-side fact at the world's
  `repeat_untick_threshold` or above (`create.repeat_flags`) is a repeat,
  unticked ("already there");
- **the pairs:** facts that may disagree, one from each side
  (`decide.contradiction_pairs`: word overlap, and the dates that
  disagree), for the owner to pick between;
- **the moves:** how many facts, links, fields, filings and ties go over.

**Repeats and pairs.** A fact is never both. A from-side fact in a pair of
disagreeing dates is a pair, never a repeat: the years are the owner's to
pick. Otherwise a repeat (unticked) is in no pair, and a fact that only
overlaps (below the untick threshold, or too short to untick) is a pair,
shown without its match.

`accept_merge` writes it in one revision (`repoint.plan_merge`, the mover
Re-point uses), so one undo reverses it:

- each pair's choice: `"a"` keeps the from-side's fact, `"b"` the
  into-side's, `"both"` (or no answer) both. The loser is removed
  (`lose="remove"`: the into-side's removed, the from-side's not copied)
  or ended at the world's now (`lose="end"`; one that starts later is
  removed, with a note). A fact that loses any pair loses;
- the from-side's ticked facts, and those in a pair it doesn't lose, are
  copied onto the into-side with new ids (ruling R1); the rest go with it.
  An override of a fact that went points at what replaced it (the fact it
  repeats, or the pair's winner), or is dropped;
- every reference, field, filing and tie naming the from-side moves over,
  the into-side's empty fields are filled, and it keeps its own filing;
- the main name is set, the other becomes a common other name;
- the from-side is removed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import structlog
from pydantic import BaseModel, Field

from talemate.world import spheres
from talemate.world.dates import WorldDate
from talemate.world.store import Revision, Source, World
from talemate.world.view import WorldView
from talemate.worldplay.create import current_date, repeat_flags
from talemate.worldplay.decide import Pair, contradiction_pairs
from talemate.worldplay.repoint import RepointResult, plan_merge

log = structlog.get_logger("talemate.worldplay.merge")

__all__ = [
    "Choice",
    "MergeFact",
    "MergePreview",
    "accept_merge",
    "preview_merge",
]

Choice = Literal["a", "b", "both"]
_CHOICES: tuple[str, ...] = ("a", "b", "both")


class MergeFact(BaseModel):
    """One fact of either side, as it reads. A from-side fact moves when
    `ticked` (and loses no pair); `repeat_of` is the into-side fact it
    restates (`{fact_id, owner_id, owner_name, text, score}`), when it's
    a repeat. An into-side fact always stays, unless it loses a pair."""

    fact_id: str
    side: Literal["from", "into"]
    category: str
    text: str
    repeat_of: dict | None = None
    ticked: bool = True


class MergePreview(BaseModel):
    from_id: str
    into_id: str
    from_name: str
    into_name: str
    # the main name is one of these: the into-side's, then the from-side's
    names: list[str]
    facts: list[MergeFact] = Field(default_factory=list)
    pairs: list[Pair] = Field(default_factory=list)
    # how much moves over: facts (ticked), links, fields, filings, ties
    moves: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def preview_merge(world: World, from_id: str, into_id: str) -> MergePreview:
    """What merging `from_id` into `into_id` would do (see the module
    docstring), writing nothing and asking no model. Refused as the merge
    is: `KeyError` for a missing thing, `ValueError` for the rest."""

    plan = plan_merge(world, from_id, into_id)
    view = world.view()
    into = view.thing(into_id)
    assert into is not None
    from_name = view.name_of(from_id) or from_id
    into_name = view.name_of(into_id) or into_id
    own = world.live_facts(from_id)
    flags = repeat_flags(view, [fact.text for fact in own], [into_id], world.curation())
    pairs = contradiction_pairs(view, from_id, into_id)
    dated = {pair.a for pair in pairs if pair.years is not None}

    facts: list[MergeFact] = []
    repeats: set[str] = set()
    for fact, (repeat_of, ticked) in zip(own, flags):
        row = MergeFact(
            fact_id=fact.fact_id,
            side="from",
            category=fact.category,
            text=view.render(fact.text),
        )
        if repeat_of is not None and not ticked and fact.fact_id not in dated:
            row.repeat_of, row.ticked = repeat_of, False
            repeats.add(fact.fact_id)
        if spheres.is_summary_fact(fact) and spheres.is_sphere(into):
            # the into-side has a summary of its own
            row.ticked = False
        facts.append(row)
    facts += [
        MergeFact(
            fact_id=fact.fact_id,
            side="into",
            category=fact.category,
            text=view.render(fact.text),
        )
        for fact in world.live_facts(into_id)
    ]
    pairs = [pair for pair in pairs if pair.years is not None or pair.a not in repeats]
    in_pair = {pair.a for pair in pairs}
    moving = sum(
        1
        for row in facts
        if row.side == "from" and (row.ticked or row.fact_id in in_pair)
    )
    preview = MergePreview(
        from_id=from_id,
        into_id=into_id,
        from_name=from_name,
        into_name=into_name,
        names=list(dict.fromkeys([into_name, from_name])),
        facts=facts,
        pairs=pairs,
        moves={"facts": moving, "links": plan.links, **plan.use_counts},
        notes=list(dict.fromkeys(plan.notes)),
    )
    log.info(
        "worlds.merge_previewed",
        from_id=from_id,
        into_id=into_id,
        facts=len(own),
        repeats=len(repeats),
        pairs=len(pairs),
    )
    return preview


def _end(
    rev: Revision, view: WorldView, fact_id: str, now: WorldDate, notes: list[str]
) -> bool:
    """End the fact at `now`, in `rev`; one that has ended by then stays
    as it is, and one that starts at `now` or later is removed instead,
    with a note. Whether it was removed."""

    found = view.fact(fact_id)
    if found is None:
        return False
    fact = found[1]
    if fact.valid_until is not None and fact.valid_until <= now:
        return False
    if fact.valid_from is not None and fact.valid_from >= now:
        rev.remove_fact(fact_id)
        notes.append(
            f"“{view.render(fact.text)}” starts after now, so it was removed, not ended"
        )
        return True
    rev.end_fact(fact_id, now)
    return False


def accept_merge(
    world: World,
    preview: MergePreview,
    *,
    main_name: str,
    keep: Mapping[str, str] | None = None,
    lose: Literal["remove", "end"] = "remove",
) -> RepointResult:
    """Merge `preview.from_id` into `preview.into_id` as the owner picked
    (see the module docstring), in one revision: `main_name` (either
    side's), the ticks on `preview.facts`, and `keep`, each pair's choice
    by its `key` ("a", "b" or "both"; a pair left out keeps both). The
    result's `prose` lists the into-side and each thing whose rendered
    fields changed.

    Refused before anything is written: as `preview_merge` is, a main name
    that isn't either side's, a choice for no such pair or no such choice,
    and a from-side whose facts changed since the preview."""

    choices = dict(keep or {})
    pairs = {pair.key: pair for pair in preview.pairs}
    for key, choice in choices.items():
        if key not in pairs:
            raise ValueError(f"no such pair in the preview: {key}")
        if choice not in _CHOICES:
            raise ValueError(f"pick a, b or both, not {choice!r}")
    if lose not in ("remove", "end"):
        raise ValueError(f"a losing fact is removed or ended, not {lose!r}")

    listed = [row for row in preview.facts if row.side == "from"]
    live = [fact.fact_id for fact in world.live_facts(preview.from_id)]
    if world.view().thing(preview.from_id) is not None and sorted(live) != sorted(
        row.fact_id for row in listed
    ):
        raise ValueError(
            f"{preview.from_name}'s facts changed since the preview: preview it again"
        )

    from_losers: set[str] = set()
    into_losers: set[str] = set()
    # a losing fact -> the fact that won over it
    winner: dict[str, str] = {}
    for key, pair in pairs.items():
        choice = choices.get(key, "both")
        if choice == "a":
            into_losers.add(pair.b)
            winner.setdefault(pair.b, pair.a)
        elif choice == "b":
            from_losers.add(pair.a)
            winner.setdefault(pair.a, pair.b)
    in_pair = {pair.a for pair in pairs.values()}
    copied = [
        row.fact_id
        for row in listed
        if (row.ticked or row.fact_id in in_pair)
        and (row.fact_id not in from_losers or lose == "end")
    ]
    replaced = {
        row.fact_id: str(row.repeat_of["fact_id"])
        for row in listed
        if row.repeat_of is not None and isinstance(row.repeat_of.get("fact_id"), str)
    }
    replaced.update(winner)

    plan = plan_merge(
        world,
        preview.from_id,
        preview.into_id,
        fact_ids=copied,
        main_name=main_name,
    )
    notes: list[str] = []
    summaries = [
        row.fact_id
        for row in listed
        if row.fact_id in copied
        and any(
            spheres.is_summary_fact(fact)
            for fact in world.live_facts(preview.from_id)
            if fact.fact_id == row.fact_id
        )
    ]
    with world.revision(Source.manual(note=plan.note)) as rev:
        plan.write(rev)
        copies = plan.copies
        view = world.view()
        now = current_date(world)
        gone = {row.fact_id for row in listed} - set(copied)
        for fact_id in sorted(into_losers):
            if view.fact(fact_id) is None:
                continue
            if lose == "remove":
                rev.remove_fact(fact_id)
                gone.add(fact_id)
            elif _end(rev, view, fact_id, now, notes):
                gone.add(fact_id)
        if lose == "end":
            for fact_id in sorted(from_losers):
                copy = copies.get(fact_id)
                if copy is not None and _end(rev, world.view(), copy, now, notes):
                    gone.add(copy)
                    replaced[copy] = replaced[fact_id]
        for fact_id in summaries:
            # one summary per sphere: the into-side's
            found = world.view().fact(copies[fact_id])
            if found is not None and found[1].origin is not None:
                origin = {k: v for k, v in found[1].origin.items() if k != "summary"}
                rev.correct_fact(copies[fact_id], origin=origin or None)
        _repoint_overrides(rev, world.view(), gone, replaced, copies)

    result = plan.result()
    log.info(
        "worlds.merged",
        from_id=preview.from_id,
        into_id=preview.into_id,
        facts_moved=result.facts_moved,
        removed=len(into_losers) if lose == "remove" else 0,
        links=result.links,
    )
    return result.model_copy(
        update={"notes": list(dict.fromkeys([*result.notes, *notes]))}
    )


def _repoint_overrides(
    rev: Revision,
    view: WorldView,
    gone: set[str],
    replaced: Mapping[str, str],
    copies: Mapping[str, str],
) -> None:
    """Each live fact overriding a fact that went: it overrides what
    replaced it (through `copies` when that moved too) while that's live,
    else it no longer overrides it."""

    if not gone:
        return
    for _owner, fact in view.overriding(sorted(gone)):
        overrides: list[str] = []
        for fact_id in fact.overrides:
            if fact_id in gone:
                swap = replaced.get(fact_id)
                swap = copies.get(swap, swap) if swap is not None else None
                if swap is None or swap in gone or view.fact(swap) is None:
                    continue
                fact_id = swap
            if fact_id not in overrides and fact_id != fact.fact_id:
                overrides.append(fact_id)
        if overrides != fact.overrides:
            rev.correct_fact(fact.fact_id, overrides=overrides)
