"""Replacing bad names (languages 4a): names rolled from the language, the
model's pick among them (with a meaning), stock titles rewritten around a
slot, then plain substitution (probe 4, finding 3). Every change and every
doubt comes back as a mark the owner can undo or act on."""

from __future__ import annotations

import re
import uuid
import structlog
from pydantic import BaseModel

from talemate.languages.cleaning.model import ask
from talemate.languages.cleaning.find import (
    PERSON_KINDS,
    Spot,
    Verdict,
    judge,
    protected_names,
    spots,
)
from talemate.languages.cleaning.languages import named_languages
from talemate.languages.cleaning.lists import NameLists
from talemate.languages.cleaning.marks import Mark
from talemate.languages.entry import language_of
from talemate.languages.entry import languages as all_languages
from talemate.languages.models import DictionaryEntry, Language
from talemate.languages.naming import roll_names
from talemate.world.view import WorldView
from talemate.worldplay.create import json_objects

__all__ = ["Cleaned", "Mark", "apply_mark", "clean_texts", "save_mark_words"]

log = structlog.get_logger("talemate.languages.cleaning")

CANDIDATES = 6
_SLOT = re.compile(r"\{name\}", re.I)


class Cleaned(BaseModel):
    texts: list[str]
    marks: list[Mark]


def _swap(texts: list[str], old: str, new: str) -> list[str]:
    pattern = re.compile(r"(?<!\w)" + re.escape(old) + r"(?!\w)")
    return [pattern.sub(lambda _m: new, text) for text in texts]


def apply_mark(texts: list[str], mark: Mark, new: str) -> list[str]:
    """`texts` with the mark's name, as a whole word, swapped for `new`
    (a possessive stays: "Sovyetsk's" → "Lezhograd's")."""

    return _swap(texts, mark.name, new)


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


def _candidates(language: Language, spot: Spot, exclude: set[str]) -> list[str]:
    """Up to CANDIDATES rolled names for the spot; a person's part is one
    word (a given name from a rolled name's first word, a family name from
    its last). ValueError when the language has no name rule for it."""

    kind = spot.kind if spot.kind != "title" else "place"
    rolled = roll_names(
        language, kind, count=CANDIDATES * 3, exclude=frozenset(exclude)
    )
    if spot.kind in PERSON_KINDS:
        words = []
        for name in rolled:
            parts = name.split()
            pick = parts[-1] if spot.part == "family" and len(parts) > 1 else parts[0]
            words.append(pick)
        rolled = words
    found: list[str] = []
    for name in rolled:
        if name.lower() not in exclude and name not in found:
            found.append(name)
    return found[:CANDIDATES]


def _whole(spot: Spot) -> str:
    """A stock title as written, without a leading "the": a title is
    rewritten whole, frame words and all."""

    return re.sub(r"^the\s+", "", spot.full, flags=re.I)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


async def _picks(
    client, language: Language | None, items: list[dict]
) -> dict[int, dict]:
    try:
        reply = await ask(
            client,
            "name-picks",
            {
                "language": language.name if language else "",
                "sound": language.sound if language else "",
                "words": [e.model_dump() for e in language.dictionary[:40]]
                if language
                else [],
                "items": items,
            },
        )
        objects = json_objects(reply)
        rows = objects[0].get("picks") if objects else None
        if not isinstance(rows, list):
            raise ValueError("no picks in the reply")
    except Exception as exc:
        log.warning("languages.clean_picks_failed", error=str(exc))
        return {}
    return {r.get("n"): r for r in rows if isinstance(r, dict)}


async def _titles(client, items: list[dict]) -> dict[int, str]:
    try:
        reply = await ask(client, "title-rewrites", {"items": items})
        objects = json_objects(reply)
        rows = objects[0].get("titles") if objects else None
        if not isinstance(rows, list):
            raise ValueError("no titles in the reply")
    except Exception as exc:
        log.warning("languages.clean_titles_failed", error=str(exc))
        return {}
    return {r.get("n"): str(r.get("title") or "") for r in rows if isinstance(r, dict)}


