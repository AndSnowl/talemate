"""Bodies within bodies (curation Task 7, spec goal 9, ruling C10).

The White Talon is a division of the Tsar's Army, an order sphere of its
own that is part of the Tsardom. The curation probe's probe 5 took the
fallback: the model never proposed the outer body, so the owner names it
(`bodies.add_outer_body`, no model call); its default name is "<inner
part>'s parent". The entries already filed where it goes are offered to
move into it, unticked. A tie can be `within` one part of its sphere.

A create preview takes no outer body any more (Filing, Task 4); a
sphere's core, branch and Fill still do until the spheres go (Task 7).
A create preview's "In" row can be `within` a part of its target."""

import pytest

from talemate.world import spheres
from talemate.world.dates import WorldDate
from talemate.world.kinds import UNSORTED_DRAWER_ID, get_kind, validate_field
from talemate.world.store import Source
from talemate.worldplay.bodies import OuterBody, add_outer_body, outer_name
from talemate.worldplay.characters import tie_lines
from talemate.world.filing import filings_of
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    PreviewFiling,
    accept_preview,
)
from talemate.worldplay.links import NewName
from talemate.worldplay.repoint import repoint_stub
from talemate.worldplay.spheres import (
    FillPreview,
    SpherePreview,
    accept_fill,
    accept_sphere,
)

MILITARY, LAWS, LANDS = "a1a1a1a1", "b2b2b2b2", "c3c3c3c3"
ARMY = "The Tsar's Army"


def _drawer(drawer_id, type_, title):
    return {"id": drawer_id, "type": type_, "title": title}


def _tsardom(world):
    """Present 1020. The Tsardom of Moscavia, a nation sphere: the Frosted
    Wing (a lore stub, filed there since 1005) and the Kremlin Guard in
    its Governance & Military drawer, the Zakonnik in its Laws."""

    world.set_present(WorldDate.of(1020))
    ids = {}
    with world.revision(Source.manual(note="tsardom")) as rev:
        ids["tsardom"] = rev.create_thing(
            "sphere",
            {
                "name": "Tsardom of Moscavia",
                "template": "nation",
                "drawers": [
                    _drawer(MILITARY, "structure", "Governance & Military"),
                    _drawer(LAWS, "beliefs", "Laws"),
                    _drawer(LANDS, "places", "Lands"),
                ],
            },
        )
        ids["frosted"] = rev.create_thing(
            "lore", {"name": "Frosted Wing", "stub": {"ignored": False}}
        )
        rev.set_field(
            ids["frosted"],
            "part_of",
            {"sphere": ids["tsardom"], "drawer": MILITARY},
            WorldDate.of(1005),
        )
        ids["guard"] = rev.create_thing(
            "lore",
            {
                "name": "Kremlin Guard",
                "part_of": {"sphere": ids["tsardom"], "drawer": MILITARY},
            },
        )
        rev.add_fact(ids["guard"], "general", "The Tsar's own guard.")
        ids["zakonnik"] = rev.create_thing(
            "lore",
            {"name": "Zakonnik", "part_of": {"sphere": ids["tsardom"], "drawer": LAWS}},
        )
        rev.add_fact(ids["zakonnik"], "general", "The code of laws.")
    return ids


def _trooper() -> CreatePreview:
    """A character preview whose fact names the White Talon, a new name."""

    return CreatePreview(
        kind="character",
        prompt="A trooper of regiments such as the White Talon.",
        name="Ivan Petrov",
        facts=[
            PreviewFact(category="background", text="Ivan rides with the White Talon.")
        ],
        prose={},
        new_names=[NewName(name="White Talon", kind="lore")],
    )


def _in_military(ids) -> OuterBody:
    return OuterBody(
        name=ARMY,
        template="order",
        part_of={"sphere": ids["tsardom"], "drawer": MILITARY},
    )


def _named(view, name):
    found = [s for s in view.things() if view.name_of(s.id) == name]
    assert len(found) == 1, name
    return found[0]


