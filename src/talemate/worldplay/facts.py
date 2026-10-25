"""A few more facts for an entry the world has: "+ Add facts..." and
"+ Add event..." (Filing spec, "An entry page").

`draft_facts` asks the model for a small draft of facts about one entry
from the owner's prompt (`world/add-facts.jinja2`, through
`ai.world_ai_call`, read with `create.parse_create_reply`, which parses
with `create.json_objects`), writing nothing. Given a `year` (an event),
every fact is dated to it. `draft_facts_for` does the same for an entry
still in draft (a `CreatePreview`), for the router to add to the draft.
Each fact a fact of the entry already says arrives as a repeat (`create.repeat_flags`: shown with its match, and
unticked at the untick threshold).

The reply also lists the proper names its facts use (ruling H8: the
names line and shape are create-thing's, verbatim), read as a create
reply's are (`create.listed_names`, so a title or office is no name,
ruling F5; `create.name_filings`, an "in" naming the entry filing its
stub there; `create._new_names`, keeping only the names the facts write
with a capital, ruling F26, that the world doesn't have). They're the
draft's `new_names`, ticked (`DraftName`), each with its same-thing
offers. On a draft (`draft_facts_for`) they join the draft's own new
names instead, less the ones it holds already.

`accept_facts` writes the draft's ticked facts onto the entry in one
revision, linked as a hand-written fact is (`links.link_text`: entries
and stubs by name, never the entry itself), with a stub for each ticked
new name (`create._row_stubs`, filed as its row says,
`create._file_new_names`), all in that revision. The rows come back from
the page, so they're checked again against the facts written: a name
they no longer write, one the world has by now, a title (ruling F5) or
one no fact ends up linking makes no stub, and its words stay plain.

The template's wording is new and unprobed (Filing, Task 12 measures
it).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, NamedTuple

import structlog
from pydantic import BaseModel, Field

from talemate.prompts import Prompt
from talemate.world import entries
from talemate.world.dates import WorldDate
from talemate.world.kinds import get_kind
from talemate.world.refs import parse_refs, scrub_emphasis
from talemate.world.store import Source, World
from talemate.world.view import FactState
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.create import (
    TITLE_WORDS,
    CreatePreview,
    MoveHereFact,
    PreviewFact,
    _aka_entries,
    _moved_from_prose,
    _file_new_names,
    _new_names,
    _raw_aka_and_names,
    _row_stubs,
    clean_tag,
    create_categories,
    current_date,
    default_category,
    entry_names,
    holder_named,
    listed_names,
    name_filings,
    offer_same,
    parse_create_reply,
    prose_reads,
    repeat_flags,
    write_repeat_choices,
)
from talemate.worldplay.held import held_text
from talemate.worldplay.links import NewName, link_text, name_key

__all__ = [
    "DraftAddition",
    "DraftName",
    "FactDraft",
    "accept_facts",
    "draft_facts",
    "draft_facts_for",
]

log = structlog.get_logger("talemate.worldplay.facts")

# the most facts one draft holds: a few, for the owner to tick
DRAFT_FACTS = 6

# the facts of the entry the prompt shows, so the reply doesn't repeat
# them (the most recent written first)
SHOWN_FACTS = 20

PROMPT_KIND = "creative_instruction_2048"


class DraftName(NewName):
    """A fact draft's "New names" row: a name its facts use that the world
    hasn't, a stub on accept while `ticked` (ruling H8)."""

    ticked: bool = True


class FactDraft(BaseModel):
    """A small draft of facts for an entry (`thing_id`), from the owner's
    `prompt`; `year`, the year an event's facts are dated to, or `None`.
    `new_names`: the names its facts use that the world hasn't. The owner
    ticks, edits or drops them before `accept_facts`. `move_here`: the
    owner's "Move existing here" rows (`repeat`) on facts that repeat the
    world's, as a page draft's."""

    thing_id: str
    prompt: str
    year: int | None = None
    facts: list[PreviewFact] = Field(default_factory=list)
    new_names: list[DraftName] = Field(default_factory=list)
    move_here: list[MoveHereFact] = Field(default_factory=list)


class DraftAddition(NamedTuple):
    """What `draft_facts_for` adds to a draft: its facts, and the new names
    they use that the draft doesn't hold yet."""

    facts: list[PreviewFact]
    new_names: list[NewName]


def _own_names(name: str, aka: object) -> list[str]:
    return [name, *(str(entry["name"]) for entry in _aka_entries(aka))]


