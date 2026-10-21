"""Scene setup: from one storyline prompt plus the world to a scene ready
to play.

- `match_names` finds world thing names in the prompt as the owner types,
  so the screen can highlight them and let the owner pick which thing each
  one means. Plain string matching, as the slice spec says, by the shared
  name index (`world.names`).
- `plan_scene` asks the model (`world/scene-setup`, seeded from the
  scene-setup probe's prompt) who, where and what, given the prompt, the
  owner's picks rendered at the scene's date, and the closest hits from the
  world index. It writes nothing.
- `start_scene` writes a planned setup as a new world scene.
- A stub the setup uses -- picked, resolved as a character or the place,
  or named in the reply's goal or intro, ignored or not -- is filled out:
  planning previews it (`create.preview_thing` with its `stub_id`, once
  per stub) and `start_scene` accepts the previews before writing the
  scene, so the scene plays the full entries. Cancelling leaves the stubs
  as they were. A stub the index merely finds is neither shown nor pulled
  in. A culture stub can't be expanded yet, and a race or mix stub has no
  species or parents to fill it from: those stay stubs, and so does one
  whose preview fails.
- `continue_setup` plans the next scene from where an earlier one ended.

What the scene-setup probe (docs/superpowers/probes/2026-10-19-world-create-
and-setup.md) settled:

- the reply keeps the probe's JSON shape. An invented character or place
  may carry `facts`, and `extras` lists invented groups that aren't
  characters (a "Warden Patrol"). Extras are kept as scene-local things of
  kind `extra`, never as characters, so no agent voices them; the intro and
  their facts are where the story sees them;
- the model's own `world: true|false` flag is not trusted: every name is
  resolved against the world in code;
- a player picked in the UI always wins over the model's choice;
- an invented character may carry a `heritage`, one of the `heritages`
  (species, race or mix names) the prompt is given; an unknown name is
  ignored. `start_scene` gives it a description made from its own facts
  plus its heritage's effective physical/variation facts, and an
  instinct-based `personality`, so the inherited body reaches play; the
  heritage id is kept on the local character for a later make-real.

The owner's choices always win over automatic matching: a name the owner
picked a thing for resolves to that thing, and a name the owner treats as
new (`new_names`) is always invented.

For the browser tests, `plan_scene` and `continue_setup` take a ready-made
model `reply` instead of asking the model (the websocket plugin's
`TALEMATE_TEST_FIXED_SETUP`); everything after the model's answer runs as
usual.

Invented things stay scene-local. Planning writes nothing to the world;
starting writes only the stub previews (and the scene).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field, model_validator

import talemate.instance as instance
from talemate.character import Character
from talemate.prompts import Prompt
from talemate.world import heritage
from talemate.world.dates import WorldDate
from talemate.world.index import IndexDoc, WorldIndex
from talemate.world.kinds import HERITAGE_KINDS

# `NameCandidate` and `NameMatch` are re-exported: they were scene setup's
from talemate.world.names import NameCandidate, NameMatch, find_names  # noqa: F401
from talemate.world.scenes import MessageRecord, SceneRecord, scene_end
from talemate.world.store import World
from talemate.world.view import ThingState, WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.context import LOCAL_PLACE_KIND
from talemate.worldplay.create import (
    CREATE_KINDS,
    CreatePreview,
    accept_preview,
    current_date,
    json_objects,
    preview_thing,
)
from talemate.worldplay.mentions import suggested_prompt
from talemate.worldplay.persistence import LOCAL_CHARACTER_KIND

log = structlog.get_logger("talemate.worldplay.setup")

# room for a paragraph or two of intro plus the cast
SETUP_PROMPT_KIND = "creative_instruction_2048"

# how many index hits the setup prompt is given
INDEX_HITS = 8

# the scene-local thing kind of an invented group that isn't a character
# (the place's, `LOCAL_PLACE_KIND`, lives in context.py, which reads it)
LOCAL_EXTRA_KIND = "extra"

# the message kinds whose text goes into a continued scene's summary
_SUMMARIZED_KINDS = {"narrator", "character", "scene"}

_KIND_LABELS = {"character": "Characters", "place": "Places", "lore": "Lore"}

_SCENE_NAME_LENGTH = 60


# --- models ------------------------------------------------------------------


class LocalThing(BaseModel):
    """A thing invented for one scene."""

    name: str
    facts: list[str] = Field(default_factory=list)
    # a character's heritage (species, race or mix), picked from the
    # `heritages` the setup prompt offers; kept for a later make-real
    heritage_id: str | None = None


class SetupRef(BaseModel):
    """A world thing (`thing_id`) or an invented one (`local`), never both."""

    thing_id: str | None = None
    local: LocalThing | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "SetupRef":
        if (self.thing_id is None) == (self.local is None):
            raise ValueError("a setup entry is either a world thing or a local one")
        return self


class SceneSetup(BaseModel):
    """A planned scene: who (the player and the other characters), where,
    when, what it's about and how it opens. `pulled_in` is the lore the
    scene draws on; `invented` names everything made up for it. `prompt`
    (the owner's storyline) and `summary` (of the scene it continues, if
    any) become the scene's premise."""

    player: SetupRef
    characters: list[SetupRef] = Field(default_factory=list)
    place: SetupRef | None = None
    extras: list[LocalThing] = Field(default_factory=list)
    start: WorldDate
    goal: str = ""
    intro: str = ""
    pulled_in: list[str] = Field(default_factory=list)
    invented: list[str] = Field(default_factory=list)
    prompt: str = ""
    summary: str = ""
    continued_from: str | None = None
    # the stubs the setup uses, filled out: written to the world (each
    # into its stub, keeping the id) when the scene starts
    stub_previews: list[CreatePreview] = Field(default_factory=list)


