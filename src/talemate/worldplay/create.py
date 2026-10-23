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

Spheres (docs/superpowers/probes/2026-10-22-spheres.md) are made by
`worldplay.spheres`, not here. A listed name's kind is read as a stub
guess (`name_guess`): a culture or order is a sphere with that template,
so the legacy `culture` kind is never made. An expanded stub that belongs
in a sphere -- mentioned only inside one sphere's items, or with a sphere
stub named in its prompt -- joins it (`CreatePreview.part_of`); the parent
is never written to.

A character is offered ties to the spheres in its context (the spheres
probe's (c)): those the prompt names or that mention a stub being
expanded (Connections' context), and those whose territory holds a place
the prompt names, each listed once with its items (places left out)
labelled S1... across all of them. A sphere listed there isn't also
"Named in this prompt". The reply's `"ties"` resolve by a sphere's name
or other name only (never an adjective form), and an unknown one is
dropped; a tie's `since` is read as a fact's; an exception's `"rejects"`
label maps to an item of its own tie's sphere, or the exception is
dropped (`parse_ties`). On accept the ties are written, and each
exception becomes a `ties` fact that references what it rejects: a thing
item at the end of its text, or, for a statement item, the sphere, with
`origin = {"rejects_fact": <fact id>}` (`world.spheres.exceptions` reads
both).

Curation (docs/superpowers/probes/2026-10-22-curation.md, probe 1, and
the owner's rulings on it). The generic branch's prompt lists the entries
near the thing (`nearby_ids`, `candidate_line`): today's context first --
the sphere it's part of, what mentions it, what the prompt names -- then
`nearness.near` from the stub or the named things, at the world's
`reach` and `entries`. The reply's `"elsewhere"` list, facts mainly about
those entries (or a new name), becomes the preview's `elsewhere`
(`parse_elsewhere`), ticked, grouped by entry, each with
`default_category`. Repeats are flagged by code (`repeat_flags`): an own
fact whose words a near entry's fact already holds (the world's
`repeat_threshold`) is shown with that match, and arrives unticked only
at `repeat_untick_threshold` or above -- at 0.4 the probe's detector
unticked a third of the good facts, which mostly restate the stub's own
drawer line. An elsewhere item repeating its target is shown the same
way. Accept writes the ticked own facts, and each ticked elsewhere fact
onto its target (a stub for a new name), in the same revision.

`json_objects` decodes with `strict=False`: a model sometimes puts a real
line break inside a string (a paragraph break in an "intro") instead of
escaping it, and a strict decoder rejects the whole object over that one
control character. `worldplay.setup` shares this parser rather than its
own copy.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

import structlog
from pydantic import BaseModel, Field

from talemate.prompts import Prompt
from talemate.world import heritage, spheres
from talemate.world.calendar import Calendar, Era
from talemate.world.curation import CurationSettings
from talemate.world.dates import WorldDate
from talemate.world.kinds import (
    AKA_TAGS,
    ENTRY_DRAWER_TYPES,
    HERITAGE_KINDS,
    PART_OF_KINDS,
    SPHERE_CATEGORIES,
    UNSORTED_DRAWER_ID,
    get_kind,
    validate_field,
)
from talemate.world.nearness import near
from talemate.world.refs import parse_refs, ref
from talemate.world.repeats import content_words, find_repeats
from talemate.world.names import (
    ARTICLES,
    everyday_name,
    find_names,
    unknown_proper_phrases,
)
from talemate.world.store import Source, World
from talemate.world.view import ThingState, WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.characters import DEPARTS_FROM, DEPARTS_FROM_TEACHING
from talemate.worldplay.links import (
    FALLBACK_KIND,
    NewName,
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

# the kinds the create box offers in the slice (a sphere is made by
# `worldplay.spheres`, from a template; the legacy `culture` kind isn't)
CREATE_KINDS: tuple[str, ...] = (
    "character",
    "place",
    "lore",
    "species",
    "race",
    "mix",
    "event",
    "item",
    "sphere",
    "being",
)

# the kinds the reply's "names" may give a name (the prompt lists them);
# an entry with any other kind ("title") is dropped, one with none is lore.
# `name_guess` maps a few others first: "culture" (the legacy kind) and
# "order" to a sphere, "office" to lore
NAME_KINDS: tuple[str, ...] = (
    "character",
    "place",
    "species",
    "race",
    "sphere",
    "event",
    "item",
    "lore",
    "being",
)

# the templates a sphere name guess may carry (the spheres probe's names
# rule lists them; a country is a place), and the ones it maps
GUESS_TEMPLATES: tuple[str, ...] = ("religion", "nation", "order", "culture", "field")
_TEMPLATE_GUESSES = {"council": "order", "guild": "order"}
# kinds a reply gives a name that are really another kind (and template)
_KIND_GUESSES: dict[str, tuple[str, str | None]] = {
    "culture": ("sphere", "culture"),
    "order": ("sphere", "order"),
    "office": ("lore", None),
    "god": ("being", None),
    "spirit": ("being", None),
    "deity": ("being", None),
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
    "sphere",
    "role",
    "exceptions",
    "rejects",
    "held_by",
    "entry",
}

# keys only an `aka` entry or a "names" entry has: an object with one is
# never a fact, even when a cut-off reply's fallback finds it on its own
_NAME_ENTRY_KEYS = {"tag", "everyday", "kind"}
# keys only a tie or an exception has, likewise
_TIE_KEYS = {"sphere", "rejects", "exceptions"}
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
_TIES_LIST_RE = re.compile(r'"ties"\s*:\s*\[')
_ELSEWHERE_LIST_RE = re.compile(r'"elsewhere"\s*:\s*\[')
# the format example's placeholder, copied as is
_PLACEHOLDER = "..."
_AGE_RE = re.compile(r'"age"\s*:\s*"?(\d{1,4})')
_YEAR_RE = re.compile(r"^\s*(\d{1,4})\s*([^\d\s][^\d]*)?\s*$")

_CREATED_NOTE = "created from prompt"


class PreviewFact(BaseModel):
    category: str
    text: str
    since: WorldDate | None = None
    # the fact_ids of the inherited facts this one makes untrue
    overrides: list[str] = Field(default_factory=list)
    # the thing that holds this fact as a belief (`spheres.held_by`), set
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
    """A "but..." of a proposed tie: what the character does differently,
    and the sphere item it departs from -- a thing (`thing_id`) or a
    statement (`fact_id`), named `item` as the prompt showed it."""

    text: str
    item: str
    thing_id: str | None = None
    fact_id: str | None = None


class PreviewTie(BaseModel):
    """A tie the reply proposes to a sphere already in the world."""

    sphere_id: str
    # the sphere's name, for the owner
    sphere: str
    role: str
    since: WorldDate | None = None
    exceptions: list[PreviewException] = Field(default_factory=list)


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
    # the sphere drawer an expanded stub joins (`child_part_of`), as the
    # `part_of` field holds it, or None
    part_of: dict[str, str] | None = None
    # a character's proposed ties to spheres in its context, with their
    # exceptions
    ties: list[PreviewTie] = Field(default_factory=list)
    # facts about other entries, grouped by entry
    elsewhere: list[ElsewhereFact] = Field(default_factory=list)


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


# categories a create reply's facts never take: a sphere's (a place's
# timeline, about and statement facts come from `worldplay.spheres`), and
# a character's `ties`, which are exceptions written from its ties alone
_NOT_CREATED_CATEGORIES = (*SPHERE_CATEGORIES, "ties")


def create_categories(kind: str) -> list[str]:
    """The fact categories a `kind` thing is written from a prompt: its
    kind's, less the ones only a sphere uses and `ties` (exceptions come
    from the reply's ties, never its facts)."""

    return [c for c in get_kind(kind).categories if c not in _NOT_CREATED_CATEGORIES]


def parse_create_reply(
    reply: str,
    kind: str,
    calendar: Calendar,
    now_year: int,
    labels: dict[str, str] | None = None,
    holder: Callable[[str], str | None] | None = None,
) -> tuple[str | None, int | None, list[PreviewFact]]:
    """`(name, age, facts)` from a `world/create-thing` reply. `name` and
    `age` are `None` when the reply doesn't give them. At most `MAX_FACTS`
    facts are kept; empty and repeated ones are dropped. A fact's
    `"overrides"` labels are mapped through `labels` (label -> fact id) to
    its `overrides`, and its `"held_by"` name through `holder` (name ->
    thing id, `None` for no known entry) to its `held_by`. The prompt
    doesn't ask for `held_by` (the curation probe 4 fell back to tagging
    by hand); a reply that gives one anyway is read."""

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
            # an `aka`, "names", "ties" or "elsewhere" entry a broken
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
    them (`name_entries`; `_new_names` decides which count).

    Both lists are decoded on their own when the wrapper object broke, so
    a cut-off reply keeps them: the thing's `aka` from before the facts,
    and every complete entry of the last `"names"` list."""

    wrapper = _reply_wrapper(reply)
    if wrapper is not None:
        raw_aka: object = wrapper.get("aka")
        raw_names: object = wrapper.get("names")
    else:
        head = reply.split('"facts"', 1)[0]
        raw_aka = _list_at(head, _AKA_LIST_RE.search(head))
        last = None
        for last in _NAMES_LIST_RE.finditer(reply):
            pass
        raw_names = _list_at(reply, last)
    return _aka_entries(raw_aka), name_entries(raw_names)


def name_guess(kind: str, template: object) -> tuple[str, str | None]:
    """A listed name's `(kind, template)` as a stub guess, from the kind and
    template a reply gave it (the spheres probe's guards): the legacy
    "culture" kind is a culture sphere and an "order" an order sphere; an
    "office" is lore; a sphere's "council" or "guild" template is an order,
    and a template outside `GUESS_TEMPLATES` is dropped. Only a sphere
    keeps a template."""

    kind = kind.strip().lower()
    if kind in _KIND_GUESSES:
        return _KIND_GUESSES[kind]
    if kind != "sphere":
        return kind, None
    guess = template.strip().lower() if isinstance(template, str) else ""
    guess = _TEMPLATE_GUESSES.get(guess, guess)
    return kind, guess if guess in GUESS_TEMPLATES else None


def name_entries(raw_names: object) -> list[NewName]:
    """A reply's "names" list as `NewName`s, kind as `name_guess` reads it
    (`_new_names` decides which count). An entry with no name, the format
    example's placeholder, and an `aka` object a cut-off reply left on its
    own are skipped."""

    names: list[NewName] = []
    for item in raw_names if isinstance(raw_names, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        if "tag" in item or "everyday" in item:
            # an `aka` object of an entry that was cut off, which the
            # fallback found on its own: no name of its own
            continue
        name = " ".join(item["name"].split())
        if not name.strip(" ."):
            continue
        raw_kind = item.get("kind")
        kind, template = name_guess(
            raw_kind if isinstance(raw_kind, str) else "", item.get("template")
        )
        names.append(
            NewName(
                name=name,
                kind=kind,
                aka=_aka_entries(item.get("aka")),
                template=template,
            )
        )
    return names


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
                template=item.template,
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
# kind's fallback; never one heritage passes down section by section, nor
# a sphere's `statement`, which its members hold (spec, "Categories")
_DEFAULT_CATEGORIES: dict[str, tuple[str, str]] = {
    "sphere": ("about", "timeline"),
    "place": ("general", "history"),
}


def default_category(kind: str, dated: bool) -> str:
    """The category an elsewhere fact goes in on a `kind` target until the
    owner picks another: a sphere's `about`, or `timeline` when dated (a
    drawer statement is the owner's to file); a place's `general`, or
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


def _part_of_link(state: ThingState) -> tuple[str, str | None] | None:
    link = state.fields.get("part_of")
    if isinstance(link, dict) and isinstance(link.get("sphere"), str):
        drawer = link.get("drawer")
        return link["sphere"], drawer if isinstance(drawer, str) else None
    return None


def candidate_line(view: WorldView, state: ThingState) -> str:
    """One entry of the "Entries near this one" list, as the curation probe
    wrote it: "Name (kind; usually called X; part of Y, in its Z drawer;
    drawers: ...; stub): its summary or first fact", the text cut at
    `CANDIDATE_LINE_CHARS`. A sphere's kind reads "sphere: <template>"
    ("place, sphere: nation" for a place sphere), and lists the drawers a
    prompt fills."""

    # imported here: `worldplay.spheres` imports this module
    from talemate.worldplay.spheres import TYPE_HELP

    is_sphere = spheres.is_sphere(state)
    template = state.fields.get("template")
    if is_sphere:
        bits = [
            f"sphere: {template}"
            if state.kind == "sphere"
            else f"{state.kind}, sphere: {template}"
        ]
    else:
        bits = [state.kind]
    everyday = everyday_name(state)
    if everyday:
        bits.append(f"usually called {everyday}")
    link = _part_of_link(state)
    if link is not None:
        title = next(
            (d.title for d in spheres.drawers(view, link[0]) if d.id == link[1]), None
        )
        bits.append(
            f"part of {view.name_of(link[0])}"
            + (f", in its {title} drawer" if title else "")
        )
    if is_sphere:
        titles = [
            d.title for d in spheres.drawers(view, state.id) if d.type in TYPE_HELP
        ]
        if titles:
            bits.append("drawers: " + ", ".join(titles))
    if state.is_stub:
        bits.append("stub")
    fact = spheres.summary_fact(state) if is_sphere else None
    if fact is None and state.facts:
        fact = min(state.facts, key=lambda f: f.created)
    line = (
        _clip(view.render(fact.text)) if fact is not None else "(nothing written yet)"
    )
    return f"{view.name_of(state.id)} ({'; '.join(bits)}): {line}"


def nearby_ids(
    view: WorldView,
    focus: Sequence[str],
    first: Sequence[str],
    settings: CurationSettings,
    exclude: set[str],
) -> list[str]:
    """The entries a prompt lists as near, at most `settings.entries`:
    today's context (`first`: the sphere a stub is part of, what mentions
    it, what the prompt names) first, then `nearness.near` of each `focus`
    thing at `settings.reach` (a thing near two keeps its better rank),
    never one in `exclude`, a removed thing or an ignored stub."""

    best: dict[str, tuple[float, int, int]] = {}
    room = settings.entries + len(first) + len(exclude)
    for thing_id in dict.fromkeys(focus):
        hits = near(view, thing_id, reach=settings.reach, limit=room)
        for position, hit in enumerate(hits):
            key = (-hit.score, hit.steps, position)
            if hit.thing_id not in best or key < best[hit.thing_id]:
                best[hit.thing_id] = key
    ranked = sorted(best, key=lambda thing_id: best[thing_id])
    order: list[str] = []
    for thing_id in [*first, *ranked]:
        if thing_id in order or thing_id in exclude:
            continue
        state = view.thing(thing_id)
        if state is None or state.stub_ignored:
            continue
        order.append(thing_id)
    return order[: settings.entries]


def _nearby_lines(view: WorldView, ids: Sequence[str]) -> list[str]:
    return [
        candidate_line(view, state)
        for thing_id in ids
        if (state := view.thing(thing_id)) is not None
    ]


def entry_named(view: WorldView, name: str, prefer: Sequence[str] = ()) -> str | None:
    """The live thing whose name or other name is `name` (ignoring case and
    a leading article), the `prefer`red ones (the entries listed as near)
    first, then the first made; an ignored stub never; `None` for none."""

    key = name_key(name)
    if not key:
        return None
    others = sorted(view.things(), key=lambda thing: thing.created)
    for state in [view.thing(thing_id) for thing_id in prefer] + others:
        if state is None or state.stub_ignored:
            continue
        names = [view.name_of(state.id) or ""]
        names += [entry["name"] for entry in _aka_entries(state.fields.get("aka"))]
        if key in {name_key(other) for other in names}:
            return state.id
    return None


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
    new_items: Sequence[str] = (),
) -> list[ElsewhereFact]:
    """The reply's elsewhere items, `{"entry", "text", "held_by"}`, as
    additions to other entries, grouped by entry (`_grouped`):

    - `entry` is matched by name or other name (`entry_named`, the listed
      entries first); an unmatched one is a new stub, its kind (and
      template) as the reply's `"names"` lists it, else lore;
    - one about the thing itself (`own_keys`, its names; `own_ids`) is
      dropped, as is a copy of the format example's placeholder, an empty
      one, and a repeat of an item already kept;
    - with `new_items` (Fill's new items' names, ruling C1's filter), one
      naming a new item, or whose text opens with one's name, is about that
      item and dropped (the probe: 10 of 11 false moves, no right item);
    - `since` is read as a fact's, `held_by` through `holder`, and the
      category is `default_category`'s for the target's kind."""

    item_names = [name for name in new_items if name.strip()]
    item_keys = {name_key(name) for name in item_names}
    by_key = {name_key(n.name): n for n in listed}
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
        if key in own_keys or key in item_keys:
            log.debug("create.elsewhere_own", entry=entry)
            continue
        if item_names and _opens_with(text, item_names):
            log.debug("create.elsewhere_about_new_item", entry=entry)
            continue
        target = entry_named(view, entry, prefer)
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
                template=guess.template if guess is not None else None,
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
        )
        linked.update(parse_refs(text))
        linked.add(target)
        held = item.held_by is not None and view.thing(item.held_by) is not None
        rev.add_fact(
            target,
            category,
            text,
            valid_from=item.since,
            origin=spheres.with_held_by(None, item.held_by) if held else None,
        )
    return linked


def _generic_branch(kind: str, sources: Sequence[str]) -> bool:
    """Whether `world/create-thing` writes a `kind` thing in its generic
    branch, the one the curation probe tested the elsewhere list in: not a
    species, race or mix, nor a character of a heritage."""

    return kind not in HERITAGE_KINDS and not (kind == "character" and sources)


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
        elif field in ("parent", "culture", "owner", "place"):
            lines.append((field, view.name_of(value) or str(value)))
        elif field == "cultures":
            names = [view.name_of(share["thing_id"]) or "" for share in value]
            lines.append((field, ", ".join(name for name in names if name)))
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
    at the view's date, rendered, as scene setup shows them, in its kind's
    category order. `ValueError` for a pick that's no thing."""

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
        facts = sorted(state.facts, key=lambda fact: rank.get(fact.category, len(rank)))
        named.append((written, label, [view.render(f.text) for f in facts]))
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


# --- spheres a character may be tied to --------------------------------------


class _SphereItem(NamedTuple):
    """An item the spheres block labels, as an exception's `"rejects"`
    maps back to it."""

    sphere_id: str
    item: spheres.Item


# a tie's role when the reply gives none
_DEFAULT_ROLE = "member"

# the most items the spheres block shows per sphere, places not counted
# (ruling P9)
SPHERE_BLOCK_ITEMS = 8


def context_spheres(
    view: WorldView, picks: dict[str, str], gathered: MentionContext | None
) -> list[str]:
    """The spheres a character's prompt has in context, each once: those
    picked or found in the prompt, those mentioning the stub being
    expanded (`gathered`), then those whose territory holds a picked
    place, in the order they were made."""

    found: list[str] = []

    def add(thing_id: str) -> None:
        state = view.thing(thing_id)
        if state is not None and spheres.is_sphere(state) and thing_id not in found:
            found.append(thing_id)

    for thing_id in picks.values():
        add(thing_id)
    if gathered is not None:
        for mention in gathered.mentioned:
            add(mention.owner_id)
        for about in gathered.about:
            add(about.id)
    places = {
        thing_id
        for thing_id in picks.values()
        if (state := view.thing(thing_id)) is not None and state.kind == "place"
    }
    if places:
        for state in sorted(view.things(), key=lambda thing: thing.created):
            if spheres.is_sphere(state) and places.intersection(
                spheres.territory(view, state.id)
            ):
                add(state.id)
    return found


def _sphere_heading(view: WorldView, state: ThingState) -> str:
    """A sphere as the spheres block heads it, by its template: "The
    White Dawn (religion)"."""

    template = state.fields.get("template")
    heading: str = entry_label(
        view.name_of(state.id) or "",
        template if isinstance(template, str) else state.kind,
        everyday_name(state),
    )
    return heading


def cached_summary(world: World, sphere_id: str) -> str | None:
    """The sphere's summary as last written: its cached `description`
    prose now, or `None` (`spheres.summary` falls back to its summary
    fact)."""

    cached = world.prose().get(sphere_id, "description", None)
    return cached.text if cached is not None else None


def spheres_block(
    view: WorldView,
    sphere_ids: list[str],
    cached: Callable[[str], str | None] | None = None,
) -> tuple[list[tuple[str, str, list[tuple[str, str, str]]]], dict[str, _SphereItem]]:
    """The spheres block as the create prompt lists it -- `(heading,
    summary, [(label, drawer title, line)])` per sphere: its summary
    (`spheres.summary`, from `cached`'s prose for it when given), then its
    first `SPHERE_BLOCK_ITEMS` items in `items` order, places left out
    before counting -- and what each label (S1... running across all the
    spheres, only for the items shown) stands for."""

    block: list[tuple[str, str, list[tuple[str, str, str]]]] = []
    labels: dict[str, _SphereItem] = {}
    for sphere_id in sphere_ids:
        state = view.thing(sphere_id)
        if state is None:
            continue
        titles = {
            drawer.id: drawer.title for drawer in spheres.drawers(view, sphere_id)
        }
        lines: list[tuple[str, str, str]] = []
        for item in spheres.items(view, sphere_id):
            thing = view.thing(item.thing_id) if item.thing_id is not None else None
            if thing is not None and thing.kind == "place":
                continue
            if len(lines) == SPHERE_BLOCK_ITEMS:
                break
            label = f"S{len(labels) + 1}"
            labels[label] = _SphereItem(sphere_id, item)
            title = titles.get(item.drawer_id, spheres.UNSORTED.title)
            lines.append((label, title, spheres._item_line(item)))
        block.append(
            (
                _sphere_heading(view, state),
                spheres.summary(
                    view, sphere_id, cached(sphere_id) if cached is not None else None
                ),
                lines,
            )
        )
    return block, labels


def _sphere_named(view: WorldView, name: str, shown: list[str]) -> str | None:
    """The sphere whose name or other name is `name` (ignoring case and a
    leading article), the ones shown first; never by an adjective form."""

    key = name_key(name)
    if not key:
        return None
    others: list[str] = [
        state.id
        for state in sorted(view.things(), key=lambda thing: thing.created)
        if spheres.is_sphere(state) and state.id not in shown
    ]
    for sphere_id in [*shown, *others]:
        state = view.thing(sphere_id)
        if state is None or not spheres.is_sphere(state):
            continue
        names = [view.name_of(sphere_id) or ""]
        names += [entry["name"] for entry in _aka_entries(state.fields.get("aka"))]
        if key in {name_key(other) for other in names}:
            return sphere_id
    return None


def holder_named(view: WorldView, name: str) -> str | None:
    """The thing that can hold a belief -- a sphere, a character or a being
    -- whose name or other name is `name` (ignoring case and a leading
    article), the first made; `None` for none."""

    key = name_key(name)
    if not key:
        return None
    for state in sorted(view.things(), key=lambda thing: thing.created):
        if not (spheres.is_sphere(state) or state.kind in ("character", "being")):
            continue
        names = [view.name_of(state.id) or ""]
        names += [entry["name"] for entry in _aka_entries(state.fields.get("aka"))]
        if key in {name_key(other) for other in names}:
            return state.id
    return None


def _raw_ties(reply: str) -> object:
    """The reply's `"ties"` list: the wrapper's, or, when it was cut off,
    every complete tie of the last `"ties"` list."""

    wrapper = _reply_wrapper(reply)
    if wrapper is not None:
        return wrapper.get("ties")
    last = None
    for last in _TIES_LIST_RE.finditer(reply):
        pass
    return _list_at(reply, last)


def _tie_exceptions(
    raw: object, sphere_id: str, labels: dict[str, _SphereItem]
) -> list[PreviewException]:
    """A tie's exceptions whose `"rejects"` label is one of its own
    sphere's items; the rest are dropped."""

    found: list[PreviewException] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        text, label = entry.get("text"), entry.get("rejects")
        if not isinstance(text, str) or not text.strip() or not isinstance(label, str):
            continue
        target = labels.get(label.strip().upper())
        if target is None or target.sphere_id != sphere_id:
            log.debug("create.exception_dropped", label=label)
            continue
        found.append(
            PreviewException(
                text=" ".join(text.split()),
                item=target.item.name,
                thing_id=target.item.thing_id,
                fact_id=None if target.item.thing_id else target.item.fact_id,
            )
        )
    return found


def parse_ties(
    reply: str,
    view: WorldView,
    labels: dict[str, _SphereItem],
    shown: list[str],
    calendar: Calendar,
    now_year: int,
) -> list[PreviewTie]:
    """The reply's ties to spheres already in the world (by name or other
    name, the `shown` ones first), in order; one to an unknown sphere is
    dropped. `since` is read as a fact's (`_parse_since`), and a tie
    without a role is a member's."""

    ties: list[PreviewTie] = []
    raw_ties = _raw_ties(reply)
    for raw in raw_ties if isinstance(raw_ties, list) else []:
        if not isinstance(raw, dict) or not isinstance(raw.get("sphere"), str):
            continue
        sphere_id = _sphere_named(view, raw["sphere"], shown)
        if sphere_id is None:
            log.debug("create.unknown_sphere", sphere=raw["sphere"])
            continue
        role = raw.get("role")
        role = " ".join(role.split()) if isinstance(role, str) else ""
        ties.append(
            PreviewTie(
                sphere_id=sphere_id,
                sphere=view.name_of(sphere_id) or "",
                role=role if role.strip(" .") else _DEFAULT_ROLE,
                since=_parse_since(raw.get("since"), calendar, now_year),
                exceptions=_tie_exceptions(raw.get("exceptions"), sphere_id, labels),
            )
        )
    return ties


def _live_exceptions(view: WorldView, tie: PreviewTie) -> list[PreviewException]:
    """The tie's exceptions worth writing: not blank, and rejecting an
    item the sphere still holds (one deleted or ended since the preview
    is dropped quietly)."""

    held = spheres.items(view, tie.sphere_id) if tie.exceptions else []
    thing_ids = {item.thing_id for item in held if item.thing_id}
    fact_ids = {item.fact_id for item in held if item.thing_id is None}
    kept: list[PreviewException] = []
    for exception in tie.exceptions:
        if not exception.text.strip():
            continue
        if exception.thing_id is not None:
            live = exception.thing_id in thing_ids
        else:
            live = exception.fact_id is None or exception.fact_id in fact_ids
        if not live:
            log.debug("create.exception_item_gone", tie=tie.sphere_id)
            continue
        kept.append(exception)
    return kept


def exception_fact(
    text: str, tie: PreviewTie, exception: PreviewException
) -> tuple[str, dict[str, object]]:
    """An exception's `ties` fact, `(text, origin)`: filed under its tie
    (origin `tie`, the sphere: ruling P22), one rejecting a thing item ends
    with a reference to it; one rejecting a statement references the
    sphere and records the statement in its origin too (ruling P3). Text
    that references its target already is kept as it is."""

    origin: dict[str, object] = {"tie": tie.sphere_id}
    if exception.thing_id is not None:
        target, shown, lead = exception.thing_id, exception.item, DEPARTS_FROM
    else:
        target, shown, lead = tie.sphere_id, tie.sphere, DEPARTS_FROM_TEACHING
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


def part_of_since(
    world: World,
    thing_id: str,
    at: WorldDate | None = None,
    *,
    strict: bool = True,
) -> WorldDate | None:
    """The date a new `part_of` value for `thing_id` holds from: `None`
    (undated) when the field has no dated values; else `at`, or the
    world's now (`current_date`), since an undated value would stay hidden
    behind a dated one (an `end_item` end). A date before the latest dated
    value is refused (`ValueError`) -- that value would still win -- or,
    with `strict=False` (a writer the owner didn't date), moved up to it."""

    try:
        entries = world.timeline(thing_id)
    except KeyError:
        # made in this revision: no history yet
        return None
    dated = [
        entry.date
        for entry in entries
        if entry.change == "field"
        and entry.field == "part_of"
        and entry.date is not None
    ]
    if not dated:
        return None
    since = at or current_date(world)
    latest = max(dated, key=lambda date: date.instant)
    if since.instant < latest.instant:
        if not strict:
            return latest
        raise ValueError(
            f"it changed spheres in {world.calendar.format(latest)}: "
            "file it from then on"
        )
    return since


def drawer_types_for(kind: str) -> tuple[str, ...]:
    """The drawer types a `kind` thing may be filed in, as creation files
    them (`kinds.ENTRY_DRAWER_TYPES`): a place in a places drawer, any
    other entry in one that holds entries; none for a kind outside
    `PART_OF_KINDS`. Never people (ties), events (the timeline) or
    branches; any thing may sit in `UNSORTED`."""

    return ENTRY_DRAWER_TYPES.get(kind, ())


def _item_home(view: WorldView, owner_id: str, fact: Any) -> tuple[str, str] | None:
    """`(sphere id, drawer id)` when a fact mentioning a thing is inside a
    sphere's items: a sphere's `statement` (in the drawer its origin
    names), or a fact of a thing part of a sphere (in that thing's
    drawer). `None` for any other fact."""

    owner = view.thing(owner_id)
    if owner is None:
        return None
    if spheres.is_sphere(owner) and fact.category == "statement":
        drawer = (fact.origin or {}).get("drawer")
        return owner.id, drawer if isinstance(drawer, str) else UNSORTED_DRAWER_ID
    link = owner.fields.get("part_of")
    if isinstance(link, dict) and isinstance(link.get("sphere"), str):
        home = view.thing(link["sphere"])
        if home is not None and spheres.is_sphere(home):
            drawer = link.get("drawer")
            return home.id, drawer if isinstance(drawer, str) else UNSORTED_DRAWER_ID
    return None


def _guessed_drawer(
    view: WorldView, sphere_id: str, kind: str, mentioned_in: list[str]
) -> str:
    """The drawer a `kind` child of the sphere goes in: a place in the
    sphere's first places drawer; anything else in the first drawer its
    mentions are in that holds entries; else unsorted."""

    drawers = spheres.drawers(view, sphere_id)
    if kind == "place":
        wanted = [d.id for d in drawers if d.type == "places"]
    else:
        holding = {d.id for d in drawers if d.type in drawer_types_for(kind)}
        wanted = [drawer for drawer in mentioned_in if drawer in holding]
    return wanted[0] if wanted else UNSORTED_DRAWER_ID


def child_part_of(
    view: WorldView, stub: Any, prompt: str, picks: dict[str, str]
) -> dict[str, str] | None:
    """The sphere drawer an expanded stub joins (child first, as the
    spheres spec has it), or `None`:

    - every fact mentioning it is inside one sphere's items (its
      statements, or facts of things part of it): that sphere, in
      `_guessed_drawer`;
    - else its prompt names a sphere stub (picked, or matched in full):
      that stub, unsorted -- the stub has no drawers yet, and expanding it
      later files its children (`worldplay.spheres` adoption).

    A stub that's part of a sphere already stays where it is, and one of a
    kind outside `PART_OF_KINDS` (a character) joins none; nor does a
    sphere stub join a sphere that sits inside it (`spheres.sits_in`). The parent
    is never written to: expanding a child never creates its sphere."""

    if stub.kind not in PART_OF_KINDS or stub.fields.get("part_of") is not None:
        return None
    mentioning = [
        (owner_id, fact)
        for owner_id, fact in view.referencing(stub.id, any_date=True)
        if owner_id != stub.id
    ]
    homes = [
        home
        for owner_id, fact in mentioning
        if (home := _item_home(view, owner_id, fact)) is not None
    ]
    if mentioning and len(homes) == len(mentioning):
        sphere_ids = {sphere_id for sphere_id, _drawer in homes}
        if len(sphere_ids) == 1 and not spheres.sits_in(
            view, next(iter(sphere_ids)), stub.id
        ):
            sphere_id = sphere_ids.pop()
            drawers = [drawer for _sphere, drawer in homes]
            return {
                "sphere": sphere_id,
                "drawer": _guessed_drawer(view, sphere_id, stub.kind, drawers),
            }

    named = [*picks.values()]
    named += [
        match.candidates[0].id
        for match in find_names(view, prompt)
        if not match.suggested
    ]
    for thing_id in named:
        state = view.thing(thing_id)
        if (
            thing_id != stub.id
            and state is not None
            and state.kind == "sphere"
            and state.is_stub
            and not spheres.sits_in(view, thing_id, stub.id)
        ):
            return {"sphere": thing_id, "drawer": UNSORTED_DRAWER_ID}
    return None


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
) -> CreatePreview:
    """Create a `kind` thing from `prompt` -- facts, then prose -- without
    writing anything to the world. `fields` are the owner's picks (`name`,
    `born`, a place's `parent`, a race's `species`, ...), kept as given;
    an `aka` among them is the preview's other names, and a `stub` marker
    is dropped.

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
    - an expanded stub that belongs in a sphere (`child_part_of`: its
      mentions are all inside one sphere's items, or its prompt names a
      sphere stub) carries the `part_of` accept gives it.
    - a character is shown the spheres in its context
      (`context_spheres`, `spheres_block`) instead of as named entries,
      and the reply's ties to existing spheres become the preview's `ties`
      (`parse_ties`).

    A sphere isn't made here: `worldplay.spheres.preview_sphere` makes one
    from a template.

    The reply's `aka` becomes the preview's other names and its `names`
    the `new_names` accept makes stubs for (`_new_names`). Without a
    `stub_id`, a live stub of the same kind and name is offered as
    `matching_stub_id`."""

    view = world.view()
    stub = _live_stub(view, stub_id) if stub_id is not None else None
    if stub is not None:
        kind = stub.kind
        if kind not in CREATE_KINDS:
            raise ValueError(f"a {kind} stub can't be expanded yet")
    if kind not in CREATE_KINDS:
        raise ValueError(f"can't create a {kind!r} from a prompt")
    if kind == "sphere":
        raise ValueError("a sphere is made from a template: preview_sphere")
    prose_gen.require_client(client)
    kind_spec = get_kind(kind)
    fields = dict(fields or {})
    for field, value in fields.items():
        validate_field(kind_spec, field, value)
    owner_aka = fields.pop("aka", None)
    fields.pop("stub", None)
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
    # a character's spheres in context are shown as such, not as named
    sphere_ids = context_spheres(view, picks, gathered) if kind == "character" else []
    sphere_block, sphere_labels = spheres_block(
        view, sphere_ids, lambda sphere_id: cached_summary(world, sphere_id)
    )
    named = _named_in_prompt(
        view,
        {w: thing_id for w, thing_id in picks.items() if thing_id not in sphere_ids},
        stub_id,
    )
    part_of = child_part_of(view, stub, prompt, picks) if stub is not None else None
    # the entries near it: today's context first (the sphere it's part of,
    # what mentions it, what the prompt names), then nearness from the stub
    # and the named things
    settings = world.curation()
    first: list[str] = []
    focus: list[str] = []
    if stub is not None:
        link = _part_of_link(stub)
        home = link[0] if link is not None else (part_of or {}).get("sphere")
        if home is not None:
            first.append(home)
        if gathered is not None:
            first += [m.owner_id for m in gathered.mentioned]
        # an ignored stub is in no link (nearness skips it): its sphere
        # stands in for it
        if not stub.stub_ignored:
            focus.append(stub.id)
        elif home is not None:
            focus.append(home)
    first += list(picks.values())
    focus += list(picks.values())
    near_ids = nearby_ids(
        view, focus, first, settings, {stub.id} if stub is not None else set()
    )
    nearby = _nearby_lines(view, near_ids) if _generic_branch(kind, sources) else []
    groups = _labelled_facts(view, sources)
    rows = [row for group in groups for row in group]
    labels = {row.label: row.fact_id for row in rows}

    calendar = world.calendar
    now = current_date(world)
    now_year = now.to_datetime().year
    shown_now = _shown_year(calendar, now_year)
    era = _era_at(calendar, now_year)

    template_vars: dict[str, Any] = {
        "kind": kind,
        "prompt": prompt,
        "categories": create_categories(kind),
        "known_fields": _known_fields(world, fields, now),
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
        "spheres": sphere_block,
        "nearby": nearby,
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
            f"Sphere: {heading}",
            [*([about] if about else []), *(f"{a} ({b}): {c}" for a, b, c in lines)],
        )
        for heading, about, lines in sphere_block
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
    )
    if not facts:
        raise ValueError("the model's reply had no facts in it")
    ties = (
        parse_ties(reply, view, sphere_labels, sphere_ids, calendar, now_year)
        if sphere_ids
        else []
    )

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

    reply_aka, listed = parse_names(reply)
    if owner_aka is not None:
        aka_entries = list(owner_aka)
    else:
        existing = _aka_entries(stub.fields.get("aka")) if stub is not None else []
        aka_entries = [*existing, *reply_aka]
    aka = clean_aka(aka_entries, name, name_keys(view, skip=stub_id))
    own_names = [name, *(str(entry["name"]) for entry in aka)]
    if stub is not None:
        own_names.append(view.name_of(stub.id) or "")
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

    # repeats: what the entries near it (and a stub itself) already say
    owners = [*([stub.id] if stub is not None else []), *near_ids]
    flags = repeat_flags(view, [f.text for f in facts], owners, settings)
    for fact, (repeat_of, ticked) in zip(facts, flags):
        fact.repeat_of, fact.ticked = repeat_of, ticked
    elsewhere: list[ElsewhereFact] = []
    if nearby:
        elsewhere = parse_elsewhere(
            raw_elsewhere(reply, _reply_wrapper(reply)),
            view,
            own_keys={name_key(n) for n in own_names if n.strip()},
            own_ids={stub.id} if stub is not None else set(),
            listed=listed,
            calendar=calendar,
            now_year=now_year,
            prefer=near_ids,
            holder=lambda held: holder_named(view, held),
        )
        flag_elsewhere_repeats(view, elsewhere, settings)

    prose = await _preview_prose(
        view, calendar, kind, name, facts, fields, rows, sources, client
    )

    log.info(
        "create.preview",
        kind=kind,
        name=name,
        facts=len(facts),
        repeats=sum(1 for f in facts if f.repeat_of is not None),
        unticked=sum(1 for f in facts if not f.ticked),
        elsewhere=len(elsewhere),
        new_names=len(stub_names),
        stub_id=stub_id,
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
        matching_stub_id=None if stub is not None else matching_stub(view, kind, name),
        context=context,
        picks=picks,
        treated_as_new=treated_as_new,
        part_of=part_of,
        ties=ties,
        elsewhere=elsewhere,
    )


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
    species', race's or mix's `physical` and `variation`, a culture's
    `dress`) -- the same rule `prose_gen._section_facts` applies for a
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

    # the preview's own identity, for every section's background -- the
    # same core fields `prose_gen.generate_section` reads off a `ThingState`
    fact_pairs = [(f.category, f.text) for f in facts]
    background_fields = {**fields, "name": name}

    prose: dict[str, str] = {}
    for section in prose_gen.sections_for(kind):
        categories = prose_gen.section_categories(kind, section)
        section_facts = [f.text for f in facts if f.category in categories]
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


