"""Websocket plugin for the fantasymate world screens (`talemate.world`).

Reply contract: a request `{"type": "worlds", "action": <a>, ...}` is
answered with `{"type": "worlds", "action": <a>, "data": {...}}`. Errors go
through `signal_operation_failed` (an `operation_done` envelope with
`error.message`), writing nothing.

- Worlds: `list_worlds`, `create_world {name, present_year}`,
  `open_world {path}`, `get_present`, `set_present {year}`. A world's
  present (default year 1000) is the date things are created at before
  any scene has moved past it. The
  open world is held on the websocket handler (`handler.world`), one per
  connection, and closed when the connection goes.
- Things: `list_things {kind}` (stubs included, each with its `stub`
  marker; ignored stubs left out), `get_thing {id, at}`. A thing's payload
  holds its fields, the facts visible at `at` (each with the inherited
  facts it `overrides`), its cached prose per section (with whether it's
  stale, following its lineage), its whole change history (`timeline`)
  and the scenes it appears in. From `talemate.world.heritage` it adds what it inherits
  (`inherited`, each with what overrides it), its resolved `numbers`, a
  character's `life_stage` (from `born`, at `at` or else the world's
  "now"), and, on a species page, its `races` and `mixes`.
  `referenced_in` is what `thing_references` reports, plus
  `member_scenes`: the scenes with a member character (one whose lineage
  includes the thing) in them.
- Links: each own and inherited fact carries `segments`, its rendered
  text as `{text, ref, stub}` runs (`ref` the thing a run links to, `stub`
  whether that's a stub; a link to an ignored stub is plain text), and
  `prose_segments` holds each section's cached prose the same way, its
  names found by `world.names.find_names` (never the thing's own, and
  never making anything). The payload also has the thing's other names
  (`aka`), its `stub` marker (`null` or `{ignored}`; `fields` holds
  neither), its `mentions` (every other entry's fact that references it)
  and `named_stubs` (`{id, name, kind}` of the stubs its facts link to).
- Curation (curation spec): each own and inherited fact row, and each
  drawer item, carries `held_by`, `{id, name}` of the sphere, character
  or being that holds it as a belief (`spheres.held_by`, the implicit
  holder of a religion's or culture's beliefs statement included), or
  `null`. Every kind's payload has `entry_timeline`
  (`world.timelines.entry_timeline` at the world's `timeline_reach`,
  disagreements worked out): `[{fact_id, owner_id, owner_name, date,
  until, segments, here, disagrees_with}]` in date order -- its own
  dated facts and, for a sphere, the lines it gathers (`here` false,
  `owner_*` whose they are); `until` is set once the fact has ended (the
  screen shows "900–1010"), and a held line's `segments` read "<Holder>
  holds that ..." (`worldplay.held`), the holder linked.
  `set_held_by {thing_id, fact_id, holder_id|null, at}` sets or clears
  one own fact's holder in one revision (null makes it world truth, also
  for a beliefs statement) and answers with the thing; held-ness feeds
  description prose (ruling C3), so prose is refreshed when the thing's
  prose reads the fact's category. `pick_date {keep_fact_id,
  drop_fact_id, mode: "end"|"remove", thing_id?, at?}` settles a
  timeline disagreement: refused unless the two disagree now
  (`repeats.disagreeing_dates`, worked out again, never the client's
  word); "end" ends the dropped fact at the world's now, "remove" removes
  it, in one revision; answers `{keep_fact_id, drop_fact_id, mode,
  owner_id, notes, thing?}` and refreshes the dropped fact's entry's
  prose as an edit would. `get_curation` and `set_curation {settings}`
  (a part of `CurationSettings`, the rest kept; unknown or out of range
  refused) answer `{settings, defaults}`.
  Previews (`preview_thing`, `preview_sphere`, `preview_branch`,
  `fill_drawer`, `add_outer_body`) are the preview's dump plus names for
  display: `held_by_name` on each fact and elsewhere fact, `from_name`
  on each `move_in` row, `name`, `from_name` and `to_name` on each
  `refile` row. Everything curation adds is in the dump: facts' `ticked`,
  `repeat_of`, `held_by`; `elsewhere` (`target_id`, `target_name`, `new`,
  `category`, `text`, `since`, `held_by`, `ticked`, `repeat_of`);
  `same_as` and `verdict` (with its `why`); `new_names` (with `part_of`,
  `same_as`, `same_target_id`); `refile`; `move_in`. The accepts take the
  owner's edits to all of it back, validated (`RefileRow`, `ItemIn`, the
  preview models), and every accept answers `notes`. An accept schedules
  prose for each entry the world has whose prose reads what it took (an
  elsewhere fact, an item's text, a fact moved off it), never for a
  sphere's statements or timeline (rulings P18, P19).
- Stubs: `make_stub {thing_id, fact_id, text, kind}` makes a stub named
  `text` (or reuses the thing that already has that name, reviving an
  ignored stub) and links that phrase in the fact (its first plain
  occurrence, nothing else), answering like `correct_fact`. `list_stubs {include_ignored}` answers `{stubs: [{id, name, kind, first_mentioned:
  {thing_id, name}, mentions, ignored}]}`. `ignore_stub {id, ignored}` and
  `change_stub_kind {id, kind}` answer with the stub's payload.
  `stub_suggestion {id}` answers `{id, prompt, context}`: the create box's
  starting prompt for the stub and the mention context its expansion gets.
  `repoint_stub {stub_id, target_id}` (`talemate.worldplay.repoint`)
  points everything naming the stub at the target (an entry, or another
  live stub) -- fact links, fields, filings, ties, the stub's own facts
  and filing -- teaches the target its names and removes the stub, in one
  revision. It answers `{stub_id, stub_name, target, links, aka_added,
  facts_moved, notes}` (`target` the target's payload; `notes` what didn't
  carry over as the stub had it). Refused, writing nothing: the stub
  itself, a deleted thing or an ignored stub as the target, and a use the
  target can't take (a scene's, a field of another kind, a filing or tie
  when it isn't a sphere, a loop of parents or filings, a mix's parents or
  shares naming it twice, its own). Prose is refreshed where its input
  changed: the target's for facts or rendered fields it took, another
  thing's for a rendered field rewritten.
  `move_fact {fact_id, target_id}` (`repoint.move_fact`) moves one fact
  onto another entry in one revision (a new fact, the original removed,
  its overrides re-pointed) and answers `{fact_id, target, notes}` (the
  copy's id and the target's payload). Refused, writing nothing: a removed
  fact, a deleted target, the fact's own entry. Prose is refreshed for
  each side whose prose reads the fact's category.
  `preview_merge {from_id, into_id}` (`talemate.worldplay.merge`) answers
  `preview_merge {preview}`, writing nothing and asking no model: both
  names, both sides' facts (repeats unticked), the pairs that may disagree
  and what moves, and the links' words it would add as other names
  (`akas`). `accept_merge {preview, main_name, keep, lose, akas}` folds
  `from_id` into `into_id` in one revision (`keep`: each pair's key ->
  "a", "b" or "both"; `lose`: "remove" or "end") and answers `{from_id,
  into, main_name, links, aka_added, facts_moved, notes}`. Refused as
  Re-point is, and for a thing into itself, a sphere with parts or ties
  into a non-sphere, an entry into a stub, and a stale preview. Prose is
  refreshed for the into-side and each rendered field rewritten.
- Heritage: `override_fact {thing_id, overridden_fact_id, text, category,
  at}` adds an own fact that overrides an inherited one and answers like
  `add_fact`. `list_heritage` answers `{things: [{id, kind, name,
  species_ids}]}`, every species, race and mix, for the heritage picker.
  `find_mix {parents: [a, b]}` answers `{parents, mix_id}`, the mix of
  those two parents in either order (`null` if there's none yet).
- Create: `preview_thing {kind, prompt, fields, stub_id, picks,
  new_names}` runs in the background and answers `preview_thing {preview}`
  or `preview_failed {message}`; it writes nothing. `stub_id` expands that
  stub, `picks` maps a name written in the prompt to the thing the owner
  matched it to, and `new_names` are written names the owner treats as new.
  `accept_preview {preview, into_stub, same_target_id}` writes it (into
  the stub `into_stub`, or onto the entry `same_target_id`, "Is this
  X?", if given) and answers with the thing and `notes` (what was left
  out, as an elsewhere fact whose target was deleted since the preview);
  the prose of what else it changed is scheduled. For the browser
  tests only, `TALEMATE_TEST_FIXED_PREVIEW` names a JSON file (`{name,
  facts, prose, fields?, ties?}`) that previews are answered from instead
  of the model (listing what the request's fields inherit, and for a
  `stub_id` its kind, name, mention context and sphere `part_of`, as a
  real preview does). The file's facts may name a `held_by` holder, and
  it may hold `elsewhere` (`[{entry, text, since?, held_by?}]`) and
  `move_in` (`["M1", ...]`, the broader entry's facts as labelled), each
  read through the real parsers (`create.holder_named`,
  `parse_elsewhere`, `broader_entry` and `parse_move_in`).
- Edits: `add_fact`, `correct_fact`, `end_fact`, `remove_fact` and
  `set_field` each write one revision, answer with the thing, then start a
  background `ensure_prose` that answers `prose_updated {id}` (or
  `prose_failed`); with no AI client the edit stands and the prose is left
  stale. `regenerate_prose {id, at, section?}` regenerates that one
  section (answering `prose_updated {id, section}`), or every section.
  Prose tasks for one thing run one at a time, in order, so a later edit's
  check always sees what the earlier task cached.
- Delete: `thing_references {id}` answers `{id, kind, name, references}`
  (the facts, fields and scenes that use it, from
  `talemate.worldplay.references`), writing nothing. `delete_thing {id}`
  removes it in one manual revision noted "deleted <name>", so undoing
  that revision restores it, and answers `thing_deleted {id, kind}` and
  that kind's `list_things`. A loaded scene keeps playing with it until
  it's reloaded.
- Fact text written by hand (`add_fact`, `correct_fact`, `override_fact`,
  each taking `picks`, `new_names` and `spans`) is linked before it's
  written: first the `spans` (`[{start, end, ref}]`, code points: a fact
  form's existing links, by position, so two links of the same words keep
  their own targets; a span with a null `ref` keeps its words plain), then (`worldplay.links.link_text`) the names of
  entries and stubs, and the picks, in the rest, keeping the words
  written; the thing's own names, and names the owner treats as new, stay
  plain, and unknown phrases are never made stubs.
  `repoint_ref {thing_id, fact_id, occurrence, to_id, at}` points one
  reference of a fact (the `occurrence`-th in its text) at another thing,
  keeping its words and changing nothing else; it answers like
  `correct_fact`.
- Spheres (`talemate.world.spheres`): the thing payload has `sphere`
  (`null`, or `{template, agent, drawers: [{id, type, title, inherited,
  items: [{thing_id, fact_id, name, segments, inherited, stub}]}], people:
  [{character_id, name, role, since, until, within, within_name}],
  territory: [{id, name}],
  timeline, branches: [{id, name}], parent: {id, name} | null}`; an item
  in no drawer the sphere has is in a last `unsorted` drawer; `timeline`
  is the payload's `entry_timeline` lines after its undated `timeline`
  facts, a branch's inherited ones included, each a line with a null
  `date`), `part_of` (`null`, or `{sphere_id, sphere_name,
  drawer_id, drawer_title}`, Unsorted's title for a drawer that's gone)
  and, for a character, `ties` (`[{sphere_id, sphere_name, role, since,
  until, within, within_name, exceptions: [{fact_id, segments}]}]`). `list_things {kind:
  "sphere"}` lists place spheres too, each with its `template`, and adds
  `groups: [{template, things}]`. `preview_sphere {template, prompt,
  fields, stub_id, picks, new_names, promote_id}` and `preview_branch
  {parent_id, prompt}` run in the background like `preview_thing`
  (answering with `{preview}` data, or `preview_sphere_failed` /
  `preview_branch_failed`); `accept_sphere {preview}` writes either,
  answering with the sphere and `notes`.
  `fill_drawer {sphere_id, drawer_id}` answers the `FillPreview`,
  `{sphere_id, drawer_id, items, elsewhere, new_names, refile}` (or
  `fill_failed`) and `accept_fill {sphere_id,
  drawer_id, items, elsewhere, new_names, refile}` writes the ticked ones, answering with the
  sphere and `notes` (an elsewhere fact whose target was deleted).
  `add_outer_body {preview_type: "create" | "sphere" | "fill", preview,
  row_name, outer: {name, template, part_of}, as_sphere}` puts the outer body the
  owner named around a part of a preview (`worldplay.bodies`), with no
  model call, and answers `{preview_type, preview}`; the preview's
  `refile` rows are accepted with it (Fill's `accept_fill` takes
  `new_names` and `refile`). `add_statement {sphere_id, drawer_id, text, picks,
  new_names, spans, at}` writes a statement by hand into a drawer that
  holds items (own or inherited; not Unsorted), linked like `add_fact`,
  and answers with the sphere. `set_drawers {sphere_id, drawers}`, `set_part_of
  {thing_id, sphere_id|null, drawer_id}`, `set_ties {character_id, ties:
  [{sphere_id, role, since, until, within}]}` (`within`, a part of the
  sphere the tie is in, kept when left out), `add_exception {character_id,
  sphere_id, text, rejects: {thing_id}|{fact_id}|null}` and `end_item
  {sphere_id, thing_id|fact_id, at, by}` answer with the thing edited (the
  sphere, for `end_item`). Prose is refreshed only when rendered text
  changed: drawers, part-of and ties are no prose's input, nor are a
  sphere's statements and timeline (rulings P18, P19).
- Scenes: `match_names {text, at}` finds world thing names in a storyline
  prompt (the reply echoes `text` and `at`), each candidate marked `stub`
  and `via`, plus the `unknown` capitalised phrases no name covers.
  `plan_scene {prompt, picks, new_names, player, start}` (picks and names
  treated as new always win over automatic matching) and
  `continue_scene {scene_id, goal_prompt}` (saving that scene first if
  it's the one loaded) run in the background and answer
  with `{setup, names}` (the world things' names, for display), or
  `plan_failed`/`continue_failed`; they write nothing. The setup's
  `stub_previews` (`CreatePreview` dumps) fill out the stubs it uses.
  `start_scene {setup}` (background too: it brings the characters' prose
  up to date) writes the stub previews into their stubs, then the scene, and
  answers `{scene_id, target, scene}` (or `start_failed`), where
  `target` is the `world://` path the frontend then sends to `load_scene`.
  `list_scenes` lists the world's scenes, newest first.
  `reposition_scene {scene_id, start}` moves a scene's start date; if that
  scene is the one loaded, its characters are rebuilt for the new date and
  its status sent. The scene's world characters' prose is then brought up
  to date at the new start in the background, as after an edit.
  For the browser tests only, `TALEMATE_TEST_FIXED_SETUP` names a JSON
  file holding a scene-setup model reply (`{player, characters, place,
  goal, intro, extras?}`) that `plan_scene` and `continue_scene` use
  instead of asking any model; `start_scene` then leaves the prose as it
  is. With `TALEMATE_TEST_FIXED_PREVIEW` set as well, each stub the setup
  uses gets the fixed preview; without it, stubs stay stubs.
  Likewise `TALEMATE_TEST_FIXED_SPHERE` names a JSON file `{"sphere":
  {...}, "fill": [...], "branch": {...}}` of model replies (the core's,
  Fill's items, a branch's) that `preview_sphere`, `fill_drawer` and
  `preview_branch` read through their real parsing instead of asking the
  model; a missing file or key asks the model as usual. `fill` may also
  be the whole reply object, `{new_items, elsewhere, names}`, so a fixed
  Fill carries elsewhere facts (each with its `held_by`) through the real
  parser. A core has no elsewhere and no move-in (ruling C1), and a merge
  asks no model, so it has no fixed reply.

Dates go over the wire as `{"instant", "precision", "label"}`, the label
formatted with the world's calendar; `label` is ignored on the way in.
"""

