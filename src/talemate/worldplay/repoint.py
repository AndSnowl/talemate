"""Re-pointing a stub onto an entry: the stub was a name for something the
world already has.

`repoint_stub` moves everything that names the stub to the target, in one
revision, so one undo restores it all:

- every fact link to it, keeping its words (a link in the target's own
  facts becomes those words, plain: a thing never links to itself); with
  `use_name` (the "hard re-point"), one of the target's own names in
  place of the words;
- every field that points at it (`thing`, `things`), at each
  story date the field holds it, and every filing into it or `within` it
  (`filings`): filed in the target instead, a thing filed in both keeping
  the one it had in the target (the stub's exceptions joining it), a
  `within` that would be its own target within no part; an exception
  filed under the stub (its origin `tie`) is filed under the target;
- the stub's own facts, moved to the target (`copy_facts`: copied as
  new facts with their dates and origin, a category the target's kind
  lacks becoming `default_category`'s, every override of one pointed at
  its copy, the original removed); a fact never changes thing, since
  replay and undo key a fact by its id;
- the stub's own filings: the target is filed where the stub was, each
  with its role, dates, `within` and exceptions (mapped onto the moved
  copies), unless it's filed there already (the exceptions join that
  filing), or can't be (it would sit inside itself: a note says so); a
  `within` that doesn't hold under the target is dropped, with a note;
- the stub's other own fields the target has none of (never one naming
  the target or a thing inside it);
- its names: the stub's name, its other names and each distinct shown
  text become the target's common other names, unless the target or
  another thing already has that name. A hard re-point adds the stub's
  name and other names only: the links' words are gone from the world.
  "Link only" (`teach_names` false, ruling H2) adds none.

Then the stub is removed. Refused before anything is written (a
`ValueError` naming every use that blocks it): a use by a scene, a field
whose kind of thing the target isn't (a race's species can't be lore), a
filing that would put a thing inside itself, a mix's parents that
would name the target twice, and a use by the target itself. Prose
is refreshed only where its input changed (`RepointResult.prose`).

`plan_repoint` reads and decides it all without writing, and its
`RepointPlan.write` writes it into a revision, so another writer can
re-point a stub in its own revision (`create.accept_preview` with a same
target, for the stub it expanded, or folding a bare stub into it).

The same mover folds any thing into another of its kind (ruling C17),
for `worldplay.merge` (`plan_merge`): the same refusals, and a thing
merged into itself; a full entry doesn't fold into a stub (re-point the
stub instead). The target's own fields naming the stub aren't refused but
redirected: the merged entry sits where the stub sat (a single thing
field takes the stub's, a list drops the stub, a filing into the stub
goes, the target taking the stub's filings as above; one `within` it is
within no part), each with a note, a value left empty retired so an
earlier one shows. It differs from a re-point in what the owner picks:
- only the facts named move (`fact_ids`, the owner's ticks); the rest go
  with the thing;
- the main name (`main_name`, either side's): the other becomes a common
  other name, and both sides' other names carry over (each keeping its
  tag), one of the into-side's that is now the main name dropped;
- of the links' words, only `link_akas` become other names;
- the into-side's prose is always refreshed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from collections.abc import Set as AbstractSet

import structlog
from pydantic import BaseModel

from talemate.world import entries
from talemate.world.filing import Filing, check_filings, filings_of, sits_in
from talemate.world.kinds import (
    HERITAGE_KINDS,
    get_kind,
    kinds_can_be_one,
    moved_category,
)
from talemate.world.names import ARTICLES
from talemate.world.refs import REF_PATTERN, ref
from talemate.world.prose import UNRENDERED_FIELDS
from talemate.world.store import Revision, Source, World
from talemate.world.view import FactState, ThingState, WorldView
from talemate.worldplay.create import filings_since, prose_reads
from talemate.worldplay.links import name_key
from talemate.worldplay.references import thing_references

log = structlog.get_logger("talemate.worldplay.repoint")

__all__ = [
    "RepointPlan",
    "RepointResult",
    "copy_facts",
    "learn_names",
    "move_fact",
    "plan_merge",
    "plan_repoint",
    "repoint_stub",
]

# the kinds a field may point at, where that isn't the stub's own kind
FIELD_TARGET_KINDS: dict[str, tuple[str, ...]] = {
    "heritage": HERITAGE_KINDS,
    "parents": HERITAGE_KINDS,
    "species": ("species",),
}

# the stub's own fields that aren't carried over as they are
_OWN_HANDLED = ("name", "aka", "stub", "filings")


class RepointResult(BaseModel):
    stub_name: str
    target_name: str
    # fact links moved
    links: int
    # the other names the target took
    aka_added: list[str]
    # the stub's own facts the target took
    facts_moved: int
    # what didn't carry over as the stub had it, for the owner
    notes: list[str]
    # the things whose prose input changed (facts, rendered fields)
    prose: list[str]


class _FieldUse(BaseModel):
    thing_id: str
    field: str
    date: object
    value: object
    # the value at `date` is retired, not replaced (a merge's redirect)
    clear: bool = False


def _filings(value: object) -> list[Filing]:
    """A stored `filings` value as `Filing`s (one that doesn't parse
    skipped)."""

    found: list[Filing] = []
    for raw in value if isinstance(value, list) else []:
        try:
            found.append(Filing.model_validate(raw))
        except ValueError:
            continue
    return found


def _dumped(filings: Sequence[Filing]) -> list[dict[str, object]]:
    return [filing.model_dump(mode="json") for filing in filings]


def _repointed_filings(
    filings: list[Filing], stub_id: str, target_id: str
) -> tuple[list[Filing], bool]:
    """`(filings, both)`: `filings` with the stub, as a target or the part
    one is `within`, made the target. A thing filed in both keeps its
    filing into the target, the stub's exceptions joining it (`both`). A
    filing whose part would be its own target is within no part."""

    kept_target = next((f for f in filings if f.target == target_id), None)
    both = kept_target is not None and any(f.target == stub_id for f in filings)
    joined: list[str] = []
    moved: list[Filing] = []
    for filing in filings:
        if filing.target == stub_id and both:
            joined += filing.exceptions
            continue
        update: dict[str, object] = {}
        if filing.target == stub_id:
            update["target"] = target_id
        if filing.within == stub_id:
            update["within"] = target_id
        filing = filing.model_copy(update=update) if update else filing
        if filing.within is not None and filing.within == filing.target:
            filing = filing.model_copy(update={"within": None})
        moved.append(filing)
    if joined:
        moved = [
            f.model_copy(
                update={"exceptions": list(dict.fromkeys([*f.exceptions, *joined]))}
            )
            if f.target == target_id
            else f
            for f in moved
        ]
    return moved, both


def _field_uses(
    world: World,
    view: WorldView,
    stub: ThingState,
    target: ThingState,
    blocked: list[str],
    notes: list[str],
    *,
    skip_target: bool = False,
) -> list[_FieldUse]:
    """Every field value of another thing naming the stub, rewritten to
    name the target, at its date: a `thing` or `things` field, and
    `filings` (`_repointed_filings`). What can't be is added to
    `blocked`. With `skip_target`, the target's own values are left to the
    caller (a merge redirects them)."""

    uses: list[_FieldUse] = []
    for state in view.things():
        if state.id == stub.id or (skip_target and state.id == target.id):
            continue
        name = view.name_of(state.id) or state.id
        types = {spec.name: spec.type for spec in get_kind(state.kind).fields}
        for entry in world.timeline(state.id):
            if entry.change != "field" or entry.field is None:
                continue
            field, value = entry.field, entry.value
            label = f"{name}'s {field.replace('_', ' ')}"
            new: object = None
            if field == "filings":
                filings = _filings(value)
                if not any(stub.id in (f.target, f.within) for f in filings):
                    continue
                if any(f.target == stub.id for f in filings) and sits_in(
                    view, target.id, state.id
                ):
                    blocked.append(f"{label} would put it inside itself")
                    continue
                moved, both = _repointed_filings(filings, stub.id, target.id)
                if both:
                    notes.append(
                        f"{name} was filed in both; its filing in"
                        f" {view.name_of(target.id)} is kept"
                    )
                new = _dumped(moved)
            else:
                kind = types.get(field)
                if kind == "thing" and value == stub.id:
                    new = target.id
                elif kind == "things" and isinstance(value, list) and stub.id in value:
                    if field == "parents" and target.id in value:
                        blocked.append(
                            f"{label} would name {view.name_of(target.id)} twice"
                        )
                        continue
                    new = []
                    for thing_id in value:
                        swapped = target.id if thing_id == stub.id else thing_id
                        if swapped not in new:
                            new.append(swapped)
                else:
                    continue
                allowed = FIELD_TARGET_KINDS.get(field, (stub.kind,))
                if target.kind not in allowed:
                    blocked.append(f"{label} can't be a {target.kind}")
                    continue
            if state.id == target.id:
                blocked.append(f"{label} would point at itself")
                continue
            uses.append(
                _FieldUse(thing_id=state.id, field=field, date=entry.date, value=new)
            )
    return uses


# an article ending the text just before a link ("...held in the ")
_ARTICLE_BEFORE = re.compile(r"(?<![\w-])(the|a|an)\s+$", re.IGNORECASE)


def _hard_words(use_name: str, shown: str, before: str) -> str:
    """The words a hard re-point writes for one link: `use_name`, less its
    leading article when the text just `before` the link ends with one
    and either of the two is "the" ("the Grand Hall's" becomes "the Great
    Hall's", never "the The Great Hall's"; "Plan A" before "An Old Hall"
    keeps it), or with the article the link's `shown` words open with, as
    they wrote it ("It meets in the Great Hall", mid-sentence)."""

    words = use_name.split()
    if len(words) < 2 or words[0].casefold() not in ARTICLES:
        return use_name
    found = _ARTICLE_BEFORE.search(before)
    if found and "the" in (found.group(1).casefold(), words[0].casefold()):
        return " ".join(words[1:])
    opening = shown.split()[:1]
    if opening and opening[0].casefold() in ARTICLES:
        return " ".join([opening[0], *words[1:]])
    return use_name


def target_name(view: WorldView, target_id: str, use_name: str) -> str:
    """`use_name` as the thing `target_id` has it: one of its own names
    (its name or an other name), matched by `name_key`, so any case will
    do. `KeyError` for a thing that isn't there, `ValueError` for a name
    it hasn't."""

    state = view.thing(target_id)
    if state is None:
        raise KeyError(f"no such thing: {target_id}")
    name = view.name_of(target_id) or ""
    names = {name_key(each): each for each in _target_names(state, name)}
    key = name_key(use_name)
    if not key or key not in names:
        raise ValueError(
            f"the links can take one of {name}'s names"
            f" ({', '.join(names.values())}), not {' '.join(use_name.split())}"
        )
    return names[key]


