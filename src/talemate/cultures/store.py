"""Persistence for a shared world's cultures, places and glossary.

A scene's shared world data lives next to its shared-context file, in a
sibling directory named after it (``<name>.json`` -> ``<name>.world/``):

- ``cultures/<culture-id>.json``: one culture plus its language
- ``places.json``
- ``glossary.json``

All writes are atomic: a temp file is written in the same directory, then
``os.replace`` moves it into place, so a crash mid-write never corrupts the
existing file.

``places.json`` and ``glossary.json`` are loaded entry by entry: an entry
that doesn't validate is skipped (with a warning) instead of failing the
whole file, and is written back unchanged on the next save, so a single bad
hand-edit never loses data. A file that can't be read as JSON at all raises
`WorldFileError`, and is never overwritten while it is in that state.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pydantic
import structlog

from .models import Culture, GlossaryEntry, GlossaryFile, Place, PlacesFile
from .places import country_of, describe_mix, effective_mix

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

__all__ = [
    "WorldFileError",
    "WorldStore",
    "atomic_write_json",
    "world_dir_for",
    "world_dir_for_scene",
]

log = structlog.get_logger("talemate.cultures.store")


class WorldFileError(ValueError):
    """Raised for a world file that can't be read as JSON (or has the wrong shape)."""


def world_dir_for(shared_context_path: str | Path) -> Path:
    """Return the world directory for a shared-context file's path.

    ``.../shared-context/world.json`` -> ``.../shared-context/world.world/``
    """

    path = Path(shared_context_path)
    return path.with_name(f"{path.stem}.world")


def world_dir_for_scene(scene: "Scene") -> Path | None:
    """Return the scene's world directory, or `None` without a shared context."""

    if scene.shared_context is None:
        return None
    return world_dir_for(scene.shared_context.filepath)


def atomic_write_json(path: Path, data: dict) -> None:
    """Write `data` as JSON to `path`, atomically.

    Writes to a temp file in the same directory, flushes and fsyncs it, then
    `os.replace`s it into place. On failure the original file (if any) is
    left untouched, and the temp file is removed.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, delete=False, suffix=".tmp"
    )
    try:
        with tmp_file:
            json.dump(data, tmp_file, indent=2)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_file.name, path)
    finally:
        if os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)


class WorldStore:
    """Reads and writes a shared world's cultures, places and glossary."""

    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def cultures_dir(self) -> Path:
        return self.root / "cultures"

    @property
    def places_path(self) -> Path:
        return self.root / "places.json"

    @property
    def glossary_path(self) -> Path:
        return self.root / "glossary.json"

    def load_cultures(self) -> dict[str, Culture]:
        cultures: dict[str, Culture] = {}
        if not self.cultures_dir.exists():
            return cultures

        for file_path in sorted(self.cultures_dir.glob("*.json")):
            try:
                data = json.loads(file_path.read_text())
                culture = Culture.model_validate(data)
            except Exception:
                log.warning(
                    "cultures.load_cultures: skipping unreadable file",
                    path=str(file_path),
                )
                continue
            cultures[culture.id] = culture

        return cultures

    def save_culture(self, c: Culture) -> None:
        atomic_write_json(self.cultures_dir / f"{c.id}.json", c.model_dump(mode="json"))

    def delete_culture(self, culture_id: str) -> None:
        path = self.cultures_dir / f"{culture_id}.json"
        if path.exists():
            path.unlink()

    def _read_entries(
        self, path: Path, key: str, model: type[pydantic.BaseModel]
    ) -> tuple[list, list]:
        """Return `(valid, invalid_raw)` entries of the list `key` in `path`."""

        if not path.exists():
            return [], []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorldFileError(f"{path.name} can't be read: {exc}") from exc

        raw_entries = data.get(key, []) if isinstance(data, dict) else None
        if not isinstance(raw_entries, list):
            raise WorldFileError(f"{path.name} has no '{key}' list")

        valid: list = []
        invalid: list = []
        for index, raw in enumerate(raw_entries):
            try:
                valid.append(model.model_validate(raw))
            except pydantic.ValidationError as exc:
                log.warning(
                    "cultures.store: skipping invalid entry",
                    path=str(path),
                    index=index,
                    error=str(exc),
                )
                invalid.append(raw)
        return valid, invalid

    def _write_entries(
        self,
        path: Path,
        key: str,
        model: type[pydantic.BaseModel],
        file_data: dict,
    ) -> None:
        # Entries that didn't validate on load are kept, unchanged, after
        # the valid ones (re-read now, so this works on a fresh store too).
        _, invalid = self._read_entries(path, key, model)
        file_data[key] = file_data[key] + invalid
        atomic_write_json(path, file_data)

    def load_places(self) -> list[Place]:
        return self._read_entries(self.places_path, "places", Place)[0]

    def save_places(self, places: list[Place]) -> None:
        places_file = PlacesFile(places=places)
        self._write_entries(
            self.places_path, "places", Place, places_file.model_dump(mode="json")
        )

    def load_glossary(self) -> list[GlossaryEntry]:
        return self._read_entries(self.glossary_path, "entries", GlossaryEntry)[0]

    def save_glossary(self, entries: list[GlossaryEntry]) -> None:
        glossary_file = GlossaryFile(entries=entries)
        self._write_entries(
            self.glossary_path,
            "entries",
            GlossaryEntry,
            glossary_file.model_dump(mode="json"),
        )

    def snapshot(self) -> dict:
        cultures = self.load_cultures()
        places = self.load_places()
        glossary = self.load_glossary()

        unreviewed_by_culture: dict[str, int] = {}
        unreviewed_unassigned = 0
        for entry in glossary:
            if entry.status != "unreviewed":
                continue
            if entry.language is None:
                unreviewed_unassigned += 1
            else:
                unreviewed_by_culture[entry.language] = (
                    unreviewed_by_culture.get(entry.language, 0) + 1
                )

        unsure_places = sum(1 for place in places if place.unsure)

        place_dumps = []
        for place in places:
            mix, source = effective_mix(places, place.id)
            country = country_of(places, place.id)
            dump = place.model_dump(mode="json")
            dump["effective"] = {
                "mix": [cs.model_dump(mode="json") for cs in mix],
                "source_id": source.id if source is not None else None,
                "description": describe_mix(places, cultures, place.id),
                "country_id": country.id if country is not None else None,
            }
            place_dumps.append(dump)

        unreviewed_additions_by_culture: dict[str, int] = {}
        for culture in cultures.values():
            count = sum(
                1 for addition in culture.additions if addition.status == "unreviewed"
            )
            if count:
                unreviewed_additions_by_culture[culture.id] = count

        unreviewed_total = (
            sum(unreviewed_by_culture.values())
            + unreviewed_unassigned
            + unsure_places
            + sum(unreviewed_additions_by_culture.values())
        )

        return {
            "cultures": [c.model_dump(mode="json") for c in cultures.values()],
            "places": place_dumps,
            "glossary": [g.model_dump(mode="json") for g in glossary],
            "counts": {
                "unreviewed_total": unreviewed_total,
                "unreviewed_by_culture": unreviewed_by_culture,
                "unreviewed_unassigned": unreviewed_unassigned,
                "unsure_places": unsure_places,
                "unreviewed_additions_by_culture": unreviewed_additions_by_culture,
            },
        }
