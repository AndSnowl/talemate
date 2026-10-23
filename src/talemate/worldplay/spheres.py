"""Spheres from the owner's prompt, in two steps, and promotion.

A sphere (`world.spheres`) is made the way the spheres probe settled
(docs/superpowers/probes/2026-10-22-spheres.md):

1. **The core** (`preview_sphere`, `world/sphere-core`): its name, summary,
   other names, a short timeline, and a drawer outline with a few items
   each, in the flat shape the probe found complete every time -- drawers
   `[{type, title}]`, then items `[{drawer: <title>, name, text, kind}]`.
   Named items become stubs part of the sphere on accept, nameless ones
   its `statement` facts. The summary is the sphere's `description` prose
   (ledger ruling P1): accept caches it, as `create.accept_preview` caches
   a thing's prose.
2. **Fill** (`fill_drawer`, `world/sphere-fill`): new items for one drawer,
   under the reply key `new_items`, with a plain statement as `{"text"}`.
   Nothing is written until `accept_fill`. Fill also gets the curation
   probe's elsewhere list (`FillPreview.elsewhere`), as create does, with
   ruling C1's filter: an item about one of the reply's new items is
   dropped. Its items are checked for repeats of what the entries near
   the sphere say. The core gets no elsewhere list (ruling C1: in the
   probe its elsewhere items were copies of their targets' facts).

The core can make a new sphere, expand a stub (its kind becomes `sphere`,
or it stays a place), or promote a thing: a lore entry or a stub becomes a
`sphere` under its own id (`Revision.promote_to_sphere`), and a place takes
on the template and drawers as a place. A promoted thing's facts are the
prompt's "Already known", and are kept. Whatever is already part of the
stub or promoted thing is the prompt's "Already part of it", and is
adopted: filed in the drawer of the item the reply relists it as, or a
place in the first places drawer, else left unsorted.

The probe's guards on what the model writes:
- an item kind outside lore, place, item and event ("rite", "ceremony",
  "custom", "practice", "sphere") is lore;
- a drawer of a type the reply may not write is dropped, and the app's own
  drawers (people, the timeline) are added from the template;
- an item naming no drawer title goes to the first drawer of the type its
  title names (a type, or a template's drawer title), else unsorted;
- an item already part of the sphere is adopted, not made again; one
  naming a free stub links that stub into the drawer; one naming any other
  thing in the world is kept as a statement that links it, never a stub;
- Fill flags an item that repeats one the sphere holds, by name or by
  (nearly) the same words: it comes unticked, never dropped silently;
- month names never become names, and `create.name_guess` maps the names'
  kinds and templates (council and guild templates are orders).

**A branch** (`preview_branch`, `world/sphere-branch`) is a `sphere` whose
`parent` is another, linked from now (the date it splits), in the core's
flat shape. The prompt lists the parent's items labelled F1...Fn; the
reply's `"drops"` and an item's `"overrides"` name labels, mapped back as
Connections maps inherited facts' labels:
- a thing item's label goes to the branch's `drops`;
- a statement's label, on a statement the branch writes, makes it
  override that fact; dropped outright or replaced by a named item, the
  branch rejects it with an `about` fact overriding it (`rejects`).
Its drawers are the parent's, plus any of a title the parent lacks.

**Ending an item** (`end_item`, the owner's "End this..."): its part-of
link or statement ends at a date, it notes when and by what, and the
sphere that ended it gets a timeline fact linking it.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from pydantic import BaseModel, Field

from talemate.prompts import Prompt
from talemate.world import spheres
from talemate.world.calendar import Calendar
from talemate.world.dates import WorldDate
from talemate.world.kinds import (
    SPHERE_TEMPLATES,
    TEMPLATE_AGENT,
    UNSORTED_DRAWER_ID,
    get_kind,
    validate_field,
)
from talemate.world.names import ARTICLES, everyday_name
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Revision, Source, World
from talemate.world.view import ThingState, WorldView
from talemate.worldplay import create, prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.create import (
    PART_OF_KINDS,
    CreatePreview,
    ElsewhereFact,
    PreviewFact,
    json_objects,
)
from talemate.worldplay.links import (
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

log = structlog.get_logger("talemate.worldplay.spheres")

# the probe's presets: the core's reply ran to 1658 tokens, Fill's to 456
CORE_PROMPT_KIND = "creative_instruction_2048"
FILL_PROMPT_KIND = "creative_instruction_1024"

# how the prompts name each template
TEMPLATE_LABELS: dict[str, str] = {
    "religion": "religion (a faith or church)",
    "nation": "nation",
    "order": "order (an academy, guild, order, council or other body)",
    "culture": "culture",
    "field": "field of knowledge or magic",
    "other": "sphere",
}

# the drawer types the core and Fill write, each with its gloss; people,
# events and branches are the app's (ties, the timeline, branches)
TYPE_HELP: dict[str, str] = {
    "places": "its territory and sites: where it holds sway, is seated, or holy sites",
    "practices": "rites, ceremonies, customs, holidays, techniques",
    "beliefs": "doctrines, values, attitudes, laws, myths and legends",
    "knowledge": "what is known or studied, and its frontier",
    "structure": "ranks, offices, councils, divisions",
}

# the kinds a named item may be; any other is lore
ITEM_KINDS: tuple[str, ...] = ("lore", "place", "item", "event")
# the category an item stub's text is written in, by its kind
_ITEM_CATEGORY = {
    "lore": "general",
    "place": "description",
    "item": "description",
    "event": "summary",
    "sphere": "about",
}

# two item texts sharing this much of their topic words say the same
_REPEAT_OVERLAP = 0.75

_CREATED_NOTE = "sphere created from prompt"

# the origin of a sphere's summary fact (ruling P21)
SUMMARY_ORIGIN: dict[str, object] = {"summary": True}
_FILLED_NOTE = "sphere drawer filled"
_ENDED_NOTE = "sphere item ended"


class SpherePreview(CreatePreview):
    """A sphere's core, before it's written. `kind` is `sphere`, or `place`
    for a place taking on a template; `facts` are its dated `timeline`
    (an entry with no usable year is `about`), and `prose["description"]`
    its summary.

    - `drawers`: `{"id", "type", "title"}`, as the `drawers` field holds
      them;
    - `items`: `{"drawer_id", "name", "text", "kind"}`; a named one becomes
      a stub part of the sphere, a nameless one (`name` "") a statement.
      One with a `thing_id` links that stub instead of making one;
    - `adopted`: `{"thing_id", "drawer_id"}`, the entries already part of
      the stub or promoted thing, and the drawer each is filed in.

    A branch (`preview_branch`) has `fields["parent"]`, linked from
    `split`; its `drawers` are only those it adds to its parent's.
    - `parent_items`: `{"label", "thing_id", "fact_id", "source_id",
      "name", "text", "drawer_id"}`, the parent's items as the prompt
      labelled them, so the owner can drop one the model missed;
    - `drops`: the inherited thing items it drops (its `drops` field);
    - `rejects`: the inherited statements it drops, each written as an
      `about` fact overriding it;
    - an item's `overrides`: on a statement, the inherited statements it
      replaces."""

    template: str
    agent: bool
    drawers: list[dict[str, str]] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    adopted: list[dict[str, str]] = Field(default_factory=list)
    # the lore entry, place or stub this preview promotes
    promote_id: str | None = None
    # a branch: the date its `parent` link holds from, and what it drops
    split: WorldDate | None = None
    parent_items: list[dict[str, Any]] = Field(default_factory=list)
    drops: list[str] = Field(default_factory=list)
    rejects: list[str] = Field(default_factory=list)


class FillPreview(BaseModel):
    """What Fill proposes for a drawer, before it's written: `items`, as
    `SpherePreview.items` holds them, each with its `names`, its
    `repeat_of` (`create.repeat_flags`) and whether it's `ticked`; and
    `elsewhere`, the facts about other entries, grouped by entry."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    elsewhere: list[ElsewhereFact] = Field(default_factory=list)


