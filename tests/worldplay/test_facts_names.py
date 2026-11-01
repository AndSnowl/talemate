"""Ruling H8: "+ Add facts" and "+ Add event" ask for the new names their
facts use, as create-thing does, and accept makes the stubs and links
them in the same revision as the facts."""

import json

import pytest

from talemate.world.dates import WorldDate
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay import facts
from talemate.worldplay.create import CreatePreview, PreviewFact, accept_preview
from talemate.worldplay.links import NewName

from conftest import MockClient, MockClientContext, client_responses

TSARDOM = "Tsardom of Moscavia"


@pytest.fixture
def realm(world):
    """Present 1004: the Tsardom of Moscavia (a place, tagged country)
    with Novogrudok, its capital, filed in it."""

    world.set_present(WorldDate.of(1004))
    with world.revision(Source.manual(note="realm")) as rev:
        tsardom = rev.create_thing("place", {"name": TSARDOM, "tag": "country"})
        rev.add_fact(tsardom, "general", "A vast northern realm of owl-folk.")
        city = rev.create_thing(
            "place",
            {
                "name": "Novogrudok",
                "tag": "capital",
                "filings": [{"target": tsardom, "role": None}],
            },
        )
    world.tsardom, world.city = tsardom, city
    return world


def _names(world) -> set[str]:
    view = world.view()
    return {view.name_of(t.id) for t in view.things()}


def _reply(*texts: str, names: list[dict] | None = None) -> str:
    out: dict = {"facts": [{"category": "general", "text": t} for t in texts]}
    if names is not None:
        out["names"] = names
    return json.dumps(out)


TSAR_FACTS = (
    "The current Tsar is Tsar Ivan III, crowned in Novogrudok in 998.",
    "Ivan III took the throne after his father, Tsar Alexei II, died.",
)
TSAR_NAMES = [
    {"name": "Tsar Ivan III", "kind": "character", "tag": "ruler", "in": TSARDOM},
    {"name": "Tsar Alexei II", "kind": "character", "tag": "ruler", "in": None},
    # a title on its own and an office are never stubs (ruling F5)
    {"name": "the Tsar", "kind": "office", "tag": "title", "in": None},
    {"name": "High Chancellor", "kind": "lore", "tag": "office", "in": None},
    # a name the world has links, and one the facts don't use is dropped
    {"name": "Novogrudok", "kind": "place", "tag": "capital", "in": TSARDOM},
    {"name": "Velikoye", "kind": "place", "tag": "city", "in": None},
]


async def test_add_facts_prompt_asks_for_names_as_create_does(realm):
    client = MockClient("test")
    async with MockClientContext():
        client_responses.get().append(_reply("It is cold."))
        await facts.draft_facts(realm, realm.tsardom, "the current Tsar", client)
    prompt = str(client.prompt_history[-1]["prompt"])
    assert (
        '"names": [{"name": "...", "kind": "place", "tag": "...", "in": null,'
        ' "aka": []}]' in prompt
    )
    assert '- "names": after the facts, every proper name your facts use' in prompt
    assert "Only named things become entries." in prompt


async def test_add_event_prompt_asks_for_names(realm):
    client = MockClient("test")
    async with MockClientContext():
        client_responses.get().append(_reply("It was founded."))
        await facts.draft_facts(realm, realm.tsardom, "its founding", client, year=612)
    prompt = str(client.prompt_history[-1]["prompt"])
    assert '- "names": after the facts, every proper name your facts use' in prompt


async def test_draft_lists_the_new_names_its_facts_use(realm):
    draft = await facts.draft_facts(
        realm,
        realm.tsardom,
        "the current Tsar",
        None,
        reply=_reply(*TSAR_FACTS, names=TSAR_NAMES),
    )
    rows = {n.name: n for n in draft.new_names}
    assert list(rows) == ["Tsar Ivan III", "Tsar Alexei II"]
    ivan = rows["Tsar Ivan III"]
    assert (ivan.kind, ivan.tag, ivan.ticked) == ("character", "ruler", True)
    # its "in" is this entry
    assert ivan.filing is not None and ivan.filing.this_entry
    assert rows["Tsar Alexei II"].filing is None
    # nothing is written
    assert _names(realm) == {TSARDOM, "Novogrudok"}