def _row(preview, name):
    return next(n for n in preview.new_names if n.name == name)


# --- the chain ---------------------------------------------------------------


def test_add_outer_body_refuses_a_create_preview(world):
    """A create preview is filed through its "In" rows now (Filing, Task
    4): it takes no outer body."""

    ids = _tsardom(world)
    with pytest.raises(ValueError, match="In rows"):
        add_outer_body(world, _trooper(), "White Talon", _in_military(ids))


def test_outer_body_default_name():
    assert outer_name("White Talon") == "White Talon's parent"
    assert outer_name("  The  White Talon ") == "The White Talon's parent"


def test_outer_body_around_a_core_item(world):
    """A sphere's core: the White Talon item goes inside the army, and the
    army takes the item's place in the new sphere's drawer."""

    world.set_present(WorldDate.of(1020))
    preview = SpherePreview(
        kind="sphere",
        prompt="The Tsardom, with regiments such as the White Talon.",
        name="Tsardom of Moscavia",
        facts=[],
        prose={},
        template="nation",
        agent=False,
        drawers=[_drawer(MILITARY, "structure", "Military")],
        items=[
            {
                "drawer_id": MILITARY,
                "name": "White Talon",
                "text": "A regiment of winged riders.",
                "kind": "lore",
            }
        ],
    )
    preview = add_outer_body(
        world, preview, "White Talon", OuterBody(name=ARMY, template="order")
    )
    assert preview.items[0]["part_of"] == {"name": ARMY, "drawer": UNSORTED_DRAWER_ID}
    assert _row(preview, ARMY).part_of == {
        "name": "Tsardom of Moscavia",
        "drawer": MILITARY,
    }
    assert preview.refile == []
    head = world.head_rev()

    tsardom = accept_sphere(world, preview)

    assert world.head_rev() == head + 1
    view = world.view()
    army = _named(view, ARMY)
    talon = _named(view, "White Talon")
    assert army.fields["part_of"] == {"sphere": tsardom, "drawer": MILITARY}
    assert talon.fields["part_of"] == {"sphere": army.id, "drawer": UNSORTED_DRAWER_ID}
    assert [view.render(f.text) for f in talon.facts] == [
        "A regiment of winged riders."
    ]


def test_outer_body_around_a_branch_item(world):
    ids = _tsardom(world)
    preview = SpherePreview(
        kind="sphere",
        prompt="The northern Tsardom.",
        name="Northern Tsardom",
        fields={"parent": ids["tsardom"]},
        facts=[],
        prose={},
        template="nation",
        agent=False,
        split=WorldDate.of(1015),
        items=[
            {
                "drawer_id": MILITARY,
                "name": "White Talon",
                "text": "A regiment of winged riders.",
                "kind": "lore",
            }
        ],
    )
    preview = add_outer_body(
        world, preview, "White Talon", OuterBody(name=ARMY, template="order")
    )
    branch = accept_sphere(world, preview)
    view = world.view()
    army = _named(view, ARMY)
    assert army.fields["part_of"]["sphere"] == branch
    assert _named(view, "White Talon").fields["part_of"]["sphere"] == army.id


def test_outer_body_around_a_fill_item(world):
    ids = _tsardom(world)
    preview = FillPreview(
        sphere_id=ids["tsardom"],
        drawer_id=MILITARY,
        items=[
            {
                "drawer_id": MILITARY,
                "name": "White Talon",
                "text": "A regiment of winged riders.",
                "kind": "lore",
                "names": [],
                "ticked": True,
            }
        ],
    )
    preview = add_outer_body(
        world, preview, "White Talon", OuterBody(name=ARMY, template="order")
    )
    assert _row(preview, ARMY).part_of == {
        "sphere": ids["tsardom"],
        "drawer": MILITARY,
    }
    assert {r["thing_id"] for r in preview.refile} == {ids["frosted"], ids["guard"]}
    for row in preview.refile:
        row["ticked"] = row["thing_id"] == ids["frosted"]
    head = world.head_rev()

    accept_fill(
        world,
        ids["tsardom"],
        MILITARY,
        preview.items,
        preview.elsewhere,
        new_names=preview.new_names,
        refile=preview.refile,
    )

    assert world.head_rev() == head + 1
    view = world.view()
    army = _named(view, ARMY)
    assert army.fields["part_of"] == {"sphere": ids["tsardom"], "drawer": MILITARY}
    in_army = {i.thing_id for i in spheres.items(view, army.id)}
    assert in_army == {_named(view, "White Talon").id, ids["frosted"]}
    assert view.thing(ids["guard"]).fields["part_of"]["sphere"] == ids["tsardom"]


