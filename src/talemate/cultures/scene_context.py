"""Working out which place and cultures a scene is in.

`match_place` looks for a known place in the scene's free-text
`world_state.location` (or, failing that, in a snapshot's recent place
names), and `resolve_scene_cultures` turns that into the culture mix
and the list of present cultures the Culture agent uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import Culture, CultureShare, Place
from .places import describe_mix, effective_mix

if TYPE_CHECKING:
    from talemate.character import Character

__all__ = [
    "SceneCultures",
    "match_place",
    "resolve_scene_cultures",
]


@dataclass
class SceneCultures:
    place: Place | None
    mix: list[CultureShare]
    mix_source: Place | None
    description: str
    cultures: list[Culture] = field(default_factory=list)
    ancestor_ids: list[str] = field(default_factory=list)
    # one culture id per scene character with a (known) culture, in order
    character_culture_ids: list[str] = field(default_factory=list)


def _whole_word_in(candidate: str, text: str) -> bool:
    pattern = re.compile(r"\b" + re.escape(candidate) + r"\b", re.IGNORECASE)
    return pattern.search(text) is not None


def _without_leading_the(name: str) -> str | None:
    if name.startswith("The "):
        return name[4:]
    return None


def _ancestor_depth(by_id: dict[str, Place], place_id: str) -> int:
    """Return the number of ancestors of `place_id`."""

    depth = 0
    visited: set[str] = {place_id}
    place = by_id.get(place_id)
    current_id = place.parent_id if place is not None else None
    while current_id is not None and current_id not in visited:
        depth += 1
        visited.add(current_id)
        place = by_id.get(current_id)
        current_id = place.parent_id if place is not None else None
    return depth


def _ancestor_ids(by_id: dict[str, Place], place_id: str) -> list[str]:
    """Return `place_id` followed by every ancestor up to the root, in order."""

    ids: list[str] = [place_id]
    visited: set[str] = {place_id}
    place = by_id.get(place_id)
    current_id = place.parent_id if place is not None else None
    while current_id is not None and current_id not in visited:
        ids.append(current_id)
        visited.add(current_id)
        place = by_id.get(current_id)
        current_id = place.parent_id if place is not None else None
    return ids


def match_place(
    places: list[Place],
    location: str | None,
    snapshot_places: list[str],
) -> Place | None:
    """Return the deepest place matching `location`, then `snapshot_places`."""

    by_id = {place.id: place for place in places}

    def deepest(matches: list[Place]) -> Place | None:
        if not matches:
            return None
        return max(matches, key=lambda place: _ancestor_depth(by_id, place.id))

    if location:
        matches = []
        for place in places:
            candidates = [place.name]
            without_the = _without_leading_the(place.name)
            if without_the is not None:
                candidates.append(without_the)
            if any(_whole_word_in(candidate, location) for candidate in candidates):
                matches.append(place)
        found = deepest(matches)
        if found is not None:
            return found

    if snapshot_places:
        lowered = {s.lower() for s in snapshot_places}
        matches = [place for place in places if place.name.lower() in lowered]
        found = deepest(matches)
        if found is not None:
            return found

    return None


def resolve_scene_cultures(
    cultures: dict[str, Culture],
    places: list[Place],
    location: str | None,
    snapshot_places: list[str],
    characters: list["Character"],
    fallback_place_id: str | None = None,
) -> SceneCultures:
    """Resolve the place, culture mix and present cultures for a scene."""

    place = match_place(places, location, snapshot_places)
    if place is None and fallback_place_id is not None:
        place = next((p for p in places if p.id == fallback_place_id), None)

    if place is not None:
        mix, mix_source = effective_mix(places, place.id)
        description = describe_mix(places, cultures, place.id)
        by_id = {p.id: p for p in places}
        ancestor_ids = _ancestor_ids(by_id, place.id)
    else:
        mix, mix_source = [], None
        description = ""
        ancestor_ids = []

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for culture_share in sorted(mix, key=lambda cs: -cs.share):
        if (
            culture_share.culture_id in cultures
            and culture_share.culture_id not in seen
        ):
            ordered_ids.append(culture_share.culture_id)
            seen.add(culture_share.culture_id)

    character_culture_ids: list[str] = []
    for character in characters:
        character_culture = getattr(character, "culture", None)
        culture_id = (
            getattr(character_culture, "culture_id", None)
            if character_culture is not None
            else None
        )
        if not culture_id or culture_id not in cultures:
            continue
        character_culture_ids.append(culture_id)
        if culture_id not in seen:
            ordered_ids.append(culture_id)
            seen.add(culture_id)

    return SceneCultures(
        place=place,
        mix=list(mix),
        mix_source=mix_source,
        description=description,
        cultures=[cultures[culture_id] for culture_id in ordered_ids],
        ancestor_ids=ancestor_ids,
        character_culture_ids=character_culture_ids,
    )
