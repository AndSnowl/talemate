"""Culture-aware character naming for the Culture agent.

A stub in Task 6: the handlers are guarded no-ops. Task 7 fills them in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from talemate.cultures.signals import guarded

if TYPE_CHECKING:
    from talemate.agents.creator.character import CharacterNamingEmission

__all__ = ["CultureNamingMixin"]

log = structlog.get_logger("talemate.agents.culture.naming")


class CultureNamingMixin:
    @guarded
    async def on_before_name_character(
        self, emission: "CharacterNamingEmission"
    ) -> None:
        """`agent.creator.before_name_character` listener (Task 7)."""
        return None

    @guarded
    async def on_after_persist_character(self, emission) -> None:
        """`agent.director.character_management.after_persist_character`
        listener (Task 7)."""
        return None