async def clean_texts(
    client,
    view: WorldView,
    texts: list[str],
    listed: list[tuple[str, str]],
    prompt: str,
    rows: list,
    lists: NameLists,
    keep: set[str] = frozenset(),
) -> Cleaned:
    """Clean `texts`: find the bad names, replace those a language can,
    mark the rest suspect. `listed` is the draft's own name and new names
    with their kinds; `rows` its Languages rows (dicts, or the lookup's
    rows). A world with no languages is left alone."""

    texts = list(texts)
    if not all_languages(view):
        return Cleaned(texts=texts, marks=[])
    langs: dict[str, Language] = {}
    for row in rows:
        lid = _row(row)[0]
        state = view.thing(lid)
        if state is not None and state.kind == "language":
            langs[lid] = language_of(state)
    main_id = _main([r for r in rows if _row(r)[0] in langs])
    main = langs.get(main_id)
    # `keep`: names the owner kept or wrote on this draft (final review I4)
    protected = protected_names(view, prompt, main, lists.keep) | {
        k.lower() for k in keep
    }
    found = spots(view, texts, listed, protected, lists)
    # every name the draft already uses: never rolled for another (final
    # review I1: two places would merge)
    in_use = set(protected)
    in_use.update(full.lower() for full, _kind in listed)
    for text in texts:
        in_use.update(w.lower() for w in re.findall(r"[A-Z][\w'’-]*", text))
    if not found:
        return Cleaned(texts=texts, marks=[])
    verdicts = await judge(client, found, lists, main, texts)

    marks: list[Mark] = []
    picked: set[str] = set()
    to_pick: list[tuple[Verdict, str, list[str]]] = []
    to_rewrite: list[tuple[Verdict, str, Language]] = []

    def suspect(v: Verdict, why: str, lid=None, spares=()) -> None:
        marks.append(
            Mark(
                id=_new_id(),
                kind="suspect",
                name=v.spot.name,
                was=v.spot.name,
                why=why,
                language_id=lid,
                spares=list(spares),
                entry_kind=v.spot.kind,
            )  # fmt: skip
        )

    for v in verdicts:
        lid = _language_for(view, v.spot, texts, langs, main_id)
        language = langs.get(lid)
        if language is None:
            suspect(v, v.why)
            continue
        try:
            candidates = _candidates(language, v.spot, in_use)
        except ValueError:
            suspect(v, f"{language.name} has no name rules for this", lid)
            continue
        if v.action == "suspect":
            suspect(v, v.why, lid, candidates)
        elif not candidates:
            suspect(v, f"no {language.name} names left for this", lid)
        elif v.action == "replace":
            to_pick.append((v, lid, candidates))
        else:
            to_rewrite.append((v, lid, language))

    if to_pick:
        items = [
            {
                "n": n + 1,
                "sentence": _sentence(texts[v.spot.texts[0]], v.spot.name)
                if v.spot.texts
                else v.spot.full,
                "was": v.spot.name,
                "person": v.spot.person,
                "candidates": candidates,
            }
            for n, (v, _lid, candidates) in enumerate(to_pick)
        ]
        replies = await _picks(client, langs.get(main_id), items)
        for n, (v, lid, candidates) in enumerate(to_pick):
            reply = replies.get(n + 1) or {}
            free = [c for c in candidates if c.lower() not in picked]
            if not free:
                suspect(v, f"no {langs[lid].name} names left for this", lid)
                continue
            pick = str(reply.get("pick") or "")
            name = pick if pick in free else free[0]
            meaning = (
                " ".join(str(reply.get("meaning") or "").split())
                if pick == name
                else ""
            )
            picked.add(name.lower())
            # a place found without its kind or frame words ("White" of
            # "White Sea") is swapped in its whole written form only, so
            # "the White Light" elsewhere stays (real runs); a person's
            # part is swapped wherever it stands (it's the same person)
            was, form = v.spot.name, lambda c: c
            if v.spot.kind not in PERSON_KINDS and _whole(v.spot) != v.spot.name:
                was = _whole(v.spot)
                form = lambda c, old=was, part=v.spot.name: _swap([old], part, c)[0]  # noqa: E731
            texts = _swap(texts, was, form(name))
            marks.append(
                Mark(
                    id=_new_id(),
                    kind="replaced",
                    name=form(name),
                    was=was,
                    why=v.why,
                    meaning=meaning,
                    language_id=lid,
                    spares=[form(c) for c in free if c != name],
                    entry_kind=v.spot.kind,
                )  # fmt: skip
            )

    if to_rewrite:
        items = [
            {"n": n + 1, "title": _whole(v.spot)}
            for n, (v, _l, _g) in enumerate(to_rewrite)
        ]
        titles = await _titles(client, items)
        for n, (v, lid, language) in enumerate(to_rewrite):
            title = titles.get(n + 1, "")
            # the slot takes a place's name ("Free Provinces of Sorau")
            slot = v.spot.model_copy(update={"kind": "place", "part": "whole"})
            try:
                rolled = _candidates(language, slot, in_use)
            except ValueError:
                rolled = []
            fillers = [c for c in rolled if c.lower() not in picked]
            if not _SLOT.search(title) or not fillers:
                suspect(v, "a stock title", lid)
                continue
            filler = fillers[0]
            picked.add(filler.lower())
            name = " ".join(_SLOT.sub(filler, title).split())
            if name.lower().startswith("the "):
                name = name[4:]
            texts = _swap(texts, _whole(v.spot), name)
            marks.append(
                Mark(
                    id=_new_id(),
                    kind="replaced",
                    name=name,
                    was=_whole(v.spot),
                    why=v.why,
                    language_id=lid,
                    spares=[],
                    entry_kind=v.spot.kind,
                )  # fmt: skip
            )
    # no mark's spares hold a name another mark took (final review I2)
    taken = {m.name.lower() for m in marks}
    marks = [
        m.model_copy(update={"spares": [x for x in m.spares if x.lower() not in taken]})
        for m in marks
    ]
    return Cleaned(texts=texts, marks=marks)


