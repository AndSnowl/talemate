"""Heritage resolution: what a thing inherits from its race, mix, species
and culture.

`lineage` walks a thing's layers, most specific first: the thing itself,
then its `heritage` (a race or mix), a mix's own layer followed by each
parent's chain in turn, a race's `species`, and last a character's
`culture`. Each thing appears once, so a cycle in mix parents terminates,
and a missing or deleted target is skipped.

Facts and numbers are resolved from those layers in code. A fact is
dropped from the inherited set when a fact of a layer that inherits from
its layer (the thing's own included) lists its `fact_id` in `overrides`.
A number is the first one set along the chain; a mix with a number unset
averages its two parents' resolved values.

Every read goes through the given `WorldView`, so a dated heritage change
or a deleted ancestor follows the view's `(at, rev)`.
"""

from typing import Literal

import structlog
from pydantic import BaseModel

from .view import FactState, ThingState, WorldView

log = structlog.get_logger("talemate.world.heritage")

LifeStage = Literal["child", "adolescent", "adult", "elder"]

# the fields that lead from a thing to the next, less specific heritage
# layer; a character's `culture` is followed separately, after them all
_HERITAGE_LINKS = ("heritage", "species")


class Layer(BaseModel):
    thing_id: str
    kind: str
    name: str
    # the layer's position in the lineage: 0 for the thing itself, rising
    # as the layers get less specific
    depth: int


class InheritedFact(BaseModel):
    fact: FactState
    source_id: str
    source_kind: str
    source_name: str
    # the `fact_id` of the more specific fact that overrides this one
    overridden_by: str | None


class Range(BaseModel):
    min: float
    max: float
    unit: str


class Numbers(BaseModel):
    lifespan: float | None
    adult_age: float | None
    measures: dict[str, Range]


def _name(state: ThingState) -> str:
    name = state.fields.get("name")
    return name if isinstance(name, str) else ""


def _link(state: ThingState, field: str) -> str | None:
    value = state.fields.get(field)
    return value if isinstance(value, str) else None


def _parents(state: ThingState) -> list[str]:
    value = state.fields.get("parents")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _next_ids(state: ThingState) -> list[str]:
    """The ids one heritage step up from `state`, in inheritance order."""

    ids = [link for field in _HERITAGE_LINKS if (link := _link(state, field))]
    return ids + _parents(state)


def _heritage_chain(view: WorldView, thing_id: str, seen: set[str]) -> list[ThingState]:
    """`thing_id`'s state, then each thing it inherits from, depth first,
    skipping ids already in `seen` (which this fills in)."""

    if thing_id in seen:
        return []
    seen.add(thing_id)
    state = view.thing(thing_id)
    if state is None:
        return []
    chain = [state]
    for next_id in _next_ids(state):
        chain.extend(_heritage_chain(view, next_id, seen))
    return chain


def _lineage_states(view: WorldView, thing_id: str) -> list[ThingState]:
    seen: set[str] = set()
    states = _heritage_chain(view, thing_id, seen)
    if states and states[0].kind == "character":
        culture_id = _link(states[0], "culture")
        if culture_id is not None and culture_id not in seen:
            culture = view.thing(culture_id)
            if culture is not None:
                states.append(culture)
    return states


def lineage(view: WorldView, thing_id: str) -> list[Layer]:
    """The thing's layers, most specific first (see the module docstring).
    Empty when the thing itself doesn't exist in `view`."""

    return [
        Layer(thing_id=state.id, kind=state.kind, name=_name(state), depth=depth)
        for depth, state in enumerate(_lineage_states(view, thing_id))
    ]


def _ancestors(states: list[ThingState]) -> dict[str, set[str]]:
    """Each layer's id -> the ids of the layers it inherits from, by the
    heritage links among `states` rather than by list position (a species
    listed once under parent A is still an ancestor of parent B). The
    thing itself inherits from every other layer, its culture included."""

    by_id = {state.id: state for state in states}
    ancestors: dict[str, set[str]] = {}
    for state in states[1:]:
        reached: set[str] = set()
        stack = [state.id]
        while stack:
            for next_id in _next_ids(by_id[stack.pop()]):
                if next_id in by_id and next_id not in reached:
                    reached.add(next_id)
                    stack.append(next_id)
        reached.discard(state.id)
        ancestors[state.id] = reached
    if states:
        ancestors[states[0].id] = {state.id for state in states[1:]}
    return ancestors


def _inherited_with_layers(
    view: WorldView, thing_id: str
) -> tuple[list[tuple[FactState, Layer]], list[tuple[InheritedFact, Layer]]]:
    """The thing's own facts and its inherited ones, each with its layer."""

    states = _lineage_states(view, thing_id)
    layers = [
        Layer(thing_id=state.id, kind=state.kind, name=_name(state), depth=depth)
        for depth, state in enumerate(states)
    ]
    ancestors = _ancestors(states)
    fact_layer = {fact.fact_id: state.id for state in states for fact in state.facts}

    # fact_id -> the most specific fact overriding it. A fact overrides
    # only a target in a layer its own layer inherits from, so a sibling
    # parent (or a less specific layer) can't drop it
    overriders: dict[str, str] = {}
    for state in states:
        for fact in state.facts:
            for target in fact.overrides:
                if fact_layer.get(target) in ancestors[state.id]:
                    overriders.setdefault(target, fact.fact_id)

    own: list[tuple[FactState, Layer]] = []
    inherited_facts: list[tuple[InheritedFact, Layer]] = []
    for state, layer in zip(states, layers):
        for fact in state.facts:
            if layer.depth == 0:
                own.append((fact, layer))
                continue
            item = InheritedFact(
                fact=fact,
                source_id=state.id,
                source_kind=state.kind,
                source_name=layer.name,
                overridden_by=overriders.get(fact.fact_id),
            )
            inherited_facts.append((item, layer))
    return own, inherited_facts


