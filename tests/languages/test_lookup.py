"""Which languages apply to an entry (languages 3a, Task 5)."""

from _language_test_helpers import _row

import talemate.world.store as store
from talemate.languages.lookup import (
    LanguageRow,
    default_language,
    languages_for,
    languages_for_scene,
)
from talemate.world.dates import WorldDate
from talemate.world.store import Source


def _names(rows):
    return {(r.name, r.role) for r in rows}


def test_own_rows_win(lang_world):
    rows = languages_for(lang_world.world.view(), lang_world.ids["Sorau"])
    assert _names(rows) == {("Sorauan", "official"), ("Moscavian", "spoken")}
    assert not any(r.inherited for r in rows)
    assert next(r for r in rows if r.name == "Moscavian").share == 25


def test_inherits_from_filed_place(lang_world):
    rows = languages_for(lang_world.world.view(), lang_world.ids["Thornfield"])
    assert {r.name for r in rows} == {"Sorauan", "Moscavian"}
    assert all(r.inherited and r.source_id == lang_world.ids["Sorau"] for r in rows)


def test_character_takes_places_only_and_spoken_official(lang_world):
    rows = languages_for(lang_world.world.view(), lang_world.ids["Mira"])
    assert {r.name for r in rows} == {"Sorauan", "Moscavian"}


def test_character_own_rows_win(lang_world):
    w, ids = lang_world.world, lang_world.ids
    with w.revision(Source.manual()) as rev:
        rev.set_field(
            ids["Mira"],
            "languages",
            [_row(ids["Sorauan"], "spoken", fluency="native")],
            None,
        )
    rows = languages_for(w.view(), ids["Mira"])
    assert [(r.name, r.fluency, r.inherited) for r in rows] == [
        ("Sorauan", "native", False)
    ]


def test_dated_rows(lang_world):
    w, ids = lang_world.world, lang_world.ids
    with w.revision(Source.manual()) as rev:
        rev.set_field(
            ids["Sorau"],
            "languages",
            [
                _row(ids["Moscavian"], "official", until=1412),
                _row(ids["Sorauan"], "official", since=1412),
            ],
            None,
        )
    before = languages_for(w.view(at=WorldDate.of(1400)), ids["Sorau"])
    after = languages_for(w.view(at=WorldDate.of(1500)), ids["Sorau"])
    assert {r.name for r in before} == {"Moscavian"}
    assert {r.name for r in after} == {"Sorauan"}


def test_lookup_survives_a_filing_cycle(lang_world, monkeypatch):
    w = lang_world.world
    with w.revision(Source.manual()) as rev:
        a = rev.create_thing("place", {"name": "A"})
        b = rev.create_thing("place", {"name": "B", "filings": [{"target": a}]})
    # the store refuses a cycle, but undo can bring one back
    monkeypatch.setattr(store, "check_filings", lambda *args, **kwargs: [])
    with w.revision(Source.manual()) as rev:
        rev.set_field(a, "filings", [{"target": b}], None)
    assert languages_for(w.view(), a) == []


def test_lookup_skips_deleted_language(lang_world):
    w, ids = lang_world.world, lang_world.ids
    with w.revision(Source.manual()) as rev:
        rev.remove_thing(ids["Moscavian"])
    rows = languages_for(w.view(), ids["Sorau"])
    assert {r.name for r in rows} == {"Sorauan"}


def test_default_language_order():
    def row(lid, role, share=None):
        return LanguageRow(
            language_id=lid,
            name=lid,
            role=role,
            share=share,
            fluency=None,
            source_id="x",
            inherited=False,
        )

    assert default_language([row("a", "spoken", 25), row("b", "official")]) == "b"
    assert default_language([row("a", "spoken", 25), row("c", "spoken", 70)]) == "c"
    assert default_language([row("d", "scholarly")]) == "d"
    assert default_language([]) is None


def test_scene_languages_speaker_first(lang_world):
    w, ids = lang_world.world, lang_world.ids
    with w.revision(Source.manual()) as rev:
        ivan = rev.create_thing(
            "character",
            {
                "name": "Ivan",
                "languages": [_row(ids["Moscavian"], "spoken", fluency="native")],
            },
        )
    rows = languages_for_scene(w.view(), ids["Sorau"], ivan)
    assert [r.name for r in rows] == ["Moscavian", "Sorauan"]
