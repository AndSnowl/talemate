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
- A file place matching an existing place's name (case-insensitively): if
  this culture already has a share there, a re-import never moves it —
  the file's value is ignored (a mismatch is a preview warning, not a
  change). If it has no share there yet, `places.set_share` gives it the
  file's share exactly and scales the place's other shares to fill the
  remainder; if no other culture has a share there, it becomes 100%
  regardless of the file's value, since shares must sum to 100 (also a
  preview warning when that value isn't already 100). An unmatched place
  is created new, under its matched parent (by name) or as a root, and
  given this culture's share the same way (also sole, so also 100%). New
  places are all created before any parent is resolved, so a child may be
  listed before its parent in the file.
- Nothing already in Talemate — a glossary entry, a place, a play
  addition — is ever deleted by an import.
- The preview lists what a re-import would overwrite: the core sections
  whose content differs from Talemate's copy (`replaced_sections`), the
  existing places whose share for this culture changes (`share_changes`),
  and Talemate's play additions whose text the file now also carries in
  the matching section (`additions_in_file`; never dropped automatically).
- A generator whose patterns or reject rules don't parse (or nest too
  deeply), or a duplicate generator id, makes the whole file invalid
  (`ImportFormatError`), for both `preview_import` and `apply_import` — a
  file like that must not be importable silently.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .generator import (
    GeneratorError,
    name_fits,
    pattern_letters,
    roll,
    validate_language,
)
from .models import (
    Culture,
    GeneratorDef,
    GlossaryEntry,
    GlossaryOrigin,
    Language,
    Place,
    new_id,
    slugify,
)
from .places import reparent, set_share
from .store import WorldStore

