"""Marking names in AI text under review (languages 4a revised): a new
entry's draft (its languages found from the owner's words), "+ Add facts"
and "+ Add event" drafts, and a group's "+ Add". Flagged names are marked
with why; the text is never changed (owner, 2026-11-01): the owner names
things with Name it…."""

from __future__ import annotations

import re
import uuid

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
    "clean_draft",
    "clean_preview",
    "inherited_rows",
    "name_person",
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


def _with_named(view, prompt: str, rows: list) -> list:
    """`rows`, with languages the owner's words name first (as spoken)."""

    named = [
        {"language": lid, "role": "spoken"} for lid in named_languages(view, prompt)
    ]
    return named + list(rows) if named else list(rows)


async def clean_draft(
    world: World,
    client,
    *,
    texts: list[str],
    listed: list[tuple[str, str]],
    prompt: str,
    rows: list,
    keep: set[str] = frozenset(),
    person: CreatePreview | None = None,
    person_language: str | None = None,
) -> tuple[list[Mark], CreatePreview | None]:
    """The one cleaning every draft goes through (languages 4c): its
    flagged names marked (the lists always, the model's check when there's
    a model), and a drafted `person` marked for Name it in
    `person_language`. The text is never changed. A world with no
    languages: nothing."""

    view = world.view()
    if not all_languages(view):
        return [], person
    marks = await mark_texts(
        client, view, texts, listed, prompt, rows, effective(world), keep
    )
    if person is not None and person_language:
        person = name_person(
            view, person.model_copy(update={"marks": marks}), person_language
        )
        marks = list(person.marks)
    return marks, person


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
    language_id = _main_language(used)
    if preview.kind == "character" and not language_id:
        # a person: their parents' language, from the model's parent rows
        # (unticked, ruling F7) when nothing else gives one (4b-2)
        language_id = _main_language(_parent_languages(view, preview))
    marks, person = await clean_draft(
        world,
        client,
        texts=_texts(preview),
        listed=listed,
        prompt=preview.prompt,
        rows=used,
        keep=keep,
        person=preview if preview.kind == "character" else None,
        person_language=language_id,
    )
    shown = (
        [{**dict(r), "from_words": True} for r in rows]
        if from_words
        else [dict(r) for r in rows]
    )
    return (person or preview).model_copy(
        update={
            "marks": marks,
            "languages": shown,
            "inherited_languages": _shown_inherited(view, inherited),
        }
    )


def _parent_languages(view, preview: CreatePreview) -> list:
    """The languages of the draft's parent rows, ticked or not; with none,
    of any of its rows (the model's place for them, acceptance 4b-2)."""

    from talemate.languages.person_names import PARENT_WORDS, role_matches

    rows: list = []
    for row in preview.filings:
        if row.target_id and role_matches(list(PARENT_WORDS), row.role or ""):
            rows += languages_for(view, row.target_id)
    if not rows:
        for row in preview.filings:
            if row.target_id:
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


def _owners_name(preview: CreatePreview) -> bool:
    """The draft's name is the owner's: the whole of it, or its first word
    (a given name the model added to: "Ysolde" → "Ysolde of Drassone",
    final review I1), is written in the prompt with a capital."""

    words = preview.name.split()
    if not words:
        return False
    for wanted in (preview.name, words[0]):
        if re.search(rf"(?<!\w){re.escape(wanted)}(?!\w)", preview.prompt):
            return True
    return False


def name_person(view, preview: CreatePreview, language_id: str) -> CreatePreview:
    """A drafted person's name, marked for Name it (languages 4b-2; owner,
    2026-11-06: drafts only mark): the owner's own name, a stub's or a set
    name is left alone; otherwise the draft keeps who the person is built
    as (for Name it, which builds the name from the rules with what's
    inherited pinned) and the model's title, and its name is marked. A
    language without people rules leaves it as it is."""

    from talemate.languages.entry import language_of
    from talemate.languages.person_names import choose, stored_written

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        return preview
    language = language_of(state)
    if not _has_people_rules(language):
        return preview
    # a stub's name, or one the owner set: never rebuilt (final review C1)
    if preview.stub_id or preview.fields.get("name"):
        return preview
    stored = preview.fields.get("name_parts")
    if stored is not None:
        # marked already (no parts yet), or built and still so: as it is
        if not stored.get("parts") or stored_written(view, stored) == preview.name:
            return preview
        # built once, then renamed by the owner: their name stands, the
        # parts go (final review C2)
        return preview.model_copy(
            update={
                "fields": {k: v for k, v in preview.fields.items() if k != "name_parts"}
            }
        )
    if _owners_name(preview):
        # the owner's own name: never rebuilt
        return preview
    # drafts only mark (owner, 2026-11-06): the name the rules would build
    # waits in Name it, which reads who the person is built as from here
    stored = {
        "language": language_id,
        "rule": "",
        "shape": 0,
        "built_as": choose(language, preview.person),
        "parts": [],
    }
    aka = [dict(a) for a in preview.aka if a.get("kind") != "title"]
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
    marks = [m for m in preview.marks if m.name != preview.name]
    marks.append(
        Mark(
            id=uuid.uuid4().hex[:12],
            name=preview.name,
            part=preview.name,
            why=f"Name it can build it from {language.name}'s rules for people",
            language_id=language_id,
            entry_kind="character",
        )
    )
    return preview.model_copy(
        update={
            "fields": {**preview.fields, "name_parts": stored},
            "aka": aka,
            "marks": marks,
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
    owner's words name come first. Through `clean_draft`, as every draft."""

    view = world.view()
    if rows is None:
        rows = languages_for(view, draft.thing_id) if draft.thing_id else []
    marks, _ = await clean_draft(
        world,
        client,
        texts=[f.text for f in draft.facts],
        listed=[(n.name, n.kind) for n in draft.new_names],
        prompt=draft.prompt,
        rows=_with_named(view, draft.prompt, rows),
    )
    return draft.model_copy(update={"marks": marks})


async def clean_group_draft(
    world: World, draft: GroupAddDraft, client
) -> GroupAddDraft:
    """A group's "+ Add" draft with each row's flagged names marked, in
    the page's languages (or ones the owner's words name). Through
    `clean_draft`, as every draft."""

    view = world.view()
    marks, _ = await clean_draft(
        world,
        client,
        texts=[t for row in draft.rows for t in (row.name, row.line)],
        listed=[(row.name, row.kind) for row in draft.rows],
        prompt=draft.prompt,
        rows=_with_named(view, draft.prompt, languages_for(view, draft.thing_id)),
    )
    return draft.model_copy(update={"marks": marks})
