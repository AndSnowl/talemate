"""Cleaning names in a group's "+ Add" draft (languages 4a, Task 8): each
drafted row's name and line are cleaned in the page's languages, and
accepting saves the new names as words."""

import pytest

import talemate.config.state as config_state
from conftest import MockClient, MockClientContext
from talemate.languages.entry import fields_of
from talemate.languages.models import GeneratorDef, Language
from talemate.world.store import Source
from talemate.worldplay.cleaning import clean_group_draft
from talemate.worldplay.groups import GroupAddDraft, GroupAddRow

PLACES = ["Zizhigrad", "Sovyetsk", "Lezhograd"]
MOSCAVIAN = Language(
    name="Moscavian",
    level="naming",
    categories={"C": "k", "V": "a"},
    generators=[
        GeneratorDef(
            id="places", name="Places", use="place", patterns=[f"[{'|'.join(PLACES)}]"]
        )
    ],
)


@pytest.fixture(autouse=True)
def shipped_lists():
    saved = config_state.get_config().name_lists
    config_state.get_config().name_lists = None
    yield
    config_state.get_config().name_lists = saved


@pytest.fixture
def setup(world):
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing(
            "language", {"name": "Moscavian", **fields_of(MOSCAVIAN)}
        )
        page = rev.create_thing(
            "place",
            {"name": "Sorau", "languages": [{"language": lid, "role": "official"}]},
        )
    return lid, page


def _draft(page):
    return GroupAddDraft(
        thing_id=page,
        tag="town",
        prompt="its towns",
        rows=[
            GroupAddRow(
                name="Novgorod",
                kind="place",
                tag="town",
                line="Novgorod trades in furs.",
            )
        ],
    )


async def test_group_add_marks_its_rows(world, setup):
    lid, page = setup
    async with MockClientContext():
        cleaned = await clean_group_draft(world, _draft(page), MockClient("t"))
    [row] = cleaned.rows
    assert (row.name, row.line) == ("Novgorod", "Novgorod trades in furs.")
    assert [(m.name, m.language_id) for m in cleaned.marks] == [("Novgorod", lid)]
