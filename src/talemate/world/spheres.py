"""Sphere resolution: what a sphere holds, read through a `WorldView`.

A sphere is a `sphere` thing, or a place with a `template` (a nation that's
also a territory). Its content sits in typed, titled drawers (its `drawers`
field), filled two ways: things whose `part_of` points at the sphere and a
drawer, and the sphere's own `statement` facts, whose origin names their
drawer. An item whose drawer is gone (dropped, or never there) shows under
`UNSORTED` rather than vanishing.

A branch is a sphere whose `parent` is another sphere. It inherits the
parent's drawers it lacks (matched by id) and its items, less the things
it `drops` and the parent facts its own facts override -- plan B's rule
from `heritage.overriders`, over the chain of parents. The chain stops at a
parent that's deleted, isn't a sphere, or is already on it (a cycle). Only
the `sphere` kind has branches: a place sphere's `parent` is the place it
sits in.

People come from character ties (a character's `ties` field), not from a
list on the sphere, so a branch's members aren't its parent's. Exceptions
are the character's `ties` facts filed under the tie (origin `tie`, ruling
P22). A tie can be `within` one part of its sphere: a thing filed in it,
directly or through other parts (`within_sphere`).

A sphere's summary (ruling P21) is its `about` fact whose origin marks it
`summary`; its description prose is written from it first (`summary`).

A fact can be held by a sphere or a character: a belief, not world truth
(`held_by`). Its origin names the holder (`with_held_by`); a statement in
a beliefs drawer of a religion or culture is held by its sphere unmarked.

A `being` whose `existence` is `real` acts in the world like a character
(`acts_in_world`): its ties count. Once it isn't, its ties are kept but
hidden, as a tie to a deleted sphere is (ruling P12).

Every read goes through the given `WorldView`, so a dated part-of ending
or tie follows the view's `(at, rev)`.
"""

import re
from collections.abc import Callable, Collection, Sequence

import structlog
from pydantic import BaseModel, ValidationError

from .calendar import Calendar
from .dates import Precision, WorldDate
from .heritage import overriders
from .kinds import (
    DEFAULT_EXISTENCE,
    ENTRY_DRAWER_TYPES,
    EXISTENCE_VALUES,
    TEMPLATE_AGENT,
    UNSORTED_DRAWER_ID,
    WRITTEN_DRAWER_TYPES,
)
from .refs import REF_PATTERN, parse_refs
from .view import FactState, ThingState, WorldView

log = structlog.get_logger("talemate.world.spheres")

# the most lines `key_facts` gives one sphere, and how many of them are
# its latest timeline facts
KEY_FACTS_CAP = 8
KEY_TIMELINE = _KEY_TIMELINE = 3


class Drawer(BaseModel):
    id: str
    type: str
    title: str


# where an item goes when its drawer isn't among the sphere's drawers
UNSORTED = Drawer(id=UNSORTED_DRAWER_ID, type="knowledge", title="Unsorted")

# a template's starting drawers, as (type, title), in display order. A
# nation has no Branches (ruling P23): a place sphere never branches, its
# `parent` being the place it lies in
TEMPLATE_DRAWERS: dict[str, list[tuple[str, str]]] = {
    "religion": [
        ("beliefs", "Doctrines"),
        ("structure", "Hierarchy"),
        ("practices", "Rites and Ceremonies"),
        ("people", "People"),
        ("places", "Holy Sites"),
        ("events", "Timeline"),
        ("branches", "Branches"),
    ],
    "nation": [
        ("structure", "Government"),
        ("beliefs", "Laws"),
        ("people", "People"),
        ("places", "Lands"),
        ("events", "Timeline"),
    ],
    "order": [
        ("structure", "Ranks"),
        ("knowledge", "Fields of Study"),
        ("practices", "Practices"),
        ("people", "Members"),
        ("places", "Sites"),
        ("events", "Timeline"),
        ("branches", "Branches"),
    ],
    "culture": [
        ("practices", "Customs and Holidays"),
        ("beliefs", "Beliefs and Legends"),
        ("people", "People"),
        ("events", "Timeline"),
        ("branches", "Branches"),
    ],
    "field": [
        ("knowledge", "Principles"),
        ("practices", "Techniques"),
        ("knowledge", "Frontier"),
        ("people", "Practitioners"),
        ("events", "Timeline"),
        ("branches", "Branches"),
    ],
    "other": [("events", "Timeline")],
}


