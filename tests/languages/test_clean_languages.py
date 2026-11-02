"""A draft's languages from the owner's words (languages 4a, Task 2): a
name match decides which languages; the model only gives roles and shares
(probe 4, finding 4)."""

import json

from conftest import MockClient, MockClientContext, client_responses
from talemate.languages.cleaning.languages import language_rows, named_languages


def _ids(lang_world, *names):
    return [lang_world.ids[n] for n in names]


def test_the_country_form_finds_its_language(lang_world):
    view = lang_world.world.view()
    found = named_languages(view, "Tsardom of Moscavia, a cold northern realm")
    assert found == _ids(lang_world, "Moscavian")


def test_no_language_named_means_none(lang_world):
    assert named_languages(lang_world.world.view(), "a mountain village") == []


async def test_no_language_makes_no_call(lang_world):
    client = MockClient("test")
    async with MockClientContext():
        rows = await language_rows(client, lang_world.world.view(), "a village", [])
        assert rows == []
        assert client.prompt_history == []


def test_two_languages_in_prompt_order(lang_world):
    view = lang_world.world.view()
    found = named_languages(view, "a Sorauan town where Moscavian traders winter")
    assert found == _ids(lang_world, "Sorauan", "Moscavian")


def test_old_moscavian_is_found_whole_not_as_moscavian(lang_world):
    view = lang_world.world.view()
    found = named_languages(view, "a shrine where Old Moscavian is sung")
    assert found == _ids(lang_world, "Old Moscavian")


async def test_the_model_gives_roles_and_shares(lang_world):
    ids = _ids(lang_world, "Sorauan", "Moscavian")
    reply = {
        "languages": [
            {"language": "Sorauan", "role": "spoken", "share": 0.65},
            {"language": "Moscavian", "role": "spoken", "share": 0.35},
        ]
    }
    async with MockClientContext():
        client_responses.get().append(json.dumps(reply))
        rows = await language_rows(
            MockClient("test"), lang_world.world.view(), "a border town", ids
        )
    assert rows == [
        {"language": ids[0], "role": "spoken", "share": 65},
        {"language": ids[1], "role": "spoken", "share": 35},
    ]


async def test_the_model_cannot_add_a_language(lang_world):
    ids = _ids(lang_world, "Moscavian")
    reply = {
        "languages": [
            {"language": "Moscavian", "role": "official", "share": 0.8},
            {"language": "Sorauan", "role": "trade", "share": 0.2},
        ]
    }
    async with MockClientContext():
        client_responses.get().append(json.dumps(reply))
        rows = await language_rows(
            MockClient("test"), lang_world.world.view(), "the capital", ids
        )
    assert rows == [{"language": ids[0], "role": "official"}]


async def test_an_unknown_role_becomes_spoken(lang_world):
    ids = _ids(lang_world, "Moscavian")
    reply = {"languages": [{"language": "Moscavian", "role": "royal"}]}
    async with MockClientContext():
        client_responses.get().append(json.dumps(reply))
        rows = await language_rows(
            MockClient("test"), lang_world.world.view(), "the court", ids
        )
    assert rows == [{"language": ids[0], "role": "spoken"}]


async def test_a_broken_reply_gives_even_spoken_rows(lang_world):
    ids = _ids(lang_world, "Sorauan", "Moscavian")
    async with MockClientContext():
        client_responses.get().append("not json at all")
        rows = await language_rows(
            MockClient("test"), lang_world.world.view(), "a border town", ids
        )
    assert rows == [
        {"language": ids[0], "role": "spoken", "share": 50},
        {"language": ids[1], "role": "spoken", "share": 50},
    ]
