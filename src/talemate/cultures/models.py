"""Data models for cultures, languages, glossaries and places.

These models are intentionally permissive on input (`extra="ignore"`) so
that hand-edited or AI-generated data files that carry extra, unknown
fields do not break loading.
"""

import re
import unicodedata
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "GeneratorDef",
    "Phrase",
    "DictionaryEntry",
    "Language",
    "Holiday",
    "PlayAddition",
    "Culture",
    "CultureShare",
    "Place",
    "GlossaryOrigin",
    "GlossaryEntry",
    "PlacesFile",
    "GlossaryFile",
    "new_id",
    "slugify",
]


def new_id() -> str:
    """Return a short unique id."""
    return uuid4().hex[:12]


def slugify(name: str) -> str:
    """Lowercase ASCII slug, with runs of non-alphanumerics collapsed to `-`."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-")
    return slug.lower()


class GeneratorDef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    use: Literal["people", "places", "things"]
    patterns: list[str]
    reject: list[str] = Field(default_factory=list)
    capitalize: bool = True
    min_length: int = 2
    max_length: int = 24


class Phrase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    category: str
    original: str
    translation: str
    breakdown: list[tuple[str, str]] = Field(default_factory=list)
    usage: str = ""


class DictionaryEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    word: str
    meaning: str
    part: str = ""
    notes: str = ""


class Language(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    level: Literal["description", "naming", "full"]
    writable: bool = True
    sound: str = ""
    categories: dict[str, str] = Field(default_factory=dict)
    syllable_notes: list[str] = Field(default_factory=list)
    generators: list[GeneratorDef] = Field(default_factory=list)
    grammar: str = ""
    dictionary: list[DictionaryEntry] = Field(default_factory=list)
    phrases: list[Phrase] = Field(default_factory=list)


class Holiday(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    when: str = ""
    description: str = ""


class PlayAddition(BaseModel):
    """A candidate addition to scene play (customs, food, holidays).

    Keep sets `status` to `reviewed`; Edit changes the `text`.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    section: Literal["customs", "food", "holidays"]
    text: str
    source: str = ""
    status: Literal["unreviewed", "reviewed"] = "unreviewed"


class Culture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    color: str = "#9E9E9E"
    description: str = ""
    language: Language
    customs: list[str] = Field(default_factory=list)
    food: str = ""
    holidays: list[Holiday] = Field(default_factory=list)
    additions: list[PlayAddition] = Field(default_factory=list)
    source_file: str = ""
    imported_at: str = ""


class CultureShare(BaseModel):
    model_config = ConfigDict(extra="ignore")

    culture_id: str
    share: int


class Place(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
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
    ] = "town"
    parent_id: str | None = None
    cultures: list[CultureShare] = Field(default_factory=list)
    world_entry_id: str | None = None
    set_by: Literal["ai", "owner"] = "owner"
    unsure: bool = False
    note: str = ""


class GlossaryOrigin(BaseModel):
    model_config = ConfigDict(extra="ignore")

    by: Literal["ai", "ai_free", "import", "owner"]
    generator_id: str | None = None
    candidates: list[str] = Field(default_factory=list)


class GlossaryEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    text: str
    language: str | None
    kind: Literal["person", "place", "thing", "word"]
    meaning: str = ""
    renderings: dict[str, str] = Field(default_factory=dict)
    true_name: str = ""
    origin: GlossaryOrigin
    first_used: str = ""
    status: Literal["unreviewed", "reviewed"] = "unreviewed"
    edited_by_owner: bool = False
    character_name: str | None = None
    place_id: str | None = None


class PlacesFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format_version: int = 1
    places: list[Place] = Field(default_factory=list)


class GlossaryFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format_version: int = 1
    entries: list[GlossaryEntry] = Field(default_factory=list)