# --- name matching -----------------------------------------------------------


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def match_names(world: World, text: str, at: WorldDate | None) -> list[NameMatch]:
    """Every world thing name in `text`, as the things are named at `at`:
    the shared name index's `find_names` (main and other names, a
    character's first name on its own, stubs, partial suggestions)."""

    return find_names(world.view(at), text)


# --- the index -------------------------------------------------------------


def _index_hits(
    world: World, prompt: str, at: WorldDate, embedding_function: Any
) -> list[IndexDoc]:
    """The index's closest documents to `prompt` at `at`, rebuilding the
    index first if the world has moved on since it was built. With no
    embedding function to be had (no memory database yet), the plan goes
    ahead without index hits."""

    if embedding_function is None:
        try:
            embedding_function = instance.get_agent("memory").embedding_function
        except (KeyError, RuntimeError) as exc:
            log.warning("setup.index_unavailable", reason=str(exc))
            return []

    index = WorldIndex(world, embedding_function=embedding_function)
    if index.built_rev() != world.head_rev():
        index.rebuild()
    return index.query(prompt, at=at, n=INDEX_HITS)


# --- the prompt and its reply --------------------------------------------------


def _dedupe(ids: list[str]) -> list[str]:
    return list(dict.fromkeys(ids))


def _world_things(view: WorldView, thing_ids: list[str]) -> list[tuple[str, list]]:
    """`thing_ids` rendered at the view's date, grouped by kind, as
    `(label, [{"name", "facts"}])` for the template."""

    groups: dict[str, list[dict[str, Any]]] = {}
    for thing_id in thing_ids:
        state = view.thing(thing_id)
        if state is None:
            continue
        groups.setdefault(state.kind, []).append(
            {
                "name": view.name_of(thing_id) or "",
                "facts": [view.render(fact.text) for fact in state.facts],
            }
        )
    order = list(_KIND_LABELS)
    kinds = sorted(groups, key=lambda k: order.index(k) if k in order else len(order))
    return [(_KIND_LABELS.get(kind, kind.capitalize()), groups[kind]) for kind in kinds]


def _heritage_label(view: WorldView, state: ThingState) -> str:
    """How a heritage thing is shown in the setup prompt's `heritages`
    var: a race labelled with its species ("Snowy (Owl-folk)"), a species
    or mix by its bare name. `""` for a thing with no name."""

    name = view.name_of(state.id) or ""
    if not name:
        return ""
    if state.kind == "race":
        species_id = state.fields.get("species")
        species_name = view.name_of(species_id) if isinstance(species_id, str) else None
        return f"{name} ({species_name})" if species_name else name
    return name


