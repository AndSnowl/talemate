"""The `cultures.event` signal: what the Culture agent did, for the Cultures tab.

The Culture agent sends one `CulturesEvent` whenever it injects the prompt
section, picks a name or processes a snapshot. The cultures websocket
plugin forwards events for the world its scene uses to the frontend (and
re-sends the whole world first when `changed` is set).

`guarded` wraps the agent's signal handlers so that nothing they do can
break play: any exception other than `GenerationCancelled` is logged and
swallowed.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

import pydantic
import structlog

import talemate.emit.async_signals as async_signals
from talemate.exceptions import GenerationCancelled

__all__ = ["CulturesEvent", "send_event", "guarded"]

log = structlog.get_logger("talemate.cultures.signals")


class CulturesEvent(pydantic.BaseModel):
    kind: Literal["context_injected", "name_chosen", "snapshot_processed"]
    world_dir: str
    data: dict = {}
    # True when world files were written
    changed: bool = False


async_signals.register("cultures.event")


async def send_event(
    kind: str, world_dir: Path, data: dict, changed: bool = False
) -> None:
    await async_signals.get("cultures.event").send(
        CulturesEvent(kind=kind, world_dir=str(world_dir), data=data, changed=changed)
    )


def guarded(fn):
    """Decorate an async signal handler so it never raises into the sender.

    `GenerationCancelled` is re-raised (a cancel must still cancel); any
    other exception is logged and the handler returns `None`.
    """

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except GenerationCancelled:
            raise
        except Exception:
            log.exception("cultures: signal handler failed", handler=fn.__qualname__)
            return None

    return wrapper
