"""Story data for the Cultures-in-the-story feature (plan 3 / task 2).

Turns the shared world's glossary, characters and places into the small,
scene-scoped shapes the frontend needs to show name chips, character
chips and place chips: which glossary names actually turn up in the
current scene, what's known about each scene character's culture, and
each place's effective culture mix. Pure, no model calls, no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Literal

from pydantic import BaseModel, Field

from .models import Culture, GlossaryEntry, Place
from .places import effective_mix
from .words import clean_name

if TYPE_CHECKING:
    from talemate.character import Character

__all__ = [
    "NameInfo",
    "CharacterInfo",
    "PlaceInfo",
    "scene_name_keys",
    "build_story",
]

# At most this many names are returned by `build_story`, so a glossary-heavy
# world can't bloat every story push.
MAX_NAMES = 500


class NameInfo(BaseModel):
    """A glossary name (person, place or thing) that turns up in the scene."""

    id: str
    text: str
    kind: str
    status: str
    culture_id: str | None = None
    culture_name: str | None = None
    language_name: str | None = None
    color: str | None = None
    writable: bool = True
    meaning: str = ""
    true_name: str = ""
    renderings: list[dict] = Field(default_factory=list)
    origin_by: str
    generator_name: str | None = None
    doesnt_fit: bool = False
    character_name: str | None = None
    place_id: str | None = None


class CharacterInfo(BaseModel):
    """What's known about a scene character's culture."""

    name: str
    culture_id: str | None = None
    culture_name: str | None = None
    color: str | None = None
    set_by: Literal["ai", "owner"] | None = None
    unsure: bool = False
    reason: str = ""


class PlaceInfo(BaseModel):
    """A place's effective culture mix, for the places panel."""

    id: str
    name: str
    kind: str
    own: bool
    source_name: str | None = None
    mix: list[dict] = Field(default_factory=list)
    set_by: str
    unsure: bool


def scene_name_keys(names: Iterable[str]) -> set[str]:
    """Return `clean_name(n).lower()` for each non-empty `name` in `names`."""

    keys: set[str] = set()
    for name in names:
        if not name:
            continue
        cleaned = clean_name(name).lower()
        if cleaned:
            keys.add(cleaned)
    return keys


def _culture_name(cultures: dict[str, Culture], culture_id: str | None) -> str | None:
    if culture_id is None:
        return None
    culture = cultures.get(culture_id)
    return culture.name if culture is not None else culture_id


def _generator_name(
    cultures: dict[str, Culture], culture_id: str | None, generator_id: str | None
) -> str | None:
    if culture_id is None or generator_id is None:
        return None
    culture = cultures.get(culture_id)
    if culture is None:
        return None
    for generator in culture.language.generators:
        if generator.id == generator_id:
            return generator.name
    return None


def _name_info(entry: GlossaryEntry, cultures: dict[str, Culture]) -> NameInfo:
    culture = cultures.get(entry.language) if entry.language is not None else None

    renderings = [
        {
            "culture_id": culture_id,
            "culture_name": _culture_name(cultures, culture_id),
            "text": text,
        }
        for culture_id, text in entry.renderings.items()
    ]

    return NameInfo(
        id=entry.id,
        text=entry.text,
        kind=entry.kind,
        status=entry.status,
        culture_id=entry.language,
        culture_name=_culture_name(cultures, entry.language),
        language_name=culture.language.name if culture is not None else None,
        color=culture.color if culture is not None else None,
        writable=culture.language.writable if culture is not None else True,
        meaning=entry.meaning,
        true_name=entry.true_name,
        renderings=renderings,
        origin_by=entry.origin.by,
        generator_name=_generator_name(
            cultures, entry.language, entry.origin.generator_id
        ),
        doesnt_fit=entry.doesnt_fit,
        character_name=entry.character_name,
        place_id=entry.place_id,
    )


def _matches_scene(entry: GlossaryEntry, scene_names: set[str]) -> bool:
    candidates = [entry.text, *entry.renderings.values()]
    if entry.character_name:
        candidates.append(entry.character_name)
    return any(clean_name(candidate).lower() in scene_names for candidate in candidates)


def _character_info(
    character: "Character", cultures: dict[str, Culture]
) -> CharacterInfo:
    culture_data = character.culture
    if culture_data is None:
        return CharacterInfo(name=character.name)

    culture_id = culture_data.culture_id
    culture = cultures.get(culture_id) if culture_id is not None else None
    return CharacterInfo(
        name=character.name,
        culture_id=culture_id,
        culture_name=culture.name if culture is not None else None,
        color=culture.color if culture is not None else None,
        set_by=culture_data.set_by,
        unsure=culture_data.unsure,
        reason=culture_data.reason,
    )


def _place_info(
    place: Place, places: list[Place], cultures: dict[str, Culture]
) -> PlaceInfo:
    mix, source = effective_mix(places, place.id)
    own = source is not None and source.id == place.id

    mix_dumps = [
        {
            "culture_id": cs.culture_id,
            "culture_name": _culture_name(cultures, cs.culture_id),
            "color": cultures[cs.culture_id].color
            if cs.culture_id in cultures
            else None,
            "share": cs.share,
        }
        for cs in sorted(mix, key=lambda cs: -cs.share)
    ]

    return PlaceInfo(
        id=place.id,
        name=place.name,
        kind=place.kind,
        own=own,
        source_name=source.name if (source is not None and not own) else None,
        mix=mix_dumps,
        set_by=place.set_by,
        unsure=place.unsure,
    )


def build_story(
    *,
    cultures: dict[str, Culture],
    places: list[Place],
    glossary: list[GlossaryEntry],
    characters: list["Character"],
    scene_names: set[str],
) -> dict:
    """Return the scene's names, characters and places, each
    `model_dump(mode="json")`-ed."""

    names = [
        _name_info(entry, cultures)
        for entry in glossary
        if entry.kind in ("person", "place", "thing")
        and _matches_scene(entry, scene_names)
    ][:MAX_NAMES]

    character_infos = sorted(
        (_character_info(character, cultures) for character in characters),
        key=lambda info: info.name,
    )

    place_infos = [_place_info(place, places, cultures) for place in places]

    return {
        "names": [n.model_dump(mode="json") for n in names],
        "characters": [c.model_dump(mode="json") for c in character_infos],
        "places": [p.model_dump(mode="json") for p in place_infos],
    }
