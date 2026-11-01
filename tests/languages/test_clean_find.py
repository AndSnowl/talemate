"""Finding bad names (languages 4a, Task 3): the spots in a draft's texts,
what's protected, and the verdicts from the lists, the model's flag call,
the real-words list and the fit check."""

import json


from conftest import MockClient, MockClientContext, client_responses
from talemate.languages.cleaning.find import judge, protected_names, spots
from talemate.languages.cleaning.lists import NameLists
from talemate.languages.models import DictionaryEntry, GeneratorDef, Language
from talemate.world.store import Source

MOSCAVIAN = Language(
    name="Moscavian",
    level="full",
    flavour="russian",
    categories={"C": "k v r s l d z", "V": "a o e i"},
    generators=[
        GeneratorDef(
            id="people", name="People", use="character", patterns=["CVCV[slan|dey]"]
        ),
        GeneratorDef(
            id="places", name="Places", use="place", patterns=["CVCV[grad|vets]"]
        ),
    ],
    dictionary=[DictionaryEntry(word="sovy", meanings=["owl"])],
)


def _names(found):
    return [s.name for s in found]


def test_sentence_starts_and_months_are_not_spots(world):
    texts = ["In May the caravans leave for Novgorod. The road is long."]
    assert _names(spots(world.view(), texts, [], set())) == ["Novgorod"]


def test_title_words_stay_and_only_the_part_is_judged(world):
    found = spots(
        world.view(),
        ["Tsar Dmitri II rules."],
        [("Tsar Dmitri II", "character")],
        set(),
    )
    assert _names(found) == ["Dmitri"]
    assert found[0].full == "Tsar Dmitri II"
    assert found[0].person == "man"


def test_a_persons_name_is_judged_word_by_word(world):
    found = spots(
        world.view(),
        ["Aleksei Voronov commands."],
        [("Aleksei Voronov", "character")],
        set(),
    )
    assert [(s.name, s.part) for s in found] == [
        ("Aleksei", "given"),
        ("Voronov", "family"),
    ]


def test_kind_words_stay_on_a_place(world):
    found = spots(
        world.view(),
        ["The River Kholodnaya floods."],
        [("River Kholodnaya", "place")],
        set(),
    )
    assert _names(found) == ["Kholodnaya"]


def test_a_possessive_is_one_spot_with_its_texts(world):
    texts = ["Trade with Novgorod.", "Novgorod's walls are old."]
    found = spots(world.view(), texts, [], set())
    assert _names(found) == ["Novgorod"]
    assert found[0].texts == [0, 1]


def test_prompt_words_and_existing_entries_are_protected(world):
    with world.revision(Source.manual()) as rev:
        rev.create_thing("place", {"name": "Kolvagorsk"})
    view = world.view()
    keep = protected_names(
        view, "Tsardom of Moscavia, by Novgorod", MOSCAVIAN, ["Kiev"]
    )
    texts = ["Moscavia trades with Novgorod, Kolvagorsk, Kiev and Smolensk; sovy."]
    assert _names(spots(view, texts, [("Tsardom of Moscavia", "place")], keep)) == [
        "Smolensk"
    ]


async def test_the_lists_replace_without_asking_the_model(world):
    found = spots(world.view(), ["Trade with Novgorod."], [], set())
    client = MockClient("test")
    lists = NameLists(real=["Novgorod"])
    async with MockClientContext():
        client_responses.get().append(json.dumps({"names": []}))
        verdicts = await judge(client, found, lists, MOSCAVIAN)
        client_responses.get().clear()
    assert [(v.spot.name, v.action, v.why) for v in verdicts] == [
        ("Novgorod", "replace", "a real name, on the Real names list")
    ]


async def test_a_title_on_the_list_is_rewritten(world):
    found = spots(
        world.view(), ["The Iron Council rules."], [("Iron Council", "lore")], set()
    )
    async with MockClientContext():
        verdicts = await judge(
            MockClient("t"), found, NameLists(title=["Iron Council"]), MOSCAVIAN
        )
        client_responses.get().clear()
    # "Council" is a kind word: the spot is "Iron", the title its whole
    assert [(v.spot.full, v.action) for v in verdicts] == [("Iron Council", "rewrite")]


async def test_the_flag_call_replaces_with_its_reason(world):
    found = spots(
        world.view(), ["Velikograd is old."], [("Velikograd", "place")], set()
    )
    reply = {
        "names": [
            {"name": "Velikograd", "label": "real", "why": "Russian 'great city'"}
        ]
    }
    async with MockClientContext():
        client_responses.get().append(json.dumps(reply))
        verdicts = await judge(MockClient("t"), found, NameLists(), MOSCAVIAN)
    assert [(v.spot.name, v.action, v.why) for v in verdicts] == [
        ("Velikograd", "replace", "Russian 'great city'")
    ]


async def test_a_misfit_is_only_suspect(world):
    found = spots(
        world.view(),
        ["Aldric Moonshadow rides."],
        [("Aldric Moonshadow", "character")],
        set(),
    )
    reply = {
        "names": [
            {"name": "Aldric", "label": "ok"},
            {"name": "Moonshadow", "label": "ok"},
        ]
    }
    async with MockClientContext():
        client_responses.get().append(json.dumps(reply))
        verdicts = await judge(MockClient("t"), found, NameLists(), MOSCAVIAN)
    assert {v.action for v in verdicts} == {"suspect"}
    assert verdicts[0].why == "doesn't sound like Moscavian"


