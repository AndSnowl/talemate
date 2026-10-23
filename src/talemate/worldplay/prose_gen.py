"""Prose generation and caching for world things.

`render_section` asks the model for a reference-entry profile of one
section -- built from a list of facts, never from a continuing story --
and writes nothing. `generate_section` renders a thing's section from its
facts at `at`, together with its other facts as background (for
consistency only -- a section generated from one slice of a thing's facts
must not drift off who it's about, e.g. a personality section turning an
owl-folk courier human because only his personality facts were in view),
and caches the result for the stretch of story time containing `at`
(`World.prose()`, keyed the same way `talemate.world.prose.stretches`
reports them). `ensure_prose` regenerates whatever section is stale.
`create.py` reuses `render_section` for a preview that isn't in the world
yet.

A character has two sections: `description` (from its `appearance` and
`background` facts) and `personality` (from its `personality` facts).
Speech facts never go through here -- `characters.py` reads them straight
into `dialogue_instructions` and `example_dialogue`, no prose needed. Every
other kind has a single `description` section, from all of its facts.

A thing's heritage (`talemate.world.heritage`) feeds in too, with
overrides applied. A character's sections add the inherited facts
`inherited_categories` maps to them -- a species', race's or mix's
`physical` and `variation` facts to `description`, `instinct` to
`personality`, and a culture's dress, customs and beliefs -- and every
other inherited fact goes to the background. A race or mix gets all its
inherited facts as background. Since an ancestor's change changes the
prose, stretches and staleness follow the thing's lineage (`lineage_ids`).

`personality`'s background leaves the body out: the character's own
`appearance` facts, and whatever `inherited_categories("description")`
maps as inherited (a species', race's or mix's `physical` and
`variation`, a culture's `dress`), are left out of it entirely. Giving
the model appearance in view, even "for consistency only", made it
restate the body instead of writing personality; `description`'s own
background is unaffected (acceptance probe:
docs/superpowers/probes/2026-10-21-personality-and-actions.md).

Prose is generated at the "analyze" kind, not "create": a reference entry
is a factual restatement of known facts, not an invention, so it's asked
for at the analytical preset's lower, more deterministic temperature
rather than the creative preset `create-thing` (actual invention) uses.
"""

from __future__ import annotations

from typing import Any

import structlog

from talemate.prompts import Prompt
from talemate.world import heritage, spheres
from talemate.world.calendar import Calendar
from talemate.world.dates import WorldDate
from talemate.world.kinds import HERITAGE_KINDS, get_kind
from talemate.world.prose import stretches
from talemate.world.store import World
from talemate.world.view import ThingState, WorldView
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.held import held_text

log = structlog.get_logger("talemate.worldplay.prose_gen")

# a character's prose sections, and the fact categories each is generated
# from; every other kind has one `description` section from all its facts
SECTIONS: tuple[str, ...] = ("description", "personality")

_SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "description": ("appearance", "background"),
    "personality": ("personality",),
}

# the inherited fact categories a character's section adds to its own, by
# the source layer's kind: a heritage layer's (species, race or mix) ...
_HERITAGE_SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "description": ("physical", "variation"),
    "personality": ("instinct",),
}
# ... and a culture's -- customs shape behaviour, so they're personality
_CULTURE_SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "description": ("dress",),
    "personality": ("customs", "belief"),
}

# an instant past the proleptic-Gregorian range, mirroring view.py's and
# prose.py's own "+infinity" for at=None
_FAR_FUTURE = 10**15


# reference prose is a factual restatement of existing facts, not an
# invention -- the lower-temperature "analyze" kind (-> the analytical
# preset) keeps the register closer to a character sheet than "create"
# (-> creative_instruction) did; see
# docs/superpowers/probes/2026-10-20-prose-register.md
PROSE_PROMPT_KIND = "analyze"

