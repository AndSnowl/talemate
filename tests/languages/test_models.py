"""The language file format (languages 3a, Task 1)."""

import json

import pytest

from talemate.languages.models import GeneratorDef, Language, LanguageFile
from talemate.languages.schema import SCHEMA_PATH, language_file_schema


def test_language_file_round_trips():
    lang = Language(
        name="Moscavian",
        level="full",
        flavour="russian",
        categories={"C": "k v r", "V": "a o"},
        generators=[
            GeneratorDef(id="w", name="Words", use="words", patterns=["CVCV"]),
            GeneratorDef(id="p", name="People", use="character", patterns=["CVC"]),
        ],
    )
    f = LanguageFile(language=lang, parent="Old Moscavian")
    again = LanguageFile.model_validate_json(f.model_dump_json())
    assert again == f and again.language.word_generator().id == "w"
    assert again.format == "fantasymate.language" and again.version == 1


def test_generator_use_accepts_kinds_and_forms():
    for use in ("people", "words", "place", "adjective", "demonym"):
        GeneratorDef(id="g", name="g", use=use, patterns=["CV"])


def test_generator_use_rejects_unknown():
    with pytest.raises(ValueError):
        GeneratorDef(id="g", name="g", use="spaceships", patterns=["CV"])


def test_word_generator_absent():
    assert Language(name="x", level="naming").word_generator() is None


def test_committed_schema_matches_the_model():
    assert json.loads(SCHEMA_PATH.read_text()) == language_file_schema()
