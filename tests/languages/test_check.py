"""The shared language check (languages 3a, Task 2)."""

from talemate.languages.__main__ import main
from talemate.languages.check import (
    CheckReport,
    check_language,
    is_part_style,
    needs_repair,
    repair_note,
)
from talemate.languages.models import (
    DictionaryEntry,
    GeneratorDef,
    Language,
    LanguageFile,
)


def _lang(words=(), reject=(), flavour="", patterns=("CVCV",)):
    return Language(
        name="Testish",
        level="full",
        flavour=flavour,
        categories={"C": "k t r m n s v", "V": "a o e i u"},
        generators=[
            GeneratorDef(
                id="w",
                name="Words",
                use="words",
                patterns=list(patterns),
                reject=list(reject),
            ),
            GeneratorDef(id="p", name="Places", use="places", patterns=["CVCVC"]),
        ],
        dictionary=[DictionaryEntry(word=w, meaning=m) for w, m in words],
    )


def _parts_style(first, second):
    return Language(
        name="Hollowish",
        level="naming",
        flavour="english",
        categories={"A": " ".join(first), "B": " ".join(second)},
        generators=[GeneratorDef(id="p", name="Places", use="places", patterns=["AB"])],
        dictionary=[DictionaryEntry(word=w, meaning="part") for w in (*first, *second)],
    )


def test_bad_pattern_blocks():
    r = check_language(_lang(reject=["("]))
    assert not r.ok and any("rule" in b for b in r.blocking)


def test_unfit_words_warn_but_do_not_block():
    r = check_language(_lang(words=[("kata", "hill"), ("xyzzy", "?")]))
    assert r.ok and r.unfit_words == ["xyzzy"] and r.fit_share == 0.5


def test_compound_of_fitting_words_counts_as_fitting():
    r = check_language(
        _lang(words=[("vasa", "great"), ("karo", "walls"), ("vasakaro", "great fort")])
    )
    assert r.unfit_words == []


def test_no_word_generator_skips_fit():
    lang = _lang(words=[("kata", "hill")])
    lang.generators = [g for g in lang.generators if g.use != "words"]
    r = check_language(lang)
    assert r.fit_share is None and r.fit_skipped_reason


def test_russian_real_words_warn():
    r = check_language(_lang(flavour="russian", words=[("voda", "water")]))
    assert r.ok and "voda" in r.real_hits


def test_part_style_flags_real_place_names_not_parts():
    style = _parts_style(["ash"], ["ford"])  # only ever rolls "Ashford", a real town
    assert is_part_style(style)
    r = check_language(style)
    assert r.fit_share is None and "Ashford" in r.real_hits
    assert "ash" not in r.real_hits


def test_unknown_flavour_skips_real_check():
    r = check_language(_lang(flavour="elvish"))
    assert r.real_skipped_reason and r.real_hits == []


def test_samples_rolled_per_generator():
    r = check_language(_lang(), samples=5)
    assert set(r.samples) == {"w", "p"} and len(r.samples["p"]) == 5


def test_repair_note_lists_blocking_first_in_plain_words():
    # a language whose rules can't be read can't be fit-checked, so the
    # order is checked on a report holding both kinds of problem
    note = repair_note(
        CheckReport(blocking=["A name rule can't be read"], warnings=["1 word: xyzzy"])
    )
    assert note.index("must be fixed") < note.index("xyzzy")
    assert "must be fixed" in repair_note(check_language(_lang(reject=["("])))
    for term in ("phoneme", "phonotactic", "morpheme"):
        assert term not in note.lower()


def test_needs_repair_on_many_unfit_words():
    many = [("xyzzy", "?"), ("qwqw", "?"), ("kata", "hill")]
    assert needs_repair(check_language(_lang(words=many)))
    assert not needs_repair(check_language(_lang(words=[("kata", "hill")])))


def test_cli_exit_codes(tmp_path, capsys):
    good = tmp_path / "g.json"
    good.write_text(LanguageFile(language=_lang()).model_dump_json())
    assert main(["check", str(good)]) == 0
    bad = tmp_path / "b.json"
    bad.write_text(LanguageFile(language=_lang(reject=["("])).model_dump_json())
    assert main(["check", str(bad)]) == 1
    junk = tmp_path / "j.json"
    junk.write_text("{not json")
    assert main(["check", str(junk)]) == 1
    assert "must be fixed" in capsys.readouterr().out