def _talon_fill(ids, *items) -> FillPreview:
    """Fill of the Tsardom's Military with the White Talon (and `items`)."""

    return FillPreview(
        sphere_id=ids["tsardom"],
        drawer_id=MILITARY,
        items=[
            {
                "drawer_id": MILITARY,
                "name": "White Talon",
                "text": "A regiment of winged riders.",
                "kind": "lore",
                "names": [],
                "ticked": True,
            },
            *items,
        ],
    )


def _accept_talon_fill(world, ids, preview, notes=None):
    accept_fill(
        world,
        ids["tsardom"],
        MILITARY,
        preview.items,
        preview.elsewhere,
        new_names=preview.new_names,
        refile=preview.refile,
        notes=notes,
    )


def test_fill_refile_leaves_one_filing_in_the_new_body(world):
    """A ticked re-file row moves the Frosted Wing into the army: its
    filings say so once, never also the Tsardom it left (the filing shim
    rebuilds them from `part_of` until the spheres go, Task 7)."""

    ids = _tsardom(world)
    with world.revision(Source.manual(note="filed")) as rev:
        rev.set_field(ids["frosted"], "filings", [{"target": ids["tsardom"]}], None)
    preview = add_outer_body(world, _talon_fill(ids), "White Talon", _in_military(ids))
    for row in preview.refile:
        row["ticked"] = row["thing_id"] == ids["frosted"]
    _accept_talon_fill(world, ids, preview)
    view = world.view()
    army = _named(view, ARMY)
    assert [f.target for f in filings_of(view, ids["frosted"])] == [army.id]


def test_fill_add_outer_body_refuses_cycles_and_kinds(world):
    ids = _army(world)
    # through the preview's names: the army can't go inside the Talon
    preview = add_outer_body(world, _talon_fill(ids), "White Talon", _in_military(ids))
    with pytest.raises(ValueError, match="inside"):
        add_outer_body(
            world, preview, ARMY, OuterBody(name="White Talon", template="order")
        )
    # through the world: the White Talon sits inside the army
    preview = _talon_fill(ids)
    preview.new_names.append(NewName(name=ARMY, kind="sphere"))
    with pytest.raises(ValueError, match="inside"):
        add_outer_body(
            world, preview, ARMY, OuterBody(name="The White Talon", template="order")
        )
    # a sphere never goes in a places drawer, and only a sphere holds one
    for part_of in (
        {"sphere": ids["tsardom"], "drawer": LANDS},
        {"sphere": ids["talon"], "drawer": UNSORTED_DRAWER_ID},
    ):
        with pytest.raises(ValueError):
            add_outer_body(
                world,
                _talon_fill(ids),
                "White Talon",
                OuterBody(name="The Old Host", template="order", part_of=part_of),
            )


def test_fill_refile_refuses_cycles(world):
    ids = _tsardom(world)
    preview = add_outer_body(world, _talon_fill(ids), "White Talon", _in_military(ids))
    # the Tsardom itself, into the army that is part of it: a row the
    # preview never offered, dropped with a note before any cycle is made
    preview.refile.append(
        {
            "thing_id": ids["tsardom"],
            "from": None,
            "to": {"name": ARMY, "drawer": UNSORTED_DRAWER_ID},
            "ticked": True,
        }
    )
    notes: list[str] = []
    _accept_talon_fill(world, ids, preview, notes)
    assert world.view().thing(ids["tsardom"]).fields.get("part_of") is None
    assert any("isn't moved" in note for note in notes)