def _heritages(view: WorldView) -> list[str]:
    """Species, race and mix names for the setup prompt's `heritages` var."""

    labels = [
        label
        for kind in HERITAGE_KINDS
        for state in view.things(kind)
        if (label := _heritage_label(view, state))
    ]
    return labels


def _heritage_id(view: WorldView, name: str | None) -> str | None:
    """The species, race or mix named `name`, matched case-insensitively
    against either its own name or its `heritages` display label ("Snowy"
    and "Snowy (Owl-folk)" both find Snowy) -- a model tends to echo the
    label it was shown. `None` for no name or one that matches nothing."""

    if not isinstance(name, str) or not name.strip():
        return None
    key = _norm(name)
    for kind in HERITAGE_KINDS:
        for state in view.things(kind):
            bare = _norm(view.name_of(state.id) or "")
            if key == bare or key == _norm(_heritage_label(view, state)):
                return state.id
    return None


async def _ask(
    world: World,
    view: WorldView,
    client: Any,
    *,
    prompt: str,
    start: WorldDate,
    shown: list[str],
    player_name: str = "",
    summary: str = "",
    carried: list[str] | None = None,
) -> dict[str, Any]:
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.scene-setup",
            client,
            SETUP_PROMPT_KIND,
            vars={
                "prompt": prompt,
                "start_label": world.calendar.format(start),
                "player_name": player_name,
                "summary": summary,
                "carried": carried or [],
                "world_things": _world_things(view, shown),
                "heritages": _heritages(view),
            },
        )
    return _reply_object(extracted["response"])


def _setup_in(obj: Any) -> dict[str, Any] | None:
    """`obj` itself, if it has a setup key, or the first dict value of
    `obj` that does, searched recursively -- a reply that wraps the setup
    in an outer key, e.g. `{"scene": {"player": ..., "intro": ...}}`."""

    if not isinstance(obj, dict):
        return None
    if {"player", "characters", "intro"} & set(obj):
        return obj
    for value in obj.values():
        found = _setup_in(value)
        if found is not None:
            return found
    return None


def _reply_object(reply: str) -> dict[str, Any]:
    """The setup object in the model's reply: the first JSON object (found
    by `create.json_objects`) with a setup key in it, at the top level or
    nested inside another object's value."""

    for obj in json_objects(reply):
        found = _setup_in(obj)
        if found is not None:
            return found
    raise ValueError(f"no scene setup found in the model's reply: {reply!r}")


def _entry(value: object) -> tuple[str, list[str], str | None]:
    """`(name, facts, heritage)` from a reply entry: an object, or a bare
    name. `heritage` is the reply's raw `"heritage"` name, unresolved."""

    if isinstance(value, str):
        return value.strip(), [], None
    if not isinstance(value, dict):
        return "", [], None
    name = value.get("name")
    facts = value.get("facts")
    if isinstance(facts, str):
        facts = [facts]
    heritage_name = value.get("heritage")
    return (
        name.strip() if isinstance(name, str) else "",
        [f.strip() for f in facts or [] if isinstance(f, str) and f.strip()],
        heritage_name.strip()
        if isinstance(heritage_name, str) and heritage_name.strip()
        else None,
    )


def _is_new(key: str, new_names: frozenset[str]) -> bool:
    """Whether the (normalised) name `key` is one the owner treats as new,
    or starts with one ("Maren Ashdown" when "Maren" is new)."""

    return any(key == new or key.startswith(new + " ") for new in new_names)


def _resolve(
    view: WorldView,
    name: str,
    kind: str,
    picks: dict[str, str],
    new_names: frozenset[str] = frozenset(),
) -> str | None:
    """The world thing of `kind` the model's `name` means. The owner's
    choices come first: a name treated as new (`new_names`, normalised) is
    invented, and a picked thing the owner's text, its name or its first
    name matches is that thing. Then a thing with that full name, or the
    only thing of that kind with that first name. `None` means invented."""

    key = _norm(name)
    if not key or _is_new(key, new_names):
        return None
    things = {
        state.id: _norm(view.name_of(state.id) or "") for state in view.things(kind)
    }

    for text, thing_id in picks.items():
        if thing_id in things and key in (
            _norm(text),
            things[thing_id],
            things[thing_id].split(" ")[0],
        ):
            return thing_id

    exact = [thing_id for thing_id, thing_name in things.items() if thing_name == key]
    if exact:
        return exact[0]

    by_first = [
        t for t, thing_name in things.items() if thing_name.split(" ")[0] == key
    ]
    return by_first[0] if len(by_first) == 1 else None


