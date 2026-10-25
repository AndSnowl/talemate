"""Hubs round 1, P2 (feedback lines 11-12): markdown emphasis the model
writes into a fact (`*x*`, `**x**`, `_x_`) is scrubbed on every fact write
path, before names are looked for, so "*Boyar Council*" becomes a stub; a
reference's own words, a lone asterisk and arithmetic are left alone, and
prose (the scene-like text) keeps its emphasis."""

import json

from talemate.world.dates import WorldDate
from talemate.world.refs import parse_refs, ref, scrub_emphasis
from talemate.world.store import Source
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    accept_preview,
    preview_thing,
)
from talemate.worldplay.facts import FactDraft, accept_facts
from talemate.worldplay.groups import GroupAddRow, accept_group_add

from conftest import MockClient, MockClientContext, client_responses


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


def _texts(world, thing_id) -> list[str]:
    return [f.text for f in world.view().thing(thing_id).facts]


def test_scrub_emphasis_keeps_refs_and_lone_asterisks():
    """The scrub itself: emphasis goes, its words stay; a reference token,
    a lone asterisk, arithmetic and snake_case are untouched."""

    thing = "a" * 32
    assert scrub_emphasis("The *Boyar Council* sits.") == "The Boyar Council sits."
    assert scrub_emphasis("**Bold** and __bold__ and _it_.") == "Bold and bold and it."
    assert scrub_emphasis("***Both***, *a* and *b*.") == "Both, a and b."
    assert scrub_emphasis(f"*{ref(thing, 'Sir *Bob')}* rides.") == (
        f"{ref(thing, 'Sir *Bob')} rides."
    )
    assert scrub_emphasis(ref(thing, "*Odd* Name")) == ref(thing, "*Odd* Name")
    for kept in (
        "Sir *Bob of the Ford.",
        "Two*three*four is twenty-four.",
        "A * B * C, in the runic sums.",
        "The snake_case_word stays.",
        "Five * marks.",
    ):
        assert scrub_emphasis(kept) == kept


async def test_emphasis_scrubbed_from_facts(world):
    """Create accept (facts, summary and elsewhere), facts from a prompt,
    a group's add lines: each writes its facts without emphasis."""

    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="river")) as rev:
        river = rev.create_thing("place", {"name": "Khorol River", "tag": "river"})
        rev.add_fact(river, "general", "A river.")
    reply = {
        "name": "Velikoye",
        "tag": "city",
        "summary": "The *great* northern capital.",
        "facts": [
            {"category": "general", "text": "Velikoye is **cold** and _proud_."},
            {"category": "general", "text": "Its walls are *very* old."},
        ],
        "names": [],
        "elsewhere": [
            {"entry": "Khorol River", "text": "The river is *frozen* in winter."}
        ],
    }
    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps(reply))
        preview = await preview_thing(
            world, "place", "Velikoye, on the Khorol River", {}, client
        )
    # the draft shows them scrubbed already
    assert [f.text for f in preview.facts] == [
        "Velikoye is cold and proud.",
        "Its walls are very old.",
    ]
    assert preview.summary == "The great northern capital."
    assert [e.text for e in preview.elsewhere] == ["The river is frozen in winter."]
    # an owner's edit on the draft that writes emphasis is scrubbed on accept
    preview.facts[1].text = "Its walls are *very* old."
    city = accept_preview(world, preview)
    assert set(_texts(world, city)) == {
        "The great northern capital.",
        "Velikoye is cold and proud.",
        "Its walls are very old.",
    }
    assert "The river is frozen in winter." in _texts(world, river)

    accept_facts(
        world,
        FactDraft(
            thing_id=river,
            prompt="more",
            facts=[PreviewFact(category="general", text="Barges *crawl* on it.")],
        ),
    )
    assert "Barges crawl on it." in _texts(world, river)

    [made] = accept_group_add(
        world,
        city,
        [GroupAddRow(name="Lower Market", kind="place", line="A **busy** market.")],
    )
    assert _texts(world, made) == ["A busy market."]


async def test_emphasis_hid_names_now_found(world):
    """The acceptance session's "*Boyar Council*" and "*Obscheinye
    Sobraniye*": with the emphasis scrubbed first, both names become stubs
    their facts link, and no asterisk is left around either link."""

    world.set_present(WorldDate.of(1000))
    reply = {
        "name": "Tsardom of Moscavia",
        "tag": "nation",
        "facts": [
            {
                "category": "general",
                "text": "The Tsar rules with the *Boyar Council* at his side.",
            },
            {
                "category": "general",
                "text": "Each village sends elders to the **Obscheinye Sobraniye**.",
            },
        ],
        "names": [
            {"name": "*Boyar Council*", "kind": "lore", "tag": "council", "in": None},
            {"name": "Obscheinye Sobraniye", "kind": "lore", "tag": "assembly"},
        ],
    }
    client = MockClient("test")
    async with MockClientContext():
        _queue(json.dumps(reply))
        preview = await preview_thing(world, "place", "The Tsardom", {}, client)
    assert sorted(n.name for n in preview.new_names) == [
        "Boyar Council",
        "Obscheinye Sobraniye",
    ]
    tsardom = accept_preview(world, preview)
    view = world.view()
    texts = _texts(world, tsardom)
    assert not any("*" in text for text in texts)
    linked = {view.name_of(t) for text in texts for t in parse_refs(text)}
    assert linked == {"Boyar Council", "Obscheinye Sobraniye"}
    for thing_id in parse_refs(" ".join(texts)):
        assert view.thing(thing_id).is_stub


async def test_scene_text_keeps_emphasis(world):
    """Prose is the writer's own, as scene text is: a draft's prose keeps
    its emphasis through accept (cached as written), while its facts lose
    theirs; and the scrub is only called on the fact paths."""

    world.set_present(WorldDate.of(1000))
    preview = CreatePreview(
        kind="place",
        prompt="a ford",
        name="Cairn Ford",
        facts=[PreviewFact(category="general", text="The ford is *shallow*.")],
        prose={"description": "The ford is *shallow*, and **cold**."},
    )
    thing_id = accept_preview(world, preview)
    assert _texts(world, thing_id) == ["The ford is shallow."]
    cached = world.prose().get(thing_id, "description", None)
    assert cached.text == "The ford is *shallow*, and **cold**."


def test_scrub_emphasis_keeps_a_stray_placeholder():
    """Task 2 follow-up: text that already holds the scrub's private-use
    placeholder, with a number no reference stands for, is kept as it is
    rather than raising."""

    stray = "7 and *this*"
    assert scrub_emphasis(stray) == "7 and this"
    thing = "b" * 32
    assert scrub_emphasis(f"3 {ref(thing, 'X')}") == (f"3 {ref(thing, 'X')}")
