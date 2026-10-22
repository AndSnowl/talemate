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
are the character's `ties` facts that name the sphere or one of its items.

Every read goes through the given `WorldView`, so a dated part-of ending
or tie follows the view's `(at, rev)`.
"""

import structlog
from pydantic import BaseModel, ValidationError

from .dates import WorldDate
from .heritage import overriders
from .kinds import TEMPLATE_AGENT
from .view import FactState, ThingState, WorldView

log = structlog.get_logger("talemate.world.spheres")

# the most lines `key_facts` gives one sphere, and how many of them are
# its latest timeline facts
KEY_FACTS_CAP = 8
_KEY_TIMELINE = 3


class Drawer(BaseModel):
    id: str
    type: str
    title: str


# where an item goes when its drawer isn't among the sphere's drawers
UNSORTED = Drawer(id="unsorted", type="knowledge", title="Unsorted")

# a template's starting drawers, as (type, title), in display order
TEMPLATE_DRAWERS: dict[str, list[tuple[str, str]]] = {
    "religion": [
        ("beliefs", "Doctrines"),
        ("structure", "Hierarchy"),
        ("practices", "Rites and Ceremonies"),
        ("people", "People"),
        ("places", "Holy Sites"),
        ("events", "Timeline"),
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
    ],
    "culture": [
        ("practices", "Customs and Holidays"),
        ("beliefs", "Beliefs and Legends"),
        ("people", "People"),
        ("events", "Timeline"),
    ],
    "field": [
        ("knowledge", "Principles"),
        ("practices", "Techniques"),
        ("knowledge", "Frontier"),
        ("people", "Practitioners"),
        ("events", "Timeline"),
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


def _chain(view: WorldView, sphere_id: str) -> list[ThingState]:
    """The sphere, then its parent, its parent's parent and so on, stopping
    at one that's missing, not a sphere, or already in the chain."""

    chain: list[ThingState] = []
    seen: set[str] = set()
    next_id: str | None = sphere_id
    while next_id is not None and next_id not in seen:
        seen.add(next_id)
        state = view.thing(next_id)
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


def _statement_drawer(fact: FactState) -> str:
    drawer = (fact.origin or {}).get("drawer")
    return drawer if isinstance(drawer, str) else UNSORTED.id


def items(view: WorldView, sphere_id: str) -> list[Item]:
    """The sphere's items: the things part of it, then its statement facts;
    for a branch, then each parent's in turn, less the things a more
    specific sphere in the chain drops and the facts its facts override.
    An item whose drawer the sphere doesn't have is in `UNSORTED`."""

    chain = _chain(view, sphere_id)
    if not chain:
        return []
    chain_ids = {state.id for state in chain}
    drawer_ids = {drawer.id for drawer in _drawers_of(chain)}
    overridden = overriders(chain, _parent_ids)

    members: dict[str, list[tuple[ThingState, str]]] = {}
    for thing in view.things():
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
                    text=view.render(thing.facts[0].text) if thing.facts else "",
                    drawer_id=placed(drawer_id),
                    source_id=state.id,
                    inherited=depth > 0,
                    stub=thing.is_stub,
                )
            )
        for fact in state.facts:
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


def _date(value: object) -> WorldDate | None:
    if value is None:
        return None
    try:
        return WorldDate.model_validate(value)
    except ValidationError:
        return None