def renamed_words(use_name: str, shown: str, before: str) -> str:
    """The words "Rename to..." writes for a link (or selected words)
    showing `shown` after the text `before`: `use_name`, its article fitted
    to the text (`_hard_words`, as the hard re-point writes them)."""

    return _hard_words(use_name, shown, before)


def _rewriter(
    view: WorldView,
    stub_id: str,
    target_id: str,
    shown_texts: list[str],
    use_name: str | None = None,
) -> Callable[[str, str, bool], tuple[str, int]]:
    """A function `(text, owner after, count) -> (text, links moved)`:
    links to the stub point at the target (their words, plain, in the
    target's own facts; `use_name` in place of the words when given, its
    article fitted to the text, `_hard_words`), and
    in the target's own facts its links to itself become words too. Each
    moved link's words go in `shown_texts`."""

    def rewrite(text: str, owner: str, count: bool) -> tuple[str, int]:
        moved = 0

        def one(found: re.Match[str]) -> str:
            nonlocal moved
            linked = found.group(1)
            if linked not in (stub_id, target_id):
                return found.group(0)
            shown = found.group(2) or "".join(
                seg.text for seg in view.segments(found.group(0))
            )
            if linked == stub_id:
                if count:
                    moved += 1
                    shown_texts.append(shown)
                if use_name is not None:
                    shown = _hard_words(use_name, shown, found.string[: found.start()])
                return shown if owner == target_id else ref(target_id, shown)
            return shown if owner == target_id else found.group(0)

        return REF_PATTERN.sub(one, text), moved

    return rewrite


def _other_name_keys(view: WorldView, skip: set[str]) -> set[str]:
    keys: set[str] = set()
    for state in view.things():
        if state.id in skip:
            continue
        keys.add(name_key(view.name_of(state.id) or ""))
        for entry in state.fields.get("aka") or []:
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                keys.add(name_key(entry["name"]))
    keys.discard("")
    return keys


def name_holder(
    view: WorldView, name: str, skip: AbstractSet[str]
) -> ThingState | None:
    """A thing (other than `skip`) that goes by `name`, as its name or an
    other name, or None."""

    key = name_key(name)
    for state in view.things():
        if state.id in skip:
            continue
        names = [view.name_of(state.id) or ""] + [
            entry["name"]
            for entry in state.fields.get("aka") or []
            if isinstance(entry, dict) and isinstance(entry.get("name"), str)
        ]
        if any(name_key(each) == key for each in names):
            return state
    return None


def refuse_name_in_use(view: WorldView, name: str, skip: AbstractSet[str]) -> None:
    """`ValueError` when a thing other than `skip` goes by `name` (a
    retitle can't take a name in use); for a stub, the note says to
    re-point the whole stub."""

    holder = name_holder(view, name, skip)
    if holder is None:
        return
    words = " ".join(name.split())
    holder_name = view.name_of(holder.id)
    if holder.is_stub:
        raise ValueError(
            f"{words} is already the name of the stub {holder_name}:"
            " re-point the whole stub instead"
        )
    raise ValueError(f"{words} is already the name of {holder_name}")


