"""Tags and filings, read through a `WorldView`.

Every entry has one `tag` (what it is: "river", "custom", "ruler") and any
number of `filings`, each into a target entry with an optional role, dates
(`since`/`until`), and for a person a `within` (a part of the target it
belongs in) and "but..." `exceptions` (fact ids). Filing is the one
connection between entries (the spec's "The model"); mentions (fact
references) are not filings.

A filing holds over its own dates: from `since` (or always) until `until`
(or for good). At the latest telling (`view.at is None`) only the filings
that haven't ended hold, as with ties. A filing whose target is deleted is
kept, hidden, and shows again once the target is back.

A page's Connected section groups what is filed in it by each entry's tag
(`connected`), headed by the tag pluralised (`tag_heading`); an untagged
entry goes under "Other".

The store runs `check_filings` on every write of `filings`; it refuses a
filing into the thing itself, a `within` that doesn't sit in its target,
and a cycle (a thing filed, directly or through others, in itself). It
also refuses a new target or `within` that isn't live, so a deleted entry
can't be used to close a cycle that would reappear when it's restored.
Undo restores rows without these checks, so undoing a removal can still
bring a cycle back: every reader that walks filings must be cycle-safe
(`sits_in` visits each thing once).

A stored filing always has the full shape (`stored_filings_value`), with
a blank role kept as `None`.

An event's `place` and an item's `owner` are filings too (`FIELD_ROLES`):
an event "took place in" its place, an item is "owned by" its owner.
Whatever would write those fields writes the filing instead, and readers
read the filing.
"""

from collections.abc import Sequence

import structlog
from pydantic import BaseModel, Field, ValidationError

from .dates import WorldDate
from .view import ThingState, WorldView

log = structlog.get_logger("talemate.world.filing")

__all__ = [
    "FIELD_ROLES",
    "OTHER_HEADING",
    "Filing",
    "Group",
    "check_filings",
    "connected",
    "filed_in",
    "filed_index",
    "filing_live",
    "filings_of",
    "mentioned_in",
    "sits_in",
    "stored_filings_value",
    "tag_heading",
    "tag_of",
    "tags_in_use",
]

# the heading of the group of untagged entries
OTHER_HEADING = "Other"

# the fields that are filings, by kind: `(kind, field) -> role`
FIELD_ROLES: dict[tuple[str, str], str] = {
    ("event", "place"): "took place in",
    ("item", "owner"): "owned by",
}


class Filing(BaseModel):
    target: str
    role: str | None = None
    since: WorldDate | None = None
    until: WorldDate | None = None
    within: str | None = None
    exceptions: list[str] = Field(default_factory=list)


class Group(BaseModel):
    tag: str | None
    heading: str
    rows: list[tuple[str, Filing]]


def _stored_filings(state: ThingState) -> list[Filing]:
    """The thing's `filings` field as `Filing`s, in stored order; an entry
    that doesn't parse is skipped."""

    value = state.fields.get("filings")
    if not isinstance(value, list):
        return []
    found: list[Filing] = []
    for raw in value:
        try:
            found.append(Filing.model_validate(raw))
        except ValidationError:
            log.warning("unreadable filing", thing_id=state.id, filing=raw)
    return found


def stored_filings_value(filings: Sequence[object]) -> list[dict[str, object]]:
    """`filings` (already of the right shape, `kinds.validate_field`) as
    they're stored: every key present (`Filing`'s defaults filling the
    missing ones), dates in their JSON form, and a blank role as `None`."""

    stored: list[dict[str, object]] = []
    for raw in filings:
        filing = Filing.model_validate(raw)
        if filing.role is not None and not filing.role.strip():
            filing.role = None
        stored.append(filing.model_dump(mode="json"))
    return stored


def filing_live(filing: Filing, at: WorldDate | None) -> bool:
    """Whether the filing's dates cover `at` (`None`, the latest telling,
    holds every filing that hasn't ended)."""

    if at is None:
        return filing.until is None
    if filing.since is not None and filing.since.instant > at.instant:
        return False
    return filing.until is None or filing.until.instant > at.instant


def _live(
    view: WorldView,
    state: ThingState,
    alive: dict[str, bool] | None = None,
    include_ended: bool = False,
) -> list[Filing]:
    """The thing's filings whose dates cover the view's date and whose
    target exists at it; `alive` caches which targets do, across calls.
    With `include_ended`, a filing counts whatever its dates (one that has
    ended, or not begun)."""

    cache = {} if alive is None else alive

    def exists(thing_id: str) -> bool:
        if thing_id not in cache:
            cache[thing_id] = view.thing(thing_id) is not None
        return cache[thing_id]

    return [
        filing
        for filing in _stored_filings(state)
        if (include_ended or filing_live(filing, view.at)) and exists(filing.target)
    ]


