"""Same thing? before anything new (curation Task 6): the preview offers
the entries a new entry or stub could be the same as, the model's verdict
for the entry as a hint (only when both sides have facts), and accept can
put the new material onto the existing entry instead.

The verdict replies are Skyfall's from the curation probe
(docs/superpowers/probes/raw/2026-10-22-curation.json, "same", pairs S1 and
S5), copied verbatim; the core reply is the probe's Tsardom promotion,
trimmed to two items."""

import json

import pytest

from talemate.world.dates import WorldDate
from talemate.world.filing import filings_of
from talemate.world.refs import parse_refs, ref
from talemate.world.store import Source
from talemate.worldplay import create, decide, prose_gen
from talemate.worldplay.create import accept_preview, preview_thing
from talemate.worldplay.decide import Verdict

from conftest import MockClient, MockClientContext, client_responses

# pair S1, run 1
VERDICT_SAME = (
    '{ "verdict": "same", "why": "A and B describe identical geographic '
    "features, historical significance, and the event of the 947 rediscovery "
    "— they are one and the same place, and A's name 'The Ashenmere "
    "Caves' is simply a more descriptive variant of the existing name "
    "'Ashenmere'.\" }"
)
# pair S5, run 0, without the prepared "{" (the reply may come either way)
VERDICT_PART = (
    ' "verdict": "part", "why": "A describes the historical event that B '
    "commemorates; the Feast of the Illumination is a celebration of the "
    'transformation described in A." }'
)

CAVES_FACTS = [
    "The Ashenmere Caves are a maze of pale limestone galleries beneath the "
    "Greymarch Mountains.",
    "Runes cover the walls of the deepest chambers, cut by the old cave-inscribers.",
    "Runeweavers mapped the upper galleries in 947.",
]
ELSEWHERE_STONEHOLD = (
    "Stonehold sends its apprentices to copy the runes of the caves each spring."
)
CREATE_CAVES = json.dumps(
    {
        "name": "The Ashenmere Caves",
        "aka": [],
        "facts": [
            {"category": "description", "text": CAVES_FACTS[0]},
            {"category": "description", "text": CAVES_FACTS[1]},
            {"category": "history", "text": CAVES_FACTS[2], "since": 947},
        ],
        "names": [{"name": "Greymarch Mountains", "kind": "place", "aka": []}],
        "elsewhere": [
            {"entry": "Stonehold", "text": ELSEWHERE_STONEHOLD, "held_by": None}
        ],
    }
)

ASHENMERE_FACTS = [
    "A vast network of limestone caves in the northern foothills, its "
    "formations the pale grey of ash.",
    "Rediscovered in 947 by runeweavers from Stonehold.",
]


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


def _prose_replies(kind: str) -> list[str]:
    return [f"Prose {n}." for n, _ in enumerate(prose_gen.sections_for(kind))]


def _make(
    world, *, stub: bool = True, ashenmere_facts: bool = True, bare_kind="lore"
) -> dict:
    """Stonehold, whose fact mentions the Ashenmere Caves (a place stub,
    with `stub`); Ashenmere, a place with facts (or, without
    `ashenmere_facts`, a bare stub of `bare_kind`); the Greymarch, a place.
    A stub's kind is a guess, so a bare stub of another kind is still a
    candidate for the place (ruling C35)."""

    world.set_present(WorldDate.of(1000))
    ids: dict = {}
    with world.revision(Source.manual(note="caves")) as rev:
        if ashenmere_facts:
            ids["ashenmere"] = rev.create_thing("place", {"name": "Ashenmere"})
            for text in ASHENMERE_FACTS:
                rev.add_fact(ids["ashenmere"], "description", text)
        else:
            ids["ashenmere"] = rev.create_thing(
                bare_kind, {"name": "Ashenmere", "stub": {"ignored": False}}
            )
        ids["greymarch"] = rev.create_thing("place", {"name": "Greymarch"})
        rev.add_fact(ids["greymarch"], "description", "A range of grey peaks.")
        ids["stonehold"] = rev.create_thing("place", {"name": "Stonehold"})
        if stub:
            ids["caves"] = rev.create_thing(
                "place", {"name": "The Ashenmere Caves", "stub": {"ignored": False}}
            )
            ids["mention"] = rev.add_fact(
                ids["stonehold"],
                "general",
                f"The weavers of Stonehold study the runes of "
                f"{ref(ids['caves'], 'the Ashenmere Caves')}.",
            )
        else:
            rev.add_fact(ids["stonehold"], "general", "A fortress of weavers.")
    return ids