class Item(BaseModel):
    # a thing part of the sphere, or (`thing_id` None) a statement fact
    thing_id: str | None
    fact_id: str | None
    name: str
    text: str
    drawer_id: str
    # the sphere the item comes from: this one, or a parent for a branch
    source_id: str
    inherited: bool
    stub: bool


class Tie(BaseModel):
    character_id: str
    sphere_id: str
    role: str
    since: WorldDate | None
    until: WorldDate | None
    # the part of the sphere the tie is within (`within_sphere`), or None
    within: str | None = None


def is_sphere(state: ThingState) -> bool:
    """Whether the thing is a sphere: the `sphere` kind, or a place that
    has taken on a template."""

    if state.kind == "sphere":
        return True
    return state.kind == "place" and isinstance(state.fields.get("template"), str)


def _name(state: ThingState) -> str:
    name = state.fields.get("name")
    return name if isinstance(name, str) else ""


def _parent_ids(state: ThingState) -> list[str]:
    """The branch parent of a `sphere` thing, as a list (empty for none)."""

    if state.kind != "sphere":
        return []
    parent = state.fields.get("parent")
    return [parent] if isinstance(parent, str) else []


def _chain(
    view: WorldView,
    sphere_id: str,
    lookup: Callable[[str], ThingState | None] | None = None,
) -> list[ThingState]:
    """The sphere, then its parent, its parent's parent and so on, stopping
    at one that's missing, not a sphere, or already in the chain. Things
    are read with `lookup` when given (a snapshot), else `view.thing`."""

    get = lookup or view.thing
    chain: list[ThingState] = []
    seen: set[str] = set()
    next_id: str | None = sphere_id
    while next_id is not None and next_id not in seen:
        seen.add(next_id)
        state = get(next_id)
        if state is None or not is_sphere(state):
            break
        chain.append(state)
        parents = _parent_ids(state)
        next_id = parents[0] if parents else None
    return chain


def _own_drawers(state: ThingState) -> list[Drawer]:
    value = state.fields.get("drawers")
    if not isinstance(value, list):
        return []
    found: list[Drawer] = []
    for raw in value:
        try:
            found.append(Drawer.model_validate(raw))
        except ValidationError:
            log.warning("spheres.bad_drawer", thing_id=state.id, drawer=raw)
    return found


def _drawers_of(chain: list[ThingState]) -> list[Drawer]:
    found: list[Drawer] = []
    ids: set[str] = set()
    for state in chain:
        for drawer in _own_drawers(state):
            if drawer.id not in ids:
                ids.add(drawer.id)
                found.append(drawer)
    return found


def sphere_chain(view: WorldView, sphere_id: str) -> list[ThingState]:
    """The sphere, then the sphere it branches from, and so on (each
    once; stopping at one that's missing or no sphere)."""

    return _chain(view, sphere_id)


def drawers(view: WorldView, sphere_id: str) -> list[Drawer]:
    """The sphere's own drawers, in their order, then, for a branch, each
    parent's drawers it doesn't already have (matched by id)."""

    return _drawers_of(_chain(view, sphere_id))


def _drops(state: ThingState) -> set[str]:
    value = state.fields.get("drops")
    if not isinstance(value, list):
        return set()
    return {thing_id for thing_id in value if isinstance(thing_id, str)}


def _part_of(state: ThingState) -> tuple[str, str] | None:
    value = state.fields.get("part_of")
    if not isinstance(value, dict):
        return None
    sphere, drawer = value.get("sphere"), value.get("drawer")
    if isinstance(sphere, str) and isinstance(drawer, str):
        return sphere, drawer
    return None


def _authored(facts: list[FactState]) -> list[FactState]:
    """`facts` in the order they were written (a view orders them by date,
    then by their random ids)."""

    return sorted(facts, key=lambda fact: fact.created)


def _statement_drawer(fact: FactState) -> str:
    drawer = (fact.origin or {}).get("drawer")
    return drawer if isinstance(drawer, str) else UNSORTED.id


