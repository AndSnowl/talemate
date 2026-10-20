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
- a character's age becomes its born year, against the world's current date.

The model's own idea of which facts it invented isn't asked for: the probe
showed it can't be relied on.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from pydantic import BaseModel, Field

from talemate.prompts import Prompt
from talemate.world.calendar import Calendar, Era
from talemate.world.dates import WorldDate
from talemate.world.kinds import get_kind, validate_field
from talemate.world.store import Source, World
from talemate.worldplay import prose_gen

log = structlog.get_logger("talemate.worldplay.create")

# the kinds the create box offers in the slice
CREATE_KINDS: tuple[str, ...] = ("character", "place", "lore")

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
# "text"}` shape
_NOT_CATEGORY_KEYS = {"since", "name", "age", "category", "text", "facts"}

_NAME_RE = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
_AGE_RE = re.compile(r'"age"\s*:\s*"?(\d{1,4})')
_YEAR_RE = re.compile(r"^\s*(\d{1,4})\s*([^\d\s][^\d]*)?\s*$")

_CREATED_NOTE = "created from prompt"


class PreviewFact(BaseModel):
    category: str
    text: str
    since: WorldDate | None = None


class CreatePreview(BaseModel):
    kind: str
    prompt: str
    fields: dict[str, Any] = Field(default_factory=dict)
    name: str
    facts: list[PreviewFact]
    prose: dict[str, str]


# --- the calendar ------------------------------------------------------------


def current_date(world: World) -> WorldDate:
    """The world's "now": where its latest scene got to, or year 1 for a
    world with no scenes yet (the same default scene setup uses)."""

    return world.scenes().latest_end() or WorldDate.of(1)


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


def _json_objects(text: str) -> list[dict[str, Any]]:
    """Every complete top-level JSON object in `text`, in order. An object
    that doesn't parse (a reply cut off mid-object) is skipped, and the scan
    carries on inside it, so the complete facts of a truncated list are
    still found."""

    decoder = json.JSONDecoder()
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
        index = end
    return found


def _raw_facts(obj: dict[str, Any]) -> list[tuple[str, str, object]]:
    """`(category, text, since)` from one fact object, in either shape."""

    since = obj.get("since")
    text = obj.get("text")
    if isinstance(text, str):
        return [(str(obj.get("category") or ""), text, since)]
    return [
        (key, value, since)
        for key, value in obj.items()
        if key not in _NOT_CATEGORY_KEYS and isinstance(value, str)
    ]


def parse_create_reply(
    reply: str, kind: str, calendar: Calendar, now_year: int
) -> tuple[str | None, int | None, list[PreviewFact]]:
    """`(name, age, facts)` from a `world/create-thing` reply. `name` and
    `age` are `None` when the reply doesn't give them. At most `MAX_FACTS`
    facts are kept; empty and repeated ones are dropped."""

    categories = get_kind(kind).categories
    fallback = _FALLBACK_CATEGORY.get(kind, "general")

    name: str | None = None
    age: int | None = None
    fact_objects: list[dict[str, Any]] = []
    for obj in _json_objects(reply):
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
        name = json.loads(f'"{match.group(1)}"')
    if age is None and (match := _AGE_RE.search(head)):
        age = int(match.group(1))

    facts: list[PreviewFact] = []
    seen: set[tuple[str, str]] = set()
    for obj in fact_objects:
        for category, text, since in _raw_facts(obj):
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
                )
            )
    if len(facts) > MAX_FACTS:
        log.info("create.facts_capped", got=len(facts), kept=MAX_FACTS)
    # the format example's placeholder name, copied as is, is no name
    name = name.strip() if name and name.strip(" .") else None
    return name, age, facts[:MAX_FACTS]


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
    `born`, a place's `parent`, ...), kept as given."""

    if kind not in CREATE_KINDS:
        raise ValueError(f"can't create a {kind!r} from a prompt")
    kind_spec = get_kind(kind)
    fields = dict(fields or {})
    for field, value in fields.items():
        validate_field(kind_spec, field, value)

    calendar = world.calendar
    now = current_date(world)
    now_year = now.to_datetime().year
    shown_now = _shown_year(calendar, now_year)
    era = _era_at(calendar, now_year)

    _response, extracted = await Prompt.request(
        "world.create-thing",
        client,
        CREATE_PROMPT_KIND,
        vars={
            "kind": kind,
            "prompt": prompt,
            "categories": kind_spec.categories,
            "known_fields": _known_fields(world, fields, now),
            "has_name": bool(fields.get("name")),
            "now_label": calendar.format(now),
            "now_year": shown_now,
            "era": era.name if era is not None else "",
            "example_year": max(1, shown_now - 5),
            "month_names": calendar.month_names,
            "min_facts": MIN_FACTS,
            "max_facts": MAX_FACTS,
        },
    )
    reply = extracted["response"]
    name, age, facts = parse_create_reply(reply, kind, calendar, now_year)
    if not facts:
        raise ValueError("the model's reply had no facts in it")

    name = fields.get("name") or name or _fallback_name(prompt)
    fields.pop("name", None)
    if kind == "character" and "born" not in fields and age is not None:
        if 0 <= age < now_year:
            fields["born"] = WorldDate.of(now_year - age)

    prose: dict[str, str] = {}
    for section in prose_gen.sections_for(kind):
        categories = prose_gen.section_categories(kind, section)
        section_facts = [f.text for f in facts if f.category in categories]
        prose[section] = await prose_gen.render_section(
            kind, name, section, section_facts, client
        )

    log.info("create.preview", kind=kind, name=name, facts=len(facts))
    return CreatePreview(
        kind=kind,
        prompt=prompt,
        fields=fields,
        name=name,
        facts=facts,
        prose=prose,
    )


def accept_preview(world: World, preview: CreatePreview) -> str:
    """Write `preview` as a new thing in one revision -- the thing, its
    fields and its facts -- then cache its prose for the current stretch.
    Returns the new thing id."""

    with world.revision(Source.manual(note=_CREATED_NOTE)) as rev:
        thing_id = rev.create_thing(
            preview.kind, {**preview.fields, "name": preview.name}
        )
        for fact in preview.facts:
            rev.add_fact(thing_id, fact.category, fact.text, valid_from=fact.since)

    # the prose was written from every fact, which is how the thing reads
    # at the open, "now" end of its timeline
    start, end = prose_gen.stretch_containing(world, thing_id, None)
    cache = world.prose()
    for section in prose_gen.sections_for(preview.kind):
        if section in preview.prose:
            cache.put(thing_id, section, start, end, preview.prose[section])
    log.info("create.accept", kind=preview.kind, thing_id=thing_id)
    return thing_id