async def _caves_preview(world, ids, *, verdict: str | None = VERDICT_SAME):
    client = MockClient("test")
    async with MockClientContext():
        _queue(CREATE_CAVES, *_prose_replies("place"))
        if verdict is not None:
            _queue(verdict)
        preview = await preview_thing(
            world,
            "place",
            "The Ashenmere Caves: pale limestone caves full of runes.",
            {},
            client,
            stub_id=ids.get("caves"),
        )
    return preview, client


def _texts(view, thing_id):
    state = view.thing(thing_id)
    return [view.render(fact.text) for fact in state.facts] if state else []


def _named(view, name):
    return [t for t in view.things() if view.name_of(t.id) == name]


def _analyze_calls(client):
    return [
        p
        for p in client.prompt_history
        if p["prompt"].uid == "world.same-thing"
        and p["kind"] == decide.SAME_PROMPT_KIND
    ]


# --- the preview ---------------------------------------------------------------


async def test_preview_offers_same_candidate_with_verdict(world):
    ids = _make(world)
    preview, client = await _caves_preview(world, ids)

    # the stub being filled is never its own candidate
    assert [offer.thing_id for offer in preview.same_as] == [ids["ashenmere"]]
    offer = preview.same_as[0]
    assert (offer.name, offer.kind, offer.reason) == ("Ashenmere", "place", "inside")
    assert offer.has_facts
    assert offer.line.startswith("Ashenmere (place): A vast network")

    # one verdict call, at `analyze`, after the preview's own calls
    calls = _analyze_calls(client)
    assert len(calls) == 1 and client.prompt_history[-1] is calls[0]
    prompt = str(calls[0]["prompt"])
    assert "A, the new entry: The Ashenmere Caves (place)" in prompt
    assert "B, already in the world: Ashenmere (place)" in prompt
    for text in CAVES_FACTS + ASHENMERE_FACTS:
        assert f"- {text}" in prompt

    # a hint, never a default: the owner answers
    assert preview.verdict == {
        ids["ashenmere"]: Verdict(
            verdict="same", why=json.loads(VERDICT_SAME)["why"], confidence=None
        )
    }
    # the stub row for a name the world has a candidate for: no call, new
    greymarch = next(n for n in preview.new_names if n.name == "Greymarch Mountains")
    assert [o.thing_id for o in greymarch.same_as] == [ids["greymarch"]]
    assert greymarch.same_target_id is None


async def test_no_verdict_call_when_candidate_bare_stub(world, monkeypatch):
    ids = _make(world, stub=False, ashenmere_facts=False)
    indexes = []
    real = create.name_index

    def counted(view):
        indexes.append(view)
        return real(view)

    monkeypatch.setattr(create, "name_index", counted)
    preview, client = await _caves_preview(world, ids, verdict=None)

    assert [o.thing_id for o in preview.same_as] == [ids["ashenmere"]]
    assert not preview.same_as[0].has_facts
    assert "stub" in preview.same_as[0].line
    assert preview.verdict is None
    # the stub rows' candidates come without a call either
    greymarch = next(n for n in preview.new_names if n.name == "Greymarch Mountains")
    assert [o.thing_id for o in greymarch.same_as] == [ids["greymarch"]]
    assert greymarch.same_as[0].has_facts
    assert _analyze_calls(client) == []
    # one name index for the entry and every stub row
    assert len(indexes) == 1


