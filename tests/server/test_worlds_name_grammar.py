"""The Names chapter's grammar for names (languages 4b-1, Task 5): the
rows in plain words with examples the engine builds."""

from talemate.languages.entry import fields_of
from talemate.languages.models import (
    DictionaryEntry,
    FormChange,
    GrammarSection,
    GrammarTable,
    Language,
    NameGrammar,
)
from talemate.world.store import Source

from server.test_worlds_name_it import _act, _last, plugin  # noqa: F401

VAROVNI = Language(
    name="Varovni",
    level="full",
    categories={"C": "k v", "V": "a e i o u"},
    dictionary=[DictionaryEntry(word="skelt", meanings=["stone"], part="noun")],
    grammar=[
        GrammarSection(
            title="Nouns",
            topic="nouns",
            tables=[GrammarTable(caption="skelt (stone)", columns=[], rows=[])],
        )
    ],
    name_grammar=NameGrammar(
        the=[
            FormChange(when="after_vowel", kind="ending", text="k"),
            FormChange(kind="ending", text="ek"),
        ],
        more_than_one=[FormChange(kind="ending", text="i")],
    ),
)


async def _language(plugin, language):  # noqa: F811
    await _act(plugin, "create_world", name="Test")
    with plugin.world.revision(Source.manual()) as rev:
        return rev.create_thing(
            "language", {"name": language.name, **fields_of(language)}
        )


async def test_language_name_grammar_answers_rows(plugin):  # noqa: F811
    lid = await _language(plugin, VAROVNI)
    await _act(plugin, "language_name_grammar", thing_id=lid)
    data = _last(plugin, "language_name_grammar")["data"]
    assert data["thing_id"] == lid and data["has_grammar"] is True
    the = next(r for r in data["rows"] if r["key"] == "the")
    assert the["example"] == "skelt → skeltek" and not the["error"]


async def test_a_language_without_grammar_has_no_rows(plugin):  # noqa: F811
    lid = await _language(plugin, VAROVNI.model_copy(update={"name_grammar": None}))
    await _act(plugin, "language_name_grammar", thing_id=lid)
    data = _last(plugin, "language_name_grammar")["data"]
    assert data == {"thing_id": lid, "has_grammar": False, "rows": []}


async def test_a_row_that_cannot_build_says_so(plugin):  # noqa: F811
    grammar = VAROVNI.name_grammar.model_copy(
        update={"more_than_one": [FormChange(kind="ending", text="")]}
    )
    lid = await _language(plugin, VAROVNI.model_copy(update={"name_grammar": grammar}))
    await _act(plugin, "language_name_grammar", thing_id=lid)
    rows = {r["key"]: r for r in _last(plugin, "language_name_grammar")["data"]["rows"]}
    assert rows["more_than_one"]["error"] and not rows["more_than_one"]["example"]
    assert rows["the"]["example"] == "skelt → skeltek"
