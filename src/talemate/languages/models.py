"""Data models for languages: sound categories, name generators, words and
phrases.

They are permissive on input (`extra="ignore"`), so hand-edited or
AI-written language data carrying unknown fields still loads.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["GeneratorDef", "Phrase", "DictionaryEntry", "Language"]


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
