"""A mark on a cleaned name (languages 4a): what replaced what and why, or
why a name is suspect. Kept free of imports, so drafts can carry marks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

__all__ = ["Mark"]


class Mark(BaseModel):
    id: str
    kind: Literal["replaced", "suspect"]
    name: str
    was: str
    why: str
    meaning: str = ""
    language_id: str | None = None
    # the other rolled names: Reroll, and Replace it on a suspect one
    spares: list[str] = []
    entry_kind: str = "place"