def filings_of(view: WorldView, thing_id: str, *, live: bool = True) -> list[Filing]:
    """The thing's filings, in stored order. With `live`, only those whose
    target exists at the view and whose dates cover its date; without, all
    of them as stored. A missing thing has none."""

    state = view.thing(thing_id)
    if state is None:
        return []
    return _live(view, state) if live else _stored_filings(state)


def sits_in(view: WorldView, start_id: str, thing_id: str) -> bool:
    """Whether `thing_id` is `start_id` or an entry `start_id` sits in,
    going up its filings (every stored one, whatever its dates: a cycle at
    any date is still a cycle), each thing once, so a cycle ends."""

    seen: set[str] = set()
    stack = [start_id]
    while stack:
        current = stack.pop()
        if current == thing_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        state = view.thing(current)
        if state is None:
            continue
        stack.extend(filing.target for filing in _stored_filings(state))
    return False


def _within_holds(view: WorldView, filing: Filing) -> bool:
    """Whether the filing's `within` is a live part of its target: an
    entry other than the target that sits in it."""

    return (
        filing.within is not None
        and filing.within != filing.target
        and view.thing(filing.within) is not None
        and sits_in(view, filing.within, filing.target)
    )


def _sits_in_live(
    view: WorldView, start_id: str, thing_id: str, live_of: "_LiveOf"
) -> bool:
    """`sits_in` over live filings only (`live_of`): whether `thing_id`
    is `start_id` or an entry `start_id` sits in at the view's date. Each
    thing once, so a cycle ends."""

    seen: set[str] = set()
    stack = [start_id]
    while stack:
        current = stack.pop()
        if current == thing_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(filing.target for filing in live_of(current))
    return False


class _LiveOf:
    """Each thing's live filings at one view (`_live`), read once; with
    `include_ended`, every filing into a live target."""

    def __init__(
        self,
        view: WorldView,
        things: Sequence[ThingState],
        include_ended: bool = False,
    ) -> None:
        self.view = view
        self.include_ended = include_ended
        self.states = {state.id: state for state in things}
        self.alive: dict[str, bool] = {}
        self.found: dict[str, list[Filing]] = {}

    def __call__(self, thing_id: str) -> list[Filing]:
        if thing_id not in self.found:
            state = self.states.get(thing_id) or self.view.thing(thing_id)
            self.found[thing_id] = (
                []
                if state is None
                else _live(self.view, state, self.alive, self.include_ended)
            )
        return self.found[thing_id]


def _within_live(view: WorldView, filing: Filing, live_of: _LiveOf) -> bool:
    """Whether the filing's `within` is, at the view's date, a live part
    of its target: an entry other than the target that sits in it through
    filings live then (a part filed in the target only from 900 is no part
    of it at 800)."""

    return (
        filing.within is not None
        and filing.within != filing.target
        and view.thing(filing.within) is not None
        and _sits_in_live(view, filing.within, filing.target, live_of)
    )


def filed_index(
    view: WorldView,
    *,
    things: Sequence[ThingState] | None = None,
    include_ended: bool = False,
) -> dict[str, list[tuple[ThingState, Filing]]]:
    """`filed_in` for every target at once: `target id -> [(entry,
    filing)]`, each list in the order the entries were made, read in one
    pass over `things` (all the view's things when not given). With
    `include_ended`, a filing counts whatever its dates: an entry page at
    the latest telling lists what was filed in it and has ended too
    ("in Velikoye from 900 to 1015")."""

    pool = view.things() if things is None else things
    live_of = _LiveOf(view, pool, include_ended)
    found: dict[str, list[tuple[ThingState, Filing]]] = {}
    for state in sorted(pool, key=lambda thing: thing.created):
        chosen: dict[str, Filing] = {}
        for filing in live_of(state.id):
            if filing.target != state.id:
                chosen[filing.target] = filing
        # one row per entry and target: its direct filing, else one within
        for filing in live_of(state.id):
            within = filing.within
            if (
                within is not None
                and within != state.id
                and within not in chosen
                and _within_live(view, filing, live_of)
            ):
                chosen[within] = filing
        for target_id, filing in chosen.items():
            found.setdefault(target_id, []).append((state, filing))
    return found


def filed_in(
    view: WorldView,
    target_id: str,
    *,
    things: Sequence[ThingState] | None = None,
    include_ended: bool = False,
) -> list[tuple[ThingState, Filing]]:
    """Every live `(entry, filing)` filed directly in the target, in the
    order the entries were made. A filing `within` the target (a person in
    the White Talon, filed in the Tsar's Army) lists the entry here too,
    while that part sits in its own target at the view's date. An entry is
    listed once, by its direct filing when it has both. `things` is the
    snapshot to scan (all the view's things when not given);
    `include_ended` as `filed_index` has it."""

    return filed_index(view, things=things, include_ended=include_ended).get(
        target_id, []
    )