def _ref(
    view: WorldView,
    value: object,
    kind: str,
    picks: dict[str, str],
    new_names: frozenset[str] = frozenset(),
) -> SetupRef | None:
    name, facts, heritage_name = _entry(value)
    if not name:
        return None
    thing_id = _resolve(view, name, kind, picks, new_names)
    if thing_id is not None:
        return SetupRef(thing_id=thing_id)
    local = LocalThing(name=name, facts=facts)
    if kind == "character":
        local.heritage_id = _heritage_id(view, heritage_name)
    return SetupRef(local=local)


def _same(a: SetupRef, b: SetupRef) -> bool:
    if a.thing_id is not None or b.thing_id is not None:
        return a.thing_id == b.thing_id
    assert a.local is not None and b.local is not None
    return _norm(a.local.name) == _norm(b.local.name)


def _add_ref(refs: list[SetupRef], ref: SetupRef, *, unless: SetupRef) -> None:
    if not _same(ref, unless) and not any(_same(ref, other) for other in refs):
        refs.append(ref)


def _invented(setup: SceneSetup) -> list[str]:
    refs = [setup.player, *setup.characters]
    if setup.place is not None:
        refs.append(setup.place)
    names = [ref.local.name for ref in refs if ref.local is not None]
    return names + [extra.name for extra in setup.extras]


def _setup_from_reply(
    view: WorldView,
    reply: dict[str, Any],
    *,
    picks: dict[str, str],
    player: SetupRef | None,
    start: WorldDate,
    prompt: str,
    new_names: frozenset[str] = frozenset(),
) -> SceneSetup:
    """A `SceneSetup` from the model's reply, every name resolved against
    the world. A `player` given wins over the model's; the model's player
    then joins the other characters. Picked characters the model left out
    are added, and a picked place stands in for an invented one."""

    raw_characters = reply.get("characters")
    if not isinstance(raw_characters, list):
        raw_characters = []
    characters = [
        ref
        for ref in (
            _ref(view, value, "character", picks, new_names) for value in raw_characters
        )
        if ref is not None
    ]

    model_player = _ref(view, reply.get("player"), "character", picks, new_names)
    if player is None:
        if model_player is None:
            if not characters:
                raise ValueError("the model's reply named no player")
            model_player = characters[0]
        # an invented player's facts are on its characters entry
        player = next((c for c in characters if _same(c, model_player)), model_player)

    cast: list[SetupRef] = []
    if model_player is not None:
        _add_ref(cast, model_player, unless=player)
    for ref in characters:
        _add_ref(cast, ref, unless=player)
    for thing_id in picks.values():
        state = view.thing(thing_id)
        if state is not None and state.kind == "character":
            _add_ref(cast, SetupRef(thing_id=thing_id), unless=player)

    place = _ref(view, reply.get("place"), "place", picks, new_names)
    picked_places = [
        thing_id
        for thing_id in picks.values()
        if (state := view.thing(thing_id)) is not None and state.kind == "place"
    ]
    if (place is None or place.thing_id is None) and picked_places:
        place = SetupRef(thing_id=picked_places[0])

    raw_extras = reply.get("extras")
    extras = []
    for value in raw_extras if isinstance(raw_extras, list) else []:
        name, facts, _heritage_name = _entry(value)
        if name:
            extras.append(LocalThing(name=name, facts=facts))

    goal = reply.get("goal")
    intro = reply.get("intro")
    setup = SceneSetup(
        player=player,
        characters=cast,
        place=place,
        extras=extras,
        start=start,
        goal=goal.strip() if isinstance(goal, str) else "",
        intro=intro.strip() if isinstance(intro, str) else "",
        prompt=prompt,
    )
    setup.invented = _invented(setup)
    return setup


# --- stubs ---------------------------------------------------------------------


# stub kinds setup never fills: a culture can't be expanded yet, and a
# race needs its species and a mix its parents, which a stub has none of
_UNFILLED_STUB_KINDS = ("race", "mix")