# the templates whose beliefs-drawer statements are held by their sphere
# unmarked: a nation's beliefs drawer is its Laws (true as laws), and a
# field's theories stay plain claims
HELD_TEMPLATES: tuple[str, ...] = ("religion", "culture")


def with_held_by(
    origin: dict[str, object] | None, holder_id: str | None
) -> dict[str, object]:
    """`origin` with its holder set to `holder_id`, its other keys (a
    statement's drawer, an exception's tie) kept. `None` clears it: stored
    as an explicit `"held_by": None`, so a beliefs-drawer statement can
    read plain too."""

    return {**(origin or {}), "held_by": holder_id}


def held_by(view: WorldView, fact: FactState, owner: ThingState) -> str | None:
    """The thing that holds `fact` (of `owner`) as a belief, or `None` for
    world truth: its origin's `held_by`, when that's a live thing (a
    deleted holder holds nothing, until undone); otherwise, unless the
    origin clears it, a `statement` of a religion or culture sphere in one
    of its beliefs drawers is held by that sphere. An entry filed in a
    beliefs drawer (a doctrine) inherits nothing: its facts are marked one
    by one."""

    origin = fact.origin or {}
    if "held_by" in origin:
        holder = origin["held_by"]
        if isinstance(holder, str) and view.thing(holder) is not None:
            return holder
        return None
    if (
        fact.category != "statement"
        or not is_sphere(owner)
        or owner.fields.get("template") not in HELD_TEMPLATES
    ):
        return None
    types = {d.id: d.type for d in _drawers_of(_chain(view, owner.id))}
    return owner.id if types.get(_statement_drawer(fact)) == "beliefs" else None


def is_summary_fact(fact: FactState) -> bool:
    """Whether the fact is a sphere's summary: an `about` fact whose origin
    marks it so (ruling P21)."""

    return fact.category == "about" and (fact.origin or {}).get("summary") is True


def summary_fact(state: ThingState) -> FactState | None:
    """The sphere's summary fact (`is_summary_fact`), else, for a sphere
    written before there was one, its first written `about` fact; `None`
    for neither."""

    about = [fact for fact in _authored(state.facts) if fact.category == "about"]
    return next((fact for fact in about if is_summary_fact(fact)), None) or (
        about[0] if about else None
    )


def summary(view: WorldView, sphere_id: str, cached: str | None = None) -> str:
    """The sphere's summary, rendered: `cached` (the caller's cached
    `description` prose, the summary as last written) when it's not
    empty, else its summary fact (`summary_fact`), else ""."""

    if cached:
        return view.render(cached)
    state = view.thing(sphere_id)
    fact = summary_fact(state) if state is not None else None
    return view.render(fact.text) if fact is not None else ""


# `summary`, for `key_facts`, whose parameter of that name hides it
_summary_of = summary


def item_fact(state: ThingState) -> FactState | None:
    """The fact a thing item shows as its text: a nested sphere's summary
    fact (`summary_fact`), never its first timeline fact; any other
    thing's first written visible fact."""

    if is_sphere(state):
        return summary_fact(state)
    facts = _authored(state.facts)
    return facts[0] if facts else None


def _first_text(view: WorldView, thing: ThingState) -> str:
    """The thing item's text (`item_fact`), rendered ("" for none)."""

    fact = item_fact(thing)
    return view.render(fact.text) if fact is not None else ""