def retitle(
    rev: Revision,
    world: World,
    target_id: str,
    name: str,
    *,
    also: Sequence[str] = (),
    skip: AbstractSet[str] = frozenset(),
) -> list[str]:
    """Rename `target_id` to `name` ("Rename the entry to these words",
    polish 4), in `rev`: its main name, corrected at that value's date,
    becomes `name`; its old main name joins its other names (common, not
    everyday), as do `also` (a re-pointed stub's names), unless another
    thing (other than `skip`) goes by one. Refused (`ValueError`) when
    another thing already goes by `name`. Returns the other names added."""

    view = world.view()
    target = view.thing(target_id)
    if target is None:
        raise KeyError(f"no such thing: {target_id}")
    name = " ".join(name.split())
    refuse_name_in_use(view, name, {target_id, *skip})
    old = view.name_of(target_id) or ""
    if name_key(old) == name_key(name):
        return []
    aka = [
        entry
        for entry in target.fields.get("aka") or []
        if isinstance(entry, dict)
        and name_key(str(entry.get("name", ""))) != name_key(name)
    ]
    held = {name_key(name)} | {name_key(str(entry.get("name", ""))) for entry in aka}
    taken = _other_name_keys(view, {target_id, *skip})
    added: list[str] = []
    for other in [old, *also]:
        other = " ".join(other.split())
        key = name_key(other)
        if not key or key in held or key in taken:
            continue
        held.add(key)
        added.append(other)
        aka.append({"name": other, "tag": "common", "everyday": False})
    rev.set_field(target_id, "name", name, view.field_since(target_id, "name"))
    latest = view.field_since(target_id, "aka")
    # every other dated value of its other names too, so a scene set at
    # any date knows the old name and doesn't list the new one twice
    extra = [entry for entry in aka if entry.get("name") in added]
    for entry in world.timeline(target_id):
        if entry.change != "field" or entry.field != "aka":
            continue
        if getattr(entry.date, "instant", None) == getattr(latest, "instant", None):
            continue
        value = [
            e
            for e in entry.value or []
            if isinstance(e, dict)
            and name_key(str(e.get("name", ""))) != name_key(name)
        ]
        have = {name_key(str(e.get("name", ""))) for e in value}
        value += [e for e in extra if name_key(str(e["name"])) not in have]
        if value != entry.value:
            rev.set_field(target_id, "aka", value, entry.date)
    rev.set_field(target_id, "aka", aka, latest)
    return added


def learn_names(
    rev: Revision,
    world: World,
    target_id: str,
    names: Sequence[str],
    *,
    skip: AbstractSet[str] = frozenset(),
) -> list[str]:
    """Teach `target_id` the other names `names`, in `rev`, as a re-point
    teaches its target (`_names`, `RepointPlan._write_aka`): each a common
    name, not everyday, unless the target already has it or another thing
    (other than `skip`, the thing the names came from) goes by it, added
    to every dated value of its other names too. Returns those added."""

    view = world.view()
    target = view.thing(target_id)
    if target is None:
        return []
    aka = [e for e in target.fields.get("aka") or [] if isinstance(e, dict)]
    held = {name_key(view.name_of(target_id) or "")} | {
        name_key(str(entry.get("name", ""))) for entry in aka
    }
    taken = _other_name_keys(view, {target_id, *skip})
    added: list[dict] = []
    for name in names:
        name = " ".join(name.split())
        key = name_key(name)
        if not key or key in held or key in taken:
            continue
        held.add(key)
        added.append({"name": name, "tag": "common", "everyday": False})
    if not added:
        return []
    latest = view.field_since(target_id, "aka")
    for entry in world.timeline(target_id):
        if entry.change != "field" or entry.field != "aka":
            continue
        if getattr(entry.date, "instant", None) == getattr(latest, "instant", None):
            continue
        value = [e for e in entry.value or [] if isinstance(e, dict)]
        have = {name_key(str(e.get("name", ""))) for e in value}
        extra = [e for e in added if name_key(str(e["name"])) not in have]
        if extra:
            rev.set_field(target_id, "aka", [*value, *extra], entry.date)
    rev.set_field(target_id, "aka", [*aka, *added], latest)
    return [str(entry["name"]) for entry in added]


class _Job(BaseModel):
    """What one re-point reads and decides, before it writes."""

    model_config = {"arbitrary_types_allowed": True}

    world: World
    view: WorldView
    stub: ThingState
    target: ThingState
    stub_name: str
    target_name: str
    notes: list[str] = []
    # a merge (`plan_merge`): any thing, not a stub, into any thing
    merge: bool = False
    # a merge's facts to move (the owner's ticks); `None`, all of them
    fact_ids: list[str] | None = None
    # a merge's main name, either side's (a retitle's, the stub's); `None`,
    # the target's own
    main_name: str | None = None
    # a merge's link words to add as other names; `None`, every one
    link_akas: list[str] | None = None
    # a hard re-point's name for the links: one of the target's own
    use_name: str | None = None
    # whether the target learns names at all (ruling H2: "link only"
    # teaches none)
    teach_names: bool = True
    # the target's own fields that named the stub, redirected
    redirected: set[str] = set()
    # a merge's other names added from the links' words
    link_names: list[str] = []

    @property
    def verb(self) -> str:
        return "merged into" if self.merge else "re-pointed to"


def _fact_changes(
    job: _Job, shown_texts: list[str]
) -> tuple[dict[str, dict], int, list]:
    """`(changes, links, own facts)`: each other fact's changes (`text`, its
    links to the stub pointed at the target; `origin`, a tie to the stub
    filed under the target, a belief the stub held held by the target),
    the fact links moved, and the stub's own
    facts (`FactState`s), which `copy_facts` moves to the target."""

    view, stub_id, target_id = job.view, job.stub.id, job.target.id
    rewrite = _rewriter(view, stub_id, target_id, shown_texts, job.use_name)
    changes: dict[str, dict] = {}
    links = 0
    for owner, fact in view.referencing(stub_id, any_date=True):
        if owner == stub_id or fact.fact_id in changes:
            continue
        text, moved = rewrite(fact.text or "", owner, True)
        links += moved
        changes[fact.fact_id] = {"text": text}
    # a character's exception filed under a tie to the stub, and any fact
    # the stub holds as a belief, go over to the target
    own_ids = {fact.fact_id for fact in job.world.live_facts(stub_id)}
    for fact in job.world.live_facts():
        origin = fact.origin or {}
        keys = [key for key in ("tie", "held_by") if origin.get(key) == stub_id]
        if fact.fact_id in own_ids:
            continue
        if keys:
            changes.setdefault(fact.fact_id, {})["origin"] = {
                **origin,
                **{key: target_id for key in keys},
            }
    own = job.world.live_facts(stub_id)
    if job.fact_ids is not None:
        wanted = set(job.fact_ids)
        own = [fact for fact in own if fact.fact_id in wanted]
    return changes, links, own


def _relinked(
    view: WorldView, text: str, same: set[str], target_id: str, plain: bool
) -> str:
    """`text` with its links to `same` (the target, and what stands for it)
    pointed at the target: as their words, plain, when `plain` (a thing
    never links to itself)."""

    def one(found: re.Match[str]) -> str:
        if found.group(1) not in same:
            return str(found.group(0))
        shown = str(
            found.group(2) or "".join(seg.text for seg in view.segments(found.group(0)))
        )
        return shown if plain else ref(target_id, shown)

    return REF_PATTERN.sub(one, text)


