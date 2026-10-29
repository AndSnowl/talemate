"""Grammar as sections with tables and examples (languages 3b-2a, Task 1)."""

from talemate.languages.check import check_language
from talemate.languages.entry import fields_of, language_of
from talemate.languages.models import (
    GRAMMAR_TOPICS,
    GeneratorDef,
    GrammarExample,
    GrammarSection,
    GrammarTable,
    Language,
)
from talemate.languages.schema import language_file_schema
from talemate.world.kinds import get_kind, validate_field
from talemate.world.view import ThingState

NOUNS = GrammarSection(
    title="Nouns",
    topic="nouns",
    text="Nouns are masculine or feminine.",
    tables=[
        GrammarTable(
            caption="dov (shrine)",
            columns=["", "one", "more than one"],
            rows=[
                ["a", "dov", "dovy"],
                ["the", "doven"],
                ["of the", "dovena", "dovyena", "x"],
            ],
        )
    ],
    examples=[
        GrammarExample(
            original="Zorin doven stoi",
            breakdown=[
                ("zorin", "bright"),
                ("doven", "shrine-the"),
                ("stoi", "stands"),
            ],
            translation="The bright shrine stands.",
        )
    ],
)


def _language(**kw):
    return Language(
        name="Moscavian",
        level="full",
        categories={"C": "k s r d v", "V": "a o u"},
        generators=[GeneratorDef(id="w", name="Words", use="words", patterns=["CVC"])],
        **kw,
    )


def test_old_grammar_text_is_one_section():
    lang = _language(grammar="Verbs come last.")
    assert lang.grammar == [
        GrammarSection(title="Grammar", topic="other", text="Verbs come last.")
    ]


def test_empty_grammar_is_no_sections():
    assert _language(grammar="").grammar == []
    assert _language().grammar == []


def test_the_standard_topics():
    assert [t for t, _ in GRAMMAR_TOPICS] == [
        "sounds", "word_order", "nouns", "pronouns", "verbs", "adjectives",
        "questions", "numbers", "word_building", "names", "politeness",
    ]  # fmt: skip


def test_sections_round_trip_through_an_entry():
    lang = _language(grammar=[NOUNS])
    fields = fields_of(lang)
    validate_field(get_kind("language"), "rules", fields["rules"])
    state = ThingState(
        id="x", kind="language", fields={"name": "Moscavian", **fields}, facts=[]
    )
    assert language_of(state).grammar == [NOUNS]


def test_a_ragged_table_loads_as_written():
    rows = _language(grammar=[NOUNS]).grammar[0].tables[0].rows
    assert [len(r) for r in rows] == [3, 2, 4]


def test_real_words_in_grammar_examples_are_flagged():
    example = GrammarExample(original="Voda kor", breakdown=[("voda", "water")])
    lang = _language(
        flavour="russian",
        grammar=[GrammarSection(title="Nouns", topic="nouns", examples=[example])],
    )
    assert "Voda kor" in check_language(lang).real_hits


def test_the_schema_has_grammar_sections():
    schema = language_file_schema()
    grammar = schema["$defs"]["Language"]["properties"]["grammar"]
    assert grammar["type"] == "array"
    assert grammar["items"]["$ref"].endswith("/GrammarSection")


# --- final review fixes ------------------------------------------------------

import json  # noqa: E402
from pathlib import Path  # noqa: E402

from talemate.languages.importer import parse_language_text  # noqa: E402


def test_the_briefs_example_uses_grammar_sections():
    example = json.loads(Path("src/talemate/languages/data/example.language.json").read_text())
    grammar = example["language"]["grammar"]
    assert isinstance(grammar, list) and len(grammar) >= 2
    assert any(section.get("tables") for section in grammar)
    assert any(section.get("examples") for section in grammar)


def test_loosely_typed_grammar_still_loads():
    section = {
        "topic": "numbers",
        "tables": [{"caption": "counting", "columns": ["", "word"], "rows": [[1, "un"], [2, None]]}],
        "examples": [{"original": "Un dov", "breakdown": [["un", "one"]], "translation": None}],
    }
    lang = _language(grammar=[section])
    assert lang.grammar[0].title == "Numbers"
    assert lang.grammar[0].tables[0].rows == [["1", "un"], ["2", ""]]
    assert lang.grammar[0].examples[0].translation == ""


def test_a_bad_file_says_where_it_went_wrong():
    text = json.dumps(
        {"language": {"name": "X", "level": "full", "grammar": [{"title": "N", "tables": "oops"}]}}
    )
    try:
        parse_language_text(text)
    except ValueError as exc:
        assert "grammar" in str(exc)
    else:
        raise AssertionError("expected a ValueError")