# the core thing fields, beyond its facts, worth naming in a section's
# background -- when there are any -- so identity survives even when a
# section's own facts say nothing about them (e.g. a personality section
# with no appearance facts at all still knows it's writing about an owl,
# not a human)
_CORE_BACKGROUND_FIELDS: tuple[str, ...] = ("name", "born", "kind")

NO_CLIENT_MESSAGE = "No AI client is configured for the creator agent"


def require_client(client: Any) -> None:
    """Refuse to ask the model with no client, in words the owner can act
    on rather than a `NoneType` error from deep inside the prompt."""

    if client is None:
        raise ValueError(NO_CLIENT_MESSAGE)


def sections_for(kind: str) -> tuple[str, ...]:
    """The prose sections a thing of `kind` has."""

    if kind == "character":
        return SECTIONS
    return ("description",)


# the sphere categories no description is written from (ruling P18): a
# sphere's summary (ruling P1) stays its own, never a retelling of its
# drawers' statements or its timeline, and a place sphere is described
# from its place facts; nor a real being's exceptions to its ties, which
# are on its sheet, as a character's are
_NOT_DESCRIBED: tuple[str, ...] = ("statement", "timeline", "ties")


def section_categories(kind: str, section: str) -> tuple[str, ...]:
    """The fact categories `section` of a `kind` thing is generated from:
    for `description`, never a sphere's statements or timeline
    (`_NOT_DESCRIBED`)."""

    if kind == "character":
        return _SECTION_CATEGORIES[section]
    categories = tuple(get_kind(kind).categories)
    if section == "description":
        categories = tuple(c for c in categories if c not in _NOT_DESCRIBED)
    return categories


def unread_categories(kind: str, section: str) -> tuple[str, ...]:
    """The `kind`'s fact categories `section` isn't written from
    (`section_categories` leaves them out): a change to one of them leaves
    the section's prose fresh. None for a character, whose sections each
    keep their prose staleness as it was."""

    if kind == "character":
        return ()
    read = section_categories(kind, section)
    return tuple(c for c in get_kind(kind).categories if c not in read)


def inherited_categories(section: str) -> dict[str, tuple[str, ...]]:
    """The inherited fact categories a character's `section` adds to its
    own, by the kind of layer they're inherited from."""

    categories = {
        kind: _HERITAGE_SECTION_CATEGORIES[section] for kind in HERITAGE_KINDS
    }
    categories["culture"] = _CULTURE_SECTION_CATEGORIES[section]
    return categories


def lineage_ids(
    world: World, thing_id: str, at: WorldDate | None, rev: int | None = None
) -> list[str]:
    """The ids of the layers `thing_id` inherits from (`heritage.lineage`,
    the thing itself left out) as of `(at, rev)` -- the `also` every
    `stretches`/`stale` call for the thing passes, so a change to an
    ancestor counts as a change to the thing."""

    return [
        layer.thing_id
        for layer in heritage.lineage(world.view(at, rev), thing_id)
        if layer.depth > 0
    ]


def _section_facts(
    view: WorldView, state: ThingState, section: str
) -> tuple[list[str], list[str]]:
    """`section`'s facts -- the thing's own facts in its categories, then,
    for a character, the inherited facts `inherited_categories` adds -- and
    the rest of its inherited facts, for the background. Overridden facts
    are left out of both.

    `personality`'s background also drops whatever `description` maps as
    inherited (a species', race's or mix's `physical` and `variation`
    facts, and a culture's `dress`) -- giving the model appearance in view
    made it narrate the body instead of writing personality (acceptance
    probe: docs/superpowers/probes/2026-10-21-personality-and-actions.md).
    `description`'s own background is unaffected. A sphere's summary fact
    (`spheres.is_summary_fact`) comes first."""

    own_categories = section_categories(state.kind, section)
    by_kind = inherited_categories(section) if state.kind == "character" else {}
    exclude_by_kind = (
        inherited_categories("description") if section == "personality" else {}
    )

    facts: list[str] = []
    inherited_background: list[str] = []
    found = heritage.effective_facts(view, state.id)
    # a sphere's summary fact leads its description (ruling P21): the
    # other about facts add to it, never replace it
    found.sort(key=lambda pair: not spheres.is_summary_fact(pair[0]))
    owners: dict[str, ThingState | None] = {}
    for fact, layer in found:
        # rendered: a linked fact reads as written, never as `[[thing:...]]`;
        # a held one as belief ("<Holder> holds that ...", `held_text`)
        if layer.thing_id not in owners:
            owners[layer.thing_id] = view.thing(layer.thing_id)
        owner = owners[layer.thing_id]
        text = (
            held_text(view, fact, owner)
            if owner is not None
            else view.render(fact.text)
        )
        if layer.depth == 0:
            if fact.category in own_categories:
                facts.append(text)
        elif fact.category in by_kind.get(layer.kind, ()):
            facts.append(text)
        elif fact.category in exclude_by_kind.get(layer.kind, ()):
            continue
        else:
            inherited_background.append(text)
    return facts, inherited_background


