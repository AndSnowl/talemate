"""Culture file format: import preview, import and export.

One JSON file per culture (``<culture-id>.culture.json``) carries a
`Culture` (with its `Language`), optional glossary entries and places it
lives in, and optional renderings of other cultures' names. This is the
format the culture-design skill (Task 7) writes and Talemate's websocket
plugin (Task 6) imports through `preview_import` / `apply_import`, and
exports through `export_culture`. See spec section 9.2.

Re-import rules (spec 9.2, and the controller's rulings for this task):

- The culture id is `culture.id` or, if that sanitises to empty,
  `slugify(culture.name)`. Either way the id is passed through `slugify`
  before it is ever used as a filename, since it comes from an untrusted
  file.
- Re-importing an existing id replaces every field of the culture and its
  language except `additions`: Talemate's own additions are kept, and any
  addition in the file whose `id` isn't already in Talemate's list is
  appended.
- A glossary entry from the file is matched to an existing entry by
  `text`, case-insensitively, within the same culture. No match: it is
  added with `origin.by="import"` and `status="reviewed"`. A match that
  Talemate has reviewed or edited keeps Talemate's copy (and is reported
  as a conflict if any field differs); otherwise it is updated from the
  file.
- A file glossary entry that matches an *unassigned* entry (case
  insensitively) claims it: the entry moves to this culture, status
  becomes `"unreviewed"`, and its meaning is filled in.
- A foreign rendering sets `renderings[this culture id]` on whatever
  glossary entry (in any culture) has that name; a name that isn't found
  is reported as a warning instead.
- A file place matching an existing place's name (case-insensitively) has
  this culture's share merged onto it with `places.set_share`, which keeps
  the file's share exactly and scales the place's other shares to fill
  the remainder. An unmatched place is created new, under its matched
  parent (by name) or as a root, and given this culture's share the same
  way.
- Nothing already in Talemate — a glossary entry, a place, a play
  addition — is ever deleted by an import.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .generator import roll
from .models import (
    Culture,
    GlossaryEntry,
    GlossaryOrigin,
    Place,
    new_id,
    slugify,
)
from .places import set_share
from .store import WorldStore

__all__ = [
    "ImportFormatError",
    "CultureFileGlossary",
    "CultureFilePlace",
    "ForeignRendering",
    "CultureFile",
    "ImportPreview",
    "preview_import",
    "apply_import",
    "export_culture",
    "write_schema",
]


class ImportFormatError(ValueError):
    """Raised for a culture file that isn't valid JSON, or doesn't fit the schema."""


class CultureFileGlossary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    kind: Literal["person", "place", "thing", "word"]
    meaning: str = ""
    true_name: str = ""
    renderings: dict[str, str] = Field(default_factory=dict)


class CultureFilePlace(BaseModel):
    """A place where this culture lives. `parent` is matched by name."""

    model_config = ConfigDict(extra="ignore")

    name: str
    kind: Literal[
        "country",
        "region",
        "city",
        "town",
        "village",
        "building",
        "poi",
        "terrain",
    ]
    parent: str | None = None
    share: int = 100


class ForeignRendering(BaseModel):
    """This culture's rendering of a name that belongs to another culture."""

    model_config = ConfigDict(extra="ignore")

    name: str
    rendering: str


class CultureFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format_version: Literal[1] = 1
    culture: Culture
    glossary: list[CultureFileGlossary] = Field(default_factory=list)
    places: list[CultureFilePlace] = Field(default_factory=list)
    foreign_renderings: list[ForeignRendering] = Field(default_factory=list)


class ImportPreview(BaseModel):
    culture_id: str
    culture_name: str
    is_update: bool
    counts: dict[str, int]
    claimed_unassigned: list[str]
    places_existing: list[str]
    places_new: list[str]
    conflicts: list[str]
    name_clash: str | None
    warnings: list[str]


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _parse_and_resolve(raw: str) -> tuple[CultureFile, str]:
    """Parse `raw` into a `CultureFile` and resolve its sanitised culture id."""

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImportFormatError(
            f"invalid culture file: not valid JSON ({exc})"
        ) from exc

    try:
        file = CultureFile.model_validate(data)
    except ValidationError as exc:
        raise ImportFormatError(f"invalid culture file: {exc}") from exc

    culture_id = slugify(file.culture.id) or slugify(file.culture.name)
    if not culture_id:
        raise ImportFormatError(
            "invalid culture file: culture has no usable id or name"
        )

    return file, culture_id