def tag_of(state: ThingState) -> str | None:
    """The entry's tag, or `None` when it has none (or a blank one)."""

    tag = state.fields.get("tag")
    return tag if isinstance(tag, str) and tag else None


def _name(state: ThingState) -> str:
    name = state.fields.get("name")
    return name if isinstance(name, str) else ""


def connected(
    view: WorldView,
    target_id: str,
    *,
    things: Sequence[ThingState] | None = None,
    include_ended: bool = False,
) -> list[Group]:
    """What is filed in the target (`filed_in`, ended filings too with
    `include_ended`), grouped by each entry's tag, an untagged entry under
    "Other". Groups run largest first, then by heading; rows by role (a
    row without one last), then since (undated first), then name."""

    by_tag: dict[str | None, list[tuple[ThingState, Filing]]] = {}
    for state, filing in filed_in(
        view, target_id, things=things, include_ended=include_ended
    ):
        by_tag.setdefault(tag_of(state), []).append((state, filing))

    def row_key(
        row: tuple[ThingState, Filing],
    ) -> tuple[bool, str, bool, int, str]:
        state, filing = row
        role = filing.role.casefold() if filing.role else ""
        since = filing.since
        return (
            filing.role is None,
            role,
            since is not None,
            since.instant if since is not None else 0,
            _name(state).casefold(),
        )

    groups = [
        Group(
            tag=tag,
            heading=tag_heading(tag) if tag is not None else OTHER_HEADING,
            rows=[(state.id, filing) for state, filing in sorted(rows, key=row_key)],
        )
        for tag, rows in by_tag.items()
    ]
    groups.sort(key=lambda group: (-len(group.rows), group.heading.casefold()))
    return groups


def mentioned_in(
    view: WorldView, thing_id: str, *, include_ended: bool = False
) -> list[str]:
    """The live entries, other than the thing, whose facts visible at the
    view reference it and that aren't filed in it (`filed_in`, with
    `include_ended` as Connected has it), in the order they were made."""

    filed = {
        state.id for state, _ in filed_in(view, thing_id, include_ended=include_ended)
    }
    owners: dict[str, int] = {}
    for owner_id, _ in view.referencing(thing_id):
        if owner_id == thing_id or owner_id in filed or owner_id in owners:
            continue
        state = view.thing(owner_id)
        if state is not None:
            owners[owner_id] = state.created
    return sorted(owners, key=lambda owner_id: owners[owner_id])


def tags_in_use(view: WorldView) -> list[tuple[str, int]]:
    """Every tag the view's entries carry, with how many carry it, most
    used first, then by tag. An ignored stub doesn't count: ignoring a
    stub hides it everywhere."""

    counts: dict[str, int] = {}
    for state in view.things():
        if state.stub_ignored:
            continue
        tag = tag_of(state)
        if tag is not None:
            counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _plural(word: str) -> str:
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def tag_heading(tag: str) -> str:
    """A group's heading: the tag pluralised (its last word) and
    capitalised, "river" -> "Rivers", "holy site" -> "Holy sites"."""

    words = tag.strip().split(" ")
    if not words[-1]:
        return OTHER_HEADING
    words[-1] = _plural(words[-1])
    heading = " ".join(words)
    return heading[:1].upper() + heading[1:]


def check_filings(
    view: WorldView, thing_id: str, filings: Sequence[object]
) -> list[str]:
    """What's wrong with giving the thing these `filings` (already of the
    right shape, `kinds.validate_field`), read through `view`: a filing
    into the thing itself, a cycle (a target that sits in the thing), or a
    `within` that doesn't sit in its target, or a new target that isn't
    live (a deleted one, through which a cycle could be closed and come
    back on restore; one the thing already files in stays allowed, so a
    hidden filing never blocks rewriting the list). A `within` the thing already
    has on that target is kept unchecked, so a part moved out later never
    blocks rewriting the rest of the list (it reads as filed in the target
    alone). Empty when the write is fine."""

    current = {
        filing.target: filing.within
        for filing in filings_of(view, thing_id, live=False)
    }
    errors: list[str] = []
    for raw in filings:
        try:
            filing = Filing.model_validate(raw)
        except ValidationError:
            errors.append(f"unreadable filing: {raw!r}")
            continue
        if filing.target == thing_id:
            errors.append("an entry can't be filed in itself")
            continue
        if filing.target not in current and view.thing(filing.target) is None:
            errors.append(f"{filing.target} isn't a live entry to file in")
            continue
        if sits_in(view, filing.target, thing_id):
            errors.append(
                f"filing in {filing.target} would put the entry inside itself"
            )
            continue
        if filing.within is None or current.get(filing.target) == filing.within:
            continue
        if filing.within == thing_id or not _within_holds(view, filing):
            errors.append(
                f"{filing.within} isn't a part of {filing.target} to be within"
            )
    return errors
