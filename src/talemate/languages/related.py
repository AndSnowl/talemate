"""The entries a change to a language should fit (languages 3b-2): who
speaks it, what's filed in them, and entries whose facts use its words.
They're suggestions, each with why; the owner ticks which go in."""

from __future__ import annotations

import re

from pydantic import BaseModel

from talemate.languages.entry import language_of
from talemate.world.filing import filed_in
from talemate.world.view import WorldView

__all__ = ["RelatedEntry", "related_entries"]

# a dictionary word shorter than this matches too much English ("on")
MIN_WORD = 3


class RelatedEntry(BaseModel):
    id: str
    name: str
    kind: str
    why: str


def related_entries(
    view: WorldView, language_id: str, limit: int = 12
) -> list[RelatedEntry]:
    """Speakers first (with their role), then entries filed in them, then
    entries whose facts use the language's words; each entry once, at most
    `limit`."""

    found: dict[str, RelatedEntry] = {}

    def add(state, why: str) -> None:
        if state.id != language_id and state.id not in found:
            found[state.id] = RelatedEntry(
                id=state.id,
                name=str(state.fields.get("name", "")),
                kind=state.kind,
                why=why,
            )

    things = view.things()
    speakers = []
    for state in things:
        for row in state.fields.get("languages") or []:
            if isinstance(row, dict) and row.get("language") == language_id:
                add(state, f"speaks it ({row.get('role', 'spoken')})")
                speakers.append(state)
                break
    for speaker in speakers:
        for state, _filing in filed_in(view, speaker.id, things=things):
            add(state, f"filed in {speaker.fields.get('name', '')}")

    language_state = view.thing(language_id)
    words = (
        {
            entry.word.lower()
            for entry in language_of(language_state).dictionary
            if len(entry.word) >= MIN_WORD
        }
        if language_state is not None
        else set()
    )
    if words:
        for state in things:
            if state.id in found or state.id == language_id:
                continue
            text = " ".join(view.render(fact.text) for fact in state.facts).lower()
            used = [w for w in sorted(words) if re.search(rf"\b{re.escape(w)}\b", text)]
            if used:
                shown = ", ".join(f'"{w}"' for w in used[:3])
                add(state, f"its facts use {shown}")
    return list(found.values())[:limit]