def test_fill_refile_into_a_body_inside_it_refuses_a_cycle(world):
    """An offered, ticked re-file row that would put a sphere inside the
    body it holds reaches `file_in`'s cycle guard: the whole accept is
    refused, nothing written."""

    ids = _tsardom(world)
    military = {"sphere": ids["tsardom"], "drawer": MILITARY}
    with world.revision(Source.manual(note="legion")) as rev:
        legion = rev.create_thing(
            "sphere",
            {"name": "Iron Legion", "template": "order", "part_of": military},
        )
        rev.create_thing(
            "sphere",
            {
                "name": ARMY,
                "template": "order",
                "part_of": {"sphere": legion, "drawer": UNSORTED_DRAWER_ID},
            },
        )
    preview = add_outer_body(world, _talon_fill(ids), "White Talon", _in_military(ids))
    row = next(r for r in preview.refile if r["thing_id"] == legion)
    assert row["from"] == military
    row["ticked"] = True
    head = world.head_rev()
    with pytest.raises(ValueError, match="inside itself"):
        _accept_talon_fill(world, ids, preview)
    assert world.head_rev() == head


def test_fill_chain_accept_with_refile_undo_and_redo(world):
    ids = _tsardom(world)
    preview = add_outer_body(world, _talon_fill(ids), "White Talon", _in_military(ids))
    for row in preview.refile:
        row["ticked"] = row["thing_id"] == ids["frosted"]
    head = world.head_rev()
    _accept_talon_fill(world, ids, preview)
    army = _named(world.view(), ARMY)

    undone = world.undo([head + 1])
    assert world.view().thing(army.id) is None
    assert _part_of(world, ids["frosted"])["sphere"] == ids["tsardom"]
    assert not [
        s for s in world.view().things() if world.view().name_of(s.id) == "White Talon"
    ]

    world.undo([undone.undo_rev])
    view = world.view()
    assert view.thing(army.id).fields["part_of"] == {
        "sphere": ids["tsardom"],
        "drawer": MILITARY,
    }
    assert _part_of(world, ids["frosted"]) == {
        "sphere": army.id,
        "drawer": UNSORTED_DRAWER_ID,
    }
    assert _named(view, "White Talon").fields["part_of"]["sphere"] == army.id


# --- ties within a part ------------------------------------------------------


def _army(world):
    """The Tsar's Army, an order sphere in the Tsardom's Military, with the
    White Talon in its Ranks and the First Squadron in the White Talon;
    Ivan, a trooper of the army within the White Talon since 1012."""

    ids = _tsardom(world)
    with world.revision(Source.manual(note="army")) as rev:
        ids["army"] = rev.create_thing(
            "sphere",
            {
                "name": ARMY,
                "template": "order",
                "drawers": [_drawer(MILITARY, "structure", "Ranks")],
                "part_of": {"sphere": ids["tsardom"], "drawer": MILITARY},
            },
        )
        ids["talon"] = rev.create_thing(
            "lore",
            {
                "name": "The White Talon",
                "part_of": {"sphere": ids["army"], "drawer": MILITARY},
            },
        )
        ids["squadron"] = rev.create_thing(
            "lore",
            {
                "name": "First Squadron",
                "part_of": {"sphere": ids["talon"], "drawer": UNSORTED_DRAWER_ID},
            },
        )
        ids["ivan"] = rev.create_thing(
            "character",
            {
                "name": "Ivan",
                "ties": [
                    {
                        "sphere": ids["army"],
                        "role": "trooper",
                        "since": WorldDate.of(1012).model_dump(mode="json"),
                        "until": None,
                        "within": ids["talon"],
                    }
                ],
            },
        )
    return ids