async def test_accept_makes_the_stubs_and_links_them_in_one_revision(realm):
    draft = await facts.draft_facts(
        realm,
        realm.tsardom,
        "the current Tsar",
        None,
        reply=_reply(*TSAR_FACTS, names=TSAR_NAMES),
    )
    head = realm.head_rev()
    written = facts.accept_facts(realm, draft)
    assert realm.head_rev() == head + 1
    view = realm.view()
    by_name = {view.name_of(t.id): t for t in view.things()}
    ivan, alexei = by_name["Tsar Ivan III"], by_name["Tsar Alexei II"]
    assert ivan.is_stub and ivan.kind == "character"
    assert ivan.fields.get("tag") == "ruler"
    # filed where the reply's "in" said: this entry
    assert [f["target"] for f in ivan.fields.get("filings") or []] == [realm.tsardom]
    assert "the Tsar" not in by_name and "High Chancellor" not in by_name
    texts = [f.text for f in view.thing(realm.tsardom).facts if f.fact_id in written]
    assert texts[0] == (
        f"The current Tsar is {ref(ivan.id, 'Tsar Ivan III')}, crowned in "
        f"{ref(realm.city, 'Novogrudok')} in 998."
    )
    assert ref(alexei.id, "Tsar Alexei II") in texts[1]
    # the second fact's "Ivan III" links him too, as a create's facts do
    assert ivan.id in parse_refs(texts[1])

    # and the one revision undoes exactly
    realm.undo([head + 1])
    view = realm.view()
    assert _names(realm) == {TSARDOM, "Novogrudok"}
    assert len(view.thing(realm.tsardom).facts) == 1


async def test_accept_skips_unticked_names_and_names_of_unticked_facts(realm):
    draft = await facts.draft_facts(
        realm,
        realm.tsardom,
        "the current Tsar",
        None,
        reply=_reply(*TSAR_FACTS, names=TSAR_NAMES),
    )
    draft.new_names[1].ticked = False
    draft.facts[1].ticked = False
    facts.accept_facts(realm, draft)
    view = realm.view()
    names = [view.name_of(t.id) for t in view.things()]
    assert "Tsar Alexei II" not in names and "Tsar Ivan III" in names

    draft = await facts.draft_facts(
        realm,
        realm.tsardom,
        "the old Tsar",
        None,
        reply=_reply(
            "Tsar Boris I built the walls.",
            names=[{"name": "Tsar Boris I", "kind": "character", "tag": "ruler"}],
        ),
    )
    draft.new_names[0].ticked = False
    (fact_id,) = facts.accept_facts(realm, draft)
    view = realm.view()
    assert "Tsar Boris I" not in [view.name_of(t.id) for t in view.things()]
    (fact,) = [f for f in view.thing(realm.tsardom).facts if f.fact_id == fact_id]
    assert fact.text == "Tsar Boris I built the walls."


async def test_accept_rechecks_the_names_the_client_sent(realm):
    """The rows come back from the page: a name retagged as a title makes
    no stub (ruling F5), nor does one the facts don't write, nor one
    written only in lowercase (ruling F26: the owner selected nothing)."""

    draft = await facts.draft_facts(
        realm,
        realm.tsardom,
        "the court",
        None,
        reply=_reply(
            "The Grand Vizier serves the Tsar beside the bells of dawn.",
            names=[
                {"name": "Grand Vizier", "kind": "lore", "tag": "council"},
                {"name": "bells of dawn", "kind": "item", "tag": "bell"},
            ],
        ),
    )
    # a name the facts write only in lowercase is no new name
    assert [n.name for n in draft.new_names] == ["Grand Vizier"]
    draft.new_names.append(
        facts.DraftName(name="bells of dawn", kind="item", tag="bell")
    )
    draft.new_names[0].tag = "title"
    draft.new_names.append(
        facts.DraftName(name="Prince Yaroslav", kind="character", tag="heir")
    )
    head = realm.head_rev()
    facts.accept_facts(realm, draft)
    assert realm.head_rev() == head + 1
    assert _names(realm) == {TSARDOM, "Novogrudok"}