# --- reading replies -----------------------------------------------------------


def _reply_object(reply: str, key: str) -> dict[str, Any] | None:
    """The reply's object holding a `key` list, or `None` (cut off or
    broken). The prepared `{` may or may not lead the reply."""

    for text in (reply, "{" + reply):
        for obj in json_objects(text):
            if isinstance(obj.get(key), list):
                return obj
    return None


def _tidy(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _new_drawer_id(taken: set[str]) -> str:
    while (drawer_id := uuid.uuid4().hex[:8]) in taken:
        pass
    taken.add(drawer_id)
    return drawer_id


def _outline(raw: object, template: str, kind: str = "sphere") -> list[dict[str, str]]:
    """The drawers of the reply's outline that are a type it may write,
    titles tidied and each title once -- or the template's own when none
    is -- then the template's drawers of the app's types (people, the
    timeline, branches: never filled by the reply), each with a new id. A
    place sphere gets no Branches drawer (ruling P23): it never branches."""

    taken: set[str] = set()
    found: list[dict[str, str]] = []
    titles: set[str] = set()
    for drawer in raw if isinstance(raw, list) else []:
        if not isinstance(drawer, dict):
            continue
        type_ = _tidy(drawer.get("type")).lower()
        title = _tidy(drawer.get("title"))
        if type_ not in TYPE_HELP or not title or title.casefold() in titles:
            continue
        titles.add(title.casefold())
        found.append({"id": _new_drawer_id(taken), "type": type_, "title": title})
    start = spheres.TEMPLATE_DRAWERS[template]
    if not found:
        found = [
            {"id": _new_drawer_id(taken), "type": type_, "title": title}
            for type_, title in start
            if type_ in TYPE_HELP
        ]
    found += [
        {"id": _new_drawer_id(taken), "type": type_, "title": title}
        for type_, title in start
        if type_ not in TYPE_HELP and (kind != "place" or type_ != "branches")
    ]
    return found


# a template drawer's title, as an item may name it, to its type
_TITLE_TYPES = {
    title.casefold(): type_
    for start in spheres.TEMPLATE_DRAWERS.values()
    for type_, title in start
}


def _drawer_for(title: object, drawers: list[dict[str, str]]) -> str:
    """The drawer an item naming `title` goes in: the drawer of that title;
    else the first of the type the title names (a drawer type, or a
    template's drawer title); else unsorted."""

    key = _tidy(title).casefold()
    for drawer in drawers:
        if drawer["title"].casefold() == key:
            return drawer["id"]
    type_ = key if key in TYPE_HELP else _TITLE_TYPES.get(key)
    for drawer in drawers:
        if drawer["type"] == type_:
            return drawer["id"]
    return UNSORTED_DRAWER_ID


def _item(raw: object, drawer_id: str) -> dict[str, Any] | None:
    """One reply item as a preview item, or `None` with no text. A
    nameless item is a statement (kind ""); a named one's kind outside
    `ITEM_KINDS` is lore."""

    if not isinstance(raw, dict):
        return None
    text = _tidy(raw.get("text"))
    if not text:
        return None
    name = _tidy(raw.get("name"))
    if not name.strip(" .") or name.casefold() in ARTICLES:
        # no name, or an article alone ("the"): a statement
        return {"drawer_id": drawer_id, "name": "", "text": text, "kind": ""}
    kind = _tidy(raw.get("kind")).lower()
    return {
        "drawer_id": drawer_id,
        "name": name,
        "text": text,
        "kind": kind if kind in ITEM_KINDS else "lore",
    }


def _named_keys(view: WorldView, state: ThingState) -> set[str]:
    keys = {name_key(view.name_of(state.id) or "")}
    aka = state.fields.get("aka")
    for entry in aka if isinstance(aka, list) else []:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            keys.add(name_key(entry["name"]))
    return keys - {""}


def _as_statement(item: dict[str, Any]) -> dict[str, Any]:
    """A named item kept as a statement: its text, led by its name unless
    the text already uses it, so linking still finds the name."""

    name, text = item["name"], item["text"]
    if name_key(name) not in text.casefold():
        text = f"{name}: {text}"
    kept = {"overrides": item["overrides"]} if item.get("overrides") else {}
    return {
        "drawer_id": item["drawer_id"],
        "name": "",
        "text": text,
        "kind": "",
        **kept,
    }


def _settle_items(
    view: WorldView,
    items: list[dict[str, Any]],
    own_keys: set[str],
    parts: list[ThingState],
    adopt: dict[str, str],
    as_new: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """`items` matched against the world, each name and statement once:

    - an item naming the sphere itself is dropped;
    - one naming an entry already part of it is dropped, and that entry is
      filed in the item's drawer (`adopt`, thing id -> drawer id, first
      item wins);
    - one naming a stub of a `PART_OF_KINDS` kind that's in no sphere links
      it (`thing_id`): a nested sphere stub too, never a character;
    - one naming any other thing in the world becomes a statement;
    - any other, or one named like a name the owner treats as new
      (`as_new`), makes a stub on accept."""

    part_of_keys = {key: part.id for part in parts for key in _named_keys(view, part)}
    seen: set[str] = set()
    settled: list[dict[str, Any]] = []
    for item in items:
        if not item["name"]:
            key = "text:" + item["text"].casefold()
            if key not in seen:
                seen.add(key)
                settled.append(item)
            continue
        key = name_key(item["name"])
        if key in seen or key in own_keys:
            continue
        seen.add(key)
        if is_new(item["name"], as_new):
            settled.append(item)
            continue
        if key in part_of_keys:
            adopt.setdefault(part_of_keys[key], item["drawer_id"])
            continue
        thing_id = existing_id(view, item["name"], item["kind"])
        state = view.thing(thing_id) if thing_id is not None else None
        if state is None:
            settled.append(item)
        elif (
            state.is_stub
            and state.kind in PART_OF_KINDS
            and state.fields.get("part_of") is None
        ):
            settled.append({**item, "thing_id": state.id})
        else:
            settled.append(_as_statement(item))
    return settled


def _months(calendar: Calendar) -> set[str]:
    return {month.casefold() for month in calendar.month_names}


def _listed_names(raw: object, calendar: Calendar) -> list[NewName]:
    """A reply's "names", less month names ("May" listed as an event)."""

    months = _months(calendar)
    return [n for n in create.name_entries(raw) if name_key(n.name) not in months]


# --- the context -------------------------------------------------------------


def _parts_of(view: WorldView, thing_id: str) -> list[ThingState]:
    """The things part of `thing_id` now, in the order they were made, of
    the kinds a drawer holds (`PART_OF_KINDS`)."""

    found = []
    for state in sorted(view.things(), key=lambda thing: thing.created):
        if state.kind not in PART_OF_KINDS:
            continue
        link = state.fields.get("part_of")
        if isinstance(link, dict) and link.get("sphere") == thing_id:
            found.append(state)
    return found


def _rendered_facts(view: WorldView, state: ThingState) -> list[str]:
    return [
        view.render(fact.text)
        for fact in sorted(state.facts, key=lambda fact: fact.created)
    ]


def _part_heading(view: WorldView, state: ThingState) -> str:
    return entry_label(view.name_of(state.id) or "", state.kind, everyday_name(state))


def _mention_vars(
    gathered: MentionContext | None, skip: set[str]
) -> tuple[list[tuple[str, str]], list[tuple[str, list[str]]]]:
    """The "Mentioned elsewhere" and "About those" blocks, as
    `preview_thing` builds them, leaving out the entries in `skip` (those
    part of the sphere: they're shown as such)."""

    if gathered is None:
        return [], []
    mentions = [
        (
            create._mention_lead(
                m.owner_name, m.owner_kind, m.category, m.owner_everyday
            ),
            m.text,
        )
        for m in gathered.mentioned
        if m.owner_id not in skip
    ]
    about = [
        (entry_label(a.name, a.kind, a.everyday), a.facts)
        for a in gathered.about
        if a.facts and a.id not in skip
    ]
    return mentions, about


def _calendar_vars(world: World) -> dict[str, Any]:
    calendar = world.calendar
    now = create.current_date(world)
    now_year = now.to_datetime().year
    era = create._era_at(calendar, now_year)
    return {
        "now_label": calendar.format(now),
        "now_year": create._shown_year(calendar, now_year),
        "era": era.name if era is not None else "",
        "month_names": calendar.month_names,
    }


# --- the core ----------------------------------------------------------------


def _promotable(state: ThingState) -> bool:
    """Whether a thing can be promoted: a lore entry, a place that isn't a
    sphere yet, or a stub of any kind but `sphere` (that one's expanded)."""

    if state.kind == "lore" or (state.kind == "place" and not spheres.is_sphere(state)):
        return True
    return state.is_stub and state.kind != "sphere"


async def preview_sphere(
    world: World,
    template: str,
    prompt: str,
    fields: dict[str, Any],
    client: Any,
    *,
    stub_id: str | None = None,
    picks: dict[str, str] | None = None,
    new_names: Sequence[str] = (),
    promote_id: str | None = None,
    reply: str | None = None,
) -> SpherePreview:
    """A sphere's core from `prompt`, under `template`, without writing
    anything: one call (`world/sphere-core`), with no prose call, since the
    reply's summary is the description.

    - with `stub_id`, the stub is expanded: its name is used, its
      mentions are context, and it joins the sphere it belongs in
      (`create.child_part_of`, child first), as `create.preview_thing`
      does;
    - with `promote_id`, a lore entry, a place or a stub is promoted: its
      facts are "Already known" and stay on it;
    - either way, the entries already part of it are "Already part of it"
      and become `adopted`;
    - `picks` and `new_names` are the prompt's names, as in
      `create.preview_thing`.

    `fields` are the owner's picks (`name`, a place's or branch's
    `parent`, ...); an `agent` among them wins over the template's flag.

    A given `reply` (the browser tests' fixed reply) stands in for the
    model's, read the same way; no client is needed then."""

    if template not in SPHERE_TEMPLATES:
        raise ValueError(f"no such sphere template: {template!r}")
    if stub_id is not None and promote_id is not None:
        raise ValueError("a preview expands a stub or promotes a thing, not both")
    view = world.view()
    target: ThingState | None = None
    if stub_id is not None:
        target = create._live_stub(view, stub_id)
    elif promote_id is not None:
        target = view.thing(promote_id)
        if target is None:
            raise ValueError(f"no such thing: {promote_id}")
        if not _promotable(target):
            raise ValueError(f"a {target.kind} can't be promoted to a sphere")
    if reply is None:
        prose_gen.require_client(client)

    kind = "place" if target is not None and target.kind == "place" else "sphere"
    kind_spec = get_kind(kind)
    fields = dict(fields or {})
    for field, value in fields.items():
        validate_field(kind_spec, field, value)
    owner_aka = fields.pop("aka", None)
    agent = fields.pop("agent", TEMPLATE_AGENT[template])
    for field in ("stub", "template", "drawers", "part_of"):
        fields.pop(field, None)
    if target is not None and not fields.get("name"):
        fields["name"] = view.name_of(target.id) or ""
    if not prompt.strip():
        if target is None:
            raise ValueError("a sphere needs a prompt")
        prompt = fields["name"]
    treated_as_new = [name for name in new_names if name.strip()]
    picks = {
        written: thing_id
        for written, thing_id in (picks or {}).items()
        if not is_new(written, treated_as_new)
    }

    parts = _parts_of(view, target.id) if target is not None else []
    part_ids = {part.id for part in parts}
    gathered = gather_mentions(view, target.id) if target is not None else None
    in_context = {
        *picks.values(),
        *part_ids,
        *([target.id] if target is not None else []),
        *(m.owner_id for m in (gathered.mentioned if gathered is not None else [])),
    }
    picks.update(
        create._found_in_prompt(view, prompt, picks, treated_as_new, in_context)
    )
    named = create._named_in_prompt(
        view, picks, target.id if target is not None else None
    )
    # an expanded stub joins the sphere it belongs in, child first, as
    # `create.preview_thing` has it (never a branch: its parent is its own)
    part_of = (
        create.child_part_of(view, target, prompt, picks)
        if stub_id is not None and target is not None and "parent" not in fields
        else None
    )
    mentions, about = _mention_vars(gathered, part_ids)
    known = _rendered_facts(view, target) if target is not None else []
    held = [(_part_heading(view, part), _rendered_facts(view, part)) for part in parts]

    template_vars: dict[str, Any] = {
        "label": TEMPLATE_LABELS[template],
        "template": "sphere" if template == "other" else template,
        "agent": agent,
        "prompt": prompt,
        "known": known,
        "part_of": held,
        "mentions": mentions,
        "about": about,
        "named": named,
        "start_drawers": [
            (type_, title)
            for type_, title in spheres.TEMPLATE_DRAWERS[template]
            if type_ in TYPE_HELP
        ],
        "types": list(TYPE_HELP.items()),
        "has_name": bool(fields.get("name")),
        "name": fields.get("name") or "",
        **_calendar_vars(world),
    }
    if reply is None:
        with world_ai_call():
            _response, extracted = await Prompt.request(
                "world.sphere-core", client, CORE_PROMPT_KIND, vars=template_vars
            )
        reply = extracted["response"]
    core = _reply_object(reply, "drawers")
    if core is None:
        raise ValueError("the model's reply had no drawer outline in it")

    name = fields.pop("name", None) or _tidy(core.get("name")).strip(" .")
    name = name or create._fallback_name(prompt)
    calendar = world.calendar
    now_year = create.current_date(world).to_datetime().year
    facts: list[PreviewFact] = []
    for entry in core.get("timeline") or []:
        text = _tidy(entry.get("text")) if isinstance(entry, dict) else ""
        if text and all(fact.text != text for fact in facts):
            since = create._parse_since(entry.get("year"), calendar, now_year)
            # an entry with no year of this calendar up to now (after now,
            # or unreadable) is no moment of the timeline: it's "about"
            category = "timeline" if since is not None else "about"
            facts.append(PreviewFact(category=category, text=text, since=since))

    drawers = _outline(core.get("drawers"), template, kind)
    raw_items = [
        _item(raw, _drawer_for(raw.get("drawer"), drawers))
        for raw in core.get("items") or []
        if isinstance(raw, dict)
    ]
    own_keys = {name_key(name)} | (
        _named_keys(view, target) if target is not None else set()
    )
    adopt: dict[str, str] = {}
    items = _settle_items(
        view,
        [item for item in raw_items if item],
        own_keys,
        parts,
        adopt,
        treated_as_new,
    )
    shelves = _shelves(drawers)
    items = _filed(view, items, shelves)
    # an entry the reply relists is filed in its drawer; one it doesn't is
    # filed by a guess (`spheres.entry_drawer`), so a council the reply
    # leaves out still lands in Hierarchy
    adopted = [
        {
            "thing_id": part.id,
            "drawer_id": spheres.entry_drawer(
                shelves,
                part.kind,
                adopt.get(part.id),
                view.name_of(part.id) or "",
            ),
        }
        for part in parts
    ]

    if owner_aka is not None:
        aka_entries = list(owner_aka)
    else:
        existing = (
            create._aka_entries(target.fields.get("aka")) if target is not None else []
        )
        aka_entries = [*existing, *create._aka_entries(core.get("aka"))]
    skip = target.id if target is not None else None
    aka = clean_aka(aka_entries, name, name_keys(view, skip=skip))
    own_names = [name, *(str(entry["name"]) for entry in aka)]
    own_names += [item["name"] for item in items if item["name"]]
    if target is not None:
        own_names.append(view.name_of(target.id) or "")
    stub_names = create._new_names(
        view,
        _listed_names(core.get("names"), calendar),
        [fact.text for fact in facts] + [item["text"] for item in items],
        own_names,
        list(picks),
        treated_as_new,
    )
    summary = _tidy(core.get("summary"))

    context = [(f"Part of it: {heading}", texts) for heading, texts in held]
    if stub_id is not None and target is not None:
        context = mention_context(view, target.id) + context
    context += [
        (f'Named in this prompt: "{written}" means {label}', texts)
        for written, label, texts in named
    ]
    log.info(
        "spheres.preview",
        template=template,
        name=name,
        drawers=len(drawers),
        items=len(items),
        adopted=len(adopted),
        new_names=len(stub_names),
        stub_id=stub_id,
        promote_id=promote_id,
    )
    return SpherePreview(
        kind=kind,
        prompt=prompt,
        fields=fields,
        name=name,
        facts=facts,
        prose={"description": summary} if summary else {},
        aka=aka,
        new_names=stub_names,
        stub_id=stub_id,
        matching_stub_id=(
            None if target is not None else create.matching_stub(view, "sphere", name)
        ),
        context=context,
        picks=picks,
        treated_as_new=treated_as_new,
        template=template,
        agent=agent,
        drawers=drawers,
        items=items,
        adopted=adopted,
        promote_id=promote_id,
        part_of=part_of,
    )


# --- writing -----------------------------------------------------------------


def _shelves(drawers: Sequence[dict[str, str]]) -> list[spheres.Drawer]:
    return [spheres.Drawer.model_validate(drawer) for drawer in drawers]


def _item_kind(view: WorldView, item: dict[str, Any]) -> str:
    """The kind an item is filed as: its stub's, for one linking a stub;
    its own (lore outside `ITEM_KINDS`) for a named one; "" for a
    statement."""

    if item.get("thing_id"):
        state = view.thing(item["thing_id"])
        return state.kind if state is not None else "lore"
    if not item.get("name"):
        return ""
    return item["kind"] if item["kind"] in ITEM_KINDS else "lore"


def _filed(
    view: WorldView, items: list[dict[str, Any]], drawers: Sequence[spheres.Drawer]
) -> list[dict[str, Any]]:
    """`items`, each in a drawer it may go in (`spheres.entry_drawer`, the
    rule `set_part_of` keeps): a place named in a practices drawer goes to
    the places drawer, lore in Holy Sites to Unsorted (or, named like a
    council, to the structure drawer); a statement in the people drawer to
    Unsorted."""

    return [
        {
            **item,
            "drawer_id": spheres.entry_drawer(
                drawers, _item_kind(view, item), item["drawer_id"], item["name"]
            ),
        }
        for item in items
    ]


def _without_article(name: str) -> str:
    words = name.split()
    if len(words) > 1 and words[0].casefold() in ("the", "a", "an"):
        return " ".join(words[1:])
    return name


def _write_items(
    rev: Revision,
    world: World,
    sphere_id: str,
    items: list[dict[str, Any]],
    made: dict[str, str],
    *,
    picks: dict[str, str] | None = None,
    as_new: Sequence[str] = (),
) -> set[str]:
    """Write `items` into the sphere, in `rev`: a named item is a stub of
    its kind part of the sphere in its drawer (or, with a `thing_id`, that
    stub put there), with its text as a fact; a nameless one is a
    `statement` fact of the sphere whose origin names its drawer, each in
    a drawer it may go in (`_filed`). `made`
    (written name -> id, from `make_stubs`) gains the item stubs, so every
    text links them; texts are linked once all are made. Returns the ids
    the written texts link to."""

    # filed in drawers they may go in, whatever the preview said
    items = _filed(world.view(), items, spheres.drawers(world.view(), sphere_id))
    placed: list[tuple[str, dict[str, Any]]] = []
    for item in items:
        if not item.get("name"):
            continue
        part_of = {"sphere": sphere_id, "drawer": item["drawer_id"]}
        thing_id = item.get("thing_id")
        if thing_id:
            since = create.part_of_since(world, thing_id, strict=False)
            rev.set_field(thing_id, "part_of", part_of, since)
        else:
            kind = item["kind"] if item["kind"] in ITEM_KINDS else "lore"
            words = item["name"].split()
            # a lowercase leading "the" isn't part of the name, as with
            # `make_stubs` ("the Dawn Vigil" makes "Dawn Vigil")
            name = (
                " ".join(words[1:])
                if len(words) > 1 and words[0] == "the"
                else item["name"]
            )
            thing_id = rev.create_thing(
                kind,
                fields={"name": name, "stub": {"ignored": False}, "part_of": part_of},
            )
        placed.append((thing_id, item))
        for form in (item["name"], _without_article(item["name"])):
            made.setdefault(form, thing_id)

    # the revision's own view: the stubs just made are in it
    linking = world.view()
    linked: set[str] = set()

    def linked_text(text: str, owner: str) -> str:
        written = link_text(
            linking, text, picks=picks, new_names=made, owner=owner, as_new=as_new
        )
        linked.update(parse_refs(written))
        return written

    for thing_id, item in placed:
        state = linking.thing(thing_id)
        category = _ITEM_CATEGORY.get(state.kind if state else "", "general")
        rev.add_fact(thing_id, category, linked_text(item["text"], thing_id))
    for item in items:
        if not item.get("name"):
            rev.add_fact(
                sphere_id,
                "statement",
                linked_text(item["text"], sphere_id),
                origin={"drawer": item["drawer_id"]},
                overrides=item.get("overrides") or None,
            )
    return linked


def _write_core(
    rev: Revision, view: WorldView, preview: SpherePreview, target: ThingState | None
) -> str:
    """The sphere's own thing, in `rev`: a new one, or the stub or promoted
    thing kept under its id -- made a `sphere` (`promote_to_sphere`), or a
    place staying a place. Then its template, agent flag and drawers; a
    branch's `parent` is linked from its `split` either way."""

    fields: dict[str, Any] = dict(preview.fields)
    # a branch's parent link holds from the date it splits
    parent = fields.pop("parent", None) if preview.split is not None else None
    if target is None:
        fields["name"] = preview.name
        if preview.aka:
            fields["aka"] = preview.aka
        thing_id = rev.create_thing(preview.kind, fields)
    else:
        thing_id = target.id
        if target.kind != preview.kind:
            # a stub's kind changes as a promotion's does: `change_stub_kind`
            # would refuse the facts a sphere has no category for (an item
            # stub's text), which this files as about or timeline
            rev.promote_to_sphere(thing_id)
        for field, value in fields.items():
            rev.set_field(thing_id, field, value, None)
        create.name_thing(rev, view, target, preview.name, preview.aka)
        if target.is_stub:
            rev.remove_field_value(thing_id, "stub", None)
    if parent is not None:
        rev.set_field(thing_id, "parent", parent, preview.split)
    rev.set_field(thing_id, "template", preview.template, None)
    rev.set_field(thing_id, "agent", preview.agent, None)
    rev.set_field(thing_id, "drawers", preview.drawers, None)
    if preview.drops:
        rev.set_field(thing_id, "drops", preview.drops, None)
    return thing_id


def _fact_text(view: WorldView, fact_id: str) -> str | None:
    """The live fact's text as stored (links kept), or `None`."""

    for state in view.things():
        for fact in state.facts:
            if fact.fact_id == fact_id:
                return fact.text
    return None


def _orphans(
    view: WorldView, made: dict[str, str], new_names: list[NewName], linked: set[str]
) -> list[NewName]:
    """The new names whose stubs (made in this revision) nothing links."""

    orphans = {
        thing_id
        for thing_id in made.values()
        if view.thing(thing_id) is None and thing_id not in linked
    }
    return [n for n in new_names if made.get(" ".join(n.name.split())) in orphans]


def _write_sphere(
    world: World,
    view: WorldView,
    preview: SpherePreview,
    target: ThingState | None,
    new_names: list[NewName],
) -> str:
    with world.revision(Source.manual(note=_CREATED_NOTE)) as rev:
        made = make_stubs(rev, view, new_names, fresh=preview.treated_as_new)
        stubs = dict(made)
        thing_id = _write_core(rev, view, preview, target)
        if preview.part_of is not None:
            rev.set_field(
                thing_id,
                "part_of",
                preview.part_of,
                create.part_of_since(world, thing_id, strict=False),
            )
        for adopted in preview.adopted:
            rev.set_field(
                adopted["thing_id"],
                "part_of",
                {"sphere": thing_id, "drawer": adopted["drawer_id"]},
                create.part_of_since(world, adopted["thing_id"], strict=False),
            )
        linked = _write_items(
            rev,
            world,
            thing_id,
            [item for item in preview.items if item.get("ticked", True)],
            made,
            picks=preview.picks,
            as_new=preview.treated_as_new,
        )
        linking = world.view()
        summary = preview.prose.get("description", "").strip()
        if summary:
            # the summary's source of truth (ruling P21): the description
            # is written from it first, so other about facts never wipe it
            text = link_text(
                linking,
                summary,
                picks=preview.picks,
                new_names=made,
                owner=thing_id,
                as_new=preview.treated_as_new,
            )
            linked.update(parse_refs(text))
            rev.add_fact(thing_id, "about", text, origin=SUMMARY_ORIGIN)
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
            rev.add_fact(
                thing_id,
                fact.category,
                text,
                valid_from=fact.since,
                overrides=fact.overrides or None,
            )
        for fact_id in preview.rejects:
            rejected = _fact_text(view, fact_id)
            if rejected is None:
                raise ValueError(f"the rejected fact is gone: {fact_id}")
            rev.add_fact(thing_id, "about", f"Rejects: {rejected}", overrides=[fact_id])
        unlinked = _orphans(view, stubs, new_names, linked)
        if unlinked:
            raise create._UnlinkedNames([n.name for n in unlinked])
    return thing_id


def _without_unlinked(
    new_names: list[NewName], unlinked: create._UnlinkedNames
) -> list[NewName]:
    log.debug("spheres.unlinked_names", names=unlinked.names)
    kept = [n for n in new_names if n.name not in unlinked.names]
    if len(kept) == len(new_names):
        raise RuntimeError(f"unlinked stubs with no name: {unlinked}")
    return kept


def accept_sphere(world: World, preview: SpherePreview) -> str:
    """Write `preview` in one revision, then cache its summary as the
    sphere's description. Returns the sphere's id.

    - expanding a stub fills it under its id, its kind changed to the
      preview's (`sphere`, or a place stays a place);
    - promoting keeps the thing's id and facts: a lore entry or stub
      becomes a `sphere` (`Revision.promote_to_sphere`), a place stays a
      place;
    - otherwise a new sphere is made.

    Then its template, agent flag and drawers are set, the adopted entries
    filed in their drawers, its items written (`_write_items`), its new
    names made stubs and its timeline written, every text linked. As in
    `create.accept_preview`, a new name nothing ends up linking makes no
    stub. A deleted stub or promoted thing is a `ValueError`."""

    view = world.view()
    target: ThingState | None = None
    if preview.stub_id is not None:
        target = create._live_stub(view, preview.stub_id)
    elif preview.promote_id is not None:
        target = view.thing(preview.promote_id)
        if target is None:
            raise ValueError(f"the thing was deleted: {preview.promote_id}")

    before = world.head_rev()
    new_names = list(preview.new_names)
    while True:
        try:
            thing_id = _write_sphere(world, view, preview, target, new_names)
            break
        except create._UnlinkedNames as unlinked:
            # written again without them, in a fresh revision: the first
            # was rolled back whole
            new_names = _without_unlinked(new_names, unlinked)

    if "description" in preview.prose:
        # the summary was written from everything, as the sphere reads at
        # the open, "now" end of its timeline
        start, end = prose_gen.stretch_containing(world, thing_id, None)
        # as `create.accept_preview` has it: a summary written from a fact
        # or item the owner left unticked is cached as of before the
        # accept, so it reads stale
        unticked = any(not fact.ticked for fact in preview.facts) or any(
            not item.get("ticked", True) for item in preview.items
        )
        world.prose().put(
            thing_id,
            "description",
            start,
            end,
            preview.prose["description"],
            rev=before if unticked else None,
        )
    log.info(
        "spheres.accept",
        thing_id=thing_id,
        template=preview.template,
        items=len(preview.items),
        adopted=len(preview.adopted),
        stub=preview.stub_id is not None,
        promoted=preview.promote_id is not None,
    )
    return thing_id


# --- Fill --------------------------------------------------------------------


def _sphere_state(view: WorldView, sphere_id: str) -> ThingState:
    state = view.thing(sphere_id)
    if state is None or not spheres.is_sphere(state):
        raise ValueError(f"not a sphere: {sphere_id}")
    return state


def _fill_drawer_of(view: WorldView, sphere_id: str, drawer_id: str) -> spheres.Drawer:
    drawer = next(
        (d for d in spheres.drawers(view, sphere_id) if d.id == drawer_id), None
    )
    if drawer is None:
        raise ValueError(f"the sphere has no drawer {drawer_id}")
    if drawer.type not in TYPE_HELP:
        raise ValueError(f"a {drawer.type} drawer isn't filled")
    return drawer


def _item_line(view: WorldView, item: spheres.Item) -> str:
    """A drawer's item as Fill lists it: a statement's text, or a thing's
    name and all its facts (`spheres.item_line`: no doubled name)."""

    if item.thing_id is None:
        return item.text
    state = view.thing(item.thing_id)
    texts = _rendered_facts(view, state) if state is not None else []
    return spheres.item_line(item.name, " ".join(texts))


def _summary(world: World, view: WorldView, state: ThingState) -> str:
    """The sphere's summary (`spheres.summary`): its cached description,
    else its summary fact."""

    return spheres.summary(view, state.id, create.cached_summary(world, state.id))


def _timeline_lines(world: World, view: WorldView, sphere_id: str) -> list[str]:
    """The sphere's timeline as prompts list it, "<year>: <text>" (an
    undated fact without a year)."""

    lines = []
    for fact in spheres.timeline(view, sphere_id):
        text = view.render(fact.text)
        if fact.valid_from is not None:
            year = fact.valid_from.to_datetime().year
            text = f"{create._shown_year(world.calendar, year)}: {text}"
        lines.append(text)
    return lines


def _held_repeat(
    view: WorldView, sphere_id: str, item: dict[str, Any], held: list[spheres.Item]
) -> dict[str, Any] | None:
    """The sphere's item a Fill item says again, as `repeat_of` shows it
    (`{fact_id, owner_id, owner_name, text, score}`), or `None`: one of
    the same name, ignoring case and a leading article (score 1), or one
    of (nearly) the same topic words (`_REPEAT_OVERLAP` of the two texts'
    words in common)."""

    def found(other: spheres.Item, score: float) -> dict[str, Any]:
        owner = other.thing_id or sphere_id
        return {
            "fact_id": other.fact_id,
            "owner_id": owner,
            "owner_name": view.name_of(owner) or "",
            "text": spheres.item_line(other.name, other.text)
            if other.name
            else other.text,
            "score": score,
        }

    if item["name"]:
        key = name_key(item["name"])
        for other in held:
            if other.thing_id and name_key(other.name) == key:
                return found(other, 1.0)
    words = create._content_words(item["text"], set())
    for other in held:
        theirs = create._content_words(other.text, set())
        union = words | theirs
        if union and (score := len(words & theirs) / len(union)) >= _REPEAT_OVERLAP:
            return found(other, score)
    return None


def _written_by(text: str, new: NewName) -> bool:
    return any(
        create._written_in([text], form) is not None
        for form in (new.name, *new.written)
    )


async def fill_drawer(
    world: World,
    sphere_id: str,
    drawer_id: str,
    client: Any,
    *,
    reply: str | None = None,
) -> FillPreview:
    """New items for one drawer of a sphere (`world/sphere-fill`), as
    `SpherePreview.items` holds them, and facts about other entries,
    without writing anything (`FillPreview`). Each item also carries
    `names`: the new names (`NewName` dumps) its text is the first to use,
    which `accept_fill` makes stubs for.

    The prompt has the sphere's summary, timeline and writable drawers
    with what they hold, its mentions (but those from entries part of
    it), and the entries near it (`create.nearby_ids`, at the world's
    curation settings). An item repeating one the sphere holds comes
    last, unticked, with that item as its `repeat_of`; the rest are matched against the world as the core's are, and one
    repeating what the sphere or an entry near it says is flagged
    (`repeat_of`; unticked at the untick threshold). The reply's
    elsewhere items are read as create reads them (`create.parse_elsewhere`),
    less those about the reply's own new items. A given `reply` stands in
    for the model's, as in `preview_sphere`."""

    view = world.view()
    state = _sphere_state(view, sphere_id)
    drawer = _fill_drawer_of(view, sphere_id, drawer_id)
    if reply is None:
        prose_gen.require_client(client)
    calendar = world.calendar

    held = spheres.items(view, sphere_id)
    # (title, type, lines, whether it's the drawer to fill): matched by id,
    # so two drawers of one title stay apart
    lines = [
        (
            d.title,
            d.type,
            [_item_line(view, i) for i in held if i.drawer_id == d.id],
            d.id == drawer.id,
        )
        for d in spheres.drawers(view, sphere_id)
        if d.type in TYPE_HELP
    ]
    members = {item.thing_id for item in held if item.thing_id}
    mentions, about = _mention_vars(gather_mentions(view, sphere_id), members)
    template = state.fields.get("template")
    template = template if template in TEMPLATE_LABELS else "other"
    name = view.name_of(sphere_id) or ""
    settings = world.curation()
    near_ids = create.nearby_ids(view, [sphere_id], [], settings, {sphere_id})

    template_vars: dict[str, Any] = {
        "name": name,
        "label": TEMPLATE_LABELS[template],
        "drawer_title": drawer.title,
        "drawer_type": drawer.type,
        "drawer_help": TYPE_HELP[drawer.type],
        "summary": _summary(world, view, state),
        "timeline": _timeline_lines(world, view, sphere_id),
        "drawers": lines,
        "existing": [line for *_, ls, target in lines if target for line in ls],
        "mentions": mentions,
        "about": about,
        "nearby": create._nearby_lines(view, near_ids),
        **_calendar_vars(world),
    }
    if reply is None:
        with world_ai_call():
            _response, extracted = await Prompt.request(
                "world.sphere-fill", client, FILL_PROMPT_KIND, vars=template_vars
            )
        reply = extracted["response"]
    obj = _reply_object(reply, "new_items") or _reply_object(reply, "items")
    if obj is not None:
        raw: list[Any] = obj.get("new_items") or obj.get("items") or []
    else:
        # a broken wrapper (a statement written `{ "", "text": ...}`): the
        # complete items are still there on their own
        raw = [
            o
            for o in json_objects(reply)
            if isinstance(o.get("text"), str)
            and not {"tag", "everyday", "entry"} & o.keys()
        ]

    parsed = [item for raw_item in raw if (item := _item(raw_item, drawer.id))]
    # an item the sphere holds already isn't dropped silently (goal 3): it
    # comes last, unticked, with the item it repeats
    held_repeats = [
        (item, _held_repeat(view, sphere_id, item, held)) for item in parsed
    ]
    fresh = [item for item, repeat_of in held_repeats if repeat_of is None]
    own_keys = _named_keys(view, state)
    items = _settle_items(view, fresh, own_keys, _parts_of(view, sphere_id), {})
    items = _filed(view, items, spheres.drawers(view, sphere_id))

    own_names = [name, *(item["name"] for item in items if item["name"])]
    listed = _listed_names(obj.get("names") if obj is not None else None, calendar)
    new = create._new_names(view, listed, [item["text"] for item in items], own_names)
    for item in items:
        item["names"] = []
    for new_name in new:
        first = next((i for i in items if _written_by(i["text"], new_name)), None)
        if first is not None:
            first["names"].append(new_name.model_dump())

    flags = create.repeat_flags(
        view, [item["text"] for item in items], [sphere_id, *near_ids], settings
    )
    for item, (repeat_of, ticked) in zip(items, flags):
        item["repeat_of"], item["ticked"] = repeat_of, ticked
    repeats = [
        {**item, "names": [], "repeat_of": repeat_of, "ticked": False}
        for item, repeat_of in held_repeats
        if repeat_of is not None
    ]
    items += _filed(view, repeats, spheres.drawers(view, sphere_id))
    if obj is not None:
        raw_elsewhere = obj.get("elsewhere")
    else:
        raw_elsewhere = create.raw_elsewhere(reply, None)
    elsewhere = create.parse_elsewhere(
        raw_elsewhere,
        view,
        own_keys=own_keys,
        own_ids={sphere_id},
        listed=listed,
        calendar=calendar,
        now_year=create.current_date(world).to_datetime().year,
        prefer=near_ids,
        holder=lambda held: create.holder_named(view, held),
        new_items=[item["name"] for item in parsed if item["name"]],
    )
    create.flag_elsewhere_repeats(view, elsewhere, settings)
    log.info(
        "spheres.fill",
        sphere_id=sphere_id,
        drawer=drawer.title,
        got=len(parsed),
        repeats=len(repeats),
        kept=len(items) - len(repeats),
        flagged=sum(1 for item in items if item["repeat_of"] is not None),
        elsewhere=len(elsewhere),
    )
    return FillPreview(items=items, elsewhere=elsewhere)


def accept_fill(
    world: World,
    sphere_id: str,
    drawer_id: str,
    items: list[dict[str, Any]],
    elsewhere: Sequence[ElsewhereFact] = (),
    *,
    notes: list[str] | None = None,
) -> None:
    """Write Fill's ticked `items` (as `fill_drawer` gave them, less any the
    owner dropped; an item with `ticked` false, a repeat, isn't written)
    into the sphere in one revision, as `accept_sphere` writes the core's:
    named items become stubs part of it, nameless ones its statements, in
    `drawer_id` unless an item names its own drawer. The new names the
    kept items carry become stubs, unless nothing links them. The ticked
    `elsewhere` facts go onto their targets in the same revision, as
    `create.accept_preview` writes them; one whose target was deleted is
    dropped with a note in `notes`."""

    view = world.view()
    _sphere_state(view, sphere_id)
    _fill_drawer_of(view, sphere_id, drawer_id)
    items = [
        {**item, "drawer_id": item.get("drawer_id") or drawer_id}
        for item in items
        if item.get("ticked", True)
    ]
    others = create.live_elsewhere(view, elsewhere, {sphere_id}, notes)
    elsewhere_names = [e.new for e in others if e.new is not None]
    new_names: list[NewName] = []
    for item in items:
        for raw in item.get("names") or []:
            new_name = NewName.model_validate(raw)
            if all(name_key(n.name) != name_key(new_name.name) for n in new_names):
                new_names.append(new_name)

    while True:
        try:
            with world.revision(Source.manual(note=_FILLED_NOTE)) as rev:
                made = make_stubs(rev, view, [*new_names, *elsewhere_names])
                stubs = dict(made)
                linked = _write_items(rev, world, sphere_id, items, made)
                linked |= create.write_elsewhere(rev, world.view(), view, others, made)
                unlinked = _orphans(view, stubs, new_names, linked)
                if unlinked:
                    raise create._UnlinkedNames([n.name for n in unlinked])
            break
        except create._UnlinkedNames as unlinked_names:
            new_names = _without_unlinked(new_names, unlinked_names)
    log.info(
        "spheres.fill_accept",
        sphere_id=sphere_id,
        items=len(items),
        elsewhere=len(others),
    )


# --- branches ----------------------------------------------------------------


def _parent_items(
    view: WorldView, parent_id: str, drawers: list[spheres.Drawer]
) -> list[dict[str, Any]]:
    """The parent's items a branch inherits, in `spheres.items` order,
    labelled F1...Fn: those in a drawer the core writes, or unsorted (not
    people, the timeline or branches)."""

    titles = {d.id: d.title for d in drawers if d.type in TYPE_HELP}
    titles[spheres.UNSORTED.id] = spheres.UNSORTED.title
    rows: list[dict[str, Any]] = []
    for item in spheres.items(view, parent_id):
        if item.drawer_id not in titles:
            continue
        rows.append(
            {
                "label": f"F{len(rows) + 1}",
                "thing_id": item.thing_id,
                "fact_id": item.fact_id,
                "source_id": item.source_id,
                "name": item.name,
                "text": _item_line(view, item),
                "drawer_id": item.drawer_id,
            }
        )
    return rows


def _branch_labels(
    value: object, rows: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str]]:
    """The thing ids and the fact ids of the `F1`-style labels in `value`
    (a list, or one label), each once. Unknown labels are dropped."""

    things: list[str] = []
    facts: list[str] = []
    for label in value if isinstance(value, list) else [value]:
        row = rows.get(label.strip().upper()) if isinstance(label, str) else None
        if row is None:
            log.debug("spheres.unknown_label", label=label)
        elif row["thing_id"] and row["thing_id"] not in things:
            things.append(row["thing_id"])
        elif row["fact_id"] and row["fact_id"] not in facts:
            facts.append(row["fact_id"])
    return things, facts


def _branch_outline(
    raw: object, parent_drawers: list[spheres.Drawer], template: str
) -> list[dict[str, str]]:
    """A branch's own drawers: the reply's of a type it may write and a
    title its parent lacks (the parent's serve it otherwise), then the
    template's app drawers of a type the parent lacks."""

    taken = {d.id for d in parent_drawers}
    titles = {d.title.casefold() for d in parent_drawers}
    types = {d.type for d in parent_drawers}
    found: list[dict[str, str]] = []
    for drawer in raw if isinstance(raw, list) else []:
        if not isinstance(drawer, dict):
            continue
        type_ = _tidy(drawer.get("type")).lower()
        title = _tidy(drawer.get("title"))
        if type_ not in TYPE_HELP or not title or title.casefold() in titles:
            continue
        titles.add(title.casefold())
        found.append({"id": _new_drawer_id(taken), "type": type_, "title": title})
    for type_, title in spheres.TEMPLATE_DRAWERS[template]:
        if type_ not in TYPE_HELP and type_ not in types:
            types.add(type_)
            found.append({"id": _new_drawer_id(taken), "type": type_, "title": title})
    return found


async def preview_branch(
    world: World,
    parent_id: str,
    prompt: str,
    client: Any,
    *,
    reply: str | None = None,
) -> SpherePreview:
    """A branch of the sphere `parent_id` from `prompt`, without writing
    anything: one call (`world/sphere-branch`). It's a `sphere` under its
    parent's template and agent flag, whose `parent` link holds from now
    (`split`). The prompt lists the parent's items labelled F1...Fn
    (`parent_items`); the reply's labels are mapped back (see the module
    docstring) to `drops`, `rejects` and its statements' `overrides`.

    An item naming one the branch inherits isn't made again; the rest are
    matched against the world as the core's are. A given `reply` stands in
    for the model's, as in `preview_sphere`."""

    if not prompt.strip():
        raise ValueError("a branch needs a prompt")
    view = world.view()
    parent = _sphere_state(view, parent_id)
    if parent.kind != "sphere":
        # a place sphere's `parent` is the place it lies in
        raise ValueError("only a sphere has branches")
    if reply is None:
        prose_gen.require_client(client)
    template = parent.fields.get("template")
    template = template if template in TEMPLATE_LABELS else "other"
    agent = parent.fields.get("agent")
    agent = agent if isinstance(agent, bool) else TEMPLATE_AGENT[template]
    parent_name = view.name_of(parent_id) or ""

    parent_drawers = spheres.drawers(view, parent_id)
    rows = _parent_items(view, parent_id, parent_drawers)
    by_label = {row["label"]: row for row in rows}
    titles = {d.id: d.title for d in parent_drawers}
    titles[spheres.UNSORTED.id] = spheres.UNSORTED.title
    in_context = {parent_id, *(row["thing_id"] for row in rows if row["thing_id"])}
    picks = create._found_in_prompt(view, prompt, {}, [], in_context)
    named = create._named_in_prompt(view, picks, None)

    template_vars: dict[str, Any] = {
        "label": TEMPLATE_LABELS[template],
        "agent": agent,
        "prompt": prompt,
        "parent_name": parent_name,
        "parent_summary": _summary(world, view, parent),
        "parent_timeline": _timeline_lines(world, view, parent_id),
        "inherited": [
            (row["label"], titles[row["drawer_id"]], row["text"]) for row in rows
        ],
        "named": named,
        "drawers": [(d.type, d.title) for d in parent_drawers if d.type in TYPE_HELP],
        "types": list(TYPE_HELP.items()),
        **_calendar_vars(world),
    }
    if reply is None:
        with world_ai_call():
            _response, extracted = await Prompt.request(
                "world.sphere-branch", client, CORE_PROMPT_KIND, vars=template_vars
            )
        reply = extracted["response"]
    core = _reply_object(reply, "items") or _reply_object(reply, "drawers")
    if core is None:
        raise ValueError("the model's reply had no items in it")

    drops, rejects = _branch_labels(core.get("drops") or [], by_label)
    calendar = world.calendar
    now_year = create.current_date(world).to_datetime().year
    facts: list[PreviewFact] = []
    for entry in core.get("timeline") or []:
        text = _tidy(entry.get("text")) if isinstance(entry, dict) else ""
        if text and all(fact.text != text for fact in facts):
            since = create._parse_since(entry.get("year"), calendar, now_year)
            things, overrides = _branch_labels(entry.get("overrides") or [], by_label)
            drops += [thing_id for thing_id in things if thing_id not in drops]
            facts.append(
                PreviewFact(
                    category="timeline" if since is not None else "about",
                    text=text,
                    since=since,
                    overrides=overrides,
                )
            )

    drawers = _branch_outline(core.get("drawers"), parent_drawers, template)
    every_drawer = drawers + [d.model_dump() for d in parent_drawers]
    raw_items = []
    for raw in core.get("items") or []:
        if not isinstance(raw, dict):
            continue
        item = _item(raw, _drawer_for(raw.get("drawer"), every_drawer))
        if item is None:
            continue
        things, overrides = _branch_labels(raw.get("overrides") or [], by_label)
        drops += [thing_id for thing_id in things if thing_id not in drops]
        if overrides:
            item["overrides"] = overrides
        raw_items.append(item)

    name = _tidy(core.get("name")).strip(" .") or create._fallback_name(prompt)
    # an item naming one the branch still inherits isn't made again
    kept = [row for row in rows if row["thing_id"] and row["thing_id"] not in drops]
    own_keys = {name_key(name)} | {name_key(row["name"]) for row in kept}
    items = _settle_items(view, raw_items, own_keys, [], {})
    items = _filed(view, items, _shelves(every_drawer))
    for item in items:
        # a named item can't carry an override: the branch rejects the
        # statements it replaces instead
        if item["name"] and item.get("overrides"):
            rejects += [f for f in item.pop("overrides") if f not in rejects]
    # each statement is overridden once: by the first of the branch's
    # statements replacing it, else by a rejection
    replaced: set[str] = set()
    for item in items:
        if item.get("overrides"):
            item["overrides"] = [f for f in item["overrides"] if f not in replaced]
            replaced.update(item["overrides"])
            if not item["overrides"]:
                del item["overrides"]
    rejects = [f for f in rejects if f not in replaced]

    aka = clean_aka(create._aka_entries(core.get("aka")), name, name_keys(view))
    own_names = [name, *(str(entry["name"]) for entry in aka)]
    own_names += [item["name"] for item in items if item["name"]]
    own_names += [row["name"] for row in kept]
    stub_names = create._new_names(
        view,
        _listed_names(core.get("names"), calendar),
        [fact.text for fact in facts] + [item["text"] for item in items],
        own_names,
        list(picks),
    )
    summary = _tidy(core.get("summary"))
    log.info(
        "spheres.preview_branch",
        parent_id=parent_id,
        name=name,
        drawers=len(drawers),
        items=len(items),
        drops=len(drops),
        rejects=len(rejects),
        new_names=len(stub_names),
    )
    return SpherePreview(
        kind="sphere",
        prompt=prompt,
        fields={"parent": parent_id},
        name=name,
        facts=facts,
        prose={"description": summary} if summary else {},
        aka=aka,
        new_names=stub_names,
        matching_stub_id=create.matching_stub(view, "sphere", name),
        context=[
            (f'Named in this prompt: "{written}" means {label}', texts)
            for written, label, texts in named
        ],
        picks=picks,
        template=template,
        agent=agent,
        drawers=drawers,
        items=items,
        split=create.current_date(world),
        parent_items=rows,
        drops=drops,
        rejects=rejects,
    )


# --- ending an item ------------------------------------------------------------


def end_item(
    world: World, sphere_id: str, item: spheres.Item, at: WorldDate, by: str | None
) -> None:
    """End one of the sphere's own items at `at` (the owner's "End
    this..."), in one revision:

    - a thing item's `part_of` becomes `None` from `at`, and it gets an
      `about` fact (`general` for a kind without one), "Ended in <date>",
      with " by <by>" when something ended it;
    - a statement's fact ends at `at`, and the sphere gets that `about`
      fact, followed by the statement;
    - when `by` is a sphere, it gets a `timeline` fact at `at` linking the
      item (a statement: the sphere it was part of).

    An inherited item is ended in the sphere it comes from, never here: a
    `ValueError`, as is an item the sphere doesn't hold, an `at` before the
    thing became part of it, or a `by` that's no thing."""

    view = world.view()
    _sphere_state(view, sphere_id)
    if item.inherited or item.source_id != sphere_id:
        raise ValueError("an inherited item is ended in the sphere it comes from")
    by_state = view.thing(by) if by is not None else None
    if by is not None and by_state is None:
        raise ValueError(f"no such thing: {by}")
    if item.thing_id is not None:
        joined = view.field_since(item.thing_id, "part_of")
        if joined is not None and at.instant < joined.instant:
            raise ValueError("an item can't end before it became part of the sphere")
    note = f"Ended in {world.calendar.format(at)}"
    if by is not None:
        note += f" by {ref(by, view.name_of(by) or '')}"

    with world.revision(Source.manual(note=_ENDED_NOTE)) as rev:
        if item.thing_id is not None:
            state = view.thing(item.thing_id)
            link = state.fields.get("part_of") if state is not None else None
            if (
                state is None
                or not isinstance(link, dict)
                or link.get("sphere") != sphere_id
            ):
                raise ValueError(f"not part of the sphere: {item.thing_id}")
            rev.set_field(state.id, "part_of", None, at)
            category = (
                "about" if "about" in get_kind(state.kind).categories else "general"
            )
            rev.add_fact(state.id, category, note, valid_from=at)
            linked = ref(state.id, view.name_of(state.id) or item.name)
        elif item.fact_id is not None:
            text = _fact_text(view, item.fact_id)
            if text is None:
                raise ValueError(f"no such statement: {item.fact_id}")
            rev.end_fact(item.fact_id, at)
            rev.add_fact(sphere_id, "about", f"{note}: {text}", valid_from=at)
            linked = f'{ref(sphere_id, view.name_of(sphere_id) or "")}\'s "{text}"'
        else:
            raise ValueError("an item is a thing or a statement")
        if by_state is not None and spheres.is_sphere(by_state):
            rev.add_fact(by_state.id, "timeline", f"Ended {linked}", valid_from=at)
    log.info(
        "spheres.end_item",
        sphere_id=sphere_id,
        thing_id=item.thing_id,
        fact_id=item.fact_id,
        by=by,
    )