def _listed_new_names(
    view: Any,
    reply: str,
    texts: list[str],
    own_names: list[str],
    *,
    near: Sequence[str],
    exclude: Sequence[str] = (),
    picks: Sequence[str] = (),
    as_new: Sequence[str] = (),
    taken: Sequence[NewName] = (),
) -> list[NewName]:
    """The reply's "names" that become stubs (create's rules: `listed_names`,
    `name_filings` with this entry as `own_names`, `_new_names` against
    `texts`), less a name `taken` holds already (by name or written form),
    each with its same-thing offers (`offer_same`, near `near`)."""

    _aka, raw_names = _raw_aka_and_names(reply)
    own_keys = {name_key(n) for n in own_names if n.strip()}
    listed, _into = name_filings(
        view,
        listed_names(raw_names),
        own_keys=own_keys,
        prefer=near,
        lookup=entry_names(view, near),
    )
    held = {name_key(form) for n in taken for form in (n.name, *n.written)}
    kept = [
        n
        for n in _new_names(view, listed, texts, own_names, picks, as_new)
        if not {name_key(form) for form in (n.name, *n.written)} & held
    ]
    offer_same(view, kept, near_ids=near, exclude=exclude, as_new=as_new)
    return kept


async def _ask(
    world: World,
    *,
    name: str,
    kind: str,
    tag: object,
    hint: object,
    summary: str,
    known: list[str],
    owners: list[str],
    prompt: str,
    client: Any,
    year: int | None,
    reply: str | None,
) -> tuple[list[PreviewFact], str]:
    """The facts the model writes about an entry (`name`, a `kind`, what
    it says already, `known`), at most `DRAFT_FACTS`, each dated `year`
    when given, each flagged as a repeat of what `owners` say; and the
    reply, for its names."""

    view = world.view()
    if not prompt.strip():
        raise ValueError("say what the facts are about")
    calendar = world.calendar
    now_year = current_date(world).to_datetime().year
    categories = create_categories(kind, hint if isinstance(hint, str) else None)
    if reply is None:
        prose_gen.require_client(client)
        with world_ai_call():
            _response, extracted = await Prompt.request(
                "world.add-facts",
                client,
                PROMPT_KIND,
                vars={
                    "name": name,
                    "kind": kind,
                    "tag": tag if isinstance(tag, str) else None,
                    "summary": summary,
                    "facts": known[:SHOWN_FACTS],
                    "prompt": prompt.strip(),
                    "categories": categories,
                    "year": calendar.format(WorldDate.of(year)) if year else None,
                    "now_year": now_year,
                },
            )
        reply = extracted["response"]
    _name, _age, facts = parse_create_reply(
        reply,
        kind,
        calendar,
        now_year,
        holder=lambda held: holder_named(view, held),
        categories=categories,
    )
    if not facts:
        raise ValueError("the model's reply had no facts in it")
    facts = facts[:DRAFT_FACTS]
    if year is not None:
        dated = WorldDate.of(year)
        for fact in facts:
            fact.since = dated
    flags = repeat_flags(view, [f.text for f in facts], owners, world.curation())
    for fact, (repeat_of, ticked) in zip(facts, flags):
        fact.repeat_of, fact.ticked = repeat_of, ticked
    return facts, reply


async def draft_facts(
    world: World,
    thing_id: str,
    prompt: str,
    client: Any,
    *,
    year: int | None = None,
    reply: str | None = None,
) -> FactDraft:
    """A `FactDraft` of at most `DRAFT_FACTS` facts about the entry, from
    the owner's `prompt`, writing nothing. With `year`, each is dated to
    it. `reply` stands in for the model's (the browser tests' fixed
    reply), read through the same parsing. A missing entry is a
    `KeyError`; a reply with no facts a `ValueError`."""

    view = world.view()
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such entry: {thing_id}")
    summary = entries.summary_fact(state)
    known = sorted(state.facts, key=lambda fact: fact.created, reverse=True)
    name = view.name_of(thing_id) or ""
    facts, answer = await _ask(
        world,
        name=name,
        kind=state.kind,
        tag=state.fields.get("tag"),
        hint=state.fields.get("hint"),
        # a held one worded as held, never as world truth
        summary=held_text(view, summary, state) if summary else "",
        known=[held_text(view, f, state) for f in known],
        owners=[thing_id],
        prompt=prompt,
        client=client,
        year=year,
        reply=reply,
    )
    names = _listed_new_names(
        view,
        answer,
        [f.text for f in facts],
        _own_names(name, state.fields.get("aka")),
        near=[thing_id],
        exclude=[thing_id],
    )
    log.info(
        "facts.draft",
        thing_id=thing_id,
        year=year,
        facts=len(facts),
        repeats=sum(1 for f in facts if f.repeat_of is not None),
        new_names=len(names),
    )
    return FactDraft(
        thing_id=thing_id,
        prompt=prompt,
        year=year,
        facts=facts,
        new_names=[DraftName(**n.model_dump()) for n in names],
    )


