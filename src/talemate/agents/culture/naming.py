"""Culture-aware character naming for the Culture agent.

When the creator is about to invent a name for a new character
(`agent.creator.before_name_character`), the agent guesses the character's
culture, rolls candidates from that culture's generator and makes one model
call to pick the best fit. The pick is supplied as the character's name and
recorded in the glossary (unreviewed). Once the character is saved
(`agent.director.character_management.after_persist_character`) its
culture is set; a name the agent didn't pick is recorded as a free one.

Existing names are never replaced, and owner-set cultures are final.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import structlog

from talemate.agents.base import DynamicInstruction, set_processing
from talemate.cultures.generator import fits
from talemate.cultures.models import (
    CharacterCulture,
    Culture,
    GlossaryEntry,
    GlossaryOrigin,
    new_id,
)
from talemate.cultures.naming import (
    choose_generator,
    guess_culture,
    guess_culture_for_name,
    infer_gender,
    match_candidate,
    roll_candidates,
)
from talemate.cultures.signals import guarded, send_event
from talemate.cultures.words import (
    _LEADING_STOP_WORDS,
    clean_name,
    first_mention,
    looks_like_name,
    mid_sentence_occurrence,
)
from talemate.exceptions import GenerationCancelled
from talemate.prompts import Prompt
from talemate.prompts.response import AnchorExtractor, ResponseSpec

if TYPE_CHECKING:
    from talemate.agents.creator.character import CharacterNamingEmission
    from talemate.agents.director.character_management import (
        PersistCharacterEmission,
    )

__all__ = ["CultureNamingMixin", "MAX_PENDING", "NAMING_DECISION_TTL"]

log = structlog.get_logger("talemate.agents.culture.naming")

# At most this many picked-but-not-yet-saved names are remembered (oldest
# dropped), like `offered_spares`.
MAX_PENDING = 20

# The pre-naming hook can fire twice for one creation (the director's fast
# flow retries `determine_character_name` when the one-shot missed the
# name). A decision is remembered this long (seconds), keyed by the
# requested name and content, so the second call neither rolls nor asks the
# model again. Saving a character clears the remembered decisions.
NAMING_DECISION_TTL = 120.0
MAX_NAMING_DECISIONS = 20

PICK_NAME_SPEC = ResponseSpec(
    extractors={
        "name": AnchorExtractor(left="<NAME>", right="</NAME>"),
        "why": AnchorExtractor(left="<WHY>", right="</WHY>"),
    },
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    return _SENTENCE_END.split(text, maxsplit=1)[0]


def _culture_instruction(name: str, culture: Culture) -> str:
    """`"{name} is {culture}. {description} Their language, {language},
    {sound}"`, from the non-empty parts only."""

    language = culture.language
    parts = [f"{name} is {culture.name}."]
    description = _first_sentence(culture.description)
    if description:
        parts.append(description)
    sound = _first_sentence(language.sound)
    if sound:
        parts.append(f"Their language, {language.name}, {sound}")
    elif language.name:
        parts.append(f"Their language is {language.name}.")
    return " ".join(parts)


def _decision_key(emission: "CharacterNamingEmission") -> tuple[str, str]:
    return (emission.name.strip().lower(), emission.content.strip())


class CultureNamingMixin:
    def _naming_decision_store(self) -> dict:
        """The pre-naming hook's recent decisions (see NAMING_DECISION_TTL),
        expired ones dropped: key -> (monotonic time, chosen name or None,
        dynamic instructions)."""
        store = getattr(self, "_naming_decisions", None)
        if store is None:
            store = self._naming_decisions = {}
        now = time.monotonic()
        for key in [
            k for k, (at, _, _) in store.items() if now - at > NAMING_DECISION_TTL
        ]:
            store.pop(key)
        return store

    def _remember_naming_decision(
        self,
        key: tuple[str, str],
        name: str | None,
        instructions: list[DynamicInstruction],
    ) -> None:
        store = self._naming_decision_store()
        store.pop(key, None)
        store[key] = (time.monotonic(), name, list(instructions))
        while len(store) > MAX_NAMING_DECISIONS:
            store.pop(next(iter(store)))

    def _remember_pending(self, name: str, culture: CharacterCulture) -> None:
        key = name.lower()
        self._pending.pop(key, None)
        self._pending[key] = culture
        while len(self._pending) > MAX_PENDING:
            self._pending.pop(next(iter(self._pending)))

    def _place_label(self) -> str:
        """The matched place's name, else the scene's free-text location."""
        place_id = self.get_scene_state("current_place_id")
        world = self.load_world() if place_id else None
        if world is not None:
            for place in world.places:
                if place.id == place_id:
                    return place.name
        return self.scene.world_state.location or ""

    def _story_label(self) -> str:
        return self.scene.title or self.scene.name or ""

    def _is_existing_name(self, name: str) -> bool:
        if not name:
            return False
        if looks_like_name(name):
            return True
        # a lowercase description ("the ferryman") is not a name, however
        # often the scene mentions it: only a capitalised hint ("the Rook")
        # can be a name in use
        words = name.split()
        while words and words[0].lower() in _LEADING_STOP_WORDS:
            words = words[1:]
        if not any(word[:1].isupper() for word in words):
            return False
        return any(
            mid_sentence_occurrence(name, str(getattr(message, "message", "") or ""))
            for message in self.scene.history
        )

    @guarded
    async def on_before_name_character(
        self, emission: "CharacterNamingEmission"
    ) -> None:
        """`agent.creator.before_name_character` listener: pre-supply a name
        from the character's culture when the creator was about to invent
        one."""

        started = time.monotonic()
        world = self.load_world()
        if world is None:
            return

        key = _decision_key(emission)
        remembered = self._naming_decision_store().get(key)
        if remembered is not None:
            _, name, instructions = remembered
            if name is None or name not in self.scene.all_character_names:
                if name:
                    emission.chosen_name = name
                    emission.dynamic_instructions.extend(instructions)
                return
            # that creation finished; this is a new one with the same request
            self._naming_decision_store().pop(key, None)

        # 1. existing names are kept
        if self._is_existing_name(clean_name(emission.name)):
            return

        # from here on the decision (even "no name") is remembered, so a
        # second hook for the same creation doesn't roll or ask again
        self._remember_naming_decision(key, None, [])

        # 2. culture
        text = f"{emission.name} {emission.content} {emission.description}"
        scene_cultures = self.scene_cultures(world)
        guess = guess_culture(world.cultures, scene_cultures, text, self.rng)
        culture = world.cultures.get(guess.culture_id) if guess.culture_id else None
        if culture is None:
            return
        language = culture.language

        # 3. generator
        generator = choose_generator(language, infer_gender(text), self.rng)
        if generator is None:
            return

        # 4. candidates
        exclude = {entry.text for entry in world.glossary} | set(
            self.scene.all_character_names
        )
        candidates = roll_candidates(
            language, generator, self.candidate_count, exclude, self.rng
        )
        if not candidates:
            return

        # 5. pick (the only await between rolling and recording)
        try:
            name, why, by_model = await self.pick_name(candidates, culture, emission)
        except GenerationCancelled:
            # a cancelled creation decided nothing; a retry may ask again
            self._naming_decision_store().pop(key, None)
            raise

        # 6. record
        instructions = [
            DynamicInstruction(
                title="Culture",
                content=_culture_instruction(name, culture),
            )
        ]
        request = "; ".join(
            part for part in (emission.name.strip(), emission.content.strip()) if part
        )
        if request:
            instructions.append(
                DynamicInstruction(
                    title="Character request",
                    content=(
                        f"{name} is the character requested as: {request}. "
                        "Write the rest of the character to fit that request."
                    ),
                )
            )
        emission.chosen_name = name
        emission.dynamic_instructions.extend(instructions)
        self._remember_naming_decision(key, name, instructions)

        # before the save, so a disk error there doesn't lose it
        self._remember_pending(
            name,
            CharacterCulture(
                culture_id=culture.id,
                set_by="ai",
                unsure=guess.unsure,
                reason=guess.reason,
            ),
        )

        # R2: re-load right before the save, no await in between
        entries = world.store.load_glossary()
        if not any(entry.text.lower() == name.lower() for entry in entries):
            entries.append(
                GlossaryEntry(
                    id=new_id(),
                    text=name,
                    language=culture.id,
                    kind="person",
                    origin=GlossaryOrigin(
                        by="ai", generator_id=generator.id, candidates=candidates
                    ),
                    first_used=f"{self._story_label()}, character creation",
                    status="unreviewed",
                    character_name=name,
                )
            )
            world.store.save_glossary(entries)

        await send_event(
            "name_chosen",
            world.world_dir,
            {
                "name": name,
                "culture_id": culture.id,
                "generator_id": generator.id,
                "candidates": candidates,
                "by_model": by_model,
                "why": why,
                "ms": int((time.monotonic() - started) * 1000),
            },
            changed=True,
        )

    @set_processing
    async def pick_name(
        self,
        candidates: list[str],
        culture: Culture,
        emission: "CharacterNamingEmission",
    ) -> tuple[str, str, bool]:
        """Ask the model to pick one of `candidates`.

        Returns `(name, why, by_model)`. A pick that isn't one of the
        candidates, or a failed call, falls back to the first candidate
        with `by_model=False`.
        """

        try:
            response, extracted = await Prompt.request(
                "culture.pick-name",
                self.client,
                "analyze_freeform_medium_short",
                vars={
                    "scene": self.scene,
                    "max_tokens": self.client.max_token_length,
                    "candidates": candidates,
                    "culture": culture,
                    "language": culture.language,
                    "character_hint": emission.name,
                    "content": emission.content,
                    "description": emission.description,
                    "recent_text": self.recent_text(3),
                    "place": self._place_label(),
                },
                response_spec=PICK_NAME_SPEC,
            )
        except GenerationCancelled:
            raise
        except Exception:
            log.exception("culture: pick-name request failed")
            return candidates[0], "", False

        extracted = extracted or {}
        picked = extracted.get("name") or response or ""
        name = match_candidate(str(picked), candidates)
        if name is None:
            return candidates[0], "", False
        why = str(extracted.get("why") or "").strip()
        return name, why, True

    @guarded
    async def on_after_persist_character(
        self, emission: "PersistCharacterEmission"
    ) -> None:
        """`agent.director.character_management.after_persist_character`
        listener: set the saved character's culture, and record a name the
        agent didn't pick."""

        character = emission.character
        # the creation is finished: forget the pre-naming decisions
        self._naming_decision_store().clear()

        if character.culture is not None and character.culture.set_by == "owner":
            return

        world = self.load_world()
        if world is None:
            return

        name = character.name
        pending = self._pending.pop(name.lower(), None)
        culture_set = False
        glossary_written = False

        if pending is not None:
            character.culture = pending
            culture_set = True
        elif character.culture is None:
            guess = guess_culture_for_name(
                world.cultures, self.scene_cultures(world), name
            )
            # a mix can name a culture the world doesn't have (yet)
            culture = world.cultures.get(guess.culture_id) if guess.culture_id else None
            if culture is not None:
                character.culture = CharacterCulture(
                    culture_id=culture.id,
                    set_by="ai",
                    unsure=guess.unsure,
                    reason=guess.reason,
                )
                culture_set = True

            mention = first_mention(name, list(self.scene.history))
            story = self._story_label()
            first_used = (
                f"{story}, message {mention.id}"
                if mention is not None
                else f"{story}, character creation"
            )

            # R2: load and save with no await in between
            entries = world.store.load_glossary()
            if not any(entry.text.lower() == name.lower() for entry in entries):
                entries.append(
                    GlossaryEntry(
                        id=new_id(),
                        text=name,
                        language=culture.id if culture is not None else None,
                        kind="person",
                        origin=GlossaryOrigin(by="ai_free"),
                        first_used=first_used,
                        status="unreviewed",
                        character_name=name,
                        doesnt_fit=(
                            culture is not None and not fits(culture.language, name)
                        ),
                    )
                )
                world.store.save_glossary(entries)
                glossary_written = True

        if not (culture_set or glossary_written):
            return

        await send_event(
            "name_chosen",
            world.world_dir,
            {
                "name": name,
                "culture_id": (
                    character.culture.culture_id if character.culture else None
                ),
                "generator_id": None,
                "candidates": [],
                "by_model": False,
                "why": "",
                "ms": 0,
            },
            changed=True,
        )
