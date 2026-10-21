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

`json_objects` decodes with `strict=False`: a model sometimes puts a real
line break inside a string (a paragraph break in an "intro") instead of
escaping it, and a strict decoder rejects the whole object over that one
control character. `worldplay.setup` shares this parser rather than its
own copy.
"""

from __future__ import annotations

import json
import re
from typing import Any, NamedTuple

import structlog
from pydantic import BaseModel, Field

from talemate.prompts import Prompt
from talemate.world import heritage
from talemate.world.calendar import Calendar, Era
from talemate.world.dates import WorldDate
from talemate.world.kinds import HERITAGE_KINDS, get_kind, validate_field
from talemate.world.store import Source, World
from talemate.world.view import WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call

log = structlog.get_logger("talemate.worldplay.create")

# the kinds the create box offers in the slice
CREATE_KINDS: tuple[str, ...] = (
    "character",
    "place",
    "lore",
    "species",
    "race",
    "mix",
)

# how many facts the prompt asks for, and the most a preview keeps
MIN_FACTS = 8
MAX_FACTS = 12

# the creative-instruction preset, with room for 12 facts and the wrapper
# (the plain "create" kind caps out at 1024 tokens, which the probe's
# longer lists ran past)
CREATE_PROMPT_KIND = "creative_instruction_2048"

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
}

# words that say nothing about a fact's topic, left out of the overlap a
# top-level "no_longer_true" label is attached by
_STOP_WORDS = frozenset(
    "a an and the of to in for with by on at as is are be or from their "
    "they them its it this that than".split()
)
_WORD_RE = re.compile(r"[a-z]+")

_NAME_RE = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
_AGE_RE = re.compile(r'"age"\s*:\s*"?(\d{1,4})')
_YEAR_RE = re.compile(r"^\s*(\d{1,4})\s*([^\d\s][^\d]*)?\s*$")

_CREATED_NOTE = "created from prompt"


class PreviewFact(BaseModel):
    category: str
    text: str
    since: WorldDate | None = None
    # the fact_ids of the inherited facts this one makes untrue
    overrides: list[str] = Field(default_factory=list)


class PreviewInherited(BaseModel):
    """One inherited fact the preview was made with, as the model was
    shown it, so the owner can mark it overridden before accepting."""

    fact_id: str
    # the layer it comes from: its name and thing id
    source: str
    source_id: str
    category: str
    text: str


class CreatePreview(BaseModel):
    kind: str
    prompt: str
    fields: dict[str, Any] = Field(default_factory=dict)
    name: str
    facts: list[PreviewFact]
    prose: dict[str, str]
    # what the new thing will inherit (empty for a kind with no heritage)
    inherited: list[PreviewInherited] = Field(default_factory=list)


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


def _raw_facts(obj: dict[str, Any]) -> list[tuple[str, str, object, object]]:
    """`(category, text, since, overrides)` from one fact object, in either
    shape."""

    since = obj.get("since")
    overrides = obj.get("overrides")
    text = obj.get("text")
    if isinstance(text, str):
        return [(str(obj.get("category") or ""), text, since, overrides)]
    return [
        (key, value, since, overrides)
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


def parse_create_reply(
    reply: str,
    kind: str,
    calendar: Calendar,
    now_year: int,
    labels: dict[str, str] | None = None,
) -> tuple[str | None, int | None, list[PreviewFact]]:
    """`(name, age, facts)` from a `world/create-thing` reply. `name` and
    `age` are `None` when the reply doesn't give them. At most `MAX_FACTS`
    facts are kept; empty and repeated ones are dropped. A fact's
    `"overrides"` labels are mapped through `labels` (label -> fact id) to
    its `overrides`."""

    categories = get_kind(kind).categories
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
        else:
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
        for category, text, since, overrides in _raw_facts(obj):
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
                )
            )
    if len(facts) > MAX_FACTS:
        log.info("create.facts_capped", got=len(facts), kept=MAX_FACTS)
    # the format example's placeholder name, copied as is, is no name
    name = name.strip() if name and name.strip(" .") else None
    return name, age, facts[:MAX_FACTS]


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
                    text=fact.text,
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


# --- preview and accept ------------------------------------------------------


def _known_fields(
    world: World, fields: dict[str, Any], now: WorldDate
) -> list[tuple[str, str]]:
    """The owner's picks, as `(label, text)` lines for the prompt."""

    calendar = world.calendar
    view = world.view()
    lines: list[tuple[str, str]] = []
    for field, value in fields.items():
        if field == "born":
            born = value if isinstance(value, WorldDate) else WorldDate(**value)
            age = now.to_datetime().year - born.to_datetime().year
            lines.append(("born", f"{calendar.format(born)} (age {age} now)"))
        elif field in ("parent", "culture", "owner", "place"):
            lines.append((field, view.name_of(value) or str(value)))
        elif field in ("heritage", "species", "parents"):
            # the lineage is named in the prompt's own heritage lines
            continue
        else:
            lines.append((field, str(value)))
    return lines


