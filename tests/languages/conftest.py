import pytest

from talemate.world.store import World


@pytest.fixture
def world(tmp_path):
    w = World.create("Test World", root=tmp_path)
    yield w
    w.close()


from dataclasses import dataclass  # noqa: E402

from _language_test_helpers import _lang_fields, _row  # noqa: E402
from talemate.world.store import Source  # noqa: E402


@dataclass
class LangWorld:
    world: World
    ids: dict[str, str]


@pytest.fixture
def lang_world(world):
    """Moscavian, Sorauan and Old Moscavian; Sorau (a place) speaking
    Sorauan officially and Moscavian at 25%; Thornfield filed in Sorau,
    stating nothing; the Owl Synod (lore) using Old Moscavian liturgically;
    Mira, a character filed in Sorau and the Owl Synod."""

    ids: dict[str, str] = {}
    with world.revision(Source.manual()) as rev:
        for name in ("Moscavian", "Sorauan", "Old Moscavian"):
            ids[name] = rev.create_thing("language", _lang_fields(name))
        ids["Sorau"] = rev.create_thing(
            "place",
            {
                "name": "Free Provinces of Sorau",
                "languages": [
                    _row(ids["Sorauan"], "official"),
                    _row(ids["Moscavian"], "spoken", 25),
                ],
            },
        )
        ids["Thornfield"] = rev.create_thing(
            "place", {"name": "Thornfield", "filings": [{"target": ids["Sorau"]}]}
        )
        ids["Synod"] = rev.create_thing(
            "lore",
            {
                "name": "The Owl Synod",
                "languages": [_row(ids["Old Moscavian"], "liturgical")],
            },
        )
        ids["Mira"] = rev.create_thing(
            "character",
            {
                "name": "Mira",
                "filings": [{"target": ids["Sorau"]}, {"target": ids["Synod"]}],
            },
        )
    return LangWorld(world, ids)
