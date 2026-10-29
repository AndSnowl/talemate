"""Fixes from the languages 3a whole-branch review."""

from talemate.languages.importer import parse_language_text
from talemate.languages.models import Language
from talemate.worldplay.create import _aka_entries
from talemate.worldplay.links import clean_aka

LID = "a" * 32


def test_clean_aka_keeps_a_language_marker():
    got = clean_aka(
        [{"name": "Sel Karaj", "tag": "proper", "everyday": False, "language": LID}],
        "Sorau",
    )
    assert got == [
        {"name": "Sel Karaj", "tag": "proper", "everyday": False, "language": LID}
    ]
    bad = clean_aka(
        [{"name": "X", "tag": "proper", "everyday": False, "language": "nope"}], "Y"
    )
    assert "language" not in bad[0]


def test_aka_entries_keep_a_language_marker():
    got = _aka_entries([{"name": "Sel Karaj", "tag": "proper", "language": LID}])
    assert got[0]["language"] == LID


def test_flavour_is_lower_cased():
    assert Language(name="x", level="naming", flavour=" Russian ").flavour == "russian"


def test_parse_accepts_raw_line_breaks_in_strings():
    text = '{"language": {"name": "Velskar", "level": "full", "grammar": "line one\nline two"}}'
    # an older file's grammar text: one section, its line break kept
    assert parse_language_text(text).language.grammar[0].text == "line one\nline two"
