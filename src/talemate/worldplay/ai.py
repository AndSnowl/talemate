"""Shared setup for the AI calls world-level code makes outside of any
loaded scene -- `create.preview_thing`, `prose_gen.render_section` and
`setup.plan_scene`/`continue_setup`'s ask and summary. These run from the
World tab or the Worlds home, before any scene is playing; `continue_setup`
runs from inside a loaded scene, but is wrapped the same way for safety.

`ClientBase._send_prompt` refuses to send when `requires_active_scene` is
set (the default) and there's no active scene, or it isn't active
(`SceneInactiveError`). The established pattern for a scene-less call is
the help chat's (`agents/help/chat.py`): `with
ClientContext(requires_active_scene=False):` around the generation.

It also reads a couple of attributes off the active-agent context
unconditionally (`ClientBase.tune_prompt_parameters`, the `PromptData` it
builds) -- something every *agent* action gets for free from
`@set_processing`'s own `ActiveAgent`. World-level calls aren't agent
actions, so there's no agent to supply it. They do, however, all run on
the creator agent's client (`server/worlds.py`'s
`instance.get_agent("creator").client`), so `world_ai_call` makes that
agent active for the call -- its own per-agent generation settings
(`inject_prompt_paramters`, `allow_repetition_break`) then apply, matching
what the owner would expect from "the creator made this". A neutral
stand-in is used instead if no creator agent exists yet, or (some tests'
own stand-in, a bare `SimpleNamespace(client=...)`) it isn't a real
`Agent` -- `ActiveAgentContext` reads attributes a non-agent double won't
have. Nothing is pushed at all if some other agent context is already
active."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import talemate.instance as instance
from talemate.agents.base import Agent
from talemate.agents.context import ActiveAgent, active_agent
from talemate.client.context import ClientContext


class _WorldAgent:
    """Stands in for the active-agent context on a world-level AI call when
    the creator agent isn't available. Not a real agent -- just enough of
    one that `ClientBase` doesn't choke on it: a no-op
    `inject_prompt_paramters` (the base `Agent`'s own is the same) and a
    repetition-break that's always declined, matching
    `Agent.allow_repetition_break`'s default."""

    agent_type = "world"
    verbose_name = "World"

    def inject_prompt_paramters(
        self, prompt_param: dict, kind: str, agent_function_name: str
    ) -> None:
        pass

    def allow_repetition_break(
        self, kind: str, agent_function_name: str, auto: bool = False
    ) -> bool:
        return False


_WORLD_AGENT = _WorldAgent()


@contextmanager
def world_ai_call() -> Iterator[None]:
    """Wrap a world-level AI call so it can run with no scene active, or an
    inactive one, the same way the help chat does. Also makes the creator
    agent active for the call, so `ClientBase` reads its settings instead
    of crashing on a missing active-agent context -- unless some other
    agent context is already active (nested inside a real one, e.g. the
    summarizer's own `@set_processing`, this changes nothing), or there's
    no creator agent yet, in which case the stand-in above is used."""

    with ClientContext(requires_active_scene=False):
        if active_agent.get() is None:
            try:
                candidate = instance.get_agent("creator")
            except KeyError:
                candidate = None
            agent = candidate if isinstance(candidate, Agent) else _WORLD_AGENT
            with ActiveAgent(agent, world_ai_call):
                yield
        else:
            yield