def _moved_category(kind: str, category: str, dated: bool) -> str:
    """`category`, if a `kind` thing has it; else the kind's fallback
    (`kinds.moved_category`, as `default_category` picks for a place or a
    character), a catch-all one, or its kind's first."""

    return moved_category(kind, category, dated)


def copy_facts(
    rev: Revision,
    view: WorldView,
    fact_ids: Sequence[str],
    target_id: str,
    *,
    plain_self_links: bool,
    standing_for: Sequence[str] = (),
    keep: bool = False,
) -> dict[str, str]:
    """Move the facts `fact_ids` (of any owners) onto `target_id`, in `rev`,
    the way a fact changes thing (ruling R1): each is copied as a new fact
    and the original removed, since replay and undo key a fact by its id.
    Returns `old id -> new id`. `view` is the revision's own
    (`world.view()` inside it), so what `rev` wrote is seen.

    Each copy keeps its dates and origin; a category the target's kind
    lacks becomes `default_category`'s (`_moved_category`). Its holder
    stays its holder, and one its old owner held implicitly (a `belief`
    fact, `entries.held_by`) is written into its origin, so it stays its
    old owner's belief on the target. Links to the target, and to
    `standing_for` (a stub being re-pointed onto it, whose holdings become
    the target's too), point at the target: as plain words, with
    `plain_self_links`. An override among the moved facts points at its
    copy, the copies' own and every other live fact's, on any date; so
    does an exception's `rejects_fact` (its origin).

    With `keep` ("Copy to..."), the originals stay: nothing that names
    them (an override, an exception's `rejects_fact`) is re-pointed, and
    each copy overrides what its original does; a copied summary is a
    plain fact on the target.

    A `KeyError` for a fact or target that isn't live."""

    target = view.thing(target_id)
    if target is None:
        raise KeyError(f"no such thing: {target_id}")
    same = {target_id, *standing_for}
    found: list[tuple[str, FactState]] = []
    for fact_id in dict.fromkeys(fact_ids):
        hit = view.fact(fact_id)
        if hit is None:
            raise KeyError(f"no such fact: {fact_id}")
        found.append(hit)
    moving = {fact.fact_id for _owner, fact in found}
    copies: dict[str, str] = {}
    # each copy's origin, as written
    origins: dict[str, dict[str, object] | None] = {}
    for owner_id, fact in found:
        origin = dict(fact.origin) if fact.origin is not None else None
        owner = view.thing(owner_id)
        if owner is not None and "held_by" not in (origin or {}):
            holder = entries.held_by(view, fact, owner)
            if holder is not None:
                origin = entries.with_held_by(origin, holder)
        if origin is not None and origin.get("held_by") in standing_for:
            origin["held_by"] = target_id
        if keep and origin is not None and "summary" in origin:
            # a copy is never the target's summary
            del origin["summary"]
        origins[fact.fact_id] = origin
        copies[fact.fact_id] = rev.add_fact(
            target_id,
            _moved_category(target.kind, fact.category, fact.valid_from is not None),
            _relinked(view, fact.text, same, target_id, plain_self_links),
            valid_from=fact.valid_from,
            valid_until=fact.valid_until,
            origin=origin,
            overrides=(
                list(fact.overrides)
                if keep
                else [o for o in fact.overrides if o not in moving]
            )
            or None,
        )
    if keep:
        return copies
    for _owner, fact in found:
        if any(o in moving for o in fact.overrides):
            rev.correct_fact(
                copies[fact.fact_id],
                overrides=[copies.get(o, o) for o in fact.overrides],
            )
    for _owner, fact in view.overriding(list(moving)):
        if fact.fact_id not in moving:
            rev.correct_fact(
                fact.fact_id, overrides=[copies.get(o, o) for o in fact.overrides]
            )
    for _owner, fact in found:
        rejected = (fact.origin or {}).get("rejects_fact")
        if rejected in moving:
            origin = dict(origins[fact.fact_id] or {})
            origin["rejects_fact"] = copies[str(rejected)]
            rev.correct_fact(copies[fact.fact_id], origin=origin)
    copied = set(copies.values())
    for _owner, fact in view.rejecting(list(moving)):
        if fact.fact_id in moving or fact.fact_id in copied:
            continue
        origin = dict(fact.origin or {})
        origin["rejects_fact"] = copies[str(origin["rejects_fact"])]
        rev.correct_fact(fact.fact_id, origin=origin)
    for fact_id in moving:
        rev.remove_fact(fact_id)
    return copies


def _names_target(job: _Job, value: object) -> bool:
    """Whether a carried value names the target, or a thing inside it."""

    ids = (
        [value] if isinstance(value, str) else value if isinstance(value, list) else []
    )
    return any(
        isinstance(thing_id, str)
        and (thing_id == job.target.id or sits_in(job.view, thing_id, job.target.id))
        for thing_id in ids
    )


def _carried_fields(job: _Job) -> dict[str, object]:
    """The stub's other own fields the target takes: those its kind has
    and it has no value for, never one naming the target (or a thing
    inside it). The rest are noted, unless
    the target holds the same value."""

    target = job.target
    types = {spec.name: spec.type for spec in get_kind(target.kind).fields}
    carried: dict[str, object] = {}
    for field, value in job.stub.fields.items():
        if field in _OWN_HANDLED or value is None:
            continue
        if field in job.redirected:
            # the target's own value named the stub: redirected
            # (`_self_uses`)
            continue
        held = target.fields.get(field)
        if held == value:
            continue
        if types.get(field) in ("thing", "things") and _names_target(job, value):
            job.notes.append(
                f"{job.stub_name}'s {field} isn't carried over:"
                f" it names {job.target_name}, or a place inside it"
            )
        elif field in types and held is None:
            carried[field] = value
        else:
            job.notes.append(f"{job.stub_name}'s {field} isn't carried over")
    return carried


def _names(job: _Job, shown_texts: list[str]) -> tuple[list[dict], list[str]]:
    """`(aka, added)`: the target's other names with the stub's name, its
    other names and the links' shown texts added (common, not everyday),
    unless the target or another thing has that name already. A hard
    re-point (`use_name`) adds the stub's name and other names only: the
    links' words are gone from the world, but a later reply writing the
    stub's name must find the target rather than make the stub again."""

    view, target = job.view, job.target
    aka = list(target.fields.get("aka") or [])
    if not job.teach_names:
        return aka, []
    if job.use_name is not None:
        shown_texts = []
    held = {name_key(job.target_name)} | {
        name_key(entry["name"]) for entry in aka if isinstance(entry, dict)
    }
    taken = _other_name_keys(view, {job.stub.id, target.id})
    stub_aka = [
        entry["name"]
        for entry in job.stub.fields.get("aka") or []
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    ]
    added: list[str] = []
    for name in [job.stub_name, *stub_aka, *shown_texts]:
        name = " ".join(name.split())
        key = name_key(name)
        if not key or key in held or key in taken:
            continue
        held.add(key)
        added.append(name)
        aka.append({"name": name, "tag": "common", "everyday": False})
    return aka, added


