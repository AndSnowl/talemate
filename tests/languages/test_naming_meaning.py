"""Names from a meaning or an entry's facts, built by the engine
(languages 4b-1, Task 6; probe 4b-1's reading of the English)."""

import pytest

from conftest import MockClient, MockClientContext, client_responses
from talemate.languages.entry import fields_of, language_of
from talemate.languages.models import (
    DictionaryEntry,
    FormChange,
    GeneratorDef,
    Language,
    NameGrammar,
    NamePart,
    NameShape,
    OfRule,
)
from talemate.languages.name_grammar import MeaningPhrase
from talemate.languages.naming import translate_text
from talemate.languages.naming_meaning import (
    give_meaning,
    read_english,
    suggest_phrases,
)
from talemate.world.store import Source

OWL_PARTS = [
    NamePart(kind="rule", rule="men"),
    NamePart(kind="word", word="Ul"),
    NamePart(kind="meaning", forms=["more_than_one"], hint="something in the sky"),
]
VAROVNI = Language(
    name="Varovni",
    level="full",
    categories={"C": "k v d z", "V": "a e i o u"},
    generators=[
        GeneratorDef(id="words", name="Words", use="words", patterns=["CVCV"]),
        GeneratorDef(
            id="men", name="Men's names", use="character", patterns=["[dorvak|zemol]"]
        ),
        GeneratorDef(
            id="owl",
            name="Owl-names",
            use="character",
            shapes=[NameShape(parts=OWL_PARTS)],
        ),
    ],
    dictionary=[
        DictionaryEntry(word="zvesk", meanings=["star"], part="noun"),
        DictionaryEntry(word="ulkha", meanings=["owl"], part="noun"),
        DictionaryEntry(word="ilvo", meanings=["white"], part="adjective"),
    ],
    name_grammar=NameGrammar(
        describing="before",
        of=OfRule(text="ul", word_side="before"),
        the=[FormChange(kind="ending", text="ek")],
        more_than_one=[
            FormChange(when="after_vowel", kind="ending", text="ni"),
            FormChange(kind="ending", text="i"),
        ],
    ),
)


@pytest.fixture
def varovni(world):
    with world.revision(Source.manual()) as rev:
        return rev.create_thing("language", {"name": "Varovni", **fields_of(VAROVNI)})


def test_reading_the_english():
    assert read_english("of the Stars") == MeaningPhrase(
        noun="star", of=True, the=True, more_than_one=True
    )
    assert read_english("the old grey stones") == MeaningPhrase(
        noun="stone", describing=["old", "grey"], the=True, more_than_one=True
    )
    assert read_english("white lake") == MeaningPhrase(
        noun="lake", describing=["white"]
    )
    assert read_english("Owl-of-Frost") == MeaningPhrase(noun="frost", of=True)
    assert read_english("land of owls") == MeaningPhrase(
        noun="owl", more_than_one=True, ending="land of"
    )
    assert read_english(
        "Blackwater", compound=lambda w: {"noun": "water", "describing": ["black"]}
    ) == MeaningPhrase(noun="water", describing=["black"], joined=True)


async def test_split_of_the_stars_builds_ul_zveski(world, varovni):
    found = await give_meaning(world.view(), None, varovni, "of the Stars")
    assert found["candidates"][0]["name"] == "Ul Zveski"
    star = next(
        p for p in found["candidates"][0]["built_from"] if p["meaning"] == "star"
    )
    assert star["word"] == "zvesk" and star["new"] is False


async def test_the_owners_words_win_over_the_slot(world, varovni):
    found = await give_meaning(
        world.view(), None, varovni, "white owl", rule_id="owl", pinned={0: "Dorvak"}
    )
    parts = found["parts"]
    assert parts[0]["rolls"][0]["text"] == "Dorvak"
    assert parts[2]["rolls"][0]["text"] == "Ilvo Ulkha"


async def test_a_missing_meaning_is_coined_with_options(world, varovni):
    found = await give_meaning(world.view(), None, varovni, "frost")
    part = found["candidates"][0]["built_from"][0]
    assert part["meaning"] == "frost" and part["new"] is True
    assert 2 <= len(part["options"]) <= 8 and part["options"][0] == part["word"]
    words = [e.word for e in language_of(world.view().thing(varovni)).dictionary]
    assert words == ["zvesk", "ulkha", "ilvo"]


async def test_suggest_fills_meaning_parts_from_facts():
    client = MockClient("test")
    async with MockClientContext():
        client_responses.get().append('{"noun": "Stars", "why": "a star-watcher"}')
        phrases = await suggest_phrases(
            client, VAROVNI, OWL_PARTS, ["Dorvak watches the stars every night."]
        )
    assert phrases == [None, None, MeaningPhrase(noun="star", more_than_one=True)]
    prompt = str(client.prompt_history[-1]["prompt"])
    assert "Dorvak watches the stars every night." in prompt
    assert "something in the sky" in prompt


async def test_name_in_is_grammatical():
    drassonais = Language(
        name="Drassonais",
        level="full",
        dictionary=[
            DictionaryEntry(word="blanchic", meanings=["white"], part="adjective"),
            DictionaryEntry(word="aunfoimtte", meanings=["lake"], part="noun"),
        ],
        name_grammar=NameGrammar(describing="after"),
    )
    found = await translate_text(None, drassonais, "white lake")
    assert found.name == "Aunfoimtte Blanchic"