async def test_draft_facts_for_adds_new_names_to_the_draft(realm):
    preview = CreatePreview(
        kind="lore",
        prompt="the guard",
        name="White Talon Guard",
        facts=[PreviewFact(category="general", text="It guards Tsar Ivan III.")],
        prose={},
        new_names=[NewName(name="Tsar Ivan III", kind="character", tag="ruler")],
    )
    added = await facts.draft_facts_for(
        realm,
        preview,
        "its drills",
        None,
        reply=_reply(
            "The White Talon Guard drills on the Field of Talons for Tsar Ivan III.",
            names=[
                {"name": "Field of Talons", "kind": "place", "tag": "field"},
                {"name": "Tsar Ivan III", "kind": "character", "tag": "ruler"},
                {"name": "White Talon Guard", "kind": "lore", "tag": "regiment"},
            ],
        ),
    )
    # only the name the draft doesn't hold yet, never its own name
    assert [n.name for n in added.new_names] == ["Field of Talons"]
    assert [f.text for f in added.facts] == [
        "The White Talon Guard drills on the Field of Talons for Tsar Ivan III."
    ]
    preview.facts.extend(added.facts)
    preview.new_names.extend(added.new_names)
    head = realm.head_rev()
    thing_id = accept_preview(realm, preview)
    assert realm.head_rev() == head + 1
    view = realm.view()
    field = next(t for t in view.things() if view.name_of(t.id) == "Field of Talons")
    assert field.is_stub
    texts = [f.text for f in view.thing(thing_id).facts]
    assert any(ref(field.id, "Field of Talons") in t for t in texts)


async def test_add_facts_prompt_has_create_s_tag_rule(realm):
    """Ruling H9: the names' tags follow create-thing's tag rule, copied
    verbatim; the kind-name line only for a lore or event entry."""

    client = MockClient("test")
    async with MockClientContext():
        client_responses.get().append(_reply("It is cold."))
        await facts.draft_facts(realm, realm.tsardom, "the current Tsar", client)
    prompt = str(client.prompt_history[-1]["prompt"])
    assert (
        '- "tag": one or two words for what the place is, such as river, ruler,'
        " custom, institution, regiment, capital or doctrine." in prompt
    )
    assert "kind's own name" not in prompt
    with realm.revision(Source.manual(note="lore")) as rev:
        rite = rev.create_thing("lore", {"name": "Rite of First Flight"})
    async with MockClientContext():
        client_responses.get().append(_reply("It is old."))
        await facts.draft_facts(realm, rite, "its origin", client)
    prompt = str(client.prompt_history[-1]["prompt"])
    assert (
        "The tag is never the kind's own name (lore, event, place, …): say what"
        " sort of lore it is, such as custom, law, battle, festival." in prompt
    )


async def test_add_facts_prompt_carries_it_too(realm):
    """4a revised: the narrator rule reaches "+ Add facts" as well."""

    from talemate.languages.entry import fields_of
    from talemate.languages.models import Language

    with realm.revision(Source.manual()) as rev:
        rev.create_thing(
            "language",
            {
                "name": "Otsyenyan",
                **fields_of(Language(name="Otsyenyan", level="description")),
            },
        )
    client = MockClient("test")
    async with MockClientContext():
        client_responses.get().append(_reply("It is cold."))
        await facts.draft_facts(realm, realm.tsardom, "the current Tsar", client)
    prompt = str(client.prompt_history[-1]["prompt"])
    assert "Titles and descriptions stay English" in prompt
    assert "Otsyenyan is a language, not a thing" in prompt