def items(
    view: WorldView, sphere_id: str, things: list[ThingState] | None = None
) -> list[Item]:
    """The sphere's items: the things part of it, then its statement facts,
    each in the order they were made;
    for a branch, then each parent's in turn, less the things a more
    specific sphere in the chain drops and the facts its facts override.
    An item whose drawer the sphere doesn't have is in `UNSORTED`. Given
    `things` (a snapshot of the view's things), it reads those instead of
    scanning the view again."""

    chain = _chain(view, sphere_id)
    if not chain:
        return []
    chain_ids = {state.id for state in chain}
    drawer_ids = {drawer.id for drawer in _drawers_of(chain)}
    overridden = overriders(chain, _parent_ids)

    members: dict[str, list[tuple[ThingState, str]]] = {}
    snapshot = view.things() if things is None else things
    for thing in sorted(snapshot, key=lambda thing: thing.created):
        link = _part_of(thing)
        if link is not None and link[0] in chain_ids and thing.id not in chain_ids:
            members.setdefault(link[0], []).append((thing, link[1]))

    def placed(drawer_id: str) -> str:
        return drawer_id if drawer_id in drawer_ids else UNSORTED.id

    found: list[Item] = []
    dropped: set[str] = set()
    for depth, state in enumerate(chain):
        for thing, drawer_id in members.get(state.id, []):
            if thing.id in dropped:
                continue
            found.append(
                Item(
                    thing_id=thing.id,
                    fact_id=None,
                    name=_name(thing),
                    text=_first_text(view, thing),
                    drawer_id=placed(drawer_id),
                    source_id=state.id,
                    inherited=depth > 0,
                    stub=thing.is_stub,
                )
            )
        for fact in _authored(state.facts):
            if fact.category != "statement" or fact.fact_id in overridden:
                continue
            text = view.render(fact.text)
            found.append(
                Item(
                    thing_id=None,
                    fact_id=fact.fact_id,
                    name=text,
                    text=text,
                    drawer_id=placed(_statement_drawer(fact)),
                    source_id=state.id,
                    inherited=depth > 0,
                    stub=False,
                )
            )
        # what this sphere drops is gone from every less specific one
        dropped |= _drops(state)
    return found


# words in an entry's name that make it a body of people (a council, an
# order), filed in a structure drawer when nothing else says where
_BODY_WORDS = frozenset(("council", "order", "guild", "synod", "college", "court"))


def names_a_body(name: str) -> bool:
    """Whether `name` names a body of people ("The Council of Elders")."""

    return any(word in _BODY_WORDS for word in re.findall(r"[a-z]+", name.casefold()))


def entry_drawer(
    drawers: Sequence[Drawer], kind: str, wanted: str | None, name: str = ""
) -> str:
    """The id of the drawer among `drawers` an entry is filed in, as
    creation files it:

    - `wanted`, when it's `UNSORTED` or one of `drawers` of a type the
      entry may go in: `ENTRY_DRAWER_TYPES` for a thing of `kind`, the
      written types for a statement (`kind` "");
    - else (`wanted` is `None`, or a drawer it doesn't go in) a guess: a
      place goes in the first places drawer; a sphere, or an entry named
      like a body of people (`names_a_body`), in the first structure
      drawer;
    - else `UNSORTED`."""

    allowed = ENTRY_DRAWER_TYPES.get(kind, ()) if kind else WRITTEN_DRAWER_TYPES
    if wanted == UNSORTED.id:
        return wanted
    if any(d.id == wanted and d.type in allowed for d in drawers):
        return str(wanted)
    if kind == "place":
        guess = "places"
    elif kind == "sphere" or (kind and names_a_body(name)):
        guess = "structure"
    else:
        return UNSORTED.id
    return next((d.id for d in drawers if d.type == guess), UNSORTED.id)


def sits_in(view: WorldView, start_id: str, thing_id: str) -> bool:
    """Whether `thing_id` is `start_id` or a thing `start_id` sits in,
    going up its `parent` and `part_of` links, each thing once (so a cycle
    ends): a thing can't be filed in, nor branch from, anything sitting
    inside it."""

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
        parent = state.fields.get("parent")
        if isinstance(parent, str):
            stack.append(parent)
        link = _part_of(state)
        if link is not None:
            stack.append(link[0])
    return False


def _date(value: object) -> WorldDate | None:
    if value is None:
        return None
    try:
        return WorldDate.model_validate(value)
    except ValidationError:
        return None


def existence(state: ThingState) -> str:
    """A being's `existence`: real, believed or undecided (also for one
    unset, or set to something else)."""

    value = state.fields.get("existence")
    return value if value in EXISTENCE_VALUES else DEFAULT_EXISTENCE


def acts_in_world(state: ThingState) -> bool:
    """Whether the thing acts in the world as a character does -- can be
    cast in a scene and hold ties: a character, or a being whose
    `existence` is real."""

    return state.kind == "character" or (
        state.kind == "being" and existence(state) == "real"
    )