def _stubs_named(view: WorldView, setup: SceneSetup) -> list[str]:
    """The stubs (not ignored) the setup's goal and intro name in full,
    in order: lore the scene uses, so it's pulled in and filled out."""

    text = "\n".join((setup.goal, setup.intro))
    return _dedupe(
        [
            match.candidates[0].id
            for match in find_names(view, text)
            if not match.suggested and match.candidates[0].stub
        ]
    )


def stubs_to_fill(world: World, setup: SceneSetup) -> list[str]:
    """The stubs `setup` uses that can be filled out, each once, in setup
    order: the player, the characters, the place, then the pulled-in lore
    (picked, or named in the reply; a stub the index merely found isn't
    pulled in). Ignored stubs too: using one revives it. A culture stub
    can't be expanded yet, and a race or mix stub has no species or
    parents to fill it from: those are left out (logged) and stay stubs."""

    view = world.view()
    refs = [setup.player, *setup.characters]
    if setup.place is not None:
        refs.append(setup.place)
    thing_ids = [ref.thing_id for ref in refs if ref.thing_id is not None]
    stub_ids = []
    for thing_id in _dedupe([*thing_ids, *setup.pulled_in]):
        state = view.thing(thing_id)
        if state is None or not state.is_stub:
            continue
        if state.kind not in CREATE_KINDS or state.kind in _UNFILLED_STUB_KINDS:
            log.info(
                "setup.stub_skipped",
                stub_id=thing_id,
                name=view.name_of(thing_id),
                kind=state.kind,
                reason=f"a {state.kind} stub can't be filled out from setup",
            )
            continue
        stub_ids.append(thing_id)
    return stub_ids


async def _stub_previews(
    world: World, setup: SceneSetup, client: Any
) -> list[CreatePreview]:
    """A preview filling out each stub `setup` uses (`stubs_to_fill`), made
    from the stub's suggested prompt and what its mentions say. A stub
    whose preview fails is logged and left a stub; the plan goes on. With
    no `client` (the browser tests' fixed setup) no stub is previewed."""

    stub_ids = stubs_to_fill(world, setup)
    if client is None:
        if stub_ids:
            log.info("setup.stubs_not_previewed", reason="no client", stubs=stub_ids)
        return []

    view = world.view()
    previews = []
    for stub_id in stub_ids:
        state = view.thing(stub_id)
        assert state is not None
        try:
            preview = await preview_thing(
                world,
                state.kind,
                suggested_prompt(view, stub_id),
                {},
                client,
                stub_id=stub_id,
            )
        except Exception as exc:
            log.warning(
                "setup.stub_preview_failed",
                stub_id=stub_id,
                name=view.name_of(stub_id),
                error=str(exc),
            )
            continue
        previews.append(preview)
    return previews


def _accept_stub_previews(world: World, previews: list[CreatePreview]) -> None:
    """Write each stub preview into its stub, keeping the id. A stub
    deleted since planning refuses the start before anything is written;
    one already filled out (by hand, in the meantime) is left as it is."""

    view = world.view()
    todo = []
    for preview in previews:
        if preview.stub_id is None:
            raise ValueError(f"not a stub preview: {preview.name}")
        state = view.thing(preview.stub_id)
        if state is None:
            raise ValueError(f"the stub was deleted: {preview.name}")
        if not state.is_stub:
            log.info("setup.stub_already_filled", stub_id=preview.stub_id)
            continue
        todo.append(preview)
    for preview in todo:
        accept_preview(world, preview)


# --- planning ------------------------------------------------------------------