def test_tie_within_item(world):
    ids = _army(world)
    view = world.view()
    (tie,) = spheres.ties_of(view, ids["ivan"])
    assert (tie.sphere_id, tie.within) == (ids["army"], ids["talon"])
    (person,) = spheres.people(view, ids["army"])
    assert person.within == ids["talon"]

    # a part of a part is within the sphere too, and a real being is tied
    # like a character
    with world.revision(Source.manual()) as rev:
        ids["spirit"] = rev.create_thing(
            "being",
            {
                "name": "Frost Spirit",
                "existence": "real",
                "ties": [
                    {
                        "sphere": ids["army"],
                        "role": "guardian",
                        "since": None,
                        "until": None,
                        "within": ids["squadron"],
                    }
                ],
            },
        )
    (tie,) = spheres.ties_of(world.view(), ids["spirit"])
    assert tie.within == ids["squadron"]
    assert [t.within for t in spheres.people(world.view(), ids["army"])] == [
        ids["talon"],
        ids["squadron"],
    ]

    # a tie with no within is to the sphere as a whole
    assert (
        spheres.Tie(
            character_id=ids["ivan"],
            sphere_id=ids["army"],
            role="",
            since=None,
            until=None,
        ).within
        is None
    )


def test_tie_within_must_be_part_of_sphere(world):
    ids = _army(world)
    base = {"sphere": ids["army"], "role": "trooper", "since": None, "until": None}
    validate_field(get_kind("character"), "ties", [{**base, "within": ids["talon"]}])
    validate_field(get_kind("character"), "ties", [{**base, "within": None}])
    validate_field(get_kind("character"), "ties", [base])
    for within in ("short", 3, ids["army"]):
        with pytest.raises(ValueError):
            validate_field(get_kind("character"), "ties", [{**base, "within": within}])
    with pytest.raises(ValueError):
        validate_field(
            get_kind("character"), "ties", [{**base, "within": None, "other": 1}]
        )

    view = world.view()
    assert spheres.within_sphere(view, ids["talon"], ids["army"])
    assert spheres.within_sphere(view, ids["squadron"], ids["army"])
    # the army is within the Tsardom too, and so is all of it
    assert spheres.within_sphere(view, ids["talon"], ids["tsardom"])
    # the Frosted Wing is the Tsardom's, not the army's
    assert not spheres.within_sphere(view, ids["frosted"], ids["army"])
    assert not spheres.within_sphere(view, ids["army"], ids["army"])

    # a part moved out, or deleted, leaves the tie to the sphere as a whole
    with world.revision(Source.manual()) as rev:
        rev.set_field(
            ids["talon"],
            "part_of",
            {"sphere": ids["tsardom"], "drawer": MILITARY},
            None,
        )
    (tie,) = spheres.ties_of(world.view(), ids["ivan"])
    assert tie.within is None
    with world.revision(Source.manual()) as rev:
        rev.set_field(
            ids["talon"], "part_of", {"sphere": ids["army"], "drawer": MILITARY}, None
        )
    assert spheres.ties_of(world.view(), ids["ivan"])[0].within == ids["talon"]
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(ids["squadron"])
        rev.remove_thing(ids["talon"])
    assert spheres.ties_of(world.view(), ids["ivan"])[0].within is None


def test_tie_line_reads_within(world):
    ids = _army(world)
    view = world.view(WorldDate.of(1020))
    assert tie_lines(view, world.calendar, ids["ivan"]) == [
        "Trooper in the Tsar's Army, within the White Talon (since 1012)"
    ]
    # without a part, the line reads as before
    with world.revision(Source.manual()) as rev:
        rev.create_thing(
            "character",
            {
                "name": "Olga",
                "ties": [
                    {
                        "sphere": ids["army"],
                        "role": "quartermaster",
                        "since": None,
                        "until": None,
                    }
                ],
            },
        )
    olga = _named(world.view(), "Olga")
    assert tie_lines(world.view(), world.calendar, olga.id) == [
        "Quartermaster of the Tsar's Army"
    ]


def _filed_army(world, ids):
    """The army's filings beside its `part_of`s: the army in the Tsardom,
    the White Talon in the army, so a filing can be `within` the Talon."""

    with world.revision(Source.manual(note="filings")) as rev:
        rev.set_field(ids["army"], "filings", [{"target": ids["tsardom"]}], None)
        rev.set_field(ids["talon"], "filings", [{"target": ids["army"]}], None)


