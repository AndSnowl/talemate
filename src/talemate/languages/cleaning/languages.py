"""A draft's languages from the owner's words (languages 4a): which
languages is a name match; the model only gives each one's role and share,
and never adds one (probe 4, finding 4)."""

from __future__ import annotations

import re

import structlog

from talemate.languages.cleaning import ask
from talemate.languages.entry import languages as all_languages
from talemate.world.kinds import LANGUAGE_ROLES
from talemate.world.view import WorldView
from talemate.worldplay.create import json_objects

__all__ = ["language_rows", "named_languages"]

log = structlog.get_logger("talemate.languages.cleaning")

# a one-word name's first letters also match ("Moscavian" finds "Moscavia")
STEM = 5


def _names(state) -> list[str]:
    names = [str(state.fields.get("name") or "")]
    names += [str(a.get("name", "")) for a in state.fields.get("aka") or []]
    return [n for n in names if n.strip()]


def _patterns(name: str) -> list[re.Pattern]:
    words = name.split()
    found = [
        re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, words)) + r"(?!\w)", re.I)
    ]
    if len(words) == 1 and len(name) > STEM:
        found.append(re.compile(r"(?<!\w)" + re.escape(name[:STEM]), re.I))
    return found


def named_languages(view: WorldView, prompt: str) -> list[str]:
    """The ids of the world's languages the owner's words name, by their
    name, other names or (one-word names) first letters, in the order the
    words name them. A longer name wins over a shorter one inside it ("Old
    Moscavian" isn't also Moscavian)."""

    spans: list[tuple[int, int, str]] = []
    candidates = [
        (name, state.id) for state in all_languages(view) for name in _names(state)
    ]
    for name, lid in sorted(candidates, key=lambda c: -len(c[0])):
        for pattern in _patterns(name):
            for m in pattern.finditer(prompt):
                if any(a < m.end() and m.start() < b for a, b, _ in spans):
                    continue
                spans.append((m.start(), m.end(), lid))
    ids: list[str] = []
    for _start, _end, lid in sorted(spans):
        if lid not in ids:
            ids.append(lid)
    return ids


def _even(ids: list[str]) -> list[dict]:
    rows = [{"language": lid, "role": "spoken"} for lid in ids]
    if len(rows) > 1:
        for row in rows:
            row["share"] = round(100 / len(rows))
    return rows


async def language_rows(
    client, view: WorldView, prompt: str, ids: list[str]
) -> list[dict]:
    """Languages rows for `ids` (`languages` field shape), roles and
    shares from one model call; a share (0-100) only on spoken rows, and
    only when two or more are spoken. A failed or unreadable reply gives
    each one spoken, evenly."""

    if not ids:
        return []
    names = {lid: str(view.thing(lid).fields.get("name") or "") for lid in ids}
    try:
        reply = await ask(
            client,
            "language-roles",
            {
                "languages": [{"name": names[lid], "about": ""} for lid in ids],
                "roles": list(LANGUAGE_ROLES),
                "prompt": prompt,
            },
        )
        objects = json_objects(reply)
        got = objects[0].get("languages") if objects else None
        if not isinstance(got, list):
            raise ValueError("no languages in the reply")
    except Exception as exc:  # a failed call still gives rows
        log.warning("languages.clean_roles_failed", error=str(exc))
        return _even(ids)
    by_name = {n.lower(): lid for lid, n in names.items()}
    rows: dict[str, dict] = {}
    for item in got:
        if not isinstance(item, dict):
            continue
        lid = by_name.get(str(item.get("language", "")).strip().lower())
        if lid is None or lid in rows:
            continue
        role = item.get("role") if item.get("role") in LANGUAGE_ROLES else "spoken"
        share = item.get("share")
        rows[lid] = {
            "language": lid,
            "role": role,
            "_share": share
            if isinstance(share, (int, float)) and not isinstance(share, bool)
            else None,
        }
    if not rows:
        return _even(ids)
    ordered = [rows[lid] for lid in ids if lid in rows]
    spoken = [r for r in ordered if r["role"] == "spoken"]
    if len(spoken) > 1:
        total = sum(r["_share"] or 0 for r in spoken)
        for r in spoken:
            r["share"] = (
                round(100 * (r["_share"] or 0) / total)
                if total
                else round(100 / len(spoken))
            )
    for r in ordered:
        r.pop("_share")
    return ordered
