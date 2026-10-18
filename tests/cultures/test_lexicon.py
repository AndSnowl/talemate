"""Tests for the scene lexicon builder."""

from pathlib import Path

from talemate.cultures.exchange import CultureFile
from talemate.cultures.lexicon import (
    MAX_LEXICON_ENTRIES,
    build_scene_lexicon,
    can_highlight,
    phrase_kind,
)
from talemate.cultures.models import (
    Culture,
    DictionaryEntry,
    GlossaryEntry,
    GlossaryOrigin,
    Language,
)

FIXTURE_PATH = Path(__file__).parent / "data" / "taelrik.culture.json"


def load_taelrik() -> Culture:
    return CultureFile.model_validate_json(FIXTURE_PATH.read_text()).culture


def test_can_highlight_single_words():
    assert can_highlight("saervik") is True
    assert can_highlight("Rhok") is True
    assert can_highlight("dhaer") is True

    assert can_highlight("tal") is False
    assert can_highlight("the") is False
    assert can_highlight("lantern") is False
    assert can_highlight("Lanterns") is False
    assert can_highlight("lantern's") is False
    assert can_highlight("river") is False
    assert can_highlight("") is False
    assert can_highlight("1234") is False


def test_can_highlight_phrases_and_multiword_names():
    assert can_highlight("Rhok tal'dun!", phrase=True) is True
    assert can_highlight("Vel'dhaer ossa tae.", phrase=True) is True
    assert can_highlight("Go home", phrase=True) is False

    assert can_highlight("Grey Gull", phrase=False) is False
    assert can_highlight("Saervik Dhun", phrase=False) is True


def test_phrase_kind():
    assert phrase_kind("curse") == "curse"
    assert phrase_kind("Curses") == "curse"
    assert phrase_kind("Sayings & blessings") == "saying"
    assert phrase_kind("Greetings") == "greeting"
    assert phrase_kind("inscription") == "inscription"
    assert phrase_kind("") == "phrase"


def _glossary_entry(**overrides) -> GlossaryEntry:
    defaults = dict(
        id="g-saervik",
        text="saervik",
        language="taelrik",
        kind="thing",
        meaning="river-runner; a flat ferry boat",
        origin=GlossaryOrigin(by="import"),
    )
    defaults.update(overrides)
    return GlossaryEntry(**defaults)


def test_lexicon_phrases_and_words():
    taelrik = load_taelrik()
    glossary = [_glossary_entry()]

    lexicon = build_scene_lexicon([taelrik], glossary)
    texts = {entry.text for entry in lexicon}

    for phrase in taelrik.language.phrases:
        assert phrase.original in texts
    assert "saervik" in texts

    curse = next(e for e in lexicon if e.id == "phrase:taelrik:curse-rot")
    assert curse.kind == "curse"
    assert curse.translation == "Rot your roots!"
    assert curse.breakdown == [
        ["rhok", "rot"],
        ["tal", "your (scornful)"],
        ["dun", "roots"],
    ]
    assert curse.usage == "Common, coarse. Spat, not said."
    assert curse.culture_name == "Taelrik"
    assert curse.color == "#FF8A65"
    assert curse.target == {
        "type": "phrase",
        "culture_id": "taelrik",
        "phrase_id": "curse-rot",
    }

    saervik = next(e for e in lexicon if e.text == "saervik")
    assert saervik.kind == "word"
    assert saervik.target == {"type": "glossary", "entry_id": "g-saervik"}