def within_sphere(view: WorldView, thing_id: str, sphere_id: str) -> bool:
    """Whether `thing_id` is a live thing inside the sphere: filed in it,
    or in a thing filed in it, and so on up its `part_of` links (the White
    Talon in the Tsar's Army), each thing once. A sphere is never within
    itself."""

    seen: set[str] = set()
    current: str | None = thing_id
    while current is not None and current not in seen:
        seen.add(current)
        state = view.thing(current)
        if state is None:
            return False
        link = _part_of(state)
        if link is None:
            return False
        if link[0] == sphere_id:
            return current != sphere_id and view.thing(sphere_id) is not None
        current = link[0]
    return False


def _ties(state: ThingState, view: WorldView | None = None) -> list[Tie]:
    """The thing's ties, each `within` kept, given a `view`, only while
    that part is live and inside the tie's sphere (`within_sphere`): one
    deleted, or moved out, reads as a tie to the sphere as a whole.
    Without one, `within` is left out."""

    value = state.fields.get("ties")
    if not acts_in_world(state) or not isinstance(value, list):
        return []
    found: list[Tie] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        sphere, role = raw.get("sphere"), raw.get("role")
        if not isinstance(sphere, str) or not isinstance(role, str):
            continue
        within = raw.get("within")
        if not (
            view is not None
            and isinstance(within, str)
            and within_sphere(view, within, sphere)
        ):
            within = None
        found.append(
            Tie(
                character_id=state.id,
                sphere_id=sphere,
                role=role,
                since=_date(raw.get("since")),
                until=_date(raw.get("until")),
                within=within,
            )
        )
    return found


def _tie_live(tie: Tie, at: WorldDate | None) -> bool:
    """Whether the tie holds at `at` (`None`, the latest telling, holds
    every tie that hasn't ended)."""

    if at is None:
        return tie.until is None
    if tie.since is not None and tie.since.instant > at.instant:
        return False
    return tie.until is None or tie.until.instant > at.instant


def ties_of(view: WorldView, character_id: str, *, live: bool = False) -> list[Tie]:
    """The character's (or real being's) ties, in its `ties` field's order,
    each with the part of its sphere it's `within`, if any;
    with `live`, only those that hold at `view.at`. A tie to a sphere
    that's since been deleted is still given. A being that isn't real has
    none: its stored ties are kept, hidden."""

    state = view.thing(character_id)
    if state is None:
        return []
    found = _ties(state, view)
    if live:
        found = [tie for tie in found if _tie_live(tie, view.at)]
    return found


def people(view: WorldView, sphere_id: str) -> list[Tie]:
    """The ties pointing at the sphere that hold at `view.at`, in the order
    the characters (and real beings) were made, each with the part of the
    sphere it's `within`, if any. A branch's people are its
    own, not its parent's."""

    characters = sorted(
        [*view.things("character"), *view.things("being")],
        key=lambda thing: thing.created,
    )
    return [
        tie
        for character in characters
        for tie in _ties(character, view)
        if tie.sphere_id == sphere_id and _tie_live(tie, view.at)
    ]


def territory(
    view: WorldView, sphere_id: str, things: list[ThingState] | None = None
) -> list[str]:
    """The ids of the places the sphere holds: for a place sphere, itself;
    the places in its places drawers (inherited ones too); and every place
    under any of those, each once. Given `things` (a snapshot of the
    view's things, as `items` takes it), it reads those instead of
    scanning the view again."""

    state = view.thing(sphere_id)
    if state is None:
        return []
    places = {
        place.id: place
        for place in (
            view.things("place")
            if things is None
            else [t for t in things if t.kind == "place"]
        )
    }
    children: dict[str, list[str]] = {}
    for place in sorted(places.values(), key=lambda thing: thing.created):
        parent = place.fields.get("parent")
        if isinstance(parent, str):
            children.setdefault(parent, []).append(place.id)

    roots = [sphere_id] if state.kind == "place" and is_sphere(state) else []
    types = {drawer.id: drawer.type for drawer in drawers(view, sphere_id)}
    roots += [
        item.thing_id
        for item in items(view, sphere_id, things)
        if item.thing_id in places and types.get(item.drawer_id) == "places"
    ]

    held: list[str] = []
    seen: set[str] = set()
    stack = list(reversed(roots))
    while stack:
        place_id = stack.pop()
        if place_id in seen:
            continue
        seen.add(place_id)
        held.append(place_id)
        stack.extend(reversed(children.get(place_id, [])))
    return held


