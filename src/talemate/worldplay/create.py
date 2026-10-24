"""Create a world thing from the owner's short prompt: preview, then accept.

`preview_thing` asks the model (`world/create-thing`) to treat the prompt as
intent and invent plausible detail, the way Talemate's `@` action expands a
rough action, then renders prose from the resulting facts
(`prose_gen.render_section`, the `world/thing-prose` template). It writes
nothing: a cancelled preview leaves the world as it was. `accept_preview`
writes the preview in one revision and caches its prose.

The reply parser is built around the create probe's findings
(docs/superpowers/probes/2026-10-19-world-create-and-setup.md):

- facts come back as `{"category", "text", "since"}` or, about half the
  time, as `{"<category>": "text"}`; both are accepted;
- long replies get cut off before the closing bracket, so every complete
  fact object is recovered from a truncated reply, and the count is capped;
- `since` is accepted only as a year of the world's calendar, no later than
  now; anything else ("childhood", "ten years ago", an off-calendar year)
  is an open start;
- a character's age becomes its born year (at least year 1), against the
  world's current date: the later of its latest scene and its present.

The model's own idea of which facts it invented isn't asked for: the probe
showed it can't be relied on.

Species, races and mixes, and characters of a heritage, follow the heritage
create probe (docs/superpowers/probes/2026-10-20-heritage-create.md). The
prompt lists what the new thing will inherit -- the effective facts
(`heritage.effective_facts`) of the thing its fields point at: a
character's `heritage`, a race's `species`, a mix's two `parents` -- each
labelled F1...Fn. The reply marks the inherited facts it makes untrue in
one of two shapes, both read from any reply: per fact, `"overrides":
["F2"]` (characters and mixes), or one top-level `"no_longer_true":
["F4"]` (races, where the probe found per-fact labels missed). A top-level
label goes to the own fact of the same category sharing the most content
words with it, else to the first own fact of that category, else nowhere.
Labels are mapped back to the real fact ids; unknown ones are dropped.
The preview carries the inherited facts it was shown (`inherited`, with
their real ids), so the owner can mark one the model missed as overridden
before accepting.

A heritage kind's `lifespan`, `adult_age` and `measures` come back as
numbers. A `0` (the example's placeholder), a word or a reversed range is
dropped, never raised, and so is a race's number that only repeats its
species' resolved one (it would pin what's inherited anyway).

Names follow the connections probe
(docs/superpowers/probes/2026-10-21-connections.md). The reply also gives
the thing's own other names (`"aka"`) and the proper names its facts use
(`"names"`); `parse_names` reads both, from a cut-off reply too, and
neither list's entries are ever read as facts. The listed names the facts
really use and the world doesn't have yet become stubs on accept
(`_new_names`); capitalised phrases the reply didn't list stay
suggestions. A stub is expanded under its own id, with what its mentions
say as context, and the entries the owner matched in the prompt are shown
as "Named in this prompt".

One writer that tags and files (Filing, docs/superpowers/probes/
2026-10-23-filing.md and its spec). Every branch but the heritage kinds'
lists the entries near the new one (`filing_candidates`, ruling F6: the
context, then what one filing or reference reaches, then the context's
siblings, at most `CREATE_CANDIDATES`; each line `filing_line`) and the
tags in use, and the reply gives:

- its `tag` (`clean_tag`, ruling F8: the first part of a comma-joined tag
  that's no kind's name);
- its "In" rows (`parse_in`), entries it's filed in with a role, arriving
  unticked (ruling F7); a character's carry "but..." exceptions, labelled
  against the items of the entries it may belong in (`homes_block`), as
  Spheres Task 6 had them on ties;
- "File into this" (`file_into_rows`): the reply's `file_into`, the names
  the world has whose `"in"` is this entry, and the near entries whose
  facts name it, all unticked (ruling F7);
- each new name's tag and filing (`listed_names`, `name_filings`): ticked
  (ruling F12), and a name whose kind or tag is a title is no stub (ruling
  F5).

"Could move here" (`move_here_rows`) is found by code, never asked: the
facts near the entry that name it (`names_draft`), less what its own
facts repeat. A prompt hint (`hint_text`, `prompts/templates/world/
hints/`) goes into the prompt, and under the religion, culture or order
hint the `belief` category is offered (ruling F9), whose facts its owner
holds (`entries.held_by`).

Accept writes the tag, the ticked filings (`write_filings`, refusing a
cycle with a note), the ticked "File into this" rows as filings of those
entries, the ticked moves (`repoint.copy_facts`, ruling R1), and the
stubs with their tags and filings, in one revision. A move row is checked
again, never trusted (`move_here_sources`: from an entry near it, a fact
still its own, no summary, naming it). "File into this" rows are the
owner's edits (ruling F13): each is checked for a live entry and a cycle,
but not recomputed, so an entry the owner ticks in is filed there. The
owner's own filings (a create box's, and an event's `place` or an item's
`owner`, `filing.FIELD_ROLES`) become ticked "In" rows (`owner_filings`).

Curation (docs/superpowers/probes/2026-10-22-curation.md, probe 1, and
the owner's rulings on it). The generic branch's reply also gives its
`"elsewhere"` list, facts mainly about the entries near it (or a new
name), which becomes the preview's `elsewhere` (`parse_elsewhere`),
ticked, grouped by entry, each with `default_category`. Repeats are
flagged by code (`repeat_flags`): an own fact whose words a near entry's
fact already holds (the world's `repeat_threshold`) is shown with that
match, and arrives unticked only at `repeat_untick_threshold` or above.
An elsewhere item repeating its target is shown the same way. Accept
writes the ticked own facts, and each ticked elsewhere fact onto its
target (a stub for a new name), in the same revision.

Same thing? (spec goal 4, the curation probe's same-thing verdict, ruling
C2). The preview offers the things the world has that the entry could be
(`same_as`, by `world.sameness.same_candidates`: shared name words, nearby
ones first, at most `SAME_CANDIDATES`), never the stub being filled nor
the matching stub (offered as "fill the stub instead"), and so does each
new stub it would make (`NewName.same_as`), from one read of the world's
names. Only for the entry, and only when its top candidate and the
preview both have facts, the model is asked (`decide.same_thing`) and its
verdict is a hint, never a default (never asked for scene planning's
stub previews, ruling C25). Accept with `same_target_id` puts the
new material onto that entry instead (`accept_preview`); a stub row the
owner marks as some thing (`NewName.same_target_id`) links its name there
and makes no stub.

`json_objects` decodes with `strict=False`: a model sometimes puts a real
line break inside a string (a paragraph break in an "intro") instead of
escaping it, and a strict decoder rejects the whole object over that one
control character. `worldplay.setup` shares this parser rather than its
own copy.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import structlog
from pydantic import BaseModel, Field, model_validator

from talemate.prompts import Prompt
from talemate.world import entries, heritage
from talemate.world.calendar import Calendar, Era
from talemate.world.curation import CurationSettings
from talemate.world.entries import SUMMARY_ORIGIN
from talemate.world.dates import WorldDate
from talemate.world.filing import (
    FIELD_ROLES,
    Filing,
    check_filings,
    filed_index,
    filings_of,
    sits_in,
    tag_of,
    tags_in_use,
)
from talemate.world.kinds import (
    AKA_TAGS,
    HINT_AGENT,
    HERITAGE_KINDS,
    KINDS,
    UNPROMPTED_CATEGORIES,
    get_kind,
    kinds_can_be_one,
    moved_category,
    validate_field,
)
from talemate.world.refs import parse_refs, ref
from talemate.world.repeats import content_words, find_repeats
from talemate.world.sameness import NameIndex, name_index, same_candidates
from talemate.world.names import (
    ARTICLES,
    everyday_name,
    find_names,
    unknown_proper_phrases,
)
from talemate.world.store import Source, World
from talemate.world.view import FactState, ThingState, WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.characters import DEPARTS_FROM, DEPARTS_FROM_TEACHING
from talemate.worldplay.decide import Verdict, preview_label, same_thing
from talemate.worldplay.held import held_text
from talemate.worldplay.links import (
    FALLBACK_KIND,
    NameFiling,
    NewName,
    SameOffer,
    clean_aka,
    existing_id,
    is_new,
    link_text,
    make_stubs,
    name_key,
    name_keys,
)
from talemate.worldplay.mentions import (
    MentionContext,
    entry_label,
    gather_mentions,
    mention_context,
)

log = structlog.get_logger("talemate.worldplay.create")

# the kinds the create box offers
CREATE_KINDS: tuple[str, ...] = (
    "character",
    "place",
    "lore",
    "species",
    "race",
    "mix",
    "event",
    "item",
    "being",
)

# the kinds the reply's "names" may give a name (the prompt lists them);
# an entry with any other kind ("title") is dropped, one with none is lore.
# `name_guess` maps a few others first: "culture", "order" and "office"
# to lore, a god, spirit or deity to a being
NAME_KINDS: tuple[str, ...] = (
    "character",
    "place",
    "species",
    "race",
    "event",
    "item",
    "lore",
    "being",
)

# kinds a reply gives a name that are really another kind
_KIND_GUESSES: dict[str, str] = {
    "culture": "lore",
    "order": "lore",
    "sphere": "lore",
    "office": "lore",
    "god": "being",
    "spirit": "being",
    "deity": "being",
}

# how many facts the prompt asks for, and the most a preview keeps
MIN_FACTS = 8
MAX_FACTS = 12

# the creative-instruction preset, with room for 12 facts, the wrapper and
# the elsewhere list (the plain "create" kind caps out at 1024 tokens,
# which the create probe's longer lists ran past; with the elsewhere list
# the curation probe's replies reached the 2048 cap, Skyfall
# pretty-printing the JSON)
CREATE_PROMPT_KIND = "creative_instruction_3072"
# a mix has no elsewhere list: the size the heritage probe ran at
MIX_PROMPT_KIND = "creative_instruction_2048"

# where a fact with a category the kind doesn't have goes
_FALLBACK_CATEGORY = {"character": "background"}

# keys of a fact object that are never a category in the `{"<category>":
# "text"}` shape -- a measure object, recovered on its own from a cut-off
# reply, has string values too
_NOT_CATEGORY_KEYS = {
    "since",
    "name",
    "age",
    "category",
    "text",
    "facts",
    "overrides",
    "lifespan",
    "adult_age",
    "measures",
    "no_longer_true",
    "unit",
    "min",
    "max",
    "aka",
    "names",
    "ties",
    "role",
    "exceptions",
    "rejects",
    "held_by",
    "entry",
}

# keys only an `aka` entry or a "names" entry has: an object with one is
# never a fact, even when a cut-off reply's fallback finds it on its own
_NAME_ENTRY_KEYS = {"tag", "everyday", "kind"}
# keys only an "in" row or an exception has, likewise
_TIE_KEYS = {"rejects", "exceptions"}
# the key only an elsewhere item has, likewise
_ELSEWHERE_KEYS = {"entry"}

# words that say nothing about a fact's topic, left out of the overlap a
# top-level "no_longer_true" label is attached by
_STOP_WORDS = frozenset(
    "a an and the of to in for with by on at as is are be or from their "
    "they them its it this that than".split()
)
_WORD_RE = re.compile(r"[a-z]+")

_NAME_RE = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
_AKA_LIST_RE = re.compile(r'"aka"\s*:\s*\[')
_NAMES_LIST_RE = re.compile(r'"names"\s*:\s*\[')
_ELSEWHERE_LIST_RE = re.compile(r'"elsewhere"\s*:\s*\[')
_AGE_RE = re.compile(r'"age"\s*:\s*"?(\d{1,4})')
_YEAR_RE = re.compile(r"^\s*(\d{1,4})\s*([^\d\s][^\d]*)?\s*$")

_CREATED_NOTE = "created from prompt"


class PreviewFact(BaseModel):
    category: str
    text: str
    since: WorldDate | None = None
    # its end, when the owner ended it on the draft ("End this")
    until: WorldDate | None = None
    # the fact_ids of the inherited facts this one makes untrue
    overrides: list[str] = Field(default_factory=list)
    # the thing that holds this fact as a belief (`entries.held_by`), set
    # by the owner or mapped from the reply's per-fact `held_by` name
    held_by: str | None = None
    # the fact the world already holds that this one repeats (`Repeat`
    # as `repeat_flags` shows it: `fact_id`, `owner_id`, `owner_name`,
    # `text`, `score`), or None
    repeat_of: dict | None = None
    # whether accept writes it: a repeat at the untick threshold starts
    # unticked
    ticked: bool = True


class ElsewhereFact(BaseModel):
    """A fact a reply wrote about another entry (its `"elsewhere"` list),
    offered as an addition to it: an existing thing (`target_id`), or a
    new name (`new`, a stub accept makes). `category` is
    `default_category`'s until the owner picks another; `held_by` the
    thing that holds it as a belief. A repeat of what the target says
    already carries `repeat_of`, as `PreviewFact` does."""

    target_id: str | None = None
    # the entry's name, as the world has it, or the new name
    target_name: str
    new: NewName | None = None
    category: str
    text: str
    since: WorldDate | None = None
    held_by: str | None = None
    ticked: bool = True
    repeat_of: dict | None = None


class PreviewInherited(BaseModel):
    """One inherited fact the preview was made with, as the model was
    shown it, so the owner can mark it overridden before accepting."""

    fact_id: str
    # the layer it comes from: its name and thing id
    source: str
    source_id: str
    category: str
    text: str


class PreviewException(BaseModel):
    """A "but..." of a person's filing: what the character does
    differently, and what it departs from -- an entry filed in the target
    (`thing_id`) or a fact of the target (`fact_id`), named `item` as the
    prompt showed it."""

    text: str
    item: str
    thing_id: str | None = None
    fact_id: str | None = None


class PreviewFiling(BaseModel):
    """An "In" row: an entry the new one is filed in, with its role and,
    for a person, the "but..." exceptions to it (each written as a `ties`
    fact whose id the filing's `exceptions` hold). The model's arrive
    unticked (ruling F7: "In" missed the bar); the owner's own picks (a
    place's parent, a filing the create box sent) arrive ticked."""

    # the entry it's filed in: one the world has, or (`new_name`, the
    # owner's "+ in..." on a name the world hasn't) a stub accept makes
    # first, with that kind and tag, in the same revision
    target_id: str | None = None
    new_name: NewName | None = None
    # the entry's name, for the owner
    target_name: str
    role: str | None = None
    since: WorldDate | None = None
    # a person's part of the target it belongs in, kept from the owner's
    within: str | None = None
    exceptions: list[PreviewException] = Field(default_factory=list)
    ticked: bool = False

    @model_validator(mode="after")
    def _one_target(self) -> "PreviewFiling":
        if (self.target_id is None) == (self.new_name is None):
            raise ValueError("an In row is a target_id or a new_name")
        return self


class FileIntoRow(BaseModel):
    """A "File into this" row: an entry the world has that looks like it
    belongs in the new one, filed in it on accept when ticked. Always
    offered unticked (ruling F7)."""

    thing_id: str
    name: str
    role: str | None = None
    ticked: bool = False


class MoveHereFact(BaseModel):
    """A "Could move here" row: a live fact of an entry near the new one
    whose text names it, found by code alone (no model call), offered
    unticked. Accept moves a ticked one onto the entry (`copy_facts`,
    ruling R1).

    `repeat`: the owner's "Move that one here" on one of the draft's own
    facts that repeats the world's (its `repeat_of`): the world's fact
    moves onto the entry instead of the draft writing a second copy. Such
    a row needn't be near or name the entry, but must be what one of the
    preview's facts says it repeats (the router checks that against its
    own copy of the draft too)."""

    fact_id: str
    from_id: str
    text: str
    ticked: bool = False
    repeat: bool = False


class CreatePreview(BaseModel):
    kind: str
    prompt: str
    fields: dict[str, Any] = Field(default_factory=dict)
    name: str
    facts: list[PreviewFact]
    prose: dict[str, str]
    # what the new thing will inherit (empty for a kind with no heritage)
    inherited: list[PreviewInherited] = Field(default_factory=list)
    # its own other names, `aka` entries, for the owner to check (the
    # everyday pick is wrong often enough to need a glance)
    aka: list[dict] = Field(default_factory=list)
    # the names its facts use that aren't in the world yet: stubs on accept
    new_names: list[NewName] = Field(default_factory=list)
    # the stub this preview expands, if any
    stub_id: str | None = None
    # a live stub of the same kind and name, offered as "fill the stub
    # instead" (only when no `stub_id` was given)
    matching_stub_id: str | None = None
    # the context the model was given, as `(heading, facts)` groups to show
    # the owner: the stub's mentions, then the entries the prompt names
    context: list[tuple[str, list[str]]] = Field(default_factory=list)
    # the owner's picks for names written in the prompt (written name ->
    # thing id); they win when the facts are linked too
    picks: dict[str, str] = Field(default_factory=dict)
    # names written in the prompt the owner treats as new: never linked to
    # the world's thing of that name, and a stub of their own if listed
    treated_as_new: list[str] = Field(default_factory=list)
    # facts about other entries, grouped by entry
    elsewhere: list[ElsewhereFact] = Field(default_factory=list)
    # the entries the world has that this one could be ("Is this X?"),
    # best first, at most `SAME_CANDIDATES`; accept's `same_target_id` is
    # the owner's answer
    same_as: list[SameOffer] = Field(default_factory=list)
    # the model's verdict on the top candidate (its id -> `Verdict`), a
    # hint beside the question, never a default; None when not asked (the
    # top candidate or the preview has no facts) or the reply gave none
    verdict: dict[str, Verdict] | None = None
    # what the entry is (its one tag, ruling F8: always the owner's to
    # change), and the prompt hint it was written with, if any
    tag: str | None = None
    hint: str | None = None
    # its one-line summary, if the reply gave one: written on accept as
    # its summary fact (else its first own fact is marked so)
    summary: str | None = None
    # "In": where it's filed (`PreviewFiling`)
    filings: list[PreviewFiling] = Field(default_factory=list)
    # "File into this": entries that belong in it (`FileIntoRow`)
    file_into: list[FileIntoRow] = Field(default_factory=list)
    # "Could move here": facts near it that name it (`MoveHereFact`)
    move_here: list[MoveHereFact] = Field(default_factory=list)
    # the draft's earlier generations, kept by the router (Task 6)
    versions: list[CreatePreview] = Field(default_factory=list)
    # words the owner selected on the draft and made a stub of or linked
    # (ruling F26): only these link where they're written without a
    # capital; the router keeps only those its own copy of the draft holds
    selected_names: list[str] = Field(default_factory=list)


# --- the calendar ------------------------------------------------------------


def current_date(world: World) -> WorldDate:
    """The world's "now": the later of where its latest scene got to and
    the world's present (`World.present`), so things made before any scene
    exists still sit at a sensible date."""

    present = world.present()
    latest = world.scenes().latest_end()
    return latest if latest is not None and latest > present else present


def _era_at(calendar: Calendar, year: int) -> Era | None:
    in_force = [era for era in calendar.eras if era.start_year <= year]
    return max(in_force, key=lambda era: era.start_year) if in_force else None


def _shown_year(calendar: Calendar, year: int) -> int:
    """`year` as the calendar numbers it, in the era in force then."""

    era = _era_at(calendar, year)
    return year - era.start_year + 1 if era is not None else year


def _parse_since(value: object, calendar: Calendar, now_year: int) -> WorldDate | None:
    """A fact's `since` as a year-precision date, or `None` (an open start)
    unless it's a year of this calendar no later than now. A bare number is
    read in the era in force now; a number followed by an era's name or
    abbreviation is read in that era."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        shown, era_label = value, None
    elif isinstance(value, str) and (match := _YEAR_RE.match(value)):
        shown, era_label = int(match.group(1)), match.group(2)
    else:
        return None

    if era_label:
        label = era_label.strip().rstrip(".").lower()
        era = next(
            (
                e
                for e in calendar.eras
                if label in {e.name.lower(), e.abbreviation.lower()}
            ),
            None,
        )
        if era is None:
            return None
    else:
        era = _era_at(calendar, now_year)

    year = era.start_year + shown - 1 if era is not None else shown
    if not 1 <= year <= now_year:
        return None
    return WorldDate.of(year)


# --- the reply ---------------------------------------------------------------


def json_objects(text: str) -> list[dict[str, Any]]:
    """Every complete top-level JSON object in `text`, in order. The
    decoder is non-strict, so a raw line break inside a string (the model
    writing a real paragraph break instead of escaping it as "\\n") doesn't
    throw the whole object out. An object that doesn't parse (a reply cut
    off mid-object) is skipped, and the scan carries on inside it, so the
    complete facts of a truncated list are still found.

    Shared with `worldplay.setup`, whose `_reply_object` picks the one
    object shaped like a scene setup out of what this returns."""

    decoder = json.JSONDecoder(strict=False)
    found: list[dict[str, Any]] = []
    index = 0
    while (index := text.find("{", index)) != -1:
        try:
            obj, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index += 1
            continue
        if isinstance(obj, dict):
            found.append(obj)
        # jumps past a successfully parsed object rather than descending
        # into it, so a setup reply (one top-level object) is found whole
        index = end
    return found


def _raw_facts(
    obj: dict[str, Any],
) -> list[tuple[str, str, object, object, object]]:
    """`(category, text, since, overrides, held_by)` from one fact object,
    in either shape."""

    since = obj.get("since")
    overrides = obj.get("overrides")
    held = obj.get("held_by")
    text = obj.get("text")
    if isinstance(text, str):
        return [(str(obj.get("category") or ""), text, since, overrides, held)]
    return [
        (key, value, since, overrides, held)
        for key, value in obj.items()
        if key not in _NOT_CATEGORY_KEYS and isinstance(value, str)
    ]


def _mapped_labels(value: object, labels: dict[str, str]) -> list[str]:
    """The fact ids of the `F1`-style labels in `value` (a list, or one
    label as a string), in order and each once. Unknown labels are
    dropped."""

    items = value if isinstance(value, list) else [value]
    fact_ids: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        fact_id = labels.get(item.strip().upper())
        if fact_id is None:
            log.debug("create.unknown_label", label=item)
        elif fact_id not in fact_ids:
            fact_ids.append(fact_id)
    return fact_ids


def _reply_wrapper(reply: str) -> dict[str, Any] | None:
    """The reply's top-level object -- the one carrying the facts -- or
    `None` when it was cut off or broken."""

    return next(
        (obj for obj in json_objects(reply) if isinstance(obj.get("facts"), list)),
        None,
    )


def _number(value: object) -> int | float | None:
    """A positive number, or `None`: a `0` is the format example's
    placeholder copied as is, and a word ("young") is no number."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if value > 0 else None


