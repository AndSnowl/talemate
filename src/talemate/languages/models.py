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
    "PARTS_OF_SPEECH",
    "GrammarExample",
    "GrammarSection",
    "GrammarTable",
    "GeneratorDef",
    "Phrase",
    "DictionaryEntry",
    "Ending",
    "FormChange",
    "NameGrammar",
    "NamePart",
    "NameShape",
    "OfRule",
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


class FormChange(BaseModel):
    """One way a word changes for a form or an ending (languages 4b-1):
    an ending added (`text`, after `drop` letters are taken off), a word
    put before or after it, or its first part doubled; only `when` its
    condition holds (`name_grammar.parse_condition`)."""

    model_config = ConfigDict(extra="ignore")

    when: str = ""
    kind: Literal["ending", "swap", "word_before", "word_after", "double"] = "ending"
    text: str = ""
    drop: str = ""


class Ending(BaseModel):
    """A meaningful ending ("-nya", land of). No `changes` means the plain
    ending added."""

    model_config = ConfigDict(extra="ignore")

    ending: str
    meaning: str
    example: str = ""
    changes: list[FormChange] = Field(default_factory=list)


class OfRule(BaseModel):
    """How "of X" is said: a word (on `word_side` of X) or an ending on X;
    the of-phrase goes `place`d before or after the thing it belongs to;
    with `the`, X takes "the"."""

    model_config = ConfigDict(extra="ignore")

    how: Literal["word", "ending"] = "word"
    text: str
    word_side: Literal["before", "after"] = "before"
    place: Literal["before", "after"] = "after"
    the: bool = False


class NameGrammar(BaseModel):
    """A language's grammar for names (languages 4b-1): word order, the
    forms "the" and "more than one", and its meaningful endings. The name
    engine (`name_grammar`) applies it; the model never does."""

    model_config = ConfigDict(extra="ignore")

    describing: Literal["before", "after"] = "before"
    of: OfRule | None = None
    joining: Literal["describing_first", "main_first"] = "describing_first"
    clip_first: bool = False
    the: list[FormChange] = Field(default_factory=list)
    more_than_one: list[FormChange] = Field(default_factory=list)
    endings: list[Ending] = Field(default_factory=list)


class NamePart(BaseModel):
    """One part of a composed name rule: another rule, a fixed word, or a
    meaning part (words of the language built from a meaning)."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["rule", "word", "meaning"]
    rule: str = ""
    word: str = ""
    slot: Literal["noun", "describing_noun"] = "noun"
    forms: list[Literal["the", "more_than_one"]] = Field(default_factory=list)
    of: bool = False
    joined: bool = False
    # an ending's meaning ("land of") the meaning part takes
    ending: str = ""
    # what the model looks for, for Suggest ("something in the sky")
    hint: str = ""
    optional: bool = False
    label: str = ""


class NameShape(BaseModel):
    """One way a composed rule's name goes, its parts in order; shapes are
    picked by `weight`, as patterns are."""

    model_config = ConfigDict(extra="ignore")

    parts: list[NamePart]
    weight: int = 1


class GeneratorDef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    use: str
    patterns: list[str] = Field(default_factory=list)
    # a composed rule's shapes (languages 4b-1), instead of patterns
    shapes: list[NameShape] = Field(default_factory=list)
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


# the parts of speech a dictionary word may have: id, plain label, example
# (languages 3b-2); the owner may also type their own
PARTS_OF_SPEECH: tuple[tuple[str, str, str], ...] = (
    ("noun", "noun", "house"),
    ("verb", "verb", "run"),
    ("adjective", "adjective", "cold"),
    ("adverb", "adverb", "quickly"),
    ("pronoun", "pronoun", "I, they"),
    ("article", "article", "the, a"),
    ("preposition", "preposition", "in, with"),
    ("conjunction", "conjunction", "and, if"),
    ("number", "number", "two"),
    ("question", "question word", "who, where"),
    ("particle", "particle", "not, yes"),
    ("exclamation", "exclamation", "alas!"),
    ("ending", "ending", "-ov"),
)


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


def _cell(value: object) -> str:
    """A table cell or text as a model may write it: a number is its
    digits, nothing is empty."""

    return "" if value is None else str(value)


class GrammarTable(BaseModel):
    """A table in a grammar section: a conjugation, noun endings, the
    pronouns. Rows are kept as written, even when ragged."""

    model_config = ConfigDict(extra="ignore")

    caption: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _loose_cells(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data["caption"] = _cell(data.get("caption"))
        data["columns"] = [_cell(c) for c in data.get("columns") or []]
        data["rows"] = [
            [_cell(c) for c in row] if isinstance(row, list) else [_cell(row)]
            for row in data.get("rows") or []
        ]
        return data


class GrammarExample(BaseModel):
    """A worked example: the original, word by word, and its translation."""

    model_config = ConfigDict(extra="ignore")

    original: str
    breakdown: list[tuple[str, str]] = Field(default_factory=list)
    translation: str = ""

    @model_validator(mode="before")
    @classmethod
    def _loose_example(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data["original"] = _cell(data.get("original"))
        data["translation"] = _cell(data.get("translation"))
        pairs = []
        for pair in data.get("breakdown") or []:
            if isinstance(pair, (list, tuple)) and pair:
                pairs.append((_cell(pair[0]), _cell(pair[1]) if len(pair) > 1 else ""))
        data["breakdown"] = pairs
        return data


class GrammarSection(BaseModel):
    """One topic of a language's grammar: plain text, tables, examples."""

    model_config = ConfigDict(extra="ignore")

    title: str
    topic: str = "other"
    text: str = ""
    tables: list[GrammarTable] = Field(default_factory=list)
    examples: list[GrammarExample] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _title_from_topic(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data["topic"] = _cell(data.get("topic")).strip() or "other"
        data["text"] = _cell(data.get("text"))
        if not _cell(data.get("title")).strip():
            data["title"] = dict(GRAMMAR_TOPICS).get(data["topic"], "Grammar")
        return data


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
    # the grammar for names (languages 4b-1); None: names are built in the
    # owner's word order, as in 4a
    name_grammar: NameGrammar | None = None

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
