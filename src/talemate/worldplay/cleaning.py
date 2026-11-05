"""Marking names in AI text under review (languages 4a revised): a new
entry's draft (its languages found from the owner's words), "+ Add facts"
and "+ Add event" drafts, and a group's "+ Add". Flagged names are marked
with why; the text is never changed (owner, 2026-11-01): the owner names
things with Name it…."""

from __future__ import annotations

import re
import uuid

from talemate.languages.cleaning import model as clean_model
from talemate.languages.cleaning.languages import language_rows, named_languages
from talemate.languages.cleaning.lists import effective
from talemate.languages.cleaning.marks import Mark
from talemate.languages.cleaning.mark import mark_texts
from talemate.languages.entry import languages as all_languages
from talemate.languages.lookup import languages_for
from talemate.world.store import World
from talemate.worldplay.create import CreatePreview
from talemate.worldplay.facts import FactDraft
from talemate.worldplay.groups import GroupAddDraft

__all__ = [
    "clean_fact_draft",
    "clean_group_draft",
    "clean_preview",
    "inherited_rows",
    "name_person",
    "owner_kept",
    "rename_in_preview",
]


def inherited_rows(view, preview: CreatePreview) -> list:
    """The languages of where the draft is filed (ticked In rows), or of
    the stub it expands."""

    rows: list = []
    targets = [f.target_id for f in preview.filings if f.ticked and f.target_id]
    if preview.stub_id:
        targets.insert(0, preview.stub_id)
    for target in targets:
        rows += languages_for(view, target)
    return rows


def _texts(preview: CreatePreview) -> list[str]:
    return (
        [preview.name]
        + [f.text for f in preview.facts]
        + [preview.summary or ""]
        + [e.text for e in preview.elsewhere]
    )


def _off(client) -> bool:
    """No model and no fixed replies: nothing can be asked."""

    return client is None and clean_model.fixed_replies is None


def _with_named(view, prompt: str, rows: list) -> list:
    """`rows`, with languages the owner's words name first (as spoken)."""

    named = [
        {"language": lid, "role": "spoken"} for lid in named_languages(view, prompt)
    ]
    return named + list(rows) if named else list(rows)


async def clean_preview(
    world: World,
    preview: CreatePreview,
    client,
    rows: list[dict] | None = None,
    keep: set[str] = frozenset(),
) -> CreatePreview:
    """`preview` with its flagged names marked. `rows` are the draft's
    Languages rows when the owner set them; else they're found from the
    owner's words (marked `from_words`), else the inherited languages are
    used and none is shown. A world with no languages is left alone."""

    view = world.view()
    if not all_languages(view):
        return preview
    from_words = rows is None
    if rows is None:
        ids = named_languages(view, preview.prompt)
        rows = await language_rows(client, view, preview.prompt, ids) if ids else []
    inherited = inherited_rows(view, preview)
    used = rows or inherited
    listed = [(preview.name, preview.kind)] + [
        (n.name, n.kind) for n in preview.new_names
    ]
    marks = await mark_texts(
        client,
        view,
        _texts(preview),
        listed,
        preview.prompt,
        used,
        effective(world),
        keep,
    )
    shown = (
        [{**dict(r), "from_words": True} for r in rows]
        if from_words
        else [dict(r) for r in rows]
    )
    cleaned = preview.model_copy(
        update={
            "marks": marks,
            "languages": shown,
            "inherited_languages": _shown_inherited(view, inherited),
        }
    )
    language_id = _main_language(used)
    if preview.kind == "character" and not language_id:
        # a person: their parents' language, from the model's parent rows
        # (unticked, ruling F7) when nothing else gives one (4b-2)
        language_id = _main_language(_parent_languages(view, preview))
    if preview.kind == "character" and language_id:
        cleaned = name_person(view, cleaned, language_id)
    return cleaned


def _parent_languages(view, preview: CreatePreview) -> list:
    """The languages of the draft's parent rows, ticked or not."""

    from talemate.languages.person_names import PARENT_WORDS, role_matches

    rows: list = []
    for row in preview.filings:
        if row.target_id and role_matches(list(PARENT_WORDS), row.role or ""):
            rows += languages_for(view, row.target_id)
    return rows


