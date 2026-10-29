"""Data models for languages: sound categories, name generators, words and
phrases.

They are permissive on input (`extra="ignore"`), so hand-edited or
AI-written language data carrying unknown fields still loads.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "GENERATOR_USES",
    "GRAMMAR_TOPICS",
    "GrammarExample",
    "GrammarSection",
    "GrammarTable",
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
    """A word and its meanings ("wind", "breath"); a word made only to be
    a name may have none. An older file's single `meaning` is read as the
    first meaning and never written back."""

    model_config = ConfigDict(extra="ignore")

    word: str
    meanings: list[str] = Field(default_factory=list)
    meaning: str = Field(default="", exclude=True)
    part: str = ""
    notes: str = ""

    @model_validator(mode="after")
    def _one_meaning_is_a_list(self) -> "DictionaryEntry":
        if self.meaning.strip() and not self.meanings:
            self.meanings = [self.meaning.strip()]
        self.meaning = ""
        self.meanings = [m.strip() for m in self.meanings if m.strip()]
        return self


# the grammar topics a full language covers, with their plain titles
# (languages 3b-2); a section on anything else is "other"
GRAMMAR_TOPICS: tuple[tuple[str, str], ...] = (
    ("sounds", "Sounds and stress"),
    ("word_order", "Word order"),
    ("nouns", "Nouns"),
    ("pronouns", "Pronouns"),
    ("verbs", "Verbs"),
    ("adjectives", "Adjectives"),
    ("questions", 'Questions and "not"'),
    ("numbers", "Numbers"),
    ("word_building", "How words are built"),
    ("names", "How names are built"),
    ("politeness", "Politeness and registers"),
)


class GrammarTable(BaseModel):
    """A table in a grammar section: a conjugation, noun endings, the
    pronouns. Rows are kept as written, even when ragged."""

    model_config = ConfigDict(extra="ignore")

    caption: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class GrammarExample(BaseModel):
    """A worked example: the original, word by word, and its translation."""

    model_config = ConfigDict(extra="ignore")

    original: str
    breakdown: list[tuple[str, str]] = Field(default_factory=list)
    translation: str = ""


class GrammarSection(BaseModel):
    """One topic of a language's grammar: plain text, tables, examples."""

    model_config = ConfigDict(extra="ignore")

    title: str
    topic: str = "other"
    text: str = ""
    tables: list[GrammarTable] = Field(default_factory=list)
    examples: list[GrammarExample] = Field(default_factory=list)


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
    # sections; an older file's grammar text is read as one section
    grammar: list[GrammarSection] = Field(default_factory=list)
    dictionary: list[DictionaryEntry] = Field(default_factory=list)
    phrases: list[Phrase] = Field(default_factory=list)
    # whose real words the real-word check looks for ("russian", "english"),
    # lower-case; "" for none
    flavour: str = ""
    similar: list[SimilarLink] = Field(default_factory=list)

    @field_validator("grammar", mode="before")
    @classmethod
    def _text_grammar_is_one_section(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [{"title": "Grammar", "topic": "other", "text": value}]
        return value

    @field_validator("flavour")
    @classmethod
    def _lower_flavour(cls, value: str) -> str:
        return value.strip().lower()

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