async def plan_scene(
    world: World,
    prompt: str,
    picks: dict[str, str],
    player: str | None,
    start: WorldDate | None,
    client: Any,
    *,
    embedding_function: Any = None,
    reply: dict[str, Any] | None = None,
    new_names: list[str] | None = None,
) -> SceneSetup:
    """Plan a scene from the owner's storyline `prompt`. `picks` maps a
    `NameMatch.text` to the thing the owner chose for it, and `new_names`
    are the matched names the owner treats as new (always invented);
    `player` is the owner's pick of who they play, if any. `start` defaults to the world's
    current date (`create.current_date`). `embedding_function` is the
    index's, by default the memory agent's. A given `reply` stands in for
    the model's (no model or index is asked). Writes nothing to the world."""

    if reply is None:
        prose_gen.require_client(client)
    start = start or current_date(world)
    view = world.view(start)

    chosen = [*picks.values(), *([player] if player else [])]
    for thing_id in chosen:
        if view.thing(thing_id) is None:
            raise KeyError(f"no such thing: {thing_id}")

    hits = (
        _index_hits(world, prompt, start, embedding_function) if reply is None else []
    )
    # a stub the index happens to find is no lore the scene uses: only a
    # picked one, or one the reply uses, is
    hit_ids = [
        hit.thing_id
        for hit in hits
        if (state := view.thing(hit.thing_id)) is not None and not state.is_stub
    ]
    shown = [
        thing_id
        for thing_id in _dedupe([*chosen, *hit_ids])
        if view.thing(thing_id) is not None
    ]

    if reply is None:
        reply = await _ask(
            world,
            view,
            client,
            prompt=prompt,
            start=start,
            shown=shown,
            player_name=(view.name_of(player) or "") if player else "",
        )
    setup = _setup_from_reply(
        view,
        reply,
        picks=picks,
        player=SetupRef(thing_id=player) if player else None,
        start=start,
        prompt=prompt,
        new_names=frozenset(_norm(name) for name in new_names or [] if name.strip()),
    )
    setup.pulled_in = [
        thing_id
        for thing_id in _dedupe([*shown, *_stubs_named(view, setup)])
        if (state := view.thing(thing_id)) is not None
        and state.kind not in ("character", "place")
    ]
    setup.stub_previews = await _stub_previews(world, setup, client)
    log.info(
        "setup.plan",
        characters=len(setup.characters),
        pulled_in=len(setup.pulled_in),
        invented=len(setup.invented),
        stub_previews=len(setup.stub_previews),
    )
    return setup


# --- starting ------------------------------------------------------------------


def _scene_name(setup: SceneSetup) -> str:
    text = " ".join((setup.goal or setup.prompt).split()).rstrip(".")
    if len(text) > _SCENE_NAME_LENGTH:
        text = text[:_SCENE_NAME_LENGTH].rsplit(" ", 1)[0]
    return text or "New scene"


def _heritage_facts(view: WorldView, heritage_id: str) -> tuple[list[str], list[str]]:
    """`(physical/variation, instinct)` effective fact texts of
    `heritage_id` (its own facts, then what it inherits, overrides already
    applied), rendered so `[[thing:id]]` references read as names."""

    physical: list[str] = []
    instinct: list[str] = []
    for fact, _layer in heritage.effective_facts(view, heritage_id):
        if fact.category in ("physical", "variation"):
            physical.append(view.render(fact.text))
        elif fact.category == "instinct":
            instinct.append(view.render(fact.text))
    return physical, instinct