def _ties(state: ThingState) -> list[Tie]:
    value = state.fields.get("ties")
    if state.kind != "character" or not isinstance(value, list):
        return []
    found: list[Tie] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        sphere, role = raw.get("sphere"), raw.get("role")
        if not isinstance(sphere, str) or not isinstance(role, str):
            continue
        found.append(
            Tie(
                character_id=state.id,
                sphere_id=sphere,
                role=role,
                since=_date(raw.get("since")),
                until=_date(raw.get("until")),
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
    """The character's ties, in its `ties` field's order; with `live`, only
    those that hold at `view.at`. A tie to a sphere that's since been
    deleted is still given."""

    state = view.thing(character_id)
    if state is None:
        return []
    found = _ties(state)
    if live:
        found = [tie for tie in found if _tie_live(tie, view.at)]
    return found


def people(view: WorldView, sphere_id: str) -> list[Tie]:
    """The ties pointing at the sphere that hold at `view.at`, by character
    id. A branch's people are its own, not its parent's."""

    return [
        tie
        for character in view.things("character")
        for tie in _ties(character)
        if tie.sphere_id == sphere_id and _tie_live(tie, view.at)
    ]


def territory(view: WorldView, sphere_id: str) -> list[str]:
    """The ids of the places the sphere holds: for a place sphere, itself;
    the places in its places drawers (inherited ones too); and every place
    under any of those, each once."""

    state = view.thing(sphere_id)
    if state is None:
        return []
    places = {place.id: place for place in view.things("place")}
    children: dict[str, list[str]] = {}
    for place in places.values():
        parent = place.fields.get("parent")
        if isinstance(parent, str):
            children.setdefault(parent, []).append(place.id)

    roots = [sphere_id] if state.kind == "place" else []
    types = {drawer.id: drawer.type for drawer in drawers(view, sphere_id)}
    roots += [
        item.thing_id
        for item in items(view, sphere_id)
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


def _date_key(fact: FactState) -> tuple[int, int]:
    return (0, 0) if fact.valid_from is None else (1, fact.valid_from.instant)


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


def exceptions(view: WorldView, character_id: str, sphere_id: str) -> list[FactState]:
    """The character's `ties` facts that depart from the sphere: those
    referencing the sphere or one of its thing items, or whose origin
    `rejects_fact` is one of its statement items."""

    state = view.thing(character_id)
    if state is None:
        return []
    sphere_items = items(view, sphere_id)
    thing_ids = {sphere_id} | {i.thing_id for i in sphere_items if i.thing_id}
    fact_ids = {i.fact_id for i in sphere_items if i.fact_id}
    return [
        fact
        for fact in state.facts
        if fact.category == "ties"
        and (
            thing_ids.intersection(fact.refs)
            or (fact.origin or {}).get("rejects_fact") in fact_ids
        )
    ]


def _is_agent(state: ThingState) -> bool:
    agent = state.fields.get("agent")
    if isinstance(agent, bool):
        return agent
    template = state.fields.get("template")
    return isinstance(template, str) and TEMPLATE_AGENT.get(template, False)


def _item_line(item: Item) -> str:
    if item.thing_id is None:
        return item.text
    return f"{item.name}: {item.text}" if item.text else item.name


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


def key_facts(view: WorldView, sphere_id: str, summary: str | None = None) -> list[str]:
    """What a scene touching the sphere is told about it, rendered, at most
    `KEY_FACTS_CAP` lines: the summary (`summary`, the caller's cached
    `description` prose, or else the sphere's first `about` fact), then its
    top beliefs and practices items (and structure, for an agent), taken a
    drawer type at a time in turn, then its latest timeline facts."""

    state = view.thing(sphere_id)
    if state is None:
        return []

    head: list[str] = []
    if summary:
        head.append(summary)
    else:
        about = next((f for f in state.facts if f.category == "about"), None)
        if about is not None:
            head.append(view.render(about.text))

    latest = [view.render(f.text) for f in timeline(view, sphere_id)[-_KEY_TIMELINE:]]

    types = ["beliefs", "practices"] + (["structure"] if _is_agent(state) else [])
    type_of = {drawer.id: drawer.type for drawer in drawers(view, sphere_id)}
    sphere_items = items(view, sphere_id)
    groups = [
        [item for item in sphere_items if type_of.get(item.drawer_id) == type_]
        for type_ in types
    ]
    taken = _round_robin(
        [len(group) for group in groups], KEY_FACTS_CAP - len(head) - len(latest)
    )
    middle = [
        _item_line(item)
        for group, count in zip(groups, taken)
        for item in group[:count]
    ]
    return (head + middle + latest)[:KEY_FACTS_CAP]