def _measure(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    name, unit = value.get("name"), value.get("unit")
    low, high = value.get("min"), value.get("max")
    if not isinstance(name, str) or not name.strip() or not isinstance(unit, str):
        return None
    # a range may start at 0 (tusks "0-0.5 in"), but needs a positive top
    if isinstance(low, bool) or not isinstance(low, (int, float)) or low < 0:
        return None
    high = _number(high)
    if high is None or low > high:
        return None
    return {"name": name.strip(), "min": low, "max": high, "unit": unit.strip()}


def parse_numbers(reply: str) -> dict[str, Any]:
    """The `lifespan`, `adult_age` and `measures` a heritage kind's reply
    gives, as thing fields. A bad number is left out, not raised: a `0`
    placeholder, a word, a negative, or a measure range that's reversed or
    not numbers. A repeated measure name keeps the first."""

    wrapper = _reply_wrapper(reply)
    if wrapper is None:
        return {}
    numbers: dict[str, Any] = {}
    for field in ("lifespan", "adult_age"):
        if (value := _number(wrapper.get(field))) is not None:
            numbers[field] = value
    measures: list[dict[str, Any]] = []
    raw = wrapper.get("measures")
    for item in raw if isinstance(raw, list) else []:
        measure = _measure(item)
        if measure is not None and all(m["name"] != measure["name"] for m in measures):
            measures.append(measure)
    if measures:
        numbers["measures"] = measures
    return numbers


def parse_no_longer_true(reply: str, labels: dict[str, str]) -> list[str]:
    """The fact ids of the top-level `"no_longer_true"` labels; unknown
    labels are dropped. Empty when the reply has no such list, or its
    wrapper broke (the per-fact labels survive with their facts)."""

    wrapper = _reply_wrapper(reply)
    if wrapper is None or "no_longer_true" not in wrapper:
        return []
    return _mapped_labels(wrapper["no_longer_true"], labels)


# categories a create reply's facts never take: a place's timeline,
# summary and statements (`kinds.UNPROMPTED_CATEGORIES`), and a
# character's `ties`, which are exceptions written from its "in" rows alone
_NOT_CREATED_CATEGORIES = (*UNPROMPTED_CATEGORIES, "ties")


def create_categories(kind: str, hint: str | None = None) -> list[str]:
    """The fact categories a `kind` thing is written from a prompt: its
    kind's, less `kinds.UNPROMPTED_CATEGORIES` and `ties` (exceptions come
    from the reply's "in" rows, never its facts). `belief` only under the
    religion, culture or order hint, and first (the probe's v2: then the
    example's first fact is a belief), when the kind has it (ruling F9)."""

    own = get_kind(kind).categories
    base = [
        c
        for c in own
        if c not in _NOT_CREATED_CATEGORIES and c != entries.BELIEF_CATEGORY
    ]
    if hint in BELIEF_HINTS and entries.BELIEF_CATEGORY in own:
        return [entries.BELIEF_CATEGORY, *base]
    return base


def parse_create_reply(
    reply: str,
    kind: str,
    calendar: Calendar,
    now_year: int,
    labels: dict[str, str] | None = None,
    holder: Callable[[str], str | None] | None = None,
    categories: Sequence[str] | None = None,
) -> tuple[str | None, int | None, list[PreviewFact]]:
    """`(name, age, facts)` from a `world/create-thing` reply. `name` and
    `age` are `None` when the reply doesn't give them. At most `MAX_FACTS`
    facts are kept; empty and repeated ones are dropped. A fact's
    `"overrides"` labels are mapped through `labels` (label -> fact id) to
    its `overrides`, and its `"held_by"` name through `holder` (name ->
    thing id, `None` for no known entry) to its `held_by`. The prompt
    doesn't ask for `held_by` (the curation probe 4 fell back to tagging
    by hand); a reply that gives one anyway is read. `categories` are the
    ones the prompt offered (`create_categories`'s, unless given)."""

    if categories is None:
        categories = create_categories(kind)
    fallback = _FALLBACK_CATEGORY.get(kind, "general")

    name: str | None = None
    age: int | None = None
    fact_objects: list[dict[str, Any]] = []
    for obj in json_objects(reply):
        if isinstance(obj.get("facts"), list):
            if isinstance(obj.get("name"), str):
                name = obj["name"]
            if isinstance(obj.get("age"), (int, str)) and str(obj["age"]).isdigit():
                age = int(obj["age"])
            fact_objects.extend(f for f in obj["facts"] if isinstance(f, dict))
        elif not (_NAME_ENTRY_KEYS | _TIE_KEYS | _ELSEWHERE_KEYS) & obj.keys():
            # an `aka`, "names", "in" or "elsewhere" entry a broken
            # wrapper left on its own (the connections probe read one as a
            # fact "common") isn't one
            fact_objects.append(obj)

    # a truncated reply never closes its wrapper object; its name and age
    # are still there before the first fact
    head = reply.split('"facts"', 1)[0]
    if name is None and (match := _NAME_RE.search(head)):
        # non-strict for the same reason as json_objects: a raw line break
        # in the name would otherwise raise here uncaught
        name = json.JSONDecoder(strict=False).decode(f'"{match.group(1)}"')
    if age is None and (match := _AGE_RE.search(head)):
        age = int(match.group(1))

    facts: list[PreviewFact] = []
    seen: set[tuple[str, str]] = set()
    for obj in fact_objects:
        for category, text, since, overrides, held in _raw_facts(obj):
            category = category.strip().lower()
            if category not in categories:
                category = fallback
            text = text.strip()
            if not text or (category, text) in seen:
                continue
            seen.add((category, text))
            facts.append(
                PreviewFact(
                    category=category,
                    text=text,
                    since=_parse_since(since, calendar, now_year),
                    overrides=_mapped_labels(overrides, labels or {}),
                    held_by=(
                        holder(held.strip())
                        if holder is not None and isinstance(held, str) and held.strip()
                        else None
                    ),
                )
            )
    if len(facts) > MAX_FACTS:
        log.info("create.facts_capped", got=len(facts), kept=MAX_FACTS)
    # the format example's placeholder name, copied as is, is no name
    name = name.strip() if name and name.strip(" .") else None
    return name, age, facts[:MAX_FACTS]


def _aka_entries(value: object) -> list[dict[str, Any]]:
    """Other names as `aka` holds them, from a reply's list of `{"name",
    "tag", "everyday"}` objects or plain strings: a tag other than proper
    or common ("former name") becomes proper, and only the first common
    name marked everyday stays everyday. The placeholder "..." and empty
    names are dropped."""

    entries: list[dict[str, Any]] = []
    everyday = False
    for item in value if isinstance(value, list) else []:
        raw = item.get("name") if isinstance(item, dict) else item
        if not isinstance(raw, str):
            continue
        name = " ".join(raw.split())
        if not name.strip(" ."):
            continue
        tag = item.get("tag") if isinstance(item, dict) else None
        tag = tag if tag in AKA_TAGS else "proper"
        is_everyday = (
            isinstance(item, dict)
            and item.get("everyday") is True
            and tag == "common"
            and not everyday
        )
        everyday = everyday or is_everyday
        entries.append({"name": name, "tag": tag, "everyday": is_everyday})
    return entries


def _list_at(text: str, match: re.Match[str] | None) -> list[Any] | None:
    """The JSON list that starts at `match`'s `[`, or, when it was cut off,
    the complete objects inside it. `None` without a match."""

    if match is None:
        return None
    start = match.end() - 1
    try:
        value, _end = json.JSONDecoder(strict=False).raw_decode(text, start)
    except json.JSONDecodeError:
        return json_objects(text[start:])
    return value if isinstance(value, list) else None


def parse_names(reply: str) -> tuple[list[dict[str, Any]], list[NewName]]:
    """`(aka, names)` from a `world/create-thing` reply: the thing's own
    other names, and the proper names its facts use, as the reply gives
    them (`listed_names`; `_new_names` decides which count).

    Both lists are decoded on their own when the wrapper object broke, so
    a cut-off reply keeps them: the thing's `aka` from before the facts,
    and every complete entry of the last `"names"` list."""

    raw_aka, raw_names = _raw_aka_and_names(reply)
    return _aka_entries(raw_aka), [listed.name for listed in listed_names(raw_names)]


def _raw_aka_and_names(reply: str) -> tuple[object, object]:
    """The reply's `aka` and `"names"` lists as written: the wrapper's,
    or, when it broke, the `aka` from before the facts and every complete
    entry of the last `"names"` list."""

    wrapper = _reply_wrapper(reply)
    if wrapper is not None:
        return wrapper.get("aka"), wrapper.get("names")
    head = reply.split('"facts"', 1)[0]
    raw_aka = _list_at(head, _AKA_LIST_RE.search(head))
    last = None
    for last in _NAMES_LIST_RE.finditer(reply):
        pass
    return raw_aka, _list_at(reply, last)


def name_guess(kind: str) -> str:
    """A listed name's kind as a stub guess, from the kind a reply gave it:
    a "culture", "order" or "sphere" (a faith, order or culture) and an
    "office" are lore, a god, spirit or deity a being."""

    kind = kind.strip().lower()
    return _KIND_GUESSES.get(kind, kind)


# a name whose kind or tag is one of these is a title, never an entry
# (ruling F5: 9 of the probe's 10 thin names were labelled so)
TITLE_WORDS: tuple[str, ...] = ("office", "title", "rank")

# words that are never a tag: a kind's name (the probe's "lore, religion")
# and the `aka` tags (v1 tagged names "proper", ruling F8's code rule)
_NOT_TAGS = frozenset((*KINDS, *AKA_TAGS))


def clean_tag(value: object) -> str | None:
    """A reply's tag as stored: lowercase, its first comma-separated part
    that's a tag (ruling F8: "institution, doctrine" is "institution"; a
    kind's name or an `aka` tag is none, so "lore, religion" is
    "religion"), or `None` (the example's "...", nothing usable)."""

    if not isinstance(value, str):
        return None
    for part in value.split(","):
        tag = " ".join(part.split()).strip(" .").lower()
        if tag and tag not in _NOT_TAGS:
            return tag
    return None


class ListedName(NamedTuple):
    """A create reply's "names" entry: the name as a `NewName` (kind, tag
    and other names), and its `"in"` as written, if any."""

    name: NewName
    into: str | None


def listed_names(raw_names: object) -> list[ListedName]:
    """A create reply's "names" list (`ListedName`s). The kind is read as
    `name_guess` reads it (a faith, order or culture is lore); a name whose kind or
    tag is a title word (`TITLE_WORDS`) is dropped (ruling F5); the tag
    goes through `clean_tag`. An entry with no name, the placeholder, and
    an `aka` object a cut-off reply left on its own are skipped."""

    found: list[ListedName] = []
    for item in raw_names if isinstance(raw_names, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        if "everyday" in item or ("tag" in item and "kind" not in item):
            # an `aka` object of an entry that was cut off
            continue
        name = " ".join(item["name"].split())
        if not name.strip(" ."):
            continue
        raw_kind = item.get("kind")
        raw_kind = raw_kind.strip().lower() if isinstance(raw_kind, str) else ""
        raw_tag = item.get("tag")
        raw_tag = raw_tag.strip().lower() if isinstance(raw_tag, str) else ""
        if raw_kind in TITLE_WORDS or raw_tag in TITLE_WORDS:
            log.debug("create.title_name_dropped", name=name)
            continue
        kind = name_guess(raw_kind)
        into = item.get("in")
        found.append(
            ListedName(
                NewName(
                    name=name,
                    kind=kind,
                    aka=_aka_entries(item.get("aka")),
                    tag=clean_tag(item.get("tag")),
                ),
                " ".join(into.split())
                if isinstance(into, str) and into.strip()
                else None,
            )
        )
    return found


# --- the names the facts use -------------------------------------------------


def _written_in(texts: list[str], name: str) -> str | None:
    """How `texts` write `name`, if they do: a whole-word, case-insensitive
    occurrence written with a capital (past a leading article), as
    written."""

    words = name.split()
    pattern = re.compile(
        r"(?<![\w-])" + r"\s+".join(map(re.escape, words)) + r"(?![\w-])",
        re.IGNORECASE,
    )
    for text in texts:
        for hit in pattern.finditer(text):
            written = " ".join(hit.group(0).split())
            first = written.split()[0]
            rest = written.split()[1:]
            if first[:1].isupper() or (
                first.casefold() in ARTICLES and rest and rest[0][:1].isupper()
            ):
                return written
    return None


def _known_in_view(view: WorldView, name: str, kind: str) -> bool:
    """Whether `name` already means a thing in `view` -- by `existing_id`,
    or as a whole name `find_names` matches (a character's first name) --
    or is wholly a suggested part of a thing's name ("Moscavia" of the
    Tsardom of Moscavia), which stays a suggestion. A species, race or mix
    name held by just one other's name isn't: `make_stubs` maps it to that
    one, so the facts link it. Nor is a name that's only another entry's
    adjective form ("Magian" of the Magi)."""

    if existing_id(view, name, kind) is not None:
        return True
    whole = [
        match
        for match in find_names(view, name)
        if (match.start, match.end) == (0, len(name))
        and any(c.via != "adjective" for c in match.candidates)
    ]
    if any(not match.suggested for match in whole):
        return True
    return bool(whole) and existing_id(view, name, kind, held=True) is None


def _written_forms(
    view: WorldView, texts: list[str], name: str, own: set[str]
) -> list[str] | None:
    """The forms the facts write a listed name in, other than the name
    itself: `[]` when the name (or the name without its leading article,
    then `["Night of Feathers"]`) is there as it is; else the longest
    capitalised phrase of the facts that the name holds as whole words
    and that's no name yet (`unknown_proper_phrases`: "Alexei III the
    Feathery" for "Tsar Alexei III the Feathery"). `None` when the facts
    don't use it at all (a name echoed from context, a lowercase coined
    word)."""

    words = name.split()
    tries = [name]
    if len(words) > 1 and words[0].casefold() in ARTICLES:
        tries.append(" ".join(words[1:]))
    for i, attempt in enumerate(tries):
        if _written_in(texts, attempt) is not None:
            return [] if i == 0 else [attempt]

    key = name_key(name)
    parts = [
        phrase.text
        for text in texts
        for phrase in unknown_proper_phrases(view, text)
        if name_key(phrase.text) not in own
        and re.search(
            r"(?<![\w-])" + re.escape(name_key(phrase.text)) + r"(?![\w-])", key
        )
    ]
    if not parts:
        return None
    return [max(parts, key=len)]


def _new_names(
    view: WorldView,
    listed: list[NewName],
    texts: list[str],
    own_names: list[str],
    picked: Sequence[str] = (),
    as_new: Sequence[str] = (),
) -> list[NewName]:
    """The reply's listed names that become stubs on accept, by the
    connections probe's merge rule
    (docs/superpowers/probes/2026-10-21-connections.md, recommendation 2):

    - a name with a kind outside `NAME_KINDS` ("title") is dropped; one
      with no kind is lore;
    - the thing's own names (`own_names`: its name and other names) are
      dropped;
    - a name the facts (`texts`) don't use is dropped; one they write only
      in part keeps that part as a `written` form;
    - a name already in the world (`existing_id`, or a whole `find_names`
      match) is dropped: linking finds it. A name the owner treats as new
      (`as_new`, by `links.is_new`) is kept all the same;
    - a name the owner picked an entry for in the prompt (`picked`, the
      picks' written names), as listed or in a form the facts write it
      in, is dropped: the owner's pick wins, and linking uses it;
    - a name listed twice, or once in full and once as the form the facts
      write it in, is one entry (the first listed).

    Capitalised phrases the reply didn't list stay suggestions, never
    stubs."""

    own = {name_key(name) for name in own_names if name.strip()}
    picks = {name_key(written) for written in picked if written.strip()}
    kept: list[NewName] = []
    # the names, and written forms, of the names kept so far
    claimed: set[str] = set()
    for item in listed:
        kind = item.kind or FALLBACK_KIND
        key = name_key(item.name)
        if not key or kind not in NAME_KINDS or key in own | claimed | picks:
            continue
        if not is_new(item.name, as_new) and _known_in_view(view, item.name, kind):
            continue
        forms = _written_forms(view, texts, item.name, own)
        if forms is None:
            log.debug("create.name_unused", name=item.name)
            continue
        if any(name_key(form) in claimed | picks for form in forms):
            continue
        kept.append(
            NewName(
                name=item.name,
                kind=kind,
                aka=item.aka,
                written=forms,
                tag=item.tag,
                filing=item.filing,
            )
        )
        claimed |= {key, *map(name_key, forms)}
    return kept


# --- what the new thing inherits ---------------------------------------------


class _Inherited(NamedTuple):
    """One inherited fact as the prompt lists it, `- F3 (Snowy, physical):
    text`, with the real fact id its label maps back to."""

    label: str
    fact_id: str
    source: str
    source_id: str
    source_kind: str
    category: str
    text: str


def _lineage_sources(kind: str, fields: dict[str, Any]) -> list[str]:
    """The ids of the things a new `kind` thing inherits from, by its
    `fields`: a character's `heritage`, a race's `species`, a mix's two
    `parents`. Empty for everything else."""

    if kind == "character" and isinstance(fields.get("heritage"), str):
        return [fields["heritage"]]
    if kind == "race" and isinstance(fields.get("species"), str):
        return [fields["species"]]
    if kind == "mix" and isinstance(fields.get("parents"), list):
        return list(fields["parents"])
    return []


def _labelled_facts(view: WorldView, sources: list[str]) -> list[list[_Inherited]]:
    """Each source's effective facts (its own, then what it inherits with
    overrides applied), labelled F1...Fn running on from one source into
    the next. A fact already listed under an earlier source (a species
    both of a mix's parents share) isn't repeated."""

    seen: set[str] = set()
    groups: list[list[_Inherited]] = []
    for source_id in sources:
        group: list[_Inherited] = []
        for fact, layer in heritage.effective_facts(view, source_id):
            if fact.fact_id in seen:
                continue
            seen.add(fact.fact_id)
            group.append(
                _Inherited(
                    label=f"F{len(seen)}",
                    fact_id=fact.fact_id,
                    source=layer.name,
                    source_id=layer.thing_id,
                    source_kind=layer.kind,
                    category=fact.category,
                    # rendered: a linked fact reads as written
                    text=view.render(fact.text),
                )
            )
        groups.append(group)
    return groups


def _preview_rows(rows: list[_Inherited]) -> list[PreviewInherited]:
    return [
        PreviewInherited(
            fact_id=row.fact_id,
            source=row.source,
            source_id=row.source_id,
            category=row.category,
            text=row.text,
        )
        for row in rows
    ]


def preview_inherited(
    view: WorldView, kind: str, fields: dict[str, Any]
) -> list[PreviewInherited]:
    """What a new `kind` thing with `fields` will inherit, as a preview
    lists it: the facts its prompt is shown, in the same order. Sources
    that aren't in the world are skipped."""

    sources = [s for s in _lineage_sources(kind, fields) if view.thing(s) is not None]
    return _preview_rows(
        [row for group in _labelled_facts(view, sources) for row in group]
    )


def heritage_label(view: WorldView, thing_id: str) -> str:
    """How the prompt names a heritage thing: "Snowy (a race of Owl-folk)",
    "Half-orc (a mix of Lowlander and Orc)", "Orc (a species)"."""

    state = view.thing(thing_id)
    name = view.name_of(thing_id) or ""
    if state is None:
        return name
    if state.kind == "race":
        species = state.fields.get("species")
        species_name = view.name_of(species) if isinstance(species, str) else None
        return f"{name} (a race of {species_name})" if species_name else name
    if state.kind == "mix":
        parents = [
            view.name_of(parent) or "" for parent in state.fields.get("parents") or []
        ]
        return f"{name} (a mix of {' and '.join(parents)})"
    return f"{name} (a {state.kind})"


def numbers_line(numbers: heritage.Numbers) -> str:
    """`lifespan 70 years, adult at 12, height 3-4 ft, wingspan 8.5-9 ft`:
    the resolved numbers as the prompt shows them, height first."""

    parts: list[str] = []
    if numbers.lifespan is not None:
        parts.append(f"lifespan {numbers.lifespan:g} years")
    if numbers.adult_age is not None:
        parts.append(f"adult at {numbers.adult_age:g}")
    names = sorted(numbers.measures, key=lambda name: name != "height")
    for name in names:
        measure = numbers.measures[name]
        parts.append(f"{name} {measure.min:g}-{measure.max:g} {measure.unit}")
    return ", ".join(parts) or "none given"


def _without_inherited_numbers(
    numbers: dict[str, Any], inherited: heritage.Numbers
) -> dict[str, Any]:
    """`numbers` less any that only repeat the inherited value: a race
    restating its species' lifespan or height range would pin it, so a
    later change to the species wouldn't reach the race."""

    kept = {
        field: value
        for field, value in numbers.items()
        if field != "measures" and value != getattr(inherited, field)
    }
    measures = [
        measure
        for measure in numbers.get("measures", [])
        if (same := inherited.measures.get(measure["name"])) is None
        or (same.min, same.max, same.unit)
        != (measure["min"], measure["max"], measure["unit"])
    ]
    if measures:
        kept["measures"] = measures
    return kept


def _name_words(names: list[str]) -> set[str]:
    return {
        word.rstrip("s") for name in names for word in _WORD_RE.findall(name.lower())
    }


def _content_words(text: str, skip: set[str]) -> set[str]:
    """`text`'s topic words, singular-ish, without stop words and the
    lineage's names -- every Owl-folk fact says "Owl-folk", which says
    nothing about its topic."""

    words = {word.rstrip("s") for word in _WORD_RE.findall(text.lower())}
    return {w for w in words if len(w) > 2 and w not in _STOP_WORDS and w not in skip}


def _attach_top_level(
    facts: list[PreviewFact],
    fact_ids: list[str],
    inherited: dict[str, _Inherited],
    names: list[str],
) -> None:
    """Attach each top-level `"no_longer_true"` fact id to the own fact of
    the same category sharing the most content words with it -- the first
    of that category when none shares any -- or drop it when the preview
    has no fact of that category."""

    skip = _name_words(names)
    for fact_id in fact_ids:
        target = inherited[fact_id]
        candidates = [fact for fact in facts if fact.category == target.category]
        if not candidates:
            log.debug("create.label_unattached", fact_id=fact_id)
            continue
        target_words = _content_words(target.text, skip)
        # max keeps the first of equals: with no overlap, the first fact
        best = max(
            candidates,
            key=lambda fact: len(_content_words(fact.text, skip) & target_words),
        )
        if fact_id not in best.overrides:
            best.overrides.append(fact_id)


# --- curation: what's near, elsewhere, repeats --------------------------------


# a candidate line's text is cut at this many characters (the probe's)
CANDIDATE_LINE_CHARS = 130

# the format example's elsewhere placeholders, copied as is
_ELSEWHERE_PLACEHOLDER = "A claim mainly about that entry, in a full sentence."

# a target kind's plain category and dated one, where they differ from the
# kind's fallback; never one heritage passes down section by section
_DEFAULT_CATEGORIES: dict[str, tuple[str, str]] = {
    "place": ("general", "history"),
}


def default_category(kind: str, dated: bool) -> str:
    """The category an elsewhere fact goes in on a `kind` target until the
    owner picks another: a place's `general`, or
    `history` when dated; any other kind's `general` -- a character's
    `background`, since it has no `general`."""

    if kind in _DEFAULT_CATEGORIES:
        plain, when = _DEFAULT_CATEGORIES[kind]
        return when if dated else plain
    return _FALLBACK_CATEGORY.get(kind, "general")


def _clip(text: str, limit: int = CANDIDATE_LINE_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "\u2026"


def entry_names(view: WorldView, prefer: Sequence[str] = ()) -> dict[str, str]:
    """`name key -> thing id` over every live thing's name and other names
    (ignoring case and a leading article), read once for a reply's many
    lookups (`entry_named`): the `prefer`red ones (the entries listed as
    near) first, then the first made, each key kept for the first thing
    holding it; an ignored stub never."""

    others = sorted(view.things(), key=lambda thing: thing.created)
    found: dict[str, str] = {}
    for state in [view.thing(thing_id) for thing_id in prefer] + others:
        if state is None or state.stub_ignored:
            continue
        names = [view.name_of(state.id) or ""]
        names += [entry["name"] for entry in _aka_entries(state.fields.get("aka"))]
        for other in names:
            key = name_key(other)
            if key:
                found.setdefault(key, state.id)
    return found


def entry_named(
    view: WorldView,
    name: str,
    prefer: Sequence[str] = (),
    lookup: dict[str, str] | None = None,
) -> str | None:
    """The live thing whose name or other name is `name` (ignoring case and
    a leading article), the `prefer`red ones (the entries listed as near)
    first, then the first made; an ignored stub never; `None` for none.
    `lookup` (`entry_names`, at this view and `prefer`) saves reading the
    world's names again."""

    key = name_key(name)
    if not key:
        return None
    if lookup is None:
        lookup = entry_names(view, prefer)
    return lookup.get(key)


def _opens_with(text: str, names: Sequence[str]) -> bool:
    """Whether `text` opens with one of `names` (ignoring case, with or
    without a leading article) as whole words."""

    for name in names:
        words = name.split()
        if len(words) > 1 and words[0].casefold() in ARTICLES:
            words = words[1:]
        if not words:
            continue
        pattern = (
            r"^\s*(?:(?:the|a|an)\s+)?"
            + r"\s+".join(map(re.escape, words))
            + r"(?![\w-])"
        )
        if re.match(pattern, text, re.IGNORECASE):
            return True
    return False


def _tidy(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def raw_elsewhere(reply: str, wrapper: dict[str, Any] | None) -> object:
    """The reply's `"elsewhere"` list: the wrapper's, or, when it was cut
    off, every complete item of the last `"elsewhere"` list."""

    if wrapper is not None:
        return wrapper.get("elsewhere")
    last = None
    for last in _ELSEWHERE_LIST_RE.finditer(reply):
        pass
    return _list_at(reply, last)


def _grouped(items: list[ElsewhereFact]) -> list[ElsewhereFact]:
    """`items` grouped by the entry they're for, each group where its entry
    first comes, in reply order within it."""

    def key(item: ElsewhereFact) -> str:
        if item.target_id is not None:
            return item.target_id
        return "new:" + name_key(item.target_name)

    groups: dict[str, list[ElsewhereFact]] = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return [item for group in groups.values() for item in group]


def parse_elsewhere(
    raw: object,
    view: WorldView,
    *,
    own_keys: set[str],
    own_ids: set[str],
    listed: Sequence[NewName],
    calendar: Calendar,
    now_year: int,
    prefer: Sequence[str] = (),
    holder: Callable[[str], str | None] | None = None,
) -> list[ElsewhereFact]:
    """The reply's elsewhere items, `{"entry", "text", "held_by"}`, as
    additions to other entries, grouped by entry (`_grouped`):

    - `entry` is matched by name or other name (`entry_named`, the listed
      entries first); an unmatched one is a new stub, its kind as the
      reply's `"names"` lists it, else lore;
    - one about the thing itself (`own_keys`, its names; `own_ids`) is
      dropped, as is a copy of the format example's placeholder, an empty
      one, and a repeat of an item already kept;
    - `since` is read as a fact's, `held_by` through `holder`, and the
      category is `default_category`'s for the target's kind."""

    by_key = {name_key(n.name): n for n in listed}
    # the world's names, read once for every item (final review minor 10)
    lookup: dict[str, str] | None = None
    found: list[ElsewhereFact] = []
    seen: set[tuple[str, str]] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        entry, text = _tidy(item.get("entry")), _tidy(item.get("text"))
        if not entry.strip(" .") or not text or entry.startswith("<"):
            continue
        if text == _ELSEWHERE_PLACEHOLDER:
            continue
        key = name_key(entry)
        if key in own_keys:
            log.debug("create.elsewhere_own", entry=entry)
            continue
        if lookup is None:
            lookup = entry_names(view, prefer)
        target = entry_named(view, entry, prefer, lookup)
        if target is not None and target in own_ids:
            continue
        new: NewName | None = None
        if target is not None:
            state = view.thing(target)
            kind = state.kind if state is not None else FALLBACK_KIND
            name = view.name_of(target) or entry
        else:
            guess = by_key.get(key)
            kind = (
                guess.kind
                if guess is not None and guess.kind in NAME_KINDS
                else FALLBACK_KIND
            )
            new = NewName(
                name=entry,
                kind=kind,
                aka=guess.aka if guess is not None else [],
            )
            name = entry
        slot = (target or "new:" + key, text)
        if slot in seen:
            continue
        seen.add(slot)
        since = _parse_since(item.get("since"), calendar, now_year)
        held = item.get("held_by")
        found.append(
            ElsewhereFact(
                target_id=target,
                target_name=name,
                new=new,
                category=default_category(kind, since is not None),
                text=text,
                since=since,
                held_by=(
                    holder(held.strip())
                    if holder is not None and isinstance(held, str) and held.strip()
                    else None
                ),
            )
        )
    return _grouped(found)


# the fewest content words (`repeats.content_words`) a repeat needs to
# arrive unticked: a short fact ("Pines.") is wholly held by many a
# longer one, so it's only flagged
UNTICK_MIN_WORDS = 3


def repeat_flags(
    view: WorldView,
    texts: Sequence[str],
    owner_ids: Sequence[str],
    settings: CurationSettings,
) -> list[tuple[dict | None, bool]]:
    """For each text, `(repeat_of, ticked)`: the fact of `owner_ids` that
    holds most of its words at the world's `repeat_threshold` or above
    (`repeats.find_repeats`), as `{fact_id, owner_id, owner_name, text,
    score}`, or `None`; and whether it starts ticked -- unticked only when
    the overlap reaches `repeat_untick_threshold` and the text has at least
    `UNTICK_MIN_WORDS` content words."""

    flags: list[tuple[dict | None, bool]] = [(None, True)] * len(texts)
    owners = list(dict.fromkeys(owner_ids))
    if not texts or not owners:
        return flags
    for found in find_repeats(view, list(texts), owners, settings.repeat_threshold):
        flags[found.index] = (
            {
                "fact_id": found.fact_id,
                "owner_id": found.owner_id,
                "owner_name": view.name_of(found.owner_id) or "",
                "text": found.text,
                "score": found.score,
            },
            found.score < settings.repeat_untick_threshold
            or len(content_words(texts[found.index])) < UNTICK_MIN_WORDS,
        )
    return flags


def flag_elsewhere_repeats(
    view: WorldView, items: list[ElsewhereFact], settings: CurationSettings
) -> None:
    """Mark each elsewhere item that repeats what its target already says
    (`repeat_flags`, against the target alone): shown with its match, and
    unticked at the untick threshold."""

    by_target: dict[str, list[ElsewhereFact]] = {}
    for item in items:
        if item.target_id is not None:
            by_target.setdefault(item.target_id, []).append(item)
    for target_id, group in by_target.items():
        flags = repeat_flags(view, [i.text for i in group], [target_id], settings)
        for item, (repeat_of, ticked) in zip(group, flags):
            item.repeat_of, item.ticked = repeat_of, ticked


# --- moving in (spec goal 2) --------------------------------------------------


def prose_reads(kind: str, category: str) -> bool:
    """Whether some section of a `kind` thing's prose is written from its
    `category` facts (`prose_gen.unread_categories`)."""

    return any(
        category not in prose_gen.unread_categories(kind, section)
        for section in prose_gen.sections_for(kind)
    )


# the most same-thing candidates a preview shows (the spec's cap)
SAME_CANDIDATES = 5


def same_offers(
    view: WorldView,
    name: str,
    *,
    near_ids: Sequence[str],
    exclude: Sequence[str] = (),
    index: NameIndex | None = None,
    kind: str | None = None,
) -> list[SameOffer]:
    """The things `name` could be the same as (`same_candidates`, the
    `near_ids` lifted, none of `exclude`), at most `SAME_CANDIDATES`, each
    with its name, kind, candidate line, whether it has facts and whether
    it's a stub. With `kind` (an entry's own question, ruling C34), only
    things that can be one entry with a `kind` thing
    (`kinds.kinds_can_be_one`, as a merge has it), and stubs of any kind
    (ruling C35: a stub's kind is a guess), filtered before the cap; a
    stub row passes none, its kind being a guess."""

    if index is None:
        index = name_index(view)
    offers: list[SameOffer] = []
    for found in same_candidates(
        view,
        name,
        near_ids=near_ids,
        # every match when filtering by kind: the cap is applied after
        limit=SAME_CANDIDATES if kind is None else len(index.names),
        exclude=exclude,
        index=index,
    ):
        if len(offers) >= SAME_CANDIDATES:
            break
        state = view.thing(found.thing_id)
        if state is None:
            continue
        # a stub's kind is only a guess (ruling C35): offered whatever it
        # is, so the owner can fill it rather than leave a duplicate
        if (
            kind is not None
            and not state.is_stub
            and not kinds_can_be_one(kind, state.kind)
        ):
            continue
        offers.append(
            SameOffer(
                **found.model_dump(),
                name=view.name_of(state.id) or "",
                kind=state.kind,
                line=filing_line(view, state),
                has_facts=bool(state.facts),
                stub=state.is_stub,
            )
        )
    return offers


def offer_same(
    view: WorldView,
    rows: Sequence[NewName | dict[str, Any]],
    *,
    near_ids: Sequence[str],
    exclude: Sequence[str] = (),
    index: NameIndex | None = None,
    as_new: Sequence[str] = (),
) -> None:
    """Set each row's same-thing candidates (`same_offers`), from one read
    of the world's names (`index`, read here when not given): a new name's
    `NewName.same_as`, and a dumped row's `"same_as"` when it links no
    thing yet. A name the owner treats as new (`as_new`) gets
    none."""

    if index is None:
        index = name_index(view)
    for row in rows:
        if isinstance(row, NewName):
            name = row.name
        elif row.get("name") and not row.get("thing_id"):
            name = row["name"]
        else:
            continue
        offers = (
            []
            if is_new(name, as_new)
            else same_offers(
                view, name, near_ids=near_ids, exclude=exclude, index=index
            )
        )
        if isinstance(row, NewName):
            row.same_as = offers
        else:
            row["same_as"] = [offer.model_dump() for offer in offers]


def live_elsewhere(
    view: WorldView,
    items: Sequence[ElsewhereFact],
    skip: set[str],
    notes: list[str] | None,
) -> list[ElsewhereFact]:
    """The ticked elsewhere items accept writes: one whose target was
    deleted since the preview is dropped with a note in `notes`, and one
    for a thing in `skip` (the entry being written) is dropped."""

    kept: list[ElsewhereFact] = []
    for item in items:
        if not item.ticked or not item.text.strip():
            continue
        if item.target_id is not None:
            if item.target_id in skip:
                continue
            if view.thing(item.target_id) is None:
                log.info("create.elsewhere_target_gone", target=item.target_id)
                if notes is not None:
                    notes.append(
                        f"{item.target_name} was deleted, so this wasn't added "
                        f"to it: {item.text}"
                    )
                continue
        elif item.new is None:
            continue
        kept.append(item)
    return kept


def write_elsewhere(
    rev: Any,
    linking: WorldView,
    view: WorldView,
    items: Sequence[ElsewhereFact],
    made: dict[str, str],
    *,
    picks: dict[str, str] | None = None,
    as_new: Sequence[str] = (),
    lowercase: Sequence[str] = (),
) -> set[str]:
    """Write each of `items` (from `live_elsewhere`) onto its target in
    `rev`: an existing thing, or the stub `make_stubs` made for its new
    name (in `made`). The text is linked as any fact's, the category kept
    unless the target's kind has no such category (then
    `default_category`'s), with its `since` and its holder (unless the
    holder was deleted). Returns the ids its texts link and the stubs it
    wrote to, so those aren't orphans."""

    linked: set[str] = set()
    for item in items:
        if item.target_id is not None:
            target: str | None = item.target_id
        else:
            assert item.new is not None
            target = made.get(" ".join(item.new.name.split()))
        state = linking.thing(target) if target is not None else None
        if target is None or state is None:
            log.debug("create.elsewhere_no_target", entry=item.target_name)
            continue
        category = item.category
        if category not in get_kind(state.kind).categories:
            category = default_category(state.kind, item.since is not None)
        text = link_text(
            linking,
            item.text,
            picks=picks,
            new_names=made,
            owner=target,
            as_new=as_new,
            lowercase=lowercase,
        )
        linked.update(parse_refs(text))
        linked.add(target)
        held = item.held_by is not None and view.thing(item.held_by) is not None
        rev.add_fact(
            target,
            category,
            text,
            valid_from=item.since,
            origin=entries.with_held_by(None, item.held_by) if held else None,
        )
    return linked


def _generic_branch(kind: str, sources: Sequence[str]) -> bool:
    """Whether `world/create-thing` writes a `kind` thing in its generic
    branch, the one the curation probe tested the elsewhere list in: not a
    species, race or mix, nor a character of a heritage."""

    return kind not in HERITAGE_KINDS and not (kind == "character" and sources)


# --- filing: tags, "In", "File into this", "Could move here" -------------------


# the prompt hints (`prompts/templates/world/hints/<name>.txt`), and those
# under which the `belief` category is offered (ruling F9)
HINTS_DIR = (
    Path(__file__).resolve().parent.parent / "prompts" / "templates" / "world" / "hints"
)
BELIEF_HINTS: tuple[str, ...] = ("religion", "culture", "order")


def hint_names() -> list[str]:
    """The prompt hints there are, by name: each text file in `HINTS_DIR`."""

    return sorted(path.stem for path in HINTS_DIR.glob("*.txt"))


def hint_text(name: str) -> str:
    """The prompt hint's text (`HINTS_DIR/<name>.txt`); `ValueError` for
    one there isn't."""

    if name not in hint_names():
        raise ValueError(f"no such prompt hint: {name!r}")
    return (HINTS_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()


# the most entries the create prompt lists as near (ruling F6, the filing
# probe's list), and the weights its ranking counts links by: a filing
# either way twice a fact reference either way
CREATE_CANDIDATES = 24
_FILING_LINKS = 2
_REFERENCE_LINKS = 1


def _homes(view: WorldView, thing_id: str) -> list[str]:
    """The entries `thing_id` is filed in at the view, each once, and the
    part of one it's filed `within`, if any."""

    found: list[str] = []
    for filing in filings_of(view, thing_id):
        found += [filing.target, *([filing.within] if filing.within else [])]
    return list(dict.fromkeys(found))


def filing_candidates(
    view: WorldView,
    seeds: Sequence[str],
    first: Sequence[str],
    exclude: Collection[str],
    limit: int = CREATE_CANDIDATES,
) -> list[str]:
    """The entries the create prompt lists as near (ruling F6), at most
    `limit`: `first` (the context: where the stub is filed, what mentions
    it, what the prompt names) in order; then every entry one link from a
    seed (`seeds`: the stub and the context), most linked first -- each
    filing between the two, either way, counts `_FILING_LINKS`, each fact
    referencing the other, either way, `_REFERENCE_LINKS`, summed over
    the seeds -- then by name; then the seeds' siblings, entries filed in
    what a seed is filed in (most such homes shared first, then by name),
    which no link of their own reaches (the probe's Frosted Wing, filed
    beside the White Talon in the Tsardom). Never one in `exclude`, a
    removed thing or an ignored stub."""

    index = filed_index(view)
    links: dict[str, int] = {}
    siblings: dict[str, int] = {}

    def add(counts: dict[str, int], thing_id: str, weight: int) -> None:
        counts[thing_id] = counts.get(thing_id, 0) + weight

    for seed in dict.fromkeys(seeds):
        state = view.thing(seed)
        if state is None:
            continue
        homes = _homes(view, seed)
        for home in homes:
            add(links, home, _FILING_LINKS)
        for filed, _filing in index.get(seed, []):
            add(links, filed.id, _FILING_LINKS)
        for fact in state.facts:
            for target in dict.fromkeys(parse_refs(fact.text)):
                add(links, target, _REFERENCE_LINKS)
        for owner_id, _fact in view.referencing(seed):
            add(links, owner_id, _REFERENCE_LINKS)
        for home in homes:
            for filed, _filing in index.get(home, []):
                add(siblings, filed.id, 1)

    def name(thing_id: str) -> str:
        return (view.name_of(thing_id) or "").casefold()

    ranked = sorted(links, key=lambda t: (-links[t], name(t), t))
    sibling_ids = sorted(
        (t for t in siblings if t not in links),
        key=lambda t: (-siblings[t], name(t), t),
    )
    order: list[str] = []
    for thing_id in [*first, *ranked, *sibling_ids]:
        if thing_id in order or thing_id in exclude:
            continue
        state = view.thing(thing_id)
        if state is None or state.stub_ignored:
            continue
        order.append(thing_id)
        if len(order) == limit:
            break
    return order


# the hubs a create prompt with no context at all is shown (ruling F31),
# at most: filing nearness's own cap
HUB_CANDIDATES = CREATE_CANDIDATES


def suggested_in_prompt(
    view: WorldView, prompt: str, as_new: Sequence[str], skip: Collection[str]
) -> list[str]:
    """Ruling F31: the entries the prompt's partial names suggest
    (`find_names`' suggestions, "Tsardom" in "the Tsardom's runes"), each
    its best candidate, once, in order -- never a name treated as new
    (`as_new`), one in `skip`, or an ignored stub. Seeds for a prompt that
    names no entry in full."""

    found: list[str] = []
    for match in find_names(view, prompt):
        if not match.suggested or not match.candidates:
            continue
        if is_new(match.text, as_new):
            continue
        thing_id = match.candidates[0].id
        state = view.thing(thing_id)
        if thing_id in skip or thing_id in found or state is None or state.stub_ignored:
            continue
        found.append(thing_id)
    return found


def hub_entries(
    view: WorldView, exclude: Collection[str], limit: int = HUB_CANDIDATES
) -> list[str]:
    """Ruling F31: the world's hubs, for a create prompt with no seed at
    all -- the entries most filed in (`filed_index`), most first, then by
    name; never one nothing is filed in, one in `exclude`, or an ignored
    stub; at most `limit`."""

    index = filed_index(view)
    counted = [
        (len(rows), thing_id)
        for thing_id, rows in index.items()
        if rows
        and thing_id not in exclude
        and (state := view.thing(thing_id)) is not None
        and not state.stub_ignored
    ]
    counted.sort(key=lambda item: (-item[0], (view.name_of(item[1]) or "").casefold()))
    return [thing_id for _count, thing_id in counted[:limit]]


def filing_line(view: WorldView, state: ThingState) -> str:
    """One entry of the "Entries near this one" list, as the filing probe
    wrote it: "Name (kind, tag; usually called X; in A (role), B; stub):
    its summary or first fact", each part only when it applies, the text
    cut at `CANDIDATE_LINE_CHARS`; a held fact reads as belief (ruling
    C33)."""

    tag = tag_of(state)
    bits = [f"{state.kind}, {tag}" if tag else state.kind]
    everyday = everyday_name(state)
    if everyday:
        bits.append(f"usually called {everyday}")
    homes = [
        f"{view.name_of(f.target) or ''} ({f.role})"
        if f.role
        else view.name_of(f.target) or ""
        for f in filings_of(view, state.id)
    ]
    homes = [home for home in homes if home]
    if homes:
        bits.append("in " + ", ".join(homes))
    if state.is_stub:
        bits.append("stub")
    # its summary fact, if it has one (`entries.is_summary_fact`)
    fact = next((f for f in state.facts if entries.is_summary_fact(f)), None)
    if fact is None and state.facts:
        fact = min(state.facts, key=lambda f: f.created)
    line = (
        _clip(held_text(view, fact, state))
        if fact is not None
        else "(nothing written yet)"
    )
    return f"{view.name_of(state.id)} ({'; '.join(bits)}): {line}"


def tags_line(view: WorldView, skip: str | None = None) -> list[str]:
    """The tags in use (`filing.tags_in_use`), as the prompt lists them,
    most used first: "city (7)". The tag of `skip` (the stub being
    written) isn't counted."""

    counts = dict(tags_in_use(view))
    state = view.thing(skip) if skip is not None else None
    own = tag_of(state) if state is not None else None
    if own is not None and own in counts:
        counts[own] -= 1
    return [
        f"{tag} ({count})"
        for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 0
    ]


# a draft's stand-in id, for matching its names as if the world had it
_DRAFT_ID = "f" * 32


def drafted(
    name: str, aka: Sequence[dict[str, Any]], kind: str, thing_id: str | None
) -> ThingState:
    """The entry being written as `find_names` matches it (its `extra`):
    its name and other names, under its stub's id (or a stand-in)."""

    return ThingState.model_construct(
        id=thing_id or _DRAFT_ID,
        kind=kind,
        fields={"name": name, "aka": list(aka)},
        facts=[],
        created=0,
    )


def names_draft(view: WorldView, raw: str, draft: ThingState) -> bool:
    """Whether a fact's text (`raw`, as stored) names the draft: it
    references its stub, or its rendered words hold the draft's name or
    one of its other names (or a character's first name) as `find_names`
    reads them, never a mere suggestion or an adjective form."""

    if draft.id in parse_refs(raw):
        return True
    text = view.render(raw)
    aka = draft.fields.get("aka")
    forms = [str(draft.fields.get("name") or "")]
    forms += [
        str(entry.get("name") or "")
        for entry in (aka if isinstance(aka, list) else [])
        if isinstance(entry, dict)
    ]
    folded = " ".join(text.split()).casefold()
    if not any((key := name_key(form)) and key.split()[0] in folded for form in forms):
        return False
    return any(
        not match.suggested
        and any(
            c.id == draft.id and c.via in ("name", "aka", "first_name")
            for c in match.candidates
        )
        for match in find_names(view, text, extra=[draft])
    )


def _resolved(
    view: WorldView,
    raw: object,
    *,
    own_keys: set[str],
    own_ids: set[str],
    prefer: Sequence[str],
    lookup: dict[str, str],
) -> Iterable[tuple[dict[str, Any], str]]:
    """Each `{"entry", ...}` item of a reply's list whose entry is one the
    world has (by name or other name, any case, a leading article
    dropped: `entry_named`), with its id, each entry once; one about the
    thing itself, the placeholder, or one that names nothing is dropped."""

    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        entry = _tidy(item.get("entry"))
        if not entry.strip(" .") or entry.startswith("<"):
            continue
        if name_key(entry) in own_keys:
            continue
        target = entry_named(view, entry, prefer, lookup)
        if target is None or target in own_ids or target in seen:
            if target is None:
                log.debug("create.filing_unknown_entry", entry=entry)
            continue
        seen.add(target)
        yield item, target


# the format example's role placeholder, copied as is
_ROLE_PLACEHOLDER = "a few words"


def _role(value: object) -> str | None:
    role = _tidy(value).strip()
    if not role.strip(" .") or role.casefold() == _ROLE_PLACEHOLDER:
        return None
    return role


def _list_in_reply(reply: str, wrapper: dict[str, Any] | None, key: str) -> object:
    """A top-level list of the reply (`key`): the wrapper's, or, when it
    was cut off, every complete item of the last `"<key>": [` list."""

    if wrapper is not None:
        return wrapper.get(key)
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*\[')
    last = None
    for last in pattern.finditer(reply):
        pass
    return _list_at(reply, last)


def parse_in(
    raw: object,
    view: WorldView,
    *,
    own_keys: set[str],
    own_ids: set[str],
    prefer: Sequence[str],
    lookup: dict[str, str],
    calendar: Calendar,
    now_year: int,
    labels: dict[str, "_HomeItem"] | None = None,
) -> list[PreviewFiling]:
    """The reply's "in" list as unticked `PreviewFiling`s (ruling F7):
    each entry resolved as `_resolved` has it, its role tidied (the
    placeholder is none), its `since` read as a fact's. An item's
    `"exceptions"` (`{"text", "rejects"}`) map through `labels` (the
    character's homes block) to an item of that same entry; any other is
    dropped."""

    rows: list[PreviewFiling] = []
    for item, target in _resolved(
        view, raw, own_keys=own_keys, own_ids=own_ids, prefer=prefer, lookup=lookup
    ):
        rows.append(
            PreviewFiling(
                target_id=target,
                target_name=view.name_of(target) or "",
                role=_role(item.get("role")),
                since=_parse_since(item.get("since"), calendar, now_year),
                exceptions=_home_exceptions(
                    item.get("exceptions"), target, labels or {}
                ),
            )
        )
    return rows


def parse_file_into(
    raw: object,
    view: WorldView,
    *,
    own_keys: set[str],
    own_ids: set[str],
    prefer: Sequence[str],
    lookup: dict[str, str],
) -> list[FileIntoRow]:
    """The reply's "file_into" list as unticked `FileIntoRow`s, each entry
    resolved as `_resolved` has it."""

    return [
        FileIntoRow(
            thing_id=target,
            name=view.name_of(target) or "",
            role=_role(item.get("role")),
        )
        for item, target in _resolved(
            view, raw, own_keys=own_keys, own_ids=own_ids, prefer=prefer, lookup=lookup
        )
    ]


def name_filings(
    view: WorldView,
    listed: Sequence[ListedName],
    *,
    own_keys: set[str],
    prefer: Sequence[str],
    lookup: dict[str, str],
) -> tuple[list[NewName], list[str]]:
    """The listed names with their `"in"` read: `(names, into_entry)`.
    Each name's `filing` (`NameFiling`, ticked, ruling F12) is the entry
    it's in -- the entry being written (`this_entry`), one the world has,
    or another listed name -- or none. `into_entry` are the entries the
    world has, listed with this entry as their "in": "File into this"
    rows (ruling F7). Any other "in" of a name the world has is ignored
    (the model re-files existing names)."""

    keys = {name_key(item.name.name) for item in listed}
    names: list[NewName] = []
    into_entry: list[str] = []
    for item in listed:
        new = item.name.model_copy()
        into = name_key(item.into) if item.into else ""
        existing = entry_named(view, new.name, prefer, lookup)
        if existing is not None and name_key(new.name) not in own_keys:
            if into and into in own_keys and existing not in into_entry:
                into_entry.append(existing)
        if into and into != name_key(new.name):
            if into in own_keys:
                new.filing = NameFiling(this_entry=True)
            elif (
                target := entry_named(view, item.into or "", prefer, lookup)
            ) is not None:
                new.filing = NameFiling(target_id=target)
            elif into in keys:
                new.filing = NameFiling(name=item.into)
        names.append(new)
    return names, into_entry


def owner_filings(
    view: WorldView, fields: dict[str, Any], kind: str | None = None
) -> list[PreviewFiling]:
    """The filings the owner's fields give, taken out of `fields`, ticked:
    its `filings`, and for a `kind` thing the fields that are filings (`filing.FIELD_ROLES`: an event's
    `place`, "took place in"; an item's `owner`, "owned by"), each live
    target once."""

    found: list[Filing] = []
    for raw in fields.pop("filings", None) or []:
        try:
            found.append(Filing.model_validate(raw))
        except ValueError:
            continue
    for (field_kind, field), role in FIELD_ROLES.items():
        if field_kind != kind:
            continue
        value = fields.pop(field, None)
        if isinstance(value, str):
            found.append(Filing(target=value, role=role))
    rows: list[PreviewFiling] = []
    for filing in found:
        if view.thing(filing.target) is None or any(
            r.target_id == filing.target for r in rows
        ):
            continue
        rows.append(
            PreviewFiling(
                target_id=filing.target,
                target_name=view.name_of(filing.target) or "",
                role=filing.role or None,
                since=filing.since,
                within=filing.within,
                ticked=True,
            )
        )
    return rows


def naming_facts(
    view: WorldView, near_ids: Sequence[str], draft: ThingState
) -> list[tuple[str, FactState]]:
    """`(owner, fact)` for each live fact of the near entries (never the
    draft's own stub) whose text names the draft (`names_draft`), in the
    list's order, each entry's facts in the order written; never a summary
    (it's its entry's own)."""

    found: list[tuple[str, FactState]] = []
    for thing_id in near_ids:
        state = view.thing(thing_id)
        if state is None or thing_id == draft.id:
            continue
        for fact in sorted(state.facts, key=lambda f: f.created):
            if entries.is_summary_fact(fact):
                continue
            if names_draft(view, fact.text, draft):
                found.append((thing_id, fact))
    return found


def move_here_rows(
    view: WorldView,
    naming: Sequence[tuple[str, FactState]],
    facts: Sequence[PreviewFact],
) -> list[MoveHereFact]:
    """The "Could move here" rows, unticked: the facts near the draft that
    name it (`naming_facts`), less any an own fact already repeats (its
    `repeat_of`)."""

    repeated = {
        fact.repeat_of.get("fact_id") for fact in facts if fact.repeat_of is not None
    }
    return [
        MoveHereFact(fact_id=fact.fact_id, from_id=owner, text=view.render(fact.text))
        for owner, fact in naming
        if fact.fact_id not in repeated
    ]


def code_file_into(
    view: WorldView, owners: Sequence[str], homes: Sequence[str]
) -> list[str]:
    """ "File into this"'s code source (ruling F7): the near entries whose
    facts name the draft (`owners`), each once -- never one the draft
    would itself sit in (ruling F32): one of `homes` (its "In" targets,
    and a stub's own id, whose filings it keeps) or what one of those sits
    in (`filing.sits_in`): filing it there would make the draft hold its
    own container. In the Task 12 session's stored replies this guard
    removed none of the 5 false code rows (each a sibling or an unrelated
    entry: the capital beside its council in the realm, a people in its
    realm) and kept the 3 right ones
    (docs/superpowers/probes/2026-10-24-filing-flow.md, fix round 1)."""

    return [
        owner
        for owner in dict.fromkeys(owners)
        if not any(sits_in(view, home, owner) for home in homes)
    ]


def file_into_rows(
    view: WorldView,
    *rows: Iterable[FileIntoRow | str],
    skip: Collection[str],
    draft_id: str | None,
) -> list[FileIntoRow]:
    """ "File into this", unticked (ruling F7), from its sources in order
    (the model's rows, then ids: the names whose "in" is this entry, the
    near entries whose facts name it), each entry once; never one in
    `skip` (the entry itself, its "In" targets) nor one filed in the draft
    already."""

    filed: set[str] = set()
    if draft_id is not None:
        filed = {state.id for state, _f in filed_index(view).get(draft_id, [])}
    kept: list[FileIntoRow] = []
    for source in rows:
        for row in source:
            if isinstance(row, str):
                row = FileIntoRow(thing_id=row, name=view.name_of(row) or "")
            if (
                row.thing_id in skip
                or row.thing_id in filed
                or view.thing(row.thing_id) is None
                or any(k.thing_id == row.thing_id for k in kept)
            ):
                continue
            kept.append(row.model_copy(update={"ticked": False}))
    return kept


# --- a character's homes: the entries it may be filed in, with their items ----


class _HomeItem(NamedTuple):
    """An item the homes block labels, as an exception's `"rejects"` maps
    back to it: one of the home's facts, or an entry filed in it."""

    home_id: str
    name: str
    thing_id: str | None
    fact_id: str | None


# the most items the homes block shows per entry (ruling P9's)
HOME_ITEMS = 8


def home_entries(
    view: WorldView, picks: dict[str, str], gathered: MentionContext | None
) -> list[str]:
    """The entries a character's prompt shows with their items, so its
    "in" rows can carry exceptions, each once: the lore picked or found
    in the prompt and the lore mentioning the stub being expanded (a
    faith, order, culture or field is lore, as the names rule has it),
    then what a picked place is filed in, lore or place (the Tsardom a
    named city is in)."""

    found: list[str] = []

    def add(thing_id: str, kinds: tuple[str, ...] = ("lore",)) -> None:
        state = view.thing(thing_id)
        if state is not None and thing_id not in found and state.kind in kinds:
            found.append(thing_id)

    for thing_id in picks.values():
        add(thing_id)
    if gathered is not None:
        for mention in gathered.mentioned:
            add(mention.owner_id)
        for about in gathered.about:
            add(about.id)
    for thing_id in picks.values():
        state = view.thing(thing_id)
        if state is not None and state.kind == "place":
            for home in _homes(view, thing_id):
                add(home, ("lore", "place"))
    return found


def homes_block(
    view: WorldView,
    home_ids: Sequence[str],
    cached: Callable[[str], str | None] | None = None,
) -> tuple[list[tuple[str, str, list[tuple[str, str]]]], dict[str, _HomeItem]]:
    """The homes block as the create prompt lists it -- `(heading,
    summary, [(label, line)])` per entry: its summary, then its first
    `HOME_ITEMS` items (its own facts in the order written, a held one
    as belief, `held.held_text`; then what's filed in it, places and
    people left out), labelled S1... across them all -- and what each
    label stands for."""

    index = filed_index(view)
    block: list[tuple[str, str, list[tuple[str, str]]]] = []
    labels: dict[str, _HomeItem] = {}
    for home_id in home_ids:
        state = view.thing(home_id)
        if state is None:
            continue
        lines: list[tuple[str, str]] = []
        items: list[_HomeItem] = []
        for fact in sorted(state.facts, key=lambda f: f.created):
            if entries.is_summary_fact(fact):
                continue
            items.append(
                _HomeItem(
                    home_id, _clip(view.render(fact.text), 60), None, fact.fact_id
                )
            )
            # a held fact as belief, never as plain truth (ruling C33)
            lines.append(("", held_text(view, fact, state)))
        for filed, _filing in index.get(home_id, []):
            if filed.kind == "place" or entries.acts_in_world(filed):
                continue
            name = view.name_of(filed.id) or ""
            fact = entries.summary_fact(filed) or (
                min(filed.facts, key=lambda f: f.created) if filed.facts else None
            )
            text = _clip(view.render(fact.text)) if fact is not None else ""
            what = tag_of(filed) or filed.kind
            items.append(_HomeItem(home_id, name, filed.id, None))
            # a text opening with its name stands alone (ruling P5)
            lines.append(
                (
                    "",
                    text
                    if text and _opens_with(text, [name])
                    else f"{name} ({what})" + (f": {text}" if text else ""),
                )
            )
        shown: list[tuple[str, str]] = []
        for item, (_label, line) in list(zip(items, lines))[:HOME_ITEMS]:
            label = f"S{len(labels) + 1}"
            labels[label] = item
            shown.append((label, line))
        block.append(
            (
                entry_label(
                    view.name_of(home_id) or "",
                    tag_of(state) or state.kind,
                    everyday_name(state),
                ),
                entries.summary(view, home_id, cached(home_id) if cached else None),
                shown,
            )
        )
    return block, labels


def _home_exceptions(
    raw: object, target: str, labels: dict[str, _HomeItem]
) -> list[PreviewException]:
    """An "in" row's exceptions whose `"rejects"` label is an item of its
    own entry; the rest are dropped."""

    found: list[PreviewException] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        text, label = entry.get("text"), entry.get("rejects")
        if not isinstance(text, str) or not text.strip() or not isinstance(label, str):
            continue
        item = labels.get(label.strip().upper())
        if item is None or item.home_id != target:
            log.debug("create.exception_dropped", label=label)
            continue
        found.append(
            PreviewException(
                text=" ".join(text.split()),
                item=item.name,
                thing_id=item.thing_id,
                fact_id=item.fact_id,
            )
        )
    return found


def _live_home_exceptions(
    view: WorldView,
    row: PreviewFiling,
    target_id: str | None = None,
    redirect: Mapping[str, str] | None = None,
    copies: Mapping[str, str] | None = None,
) -> list[PreviewException]:
    """The row's exceptions worth writing: not blank, and departing from
    an item its entry still holds at `view` (a fact still its own, an
    entry still filed in it); one gone since the preview is dropped
    quietly. The entry is `target_id`, where the filing goes, else the
    row's own: under a fold (`redirect`, the folded stub onto the one
    being filled, whose facts moved as `copies`, old id -> new) a row
    into the folded stub is checked against the filled one, and its
    exceptions name the moved copies, so the filing, its exceptions and
    what they depart from agree."""

    if not row.exceptions:
        return []
    moved = redirect or {}
    copied = copies or {}
    entry_id = target_id or row.target_id
    state = view.thing(entry_id)
    fact_ids = {f.fact_id for f in state.facts} if state is not None else set()
    filed = {s.id for s, _f in filed_index(view).get(entry_id, [])}
    found: list[PreviewException] = []
    for exception in row.exceptions:
        if not exception.text.strip():
            continue
        if exception.thing_id is not None:
            thing_id = moved.get(exception.thing_id, exception.thing_id)
            if thing_id in filed:
                found.append(exception.model_copy(update={"thing_id": thing_id}))
            continue
        if exception.fact_id is None:
            found.append(exception)
            continue
        fact_id = copied.get(exception.fact_id, exception.fact_id)
        if fact_id in fact_ids:
            found.append(exception.model_copy(update={"fact_id": fact_id}))
    return found


def filing_exception_fact(
    text: str, target_id: str, target_name: str, exception: PreviewException
) -> tuple[str, dict[str, object]]:
    """An exception's `ties` fact, `(text, origin)`: filed under its entry
    (origin `tie`, ruling P22). One departing from an entry filed in the
    target ends with a reference to it; one departing from the target, or
    a fact of it, references the target, and records the fact
    (`rejects_fact`, ruling P3). Text that references its target already
    is kept as it is."""

    origin: dict[str, object] = {"tie": target_id}
    if exception.thing_id is not None:
        target, shown, lead = exception.thing_id, exception.item, DEPARTS_FROM
    else:
        target, shown, lead = target_id, target_name, DEPARTS_FROM_TEACHING
        if exception.fact_id is not None:
            origin["rejects_fact"] = exception.fact_id
    if target in parse_refs(text):
        return text, origin
    body = text.rstrip()
    if body[-1:] not in (".", "!", "?"):
        body += "."
    try:
        token = ref(target, shown)
    except ValueError:
        token = ref(target)
    return f"{body} {lead} {token}", origin


def filings_since(world: World, thing_id: str) -> WorldDate | None:
    """The date a new `filings` value for `thing_id` holds from: `None`
    (undated) when the field has no dated values -- the thing is made in
    this revision, or was always filed undated -- else the world's now,
    or the latest dated value's date when that's later (a value before it
    would stay hidden behind it)."""

    try:
        timeline = world.timeline(thing_id)
    except KeyError:
        # made in this revision: no history yet
        return None
    dated = [
        entry.date
        for entry in timeline
        if entry.change == "field"
        and entry.field == "filings"
        and entry.date is not None
    ]
    if not dated:
        return None
    since = current_date(world)
    latest = max(dated, key=lambda date: date.instant)
    return latest if since.instant < latest.instant else since


def write_filings(
    rev: Any,
    world: World,
    thing_id: str,
    filings: Sequence[Filing],
    notes: list[str] | None,
) -> None:
    """Add `filings` to the thing's, in `rev` (`filings_since`): each
    whose target it isn't filed in already, and that the store takes
    (`check_filings`: no cycle, a live target); one whose `within` isn't a
    part of its target is filed in the target whole, and one refused is
    left out, with a note."""

    live = world.view()
    state = live.thing(thing_id)
    if state is None:
        return
    current = filings_of(live, thing_id, live=False)
    value = [f.model_dump(mode="json") for f in current]
    name = live.name_of(thing_id) or thing_id
    added = False
    for filing in filings:
        if filing.target == thing_id or any(
            f["target"] == filing.target for f in value
        ):
            continue
        trial = [*value, filing.model_dump(mode="json")]
        errors = check_filings(live, thing_id, trial)
        if errors and filing.within is not None:
            # a part that isn't the target's: filed in the target whole
            filing = filing.model_copy(update={"within": None})
            trial = [*value, filing.model_dump(mode="json")]
            errors = check_filings(live, thing_id, trial)
        if errors:
            if notes is not None:
                where = live.name_of(filing.target) or filing.target
                why = (
                    "it would be inside itself"
                    if any("inside itself" in error for error in errors)
                    else "it can't be filed there"
                )
                notes.append(f"{name} isn't filed in {where}: {why}")
            continue
        value = trial
        added = True
    if added:
        rev.set_field(thing_id, "filings", value, filings_since(world, thing_id))


def file_by_role(
    rev: Any, world: World, thing_id: str, role: str, target_id: str | None
) -> None:
    """The thing's one filing with `role` (a field that is a filing,
    `filing.FIELD_ROLES`: an event's place, an item's owner) set to
    `target_id`, in `rev`, its other filings kept: the old one with that
    role goes, and `None` leaves none. One into an entry it's filed in
    already takes the role. Refused (`ValueError`) as the store refuses
    any filing: a cycle, a target that isn't live."""

    live = world.view()
    current = filings_of(live, thing_id, live=False)
    value = [f for f in current if f.role != role]
    if target_id is not None:
        same = next((i for i, f in enumerate(value) if f.target == target_id), None)
        if same is not None:
            value[same] = value[same].model_copy(update={"role": role})
        else:
            value.append(Filing(target=target_id, role=role))
    if value == current:
        return
    rev.set_field(
        thing_id,
        "filings",
        [f.model_dump(mode="json") for f in value],
        filings_since(world, thing_id),
    )


# --- preview and accept ------------------------------------------------------


# fields every kind has that never reach a prompt as a raw value: other
# names are shown as "(usually called ...)", and the stub marker is
# bookkeeping
_UNSHOWN_FIELDS = {"aka", "stub"}


def _known_fields(
    world: World, fields: dict[str, Any], now: WorldDate
) -> list[tuple[str, str]]:
    """The owner's picks, as `(label, text)` lines for the prompt."""

    calendar = world.calendar
    view = world.view()
    lines: list[tuple[str, str]] = []
    for field, value in fields.items():
        if field in _UNSHOWN_FIELDS:
            continue
        if field == "born":
            born = value if isinstance(value, WorldDate) else WorldDate(**value)
            age = now.to_datetime().year - born.to_datetime().year
            lines.append(("born", f"{calendar.format(born)} (age {age} now)"))
        elif field in ("when", "until"):
            date = value if isinstance(value, WorldDate) else WorldDate(**value)
            lines.append((field, calendar.format(date)))
        elif field == "origin":
            # a species' origin, a place: named, never its id
            lines.append((field, view.name_of(value) or ""))
        elif field in ("heritage", "species", "parents"):
            # the lineage is named in the prompt's own heritage lines
            continue
        else:
            lines.append((field, str(value)))
    return lines


def _mention_lead(name: str, kind: str, category: str, everyday: str | None) -> str:
    """A mentioning fact's lead in the prompt: "Owl-folk (species,
    origin)", or "Owl-folk (species, origin; usually called Owls)"."""

    usually = f"; usually called {everyday}" if everyday else ""
    return f"{name} ({kind}, {category}{usually})"


def _fallback_name(prompt: str) -> str:
    """A name for a preview whose reply gave none: the prompt itself, cut
    at a word boundary. The owner edits it before accepting."""

    text = " ".join(prompt.split())
    if len(text) <= 60:
        return text
    return text[:60].rsplit(" ", 1)[0]


def _live_stub(view: WorldView, stub_id: str) -> Any:
    """The stub `stub_id` (its `ThingState`), or `ValueError` when it was
    deleted or is a full entry."""

    state = view.thing(stub_id)
    if state is None:
        raise ValueError(f"the stub was deleted: {stub_id}")
    if not state.is_stub:
        raise ValueError(f"not a stub: {stub_id}")
    return state


def _named_in_prompt(
    view: WorldView, picks: dict[str, str], skip: str | None
) -> list[tuple[str, str, list[str]]]:
    """`(written, label, facts)` for each entry the owner picked for a name
    in the prompt (but `skip`, the stub being expanded): every fact it has
    at the view's date, rendered (a held one worded as held), as scene setup
    shows them, in its kind's category order, then written order. `ValueError` for a pick that's no thing."""

    named: list[tuple[str, str, list[str]]] = []
    for written, thing_id in picks.items():
        state = view.thing(thing_id)
        if state is None:
            raise ValueError(f"no such thing: {thing_id}")
        if thing_id == skip:
            continue
        label = entry_label(
            view.name_of(thing_id) or "", state.kind, everyday_name(state)
        )
        rank = {c: i for i, c in enumerate(get_kind(state.kind).categories)}
        facts = sorted(
            state.facts,
            key=lambda fact: (
                rank.get(fact.category, len(rank)),
                fact.created,
                fact.fact_id,
            ),
        )
        # a belief worded as held (final review I2)
        named.append((written, label, [held_text(view, f, state) for f in facts]))
    return named


def _found_in_prompt(
    view: WorldView,
    prompt: str,
    picks: dict[str, str],
    as_new: Sequence[str],
    in_context: set[str],
) -> dict[str, str]:
    """The names in `prompt` the owner's `picks` don't cover, each to its
    best match (`find_names`): a Create sent before the screen's matches
    came back still gets them as context. A suggestion, a stub (it has
    nothing to say yet), a name treated as new (`as_new`), and a thing the
    prompt is given anyway (`in_context`: one picked, the stub, what
    mentions it, what's inherited) aren't found."""

    picked = {name_key(written) for written in picks}
    found: dict[str, str] = {}
    for match in find_names(view, prompt):
        key = name_key(match.text)
        thing_id = match.candidates[0].id
        if (
            match.suggested
            or match.candidates[0].stub
            or key in picked
            or thing_id in in_context
            or is_new(match.text, as_new)
        ):
            continue
        picked.add(key)
        in_context.add(thing_id)
        found[match.text] = thing_id
    return found


# --- holders and exceptions ----------------------------------------------------


def cached_summary(world: World, thing_id: str) -> str | None:
    """The entry's summary as last written: its cached `description`
    prose now, or `None` (`entries.summary` falls back to its summary
    fact)."""

    cached = world.prose().get(thing_id, "description", None)
    return cached.text if cached is not None else None


def holder_named(view: WorldView, name: str) -> str | None:
    """The thing that can hold a belief -- a faith, order or culture
    (lore), a character, a being, or any entry written with a prompt hint
    (a nation, which is a place) -- whose name or other name is `name`
    (ignoring case and a leading article), the first made; `None` for
    none."""

    key = name_key(name)
    if not key:
        return None
    for state in sorted(view.things(), key=lambda thing: thing.created):
        if state.kind not in ("character", "being", "lore") and not (
            state.fields.get("hint")
        ):
            continue
        names = [view.name_of(state.id) or ""]
        names += [entry["name"] for entry in _aka_entries(state.fields.get("aka"))]
        if key in {name_key(other) for other in names}:
            return state.id
    return None


def _tidy_name(name: str) -> str:
    return " ".join(name.split())


def _made_id(made: dict[str, str], name: str) -> str | None:
    """The id `make_stubs` (or `_row_stubs`) mapped `name` to, by its
    written form or its `name_key`."""

    found = made.get(_tidy_name(name))
    if found is not None:
        return found
    key = name_key(name)
    return next((i for form, i in made.items() if name_key(form) == key), None)


def matching_stub(view: WorldView, kind: str, name: str) -> str | None:
    """A live stub of `kind` whose name or other name is `name` (ignoring
    case and a leading article), if any."""

    key = name_key(name)
    for state in view.things(kind):
        if not state.is_stub:
            continue
        names = [view.name_of(state.id) or ""]
        names += [entry["name"] for entry in _aka_entries(state.fields.get("aka"))]
        if key in {name_key(other) for other in names}:
            return state.id
    return None


async def preview_thing(
    world: World,
    kind: str,
    prompt: str,
    fields: dict[str, Any],
    client: Any,
    *,
    stub_id: str | None = None,
    picks: dict[str, str] | None = None,
    new_names: Sequence[str] = (),
    ask_same: bool = True,
    hint: str | None = None,
) -> CreatePreview:
    """Create a `kind` thing from `prompt` -- facts, then prose -- without
    writing anything to the world. With `ask_same` false, no same-thing
    verdict is asked (scene planning's stub previews, ruling C25: nobody
    sees it). `fields` are the owner's picks (`name`, `born`, a race's
    `species`, ...), kept as given; an `aka` among them is the preview's
    other names, a `tag` its tag, and a `stub` marker is dropped. Where
    the owner files it (`filings`, an event's `place`, an item's
    `owner`) become ticked "In" rows (`owner_filings`).

    `hint` names a prompt hint (`hint_names`): its text goes into the
    prompt, and under the religion, culture or order hint the `belief`
    category is offered (`create_categories`, ruling F9), whose facts are
    held by the entry itself (`entries.held_by`). An unknown hint is a
    `ValueError`.

    A mix needs its two `parents`, and only a mix may have an empty
    `prompt`: two parents are enough to draft one from. A race needs its
    `species`. A character with a `heritage`, a race and a mix are shown
    what they inherit, and may mark inherited facts as overridden.

    Context, from the connections probe
    (docs/superpowers/probes/2026-10-21-connections.md):

    - with a `stub_id`, the stub is expanded: its kind and name are used
      (`kind` is ignored; a `name` in `fields` still wins), and the prompt
      gets what its mentions say (`mentions.gather_mentions`). A deleted
      stub, or a full entry, is a `ValueError`;
    - `picks` maps a name written in the prompt to the entry the owner
      matched it to; each entry's facts go in a "Named in this prompt"
      block, which keeps the model from inventing a duplicate. A name in
      the prompt the picks don't cover is matched here (`find_names`);
    - an entry with an everyday name is shown "Name (kind, usually called
      X)";
    - `new_names` are names written in the prompt the owner treats as new
      ("treat as new"): a pick for one is dropped, so it's no context, and
      accept never links it to the world's thing of that name; listed by
      the model, it becomes a stub of its own.
    - a character is shown the entries it may belong in with their items
      (`home_entries`, `homes_block`) instead of as named entries, so its
      "in" rows can carry exceptions.

    Filing (docs/superpowers/probes/2026-10-23-filing.md). Every branch
    but species, race and mix lists the entries near it
    (`filing_candidates`, ruling F6: filing nearness reaching siblings)
    and the tags in use, and the reply gives its `tag` (`clean_tag`), its
    "In" rows (`parse_in`, unticked) and "File into this"
    (`file_into_rows`: the model's, the names whose "in" is this entry,
    and the near entries whose facts name it, unticked). Each new name
    carries a tag and the filing its "in" gives (`name_filings`, ticked),
    and a title is no name (ruling F5). "Could move here"
    (`move_here_rows`) is found by code: facts near it that name it. The
    generic branch's reply also gives its "elsewhere" list.

    The reply's `aka` becomes the preview's other names and its `names`
    the `new_names` accept makes stubs for (`_new_names`). Without a
    `stub_id`, a live stub of the same kind and name is offered as
    `matching_stub_id`."""

    view = world.view()
    stub = _live_stub(view, stub_id) if stub_id is not None else None
    if stub is not None:
        kind = stub.kind
    if kind not in CREATE_KINDS:
        raise ValueError(f"can't create a {kind!r} from a prompt")
    hint_body = hint_text(hint) if hint is not None else None
    prose_gen.require_client(client)
    kind_spec = get_kind(kind)
    fields = dict(fields or {})
    # the owner's filings first: an event's `place` and an item's `owner`
    # are filings, no field of their own
    owned = owner_filings(view, fields, kind)
    for field, value in fields.items():
        validate_field(kind_spec, field, value)
    owner_aka = fields.pop("aka", None)
    fields.pop("stub", None)
    owner_tag = clean_tag(fields.pop("tag", None))
    if stub is not None and not fields.get("name"):
        fields["name"] = view.name_of(stub.id) or ""
    treated_as_new = [name for name in new_names if name.strip()]
    picks = {
        written: thing_id
        for written, thing_id in (picks or {}).items()
        if not is_new(written, treated_as_new)
    }
    if kind == "mix" and not fields.get("parents"):
        raise ValueError("a mix needs two parents")
    if kind == "race" and not fields.get("species"):
        raise ValueError("a race needs a species")
    if kind != "mix" and not prompt.strip():
        raise ValueError(f"a {kind} needs a prompt")

    sources = _lineage_sources(kind, fields)
    for source_id in sources:
        if view.thing(source_id) is None:
            raise ValueError(f"no such thing to inherit from: {source_id}")
    gathered = gather_mentions(view, stub.id) if stub is not None else None
    # what the prompt is given anyway: the stub, what mentions it, and
    # what the new thing inherits from
    in_context = {
        *picks.values(),
        *([stub.id] if stub is not None else []),
        *(m.owner_id for m in (gathered.mentioned if gathered is not None else [])),
        *(layer.thing_id for src in sources for layer in heritage.lineage(view, src)),
    }
    picks.update(_found_in_prompt(view, prompt, picks, treated_as_new, in_context))
    # a character's homes are shown with their items, not as named
    home_ids = home_entries(view, picks, gathered) if kind == "character" else []
    home_block, home_labels = homes_block(
        view, home_ids, lambda thing_id: cached_summary(world, thing_id)
    )
    named = _named_in_prompt(
        view,
        {w: thing_id for w, thing_id in picks.items() if thing_id not in home_ids},
        stub_id,
    )
    # the entries near it (ruling F6): today's context first -- where the
    # stub and the owner file it, what mentions it, what the prompt names
    # -- then what's one link from those, then their siblings
    first: list[str] = []
    if stub is not None:
        first += _homes(view, stub.id)
    first += [row.target_id for row in owned]
    if gathered is not None:
        first += [m.owner_id for m in gathered.mentioned]
    first += list(picks.values())
    first += home_ids
    excluded = {stub.id} if stub is not None else set()
    if not first:
        # ruling F31: a draft with no context -- its prompt names no entry
        # in full, and it has no stub mentions, homes or owner filings --
        # grows its list from what the prompt's partial names suggest
        first += suggested_in_prompt(view, prompt, treated_as_new, {*excluded, *first})
    seeds = [*([stub.id] if stub is not None else []), *first]
    near_ids = filing_candidates(view, seeds, first, excluded)
    if not near_ids:
        # ruling F31: still nothing near it -- the world's hubs, so the
        # model writes into this world rather than inventing one
        near_ids = hub_entries(view, excluded)
    generic = _generic_branch(kind, sources)
    # filing is asked of every branch but the heritage kinds' own
    nearby = (
        [
            filing_line(view, state)
            for t in near_ids
            if (state := view.thing(t)) is not None
        ]
        if kind not in HERITAGE_KINDS
        else []
    )
    groups = _labelled_facts(view, sources)
    rows = [row for group in groups for row in group]
    labels = {row.label: row.fact_id for row in rows}
    categories = create_categories(kind, hint)

    calendar = world.calendar
    now = current_date(world)
    now_year = now.to_datetime().year
    shown_now = _shown_year(calendar, now_year)
    era = _era_at(calendar, now_year)
    known_tag = owner_tag or (tag_of(stub) if stub is not None else None)
    known = _known_fields(world, fields, now)
    if owned:
        known.append(("in", ", ".join(row.target_name for row in owned)))
    if known_tag:
        known.append(("tag", known_tag))

    template_vars: dict[str, Any] = {
        "kind": kind,
        "prompt": prompt,
        "categories": categories,
        "known_fields": known,
        "has_name": bool(fields.get("name")),
        "name": fields.get("name") or "",
        "now_label": calendar.format(now),
        "now_year": shown_now,
        "era": era.name if era is not None else "",
        "month_names": calendar.month_names,
        "min_facts": MIN_FACTS,
        "max_facts": MAX_FACTS,
        "inherited": [(r.label, r.source, r.category, r.text) for r in rows],
        "heritage_label": "",
        "mentions": [],
        "about": [],
        "named": named,
        "homes": home_block,
        "nearby": nearby,
        "tags": tags_line(view, stub.id if stub is not None else None),
        "hint": hint_body,
    }
    context: list[tuple[str, list[str]]] = []
    if stub is not None and gathered is not None:
        template_vars["mentions"] = [
            (
                _mention_lead(m.owner_name, m.owner_kind, m.category, m.owner_everyday),
                m.text,
            )
            for m in gathered.mentioned
        ]
        template_vars["about"] = [
            (entry_label(a.name, a.kind, a.everyday), a.facts)
            for a in gathered.about
            # an entry whose only facts mention the stub has nothing to add
            if a.facts
        ]
        context += mention_context(view, stub.id)
    context += [
        (f'Named in this prompt: "{written}" means {label}', facts)
        for written, label, facts in named
    ]
    context += [
        (
            f"May belong in: {heading}",
            [
                *([about] if about else []),
                *(f"{label}: {line}" for label, line in items),
            ],
        )
        for heading, about, items in home_block
    ]
    if kind == "character" and sources:
        template_vars["heritage_label"] = heritage_label(view, sources[0])
        template_vars["heritage_numbers"] = numbers_line(
            heritage.numbers(view, sources[0])
        )
    elif kind == "race":
        species_numbers = heritage.numbers(view, sources[0])
        template_vars["species_name"] = view.name_of(sources[0]) or ""
        template_vars["species_numbers"] = numbers_line(species_numbers)
        template_vars["example_measure"] = next(
            (name for name in species_numbers.measures if name != "height"), "height"
        )
    elif kind == "mix":
        template_vars["parents"] = [
            (
                side,
                heritage_label(view, parent),
                numbers_line(heritage.numbers(view, parent)),
                [(r.label, r.source, r.category, r.text) for r in group],
            )
            for side, parent, group in zip("AB", sources, groups)
        ]

    template = "world.create-mix" if kind == "mix" else "world.create-thing"
    prompt_kind = MIX_PROMPT_KIND if kind == "mix" else CREATE_PROMPT_KIND
    with world_ai_call():
        _response, extracted = await Prompt.request(
            template, client, prompt_kind, vars=template_vars
        )
    reply = extracted["response"]
    name, age, facts = parse_create_reply(
        reply,
        kind,
        calendar,
        now_year,
        labels,
        holder=lambda held: holder_named(view, held),
        categories=categories,
    )
    if not facts:
        raise ValueError("the model's reply had no facts in it")
    wrapper = _reply_wrapper(reply)

    source_names = [row.source for row in rows]
    _attach_top_level(
        facts,
        parse_no_longer_true(reply, labels),
        {row.fact_id: row for row in rows},
        source_names + [name or ""],
    )

    if kind in HERITAGE_KINDS:
        numbers = parse_numbers(reply)
        if kind == "race":
            numbers = _without_inherited_numbers(
                numbers, heritage.numbers(view, sources[0])
            )
        for field, value in numbers.items():
            # the owner's own picks win over the model's
            fields.setdefault(field, value)

    if prompt.strip():
        default_name = _fallback_name(prompt)
    else:
        parent_names = [view.name_of(parent) or "" for parent in sources]
        default_name = f"Mix of {' and '.join(parent_names)}"
    name = fields.get("name") or name or default_name
    fields.pop("name", None)

    raw_aka, raw_names = _raw_aka_and_names(reply)
    reply_aka = _aka_entries(raw_aka)
    if owner_aka is not None:
        aka_entries = list(owner_aka)
    else:
        existing = _aka_entries(stub.fields.get("aka")) if stub is not None else []
        aka_entries = [*existing, *reply_aka]
    aka = clean_aka(aka_entries, name, name_keys(view, skip=stub_id))
    own_names = [name, *(str(entry["name"]) for entry in aka)]
    if stub is not None:
        own_names.append(view.name_of(stub.id) or "")
    own_keys = {name_key(n) for n in own_names if n.strip()}
    own_ids = {stub.id} if stub is not None else set()
    lookup = entry_names(view, near_ids)
    listed, names_into = name_filings(
        view,
        listed_names(raw_names),
        own_keys=own_keys,
        prefer=near_ids,
        lookup=lookup,
    )
    stub_names = _new_names(
        view,
        listed,
        [f.text for f in facts],
        own_names,
        list(picks),
        treated_as_new,
    )
    if kind == "character" and "born" not in fields and age is not None:
        # an age older than the calendar itself is clamped to year 1
        fields["born"] = WorldDate.of(max(1, now_year - age))

    tag = known_tag or clean_tag(
        wrapper.get("tag") if wrapper is not None else _cut_off_tag(reply)
    )
    raw_summary = wrapper.get("summary") if wrapper is not None else None
    summary = (
        " ".join(raw_summary.split())
        if isinstance(raw_summary, str) and raw_summary.strip(" .")
        else None
    )
    # "In": the owner's own, ticked, then the model's, unticked (F7)
    filings = list(owned)
    if nearby:
        for row in parse_in(
            _list_in_reply(reply, wrapper, "in"),
            view,
            own_keys=own_keys,
            own_ids=own_ids,
            prefer=near_ids,
            lookup=lookup,
            calendar=calendar,
            now_year=now_year,
            labels=home_labels,
        ):
            if not any(r.target_id == row.target_id for r in filings):
                filings.append(row)
    # repeats: what the entries near it (and a stub itself) already say
    settings = world.curation()
    owners = [*([stub.id] if stub is not None else []), *near_ids]
    flags = repeat_flags(view, [f.text for f in facts], owners, settings)
    for fact, (repeat_of, ticked) in zip(facts, flags):
        fact.repeat_of, fact.ticked = repeat_of, ticked
    draft = drafted(name, aka, kind, stub_id)
    naming = naming_facts(view, near_ids, draft)
    file_into = (
        file_into_rows(
            view,
            parse_file_into(
                _list_in_reply(reply, wrapper, "file_into"),
                view,
                own_keys=own_keys,
                own_ids=own_ids,
                prefer=near_ids,
                lookup=lookup,
            ),
            names_into,
            code_file_into(
                view,
                [owner for owner, _fact in naming],
                [
                    *(row.target_id for row in filings if row.target_id),
                    *([stub.id] if stub is not None else []),
                ],
            ),
            skip={*own_ids, *(row.target_id for row in filings)},
            draft_id=stub_id,
        )
        if nearby
        else []
    )
    move_here = move_here_rows(view, naming, facts)
    elsewhere: list[ElsewhereFact] = []
    if nearby and generic:
        elsewhere = parse_elsewhere(
            raw_elsewhere(reply, wrapper),
            view,
            own_keys=own_keys,
            own_ids=own_ids,
            listed=listed,
            calendar=calendar,
            now_year=now_year,
            prefer=near_ids,
            holder=lambda held: holder_named(view, held),
        )
        flag_elsewhere_repeats(view, elsewhere, settings)

    # same thing?: what the entry and each stub it would make may already
    # be, from one read of the world's names; never the stub being filled,
    # nor the matching stub ("fill the stub instead" offers that one)
    matching = None if stub is not None else matching_stub(view, kind, name)
    skip = [thing_id for thing_id in (stub_id, matching) if thing_id is not None]
    index = name_index(view)
    same_as = same_offers(
        view, name, near_ids=near_ids, exclude=skip, index=index, kind=kind
    )
    offer_same(
        view,
        [*stub_names, *(e.new for e in elsewhere if e.new is not None)],
        near_ids=near_ids,
        exclude=skip,
        index=index,
        as_new=treated_as_new,
    )

    prose = await _preview_prose(
        view, calendar, kind, name, facts, fields, rows, sources, client
    )

    # the model's verdict on the top candidate, a hint (ruling C2): only
    # when both sides have facts, after the preview's own calls
    verdict: dict[str, Verdict] | None = None
    if ask_same and same_as and same_as[0].has_facts and facts:
        homes = [*(_homes(view, stub.id) if stub is not None else [])]
        homes += [row.target_id for row in owned]
        home = homes[0] if homes else None
        found = await same_thing(
            world,
            preview_label(name, kind, view.name_of(home) if home else None),
            [fact.text for fact in facts],
            same_as[0].thing_id,
            client,
        )
        if found is not None:
            verdict = {same_as[0].thing_id: found}

    log.info(
        "create.preview",
        kind=kind,
        name=name,
        tag=tag,
        hint=hint,
        facts=len(facts),
        repeats=sum(1 for f in facts if f.repeat_of is not None),
        unticked=sum(1 for f in facts if not f.ticked),
        elsewhere=len(elsewhere),
        filings=len(filings),
        file_into=len(file_into),
        move_here=len(move_here),
        new_names=len(stub_names),
        stub_id=stub_id,
        same_as=len(same_as),
        verdict=verdict is not None,
    )
    return CreatePreview(
        kind=kind,
        prompt=prompt,
        fields=fields,
        name=name,
        facts=facts,
        prose=prose,
        inherited=_preview_rows(rows),
        aka=aka,
        new_names=stub_names,
        stub_id=stub_id,
        matching_stub_id=matching,
        context=context,
        picks=picks,
        treated_as_new=treated_as_new,
        elsewhere=elsewhere,
        same_as=same_as,
        verdict=verdict,
        tag=tag,
        hint=hint,
        summary=summary,
        filings=filings,
        file_into=file_into,
        move_here=move_here,
    )


_TAG_RE = re.compile(r'"tag"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _cut_off_tag(reply: str) -> str | None:
    """A cut-off reply's own tag, written before its facts: the first
    `"tag"` there that isn't an `aka` entry's ("proper", "common")."""

    head = reply.split('"facts"', 1)[0]
    for match in _TAG_RE.finditer(head):
        if match.group(1) not in AKA_TAGS:
            return match.group(1)
    return None


def preview_fact_text(view: WorldView, fact: PreviewFact) -> str:
    """A preview's own fact as a prompt is told it: as belief when it's
    held (`held.held_text`, ruling C3), else as it reads."""

    rendered = view.render(fact.text)
    if not fact.held_by:
        return rendered
    stand_in = FactState.model_construct(
        fact_id="", category=fact.category, text=fact.text, origin=None
    )
    return held_text(view, stand_in, None, rendered, holder_id=fact.held_by)


async def _preview_prose(
    view: WorldView,
    calendar: Calendar,
    kind: str,
    name: str,
    facts: list[PreviewFact],
    fields: dict[str, Any],
    inherited: list[_Inherited],
    sources: list[str],
    client: Any,
) -> dict[str, str]:
    """Each section's prose for a preview, the way `prose_gen` writes it
    for a thing in the world: a character's sections add the inherited
    facts `prose_gen.inherited_categories` maps to them, and every other
    inherited fact -- all of them, for a race or mix -- goes to the
    background with a "Heritage: ..." line. Inherited facts the preview
    overrides are left out.

    `personality`'s background also leaves out whatever
    `prose_gen.inherited_categories("description")` maps as inherited (a
    species', race's or mix's `physical` and `variation`) -- the same rule `prose_gen._section_facts` applies for a
    thing already in the world, and `prose_gen.background_for_section`'s
    own exclusion of the character's own `appearance` facts applies here
    too -- so a fresh preview agrees with a later regeneration (acceptance
    probe: docs/superpowers/probes/2026-10-21-personality-and-actions.md)."""

    overridden = {fact_id for fact in facts for fact_id in fact.overrides}
    live = [row for row in inherited if row.fact_id not in overridden]
    heritage_names = list(
        dict.fromkeys(
            layer.name
            for source_id in sources
            for layer in heritage.lineage(view, source_id)
            if layer.kind in HERITAGE_KINDS and layer.name
        )
    )
    heritage_line = (
        [f"Heritage: {', '.join(heritage_names)}."] if heritage_names else []
    )

    # a held fact as belief, as description prose reads one (ruling C3)
    told = [preview_fact_text(view, f) for f in facts]
    # the preview's own identity, for every section's background -- the
    # same core fields `prose_gen.generate_section` reads off a `ThingState`
    fact_pairs = [(f.category, text) for f, text in zip(facts, told)]
    background_fields = {**fields, "name": name}

    prose: dict[str, str] = {}
    for section in prose_gen.sections_for(kind):
        categories = prose_gen.section_categories(kind, section)
        section_facts = [
            text for f, text in zip(facts, told) if f.category in categories
        ]
        by_kind = prose_gen.inherited_categories(section) if kind == "character" else {}
        exclude_by_kind = (
            prose_gen.inherited_categories("description")
            if section == "personality"
            else {}
        )
        inherited_background: list[str] = []
        for row in live:
            if row.category in by_kind.get(row.source_kind, ()):
                section_facts.append(row.text)
            elif row.category in exclude_by_kind.get(row.source_kind, ()):
                continue
            else:
                inherited_background.append(row.text)
        background = prose_gen.background_for_section(
            calendar,
            kind,
            section,
            fact_pairs,
            background_fields,
            heritage_line + inherited_background,
        )
        prose[section] = await prose_gen.render_section(
            kind, name, section, section_facts, client, background
        )
    return prose


def accept_preview(
    world: World,
    preview: CreatePreview,
    *,
    into_stub: str | None = None,
    same_target_id: str | None = None,
    notes: list[str] | None = None,
    prose: list[str] | None = None,
) -> str:
    """Write `preview` in one revision, then cache its prose for the
    current stretch. Returns the thing id. `notes` gains what the owner
    should know (what was left out, and why); `prose` the other things
    whose prose input changed, for the caller to regenerate.

    One writer that tags and files (Filing, Task 4):

    - Only its ticked facts are written (a repeat starts unticked at the
      untick threshold), and each ticked elsewhere fact goes onto its
      target, in the same revision: an existing entry, or a stub made for
      its new name (`write_elsewhere`). One whose target was deleted since
      the preview is dropped, with a note added to `notes` (`live_elsewhere`).
    - Its `tag`, and its ticked "In" rows as `filings` (`write_filings`):
      a person's row carries its exceptions, each written as a `ties`
      fact (`filing_exception_fact`) whose id the filing's `exceptions`
      hold. A filing the store would refuse (a cycle, a target gone) is
      left out with a note.
    - Each ticked "File into this" row files that entry in this one; each
      ticked "Could move here" row moves its fact onto it
      (`repoint.copy_facts`, ruling R1) -- only a fact that's still its
      entry's and still names this one (the rows are checked again, never
      trusted); any other moves nothing, with a note.
    - The preview's `new_names` become stubs (`links.make_stubs`, which
      reuses a name the world has by then) with their `tag`, and each new
      stub its ticked `filing`; every fact's text is linked
      (`links.link_text`, with the preview's picks), keeping its words; a
      thing's own names never link to itself, and a name treated as new
      never links to (or is made a stub by reusing) the world's thing of
      that name. A listed name no fact ends up linking to makes no stub:
      there'd be nothing to find it by.
    - Filling a stub -- the preview's `stub_id`, or `into_stub` ("fill the
      stub instead") -- writes into that thing and keeps its id: its kind
      (`into_stub` may have another), name, fields and other names are set,
      the facts added, its filings kept beside the new ones, and the stub
      marker (ignored or not) removed, so every mention becomes a normal
      link. Filled under another name, it keeps its old one as a common
      other name. A deleted stub, a full entry, or an `into_stub` other
      than the preview's own `stub_id`, is refused with `ValueError`
      before anything is written.
    - Otherwise a new thing is created.
    - A new name the owner marked as a thing the world has
      (`NewName.same_target_id`) makes no stub: the facts link it to that
      thing, which takes it as a common other name (`_row_stubs`).
    - A fact moved here leaves its old entry in `prose` when its prose
      reads what it lost; the entry's own prose is the preview's, written
      without the moved facts, so it's cached reading stale and the entry
      goes in `prose` too.
    - With `same_target_id` ("Is this X?" -- yes) nothing new is made for
      the entry: its material goes onto X (`_accept_same`)."""

    # the old structure a client may still send in the fields is filed,
    # never written as it is (`owner_filings`)
    preview = preview.model_copy(deep=True)
    for row in owner_filings(world.view(), preview.fields, preview.kind):
        if not any(r.target_id == row.target_id for r in preview.filings):
            preview.filings.append(row)
    if same_target_id is not None:
        if into_stub is not None:
            raise ValueError("a preview goes into a stub or onto an entry, not both")
        return _accept_same(world, preview, same_target_id, notes, prose)
    return _accept_new(world, preview, into_stub, notes, prose)


def _accept_new(
    world: World,
    preview: CreatePreview,
    into_stub: str | None,
    notes: list[str] | None,
    prose: list[str] | None,
    fold: Any = None,
) -> str:
    """`accept_preview` making or filling a thing (not `_accept_same`);
    `fold` as `_write_preview` has it."""

    if into_stub is not None and preview.stub_id not in (None, into_stub):
        raise ValueError(
            f"the preview expands the stub {preview.stub_id}, not {into_stub}"
        )
    target = preview.stub_id or into_stub
    view = world.view()
    stub = _live_stub(view, target) if target is not None else None

    skip = {target} if target is not None else set()
    if fold is not None:
        skip.add(fold.stub_id)
    elsewhere = live_elsewhere(view, preview.elsewhere, skip, notes)
    before = world.head_rev()
    new_names = list(preview.new_names)
    while True:
        try:
            thing_id, made, written_notes, moved = _write_preview(
                world, view, preview, stub, new_names, elsewhere, fold
            )
            break
        except _UnlinkedNames as unlinked:
            # written again without them, in a fresh revision: the first
            # was rolled back whole
            log.debug("create.unlinked_names", names=unlinked.names)
            kept = [n for n in new_names if n.name not in unlinked.names]
            if len(kept) == len(new_names):
                raise RuntimeError(f"unlinked stubs with no name: {unlinked}")
            new_names = kept
    if notes is not None:
        notes.extend(written_notes)
        if fold is not None:
            notes.extend(fold.result().notes)
    if prose is not None and fold is not None:
        prose.extend(t for t in fold.result().prose if t != thing_id)
    if prose is not None:
        # what a fact moved here from has lost
        prose.extend(
            t for t in _moved_from_prose(view, moved, thing_id) if t not in prose
        )

    # the prose was written from every fact, which is how the thing reads
    # at the open, "now" end of its timeline -- unless the owner left a
    # fact unticked (it describes one never written) or a fact moved here
    # (it never read that one): then it's cached as of before the accept,
    # so it reads stale, and the thing goes in `prose` to be written again
    # (final review I2)
    start, end = prose_gen.stretch_containing(world, thing_id, None)
    cache = world.prose()
    rev = before if moved or any(not fact.ticked for fact in preview.facts) else None
    if moved and prose is not None and thing_id not in prose:
        prose.append(thing_id)
    for section in prose_gen.sections_for(preview.kind):
        if section in preview.prose:
            cache.put(thing_id, section, start, end, preview.prose[section], rev=rev)
    log.info(
        "create.accept",
        kind=preview.kind,
        thing_id=thing_id,
        stubs=len(set(made.values())),
        filled_stub=stub is not None,
        folded=fold.stub_id if fold is not None else None,
        elsewhere=len(elsewhere),
        moved_here=len(moved),
    )
    return thing_id


def _moved_from_prose(
    view: WorldView, moved: Sequence[tuple[str, FactState]], skip: str
) -> list[str]:
    """The entries a fact moved here from whose prose reads it, at `view`
    (before the accept): their prose is stale now."""

    changed: list[str] = []
    for owner_id, fact in moved:
        state = view.thing(owner_id)
        if state is None or owner_id in (skip, *changed):
            continue
        if prose_reads(state.kind, fact.category):
            changed.append(owner_id)
    return changed


def name_thing(
    rev: Any,
    view: WorldView,
    state: Any,
    name: str,
    aka: list[dict],
    *,
    keep_aka: bool = False,
) -> None:
    """Give a thing already in the world (a stub being filled, a thing
    promoted) `name` and the other names `aka`, in `rev`. With `keep_aka`,
    its own other names are kept as well. Named anew, it keeps its old
    name, which text still calls it by, as a common other name."""

    thing_id = state.id
    old_name = view.name_of(thing_id) or ""
    if old_name != name:
        rev.set_field(thing_id, "name", name, None)
    taken = name_keys(view, skip=thing_id)
    if keep_aka:
        aka = clean_aka([*aka, *_aka_entries(state.fields.get("aka"))], name, taken)
    if name_key(old_name) != name_key(name):
        aka = clean_aka(
            [*aka, {"name": old_name, "tag": "common", "everyday": False}],
            name,
            taken,
        )
    if aka or "aka" in state.fields:
        rev.set_field(thing_id, "aka", aka, None)


def _same_text(text: str) -> str:
    """`text` as two summaries compare: whitespace and case aside."""

    return " ".join(text.split()).casefold()


def _hint_agent(preview: CreatePreview, stub: Any = None) -> dict[str, bool]:
    """`{"agent": <bool>}`, the default its prompt hint gives an entry
    (`kinds.HINT_AGENT`: a religion, nation or order acts; a culture or
    field doesn't), unless the owner's fields set it, or the `stub` being
    filled has it already; nothing for no hint or one the table doesn't
    list."""

    agent = HINT_AGENT.get(preview.hint or "")
    if agent is None or "agent" in preview.fields:
        return {}
    if stub is not None and "agent" in stub.fields:
        return {}
    return {"agent": agent}


class _UnlinkedNames(Exception):
    """New names whose stubs no fact linked to: the write is rolled back
    and made again without them."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(", ".join(names))
        self.names = names


def _write_preview(
    world: World,
    view: WorldView,
    preview: CreatePreview,
    stub: Any,
    new_names: list[NewName],
    elsewhere: Sequence[ElsewhereFact] = (),
    fold: Any = None,
) -> tuple[str, dict[str, str], list[str], list[tuple[str, FactState]]]:
    """`accept_preview`'s one revision, making stubs for `new_names` and
    the new names of `elsewhere` (`_row_stubs`), whose facts it writes
    onto their targets. With `fold` (a `repoint.RepointPlan` of another
    stub onto `stub`), that stub is re-pointed onto the one being filled
    first, in the same revision, and every pick, holder or row naming it
    means the filled one; its names stay other names of it.
    Returns the thing's id, `make_stubs`' mapping, the notes and the facts
    moved here (`(old owner, fact)`, as they were). A stub made here that
    no fact ends up linking to (the name was written in a way linking
    doesn't take, as "al-Qadir" in lowercase) would be an orphan:
    `_UnlinkedNames` rolls the revision back, naming them."""

    notes: list[str] = []
    redirect = {fold.stub_id: fold.target_id} if fold is not None else {}
    picks = {w: redirect.get(t, t) for w, t in preview.picks.items()}
    elsewhere = [
        e.model_copy(update={"held_by": redirect[e.held_by]})
        if e.held_by in redirect
        else e
        for e in elsewhere
    ]
    with world.revision(Source.manual(note=_CREATED_NOTE)) as rev:
        if fold is not None:
            # the kind first: the folded stub's facts are written for it
            if stub is not None and stub.kind != preview.kind:
                rev.change_stub_kind(stub.id, preview.kind)
            fold.write(rev)
        rows = [*new_names, *(e.new for e in elsewhere if e.new is not None)]
        made = _row_stubs(
            rev,
            world,
            world.view(),
            rows,
            preview.treated_as_new,
            redirect=redirect,
            notes=notes,
        )
        if stub is None:
            fields: dict[str, Any] = {
                **_kind_fields(preview.kind, preview.fields, notes),
                "name": preview.name,
            }
            if preview.aka:
                fields["aka"] = preview.aka
            if preview.tag:
                fields["tag"] = preview.tag
            if preview.hint:
                # the prompt hint it was written with, shown on its page
                fields["hint"] = preview.hint
            fields.update(_hint_agent(preview))
            thing_id = rev.create_thing(preview.kind, fields)
        else:
            thing_id = stub.id
            if stub.kind != preview.kind and fold is None:
                rev.change_stub_kind(thing_id, preview.kind)
            # the fields its (perhaps changed) kind has, as a new entry's
            # are (final review I1); its names are `name_thing`'s to write
            own = {
                f: v for f, v in preview.fields.items() if f not in ("name", "aka")
            }
            for field, value in _kind_fields(preview.kind, own, notes).items():
                rev.set_field(thing_id, field, value, None)
            # filling a stub the preview wasn't made from keeps the stub's
            # own other names too
            name_thing(
                rev,
                view,
                stub,
                preview.name,
                preview.aka,
                keep_aka=stub.id != preview.stub_id,
            )
            if fold is not None:
                # the folded stub's names, which its mentions call it by
                for other in fold.aka_added:
                    _common_name(rev, world.view(), thing_id, other)
            if preview.tag and preview.tag != tag_of(stub):
                rev.set_field(thing_id, "tag", preview.tag, None)
            if preview.hint:
                rev.set_field(thing_id, "hint", preview.hint, None)
            for field, value in _hint_agent(preview, stub).items():
                rev.set_field(thing_id, field, value, None)
            rev.remove_field_value(thing_id, "stub", None)

        # the revision's own view: the stubs just made and the thing's own
        # names are in it, so a name meaning the thing itself stays plain
        linking = world.view()
        linked: set[str] = set()

        def linked_text(text: str) -> str:
            written = link_text(
                linking,
                text,
                picks=picks,
                new_names=made,
                owner=thing_id,
                as_new=preview.treated_as_new,
                lowercase=preview.selected_names,
            )
            linked.update(parse_refs(written))
            return written

        # its summary (ruling P21): the reply's, else its first own fact
        # that isn't held (ruling F28: a belief, often first under a
        # religion hint, never sums an entry up; with every fact held, none
        # is marked), unless the stub it fills has one already
        has_summary = stub is not None and any(
            entries.is_summary_fact(f) for f in stub.facts
        )
        summary = (preview.summary or "").strip()
        # a summary with an own fact's text marks that fact, never a copy
        same = _same_text(summary)
        repeated = next(
            (
                f
                for f in preview.facts
                if f.ticked and summary and _same_text(f.text) == same
            ),
            None,
        )
        if summary and not has_summary and repeated is None:
            rev.add_fact(
                thing_id,
                moved_category(preview.kind, "about", False),
                linked_text(summary),
                origin=dict(SUMMARY_ORIGIN),
            )
            has_summary = True
        for fact in preview.facts:
            if not fact.ticked:
                continue
            # a holder deleted since the preview holds nothing
            holder = redirect.get(fact.held_by or "", fact.held_by)
            held = holder is not None and view.thing(holder) is not None
            origin = entries.with_held_by(None, holder) if held else None
            plain = not held and fact.category != entries.BELIEF_CATEGORY
            if not has_summary and (
                fact is repeated if repeated is not None else plain
            ):
                origin = {**(origin or {}), **SUMMARY_ORIGIN}
                has_summary = True
            rev.add_fact(
                thing_id,
                fact.category,
                linked_text(fact.text),
                valid_from=fact.since,
                valid_until=fact.until,
                overrides=fact.overrides,
                origin=origin,
            )
        _write_entry_filings(
            rev,
            world,
            view,
            preview,
            thing_id,
            redirect,
            linked_text,
            notes,
            fold.copies if fold is not None else None,
        )
        _file_new_names(rev, world, view, rows, made, thing_id, notes)
        _write_file_into(rev, world, preview.file_into, thing_id, redirect, notes)
        # the facts that move here, after the entry's own (whose overrides
        # name them as they are)
        moved = _write_move_here(rev, world, view, preview, thing_id, notes)
        linked |= write_elsewhere(
            rev,
            linking,
            view,
            elsewhere,
            made,
            picks=picks,
            as_new=preview.treated_as_new,
            lowercase=preview.selected_names,
        )
        orphans = {
            stub_id
            for stub_id in made.values()
            if view.thing(stub_id) is None and stub_id not in linked
        }
        if orphans:
            raise _UnlinkedNames(
                [
                    n.name
                    for n in new_names
                    if made.get(" ".join(n.name.split())) in orphans
                ]
            )
    return thing_id, made, notes, moved


def _kind_fields(kind: str, fields: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    """`fields` without those `kind` lacks (a draft whose kind the owner
    changed: a character's `born` on a place), each left out with a note."""

    known = {spec.name for spec in get_kind(kind).fields}
    kept = {}
    for field, value in fields.items():
        if field in known:
            kept[field] = value
        else:
            notes.append(f"a {kind} has no {field}: it was left out")
    return kept


def _write_entry_filings(
    rev: Any,
    world: World,
    before: WorldView,
    preview: CreatePreview,
    thing_id: str,
    redirect: dict[str, str],
    linked_text: Callable[[str], str],
    notes: list[str],
    copies: Mapping[str, str] | None = None,
) -> None:
    """The entry's ticked "In" rows as its filings, in `rev`, beside any it
    has (`write_filings`). A thing that acts in the world gets each row's
    exceptions too, each a `ties` fact under its entry
    (`filing_exception_fact`), its id in the filing's `exceptions`; an
    exception whose item its entry no longer holds is dropped quietly
    (`_live_home_exceptions`). A row into a target gone since is left
    out, with a note."""

    state = world.view().thing(thing_id)
    acts = state is not None and entries.acts_in_world(state)
    filings: list[Filing] = []
    for row in preview.filings:
        if not row.ticked:
            continue
        if row.new_name is not None:
            # "+ in..." a name the world hasn't: its stub first (or the
            # entry the world has by that name by now)
            name = " ".join(row.new_name.name.split())
            target = make_stubs(rev, world.view(), [row.new_name])[name]
        else:
            target = redirect.get(row.target_id or "", row.target_id or "")
        if target == thing_id:
            continue
        if row.new_name is None and before.thing(target) is None:
            notes.append(f"{row.target_name} is gone, so it isn't filed there")
            continue
        exception_ids: list[str] = []
        # checked against the entry the filing goes to, as the revision
        # has it (a fold's redirect, its facts moved as `copies`)
        live = _live_home_exceptions(world.view(), row, target, redirect, copies)
        for exception in live if acts else []:
            text, origin = filing_exception_fact(
                linked_text(exception.text), target, row.target_name, exception
            )
            exception_ids.append(rev.add_fact(thing_id, "ties", text, origin=origin))
        filings.append(
            Filing(
                target=target,
                role=row.role,
                since=row.since,
                # a part that was the folded stub is the filled one
                within=redirect.get(row.within, row.within) if row.within else None,
                exceptions=exception_ids,
            )
        )
    write_filings(rev, world, thing_id, filings, notes)


def _file_new_names(
    rev: Any,
    world: World,
    before: WorldView,
    rows: Sequence[NewName],
    made: dict[str, str],
    thing_id: str,
    notes: list[str],
) -> None:
    """Each stub this accept made with a ticked `filing` filed there, in
    `rev`: an entry the world has, the entry being written (`this_entry`:
    `thing_id`), or by name another stub of the accept. A row marked the
    same as a thing the world has files nothing (the filing is the
    stub's, ruling F12), nor does a stub reused from the world."""

    for row in rows:
        filing = row.filing
        if filing is None or not filing.ticked or row.same_target_id is not None:
            continue
        stub_id = _made_id(made, row.name)
        if stub_id is None or before.thing(stub_id) is not None:
            continue
        target = thing_id if filing.this_entry else filing.target_id
        if target is None and filing.name:
            target = _made_id(made, filing.name)
        if target is None or target == stub_id:
            continue
        write_filings(
            rev, world, stub_id, [Filing(target=target, role=filing.role)], notes
        )


def _write_file_into(
    rev: Any,
    world: World,
    rows: Sequence[FileIntoRow],
    thing_id: str,
    redirect: dict[str, str],
    notes: list[str],
) -> None:
    """File each ticked "File into this" row's entry in `thing_id`, in
    `rev` (`write_filings`, which leaves out one already filed there or
    one that would put the entry inside itself, with a note). One deleted
    since is left, with a note."""

    for row in rows:
        if not row.ticked:
            continue
        filed = redirect.get(row.thing_id, row.thing_id)
        if filed == thing_id:
            continue
        if world.view().thing(filed) is None:
            notes.append(f"{row.name} is gone, so it isn't filed here")
            continue
        write_filings(
            rev, world, filed, [Filing(target=thing_id, role=row.role)], notes
        )


def move_here_sources(view: WorldView, preview: CreatePreview) -> set[str]:
    """The entries a "Could move here" row may take a fact from at `view`,
    worked out again from the preview rather than taken from its rows:
    the entries near it (`filing_candidates`) from its stub, its ticked
    "In" rows and its picks -- the context the preview listed."""

    stub = view.thing(preview.stub_id) if preview.stub_id else None
    first: list[str] = []
    if stub is not None:
        first += _homes(view, stub.id)
    first += [row.target_id for row in preview.filings if row.ticked and row.target_id]
    first += list(preview.picks.values())
    seeds = [*([stub.id] if stub is not None else []), *first]
    exclude = {stub.id} if stub is not None else set()
    return set(filing_candidates(view, seeds, first, exclude))


def _write_move_here(
    rev: Any,
    world: World,
    before: WorldView,
    preview: CreatePreview,
    thing_id: str,
    notes: list[str],
) -> list[tuple[str, FactState]]:
    """Move each ticked "Could move here" row's fact onto `thing_id`, in
    `rev` (`repoint.copy_facts`, ruling R1): a new fact with its dates,
    origin and holder, the original removed; its links to the entry
    itself become words. A row is checked again, never trusted: its entry
    must be near this one (`move_here_sources`, worked out again), its
    fact still that entry's (`before`, the world before the accept) and
    no summary, and its text must name this entry (`names_draft`); any
    other moves nothing, with a note. Returns `(old owner, fact)` for each
    moved."""

    # imported here: `worldplay.repoint` imports this module
    from talemate.worldplay.repoint import copy_facts

    draft = drafted(preview.name, preview.aka, preview.kind, preview.stub_id)
    sources: set[str] | None = None
    moved: list[tuple[str, FactState]] = []
    for row in preview.move_here:
        if not row.ticked or row.from_id == thing_id:
            continue
        if sources is None and not row.repeat:
            sources = move_here_sources(before, preview)
        found = before.fact(row.fact_id)
        name = before.name_of(row.from_id) or row.from_id
        if row.repeat:
            repeats = {
                (fact.repeat_of.get("fact_id"), fact.repeat_of.get("owner_id"))
                for fact in preview.facts
                if fact.repeat_of
            }
            if (row.fact_id, row.from_id) not in repeats:
                notes.append(
                    f"{name}'s fact \"{_clip(row.text, 60)}\" isn't one this "
                    "draft repeats, so it doesn't move here"
                )
                continue
        elif row.from_id not in sources:
            notes.append(
                f"{name}'s fact \"{_clip(row.text, 60)}\" isn't near "
                f"{preview.name}, so it doesn't move here"
            )
            continue
        if found is None or found[0] != row.from_id:
            notes.append(
                f'{name}\'s fact "{_clip(row.text, 60)}" was moved or removed '
                "since the preview, so it doesn't move here"
            )
            continue
        if entries.is_summary_fact(found[1]):
            notes.append(
                f'{name}\'s summary "{_clip(row.text, 60)}" is its own, so it '
                "doesn't move here"
            )
            continue
        if not row.repeat and not names_draft(before, found[1].text, draft):
            notes.append(
                f"{name}'s fact \"{_clip(row.text, 60)}\" doesn't name "
                f"{preview.name}, so it doesn't move here"
            )
            continue
        if any(fact.fact_id == row.fact_id for _owner, fact in moved):
            continue
        moved.append((row.from_id, found[1]))
    if moved:
        copy_facts(
            rev,
            world.view(),
            [fact.fact_id for _owner, fact in moved],
            thing_id,
            plain_self_links=True,
        )
    return moved


# --- same thing: onto an entry the world has ---------------------------------

_SAME_NOTE = "added to an entry from prompt"


def _common_name(rev: Any, view: WorldView, thing_id: str, name: str) -> bool:
    """Give `thing_id` `name` as a common other name, in `rev` (`view` is
    the revision's own), unless it has that name already or another thing
    does. Whether it was added."""

    state = view.thing(thing_id)
    name = " ".join(name.split())
    key = name_key(name)
    if state is None or not key:
        return False
    aka = [e for e in state.fields.get("aka") or [] if isinstance(e, dict)]
    held = {name_key(view.name_of(thing_id) or "")}
    held |= {name_key(e["name"]) for e in aka if isinstance(e.get("name"), str)}
    if key in held or key in name_keys(view, skip=thing_id):
        return False
    rev.set_field(
        thing_id,
        "aka",
        [*aka, {"name": name, "tag": "common", "everyday": False}],
        None,
    )
    return True


def _row_stubs(
    rev: Any,
    world: World,
    view: WorldView,
    rows: list[NewName],
    fresh: Sequence[str],
    *,
    redirect: dict[str, str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, str]:
    """`make_stubs` for the new names the owner left new, and for each one
    marked as a thing the world has (`same_target_id`, through `redirect`
    when that thing is going away in this revision), its name and written
    forms mapped to that thing, which takes the name as a common other
    name: the facts link it there, and no stub is made. A row whose thing
    was deleted (or ignored) since is a stub after all, with a note."""

    same: dict[str, str] = {}
    for row in rows:
        target = row.same_target_id
        if target is None:
            continue
        target = (redirect or {}).get(target, target)
        state = view.thing(target)
        if state is None or state.stub_ignored:
            log.info("create.same_row_gone", name=row.name, target=target)
            if notes is not None:
                notes.append(
                    f"The entry {row.name} was marked the same as is gone, "
                    f"so {row.name} is a new stub"
                )
            continue
        same.setdefault(name_key(row.name), target)
    made = make_stubs(
        rev, view, [r for r in rows if name_key(r.name) not in same], fresh=fresh
    )
    for row in rows:
        target = same.get(name_key(row.name))
        if target is None:
            continue
        for form in (row.name, *row.written):
            made.setdefault(" ".join(form.split()), target)
        _common_name(rev, world.view(), target, row.name)
    return made


def _accept_same(
    world: World,
    preview: CreatePreview,
    target_id: str,
    notes: list[str] | None,
    prose: list[str] | None,
) -> str:
    """Accept `preview` as the thing `target_id` (spec goal 4), in one
    revision, and return the id it went onto. Nothing new is made for the
    entry:

    - its ticked facts are added to the target, linked as the target's
      own (its names stay plain), in their category, or
      `default_category`'s when the target's kind has none such (a
      `belief` fact so moved is marked held by the target, so it stays
      a belief); an override is kept only of a fact the target inherits;
    - its ticked elsewhere facts go onto their targets, and its new names
      become stubs (or link where the owner said), as any accept's;
    - the preview's name and other names become common other names of
      the target, unless it (or another thing) has them already;
    - its fields fill those the target leaves empty (a conflicting one is
      skipped, with a note), its tag is the target's only when it has
      none, and its ticked "In" rows file the target too (with their
      exceptions, when it acts in the world); its ticked "File into this"
      rows are filed in the target, and its ticked "Could move here"
      facts move onto it;
    - a stub the preview expanded is re-pointed onto the target
      (`repoint.plan_repoint`) in the same revision, its filings carried
      over by the re-point, so nothing is left behind; a re-point the
      stub can't take is refused (`ValueError`) before anything is
      written.

    Its prose isn't cached (it describes the preview); the target, and
    what the re-point and the moves changed, go in `prose` to be written
    again.

    A target that's a stub is filled instead: by the preview, when no stub
    is being expanded (`into_stub`); else the bare target is folded into
    the stub being expanded (`plan_repoint` of it onto that stub), which is
    filled, all in one revision, and that stub's id returned. A missing or
    ignored target, the stub itself, or a deleted expanded stub is a
    `ValueError`."""

    # imported here: `worldplay.repoint` imports this module
    from talemate.worldplay.repoint import plan_repoint

    view = world.view()
    target = view.thing(target_id)
    if target is None or target.stub_ignored:
        raise ValueError(f"no such entry to add to: {target_id}")
    target_name = view.name_of(target_id) or target_id
    if target_id == preview.stub_id:
        raise ValueError("the preview fills that stub: accept it without a target")
    stub: ThingState | None = None
    if preview.stub_id is not None:
        stub = view.thing(preview.stub_id)
        if stub is None or not stub.is_stub:
            raise ValueError(
                f"the stub this preview expands is gone, so it can't go onto "
                f"{target_name}: preview it again"
            )
    if target.is_stub:
        if stub is None:
            return _accept_new(world, preview, target_id, notes, prose)
        fold = plan_repoint(world, target_id, stub.id, as_kind=preview.kind)
        return _accept_new(world, preview, None, notes, prose, fold=fold)
    plan = plan_repoint(world, stub.id, target_id) if stub is not None else None
    elsewhere = live_elsewhere(
        view, preview.elsewhere, {stub.id} if stub is not None else set(), notes
    )

    new_names = list(preview.new_names)
    while True:
        try:
            made, written_notes, moved = _write_same(
                world, view, preview, target, plan, new_names, elsewhere
            )
            break
        except _UnlinkedNames as unlinked:
            # written again without them, in a fresh revision: the first
            # was rolled back whole
            log.debug("create.unlinked_names", names=unlinked.names)
            kept = [n for n in new_names if n.name not in unlinked.names]
            if len(kept) == len(new_names):
                raise RuntimeError(f"unlinked stubs with no name: {unlinked}")
            new_names = kept
    if notes is not None:
        notes.extend(written_notes)
        if plan is not None:
            notes.extend(plan.result().notes)
    if prose is not None:
        changed = [
            target_id,
            *(plan.result().prose if plan is not None else []),
            *_moved_from_prose(view, moved, target_id),
        ]
        prose.extend(t for t in dict.fromkeys(changed) if t not in prose)
    log.info(
        "create.accept_same",
        kind=preview.kind,
        target=target_id,
        repointed=stub.id if stub is not None else None,
        stubs=len(set(made.values())),
        elsewhere=len(elsewhere),
        moved_here=len(moved),
    )
    return target_id


def _stored(value: object, type_: str) -> object:
    """A field value as stored, for comparing: a date (a `WorldDate` or
    its JSON) as a `WorldDate`, a model as its JSON."""

    if type_ == "date" and isinstance(value, dict):
        try:
            return WorldDate.model_validate(value)
        except ValueError:
            return value
    return value


def _merge_entry(
    rev: Any,
    world: World,
    preview: CreatePreview,
    target_id: str,
    notes: list[str],
    redirect: dict[str, str] | None = None,
) -> None:
    """The preview's own entry material onto the target, in `rev`: its
    other names, the fields the target leaves empty (a conflicting one, or
    one the target's kind lacks, is noted; values compared as stored, a
    thing named through `redirect`), and its tag when the target has none
    (a different one is noted)."""

    moved = redirect or {}

    view = world.view()
    state = view.thing(target_id)
    assert state is not None
    name = view.name_of(target_id) or target_id
    for entry in preview.aka:
        if isinstance(entry.get("name"), str):
            _common_name(rev, world.view(), target_id, entry["name"])

    types = {spec.name: spec.type for spec in get_kind(state.kind).fields}
    skipped: list[str] = []
    for field, value in preview.fields.items():
        if field in ("filings", "tag"):
            continue
        if types.get(field) == "thing" and isinstance(value, str):
            value = moved.get(value, value)
        elif types.get(field) == "things" and isinstance(value, list):
            value = [moved.get(v, v) if isinstance(v, str) else v for v in value]
        held = state.fields.get(field)
        if field not in types or (
            held is not None
            and _stored(held, types[field]) != _stored(value, types[field])
        ):
            skipped.append(field)
            continue
        if held is None:
            try:
                rev.set_field(target_id, field, value, None)
            except ValueError:
                skipped.append(field)
    if skipped:
        notes.append(
            f"{name} keeps its own {', '.join(skipped)}: the new entry's "
            "differed, or doesn't fit it"
        )
    if preview.tag:
        own = tag_of(state)
        if own is None:
            rev.set_field(target_id, "tag", preview.tag, None)
        elif own != preview.tag:
            notes.append(f"{name} keeps its own tag, {own}, not {preview.tag}")


def _write_same(
    world: World,
    view: WorldView,
    preview: CreatePreview,
    target: ThingState,
    plan: Any,
    new_names: list[NewName],
    elsewhere: Sequence[ElsewhereFact],
) -> tuple[dict[str, str], list[str], list[tuple[str, FactState]]]:
    """`_accept_same`'s one revision: the re-point first (the stub's links,
    names, facts and filings go to the target),
    then the preview's name and entry material (`_merge_entry`), the
    stubs, the facts, the filings (with their exceptions), the entries
    filed into it, the facts moved here and the elsewhere facts. Returns
    the stubs' mapping, the notes and the facts moved; `_UnlinkedNames` as
    `_write_preview`'s."""

    target_id = target.id
    stub_id = plan.stub_id if plan is not None else None
    redirect = {stub_id: target_id} if stub_id is not None else {}
    # a pick or holder of the stub means the target now
    picks = {w: redirect.get(t, t) for w, t in preview.picks.items()}
    elsewhere = [
        e.model_copy(update={"held_by": redirect[e.held_by]})
        if e.held_by in redirect
        else e
        for e in elsewhere
    ]
    inherited = {
        fact.fact_id
        for fact, layer in heritage.effective_facts(view, target_id)
        if layer.thing_id != target_id
    }
    notes: list[str] = []
    with world.revision(Source.manual(note=_SAME_NOTE)) as rev:
        if plan is not None:
            # its filings too: what it's filed in (with each `within` and
            # its exceptions) and what's filed in it (`RepointPlan.write`)
            plan.write(rev)
        _common_name(rev, world.view(), target_id, preview.name)
        _merge_entry(rev, world, preview, target_id, notes, redirect)
        rows = [*new_names, *(e.new for e in elsewhere if e.new is not None)]
        made = _row_stubs(
            rev,
            world,
            world.view(),
            rows,
            preview.treated_as_new,
            redirect=redirect,
            notes=notes,
        )
        linking = world.view()
        state = linking.thing(target_id)
        assert state is not None
        categories = get_kind(state.kind).categories
        linked: set[str] = set()

        def linked_text(text: str) -> str:
            written = link_text(
                linking,
                text,
                picks=picks,
                new_names=made,
                owner=target_id,
                as_new=preview.treated_as_new,
                lowercase=preview.selected_names,
            )
            linked.update(parse_refs(written))
            return written

        for fact in preview.facts:
            if not fact.ticked:
                continue
            category = fact.category
            holder = redirect.get(fact.held_by or "", fact.held_by)
            if category not in categories:
                category = default_category(state.kind, fact.since is not None)
                if fact.category == entries.BELIEF_CATEGORY and holder is None:
                    # still a belief, now marked: its category held it
                    holder = target_id
            held = holder is not None and linking.thing(holder) is not None
            rev.add_fact(
                target_id,
                category,
                linked_text(fact.text),
                valid_from=fact.since,
                overrides=[o for o in fact.overrides if o in inherited] or None,
                origin=entries.with_held_by(None, holder) if held else None,
            )
        _write_entry_filings(
            rev,
            world,
            view,
            preview,
            target_id,
            redirect,
            linked_text,
            notes,
            plan.copies if plan is not None else None,
        )
        _file_new_names(rev, world, view, rows, made, target_id, notes)
        _write_file_into(rev, world, preview.file_into, target_id, redirect, notes)
        moved = _write_move_here(rev, world, view, preview, target_id, notes)
        linked |= write_elsewhere(
            rev,
            linking,
            view,
            elsewhere,
            made,
            picks=picks,
            as_new=preview.treated_as_new,
            lowercase=preview.selected_names,
        )
        orphans = {
            thing_id
            for thing_id in made.values()
            if view.thing(thing_id) is None and thing_id not in linked
        }
        if orphans:
            raise _UnlinkedNames(
                [
                    n.name
                    for n in new_names
                    if made.get(" ".join(n.name.split())) in orphans
                ]
            )
    return made, notes, moved
