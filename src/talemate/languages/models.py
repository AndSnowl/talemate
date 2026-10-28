"""Data models for languages: sound categories, name generators, words and
phrases.

They are permissive on input (`extra="ignore"`), so hand-edited or
AI-written language data carrying unknown fields still loads.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "GENERATOR_USES",
    "GeneratorDef",
    "Phrase",
    "DictionaryEntry",
    "SimilarLink",
    "Language",
    "LanguageFile",
]

# what a generator makes: the three old buckets, ordinary words (the rules
# dictionary words are checked against and translations are rolled from),
# names for one entry kind, and the forms a name takes
GENERATOR_USES: frozenset[str] = frozenset(
    {
        "people",
        "places",
        "things",
        "words",
        "character",
        "place",
        "item",
        "event",
        "lore",
        "being",
        "species",
        "race",
        "adjective",
        "demonym",
    }
)


class GeneratorDef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    use: str
    patterns: list[str]
    reject: list[str] = Field(default_factory=list)
    capitalize: bool = True
    min_length: int = 2
    max_length: int = 24

    @field_validator("use")
    @classmethod
    def _known_use(cls, value: str) -> str:
        if value not in GENERATOR_USES:
            raise ValueError(f"unknown generator use: {value!r}")
        return value


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


class SimilarLink(BaseModel):
    """Another language this one is close to, by name (in a file; an entry
    stores the other language's id)."""

    model_config = ConfigDict(extra="ignore")

    name: str
    degree: Literal["close", "distant", "one-way"]


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
    # whose real words the real-word check looks for ("russian", "english"),
    # lower-case; "" for none
    flavour: str = ""
    similar: list[SimilarLink] = Field(default_factory=list)

    def word_generator(self) -> GeneratorDef | None:
        """The generator for ordinary words (`use == "words"`), if any."""
        return next((g for g in self.generators if g.use == "words"), None)


class LanguageFile(BaseModel):
    """A language as a file: what the language-design skill writes and the
    app imports. `parent` names the language it descends from."""

    model_config = ConfigDict(extra="ignore")

    format: Literal["fantasymate.language"] = "fantasymate.language"
    version: Literal[1] = 1
    language: Language
    parent: str | None = None
    description: str = ""
