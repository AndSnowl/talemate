"""Post-snapshot place and name detection for the Culture agent.

After each world-state snapshot (`world_state.snapshot.after`) the agent:

1. works out the scene's place and cultures,
2. infers the world's new places (one model call, only when there are new
   place names),
3. records new names in the glossary (unreviewed),
4. sets an AI culture for scene characters that have none,
5. looks for play additions to the cultures present (one model call, only
   when a culture is present and there are new messages since the last
   check),
6. and reports what it did in one `snapshot_processed` event.

Each step is guarded on its own, so a failed model call or disk write
doesn't stop the others, and the handler itself is `guarded`: an exception
from a `world_state.snapshot.after` listener would otherwise propagate into
the world-state background task. Existing places and owner-set cultures
are never changed; world files are re-loaded right before each save (R2).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog

from talemate.agents.base import set_processing
from talemate.cultures.detect import (
    PLACE_KINDS,
    find_new_names,
    location_place_name,
    name_key,
    new_place_names,
    parse_additions_reply,
    parse_places_reply,
)
from talemate.cultures.models import (
    CharacterCulture,
    GlossaryEntry,
    Place,
    PlayAddition,
    new_id,
)
from talemate.cultures.naming import CultureGuess, guess_culture_for_name
from talemate.cultures.scene_context import SceneCultures
from talemate.cultures.signals import guarded, send_event
from talemate.cultures.words import clean_name, first_mention
from talemate.exceptions import GenerationCancelled
from talemate.prompts import Prompt
from talemate.prompts.response import AnchorExtractor, ResponseSpec

from .naming import record_kept_name

if TYPE_CHECKING:
    from talemate.agents.culture import LoadedWorld
    from talemate.agents.world_state.snapshot import WorldStateSnapshotEmission

__all__ = ["CultureSnapshotMixin", "ADDITIONS_MESSAGE_LIMIT"]

log = structlog.get_logger("talemate.agents.culture.snapshot")

# At most this many of the new messages are read for play additions.
ADDITIONS_MESSAGE_LIMIT = 8

# At most this many names the place call skipped (not places) are
# remembered in scene state, so they aren't proposed again (oldest dropped).
MAX_SKIPPED_PLACES = 60

_NARRATIVE_TYPES = ("narrator", "character", "context_investigation")

INFER_PLACES_SPEC = ResponseSpec(
    extractors={"places": AnchorExtractor(left="<PLACES>", right="</PLACES>")},
)
FIND_ADDITIONS_SPEC = ResponseSpec(
    extractors={"additions": AnchorExtractor(left="<ADDITIONS>", right="</ADDITIONS>")},
)


def _place_line(place: Place, by_id: dict[str, Place]) -> str:
    parent = by_id.get(place.parent_id) if place.parent_id else None
    if parent is None:
        return f"{place.name} ({place.kind})"
    return f"{place.name} ({place.kind}, in {parent.name})"


class CultureSnapshotMixin:
    @guarded
    async def on_snapshot_after(self, emission: "WorldStateSnapshotEmission") -> None:
        """`world_state.snapshot.after` listener."""

        started = time.monotonic()
        world = self.load_world()
        if world is None:
            return

        world_state = emission.world_state or self.scene.world_state
        changed = False
        new_places: list[Place] = []
        findings = []
        cultures_set: list[dict] = []
        additions: list[tuple[str, PlayAddition]] = []

        # 1. place and cultures
        sc = self.scene_cultures(world)
        places = list(world.places)

        # 2. places (one model call, only for new names)
        try:
            new_places, places = await self._snapshot_places(world, sc, world_state)
            changed = changed or bool(new_places)
        except GenerationCancelled:
            raise
        except Exception:
            log.exception("culture: snapshot places step failed")

        # 3. names
        try:
            findings = self._snapshot_names(world, sc, world_state, new_places, places)
            changed = changed or bool(findings)
        except GenerationCancelled:
            raise
        except Exception:
            findings = []
            log.exception("culture: snapshot names step failed")

        # 4. character cultures
        try:
            cultures_set = self._snapshot_character_cultures(world, sc)
            changed = changed or bool(cultures_set)
        except GenerationCancelled:
            raise
        except Exception:
            log.exception("culture: snapshot character cultures step failed")

        # 5. additions (one gated model call)
        try:
            additions = await self._snapshot_additions(world, sc)
            changed = changed or bool(additions)
        except GenerationCancelled:
            raise
        except Exception:
            additions = []
            log.exception("culture: snapshot additions step failed")

        # 6. event: the scene's place is the one just created when the
        # location names it first ("Kesterholm, on the Birch Coast")
        place_name = sc.place.name if sc.place is not None else None
        first_key = name_key(location_place_name(world_state.location) or "")
        for place in new_places:
            if first_key and name_key(place.name) == first_key:
                place_name = place.name
        await send_event(
            "snapshot_processed",
            world.world_dir,
            {
                "place": place_name,
                "new_places": [place.name for place in new_places],
                "new_names": [
                    {
                        "text": finding.text,
                        "kind": finding.kind,
                        "culture_id": finding.culture_id,
                        "doesnt_fit": finding.doesnt_fit,
                        "origin": finding.origin.by,
                    }
                    for finding in findings
                ],
                "cultures_set": cultures_set,
                "additions": [
                    {
                        "culture_id": culture_id,
                        "section": addition.section,
                        "text": addition.text,
                    }
                    for culture_id, addition in additions
                ],
                "ms": int((time.monotonic() - started) * 1000),
            },
            changed=changed,
        )

    # steps

    async def _snapshot_places(
        self, world: "LoadedWorld", sc: SceneCultures, world_state
    ) -> tuple[list[Place], list[Place]]:
        """Infer and save new places. Returns `(added, all places)`."""

        snapshot_names = [clean_name(name) for name in world_state.characters]
        skipped = list(self.get_scene_state("skipped_places") or [])
        persons = [
            text
            for entry in world.glossary
            if entry.kind == "person"
            for text in (entry.text, entry.character_name)
            if text
        ]
        names = new_place_names(
            world_state.location,
            list(world_state.places.keys()),
            world.places,
            list(self.scene.all_character_names) + snapshot_names + skipped,
            person_names=list(self.scene.all_character_names) + persons,
        )
        if not world.cultures or not names:
            return [], list(world.places)

        inferred = await self.infer_places(names, world, sc)

        # R2: re-load right before the save, no await in between; only add
        # places the world still doesn't have (existing ones are final)
        fresh = world.store.load_places()
        taken = {place.name.lower() for place in fresh}
        added: list[Place] = []
        for place in inferred:
            if place.name.lower() not in taken:
                taken.add(place.name.lower())
                added.append(place)
        if not added:
            return [], fresh
        # a parent deleted while the model was answering is gone
        valid_ids = {place.id for place in fresh + added}
        added = [
            place
            if place.parent_id is None or place.parent_id in valid_ids
            else place.model_copy(update={"parent_id": None, "unsure": True})
            for place in added
        ]
        places = fresh + added
        world.store.save_places(places)
        return added, places

    def _snapshot_names(
        self,
        world: "LoadedWorld",
        sc: SceneCultures,
        world_state,
        new_places: list[Place],
        places: list[Place],
    ) -> list:
        places_found = [(place.name, place.id) for place in new_places]
        if sc.place is not None:
            places_found.append((sc.place.name, sc.place.id))

        # R2: the glossary is read and saved with no await in between
        glossary = world.store.load_glossary()
        findings = find_new_names(
            characters=list(world_state.characters.keys()),
            items=list(world_state.items.keys()),
            places_found=places_found,
            glossary=glossary,
            cultures=world.cultures,
            scene=sc,
            scene_characters={c.name: c for c in self.scene.characters},
            messages=list(self.scene.history),
            offered_spares=dict(self.get_scene_state("offered_spares") or {}),
            story=self._story_label(),
            places=places,
        )
        if not findings:
            return []
        glossary.extend(
            GlossaryEntry(
                id=new_id(),
                text=finding.text,
                language=finding.culture_id,
                kind=finding.kind,
                origin=finding.origin,
                first_used=finding.first_used,
                status="unreviewed",
                character_name=finding.character_name,
                place_id=finding.place_id,
                doesnt_fit=finding.doesnt_fit,
            )
            for finding in findings
        )
        world.store.save_glossary(glossary)
        return findings

    def _snapshot_character_cultures(
        self, world: "LoadedWorld", sc: SceneCultures
    ) -> list[dict]:
        """An AI culture for each scene character that has none (an existing
        culture, owner-set or not, is left alone), and a kept-name glossary
        entry for it when it doesn't have one yet (see `record_kept_name`)."""

        cultures_set = []
        offered = self.get_scene_state("offered_spares") or {}
        for character in self.scene.characters:
            if character.culture is not None:
                continue
            spare = offered.get(character.name.lower()) or {}
            if spare.get("culture_id") in world.cultures:
                # R11: a reused spare is of its generator's culture
                guess = CultureGuess(
                    spare["culture_id"], False, "a spare name of this culture"
                )
            else:
                guess = guess_culture_for_name(world.cultures, sc, character.name)
            if guess.culture_id not in world.cultures:
                continue
            character.culture = CharacterCulture(
                culture_id=guess.culture_id,
                set_by="ai",
                unsure=guess.unsure,
                reason=guess.reason,
            )
            culture = world.cultures.get(guess.culture_id)
            mention = first_mention(character.name, list(self.scene.history))
            story = self._story_label()
            first_used = (
                f"{story}, message {mention.id}" if mention is not None else story
            )
            record_kept_name(world, character.name, culture, first_used)
            cultures_set.append(
                {
                    "name": character.name,
                    "culture_id": guess.culture_id,
                    "unsure": guess.unsure,
                }
            )
        return cultures_set

    async def _snapshot_additions(
        self, world: "LoadedWorld", sc: SceneCultures
    ) -> list[tuple[str, PlayAddition]]:
        if not sc.cultures:
            return []
        checked = self.get_scene_state("additions_checked_id", -1)
        new_messages = [m for m in self.scene.history if m.id > checked]
        if not new_messages:
            return []
        newest_id = max(m.id for m in new_messages)
        narrative = [
            m for m in new_messages if getattr(m, "typ", None) in _NARRATIVE_TYPES
        ][-ADDITIONS_MESSAGE_LIMIT:]
        if not narrative:
            self.set_scene_states(additions_checked_id=newest_id)
            return []

        text = "\n".join(str(m.message) for m in narrative)
        source = f"{self._story_label()}, message {narrative[-1].id}"
        found = await self.find_additions(world, sc, text, source=source)
        # checked even when nothing was found (or the call failed), so the
        # same messages aren't sent again
        self.set_scene_states(additions_checked_id=newest_id)
        if not found:
            return []

        # R2: re-load each culture right before its save, no await between
        saved: list[tuple[str, PlayAddition]] = []
        fresh = world.store.load_cultures()
        for culture_id in dict.fromkeys(culture_id for culture_id, _ in found):
            culture = fresh.get(culture_id)
            if culture is None:
                continue
            existing = {addition.text.lower() for addition in culture.additions}
            new = [
                addition
                for cid, addition in found
                if cid == culture_id and addition.text.lower() not in existing
            ]
            if not new:
                continue
            world.store.save_culture(
                culture.model_copy(update={"additions": culture.additions + new})
            )
            saved.extend((culture_id, addition) for addition in new)
        return saved

    # model calls

    @set_processing
    async def infer_places(
        self, names: list[str], world: "LoadedWorld", sc: SceneCultures
    ) -> list[Place]:
        """One model call placing `names` in the world. A name the model
        skips (not a place) is remembered in scene state and not proposed
        again; a name it doesn't answer, or every name on a failed call, is
        dropped this round."""

        by_id = {place.id: place for place in world.places}
        culture_places = []
        for culture in world.cultures.values():
            culture_places.append(
                {
                    "name": culture.name,
                    "places": [
                        place.name
                        for place in world.places
                        if any(cs.culture_id == culture.id for cs in place.cultures)
                    ],
                }
            )
        current = sc.place.name if sc.place is not None else ""
        example_parent = current or next((place.name for place in world.places), "none")
        example_cultures = [c.name for c in world.cultures.values()][:2]
        if len(example_cultures) == 2:
            example_shares = f"{example_cultures[0]} 70, {example_cultures[1]} 30"
        else:
            example_shares = f"{example_cultures[0]} 100" if example_cultures else ""

        def parse(text: str) -> list[Place]:
            skipped: list[str] = []
            inferred = parse_places_reply(
                text, names, world.places, world.cultures, sc.place, skipped=skipped
            )
            if skipped:
                remembered = list(self.get_scene_state("skipped_places") or [])
                remembered += [name for name in skipped if name not in remembered]
                self.set_scene_states(skipped_places=remembered[-MAX_SKIPPED_PLACES:])
            return inferred

        try:
            response, extracted = await Prompt.request(
                "culture.infer-places",
                self.client,
                "analyze_freeform",
                vars={
                    "scene": self.scene,
                    "max_tokens": self.client.max_token_length,
                    "known_places": [
                        _place_line(place, by_id) for place in world.places
                    ],
                    "cultures": culture_places,
                    "current_place": current or self.scene.world_state.location or "",
                    "names": names,
                    "kinds": list(PLACE_KINDS),
                    "example_parent": example_parent,
                    "example_shares": example_shares,
                    "recent_text": self.recent_text(),
                },
                response_spec=INFER_PLACES_SPEC,
            )
        except GenerationCancelled:
            raise
        except Exception:
            log.exception("culture: infer-places request failed")
            return parse("")

        extracted = extracted or {}
        reply = extracted.get("places")
        return parse(str(reply if reply is not None else response or ""))

    @set_processing
    async def find_additions(
        self,
        world: "LoadedWorld",
        sc: SceneCultures,
        text: str,
        source: str = "",
    ) -> list[tuple[str, PlayAddition]]:
        """One model call for new, lasting facts about the present cultures.
        `[]` on a failed call."""

        try:
            response, extracted = await Prompt.request(
                "culture.find-additions",
                self.client,
                "analyze_freeform",
                vars={
                    "scene": self.scene,
                    "max_tokens": self.client.max_token_length,
                    "cultures": [
                        {
                            "name": culture.name,
                            "customs": list(culture.customs)
                            + [
                                a.text
                                for a in culture.additions
                                if a.section == "customs"
                            ],
                            "food": "; ".join(
                                part
                                for part in [culture.food]
                                + [
                                    a.text
                                    for a in culture.additions
                                    if a.section == "food"
                                ]
                                if part
                            ),
                            "holidays": [h.name for h in culture.holidays]
                            + [
                                a.text
                                for a in culture.additions
                                if a.section == "holidays"
                            ],
                        }
                        for culture in sc.cultures
                    ],
                    "text": text,
                },
                response_spec=FIND_ADDITIONS_SPEC,
            )
        except GenerationCancelled:
            raise
        except Exception:
            log.exception("culture: find-additions request failed")
            return []

        extracted = extracted or {}
        reply = extracted.get("additions")
        return parse_additions_reply(
            str(reply if reply is not None else response or ""), sc.cultures, source
        )