def _heritage_line(view: WorldView, thing_id: str) -> list[str]:
    """`["Heritage: Snowy, Owl-folk."]`, naming the race, mix and species
    the thing descends from, or nothing when it has none."""

    names = [
        layer.name
        for layer in heritage.lineage(view, thing_id)
        if layer.depth > 0 and layer.kind in HERITAGE_KINDS and layer.name
    ]
    return [f"Heritage: {', '.join(names)}."] if names else []


def background_for_section(
    calendar: Calendar,
    kind: str,
    section: str,
    facts: list[tuple[str, str]],
    fields: dict[str, Any],
    inherited: list[str] | None = None,
) -> list[str]:
    """The thing's other facts -- outside `section`'s own categories --
    then `inherited` (lines from its heritage, already left out of the
    section's own facts), plus its core fields (`name`, `born`, `kind`),
    when there are any. Given to the model for consistency only, never to
    describe.

    `facts` is `(category, text)` pairs and `fields` the thing's raw field
    values, rather than a `ThingState`, so this also serves `create.py`'s
    `preview_thing`, previewing a thing that isn't in the world yet.
    `born` is formatted by `calendar` (eras and all), the same as a built
    `Character`'s own `born` label (`characters.py`).

    `personality` also drops the thing's own `appearance` facts, for the
    same reason `_section_facts` drops the inherited physical/variation
    ones; `description` drops a sphere's statements and timeline
    (`_NOT_DESCRIBED`, ruling P18), so they don't come back as background.
    A sphere's `template` is a core field too ("A religion sphere.")."""

    categories = set(section_categories(kind, section))
    if section == "personality":
        categories.add("appearance")
    elif section == "description":
        categories.update(_NOT_DESCRIBED)
    background = [text for category, text in facts if category not in categories]
    background.extend(inherited or [])

    for field in _CORE_BACKGROUND_FIELDS:
        value = fields.get(field)
        if not value:
            continue
        if field == "born":
            born = value if isinstance(value, WorldDate) else WorldDate(**value)
            background.append(f"Born in {calendar.format(born)}.")
        elif field == "kind":
            background.append(f"A {value}.")
        elif field == "name":
            background.append(f"Named {value}.")
    template = fields.get("template")
    if isinstance(template, str) and template:
        background.append(f"A {template} sphere.")

    return background


def stretch_containing(
    world: World, thing_id: str, at: WorldDate | None
) -> tuple[WorldDate | None, WorldDate | None]:
    """The `(start, end)` stretch -- from `talemate.world.prose.stretches`,
    following the thing's lineage as of `at` -- that contains `at`. The
    last, open-ended stretch always matches, so this never falls through
    without a result."""

    at_instant = at.instant if at is not None else _FAR_FUTURE
    also = lineage_ids(world, thing_id, at)
    for start, end in stretches(lambda: world, thing_id, also):
        start_instant = start.instant if start is not None else None
        end_instant = end.instant if end is not None else None
        if (start_instant is None or start_instant <= at_instant) and (
            end_instant is None or at_instant < end_instant
        ):
            return start, end
    # unreachable: kept defensive rather than asserting, since a thing with
    # no timeline at all still has one (None, None) stretch from `stretches`
    return None, None


