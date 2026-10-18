"""Post-snapshot place and name detection for the Culture agent.

A stub in Task 6: the handler is a guarded no-op. Task 8 fills it in. The
guard matters already: an exception from a `world_state.snapshot.after`
listener would otherwise propagate into the world-state background task.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from talemate.cultures.signals import guarded

if TYPE_CHECKING:
    from talemate.agents.world_state.snapshot import WorldStateSnapshotEmission

__all__ = ["CultureSnapshotMixin"]

log = structlog.get_logger("talemate.agents.culture.snapshot")


class CultureSnapshotMixin:
    @guarded
    async def on_snapshot_after(self, emission: "WorldStateSnapshotEmission") -> None:
        """`world_state.snapshot.after` listener (Task 8)."""
        return None