import asyncio
import json
import os
import uuid
from collections.abc import Collection, Coroutine
from pathlib import Path
from typing import Any, Literal

import pydantic
import structlog

import talemate.instance as instance
from talemate.path import WORLDS_DIR
from talemate.server.websocket_plugin import Plugin
from talemate.world import heritage, spheres
from talemate.world.calendar import Calendar
from talemate.world.curation import CurationSettings
from talemate.world.dates import WorldDate
from talemate.world.kinds import (
    DRAWER_TYPES,
    HERITAGE_KINDS,
    KINDS,
    SPHERE_TEMPLATES,
    TEMPLATE_AGENT,
    UNSORTED_DRAWER_ID,
    WRITTEN_DRAWER_TYPES,
)
from talemate.world.names import find_names, unknown_proper_phrases
from talemate.world.prose import UNRENDERED_FIELDS
from talemate.world.refs import REF_PATTERN
from talemate.world.repeats import disagreeing_dates
from talemate.world.scenes import SceneRecord, scene_end
from talemate.world.store import Source, World
from talemate.world.timeline import TimelineEntry
from talemate.world.timelines import TimelineLine, entry_timeline
from talemate.world.view import FactState, Segment, ThingState, WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay import spheres as sphereplay
from talemate.worldplay.bodies import OuterBody, add_outer_body
from talemate.worldplay.characters import age_in_years
from talemate.worldplay.create import (
    CREATE_KINDS,
    PART_OF_KINDS,
    CreatePreview,
    ElsewhereFact,
    MoveInFact,
    PreviewException,
    PreviewFact,
    PreviewTie,
    accept_preview,
    broader_entry,
    broader_lines,
    child_part_of,
    current_date,
    drawer_types_for,
    exception_fact,
    flag_elsewhere_repeats,
    holder_named,
    matching_stub,
    move_in_rows,
    offer_same,
    parse_elsewhere,
    parse_move_in,
    part_of_since,
    preview_inherited,
    preview_thing,
    prose_reads,
    untick_moved_repeats,
)
from talemate.worldplay.held import held_text
from talemate.worldplay.links import (
    LinkSpan,
    NewName,
    link_phrase,
    link_text,
    make_stubs,
    name_key,
    repoint_ref,
)
from talemate.worldplay.mentions import mention_context, mentions, suggested_prompt
from talemate.worldplay.persistence import save_world_scene, world_target
from talemate.worldplay.references import thing_references
from talemate.worldplay.merge import MergePreview, accept_merge, preview_merge
from talemate.worldplay.repoint import move_fact, repoint_stub
from talemate.worldplay.setup import (
    SceneSetup,
    continue_setup,
    match_names,
    plan_scene,
    start_scene,
    stubs_to_fill,
)

__all__ = ["WorldsPlugin"]

log = structlog.get_logger("talemate.server.worlds")


def _date_in(value: Any) -> WorldDate | None:
    if value is None:
        return None
    if isinstance(value, WorldDate):
        return value
    return WorldDate.model_validate(value)


def _date_out(calendar: Calendar, date: WorldDate | None) -> dict | None:
    if date is None:
        return None
    return {
        "instant": date.instant,
        "precision": date.precision.value,
        "label": calendar.format(date),
    }


def _value_out(calendar: Calendar, value: object) -> object:
    if isinstance(value, WorldDate):
        return _date_out(calendar, value)
    return value


# --- payloads -----------------------------------------------------------------


# the present a new world starts at, unless the owner picks another year
DEFAULT_PRESENT_YEAR = 1000

# browser tests only: a JSON file `preview_thing` answers from (see the
# module docstring)
FIXED_PREVIEW_ENV = "TALEMATE_TEST_FIXED_PREVIEW"

# browser tests only: a JSON file holding the scene-setup model reply
# `plan_scene` and `continue_scene` use (see the module docstring)
FIXED_SETUP_ENV = "TALEMATE_TEST_FIXED_SETUP"

# browser tests only: a JSON file `{"sphere", "fill", "branch"}` of model
# replies `preview_sphere`, `fill_drawer` and `preview_branch` read instead
# of asking the model (see the module docstring)
FIXED_SPHERE_ENV = "TALEMATE_TEST_FIXED_SPHERE"


class CreateWorldPayload(pydantic.BaseModel):
    name: str
    present_year: int = DEFAULT_PRESENT_YEAR

    @pydantic.field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a world needs a name")
        return value.strip()


class OpenWorldPayload(pydantic.BaseModel):
    path: str


class SetPresentPayload(pydantic.BaseModel):
    year: int


class ListThingsPayload(pydantic.BaseModel):
    kind: str


class GetThingPayload(pydantic.BaseModel):
    id: str
    at: dict | None = None


class ThingIdPayload(pydantic.BaseModel):
    id: str


class PreviewPayload(pydantic.BaseModel):
    kind: str
    prompt: str
    fields: dict = pydantic.Field(default_factory=dict)
    # the stub this preview expands
    stub_id: str | None = None
    # a name written in the prompt -> the thing the owner matched it to
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    # names written in the prompt the owner treats as new
    new_names: list[str] = pydantic.Field(default_factory=list)


class RefileRow(pydantic.BaseModel):
    """A re-file row as `add_outer_body` makes it and the owner sends it
    back: the entry, where it's filed now, where it goes, and the owner's
    tick. Other keys (the names shown with it) pass through."""

    model_config = pydantic.ConfigDict(extra="allow", populate_by_name=True)

    thing_id: str
    from_: dict[str, Any] | None = pydantic.Field(default=None, alias="from")
    to: dict[str, str]
    ticked: bool = False


class ItemIn(pydantic.BaseModel):
    """A sphere core's or Fill's item as the owner sends it back: its text,
    and, for a named one, its name and kind; the owner's tick, and an
    entry the world has it's the same as. Other keys pass through as they
    came."""

    model_config = pydantic.ConfigDict(extra="allow")

    text: str
    name: str | None = None
    kind: str | None = None
    drawer_id: str | None = None
    thing_id: str | None = None
    same_target_id: str | None = None
    ticked: bool = True
    repeat_of: dict[str, Any] | None = None
    part_of: dict[str, str] | None = None


def _refile_in(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-file rows validated (`RefileRow`), as dicts the accept reads."""

    return [RefileRow.model_validate(row).model_dump(by_alias=True) for row in rows]


def _items_in(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Items validated (`ItemIn`), each the dict it was sent as."""

    return [
        ItemIn.model_validate(item).model_dump(exclude_unset=True) for item in items
    ]


class AcceptPreviewPayload(pydantic.BaseModel):
    preview: CreatePreview
    # "fill the stub instead": the stub a preview made without one fills
    into_stub: str | None = None
    # "Is this X?" -- yes: the entry the preview's material goes onto
    same_target_id: str | None = None

    @pydantic.model_validator(mode="after")
    def _rows(self) -> "AcceptPreviewPayload":
        self.preview.refile = _refile_in(self.preview.refile)
        return self


class _ThingEdit(pydantic.BaseModel):
    thing_id: str
    # the date the thing page is viewing as of: the reply and the prose
    # regenerated afterwards are for this date
    at: dict | None = None


class AddFactPayload(_ThingEdit):
    category: str
    text: str
    valid_from: dict | None = None
    valid_until: dict | None = None
    # a name written in the text -> the thing the owner picked for it
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    # names written in the text the owner treats as new: left plain
    new_names: list[str] = pydantic.Field(default_factory=list)
    # spans of the text linked by position (code points), before the rest
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)


class CorrectFactPayload(_ThingEdit):
    fact_id: str
    text: str | None = None
    category: str | None = None
    # unset means "keep"; an explicit null means "make it open"
    valid_from: dict | None = None
    valid_until: dict | None = None
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)


class RepointRefPayload(_ThingEdit):
    fact_id: str
    # which reference of the fact's text, 0-based, in order
    occurrence: int
    to_id: str


class MakeStubPayload(_ThingEdit):
    fact_id: str
    # the phrase in the fact the stub is named after
    text: str
    kind: str


class ListStubsPayload(pydantic.BaseModel):
    include_ignored: bool = False


class IgnoreStubPayload(pydantic.BaseModel):
    id: str
    ignored: bool


class RepointStubPayload(pydantic.BaseModel):
    stub_id: str
    target_id: str


class MoveFactPayload(pydantic.BaseModel):
    fact_id: str
    target_id: str


class PreviewMergePayload(pydantic.BaseModel):
    from_id: str
    into_id: str


class AcceptMergePayload(pydantic.BaseModel):
    preview: MergePreview
    main_name: str
    keep: dict[str, Literal["a", "b", "both"]] = {}
    lose: Literal["remove", "end"] = "remove"
    # the links' words to add as other names (of `preview.akas`); all when
    # left out
    akas: list[str] | None = None


class ChangeStubKindPayload(pydantic.BaseModel):
    id: str
    kind: str


class EndFactPayload(_ThingEdit):
    fact_id: str
    until: dict


class RemoveFactPayload(_ThingEdit):
    fact_id: str


class SetHeldByPayload(_ThingEdit):
    fact_id: str
    # the sphere, character or being that holds the fact as a belief;
    # null makes it world truth (also for a beliefs drawer's statement).
    # Required, so a client that leaves it out clears nothing.
    holder_id: str | None


class PickDatePayload(pydantic.BaseModel):
    keep_fact_id: str
    drop_fact_id: str
    # "end": the dropped fact ends at the world's now; "remove": it goes
    mode: Literal["end", "remove"]
    # the page the owner picked on: the reply carries its payload
    thing_id: str | None = None
    at: dict | None = None


class SetCurationPayload(pydantic.BaseModel):
    # the knobs to change (`CurationSettings`' fields); the rest are kept
    settings: dict[str, Any]

    @pydantic.field_validator("settings")
    @classmethod
    def _known(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = set(value) - set(CurationSettings.model_fields)
        if unknown:
            raise ValueError(f"no such curation setting: {', '.join(sorted(unknown))}")
        return value


class OverrideFactPayload(_ThingEdit):
    overridden_fact_id: str
    text: str
    category: str
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)


class FindMixPayload(pydantic.BaseModel):
    parents: list[str]

    @pydantic.field_validator("parents")
    @classmethod
    def _two(cls, value: list[str]) -> list[str]:
        if len(value) != 2:
            raise ValueError("a mix has two parents")
        return value


class SetFieldPayload(_ThingEdit):
    field: str
    value: Any
    valid_from: dict | None = None


class PreviewSpherePayload(pydantic.BaseModel):
    template: str
    prompt: str = ""
    fields: dict = pydantic.Field(default_factory=dict)
    # the stub this preview expands, or the thing it promotes (not both)
    stub_id: str | None = None
    promote_id: str | None = None
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)


class AcceptSpherePayload(pydantic.BaseModel):
    preview: sphereplay.SpherePreview

    @pydantic.model_validator(mode="after")
    def _rows(self) -> "AcceptSpherePayload":
        self.preview.items = _items_in(self.preview.items)
        self.preview.refile = _refile_in(self.preview.refile)
        return self


class FillDrawerPayload(pydantic.BaseModel):
    sphere_id: str
    drawer_id: str


class AcceptFillPayload(FillDrawerPayload):
    # `fill_drawer`'s items, less any the owner dropped
    items: list[dict[str, Any]]
    # `fill_drawer`'s facts about other entries, as the owner left them
    elsewhere: list[ElsewhereFact] = pydantic.Field(default_factory=list)
    # the outer bodies the owner named and the re-file rows
    # (`add_outer_body`), as it left them
    new_names: list[NewName] = pydantic.Field(default_factory=list)
    refile: list[dict[str, Any]] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _rows(self) -> "AcceptFillPayload":
        self.items = _items_in(self.items)
        self.refile = _refile_in(self.refile)
        return self


class AddOuterBodyPayload(pydantic.BaseModel):
    # which preview it is: `preview_thing`'s ("create"), `preview_sphere`'s
    # or `preview_branch`'s ("sphere"), or Fill's ("fill": `{sphere_id,
    # drawer_id, items, elsewhere, new_names, refile}`)
    preview_type: str
    preview: dict[str, Any]
    row_name: str
    outer: OuterBody
    # a new name the preview lists of another kind may become the body
    as_sphere: bool = False


class DrawerIn(pydantic.BaseModel):
    # left out for a new drawer: it's given an id
    id: str | None = None
    type: str
    title: str

    @pydantic.field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in DRAWER_TYPES:
            raise ValueError(f"no such drawer type: {value!r}")
        return value

    @pydantic.field_validator("title")
    @classmethod
    def _titled(cls, value: str) -> str:
        title = " ".join(value.split())
        if not title:
            raise ValueError("a drawer needs a title")
        return title


class SetDrawersPayload(pydantic.BaseModel):
    sphere_id: str
    drawers: list[DrawerIn]
    at: dict | None = None