async def render_section(
    kind: str,
    name: str,
    section: str,
    facts: list[str],
    client: Any,
    background: list[str] | None = None,
) -> str:
    """Ask the model for `section`'s reference-entry profile from `facts`,
    writing nothing. `background` is the thing's other facts, given for
    consistency only -- the model is told not to describe them. With no
    facts at all there is nothing to describe, so no call is made and the
    prose is empty."""

    if not facts:
        return ""

    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.thing-prose",
            client,
            PROSE_PROMPT_KIND,
            vars={
                "facts": facts,
                "background": background or [],
                "kind": kind,
                "section": section,
                "name": name,
            },
        )
    text: str = extracted["response"].strip()

    # the template primes the response with "<name> is" (to keep it
    # third-person, on-topic and in the reference-entry register); a
    # generation that produced nothing comes back as just that prefix,
    # which is reported as empty prose rather than a two-word profile
    prefill = f"{name.strip()} is"
    if text == prefill:
        text = ""
    return text


async def generate_section(
    world: World, thing_id: str, section: str, at: WorldDate | None, client: Any
) -> str:
    """Generate `section`'s prose from the thing's facts at `at` and what
    it inherits then, cache it for the stretch containing `at`, and return
    the text. A sphere with no fact the section reads (a core's summary,
    ruling P18) keeps the prose it has: no call, nothing cached; with no
    prose yet, it's written from its core fields (name, template)."""

    view = world.view(at)
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")

    name = view.name_of(thing_id) or ""
    facts, inherited_background = _section_facts(view, state, section)
    kept = (
        world.prose().get(thing_id, section, at)
        if not facts and spheres.is_sphere(state)
        else None
    )
    if kept is not None and kept.text:
        # a sphere's summary from its core reads no fact (P18): nothing new
        # to write from, so the summary it has stays, uncached anew (an
        # empty one, an accepted preview's "", is no summary)
        return kept.text
    background = background_for_section(
        world.calendar,
        state.kind,
        section,
        [(fact.category, view.render(fact.text)) for fact in state.facts],
        state.fields,
        _heritage_line(view, thing_id) + inherited_background,
    )
    if not facts and spheres.is_sphere(state):
        # no summary at all (the core gave none, or an empty one): written from what it is,
        # its name and template
        facts, background = background, []
    text = await render_section(state.kind, name, section, facts, client, background)

    # cached at the revision the facts were read at (`view.rev`), not the
    # head when the model returns: a change written while the model was
    # generating then still leaves this entry stale
    start, end = stretch_containing(world, thing_id, at)
    world.prose().put(thing_id, section, start, end, text, rev=view.rev)
    return text


async def ensure_prose(
    world: World, thing_id: str, at: WorldDate | None, client: Any
) -> None:
    """Regenerate every section that's stale at `at` (`World.prose().stale`),
    for the thing or anything in its lineage. A section with nothing cached
    yet counts as stale too."""

    state = world.view(at).thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")

    cache = world.prose()
    for section in sections_for(state.kind):
        if cache.stale(
            thing_id,
            section,
            at,
            staleness_also(world, thing_id, section, at),
            unread_categories(state.kind, section),
        ):
            await generate_section(world, thing_id, section, at, client)


def staleness_also(
    world: World, thing_id: str, section: str, at: WorldDate | None
) -> list[str]:
    """The lineage ids to check `section`'s cached prose against: today's,
    plus the ones it had when the prose was cached, so an ancestor deleted
    since (gone from today's lineage) still counts as a change."""

    also = lineage_ids(world, thing_id, at)
    cached = world.prose().get(thing_id, section, at)
    if cached is not None:
        also += lineage_ids(world, thing_id, at, cached.rev)
    return list(dict.fromkeys(also))