def test_lexicon_excludes_names_english_and_absent_cultures():
    taelrik = load_taelrik()
    elsiri = Culture(
        id="elsiri", name="Elsiri", language=Language(name="Elsiri", level="naming")
    )

    glossary = [
        GlossaryEntry(
            id="g-kethrun",
            text="Kethrun",
            language="taelrik",
            kind="person",
            meaning="ford-born",
            origin=GlossaryOrigin(by="import"),
        ),
        GlossaryEntry(
            id="g-veldhaer",
            text="Veldhaer",
            language="taelrik",
            kind="place",
            meaning="grey ford",
            origin=GlossaryOrigin(by="import"),
        ),
        GlossaryEntry(
            id="g-lantern",
            text="Lantern",
            language="taelrik",
            kind="word",
            origin=GlossaryOrigin(by="owner"),
        ),
        GlossaryEntry(
            id="g-tal",
            text="tal",
            language="taelrik",
            kind="word",
            origin=GlossaryOrigin(by="owner"),
        ),
        GlossaryEntry(
            id="g-seawolf",
            text="Seawolf",
            language="taelrik",
            kind="thing",
            origin=GlossaryOrigin(by="ai_free"),
        ),
        GlossaryEntry(
            id="g-saelin",
            text="saelin",
            language="elsiri",
            kind="word",
            meaning="light",
            origin=GlossaryOrigin(by="import"),
        ),
    ]

    # elsiri is not present, so its word must never show up even though it
    # would otherwise qualify.
    lexicon = build_scene_lexicon([taelrik], glossary)
    texts = {entry.text for entry in lexicon}

    assert "Kethrun" not in texts
    assert "Veldhaer" not in texts
    assert "Lantern" not in texts
    assert "tal" not in texts
    assert "Seawolf" not in texts
    assert "saelin" not in texts

    # sanity: elsiri's word qualifies on its own merits, just not when absent
    assert can_highlight("saelin") is True
    assert elsiri.id not in {e.culture_id for e in lexicon}


def test_lexicon_dictionary_meaning_and_dedupe():
    taelrik = load_taelrik()

    glossary = [
        _glossary_entry(),
        GlossaryEntry(
            id="g-dhaer",
            text="dhaer",
            language="taelrik",
            kind="word",
            meaning="",
            origin=GlossaryOrigin(by="owner"),
        ),
        GlossaryEntry(
            id="g-curse-dup",
            text="rhok tal’dun",
            language="taelrik",
            kind="word",
            meaning="duplicate of the curse phrase",
            origin=GlossaryOrigin(by="owner"),
        ),
    ]

    lexicon = build_scene_lexicon([taelrik], glossary)

    dhaer = next(e for e in lexicon if e.id == "glossary:g-dhaer")
    assert dhaer.translation == "ford, river crossing"

    # the glossary duplicate would qualify as its own highlight candidate
    # on its own merits...
    assert can_highlight("rhok tal’dun") is True
    # ...but the phrase (added first, same culture) wins the dedupe, so the
    # glossary duplicate of the exact same text never shows up as a second
    # entry.
    matching = [e for e in lexicon if e.text.lower().startswith("rhok tal")]
    assert len(matching) == 1
    assert matching[0].id == "phrase:taelrik:curse-rot"


def test_lexicon_usage_always_from_matching_dictionary_entry():
    """Ruling R6: `usage` comes from the matching dictionary entry's
    `notes` whenever one exists, even when the glossary entry already has
    its own `meaning` (only `translation` prefers the glossary's own
    `meaning` over the dictionary's)."""

    language = Language(
        name="Taelrik Variant",
        level="naming",
        dictionary=[
            DictionaryEntry(word="dhaer", meaning="ford", notes="formal register"),
        ],
    )
    culture = Culture(id="taelrik2", name="Taelrik Variant", language=language)

    entry = GlossaryEntry(
        id="g-dhaer2",
        text="dhaer",
        language="taelrik2",
        kind="word",
        meaning="a specific crossing near the mill",
        origin=GlossaryOrigin(by="owner"),
    )

    [lexicon_entry] = build_scene_lexicon([culture], [entry])
    assert lexicon_entry.translation == "a specific crossing near the mill"
    assert lexicon_entry.usage == "formal register"


def _letters_suffix(i: int) -> str:
    """A 4-letter, lowercase, digit-free suffix unique per `i` (base-26)."""

    alphabet = "abcdefghijklmnopqrstuvwxyz"
    chars = []
    for _ in range(4):
        chars.append(alphabet[i % 26])
        i //= 26
    return "".join(chars)


def test_lexicon_cap():
    language = Language(name="Many Words", level="naming")
    culture = Culture(id="many", name="Many", color="#123456", language=language)

    glossary = [
        GlossaryEntry(
            id=f"g-{i}",
            text=f"zorquelin{_letters_suffix(i)}",
            language="many",
            kind="word",
            origin=GlossaryOrigin(by="owner"),
        )
        for i in range(2000)
    ]

    taelrik = load_taelrik()
    lexicon = build_scene_lexicon([taelrik, culture], glossary)

    assert len(lexicon) == MAX_LEXICON_ENTRIES
    phrase_count = len(taelrik.language.phrases)
    assert all(
        entry.id.startswith("phrase:taelrik:") for entry in lexicon[:phrase_count]
    )
