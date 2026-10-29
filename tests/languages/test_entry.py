"""Language entries and used words (languages 3a, Task 4)."""

from talemate.languages.entry import fields_of, language_of, languages, used_words
from talemate.languages.models import (
    DictionaryEntry,
    GeneratorDef,
    Language,
    Phrase,
)
from talemate.world.store import Source


def _moscavian(words=(("vel", "great"),)):
    return Language(
        name="Moscavian",
        level="full",
        flavour="russian",
        sound="Hard and rolling.",
        grammar="Adjectives come first.",
        syllable_notes=["no doubled vowels"],
        categories={"C": "k v r s", "V": "a o e"},
        generators=[GeneratorDef(id="w", name="Words", use="words", patterns=["CVC"])],
        dictionary=[DictionaryEntry(word=w, meaning=m) for w, m in words],
        phrases=[
            Phrase(
                id="p1", category="curse", original="Vel kar!", translation="Great rot!"
            )
        ],
    )


def _store(world, lang):
    with world.revision(Source.manual()) as rev:
        return rev.create_thing("language", {"name": lang.name, **fields_of(lang)})


def test_entry_round_trip(world):
    lang = _moscavian()
    lid = _store(world, lang)
    assert language_of(world.view().thing(lid)).model_dump() == lang.model_dump()


def test_similar_links_round_trip_by_name(world):
    old = _store(world, _moscavian().model_copy(update={"name": "Sorauan"}))
    lang = _moscavian()
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing(
            "language",
            {
                "name": lang.name,
                **fields_of(lang),
                "similar": [{"target": old, "degree": "close"}],
            },
        )
    view = world.view()
    got = language_of(view.thing(lid), view)
    assert [(s.name, s.degree) for s in got.similar] == [("Sorauan", "close")]


def test_languages_lists_live_language_entries(world):
    lid = _store(world, _moscavian())
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Sorau"})
    assert [s.id for s in languages(world.view())] == [lid]


def test_used_words_from_names_and_aka(world):
    lid = _store(
        world,
        _moscavian(
            words=[
                ("velgarov", "great fort"),
                ("sorau", "free land"),
                ("kata", "hill"),
                ("ruk", "hand"),
            ]
        ),
    )
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Velgarov"})
        rev.create_thing(
            "place",
            {
                "name": "Free Provinces of Sorau",
                "aka": [{"name": "Kata Sorau", "tag": "proper", "everyday": False}],
            },
        )
    assert used_words(world.view(), lid) == {"velgarov", "sorau", "kata"}