class SetPartOfPayload(_ThingEdit):
    # `None` takes the thing out of every sphere
    sphere_id: str | None = None
    drawer_id: str = UNSORTED_DRAWER_ID


class TieIn(pydantic.BaseModel):
    sphere_id: str
    role: str = ""
    since: dict | None = None
    until: dict | None = None
    # the part of the sphere it's within (a thing filed in it); left out,
    # a tie to the same sphere keeps the part it had
    within: str | None = None


class SetTiesPayload(pydantic.BaseModel):
    character_id: str
    ties: list[TieIn]
    at: dict | None = None


class ItemRef(pydantic.BaseModel):
    """One item of a sphere: a thing part of it, or one of its statements
    (exactly one of the two)."""

    thing_id: str | None = None
    fact_id: str | None = None

    @pydantic.model_validator(mode="after")
    def _one(self) -> "ItemRef":
        if (self.thing_id is None) == (self.fact_id is None):
            raise ValueError("an item is a thing_id or a fact_id")
        return self


class AddExceptionPayload(pydantic.BaseModel):
    character_id: str
    sphere_id: str
    text: str
    # the item it departs from; `None` departs from the sphere's teaching
    # as a whole
    rejects: ItemRef | None = None
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)
    at: dict | None = None


class AddStatementPayload(pydantic.BaseModel):
    sphere_id: str
    drawer_id: str
    text: str
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)
    at: dict | None = None


# the fields set through an action of their own, which guards them:
# `set_field` refuses them, naming that action
GUARDED_FIELDS: dict[str, str] = {
    "part_of": "set_part_of",
    "ties": "set_ties",
    "drawers": "set_drawers",
}


class PreviewBranchPayload(pydantic.BaseModel):
    parent_id: str
    prompt: str


class EndItemPayload(ItemRef):
    sphere_id: str
    # the date the item ends at
    at: dict
    # what ended it, if anything (a sphere gets a timeline fact)
    by: str | None = None


class RegenerateProsePayload(pydantic.BaseModel):
    id: str
    at: dict | None = None
    # one section to regenerate; every section when left out
    section: str | None = None


class MatchNamesPayload(pydantic.BaseModel):
    text: str
    at: dict | None = None


class PlanScenePayload(pydantic.BaseModel):
    prompt: str
    # a `NameMatch.text` -> the thing id the owner picked for it
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    # matched names the owner treats as new: always invented
    new_names: list[str] = pydantic.Field(default_factory=list)
    player: str | None = None
    start: dict | None = None


class StartScenePayload(pydantic.BaseModel):
    setup: SceneSetup


class ContinueScenePayload(pydantic.BaseModel):
    scene_id: str
    goal_prompt: str


class RepositionScenePayload(pydantic.BaseModel):
    scene_id: str
    start: dict


def _fixed_sphere_reply(key: str) -> str | None:
    """The browser tests' fixed sphere reply for `key` (`sphere`, `fill`
    or `branch`), as the model's reply text, so the real parsing reads it:
    `None` when the setting is unset, its file isn't there, or the file has
    no `key`. A `fill` list is wrapped as `{"new_items": [...]}`; a `fill`
    object is the whole reply, so it can carry `elsewhere` (each with its
    `held_by`) and `names`."""

    path = _fixed_file(FIXED_SPHERE_ENV)
    if path is None:
        return None
    fixed = json.loads(path.read_text(encoding="utf-8"))
    reply = fixed.get(key)
    if reply is None:
        return None
    # a list is Fill's items alone; an object (`{"new_items", "elsewhere",
    # "names"}`) is the whole reply
    if key == "fill" and isinstance(reply, list):
        reply = {"new_items": reply}
    return json.dumps(reply)


def _fixed_file(env: str) -> Path | None:
    """The browser tests' fixed-reply file named by `env`, if it's set and
    a test has written the file; `None` otherwise, so a request with no
    fixed reply goes to the model (or says there's no client) as usual."""

    name = os.environ.get(env)
    if not name:
        return None
    path = Path(name)
    return path if path.exists() else None


async def _fixed_preview(
    path: Path, payload: PreviewPayload, world: World
) -> CreatePreview:
    """The browser tests' stand-in for `preview_thing`: the preview in
    `path`, for the request's kind, prompt, fields and picks, listing what
    they inherit in `view` as the real one does. With a `stub_id` it takes
    the stub's kind and name and carries its mention context, refusing a
    stub of a kind that can't be expanded as the real one does; without
    one, a live stub of the same kind and name is offered as
    `matching_stub_id`. An expanded stub that belongs in a sphere carries
    its `part_of` as the real one does (`create.child_part_of`), and a
    character's `ties` are the file's own, each `{sphere_id, sphere, role,
    since?, exceptions: [{text, item, thing_id?, fact_id?}]}`.

    Curation, read through the real parsers: a fact's `held_by` (a
    holder's name, `create.holder_named`); `elsewhere`, the model's
    `[{entry, text, since?, held_by?}]` (`create.parse_elsewhere`, repeats
    flagged, a new entry's row offered what it may be the same as); and
    `move_in`, the model's labels (`["M1", ...]`) of the broader entry's
    facts (`create.broader_entry`, `parse_move_in`, `move_in_rows`).
    Async so it runs through the same background task and reply path as
    the real one."""

    view = world.view()

    fixed = json.loads(path.read_text(encoding="utf-8"))
    fields = {**payload.fields, **fixed.get("fields", {})}
    kind, name = payload.kind, fixed["name"]
    holder = lambda held: holder_named(view, held)  # noqa: E731
    context: list[tuple[str, list[str]]] = []
    stub = view.thing(payload.stub_id) if payload.stub_id is not None else None
    if payload.stub_id is not None:
        if stub is None or not stub.is_stub:
            raise ValueError(f"not a stub: {payload.stub_id}")
        if stub.kind not in CREATE_KINDS:
            raise ValueError(f"a {stub.kind} stub can't be expanded yet")
        kind = stub.kind
        name = view.name_of(stub.id) or name
        context = mention_context(view, stub.id)
    part_of = (
        child_part_of(view, stub, payload.prompt, payload.picks)
        if stub is not None
        else None
    )
    # a fact's `held_by` is a holder's name, as the model writes it
    facts = [
        PreviewFact.model_validate(
            {
                **fact,
                "held_by": (
                    holder(fact["held_by"])
                    if isinstance(fact.get("held_by"), str)
                    else None
                ),
            }
        )
        for fact in fixed["facts"]
    ]
    settings = world.curation()
    calendar = world.calendar
    now_year = current_date(world).to_datetime().year
    elsewhere = parse_elsewhere(
        fixed.get("elsewhere") or [],
        view,
        own_keys={name_key(name)},
        own_ids={stub.id} if stub is not None else set(),
        listed=[],
        calendar=calendar,
        now_year=now_year,
        holder=holder,
    )
    flag_elsewhere_repeats(view, elsewhere, settings)
    offer_same(
        view,
        [e.new for e in elsewhere if e.new is not None],
        near_ids=[],
        exclude=[stub.id] if stub is not None else [],
    )
    move_in: list[MoveInFact] = []
    if "move_in" in fixed:
        broader_id = broader_entry(view, part_of=part_of, fields=fields, stub=stub)
        if broader_id is not None:
            _lines, labels = broader_lines(view, calendar, broader_id)
            wrapper = {"move_in": fixed["move_in"]}
            picked = parse_move_in(json.dumps(wrapper), wrapper, labels)
            move_in = move_in_rows(view, broader_id, picked)
            untick_moved_repeats(view, facts, move_in, settings)
    return CreatePreview(
        kind=kind,
        prompt=payload.prompt,
        fields=fields,
        name=name,
        facts=facts,
        prose=fixed["prose"],
        inherited=preview_inherited(view, kind, fields),
        stub_id=payload.stub_id,
        matching_stub_id=None if stub is not None else matching_stub(view, kind, name),
        context=context,
        picks=payload.picks,
        treated_as_new=payload.new_names,
        part_of=part_of,
        ties=fixed.get("ties", []) if kind == "character" else [],
        elsewhere=elsewhere,
        move_in=move_in,
    )


# --- links ------------------------------------------------------------------


def _stub_out(state: ThingState) -> dict | None:
    """A thing's stub marker for the wire: `None` for a full entry."""

    return {"ignored": state.stub_ignored} if state.is_stub else None


class _Links:
    """Linked text in one view, for the wire: runs of rendered text as
    `{text, ref, stub}`, `ref` the thing a run links to and `stub` whether
    that thing is a stub. A link to an ignored stub is plain text: ignoring
    a stub hides it everywhere. Each linked thing is looked up once."""

    def __init__(self, view: WorldView) -> None:
        self.view = view
        self._states: dict[str, ThingState | None] = {}

    def _state(self, thing_id: str) -> ThingState | None:
        if thing_id not in self._states:
            self._states[thing_id] = self.view.thing(thing_id)
        return self._states[thing_id]

    def _out(self, runs: list[Segment]) -> list[dict]:
        out: list[dict] = []
        for run in runs:
            state = self._state(run.ref) if run.ref is not None else None
            linked = state is not None and not state.stub_ignored
            ref = run.ref if linked else None
            if ref is None and out and out[-1]["ref"] is None:
                out[-1]["text"] += run.text
                continue
            out.append(
                {
                    "text": run.text,
                    "ref": ref,
                    "stub": linked and state is not None and state.is_stub,
                }
            )
        return out

    def segments(self, text: str) -> list[dict]:
        """A fact's text, rendered, as linked runs."""

        return self._out(self.view.segments(text))

    def prose_segments(self, text: str, owner: str) -> list[dict]:
        """Prose as linked runs: each name `find_names` matches links to
        its best candidate, keeping the words. A suggested match, and one
        that may mean `owner` (whose prose it is), stay plain."""

        runs: list[Segment] = []
        end = 0
        for match in find_names(self.view, text):
            if match.suggested or any(c.id == owner for c in match.candidates):
                continue
            runs.append(Segment(text=text[end : match.start], ref=None))
            runs.append(Segment(text=match.text, ref=match.candidates[0].id))
            end = match.end
        runs.append(Segment(text=text[end:], ref=None))
        return self._out([run for run in runs if run.text])

    def named_stubs(self, state: ThingState) -> list[dict]:
        """`{id, name, kind}` of each live stub `state`'s facts link to (not
        an ignored one), in the order they're first linked."""

        found: list[dict] = []
        seen: set[str] = {state.id}
        for fact in state.facts:
            for thing_id in fact.refs:
                if thing_id in seen:
                    continue
                seen.add(thing_id)
                other = self._state(thing_id)
                if other is None or not other.is_stub or other.stub_ignored:
                    continue
                found.append(
                    {
                        "id": thing_id,
                        "name": self.view.name_of(thing_id) or "",
                        "kind": other.kind,
                    }
                )
        return found


# --- curation -----------------------------------------------------------------


def _held_out(
    view: WorldView, fact: FactState, owner: ThingState | None
) -> dict | None:
    """Who holds `fact` (of `owner`) as a belief (`spheres.held_by`), as
    `{id, name}`, or `None` for world truth."""

    if owner is None:
        return None
    holder = spheres.held_by(view, fact, owner)
    if holder is None:
        return None
    return {"id": holder, "name": view.name_of(holder) or ""}


def _trimmed(runs: list[Segment], start: int, end: int) -> list[Segment]:
    """The characters `start:end` of `runs`' joined text, as runs."""

    out: list[Segment] = []
    position = 0
    for run in runs:
        lo, hi = max(start, position), min(end, position + len(run.text))
        if lo < hi:
            out.append(
                Segment(text=run.text[lo - position : hi - position], ref=run.ref)
            )
        position += len(run.text)
    return out


def _held_segments(
    view: WorldView,
    links: "_Links",
    fact: FactState | None,
    owner: ThingState | None,
    text: str,
) -> list[dict]:
    """A fact's text as linked runs, held-aware (`worldplay.held`): a held
    fact reads "<Holder> holds that <text>" (or "holds: <Text>"), the
    holder's name linked and the text's own links kept. `text` is the
    rendered text; a fact that isn't held is its plain linked runs."""

    if fact is None or owner is None:
        return [{"text": text, "ref": None, "stub": False}]
    plain = view.segments(fact.text)
    held = held_text(view, fact, owner, text)
    if held == text:
        return links._out(plain)
    holder = spheres.held_by(view, fact, owner)
    name = view.name_of(holder) if holder is not None else None
    fallback = [{"text": held, "ref": None, "stub": False}]
    if not name:
        return fallback
    shown = f"{name[0].upper()}{name[1:]}"
    lead = next(
        (
            lead
            for lead in (" holds that ", " holds: ")
            if held.startswith(shown + lead)
        ),
        None,
    )
    if lead is None:
        return fallback
    body = held[len(shown) + len(lead) :]
    # the text the body is worded from: stripped, its closing period gone,
    # only its first letter's case changed (`held.held_text`)
    start = len(text) - len(text.lstrip())
    core = text.strip().rstrip(".").rstrip()
    if not core or body[1 : len(core)] != core[1:]:
        return fallback
    runs = _trimmed(plain, start, start + len(core))
    runs[0] = Segment(text=body[0] + runs[0].text[1:], ref=runs[0].ref)
    pieces = [
        Segment(text=shown, ref=holder),
        Segment(text=lead, ref=None),
        *runs,
        Segment(text=body[len(core) :], ref=None),
    ]
    return links._out([piece for piece in pieces if piece.text])


def _line_out(
    view: WorldView, links: "_Links", calendar: Calendar, line: TimelineLine
) -> dict:
    """One timeline line for the wire (`world.timelines`): whose it is, its
    dates (`until` only once it has ended: "900–1010"), its text as linked
    runs worded held-aware, and the lines it disagrees with on the year."""

    owner = view.thing(line.owner_id)
    return {
        "fact_id": line.fact_id,
        "owner_id": line.owner_id,
        "owner_name": view.name_of(line.owner_id) or "",
        "date": _date_out(calendar, line.date),
        "until": _date_out(calendar, line.until),
        "segments": _held_segments(view, links, line.fact, owner, line.text),
        "here": line.here,
        "disagrees_with": list(line.disagrees_with),
    }


def _undated_line(
    view: WorldView, links: "_Links", owner_id: str, here: str, fact: FactState
) -> dict:
    """A sphere's undated `timeline` fact as a sphere page's timeline line
    (it has no place on an entry timeline: `date` is null)."""

    owner = view.thing(owner_id)
    return {
        "fact_id": fact.fact_id,
        "owner_id": owner_id,
        "owner_name": view.name_of(owner_id) or "",
        "date": None,
        "until": None,
        "segments": _held_segments(view, links, fact, owner, view.render(fact.text)),
        "here": owner_id == here,
        "disagrees_with": [],
    }


