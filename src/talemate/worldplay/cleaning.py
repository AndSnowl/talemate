"""Marking names in AI text under review (languages 4a revised): a new
entry's draft (its languages found from the owner's words), "+ Add facts"
and "+ Add event" drafts, and a group's "+ Add". Flagged names are marked
with why; the text is never changed (owner, 2026-11-01): the owner names
things with Name it…."""

from __future__ import annotations

import re

from talemate.languages.cleaning import model as clean_model
from talemate.languages.cleaning.languages import language_rows, named_languages
from talemate.languages.cleaning.lists import effective
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
    "owner_kept",
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
    used = rows or inherited_rows(view, preview)
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
    return preview.model_copy(update={"marks": marks, "languages": shown})


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
