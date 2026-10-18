"""The Culture agent.

Brings a shared world's cultures (plan 1: `talemate.cultures`) into play:

- injects the "Cultures and names" prompt section into narrator and
  conversation prompts (built from files and rules only, no model call)
- pre-supplies culture-appropriate names when the creator is about to
  invent one (`naming.py`, Task 7)
- records new places and names after a world-state snapshot
  (`snapshot.py`, Task 8)

A scene with no shared world, or a world with no cultures, is left exactly
as before: no section, no naming, no detection and no scene state. Every
signal handler is `guarded`, so nothing here can break play.
"""

from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass
from pathlib import Path

import structlog

from talemate.agents.base import Agent, AgentAction, AgentActionConfig
from talemate.agents.base import DynamicInstruction
from talemate.agents.conversation import ConversationAgentEmission
from talemate.agents.narrator import NarratorAgentEmission
from talemate.agents.registry import register
from talemate.client import ClientBase
from talemate.cultures.context import SECTION_TITLE, build_culture_section
from talemate.cultures.models import CharacterCulture, Culture, GlossaryEntry, Place
from talemate.cultures.scene_context import SceneCultures, resolve_scene_cultures
from talemate.cultures.signals import guarded, send_event
from talemate.cultures.store import WorldStore, world_dir_for_scene
import talemate.emit.async_signals as async_signals

from .naming import CultureNamingMixin
from .snapshot import CultureSnapshotMixin

__all__ = ["CultureAgent", "LoadedWorld"]

log = structlog.get_logger("talemate.agents.culture")

# At most this many offered spare names are remembered in scene state
# (oldest dropped), so Task 8 can tell a reused spare from a free invention.
MAX_OFFERED_SPARES = 60

_RECENT_MESSAGE_TYPES = ("narrator", "character", "context_investigation")


def _world_files_signature(store: WorldStore) -> tuple:
    """(path, mtime_ns, size) of every file `load_world` reads; a missing
    file is (path, None, None)."""

    paths = [store.places_path, store.glossary_path]
    if store.cultures_dir.exists():
        paths.extend(sorted(store.cultures_dir.glob("*.json")))
    signature = []
    for path in paths:
        try:
            stat = path.stat()
        except FileNotFoundError:
            signature.append((str(path), None, None))
        else:
            signature.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


@dataclass
class LoadedWorld:
    store: WorldStore
    world_dir: Path
    cultures: dict[str, Culture]
    places: list[Place]
    glossary: list[GlossaryEntry]