__all__ = [
    "ImportFormatError",
    "CultureFileGlossary",
    "CultureFilePlace",
    "ForeignRendering",
    "CultureFile",
    "ImportPreview",
    "lint_culture_file",
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
    # Core sections whose content in Talemate differs from the file, which
    # the import will replace (keys of `REPLACEABLE_SECTIONS`, in order).
    replaced_sections: list[str] = Field(default_factory=list)
    # Existing places where this culture's share will change, e.g.
    # "Dhunmouth: Taelrik 40% → 55%".
    share_changes: list[str] = Field(default_factory=list)
    # Texts of Talemate's play additions that the file now also has in the
    # matching core section (candidates to drop after importing).
    additions_in_file: list[str] = Field(default_factory=list)


# Core sections a re-import replaces, as (name, which model holds it).
REPLACEABLE_SECTIONS: tuple[tuple[str, str], ...] = (
    ("description", "culture"),
    ("customs", "culture"),
    ("food", "culture"),
    ("holidays", "culture"),
    ("color", "culture"),
    ("sound", "language"),
    ("categories", "language"),
    ("syllable_notes", "language"),
    ("generators", "language"),
    ("dictionary", "language"),
    ("phrases", "language"),
    ("grammar", "language"),
)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _parse_and_resolve(raw: str) -> tuple[CultureFile, str, dict]:
    """Parse `raw` into a `CultureFile` and resolve its sanitised culture id.

    Also returns the raw parsed JSON dict (before the pydantic models drop
    unknown keys), so callers that want `lint_culture_file`'s unknown-field
    check don't have to parse `raw` a second time.
    """

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

    try:
        validate_language(file.culture.language)
    except GeneratorError as exc:
        raise ImportFormatError(f"invalid culture file: {exc}") from exc

    return file, culture_id, data


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


def _place_share_update(
    current_share: int | None,
    has_other_cultures: bool,
    culture_name: str,
    place_name: str,
    file_share: int,
) -> tuple[bool, int, str | None]:
    """Decide what an import does to one culture's share at a place.

    `current_share` is this culture's existing share there (`None` if it
    has none yet there); `has_other_cultures` says whether any other
    culture already has a share there. Returns `(apply, resulting_share,
    warning)`:

    - `apply`: whether to call `set_share` with `file_share` at all. A
      culture that already has a share here keeps it exactly — a
      re-import never moves an existing share, however much the file's
      value differs.
    - `resulting_share`: the share this culture ends up with once applied
      — 100, not `file_share`, when it is the only culture at the place
      (shares must sum to 100). Used for the preview's change text; it is
      meaningless when `apply` is `False`.
    - `warning`: a preview note, or `None`.
    """

    if current_share is not None:
        warning = None
        if file_share != current_share:
            warning = (
                f"{place_name}: keeping {culture_name} at {current_share}% "
                f"(file says {file_share}%) — adjust it in Places & regions"
            )
        return False, current_share, warning

    resulting_share = file_share if has_other_cultures else 100
    warning = None
    if not has_other_cultures and file_share != 100:
        warning = (
            f"{place_name}: {culture_name} is the only culture here, so it "
            f"will be 100% (file says {file_share}%)"
        )
    return True, resulting_share, warning


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _replaced_sections(existing: Culture, incoming: Culture) -> list[str]:
    replaced = []
    for section, owner in REPLACEABLE_SECTIONS:
        old = existing if owner == "culture" else existing.language
        new = incoming if owner == "culture" else incoming.language
        old_value = old.model_dump(mode="json")[section]
        new_value = new.model_dump(mode="json")[section]
        if old_value != new_value:
            replaced.append(section)
    return replaced


def _additions_in_file(existing: Culture, incoming: Culture) -> list[str]:
    """Texts of `existing`'s additions that `incoming`'s core sections contain."""

    section_texts = {
        "customs": incoming.customs,
        "food": [incoming.food],
        "holidays": [
            text
            for holiday in incoming.holidays
            for text in (holiday.name, holiday.description)
        ],
    }
    found = []
    for addition in existing.additions:
        needle = _normalize_text(addition.text)
        if not needle:
            continue
        haystack = section_texts.get(addition.section, [])
        if any(needle in _normalize_text(text) for text in haystack):
            found.append(addition.text)
    return found


def _glossary_differs(existing: GlossaryEntry, file_entry: CultureFileGlossary) -> bool:
    return (
        existing.kind != file_entry.kind
        or existing.meaning != file_entry.meaning
        or existing.true_name != file_entry.true_name
    )


# --------------------------------------------------------------------------
# Lint: warnings about likely mistakes, never errors
# --------------------------------------------------------------------------


def _unknown_keys(obj: object, allowed: set[str], path: str) -> list[str]:
    if not isinstance(obj, dict):
        return []
    return [
        f"Unknown field '{path}.{key}' is ignored (typo?)"
        for key in obj
        if key not in allowed
    ]


def _unknown_field_warnings(raw: dict) -> list[str]:
    """Warn about keys the models silently drop (`extra=\"ignore\"`).

    Checked at the few spots a hand-edited or AI-generated file is most
    likely to carry a typo'd field: the culture itself, its language, each
    generator, each glossary entry and each place. Anything else (holidays,
    dictionary entries, phrases, additions, foreign renderings, …) isn't
    checked — YAGNI until a real mistake turns up there.
    """
    warnings: list[str] = []

    culture = raw.get("culture")
    if isinstance(culture, dict):
        warnings.extend(
            _unknown_keys(culture, set(Culture.model_fields.keys()), "culture")
        )

        language = culture.get("language")
        if isinstance(language, dict):
            warnings.extend(
                _unknown_keys(language, set(Language.model_fields.keys()), "language")
            )

            generators = language.get("generators")
            if isinstance(generators, list):
                generator_allowed = set(GeneratorDef.model_fields.keys())
                for index, gen in enumerate(generators):
                    warnings.extend(
                        _unknown_keys(
                            gen, generator_allowed, f"language.generators[{index}]"
                        )
                    )

    glossary = raw.get("glossary")
    if isinstance(glossary, list):
        glossary_allowed = set(CultureFileGlossary.model_fields.keys())
        for index, entry in enumerate(glossary):
            warnings.extend(
                _unknown_keys(entry, glossary_allowed, f"glossary[{index}]")
            )

    places = raw.get("places")
    if isinstance(places, list):
        places_allowed = set(CultureFilePlace.model_fields.keys())
        for index, place in enumerate(places):
            warnings.extend(_unknown_keys(place, places_allowed, f"places[{index}]"))

    return warnings


def lint_culture_file(raw: dict, file: CultureFile) -> list[str]:
    """Warnings about likely mistakes in a culture file.

    None of these are errors: a file that was valid yesterday must still
    import, and `apply_import` never consults this list. `raw` is the
    parsed-but-unvalidated JSON (needed only for the unknown-field check,
    since the pydantic models quietly drop keys they don't define);
    `file` is the already-validated model.
    """
    warnings: list[str] = []
    language = file.culture.language

    # An uppercase letter in a pattern that isn't one of the language's
    # own category keys is still legal (the parser treats it as literal
    # text), but it's the single most common typo in a hand-written
    # pattern, so flag every one of them, plainly.
    category_keys = set(language.categories.keys())
    for gen in language.generators:
        for pattern in gen.patterns:
            for letter in sorted(pattern_letters(pattern) - category_keys):
                warnings.append(
                    f"Generator '{gen.name}': '{letter}' in pattern "
                    f"'{pattern}' is not a category, so it is written literally"
                )

    warnings.extend(_unknown_field_warnings(raw))

    if language.level == "description" and language.generators:
        warnings.append(
            f"Language '{language.name}' is description-only but has "
            "generators; they will never be used"
        )

    # A name-shaped glossary entry (person/place) that the language's own
    # generators wouldn't have produced — most often because a generator
    # was written, then the glossary entry was typed in by hand to a
    # different shape. "thing"/"word" entries are ordinary vocabulary, not
    # generated names, so they're never checked here.
    if language.generators:
        for entry in file.glossary:
            if entry.kind not in ("person", "place"):
                continue
            if not name_fits(language, entry.text):
                warnings.append(
                    f"Glossary '{entry.text}' in {language.name} doesn't "
                    "fit its own generators"
                )

    return warnings


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------


def preview_import(store: WorldStore, raw: str) -> ImportPreview:
    file, culture_id, data = _parse_and_resolve(raw)

    cultures = store.load_cultures()
    is_update = culture_id in cultures

    name_clash = next(
        (
            other.id
            for other in cultures.values()
            if other.id != culture_id
            and other.name.strip().lower() == file.culture.name.strip().lower()
        ),
        None,
    )

    existing_culture = cultures.get(culture_id)
    replaced_sections: list[str] = []
    additions_in_file: list[str] = []
    if existing_culture is not None:
        replaced_sections = _replaced_sections(existing_culture, file.culture)
        additions_in_file = _additions_in_file(existing_culture, file.culture)

    counts = {
        "words": len(file.culture.language.dictionary),
        "phrases": len(file.culture.language.phrases),
        "generators": len(file.culture.language.generators),
        "glossary": len(file.glossary),
        "places": len(file.places),
    }

    warnings: list[str] = list(lint_culture_file(data, file))

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
    share_changes: list[str] = []
    for file_place in file.places:
        match = _match_place(places, file_place.name)
        if match is None:
            places_new.append(file_place.name)
            _, _, warning = _place_share_update(
                None, False, file.culture.name, file_place.name, file_place.share
            )
            if warning is not None:
                warnings.append(warning)
            continue
        places_existing.append(file_place.name)
        current_share = next(
            (cs.share for cs in match.cultures if cs.culture_id == culture_id), None
        )
        has_others = any(cs.culture_id != culture_id for cs in match.cultures)
        apply, resulting_share, warning = _place_share_update(
            current_share, has_others, file.culture.name, match.name, file_place.share
        )
        if warning is not None:
            warnings.append(warning)
        if apply:
            share_changes.append(
                f"{match.name}: {file.culture.name} 0% → {resulting_share}%"
            )

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
        replaced_sections=replaced_sections,
        share_changes=share_changes,
        additions_in_file=additions_in_file,
    )


