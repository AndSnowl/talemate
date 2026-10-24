"""Entries: what any entry is, whatever it's filed in, read through a
`WorldView`.

- **Held by.** A fact can be held by an entry (a religion, a character):
  a belief, not world truth (`held_by`). Its origin names the holder
  (`with_held_by`), or clears it (`"held_by": None`); unmarked, a fact in
  the `belief` category is held by its owner (ruling F9: the religion,
  culture and order prompt hints add that category). Nothing else holds a
  fact implicitly: the old beliefs-drawer rule went with drawers.
- **Acting in the world.** A character, or a `being` whose `existence` is
  `real`, acts in the world (`acts_in_world`): it can be cast in a scene,
  and on a timeline it's a member of what it's filed in, never a part.
- **Summary.** An entry's summary is its `about` fact whose origin marks
  it `summary` (ruling P21; `summary_fact`), its description prose written
  from it first (`summary`).
"""

from .kinds import DEFAULT_EXISTENCE, EXISTENCE_VALUES
from .view import FactState, ThingState, WorldView

__all__ = [
    "BELIEF_CATEGORY",
    "acts_in_world",
    "existence",
    "held_by",
    "is_summary_fact",
    "summary",
    "summary_fact",
    "with_held_by",
]

# the fact category whose facts are held by their owner, unmarked
BELIEF_CATEGORY = "belief"


def with_held_by(
    origin: dict[str, object] | None, holder_id: str | None
) -> dict[str, object]:
    """`origin` with its holder set to `holder_id`, its other keys kept.
    `None` clears it: stored as an explicit `"held_by": None`, so a
    `belief` fact can read plain too."""

    return {**(origin or {}), "held_by": holder_id}


def held_by(view: WorldView, fact: FactState, owner: ThingState) -> str | None:
    """The entry that holds `fact` (of `owner`) as a belief, or `None` for
    world truth: its origin's `held_by` when it has one (a live entry; a
    deleted holder holds nothing, until undone, and an explicit `None`
    holds nothing); otherwise, a fact in the `belief` category is held by
    its owner."""

    origin = fact.origin or {}
    if "held_by" in origin:
        holder = origin["held_by"]
        if isinstance(holder, str) and view.thing(holder) is not None:
            return holder
        return None
    return owner.id if fact.category == BELIEF_CATEGORY else None


def existence(state: ThingState) -> str:
    """A being's `existence`: real, believed or undecided (also for one
    unset, or set to something else)."""

    value = state.fields.get("existence")
    return value if value in EXISTENCE_VALUES else DEFAULT_EXISTENCE


def acts_in_world(state: ThingState) -> bool:
    """Whether the thing acts in the world as a character does -- can be
    cast in a scene: a character, or a being whose `existence` is real."""

    return state.kind == "character" or (
        state.kind == "being" and existence(state) == "real"
    )


def is_summary_fact(fact: FactState) -> bool:
    """Whether the fact is an entry's summary: an `about` fact whose origin
    marks it so (ruling P21)."""

    return fact.category == "about" and (fact.origin or {}).get("summary") is True


def summary_fact(state: ThingState) -> FactState | None:
    """The entry's summary fact (`is_summary_fact`), else, for one written
    before there was one, its first written `about` fact; `None` for
    neither."""

    about = sorted(
        (fact for fact in state.facts if fact.category == "about"),
        key=lambda fact: fact.created,
    )
    return next((fact for fact in about if is_summary_fact(fact)), None) or (
        about[0] if about else None
    )


def summary(view: WorldView, thing_id: str, cached: str | None = None) -> str:
    """The entry's summary, rendered: `cached` (the caller's cached
    `description` prose, the summary as last written) when it's not
    empty, else its summary fact (`summary_fact`), else ""."""

    if cached:
        return view.render(cached)
    state = view.thing(thing_id)
    fact = summary_fact(state) if state is not None else None
    return view.render(fact.text) if fact is not None else ""