async def draft_facts_for(
    world: World,
    preview: CreatePreview,
    prompt: str,
    client: Any,
    *,
    year: int | None = None,
    reply: str | None = None,
) -> DraftAddition:
    """`draft_facts` for an entry still in draft (a `CreatePreview`): the
    facts to add to it, writing nothing, and the new names they use that
    the draft doesn't hold yet (its picks and the names it treats as new
    count as on its create). It's told the draft's own facts (and a
    stub's), and a fact that repeats what the stub says, or one of the
    draft's own, is left out or flagged."""

    view = world.view()
    stub = view.thing(preview.stub_id) if preview.stub_id else None
    known = [fact.text for fact in preview.facts]
    if stub is not None:
        known += [held_text(view, fact, stub) for fact in stub.facts]
    facts, answer = await _ask(
        world,
        name=preview.name,
        kind=preview.kind,
        tag=preview.tag,
        hint=preview.hint,
        summary="",
        known=known,
        owners=[stub.id] if stub is not None else [],
        prompt=prompt,
        client=client,
        year=year,
        reply=reply,
    )
    own = {" ".join(text.split()).casefold() for text in known}
    kept = [f for f in facts if " ".join(f.text.split()).casefold() not in own]
    own_names = _own_names(preview.name, preview.aka)
    if stub is not None:
        own_names.append(view.name_of(stub.id) or "")
    names = _listed_new_names(
        view,
        answer,
        [f.text for f in kept],
        own_names,
        near=[*([stub.id] if stub is not None else []), *preview.picks.values()],
        exclude=[stub.id] if stub is not None else [],
        picks=list(preview.picks),
        as_new=preview.treated_as_new,
        taken=preview.new_names,
    )
    log.info(
        "facts.draft_for",
        name=preview.name,
        year=year,
        facts=len(kept),
        new_names=len(names),
    )
    return DraftAddition(kept, names)


class _Unlinked(Exception):
    """New names whose stubs no written fact linked: the write is rolled
    back and made again without them."""

    def __init__(self, keys: set[str]) -> None:
        super().__init__(", ".join(sorted(keys)))
        self.keys = keys


class _NothingWritten(Exception):
    """A fact draft whose only rows were repeat moves, none of which
    applied: the empty revision is rolled back."""


def _checked_names(
    view: Any, draft: FactDraft, texts: list[str], own_names: list[str]
) -> list[NewName]:
    """The draft's ticked new names that still make stubs, checked again
    rather than trusted from the page: never a title (ruling F5), its tag
    tidied (`create.clean_tag`), and only one the written `texts` use and
    the world doesn't have (`create._new_names`). The owner's "same as"
    answer is kept."""

    rows: list[NewName] = []
    same: dict[str, str | None] = {}
    for row in draft.new_names:
        kind = " ".join(row.kind.split()).lower()
        tag = (row.tag or "").strip().lower()
        if not row.ticked or kind in TITLE_WORDS or tag in TITLE_WORDS:
            continue
        rows.append(
            NewName(
                name=scrub_emphasis(" ".join(row.name.split())),
                kind=kind,
                aka=row.aka,
                tag=clean_tag(row.tag, kind),
                filing=row.filing,
            )
        )
        same.setdefault(name_key(row.name), row.same_target_id)
    kept = _new_names(view, rows, texts, own_names)
    for row in kept:
        row.same_target_id = same.get(name_key(row.name))
    return kept