async def start_scene(world: World, setup: SceneSetup, client: Any) -> str:
    """Write `setup` as a new world scene and return its id. The world
    characters' prose is brought up to date at the start first, so the
    scene's character sheets are fresh; with no `client` (the browser
    tests) it's left as it is. The intro is the scene's intro, the
    narration Talemate opens the scene with; invented characters, the
    place and extras become scene-local things. The setup's stub previews
    are written to the world first, each into its stub
    (`_accept_stub_previews`), so the scene uses the full entries."""

    _accept_stub_previews(world, setup.stub_previews)

    refs: list[SetupRef] = []
    for ref in [setup.player, *setup.characters]:
        if not any(_same(ref, other) for other in refs):
            refs.append(ref)

    for ref in refs:
        if ref.thing_id is not None and client is not None:
            await prose_gen.ensure_prose(world, ref.thing_id, setup.start, client)

    entries: list[dict[str, object]] = []
    local_things: list[dict[str, object]] = []
    for position, ref in enumerate(refs):
        if ref.thing_id is not None:
            entries.append(
                {"thing_id": ref.thing_id, "active": True, "scene_fields": {}}
            )
            continue
        assert ref.local is not None
        local_id = uuid.uuid4().hex
        own_facts = list(ref.local.facts)
        description_facts = list(own_facts)
        base_attributes: dict[str, object] = {}
        # `world_own_facts` is set only alongside a heritage: it's what
        # lets `_carried` rebuild the invented character later without the
        # heritage's facts already baked into `description`
        # (`character.world_own_facts`), so a later `start_scene` can
        # re-derive them fresh instead of duplicating them. A `Character`
        # field, not a plain dict key, so it survives a save in between
        # (`persistence._character_entries` re-dumps from the live,
        # already-loaded `Character`, which has no other way to carry it).
        heritage_own_facts: list[str] = []
        if ref.local.heritage_id is not None:
            physical, instinct = _heritage_facts(
                world.view(setup.start), ref.local.heritage_id
            )
            description_facts += physical
            if instinct:
                base_attributes["personality"] = " ".join(instinct)
            heritage_own_facts = own_facts
        character = Character(
            name=ref.local.name,
            description=" ".join(description_facts),
            base_attributes=base_attributes,
            is_player=position == 0,
            world_heritage_id=ref.local.heritage_id,
            world_own_facts=heritage_own_facts,
        )
        entries.append({"local_id": local_id, "active": True})
        local_things.append(
            {
                "local_id": local_id,
                "kind": LOCAL_CHARACTER_KIND,
                "data": character.model_dump(mode="json"),
            }
        )

    state: dict[str, object] = {
        "intro": setup.intro,
        "characters": entries,
        "pulled_in": list(setup.pulled_in),
    }
    if setup.place is not None:
        if setup.place.thing_id is not None:
            state["place_thing_id"] = setup.place.thing_id
        else:
            assert setup.place.local is not None
            local_id = uuid.uuid4().hex
            state["place_local_id"] = local_id
            local_things.append(
                {
                    "local_id": local_id,
                    "kind": LOCAL_PLACE_KIND,
                    "data": setup.place.local.model_dump(),
                }
            )
    for extra in setup.extras:
        local_things.append(
            {
                "local_id": uuid.uuid4().hex,
                "kind": LOCAL_EXTRA_KIND,
                "data": extra.model_dump(),
            }
        )

    store = world.scenes()
    scene_id = store.create(
        _scene_name(setup),
        setup.start,
        premise="\n\n".join(p for p in (setup.summary, setup.prompt) if p.strip()),
        goal=setup.goal,
        player_thing_id=setup.player.thing_id,
        continued_from=setup.continued_from,
        state=state,
    )
    store.set_local_things(scene_id, local_things)
    log.info("setup.start", scene_id=scene_id, continued_from=setup.continued_from)
    return scene_id


# --- continuing ----------------------------------------------------------------


def _carried(
    record: SceneRecord, local_things: list[dict[str, Any]], view: WorldView
) -> tuple[SetupRef | None, list[SetupRef], SetupRef | None, list[LocalThing]]:
    """`(player, characters, place, extras)` carried over from `record`:
    the player, the characters still active, the place and the extras. A
    world thing that's since been deleted is dropped, the same way
    `pulled_in` is filtered against `view`."""

    local = {thing["local_id"]: thing for thing in local_things}

    def local_thing(data: dict[str, Any]) -> LocalThing:
        heritage_id = data.get("world_heritage_id") or data.get("heritage_id")
        heritage_id = heritage_id if isinstance(heritage_id, str) else None
        # a heritage-bearing character's own facts, kept apart from the
        # heritage's (`Character.world_own_facts`) -- `description`
        # already has the heritage's facts baked in, which `start_scene`
        # would otherwise re-derive on top of and duplicate
        own_facts = data.get("world_own_facts")
        if heritage_id is not None and isinstance(own_facts, list):
            return LocalThing(
                name=data["name"],
                facts=[f for f in own_facts if isinstance(f, str)],
                heritage_id=heritage_id,
            )
        if isinstance(data.get("facts"), list):
            return LocalThing(
                name=data["name"], facts=data["facts"], heritage_id=heritage_id
            )
        description = data.get("description") or ""
        return LocalThing(
            name=data["name"],
            facts=[description] if description else [],
            heritage_id=heritage_id,
        )

    player: SetupRef | None = None
    characters: list[SetupRef] = []
    for entry in record.state.get("characters") or []:
        thing_id = entry.get("thing_id")
        if thing_id:
            if view.thing(thing_id) is None:
                continue
            ref = SetupRef(thing_id=thing_id)
            is_player = thing_id == record.player_thing_id
        else:
            thing = local.get(entry.get("local_id"))
            if thing is None:
                continue
            ref = SetupRef(local=local_thing(thing["data"]))
            is_player = bool(thing["data"].get("is_player"))
        if is_player:
            player = ref
        elif entry.get("active", True):
            characters.append(ref)

    place: SetupRef | None = None
    place_thing_id = record.state.get("place_thing_id")
    place_local = local.get(record.state.get("place_local_id"))
    if isinstance(place_thing_id, str) and view.thing(place_thing_id) is not None:
        place = SetupRef(thing_id=place_thing_id)
    elif place_local is not None:
        place = SetupRef(local=local_thing(place_local["data"]))

    extras = [
        local_thing(thing["data"])
        for thing in local_things
        if thing["kind"] == LOCAL_EXTRA_KIND
    ]
    return player, characters, place, extras