def _fallback_name(prompt: str) -> str:
    """A name for a preview whose reply gave none: the prompt itself, cut
    at a word boundary. The owner edits it before accepting."""

    text = " ".join(prompt.split())
    if len(text) <= 60:
        return text
    return text[:60].rsplit(" ", 1)[0]


async def preview_thing(
    world: World, kind: str, prompt: str, fields: dict[str, Any], client: Any
) -> CreatePreview:
    """Create a `kind` thing from `prompt` -- facts, then prose -- without
    writing anything to the world. `fields` are the owner's picks (`name`,
    `born`, a place's `parent`, a race's `species`, ...), kept as given.

    A mix needs its two `parents`, and only a mix may have an empty
    `prompt`: two parents are enough to draft one from. A race needs its
    `species`. A character with a `heritage`, a race and a mix are shown
    what they inherit, and may mark inherited facts as overridden."""

    if kind not in CREATE_KINDS:
        raise ValueError(f"can't create a {kind!r} from a prompt")
    prose_gen.require_client(client)
    kind_spec = get_kind(kind)
    fields = dict(fields or {})
    for field, value in fields.items():
        validate_field(kind_spec, field, value)
    if kind == "mix" and not fields.get("parents"):
        raise ValueError("a mix needs two parents")
    if kind == "race" and not fields.get("species"):
        raise ValueError("a race needs a species")
    if kind != "mix" and not prompt.strip():
        raise ValueError(f"a {kind} needs a prompt")

    view = world.view()
    sources = _lineage_sources(kind, fields)
    for source_id in sources:
        if view.thing(source_id) is None:
            raise ValueError(f"no such thing to inherit from: {source_id}")
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
        "categories": kind_spec.categories,
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
    }
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
    with world_ai_call():
        _response, extracted = await Prompt.request(
            template, client, CREATE_PROMPT_KIND, vars=template_vars
        )
    reply = extracted["response"]
    name, age, facts = parse_create_reply(reply, kind, calendar, now_year, labels)
    if not facts:
        raise ValueError("the model's reply had no facts in it")

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
    if kind == "character" and "born" not in fields and age is not None:
        # an age older than the calendar itself is clamped to year 1
        fields["born"] = WorldDate.of(max(1, now_year - age))

    prose = await _preview_prose(
        view, calendar, kind, name, facts, fields, rows, sources, client
    )

    log.info("create.preview", kind=kind, name=name, facts=len(facts))
    return CreatePreview(
        kind=kind,
        prompt=prompt,
        fields=fields,
        name=name,
        facts=facts,
        prose=prose,
        inherited=_preview_rows(rows),
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


def accept_preview(world: World, preview: CreatePreview) -> str:
    """Write `preview` as a new thing in one revision -- the thing, its
    fields and its facts -- then cache its prose for the current stretch.
    Returns the new thing id."""

    with world.revision(Source.manual(note=_CREATED_NOTE)) as rev:
        thing_id = rev.create_thing(
            preview.kind, {**preview.fields, "name": preview.name}
        )
        for fact in preview.facts:
            rev.add_fact(
                thing_id,
                fact.category,
                fact.text,
                valid_from=fact.since,
                overrides=fact.overrides,
            )

    # the prose was written from every fact, which is how the thing reads
    # at the open, "now" end of its timeline
    start, end = prose_gen.stretch_containing(world, thing_id, None)
    cache = world.prose()
    for section in prose_gen.sections_for(preview.kind):
        if section in preview.prose:
            cache.put(thing_id, section, start, end, preview.prose[section])
    log.info("create.accept", kind=preview.kind, thing_id=thing_id)
    return thing_id