def _main_language(rows: list) -> str | None:
    """The language a draft's person is named in: an official row's, else
    the first's."""

    def lid(row) -> str | None:
        if isinstance(row, dict):
            return row.get("language") or row.get("language_id")
        return getattr(row, "language_id", None)

    def role(row) -> str:
        return (
            row.get("role") if isinstance(row, dict) else getattr(row, "role", "")
        ) or ""

    for row in rows:
        if role(row) == "official" and lid(row):
            return lid(row)
    return next((lid(row) for row in rows if lid(row)), None)


def _has_people_rules(language) -> bool:
    return any(
        g.for_person or any(p.kind == "connection" for s in g.shapes for p in s.parts)
        for g in language.generators
    )


def rename_in_preview(preview: CreatePreview, old: str, new: str) -> CreatePreview:
    """`preview` with `old` (whole words) written `new` in its name, facts,
    summary, elsewhere rows and prose; marks on `old` dropped."""

    if not old or old == new:
        return preview
    pattern = re.compile(rf"(?<![\w'’-]){re.escape(old)}(?![\w'’-])")

    def swap(text: str | None) -> str | None:
        return pattern.sub(lambda _m: new, text) if text else text

    return preview.model_copy(
        update={
            "name": new,
            "facts": [
                f.model_copy(update={"text": swap(f.text)}) for f in preview.facts
            ],
            "summary": swap(preview.summary),
            "elsewhere": [
                e.model_copy(update={"text": swap(e.text)}) for e in preview.elsewhere
            ],
            "prose": {k: swap(v) or "" for k, v in preview.prose.items()},
            "marks": [m for m in preview.marks if m.name != old and m.part != old],
        }
    )


def _draft_facts(view, preview: CreatePreview) -> list[tuple[str, list[str]]]:
    """The draft's relationship facts, each with the people it names (by
    their names as the world writes them)."""

    from talemate.worldplay.create import entry_names

    names = entry_names(view)
    out = []
    for fact in preview.facts:
        if fact.category != "relationship":
            continue
        refs = [
            thing_id
            for name, thing_id in names.items()
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", fact.text)
        ]
        if refs:
            out.append((fact.text, refs))
    return out


def name_person(view, preview: CreatePreview, language_id: str) -> CreatePreview:
    """A drafted person's name built from their language's people rules
    (languages 4b-2): the owner's own name is kept; otherwise the name is
    built from who the draft says they are and the parents it's filed
    under, the draft renamed to it and marked, a title and a pet name
    offered as other names, and a parent the name implies but the world
    doesn't have offered as an unticked In row. A language without people
    rules, or a name already built, is left as it is."""

    import random

    from talemate.languages.entry import language_of
    from talemate.languages.person_names import (
        PARENT_WORDS,
        PersonContext,
        build_person_name,
        choose,
        connections_of,
        role_matches,
        roll_pet_name,
        stored_written,
    )
    from talemate.worldplay.create import NewName, PreviewFiling
    from talemate.worldplay.people import stored_parts

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        return preview
    language = language_of(state)
    if not _has_people_rules(language):
        return preview
    stored = preview.fields.get("name_parts")
    if stored is not None and stored_written(view, stored) == preview.name:
        return preview
    if preview.name and re.search(
        rf"(?<!\w){re.escape(preview.name)}(?!\w)", preview.prompt, re.I
    ):
        # the owner's own name: never rebuilt
        return preview
    rng = random.Random()
    # ticked rows, and the model's parent rows (they arrive unticked,
    # ruling F7, but the prompt said whose child this is)
    filings = [
        (f.target_id, f.role)
        for f in preview.filings
        if f.target_id and (f.ticked or role_matches(list(PARENT_WORDS), f.role or ""))
    ]
    ctx = PersonContext(
        built_as=choose(language, preview.person),
        connections=connections_of(view, None, filings, _draft_facts(view, preview)),
    )
    named = build_person_name(
        language, ctx, meaning=preview.person.get("name_meaning", ""), rng=rng
    )
    if not named.name:
        return preview
    out = rename_in_preview(preview, preview.name, named.name)
    parts = stored_parts(
        language_id,
        named.rule_id,
        named.shape,
        named.built_as,
        [p.model_dump() for p in named.parts],
    )
    aka = [dict(a) for a in out.aka if a.get("kind") not in ("title", "pet")]
    title = preview.person.get("title", "")
    if title:
        aka.append(
            {
                "name": title,
                "tag": "proper",
                "everyday": False,
                "kind": "title",
                "shown": "before",
            }
        )
    pet = roll_pet_name(language, {p.label: p.text for p in named.parts}, rng)
    if pet is not None:
        aka.append(
            {
                "name": pet[0],
                "tag": "proper",
                "everyday": False,
                "kind": "pet",
                "rule": pet[1],
            }
        )
    relation = {"woman": "daughter of", "man": "son of"}.get(
        named.built_as.get("sex", ""), "child of"
    )
    offered = [
        PreviewFiling(
            new_name=NewName(name=missing.name, kind="character", ticked=False),
            target_name=missing.name,
            role=relation,
            ticked=False,
        )
        for missing in named.missing
    ]
    mark = Mark(
        id=uuid.uuid4().hex[:12],
        name=named.name,
        part=named.name,
        why=f"built from {language.name}'s rules",
        language_id=language_id,
        entry_kind="character",
    )
    return out.model_copy(
        update={
            "fields": {**out.fields, "name_parts": parts},
            "aka": aka,
            "filings": [*out.filings, *offered],
            "marks": [*out.marks, mark],
        }
    )