def _holds_through_items(chain: list[ThingState], ancestors: list[ThingState]) -> bool:
    """Whether one of `ancestors` (places) is a thing item of the sphere
    `chain[0]` in a places drawer -- `items`' rule: part of a sphere in
    the chain, not one of the chain itself, not dropped by a more specific
    sphere in it, its drawer typed by the most specific sphere having it."""

    depth_of = {state.id: depth for depth, state in enumerate(chain)}
    types = {drawer.id: drawer.type for drawer in _drawers_of(chain)}
    for place in ancestors:
        link = _part_of(place)
        if link is None or link[0] not in depth_of or place.id in depth_of:
            continue
        if types.get(link[1]) != "places":
            continue
        if any(place.id in _drops(state) for state in chain[: depth_of[link[0]]]):
            continue
        return True
    return False


def holders(
    view: WorldView, place_id: str, things: list[ThingState] | None = None
) -> list[str]:
    """The ids of the spheres whose `territory` holds the place, in the
    order they were made, from one snapshot of the view's things
    (`things`, else `view.things()`): what asking `territory` of every
    sphere would give, without a scan per sphere. A sphere holds the place
    when the place, or a place it sits in (its `parent` chain), is the
    sphere itself (a place sphere) or one of its items in a places
    drawer."""

    snapshot = view.things() if things is None else things
    by_id = {state.id: state for state in snapshot}
    place = by_id.get(place_id)
    if place is None or place.kind != "place":
        return []

    ancestors: list[ThingState] = []
    seen: set[str] = set()
    current: ThingState | None = place
    while current is not None and current.id not in seen:
        seen.add(current.id)
        ancestors.append(current)
        parent = current.fields.get("parent")
        current = by_id.get(parent) if isinstance(parent, str) else None
        if current is not None and current.kind != "place":
            current = None
    ancestor_ids = {state.id for state in ancestors}

    found: list[str] = []
    for state in sorted(snapshot, key=lambda thing: thing.created):
        if not is_sphere(state):
            continue
        if state.kind == "place" and state.id in ancestor_ids:
            found.append(state.id)
            continue
        chain = _chain(view, state.id, by_id.get)
        if _holds_through_items(chain, ancestors):
            found.append(state.id)
    return found


def _date_key(fact: FactState) -> tuple[int, int, int]:
    """Date order, undated first, then the order the facts were written."""

    if fact.valid_from is None:
        return (0, 0, fact.created)
    return (1, fact.valid_from.instant, fact.created)


def _timeline(view: WorldView, sphere_id: str, path: frozenset[str]) -> list[FactState]:
    if sphere_id in path:
        return []
    state = view.thing(sphere_id)
    if state is None or not is_sphere(state):
        return []
    facts = [fact for fact in state.facts if fact.category == "timeline"]
    for parent_id in _parent_ids(state):
        inherited = _timeline(view, parent_id, path | {sphere_id})
        split = view.field_since(sphere_id, "parent")
        if split is not None:
            inherited = [
                fact
                for fact in inherited
                if fact.valid_from is not None
                and fact.valid_from.instant < split.instant
            ]
        facts += inherited
    return sorted(facts, key=_date_key)


def timeline(view: WorldView, sphere_id: str) -> list[FactState]:
    """The sphere's `timeline` facts and, for a branch, its parent's
    timeline from before the date the `parent` link holds from (all of it
    when that link is undated), in date order, undated first."""

    return _timeline(view, sphere_id, frozenset())


# how an exception's text ends, linking what it departs from (a thing item,
# or the sphere for one of its statements): `create.exception_fact`'s
_DEPARTS_FROM = re.compile(
    r"Departs from(?: a teaching of)?\s+(%s)\s*$" % REF_PATTERN.pattern
)


def departs_from(text: str) -> str | None:
    """The thing an exception's raw text departs from: the reference its
    closing "Departs from <link>" (or "Departs from a teaching of <link>")
    sentence links, or `None` when it doesn't end with one."""

    found = _DEPARTS_FROM.search(text)
    if found is None:
        return None
    refs = parse_refs(found.group(1))
    return refs[0] if refs else None