def save_mark_words(rev, view: WorldView, marks: list[Mark], texts: list[str]) -> None:
    """Save each replaced name still in the accepted `texts` to its
    language as a word, with its meaning, in `rev` (one write per
    language, so several words land together). A word the language has
    gains the meaning; nothing is replaced."""

    by_language: dict[str, list[Mark]] = {}
    for mark in marks:
        if mark.kind != "replaced" or not mark.language_id:
            continue
        if not any(_swap([t], mark.name, "\0")[0] != t for t in texts):
            continue
        by_language.setdefault(mark.language_id, []).append(mark)
    for lid, found in by_language.items():
        state = view.thing(lid)
        if state is None or state.kind != "language":
            continue
        words = [
            {
                **DictionaryEntry.model_validate(w).model_dump(exclude_defaults=True),
                "meanings": list(DictionaryEntry.model_validate(w).meanings),
            }
            for w in state.fields.get("words") or []
        ]
        changed = False
        for mark in found:
            meaning = " ".join(mark.meaning.split())
            existing = next(
                (
                    w
                    for w in words
                    if str(w.get("word", "")).lower() == mark.name.lower()
                ),
                None,
            )
            if existing is None:
                words.append(
                    {"word": mark.name, "meanings": [meaning] if meaning else []}
                )
                changed = True
            elif meaning and meaning.lower() not in {
                m.lower() for m in existing["meanings"]
            }:
                existing["meanings"] = [*existing["meanings"], meaning]
                changed = True
        if changed:
            rev.set_field(lid, "words", words, None)