async def test_same_thing_reads_reply_shapes(world):
    ids = _make(world)
    client = MockClient("test")
    label = decide.preview_label("The Illumination", "lore")
    async with MockClientContext():
        _queue(VERDICT_PART, '{"verdict": "maybe", "why": "unsure"}', "")
        part = await decide.same_thing(
            world, label, ["The world changed in 994."], ids["ashenmere"], client
        )
        unknown = await decide.same_thing(
            world, label, ["The world changed in 994."], ids["ashenmere"], client
        )
        empty = await decide.same_thing(
            world, label, ["The world changed in 994."], ids["ashenmere"], client
        )
        # a candidate with no facts, or a preview with none: no call
        bare = await decide.same_thing(
            world, label, ["The world changed in 994."], ids["caves"], client
        )
        none = await decide.same_thing(world, label, [], ids["ashenmere"], client)
    assert part is not None and part.verdict == "part"
    assert part.why.startswith("A describes the historical event")
    assert unknown is None and empty is None
    assert bare is None and none is None
    assert len(client.prompt_history) == 3


# --- accept --------------------------------------------------------------------


async def test_accept_into_same_target_adds_facts_and_aka(world):
    ids = _make(world)
    preview, _client = await _caves_preview(world, ids)
    preview.facts[1].ticked = False
    head = world.head_rev()
    things = len(list(world.view().things()))

    thing_id = accept_preview(world, preview, same_target_id=ids["ashenmere"])

    assert thing_id == ids["ashenmere"]
    # one revision
    assert world.head_rev() == head + 1
    view = world.view()
    # the expanded stub was re-pointed onto Ashenmere: nothing is left behind
    assert view.thing(ids["caves"]) is None
    assert _named(view, "The Ashenmere Caves") == []
    mention = next(
        f for f in view.thing(ids["stonehold"]).facts if f.fact_id == ids["mention"]
    )
    assert parse_refs(mention.text) == [ids["ashenmere"]]
    # the ticked facts, and only those, are additions to Ashenmere
    texts = _texts(view, ids["ashenmere"])
    assert CAVES_FACTS[0] in texts and CAVES_FACTS[2] in texts
    assert CAVES_FACTS[1] not in texts
    assert all(text in texts for text in ASHENMERE_FACTS)
    dated = next(
        f
        for f in view.thing(ids["ashenmere"]).facts
        if view.render(f.text) == CAVES_FACTS[2]
    )
    assert dated.category == "history" and dated.valid_from == WorldDate.of(947)
    # the ticked elsewhere fact went onto its own target
    assert ELSEWHERE_STONEHOLD in _texts(view, ids["stonehold"])
    # the preview's name is another name of Ashenmere
    aka = view.thing(ids["ashenmere"]).fields["aka"]
    assert {"name": "The Ashenmere Caves", "tag": "common", "everyday": False} in aka
    # the new name in the facts still became a stub, linked from Ashenmere
    (mountains,) = _named(view, "Greymarch Mountains")
    first = next(
        f
        for f in view.thing(ids["ashenmere"]).facts
        if view.render(f.text) == CAVES_FACTS[0]
    )
    assert mountains.id in parse_refs(first.text)
    # nothing else new: the stub went, the mountains came
    assert len(list(view.things())) == things

    # one undo reverses it all
    world.undo([head + 1])
    view = world.view()
    assert view.thing(ids["caves"]) is not None
    assert sorted(_texts(view, ids["ashenmere"])) == sorted(ASHENMERE_FACTS)
    assert (
        "aka" not in view.thing(ids["ashenmere"]).fields
        or not (view.thing(ids["ashenmere"]).fields["aka"])
    )


