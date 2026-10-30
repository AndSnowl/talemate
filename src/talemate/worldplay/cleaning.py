"""Cleaning a new entry's draft (languages 4a): its languages found from
the owner's words, its name, facts, summary and "for other pages" facts
cleaned (`languages.cleaning.replace.clean_texts`), each replacement a new
stub; and undoing it, for a re-clean when the owner changes the draft's
languages."""

from __future__ import annotations

from talemate.languages.cleaning.languages import language_rows, named_languages
from talemate.languages.cleaning.lists import effective
from talemate.languages.cleaning.replace import _swap, clean_texts
from talemate.languages.entry import languages as all_languages
from talemate.languages.lookup import languages_for
from talemate.world.store import World
from talemate.worldplay.create import CreatePreview
from talemate.worldplay.links import NewName

__all__ = ["clean_preview", "unclean_preview"]


def _inherited(view, preview: CreatePreview) -> list:
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


async def clean_preview(
    world: World, preview: CreatePreview, client, rows: list[dict] | None = None
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
    used = rows or _inherited(view, preview)
    listed = [(preview.name, preview.kind)] + [
        (n.name, n.kind) for n in preview.new_names
    ]
    cleaned = await clean_texts(
        client, view, _texts(preview), listed, preview.prompt, used, effective(world)
    )
    replaced = [m for m in cleaned.marks if m.kind == "replaced"]
    new_names = []
    covered: set[str] = set()
    for n in preview.new_names:
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
        new_names.append(n)
    for mark in replaced:
        if (
            mark.id in covered
            or _swap([preview.name], mark.was, mark.name)[0] != preview.name
        ):
            continue
        new_names.append(
            NewName(
                name=mark.name,
                kind=mark.entry_kind,
                replaced=mark.was,
                from_cleaning=True,
            )
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