async def _summarize(record: SceneRecord, messages: list[MessageRecord]) -> str:
    """What happened in the scene, from the summarizer's `summarize_events`
    over its intro and history."""

    parts = []
    intro = record.state.get("intro")
    if isinstance(intro, str) and intro.strip():
        parts.append(intro.strip())
    for message in messages:
        text = message.data.get("message")
        if message.kind in _SUMMARIZED_KINDS and isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        return ""

    summarizer = instance.get_agent("summarizer")
    with world_ai_call():
        summary = await summarizer.summarize_events("\n\n".join(parts))
    return str(summary or "").strip()


def _name(view: WorldView, ref: SetupRef) -> str:
    if ref.thing_id is not None:
        return view.name_of(ref.thing_id) or ""
    assert ref.local is not None
    return ref.local.name


async def continue_setup(
    world: World,
    scene_id: str,
    goal_prompt: str,
    client: Any,
    *,
    reply: dict[str, Any] | None = None,
) -> SceneSetup:
    """Plan the scene that follows `scene_id`: it starts where that one
    ended, at the same place, with the player and the characters still
    active there, and the same lore. The model writes the new goal and
    intro from `goal_prompt` and a summary of what happened; characters it
    brings in join the carried ones. A given `reply` stands in for the
    model's, and the summary is left empty (no summarizer is asked)."""

    if reply is None:
        prose_gen.require_client(client)
    store = world.scenes()
    record = store.get(scene_id)
    if record is None:
        raise KeyError(f"no such scene: {scene_id}")

    messages = store.messages(scene_id)
    start = scene_end(record.start, messages[-1].elapsed) if messages else record.start
    view = world.view(start)

    player, characters, place, extras = _carried(
        record, store.local_things(scene_id), view
    )
    pulled_in = [
        thing_id
        for thing_id in record.state.get("pulled_in") or []
        if view.thing(thing_id) is not None
    ]
    summary = await _summarize(record, messages) if reply is None else ""

    carried_refs = [*characters, *([place] if place is not None else [])]
    shown = _dedupe(
        [
            ref.thing_id
            for ref in [*([player] if player else []), *carried_refs]
            if ref.thing_id is not None
        ]
        + pulled_in
    )
    if reply is None:
        reply = await _ask(
            world,
            view,
            client,
            prompt=goal_prompt,
            start=start,
            shown=shown,
            player_name=_name(view, player) if player is not None else "",
            summary=summary,
            carried=[_name(view, ref) for ref in carried_refs],
        )
    planned = _setup_from_reply(
        view, reply, picks={}, player=player, start=start, prompt=goal_prompt
    )

    cast = list(characters)
    for ref in planned.characters:
        _add_ref(cast, ref, unless=planned.player)
    for extra in planned.extras:
        if not any(_norm(extra.name) == _norm(e.name) for e in extras):
            extras.append(extra)

    setup = planned.model_copy(
        update={
            "characters": cast,
            "place": place if place is not None else planned.place,
            "extras": extras,
            "pulled_in": pulled_in,
            "summary": summary,
            "continued_from": scene_id,
        }
    )
    setup.invented = _invented(setup)
    setup.stub_previews = await _stub_previews(world, setup, client)
    log.info("setup.continue", scene_id=scene_id, characters=len(cast))
    return setup