async def test_accept_same_without_stub_names_target(world):
    ids = _make(world, stub=False)
    preview, _client = await _caves_preview(world, ids)
    head = world.head_rev()

    thing_id = accept_preview(world, preview, same_target_id=ids["ashenmere"])

    assert thing_id == ids["ashenmere"] and world.head_rev() == head + 1
    view = world.view()
    assert _named(view, "The Ashenmere Caves") == []
    aka = view.thing(ids["ashenmere"]).fields["aka"]
    assert [entry["name"] for entry in aka] == ["The Ashenmere Caves"]
    # the facts read as Ashenmere's: its own name stays plain text
    first = next(
        f
        for f in view.thing(ids["ashenmere"]).facts
        if view.render(f.text) == CAVES_FACTS[0]
    )
    assert ids["ashenmere"] not in parse_refs(first.text)


async def test_accept_same_onto_a_stub_fills_it(world):
    """A bare stub the owner says the new entry is gets filled, as "fill
    the stub instead" does: its id kept, its old name another name."""

    ids = _make(world, stub=False, ashenmere_facts=False)
    preview, _client = await _caves_preview(world, ids, verdict=None)

    thing_id = accept_preview(world, preview, same_target_id=ids["ashenmere"])

    assert thing_id == ids["ashenmere"]
    state = world.view().thing(thing_id)
    assert not state.is_stub and state.kind == "place"
    assert world.view().name_of(thing_id) == "The Ashenmere Caves"
    assert "Ashenmere" in [entry["name"] for entry in state.fields["aka"]]


async def test_accept_same_target_refused_when_gone(world):
    ids = _make(world, stub=False)
    preview, _client = await _caves_preview(world, ids)
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(ids["greymarch"])
    head = world.head_rev()
    with pytest.raises(ValueError):
        accept_preview(world, preview, same_target_id=ids["greymarch"])
    assert world.head_rev() == head


async def test_stub_row_same_links_existing(world):
    ids = _make(world, stub=False)
    preview, _client = await _caves_preview(world, ids)
    row = next(n for n in preview.new_names if n.name == "Greymarch Mountains")
    row.same_target_id = ids["greymarch"]
    head = world.head_rev()

    thing_id = accept_preview(world, preview)

    assert world.head_rev() == head + 1
    view = world.view()
    # no stub made: the name links to the Greymarch
    assert _named(view, "Greymarch Mountains") == []
    first = next(
        f for f in view.thing(thing_id).facts if view.render(f.text) == CAVES_FACTS[0]
    )
    assert parse_refs(first.text) == [ids["greymarch"]]
    aka = view.thing(ids["greymarch"]).fields["aka"]
    assert [entry["name"] for entry in aka] == ["Greymarch Mountains"]


# --- the cap ---------------------------------------------------------------------