def _row_in(target, name, role, within=None):
    return PreviewFiling(
        target_id=target, target_name=name, role=role, within=within, ticked=True
    )


def test_created_filing_carries_within(world):
    """A ticked "In" row with a `within` (the owner's, from a tie in the
    create box) is written with it; one whose part isn't the target's is
    kept, whole."""

    ids = _army(world)
    _filed_army(world, ids)
    preview = CreatePreview(
        kind="character",
        prompt="A rider.",
        name="Pyotr",
        facts=[PreviewFact(category="background", text="Pyotr rides.")],
        prose={},
        filings=[
            _row_in(ids["army"], ARMY, "rider", ids["talon"]),
            # the White Talon is within the Tsardom too, through the army
            _row_in(ids["tsardom"], "Tsardom", "subject", ids["talon"]),
            # the Frosted Wing isn't the army's: kept whole
            _row_in(ids["frosted"], "Frosted Wing", "scout", ids["guard"]),
        ],
    )
    pyotr = accept_preview(world, preview)
    stored = filings_of(world.view(), pyotr, live=False)
    assert [(f.target, f.within) for f in stored] == [
        (ids["army"], ids["talon"]),
        (ids["tsardom"], ids["talon"]),
        (ids["frosted"], None),
    ]
    assert "ties" not in world.view().thing(pyotr).fields


def test_repoint_carries_within(world):
    """Re-pointing a stub a tie is within moves the tie's part to the
    entry, as other tie fields are."""

    ids = _army(world)
    with world.revision(Source.manual()) as rev:
        stub = rev.create_thing(
            "lore",
            {
                "name": "Talon Regiment",
                "stub": {"ignored": False},
                "part_of": {"sphere": ids["army"], "drawer": MILITARY},
            },
        )
        rev.set_field(
            ids["ivan"],
            "ties",
            [
                {
                    "sphere": ids["army"],
                    "role": "trooper",
                    "since": None,
                    "until": None,
                    "within": stub,
                }
            ],
            None,
        )
    assert spheres.ties_of(world.view(), ids["ivan"])[0].within == stub

    repoint_stub(world, stub, ids["talon"])

    (tie,) = spheres.ties_of(world.view(), ids["ivan"])
    assert tie.within == ids["talon"]


# --- fix round 1 -------------------------------------------------------------


def _talon_stub(world, ids):
    """The White Talon, a lore stub filed in the Tsardom's Military."""

    with world.revision(Source.manual(note="talon")) as rev:
        ids["talon"] = rev.create_thing(
            "lore",
            {
                "name": "White Talon",
                "stub": {"ignored": False},
                "part_of": {"sphere": ids["tsardom"], "drawer": MILITARY},
            },
        )
    return ids["talon"]


def _part_of(world, thing_id, at=None):
    state = world.view(at).thing(thing_id)
    return state.fields.get("part_of") if state is not None else None


def test_core_outer_in_a_world_sphere_offers_refile_rows(world):
    """A new sphere's core whose item goes inside a body filed in the
    Tsardom's Military: that drawer's entries are offered."""

    ids = _tsardom(world)
    preview = SpherePreview(
        kind="sphere",
        prompt="An order of riders.",
        name="Order of the Talon",
        facts=[],
        prose={},
        template="order",
        agent=False,
        drawers=[_drawer(MILITARY, "structure", "Ranks")],
        items=[
            {
                "drawer_id": MILITARY,
                "name": "White Talon",
                "text": "A regiment of winged riders.",
                "kind": "lore",
            }
        ],
    )
    preview = add_outer_body(world, preview, "White Talon", _in_military(ids))
    assert [r["thing_id"] for r in preview.refile] == [ids["frosted"], ids["guard"]]


