"""A mark on a flagged name (languages 4a revised): which words, why, and
the language in reach. Kept free of imports, so drafts can carry marks."""

from __future__ import annotations

from pydantic import BaseModel

__all__ = ["Mark"]


class Mark(BaseModel):
    id: str
    # the words underlined, as written ("White Sea", "Dmitri")
    name: str
    # the words Name it… starts on: the judged part ("France" in "the
    # Kingdom of France"); the same as `name` mostly
    part: str = ""
    why: str
    language_id: str | None = None
    entry_kind: str = "place"