def _shown_inherited(view, rows: list) -> list[dict]:
    """Inherited rows as the draft's Languages section shows them, each
    language once."""

    out: list[dict] = []
    for row in rows:
        if any(o["language_id"] == row.language_id for o in out):
            continue
        out.append(
            {
                "language_id": row.language_id,
                "name": row.name,
                "role": row.role,
                "share": row.share,
                "source_name": view.name_of(row.source_id) or "",
            }
        )
    return out


def owner_kept(held: CreatePreview, copy: CreatePreview) -> set[str]:
    """The names the owner kept on `copy` since the server's `held`
    version (a mark they dropped), and every capitalised word of a fact
    they rewrote: marking again leaves them be."""

    marks = {m.id for m in copy.marks}
    kept = {m.name for m in held.marks if m.id not in marks}
    held_texts = {f.text for f in held.facts}
    for fact in copy.facts:
        if fact.text not in held_texts:
            kept.update(re.findall(r"[A-Z][\w'’-]*", fact.text))
    return kept


async def clean_fact_draft(
    world: World, draft: FactDraft, client, rows: list | None = None
) -> FactDraft:
    """A "+ Add facts" or "+ Add event" draft with its flagged names
    marked. `rows` are the languages to use (a page draft's, for its
    nested draft); else the entry's own or inherited ones. Languages the
    owner's words name come first. A world with no languages, or no model
    and no fixed replies, leaves it alone."""

    view = world.view()
    if not all_languages(view) or _off(client):
        return draft
    if rows is None:
        rows = languages_for(view, draft.thing_id) if draft.thing_id else []
    marks = await mark_texts(
        client,
        view,
        [f.text for f in draft.facts],
        [(n.name, n.kind) for n in draft.new_names],
        draft.prompt,
        _with_named(view, draft.prompt, rows),
        effective(world),
    )
    return draft.model_copy(update={"marks": marks})


async def clean_group_draft(
    world: World, draft: GroupAddDraft, client
) -> GroupAddDraft:
    """A group's "+ Add" draft with each row's flagged names marked, in
    the page's languages (or ones the owner's words name). Left alone as
    `clean_fact_draft` leaves a draft alone."""

    view = world.view()
    if not all_languages(view) or _off(client):
        return draft
    marks = await mark_texts(
        client,
        view,
        [t for row in draft.rows for t in (row.name, row.line)],
        [(row.name, row.kind) for row in draft.rows],
        draft.prompt,
        _with_named(view, draft.prompt, languages_for(view, draft.thing_id)),
        effective(world),
    )
    return draft.model_copy(update={"marks": marks})