def exceptions(view: WorldView, character_id: str, sphere_id: str) -> list[FactState]:
    """The character's `ties` facts that depart from the sphere: those whose
    origin `tie` is the sphere (ruling P22). One written before exceptions
    were filed by tie (no `tie` in its origin) is matched by what it
    rejects instead: its origin `rejects_fact`, one of the sphere's
    statement items, or the link its text ends with ("Departs from
    <link>", `departs_from`), the sphere or one of its thing items -- never
    by any other reference in its text, which may name another tied
    sphere."""

    state = view.thing(character_id)
    if state is None:
        return []
    ties = [fact for fact in state.facts if fact.category == "ties"]
    filed = [fact for fact in ties if isinstance((fact.origin or {}).get("tie"), str)]
    found = [fact for fact in filed if (fact.origin or {}).get("tie") == sphere_id]
    unfiled = [fact for fact in ties if fact not in filed]
    if not unfiled:
        return found
    sphere_items = items(view, sphere_id)
    thing_ids = {sphere_id} | {i.thing_id for i in sphere_items if i.thing_id}
    fact_ids = {i.fact_id for i in sphere_items if i.fact_id}
    old = [
        fact
        for fact in unfiled
        if (fact.origin or {}).get("rejects_fact") in fact_ids
        or departs_from(fact.text) in thing_ids
    ]
    return [fact for fact in ties if fact in found or fact in old]


def _is_agent(state: ThingState) -> bool:
    agent = state.fields.get("agent")
    if isinstance(agent, bool):
        return agent
    template = state.fields.get("template")
    return isinstance(template, str) and TEMPLATE_AGENT.get(template, False)


_ARTICLES = ("the ", "a ", "an ")


def _bare(text: str) -> str:
    """`text` casefolded, less a leading article."""

    folded = text.casefold()
    for article in _ARTICLES:
        if folded.startswith(article):
            return folded[len(article) :]
    return folded


def _opens_with(text: str, name: str) -> bool:
    """Whether `text` opens with `name` (ignoring case and a leading
    article on either), ending at a word boundary."""

    bare_text, bare_name = _bare(text), _bare(name).strip()
    if not bare_name or not bare_text.startswith(bare_name):
        return False
    rest = bare_text[len(bare_name) :]
    return not rest or not rest[0].isalnum()


def item_line(name: str, text: str) -> str:
    """A thing item as one line: "<name>: <text>"; the text alone when it
    already opens with the name (no "Name: Name ..." doubling); the name
    alone when there's no text."""

    if not text:
        return name
    if _opens_with(text, name):
        return text
    return f"{name}: {text}"


# how a caller words one fact of a key-facts item: `(fact, its owner, the
# fact rendered) -> line text` (the scene context's held-by wording)
FactLine = Callable[[FactState, ThingState, str], str]


def _item_fact(view: WorldView, item: Item) -> tuple[FactState, ThingState] | None:
    """The fact an item shows, with its owner: a statement's own fact, a
    thing item's `item_fact`."""

    owner = view.thing(item.thing_id or item.source_id)
    if owner is None:
        return None
    if item.thing_id is None:
        fact = next((f for f in owner.facts if f.fact_id == item.fact_id), None)
    else:
        fact = item_fact(owner)
    return (fact, owner) if fact is not None else None


def _item_line(
    item: Item, view: WorldView | None = None, fact_line: FactLine | None = None
) -> str:
    """An item as one key-facts line: a statement's text, a thing item as
    `item_line` gives it; with `fact_line`, the fact's text is worded by
    it first (a thing item whose text opened with its name then stays
    the text alone)."""

    text = item.text
    found = (
        _item_fact(view, item) if view is not None and fact_line is not None else None
    )
    if fact_line is not None and found is not None:
        text = fact_line(*found, item.text)
    if item.thing_id is None:
        return text
    if text != item.text and _opens_with(item.text, item.name):
        return text
    return item_line(item.name, text)


def _round_robin(sizes: list[int], budget: int) -> list[int]:
    """How many to take from each of groups of `sizes`, taking one from
    each group in turn, up to `budget` in all."""

    taken = [0] * len(sizes)
    left = max(budget, 0)
    while left and any(t < size for t, size in zip(taken, sizes)):
        for index, size in enumerate(sizes):
            if left and taken[index] < size:
                taken[index] += 1
                left -= 1
    return taken


