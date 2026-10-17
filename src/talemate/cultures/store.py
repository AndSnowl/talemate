"""Persistence for a shared world's cultures, places and glossary.

A scene's shared world data lives next to its shared-context file, in a
sibling directory named after it (``<name>.json`` -> ``<name>.world/``):

- ``cultures/<culture-id>.json``: one culture plus its language
- ``places.json``
- ``glossary.json``

All writes are atomic: a temp file is written in the same directory, then
``os.replace`` moves it into place, so a crash mid-write never corrupts the
existing file.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from .models import Culture, GlossaryEntry, GlossaryFile, Place, PlacesFile

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

__all__ = [
    "WorldStore",
    "atomic_write_json",
    "world_dir_for",
    "world_dir_for_scene",
]

log = structlog.get_logger("talemate.cultures.store")


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

    def load_places(self) -> list[Place]:
        if not self.places_path.exists():
            return []
        data = json.loads(self.places_path.read_text())
        return PlacesFile.model_validate(data).places

    def save_places(self, places: list[Place]) -> None:
        places_file = PlacesFile(places=places)
        atomic_write_json(self.places_path, places_file.model_dump(mode="json"))

    def load_glossary(self) -> list[GlossaryEntry]:
        if not self.glossary_path.exists():
            return []
        data = json.loads(self.glossary_path.read_text())
        return GlossaryFile.model_validate(data).entries

    def save_glossary(self, entries: list[GlossaryEntry]) -> None:
        glossary_file = GlossaryFile(entries=entries)
        atomic_write_json(self.glossary_path, glossary_file.model_dump(mode="json"))

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
            "places": [p.model_dump(mode="json") for p in places],
            "glossary": [g.model_dump(mode="json") for g in glossary],
            "counts": {
                "unreviewed_total": unreviewed_total,
                "unreviewed_by_culture": unreviewed_by_culture,
                "unreviewed_unassigned": unreviewed_unassigned,
                "unsure_places": unsure_places,
                "unreviewed_additions_by_culture": unreviewed_additions_by_culture,
            },
        }