async def test_at_most_five_candidates(world):
    world.set_present(WorldDate.of(1000))
    names = [
        "Greyholm Bridge",
        "Greyholm Fen",
        "Greyholm Mill",
        "Greyholm Road",
        "Greyholm Tower",
        "Greyholm Weir",
    ]
    with world.revision(Source.manual(note="greyholm")) as rev:
        for name in names:
            thing_id = rev.create_thing("place", {"name": name})
            rev.add_fact(thing_id, "description", f"{name} stands by the water.")
        tale = rev.create_thing(
            "lore", {"name": "Greyholm", "stub": {"ignored": False}}
        )
    reply = json.dumps(
        {
            "name": "Greyholm",
            "facts": [{"category": "description", "text": "A grey town by a fen."}],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, *_prose_replies("place"))
        preview = await preview_thing(world, "place", "Greyholm, a town", {}, client)

    assert len(preview.same_as) == 5
    # the other "Greyholm", a lore stub, comes first, told apart by its
    # kind: a stub's kind is a guess, so it's offered (ruling C35)
    top = preview.same_as[0]
    assert (top.thing_id, top.kind, top.reason) == (tale, "lore", "aka")
    assert all(o.kind == "place" for o in preview.same_as[1:])
    assert len({o.line for o in preview.same_as}) == 5
    # the top candidate is a bare stub: no verdict
    assert preview.verdict is None and _analyze_calls(client) == []


def test_entry_candidates_keep_to_its_kind(world):
    """Ruling C34, as merge's C17: an entry's same-thing candidates are of
    its kind -- but
    a stub of any kind (ruling C35: a stub's kind is a guess). A stub row
    keeps every kind."""

    with world.revision(Source.manual(note="greyholm")) as rev:
        fen = rev.create_thing("place", {"name": "Greyholm Fen"})
        synod = rev.create_thing("event", {"name": "Greyholm Synod"})
        tale = rev.create_thing("lore", {"name": "Greyholm Tale"})
        reeve = rev.create_thing("character", {"name": "Greyholm Reeve"})
        saga = rev.create_thing(
            "lore", {"name": "Greyholm Saga", "stub": {"ignored": False}}
        )
    view = world.view()

    def offered(kind):
        return {
            o.thing_id
            for o in create.same_offers(view, "Greyholm", near_ids=[], kind=kind)
        }

    assert offered(None) == {fen, synod, tale, reeve, saga}
    assert offered("place") == {fen, saga}
    assert offered("event") == {synod, saga}
    assert offered("lore") == {tale, saga}
    assert offered("character") == {reeve, saga}

    row = create.NewName(name="Greyholm", kind="place")
    create.offer_same(view, [row], near_ids=[])
    assert {o.thing_id for o in row.same_as} == {fen, synod, tale, reeve, saga}


async def test_place_preview_offers_a_same_named_lore_stub(world):
    """Ruling C35 (the re-review's case): writing the place "Ashenmere"
    while a lore stub "Ashenmere" exists offers that stub, so the owner
    can fill it rather than leave a duplicate and a dangling stub; saying
    yes fills it, its id kept, as a place."""

    ids = _make(world, stub=False, ashenmere_facts=False)
    assert world.view().thing(ids["ashenmere"]).kind == "lore"
    preview, _client = await _caves_preview(world, ids, verdict=None)
    [offer] = preview.same_as
    assert (offer.thing_id, offer.kind, offer.stub) == (ids["ashenmere"], "lore", True)

    thing_id = accept_preview(world, preview, same_target_id=ids["ashenmere"])
    assert thing_id == ids["ashenmere"]
    state = world.view().thing(thing_id)
    assert state.kind == "place" and not state.is_stub


# --- fix round 1 -----------------------------------------------------------------


def _faith(world, ids) -> str:
    """The Ashen Faith, lore written with the religion hint, and one
    belief."""

    with world.revision(Source.manual(note="faith")) as rev:
        faith = rev.create_thing(
            "lore", {"name": "The Ashen Faith", "hint": "religion"}
        )
        ids["fast"] = rev.add_fact(faith, "belief", "The faithful fast at dusk.")
    ids["faith"] = faith
    return faith


async def test_expanded_stub_onto_stub_target_folds(world):
    ids = _make(world, stub=True, ashenmere_facts=False)
    preview, _client = await _caves_preview(world, ids, verdict=None)
    head = world.head_rev()

    thing_id = accept_preview(world, preview, same_target_id=ids["ashenmere"])

    assert thing_id == ids["caves"] and world.head_rev() == head + 1
    view = world.view()
    assert view.thing(ids["ashenmere"]) is None
    caves = view.thing(ids["caves"])
    assert not caves.is_stub and caves.kind == "place"
    assert view.name_of(ids["caves"]) == "The Ashenmere Caves"
    assert "Ashenmere" in [e["name"] for e in caves.fields["aka"]]
    assert CAVES_FACTS[0] in _texts(view, ids["caves"])


def _keth(world, ids, *, color="grey"):
    with world.revision(Source.manual(note="keth")) as rev:
        ids["keth"] = rev.create_thing(
            "character",
            {
                "name": "Keth",
                "color": color,
                "filings": [{"target": ids["faith"], "role": "member"}],
            },
        )
        rev.add_fact(ids["keth"], "background", "A weaver of Stonehold.")


def _keth_preview(ids):
    return create.CreatePreview(
        kind="character",
        prompt="Keth of Ashenmere",
        fields={"born": WorldDate.of(970), "color": "red"},
        name="Keth of Ashenmere",
        facts=[create.PreviewFact(category="background", text="Reads old runes.")],
        prose={},
        aka=[{"name": "Old Keth", "tag": "common", "everyday": False}],
        filings=[
            # the target is filed in the faith already: not twice
            create.PreviewFiling(
                target_id=ids["faith"],
                target_name="The Ashen Faith",
                role="priest",
                exceptions=[
                    create.PreviewException(
                        text="Keth eats at dusk all the same.",
                        item="The faithful fast at dusk.",
                        fact_id=ids["fast"],
                    )
                ],
                ticked=True,
            ),
            create.PreviewFiling(
                target_id=ids["stonehold"],
                target_name="Stonehold",
                role="weaver",
                ticked=True,
            ),
        ],
    )


async def test_accept_same_carries_entry_material(world):
    ids = _make(world, stub=False)
    _faith(world, ids)
    _keth(world, ids)
    notes: list[str] = []
    prose: list[str] = []

    accept_preview(
        world, _keth_preview(ids), same_target_id=ids["keth"], notes=notes, prose=prose
    )

    view = world.view()
    keth = view.thing(ids["keth"])
    # the new filing; the one it had already kept, never doubled
    assert [(f.target, f.role) for f in filings_of(view, ids["keth"])] == [
        (ids["faith"], "member"),
        (ids["stonehold"], "weaver"),
    ]
    assert "ties" not in keth.fields
    exception = next(f for f in keth.facts if f.category == "ties")
    assert exception.origin["tie"] == ids["faith"]
    assert exception.origin["rejects_fact"] == ids["fast"]
    # an empty field filled, a conflicting one kept and noted
    assert keth.fields["born"] == WorldDate.of(970)
    assert keth.fields["color"] == "grey"
    assert any("color" in note for note in notes)
    names = [e["name"] for e in keth.fields["aka"]]
    assert "Keth of Ashenmere" in names and "Old Keth" in names
    assert ids["keth"] in prose


async def test_accept_same_redo(world):
    ids = _make(world)
    preview, _client = await _caves_preview(world, ids)
    head = world.head_rev()
    accept_preview(world, preview, same_target_id=ids["ashenmere"])
    after = sorted(_texts(world.view(), ids["ashenmere"]))

    undone = world.undo([head + 1])
    assert world.view().thing(ids["caves"]) is not None
    world.undo([undone.undo_rev])

    view = world.view()
    assert view.thing(ids["caves"]) is None
    assert sorted(_texts(view, ids["ashenmere"])) == after


async def test_accept_same_deleted_stub_says_so(world):
    ids = _make(world, ashenmere_facts=False)
    preview, _client = await _caves_preview(world, ids, verdict=None)
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(ids["caves"])
    with pytest.raises(ValueError, match="the stub this preview expands is gone"):
        accept_preview(world, preview, same_target_id=ids["ashenmere"])


async def test_treated_as_new_names_get_no_candidates(world):
    ids = _make(world, stub=False)
    client = MockClient("test")
    async with MockClientContext():
        _queue(CREATE_CAVES, *_prose_replies("place"), VERDICT_SAME)
        preview = await preview_thing(
            world,
            "place",
            "The Ashenmere Caves under the Greymarch Mountains",
            {},
            client,
            new_names=["Greymarch Mountains"],
        )
    row = next(n for n in preview.new_names if n.name == "Greymarch Mountains")
    assert row.same_as == []
    assert ids["greymarch"]


# --- fix round 2 -----------------------------------------------------------------


async def test_fold_recategorises_for_the_preview_kind(world):
    world.set_present(WorldDate.of(1000))
    with world.revision(Source.manual(note="kethstubs")) as rev:
        keth = rev.create_thing(
            "lore", {"name": "Keth the Weaver", "stub": {"ignored": False}}
        )
        old = rev.create_thing("lore", {"name": "Keth", "stub": {"ignored": False}})
        rev.add_fact(old, "general", "Keth was seen at Stonehold.")
    preview = create.CreatePreview(
        kind="character",
        prompt="Keth the Weaver",
        name="Keth the Weaver",
        facts=[create.PreviewFact(category="background", text="Weaves runes.")],
        prose={},
        stub_id=keth,
    )

    thing_id = accept_preview(world, preview, same_target_id=old)

    view = world.view()
    assert thing_id == keth and view.thing(old) is None
    state = view.thing(keth)
    assert state.kind == "character" and not state.is_stub
    moved = next(f for f in state.facts if "seen at Stonehold" in f.text)
    assert moved.category == "background"


async def test_fold_undo(world):
    ids = _make(world, stub=True, ashenmere_facts=False)
    preview, _client = await _caves_preview(world, ids, verdict=None)
    head = world.head_rev()
    accept_preview(world, preview, same_target_id=ids["ashenmere"])

    world.undo([head + 1])

    view = world.view()
    assert view.thing(ids["ashenmere"]).is_stub
    assert view.thing(ids["caves"]).is_stub
    mention = next(
        f for f in view.thing(ids["stonehold"]).facts if f.fact_id == ids["mention"]
    )
    assert parse_refs(mention.text) == [ids["caves"]]


async def test_merge_tag_only_when_none(world):
    """Onto an entry the world has: the preview's tag is the target's only
    when it has none; a different one is kept, with a note."""

    ids = _make(world, stub=False)
    preview = create.CreatePreview(
        kind="place",
        prompt="the caves",
        name="Ashenmere Caverns",
        facts=[create.PreviewFact(category="description", text="Dark and deep.")],
        prose={},
        tag="cave",
    )
    accept_preview(world, preview.model_copy(), same_target_id=ids["ashenmere"])
    assert world.view().thing(ids["ashenmere"]).fields["tag"] == "cave"

    notes: list[str] = []
    again = preview.model_copy(update={"name": "Ashenmere Hollows", "tag": "hollow"})
    accept_preview(world, again, same_target_id=ids["ashenmere"], notes=notes)
    assert world.view().thing(ids["ashenmere"]).fields["tag"] == "cave"
    assert any("keeps its own tag" in note for note in notes)


async def test_merge_fields_compare_stored_forms(world):
    ids = _make(world, stub=False)
    _faith(world, ids)
    with world.revision(Source.manual(note="keth")) as rev:
        keth = rev.create_thing(
            "character", {"name": "Keth", "born": WorldDate.of(970)}
        )
        rev.add_fact(keth, "background", "A weaver.")
    preview = create.CreatePreview(
        kind="character",
        prompt="Keth",
        name="Keth of Stonehold",
        # as a preview comes back from the page: the date as JSON
        fields={"born": WorldDate.of(970).model_dump(mode="json")},
        facts=[create.PreviewFact(category="background", text="Reads runes.")],
        prose={},
    )
    notes: list[str] = []
    accept_preview(world, preview, same_target_id=keth, notes=notes)
    assert not any("born" in note for note in notes)


async def test_held_by_the_repointed_stub_is_the_target(world):
    ids = _make(world)
    preview, _client = await _caves_preview(world, ids)
    preview.facts[0].held_by = ids["caves"]

    accept_preview(world, preview, same_target_id=ids["ashenmere"])

    view = world.view()
    fact = next(
        f
        for f in view.thing(ids["ashenmere"]).facts
        if view.render(f.text) == CAVES_FACTS[0]
    )
    assert fact.origin["held_by"] == ids["ashenmere"]


async def test_row_notes_not_doubled_on_retry(world):
    ids = _make(world, stub=False)
    preview = create.CreatePreview(
        kind="place",
        prompt="caves",
        name="The Ashenmere Caves",
        facts=[
            create.PreviewFact(
                category="description",
                text="They lie beneath the Greymarch Mountains.",
            )
        ],
        prose={},
        new_names=[
            create.NewName(
                name="Greymarch Mountains",
                kind="place",
                same_target_id=ids["stonehold"],
            ),
            # listed, but no fact uses it: its stub is an orphan, and the
            # accept is written again without it
            create.NewName(name="Zzyzx", kind="lore"),
        ],
    )
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(ids["stonehold"])
    notes: list[str] = []

    accept_preview(world, preview, notes=notes)

    assert len([n for n in notes if "Greymarch Mountains" in n]) == 1
    assert _named(world.view(), "Zzyzx") == []


def _filing(target, role=None, *, within=None, exceptions=()):
    return {
        "target": target,
        "role": role,
        "since": None,
        "until": None,
        "within": within,
        "exceptions": list(exceptions),
    }


def test_accept_same_carries_the_stubs_filings_whole(world):
    """Task 4 review, M5: "Is this X?" re-points the stub it expanded onto
    X, and its filings go over whole -- the role, the `within` and the
    exceptions, mapped onto the moved copies (`repoint`'s own logic)."""

    from talemate.worldplay.create import CreatePreview

    with world.revision(Source.manual(note="weaver")) as rev:
        faith = rev.create_thing("lore", {"name": "The Loom Faith"})
        order = rev.create_thing(
            "lore", {"name": "The Order of Threads", "filings": [_filing(faith)]}
        )
        keth = rev.create_thing("character", {"name": "Keth"})
        rev.add_fact(keth, "background", "Keth weaves.")
        stub = rev.create_thing(
            "character", {"name": "the Weaver", "stub": {"ignored": False}}
        )
        doubt = rev.add_fact(stub, "ties", "Doubts the loom.", origin={"tie": faith})
        rev.set_field(
            stub,
            "filings",
            [_filing(faith, "weaver", within=order, exceptions=[doubt])],
            None,
        )
    preview = CreatePreview(
        kind="character",
        prompt="The Weaver.",
        name="the Weaver",
        facts=[],
        prose={},
        stub_id=stub,
    )
    accept_preview(world, preview, same_target_id=keth)

    view = world.view()
    assert view.thing(stub) is None
    (copy,) = [f for f in view.thing(keth).facts if f.text == "Doubts the loom."]
    (filing,) = filings_of(view, keth)
    assert (filing.target, filing.role, filing.within, filing.exceptions) == (
        faith,
        "weaver",
        order,
        [copy.fact_id],
    )


def test_same_offer_line_is_the_probes_entry_line(world):
    """Review M3: an offer's line is the filing probe's entry line
    (`create.filing_line`): kind and tag, everyday name, where it's filed
    with its role, stub, then its summary or first fact."""

    with world.revision(Source.manual(note="fen")) as rev:
        marches = rev.create_thing("place", {"name": "The Marches"})
        fen = rev.create_thing(
            "place",
            {
                "name": "Greyholm Fen",
                "tag": "fen",
                "stub": {"ignored": False},
                "aka": [{"name": "the Fen", "tag": "common", "everyday": True}],
                "filings": [{"target": marches, "role": "border of"}],
            },
        )
        rev.add_fact(fen, "description", "Reeds and mist.")
    view = world.view()
    (offer,) = create.same_offers(view, "Greyholm", near_ids=[])
    assert offer.thing_id == fen
    assert offer.line == (
        "Greyholm Fen (place, fen; usually called the Fen; in The Marches "
        "(border of); stub): Reeds and mist."
    )
