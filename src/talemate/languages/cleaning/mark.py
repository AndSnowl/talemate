"""Marking bad names (languages 4a revised): every name the lists, the
model's flag or the fit check doubts is marked with why, in the language
in reach. The text is never changed (owner, 2026-11-01): the owner names
things with Name it…."""

from __future__ import annotations

import re
import uuid

from talemate.languages.cleaning.find import (
    PERSON_KINDS,
    Spot,
    judge,
    protected_names,
    spots,
)
from talemate.languages.cleaning.languages import named_languages
from talemate.languages.cleaning.lists import NameLists
from talemate.languages.cleaning.marks import Mark
from talemate.languages.entry import language_of
from talemate.languages.entry import languages as all_languages
from talemate.languages.models import Language
from talemate.world.view import WorldView

__all__ = ["Mark", "mark_texts"]


def _row(row) -> tuple[str, str, float | None]:
    if isinstance(row, dict):
        return str(row.get("language")), str(row.get("role", "")), row.get("share")
    return row.language_id, row.role, row.share


def _main(rows: list) -> str | None:
    """The main language: official, else the largest spoken share, else
    the first (as `lookup.default_language`)."""

    parts = [_row(r) for r in rows]
    if not parts:
        return None
    for lid, role, _share in parts:
        if role == "official":
            return lid
    spoken = [p for p in parts if p[1] == "spoken"]
    if spoken:
        return max(spoken, key=lambda p: p[2] or 0)[0]
    return parts[0][0]


def _sentence(text: str, name: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if name in sentence:
            return sentence
    return text


def _language_for(view, spot: Spot, texts, langs: dict, main_id) -> str | None:
    """A language its sentence names ("the Sorauan town of …"), else the
    main one."""

    for i in spot.texts:
        for lid in named_languages(view, _sentence(texts[i], spot.name)):
            if lid in langs:
                return lid
    return main_id


def _whole(spot: Spot) -> str:
    """A stock title as written, without a leading "the": a title is
    rewritten whole, frame words and all."""

    return re.sub(r"^the\s+", "", spot.full, flags=re.I)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


async def mark_texts(
    client,
    view: WorldView,
    texts: list[str],
    listed: list[tuple[str, str]],
    prompt: str,
    rows: list,
    lists: NameLists,
    keep: set[str] = frozenset(),
) -> list[Mark]:
    """The marks on `texts`: every bad or doubtful name, with why. `listed`
    is the draft's own name and new names with their kinds; `rows` its
    Languages rows (dicts, or the lookup's rows); `keep` names the owner
    kept on this draft. A world with no languages is left alone."""

    if not all_languages(view):
        return []
    langs: dict[str, Language] = {}
    for row in rows:
        lid = _row(row)[0]
        state = view.thing(lid)
        if state is not None and state.kind == "language":
            langs[lid] = language_of(state)
    main_id = _main([r for r in rows if _row(r)[0] in langs])
    main = langs.get(main_id)
    protected = protected_names(view, prompt, main, lists.keep) | {
        k.lower() for k in keep
    }
    found = spots(view, texts, listed, protected, lists)
    if not found:
        return []
    verdicts = await judge(client, found, lists, main, texts)
    marks = []
    for v in verdicts:
        lid = _language_for(view, v.spot, texts, langs, main_id)
        whole = v.spot.name if v.spot.kind in PERSON_KINDS else _whole(v.spot)
        marks.append(
            Mark(
                id=_new_id(),
                name=whole,
                part=v.spot.name,
                why=v.why,
                language_id=lid if lid in langs else None,
                entry_kind=v.spot.kind,
            )
        )
    return marks