def accept_facts(
    world: World,
    draft: FactDraft,
    notes: list[str] | None = None,
    prose: list[str] | None = None,
) -> list[str]:
    """Write the draft's ticked facts onto its entry in one revision and
    return their ids: each in its category (`create.default_category`'s
    when the entry's kind has none such), with its date and holder (a
    holder gone since holds nothing), its text linked as a hand-written
    fact's. A blank one is skipped. A missing entry is a `KeyError`.

    In the same revision, each ticked new name the facts still use
    (`_checked_names`) becomes a stub (`create._row_stubs`: or the entry
    the owner marked it the same as), filed as its row says, and the
    facts link it (ruling H8). A stub no fact ends up linking (a name
    written only in lowercase, ruling F26) isn't made: the revision is
    made again without it. `notes` gets what was left out.

    Its repeat choices are settled in the same revision
    (`create.write_repeat_choices`): a ticked fact marked
    `replaces_repeat` ("Keep new") is written and the fact it repeats
    removed; a ticked `repeat` row of `move_here` ("Move existing here")
    moves the world's fact onto the entry. `prose` gets the entries whose
    prose read a fact moved or removed, and the entry itself when its
    prose reads a fact moved onto it."""

    view = world.view()
    state = view.thing(draft.thing_id)
    if state is None:
        raise KeyError(f"no such entry: {draft.thing_id}")
    categories = get_kind(state.kind).categories
    kept = [fact for fact in draft.facts if fact.ticked and fact.text.strip()]
    # the rows whose repeat choices are settled: all but a blank ticked one
    # (never written, so it replaces nothing)
    rows = [fact for fact in draft.facts if not fact.ticked or fact.text.strip()]
    moves = [row for row in draft.move_here if row.ticked and row.repeat]
    if not kept and not moves:
        return []
    texts = [scrub_emphasis(" ".join(fact.text.split())) for fact in kept]
    own_names = _own_names(view.name_of(draft.thing_id) or "", state.fields.get("aka"))
    names = _checked_names(view, draft, texts, own_names)
    out = notes if notes is not None else []
    while True:
        try:
            written, moved, removed = _write_facts(
                world, draft, state.kind, kept, texts, names, categories, out, rows
            )
            break
        except _Unlinked as unlinked:
            names = [n for n in names if name_key(n.name) not in unlinked.keys]
        except _NothingWritten:
            return []
    if prose is not None:
        changed = _moved_from_prose(view, [*moved, *removed], draft.thing_id)
        # the entry itself, when its prose reads a fact moved onto it
        if any(prose_reads(state.kind, fact.category) for _o, fact in moved):
            changed.append(draft.thing_id)
        prose.extend(t for t in changed if t not in prose)
    log.info(
        "facts.accept",
        thing_id=draft.thing_id,
        facts=len(written),
        new_names=len(names),
        moved_here=len(moved),
        replaced=len(removed),
    )
    return written


def _write_facts(
    world: World,
    draft: FactDraft,
    kind: str,
    kept: list[PreviewFact],
    texts: list[str],
    names: list[NewName],
    categories: Sequence[str],
    notes: list[str],
    rows: Sequence[PreviewFact],
) -> tuple[list[str], list[tuple[str, FactState]], list[tuple[str, FactState]]]:
    """`accept_facts`' one revision; raises `_Unlinked` (rolling it back)
    when a stub made for `names` is linked by no fact, and
    `_NothingWritten` when it would write nothing. Returns the written
    fact ids and `write_repeat_choices`' `(moved, removed)`."""

    view = world.view()
    written: list[str] = []
    linked: set[str] = set()
    with world.revision(Source.manual(note="added facts from prompt")) as rev:
        made = _row_stubs(rev, world, view, names, (), notes=notes) if names else {}
        # the revision's own view: the stubs just made are in it
        linking = world.view()
        for fact, text in zip(kept, texts):
            category = (
                fact.category
                if fact.category in categories
                else default_category(kind, fact.since is not None)
            )
            if category not in categories:
                category = categories[0]
            holder = fact.held_by
            held = holder is not None and view.thing(holder) is not None
            linked_text = link_text(linking, text, new_names=made, owner=draft.thing_id)
            linked.update(parse_refs(linked_text))
            written.append(
                rev.add_fact(
                    draft.thing_id,
                    category,
                    linked_text,
                    valid_from=fact.since,
                    origin=entries.with_held_by(None, holder) if held else None,
                )
            )
        orphans = {
            name_key(n.name)
            for n in names
            if (stub := made.get(" ".join(n.name.split()))) is not None
            and view.thing(stub) is None
            and stub not in linked
        }
        if orphans:
            raise _Unlinked(orphans)
        _file_new_names(rev, world, view, names, made, draft.thing_id, notes)
        # after the retry point above, so a rolled-back try adds no notes
        moved, removed = write_repeat_choices(
            rev, world, view, rows, draft.move_here, draft.thing_id, notes
        )
        if not (written or moved or removed):
            raise _NothingWritten()
    return written, moved, removed
