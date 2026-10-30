"""Cleaning a new entry's draft (languages 4a): its languages found from
the owner's words, its name, facts, summary and "for other pages" facts
cleaned (`languages.cleaning.replace.clean_texts`), each replacement a new
stub; and undoing it, for a re-clean when the owner changes the draft's
languages."""

from __future__ import annotations

import re

from talemate.languages.cleaning import model as clean_model
from talemate.languages.cleaning.languages import language_rows, named_languages
from talemate.languages.cleaning.lists import effective
from talemate.languages.cleaning.replace import _swap, clean_texts
from talemate.languages.entry import languages as all_languages
from talemate.languages.lookup import languages_for
from talemate.world.store import World
from talemate.worldplay.create import CreatePreview
from talemate.worldplay.facts import DraftName, FactDraft
from talemate.worldplay.groups import GroupAddDraft
from talemate.worldplay.links import NewName

__all__ = [
    "clean_fact_draft",
    "clean_group_draft",
    "clean_preview",
    "inherited_rows",
    "owner_kept",
    "unclean_preview",
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


def _with_texts(preview: CreatePreview, texts: list[str]) -> dict:
    n = len(preview.facts)
    facts = [
        f.model_copy(update={"text": t})
        for f, t in zip(preview.facts, texts[1 : 1 + n])
    ]
    summary = texts[1 + n] if preview.summary is not None else None
    elsewhere = [
        e.model_copy(update={"text": t})
        for e, t in zip(preview.elsewhere, texts[2 + n :])
    ]
    return {
        "name": texts[0],
        "facts": facts,
        "summary": summary,
        "elsewhere": elsewhere,
    }


def _renamed(new_names: list, marks: list, own_name: str, make) -> list:
    """`new_names` with each replaced mark's old name swapped for its new
    one (a row so renamed remembers the name it replaced), plus a row
    `make(mark)` for each replacement no row and not the entry's own name
    held."""

    replaced = [m for m in marks if m.kind == "replaced"]
    out = []
    covered: set[str] = set()
    for n in new_names:
        name = n.name
        for mark in replaced:
            swapped = _swap([name], mark.was, mark.name)[0]
            if swapped != name:
                covered.add(mark.id)
                name = swapped
        if name != n.name:
            n = n.model_copy(
                update={
                    "name": name,
                    "replaced": n.name,
                    "written": [w for w in n.written if w != n.name],
                }
            )
        out.append(n)
    for mark in replaced:
        if mark.id in covered or _swap([own_name], mark.was, mark.name)[0] != own_name:
            continue
        out.append(make(mark))
    return out


async def clean_preview(
    world: World,
    preview: CreatePreview,
    client,
    rows: list[dict] | None = None,
    keep: set[str] = frozenset(),
) -> CreatePreview:
    """`preview` cleaned. `rows` are the draft's Languages rows when the
    owner set them; else they're found from the owner's words (marked
    `from_words`), else the inherited languages are used and none is
    shown. A world with no languages is left alone."""

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
    cleaned = await clean_texts(
        client,
        view,
        _texts(preview),
        listed,
        preview.prompt,
        used,
        effective(world),
        keep,
    )
    new_names = _renamed(
        preview.new_names,
        cleaned.marks,
        preview.name,
        lambda mark: NewName(
            name=mark.name, kind=mark.entry_kind, replaced=mark.was, from_cleaning=True
        ),
    )
    shown = (
        [{**dict(r), "from_words": True} for r in rows]
        if from_words
        else [dict(r) for r in rows]
    )
    return preview.model_copy(
        update={
            **_with_texts(preview, cleaned.texts),
            "new_names": new_names,
            "marks": cleaned.marks,
            "languages": shown,
        }
    )


def owner_kept(held: CreatePreview, copy: CreatePreview) -> set[str]:
    """The names the owner chose or wrote on `copy` since the server's
    `held` version: a replaced name put back ("Keep it here"), a suspect
    one kept, and every capitalised word of a fact they rewrote. A
    re-clean leaves them be (final review I4)."""

    marks = {m.id for m in copy.marks}
    kept = {
        m.was if m.kind == "replaced" else m.name
        for m in held.marks
        if m.id not in marks
    }
    held_texts = {f.text for f in held.facts}
    for fact in copy.facts:
        if fact.text not in held_texts:
            kept.update(re.findall(r"[A-Z][\w'’-]*", fact.text))
    return kept


def unclean_preview(preview: CreatePreview) -> CreatePreview:
    """`preview` with every replaced name put back, its marks and the
    stubs cleaning made dropped: ready to be cleaned again."""

    texts = _texts(preview)
    for mark in preview.marks:
        if mark.kind == "replaced":
            texts = _swap(texts, mark.name, mark.was)
    new_names = [
        n.model_copy(update={"name": n.replaced, "replaced": ""}) if n.replaced else n
        for n in preview.new_names
        if not n.from_cleaning
    ]
    return preview.model_copy(
        update={**_with_texts(preview, texts), "new_names": new_names, "marks": []}
    )


async def clean_fact_draft(
    world: World, draft: FactDraft, client, rows: list | None = None
) -> FactDraft:
    """A "+ Add facts" or "+ Add event" draft cleaned. `rows` are the
    languages to use (a page draft's, for its nested draft); else the
    entry's own or inherited ones. Languages the owner's words name come
    first. A world with no languages, or no model and no fixed replies,
    leaves it alone."""

    view = world.view()
    if not all_languages(view) or (
        client is None and clean_model.fixed_replies is None
    ):
        return draft
    if rows is None:
        rows = languages_for(view, draft.thing_id) if draft.thing_id else []
    named = [
        {"language": lid, "role": "spoken"}
        for lid in named_languages(view, draft.prompt)
    ]
    used = named + list(rows) if named else list(rows)
    name = (view.name_of(draft.thing_id) or "") if draft.thing_id else ""
    cleaned = await clean_texts(
        client,
        view,
        [f.text for f in draft.facts],
        [(n.name, n.kind) for n in draft.new_names],
        draft.prompt,
        used,
        effective(world),
    )
    facts = [
        f.model_copy(update={"text": t}) for f, t in zip(draft.facts, cleaned.texts)
    ]
    new_names = _renamed(
        draft.new_names,
        cleaned.marks,
        name,
        lambda mark: DraftName(
            name=mark.name, kind=mark.entry_kind, replaced=mark.was, from_cleaning=True
        ),
    )
    return draft.model_copy(
        update={"facts": facts, "new_names": new_names, "marks": cleaned.marks}
    )


async def clean_group_draft(
    world: World, draft: GroupAddDraft, client
) -> GroupAddDraft:
    """A group's "+ Add" draft cleaned: each row's name and line, in the
    page's languages (or ones the owner's words name). Left alone as
    `clean_fact_draft` leaves a draft alone."""

    view = world.view()
    if not all_languages(view) or (
        client is None and clean_model.fixed_replies is None
    ):
        return draft
    rows = languages_for(view, draft.thing_id)
    named = [
        {"language": lid, "role": "spoken"}
        for lid in named_languages(view, draft.prompt)
    ]
    used = named + list(rows) if named else list(rows)
    texts = [t for row in draft.rows for t in (row.name, row.line)]
    cleaned = await clean_texts(
        client,
        view,
        texts,
        [(row.name, row.kind) for row in draft.rows],
        draft.prompt,
        used,
        effective(world),
    )
    rows_out = [
        row.model_copy(
            update={"name": cleaned.texts[2 * i], "line": cleaned.texts[2 * i + 1]}
        )
        for i, row in enumerate(draft.rows)
    ]
    return draft.model_copy(update={"rows": rows_out, "marks": cleaned.marks})