def test_expanding_a_stub_sphere_inside_an_outer_body(world):
    ids = _tsardom(world)
    talon = _talon_stub(world, ids)
    preview = SpherePreview(
        kind="sphere",
        prompt="The White Talon, a regiment.",
        name="White Talon",
        facts=[],
        prose={},
        template="order",
        agent=False,
        drawers=[_drawer("d4d4d4d4", "structure", "Squadrons")],
        stub_id=talon,
    )
    preview = add_outer_body(
        world, preview, "White Talon", OuterBody(name=ARMY, template="order")
    )
    assert _row(preview, ARMY).part_of == {
        "sphere": ids["tsardom"],
        "drawer": MILITARY,
    }
    assert [r["thing_id"] for r in preview.refile] == [ids["frosted"], ids["guard"]]

    assert accept_sphere(world, preview) == talon

    view = world.view()
    army = _named(view, ARMY)
    assert view.thing(talon).kind == "sphere"
    assert _part_of(world, talon) == {"sphere": army.id, "drawer": UNSORTED_DRAWER_ID}
    assert army.fields["part_of"] == {"sphere": ids["tsardom"], "drawer": MILITARY}


def test_merge_keeps_within(world):
    """Onto an entry the world has ("Is this X?" -- yes): its ticked "In"
    rows file it too, `within` kept."""

    ids = _army(world)
    _filed_army(world, ids)
    with world.revision(Source.manual()) as rev:
        pyotr = rev.create_thing("character", {"name": "Pyotr"})
        rev.add_fact(pyotr, "background", "A rider of the north.")
    preview = CreatePreview(
        kind="character",
        prompt="Pyotr, a rider.",
        name="Pyotr",
        facts=[PreviewFact(category="background", text="Pyotr rides at dawn.")],
        prose={},
        filings=[_row_in(ids["army"], ARMY, "rider", ids["talon"])],
    )
    accept_preview(world, preview, same_target_id=pyotr)
    (filing,) = filings_of(world.view(), pyotr)
    assert (filing.target, filing.within) == (ids["army"], ids["talon"])


def test_ticked_adopted_entry_is_not_adopted_too(world):
    """Expanding a stub into a sphere: an entry it adopts, ticked to move
    into the outer body, is filed there once, not also in its drawer."""

    world.set_present(WorldDate.of(1020))
    ranks = "e5e5e5e5"
    with world.revision(Source.manual()) as rev:
        host = rev.create_thing(
            "lore", {"name": "Tsar's Host", "stub": {"ignored": False}}
        )
        banner = rev.create_thing(
            "lore",
            {
                "name": "Banner Guard",
                "part_of": {"sphere": host, "drawer": UNSORTED_DRAWER_ID},
            },
        )
        rev.add_fact(banner, "general", "Carries the banners.")
    preview = SpherePreview(
        kind="sphere",
        prompt="The Tsar's Host.",
        name="Tsar's Host",
        facts=[],
        prose={},
        template="order",
        agent=False,
        drawers=[_drawer(ranks, "structure", "Ranks")],
        items=[
            {
                "drawer_id": ranks,
                "name": "White Talon",
                "text": "A regiment of winged riders.",
                "kind": "lore",
            }
        ],
        adopted=[{"thing_id": banner, "drawer_id": ranks}],
        stub_id=host,
    )
    preview = add_outer_body(
        world,
        preview,
        "White Talon",
        OuterBody(name="First Division", template="order"),
    )
    assert [r["thing_id"] for r in preview.refile] == [banner]
    preview.refile[0]["ticked"] = True
    head = world.head_rev()

    accept_sphere(world, preview)

    division = _named(world.view(), "First Division")
    assert division.fields["part_of"] == {"sphere": host, "drawer": ranks}
    assert _part_of(world, banner) == {
        "sphere": division.id,
        "drawer": UNSORTED_DRAWER_ID,
    }
    # written once in the accept
    moves = [
        entry
        for entry in world.timeline(banner)
        if entry.change == "field"
        and entry.field == "part_of"
        and entry.source_rev == head + 1
    ]
    assert len(moves) == 1