# --------------------------------------------------------------------------
# Apply
# --------------------------------------------------------------------------


def apply_import(store: WorldStore, raw: str, today: str) -> Culture:
    file, culture_id, _data = _parse_and_resolve(raw)

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
    # Two passes, so a new place's parent may be another new place listed
    # later in the file: create every new place first (parent unresolved),
    # then resolve parents by name once all of them exist.
    new_place_ids: list[tuple[CultureFilePlace, str]] = []
    for file_place in file.places:
        match = _match_place(places, file_place.name)
        if match is not None:
            current_share = next(
                (cs.share for cs in match.cultures if cs.culture_id == culture_id),
                None,
            )
            has_others = any(cs.culture_id != culture_id for cs in match.cultures)
            apply, _, _ = _place_share_update(
                current_share,
                has_others,
                file.culture.name,
                match.name,
                file_place.share,
            )
            if apply:
                places = set_share(places, match.id, culture_id, file_place.share)
            continue

        new_place = Place(
            id=new_id(),
            name=file_place.name,
            kind=file_place.kind,
            parent_id=None,
            set_by="owner",
        )
        places = places + [new_place]
        places = set_share(places, new_place.id, culture_id, file_place.share)
        new_place_ids.append((file_place, new_place.id))

    for file_place, place_id in new_place_ids:
        if file_place.parent is None:
            continue
        parent = _match_place(places, file_place.parent)
        if parent is not None:
            places = reparent(places, place_id, parent.id)

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
    path.write_text(
        json.dumps(CultureFile.model_json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )
