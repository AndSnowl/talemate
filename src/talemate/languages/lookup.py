"""Which languages apply to an entry (languages 3a; main spec, "Pages and
characters have a Languages section").

- An entry's own live rows win.
- Otherwise its languages come from what it's filed in: each live filing is
  walked up separately, each entry visited once (so a cycle ends), and each
  branch stops at the first entry that states rows. The union is returned,
  marked inherited.
- A character follows only filings into places, and keeps only spoken and
  official rows: a monk doesn't speak his order's liturgical language
  unless his own section says so.
- A row whose language is missing or removed is skipped.
"""

from __future__ import annotations

from pydantic import BaseModel

from talemate.world.dates import WorldDate
from talemate.world.filing import filings_of
from talemate.world.view import ThingState, WorldView

__all__ = [
    "LanguageRow",
    "default_language",
    "languages_for",
    "languages_for_scene",
]

_CHARACTER_ROLES = ("spoken", "official")


class LanguageRow(BaseModel):
    language_id: str
    name: str
    role: str
    share: float | None = None
    fluency: str | None = None
    source_id: str
    inherited: bool = False


def _date(value: object) -> WorldDate | None:
    if value is None:
        return None
    return value if isinstance(value, WorldDate) else WorldDate.model_validate(value)


def _row_live(row: dict, at: WorldDate | None) -> bool:
    since, until = _date(row.get("since")), _date(row.get("until"))
    if at is None:
        return until is None
    if since is not None and since.instant > at.instant:
        return False
    return until is None or until.instant > at.instant


def _own_rows(view: WorldView, state: ThingState, inherited: bool) -> list[LanguageRow]:
    rows = []
    for row in state.fields.get("languages") or []:
        if not _row_live(row, view.at):
            continue
        language = view.thing(row["language"])
        if language is None or language.kind != "language":
            continue
        rows.append(
            LanguageRow(
                language_id=row["language"],
                name=str(language.fields.get("name") or ""),
                role=row["role"],
                share=row.get("share"),
                fluency=row.get("fluency"),
                source_id=state.id,
                inherited=inherited,
            )
        )
    return rows


def _inherited(view: WorldView, thing_id: str, places_only: bool) -> list[LanguageRow]:
    found: list[LanguageRow] = []
    seen = {thing_id}

    def walk(current: str) -> None:
        for filing in filings_of(view, current):
            target = filing.target
            if target in seen:
                continue
            seen.add(target)
            state = view.thing(target)
            if state is None:
                continue
            if places_only and state.kind != "place":
                continue
            rows = _own_rows(view, state, inherited=True)
            if rows:
                found.extend(rows)
            else:
                walk(target)

    walk(thing_id)
    return found


def _unique(rows: list[LanguageRow]) -> list[LanguageRow]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for row in rows:
        key = (row.language_id, row.role)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def languages_for(view: WorldView, thing_id: str) -> list[LanguageRow]:
    """The languages that apply to `thing_id` at the view's date."""

    state = view.thing(thing_id)
    if state is None:
        return []
    own = _own_rows(view, state, inherited=False)
    if own:
        return own
    character = state.kind == "character"
    rows = _inherited(view, thing_id, places_only=character)
    if character:
        rows = [r for r in rows if r.role in _CHARACTER_ROLES]
    return _unique(rows)


def default_language(rows: list[LanguageRow]) -> str | None:
    """The language naming starts from: an official one, else the spoken
    one with the largest share, else the first."""

    if not rows:
        return None
    for row in rows:
        if row.role == "official":
            return row.language_id
    spoken = [r for r in rows if r.role == "spoken"]
    if spoken:
        return max(spoken, key=lambda r: r.share or 0).language_id
    return rows[0].language_id


def languages_for_scene(
    view: WorldView, place_id: str | None, speaker_id: str | None
) -> list[LanguageRow]:
    """The speaker's languages first, then the scene place's, each
    language once."""

    rows: list[LanguageRow] = []
    for thing_id in (speaker_id, place_id):
        if thing_id:
            rows += languages_for(view, thing_id)
    seen: set[str] = set()
    unique = []
    for row in rows:
        if row.language_id not in seen:
            seen.add(row.language_id)
            unique.append(row)
    return unique
