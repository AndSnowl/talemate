"""Bodies within bodies (curation Task 7, spec goal 9, ruling C10).

The White Talon is a division of the Tsar's Army, an order sphere of its
own that is part of the Tsardom. The curation probe's probe 5 took the
fallback: the model never proposed the outer body, so the owner names it
(`bodies.add_outer_body`, no model call); its default name is "<inner
part>'s parent". The entries already filed where it goes are offered to
move into it, unticked. A tie can be `within` one part of its sphere."""

import pytest

from talemate.world import spheres
from talemate.world.dates import WorldDate
from talemate.world.kinds import UNSORTED_DRAWER_ID, get_kind, validate_field
from talemate.world.store import Source
from talemate.worldplay.bodies import OuterBody, add_outer_body, outer_name
from talemate.worldplay.characters import tie_lines
from talemate.worldplay.create import (
    CreatePreview,
    PreviewFact,
    PreviewTie,
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


def test_add_outer_body_sets_chain_and_refile_rows(world):
    ids = _tsardom(world)
    head = world.head_rev()

    preview = add_outer_body(world, _trooper(), "White Talon", _in_military(ids))

    assert _row(preview, "White Talon").part_of == {
        "name": ARMY,
        "drawer": UNSORTED_DRAWER_ID,
    }
    army = _row(preview, ARMY)
    assert (army.kind, army.template) == ("sphere", "order")
    assert army.part_of == {"sphere": ids["tsardom"], "drawer": MILITARY}
    military = {"sphere": ids["tsardom"], "drawer": MILITARY}
    to = {"name": ARMY, "drawer": UNSORTED_DRAWER_ID}
    # every entry in the Military drawer, none ticked; not the Zakonnik
    assert preview.refile == [
        {"thing_id": ids["frosted"], "from": military, "to": to, "ticked": False},
        {"thing_id": ids["guard"], "from": military, "to": to, "ticked": False},
    ]
    # nothing written, no model asked
    assert world.head_rev() == head

    # naming it again for the same part replaces it, re-file rows too
    again = add_outer_body(
        world,
        preview,
        "White Talon",
        OuterBody(name="The Northern Host", template="order"),
    )
    assert [n.name for n in again.new_names] == ["White Talon", "The Northern Host"]
    # filed nowhere: a new name is in no sphere yet
    assert _row(again, "The Northern Host").part_of is None
    assert again.refile == []


def test_outer_body_default_name():
    assert outer_name("White Talon") == "White Talon's parent"
    assert outer_name("  The  White Talon ") == "The White Talon's parent"


def test_outer_body_blank_name_takes_the_default(world):
    ids = _tsardom(world)
    preview = add_outer_body(
        world,
        _trooper(),
        "White Talon",
        OuterBody(name=" ", template="order", part_of=None),
    )
    assert _row(preview, "White Talon").part_of["name"] == "White Talon's parent"
    assert _row(preview, "White Talon's parent").kind == "sphere"
    assert ids


def test_add_outer_body_refuses(world):
    ids = _tsardom(world)
    refused = [
        ("White Talon", OuterBody(name=ARMY, template="guild")),
        ("Black Talon", OuterBody(name=ARMY, template="order")),
        ("White Talon", OuterBody(name="White Talon", template="order")),
        # a sphere never goes in a places drawer
        (
            "White Talon",
            OuterBody(
                name=ARMY,
                template="order",
                part_of={"sphere": ids["tsardom"], "drawer": LANDS},
            ),
        ),
        # not a sphere
        (
            "White Talon",
            OuterBody(
                name=ARMY,
                template="order",
                part_of={"sphere": ids["guard"], "drawer": UNSORTED_DRAWER_ID},
            ),
        ),
    ]
    for row_name, outer in refused:
        with pytest.raises(ValueError):
            add_outer_body(world, _trooper(), row_name, outer)
    # a character is never part of a sphere
    preview = _trooper()
    preview.new_names.append(NewName(name="Boris", kind="character"))
    with pytest.raises(ValueError):
        add_outer_body(world, preview, "Boris", _in_military(ids))


def test_chain_made_outer_first_on_accept(world):
    ids = _tsardom(world)
    preview = add_outer_body(world, _trooper(), "White Talon", _in_military(ids))
    head = world.head_rev()

    ivan = accept_preview(world, preview)

    # one revision, so one undo reverses it
    assert world.head_rev() == head + 1
    view = world.view()
    army = _named(view, ARMY)
    talon = _named(view, "White Talon")
    assert (army.kind, army.fields.get("template"), army.is_stub) == (
        "sphere",
        "order",
        True,
    )
    assert army.fields["part_of"] == {"sphere": ids["tsardom"], "drawer": MILITARY}
    # the army is a stub with no drawers yet: its part waits in Unsorted
    assert talon.fields["part_of"] == {"sphere": army.id, "drawer": UNSORTED_DRAWER_ID}
    # outer first
    assert army.created < talon.created
    # the fact links the White Talon; the army is kept with no link to it
    assert [owner for owner, _ in view.referencing(talon.id)] == [ivan]
    assert view.referencing(army.id) == []
    # nothing ticked moved
    assert view.thing(ids["frosted"]).fields["part_of"]["sphere"] == ids["tsardom"]
    assert [i.thing_id for i in spheres.items(view, army.id)] == [talon.id]


def test_siblings_refiled_into_outer_body(world):
    ids = _tsardom(world)
    preview = add_outer_body(world, _trooper(), "White Talon", _in_military(ids))
    for row in preview.refile:
        row["ticked"] = row["thing_id"] == ids["frosted"]
    head = world.head_rev()

    accept_preview(world, preview)

    assert world.head_rev() == head + 1
    view = world.view()
    army = _named(view, ARMY)
    assert view.thing(ids["frosted"]).fields["part_of"] == {
        "sphere": army.id,
        "drawer": UNSORTED_DRAWER_ID,
    }
    # left unticked: stays
    assert view.thing(ids["guard"]).fields["part_of"] == {
        "sphere": ids["tsardom"],
        "drawer": MILITARY,
    }
    # dated as `set_part_of` dates it: the Frosted Wing's filing was dated,
    # so the move holds from now, and before it it's still the Tsardom's
    then = world.view(WorldDate.of(1010))
    assert then.thing(ids["frosted"]).fields["part_of"]["sphere"] == ids["tsardom"]
    items = {i.thing_id for i in spheres.items(view, army.id)}
    assert ids["frosted"] in items


def test_refile_of_a_thing_moved_since_is_left(world):
    ids = _tsardom(world)
    preview = add_outer_body(world, _trooper(), "White Talon", _in_military(ids))
    for row in preview.refile:
        row["ticked"] = True
    with world.revision(Source.manual()) as rev:
        rev.set_field(
            ids["guard"], "part_of", {"sphere": ids["tsardom"], "drawer": LAWS}, None
        )
    notes: list[str] = []
    accept_preview(world, preview, notes=notes)
    view = world.view()
    assert view.thing(ids["guard"]).fields["part_of"]["drawer"] == LAWS
    assert any("Kremlin Guard" in note for note in notes)


def test_refile_refuses_cycles(world):
    ids = _tsardom(world)
    preview = add_outer_body(world, _trooper(), "White Talon", _in_military(ids))
    # the Tsardom itself, into the army that is part of it
    preview.refile.append(
        {
            "thing_id": ids["tsardom"],
            "from": None,
            "to": {"name": ARMY, "drawer": UNSORTED_DRAWER_ID},
            "ticked": True,
        }
    )
    # a row the preview never offered (the Tsardom isn't filed where the
    # army goes): dropped with a note before any cycle could be made
    notes: list[str] = []
    accept_preview(world, preview, notes=notes)
    assert world.view().thing(ids["tsardom"]).fields.get("part_of") is None
    assert any("isn't moved" in note for note in notes)


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


def test_created_tie_carries_within(world):
    ids = _army(world)
    preview = CreatePreview(
        kind="character",
        prompt="A rider.",
        name="Pyotr",
        facts=[PreviewFact(category="background", text="Pyotr rides.")],
        prose={},
        ties=[
            PreviewTie(
                sphere_id=ids["army"], sphere=ARMY, role="rider", within=ids["talon"]
            ),
            # the White Talon is within the Tsardom too, through the army
            PreviewTie(
                sphere_id=ids["tsardom"],
                sphere="Tsardom",
                role="subject",
                within=ids["talon"],
            ),
            # the Frosted Wing isn't the army's: the tie is kept, whole
            PreviewTie(
                sphere_id=ids["army"], sphere=ARMY, role="scout", within=ids["frosted"]
            ),
        ],
    )
    pyotr = accept_preview(world, preview)
    stored = world.view().thing(pyotr).fields["ties"]
    assert [t.get("within") for t in stored] == [ids["talon"], ids["talon"], None]
    assert "within" not in stored[2]


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


def test_expanding_a_stub_puts_it_inside_an_outer_body(world):
    """Ruling C11, the owner's case: expanding the White Talon stub and
    saying it belongs to an army. The army goes where the stub was filed,
    the Talon inside it, and the drawer's other entries are offered."""

    ids = _tsardom(world)
    talon = _talon_stub(world, ids)
    preview = CreatePreview(
        kind="lore",
        prompt="The White Talon, a regiment.",
        name="White Talon",
        facts=[PreviewFact(category="general", text="A regiment of winged riders.")],
        prose={},
        stub_id=talon,
    )
    preview = add_outer_body(
        world, preview, "White Talon", OuterBody(name=ARMY, template="order")
    )
    assert preview.part_of == {"name": ARMY, "drawer": UNSORTED_DRAWER_ID}
    assert _row(preview, ARMY).part_of == {
        "sphere": ids["tsardom"],
        "drawer": MILITARY,
    }
    # the Talon itself isn't offered
    assert [r["thing_id"] for r in preview.refile] == [ids["frosted"], ids["guard"]]
    for row in preview.refile:
        row["ticked"] = row["thing_id"] == ids["frosted"]
    head = world.head_rev()

    assert accept_preview(world, preview) == talon

    assert world.head_rev() == head + 1
    army = _named(world.view(), ARMY)
    assert army.fields["part_of"] == {"sphere": ids["tsardom"], "drawer": MILITARY}
    assert _part_of(world, talon) == {"sphere": army.id, "drawer": UNSORTED_DRAWER_ID}
    assert _part_of(world, ids["frosted"])["sphere"] == army.id
    assert not world.view().thing(talon).is_stub

    # one undo reverses it all
    world.undo([head + 1])
    view = world.view()
    assert view.thing(army.id) is None
    assert view.thing(talon).is_stub
    assert _part_of(world, talon) == {"sphere": ids["tsardom"], "drawer": MILITARY}
    assert _part_of(world, ids["frosted"]) == {
        "sphere": ids["tsardom"],
        "drawer": MILITARY,
    }


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


def test_same_thing_accept_refiles(world):
    """Accepting onto an existing entry ("Is this X?" -- yes) makes the
    chain and moves the ticked entries too."""

    ids = _tsardom(world)
    with world.revision(Source.manual()) as rev:
        regiment = rev.create_thing("lore", {"name": "Talon Regiment"})
        rev.add_fact(regiment, "general", "Riders of the north.")
    preview = CreatePreview(
        kind="lore",
        prompt="The Talon Regiment.",
        name="Talon Regiment",
        facts=[PreviewFact(category="general", text="It trains with the White Talon.")],
        prose={},
        new_names=[NewName(name="White Talon", kind="lore")],
    )
    preview = add_outer_body(world, preview, "White Talon", _in_military(ids))
    for row in preview.refile:
        row["ticked"] = row["thing_id"] == ids["frosted"]

    accept_preview(world, preview, same_target_id=regiment)

    view = world.view()
    army = _named(view, ARMY)
    assert _part_of(world, ids["frosted"]) == {
        "sphere": army.id,
        "drawer": UNSORTED_DRAWER_ID,
    }
    assert _named(view, "White Talon").fields["part_of"]["sphere"] == army.id


def test_merge_keeps_within(world):
    ids = _army(world)
    with world.revision(Source.manual()) as rev:
        pyotr = rev.create_thing("character", {"name": "Pyotr"})
        rev.add_fact(pyotr, "background", "A rider of the north.")
    preview = CreatePreview(
        kind="character",
        prompt="Pyotr, a rider.",
        name="Pyotr",
        facts=[PreviewFact(category="background", text="Pyotr rides at dawn.")],
        prose={},
        ties=[
            PreviewTie(
                sphere_id=ids["army"], sphere=ARMY, role="rider", within=ids["talon"]
            )
        ],
    )
    accept_preview(world, preview, same_target_id=pyotr)
    (tie,) = world.view().thing(pyotr).fields["ties"]
    assert tie["within"] == ids["talon"]


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


def test_chain_accept_with_refile_undo_and_redo(world):
    ids = _tsardom(world)
    preview = add_outer_body(world, _trooper(), "White Talon", _in_military(ids))
    for row in preview.refile:
        row["ticked"] = row["thing_id"] == ids["frosted"]
    head = world.head_rev()
    accept_preview(world, preview)
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


def test_add_outer_body_refuses_cycles_and_kinds(world):
    ids = _army(world)
    # through the preview's names: the army can't go inside the Talon
    preview = add_outer_body(world, _trooper(), "White Talon", _in_military(ids))
    with pytest.raises(ValueError, match="inside"):
        add_outer_body(
            world, preview, ARMY, OuterBody(name="White Talon", template="order")
        )
    # through the world: the White Talon sits inside the army
    preview = _trooper()
    preview.new_names.append(NewName(name=ARMY, kind="sphere"))
    with pytest.raises(ValueError, match="inside"):
        add_outer_body(
            world, preview, ARMY, OuterBody(name="The White Talon", template="order")
        )
    # named as the entry being made
    with pytest.raises(ValueError):
        add_outer_body(
            world,
            _trooper(),
            "White Talon",
            OuterBody(name="Ivan Petrov", template="order"),
        )


def test_add_outer_body_upgrades_another_kind_only_when_asked(world):
    ids = _tsardom(world)
    preview = _trooper()
    preview.new_names.append(NewName(name="Northern Host", kind="lore"))
    with pytest.raises(ValueError, match="lore"):
        add_outer_body(
            world,
            preview,
            "White Talon",
            OuterBody(name="Northern Host", template="order"),
        )
    preview = add_outer_body(
        world,
        preview,
        "White Talon",
        OuterBody(name="Northern Host", template="order"),
        as_sphere=True,
    )
    host = _row(preview, "Northern Host")
    assert (host.kind, host.template) == ("sphere", "order")
    assert ids


def test_part_marked_same_as_a_filed_entry_is_offered_to_move(world):
    """A new name the owner marked as the Zakonnik, filed in the Laws: it
    isn't left where it is with an empty body around nothing; it's an
    unticked re-file row, and the body is made only once it's ticked."""

    ids = _tsardom(world)
    preview = _trooper()
    preview.new_names[0].same_target_id = ids["zakonnik"]
    preview = add_outer_body(world, preview, "White Talon", _in_military(ids))
    rows = {r["thing_id"]: r for r in preview.refile}
    assert rows[ids["zakonnik"]]["from"] == {"sphere": ids["tsardom"], "drawer": LAWS}
    assert rows[ids["zakonnik"]]["ticked"] is False

    # unticked: no empty body
    accept_preview(world, preview.model_copy(deep=True))
    view = world.view()
    assert not [s for s in view.things() if view.name_of(s.id) == ARMY]
    assert _part_of(world, ids["zakonnik"])["drawer"] == LAWS

    ticked = preview.model_copy(deep=True)
    for row in ticked.refile:
        row["ticked"] = row["thing_id"] == ids["zakonnik"]
    ticked.name = "Ivan Volkov"
    accept_preview(world, ticked)
    army = _named(world.view(), ARMY)
    assert _part_of(world, ids["zakonnik"]) == {
        "sphere": army.id,
        "drawer": UNSORTED_DRAWER_ID,
    }