# --------------------------------------------------------------------------
# Matching helpers
# --------------------------------------------------------------------------


def _match_text(
    entries: list[GlossaryEntry], text: str, language: str | None
) -> GlossaryEntry | None:
    lowered = text.lower()
    for entry in entries:
        if entry.language == language and entry.text.lower() == lowered:
            return entry
    return None


def _match_any(entries: list[GlossaryEntry], text: str) -> GlossaryEntry | None:
    lowered = text.lower()
    for entry in entries:
        if entry.text.lower() == lowered:
            return entry
    return None


def _match_place(places: list[Place], name: str) -> Place | None:
    lowered = name.lower()
    for place in places:
        if place.name.lower() == lowered:
            return place
    return None


def _glossary_differs(existing: GlossaryEntry, file_entry: CultureFileGlossary) -> bool:
    return (
        existing.kind != file_entry.kind
        or existing.meaning != file_entry.meaning
        or existing.true_name != file_entry.true_name
    )


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------


def preview_import(store: WorldStore, raw: str) -> ImportPreview:
    file, culture_id = _parse_and_resolve(raw)

    cultures = store.load_cultures()
    is_update = culture_id in cultures

    name_clash = next(
        (
            other.id
            for other in cultures.values()
            if other.id != culture_id and other.name == file.culture.name
        ),
        None,
    )

    counts = {
        "words": len(file.culture.language.dictionary),
        "phrases": len(file.culture.language.phrases),
        "generators": len(file.culture.language.generators),
        "glossary": len(file.glossary),
        "places": len(file.places),
    }

    glossary = store.load_glossary()
    claimed_unassigned: list[str] = []
    conflicts: list[str] = []
    for file_entry in file.glossary:
        existing = _match_text(glossary, file_entry.text, culture_id)
        if existing is not None:
            if (
                existing.status == "reviewed" or existing.edited_by_owner
            ) and _glossary_differs(existing, file_entry):
                conflicts.append(existing.text)
            continue

        unassigned = _match_text(glossary, file_entry.text, None)
        if unassigned is not None:
            claimed_unassigned.append(unassigned.text)

    places = store.load_places()
    places_existing: list[str] = []
    places_new: list[str] = []
    for file_place in file.places:
        if _match_place(places, file_place.name) is not None:
            places_existing.append(file_place.name)
        else:
            places_new.append(file_place.name)

    warnings: list[str] = []
    for gen in file.culture.language.generators:
        rolled = roll(file.culture.language, gen.id, count=5)
        if not rolled:
            warnings.append(f"Generator '{gen.name}' produced no names")

    for fr in file.foreign_renderings:
        if _match_any(glossary, fr.name) is None:
            warnings.append(f"No glossary entry found for '{fr.name}'")

    return ImportPreview(
        culture_id=culture_id,
        culture_name=file.culture.name,
        is_update=is_update,
        counts=counts,
        claimed_unassigned=claimed_unassigned,
        places_existing=places_existing,
        places_new=places_new,
        conflicts=conflicts,
        name_clash=name_clash,
        warnings=warnings,
    )


# --------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------