@register()
class CultureAgent(CultureNamingMixin, CultureSnapshotMixin, Agent):
    """
    Culture agent

    Keeps names, languages and customs consistent with the cultures of the
    scene's shared world.
    """

    agent_type = "culture"
    verbose_name = "Culture"
    essential = False

    @classmethod
    def init_actions(cls) -> dict[str, AgentAction]:
        return {
            "culture": AgentAction(
                enabled=True,
                container=True,
                label="Cultures",
                icon="mdi-account-group-outline",
                description=(
                    "Uses the shared world's cultures for names, languages "
                    "and customs. Does nothing in a scene without a shared "
                    "world or without cultures."
                ),
                config={
                    "context_budget": AgentActionConfig(
                        type="number",
                        label="Context budget (tokens)",
                        description=(
                            "The most tokens the Cultures and names section "
                            "may use in narrator and character prompts."
                        ),
                        value=400,
                        min=100,
                        max=1500,
                        step=50,
                    ),
                    "candidates": AgentActionConfig(
                        type="number",
                        label="Name candidates",
                        description=(
                            "How many generated names the model chooses "
                            "from when naming a new character."
                        ),
                        value=20,
                        min=5,
                        max=50,
                        step=1,
                    ),
                },
            )
        }

    def __init__(self, client: ClientBase | None = None, **kwargs):
        self.client = client
        self.is_enabled = True
        self.actions = CultureAgent.init_actions()
        self.rng = random.Random()
        self._pending: dict[str, CharacterCulture] = {}
        # ((world_dir, files signature), LoadedWorld | None), see load_world
        self._world_cache: tuple[tuple, LoadedWorld | None] | None = None

    @property
    def enabled(self):
        return self.is_enabled

    @property
    def has_toggle(self):
        return True

    @property
    def context_budget(self) -> int:
        return int(self.resolve_config("culture", "context_budget"))

    @property
    def candidate_count(self) -> int:
        return int(self.resolve_config("culture", "candidates"))

    # world access

    def load_world(self) -> LoadedWorld | None:
        """Load the scene's shared world, or `None` when there's nothing to use.

        `None` when the agent is disabled, the scene has no shared context,
        the world has no (readable) cultures, or loading fails (logged).

        The parsed world is cached per world dir and reused while every
        world file's (path, mtime_ns, size) is unchanged, so narrator and
        actor turns don't re-parse a growing glossary each time. Any write
        on disk (the agent's own, or the Cultures tab's) invalidates it.
        Callers get fresh containers but shared model objects: treat the
        models as read-only and re-load from the store before saving.
        """
        if not self.enabled or getattr(self, "scene", None) is None:
            return None
        try:
            world_dir = world_dir_for_scene(self.scene)
            if world_dir is None:
                return None
            store = WorldStore(world_dir)
            key = (str(world_dir), _world_files_signature(store))
            if self._world_cache is not None and self._world_cache[0] == key:
                cached = self._world_cache[1]
            else:
                cultures = store.load_cultures()
                cached = (
                    LoadedWorld(
                        store=store,
                        world_dir=world_dir,
                        cultures=cultures,
                        places=store.load_places(),
                        glossary=store.load_glossary(),
                    )
                    if cultures
                    else None
                )
                self._world_cache = (key, cached)
            if cached is None:
                return None
            return dataclasses.replace(
                cached,
                cultures=dict(cached.cultures),
                places=list(cached.places),
                glossary=list(cached.glossary),
            )
        except Exception:
            self._world_cache = None
            log.exception("culture: could not load the shared world")
            return None

    def scene_cultures(self, world: LoadedWorld) -> SceneCultures:
        world_state = self.scene.world_state
        resolved = resolve_scene_cultures(
            world.cultures,
            world.places,
            world_state.location,
            list(world_state.places.keys()),
            list(self.scene.characters),
            fallback_place_id=self.get_scene_state("current_place_id"),
        )
        if resolved.place is not None:
            self.set_scene_states(current_place_id=resolved.place.id)
        return resolved

    def recent_text(self, limit_messages: int = 6) -> str:
        messages = [
            message
            for message in self.scene.history
            if getattr(message, "typ", None) in _RECENT_MESSAGE_TYPES
        ]
        return "\n".join(str(m.message) for m in messages[-limit_messages:])

    # signals

    def connect(self, scene):
        super().connect(scene)
        async_signals.get("agent.narrator.inject_instructions").connect(
            self.on_inject_instructions
        )
        async_signals.get("agent.conversation.inject_instructions").connect(
            self.on_inject_instructions
        )
        async_signals.get("agent.creator.before_name_character").connect(
            self.on_before_name_character
        )
        async_signals.get(
            "agent.director.character_management.after_persist_character"
        ).connect(self.on_after_persist_character)
        async_signals.get("world_state.snapshot.after").connect(self.on_snapshot_after)

    @guarded
    async def on_inject_instructions(
        self, emission: ConversationAgentEmission | NarratorAgentEmission
    ) -> None:
        """Add the "Cultures and names" section to a narrator or actor prompt."""

        world = self.load_world()
        if world is None:
            return

        if isinstance(emission, ConversationAgentEmission):
            agent_name = "conversation"
            characters = [emission.character]
        else:
            agent_name = "narrator"
            characters = list(self.scene.characters)

        section = build_culture_section(
            scene=self.scene_cultures(world),
            cultures=world.cultures,
            glossary=world.glossary,
            characters=characters,
            recent_text=self.recent_text(),
            budget=self.context_budget,
            rng=self.rng,
        )
        if not section.text:
            return

        emission.dynamic_instructions.append(
            DynamicInstruction(title=SECTION_TITLE, content=section.text)
        )
        self._remember_spares(section.spares)

        await send_event(
            "context_injected",
            world.world_dir,
            {
                "agent": agent_name,
                "text": section.text,
                "tokens": section.tokens,
                "spares": [
                    {
                        "text": spare.text,
                        "culture_id": spare.culture_id,
                        "generator_id": spare.generator_id,
                    }
                    for spare in section.spares
                ],
            },
        )

    def _remember_spares(self, spares) -> None:
        if not spares:
            return
        offered: dict = dict(self.get_scene_state("offered_spares") or {})
        for spare in spares:
            key = spare.text.lower()
            # re-insert so a re-offered name counts as the newest
            offered.pop(key, None)
            offered[key] = {
                "culture_id": spare.culture_id,
                "generator_id": spare.generator_id,
            }
        while len(offered) > MAX_OFFERED_SPARES:
            offered.pop(next(iter(offered)))
        self.set_scene_states(offered_spares=offered)