async def test_a_broken_flag_reply_still_cleans_by_the_lists(world):
    found = spots(world.view(), ["Trade with Novgorod and Velikograd."], [], set())
    async with MockClientContext():
        client_responses.get().append("garbage")
        verdicts = await judge(
            MockClient("t"), found, NameLists(real=["Novgorod"]), MOSCAVIAN
        )
    # the list still replaces; the fit check still marks the misfit
    assert [(v.spot.name, v.action) for v in verdicts] == [
        ("Novgorod", "replace"),
        ("Velikograd", "suspect"),
    ]


async def test_a_real_word_replaces(world):
    found = spots(world.view(), ["Dmitri rules."], [("Dmitri", "character")], set())
    async with MockClientContext():
        client_responses.get().append(json.dumps({"names": []}))
        verdicts = await judge(MockClient("t"), found, NameLists(), MOSCAVIAN)
    assert [(v.spot.name, v.action, v.why) for v in verdicts] == [
        ("Dmitri", "replace", "a real Russian word")
    ]


def test_an_epithet_is_not_judged(world):
    found = spots(
        world.view(),
        ["Dmitriy the Iron rules."],
        [("Dmitriy the Iron", "character")],
        set(),
    )
    assert _names(found) == ["Dmitriy"]


async def test_no_language_makes_everything_suspect_without_a_call(world):
    found = spots(world.view(), ["Trade with Novgorod."], [], set())
    client = MockClient("t")
    async with MockClientContext():
        verdicts = await judge(client, found, NameLists(real=["Novgorod"]), None)
        assert client.prompt_history == []
    assert [(v.action, v.why) for v in verdicts] == [("suspect", "no language picked")]


# --- acceptance fixes (real runs, 2026-10-30) ---------------------------------


def test_a_title_word_is_never_a_spot(world):
    """Real run: "Tsar" became "Tsemasha" everywhere."""

    found = spots(
        world.view(), ["Each spring the Tsar rides out, and the Boyar too."], [], set()
    )
    assert _names(found) == []


def test_a_roman_numeral_is_never_a_spot(world):
    found = spots(world.view(), ["Bogdan II rules, as did Bogdan III."], [], set())
    assert "II" not in _names(found) and "III" not in _names(found)


def test_institution_and_building_words_frame_a_name(world):
    """Real run: "Grand Palace of Velikigrad" and "Boyar Council" lost
    their frame words."""

    texts = ["The Grand Palace of Velikigrad and the Boyar Council."]
    found = spots(
        world.view(),
        texts,
        [("Grand Palace of Velikigrad", "place"), ("Boyar Council", "lore")],
        set(),
    )
    assert _names(found) == ["Velikigrad"]


async def test_many_names_are_flagged_in_batches(world):
    """Real run: about forty names in one flag call overran the reply."""

    names = [f"Vel{chr(97 + i)}grad" for i in range(20)]
    found = spots(
        world.view(),
        ["Roads to " + ", ".join(names) + "."],
        [(n, "place") for n in names],
        set(),
    )
    first = {"names": [{"name": n, "label": "real", "why": "x"} for n in names[:14]]}
    second = {"names": [{"name": n, "label": "real", "why": "x"} for n in names[14:]]}
    client = MockClient("t")
    async with MockClientContext():
        client_responses.get().append(json.dumps(first))
        client_responses.get().append(json.dumps(second))
        verdicts = await judge(client, found, NameLists(), MOSCAVIAN)
    assert len(client.prompt_history) == 2
    assert {v.spot.name for v in verdicts if v.action == "replace"} == set(names)


async def test_a_stock_title_label_on_an_epithet_is_only_suspect(world):
    """Real run: "known as 'The Watchful'" became "'The Tsozyegorsk Watch'"."""

    found = spots(
        world.view(), ["Zvubisha II, known as 'The Watchful,' rules."], [], set()
    )
    reply = {
        "names": [
            {"name": "Watchful", "label": "stock-title", "why": "a generic epithet"}
        ]
    }
    async with MockClientContext():
        client_responses.get().append(json.dumps(reply))
        verdicts = await judge(MockClient("t"), found, NameLists(), MOSCAVIAN)
    assert [(v.spot.name, v.action) for v in verdicts if v.spot.name == "Watchful"] == [
        ("Watchful", "suspect")
    ]


def test_a_plural_frame_name_judges_only_its_name(world):
    """Owner's run: "Duchies of the Greywash Coast" was judged as
    "Duchies of the Greywash"; plural frame and kind words frame a name
    too, and the whole form keeps them."""

    texts = ["It borders the Duchies of the Greywash Coast and the Isles of Vel."]
    found = spots(
        world.view(),
        texts,
        [("Duchies of the Greywash Coast", "place"), ("Isles of Vel", "place")],
        set(),
    )
    assert _names(found) == ["Greywash", "Vel"]
    assert found[0].full == "Duchies of the Greywash Coast"
    found = spots(
        world.view(),
        ["The Kingdoms of Ost and the Velmar Coasts."],
        [("Kingdoms of Ost", "place"), ("Velmar Coasts", "place")],
        set(),
    )
    assert _names(found) == ["Ost", "Velmar"]
