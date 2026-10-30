"""Import, export and diffs (languages 3a, Task 6)."""

import pytest

from talemate.languages.__main__ import main
from talemate.languages.entry import fields_of, language_of
from talemate.languages.importer import (
    LanguageParseError,
    apply_import,
    export_language,
    parse_language_text,
    preview_import,
)
from talemate.languages.models import (
    DictionaryEntry,
    GeneratorDef,
    Language,
    LanguageFile,
    Phrase,
)
from talemate.world.store import Source


def _moscavian(words=(("vel", "great"), ("sorau", "free land")), reject=()):
    return Language(
        name="Moscavian",
        level="full",
        flavour="russian",
        categories={"C": "k v r s l", "V": "a o e u"},
        generators=[
            GeneratorDef(
                id="w",
                name="Words",
                use="words",
                patterns=["CVC", "CVCVC"],
                reject=list(reject),
            ),
            GeneratorDef(id="p", name="Places", use="places", patterns=["CVCVC"]),
        ],
        dictionary=[DictionaryEntry(word=w, meaning=m) for w, m in words],
    )


def _text(lang, **kw):
    return LanguageFile(language=lang, **kw).model_dump_json()


def test_parse_accepts_fenced_and_wrapped_text():
    body = _text(_moscavian())
    for text in (
        body,
        f"Here you go:\n```json\n{body}\n```\nEnjoy!",
        _moscavian().model_dump_json(),
    ):
        assert parse_language_text(text).language.name == "Moscavian"


def test_parse_error_is_plain():
    with pytest.raises(LanguageParseError, match="no language"):
        parse_language_text("sorry, I can't")


def test_import_creates_entry_and_links_parent(world):
    with world.revision(Source.manual()) as rev:
        old = rev.create_thing("language", {"name": "Old Moscavian"})
    preview = preview_import(world.view(), _text(_moscavian(), parent="Old Moscavian"))
    assert preview.report.ok and preview.diff is None
    with world.revision(Source.manual()) as rev:
        lid = apply_import(rev, world.view(), preview)
    state = world.view().thing(lid)
    assert state.fields["name"] == "Moscavian"
    assert state.fields["descends_from"] == old
    assert language_of(state).dictionary[0].word == "vel"


def test_import_drops_unknown_parent(world):
    preview = preview_import(world.view(), _text(_moscavian(), parent="Nowhere"))
    with world.revision(Source.manual()) as rev:
        lid = apply_import(rev, world.view(), preview)
    assert "descends_from" not in world.view().thing(lid).fields


def test_import_refuses_blocking(world):
    preview = preview_import(world.view(), _text(_moscavian(reject=["("])))
    assert not preview.report.ok
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            apply_import(rev, world.view(), preview)


def _stored(world, lang):
    with world.revision(Source.manual()) as rev:
        return rev.create_thing("language", {"name": lang.name, **fields_of(lang)})


def test_revision_keeps_used_words(world):
    lid = _stored(
        world, _moscavian(words=[("velgarov", "great fort"), ("sorau", "free land")])
    )
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Velgarov"})
        rev.create_thing("place", {"name": "Free Provinces of Sorau"})
    new = _moscavian(words=[("sorau", "southern march"), ("kor", "river")])
    preview = preview_import(world.view(), _text(new), target_id=lid)
    assert set(preview.diff.kept_used) == {"velgarov", "sorau"}
    with world.revision(Source.manual()) as rev:
        apply_import(rev, world.view(), preview, target_id=lid)
    words = {
        e.word: e.meanings[0] for e in language_of(world.view().thing(lid)).dictionary
    }
    assert words == {"velgarov": "great fort", "sorau": "free land", "kor": "river"}


def test_diff_lists_changes(world):
    lid = _stored(world, _moscavian(words=[("vel", "great"), ("kar", "rot")]))
    new = _moscavian(words=[("vel", "big"), ("lor", "light")])
    diff = preview_import(world.view(), _text(new), target_id=lid).diff
    assert diff.words_added == ["lor"]
    assert diff.words_removed == ["kar"]
    assert diff.words_changed == ["vel"]
    assert not diff.generators_changed
    assert set(diff.samples_before) == set(diff.samples_after) == {"w", "p"}


def test_diff_shows_changed_phrases_before_and_after_by_category(world):
    def phrase(pid, category, original, translation):
        return Phrase(
            id=pid, category=category, original=original, translation=translation
        )

    old = _moscavian()
    old.phrases = [
        phrase("c1", "curse", "Zelgor nirosh te!", "Fierce shadow upon you!"),
        phrase("c2", "curse", "Kol ye zor!", "Frost and star!"),
        phrase("g1", "greeting", "Vel sorau.", "Great land."),
    ]
    lid = _stored(world, old)
    new = _moscavian()
    new.phrases = [
        phrase("c2", "curse", "Kol ye zor!", "Frost and stars!"),
        phrase("c3", "curse", "Dolg tvoi v reke!", "Your debt in the river!"),
        phrase("g1", "greeting", "Vel sorau.", "Great land."),
        phrase("o1", "oath", "Pon rukva.", "By hand."),
    ]
    diff = preview_import(world.view(), _text(new), target_id=lid).diff
    # only the categories that changed, each whole, before and after
    assert [c.category for c in diff.phrase_changes] == ["curse", "oath"]
    curse, oath = diff.phrase_changes
    assert [(p.original, p.translation) for p in curse.before] == [
        ("Zelgor nirosh te!", "Fierce shadow upon you!"),
        ("Kol ye zor!", "Frost and star!"),
    ]
    assert [p.translation for p in curse.after] == [
        "Frost and stars!",
        "Your debt in the river!",
    ]
    assert oath.before == [] and [p.original for p in oath.after] == ["Pon rukva."]


def test_export_round_trips(world):
    lid = _stored(world, _moscavian())
    exported = export_language(world.view(), lid)
    assert exported.language.model_dump() == _moscavian().model_dump()


def test_cli_reads_wrapped_text(tmp_path):
    path = tmp_path / "reply.txt"
    path.write_text("Sure!\n```json\n" + _text(_moscavian()) + "\n```")
    assert main(["check", str(path)]) == 0