def _target_names(state: ThingState, name: str) -> list[str]:
    """The target's own names: its name, then its other names."""

    return [
        name,
        *(
            entry["name"]
            for entry in state.fields.get("aka") or []
            if isinstance(entry, dict) and isinstance(entry.get("name"), str)
        ),
    ]


def _merge_names(job: _Job, shown_texts: list[str]) -> tuple[list[dict], list[str]]:
    """A merge's `(aka, added)`: the target's other names, less one that is
    now the main name, then the side's name that isn't the main name, the
    stub's other names (each keeping its tag) and the links' shown texts,
    added unless the main name, the list or another thing has that name
    already. None is everyday but the target's own."""

    view, target = job.view, job.target
    main = job.main_name or job.target_name
    main_key = name_key(main)
    aka = [
        entry
        for entry in target.fields.get("aka") or []
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("name"), str)
            and name_key(entry["name"]) == main_key
        )
    ]
    held = {main_key} | {
        name_key(entry["name"])
        for entry in aka
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    taken = _other_name_keys(view, {job.stub.id, target.id})
    other = job.stub_name if main_key != name_key(job.stub_name) else job.target_name
    wanted: list[tuple[str, str]] = [(other, "common")]
    for entry in job.stub.fields.get("aka") or []:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            tag = entry.get("tag")
            wanted.append((entry["name"], tag if isinstance(tag, str) else "common"))
    if job.link_akas is not None:
        allowed = {name_key(name) for name in job.link_akas}
        shown_texts = [text for text in shown_texts if name_key(text) in allowed]
    names_first = len(wanted)
    wanted += [(text, "common") for text in shown_texts]
    added: list[str] = []
    job.link_names = []
    for index, (name, tag) in enumerate(wanted):
        name = " ".join(name.split())
        key = name_key(name)
        if not key or key in held or key in taken:
            continue
        held.add(key)
        added.append(name)
        if index >= names_first:
            job.link_names.append(name)
        aka.append({"name": name, "tag": tag, "everyday": False})
    return aka, added


def _inside_either(job: _Job, thing_id: str) -> bool:
    """Whether `thing_id` is, or sits inside, the target or the stub (which
    becomes the target)."""

    return sits_in(job.view, thing_id, job.target.id) or sits_in(
        job.view, thing_id, job.stub.id
    )


def _said(view: WorldView, value: object) -> str:
    """A field value as the owner reads it: a thing's name, filings by
    what they're filed in, else a short form."""

    if isinstance(value, str):
        return view.name_of(value) or value
    if isinstance(value, list) and any(
        isinstance(item, dict) and "target" in item for item in value
    ):
        return (
            ", ".join(
                view.name_of(filing.target) or filing.target
                for filing in _filings(value)
            )
            or "none"
        )
    if isinstance(value, list):
        return ", ".join(_said(view, item) for item in value) or "none"
    return str(value)


def _shown_before(
    job: _Job, field: str, date: object, uses: list[_FieldUse]
) -> str | None:
    """What the target's `field` shows from `date` once its value there is
    retired: its latest value dated before (as already redirected in
    `uses`), or `None` when there's none and the field is empty."""

    if date is None:
        return None
    instant = getattr(date, "instant", None)
    changed = {
        (use.field, getattr(use.date, "instant", None)): use
        for use in uses
        if use.thing_id == job.target.id
    }
    found: object = None
    for entry in job.world.timeline(job.target.id):
        if entry.change != "field" or entry.field != field:
            continue
        at = getattr(entry.date, "instant", None)
        if at is not None and instant is not None and at >= instant:
            break
        use = changed.get((field, at))
        if use is not None and use.clear:
            # retired too: the one before shows
            continue
        found = entry.value if use is None else use.value
    return _said(job.view, found) if found else None


def _self_uses(job: _Job) -> list[_FieldUse]:
    """A merge's target values naming the stub, redirected rather than
    refused: the merged entry sits where the stub sat. A filing into the
    stub goes (the target takes the stub's own filings, `_own_filings`),
    one `within` it is within no part; a single thing field takes the
    stub's own value, cleared when the stub has none, or when its value
    would name the target or make a loop; a list drops the stub. A value
    left empty is retired, so an earlier one shows. Each one is noted."""

    view, stub, target = job.view, job.stub, job.target
    types = {spec.name: spec.type for spec in get_kind(target.kind).fields}
    stub_filings = [
        f for f in filings_of(view, stub.id, live=False) if f.target != target.id
    ]
    uses: list[_FieldUse] = []
    for entry in job.world.timeline(target.id):
        if entry.change != "field" or entry.field is None:
            continue
        field, value = entry.field, entry.value
        kind = types.get(field)
        new: object = None
        label = field.replace("_", " ")
        if field == "filings":
            filings = _filings(value)
            if not any(stub.id in (f.target, f.within) for f in filings):
                continue
            kept = [
                f.model_copy(update={"within": None}) if f.within == stub.id else f
                for f in filings
                if f.target != stub.id
            ]
            new = _dumped(kept) or None
            if any(f.target == stub.id for f in filings):
                job.notes.append(
                    f"{job.target_name} was filed in {job.stub_name}: "
                    + (
                        f"it takes {job.stub_name}'s filings, "
                        f"{_said(view, _dumped(stub_filings))}"
                        if stub_filings
                        else "it's no longer filed there"
                    )
                )
            if any(f.within == stub.id for f in filings):
                job.notes.append(
                    f"{job.target_name} was within {job.stub_name}: it's within"
                    " no part now"
                )
            if new is None and entry.date is not None:
                earlier = _shown_before(job, field, entry.date, uses)
                if earlier is not None:
                    job.notes.append(
                        f"{job.target_name}'s filings fall back to its earlier"
                        f" filings, {earlier}"
                    )
        else:
            if kind == "thing" and value == stub.id:
                own_value = stub.fields.get(field)
                other = view.thing(own_value) if isinstance(own_value, str) else None
                allowed = FIELD_TARGET_KINDS.get(field, (target.kind,))
                if (
                    other is not None
                    and other.kind in allowed
                    and not _inside_either(job, other.id)
                ):
                    new = other.id
            elif kind == "things" and isinstance(value, list) and stub.id in value:
                new = [thing_id for thing_id in value if thing_id != stub.id] or None
            else:
                continue
            if new is None:
                earlier = _shown_before(job, field, entry.date, uses)
                job.notes.append(
                    f"{job.target_name}'s {label} was {job.stub_name}: "
                    + (
                        f"it falls back to its earlier {label}, {earlier}"
                        if earlier is not None
                        else "it's cleared"
                    )
                )
            elif kind == "thing":
                job.notes.append(
                    f"{job.target_name}'s {label} was {job.stub_name}: it takes"
                    f" {job.stub_name}'s, {view.name_of(str(new))}"
                )
            else:
                job.notes.append(
                    f"{job.target_name}'s {label} named {job.stub_name}: it no"
                    " longer does"
                )
        job.redirected.add(field)
        uses.append(
            _FieldUse(
                thing_id=target.id,
                field=field,
                date=entry.date,
                value=new,
                clear=new is None,
            )
        )
    return uses


def _own_filings(job: _Job) -> list[Filing]:
    """The stub's own filings the target takes (at write time, `_carry`):
    each as stored, never one into the target itself or one that would put
    the target inside itself (a note says why), nor one into an entry
    gone at the view."""

    view, target = job.view, job.target
    found: list[Filing] = []
    for filing in filings_of(view, job.stub.id, live=False):
        where = view.name_of(filing.target) or filing.target
        if filing.target == target.id:
            if not job.merge or "filings" not in job.redirected:
                job.notes.append(
                    f"{job.target_name} isn't filed in itself, as"
                    f" {job.stub_name} was filed in it"
                )
            continue
        if view.thing(filing.target) is None:
            continue
        if sits_in(view, filing.target, target.id):
            job.notes.append(
                f"{job.target_name} isn't filed in {where}: it would be inside itself"
            )
            continue
        found.append(filing)
    return found


def _job(world: World, stub_id: str, target_id: str, *, merge: bool = False) -> _Job:
    view = world.view()
    stub = view.thing(stub_id)
    if stub is None:
        raise KeyError(f"no such thing: {stub_id}")
    stub_name = view.name_of(stub_id) or stub_id
    if not merge and not stub.is_stub:
        raise ValueError(f"not a stub: {stub_name}")
    if target_id == stub_id:
        raise ValueError(
            "a thing can't be merged into itself"
            if merge
            else "a stub can't be re-pointed onto itself"
        )
    target = view.thing(target_id)
    if target is None:
        raise KeyError(f"no such thing: {target_id}")
    target_name = view.name_of(target_id) or target_id
    if target.stub_ignored:
        raise ValueError(f"{target_name} is an ignored stub")
    if merge and not kinds_can_be_one(stub.kind, target.kind):
        raise ValueError(
            f"{stub_name} is a {stub.kind} and {target_name} a {target.kind}:"
            " only entries of one kind merge"
        )
    if merge and target.is_stub and not stub.is_stub:
        raise ValueError(
            f"{target_name} is a stub: re-point it onto {stub_name} instead"
        )
    return _Job(
        world=world,
        view=view,
        stub=stub,
        target=target,
        stub_name=stub_name,
        target_name=target_name,
        notes=[],
        merge=merge,
    )


class RepointPlan:
    """A re-point read and decided (`plan_repoint`), not yet written:
    `write` writes it into a revision, which may be another writer's own
    (an accept that is "the same thing" re-points the stub it expanded in
    its revision), and `result` reports it once written."""

    def __init__(
        self,
        job: _Job,
        uses: list[_FieldUse],
        changes: dict[str, dict],
        links: int,
        own: list,
        own_filings: list[Filing],
        carried: dict[str, object],
        aka: list[dict],
        added: list[str],
    ) -> None:
        self._job = job
        self._uses = uses
        self._changes = changes
        self._links = links
        self._own = own
        self._own_filings = own_filings
        self._carried = carried
        self._aka = aka
        self._added = added
        # old fact id -> its copy's, once written
        self.copies: dict[str, str] = {}

    @property
    def stub_id(self) -> str:
        return self._job.stub.id

    @property
    def target_id(self) -> str:
        return self._job.target.id

    @property
    def notes(self) -> list[str]:
        return self._job.notes

    @property
    def aka_added(self) -> list[str]:
        """The names the target takes as other names."""

        return list(self._added)

    @property
    def link_akas(self) -> list[str]:
        """A merge's other names that come from the words of links to the
        stub (not its names), for the owner to untick."""

        return list(self._job.link_names)

    @property
    def uses(self) -> int:
        """How many field values that point at the stub are re-pointed."""

        return len(self._uses)

    @property
    def links(self) -> int:
        """How many fact links to the stub are pointed at the target."""

        return self._links

    @property
    def use_counts(self) -> dict[str, int]:
        """The field values re-pointed, by what they are: `filings` and the
        other `fields`."""

        counts = {"fields": 0, "filings": 0}
        for use in self._uses:
            counts["filings" if use.field == "filings" else "fields"] += 1
        return counts

    @property
    def note(self) -> str:
        """The revision note a re-point (or merge) of its own writes."""

        job = self._job
        if job.merge:
            return f"merged {job.stub_name} into {job.target_name}"
        return f"re-pointed {job.stub_name} to {job.target_name}"

    def _carry(self, rev: Revision) -> None:
        """The stub's own filings onto the target, in `rev` (the revision's
        own view): beside its filings, each with its role, dates, `within`
        and exceptions (each mapped onto its moved copy, one that didn't
        move dropped). One into an entry the target is filed in already
        adds its exceptions to that filing. A `within` that doesn't hold
        under the target is dropped, and one the store still refuses is
        left out, each with a note."""

        job, target_id = self._job, self.target_id
        if not self._own_filings:
            return
        live = job.world.view()
        value = filings_of(live, target_id, live=False)
        changed = False
        for filing in self._own_filings:
            where = live.name_of(filing.target) or filing.target
            exceptions = [self.copies[e] for e in filing.exceptions if e in self.copies]
            filing = filing.model_copy(update={"exceptions": exceptions})
            same = next(
                (i for i, held in enumerate(value) if held.target == filing.target),
                None,
            )
            if same is not None:
                held = value[same]
                joined = list(dict.fromkeys([*held.exceptions, *exceptions]))
                if joined != held.exceptions:
                    value[same] = held.model_copy(update={"exceptions": joined})
                    changed = True
                continue
            errors = check_filings(live, target_id, _dumped([*value, filing]))
            if errors and filing.within is not None:
                within = live.name_of(filing.within) or filing.within
                filing = filing.model_copy(update={"within": None})
                retry = check_filings(live, target_id, _dumped([*value, filing]))
                if not retry:
                    job.notes.append(
                        f"{job.target_name} is filed in {where} within no part:"
                        f" {within} isn't a part of it"
                    )
                errors = retry
            if errors:
                job.notes.append(f"{job.target_name} isn't filed in {where}")
                continue
            value.append(filing)
            changed = True
        if changed:
            rev.set_field(
                target_id,
                "filings",
                _dumped(value),
                filings_since(job.world, target_id),
            )

    def _checked(self, use: _FieldUse) -> object:
        """Another thing's re-pointed filings, each `within` that doesn't
        hold once the target is filed where it will be dropped (within no
        part), with a note."""

        if use.field != "filings" or use.clear:
            return use.value
        job = self._job
        live = job.world.view()
        filings = _filings(use.value)
        if not check_filings(live, use.thing_id, _dumped(filings)):
            return use.value
        name = live.name_of(use.thing_id) or use.thing_id
        fixed: list[Filing] = []
        for filing in filings:
            if filing.within is not None and check_filings(
                live, use.thing_id, _dumped([filing])
            ):
                job.notes.append(
                    f"{name}'s filing in {live.name_of(filing.target)} is within"
                    f" no part: {live.name_of(filing.within)} isn't inside it"
                )
                filing = filing.model_copy(update={"within": None})
            fixed.append(filing)
        return _dumped(fixed)

    def write(self, rev: Revision) -> None:
        """Every change, in `rev`; the stub is removed last. Written again
        into a fresh revision (the first rolled back), it writes the
        same."""

        job, target_id = self._job, self.target_id
        changes = {fact_id: dict(change) for fact_id, change in self._changes.items()}
        recategorised = sum(
            1
            for fact in self._own
            if fact.category not in get_kind(job.target.kind).categories
        )
        if recategorised:
            job.notes.append(
                f"{recategorised} of {job.stub_name}'s facts moved under another"
                f" category: a {job.target.kind} has no such category"
            )
        # the stub's own facts, copied to the target (the stub's links in
        # them its words), then everyone else's changes
        self.copies = copy_facts(
            rev,
            job.world.view(),
            [fact.fact_id for fact in self._own],
            target_id,
            plain_self_links=True,
            standing_for=[self.stub_id],
        )
        for fact_id, change in changes.items():
            rev.correct_fact(fact_id, **change)
        # the target's own values first (a merge's redirects), then the
        # stub's filings onto it, then everyone else's, whose `within`
        # the target's filings decide
        uses = sorted(self._uses, key=lambda use: use.thing_id != target_id)
        for use in uses:
            if use.thing_id != target_id:
                break
            self._write_use(rev, use)
        self._carry(rev)
        # a `within` holds once its part's own filing is written, whichever
        # thing comes first: what holds now goes first, then the rest
        pending = [use for use in uses if use.thing_id != target_id]
        while pending:
            ready = [use for use in pending if self._holds(use)]
            for use in ready or pending[:1]:
                self._write_use(rev, use)
                pending.remove(use)
        renamed = job.main_name not in (None, job.target_name)
        if self._added or (
            (job.merge or renamed) and self._aka != (job.target.fields.get("aka") or [])
        ):
            self._write_aka(rev)
        if renamed:
            # a correction of the name it holds now, at that value's date
            rev.set_field(
                target_id,
                "name",
                job.main_name,
                job.view.field_since(target_id, "name"),
            )
        for field, value in self._carried.items():
            rev.set_field(target_id, field, value, None)
        rev.remove_thing(self.stub_id)

    def _holds(self, use: _FieldUse) -> bool:
        """Whether the use can be written as it is now: anything but
        filings, and filings the store takes (each `within` a part of its
        entry) at the revision's own view."""

        if use.field != "filings" or use.clear:
            return True
        value = use.value if isinstance(use.value, list) else []
        return not check_filings(self._job.world.view(), use.thing_id, value)

    def _write_aka(self, rev: Revision) -> None:
        """The target's other names, in `rev`: the value showing now (at
        its date) becomes `_aka`, and every other dated value takes the
        names added too, so a scene set at any date knows them -- as
        filings are rewritten at every value."""

        job, target_id = self._job, self.target_id
        latest = job.view.field_since(target_id, "aka")
        added = [
            entry
            for entry in self._aka
            if isinstance(entry, dict) and entry.get("name") in self._added
        ]
        for entry in job.world.timeline(target_id):
            if entry.change != "field" or entry.field != "aka":
                continue
            if getattr(entry.date, "instant", None) == getattr(latest, "instant", None):
                continue
            value = [e for e in entry.value or [] if isinstance(e, dict)]
            held = {name_key(str(e.get("name", ""))) for e in value}
            extra = [e for e in added if name_key(str(e["name"])) not in held]
            if extra:
                rev.set_field(target_id, "aka", [*value, *extra], entry.date)
        rev.set_field(target_id, "aka", self._aka, latest)

    def _write_use(self, rev: Revision, use: _FieldUse) -> None:
        if use.clear:
            rev.remove_field_value(use.thing_id, use.field, use.date)
        else:
            rev.set_field(use.thing_id, use.field, self._checked(use), use.date)

    def result(self) -> RepointResult:
        """What was re-pointed, once `write`n. Prose is refreshed only
        where its input changed: the target's facts and rendered fields,
        and the rendered fields that pointed at the stub."""

        target_id = self.target_id
        prose = list(
            dict.fromkeys(
                [
                    *(
                        [target_id]
                        if self._job.merge
                        or self._job.main_name not in (None, self._job.target_name)
                        or self._own
                        or set(self._carried) - set(UNRENDERED_FIELDS)
                        else []
                    ),
                    *(
                        use.thing_id
                        for use in self._uses
                        if use.field not in UNRENDERED_FIELDS
                    ),
                ]
            )
        )
        return RepointResult(
            stub_name=self._job.stub_name,
            target_name=self._job.main_name or self._job.target_name,
            links=self._links,
            aka_added=self._added,
            facts_moved=len(self._own),
            notes=list(dict.fromkeys(self._job.notes)),
            prose=prose,
        )


def plan_repoint(
    world: World,
    stub_id: str,
    target_id: str,
    *,
    as_kind: str | None = None,
    use_name: str | None = None,
    teach_names: bool = True,
    retitle: bool = False,
) -> RepointPlan:
    """Read and decide a re-point of the stub `stub_id` onto `target_id`
    (see the module docstring), writing nothing. Raises `KeyError` for a
    missing thing and `ValueError` for what's refused. With `as_kind`, the
    target is taken to be that kind (a stub whose kind changes in the same
    revision, before the plan is written): fields, filing and the moved
    facts' categories are decided for it. With `use_name` (the "hard
    re-point"), every link's words become that name, which must be one of
    the target's own (its name or an other name; any case, written as the
    target has it): anything else is refused. With `teach_names` false
    ("link only", ruling H2) the target learns no names at all. With
    `retitle` ("Rename the entry to these words", polish 4) the target
    takes the stub's name as its main name, its old one an other name;
    refused when a third thing goes by the stub's name."""

    job = _job(world, stub_id, target_id)
    job.teach_names = teach_names
    if retitle:
        refuse_name_in_use(job.view, job.stub_name, {stub_id, target_id})
        job.main_name = job.stub_name
    if use_name is not None:
        job.use_name = target_name(job.view, target_id, use_name)
    if as_kind is not None and as_kind != job.target.kind:
        job.target = job.target.model_copy(update={"kind": as_kind})
    return _plan(job)


def _plan(job: _Job) -> RepointPlan:
    world = job.world
    blocked = [
        f"the scene {scene['name']}"
        for scene in thing_references(world, job.stub.id)["scenes"]
    ]
    if job.merge:
        uses = _self_uses(job)
        uses += _field_uses(
            world,
            job.view,
            job.stub,
            job.target,
            blocked,
            job.notes,
            skip_target=True,
        )
    else:
        uses = _field_uses(world, job.view, job.stub, job.target, blocked, job.notes)
    if blocked:
        raise ValueError(
            f"{job.stub_name} can't be {job.verb} {job.target_name}:"
            f" {'; '.join(dict.fromkeys(blocked))}"
        )

    shown_texts: list[str] = []
    changes, links, own = _fact_changes(job, shown_texts)
    own_filings = _own_filings(job)
    carried = _carried_fields(job)
    if job.merge or job.main_name is not None:
        aka, added = _merge_names(job, shown_texts)
    else:
        aka, added = _names(job, shown_texts)
    return RepointPlan(job, uses, changes, links, own, own_filings, carried, aka, added)


def plan_merge(
    world: World,
    from_id: str,
    into_id: str,
    *,
    fact_ids: Sequence[str] | None = None,
    main_name: str | None = None,
    link_akas: Sequence[str] | None = None,
) -> RepointPlan:
    """Read and decide a merge of the thing `from_id` into `into_id` (any
    two things; see the module docstring), writing nothing: the facts
    `fact_ids` of `from_id` move (`None`, all of them), and `into_id`
    takes `main_name` (either side's name; `None`, its own) and, of the
    links' words, only `link_akas` as other names (`None`, all). Raises
    `KeyError` for a missing thing and `ValueError` for what's refused."""

    job = _job(world, from_id, into_id, merge=True)
    if main_name is not None:
        names = {name_key(name): name for name in (job.stub_name, job.target_name)}
        if name_key(main_name) not in names:
            raise ValueError(
                f"the main name is {job.target_name} or {job.stub_name},"
                f" not {' '.join(main_name.split())}"
            )
        main_name = names[name_key(main_name)]
    job.main_name = main_name
    job.fact_ids = list(fact_ids) if fact_ids is not None else None
    job.link_akas = list(link_akas) if link_akas is not None else None
    return _plan(job)


def repoint_stub(
    world: World,
    stub_id: str,
    target_id: str,
    *,
    use_name: str | None = None,
    teach_names: bool = True,
    retitle: bool = False,
) -> RepointResult:
    """Point everything that names the stub `stub_id` at `target_id`, and
    remove the stub, in one revision (see the module docstring); with
    `use_name`, the hard re-point, and without `teach_names`, no names
    taught, and with `retitle`, the target renamed to the stub's name
    (`plan_repoint`). Raises `KeyError` for a missing thing and
    `ValueError` for what's refused, writing nothing."""

    plan = plan_repoint(
        world,
        stub_id,
        target_id,
        use_name=use_name,
        teach_names=teach_names,
        retitle=retitle,
    )
    with world.revision(Source.manual(note=plan.note)) as rev:
        plan.write(rev)
    result = plan.result()
    log.info(
        "worlds.stub_repointed",
        stub=stub_id,
        target=target_id,
        links=result.links,
        uses=plan.uses,
        facts_moved=result.facts_moved,
        aka_added=result.aka_added,
        use_name=use_name,
    )
    return result


def move_fact(
    world: World,
    fact_id: str,
    target_id: str,
    *,
    notes: list[str] | None = None,
    prose: list[str] | None = None,
) -> str:
    """Move one fact onto another entry (a fact row's "Move to..."), in
    one revision (`copy_facts`, ruling R1): a new fact on the target with
    its dates, origin and holder, the original removed, every override of
    it pointed at the copy, its links to the target made words. Returns
    the copy's id.

    Refused with `ValueError`, writing nothing: a fact that isn't live
    (removed, or never was), an entry's summary, a target that's gone or
    an ignored stub, and the fact's own entry. A category the target's kind lacks becomes
    `default_category`'s, with a note in `notes`. `prose` gains each of
    the two entries whose prose is written from the fact's category (the
    old owner's, the copy's)."""

    view = world.view()
    found = view.fact(fact_id)
    if found is None:
        raise ValueError(f"no such fact, or it was removed: {fact_id}")
    owner_id, fact = found
    if entries.is_summary_fact(fact):
        raise ValueError("an entry's summary stays its own: it can't be moved")
    target = view.thing(target_id)
    if target is None or target.stub_ignored:
        raise ValueError(f"no such entry to move it to: {target_id}")
    owner = view.thing(owner_id)
    assert owner is not None
    owner_name = view.name_of(owner_id) or owner_id
    target_name = view.name_of(target_id) or target_id
    if owner_id == target_id:
        raise ValueError(f"the fact is already {target_name}'s")
    category = _moved_category(target.kind, fact.category, fact.valid_from is not None)
    if category != fact.category and notes is not None:
        notes.append(
            f"a {target.kind} has no {fact.category} facts:"
            f" it's under {category} on {target_name}"
        )
    note = f"moved a fact from {owner_name} to {target_name}"
    with world.revision(Source.manual(note=note)) as rev:
        new_id = copy_facts(
            rev, world.view(), [fact_id], target_id, plain_self_links=True
        )[fact_id]
    if prose is not None:
        for thing_id, kind, read in (
            (owner_id, owner.kind, fact.category),
            (target_id, target.kind, category),
        ):
            if prose_reads(kind, read) and thing_id not in prose:
                prose.append(thing_id)
    log.info(
        "worlds.fact_moved",
        fact=fact_id,
        copy=new_id,
        owner=owner_id,
        target=target_id,
        category=category,
    )
    return new_id


def rename_everywhere(rev: Revision, world: World, thing_id: str, name: str) -> None:
    """Rename `thing_id` to `name` (Name it…, languages 4a revised), in
    `rev`: a stub forgets its old name; anything else keeps it as a common
    other name (`retitle`). Every link to it that showed the old name
    shows the new one. Refused (`ValueError`) when another thing already
    goes by `name`."""

    view = world.view()
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")
    name = " ".join(name.split())
    old = view.name_of(thing_id) or ""
    if state.is_stub:
        refuse_name_in_use(view, name, {thing_id})
        rev.set_field(thing_id, "name", name, None)
    else:
        retitle(rev, world, thing_id, name)
    shown = f"[[thing:{thing_id}|{old}]]"
    for _owner, fact in view.referencing(thing_id):
        if shown in fact.text:
            rev.correct_fact(
                fact.fact_id,
                text=fact.text.replace(shown, f"[[thing:{thing_id}|{name}]]"),
            )


def drop_other_names(rev: Revision, world: World, thing_id: str, aka: object) -> None:
    """Set `thing_id`'s other names to `aka`, in `rev`. A link to it that
    showed one of the names dropped shows its main name instead (owner,
    languages 4a revised: "Drassone" leaves the Principality of Drassone's
    facts, free for its capital)."""

    view = world.view()
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")
    kept = {
        name_key(str(entry.get("name") or ""))
        for entry in (aka if isinstance(aka, list) else [])
        if isinstance(entry, dict)
    }
    name = view.name_of(thing_id) or ""
    dropped = (
        {
            name_key(str(entry.get("name") or ""))
            for entry in state.fields.get("aka") or []
            if isinstance(entry, dict)
        }
        - kept
        - {name_key(name), ""}
    )
    rev.set_field(thing_id, "aka", aka, None)
    if not dropped:
        return
    link = re.compile(r"\[\[thing:" + re.escape(thing_id) + r"\|([^\]]*)\]\]")

    def shown(match: re.Match) -> str:
        if name_key(match.group(1)) in dropped:
            return f"[[thing:{thing_id}|{name}]]"
        return match.group(0)

    for _owner, fact in view.referencing(thing_id):
        text = link.sub(shown, fact.text)
        if text != fact.text:
            rev.correct_fact(fact.fact_id, text=text)