def _year(date: WorldDate) -> WorldDate:
    return WorldDate(instant=date.instant, precision=Precision.YEAR)


def dated_line(
    calendar: Calendar,
    date: WorldDate | None,
    text: str,
    until: WorldDate | None = None,
) -> str:
    """A timeline line as key facts give it: "In <year>: <text>" (the
    spheres probe's (d) wording), or "From <year> to <year>: <text>" for
    one that has ended (`until`, ruling C18), each year as `calendar`
    labels it; the text alone when it's undated."""

    if date is None:
        return text
    if until is not None:
        return (
            f"From {calendar.format(_year(date))} to "
            f"{calendar.format(_year(until))}: {text}"
        )
    return f"In {calendar.format(_year(date))}: {text}"


def _timeline_line(view: WorldView, fact: FactState, calendar: Calendar) -> str:
    """A timeline fact as key facts give it (`dated_line`)."""

    return dated_line(calendar, fact.valid_from, view.render(fact.text))


def _summary_lines(view: WorldView, sphere_id: str, summary: str | None) -> list[str]:
    return [line for line in [summary or _summary_of(view, sphere_id)] if line]


def key_items(
    view: WorldView,
    sphere_id: str,
    used: int,
    things: list[ThingState] | None = None,
    skip: Collection[str] = (),
) -> list[Item]:
    """The items `key_facts` prints for the sphere when `used` of its
    lines go to the summary and the timeline: its top beliefs and
    practices items (and structure, for an agent), the first in `items`
    order, a drawer type at a time in turn, less those in `skip`."""

    state = view.thing(sphere_id)
    if state is None:
        return []
    types = ["beliefs", "practices"] + (["structure"] if _is_agent(state) else [])
    type_of = {drawer.id: drawer.type for drawer in drawers(view, sphere_id)}
    sphere_items = [
        item for item in items(view, sphere_id, things) if item.thing_id not in skip
    ]
    groups = [
        [item for item in sphere_items if type_of.get(item.drawer_id) == type_]
        for type_ in types
    ]
    taken = _round_robin([len(group) for group in groups], KEY_FACTS_CAP - used)
    return [item for group, count in zip(groups, taken) for item in group[:count]]


def key_facts(
    view: WorldView,
    sphere_id: str,
    summary: str | None = None,
    calendar: Calendar | None = None,
    things: list[ThingState] | None = None,
    skip: Collection[str] = (),
    fact_line: FactLine | None = None,
    latest: Sequence[tuple[str, str]] | None = None,
) -> list[str]:
    """What a scene touching the sphere is told about it, rendered, at most
    `KEY_FACTS_CAP` lines: the summary (`summary`, as the caller found it,
    else the sphere's summary fact: module `summary`), then its top items
    (`key_items`, a thing item as `item_line` gives it), then its latest
    timeline lines, each "In <year>: <text>" by `calendar` (the default one
    when not given). `things`, a snapshot of the view's things, saves
    `items` a scan. A thing item in `skip` (shown elsewhere in full) is
    left out, and the next item takes its place. `fact_line`, when given,
    words each item's fact (`_item_line`).

    `latest`, when given, is the timeline lines as `(owner id, text)`,
    worded by the caller (its gathered timeline, `timelines`); otherwise
    the sphere's own timeline facts. A line of a thing printed as an item
    is left out, so nothing shows twice, and the last `_KEY_TIMELINE` of
    the rest are taken."""

    state = view.thing(sphere_id)
    if state is None:
        return []

    head = _summary_lines(view, sphere_id, summary)
    calendar = calendar or Calendar()
    lines = (
        [
            (sphere_id, _timeline_line(view, fact, calendar))
            for fact in timeline(view, sphere_id)
        ]
        if latest is None
        else list(latest)
    )
    shown = key_items(
        view, sphere_id, len(head) + min(len(lines), _KEY_TIMELINE), things, skip
    )
    printed = {item.thing_id for item in shown if item.thing_id}
    tail = [text for owner, text in lines if owner not in printed][-_KEY_TIMELINE:]
    middle = [_item_line(item, view, fact_line) for item in shown]
    return (head + middle + tail)[:KEY_FACTS_CAP]