def _can_be_tied(preview: CreatePreview) -> bool:
    """Whether the previewed thing can hold ties: a character, or a being
    whose `existence` is real (`spheres.acts_in_world`)."""

    state = ThingState(
        id="0" * 32, kind=preview.kind, fields=dict(preview.fields), facts=[]
    )
    return spheres.acts_in_world(state)


def accept_preview(
    world: World,
    preview: CreatePreview,
    *,
    into_stub: str | None = None,
    notes: list[str] | None = None,
) -> str:
    """Write `preview` in one revision, then cache its prose for the
    current stretch. Returns the thing id.

    - Only its ticked facts are written (a repeat starts unticked at the
      untick threshold), and each ticked elsewhere fact goes onto its
      target, in the same revision: an existing entry, or a stub made for
      its new name (`write_elsewhere`). One whose target was deleted since
      the preview is dropped, with a note added to `notes` (`live_elsewhere`).

    - The preview's `new_names` become stubs (`links.make_stubs`, which
      reuses a name the world has by then), and every fact's text is
      linked (`links.link_text`, with the preview's picks), keeping its
      words; a thing's own names never link to itself, and a name treated
      as new never links to (or is made a stub by reusing) the world's
      thing of that name. A listed name no fact ends up linking to makes
      no stub: there'd be nothing to find it by.
    - A character's (or real being's) `ties` are written (after any the
      owner's fields give; any other kind's are refused with `ValueError`), and each of their exceptions becomes a `ties` fact
      (`exception_fact`); a blank exception, or one whose rejected item
      the sphere no longer holds, is dropped quietly (`_live_exceptions`).
      A tie to a thing that's no sphere (deleted since) is refused with
      `ValueError` before anything is written.
    - Filling a stub -- the preview's `stub_id`, or `into_stub` ("fill the
      stub instead") -- writes into that thing and keeps its id: its kind
      (`into_stub` may have another), name, fields and other names are set,
      the facts added, and the stub marker (ignored or not) removed, so
      every mention becomes a normal link. Filled under another name, it
      keeps its old one as a common other name. A deleted stub, a full
      entry, or an `into_stub` other than the preview's own `stub_id`, is
      refused with `ValueError` before anything is written.
    - Otherwise a new thing is created."""

    if into_stub is not None and preview.stub_id not in (None, into_stub):
        raise ValueError(
            f"the preview expands the stub {preview.stub_id}, not {into_stub}"
        )
    target = preview.stub_id or into_stub
    view = world.view()
    stub = _live_stub(view, target) if target is not None else None
    if preview.ties and not _can_be_tied(preview):
        raise ValueError(f"a {preview.kind} that isn't real can't be tied")
    for tie in preview.ties:
        sphere = view.thing(tie.sphere_id)
        if sphere is None or not spheres.is_sphere(sphere):
            raise ValueError(f"a tie to no sphere: {tie.sphere_id}")

    elsewhere = live_elsewhere(
        view, preview.elsewhere, {target} if target is not None else set(), notes
    )
    before = world.head_rev()
    new_names = list(preview.new_names)
    while True:
        try:
            thing_id, made = _write_preview(
                world, view, preview, stub, new_names, elsewhere
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

    # the prose was written from every fact, which is how the thing reads
    # at the open, "now" end of its timeline -- unless the owner left a
    # fact unticked: then it describes one never written, and is cached as
    # of before the accept, so it reads stale and is written again
    start, end = prose_gen.stretch_containing(world, thing_id, None)
    cache = world.prose()
    rev = before if any(not fact.ticked for fact in preview.facts) else None
    for section in prose_gen.sections_for(preview.kind):
        if section in preview.prose:
            cache.put(thing_id, section, start, end, preview.prose[section], rev=rev)
    log.info(
        "create.accept",
        kind=preview.kind,
        thing_id=thing_id,
        stubs=len(set(made.values())),
        filled_stub=stub is not None,
        elsewhere=len(elsewhere),
    )
    return thing_id


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
) -> tuple[str, dict[str, str]]:
    """`accept_preview`'s one revision, making stubs for `new_names` and
    the new names of `elsewhere`, whose facts it writes onto their
    targets.
    Returns the thing's id and `make_stubs`' mapping. A stub made here that
    no fact ends up linking to (the name was written in a way linking
    doesn't take, as "al-Qadir" in lowercase) would be an orphan:
    `_UnlinkedNames` rolls the revision back, naming them."""

    with world.revision(Source.manual(note=_CREATED_NOTE)) as rev:
        made = make_stubs(
            rev,
            view,
            [*new_names, *(e.new for e in elsewhere if e.new is not None)],
            fresh=preview.treated_as_new,
        )
        if stub is None:
            fields: dict[str, Any] = {**preview.fields, "name": preview.name}
            if preview.aka:
                fields["aka"] = preview.aka
            thing_id = rev.create_thing(preview.kind, fields)
        else:
            thing_id = stub.id
            if stub.kind != preview.kind:
                rev.change_stub_kind(thing_id, preview.kind)
            for field, value in preview.fields.items():
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
            rev.remove_field_value(thing_id, "stub", None)
        if preview.part_of is not None:
            rev.set_field(
                thing_id,
                "part_of",
                preview.part_of,
                part_of_since(world, thing_id, strict=False),
            )
        if preview.ties:
            held = preview.fields.get("ties")
            rev.set_field(
                thing_id,
                "ties",
                [
                    *(held if isinstance(held, list) else []),
                    *(
                        {
                            "sphere": tie.sphere_id,
                            "role": tie.role,
                            "since": (
                                tie.since.model_dump(mode="json")
                                if tie.since is not None
                                else None
                            ),
                            "until": None,
                        }
                        for tie in preview.ties
                    ),
                ],
                None,
            )

        # the revision's own view: the stubs just made and the thing's own
        # names are in it, so a name meaning the thing itself stays plain
        linking = world.view()
        linked: set[str] = set()
        for fact in preview.facts:
            if not fact.ticked:
                continue
            text = link_text(
                linking,
                fact.text,
                picks=preview.picks,
                new_names=made,
                owner=thing_id,
                as_new=preview.treated_as_new,
            )
            linked.update(parse_refs(text))
            # a holder deleted since the preview holds nothing
            held = fact.held_by is not None and view.thing(fact.held_by) is not None
            rev.add_fact(
                thing_id,
                fact.category,
                text,
                valid_from=fact.since,
                overrides=fact.overrides,
                origin=spheres.with_held_by(None, fact.held_by) if held else None,
            )
        for tie in preview.ties:
            for exception in _live_exceptions(view, tie):
                text = link_text(
                    linking,
                    exception.text,
                    picks=preview.picks,
                    new_names=made,
                    owner=thing_id,
                    as_new=preview.treated_as_new,
                )
                linked.update(parse_refs(text))
                text, origin = exception_fact(text, tie, exception)
                rev.add_fact(thing_id, "ties", text, origin=origin)
        linked |= write_elsewhere(
            rev,
            linking,
            view,
            elsewhere,
            made,
            picks=preview.picks,
            as_new=preview.treated_as_new,
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
    return thing_id, made
