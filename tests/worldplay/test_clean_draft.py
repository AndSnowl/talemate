"""One cleaning pipeline (languages 4c, Task 5): every kind of draft (a
new entry, "+ Add facts", a group's "+ Add") goes through `clean_draft`,
and with no model, none gets the model's name check."""

import talemate.worldplay.cleaning as cleaning
from talemate.languages.entry import fields_of
from talemate.languages.models import GeneratorDef, Language
from talemate.world.store import Source
from talemate.worldplay.create import CreatePreview, PreviewFact
from talemate.worldplay.facts import FactDraft
from talemate.worldplay.groups import GroupAddDraft, GroupAddRow

LANG = Language(
    name="Moscavian",
    level="naming",
    categories={"C": "k v", "V": "a"},
    generators=[
        GeneratorDef(id="places", name="Places", use="place", patterns=["[Kava|Vaka]"])
    ],
)


def _world(world):
    with world.revision(Source.manual()) as rev:
        lid = rev.create_thing("language", {"name": "Moscavian", **fields_of(LANG)})
        sorau = rev.create_thing(
            "place",
            {"name": "Sorau", "languages": [{"language": lid, "role": "official"}]},
        )
    return sorau


async def test_every_draft_kind_marks_through_clean_draft(world, monkeypatch):
    sorau = _world(world)
    calls = []

    async def spy(world_, client, **kwargs):
        calls.append(kwargs)
        return [], kwargs.get("person")

    monkeypatch.setattr(cleaning, "clean_draft", spy)
    preview = CreatePreview(
        kind="place", prompt="a town", name="Novgorod", facts=[], prose={}
    )
    await cleaning.clean_preview(world, preview, None)
    await cleaning.clean_fact_draft(
        world,
        FactDraft(
            thing_id=sorau,
            prompt="trade",
            facts=[
                PreviewFact(category="description", text="It trades with Novgorod.")
            ],
        ),
        None,
    )
    await cleaning.clean_group_draft(
        world,
        GroupAddDraft(
            thing_id=sorau,
            tag=None,
            prompt="towns",
            rows=[GroupAddRow(name="Novgorod", kind="place", line="A town.")],
        ),
        None,
    )
    assert len(calls) == 3
    assert all("texts" in c and "listed" in c for c in calls)


async def test_with_no_model_every_draft_still_gets_the_list_checks(world):
    """The name check's lists need no model; every kind of draft gets them
    alike (a fact draft was left alone before 4c)."""

    sorau = _world(world)
    preview = CreatePreview(
        kind="place",
        prompt="a town",
        name="Sorau Market",
        facts=[PreviewFact(category="description", text="It trades with Novgorod.")],
        prose={},
    )
    page = await cleaning.clean_preview(world, preview, None)
    facts = await cleaning.clean_fact_draft(
        world,
        FactDraft(
            thing_id=sorau,
            prompt="trade",
            facts=[
                PreviewFact(category="description", text="It trades with Novgorod.")
            ],
        ),
        None,
    )
    assert any(m.name == "Novgorod" for m in page.marks)
    assert any(m.name == "Novgorod" for m in facts.marks)
