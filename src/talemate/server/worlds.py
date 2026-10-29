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
  marker; ignored stubs left out; each with `filed_in`, the live
  entries it's filed in now, for the World tab's list; a being with
  its `existence`, so the scene pickers offer only real ones),
  `get_thing {id, at}`. A thing's payload
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
- Curation (curation spec): each own and inherited fact row carries
  `summary` (whether it's the entry's summary fact, `entries.summary_fact`,
  which the page shows first) and
  `held_by`, `{id, name}` of the entry that holds it as a belief
  (`entries.held_by`: a marked holder, or the owner of a `belief` fact),
  or `null`. Every kind's payload has `entry_timeline`
  (`world.timelines.entry_timeline` at the world's `timeline_reach`,
  disagreements worked out at its `date_threshold`, ruling C31): `[{fact_id, owner_id, owner_name, date,
  until, segments, here, disagrees_with}]` in date order -- its own
  dated facts and the lines it gathers from what's filed in it (`here` false,
  `owner_*` whose they are); `until` is set once the fact has ended (the
  screen shows "900–1010"), and a held line's `segments` read "<Holder>
  holds that ..." (`worldplay.held`), the holder linked.
  `set_held_by {thing_id, fact_id, holder_id|null, at}` sets or clears
  one own fact's holder (any live entry) in one revision (null makes it
  world truth, also for a `belief` fact) and answers with the thing; held-ness feeds
  description prose (ruling C3), so prose is refreshed when the thing's
  prose reads the fact's category. `pick_date {keep_fact_id,
  drop_fact_id, mode: "end"|"remove", thing_id?, at?}` settles a
  timeline disagreement: refused unless the two disagree now
  (`repeats.disagreeing_dates`, worked out again, never the client's
  word; an ended fact disagrees with nothing, ruling C22); "end" ends the dropped fact at the world's now, "remove" removes
  it, in one revision; answers `{keep_fact_id, drop_fact_id, mode,
  owner_id, notes, thing?}` and refreshes the dropped fact's entry's
  prose as an edit would. `get_curation` and `set_curation {settings}`
  (a part of `CurationSettings`, the rest kept; unknown or out of range
  refused) answer `{settings, defaults}`.
  A draft's `preview` (below) is the preview's dump plus names for
  display: `held_by_name` on each fact and elsewhere fact, `from_name`
  on each `move_here` row. Everything curation and filing add is in the
  dump: facts' `ticked`, `repeat_of`, `held_by`; `elsewhere`
  (`target_id`, `target_name`, `new`, `category`, `text`, `since`,
  `held_by`, `ticked`, `repeat_of`, `replaces_repeat`); `same_as` and
  `verdict` (with its `why`); `new_names` (with `tag`, `filing`,
  `same_as`, `same_target_id`); `tag`, `hint`, `filings` ("In"),
  `file_into`, `move_here`. `accept_preview` takes the owner's edits to
  all of it back, validated by the preview models and checked again on
  the server (ruling F13: "In" and "File into this" rows for a live
  target and no cycle, a `within` that sits in its target, exceptions
  departing from what the target holds; "Could move here" recomputed; a
  "Move existing here" row, `move_here` with `repeat`, and a "Keep new"
  fact or elsewhere fact (P8: a `replaces_repeat`, the fact it repeats
  removed in the accept's revision, on its own page or, for an
  elsewhere row, on its target), kept only when a version of the draft
  this session holds says one of its matching rows (own facts for own
  facts, elsewhere rows for elsewhere rows) repeats that fact; the
  `selected_names` kept only as the server's copy recorded them), and
  answers `notes`. Accepted
  under another name than the one its prose was written under (the
  owner renamed the draft, P7), its prose is cached stale. An "In" row
  may name a `new_name` instead of a `target_id` (the owner's "+ in..."
  on a name the world hasn't): accept makes that stub and files the entry
  in it, in the one revision. A fact's `until` (the owner's "End this")
  is written as its end. It schedules prose for each entry the world has
  whose prose reads what it took (an elsewhere fact, a fact moved off
  it, a fact "Keep new" removed).
- Stubs: `make_stub {thing_id, fact_id, text, kind}` makes a stub named
  `text` (or reuses the thing that already has that name, reviving an
  ignored stub) and links that phrase in the fact (its first plain
  occurrence, nothing else), answering like `correct_fact`. `list_stubs {include_ignored}` answers `{stubs: [{id, name, kind, tag, first_mentioned:
  {thing_id, name}, mentions, ignored}]}`. `ignore_stub {id, ignored}` and
  `change_stub_kind {id, kind}` answer with the stub's payload.
  `stub_suggestion {id}` answers `{id, prompt, context}`: the create box's
  starting prompt for the stub and the mention context its expansion gets.
  `change_stub_kind` adds `notes`, naming each field the new kind lacks
  that was dropped with its value.
  `repoint_stub {stub_id, target_id, mode?, use_name?}` (`talemate.worldplay.repoint`;
  `mode` "link" teaches the target no names, ruling H2)
  points everything naming the stub at the target (an entry, or another
  live stub) -- fact links, fields, filings, the stub's own facts and
  filings -- teaches the target its names (`use_name`, one of the
  target's names, rewrites the links' words to it instead, its article
  fitted to the text, and teaches only the stub's own names) and removes
  the stub, in one revision. It answers `{stub_id, stub_name, target, links, aka_added,
  facts_moved, notes}` (`target` the target's payload; `notes` what didn't
  carry over as the stub had it). Refused, writing nothing: the stub
  itself, a deleted thing or an ignored stub as the target, and a use the
  target can't take (a scene's, a field of another kind, a loop of
  parents or filings, a mix's parents naming it twice, its own). Prose is refreshed where its input
  changed: the target's for facts or rendered fields it took, another
  thing's for a rendered field rewritten.
  `copy_fact {fact_id, target_id}` ("Copy to...", `repoint.copy_facts`
  with `keep`) copies one fact onto another entry in one revision, the
  original kept, and answers `{fact_id, target, notes}` like `move_fact`.
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
  Re-point is, and for a thing into itself, a thing of another kind, an
  entry into a stub, and a stale preview. Prose is
  refreshed for the into-side and each rendered field rewritten.
- Heritage: `override_fact {thing_id, overridden_fact_id, text, category,
  at}` adds an own fact that overrides an inherited one and answers like
  `add_fact`. `list_heritage` answers `{things: [{id, kind, name,
  species_ids}]}`, every species, race and mix, for the heritage picker.
  `find_mix {parents: [a, b]}` answers `{parents, mix_id}`, the mix of
  those two parents in either order (`null` if there's none yet).
- Create, as drafts: `preview_thing {kind, prompt, fields, stub_id,
  picks, new_names, hint, draft_key?}` runs in the background and answers
  `preview_thing` with the draft (or `preview_failed {message}`); it
  writes nothing. `stub_id` expands that stub, `picks` maps a name
  written in the prompt to the thing the owner matched it to,
  `new_names` are written names the owner treats as new, and `hint` a
  prompt hint's name. The draft is the page the entry will be (the thing
  payload's shape, `draft: true`, `id` the stub's or null; its own facts
  and "In" rows marked `draft: true` with their `ticked`), plus `preview`
  (the data `accept_preview` takes), `draft_key`, `version` (1-based) and
  `versions: [{version, name, prompt}]`. A session keeps up to
  `DRAFT_VERSIONS` (5) versions per draft key, in memory: `stub:<id>` for
  a stub's expansion, else `new:<kind>:<name key>`; Regenerate and Edit
  prompt send the draft's key back, so a new version joins it whatever
  it's named. At most `DRAFTS_KEPT` (20) drafts are kept, the least
  recently used forgotten first. `use_version {draft_key, version}`
  answers that version as `preview_thing` does and makes it the current
  one; `discard_preview {draft_key}` drops every version, writing
  nothing, and answers `{draft_key}`; `draft_render {draft_key, seq?,
  preview}` (P6) answers `{draft_key, seq, facts: [{index, text,
  segments}], prose_segments, entry_timeline, numbers}`: the owner's copy linked
  as accept will link it, writing nothing; a regeneration whose draft is
  discarded before its reply comes is dropped, unanswered. Opening
  another world drops them all. The client must always send `draft_key`
  with `accept_preview`, or the draft lingers until forgotten.
  `accept_preview {preview, into_stub, same_target_id, draft_key?}`
  writes it (into the stub `into_stub`, or onto the entry
  `same_target_id`, "Is this X?", if given), storing its `hint` on the
  entry, drops the draft's versions, and answers with the thing and
  `notes` (what was left out, as an elsewhere fact whose target was
  deleted since the preview); the prose of what else it changed is
  scheduled. For the browser
  tests only, `TALEMATE_TEST_FIXED_PREVIEW` names a JSON file (`{name,
  facts, prose, fields?, tag?, aka?, in?, file_into?, names?}`) that previews are
  answered from instead of the model (listing what the request's fields
  inherit, and for a `stub_id` its kind, name and mention context, as a
  real preview does). The file's facts may name a `held_by` holder, and
  it may hold `elsewhere` (`[{entry, text, since?, held_by?}]`), each
  read through the real parsers (`create.holder_named`,
  `parse_elsewhere`, `parse_in`, `parse_file_into`); "Could move here" is
  found by code as the real one's. The entry's
  `same_as` is offered as the real preview's is (`create.same_offers`),
  and the file's `verdict` (`{verdict, why}`) stands in for the model's
  hint on the top candidate when both sides have facts.
- Edits: `add_fact`, `correct_fact`, `end_fact`, `remove_fact` and
  `set_field` (never filings, the old structure or the tag:
  `GUARDED_FIELDS`) each write one revision, answer with the thing, then start a
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
  `repoint_ref {thing_id, fact_id, occurrence, to_id, mode?, use_name?,
  at}` (`mode`, `LinkMode`: "name" by default; "link" keeps the words and
  teaches nothing, ruling H2)
  points one reference of a fact (the `occurrence`-th in its text) at
  another thing, keeping its words, and teaches the target the link's
  words (unless another entry goes by them) and, when it was a stub's last
  reference, the stub's names, as other names (`repoint.learn_names`), in
  one revision; with `use_name` ("Rename to...", P4: one of the target's
  names) that name takes the words' place, its article fitted, and only
  the stub's names are taught. It answers like `correct_fact`, plus
  `aka_added`.
- Selected words (`start`/`end` index a fact's `rendered` text, in
  UTF-16 code units, ruling F18; a held fact's "<Holder> holds that ..."
  prefix isn't in `rendered`, and a link to an ignored stub shown plain
  is still a link, so a selection over it is refused; a link to a deleted
  thing counts as its words, P5, and is replaced by them where the
  selection touches it, in the same revision):
  `make_stub_from_text {fact_id, start, end, kind, tag?, filing?:
  {target_id, role}, at}` makes a stub of the words (or uses the entry
  of that name), filed as `filing` says, and links them, in one
  revision, answering with the fact's entry plus `stub_id`;
  `link_text {fact_id, start, end, target_id, mode?, use_name?, at}`
  links them to an entry: as written ("link", the default, ruling H2),
  teaching it the words as another name too ("name", P4), or writing one
  of its names, `use_name`, in their place ("rename"); it answers with
  the fact's entry plus `aka_added`. A selection that cuts through or
  takes in a link is refused. On a draft, the words are recorded in its
  `selected_names` (ruling F26): only those link where they're written
  without a capital; a link's words join its `pick_names`, taught at
  accept, and `use_name` is refused.
- Prompt additions: `add_facts {thing_id, prompt}` and `add_event
  {thing_id, prompt, year}` (`worldplay.facts`) run in the background and
  answer `{thing_id, draft, facts}` (or `add_facts_failed` /
  `add_event_failed`), writing nothing; the draft's `new_names` are the
  names its facts use that the world hasn't (ruling H8: ticked rows, each
  `{name, kind, tag, filing, same_as, same_target_id, ticked}`).
  `accept_facts {draft, at}` writes the ticked facts, and a stub for each
  ticked new name they still use, linked, in one revision and answers
  with the entry plus `fact_ids`. With `draft_key` (a draft page) the
  facts are the page draft's own nested fact draft (key `nested:<page
  draft key>`, `thing_id: null`, linked as the page draft would link
  them), answered with `nested_in: <page draft key>`; a result that
  comes after another version of the page draft became current is held
  nowhere and answers `add_facts_failed`/`add_event_failed` with
  `{draft_key: <page draft key>, stale: true}`; one asked while a
  `preview_thing` for the page draft is still out answers
  `add_facts_failed`/`add_event_failed` ("wait for the draft to finish
  regenerating", `{draft_key}`), and a `preview_thing` reply landing on
  a page draft whose nested draft is held answers `preview_failed`
  ("write or discard the added facts first", `{draft_key}`), adding no
  version. `write_nested_facts
  {draft_key: <page draft key>, draft}` checks its repeat choices against
  the nested draft's held versions, puts its ticked facts and new names
  (and kept "Move existing here" rows) into a copy of the page draft's
  current version, held as a new version, drops the nested draft and
  answers with the page draft plus `notes`, writing nothing to the
  world. While a nested draft is held, or its ask is still out,
  `accept_preview`, `use_version` and `preview_thing` with its page
  draft's key are refused ("write or discard the added facts first");
  `discard_preview` drops it too;
  `accept_facts` refuses a nested draft.
  `TALEMATE_TEST_FIXED_FACTS` (browser tests) names a file
  holding the model's reply.
- Small drafts (`server.world_drafts`): a fact or event draft (key
  `facts:<thing_id>`), a group-add draft (key `group:<thing_id>:<tag
  or "">`) and a page draft's nested fact draft (key `nested:<page draft
  key>`) are held on the server, up to `DRAFT_VERSIONS` versions each,
  at most `SMALL_DRAFTS_KEPT` slots (the least recently used forgotten
  first). `add_facts`/`add_event` and `group_add` start a
  fresh slot (its versions gone), or, with `regenerate: true`, add a
  version to the slot; their replies gain `draft_key`, `version`
  (1-based) and `versions` (`[{version, prompt, year}]` for facts,
  `[{version, prompt}]` for a group). Only the latest ask for a key
  answers: one whose slot was discarded, replaced or asked again while
  it was out is dropped, unanswered (failures too).
  `use_small_version {draft_key, version}` answers `use_small_version`
  with that version as the slot's own reply would have it (a fact draft
  linked against the world as it is now), plus `kind` ("facts",
  "group", "nested"); `discard_small_draft {draft_key}` drops the slot,
  writing nothing, and answers `{draft_key}`. `accept_facts` and
  `accept_group_add` take an optional `draft_key`, the slot they drop
  once written. Opening another world drops them all.
- Filing and tags (`talemate.world.filing`): the thing payload has
  `tag`, `hint` (the prompt hint it was written with), `in: [{target_id,
  target_name, role, show_under, since, until, within_id, within_name,
  exceptions: [{fact_id, segments}]}]` (every filing, ended ones too, a target gone
  hidden), `connected: [{tag, heading, synopsis, rows: [{id, name, stub,
  believed, line_segments, role, show_under, since, until}]}]` (what's
  filed in it, grouped by the group each filing shows under, else the
  entry's tag; `believed` marks a believed or undecided being, shown
  but not one of the people, ruling F24; `synopsis` is `groups.cached_synopsis` -- a fresh cached one, read
  with no model call, null when there's none cached or it's gone stale --
  and only at the latest telling) and `mentioned_in: [{id, name}]`.
  `add_filing {thing_id, target_id|new_name, kind?, tag?, role, since,
  until, within, show_under?, at}`, `edit_filing {thing_id, target_id,
  role?, since?, until?, within?, show_under?, at}` (an `until` ends it;
  `show_under` is a tag, the group it shows under on the target's page) and `remove_filing {thing_id,
  target_id, at}` (its exceptions go with it, named in its `notes`) each
  write one revision and answer with the thing; `add_exception {character_id, target_id, text,
  rejects, ...}` adds a "but..." to a filing. `set_tag {thing_id, tag}`
  answers with the thing; `list_tags` answers `{tags: [{tag, heading,
  count}]}` (a filing's `show_under` counts) and `list_roles` `{roles:
  [{role, count}]}`, the roles in use; `rename_tag {old, new}` and `merge_tag {from, into}` retag
  every entry in one revision and answer `{old, new | from, into,
  changed, tags}`. Filings and tags are no prose input: none is
  scheduled.
- Groups (`talemate.worldplay.groups`): `group_synopsis {thing_id, tag,
  force?}` (`tag` null for the untagged "Other" group) asks the model
  for the group's synopsis, cached, in the background (skipping the
  cache with `force`), and answers `group_synopsis {thing_id, tag,
  synopsis}` or `group_synopsis_failed` (an unusable reply, never an
  empty synopsis cached as a real one); "" for an empty group, or with
  synopses off (a probe fallback). `group_add {thing_id, tag, prompt,
  show_under?}` (`tag` null is the page's own top-level "+ Add", no tag
  preset; `show_under` true for a Connected group that is
  `via_show_under`, ruling H5: each row keeps its own tag and shows
  under `tag`) drafts
  up to 3 new entries from the owner's prompt, in the background,
  writing nothing, and answers `group_add {thing_id, tag, rows}` (each
  row `{name, kind, tag, line, ticked, show_under}`) or
  `group_add_failed`.
  `accept_group_add {thing_id, rows}` writes the ticked rows, each filed
  in `thing_id` with its own tag, its line its first fact and (unless it
  already has one) its summary, in one revision, checked again rather
  than trusted from the client -- a row whose name the world already
  has reuses that entry rather than duplicating it, and only a
  genuinely new one becomes a stub -- and answers the thing plus
  `thing_ids` (each kept row's resolved entry id, new or reused, in
  order) and `notes` (a row whose filing the store refused -- a cycle, a
  target gone since -- noted rather than silently dropped; its fact is
  still written; and a reused entry, which keeps its own tag, with the
  group it's listed under). `TALEMATE_TEST_FIXED_GROUP_SYNOPSIS`/`TALEMATE_TEST_FIXED_GROUP_ADD`
  (browser tests) each name a file holding the model's reply.
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
  A merge asks no model, so it has no fixed reply.

Dates go over the wire as `{"instant", "precision", "label"}`, the label
formatted with the world's calendar; `label` is ignored on the way in.
"""

import asyncio
import hashlib
import json
import os
from collections import Counter, OrderedDict
from collections.abc import Callable, Collection, Coroutine, Sequence
from pathlib import Path
from typing import Any, Literal, cast

import pydantic
import structlog

import talemate.instance as instance
from talemate.path import WORLDS_DIR
from talemate.server.websocket_plugin import Plugin
from talemate.server.world_drafts import (
    DRAFT_VERSIONS,
    SmallDrafts,
    facts_key,
    group_key,
    nested_key,
    page_key,
)
from talemate.world import entries, heritage
from talemate.world.calendar import Calendar
from talemate.world.curation import CurationSettings
from talemate.world.dates import WorldDate
from talemate.world.filing import (
    FIELD_ROLES,
    Filing,
    FilingIndex,
    connected,
    filed_in,
    filings_of,
    mentioned_in,
    roles_in_use,
    stored_filings,
    tag_heading,
    tag_of,
    tags_in_use,
)
from talemate.world.kinds import (
    HERITAGE_KINDS,
    KINDS,
    get_kind,
    normalise_tag,
)
from talemate.world.names import (
    Aliases,
    alias_table,
    find_names,
    find_own_names,
    own_alias_table,
    unknown_proper_phrases,
)
from talemate.world.prose import UNRENDERED_FIELDS
from talemate.world.refs import REF_PATTERN, ref, scrub_emphasis
from talemate.world.repeats import disagreeing_dates
from talemate.world.scenes import SceneRecord, scene_end
from talemate.languages.check import check_language, repair_note
from talemate.languages.entry import fields_of, language_of, used_words, word_uses
from talemate.languages.entry import languages as all_languages
from talemate.languages.lookup import (
    default_language,
    languages_for,
    languages_for_scene,
)
from talemate.languages.brief import write_brief
from talemate.languages.related import related_entries
from talemate.languages.completeness import completeness as completeness_of
from talemate.languages.making import (
    MakeError,
    MakeRequest,
    MakeSettings,
    ask_questions,
    effective_size,
    make_language,
)
from talemate.languages.models import Language
from talemate.languages.naming import (
    NameInResult,
    add_word,
    apply_name_in,
    name_in,
    roll_names,
)
from talemate.languages.naming import define as define_names
from talemate.languages.importer import apply_import, export_language, preview_import
from talemate.world.store import Revision, Source, World
from talemate.world.timeline import TimelineEntry
from talemate.world.timelines import TimelineLine, entry_timeline
from talemate.world.view import FactState, Segment, ThingState, WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.characters import age_in_years
from talemate.worldplay.create import (
    CREATE_KINDS,
    CreatePreview,
    ElsewhereFact,
    FileIntoRow,
    MoveHereFact,
    PreviewException,
    PreviewFact,
    PreviewInherited,
    accept_preview,
    clean_tag,
    current_date,
    drafted,
    entry_names,
    file_by_role,
    filing_exception_fact,
    filings_since,
    flag_elsewhere_repeats,
    holder_named,
    listed_names,
    matching_stub,
    move_here_rows,
    name_filings,
    naming_facts,
    offer_same,
    owner_filings,
    parse_elsewhere,
    parse_file_into,
    parse_in,
    preview_inherited,
    preview_thing,
    prose_reads,
    same_offers,
)
from talemate.worldplay.create import _new_names as listed_stub_names
from talemate.worldplay.decide import Verdict
from talemate.worldplay.facts import (
    DraftAddition,
    DraftName,
    FactDraft,
    accept_facts,
    draft_facts,
    draft_facts_for,
)
from talemate.worldplay.groups import (
    GroupAddDraft,
    GroupAddRow,
    accept_group_add,
    cached_synopsis,
    group_add,
    group_synopsis,
)
from talemate.worldplay.held import held_text
from talemate.worldplay.links import (
    LinkSpan,
    NameFiling,
    NewName,
    link_phrase,
    link_text,
    make_stubs,
    name_key,
    repoint_ref,
)
from talemate.worldplay.mentions import (
    gather_mentions,
    mention_context,
    mentions,
    suggested_prompt,
)
from talemate.worldplay.persistence import save_world_scene, world_target
from talemate.worldplay.references import thing_references
from talemate.worldplay.merge import (
    MergePreview,
    accept_merge,
    preview_merge,
    repoint_overrides,
)
from talemate.worldplay.repoint import (
    copy_facts,
    learn_names,
    move_fact,
    renamed_words,
    repoint_stub,
    retitle,
    target_name,
)
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

# the drafts a session keeps, the least recently used forgotten first
DRAFTS_KEPT = 20

# browser tests only: a JSON file holding the model's reply `add_facts`
# and `add_event` read through their real parsing instead of asking it
FIXED_FACTS_ENV = "TALEMATE_TEST_FIXED_FACTS"

# browser tests only: a JSON file holding the model's reply `group_synopsis`
# and `group_add` read through their real parsing instead of asking it
FIXED_GROUP_SYNOPSIS_ENV = "TALEMATE_TEST_FIXED_GROUP_SYNOPSIS"
FIXED_GROUP_ADD_ENV = "TALEMATE_TEST_FIXED_GROUP_ADD"
# browser tests: the model's reply to every language naming call
# (definitions and picks, `languages.naming`)
FIXED_LANGUAGE_ENV = "TALEMATE_TEST_FIXED_LANGUAGE"
# one language job at a time (a make, a change or a fill)
BUSY = "Something else is being made or changed; wait for it or cancel it"
LANGUAGE_GONE = "The language this was for is gone"
# the browser tests' stand-in for Claude Code (a fake `claude` script)
CLAUDE_COMMAND_ENV = "TALEMATE_TEST_CLAUDE_COMMAND"


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
    # the prompt hint the owner picked (`create.hint_names`), if any
    hint: str | None = None
    # the draft this generation is a new version of (`_draft_key`): sent
    # back from an earlier reply by Regenerate or Edit prompt
    draft_key: str | None = None


class AcceptPreviewPayload(pydantic.BaseModel):
    preview: CreatePreview
    # "fill the stub instead": the stub a preview made without one fills
    into_stub: str | None = None
    # "Is this X?" -- yes: the entry the preview's material goes onto
    same_target_id: str | None = None
    # the draft accepted: its versions are dropped once it's written
    draft_key: str | None = None


class DraftKeyPayload(pydantic.BaseModel):
    draft_key: str


class DraftRenderPayload(DraftKeyPayload):
    # the draft as the owner left it: the client's copy, edits and all
    preview: CreatePreview
    # sent back as it came, so the client keeps the newest reply only
    seq: int | None = None


class UseVersionPayload(DraftKeyPayload):
    # 1-based, as the reply's `versions` number them
    version: int


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


# how a link takes its words (P4, ruling H2): "link" keeps them and teaches
# nothing, "name" keeps them and teaches them as another name, "rename"
# writes one of the target's names (`use_name`) in their place, "retitle"
# (polish 4) keeps them and makes them the target's main name, its old one
# an other name (`repoint.retitle`)
LinkMode = Literal["link", "name", "rename", "retitle"]


def _aka_names(state: ThingState) -> list[str]:
    """A thing's other names, the names alone, in their order."""

    return [
        str(entry.get("name"))
        for entry in (state.fields.get("aka") or [])
        if isinstance(entry, dict) and entry.get("name")
    ]


def _year_of(value: object) -> int | None:
    """A stored date's year (a `WorldDate` or its dumped dict), or None."""

    if value is None:
        return None
    try:
        return WorldDate.model_validate(value).to_datetime().year
    except (TypeError, ValueError):
        return None


def _span_out(state: ThingState) -> dict[str, int | None] | None:
    """When an entry is in the world, as years (polish 5, `when:`): a
    character's or being's birth on, an event's span; None for a kind
    with no span of its own (or a being with no birth)."""

    if state.kind in ("character", "being"):
        born = _year_of(state.fields.get("born"))
        if state.kind == "being" and born is None:
            return None
        return {"from": born, "until": None}
    if state.kind == "event":
        return {
            "from": _year_of(state.fields.get("when")),
            "until": _year_of(state.fields.get("until")),
        }
    return None


def _link_mode(
    mode: LinkMode | None, use_name: str | None, default: LinkMode
) -> LinkMode:
    """The mode a link payload asks for: `mode`, else "rename" when it
    names a `use_name`, else `default`; a rename needs a name and only a
    rename takes one (`ValueError`)."""

    chosen: LinkMode = mode or ("rename" if use_name is not None else default)
    if chosen == "rename" and use_name is None:
        raise ValueError("a rename needs one of the target's names")
    if chosen != "rename" and use_name is not None:
        raise ValueError(f"only a rename writes a name, not {chosen!r}")
    return chosen


class RepointRefPayload(_ThingEdit):
    fact_id: str
    # which reference of the fact's text, 0-based, in order
    occurrence: int
    to_id: str
    # how the link takes its words (`LinkMode`); unset, "name" (or
    # "rename" with a `use_name`)
    mode: LinkMode | None = None
    # "Rename to...": one of the target's names for the link's words
    use_name: str | None = None


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
    # how the links take their words (`LinkMode`); unset, "name" (or
    # "rename" with a `use_name`): a stub's words are a name
    mode: LinkMode | None = None
    # the hard re-point: one of the target's names for every link's words
    use_name: str | None = None


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
    # the entry that holds the fact as a belief; null makes it world
    # truth (also for a `belief` fact).
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


class LanguageQuestionsPayload(pydantic.BaseModel):
    """What the owner asked for, before a language is made."""

    text: str


class LanguageTextPayload(pydantic.BaseModel):
    """A language file's text (a file or a pasted reply), for a new
    language or a new version of `target_id`."""

    text: str
    target_id: str | None = None
    at: dict | None = None
    # for a change: the version it was briefed on (merged onto the
    # language as it is now, keeping the owner's edits)
    base: str | None = None


class LanguageSamplesPayload(pydantic.BaseModel):
    thing_id: str
    seed: int = 0


class LanguageNamesPayload(pydantic.BaseModel):
    language_id: str
    # asked from a world scene's message box: the scene's world
    scene: bool = False
    kind: str = "place"
    count: int = 4
    seed: int | None = None
    # what the names are for, given to the definitions
    context: str = ""
    exclude: list[str] = pydantic.Field(default_factory=list)


class LanguageWordPayload(pydantic.BaseModel):
    language_id: str
    # asked from a world scene's message box: the scene's world
    scene: bool = False
    word: str
    meaning: str = ""
    context: str = ""
    at: dict | None = None


class LanguageNameInPayload(_ThingEdit):
    language_id: str
    result: dict | None = None


class SetFieldPayload(_ThingEdit):
    field: str
    value: Any
    valid_from: dict | None = None


# the fields `set_field` never writes, each with what does: filings go
# through the filing actions alone (rulings F11, F14)
GUARDED_FIELDS: dict[str, str] = {
    "filings": "add_filing, edit_filing or remove_filing",
    "tag": "set_tag",
}


class AddFilingPayload(_ThingEdit):
    """File a thing in an entry the world has (`target_id`) or in a new
    stub named `new_name` (of `kind`, default lore, with `tag`), with a
    role, dates and, for a person, a part of the target it's `within`;
    `show_under`, the group it shows under on the target's page (a tag),
    else the entry's own tag."""

    target_id: str | None = None
    new_name: str | None = None
    kind: str | None = None
    tag: str | None = None
    role: str | None = None
    since: dict | None = None
    until: dict | None = None
    within: str | None = None
    show_under: str | None = None

    @pydantic.model_validator(mode="after")
    def _one_target(self) -> "AddFilingPayload":
        has_name = bool(self.new_name and self.new_name.strip())
        if (self.target_id is None) == (not has_name):
            raise ValueError("a filing goes into a target_id or a new_name")
        return self


class EditFilingPayload(_ThingEdit):
    """Change one filing (the one into `target_id`): only the keys sent
    change (`role`, `since`, `until`, `within`, `show_under`; null clears
    one). An `until` ends it ("End this"). Its exceptions are kept."""

    target_id: str
    role: str | None = None
    since: dict | None = None
    until: dict | None = None
    within: str | None = None
    show_under: str | None = None


class RemoveFilingPayload(_ThingEdit):
    target_id: str


class SetTagPayload(_ThingEdit):
    # null or blank clears it
    tag: str | None


class RenameTagPayload(pydantic.BaseModel):
    old: str
    new: str


class MergeTagPayload(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(populate_by_name=True)

    from_: str = pydantic.Field(alias="from")
    into: str


class GroupSynopsisPayload(pydantic.BaseModel):
    thing_id: str
    tag: str | None = None
    # ask the model again even if a fresh one is cached
    force: bool = False


class GroupAddPayload(pydantic.BaseModel):
    thing_id: str
    tag: str | None = None
    prompt: str
    # the group exists through its rows' `show_under` (Connected's
    # `via_show_under`, ruling H5)
    show_under: bool = False
    # add a version to the held draft rather than start it afresh
    regenerate: bool = False


class AcceptGroupAddPayload(pydantic.BaseModel):
    thing_id: str
    rows: list[GroupAddRow]
    # the small draft accepted: dropped once it's written
    draft_key: str | None = None


class AddFactsPayload(pydantic.BaseModel):
    """ "+ Add facts...": onto an entry the world has (`thing_id`), or into
    a draft (`draft_key`: its current version), exactly one of the two."""

    thing_id: str | None = None
    draft_key: str | None = None
    prompt: str
    at: dict | None = None
    # with `thing_id`: add a version to the held fact draft rather than
    # start it afresh
    regenerate: bool = False

    @pydantic.model_validator(mode="after")
    def _one(self) -> "AddFactsPayload":
        if (self.thing_id is None) == (self.draft_key is None):
            raise ValueError("facts are added to a thing_id or a draft_key")
        return self


class AddEventPayload(AddFactsPayload):
    # the year the event happened (a year of the world's calendar)
    year: int


class WriteNestedFactsPayload(pydantic.BaseModel):
    # the page draft whose nested fact draft is written into it
    draft_key: str
    # the nested draft, as the owner left it
    draft: FactDraft


class AcceptFactsPayload(pydantic.BaseModel):
    # `add_facts`' or `add_event`'s draft, as the owner left it
    draft: FactDraft
    at: dict | None = None
    # the small draft accepted: dropped once it's written
    draft_key: str | None = None


class _Selection(pydantic.BaseModel):
    """Selected words of a fact: an accepted one (`fact_id`) or a draft's
    (`draft_key` and the fact's `index` in its current version);
    `start`/`end` index its `rendered` text in UTF-16 code units (ruling
    F18), as the page counts them."""

    fact_id: str | None = None
    draft_key: str | None = None
    index: int | None = None
    start: int
    end: int
    at: dict | None = None

    @pydantic.model_validator(mode="after")
    def _one(self) -> "_Selection":
        drafted = self.draft_key is not None and self.index is not None
        if (self.fact_id is None) == (not drafted):
            raise ValueError("a selection is in a fact_id, or a draft_key's index")
        return self


class SelectionFiling(pydantic.BaseModel):
    target_id: str
    role: str | None = None


class MakeStubFromTextPayload(_Selection):
    kind: str
    tag: str | None = None
    filing: SelectionFiling | None = None


class LinkTextPayload(_Selection):
    target_id: str
    # how the link takes the words (`LinkMode`); unset, "link" (or
    # "rename" with a `use_name`): plain words never become a name unasked
    mode: LinkMode | None = None
    # "Rename to...": one of the target's names in the words' place
    use_name: str | None = None


class CopyFactPayload(pydantic.BaseModel):
    fact_id: str
    target_id: str


class ItemRef(pydantic.BaseModel):
    """What an exception departs from: an entry filed in the filing's
    target, or one of the target's facts (exactly one of the two)."""

    thing_id: str | None = None
    fact_id: str | None = None

    @pydantic.model_validator(mode="after")
    def _one(self) -> "ItemRef":
        if (self.thing_id is None) == (self.fact_id is None):
            raise ValueError("an item is a thing_id or a fact_id")
        return self


class AddExceptionPayload(pydantic.BaseModel):
    character_id: str
    # the entry the character is filed in
    target_id: str
    text: str
    # what it departs from; `None` departs from the entry as a whole
    rejects: ItemRef | None = None
    picks: dict[str, str] = pydantic.Field(default_factory=dict)
    new_names: list[str] = pydantic.Field(default_factory=list)
    spans: list[LinkSpan] = pydantic.Field(default_factory=list)
    at: dict | None = None


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


def _has_name_rules(state: ThingState) -> bool:
    """Whether a language entry can make names: a name rule that isn't
    for ordinary words (a description-only language has none)."""

    rules = state.fields.get("rules") or {}
    return any(g.get("use") != "words" for g in rules.get("generators") or [])


def _languages_page(view: WorldView, state: ThingState) -> dict:
    """A page's Languages section (languages 3a): its own rows, each named
    (None for a deleted language), the languages that apply to it (its own,
    or inherited through its filings) and, when inherited, where from."""

    own = []
    for row in state.fields.get("languages") or []:
        language = view.thing(row["language"])
        named = language is not None and language.kind == "language"
        own.append({**row, "name": language.fields.get("name") if named else None})
    rows = languages_for(view, state.id)
    source = rows[0].source_id if rows and rows[0].inherited else None
    return {
        "languages_own": own,
        "languages_view": [
            {**r.model_dump(), "source_name": view.name_of(r.source_id)} for r in rows
        ],
        "languages_source_name": view.name_of(source) if source else None,
    }


def _same_language(old: Language, new: Language) -> bool:
    """Whether importing `new` onto `old` would change nothing it stores
    (the name stays the entry's own either way)."""

    return fields_of(old) == fields_of(new)


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
    `matching_stub_id`.

    Read through the real parsers: a fact's `held_by` (a holder's name,
    `create.holder_named`); `elsewhere`, the model's `[{entry, text,
    since?, held_by?}]` (`create.parse_elsewhere`, repeats flagged, a new
    entry's row offered what it may be the same as); the file's `tag`
    (`create.clean_tag`), `in` and `file_into` (`[{entry, role}]`,
    `create.parse_in`, `parse_file_into`, unticked), after the owner's own
    filings from the fields (ticked, `create.owner_filings`); its `names`
    (`[{name, kind, tag, in}]`, `create.listed_names`, `name_filings`:
    each new name with its tag and the ticked filing its "in" gives, an
    existing entry whose "in" is this one offered under "File into
    this"), kept only as the facts use them, as the real ones; "Could move
    here" found by code as the real one's (`naming_facts`,
    `move_here_rows`) among where it's filed, what mentions the stub and
    the picks; and the entry's `same_as` (`create.same_offers`), with the
    file's `verdict` as the hint on the top candidate. Async so it runs
    through the same background task and reply path as the real one."""

    view = world.view()

    fixed = json.loads(path.read_text(encoding="utf-8"))
    fields = {**payload.fields, **fixed.get("fields", {})}
    kind, name = payload.kind, fixed["name"]

    def holder(held: str) -> str | None:
        return holder_named(view, held)

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
    # the file's "in" and "file_into", `[{entry, role}]`, read as the
    # model's are (unticked); "Could move here" found as the real one's
    own_keys = {name_key(name)}
    own_ids = {stub.id} if stub is not None else set()
    lookup = entry_names(view)
    # the owner's own filings (`filings`, an event's `place`...) are
    # ticked "In" rows, as the real preview makes them, then the file's
    filings = owner_filings(view, fields, kind)
    for row in parse_in(
        fixed.get("in") or [],
        view,
        own_keys=own_keys,
        own_ids=own_ids,
        prefer=[],
        lookup=lookup,
        calendar=calendar,
        now_year=now_year,
    ):
        if not any(r.target_id == row.target_id for r in filings):
            filings.append(row)
    # the file's names (`[{name, kind, tag, in}]`), read as the model's
    # are: each with its tag, and the filing its "in" gives (ticked); an
    # existing entry whose "in" is this one is a "File into this" row
    listed, names_into = name_filings(
        view,
        listed_names(fixed.get("names") or []),
        own_keys=own_keys,
        prefer=[],
        lookup=lookup,
    )
    new_names = listed_stub_names(
        view,
        listed,
        [fact.text for fact in facts],
        [name],
        list(payload.picks),
        payload.new_names,
    )
    file_into = parse_file_into(
        fixed.get("file_into") or [],
        view,
        own_keys=own_keys,
        own_ids=own_ids,
        prefer=[],
        lookup=lookup,
    )
    for thing_id in names_into:
        if thing_id not in own_ids and not any(
            row.thing_id == thing_id for row in file_into
        ):
            file_into.append(
                FileIntoRow(thing_id=thing_id, name=view.name_of(thing_id) or "")
            )
    # near it, as the real preview's context: where it's filed, what
    # mentions the stub, what the prompt picks
    near = [row.target_id for row in filings if row.ticked]
    if stub is not None:
        near += [m.owner_id for m in gather_mentions(view, stub.id).mentioned]
    near += list(payload.picks.values())
    move_here = move_here_rows(
        view,
        naming_facts(view, near, drafted(name, [], kind, payload.stub_id)),
        facts,
    )
    # same thing?: what the entry may already be, as the real preview
    # offers it (never the stub filled, nor the matching stub); the file's
    # `verdict` (`{verdict, why}`) stands in for the model's hint on the
    # top candidate, given only when both sides have facts
    matching = None if stub is not None else matching_stub(view, kind, name)
    skip = [thing_id for thing_id in (payload.stub_id, matching) if thing_id]
    same_as = same_offers(view, name, near_ids=[], exclude=skip, kind=kind)
    verdict: dict[str, Verdict] | None = None
    hint = fixed.get("verdict")
    if isinstance(hint, dict) and same_as and same_as[0].has_facts and facts:
        verdict = {same_as[0].thing_id: Verdict.model_validate(hint)}
    return CreatePreview(
        kind=kind,
        prompt=payload.prompt,
        fields=fields,
        name=name,
        facts=facts,
        prose=fixed["prose"],
        inherited=preview_inherited(view, kind, fields),
        stub_id=payload.stub_id,
        matching_stub_id=matching,
        context=context,
        picks=payload.picks,
        treated_as_new=payload.new_names,
        elsewhere=elsewhere,
        same_as=same_as,
        verdict=verdict,
        new_names=new_names,
        tag=clean_tag(fixed.get("tag"), kind),
        aka=list(fixed.get("aka") or []),
        hint=payload.hint,
        filings=filings,
        file_into=file_into,
        move_here=move_here,
    )


# --- links ------------------------------------------------------------------


def _stub_out(state: ThingState) -> dict | None:
    """A thing's stub marker for the wire: `None` for a full entry."""

    return {"ignored": state.stub_ignored} if state.is_stub else None


def _mark_self(runs: list[dict], own: Aliases) -> list[dict]:
    """`runs` (linked runs for the wire) with the page's own names in
    their plain runs split out as `{text, ref: None, stub: False, self:
    True}`: on its own page an entry's names, never linked there, read as
    "this page" (ruling H7). `own` is `names.own_alias_table` of the
    page's entry. Display only: the words, and so every offset into
    them, are unchanged, and a `self` run links nothing."""

    if not own:
        return runs
    out: list[dict] = []
    for run in runs:
        if run.get("ref") is not None or run.get("fresh") or run.get("self"):
            out.append(run)
            continue
        text = run["text"]
        end = 0
        for match in find_own_names(text, own):
            if match.start > end:
                out.append({**run, "text": text[end : match.start]})
            out.append({"text": match.text, "ref": None, "stub": False, "self": True})
            end = match.end
        if end == 0:
            out.append(run)
        elif end < len(text):
            out.append({**run, "text": text[end:]})
    return out


def _mark_own_page(page: dict, own: Aliases) -> None:
    """Mark the page's own names as "this page" (`_mark_self`) in the
    runs it shows as its own: its facts and what it inherits, the "but..."
    exceptions of its "In" rows, its prose and its timeline."""

    for row in [*page.get("facts", []), *page.get("inherited", [])]:
        row["segments"] = _mark_self(row["segments"], own)
    for row in page.get("in", []):
        for exception in row.get("exceptions", []):
            exception["segments"] = _mark_self(exception["segments"], own)
    for section, runs in page.get("prose_segments", {}).items():
        page["prose_segments"][section] = _mark_self(runs, own)
    for line in page.get("entry_timeline", []):
        line["segments"] = _mark_self(line["segments"], own)


class _Links:
    """Linked text in one view, for the wire: runs of rendered text as
    `{text, ref, stub}`, `ref` the thing a run links to and `stub` whether
    that thing is a stub. A link to an ignored stub is plain text: ignoring
    a stub hides it everywhere. Each linked thing is looked up once;
    `aliases`, the view's `alias_table` when the caller built it."""

    def __init__(self, view: WorldView, aliases: Aliases | None = None) -> None:
        self.view = view
        self.aliases = aliases
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
        for match in find_names(self.view, text, aliases=self.aliases):
            if match.suggested or any(c.id == owner for c in match.candidates):
                continue
            runs.append(Segment(text=text[end : match.start], ref=None))
            runs.append(Segment(text=match.text, ref=match.candidates[0].id))
            end = match.end
        runs.append(Segment(text=text[end:], ref=None))
        return self._out([run for run in runs if run.text])

    def draft_segments(
        self,
        written: str,
        fresh: dict[str, str],
        *,
        keep: Collection[str] | None = None,
    ) -> list[dict]:
        """A draft's text as linked runs, from `written`, the text as
        `link_text` links it with each of the draft's new names linked to a
        stand-in id (`_draft_new_names`; `fresh` maps each stand-in to its
        kind): a run linking a stand-in is the stub it will be on accept,
        `fresh` (with its `kind`), linking nothing yet. With `keep`, only
        links to those ids stay links and every other reads as its plain
        words (prose, whose links `prose_segments` found already: `keep`
        holds the entries the draft's new names were marked the same
        as)."""

        out: list[dict] = []

        def add(run: dict) -> None:
            plain = run["ref"] is None and not run.get("fresh")
            if plain and out and out[-1]["ref"] is None and not out[-1].get("fresh"):
                out[-1]["text"] += run["text"]
            elif run["text"]:
                out.append(run)

        def words(text: str) -> None:
            if not text:
                return
            for run in self.segments(text):
                if keep is not None and run["ref"] not in keep:
                    run = {"text": run["text"], "ref": None, "stub": False}
                add(run)

        end = 0
        for match in REF_PATTERN.finditer(written):
            words(written[end : match.start()])
            kind = fresh.get(match.group(1))
            if kind is not None:
                shown = match.group(2) or ""
                add(
                    {
                        "text": shown,
                        "ref": None,
                        "stub": False,
                        "fresh": True,
                        "kind": kind,
                    }
                )
            else:
                words(match.group(0))
            end = match.end()
        words(written[end:])
        return out

    def named_stubs(self, state: ThingState) -> list[dict]:
        """`{id, name, kind, tag, mentions, ignored}` of each live stub `state`'s facts link to (not
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
                        # the rest of a `list_stubs` row, so the stub's card
                        # is whole on the page that names it (polish 4)
                        "tag": tag_of(other),
                        "mentions": len(mentions(self.view, thing_id)),
                        "ignored": False,
                    }
                )
        return found


# joins a draft prose's plain runs, linked in one pass (`_draft_payload`):
# not a word character nor a space, so no name matches across it
_RUN_MARK = "\ue002"


class _DryStubs:
    """`make_stubs`' revision for a draft, writing nothing: each stub it
    would make is a stand-in id (and its kind), so the draft maps its new
    names exactly as accept will."""

    def __init__(self) -> None:
        self.kinds: dict[str, str] = {}

    def create_thing(self, kind: str, fields: dict[str, object]) -> str:
        key = name_key(str(fields.get("name") or ""))
        stand_in = hashlib.sha256(
            f"draft-new:{key}:{len(self.kinds)}".encode()
        ).hexdigest()[:32]
        self.kinds[stand_in] = kind
        return stand_in


def _draft_new_names(
    view: WorldView, rows: Collection[NewName], fresh: Collection[str] = ()
) -> tuple[dict[str, str], dict[str, str]]:
    """A draft's new names (`rows`: its own and its elsewhere rows') as
    `link_text`'s `new_names`, mapped the way accept maps them
    (`create._row_stubs`: `links.make_stubs`, run without writing), so the
    draft links them as accept will (M3): a name the world already has
    (by name or other name, a leading article aside; a species, race or
    mix by containment) maps to that entry; one left new, with its name
    without a lowercase leading "the", its other names that no other
    entry has and its written forms, maps to a stand-in id for the stub
    it will be (the second mapping: stand-in to kind, for
    `_Links.draft_segments`); a name marked the same as a live entry
    maps, with its written forms, to that entry. `fresh`: the names the
    owner treats as new (`treated_as_new`)."""

    same: dict[str, str] = {}
    for row in rows:
        target = row.same_target_id
        state = view.thing(target) if target else None
        if target is not None and state is not None and not state.stub_ignored:
            same.setdefault(name_key(row.name), target)
    dry = _DryStubs()
    mapping = make_stubs(
        cast(Revision, dry),
        view,
        [row for row in rows if name_key(row.name) not in same],
        fresh=fresh,
    )
    for row in rows:
        target = same.get(name_key(row.name))
        if target is None:
            continue
        for form in (row.name, *row.written):
            mapping.setdefault(" ".join(form.split()), target)
    return mapping, dict(dry.kinds)


# --- curation -----------------------------------------------------------------


def _draft_inherited_out(
    view: WorldView,
    links: _Links,
    calendar: Calendar,
    row: PreviewInherited,
    preview: CreatePreview,
) -> dict:
    """One inherited fact of a draft, as a saved page's `inherited` sends
    it (its category, dates, linked words and holder, from the fact as
    the world has it now), so the draft draws it on the same fact line;
    the words the preview was made with if the fact is gone.
    `overridden_by` is the index of the draft's own fact that replaces
    it, or `None`."""

    found = view.fact(row.fact_id)
    fact = found[1] if found is not None else None
    source = view.thing(row.source_id)
    return {
        "fact_id": row.fact_id,
        "category": row.category,
        "rendered": view.render(fact.text) if fact is not None else row.text,
        "segments": (
            links.segments(fact.text)
            if fact is not None
            else [{"text": row.text, "ref": None, "stub": False}]
        ),
        "valid_from": _date_out(calendar, fact.valid_from) if fact else None,
        "valid_until": _date_out(calendar, fact.valid_until) if fact else None,
        "source_id": row.source_id,
        "source_kind": source.kind if source is not None else None,
        "source_name": row.source,
        "overridden_by": next(
            (
                index
                for index, own in enumerate(preview.facts)
                if row.fact_id in own.overrides
            ),
            None,
        ),
        "held_by": _held_out(view, fact, source) if fact is not None else None,
    }


def _held_out(
    view: WorldView, fact: FactState, owner: ThingState | None
) -> dict | None:
    """Who holds `fact` (of `owner`) as a belief (`entries.held_by`), as
    `{id, name}`, or `None` for world truth."""

    if owner is None:
        return None
    holder = entries.held_by(view, fact, owner)
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
    holder = entries.held_by(view, fact, owner)
    if holder is None:
        return links._out(plain)
    held = held_text(view, fact, owner, text, holder_id=holder)
    if held == text:
        return links._out(plain)
    name = view.name_of(holder)
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


def _preview_out(world: World, preview: pydantic.BaseModel) -> dict:
    """A create preview for the wire: its dump, sent back as it is on
    accept, with the names the screen shows beside ids -- `held_by_name`
    on each fact and elsewhere fact, `from_name` on each "Could move here"
    row. The models ignore these on the way back in."""

    view = world.view()
    out = preview.model_dump(mode="json")

    def name(thing_id: object) -> str | None:
        return (view.name_of(thing_id) or "") if isinstance(thing_id, str) else None

    for row in [*out.get("facts", []), *out.get("elsewhere", [])]:
        row["held_by_name"] = name(row.get("held_by"))
    for row in out.get("move_here", []):
        row["from_name"] = name(row.get("from_id"))
    return out


def _settings_out(settings: CurationSettings) -> dict:
    return {
        "settings": settings.model_dump(mode="json"),
        "defaults": CurationSettings().model_dump(mode="json"),
    }


# --- filing -------------------------------------------------------------------


def _own_fact(state: ThingState | None, fact_id: str | None) -> FactState | None:
    if state is None:
        return None
    return next((fact for fact in state.facts if fact.fact_id == fact_id), None)


def _in_out(
    view: WorldView,
    links: _Links,
    calendar: Calendar,
    state: ThingState,
    index: FilingIndex,
) -> list[dict]:
    """The thing's "In" rows: each filing it has, in stored order, ended
    ones too (the dates say so), with its target, role, dates, the part of
    the target it's `within` (while that's live), whether that part still
    sits in the target as the part's own page reads it (`within_holds`,
    final review M3: the page marks one that has moved out) and its
    "but..." exceptions (its own facts the filing names, as linked runs).
    A filing into an entry that's gone is left out, hidden until it's
    back. `index` is the page's shared `FilingIndex`."""

    ended = view.at is None
    rows = []
    for filing in filings_of(view, state.id, live=False):
        if view.thing(filing.target) is None:
            continue
        within = (
            filing.within
            if filing.within is not None and view.thing(filing.within) is not None
            else None
        )
        exceptions = []
        for fact_id in filing.exceptions:
            found = view.fact(fact_id)
            if found is None or found[0] != state.id:
                continue
            exceptions.append(
                {"fact_id": fact_id, "segments": links.segments(found[1].text)}
            )
        rows.append(
            {
                "target_id": filing.target,
                "target_name": view.name_of(filing.target) or "",
                "role": filing.role,
                "show_under": filing.show_under,
                "since": _date_out(calendar, filing.since),
                "until": _date_out(calendar, filing.until),
                "within_id": within,
                "within_name": view.name_of(within) if within else None,
                "within_holds": within is not None
                and index.within_holds(filing, ended),
                "exceptions": exceptions,
            }
        )
    return rows


def _hint_of(state: ThingState) -> str | None:
    hint = state.fields.get("hint")
    return hint if isinstance(hint, str) and hint else None


def _line_fact(state: ThingState) -> FactState | None:
    """The fact an entry is shown by on one line (a Connected row): its
    summary (`entries.summary_fact`), else its first own fact."""

    summary = entries.summary_fact(state)
    if summary is not None:
        return summary
    return min(state.facts, key=lambda fact: fact.created, default=None)


def _connected_out(
    world: World,
    view: WorldView,
    links: _Links,
    calendar: Calendar,
    thing_id: str,
    things: list[ThingState],
    index: FilingIndex | None = None,
) -> list[dict]:
    """What is filed in the thing, grouped by tag (`filing.connected`,
    through the page's `index` when given):
    each group's tag (`None` for Other), heading and synopsis
    (`groups.cached_synopsis`: only a fresh cached one, no model call,
    and only at the latest telling -- `group_synopsis` has no sense of a
    past date), then one row per entry with its own line (its summary, as
    linked runs), whether it's a stub, whether it's a believed (or
    undecided) being -- listed, marked so (ruling F24) -- and the
    filing's role and dates.
    At the latest telling an ended filing is listed too (its `until`
    says so); at a date, only what holds then. An ignored stub is hidden
    here as everywhere."""

    states = {state.id: state for state in things}
    groups = []
    # at the latest telling, what has ended shows too, with its dates; at
    # a date, only what holds then
    for group in connected(
        view, thing_id, things=things, include_ended=view.at is None, index=index
    ):
        rows = []
        members: list[tuple[ThingState, Filing]] = []
        for row_id, filing in group.rows:
            state = states.get(row_id) or view.thing(row_id)
            if state is None or state.stub_ignored:
                continue
            members.append((state, filing))
            fact = _line_fact(state)
            rows.append(
                {
                    "id": row_id,
                    "name": view.name_of(row_id) or "",
                    "stub": state.is_stub,
                    # a believed (or undecided) being: shown, marked so
                    # (ruling F24)
                    "believed": state.kind == "being"
                    and not entries.acts_in_world(state),
                    "line_segments": links.segments(fact.text) if fact else [],
                    "role": filing.role,
                    "show_under": filing.show_under,
                    "since": _date_out(calendar, filing.since),
                    "until": _date_out(calendar, filing.until),
                }
            )
        if rows:
            groups.append(
                {
                    "tag": group.tag,
                    "heading": group.heading,
                    # the group's rows, worked out once here (final
                    # review I4)
                    "synopsis": (
                        cached_synopsis(
                            world, thing_id, group.tag, view=view, rows=members
                        )
                        if view.at is None
                        else None
                    ),
                    "rows": rows,
                    # the group exists only through its rows' `show_under`
                    # (no row carries it as its own tag): adding or
                    # dragging into it files with that `show_under`,
                    # never retags (ruling H5)
                    "via_show_under": group.tag is not None
                    and all(filing.show_under == group.tag for _s, filing in members),
                }
            )
    return groups


def _mentioned_out(
    view: WorldView, thing_id: str, index: FilingIndex | None = None
) -> list[dict]:
    """The entries whose facts name the thing without being filed in it
    (`filing.mentioned_in`, through the page's `index` when given), an
    ignored stub left out."""

    found = []
    for owner_id in mentioned_in(
        view, thing_id, include_ended=view.at is None, index=index
    ):
        state = view.thing(owner_id)
        if state is None or state.stub_ignored:
            continue
        found.append({"id": owner_id, "name": view.name_of(owner_id) or ""})
    return found


def _code_points(text: str, offset: int) -> int:
    """A UTF-16 code-unit offset into `text` (the page's JavaScript
    counts so: an emoji outside the Basic Multilingual Plane is two) as a
    code-point offset; `ValueError` for one past the end or inside such a
    character."""

    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        units += 2 if ord(char) > 0xFFFF else 1
        if units > offset:
            raise ValueError(f"offset {offset} is inside a character")
    if units == offset:
        return len(text)
    raise ValueError(f"no such selection in the fact: offset {offset}")


def _raw_span(view: WorldView, text: str, start: int, end: int) -> tuple[str, int, int]:
    """`(text, start, end)`: where the selected `start:end` of a fact's
    rendered text (as `view.render` shows it, the payload's `rendered`)
    lies in its stored `text`, links kept: a selection may cover plain
    words and whole links, never cut through a link (`ValueError`).
    Leading and trailing spaces are left out.

    A link the selection holds whole (polish 4: "House of Solarius" over
    the "Solarius" link) counts as its words: it's replaced by them in the
    `text` returned (the rest of the fact as stored), so the caller writes
    the selection's link over them, the longer name winning. So is a link
    whose target is deleted (P5), which shows as plain words: each one the
    selection touches, whole or in part.

    `start` and `end` are UTF-16 code units (ruling F18), the page's own
    unit, converted here (`_code_points`). They index `rendered`, not the
    runs the page shows: a held fact's segments read "<Holder> holds that
    ..." (`_held_segments`), a prefix `rendered` doesn't have, so the page
    takes it off first; and a link to an ignored stub shows as plain words
    but is still a link, so a selection over it is refused."""

    rendered = view.render(text)
    if not 0 <= start < end:
        raise ValueError(f"no such selection in the fact: {start}-{end}")
    start, end = _code_points(rendered, start), _code_points(rendered, end)
    if not 0 <= start < end <= len(rendered):
        raise ValueError(f"no such selection in the fact: {start}-{end}")
    while start < end and rendered[start].isspace():
        start += 1
    while end > start and rendered[end - 1].isspace():
        end -= 1
    if start == end:
        raise ValueError("the selection holds no words")
    text = _links_as_words(view, text, start, end)
    # rendered offset -> stored offset, run by run
    shown = 0
    stored = 0
    raw_start = raw_end = None
    for found in [*REF_PATTERN.finditer(text), None]:
        plain_to = found.start() if found is not None else len(text)
        length = plain_to - stored
        if raw_start is None and shown <= start <= shown + length:
            raw_start = stored + (start - shown)
        if raw_end is None and shown <= end <= shown + length:
            raw_end = stored + (end - shown)
        shown += length
        if found is None:
            break
        words = len(view.render(found.group(0)))
        if start < shown + words and end > shown:
            if raw_start is None or raw_end is None or raw_end > found.start():
                raise ValueError("the selection cuts through a link")
        shown += words
        stored = found.end()
    if raw_start is None or raw_end is None or raw_start > raw_end:
        raise ValueError("the selection cuts through a link")
    return text, raw_start, raw_end


def _links_as_words(view: WorldView, text: str, start: int, end: int) -> str:
    """`text` with each link the rendered `start:end` holds whole, and
    each link to a deleted thing it touches (P5), replaced by the words it
    renders as; the rendered text is the same either way."""

    shown = 0
    stored = 0
    out: list[str] = []
    for found in REF_PATTERN.finditer(text):
        shown += found.start() - stored
        words = view.render(found.group(0))
        dead = view.thing(found.group(1)) is None
        touched = start < shown + len(words) and end > shown
        whole = start <= shown and shown + len(words) <= end
        out.append(text[stored : found.start()])
        out.append(words if whole or (dead and touched) else found.group(0))
        shown += len(words)
        stored = found.end()
    out.append(text[stored:])
    return "".join(out)


# --- the plugin ---------------------------------------------------------------


class WorldsPlugin(Plugin):
    router = "worlds"

    async def signal_operation_failed(self, message: str, emit_status: bool = True):
        """A refused worlds action shows once, in the World tab's own error
        message (polish 5): no app-wide status popup repeats it."""

        await super().signal_operation_failed(message, emit_status=False)

    # where worlds live; tests point this at a temp directory
    worlds_root: Path | None = None

    def connect(self):
        # background tasks, kept referenced until they finish
        self.tasks: set[asyncio.Task] = set()
        # the language being made (one at a time), for cancelling
        self._make_task: asyncio.Task | None = None
        # one lock per thing id, so its prose tasks run in order
        self._prose_locks: dict[str, asyncio.Lock] = {}
        # the drafts of this session: draft key -> its versions, oldest
        # first (at most `DRAFT_VERSIONS`), in memory only
        self._drafts: OrderedDict[str, list[CreatePreview]] = OrderedDict()
        # each draft's current version (0-based): the newest, or the one
        # `use_version` restored; what prompt additions and selections add to
        self._current: dict[str, int] = {}
        # the small drafts of this session (fact, event and group-add
        # drafts), versioned, in memory only
        self._small = SmallDrafts()
        # the page drafts with a `preview_thing` (a Regenerate) still out,
        # and how many: a nested ask waits for them (R7)
        self._previews_out: Counter[str] = Counter()

    def disconnect(self):
        # nobody is left to review a language being made: stop it too
        if self._make_task is not None:
            self._make_task.cancel()
            self._make_task = None
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
                # a language being made read the world only to start: its
                # file still comes to the review, against the world open then
                if task is not self._make_task:
                    task.cancel()
            old.close()
            # a draft belongs to the world it was made in
            self._drafts.clear()
            self._current.clear()
            self._small.clear()
        self.websocket_handler.world = world

    def _require_world(self) -> World:
        world = self.world
        if world is None:
            raise ValueError("No world is open")
        return world

    def _client(self) -> Any:
        return instance.get_agent("creator").client

    def _language_client(self) -> Any:
        """The language agent's client, for naming and meanings; the
        creator's when the language agent has none."""

        try:
            client = instance.get_agent("language").client
        except KeyError:
            client = None
        return client if client is not None else self._client()

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

    def _thing_payload(
        self,
        world: World,
        thing_id: str,
        at: WorldDate | None,
        *,
        mark_own: bool = True,
    ) -> dict:
        """The thing's page at `at`. Its own names read as "this page" in
        its own runs (`_mark_own_page`, ruling H7), unless `mark_own` is
        false (a draft marks its own current names instead)."""

        view = world.view(at)
        state = view.thing(thing_id)
        if state is None:
            raise KeyError(f"no such thing: {thing_id}")
        calendar = world.calendar

        links = _Links(view)
        # the entry's summary fact, which the page heads its facts with
        summary = entries.summary_fact(state)
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
                "summary": summary is not None and fact.fact_id == summary.fact_id,
            }
            for fact in state.facts
        ]
        inherited = [
            {
                "fact_id": item.fact.fact_id,
                "category": item.fact.category,
                "rendered": view.render(item.fact.text),
                "segments": links.segments(item.fact.text),
                "valid_from": _date_out(calendar, item.fact.valid_from),
                "valid_until": _date_out(calendar, item.fact.valid_until),
                "source_id": item.source_id,
                "source_kind": item.source_kind,
                "source_name": item.source_name,
                "overridden_by": item.overridden_by,
                "held_by": _held_out(view, item.fact, view.thing(item.source_id)),
            }
            for item in heritage.inherited(view, thing_id)
        ]
        settings = world.curation()
        # Connected, Mentioned in and the timeline read every thing and
        # every filing: once, in one index (final review I4). At the latest
        # telling Connected and Mentioned in count ended filings too; the
        # timeline never does
        things = view.things()
        index = FilingIndex(
            view, things, (False, True) if view.at is None else (False,)
        )
        entry_lines = [
            _line_out(view, links, calendar, line)
            for line in entry_timeline(
                view,
                thing_id,
                reach=settings.timeline_reach,
                threshold=settings.date_threshold,
                things=things,
                index=index,
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

        page = {
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
            # what it is, and the prompt hint it was written with
            "tag": tag_of(state),
            "hint": _hint_of(state),
            # where it's filed, what's filed in it (by tag), and what names
            # it without being filed in it
            "in": _in_out(view, links, calendar, state, index),
            "connected": _connected_out(
                world, view, links, calendar, thing_id, things, index
            ),
            "mentioned_in": _mentioned_out(view, thing_id, index),
            # every change made to the thing (`World.timeline`)
            "timeline": timeline,
            # its dated facts, and what it gathers from what's filed in it
            "entry_timeline": entry_lines,
            "appears_in": self._appears_in(world, [thing_id]),
            "referenced_in": {
                **thing_references(world, thing_id),
                "member_scenes": self._appears_in(
                    world, heritage.members(view, thing_id)
                ),
            },
        }
        page.update(_languages_page(view, state))
        if state.kind == "language":
            # which of its words name something, worked out each time
            page["word_uses"] = word_uses(view, thing_id)
            # what a full language still lacks ("Still to fill in")
            found = (
                completeness_of(language_of(state, view))
                if state.fields.get("depth") == "full"
                else None
            )
            page["completeness"] = found.model_dump() if found is not None else None
        if mark_own:
            _mark_own_page(page, own_alias_table(state, page["name"]))
        return page

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
        there, keeps its words plain. Unknown phrases stay as they are.
        Markdown emphasis is scrubbed (`refs.scrub_emphasis`), keeping its
        words."""

        view = world.view(at)
        kept = [
            (
                span
                if span.ref is None
                or (span.ref != thing_id and view.thing(span.ref) is not None)
                else LinkSpan(start=span.start, end=span.end)
            )
            for span in spans or []
        ]
        # markdown emphasis goes after linking, so the spans' offsets hold;
        # a reference's words are never touched (hubs round 1, P2)
        return scrub_emphasis(
            link_text(
                view,
                text,
                picks=picks,
                owner=thing_id,
                as_new=new_names or (),
                spans=kept,
            )
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
        (`create.prose_reads`). A place's statements and timeline feed no
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
        old = world.unknown_structure()
        if old:
            # a world made before Filing (final review I3): refused with a
            # plain message, not opened to fail on every list. Fresh worlds
            # only, no migration (the spec)
            world.close()
            log.info("worlds.open_refused", path=str(path), unknown=old)
            await self.signal_operation_failed(
                "This world was made before Filing and can't be opened here "
                f"(it uses {', '.join(old[:4])}). Start a fresh world."
            )
            return
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
        """A kind's things, ignored stubs left out."""

        payload = ListThingsPayload(**data)
        world = self._require_world()
        view = world.view()
        # how many live entries are filed in each one now (its connections),
        # read once from the stored filings: no per-entry checks
        everything = [other for other in view.things() if not other.stub_ignored]
        live_ids = {other.id for other in everything}
        filed_here: dict[str, int] = {}
        for other in everything:
            targets = {
                filing.target
                for filing in stored_filings(other)
                if filing.until is None and filing.target in live_ids
            }
            for target in targets:
                filed_here[target] = filed_here.get(target, 0) + 1
        things = []
        for state in everything:
            if state.kind != payload.kind:
                continue
            entry: dict[str, Any] = {
                "id": state.id,
                "kind": state.kind,
                "name": view.name_of(state.id) or "",
                # its other names, so a picker finds it by one (polish 4)
                "aka": _aka_names(state),
            }
            if state.is_stub:
                entry["stub"] = _stub_out(state)
            # the entries it's filed in now (the World tab nests a place
            # under its most precise one, client-side)
            entry["filed_in"] = [
                filing.target
                for filing in filings_of(view, state.id)
                if view.thing(filing.target) is not None
            ]
            if state.kind == "being":
                # only a real being is cast or played (the scene pickers)
                entry["existence"] = entries.existence(state)
            # what a kind's list and the side search read (polish 5)
            line = _line_fact(state)
            span = _span_out(state)
            dated = [
                year
                for year in (_year_of(fact.valid_from) for fact in state.facts)
                if year is not None
            ]
            entry["tag"] = tag_of(state)
            entry["line"] = view.render(line.text) if line else ""
            entry["changed_rev"] = max(
                (change.source_rev for change in world.timeline(state.id)), default=0
            )
            # the facts of other entries that name it, counted, not rendered
            named = sum(
                1
                for owner, _fact in view.referencing(state.id, any_date=True)
                if owner != state.id
            )
            entry["connections"] = named + filed_here.get(state.id, 0)
            entry["span"] = span
            entry["sort_date"] = (span or {}).get("from") or (
                min(dated) if dated else None
            )
            things.append(entry)
        self._reply("list_things", {"kind": payload.kind, "things": things})

    async def handle_list_heritage(self, data: dict):
        view = self._require_world().view()
        things = [
            {
                "id": state.id,
                "kind": state.kind,
                "name": view.name_of(state.id) or "",
                "aka": _aka_names(state),
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
        self._refuse_while_nested(payload.draft_key)
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
                hint=payload.hint,
            )
        key = payload.draft_key
        # a regeneration of a draft that's discarded (or forgotten) before
        # its reply comes is dropped: the owner threw the draft away
        known = key is not None and key in self._drafts
        answer = self.create_task_done_callback(
            "preview_thing",
            "preview_failed",
            "Error previewing a world thing",
            success_data=lambda preview: self._new_version(world, key, preview),
        )
        if key is not None:
            self._previews_out[key] += 1

        def on_done(task: asyncio.Task) -> None:
            if key is not None:
                self._previews_out[key] -= 1
                if self._previews_out[key] <= 0:
                    del self._previews_out[key]
            done = not task.cancelled() and task.exception() is None
            if done and known and key not in self._drafts:
                log.info("worlds.preview_dropped", draft_key=key)
                return
            resolved = (key or self._draft_key(task.result())) if done else None
            if resolved is not None and self._small.held(nested_key(resolved)):
                # R7: the page draft's nested draft was asked on the
                # version current now, so no other version joins it
                log.info("worlds.preview_refused_nested", draft_key=resolved)
                self.websocket_handler.queue_put(
                    {
                        "type": self.router,
                        "action": "preview_failed",
                        "message": "write or discard the added facts first",
                        "data": {"draft_key": resolved},
                    }
                )
                return
            answer(task)

        self._spawn(preview, on_done)

    # --- drafts -----------------------------------------------------------

    @staticmethod
    def _draft_key(preview: CreatePreview) -> str:
        """A new draft's key: `stub:<id>` for a stub being expanded (one
        draft per stub), else `new:<kind>:<name>` (the name as compared,
        `links.name_key`). A regeneration sends its draft's key back, so
        its versions stay together whatever the model names it."""

        if preview.stub_id is not None:
            return f"stub:{preview.stub_id}"
        return f"new:{preview.kind}:{name_key(preview.name)}"

    def _new_version(
        self, world: World, key: str | None, preview: CreatePreview
    ) -> dict:
        """Keep `preview` as the newest version of its draft (at most
        `DRAFT_VERSIONS`, the oldest dropped first) and answer with it."""

        key = key or self._draft_key(preview)
        versions = self._drafts.setdefault(key, [])
        versions.append(preview)
        del versions[:-DRAFT_VERSIONS]
        self._touch(key, len(versions) - 1)
        return self._draft_out(world, key)

    def _touch(self, key: str, current: int) -> None:
        """Make `current` the draft's current version and the draft the
        most recently used, forgetting the least recently used past
        `DRAFTS_KEPT`."""

        self._current[key] = current
        self._drafts.move_to_end(key)
        while len(self._drafts) > DRAFTS_KEPT:
            gone, _versions = self._drafts.popitem(last=False)
            self._current.pop(gone, None)
            # its nested fact draft, and any ask for it, go with it
            self._small.discard(nested_key(gone))
            log.info("worlds.draft_forgotten", draft_key=gone)

    def _draft_out(self, world: World, key: str, index: int | None = None) -> dict:
        """A draft version for the wire: the draft as a page payload
        (`_draft_payload`), plus the data to accept (`preview`), its key,
        which version it is (1-based) and every version kept (`versions:
        [{version, name, prompt}]`)."""

        versions = self._drafts[key]
        if index is None:
            index = self._current.get(key, len(versions) - 1)
        preview = versions[index]
        return {
            **self._draft_payload(world, preview),
            "preview": _preview_out(world, preview),
            "draft_key": key,
            "version": index + 1,
            "versions": [
                {"version": number, "name": kept.name, "prompt": kept.prompt}
                for number, kept in enumerate(versions, start=1)
            ],
        }

    def _require_draft(self, key: str) -> list[CreatePreview]:
        versions = self._drafts.get(key)
        if not versions:
            raise KeyError(f"no such draft: {key}")
        return versions

    def _refuse_while_nested(self, key: str | None) -> None:
        """Refuse what would accept the page draft `key` or make another
        of its versions current while its nested fact draft is held or
        still being asked for: the nested draft is written into (or
        discarded from) the version it was asked on first, and an accept
        never leaves an ask's facts behind."""

        if key is None:
            return
        nested = nested_key(key)
        if self._small.held(nested) or self._small.asking(nested):
            raise ValueError("write or discard the added facts first")

    async def handle_use_version(self, data: dict):
        """Restore one kept version of a draft ("Version n of m"): answers
        `use_version` as `preview_thing` does, for that version. Writes
        nothing; the versions kept stay as they are."""

        payload = UseVersionPayload(**data)
        world = self._require_world()
        versions = self._require_draft(payload.draft_key)
        self._refuse_while_nested(payload.draft_key)
        if not 1 <= payload.version <= len(versions):
            raise ValueError(f"the draft has no version {payload.version}")
        self._touch(payload.draft_key, payload.version - 1)
        self._reply("use_version", self._draft_out(world, payload.draft_key))

    async def handle_discard_preview(self, data: dict):
        """Discard a draft: every version kept goes, and its nested fact
        draft (and any ask for one still out) with it, and nothing is
        written (no stub, filing or fact). Answers `{draft_key}`."""

        payload = DraftKeyPayload(**data)
        self._drafts.pop(payload.draft_key, None)
        self._current.pop(payload.draft_key, None)
        self._small.discard(nested_key(payload.draft_key))
        self._reply("discard_preview", {"draft_key": payload.draft_key})

    async def handle_draft_render(self, data: dict):
        """The draft as the owner left it, linked as accept will link it
        (P6), writing nothing: `{draft_key, seq, facts: [{index, text,
        segments}], prose_segments, entry_timeline, numbers}` for `preview`, the
        client's copy with the owner's edits. Its facts, prose and
        timeline are `_draft_payload`'s for that copy: a rewritten fact's
        names link, its new names show `fresh`, and the timeline holds the
        dated facts accept will write. As at accept, only the selected
        names a version held here recorded link without a capital, and
        the stub expanded is the server's copy's. Its "For other pages"
        rows come as `elsewhere: [{index, text, segments}]`, and its
        `numbers` as its page shows them (its own, else inherited).

        A render that can't be made (a draft no longer held, a copy that
        doesn't parse) answers `draft_render_failed {draft_key, seq}`
        instead of an error: the page keeps what it shows, and nothing it
        has pending is touched."""

        try:
            payload = DraftRenderPayload(**data)
            world = self._require_world()
            held = self._current_preview(payload.draft_key)
            preview = payload.preview.model_copy(update={"stub_id": held.stub_id})
            self._check_selected_names(preview, payload.draft_key)
            # only the repeat moves a version held here recorded, as at
            # accept
            self._check_page_repeats(preview, payload.draft_key, [])
            page = self._draft_payload(world, preview)
        except Exception as exc:
            log.warning(
                "worlds.draft_render_failed",
                draft_key=data.get("draft_key"),
                error=str(exc),
            )
            self._reply(
                "draft_render_failed",
                {"draft_key": data.get("draft_key"), "seq": data.get("seq")},
            )
            return
        self._reply(
            "draft_render",
            {
                "draft_key": payload.draft_key,
                "seq": payload.seq,
                "facts": [
                    {
                        "index": fact["index"],
                        "text": fact["text"],
                        "segments": fact["segments"],
                    }
                    for fact in page["facts"]
                    if fact.get("draft")
                ],
                "elsewhere": page["elsewhere"],
                "prose_segments": page["prose_segments"],
                "entry_timeline": page["entry_timeline"],
                "numbers": page["numbers"],
            },
        )

    def _draft_payload(self, world: World, preview: CreatePreview) -> dict:
        """The draft as the page the entry will be, from the data it would
        write, writing nothing. A stub being expanded starts from its own
        page (what's filed in it, what names it, its facts and filings so
        far), a new entry from an empty one; the draft adds its name,
        kind, tag, hint, other names, fields, prose, what it inherits, its
        facts (`draft: true`, each linked as it would be, with its tick,
        repeat and holder) and its "In" rows (`draft: true`, with their
        tick), and the dated facts accept will write (its ticked ones) on
        the timeline. Its new names are linked as accept links them, to
        the stubs they'll be, and shown `fresh` (`_draft_new_names`), in
        its facts, timeline and prose alike; `elsewhere` holds its "For
        other pages" facts (`{index, text, segments}`), each linked onto
        its target as accept links it, the entry's own names included. `id` is the stub's, or
        `null`; `draft` is true."""

        view = world.view()
        calendar = world.calendar
        # the world's names, gathered once for every text the draft links
        # (I1): a revision's view never changes
        aliases = alias_table(view)
        links = _Links(view, aliases)
        stub = view.thing(preview.stub_id) if preview.stub_id else None
        if stub is not None and stub.is_stub:
            page = self._thing_payload(world, stub.id, None, mark_own=False)
        else:
            stub = None
            page = {
                "id": None,
                "at": None,
                "stub": None,
                "facts": [],
                "numbers": heritage.Numbers(
                    lifespan=None, adult_age=None, measures={}
                ).model_dump(),
                "life_stage": None,
                "races": [],
                "mixes": [],
                "mentions": [],
                "named_stubs": [],
                "in": [],
                "connected": [],
                "mentioned_in": [],
                "timeline": [],
                "entry_timeline": [],
                "appears_in": [],
                "referenced_in": {
                    "facts": [],
                    "fields": [],
                    "scenes": [],
                    "member_scenes": [],
                },
            }
        owner = stub.id if stub is not None else None
        # its new names linked as accept will link them: each to a
        # stand-in for its stub, shown `fresh`
        new_names, fresh = _draft_new_names(
            view,
            [
                *preview.new_names,
                *(row.new for row in preview.elsewhere if row.new is not None),
            ],
            preview.treated_as_new,
        )

        def linked(text: str) -> list[dict]:
            # emphasis scrubbed first, as accept's `linked_text` does (M3)
            return links.draft_segments(
                link_text(
                    view,
                    scrub_emphasis(text),
                    picks=preview.picks,
                    new_names=new_names,
                    owner=owner,
                    as_new=preview.treated_as_new,
                    lowercase=preview.selected_names,
                    aliases=aliases,
                ),
                fresh,
            )

        # the entries new names were marked the same as: linked in prose
        same_targets = {
            thing_id for thing_id in new_names.values() if thing_id not in fresh
        }
        # "For other pages" facts link the entry itself too, as accept's
        # do (its revision's view has it); a new entry's names stand in
        # for it, shown `fresh`
        own_names: dict[str, str] = {}
        own_fresh = dict(fresh)
        if owner is None:
            itself = hashlib.sha256(b"draft-self").hexdigest()[:32]
            own_fresh[itself] = preview.kind
            for form in [
                preview.name,
                *(
                    str(entry["name"])
                    for entry in preview.aka
                    if isinstance(entry, dict) and isinstance(entry.get("name"), str)
                ),
            ]:
                tidy = " ".join(form.split())
                if tidy:
                    own_names.setdefault(tidy, itself)

        def elsewhere_linked(row: ElsewhereFact) -> list[dict]:
            # linked onto its target, as `write_elsewhere` links it
            target = row.target_id
            if target is None and row.new is not None:
                target = new_names.get(" ".join(row.new.name.split()))
            return links.draft_segments(
                link_text(
                    view,
                    scrub_emphasis(row.text),
                    picks=preview.picks,
                    new_names={**own_names, **new_names},
                    owner=target,
                    as_new=preview.treated_as_new,
                    lowercase=preview.selected_names,
                    aliases=aliases,
                ),
                own_fresh,
            )

        def prose_linked(text: str) -> list[dict]:
            # as the accepted page links it (`prose_segments`), the new
            # names, stubs then, marked in the words it leaves plain: those
            # words linked in one pass, joined by a mark no name matches
            # across, so each run links as it would alone
            runs = links.prose_segments(text, owner or "")
            plain = [run["text"] for run in runs if run["ref"] is None]
            if any(_RUN_MARK in words for words in plain):
                written = [
                    link_text(
                        view,
                        words,
                        new_names=new_names,
                        owner=owner,
                        as_new=preview.treated_as_new,
                        lowercase=preview.selected_names,
                        aliases=aliases,
                    )
                    for words in plain
                ]
            else:
                written = link_text(
                    view,
                    _RUN_MARK.join(plain),
                    new_names=new_names,
                    owner=owner,
                    as_new=preview.treated_as_new,
                    lowercase=preview.selected_names,
                    aliases=aliases,
                ).split(_RUN_MARK)
            linked_runs = iter(written)
            out: list[dict] = []
            for run in runs:
                found = (
                    links.draft_segments(next(linked_runs), fresh, keep=same_targets)
                    if run["ref"] is None
                    else [run]
                )
                for part in found:
                    if (
                        out
                        and part["ref"] is None
                        and not part.get("fresh")
                        and out[-1]["ref"] is None
                        and not out[-1].get("fresh")
                    ):
                        out[-1] = {**out[-1], "text": out[-1]["text"] + part["text"]}
                    else:
                        out.append(part)
            return out

        def held(holder: str | None) -> dict | None:
            if holder is None or view.thing(holder) is None:
                return None
            return {"id": holder, "name": view.name_of(holder) or ""}

        # each fact linked once, its timeline line reusing its segments
        segments = [linked(fact.text) for fact in preview.facts]
        facts = [
            {
                "fact_id": None,
                "draft": True,
                "index": index,
                "category": fact.category,
                "text": fact.text,
                "rendered": fact.text,
                "segments": segments[index],
                "valid_from": _date_out(calendar, fact.since),
                "valid_until": None,
                "source_rev": None,
                "overrides": list(fact.overrides),
                "held_by": held(fact.held_by),
                "ticked": fact.ticked,
                "repeat_of": fact.repeat_of,
            }
            for index, fact in enumerate(preview.facts)
        ]
        filed = {row["target_id"] for row in page["in"]}
        drafted_in = [
            {
                "target_id": row.target_id,
                "target_name": (view.name_of(row.target_id) if row.target_id else None)
                or row.target_name,
                "role": row.role,
                "show_under": row.show_under,
                "since": _date_out(calendar, row.since),
                "until": None,
                "within_id": row.within,
                "within_name": view.name_of(row.within) if row.within else None,
                "exceptions": [
                    {"fact_id": None, "segments": linked(exception.text)}
                    for exception in row.exceptions
                ],
                "draft": True,
                "ticked": row.ticked,
            }
            for row in preview.filings
            if row.target_id is None or row.target_id not in filed
        ]
        # the dated facts accept will write (its ticked ones), as the
        # owner left them
        lines = [
            {
                "fact_id": None,
                "owner_id": owner,
                "owner_name": preview.name,
                "date": _date_out(calendar, fact.since),
                "until": _date_out(calendar, fact.until),
                "segments": segments[index],
                "here": True,
                "disagrees_with": [],
            }
            for index, fact in enumerate(preview.facts)
            if fact.since is not None and fact.ticked
        ]
        # and the dated facts its ticked "Move existing here" and "Could
        # move here" rows move onto it, as accept moves them (M3): still
        # their entry's, no summary; their links to the entry, words
        moved_ids: set[str] = set()
        for row in preview.move_here:
            found = view.fact(row.fact_id) if row.ticked else None
            if (
                found is None
                or found[0] != row.from_id
                or row.from_id == owner
                or found[1].valid_from is None
                or entries.is_summary_fact(found[1])
            ):
                continue
            moved_ids.add(row.fact_id)
            lines.append(
                {
                    "fact_id": None,
                    "owner_id": owner,
                    "owner_name": preview.name,
                    "date": _date_out(calendar, found[1].valid_from),
                    "until": _date_out(calendar, found[1].valid_until),
                    "segments": [
                        seg
                        if seg["ref"] != owner or owner is None
                        else {**seg, "ref": None, "stub": False}
                        for seg in links.segments(found[1].text)
                    ],
                    "here": True,
                    "disagrees_with": [],
                }
            )
        timeline = sorted(
            [
                *(
                    line
                    for line in page["entry_timeline"]
                    if line.get("fact_id") not in moved_ids
                ),
                *lines,
            ],
            key=lambda line: line["date"]["instant"] if line["date"] else -1,
        )
        sections = prose_gen.sections_for(preview.kind)
        # what its page will show: its own numbers, the rest inherited
        # along the species or parents its fields name (a saved entry's
        # `heritage.numbers`)
        numbers = heritage.numbers_of(
            view,
            ThingState(
                id=owner or "", kind=preview.kind, fields=preview.fields, facts=[]
            ),
        )
        drafted = {
            **page,
            "id": owner,
            "draft": True,
            "kind": preview.kind,
            "name": preview.name,
            "numbers": numbers.model_dump(),
            "fields": {
                field: _value_out(calendar, value)
                for field, value in preview.fields.items()
                if field not in ("aka", "stub")
            },
            "aka": preview.aka,
            "tag": preview.tag,
            "hint": preview.hint,
            "facts": [*page["facts"], *facts],
            "inherited": [
                _draft_inherited_out(view, links, calendar, row, preview)
                for row in preview.inherited
            ],
            "prose": {
                section: {
                    "text": preview.prose.get(section),
                    "stale": False,
                    "edited": False,
                }
                for section in sections
            },
            "prose_segments": {
                section: (
                    prose_linked(preview.prose[section])
                    if preview.prose.get(section)
                    else []
                )
                for section in sections
            },
            "in": [*page["in"], *drafted_in],
            "entry_timeline": timeline,
            "elsewhere": [
                {"index": index, "text": row.text, "segments": elsewhere_linked(row)}
                for index, row in enumerate(preview.elsewhere)
            ],
        }
        # its own current names read as "this page" (ruling H7), as an
        # accepted entry's do; its "For other pages" rows are others'
        itself = ThingState(
            id=owner or "",
            kind=preview.kind,
            fields={"name": preview.name, "aka": list(preview.aka)},
            facts=[],
        )
        _mark_own_page(drafted, own_alias_table(itself, preview.name))
        return drafted

    def _check_repeat_moves(
        self,
        rows: Sequence[Any],
        move_here: Sequence[MoveHereFact],
        held_rows: Sequence[Any],
        notes: list[str],
    ) -> list[MoveHereFact]:
        """Keep only the "Move existing here" rows (`move_here` with
        `repeat`) and the "Keep new" rows (`replaces_repeat`, P8) whose
        repeat one of `held_rows` (every row of every version of the draft
        this session holds) says it repeats, checked against the server's
        copy rather than the client's word; any other move row is dropped,
        and any other row keeps the fact it repeats (its `replaces_repeat`
        cleared), with a note. Returns the kept `move_here`. `rows` and
        `held_rows` are duck-typed (`replaces_repeat`, `repeat_of`):
        `_check_page_repeats` calls this once for a page draft's own
        facts (with its `move_here`) and again for its elsewhere rows
        (with none), each against the matching rows of `held_rows`."""

        held = {
            (row.repeat_of.get("fact_id"), row.repeat_of.get("owner_id"))
            for row in held_rows
            if row.repeat_of
        }
        kept = []
        for move in move_here:
            if move.repeat and (move.fact_id, move.from_id) not in held:
                notes.append(
                    f'"{move.text[:60]}" isn\'t a fact this draft repeats, so it'
                    " doesn't move here"
                )
                continue
            kept.append(move)
        for row in rows:
            repeat = row.repeat_of or {}
            if not row.replaces_repeat:
                continue
            if (repeat.get("fact_id"), repeat.get("owner_id")) not in held:
                row.replaces_repeat = False
                shown = str(repeat.get("text") or "")[:60]
                notes.append(
                    f"\"{shown}\" isn't a fact this draft repeats, so it isn't removed"
                )
        return kept

    def _check_page_repeats(
        self, preview: CreatePreview, key: str | None, notes: list[str]
    ) -> None:
        """`_check_repeat_moves` for a page draft: against the facts of
        every version of the draft `key` this session holds. Its
        elsewhere rows' "Keep new" (`replaces_repeat`) is checked again,
        separately, against those versions' own elsewhere rows'
        `repeat_of` -- an elsewhere repeat is its target's fact, never
        one of the draft's own, so it never vouches for or is vouched by
        an own fact's repeat."""

        versions = self._drafts.get(key or "") or []
        held = [fact for version in versions for fact in version.facts]
        preview.move_here = self._check_repeat_moves(
            preview.facts, preview.move_here, held, notes
        )
        held_elsewhere = [row for version in versions for row in version.elsewhere]
        self._check_repeat_moves(preview.elsewhere, [], held_elsewhere, notes)

    def _prose_name(self, preview: CreatePreview, key: str | None) -> str | None:
        """The name the preview's prose was written under, from the
        server's own copies (P7): the name of the version of the draft
        this session holds with that prose, else (the owner edited the
        prose too, M4) the name of its current version, whose prose the
        edits began from; `None` without a held draft."""

        versions = self._drafts.get(key or "") or []
        for version in versions:
            if version.prose == preview.prose:
                return version.name
        return self._current_preview(key).name if key and versions else None

    def _check_selected_names(self, preview: CreatePreview, key: str | None) -> None:
        """Keep only the `selected_names` (ruling F26: words that link
        without a capital) and `pick_names` (P4: words taught as other
        names) a version of the draft this session holds recorded from the
        owner's own selections, never the client's word."""

        held = {
            name_key(name)
            for version in (self._drafts.get(key or "") or [])
            for name in version.selected_names
        }
        preview.selected_names = [
            name for name in preview.selected_names if name_key(name) in held
        ]
        # P4's "add as another name" on the draft, as recorded here too
        taught = {
            name_key(name)
            for version in (self._drafts.get(key or "") or [])
            for name in version.pick_names
        }
        preview.pick_names = [
            name for name in preview.pick_names if name_key(name) in taught
        ]

    async def handle_accept_preview(self, data: dict):
        payload = AcceptPreviewPayload(**data)
        world = self._require_world()
        self._refuse_while_nested(payload.draft_key)
        notes: list[str] = []
        self._check_page_repeats(payload.preview, payload.draft_key, notes)
        self._check_selected_names(payload.preview, payload.draft_key)
        # the other things whose prose input the accept changed
        prose: list[str] = []
        thing_id = accept_preview(
            world,
            payload.preview,
            into_stub=payload.into_stub,
            same_target_id=payload.same_target_id,
            notes=notes,
            prose=prose,
            prose_name=self._prose_name(payload.preview, payload.draft_key),
        )
        if payload.draft_key is not None:
            # written: the draft and its versions are done, and so is any
            # nested ask still out for it
            self._drafts.pop(payload.draft_key, None)
            self._current.pop(payload.draft_key, None)
            self._small.discard(nested_key(payload.draft_key))
        self._reply(
            "accept_preview",
            {**self._thing_payload(world, thing_id, None), "notes": notes},
        )
        # the accept's own list (a re-pointed stub, a "Could move here"
        # row's source, a same-thing target), then the elsewhere targets whose
        # prose reads what they took
        prose += self._wrote_prose_input(
            world,
            self._elsewhere_targets(payload.preview.elsewhere),
            skip={thing_id, *prose},
        )
        for changed in dict.fromkeys(prose):
            self._schedule_prose(changed, None)

    # --- filing -----------------------------------------------------------

    @staticmethod
    def _require_entry(view: WorldView, thing_id: str) -> ThingState:
        """A live entry (or stub) to file in or to act on; an ignored stub
        is no entry to use."""

        state = view.thing(thing_id)
        if state is None or state.stub_ignored:
            raise KeyError(f"no such entry: {thing_id}")
        return state

    @staticmethod
    def _filing_dates(
        since: WorldDate | None, until: WorldDate | None
    ) -> tuple[WorldDate | None, WorldDate | None]:
        if since is not None and until is not None and since.instant > until.instant:
            raise ValueError("a filing can't end before it starts")
        return since, until

    @staticmethod
    def _write_filings(
        rev: Any, world: World, thing_id: str, filings: list[Filing]
    ) -> None:
        """The thing's whole `filings` value, dated as any filings write
        (`create.filings_since`). The store checks it
        (`filing.check_filings`: no cycle, a live target, a `within` that
        sits in its target) and refuses it whole, naming what's wrong."""

        rev.set_field(
            thing_id,
            "filings",
            [filing.model_dump(mode="json") for filing in filings],
            filings_since(world, thing_id),
        )

    async def handle_add_filing(self, data: dict):
        """File a thing in an entry ("+ in..."): `target_id`, or
        `new_name`, a stub made on the spot (of `kind`, lore by default,
        with `tag`; a name the world has already is that entry), in one
        revision. Refused, writing nothing: a target it's filed in already
        (`edit_filing` changes that one), a target that's gone, a cycle, a
        `within` that isn't a part of the target, an end before the start.
        Filings are no prose input: none is scheduled."""

        payload = AddFilingPayload(**data)
        world = self._require_world()
        view = world.view()
        state = self._require_entry(view, payload.thing_id)
        since, until = self._filing_dates(
            _date_in(payload.since), _date_in(payload.until)
        )
        if payload.kind is not None and payload.kind not in KINDS:
            raise ValueError(f"no such kind: {payload.kind!r}")
        if payload.target_id is not None:
            self._require_entry(view, payload.target_id)
        current = filings_of(view, state.id, live=False)
        name = " ".join((payload.new_name or "").split())
        with world.revision(Source.manual(note="filed")) as rev:
            target_id = payload.target_id
            if target_id is None:
                made = make_stubs(
                    rev,
                    world.view(),
                    [NewName(name=name, kind=payload.kind or "lore", tag=payload.tag)],
                )
                target_id = made[name]
                reused = view.thing(target_id)
                if reused is not None and reused.stub_ignored:
                    # the owner asked for it by name: no longer ignored
                    rev.set_field(target_id, "stub", {"ignored": False}, None)
            if any(filing.target == target_id for filing in current):
                raise ValueError(
                    f"{view.name_of(payload.thing_id)} is filed in"
                    f" {world.view().name_of(target_id)} already"
                )
            role = (payload.role or "").strip() or None
            self._write_filings(
                rev,
                world,
                payload.thing_id,
                [
                    *current,
                    Filing(
                        target=target_id,
                        role=role,
                        since=since,
                        until=until,
                        within=payload.within,
                        show_under=normalise_tag(payload.show_under or "") or None,
                    ),
                ],
            )
        self._edited("add_filing", payload.thing_id, _date_in(payload.at), prose=False)

    async def handle_edit_filing(self, data: dict):
        """Change the thing's filing into `target_id`: the keys sent
        (`role`, `since`, `until`, `within`, `show_under`: the group it
        shows under on the target's page, a tag; null clears one), the rest
        and its exceptions kept, in one revision. An `until` ends it
        ("End this"), which is how an item leaves an entry now. Refused as
        `add_filing` is, and for a filing the thing doesn't have."""

        payload = EditFilingPayload(**data)
        world = self._require_world()
        view = world.view()
        self._require_entry(view, payload.thing_id)
        current = filings_of(view, payload.thing_id, live=False)
        index = next(
            (i for i, f in enumerate(current) if f.target == payload.target_id), None
        )
        if index is None:
            raise KeyError(
                f"{view.name_of(payload.thing_id)} isn't filed in {payload.target_id}"
            )
        sent = payload.model_fields_set
        update: dict[str, Any] = {}
        if "role" in sent:
            update["role"] = (payload.role or "").strip() or None
        if "since" in sent:
            update["since"] = _date_in(payload.since)
        if "until" in sent:
            update["until"] = _date_in(payload.until)
        if "within" in sent:
            update["within"] = payload.within
        if "show_under" in sent:
            update["show_under"] = normalise_tag(payload.show_under or "") or None
        filing = current[index].model_copy(update=update)
        self._filing_dates(filing.since, filing.until)
        filings = [*current[:index], filing, *current[index + 1 :]]
        with world.revision(Source.manual(note="filing changed")) as rev:
            self._write_filings(rev, world, payload.thing_id, filings)
        self._edited("edit_filing", payload.thing_id, _date_in(payload.at), prose=False)

    async def handle_remove_filing(self, data: dict):
        """Take the thing out of `target_id`, in one revision: the filing
        goes, and with it the "but..." exceptions it held (its own facts,
        which say nothing once it isn't filed there). Answers with the
        thing and `notes`, naming each "but..." removed. The exceptions
        feed its prose, so prose is refreshed when any went."""

        payload = RemoveFilingPayload(**data)
        world = self._require_world()
        view = world.view()
        state = self._require_entry(view, payload.thing_id)
        current = filings_of(view, payload.thing_id, live=False)
        gone = next((f for f in current if f.target == payload.target_id), None)
        if gone is None:
            raise KeyError(
                f"{view.name_of(payload.thing_id)} isn't filed in {payload.target_id}"
            )
        own = {fact.fact_id for fact in world.live_facts(payload.thing_id)}
        exceptions = [fact_id for fact_id in gone.exceptions if fact_id in own]
        with world.revision(Source.manual(note="unfiled")) as rev:
            rev.set_field(
                payload.thing_id,
                "filings",
                [f.model_dump(mode="json") for f in current if f is not gone],
                filings_since(world, payload.thing_id),
            )
            for fact_id in exceptions:
                rev.remove_fact(fact_id)
        target_name = view.name_of(payload.target_id) or payload.target_id
        notes = [
            f'Removed the "but..." "{view.render(found[1].text)}": it was an'
            f" exception to {target_name}"
            for fact_id in exceptions
            if (found := view.fact(fact_id)) is not None
        ]
        at = _date_in(payload.at)
        self._reply(
            "remove_filing",
            {**self._thing_payload(world, payload.thing_id, at), "notes": notes},
        )
        if exceptions and not state.is_stub:
            self._schedule_prose(payload.thing_id, at)

    async def handle_add_exception(self, data: dict):
        """Add a "but..." to a character's (or real being's) filing in
        `target_id`: a `ties` fact written as creation writes one
        (`create.filing_exception_fact`), its id added to the filing's
        `exceptions`, in one revision. `rejects` is what it departs from:
        `{thing_id}`, an entry filed in the target, or `{fact_id}`, one of
        the target's own facts; null departs from the target as a whole.
        The text is linked like `add_fact`'s. A fact feeds its prose,
        which is refreshed."""

        payload = AddExceptionPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
        view = world.view()
        state = view.thing(payload.character_id)
        if state is None or not entries.acts_in_world(state):
            raise ValueError(
                "only a character or a real being has exceptions to a filing"
            )
        current = filings_of(view, payload.character_id, live=False)
        index = next(
            (i for i, f in enumerate(current) if f.target == payload.target_id), None
        )
        if index is None or view.thing(payload.target_id) is None:
            raise ValueError("the character isn't filed in that entry")
        if not payload.text.strip():
            raise ValueError("an exception needs some text")
        target_name = view.name_of(payload.target_id) or ""
        rejects = payload.rejects
        item_name = target_name
        if rejects is not None and rejects.thing_id is not None:
            filed = {other.id for other, _filing in filed_in(view, payload.target_id)}
            if rejects.thing_id not in filed:
                raise ValueError(f"that isn't filed in {target_name}")
            item_name = view.name_of(rejects.thing_id) or ""
        elif rejects is not None:
            found = view.fact(rejects.fact_id or "")
            if found is None or found[0] != payload.target_id:
                raise ValueError(f"that isn't one of {target_name}'s facts")
            item_name = target_name
        text = self._linked(
            world,
            payload.character_id,
            payload.text,
            payload.picks,
            at,
            payload.new_names,
            payload.spans,
        )
        exception = PreviewException(
            text=payload.text,
            item=item_name,
            thing_id=rejects.thing_id if rejects is not None else None,
            fact_id=rejects.fact_id if rejects is not None else None,
        )
        text, origin = filing_exception_fact(
            text, payload.target_id, target_name, exception
        )
        with world.revision(Source.manual()) as rev:
            fact_id = rev.add_fact(payload.character_id, "ties", text, origin=origin)
            filing = current[index]
            filings = [
                *current[:index],
                filing.model_copy(update={"exceptions": [*filing.exceptions, fact_id]}),
                *current[index + 1 :],
            ]
            rev.set_field(
                payload.character_id,
                "filings",
                [f.model_dump(mode="json") for f in filings],
                filings_since(world, payload.character_id),
            )
        self._edited("add_exception", payload.character_id, at)

    # --- tags -------------------------------------------------------------

    @staticmethod
    def _tags_out(view: WorldView) -> list[dict]:
        return [
            {"tag": tag, "heading": tag_heading(tag), "count": count}
            for tag, count in tags_in_use(view)
        ]

    async def handle_list_tags(self, data: dict):
        """The tags in use (`filing.tags_in_use`), most used first, each
        with its group heading and how many entries carry it: `{tags:
        [{tag, heading, count}]}`, for the tag picker and the Tags tab."""

        self._reply("list_tags", {"tags": self._tags_out(self._require_world().view())})

    async def handle_list_roles(self, data: dict):
        """The filing roles in use (`filing.roles_in_use`), most used
        first: `{roles: [{role, count}]}`, for the role picker."""

        self._reply(
            "list_roles",
            {
                "roles": [
                    {"role": role, "count": count}
                    for role, count in roles_in_use(self._require_world().view())
                ]
            },
        )

    async def handle_set_tag(self, data: dict):
        """Give an entry its one tag (lowercased, its first comma part:
        `kinds.normalise_tag`), or clear it with a null or blank one, in
        one revision. Every page it's filed in regroups it (Connected
        reads the tag). A tag is no prose input: none is scheduled."""

        payload = SetTagPayload(**data)
        world = self._require_world()
        view = world.view()
        state = self._require_entry(view, payload.thing_id)
        tag = normalise_tag(payload.tag or "")
        if tag == (tag_of(state) or ""):
            self._edited("set_tag", payload.thing_id, _date_in(payload.at), prose=False)
            return
        since = view.field_since(payload.thing_id, "tag")
        with world.revision(Source.manual(note="tagged")) as rev:
            if tag:
                rev.set_field(payload.thing_id, "tag", tag, since)
            else:
                rev.remove_field_value(payload.thing_id, "tag", since)
        self._edited("set_tag", payload.thing_id, _date_in(payload.at), prose=False)

    def _retag(self, world: World, old: str, new: str, note: str) -> list[str]:
        """Every tag value `old`, at every date, made `new`, in one
        revision (`Revision.retag`: a deleted entry's too, so undoing its
        delete brings it back retagged); the entries changed, in id
        order."""

        with world.revision(Source.manual(note=note)) as rev:
            return rev.retag(old, new)

    @staticmethod
    def _tags_ever(world: World) -> set[str]:
        """Every tag the world's entries carry at any date, as their own
        or as a filing's `show_under` (a tag that only holds in the past
        is in use too)."""

        found: set[str] = set()
        for state in world.view().things():
            for entry in world.timeline(state.id):
                if entry.change != "field":
                    continue
                if entry.field == "tag" and isinstance(entry.value, str):
                    found.add(normalise_tag(entry.value))
                elif entry.field == "filings" and isinstance(entry.value, list):
                    found.update(
                        normalise_tag(filing["show_under"])
                        for filing in entry.value
                        if isinstance(filing, dict)
                        and isinstance(filing.get("show_under"), str)
                    )
        return found

    def _tag_reply(self, action: str, world: World, changed: list[str], **data) -> None:
        self._reply(
            action,
            {**data, "changed": changed, "tags": self._tags_out(world.view())},
        )

    async def handle_rename_tag(self, data: dict):
        """Rename a tag on every entry that carries it ("school" ->
        "academy"), in one revision, at every date its values hold (a tag
        that only holds in the past can be renamed) and on deleted entries
        too: every page regroups. A tag already in use is refused: that's
        `merge_tag`. Answers `{old, new, changed, tags}` (`changed` the
        entries retagged, `tags` as `list_tags`)."""

        payload = RenameTagPayload(**data)
        world = self._require_world()
        old, new = normalise_tag(payload.old), normalise_tag(payload.new)
        in_use = self._tags_ever(world)
        if not new:
            raise ValueError("a tag needs a name")
        if old not in in_use:
            raise ValueError(f"no entry is tagged {old!r}")
        if new == old:
            self._tag_reply("rename_tag", world, [], old=old, new=new)
            return
        if new in in_use:
            raise ValueError(f"{new!r} is in use already: merge {old!r} into it")
        changed = self._retag(world, old, new, f"tag {old} renamed {new}")
        self._tag_reply("rename_tag", world, changed, old=old, new=new)

    async def handle_merge_tag(self, data: dict):
        """Merge one tag into another in use ("school" into
        "institution"): every entry tagged `from` takes `into`, in one
        revision. Answers `{from, into, changed, tags}`."""

        payload = MergeTagPayload(**data)
        world = self._require_world()
        old, into = normalise_tag(payload.from_), normalise_tag(payload.into)
        in_use = self._tags_ever(world)
        if old not in in_use:
            raise ValueError(f"no entry is tagged {old!r}")
        if into not in in_use:
            raise ValueError(f"no entry is tagged {into!r}: rename {old!r} instead")
        if old == into:
            raise ValueError("a tag can't be merged into itself")
        changed = self._retag(world, old, into, f"tag {old} merged into {into}")
        self._tag_reply("merge_tag", world, changed, **{"from": old, "into": into})

    # --- groups (Task 8) ----------------------------------------------------

    async def handle_group_synopsis(self, data: dict):
        """A group's synopsis (`worldplay.groups.group_synopsis`), cached,
        in the background: asks the model only when nothing fresh is
        cached, or with `force`. Answers `group_synopsis {thing_id, tag,
        synopsis}` ("" for an empty group, or with synopses off) or
        `group_synopsis_failed` (an unusable reply raises rather than
        caching an empty one). Writes nothing. `TALEMATE_TEST_FIXED_GROUP_SYNOPSIS`
        (browser tests) names a file holding the model's reply."""

        payload = GroupSynopsisPayload(**data)
        world = self._require_world()
        self._require_entry(world.view(), payload.thing_id)
        fixed = _fixed_file(FIXED_GROUP_SYNOPSIS_ENV)
        client = self._client() if fixed is None else None
        reply = fixed.read_text(encoding="utf-8") if fixed is not None else None
        self._spawn(
            group_synopsis(
                world,
                payload.thing_id,
                payload.tag,
                client,
                force=payload.force,
                reply=reply,
            ),
            self.create_task_done_callback(
                "group_synopsis",
                "group_synopsis_failed",
                "Error writing a group synopsis",
                success_data=lambda synopsis: {
                    "thing_id": payload.thing_id,
                    "tag": payload.tag,
                    "synopsis": synopsis,
                },
                failure_data={"thing_id": payload.thing_id, "tag": payload.tag},
            ),
        )

    async def handle_group_add(self, data: dict):
        """ "+ Add" in a group, or (with no `tag`) the page's own
        top-level "+ Add" (`worldplay.groups.group_add`), in the
        background: at most 3 draft rows, each ticked, `{name, kind, tag,
        line, ticked}`, for the owner to amend before
        `accept_group_add`. Answers `group_add {thing_id, tag, rows,
        draft_key, version, versions}` (held as a small draft, `group_key`:
        a fresh one, or with `regenerate` a new version of the held one)
        or `group_add_failed`; a reply no longer the latest ask for its key
        is dropped (R2). Writes nothing. `TALEMATE_TEST_FIXED_GROUP_ADD`
        (browser tests) names a file holding the model's reply."""

        payload = GroupAddPayload(**data)
        world = self._require_world()
        self._require_entry(world.view(), payload.thing_id)
        fixed = _fixed_file(FIXED_GROUP_ADD_ENV)
        client = self._client() if fixed is None else None
        reply = fixed.read_text(encoding="utf-8") if fixed is not None else None
        key = group_key(payload.thing_id, payload.tag)
        seq = self._ask_small(key, payload.regenerate)

        def drafted(rows: list[GroupAddRow]) -> dict:
            draft = GroupAddDraft(
                thing_id=payload.thing_id,
                tag=payload.tag,
                prompt=payload.prompt,
                show_under=payload.show_under,
                rows=rows,
            )
            return self._small_add(world, key, draft)

        self._spawn(
            group_add(
                world,
                payload.thing_id,
                payload.tag,
                payload.prompt,
                client,
                reply=reply,
                show_under=payload.show_under,
            ),
            self._small_done(
                key,
                seq,
                self.create_task_done_callback(
                    "group_add",
                    "group_add_failed",
                    "Error adding to a group",
                    success_data=drafted,
                    failure_data={"thing_id": payload.thing_id, "tag": payload.tag},
                ),
            ),
        )

    async def handle_accept_group_add(self, data: dict):
        """Write `group_add`'s ticked rows, each filed in the page with
        its own tag, in one revision (`worldplay.groups.accept_group_add`);
        checked again here, never trusted from the client. A row whose
        name the world already has reuses that entry instead of
        duplicating it; only a genuinely new one becomes a stub. A row's
        filing the store refuses (a cycle, a target gone since) is noted
        rather than silently dropped -- its fact is still written, since
        it's the owner's row. Answers `accept_group_add {..., thing_ids,
        notes, draft_key}` with the page's payload plus each kept row's
        resolved entry id (new or reused). With `draft_key`, that small
        draft is dropped once written, and echoed back so the client
        drops its own slot by key rather than guessing which one
        answered."""

        payload = AcceptGroupAddPayload(**data)
        world = self._require_world()
        self._require_entry(world.view(), payload.thing_id)
        notes: list[str] = []
        thing_ids = accept_group_add(world, payload.thing_id, payload.rows, notes=notes)
        if payload.draft_key is not None:
            self._small.discard(payload.draft_key)
        self._reply(
            "accept_group_add",
            {
                **self._thing_payload(world, payload.thing_id, None),
                "thing_ids": thing_ids,
                "notes": notes,
                "draft_key": payload.draft_key,
            },
        )

    # --- small drafts -------------------------------------------------------

    def _ask_small(self, key: str, regenerate: bool) -> int:
        """Start an ask for the small draft `key` (R2) and return its
        number. A fresh ask drops the slot first, so no older reply still
        out can land in its replacement; a Regenerate keeps it, and its
        reply adds a version."""

        if not regenerate:
            self._small.discard(key)
        return self._small.ask(key)

    def _small_done(
        self, key: str, seq: int, answer: Callable[[asyncio.Task], None]
    ) -> Callable[[asyncio.Task], None]:
        """`answer` a small draft's reply only while its ask is still the
        latest for `key` (R2): once the slot was discarded, replaced,
        asked again or forgotten, the reply (a failure too) is dropped,
        adding no version and answering nothing."""

        def on_done(task: asyncio.Task) -> None:
            self._small.answered(key, seq)
            if not task.cancelled() and not self._small.is_latest(key, seq):
                log.info("worlds.small_draft_dropped", draft_key=key)
                return
            answer(task)

        return on_done

    def _small_add(self, world: World, key: str, draft: pydantic.BaseModel) -> dict:
        """Keep `draft` as the newest version of the small draft `key` and
        answer with it."""

        self._small.add(key, draft)
        return self._small_out(world, key)

    def _small_out(self, world: World, key: str) -> dict:
        """A small draft's current version for the wire, as its own ask
        answers it -- a fact draft `_fact_draft_out` (linked against the
        world as it is now), a nested one `_nested_draft_out`, a group-add
        draft `{thing_id, tag, rows}` --
        plus its `draft_key`, which version it is (1-based) and every
        version kept (`versions`: `[{version, prompt, year}]` for a fact
        draft, `[{version, prompt}]` for a group-add one)."""

        draft = self._small.current(key)
        kept = self._small.versions(key)
        if isinstance(draft, FactDraft):
            out = (
                self._fact_draft_out(world, draft)
                if draft.thing_id is not None
                else self._nested_draft_out(world, key, draft)
            )
            versions = [
                {"version": number, "prompt": version.prompt, "year": version.year}
                for number, version in enumerate(kept, start=1)
                if isinstance(version, FactDraft)
            ]
        elif isinstance(draft, GroupAddDraft):
            out = {
                "thing_id": draft.thing_id,
                "tag": draft.tag,
                "rows": [row.model_dump(mode="json") for row in draft.rows],
            }
            versions = [
                {"version": number, "prompt": version.prompt}
                for number, version in enumerate(kept, start=1)
                if isinstance(version, GroupAddDraft)
            ]
        else:
            raise TypeError(f"not a small draft: {type(draft).__name__}")
        return {
            **out,
            "draft_key": key,
            "version": self._small.index(key) + 1,
            "versions": versions,
        }

    async def handle_use_small_version(self, data: dict):
        """Restore one kept version of a small draft: answers
        `use_small_version` with it as the slot's own ask would
        (`_small_out`), plus `kind` (`facts`, `group` or `nested`, the
        key's own prefix). Writes nothing."""

        payload = UseVersionPayload(**data)
        world = self._require_world()
        self._small.use(payload.draft_key, payload.version)
        self._reply(
            "use_small_version",
            {
                **self._small_out(world, payload.draft_key),
                "kind": payload.draft_key.split(":", 1)[0],
            },
        )

    async def handle_discard_small_draft(self, data: dict):
        """Drop a small draft, every version kept, and any reply still
        out for it; writes nothing. Answers `{draft_key}`."""

        payload = DraftKeyPayload(**data)
        self._small.discard(payload.draft_key)
        self._reply("discard_small_draft", {"draft_key": payload.draft_key})

    # --- prompt additions ---------------------------------------------------

    def _draft_facts(self, action: str, payload: Any, year: int | None) -> None:
        world = self._require_world()
        fixed = _fixed_file(FIXED_FACTS_ENV)
        client = self._client() if fixed is None else None
        reply = fixed.read_text(encoding="utf-8") if fixed is not None else None
        key = payload.draft_key
        if key is not None and self._previews_out.get(key):
            # R7: a Regenerate of the page draft is still out, and would
            # make another version current under the nested draft
            log.info("worlds.facts_wait", draft_key=key)
            self.websocket_handler.queue_put(
                {
                    "type": self.router,
                    "action": f"{action}_failed",
                    "message": "wait for the draft to finish regenerating",
                    "data": {"draft_key": key},
                }
            )
            return
        if key is not None:
            # for the page draft's current version, held as its own nested
            # fact draft (`nested_key`): a fresh one, or with `regenerate`
            # a new version of the held one; `write_nested_facts` puts the
            # ticked facts into the page draft
            preview = self._current_preview(key)
            adding = draft_facts_for(
                world, preview, payload.prompt, client, year=year, reply=reply
            )
            small = nested_key(key)
            seq = self._ask_small(small, payload.regenerate)

            def nested(added: DraftAddition) -> dict:
                draft = FactDraft(
                    thing_id=None,
                    prompt=payload.prompt,
                    year=year,
                    facts=added.facts,
                    new_names=[DraftName(**n.model_dump()) for n in added.new_names],
                )
                return self._small_add(world, small, draft)

            answer = self._small_done(
                small,
                seq,
                self.create_task_done_callback(
                    action,
                    f"{action}_failed",
                    "Error drafting facts",
                    success_data=nested,
                    failure_data={"draft_key": key},
                ),
            )

            def on_done(task: asyncio.Task) -> None:
                # its ask is no longer out, whatever becomes of the reply
                self._small.answered(small, seq)
                done = not task.cancelled() and task.exception() is None
                if done and key not in self._drafts:
                    log.info("worlds.facts_dropped", draft_key=key)
                    return
                if (
                    done
                    and self._small.is_latest(small, seq)
                    and self._current_preview(key) is not preview
                ):
                    # a Regenerate, `use_version` or Discard-and-redraft
                    # made another version current meanwhile: the facts
                    # were drafted for one the owner left, so they join
                    # none, and the owner is told to ask again
                    log.info("worlds.facts_stale", draft_key=key)
                    self.websocket_handler.queue_put(
                        {
                            "type": self.router,
                            "action": f"{action}_failed",
                            "message": "The draft changed to another version"
                            " before the facts came: ask again.",
                            "data": {"draft_key": key, "stale": True},
                        }
                    )
                    return
                answer(task)

            self._spawn(adding, on_done)
            return
        self._require_entry(world.view(), payload.thing_id)
        drafting = draft_facts(
            world, payload.thing_id, payload.prompt, client, year=year, reply=reply
        )
        # held as the page's small draft (`facts_key`): a fresh one, or
        # with `regenerate` a new version of the held one
        small = facts_key(payload.thing_id)
        seq = self._ask_small(small, payload.regenerate)
        self._spawn(
            drafting,
            self._small_done(
                small,
                seq,
                self.create_task_done_callback(
                    action,
                    f"{action}_failed",
                    "Error drafting facts",
                    success_data=lambda draft: self._small_add(world, small, draft),
                    failure_data={"thing_id": payload.thing_id},
                ),
            ),
        )

    def _current_preview(self, key: str) -> CreatePreview:
        """The draft's current version (its server copy)."""

        versions = self._require_draft(key)
        return versions[self._current.get(key, len(versions) - 1)]

    def _nested_draft_out(self, world: World, key: str, draft: FactDraft) -> dict:
        """A nested fact draft for the wire, as `_fact_draft_out` answers a
        fact draft (`thing_id: null`, `draft`, `facts`), plus `nested_in`,
        the page draft's key. Each fact is linked as the page draft would
        link it once written (`_draft_payload` of its current version with
        the facts and new names added): its picks, the names it treats as
        new, its own names "this page" and the new names `fresh`."""

        page = page_key(key)
        preview = self._current_preview(page)
        start = len(preview.facts)
        joined = preview.model_copy(
            update={
                "facts": [*preview.facts, *draft.facts],
                "new_names": [
                    *preview.new_names,
                    *self._nested_names(preview, draft.new_names),
                ],
            }
        )
        rows = [
            row
            for row in self._draft_payload(world, joined)["facts"]
            if row.get("draft") and row["index"] >= start
        ]
        return {
            "thing_id": None,
            "nested_in": page,
            "draft": draft.model_dump(mode="json"),
            "facts": [
                {
                    "index": row["index"] - start,
                    "category": row["category"],
                    "rendered": row["rendered"],
                    "segments": row["segments"],
                    "since": row["valid_from"],
                    "ticked": row["ticked"],
                    "repeat_of": row["repeat_of"],
                }
                for row in rows
            ],
        }

    @staticmethod
    def _nested_names(
        preview: CreatePreview, rows: Sequence[DraftName]
    ) -> list[NewName]:
        """A nested draft's new names (`rows`) as the page draft's own:
        each the page draft doesn't name yet, without its tick."""

        taken = {name_key(row.name) for row in preview.new_names}
        out: list[NewName] = []
        for row in rows:
            if name_key(row.name) in taken:
                continue
            taken.add(name_key(row.name))
            out.append(NewName(**row.model_dump(exclude={"ticked"})))
        return out

    async def handle_write_nested_facts(self, data: dict):
        """Write a page draft's nested fact draft into it, writing nothing
        to the world: its repeat choices are checked against every held
        version of the nested draft (`_check_repeat_moves`), and each
        fact's `repeat_of` is taken from those versions (one none of them
        flagged is dropped, with its "Keep new"); then its ticked facts
        (each keeping its `repeat_of` and "Keep new"), the unticked ones
        a kept "Move existing here" row stands on (unticked) and its
        ticked new names join a copy of the page draft's current version,
        its kept "Move existing here" rows the copy's `move_here`. The
        copy is held as a new version of the page draft (`_new_version`),
        the nested draft is dropped, and `write_nested_facts` answers with
        the page draft (`_draft_out`) plus `notes`."""

        payload = WriteNestedFactsPayload(**data)
        world = self._require_world()
        key = payload.draft_key
        small = nested_key(key)
        if not self._small.held(small):
            raise KeyError(f"no such draft: {small}")
        preview = self._current_preview(key)
        draft = payload.draft
        notes: list[str] = []
        held = [
            fact
            for version in self._small.versions(small)
            for fact in cast(FactDraft, version).facts
        ]
        moves = [
            move
            for move in self._check_repeat_moves(
                draft.facts, draft.move_here, held, notes
            )
            if move.repeat and move.ticked
        ]
        moving = {(move.fact_id, move.from_id) for move in moves}
        # each fact's repeat as the server flagged it, never the client's
        # word: the page draft's accept vouches for its repeat choices
        # against what its held versions say (`_check_page_repeats`), so
        # an unflagged `repeat_of` must not reach them
        flagged = {
            (fact.repeat_of.get("fact_id"), fact.repeat_of.get("owner_id")): (
                fact.repeat_of
            )
            for fact in held
            if fact.repeat_of
        }
        joining: list[PreviewFact] = []
        for fact in draft.facts:
            repeat = fact.repeat_of or {}
            pair = (repeat.get("fact_id"), repeat.get("owner_id"))
            fact.repeat_of = dict(flagged[pair]) if pair in flagged else None
            if fact.repeat_of is None:
                fact.replaces_repeat = False
            # the ticked ones, and an unticked one a kept "Move existing
            # here" row stands on (as on a page draft, accept writes it
            # not, but vouches for the move by it)
            if fact.text.strip() and (fact.ticked or pair in moving):
                joining.append(fact)
        copy = preview.model_copy(deep=True)
        copy.facts.extend(joining)
        copy.new_names.extend(
            self._nested_names(copy, [row for row in draft.new_names if row.ticked])
        )
        copy.move_here = [
            row for row in copy.move_here if (row.fact_id, row.from_id) not in moving
        ] + moves
        self._small.discard(small)
        self._reply(
            "write_nested_facts",
            {**self._new_version(world, key, copy), "notes": notes},
        )

    def _stub_drafted(self, thing_id: str) -> bool:
        """Whether a draft this session holds expands the stub `thing_id`."""

        return any(
            any(version.stub_id == thing_id for version in versions)
            for versions in self._drafts.values()
        )

    def _fact_draft_out(self, world: World, draft: FactDraft) -> dict:
        """A fact draft for the wire: the draft itself (`draft`, sent back
        to `accept_facts`) and each fact as the page shows it, linked as it
        would be (`facts`: `{index, category, rendered, segments, since,
        ticked, repeat_of}`), the entry's own names "this page" (ruling
        H7), as on its page."""

        view = world.view()
        links = _Links(view)
        calendar = world.calendar
        state = view.thing(draft.thing_id)
        own = (
            own_alias_table(state, view.name_of(draft.thing_id) or "")
            if state is not None
            else {}
        )
        return {
            "thing_id": draft.thing_id,
            "draft": draft.model_dump(mode="json"),
            "facts": [
                {
                    "index": index,
                    "category": fact.category,
                    "rendered": fact.text,
                    "segments": _mark_self(
                        links.segments(
                            link_text(view, fact.text, owner=draft.thing_id)
                        ),
                        own,
                    ),
                    "since": _date_out(calendar, fact.since),
                    "ticked": fact.ticked,
                    "repeat_of": fact.repeat_of,
                }
                for index, fact in enumerate(draft.facts)
            ],
        }

    async def handle_add_facts(self, data: dict):
        """ "+ Add facts...": a few facts for the entry from the owner's
        prompt, in the background (`worldplay.facts.draft_facts`): answers
        `add_facts` (a fact draft, `_fact_draft_out`) or
        `add_facts_failed`. Writes nothing: `accept_facts` writes the
        ticked ones. The draft is held as the page's small draft
        (`facts:<thing_id>`, with `draft_key`, `version` and `versions`
        in the reply): a fresh one, or with `regenerate` a new version of
        the held one. With `draft_key` (on a draft page, ruling F16), the
        facts (`facts.draft_facts_for`, for the page draft's current
        version) are held as the page draft's nested fact draft
        (`nested:<draft_key>`, `_nested_draft_out`, with `nested_in`), the
        page draft left as it is: `write_nested_facts` puts the ticked
        ones into a new version of it, and its accept writes them."""

        self._draft_facts("add_facts", AddFactsPayload(**data), None)

    async def handle_add_event(self, data: dict):
        """ "+ Add event...": the entry's dated facts for what happened in
        `year`, from the owner's prompt, as `add_facts` (answers
        `add_event` or `add_event_failed`); each fact dated `year`. With
        `draft_key`, a nested draft of the page draft as `add_facts`
        makes."""

        payload = AddEventPayload(**data)
        WorldDate.of(payload.year)
        self._draft_facts("add_event", payload, payload.year)

    def _held_fact_rows(self, payload: AcceptFactsPayload) -> list[PreviewFact]:
        """The facts of every version of the fact draft `payload` names
        (`draft_key`) this session holds for its entry: what its repeat
        choices are checked against. None without a held draft, so no
        repeat choice is trusted."""

        key = payload.draft_key
        if key is None or not self._small.held(key):
            return []
        return [
            fact
            for version in self._small.versions(key)
            if getattr(version, "thing_id", None) == payload.draft.thing_id
            for fact in getattr(version, "facts", [])
        ]

    async def handle_accept_facts(self, data: dict):
        """Write a fact draft's ticked facts onto its entry, linked as
        `add_fact` links (`worldplay.facts.accept_facts`), in one revision,
        with its repeat choices ("Keep new", "Move existing here") once
        checked against the held versions of the draft (`draft_key`,
        `_check_repeat_moves`); answers `accept_facts` with the entry,
        `fact_ids`, `notes` and `draft_key` (echoed back, so the client
        drops its own slot by key rather than guessing which one
        answered), and refreshes the prose that reads what changed. A
        stub a draft of this session expands is refused: its facts go
        into the draft, and nothing is written before the draft is
        accepted."""

        payload = AcceptFactsPayload(**data)
        world = self._require_world()
        if payload.draft.thing_id is None:
            # a page draft's nested draft (`write_nested_facts`)
            raise ValueError("a page draft's facts are written into the draft")
        self._require_entry(world.view(), payload.draft.thing_id)
        if self._stub_drafted(payload.draft.thing_id):
            raise ValueError(
                "that stub is being drafted: add the facts to its draft"
                " (add_facts with its draft_key), or discard the draft first"
            )
        notes: list[str] = []
        draft = payload.draft
        draft.move_here = self._check_repeat_moves(
            draft.facts, draft.move_here, self._held_fact_rows(payload), notes
        )
        # the other entries whose prose read a fact moved or removed
        prose: list[str] = []
        fact_ids = accept_facts(world, draft, notes, prose)
        if payload.draft_key is not None:
            self._small.discard(payload.draft_key)
        at = _date_in(payload.at)
        self._reply(
            "accept_facts",
            {
                **self._thing_payload(world, draft.thing_id, at),
                "fact_ids": fact_ids,
                "notes": notes,
                "draft_key": payload.draft_key,
            },
        )
        for changed in prose:
            if changed != draft.thing_id:
                self._schedule_prose(changed, None)
        state = world.view().thing(payload.draft.thing_id)
        if (
            state is not None
            and not state.is_stub
            and (
                # its prose reads a fact moved onto it
                draft.thing_id in prose
                or (
                    fact_ids
                    and any(
                        prose_reads(state.kind, fact.category)
                        for fact in draft.facts
                        if fact.ticked
                    )
                )
            )
        ):
            self._schedule_prose(payload.draft.thing_id, at)

    # --- selected words -----------------------------------------------------

    def _selected(
        self, world: World, payload: _Selection
    ) -> tuple[str, FactState, str, int, int, str]:
        """`(owner id, fact, text, start, end, words)`: where the selection
        lies in the fact's stored text (`_raw_span`; `text` is that, with
        the dead links it touches as their words, P5), refusing a fact
        that isn't live or a selection that cuts through a link."""

        view = world.view(_date_in(payload.at))
        found = world.view().fact(payload.fact_id or "")
        if found is None:
            raise KeyError(f"no such fact: {payload.fact_id}")
        owner_id, fact = found
        text, start, end = _raw_span(view, fact.text, payload.start, payload.end)
        return owner_id, fact, text, start, end, text[start:end]

    def _draft_selected(
        self, world: World, payload: _Selection
    ) -> tuple[str, CreatePreview, str]:
        """`(draft key, current version, words)` for a selection in a
        draft's fact (its `index`), refusing one that cuts through a link
        or runs through a link to a deleted thing (P5: the draft writes no
        text to replace it)."""

        key = payload.draft_key or ""
        preview = self._current_preview(key)
        index = payload.index if payload.index is not None else -1
        if not 0 <= index < len(preview.facts):
            raise ValueError(f"the draft has no fact {payload.index}")
        stored = preview.facts[index].text
        view = world.view()
        text, start, end = _raw_span(view, stored, payload.start, payload.end)
        kept = {found.group(0) for found in REF_PATTERN.finditer(text)}
        if any(
            view.thing(found.group(1)) is None and found.group(0) not in kept
            for found in REF_PATTERN.finditer(stored)
        ):
            # a draft keeps its picks by name and writes no text here, so a
            # dead link's words can't be taken out of it (P5)
            raise ValueError(
                "these words were a link to a deleted entry: use them once the"
                " draft is accepted"
            )
        return key, preview, " ".join(text[start:end].split())

    @staticmethod
    def _unnamed(preview: CreatePreview, words: str) -> None:
        """Drop what the draft says the words are (a pick, a new name, a
        name treated as new), before saying it anew."""

        key = name_key(words)
        preview.picks = {w: t for w, t in preview.picks.items() if name_key(w) != key}
        preview.new_names = [n for n in preview.new_names if name_key(n.name) != key]
        preview.treated_as_new = [
            w for w in preview.treated_as_new if name_key(w) != key
        ]
        preview.pick_names = [w for w in preview.pick_names if name_key(w) != key]

    @staticmethod
    def _selected_name(preview: CreatePreview, words: str) -> None:
        """Record words the owner selected on the draft (ruling F26): they
        link as written, capital or not."""

        if not any(name_key(n) == name_key(words) for n in preview.selected_names):
            preview.selected_names.append(words)

    async def handle_make_stub_from_text(self, data: dict):
        """Make a stub of selected words of a fact ("Make a stub"): a stub
        of `kind` with `tag`, named the words (or the entry the world has
        by that name, an ignored stub revived), filed where `filing` says
        when given, and the words made a link to it, in one revision.
        A stub made here is filed as `filing` says; an entry the world has
        by that name keeps its own filings. Answers with the fact's entry
        and `stub_id` (so "Make a stub and expand it now" can expand it).
        Refused, writing nothing: a selection that cuts through a link, the
        entry's own name.

        On a draft (`draft_key` and the fact's `index`, ruling F16) nothing
        is written: the draft's current version gains a new name with the
        kind, tag and filing given, keyed by name (accept makes the stub
        and links the words wherever the draft writes them), and the
        updated draft answers, with `stub_id: null` and `new_name`."""

        payload = MakeStubFromTextPayload(**data)
        world = self._require_world()
        if payload.kind not in KINDS:
            raise ValueError(f"no such kind: {payload.kind!r}")
        if payload.draft_key is not None:
            # a draft's fact (ruling F16): a new name, keyed by name, which
            # accept makes a stub of and links wherever the draft writes it
            key, preview, words = self._draft_selected(world, payload)
            if name_key(words) == name_key(preview.name):
                raise ValueError(f"{words!r} is this entry's own name")
            if payload.filing is not None:
                self._require_entry(world.view(), payload.filing.target_id)
            self._unnamed(preview, words)
            self._selected_name(preview, words)
            preview.new_names.append(
                NewName(
                    name=words,
                    kind=payload.kind,
                    tag=(normalise_tag(payload.tag) or None) if payload.tag else None,
                    filing=(
                        NameFiling(
                            target_id=payload.filing.target_id,
                            role=(payload.filing.role or "").strip() or None,
                        )
                        if payload.filing is not None
                        else None
                    ),
                )
            )
            self._reply(
                "make_stub_from_text",
                {**self._draft_out(world, key), "stub_id": None, "new_name": words},
            )
            return
        owner_id, fact, text, start, end, words = self._selected(world, payload)
        name = " ".join(words.split())
        # stored as the draft path stores it; a blank tag is none
        tag = (normalise_tag(payload.tag) or None) if payload.tag else None
        before = world.view()
        if payload.filing is not None:
            self._require_entry(before, payload.filing.target_id)
        with world.revision(Source.manual(note=f"stub {name}")) as rev:
            made = make_stubs(
                rev,
                world.view(),
                [NewName(name=name, kind=payload.kind, tag=tag)],
            )
            stub_id = made[name]
            if stub_id == owner_id:
                raise ValueError(f"{name!r} is this entry's own name")
            reused = before.thing(stub_id)
            if reused is not None and reused.stub_ignored:
                rev.set_field(stub_id, "stub", {"ignored": False}, None)
            if payload.filing is not None and reused is None:
                self._write_filings(
                    rev,
                    world,
                    stub_id,
                    [
                        Filing(
                            target=payload.filing.target_id,
                            role=(payload.filing.role or "").strip() or None,
                        )
                    ],
                )
            rev.correct_fact(
                fact.fact_id,
                text=text[:start] + ref(stub_id, words) + text[end:],
            )
        log.info("worlds.stub_from_text", id=stub_id, name=name, kind=payload.kind)
        self._reply(
            "make_stub_from_text",
            {
                **self._thing_payload(world, owner_id, _date_in(payload.at)),
                "stub_id": stub_id,
            },
        )

    async def handle_link_text(self, data: dict):
        """Link selected words of a fact to an entry ("Link to an
        entry..."), in one revision, in one of three modes (`LinkMode`):
        "link only" (the default, ruling H2) keeps the words and teaches
        nothing; "add as another name" (P4) keeps the words and teaches
        the target them, spaces normalised, as a common other name
        (`repoint.learn_names`: never one it has or another thing goes
        by); "Rename to..." (`use_name`, one of the target's names) writes
        that name in the words' place, its article fitted
        (`repoint.renamed_words`), teaching nothing. Answers with the
        fact's entry plus `aka_added`. Refused, writing nothing: a
        selection that cuts through a link, a target that's gone, the
        fact's own entry, a name the target hasn't. On a draft (`draft_key`
        and `index`, ruling F16), the draft's current version gains a pick
        of the words for the target, keyed by name, so accept links every
        occurrence of those words in the draft, and the words join its
        `pick_names` ("name" only), which accept teaches the target; "Rename to..."
        waits for the accept (refused). The updated draft answers."""

        payload = LinkTextPayload(**data)
        world = self._require_world()
        mode = _link_mode(payload.mode, payload.use_name, "link")
        self._require_entry(world.view(), payload.target_id)
        if payload.draft_key is not None:
            # a draft's fact (ruling F16): a pick, keyed by name, so accept
            # links every place the draft writes these words
            if mode in ("rename", "retitle"):
                raise ValueError(
                    "on a draft the words can't be renamed yet: rename them"
                    " once it's accepted"
                )
            key, preview, words = self._draft_selected(world, payload)
            if payload.target_id == preview.stub_id:
                raise ValueError("a fact can't link its own entry")
            self._unnamed(preview, words)
            self._selected_name(preview, words)
            preview.picks[words] = payload.target_id
            if mode == "name":
                preview.pick_names.append(words)
            self._reply("link_text", self._draft_out(world, key))
            return
        owner_id, fact, text, start, end, words = self._selected(world, payload)
        if payload.target_id == owner_id:
            raise ValueError("a fact can't link its own entry")
        shown = words
        if payload.use_name is not None:
            name = target_name(world.view(), payload.target_id, payload.use_name)
            shown = renamed_words(name, words, text[:start])
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(
                fact.fact_id,
                text=text[:start] + ref(payload.target_id, shown) + text[end:],
            )
            if mode == "retitle":
                added = retitle(rev, world, payload.target_id, words)
            elif mode == "name":
                added = learn_names(rev, world, payload.target_id, [words])
            else:
                added = []
        at = _date_in(payload.at)
        self._reply(
            "link_text",
            {**self._thing_payload(world, owner_id, at), "aka_added": added},
        )
        if payload.use_name is not None:
            # the fact's words changed
            self._schedule_prose(owner_id, at)
        if mode == "retitle":
            # the target's name changed
            self._schedule_prose(payload.target_id, at)

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
                    "tag": tag_of(state),
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
        """Give a stub another kind (`Revision.change_stub_kind`), in one
        revision. A field the new kind lacks (or has with another type) is
        dropped by the store: the reply's `notes` names each one that had
        a value, beside the stub's payload."""

        payload = ChangeStubKindPayload(**data)
        world = self._require_world()
        state = self._require_stub(world, payload.id)
        if payload.kind not in KINDS:
            raise ValueError(f"no such kind: {payload.kind!r}")
        new_types = {spec.name: spec.type for spec in get_kind(payload.kind).fields}
        old_types = {spec.name: spec.type for spec in get_kind(state.kind).fields}
        dropped = [
            field
            for field, value in state.fields.items()
            if value is not None
            and payload.kind != state.kind
            and new_types.get(field) != old_types.get(field)
        ]
        with world.revision(Source.manual()) as rev:
            rev.change_stub_kind(payload.id, payload.kind)
        notes = [
            f"a {payload.kind} has no {field.replace('_', ' ')}: it was dropped"
            for field in dropped
        ]
        self._reply(
            "change_stub_kind",
            {**self._thing_payload(world, payload.id, None), "notes": notes},
        )

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
        rendered field rewritten (a heritage, a species)."""

        payload = RepointStubPayload(**data)
        world = self._require_world()
        mode = _link_mode(payload.mode, payload.use_name, "name")
        done = repoint_stub(
            world,
            payload.stub_id,
            payload.target_id,
            use_name=payload.use_name,
            teach_names=mode != "link",
            retitle=mode == "retitle",
        )
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

    async def handle_copy_fact(self, data: dict):
        """Copy one fact onto another entry ("Copy to..."), in one revision
        (`repoint.copy_facts` with `keep`: a new fact with its dates,
        origin and holder, the original kept); its links to the target
        become words. Answers `{fact_id, target, notes}` (the copy's id and
        the target's payload). Refused, writing nothing: a fact that isn't
        live, a target that's gone, the fact's own entry. Prose is
        refreshed for the target when it reads the copy's category."""

        payload = CopyFactPayload(**data)
        world = self._require_world()
        view = world.view()
        found = view.fact(payload.fact_id)
        if found is None:
            raise KeyError(f"no such fact: {payload.fact_id}")
        owner_id = found[0]
        target = self._require_entry(view, payload.target_id)
        if owner_id == payload.target_id:
            raise ValueError("the fact is that entry's already")
        notes: list[str] = []
        note = (
            f"copied a fact from {view.name_of(owner_id)} to"
            f" {view.name_of(payload.target_id)}"
        )
        with world.revision(Source.manual(note=note)) as rev:
            new_id = copy_facts(
                rev,
                world.view(),
                [payload.fact_id],
                payload.target_id,
                plain_self_links=True,
                keep=True,
            )[payload.fact_id]
        copied = world.view().fact(new_id)
        category = copied[1].category if copied is not None else found[1].category
        if category != found[1].category:
            notes.append(
                f"a {target.kind} has no {found[1].category} facts:"
                f" it's under {category} on {view.name_of(payload.target_id)}"
            )
        self._reply(
            "copy_fact",
            {
                "fact_id": new_id,
                "target": self._thing_payload(world, payload.target_id, None),
                "notes": notes,
            },
        )
        if not target.is_stub and prose_reads(target.kind, category):
            self._schedule_prose(payload.target_id, None)

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
        raw text) at `to_id`; nothing else in the fact changes. Three modes
        (`LinkMode`): "add as another name" (the default, P4) keeps its
        words and teaches the target them; "link only" (ruling H2) keeps
        them and teaches nothing; "Rename to..." (`use_name`, one of the
        target's names) writes that name in their place, its article
        fitted (`repoint.renamed_words`), teaching only a stub's own names.
        Answers like `correct_fact`, plus `aka_added`."""

        payload = RepointRefPayload(**data)
        world = self._require_world()
        mode = _link_mode(payload.mode, payload.use_name, "name")
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
        if payload.use_name is not None and old is not None:
            name = target_name(view, payload.to_id, payload.use_name)
            rendered = renamed_words(
                name, old.group(2) or rendered, text[: old.start()]
            )
            new_text = (
                text[: old.start()] + ref(payload.to_id, rendered) + text[old.end() :]
            )
        else:
            new_text = repoint_ref(text, payload.occurrence, payload.to_id, rendered)
        # the names the link went by, which the target learns as other
        # names (as `repoint_stub` teaches them): its words, unless another
        # entry goes by them or they're renamed; and a stub's own names
        # only when this was its last reference (it names nothing else, so
        # its names are free)
        from_id = old.group(1) if old else None
        words = (old.group(2) or rendered) if old else ""
        names = [words] if mode == "name" else []
        skip: set[str] = set()
        source = view.thing(from_id) if from_id else None
        if (
            mode != "link"
            and source is not None
            and source.is_stub
            and from_id is not None
        ):
            uses = sum(
                1
                for live in world.live_facts()
                for found in REF_PATTERN.finditer(live.text)
                if found.group(1) == from_id
            )
            if uses <= 1:
                skip = {from_id}
                names += [
                    view.name_of(from_id) or "",
                    *(
                        entry["name"]
                        for entry in source.fields.get("aka") or []
                        if isinstance(entry, dict)
                        and isinstance(entry.get("name"), str)
                    ),
                ]
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(payload.fact_id, text=new_text)
            if mode == "retitle":
                # the stub's last link, and nothing else uses it: it goes,
                # so no two things share the name; else it keeps the name,
                # and the retitle is refused
                removable = bool(skip) and not any(
                    found
                    for kind, found in thing_references(world, from_id or "").items()
                    if kind != "facts"
                )
                added = retitle(
                    rev,
                    world,
                    payload.to_id,
                    words,
                    also=names,
                    skip=skip if removable else frozenset(),
                )
                if removable:
                    rev.remove_thing(from_id or "")
            else:
                added = learn_names(
                    rev,
                    world,
                    payload.to_id,
                    names,
                    skip=skip,
                )
        self._reply(
            "repoint_ref",
            {**self._thing_payload(world, payload.thing_id, at), "aka_added": added},
        )
        if mode == "retitle":
            # the target's name changed
            self._schedule_prose(payload.to_id, at)
        if payload.use_name is not None:
            # the fact's words changed
            self._schedule_prose(payload.thing_id, at)

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
        (`entries.with_held_by`): any live entry (a faith, an order, a
        character), or null for world truth (an explicit clear, so a
        `belief` fact can read plain too). One revision; nothing is written when the fact
        is already held so. Answers with the thing. Held-ness feeds
        description prose (ruling C3): prose is refreshed when the thing's
        prose reads the fact's category (not a place's statement or
        timeline fact, rulings P18, P19)."""

        payload = SetHeldByPayload(**data)
        world = self._require_world()
        at = _date_in(payload.at)
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
        if entries.held_by(view, fact, state) == holder_id:
            self._edited("set_held_by", payload.thing_id, at, prose=False)
            return
        with world.revision(Source.manual()) as rev:
            rev.correct_fact(
                payload.fact_id, origin=entries.with_held_by(fact.origin, holder_id)
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
        world's `date_threshold` (ruling C31); a fact that has ended is in
        no pair (ruling C22), so one ended already is refused. A dropped fact that
        starts at or after now is removed instead of ended, with a note.
        A removed fact's overrides and exceptions (`rejects_fact`) point at
        the kept fact (`merge.repoint_overrides`). Answers `{keep_fact_id,
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
        threshold = world.curation().date_threshold
        if not disagreeing_dates(view, [keep, drop], threshold):
            raise ValueError("those two facts don't disagree on the year")
        owner_id, fact = found
        notes: list[str] = []
        now = current_date(world)
        mode = payload.mode
        # an ended fact is in no pair (ruling C22), so it's refused above
        if mode == "end" and (
            fact.valid_from is not None and fact.valid_from.instant >= now.instant
        ):
            notes.append(
                "That fact starts at or after the world's now, so it's removed "
                "instead of ended"
            )
            mode = "remove"
        with world.revision(Source.manual(note="picked a date")) as rev:
            if mode == "end":
                rev.end_fact(drop, now)
            else:
                rev.remove_fact(drop)
                # what overrode or rejected the removed fact points at the
                # kept one now, as a merge's losers do
                repoint_overrides(rev, world.view(), {drop}, {drop: keep}, {}, notes)
        reply: dict[str, Any] = {
            "keep_fact_id": keep,
            "drop_fact_id": drop,
            # the mode applied: "remove" for one that starts at or after now
            "mode": mode,
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
            owner is not None
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
        """Set one field. Never `filings`, which only the filing actions
        write (`add_filing`, `edit_filing`, `remove_filing`), nor
        the tag (`set_tag`): those are refused here, naming the action
        (`GUARDED_FIELDS`). An event's `place` and an item's `owner` are
        filings (`filing.FIELD_ROLES`): set as the thing's filing with that
        role (`create.file_by_role`)."""

        payload = SetFieldPayload(**data)
        if payload.field in GUARDED_FIELDS:
            raise ValueError(
                f"{payload.field!r} is set with {GUARDED_FIELDS[payload.field]}"
            )
        world = self._require_world()
        state = world.view().thing(payload.thing_id)
        role = FIELD_ROLES.get((state.kind, payload.field)) if state else None
        with world.revision(Source.manual()) as rev:
            if role is not None:
                # an event's place, an item's owner: a filing, never the field
                if payload.value is not None and not isinstance(payload.value, str):
                    raise ValueError(f"{payload.field!r} must be a thing id")
                file_by_role(rev, world, payload.thing_id, role, payload.value)
            elif payload.value is None:
                # a cleared field (a language's "Descends from", languages
                # 3a): its value is removed, not set to nothing
                if state is not None and payload.field in state.fields:
                    rev.remove_field_value(
                        payload.thing_id, payload.field, _date_in(payload.valid_from)
                    )
            else:
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

    # --- languages (languages 3a) -------------------------------------------

    async def handle_language_preview(self, data: dict):
        """What importing a language would give: the file, the shared check
        and its repair note, and, for a new version, what changes."""

        payload = LanguageTextPayload(**data)
        view = self._require_world().view()
        self._require_target(view, payload)
        preview = preview_import(view, payload.text, payload.target_id, payload.base)
        self._reply(
            "language_preview",
            {
                **preview.model_dump(mode="json"),
                "ok": preview.report.ok,
                "repair_note": repair_note(preview.report),
                "target_id": payload.target_id,
            },
        )

    async def handle_language_import(self, data: dict):
        """Import a language as a new entry, or a new version onto
        `target_id`; refused when something must be fixed first."""

        payload = LanguageTextPayload(**data)
        world = self._require_world()
        view = world.view()
        self._require_target(view, payload)
        preview = preview_import(view, payload.text, payload.target_id, payload.base)
        if payload.target_id is not None and _same_language(
            language_of(view.thing(payload.target_id), view), preview.file.language
        ):
            # nothing would change (a second Accept): write nothing
            thing_id = payload.target_id
        else:
            with world.revision(Source.manual(note="import language")) as rev:
                thing_id = apply_import(rev, world.view(), preview, payload.target_id)
        self._edited("language_import", thing_id, _date_in(payload.at), prose=False)

    def _require_target(self, view: WorldView, payload: LanguageTextPayload) -> None:
        """A new version or change needs its language still there."""

        if payload.target_id is None:
            return
        state = view.thing(payload.target_id)
        if state is None or state.kind != "language":
            raise ValueError(LANGUAGE_GONE)

    async def handle_language_export(self, data: dict):
        """The language entry as a file's text."""

        thing_id = str(data.get("thing_id", ""))
        exported = export_language(self._require_world().view(), thing_id)
        self._reply(
            "language_export",
            {"thing_id": thing_id, "text": exported.model_dump_json(indent=2)},
        )

    async def handle_language_samples(self, data: dict):
        """Sample names from each of the language's name rules."""

        payload = LanguageSamplesPayload(**data)
        state = self._require_world().view().thing(payload.thing_id)
        if state is None or state.kind != "language":
            raise ValueError("there's no such language")
        report = check_language(language_of(state), seed=payload.seed)
        self._reply(
            "language_samples",
            {"thing_id": payload.thing_id, "samples": report.samples},
        )

    def _language_reply(self) -> tuple[Any, str | None]:
        fixed = _fixed_file(FIXED_LANGUAGE_ENV)
        if fixed is not None:
            return None, fixed.read_text(encoding="utf-8")
        return self._language_client(), None

    def _naming_world(self, scene: bool = False) -> World:
        """The world naming works in: the world scene's, for the scene's
        message box (whatever world the Worlds tab has open), else the open
        one."""

        if scene:
            context = getattr(
                getattr(self.websocket_handler, "scene", None), "world_context", None
            )
            if context is not None:
                return context.world
        return self._require_world()

    def _language(self, view: WorldView, language_id: str) -> Language:
        state = view.thing(language_id)
        if state is None or state.kind != "language":
            raise ValueError("there's no such language")
        return language_of(state, view)

    async def handle_language_menu(self, data: dict):
        """The languages in reach of an entry for naming (`thing_id`, or
        none for a box with no page): its rows, the default, and every
        language in the world for the picker."""

        if data.get("scene"):
            # the scene's message box: the speaker's languages, then the
            # scene place's; none in a scene with no world
            context = getattr(
                getattr(self.websocket_handler, "scene", None), "world_context", None
            )
            if context is None:
                self._reply(
                    "language_menu",
                    {
                        "thing_id": None,
                        "scene": True,
                        "rows": [],
                        "default": None,
                        "languages": [],
                    },
                )
                return
            view = context.world.view()
            place = context.record.state.get("place_thing_id")
            rows = languages_for_scene(
                view,
                place if isinstance(place, str) else None,
                context.record.player_thing_id,
            )
            self._reply(
                "language_menu",
                {
                    "thing_id": None,
                    "scene": True,
                    "rows": [r.model_dump() for r in rows],
                    "default": rows[0].language_id if rows else None,
                    "languages": [
                        {
                            "id": s.id,
                            "name": s.fields.get("name", ""),
                            "phrases": s.fields.get("phrases") or [],
                            "has_names": _has_name_rules(s),
                        }
                        for s in all_languages(view)
                    ],
                },
            )
            return
        view = self._require_world().view()
        thing_id = data.get("thing_id")
        rows = languages_for(view, thing_id) if thing_id else []
        self._reply(
            "language_menu",
            {
                "thing_id": thing_id,
                "scene": False,
                "rows": [r.model_dump() for r in rows],
                "default": default_language(rows),
                "languages": [
                    {
                        "id": s.id,
                        "name": s.fields.get("name", ""),
                        "phrases": s.fields.get("phrases") or [],
                        "has_names": _has_name_rules(s),
                    }
                    for s in all_languages(view)
                ],
            },
        )

    async def handle_language_names(self, data: dict):
        """Names rolled from the language for an entry kind, each with a
        definition from the model, in the background: answers
        `language_names {language_id, kind, names: [{name, definition}]}`."""

        payload = LanguageNamesPayload(**data)
        view = self._naming_world(payload.scene).view()
        language = self._language(view, payload.language_id)
        exclude = frozenset(payload.exclude) | frozenset(
            str(s.fields.get("name", "")) for s in view.things(facts=False)
        )
        names = roll_names(
            language,
            payload.kind,
            count=payload.count,
            seed=payload.seed,
            exclude=exclude,
        )
        client, reply = self._language_reply()

        async def named() -> list[dict]:
            # names are rolled from the language's rules; only their
            # definitions need a model, so with none they come without
            definitions: dict[str, str] = {}
            if client is not None or reply is not None:
                definitions = await define_names(
                    client, language, names, payload.context, reply=reply
                )
            return [{"name": n, "definition": definitions.get(n, "")} for n in names]

        self._spawn(
            named(),
            self.create_task_done_callback(
                "language_names",
                "language_names_failed",
                "Error making names",
                success_data=lambda found: {
                    "language_id": payload.language_id,
                    "kind": payload.kind,
                    "names": found,
                },
                failure_data={"language_id": payload.language_id},
            ),
        )

    async def handle_language_questions(self, data: dict):
        """Plain questions about what the owner wants a new language to
        sound and feel like, in the background: answers
        `language_questions {questions}` (none without a model)."""

        payload = LanguageQuestionsPayload(**data)
        client, fixed = self._language_reply()
        reply = None
        if fixed is not None:
            # the browser tests' fixed file: its "questions" text, if any
            reply = str(json.loads(fixed).get("questions", ""))

        self._spawn(
            ask_questions(client, payload.text, reply=reply),
            self.create_task_done_callback(
                "language_questions",
                "language_questions_failed",
                "Error asking questions",
                success_data=lambda questions: {"questions": questions},
            ),
        )

    def _make_settings(self) -> MakeSettings:
        """How languages are made, from the language agent's settings; the
        browser tests swap in their fake Claude Code."""

        try:
            settings = instance.get_agent("language").make_settings()
        except KeyError:
            settings = MakeSettings()
        command = os.environ.get(CLAUDE_COMMAND_ENV)
        if command:
            settings = settings.model_copy(update={"claude_command": command})
        return settings

    async def handle_language_related(self, data: dict):
        """Entries a change to a language should fit, each with why:
        answers `language_related {language_id, entries}`."""

        language_id = str(data.get("language_id") or "")
        entries = related_entries(self._require_world().view(), language_id)
        self._reply(
            "language_related",
            {"language_id": language_id, "entries": [e.model_dump() for e in entries]},
        )

    async def handle_language_make_route(self, data: dict):
        """How languages are made now, so the page offers the right
        button: answers `language_make_route {route}`."""

        settings = self._make_settings()
        self._reply(
            "language_make_route",
            {
                "route": settings.route,
                "claude_model": settings.claude_model,
                "sizes": {
                    route: effective_size(MakeRequest(text=""), route)
                    for route in ("claude_code", "in_app", "brief")
                },
            },
        )

    def _settings_for(self, request: MakeRequest) -> MakeSettings:
        """The language agent's settings with this run's choices (the
        dialog's) on top; the agent's own setting is left as it is."""

        settings = self._make_settings()
        update: dict[str, str] = {}
        if request.route is not None:
            update["route"] = request.route
        if request.claude_model is not None:
            update["claude_model"] = request.claude_model
        return settings.model_copy(update=update) if update else settings

    async def handle_language_brief(self, data: dict):
        """The brief for any outside assistant, for the owner to copy:
        answers `language_brief {text}`."""

        request = MakeRequest(**data)
        view = self.world.view() if self.world is not None else None
        size = effective_size(request, self._settings_for(request).route)
        current, used = self._change_inputs(request)
        text = write_brief(view, request, size=size, current=current, used=used)
        self._reply("language_brief", {"text": text})

    async def handle_language_make_start(self, data: dict):
        """Make a language on the language agent's route, in the
        background: `language_make_started {route}`, then
        `language_make_progress {line}` as it goes, and
        `language_make_done {text}` (the file, for the import review) or
        `language_make_failed {error}`. One job at a time."""

        if self._make_task is not None and not self._make_task.done():
            self._reply("language_make_failed", {"error": BUSY})
            return
        if self.world is None:
            self._reply("language_make_failed", {"error": "Open a world first"})
            return
        request = MakeRequest(**data)
        settings = self._settings_for(request)
        current, used = self._change_inputs(request)
        if request.kind != "new" and current is None:
            self._reply("language_make_failed", {"error": LANGUAGE_GONE})
            return
        base = current.model_dump_json() if current is not None else None
        fixed_path = _fixed_file(FIXED_LANGUAGE_ENV)
        fixed = (
            json.loads(fixed_path.read_text(encoding="utf-8")) if fixed_path else None
        )
        client = None if fixed else self._language_client()

        def progress(line: str) -> None:
            self._reply("language_make_progress", {"line": line})

        def done(task: asyncio.Task) -> None:
            if self._make_task is task:
                self._make_task = None
            if task.cancelled():
                # the owner cancelled: `language_make_cancelled` said so
                return
            exc = task.exception()
            if exc is None:
                self._reply(
                    "language_make_done",
                    {
                        "text": task.result(),
                        "kind": request.kind,
                        "target_id": request.target_id,
                        # what the change was briefed on, for the review's merge
                        "base": base,
                    },
                )
            elif isinstance(exc, MakeError):
                self._reply("language_make_failed", {"error": str(exc)})
            else:
                log.error("worlds.language_make_failed", error=str(exc))
                self._reply(
                    "language_make_failed",
                    {"error": f"Something went wrong making the language: {exc}"},
                )

        self._reply(
            "language_make_started",
            {
                "route": settings.route,
                "kind": request.kind,
                "target_id": request.target_id,
            },
        )
        self._make_task = self._spawn(
            make_language(
                self.world.view(),
                request,
                settings,
                client,
                progress,
                fixed=fixed,
                current=current,
                used=used,
            ),
            done,
        )

    def _change_inputs(self, request: MakeRequest):
        """For a change or fill: the language as it is now (as a file) and
        the words the world uses from it; (None, []) when it's gone, or for
        a new language."""

        if request.kind == "new" or not request.target_id or self.world is None:
            return None, []
        view = self.world.view()
        state = view.thing(request.target_id)
        if state is None or state.kind != "language":
            return None, []
        return export_language(view, request.target_id), sorted(
            used_words(view, request.target_id)
        )

    async def handle_language_make_cancel(self, data: dict):
        """Stop the language being made; nothing more comes from it."""

        task, self._make_task = self._make_task, None
        if task is not None and not task.done():
            task.cancel()
        self._reply("language_make_cancelled", {})

    async def handle_language_suggest_definition(self, data: dict):
        """A suggested definition for a word the owner is adding, in the
        background: answers `language_definition {language_id, word,
        definition}`."""

        payload = LanguageWordPayload(**data)
        language = self._language(
            self._naming_world(payload.scene).view(), payload.language_id
        )
        client, reply = self._language_reply()

        async def suggested() -> str:
            if client is None and reply is None:
                # no model to suggest one: the owner writes it
                return ""
            found = await define_names(
                client, language, [payload.word], payload.context, reply=reply
            )
            return found.get(payload.word, "")

        self._spawn(
            suggested(),
            self.create_task_done_callback(
                "language_definition",
                "language_definition_failed",
                "Error suggesting a definition",
                success_data=lambda definition: {
                    "language_id": payload.language_id,
                    "word": payload.word,
                    "definition": definition,
                },
                failure_data={"language_id": payload.language_id, "word": payload.word},
            ),
        )

    async def handle_language_add_word(self, data: dict):
        """Add a word with its meaning to a language (a word already used
        as a name keeps its meaning)."""

        payload = LanguageWordPayload(**data)
        world = self._naming_world(payload.scene)
        with world.revision(Source.manual(note="add word")) as rev:
            add_word(
                rev, world.view(), payload.language_id, payload.word, payload.meaning
            )
        if world is self.world:
            self._edited(
                "language_add_word",
                payload.language_id,
                _date_in(payload.at),
                prose=False,
            )
        else:
            # the scene's world, not the one the Worlds tab shows
            self._reply("language_add_word", {"id": payload.language_id, "scene": True})

    async def handle_language_name_in(self, data: dict):
        """The entry's name in a language, for review, in the background:
        answers `language_name_in {thing_id, language_id, result}`."""

        payload = LanguageNameInPayload(**data)
        view = self._require_world().view()
        client, reply = self._language_reply()
        self._spawn(
            name_in(view, client, payload.thing_id, payload.language_id, reply=reply),
            self.create_task_done_callback(
                "language_name_in",
                "language_name_in_failed",
                "Error naming it in another language",
                success_data=lambda result: {
                    "thing_id": payload.thing_id,
                    "language_id": payload.language_id,
                    "result": result.model_dump(),
                },
                failure_data={
                    "thing_id": payload.thing_id,
                    "language_id": payload.language_id,
                },
            ),
        )

    async def handle_language_apply_name_in(self, data: dict):
        """Keep a reviewed name in another language: an other name marked
        with its language, and its new words."""

        payload = LanguageNameInPayload(**data)
        if payload.result is None:
            raise ValueError("there's no name to keep")
        world = self._require_world()
        with world.revision(Source.manual(note="name in another language")) as rev:
            apply_name_in(
                rev,
                world.view(),
                payload.thing_id,
                payload.language_id,
                NameInResult(**payload.result),
            )
        self._edited(
            "language_apply_name_in",
            payload.thing_id,
            _date_in(payload.at),
            prose=False,
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