def _preview_out(world: World, preview: pydantic.BaseModel) -> dict:
    """A preview (create, sphere core or branch, Fill) for the wire: its
    dump, sent back as it is on accept, with the names the screen shows
    beside ids -- `held_by_name` on each fact and elsewhere fact,
    `from_name` on each move-in row, and `name`, `from_name`, `to_name` on
    each re-file row. The models ignore these on the way back in."""

    view = world.view()
    out = preview.model_dump(mode="json")

    def name(thing_id: object) -> str | None:
        return (view.name_of(thing_id) or "") if isinstance(thing_id, str) else None

    def home(link: object) -> str | None:
        if not isinstance(link, dict):
            return None
        if isinstance(link.get("name"), str):
            return link["name"]
        return name(link.get("sphere"))

    for row in [*out.get("facts", []), *out.get("elsewhere", [])]:
        row["held_by_name"] = name(row.get("held_by"))
    for row in out.get("move_in", []):
        row["from_name"] = name(row.get("from_id"))
    for row in out.get("refile", []):
        row["name"] = name(row.get("thing_id"))
        row["from_name"] = home(row.get("from"))
        row["to_name"] = home(row.get("to"))
    return out


def _settings_out(settings: CurationSettings) -> dict:
    return {
        "settings": settings.model_dump(mode="json"),
        "defaults": CurationSettings().model_dump(mode="json"),
    }


# --- spheres ------------------------------------------------------------------


def _own_fact(state: ThingState | None, fact_id: str | None) -> FactState | None:
    if state is None:
        return None
    return next((fact for fact in state.facts if fact.fact_id == fact_id), None)


def _item_out(view: WorldView, links: _Links, item: spheres.Item) -> dict:
    """A drawer's item for the wire: a statement's text, or the thing's
    fact `spheres.items` shows (`spheres.item_fact`: a nested sphere's
    summary), as linked runs."""

    if item.thing_id is not None:
        owner = view.thing(item.thing_id)
        fact = spheres.item_fact(owner) if owner is not None else None
    else:
        owner = view.thing(item.source_id)
        fact = _own_fact(owner, item.fact_id)
    return {
        "thing_id": item.thing_id,
        "fact_id": item.fact_id,
        "name": item.name,
        "segments": links.segments(fact.text) if fact is not None else [],
        "inherited": item.inherited,
        "stub": item.stub,
        "held_by": _held_out(view, fact, owner) if fact is not None else None,
    }


def _own_drawer_ids(state: ThingState) -> set[str]:
    """The ids in the sphere's own `drawers` field (not a parent's)."""

    raw = state.fields.get("drawers")
    return {
        drawer["id"]
        for drawer in (raw if isinstance(raw, list) else [])
        if isinstance(drawer, dict) and isinstance(drawer.get("id"), str)
    }


def _sphere_out(
    view: WorldView,
    links: _Links,
    calendar: Calendar,
    state: ThingState,
    timeline: list[dict],
) -> dict | None:
    """A sphere's own part of the thing payload (`None` for a thing that's
    no sphere): its template and agent flag; its drawers in order (a
    branch's inherited ones after its own, each marked `inherited`), each
    with its items, then `UNSORTED` when anything is in no drawer it has;
    its people (from ties), territory, timeline, branches and the sphere
    it branches from.

    The timeline is the entry timeline the payload has (`timeline`, the
    lines of `world.timelines.entry_timeline`: its own dated facts and
    what it gathers), after its undated `timeline` facts and a branch's
    inherited undated ones (`spheres.timeline`, which has no date to place
    them by)."""

    if not spheres.is_sphere(state):
        return None
    sphere_id = state.id
    template = state.fields.get("template")
    agent = state.fields.get("agent")
    if not isinstance(agent, bool):
        agent = (
            TEMPLATE_AGENT.get(template, False) if isinstance(template, str) else False
        )

    own = _own_drawer_ids(state)
    shelves = spheres.drawers(view, sphere_id)
    held = spheres.items(view, sphere_id)
    if any(item.drawer_id == spheres.UNSORTED.id for item in held):
        shelves = [*shelves, spheres.UNSORTED]
    drawers = [
        {
            "id": drawer.id,
            "type": drawer.type,
            "title": drawer.title,
            "inherited": drawer.id not in own and drawer.id != spheres.UNSORTED.id,
            "items": [
                _item_out(view, links, item)
                for item in held
                if item.drawer_id == drawer.id
            ],
        }
        for drawer in shelves
    ]

    parent_id = state.fields.get("parent") if state.kind == "sphere" else None
    parent = view.thing(parent_id) if isinstance(parent_id, str) else None
    branches = sorted(
        (
            other
            for other in view.things("sphere")
            if other.fields.get("parent") == sphere_id and other.id != sphere_id
        ),
        key=lambda other: other.created,
    )
    summary = spheres.summary_fact(state)
    # whose each undated timeline fact is: the sphere's, or a parent's
    owners = {
        fact.fact_id: other.id
        for other in spheres._chain(view, sphere_id)
        for fact in other.facts
    }
    return {
        "template": template if isinstance(template, str) else None,
        "agent": agent,
        # the summary's fact (ruling P21), shown and corrected as the
        # summary, not among the about facts
        "summary_fact_id": (
            summary.fact_id
            if summary is not None and spheres.is_summary_fact(summary)
            else None
        ),
        "drawers": drawers,
        "people": [
            {
                "character_id": tie.character_id,
                "name": view.name_of(tie.character_id) or "",
                "role": tie.role,
                "since": _date_out(calendar, tie.since),
                "until": _date_out(calendar, tie.until),
                "within": tie.within,
                "within_name": view.name_of(tie.within) if tie.within else None,
            }
            for tie in spheres.people(view, sphere_id)
        ],
        "territory": [
            {"id": place_id, "name": view.name_of(place_id) or ""}
            for place_id in spheres.territory(view, sphere_id)
        ],
        "timeline": [
            *(
                _undated_line(
                    view, links, owners.get(fact.fact_id, sphere_id), sphere_id, fact
                )
                for fact in spheres.timeline(view, sphere_id)
                if fact.valid_from is None
            ),
            *timeline,
        ],
        "branches": [
            {"id": other.id, "name": view.name_of(other.id) or ""} for other in branches
        ],
        "parent": (
            {"id": parent.id, "name": view.name_of(parent.id) or ""}
            if parent is not None and spheres.is_sphere(parent)
            else None
        ),
    }


def _drawer_title(view: WorldView, sphere_id: str, drawer_id: str) -> str:
    """The title of the sphere's drawer `drawer_id`; `UNSORTED`'s for one
    it doesn't have (dropped, or never there), where its items show."""

    for drawer in spheres.drawers(view, sphere_id):
        if drawer.id == drawer_id:
            return drawer.title
    return spheres.UNSORTED.title


def _part_of_out(view: WorldView, state: ThingState) -> dict | None:
    """The sphere drawer the thing is part of, or `None`: also for a
    sphere that's since been deleted (or is no sphere any more), as
    `spheres.items` never lists the thing there."""

    link = state.fields.get("part_of")
    if not isinstance(link, dict) or not isinstance(link.get("sphere"), str):
        return None
    sphere_id, drawer_id = link["sphere"], str(link.get("drawer") or "")
    sphere = view.thing(sphere_id)
    if sphere is None or not spheres.is_sphere(sphere):
        return None
    return {
        "sphere_id": sphere_id,
        "sphere_name": view.name_of(sphere_id) or "",
        "drawer_id": drawer_id,
        "drawer_title": _drawer_title(view, sphere_id, drawer_id),
    }


def _ties_out(
    view: WorldView, links: _Links, calendar: Calendar, state: ThingState
) -> list[dict]:
    """A character's (or real being's) ties, in its `ties` field's order,
    ended ones too, each with its exceptions (`spheres.exceptions`, in
    writing order). A tie to a sphere that's since been deleted is left
    out, as on the character sheet, and so are a being's while it isn't
    real (kept, hidden)."""

    if not spheres.acts_in_world(state):
        return []
    found = []
    for tie in spheres.ties_of(view, state.id):
        sphere = view.thing(tie.sphere_id)
        if sphere is None or not spheres.is_sphere(sphere):
            continue
        exceptions = sorted(
            spheres.exceptions(view, state.id, tie.sphere_id),
            key=lambda fact: fact.created,
        )
        found.append(
            {
                "sphere_id": tie.sphere_id,
                "sphere_name": view.name_of(tie.sphere_id) or "",
                "role": tie.role,
                "since": _date_out(calendar, tie.since),
                "until": _date_out(calendar, tie.until),
                "within": tie.within,
                "within_name": view.name_of(tie.within) if tie.within else None,
                "exceptions": [
                    {"fact_id": fact.fact_id, "segments": links.segments(fact.text)}
                    for fact in exceptions
                ],
            }
        )
    return found


def _kept_within(held: list[dict], value: dict[str, Any], position: int) -> str | None:
    """The part a stored tie was `within`, for the same tie sent without
    one: the stored tie of the same sphere, role and since, else the one
    at the same place in the list when it's to the same sphere."""

    key = (value["sphere"], value["role"], value["since"])
    match = next(
        (t for t in held if (t.get("sphere"), t.get("role"), t.get("since")) == key),
        None,
    )
    if match is None and position < len(held):
        if held[position].get("sphere") == value["sphere"]:
            match = held[position]
    within = match.get("within") if match is not None else None
    return within if isinstance(within, str) else None


def _new_drawer_ids(drawers: list[DrawerIn]) -> list[dict[str, str]]:
    """`drawers` as the `drawers` field holds them, a new drawer given an
    id no other has."""

    taken = {drawer.id for drawer in drawers if drawer.id is not None}
    out = []
    for drawer in drawers:
        drawer_id = drawer.id
        while drawer_id is None:
            drawer_id = uuid.uuid4().hex[:8]
            if drawer_id in taken:
                drawer_id = None
        taken.add(drawer_id)
        out.append({"id": drawer_id, "type": drawer.type, "title": drawer.title})
    return out


# --- the plugin ---------------------------------------------------------------