def apply_import(store: WorldStore, raw: str, today: str) -> Culture:
    file, culture_id = _parse_and_resolve(raw)

    cultures = store.load_cultures()
    existing_culture = cultures.get(culture_id)

    additions = list(file.culture.additions)
    if existing_culture is not None:
        existing_ids = {addition.id for addition in existing_culture.additions}
        additions = list(existing_culture.additions) + [
            addition
            for addition in file.culture.additions
            if addition.id not in existing_ids
        ]

    culture = file.culture.model_copy(
        update={
            "id": culture_id,
            "additions": additions,
            "source_file": f"{culture_id}.culture.json",
            "imported_at": today,
        }
    )

    glossary = store.load_glossary()
    for file_entry in file.glossary:
        existing = _match_text(glossary, file_entry.text, culture_id)
        if existing is not None:
            if existing.status == "reviewed" or existing.edited_by_owner:
                continue
            updated = existing.model_copy(
                update={
                    "kind": file_entry.kind,
                    "meaning": file_entry.meaning,
                    "true_name": file_entry.true_name,
                    "renderings": {**existing.renderings, **file_entry.renderings},
                }
            )
            glossary = [updated if e is existing else e for e in glossary]
            continue

        unassigned = _match_text(glossary, file_entry.text, None)
        if unassigned is not None:
            claimed = unassigned.model_copy(
                update={
                    "language": culture_id,
                    "status": "unreviewed",
                    "meaning": file_entry.meaning or unassigned.meaning,
                }
            )
            glossary = [claimed if e is unassigned else e for e in glossary]
            continue

        glossary.append(
            GlossaryEntry(
                id=new_id(),
                text=file_entry.text,
                language=culture_id,
                kind=file_entry.kind,
                meaning=file_entry.meaning,
                true_name=file_entry.true_name,
                renderings=dict(file_entry.renderings),
                origin=GlossaryOrigin(by="import"),
                status="reviewed",
            )
        )

    for fr in file.foreign_renderings:
        target = _match_any(glossary, fr.name)
        if target is not None:
            rendered = target.model_copy(
                update={"renderings": {**target.renderings, culture_id: fr.rendering}}
            )
            glossary = [rendered if e is target else e for e in glossary]

    places = store.load_places()
    for file_place in file.places:
        match = _match_place(places, file_place.name)
        if match is not None:
            places = set_share(places, match.id, culture_id, file_place.share)
            continue

        parent_id = None
        if file_place.parent is not None:
            parent = _match_place(places, file_place.parent)
            parent_id = parent.id if parent is not None else None

        new_place = Place(
            id=new_id(),
            name=file_place.name,
            kind=file_place.kind,
            parent_id=parent_id,
            set_by="owner",
        )
        places = places + [new_place]
        places = set_share(places, new_place.id, culture_id, file_place.share)

    store.save_culture(culture)
    store.save_glossary(glossary)
    store.save_places(places)

    return culture


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


def export_culture(store: WorldStore, culture_id: str) -> str:
    cultures = store.load_cultures()
    culture = cultures.get(culture_id)
    if culture is None:
        raise ValueError(f"unknown culture: {culture_id}")

    glossary = store.load_glossary()
    file_glossary = [
        CultureFileGlossary(
            text=entry.text,
            kind=entry.kind,
            meaning=entry.meaning,
            true_name=entry.true_name,
            renderings=dict(entry.renderings),
        )
        for entry in glossary
        if entry.language == culture_id
    ]

    places = store.load_places()
    places_by_id = {place.id: place for place in places}
    file_places = []
    for place in places:
        share = next(
            (cs.share for cs in place.cultures if cs.culture_id == culture_id), None
        )
        if share is None:
            continue
        parent = places_by_id.get(place.parent_id) if place.parent_id else None
        file_places.append(
            CultureFilePlace(
                name=place.name,
                kind=place.kind,
                parent=parent.name if parent is not None else None,
                share=share,
            )
        )

    foreign_renderings = [
        ForeignRendering(name=entry.text, rendering=entry.renderings[culture_id])
        for entry in glossary
        if entry.language != culture_id and culture_id in entry.renderings
    ]

    file = CultureFile(
        culture=culture,
        glossary=file_glossary,
        places=file_places,
        foreign_renderings=foreign_renderings,
    )
    return json.dumps(file.model_dump(mode="json"), indent=2)


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------


def write_schema(path: Path) -> None:
    path.write_text(json.dumps(CultureFile.model_json_schema(), indent=2) + "\n")