def inherited(view: WorldView, thing_id: str) -> list[InheritedFact]:
    """Every fact of the thing's less specific layers, in layer order, with
    `overridden_by` set where a fact of a layer inheriting from that one
    overrides it."""

    _, inherited_facts = _inherited_with_layers(view, thing_id)
    return [item for item, _ in inherited_facts]


def effective_facts(view: WorldView, thing_id: str) -> list[tuple[FactState, Layer]]:
    """The thing's own facts, then the inherited facts nothing overrides,
    each with the layer it comes from."""

    own, inherited_facts = _inherited_with_layers(view, thing_id)
    return own + [
        (item.fact, layer)
        for item, layer in inherited_facts
        if item.overridden_by is None
    ]


def _number(state: ThingState, field: str) -> float | None:
    value = state.fields.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _measures(state: ThingState) -> dict[str, Range]:
    value = state.fields.get("measures")
    if not isinstance(value, list):
        return {}
    measures: dict[str, Range] = {}
    for measure in value:
        if isinstance(measure, dict) and isinstance(measure.get("name"), str):
            measures[measure["name"]] = Range(
                min=measure["min"], max=measure["max"], unit=measure["unit"]
            )
    return measures


def _average(values: list[float | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None


def _average_ranges(ranges: list[Range]) -> Range:
    return Range(
        min=sum(r.min for r in ranges) / len(ranges),
        max=sum(r.max for r in ranges) / len(ranges),
        unit=ranges[0].unit,
    )


def _resolve_numbers(
    view: WorldView, thing_id: str, path: frozenset[str]
) -> Numbers | None:
    """`thing_id`'s numbers with unset ones filled from the layer above (a
    mix averaging its parents). `None` for a thing that's missing or
    already on `path`, the chain being resolved (a cycle). Unlike
    `lineage`, a thing reached by two routes (one species under both of a
    mix's parents) resolves on each."""

    if thing_id in path:
        return None
    path = path | {thing_id}
    state = view.thing(thing_id)
    if state is None:
        return None

    lifespan = _number(state, "lifespan")
    adult_age = _number(state, "adult_age")
    measures = _measures(state)

    if state.kind == "mix":
        sources = [_resolve_numbers(view, parent, path) for parent in _parents(state)]
        above = [numbers for numbers in sources if numbers is not None]
        if lifespan is None:
            lifespan = _average([numbers.lifespan for numbers in above])
        if adult_age is None:
            adult_age = _average([numbers.adult_age for numbers in above])
        names = [name for numbers in above for name in numbers.measures]
        for name in dict.fromkeys(names):
            if name not in measures:
                measures[name] = _average_ranges(
                    [n.measures[name] for n in above if name in n.measures]
                )
    else:
        for field in _HERITAGE_LINKS:
            link = _link(state, field)
            if link is None:
                continue
            numbers = _resolve_numbers(view, link, path)
            if numbers is None:
                continue
            if lifespan is None:
                lifespan = numbers.lifespan
            if adult_age is None:
                adult_age = numbers.adult_age
            for name, measure in numbers.measures.items():
                measures.setdefault(name, measure)

    return Numbers(lifespan=lifespan, adult_age=adult_age, measures=measures)


def numbers(view: WorldView, thing_id: str) -> Numbers:
    """The thing's lifespan, adult age and measures: the first value set
    along its lineage, field by field and measure by measure, with a mix's
    unset value the average of its two parents' (or the one parent's that
    has it)."""

    resolved = _resolve_numbers(view, thing_id, frozenset())
    if resolved is None:
        return Numbers(lifespan=None, adult_age=None, measures={})
    return resolved


def life_stage(age: int, numbers: Numbers) -> tuple[LifeStage | None, bool]:
    """`(stage, past_lifespan)` for `age`: adolescent from 0.75 x adult
    age, adult from adult age, elder from 0.8 x lifespan. An age past the
    lifespan is flagged, never refused. The stage is `None` when neither
    number is set; with only a lifespan, anyone short of elder is adult."""

    lifespan, adult_age = numbers.lifespan, numbers.adult_age
    if lifespan is None and adult_age is None:
        return None, False

    past_lifespan = lifespan is not None and age > lifespan
    stage: LifeStage
    if lifespan is not None and age >= 0.8 * lifespan:
        stage = "elder"
    elif adult_age is not None and age < 0.75 * adult_age:
        stage = "child"
    elif adult_age is not None and age < adult_age:
        stage = "adolescent"
    else:
        stage = "adult"
    return stage, past_lifespan


def members(view: WorldView, thing_id: str) -> list[str]:
    """The ids of the characters whose lineage includes `thing_id` (the
    character itself not counting), ordered by id."""

    return [
        character.id
        for character in view.things("character")
        if any(
            layer.thing_id == thing_id
            for layer in lineage(view, character.id)
            if layer.depth > 0
        )
    ]


def species_of(view: WorldView, thing_id: str) -> list[str]:
    """The species a race or mix descends from, in lineage order (a
    species gives itself)."""

    return [
        layer.thing_id for layer in lineage(view, thing_id) if layer.kind == "species"
    ]


def find_mix(view: WorldView, a: str, b: str) -> str | None:
    """The mix whose `parents` are `a` and `b`, in either order, or `None`."""

    wanted = {a, b}
    for mix in view.things("mix"):
        if set(_parents(mix)) == wanted:
            return mix.id
    return None