class WorldsPlugin(Plugin):
    router = "worlds"

    # where worlds live; tests point this at a temp directory
    worlds_root: Path | None = None

    def connect(self):
        # background tasks, kept referenced until they finish
        self.tasks: set[asyncio.Task] = set()
        # one lock per thing id, so its prose tasks run in order
        self._prose_locks: dict[str, asyncio.Lock] = {}

    def disconnect(self):
        self._set_world(None)

    # --- the open world ---------------------------------------------------

    @property
    def root(self) -> Path:
        return Path(self.worlds_root or WORLDS_DIR)

    @property
    def world(self) -> World | None:
        return getattr(self.websocket_handler, "world", None)

    def _set_world(self, world: World | None) -> None:
        """Make `world` the open one, closing the one before it. Background
        tasks still working on the old world are cancelled first."""

        old = self.world
        if old is not None and old is not world:
            for task in list(self.tasks):
                task.cancel()
            old.close()
        self.websocket_handler.world = world

    def _require_world(self) -> World:
        world = self.world
        if world is None:
            raise ValueError("No world is open")
        return world

    def _client(self) -> Any:
        return instance.get_agent("creator").client

    def _fixed_setup(self) -> dict | None:
        """The browser tests' fixed scene-setup reply, or `None` normally."""

        path = _fixed_file(FIXED_SETUP_ENV)
        if path is None:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _reply(self, action: str, data: Any) -> None:
        self.websocket_handler.queue_put(
            {"type": self.router, "action": action, "data": data}
        )

    def _world_info(self, world: World) -> dict:
        calendar = world.calendar
        return {
            "id": world.id,
            "name": world.name,
            "path": str(world.path),
            "head_rev": world.head_rev(),
            "calendar": calendar.model_dump(mode="json"),
            **self._present_info(world),
        }

    def _present_info(self, world: World) -> dict:
        """The world's present, and the "now" creation uses (the later of
        the present and where the latest scene got to)."""

        calendar = world.calendar
        return {
            "present": _date_out(calendar, world.present()),
            "now": _date_out(calendar, current_date(world)),
        }

    def _thing_payload(self, world: World, thing_id: str, at: WorldDate | None) -> dict:
        view = world.view(at)
        state = view.thing(thing_id)
        if state is None:
            raise KeyError(f"no such thing: {thing_id}")
        calendar = world.calendar

        links = _Links(view)
        facts = [
            {
                "fact_id": fact.fact_id,
                "category": fact.category,
                "text": fact.text,
                "rendered": view.render(fact.text),
                "segments": links.segments(fact.text),
                "valid_from": _date_out(calendar, fact.valid_from),
                "valid_until": _date_out(calendar, fact.valid_until),
                "source_rev": fact.source_rev,
                "overrides": list(fact.overrides),
                "held_by": _held_out(view, fact, state),
            }
            for fact in state.facts
        ]
        inherited = [
            {
                "fact_id": item.fact.fact_id,
                "category": item.fact.category,
                "rendered": view.render(item.fact.text),
                "segments": links.segments(item.fact.text),
                "source_id": item.source_id,
                "source_kind": item.source_kind,
                "source_name": item.source_name,
                "overridden_by": item.overridden_by,
                "held_by": _held_out(view, item.fact, view.thing(item.source_id)),
            }
            for item in heritage.inherited(view, thing_id)
        ]
        settings = world.curation()
        entry_lines = [
            _line_out(view, links, calendar, line)
            for line in entry_timeline(
                view,
                thing_id,
                reach=settings.timeline_reach,
                threshold=settings.repeat_threshold,
            )
        ]

        cache = world.prose()
        prose = {}
        prose_segments = {}
        for section in prose_gen.sections_for(state.kind):
            cached = cache.get(thing_id, section, at)
            prose_segments[section] = (
                links.prose_segments(cached.text, thing_id)
                if cached is not None
                else []
            )
            prose[section] = {
                "text": cached.text if cached is not None else None,
                "stale": cache.stale(
                    thing_id,
                    section,
                    at,
                    prose_gen.staleness_also(world, thing_id, section, at),
                    prose_gen.unread_categories(state.kind, section),
                ),
                "edited": cached.edited if cached is not None else False,
            }

        timeline = [
            {
                "date": _date_out(calendar, entry.date),
                "change": entry.change,
                "field": entry.field,
                "value": _value_out(calendar, entry.value),
                "fact_id": entry.fact_id,
                "text": entry.text,
                "category": entry.category,
                "source_rev": entry.source_rev,
                "source": entry.source.model_dump(mode="json"),
            }
            for entry in world.timeline(thing_id)
        ]

        return {
            "id": thing_id,
            "kind": state.kind,
            "name": view.name_of(thing_id) or "",
            "at": _date_out(calendar, at),
            "fields": {
                field: _value_out(calendar, value)
                for field, value in state.fields.items()
                # each has a key of its own
                if field not in ("aka", "stub")
            },
            "aka": state.fields.get("aka") or [],
            "stub": _stub_out(state),
            "facts": facts,
            "inherited": inherited,
            "numbers": heritage.numbers(view, thing_id).model_dump(),
            "life_stage": self._life_stage(world, view, state, at),
            **self._species_members(state, view),
            "prose": prose,
            "prose_segments": prose_segments,
            "mentions": [m.model_dump() for m in mentions(view, thing_id)],
            "named_stubs": links.named_stubs(state),
            "sphere": _sphere_out(view, links, calendar, state, entry_lines),
            "part_of": _part_of_out(view, state),
            "ties": _ties_out(view, links, calendar, state),
            # every change made to the thing (`World.timeline`)
            "timeline": timeline,
            # its dated facts, and what a sphere gathers (curation goal 6)
            "entry_timeline": entry_lines,
            "appears_in": self._appears_in(world, [thing_id]),
            "referenced_in": {
                **thing_references(world, thing_id),
                "member_scenes": self._appears_in(
                    world, heritage.members(view, thing_id)
                ),
            },
        }

    @staticmethod
    def _life_stage(
        world: World, view: WorldView, state: ThingState, at: WorldDate | None
    ) -> dict | None:
        """A character's life stage at `at` (the world's "now" when `at`
        is unset), from its `born` and its resolved numbers; `None` with
        no `born`, no numbers to go by, or not born yet at `at`."""

        born = state.fields.get("born")
        if state.kind != "character" or not isinstance(born, WorldDate):
            return None
        age = age_in_years(born, at if at is not None else current_date(world))
        if age < 0:
            return None
        stage, past_lifespan = heritage.life_stage(
            age, heritage.numbers(view, state.id)
        )
        if stage is None:
            return None
        return {"stage": stage, "past_lifespan": past_lifespan}

    @staticmethod
    def _species_members(state: ThingState, view: WorldView) -> dict:
        """A species page's races and mixes (a mix listed on every species
        it descends from), by name; empty lists for any other kind."""

        found: dict[str, list[dict]] = {"races": [], "mixes": []}
        if state.kind != "species":
            return found
        for kind, key in (("race", "races"), ("mix", "mixes")):
            found[key] = sorted(
                (
                    {"id": other.id, "name": view.name_of(other.id) or ""}
                    for other in view.things(kind)
                    if state.id in heritage.species_of(view, other.id)
                ),
                key=lambda entry: entry["name"],
            )
        return found

    def _appears_in(self, world: World, thing_ids: list[str]) -> list[dict]:
        """The scenes any of `thing_ids` takes part in: as the player, a
        character, the place, or pulled-in lore. Each scene once."""

        calendar = world.calendar
        wanted = set(thing_ids)
        scenes = []
        if not wanted:
            return scenes
        for record in world.scenes().list():
            state = record.state
            characters = state.get("characters") or []
            in_scene = {
                record.player_thing_id,
                state.get("place_thing_id"),
                *(state.get("pulled_in") or []),
                *(
                    entry.get("thing_id")
                    for entry in characters
                    if isinstance(entry, dict)
                ),
            }
            if wanted & in_scene:
                scenes.append(
                    {
                        "id": record.id,
                        "name": record.name,
                        "start": _date_out(calendar, record.start),
                    }
                )
        return scenes

    def _scene_out(self, world: World, record: SceneRecord) -> dict:
        calendar = world.calendar
        messages = world.scenes().messages(record.id)
        end = (
            scene_end(record.start, messages[-1].elapsed) if messages else record.start
        )
        return {
            "id": record.id,
            "name": record.name,
            "start": _date_out(calendar, record.start),
            "end": _date_out(calendar, end),
            "premise": record.premise,
            "goal": record.goal,
            "player_thing_id": record.player_thing_id,
            "continued_from": record.continued_from,
            "updated_at": record.updated_at,
        }

    def _setup_out(self, world: World, setup: SceneSetup) -> dict:
        """A setup for the wire, with the names of the world things in it
        (as of its start) for display."""

        view = world.view(setup.start)
        refs = [setup.player, *setup.characters]
        if setup.place is not None:
            refs.append(setup.place)
        thing_ids = [ref.thing_id for ref in refs if ref.thing_id is not None]
        return {
            "setup": {
                **setup.model_dump(mode="json"),
                "start": _date_out(world.calendar, setup.start),
            },
            "names": {
                thing_id: view.name_of(thing_id) or ""
                for thing_id in [*thing_ids, *setup.pulled_in]
            },
        }

    async def _planned(self, world: World, planning: Coroutine) -> SceneSetup:
        """`planning`'s setup. In the browser tests (a fixed setup, so no
        client to preview stubs with), the fixed preview, if there is one,
        stands in for each stub's preview, as `preview_thing` would."""

        setup = await planning
        fixed = _fixed_file(FIXED_PREVIEW_ENV)
        if fixed is None or setup.stub_previews:
            return setup
        view = world.view()
        setup.stub_previews = [
            await _fixed_preview(
                fixed,
                PreviewPayload(
                    kind=state.kind,
                    prompt=suggested_prompt(view, stub_id),
                    stub_id=stub_id,
                ),
                world,
            )
            for stub_id in stubs_to_fill(world, setup)
            if (state := view.thing(stub_id)) is not None
        ]
        return setup

    # --- background tasks -------------------------------------------------

    def _spawn(self, coro: Coroutine, callback) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(callback)
        return task

    def _schedule_prose(
        self,
        thing_id: str,
        at: WorldDate | None,
        *,
        regenerate: bool = False,
        section: str | None = None,
    ) -> asyncio.Task | None:
        """Bring `thing_id`'s prose up to date at `at` in the background:
        the stale sections, or with `regenerate` every section (just
        `section`, if given). Answers `prose_updated {id}` (with `section`,
        if given) when done. With no client to ask, the edit stands and
        the prose is left stale.

        `thing_id` may be gone by the time this runs -- deleted while the
        task sat queued, or (from `reposition_scene`) a character who's
        since been removed from the world. With `regenerate=False` that's
        skipped quietly rather than reported as "Error generating world
        prose" after what was, from the owner's side, a successful
        delete."""

        world = self._require_world()
        try:
            client = self._client()
        except KeyError:
            client = None
        if client is None:
            if regenerate:
                raise ValueError("No AI client is set up to write the prose")
            log.warning("worlds.prose_skipped", reason="no AI client")
            return None

        lock = self._prose_locks.setdefault(thing_id, asyncio.Lock())

        async def run() -> None:
            async with lock:
                if not regenerate:
                    if world.view(at).thing(thing_id) is None:
                        log.info(
                            "worlds.prose_skipped", reason="thing deleted", id=thing_id
                        )
                        return
                    await prose_gen.ensure_prose(world, thing_id, at, client)
                    return
                state = world.view(at).thing(thing_id)
                if state is None:
                    raise KeyError(f"no such thing: {thing_id}")
                sections = (section,) if section else prose_gen.sections_for(state.kind)
                for name in sections:
                    await prose_gen.generate_section(world, thing_id, name, at, client)

        done = {"id": thing_id, **({"section": section} if section else {})}
        return self._spawn(
            run(),
            self.create_task_done_callback(
                "prose_updated",
                "prose_failed",
                "Error generating world prose",
                success_data=done,
                failure_data=done,
            ),
        )

    def _require_fact_of(
        self, world: World, thing_id: str, fact_id: str
    ) -> TimelineEntry:
        """The live start of `thing_id`'s own fact `fact_id` (its text and
        dates), refusing an edit to a fact that isn't the thing's own, so
        the reply and the prose refresh are for the thing that changed."""

        for entry in world.timeline(thing_id):
            if entry.fact_id == fact_id and entry.change == "fact_start":
                return entry
        raise KeyError(f"no such fact on {thing_id}: {fact_id}")

    @staticmethod
    def _linked(
        world: World,
        thing_id: str,
        text: str,
        picks: dict[str, str],
        at: WorldDate | None,
        new_names: list[str] | None = None,
        spans: list[LinkSpan] | None = None,
    ) -> str:
        """Hand-written fact text with its names linked, as things are
        named at `at` (`links.link_text`): first the `spans` (a fact form's
        existing links, by position: each to its own thing, or kept plain),
        then entries, stubs and the owner's `picks` in the rest, never
        `thing_id` itself, nor a name the owner treats as new
        (`new_names`). A span to `thing_id`, or to a thing that isn't
        there, keeps its words plain. Unknown phrases stay as they are."""

        view = world.view(at)
        kept = [
            span
            if span.ref is None
            or (span.ref != thing_id and view.thing(span.ref) is not None)
            else LinkSpan(start=span.start, end=span.end)
            for span in spans or []
        ]
        return link_text(
            view,
            text,
            picks=picks,
            owner=thing_id,
            as_new=new_names or (),
            spans=kept,
        )

    @staticmethod
    def _require_stub(world: World, thing_id: str) -> ThingState:
        """The stub `thing_id`, refusing a missing thing or a full entry."""

        view = world.view()
        state = view.thing(thing_id)
        if state is None:
            raise KeyError(f"no such thing: {thing_id}")
        if not state.is_stub:
            raise ValueError(f"not a stub: {view.name_of(thing_id) or thing_id}")
        return state

    def _edited(
        self, action: str, thing_id: str, at: WorldDate | None, *, prose: bool = True
    ) -> None:
        """Answer an edit with the thing as of `at`, then refresh its prose
        -- unless the edit changes no rendered text (`prose=False`: a link
        made or re-pointed, an other name, the stub marker)."""

        self._reply(action, self._thing_payload(self._require_world(), thing_id, at))
        if prose:
            self._schedule_prose(thing_id, at)

    @staticmethod
    def _wrote_prose_input(
        world: World, candidates: list[str], skip: Collection[str] = ()
    ) -> list[str]:
        """Of `candidates` (the entries an accept may have written onto:
        its elsewhere targets, the entries its items link), those whose
        prose input the accept's revision changed: a full entry (no stub)
        with a fact written in that revision in a category its prose reads
        (`create.prose_reads`). A sphere's statements and timeline feed no
        prose (rulings P18, P19), so they schedule none."""

        rev = world.head_rev()
        view = world.view()
        changed: list[str] = []
        for thing_id in dict.fromkeys(candidates):
            if thing_id in skip:
                continue
            state = view.thing(thing_id)
            if state is None or state.is_stub:
                continue
            if any(
                entry.source_rev == rev
                and entry.category is not None
                and prose_reads(state.kind, entry.category)
                for entry in world.timeline(thing_id)
                if entry.change != "field"
            ):
                changed.append(thing_id)
        return changed

    @staticmethod
    def _elsewhere_targets(elsewhere: list[ElsewhereFact]) -> list[str]:
        """The entries the ticked elsewhere facts go onto: a listed target,
        or the entry the owner marked a new one's row the same as."""

        found: list[str] = []
        for item in elsewhere:
            if not item.ticked:
                continue
            target = item.target_id or (
                item.new.same_target_id if item.new is not None else None
            )
            if target is not None:
                found.append(target)
        return found

    @staticmethod
    def _item_targets(items: list[dict[str, Any]]) -> list[str]:
        """The entries the world has that ticked items link (their text is
        written onto them)."""

        return [
            target
            for item in items
            if item.get("ticked", True)
            for target in (item.get("thing_id") or item.get("same_target_id"),)
            if isinstance(target, str)
        ]

    # --- worlds -----------------------------------------------------------

    async def handle_list_worlds(self, data: dict):
        worlds = [
            {
                "id": info.id,
                "name": info.name,
                "path": str(info.path),
                "head_rev": info.head_rev,
            }
            for info in World.list(self.root)
        ]
        self._reply("list_worlds", {"worlds": worlds})

    async def handle_create_world(self, data: dict):
        payload = CreateWorldPayload(**data)
        # validated before anything is written: years run 1-9999
        present = WorldDate.of(payload.present_year)
        world = World.create(payload.name, root=self.root)
        world.set_present(present)
        self._set_world(world)
        self._reply("create_world", self._world_info(world))

    async def handle_open_world(self, data: dict):
        payload = OpenWorldPayload(**data)
        path = Path(payload.path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"not a world in {self.root}: {payload.path}")
        world = World.open(path)
        self._set_world(world)
        self._reply("open_world", self._world_info(world))

    async def handle_get_present(self, data: dict):
        self._reply("get_present", self._present_info(self._require_world()))

    async def handle_set_present(self, data: dict):
        payload = SetPresentPayload(**data)
        world = self._require_world()
        world.set_present(WorldDate.of(payload.year))
        self._reply("set_present", self._present_info(world))

    # --- things -----------------------------------------------------------

    async def handle_list_things(self, data: dict):
        """A kind's things. `sphere` lists every sphere -- places that have
        taken on a template too, under their own kind -- each with its
        `template`, and adds `groups`: `[{template, things}]` in template
        order, a sphere with no template under `other`."""

        payload = ListThingsPayload(**data)
        world = self._require_world()
        view = world.view()
        states = view.things(payload.kind)
        if payload.kind == "sphere":
            places = [
                state for state in view.things("place") if spheres.is_sphere(state)
            ]
            states = sorted([*states, *places], key=lambda state: state.created)
        things = []
        for state in states:
            if state.stub_ignored:
                continue
            entry: dict[str, Any] = {
                "id": state.id,
                "kind": state.kind,
                "name": view.name_of(state.id) or "",
            }
            if state.is_stub:
                entry["stub"] = _stub_out(state)
            if payload.kind == "sphere":
                template = state.fields.get("template")
                entry["template"] = template if isinstance(template, str) else None
            things.append(entry)
        reply: dict[str, Any] = {"kind": payload.kind, "things": things}
        if payload.kind == "sphere":
            reply["groups"] = [
                {"template": template, "things": grouped}
                for template in SPHERE_TEMPLATES
                if (
                    grouped := [
                        entry
                        for entry in things
                        if (
                            entry["template"]
                            if entry["template"] in SPHERE_TEMPLATES
                            else "other"
                        )
                        == template
                    ]
                )
            ]
        self._reply("list_things", reply)

    async def handle_list_heritage(self, data: dict):
        view = self._require_world().view()
        things = [
            {
                "id": state.id,
                "kind": state.kind,
                "name": view.name_of(state.id) or "",
                "species_ids": heritage.species_of(view, state.id),
            }
            for kind in HERITAGE_KINDS
            for state in sorted(
                view.things(kind), key=lambda state: view.name_of(state.id) or ""
            )
        ]
        self._reply("list_heritage", {"things": things})

    async def handle_find_mix(self, data: dict):
        payload = FindMixPayload(**data)
        view = self._require_world().view()
        a, b = payload.parents
        self._reply(
            "find_mix",
            {"parents": payload.parents, "mix_id": heritage.find_mix(view, a, b)},
        )

    async def handle_get_thing(self, data: dict):
        payload = GetThingPayload(**data)
        world = self._require_world()
        self._reply(
            "get_thing", self._thing_payload(world, payload.id, _date_in(payload.at))
        )

    # --- delete -----------------------------------------------------------

    async def handle_thing_references(self, data: dict):
        payload = ThingIdPayload(**data)
        world = self._require_world()
        view = world.view()
        state = view.thing(payload.id)
        if state is None:
            raise KeyError(f"no such thing: {payload.id}")
        self._reply(
            "thing_references",
            {
                "id": payload.id,
                "kind": state.kind,
                "name": view.name_of(payload.id) or "",
                "references": thing_references(world, payload.id),
            },
        )

    async def handle_delete_thing(self, data: dict):
        payload = ThingIdPayload(**data)
        world = self._require_world()
        view = world.view()
        state = view.thing(payload.id)
        if state is None:
            raise KeyError(f"no such thing: {payload.id}")
        name = view.name_of(payload.id) or payload.id
        with world.revision(Source.manual(note=f"deleted {name}")) as rev:
            rev.remove_thing(payload.id)
        log.info("worlds.thing_deleted", id=payload.id, kind=state.kind, name=name)
        self._reply("thing_deleted", {"id": payload.id, "kind": state.kind})
        await self.handle_list_things({"kind": state.kind})

    # --- create -----------------------------------------------------------

    async def handle_preview_thing(self, data: dict):
        payload = PreviewPayload(**data)
        world = self._require_world()
        fixed = _fixed_file(FIXED_PREVIEW_ENV)
        if fixed is not None:
            preview = _fixed_preview(fixed, payload, world)
        else:
            client = self._client()
            preview = preview_thing(
                world,
                payload.kind,
                payload.prompt,
                payload.fields,
                client,
                stub_id=payload.stub_id,
                picks=payload.picks,
                new_names=payload.new_names,
            )
        self._spawn(
            preview,
            self.create_task_done_callback(
                "preview_thing",
                "preview_failed",
                "Error previewing a world thing",
                success_data=lambda preview: _preview_out(world, preview),
            ),
        )

    async def handle_accept_preview(self, data: dict):
        payload = AcceptPreviewPayload(**data)
        world = self._require_world()
        notes: list[str] = []
        # the other things whose prose input the accept changed
        prose: list[str] = []
        thing_id = accept_preview(
            world,
            payload.preview,
            into_stub=payload.into_stub,
            same_target_id=payload.same_target_id,
            notes=notes,
            prose=prose,
        )
        self._reply(
            "accept_preview",
            {**self._thing_payload(world, thing_id, None), "notes": notes},
        )
        # the accept's own list (a re-pointed stub, a move-in's broader
        # entry, a same-thing target), then the elsewhere targets whose
        # prose reads what they took
        prose += self._wrote_prose_input(
            world,
            self._elsewhere_targets(payload.preview.elsewhere),
            skip={thing_id, *prose},
        )
        for changed in dict.fromkeys(prose):
            self._schedule_prose(changed, None)

    # --- spheres ----------------------------------------------------------

    async def handle_preview_sphere(self, data: dict):
        """A sphere's core (`worldplay.spheres.preview_sphere`), in the
        background like `preview_thing`: answers `preview_sphere {preview}`
        (a `SpherePreview` dump) or `preview_sphere_failed`; writes
        nothing."""

        payload = PreviewSpherePayload(**data)
        world = self._require_world()
        fixed = _fixed_sphere_reply("sphere")
        preview = sphereplay.preview_sphere(
            world,
            payload.template,
            payload.prompt,
            payload.fields,
            self._client() if fixed is None else None,
            stub_id=payload.stub_id,
            picks=payload.picks,
            new_names=payload.new_names,
            promote_id=payload.promote_id,
            reply=fixed,
        )
        self._spawn(
            preview,
            self.create_task_done_callback(
                "preview_sphere",
                "preview_sphere_failed",
                "Error previewing a sphere",
                success_data=lambda preview: _preview_out(world, preview),
            ),
        )

    async def handle_accept_sphere(self, data: dict):
        """Write a `preview_sphere` or `preview_branch` preview and answer
        with the sphere and `notes` (what was left out, and why). Its
        summary is cached as its description, as `accept_preview` caches a
        thing's prose; prose is scheduled only for an entry the world has
        whose prose reads what the accept wrote onto it (an item linking
        it, an elsewhere fact)."""

        payload = AcceptSpherePayload(**data)
        world = self._require_world()
        notes: list[str] = []
        thing_id = sphereplay.accept_sphere(world, payload.preview, notes=notes)
        self._reply(
            "accept_sphere",
            {**self._thing_payload(world, thing_id, None), "notes": notes},
        )
        for changed in self._wrote_prose_input(
            world,
            [
                *self._item_targets(payload.preview.items),
                *self._elsewhere_targets(payload.preview.elsewhere),
            ],
            skip={thing_id},
        ):
            self._schedule_prose(changed, None)

    async def handle_fill_drawer(self, data: dict):
        """New items for one drawer, in the background: answers
        `fill_drawer` (the `FillPreview`: `{sphere_id, drawer_id, items,
        elsewhere, new_names, refile}`) or `fill_failed`; writes nothing."""

        payload = FillDrawerPayload(**data)
        world = self._require_world()
        fixed = _fixed_sphere_reply("fill")
        filling = sphereplay.fill_drawer(
            world,
            payload.sphere_id,
            payload.drawer_id,
            self._client() if fixed is None else None,
            reply=fixed,
        )
        self._spawn(
            filling,
            self.create_task_done_callback(
                "fill_drawer",
                "fill_failed",
                "Error filling a sphere drawer",
                # the whole Fill preview, sent back as it is on accept
                success_data=lambda filled: _preview_out(world, filled),
                failure_data={
                    "sphere_id": payload.sphere_id,
                    "drawer_id": payload.drawer_id,
                },
            ),
        )

    async def handle_accept_fill(self, data: dict):
        """Write the Fill items the owner kept and answer with the sphere
        and `notes`. The sphere's prose isn't scheduled: a statement is no
        input to its description (ruling P18; P19: prose only when its
        input changes), and named items are new stubs. An entry the world
        has gets its prose scheduled when it took text its prose reads (an
        item linking it, an elsewhere fact)."""

        payload = AcceptFillPayload(**data)
        world = self._require_world()
        notes: list[str] = []
        sphereplay.accept_fill(
            world,
            payload.sphere_id,
            payload.drawer_id,
            payload.items,
            payload.elsewhere,
            new_names=payload.new_names,
            refile=payload.refile,
            notes=notes,
        )
        self._reply(
            "accept_fill",
            {
                **self._thing_payload(world, payload.sphere_id, None),
                "notes": notes,
            },
        )
        for changed in self._wrote_prose_input(
            world,
            [
                *self._item_targets(payload.items),
                *self._elsewhere_targets(payload.elsewhere),
            ],
            skip={payload.sphere_id},
        ):
            self._schedule_prose(changed, None)

    async def handle_add_outer_body(self, data: dict):
        """Put the outer body the owner named around a part of a preview
        (`bodies.add_outer_body`): no model call, nothing written. Answers
        `add_outer_body {preview_type, preview}`, the preview with the part
        filed in the body, the body a new name and the entries filed where
        it goes as unticked `refile` rows."""

        payload = AddOuterBodyPayload(**data)
        world = self._require_world()
        preview: CreatePreview | sphereplay.FillPreview
        if payload.preview_type == "create":
            preview = CreatePreview.model_validate(payload.preview)
        elif payload.preview_type == "sphere":
            preview = sphereplay.SpherePreview.model_validate(payload.preview)
        elif payload.preview_type == "fill":
            preview = sphereplay.FillPreview.model_validate(payload.preview)
        else:
            raise ValueError(f"no such preview type: {payload.preview_type!r}")
        preview = add_outer_body(
            world,
            preview,
            payload.row_name,
            payload.outer,
            as_sphere=payload.as_sphere,
        )
        self._reply(
            "add_outer_body",
            {
                "preview_type": payload.preview_type,
                "preview": _preview_out(world, preview),
            },
        )

    def _require_sphere(self, world: World, sphere_id: str) -> ThingState:
        state = world.view().thing(sphere_id)
        if state is None or not spheres.is_sphere(state):
            raise ValueError(f"not a sphere: {sphere_id}")
        return state

    async def handle_set_drawers(self, data: dict):
        """Set a sphere's own drawers, in order: add (no `id`), retitle,
        retype, reorder and drop. A dropped drawer's items aren't moved:
        `spheres.items` shows an item whose drawer the sphere lacks under
        `UNSORTED`, and that's where they show. Drawers change no rendered
        text: no prose is scheduled.

        A branch's inherited drawer sent back as it is (same id, type and
        title) stays inherited, not copied into the branch's own; one sent
        back changed is kept as the branch's own, overriding its
        parent's."""

        payload = SetDrawersPayload(**data)
        world = self._require_world()
        state = self._require_sphere(world, payload.sphere_id)
        if any(d.id == UNSORTED_DRAWER_ID for d in payload.drawers):
            raise ValueError("Unsorted isn't a drawer of its own")
        own = _own_drawer_ids(state)
        inherited = {
            d.id: (d.type, d.title)
            for d in spheres.drawers(world.view(), payload.sphere_id)
            if d.id not in own
        }
        drawers = _new_drawer_ids(
            [
                d
                for d in payload.drawers
                if d.id is None or inherited.get(d.id) != (d.type, d.title)
            ]
        )
        with world.revision(Source.manual(note="sphere drawers")) as rev:
            rev.set_field(payload.sphere_id, "drawers", drawers, None)
        self._edited(
            "set_drawers", payload.sphere_id, _date_in(payload.at), prose=False
        )

    async def handle_set_part_of(self, data: dict):
        """File a thing in a sphere's drawer (or its `UNSORTED`), or, with
        a null `sphere_id`, take it out of every sphere. A character never
        is part of one (people come from ties); a place goes in a places
        drawer and any other entry in one that holds entries
        (`create.drawer_types_for`); nothing goes in a sphere that is,
        through its `parent` and `part_of` links, inside it.

        The link is undated, unless the thing's `part_of` has dated values
        (an item `end_item` ended): then it holds from `at` (the date
        viewed, else the world's now), which can't be before the latest of
        them -- that one would still win. Changes no rendered text."""

        payload = SetPartOfPayload(**data)
        world = self._require_world()
        view = world.view()
        state = view.thing(payload.thing_id)
        if state is None:
            raise KeyError(f"no such thing: {payload.thing_id}")
        if state.kind not in PART_OF_KINDS:
            raise ValueError(f"a {state.kind} can't be part of a sphere")
        value: dict[str, str] | None = None
        if payload.sphere_id is not None:
            self._require_sphere(world, payload.sphere_id)
            if spheres.sits_in(view, payload.sphere_id, payload.thing_id):
                raise ValueError("a thing can't be part of a sphere inside it")
            drawer = next(
                (
                    d
                    for d in spheres.drawers(view, payload.sphere_id)
                    if d.id == payload.drawer_id
                ),
                None,
            )
            if drawer is None and payload.drawer_id != UNSORTED_DRAWER_ID:
                raise ValueError(f"the sphere has no drawer {payload.drawer_id}")
            if drawer is not None and drawer.type not in drawer_types_for(state.kind):
                raise ValueError(f"a {state.kind} doesn't go in a {drawer.type} drawer")
            value = {"sphere": payload.sphere_id, "drawer": payload.drawer_id}
        since = part_of_since(world, payload.thing_id, _date_in(payload.at))
        with world.revision(Source.manual()) as rev:
            rev.set_field(payload.thing_id, "part_of", value, since)
        self._edited("set_part_of", payload.thing_id, _date_in(payload.at), prose=False)

    async def handle_set_ties(self, data: dict):
        """Replace a character's (or real being's) ties. Each names a
        sphere in the world, and its `since` can't be after its `until`.
        The stored ties the payload hides (to a sphere deleted since) are
        kept, after the rest, so undoing the delete brings them back
        (ruling P12). A being that isn't real (believed, undecided) can't
        be tied: its ties stay as they were, hidden, until it's real. Ties
        are on the character sheet, not in its prose: none is scheduled."""

        payload = SetTiesPayload(**data)
        world = self._require_world()
        view = world.view()
        state = view.thing(payload.character_id)
        if state is not None and state.kind == "being":
            if not spheres.acts_in_world(state):
                raise ValueError("only a real being can be tied to a sphere")
        elif state is None or state.kind != "character":
            raise ValueError(f"not a character: {payload.character_id}")
        stored = state.fields.get("ties")
        held = (
            [t for t in stored if isinstance(t, dict)]
            if isinstance(stored, list)
            else []
        )
        ties = []
        for position, tie in enumerate(payload.ties):
            self._require_sphere(world, tie.sphere_id)
            since, until = _date_in(tie.since), _date_in(tie.until)
            if (
                since is not None
                and until is not None
                and since.instant > until.instant
            ):
                raise ValueError("a tie can't end before it starts")
            value: dict[str, Any] = {
                "sphere": tie.sphere_id,
                "role": tie.role.strip(),
                "since": since.model_dump(mode="json") if since else None,
                "until": until.model_dump(mode="json") if until else None,
            }
            if "within" in tie.model_fields_set:
                within = tie.within
                if within is not None and not spheres.within_sphere(
                    view, within, tie.sphere_id
                ):
                    raise ValueError(
                        f"a tie can only be within a part of its sphere: {within}"
                    )
            else:
                # a client that doesn't send it keeps the stored tie's
                within = _kept_within(held, value, position)
            if within is not None:
                value["within"] = within
            ties.append(value)
        for raw in stored if isinstance(stored, list) else []:
            sphere_id = raw.get("sphere") if isinstance(raw, dict) else None
            sphere = view.thing(sphere_id) if isinstance(sphere_id, str) else None
            if sphere is None or not spheres.is_sphere(sphere):
                ties.append(raw)
        with world.revision(Source.manual()) as rev:
            rev.set_field(payload.character_id, "ties", ties, None)
        self._edited(
            "set_ties", payload.character_id, _date_in(payload.at), prose=False
        )

    async def handle_add_exception(self, data: dict):
        """Add a "but..." to a character's tie: a `ties` fact written as
        character creation writes one (`create.exception_fact`), so
        `spheres.exceptions` finds it. `rejects` is the item it departs
        from, `{thing_id}` (a thing part of the sphere: the fact links it)
        or `{fact_id}` (one of its statements: the fact links the sphere
        and its origin names the statement), a live item of the sphere,
        inherited ones included; null departs from the sphere as a whole.
        The text is linked like `add_fact`'s. The character needs a tie to
        the sphere. A fact feeds its prose, which is refreshed."""

        payload = AddExceptionPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        view = world.view()
        state = view.thing(payload.character_id)
        if state is not None and state.kind == "being":
            if not spheres.acts_in_world(state):
                raise ValueError("only a real being can have exceptions to a tie")
        elif state is None or not spheres.acts_in_world(state):
            raise ValueError(f"not a character: {payload.character_id}")
        self._require_sphere(world, payload.sphere_id)
        if all(
            tie.sphere_id != payload.sphere_id
            for tie in spheres.ties_of(view, payload.character_id)
        ):
            raise ValueError("the character has no tie to that sphere")
        if not payload.text.strip():
            raise ValueError("an exception needs some text")

        sphere_name = view.name_of(payload.sphere_id) or ""
        rejects = payload.rejects
        item_name = sphere_name
        if rejects is not None:
            item = next(
                (
                    item
                    for item in spheres.items(view, payload.sphere_id)
                    if (item.thing_id, item.fact_id)
                    == (rejects.thing_id, rejects.fact_id)
                ),
                None,
            )
            if item is None:
                raise ValueError("that's no item of the sphere")
            item_name = item.name
        text = self._linked(
            world,
            payload.character_id,
            payload.text,
            payload.picks,
            at,
            payload.new_names,
            payload.spans,
        )
        tie = PreviewTie(sphere_id=payload.sphere_id, sphere=sphere_name, role="")
        exception = PreviewException(
            text=payload.text,
            item=item_name,
            thing_id=rejects.thing_id if rejects is not None else None,
            fact_id=rejects.fact_id if rejects is not None else None,
        )
        text, origin = exception_fact(text, tie, exception)
        with world.revision(Source.manual()) as rev:
            rev.add_fact(payload.character_id, "ties", text, origin=origin)
        self._edited("add_exception", payload.character_id, at)

    async def handle_add_statement(self, data: dict):
        """Write a statement by hand into one of a sphere's drawers (its
        own or inherited) that holds items: a `statement` fact of the
        sphere, undated, its drawer as its origin, as Fill and creation
        write one (`worldplay.spheres`). The text is linked like
        `add_fact`'s. Not people, events, branches or Unsorted. A
        statement feeds no prose (rulings P18, P19), so none is
        scheduled."""

        payload = AddStatementPayload(**data)
        world = self._require_world()
        self._require_sphere(world, payload.sphere_id)
        drawer = next(
            (
                d
                for d in spheres.drawers(world.view(), payload.sphere_id)
                if d.id == payload.drawer_id
            ),
            None,
        )
        if drawer is None:
            raise ValueError(f"the sphere has no drawer {payload.drawer_id}")
        if drawer.type not in WRITTEN_DRAWER_TYPES:
            raise ValueError(f"a {drawer.type} drawer holds no statements")
        if not payload.text.strip():
            raise ValueError("a statement needs some text")
        at = _date_in(payload.at)
        text = self._linked(
            world,
            payload.sphere_id,
            payload.text.strip(),
            payload.picks,
            at,
            payload.new_names,
            payload.spans,
        )
        with world.revision(Source.manual()) as rev:
            rev.add_fact(
                payload.sphere_id, "statement", text, origin={"drawer": drawer.id}
            )
        # a statement is no input to the sphere's prose (rulings P18, P19)
        self._edited("add_statement", payload.sphere_id, at, prose=False)

    async def handle_preview_branch(self, data: dict):
        """A branch of a sphere, in the background: answers
        `preview_branch {preview}` (a `SpherePreview` dump, accepted with
        `accept_sphere`) or `preview_branch_failed`; writes nothing."""

        payload = PreviewBranchPayload(**data)
        world = self._require_world()
        fixed = _fixed_sphere_reply("branch")
        preview = sphereplay.preview_branch(
            world,
            payload.parent_id,
            payload.prompt,
            self._client() if fixed is None else None,
            reply=fixed,
        )
        self._spawn(
            preview,
            self.create_task_done_callback(
                "preview_branch",
                "preview_branch_failed",
                "Error previewing a branch",
                success_data=lambda preview: _preview_out(world, preview),
            ),
        )

    async def handle_end_item(self, data: dict):
        """End one of a sphere's own items at `at` (`thing_id` or
        `fact_id`), noting `by` (`worldplay.spheres.end_item`), and answer
        with the sphere. Prose is refreshed for the full entry whose input
        it changed: the thing item (its note), or the sphere for a
        statement (its `about` note). A `by` sphere's `timeline` fact feeds
        no prose (rulings P18, P19)."""

        payload = EndItemPayload(**data)
        world = self._require_world()
        view = world.view()
        self._require_sphere(world, payload.sphere_id)
        item = next(
            (
                item
                for item in spheres.items(view, payload.sphere_id)
                if (item.thing_id, item.fact_id) == (payload.thing_id, payload.fact_id)
            ),
            None,
        )
        if item is None:
            raise ValueError("that's no item of the sphere")
        sphereplay.end_item(
            world,
            payload.sphere_id,
            item,
            WorldDate.model_validate(payload.at),
            payload.by,
        )
        self._edited("end_item", payload.sphere_id, None, prose=False)
        # the item's note (an `about` or `general` fact) is prose input; a
        # `by` sphere's timeline fact isn't (rulings P18, P19)
        changed = item.thing_id or payload.sphere_id
        state = world.view().thing(changed)
        if state is not None and not state.is_stub:
            self._schedule_prose(changed, None)

    # --- stubs ------------------------------------------------------------

    async def handle_make_stub(self, data: dict):
        """Make a stub named `text` (or reuse the thing already named so,
        reviving an ignored stub) and link that phrase in the fact,
        answering like `correct_fact`. Only the first occurrence of the
        phrase outside any reference is linked; nothing else in the fact
        changes. A phrase the fact doesn't hold that way is refused, writing
        nothing."""

        payload = MakeStubPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        fact = self._require_fact_of(world, payload.thing_id, payload.fact_id)
        phrase = " ".join(payload.text.split())
        if not phrase:
            raise ValueError("a stub needs a name")
        if payload.kind not in KINDS:
            raise ValueError(f"no such kind: {payload.kind!r}")
        old_text = fact.text or ""
        with world.revision(Source.manual(note=f"stub {phrase}")) as rev:
            made = make_stubs(
                rev, world.view(at), [NewName(name=phrase, kind=payload.kind)]
            )
            stub_id = made[phrase]
            if stub_id == payload.thing_id:
                raise ValueError(f"{phrase!r} is this thing's own name")
            reused = world.view(at).thing(stub_id)
            if reused is not None and reused.stub_ignored:
                # the owner asked for it by name: it's no longer ignored
                rev.set_field(stub_id, "stub", {"ignored": False}, None)
            # only the phrase is linked: the rest of the fact stays as the
            # owner left it (a name treated as new stays plain)
            rev.correct_fact(
                payload.fact_id, text=link_phrase(old_text, phrase, stub_id)
            )
        log.info("worlds.stub_made", id=stub_id, name=phrase, kind=payload.kind)
        self._edited("make_stub", payload.thing_id, at, prose=False)

    async def handle_list_stubs(self, data: dict):
        payload = ListStubsPayload(**data)
        view = self._require_world().view()
        stubs = []
        for state in view.things():
            if not state.is_stub or (
                state.stub_ignored and not payload.include_ignored
            ):
                continue
            found = mentions(view, state.id)
            # the mention written first: the lowest revision, then fact order
            written = {
                fact.fact_id: fact.source_rev
                for _owner, fact in view.referencing(state.id, any_date=True)
            }
            first = min(
                enumerate(found),
                key=lambda pair: (written.get(pair[1].fact_id, 0), pair[0]),
                default=None,
            )
            stubs.append(
                {
                    "id": state.id,
                    "name": view.name_of(state.id) or "",
                    "kind": state.kind,
                    "first_mentioned": (
                        {"thing_id": first[1].owner_id, "name": first[1].owner_name}
                        if first is not None
                        else None
                    ),
                    "mentions": len(found),
                    "ignored": state.stub_ignored,
                }
            )
        stubs.sort(key=lambda stub: (stub["name"].casefold(), stub["id"]))
        self._reply("list_stubs", {"stubs": stubs})

    async def handle_ignore_stub(self, data: dict):
        payload = IgnoreStubPayload(**data)
        world = self._require_world()
        self._require_stub(world, payload.id)
        with world.revision(Source.manual()) as rev:
            rev.set_field(payload.id, "stub", {"ignored": payload.ignored}, None)
        self._reply("ignore_stub", self._thing_payload(world, payload.id, None))

    async def handle_change_stub_kind(self, data: dict):
        payload = ChangeStubKindPayload(**data)
        world = self._require_world()
        self._require_stub(world, payload.id)
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind(payload.id, payload.kind)
        self._reply("change_stub_kind", self._thing_payload(world, payload.id, None))

    async def handle_stub_suggestion(self, data: dict):
        payload = ThingIdPayload(**data)
        world = self._require_world()
        self._require_stub(world, payload.id)
        view = world.view()
        self._reply(
            "stub_suggestion",
            {
                "id": payload.id,
                "prompt": suggested_prompt(view, payload.id),
                "context": [
                    [heading, facts]
                    for heading, facts in mention_context(view, payload.id)
                ],
            },
        )

    async def handle_repoint_stub(self, data: dict):
        """Point everything that names a stub at `target_id` and remove the
        stub, in one revision (`worldplay.repoint.repoint_stub`). Prose
        is refreshed only where its input changed: the target's, for the
        stub's facts or rendered fields it took, and another thing's, for a
        rendered field rewritten (a parent, a culture, a heritage)."""

        payload = RepointStubPayload(**data)
        world = self._require_world()
        done = repoint_stub(world, payload.stub_id, payload.target_id)
        self._reply(
            "repoint_stub",
            {
                "stub_id": payload.stub_id,
                "stub_name": done.stub_name,
                "target": self._thing_payload(world, payload.target_id, None),
                "links": done.links,
                "aka_added": done.aka_added,
                "facts_moved": done.facts_moved,
                "notes": done.notes,
            },
        )
        for thing_id in done.prose:
            self._schedule_prose(thing_id, None)

    async def handle_move_fact(self, data: dict):
        """Move one fact onto another entry (`worldplay.repoint.move_fact`),
        in one revision. Prose is refreshed for each side whose prose reads
        the fact."""

        payload = MoveFactPayload(**data)
        world = self._require_world()
        notes: list[str] = []
        prose: list[str] = []
        new_id = move_fact(
            world, payload.fact_id, payload.target_id, notes=notes, prose=prose
        )
        self._reply(
            "move_fact",
            {
                "fact_id": new_id,
                "target": self._thing_payload(world, payload.target_id, None),
                "notes": notes,
            },
        )
        for thing_id in prose:
            self._schedule_prose(thing_id, None)

    async def handle_preview_merge(self, data: dict):
        """What merging one entry into another would do
        (`worldplay.merge.preview_merge`): no model call, nothing written."""

        payload = PreviewMergePayload(**data)
        world = self._require_world()
        preview = preview_merge(world, payload.from_id, payload.into_id)
        self._reply("preview_merge", {"preview": preview.model_dump(mode="json")})

    async def handle_accept_merge(self, data: dict):
        """Merge one entry into another as the owner picked, in one
        revision (`worldplay.merge.accept_merge`). Prose is refreshed for
        the into-side and each thing whose rendered fields changed."""

        payload = AcceptMergePayload(**data)
        world = self._require_world()
        done = accept_merge(
            world,
            payload.preview,
            main_name=payload.main_name,
            keep=payload.keep,
            lose=payload.lose,
            akas=payload.akas,
        )
        self._reply(
            "accept_merge",
            {
                "from_id": payload.preview.from_id,
                "into": self._thing_payload(world, payload.preview.into_id, None),
                "main_name": done.target_name,
                "links": done.links,
                "aka_added": done.aka_added,
                "facts_moved": done.facts_moved,
                "notes": done.notes,
            },
        )
        for thing_id in done.prose:
            self._schedule_prose(thing_id, None)

    # --- edits ------------------------------------------------------------

    async def handle_add_fact(self, data: dict):
        payload = AddFactPayload(**data)
        world = self._require_world()
        text = self._linked(
            world,
            payload.thing_id,
            payload.text,
            payload.picks,
            _date_in(payload.valid_from) or _date_in(payload.at),
            payload.new_names,
            payload.spans,
        )
        with world.revision(Source.manual()) as rev:
            rev.add_fact(
                payload.thing_id,
                payload.category,
                text,
                valid_from=_date_in(payload.valid_from),
                valid_until=_date_in(payload.valid_until),
            )
        self._edited("add_fact", payload.thing_id, _date_in(payload.at))

    async def handle_correct_fact(self, data: dict):
        payload = CorrectFactPayload(**data)
        world = self._require_world()
        dates = {
            key: _date_in(getattr(payload, key))
            for key in ("valid_from", "valid_until")
            if key in payload.model_fields_set
        }
        self._require_fact_of(world, payload.thing_id, payload.fact_id)
        text = payload.text
        if text is not None:
            text = self._linked(
                world,
                payload.thing_id,
                text,
                payload.picks,
                _date_in(payload.valid_from) or _date_in(payload.at),
                payload.new_names,
                payload.spans,
            )
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(
                payload.fact_id,
                text=text,
                category=payload.category,
                **dates,
            )
        self._edited("correct_fact", payload.thing_id, _date_in(payload.at))

    async def handle_repoint_ref(self, data: dict):
        """Point one reference of an own fact (its `occurrence`-th, in the
        raw text) at `to_id`, keeping its words; nothing else in the fact
        changes. Answers like `correct_fact`."""

        payload = RepointRefPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        fact = self._require_fact_of(world, payload.thing_id, payload.fact_id)
        view = world.view(at)
        if view.thing(payload.to_id) is None:
            raise KeyError(f"no such thing: {payload.to_id}")
        if payload.to_id == payload.thing_id:
            raise ValueError("a fact can't reference its own thing")
        text = fact.text or ""
        old = next(
            (
                found
                for index, found in enumerate(REF_PATTERN.finditer(text))
                if index == payload.occurrence
            ),
            None,
        )
        rendered = (
            "".join(seg.text for seg in view.segments(old.group(0))) if old else ""
        )
        new_text = repoint_ref(text, payload.occurrence, payload.to_id, rendered)
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(payload.fact_id, text=new_text)
        self._edited("repoint_ref", payload.thing_id, at, prose=False)

    async def handle_end_fact(self, data: dict):
        payload = EndFactPayload(**data)
        world = self._require_world()
        self._require_fact_of(world, payload.thing_id, payload.fact_id)
        until = WorldDate.model_validate(payload.until)
        with world.revision(Source.manual()) as rev:
            rev.end_fact(payload.fact_id, until)
        self._edited("end_fact", payload.thing_id, _date_in(payload.at))

    async def handle_remove_fact(self, data: dict):
        payload = RemoveFactPayload(**data)
        world = self._require_world()
        self._require_fact_of(world, payload.thing_id, payload.fact_id)
        with world.revision(Source.manual()) as rev:
            rev.remove_fact(payload.fact_id)
        self._edited("remove_fact", payload.thing_id, _date_in(payload.at))

    async def handle_set_held_by(self, data: dict):
        """Set or clear who holds one of a thing's own facts as a belief
        (`spheres.with_held_by`): a sphere, a character or a being, or null
        for world truth (an explicit clear, so a beliefs drawer's statement
        can read plain too). One revision; nothing is written when the fact
        is already held so. Answers with the thing. Held-ness feeds
        description prose (ruling C3): prose is refreshed when the thing's
        prose reads the fact's category (not a sphere's statement or
        timeline fact, rulings P18, P19)."""

        payload = SetHeldByPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        self._require_fact_of(world, payload.thing_id, payload.fact_id)
        view = world.view()
        state = view.thing(payload.thing_id)
        found = view.fact(payload.fact_id)
        if state is None or found is None or found[0] != payload.thing_id:
            raise KeyError(f"no such fact on {payload.thing_id}: {payload.fact_id}")
        fact = found[1]
        holder_id = payload.holder_id
        if holder_id is not None:
            holder = view.thing(holder_id)
            if holder is None or holder.stub_ignored:
                raise KeyError(f"no such thing: {holder_id}")
            if not (spheres.is_sphere(holder) or holder.kind in ("character", "being")):
                raise ValueError(
                    "only a sphere, a character or a being can hold a belief"
                )
        if spheres.held_by(view, fact, state) == holder_id:
            self._edited("set_held_by", payload.thing_id, at, prose=False)
            return
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(
                payload.fact_id, origin=spheres.with_held_by(fact.origin, holder_id)
            )
        self._edited(
            "set_held_by",
            payload.thing_id,
            at,
            prose=not state.is_stub and prose_reads(state.kind, fact.category),
        )

    async def handle_pick_date(self, data: dict):
        """Settle a timeline disagreement (`repeats.disagreeing_dates`):
        keep `keep_fact_id`'s year, and end `drop_fact_id` at the world's
        now ("end") or remove it ("remove"), in one revision. Refused,
        writing nothing, unless the two are a disagreeing pair now
        (worked out again here, never taken from the client), at the
        world's repeat threshold. A dropped fact that has ended already is
        left as it is, and one that starts at or after now is removed
        instead of ended, each with a note. Answers `{keep_fact_id,
        drop_fact_id, mode, owner_id, notes}` (`owner_id` the dropped
        fact's entry), with `thing`, the payload of `thing_id` at `at`,
        when given. Prose is refreshed for the dropped fact's entry when
        its prose reads the fact's category."""

        payload = PickDatePayload(**data)
        world = self._require_world()
        view = world.view()
        keep, drop = payload.keep_fact_id, payload.drop_fact_id
        if keep == drop:
            raise ValueError("a fact can't disagree with itself")
        found = view.fact(drop)
        if view.fact(keep) is None or found is None:
            raise KeyError("no such fact")
        threshold = world.curation().repeat_threshold
        if not disagreeing_dates(view, [keep, drop], threshold):
            raise ValueError("those two facts don't disagree on the year")
        owner_id, fact = found
        notes: list[str] = []
        now = current_date(world)
        mode = payload.mode
        if mode == "end" and fact.valid_until is not None:
            if fact.valid_until.instant <= now.instant:
                notes.append("That fact has ended already, so it's left as it is")
                mode = "none"
        if mode == "end" and (
            fact.valid_from is not None and fact.valid_from.instant >= now.instant
        ):
            notes.append(
                "That fact starts at or after the world's now, so it's removed "
                "instead of ended"
            )
            mode = "remove"
        if mode != "none":
            with world.revision(Source.manual(note="picked a date")) as rev:
                if mode == "end":
                    rev.end_fact(drop, now)
                else:
                    rev.remove_fact(drop)
        reply: dict[str, Any] = {
            "keep_fact_id": keep,
            "drop_fact_id": drop,
            "mode": payload.mode,
            "owner_id": owner_id,
            "notes": notes,
        }
        if payload.thing_id is not None:
            reply["thing"] = self._thing_payload(
                world, payload.thing_id, _date_in(payload.at)
            )
        self._reply("pick_date", reply)
        owner = world.view().thing(owner_id)
        if (
            mode != "none"
            and owner is not None
            and not owner.is_stub
            and prose_reads(owner.kind, fact.category)
        ):
            self._schedule_prose(owner_id, None)

    # --- curation settings ------------------------------------------------

    async def handle_get_curation(self, data: dict):
        """The world's curation knobs (`World.curation`) and their
        defaults: `{settings, defaults}`."""

        self._reply("get_curation", _settings_out(self._require_world().curation()))

    async def handle_set_curation(self, data: dict):
        """Change the curation knobs given (`settings`, a part of
        `CurationSettings`; the rest are kept), validated by
        `CurationSettings` -- an unknown knob or one out of range is
        refused, writing nothing -- and answer as `get_curation` does. No
        rendered text changes: no prose is scheduled."""

        payload = SetCurationPayload(**data)
        world = self._require_world()
        settings = CurationSettings.model_validate(
            {**world.curation().model_dump(), **payload.settings}
        )
        world.set_curation(settings)
        self._reply("set_curation", _settings_out(settings))

    async def handle_set_field(self, data: dict):
        """Set one field. The fields with an action of their own, which
        guards them, are refused here: `part_of` (`set_part_of`), `ties`
        (`set_ties`) and `drawers` (`set_drawers`)."""

        payload = SetFieldPayload(**data)
        if payload.field in GUARDED_FIELDS:
            raise ValueError(
                f"{payload.field!r} is set with {GUARDED_FIELDS[payload.field]}"
            )
        world = self._require_world()
        with world.revision(Source.manual()) as rev:
            rev.set_field(
                payload.thing_id,
                payload.field,
                payload.value,
                _date_in(payload.valid_from),
            )
        self._edited(
            "set_field",
            payload.thing_id,
            _date_in(payload.at),
            prose=payload.field not in UNRENDERED_FIELDS,
        )

    async def handle_override_fact(self, data: dict):
        payload = OverrideFactPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        inherited_ids = {
            item.fact.fact_id
            for item in heritage.inherited(world.view(at), payload.thing_id)
        }
        if payload.overridden_fact_id not in inherited_ids:
            raise KeyError(
                f"{payload.thing_id} doesn't inherit fact {payload.overridden_fact_id}"
            )
        text = self._linked(
            world,
            payload.thing_id,
            payload.text,
            payload.picks,
            at,
            payload.new_names,
            payload.spans,
        )
        with world.revision(Source.manual()) as rev:
            rev.add_fact(
                payload.thing_id,
                payload.category,
                text,
                overrides=[payload.overridden_fact_id],
            )
        self._edited("override_fact", payload.thing_id, at)

    async def handle_regenerate_prose(self, data: dict):
        payload = RegenerateProsePayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        if payload.section is not None:
            state = world.view(at).thing(payload.id)
            if state is None:
                raise KeyError(f"no such thing: {payload.id}")
            if payload.section not in prose_gen.sections_for(state.kind):
                raise ValueError(
                    f"a {state.kind} has no {payload.section!r} prose section"
                )
        self._schedule_prose(payload.id, at, regenerate=True, section=payload.section)

    # --- scenes -----------------------------------------------------------

    async def handle_match_names(self, data: dict):
        payload = MatchNamesPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        matches = match_names(world, payload.text, at)
        unknown = unknown_proper_phrases(world.view(at), payload.text)
        self._reply(
            "match_names",
            {
                "text": payload.text,
                # echoed, so the screen can tell which lookup this answers
                "at": payload.at,
                "matches": [m.model_dump() for m in matches],
                "unknown": [u.model_dump() for u in unknown],
            },
        )

    async def handle_plan_scene(self, data: dict):
        payload = PlanScenePayload(**data)
        world = self._require_world()
        fixed = self._fixed_setup()
        client = self._client() if fixed is None else None
        planning = plan_scene(
            world,
            payload.prompt,
            payload.picks,
            payload.player,
            _date_in(payload.start),
            client,
            reply=fixed,
            new_names=payload.new_names,
        )
        self._spawn(
            self._planned(world, planning) if fixed is not None else planning,
            self.create_task_done_callback(
                "plan_scene",
                "plan_failed",
                "Error planning a world scene",
                success_data=lambda setup: self._setup_out(world, setup),
            ),
        )

    async def handle_start_scene(self, data: dict):
        payload = StartScenePayload(**data)
        world = self._require_world()
        client = None if os.environ.get(FIXED_SETUP_ENV) else self._client()

        def started(scene_id: str) -> dict:
            record = world.scenes().get(scene_id)
            assert record is not None
            return {
                "scene_id": scene_id,
                "target": world_target(str(world.path), scene_id),
                "scene": self._scene_out(world, record),
            }

        self._spawn(
            start_scene(world, payload.setup, client),
            self.create_task_done_callback(
                "start_scene",
                "start_failed",
                "Error starting a world scene",
                success_data=started,
            ),
        )

    async def handle_list_scenes(self, data: dict):
        world = self._require_world()
        scenes = [self._scene_out(world, record) for record in world.scenes().list()]
        self._reply("list_scenes", {"scenes": scenes})

    async def handle_continue_scene(self, data: dict):
        """Plan the scene after `scene_id`. If that's the loaded scene, it's
        saved first, so the summary covers what hasn't been saved yet."""

        payload = ContinueScenePayload(**data)
        world = self._require_world()
        scene = self._loaded_scene(world, payload.scene_id)
        if scene is not None:
            save_world_scene(scene)
        fixed = self._fixed_setup()
        client = self._client() if fixed is None else None
        planning = continue_setup(
            world, payload.scene_id, payload.goal_prompt, client, reply=fixed
        )
        self._spawn(
            self._planned(world, planning) if fixed is not None else planning,
            self.create_task_done_callback(
                "continue_scene",
                "continue_failed",
                "Error continuing a world scene",
                success_data=lambda setup: self._setup_out(world, setup),
            ),
        )

    async def handle_reposition_scene(self, data: dict):
        """Move a scene's start date. In the slice nothing from a scene has
        reached the world yet, so only the start changes; the messages move
        with it. If the scene is the one loaded, its characters are rebuilt
        for the new date and its status sent, so open character sheets
        follow. The scene's world characters then get their prose for the
        new start in the background; the loaded scene is rebuilt again once
        that's done."""

        payload = RepositionScenePayload(**data)
        world = self._require_world()
        start = WorldDate.model_validate(payload.start)
        store = world.scenes()
        store.update(payload.scene_id, start=start)
        record = store.get(payload.scene_id)
        assert record is not None

        scene = self._loaded_scene(world, payload.scene_id)
        if scene is not None:
            await self._refresh_loaded(scene)

        prose_tasks = [
            task
            for task in (
                self._schedule_prose(thing_id, start)
                for thing_id in self._world_characters(record)
            )
            if task is not None
        ]
        if scene is not None and prose_tasks:

            async def refresh_after_prose() -> None:
                await asyncio.gather(*prose_tasks, return_exceptions=True)
                if self._loaded_scene(world, payload.scene_id) is scene:
                    await self._refresh_loaded(scene)

            self._spawn(refresh_after_prose(), self._log_failure)

        self._reply("reposition_scene", self._scene_out(world, record))

    def _loaded_scene(self, world: World, scene_id: str) -> Any:
        """The handler's scene if it's world scene `scene_id` of `world`."""

        scene = getattr(self.websocket_handler, "scene", None)
        ref = getattr(scene, "world_ref", None)
        if (
            ref is not None
            and getattr(scene, "world_context", None) is not None
            and ref.scene_id == scene_id
            and Path(ref.world_path).resolve() == world.path.resolve()
        ):
            return scene
        return None

    async def _refresh_loaded(self, scene: Any) -> None:
        """Rebuild a loaded world scene's characters from its (re-read)
        record and send its status."""

        context = scene.world_context
        context.record = context.world.scenes().get(context.record.id)
        await context.refresh_characters(scene)
        scene.emit_status()

    @staticmethod
    def _world_characters(record: SceneRecord) -> list[str]:
        """The world things a scene plays: its player and its characters."""

        thing_ids = [record.player_thing_id] if record.player_thing_id else []
        for entry in record.state.get("characters") or []:
            if isinstance(entry, dict) and entry.get("thing_id"):
                thing_ids.append(entry["thing_id"])
        return list(dict.fromkeys(thing_ids))

    @staticmethod
    def _log_failure(task: asyncio.Task[Any]) -> None:
        if not task.cancelled() and task.exception() is not None:
            log.error("worlds.background_failed", error=str(task.exception()))
