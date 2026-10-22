"""Spheres on the world screens: a sphere page with its typed drawers (Fill,
a new drawer, a retitle), People and Timeline; a child expanded before its
sphere, which then adopts it; a character's ties with "but…" exceptions,
from its page and from the create preview; "Make it a sphere…" on a lore
entry and on a place; and "End this…" on a drawer item.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`), the
facts' references written as `[[@Name|shown]]`. No model is asked
anything: character previews come from the fixed preview file, and sphere
cores and Fill from the fixed sphere file (read through the real parsing).
What the page sends is read back from a websocket spy.
"""

from __future__ import annotations

from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_connections_create import _opened, _wait_sent
from e2e.worlds.test_new_scene import SEND_SPY_JS, _sent
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

# drawer ids (8-hex, as the `drawers` field holds them)
DOCTRINES = "d0c71e5a"
HIERARCHY = "4e1a2c3b"
RITES = "717e5abc"
PEOPLE = "9e0b1e5a"
SITES = "5173a5be"
TIMELINE = "71e11e5a"
CUSTOMS = "c0570a5e"


def _drawer(drawer_id: str, type_: str, title: str) -> dict:
    return {"id": drawer_id, "type": type_, "title": title}


TSARDOM = {
    "kind": "place",
    "name": "Tsardom of Moscavia",
    "facts": [{"category": "description", "text": "A cold realm of the north."}],
}

WHITE_DAWN = {
    "kind": "sphere",
    "name": "The White Dawn",
    "fields": {
        "template": "religion",
        "drawers": [
            _drawer(DOCTRINES, "beliefs", "Doctrines"),
            _drawer(HIERARCHY, "structure", "Hierarchy"),
            _drawer(RITES, "practices", "Rites and Ceremonies"),
            _drawer(PEOPLE, "people", "People"),
            _drawer(SITES, "places", "Holy Sites"),
            _drawer(TIMELINE, "events", "Timeline"),
        ],
    },
    "facts": [
        {
            "category": "statement",
            "text": "Snowy owl-folk are closest to the White Light.",
            "origin": {"drawer": DOCTRINES},
        },
        {
            "category": "timeline",
            "text": "Declared the transformation a purification.",
            "since": 994,
        },
        {
            "category": "timeline",
            "text": "Issued the Doctrine of Separation.",
            "since": 1019,
        },
    ],
}

COUNCIL = {
    "kind": "lore",
    "name": "The Council of Elders",
    "part_of": {"sphere": "The White Dawn", "drawer": HIERARCHY},
    "facts": [{"category": "general", "text": "Crowns each new Tsar."}],
}

TEMPLE = {
    "kind": "place",
    "name": "Temple of the First Light",
    "part_of": {"sphere": "The White Dawn", "drawer": SITES},
    "facts": [{"category": "description", "text": "A white temple in Moskov."}],
}

VASHA = {
    "kind": "character",
    "name": "Vasha",
    "born": 1000,
    "ties": [{"sphere": "The White Dawn", "role": "practitioner", "since": 1010}],
    "facts": [
        {
            "category": "ties",
            "text": "Never bows to [[@The Council of Elders|the Council of Elders]].",
            # filed under its tie (ruling P22)
            "origin": {"tie": "The White Dawn"},
        }
    ],
}

POSTAL = {
    "kind": "sphere",
    "name": "Kalmara Postal Service",
    "fields": {"template": "order", "drawers": []},
}


def _drawer_of(thing, title: str):
    return thing.get_by_test_id("sphere-drawer").filter(
        has=thing.page.get_by_test_id("drawer-title").filter(has_text=title)
    )


def _sphere_card(page, name: str):
    page.get_by_test_id("kind-sphere").click()
    return _open_thing(page, name)


def test_sphere_page_drawers_and_fill(app, page, fixed_sphere):
    name = _world_name("Moskov")
    seed_things = [TSARDOM, WHITE_DAWN, COUNCIL, TEMPLE, VASHA]
    seed_fm_world(app.root, name, present_year=1026, things=seed_things)
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)

    # the Spheres list, grouped by template
    page.get_by_test_id("kind-sphere").click()
    group = page.get_by_test_id("sphere-group").filter(has_text="Religions")
    group.get_by_test_id("thing-card").filter(has_text="The White Dawn").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    thing = _open_thing(page, "The White Dawn")

    # the template and agent chips
    assert "sphere · religion" in thing.get_by_test_id("sphere-template").inner_text()
    assert "acts in the world" in thing.get_by_test_id("sphere-agent").inner_text()

    # typed, titled drawers with their items
    doctrines = _drawer_of(thing, "Doctrines")
    doctrines.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "beliefs" in doctrines.get_by_test_id("drawer-type").inner_text()
    assert "closest to the White Light" in doctrines.inner_text()
    hierarchy = _drawer_of(thing, "Hierarchy")
    council = hierarchy.get_by_test_id("linked-ref").filter(
        has_text="The Council of Elders"
    )
    assert council.is_visible()
    assert "Crowns each new Tsar" in hierarchy.inner_text()
    sites = _drawer_of(thing, "Holy Sites")
    assert "Temple of the First Light" in sites.inner_text()

    # People from ties, with roles and dates
    people = thing.get_by_test_id("sphere-people")
    people.filter(has_text="Vasha").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "practitioner" in people.inner_text()
    assert "1010" in people.inner_text()

    # the Timeline, in date order
    timeline = thing.get_by_test_id("sphere-timeline")
    text = timeline.inner_text()
    assert text.index("994") < text.index("1019")
    assert "Declared the transformation a purification." in text

    # an empty drawer is filled: the owner keeps one of two items
    rites = _drawer_of(thing, "Rites and Ceremonies")
    assert "Not written yet" in rites.inner_text()
    fixed_sphere(
        {
            "fill": [
                {"name": "The Dawn Vigil", "text": "A prayer at first light."},
                {"name": "The Crowning of the Tsar", "text": "Each Tsar is crowned."},
            ]
        }
    )
    rites.get_by_test_id("drawer-fill").click()
    fill = rites.get_by_test_id("fill-preview")
    fill.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert _wait_sent(page, "fill_drawer")["drawer_id"] == RITES
    crowning = fill.get_by_test_id("fill-item").filter(has_text="Crowning")
    crowning.get_by_role("checkbox").uncheck()
    fill.get_by_role("button", name="Accept").click()
    rites.get_by_test_id("linked-stub").filter(has_text="The Dawn Vigil").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "Crowning" not in rites.inner_text()
    kept = _sent(page, "accept_fill")[-1]["items"]
    assert [item["name"] for item in kept] == ["The Dawn Vigil"]

    # a new drawer, typed and titled by the owner
    thing.get_by_role("button", name="Add a drawer").click()
    form = thing.get_by_test_id("drawer-form")
    form.get_by_role("button", name="knowledge").click()
    form.get_by_label("Title").fill("Key Texts")
    form.get_by_role("button", name="Save").click()
    texts = _drawer_of(thing, "Key Texts")
    texts.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "knowledge" in texts.get_by_test_id("drawer-type").inner_text()
    drawers = _sent(page, "set_drawers")[-1]["drawers"]
    assert len(drawers) == 7
    assert drawers[-1] == {"type": "knowledge", "title": "Key Texts"}

    # a second events drawer: the Timeline shows once, under the first
    thing.get_by_role("button", name="Add a drawer").click()
    form = thing.get_by_test_id("drawer-form")
    form.get_by_role("button", name="events").click()
    form.get_by_label("Title").fill("Chronicle")
    form.get_by_role("button", name="Save").click()
    chronicle = _drawer_of(thing, "Chronicle")
    chronicle.get_by_test_id("timeline-elsewhere").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "Timeline" in chronicle.inner_text()
    expect(thing.get_by_test_id("sphere-timeline")).to_have_count(1)

    # a sphere's facts all show in its drawers: no Facts list of its own
    expect(thing.get_by_role("button", name="Add fact")).to_have_count(0)

    # retitled in place, keeping its id
    _drawer_of(thing, "Doctrines").get_by_test_id("drawer-edit").click()
    form = thing.get_by_test_id("drawer-form")
    form.get_by_label("Title").fill("Core Doctrines")
    form.get_by_role("button", name="Save").click()
    _drawer_of(thing, "Core Doctrines").wait_for(state="visible", timeout=TIMEOUT_MS)
    retitled = _sent(page, "set_drawers")[-1]["drawers"][0]
    assert retitled == {"id": DOCTRINES, "type": "beliefs", "title": "Core Doctrines"}

    # a statement written by hand into a drawer
    doctrines = _drawer_of(thing, "Core Doctrines")
    doctrines.get_by_test_id("drawer-add").click()
    add = doctrines.get_by_test_id("drawer-add-form")
    add.get_by_label("Statement").fill("Light is purity.")
    add.get_by_role("button", name="Add", exact=True).click()
    statement = doctrines.get_by_test_id("drawer-item").filter(
        has_text="Light is purity."
    )
    statement.wait_for(state="visible", timeout=TIMEOUT_MS)
    sent = _sent(page, "add_statement")[-1]
    assert (sent["drawer_id"], sent["text"]) == (DOCTRINES, "Light is purity.")

    # corrected where it shows, and kept in its drawer
    statement.get_by_test_id("sphere-fact-edit").click()
    form = doctrines.get_by_test_id("fact-form")
    # it stays a statement
    form.locator(".v-select .v-field").click()
    expect(page.get_by_role("option")).to_have_count(1)
    page.keyboard.press("Escape")
    form.get_by_label("Fact", exact=True).fill("Light is purity itself.")
    form.get_by_role("button", name="Save").click()
    doctrines.get_by_test_id("drawer-item").filter(
        has_text="Light is purity itself."
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # a timeline row too
    timeline = thing.get_by_test_id("sphere-timeline")
    row = timeline.get_by_test_id("timeline-row").filter(has_text="Declared")
    row.get_by_test_id("sphere-fact-edit").click()
    form = timeline.get_by_test_id("fact-form")
    form.get_by_label("Fact", exact=True).fill("Declared the change a purification.")
    form.get_by_role("button", name="Save").click()
    timeline.get_by_test_id("timeline-row").filter(
        has_text="Declared the change a purification."
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "994" in timeline.inner_text()

    # neither is listed again among the facts
    facts = thing.get_by_test_id("fact-row")
    assert facts.filter(has_text="Light is purity").count() == 0
    assert facts.filter(has_text="Declared the change").count() == 0
    assert page.console_errors == []


def test_child_first_then_sphere_adopts(app, page, fixed_preview, fixed_sphere):
    name = _world_name("Elders")
    dawn_stub = {
        "kind": "sphere",
        "name": "The White Dawn",
        "stub": "live",
        "fields": {"template": "religion"},
    }
    council_stub = {"kind": "lore", "name": "The Council of Elders", "stub": "live"}
    tsardom = {
        "kind": "place",
        "name": "Tsardom of Moscavia",
        "facts": [
            {
                "category": "description",
                "text": "The [[@The Council of Elders|Council of Elders]] of"
                " [[@The White Dawn|the White Dawn]] crowns each Tsar.",
            }
        ],
    }
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[dawn_stub, council_stub, tsardom]
    )
    dawn, council = (
        world.things["The White Dawn"],
        world.things["The Council of Elders"],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)

    # the council first: expanded from its stub, its prompt naming the
    # White Dawn stub
    page.get_by_test_id("kind-lore").click()
    page.get_by_test_id("stub-item").filter(has_text="The Council of Elders").click()
    stub_page = _opened(page, "The Council of Elders")
    stub_page.get_by_test_id("stub-panel").get_by_role("button", name="Expand").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").wait_for(state="visible", timeout=TIMEOUT_MS)
    box.get_by_label("Describe it").fill(
        "The council of elders of The White Dawn, who crown each Tsar."
    )
    box.get_by_test_id("name-match").filter(has_text="The White Dawn").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    fixed_preview(
        {
            "name": "The Council of Elders",
            "facts": [{"category": "general", "text": "Crowns each new Tsar."}],
            "prose": {"description": "Old owls in white."},
        }
    )
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("create-preview")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "The White Dawn" in preview.get_by_test_id("preview-part-of").inner_text()
    preview.get_by_role("button", name="Accept").click()
    thing = _opened(page, "The Council of Elders")

    # its Part of line names the stub, guessed a religion, unsorted
    part_of = thing.get_by_test_id("part-of")
    part_of.get_by_test_id("linked-stub").filter(has_text="The White Dawn").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "religion" in part_of.inner_text()
    assert "Unsorted" in part_of.inner_text()

    # then the White Dawn, from that stub: written around the council
    part_of.get_by_test_id("linked-stub").filter(has_text="The White Dawn").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").filter(has_text="The White Dawn").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    picker = box.get_by_test_id("sphere-template-picker")
    assert "v-btn--active" in picker.get_by_role(
        "button", name="Religion"
    ).get_attribute("class")
    fixed_sphere(
        {
            "sphere": {
                "name": "The White Dawn",
                "summary": "The state church of Moscavia.",
                "aka": [],
                "timeline": [
                    {"year": 994, "text": "Declared the transformation a purification."}
                ],
                "drawers": [
                    {"type": "beliefs", "title": "Doctrines"},
                    {"type": "structure", "title": "Hierarchy"},
                ],
                "items": [
                    {
                        "drawer": "Hierarchy",
                        "name": "The Council of Elders",
                        "text": "Crowns each new Tsar.",
                    },
                    {"drawer": "Doctrines", "name": "", "text": "Light is purity."},
                ],
                "names": [],
            }
        }
    )
    box.get_by_role("button", name="Create").click()
    sphere_preview = page.get_by_test_id("sphere-preview")
    sphere_preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert _sent(page, "preview_sphere")[-1]["stub_id"] == dawn
    assert _sent(page, "preview_sphere")[-1]["template"] == "religion"
    hierarchy = sphere_preview.get_by_test_id("preview-drawer").filter(
        has_text="Hierarchy"
    )
    assert "The Council of Elders" in hierarchy.inner_text()
    sphere_preview.get_by_role("button", name="Accept").click()
    sphere = _opened(page, "The White Dawn")
    accepted = _sent(page, "accept_sphere")[-1]["preview"]
    assert accepted["stub_id"] == dawn
    assert accepted["adopted"][0]["thing_id"] == council

    # its summary shows once, as the summary, never as an about row; Edit
    # corrects its fact, which can't be removed (ruling P21)
    summary = sphere.get_by_test_id("sphere-summary")
    summary.filter(has_text="The state church of Moscavia.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(sphere.get_by_test_id("about-row")).to_have_count(0)
    expect(summary.get_by_test_id("sphere-fact-remove")).to_have_count(0)
    summary.get_by_test_id("sphere-fact-edit").click()
    form = summary.get_by_test_id("fact-form")
    expect(form.get_by_role("button", name="Remove")).to_have_count(0)
    form.get_by_label("Fact", exact=True).fill("The state church of all Moscavia.")
    form.get_by_role("button", name="Save").click()
    expect(form).to_have_count(0)
    corrected = _sent(page, "correct_fact")[-1]
    assert corrected["text"] == "The state church of all Moscavia."
    expect(sphere.get_by_test_id("about-row")).to_have_count(0)

    # made by the core, with no drawer seeded by hand: its Branches drawer
    # offers "+ New branch", and the branch shows on its parent (P23)
    branches = _drawer_of(sphere, "Branches")
    assert "branches" in branches.get_by_test_id("drawer-type").inner_text()
    fixed_sphere(
        {
            "branch": {
                "name": "The Forge Dawn",
                "summary": "Smiths who keep the Dawn at the anvil.",
                "aka": [],
                "timeline": [],
                "drawers": [],
                "drops": [],
                "items": [{"drawer": "Doctrines", "text": "The forge is a dawn too."}],
                "names": [],
            }
        }
    )
    branches.get_by_role("button", name="New branch").click()
    branches.get_by_label("Describe the branch").fill("the smiths' Dawn")
    branches.get_by_role("button", name="Preview").click()
    branch_preview = branches.get_by_test_id("sphere-preview")
    branch_preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    branch_preview.get_by_role("button", name="Accept").click()
    branch = _opened(page, "The Forge Dawn")
    branch.get_by_test_id("sphere-parent").get_by_test_id("linked-ref").filter(
        has_text="The White Dawn"
    ).click()
    sphere = _opened(page, "The White Dawn")
    _drawer_of(sphere, "Branches").get_by_test_id("sphere-branch").filter(
        has_text="The Forge Dawn"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # its Hierarchy drawer holds the council, now an entry's link
    hierarchy = _drawer_of(sphere, "Hierarchy")
    hierarchy.get_by_test_id("linked-ref").filter(
        has_text="The Council of Elders"
    ).click()
    thing = _opened(page, "The Council of Elders")
    part_of = thing.get_by_test_id("part-of")
    part_of.get_by_test_id("linked-ref").filter(has_text="The White Dawn").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "Hierarchy" in part_of.inner_text()
    assert page.console_errors == []


def test_ties_with_exceptions(app, page, fixed_preview):
    name = _world_name("Ties")
    world = seed_fm_world(
        app.root,
        name,
        present_year=1026,
        things=[WHITE_DAWN, COUNCIL, POSTAL, VASHA],
    )
    dawn, council = (
        world.things["The White Dawn"],
        world.things["The Council of Elders"],
    )
    postal = world.things["Kalmara Postal Service"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Vasha")

    # the tie, its role and date, and only its "but…"
    ties = thing.get_by_test_id("ties-section")
    tie = ties.get_by_test_id("tie").filter(has_text="The White Dawn")
    tie.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Practitioner of" in tie.inner_text()
    assert "since 1010" in tie.inner_text()
    exception = tie.get_by_test_id("tie-exception").filter(has_text="Never bows")
    assert (
        exception.get_by_test_id("linked-ref")
        .filter(has_text="the Council of Elders")
        .is_visible()
    )
    # the exception isn't listed again among the facts
    assert thing.get_by_test_id("fact-row").filter(has_text="Never bows").count() == 0

    # "+ Add exception", departing from one of the sphere's items
    tie.get_by_role("button", name="Add exception").click()
    form = tie.get_by_test_id("exception-form")
    form.get_by_label("But…").fill("Skips the dawn prayers when on the road.")
    form.get_by_test_id("exception-rejects").locator(".v-field").click()
    page.get_by_role("option", name="The Council of Elders").click()
    form.get_by_role("button", name="Save").click()
    tie.get_by_test_id("tie-exception").filter(has_text="Skips the dawn").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    sent = _sent(page, "add_exception")[-1]
    assert (sent["sphere_id"], sent["rejects"]) == (dawn, {"thing_id": council})

    # "+ Add tie": a sphere and a role
    ties.get_by_role("button", name="Add tie").click()
    form = ties.get_by_test_id("tie-form")
    form.get_by_test_id("tie-sphere").locator(".v-field").click()
    page.get_by_role("option", name="Kalmara Postal Service").click()
    form.get_by_label("Role").fill("courier")
    form.get_by_label("Since (year)").fill("1009")
    form.get_by_role("button", name="Save").click()
    courier = ties.get_by_test_id("tie").filter(has_text="Kalmara Postal Service")
    courier.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Courier of" in courier.inner_text()
    assert "no exceptions" in courier.inner_text()
    saved = _sent(page, "set_ties")[-1]["ties"]
    assert [(t["sphere_id"], t["role"]) for t in saved] == [
        (dawn, "practitioner"),
        (postal, "courier"),
    ]

    # a new character's proposed ties: the owner drops one tie and one
    # exception before accepting
    thing.get_by_role("button", name="Back").click()
    box = page.get_by_test_id("create-box")
    box.get_by_label("Describe it").fill("An old elder of the church.")
    fixed_preview(
        {
            "name": "Marfa",
            "facts": [{"category": "background", "text": "An elder of the church."}],
            "prose": {"description": "Marfa is old."},
            "ties": [
                {
                    "sphere_id": dawn,
                    "sphere": "The White Dawn",
                    "role": "elder",
                    "since": None,
                    "exceptions": [
                        {
                            "text": "Doubts the council's choice of Tsar.",
                            "item": "The Council of Elders",
                            "thing_id": council,
                        },
                        {"text": "Eats before the vigil.", "item": "The White Dawn"},
                    ],
                },
                {
                    "sphere_id": postal,
                    "sphere": "Kalmara Postal Service",
                    "role": "courier",
                    "exceptions": [],
                },
            ],
        }
    )
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("create-preview")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    proposed = preview.get_by_test_id("preview-tie")
    assert proposed.count() == 2
    elder = proposed.filter(has_text="The White Dawn")
    elder.get_by_test_id("preview-tie-exception").filter(
        has_text="Eats before"
    ).get_by_role("button", name="Drop exception").click()
    proposed.filter(has_text="Kalmara Postal Service").get_by_role(
        "button", name="Drop tie"
    ).click()
    expect(proposed).to_have_count(1)
    preview.get_by_role("button", name="Accept").click()
    marfa = _opened(page, "Marfa")
    ties = marfa.get_by_test_id("ties-section")
    tie = ties.get_by_test_id("tie").filter(has_text="The White Dawn")
    tie.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Elder of" in tie.inner_text()
    assert tie.get_by_test_id("tie-exception").count() == 1
    assert "Doubts the council" in tie.inner_text()
    sent = _sent(page, "accept_preview")[-1]["preview"]["ties"]
    assert [len(t["exceptions"]) for t in sent] == [1]
    assert page.console_errors == []


def test_promote_lore_and_place(app, page, fixed_sphere):
    name = _world_name("Promote")
    doctrine = {
        "kind": "lore",
        "name": "The Doctrine of Separation",
        "facts": [{"category": "general", "text": "Issued by the synod."}],
    }
    world = seed_fm_world(app.root, name, present_year=1026, things=[TSARDOM, doctrine])
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    fixed_sphere(
        {
            "sphere": {
                "name": "Anything",
                "summary": "Written from what it was.",
                "aka": [],
                "timeline": [],
                "drawers": [{"type": "beliefs", "title": "Tenets"}],
                "items": [
                    {"drawer": "Tenets", "name": "", "text": "Owls stand apart."}
                ],
                "names": [],
            }
        }
    )

    # a lore entry becomes a religion sphere, keeping its id
    page.get_by_test_id("kind-lore").click()
    lore = _open_thing(page, "The Doctrine of Separation")
    lore.get_by_test_id("make-sphere").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("promoting").filter(
        has_text="The Doctrine of Separation"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    box.get_by_test_id("sphere-template-picker").get_by_role(
        "button", name="Religion"
    ).click()
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("sphere-preview")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    sent = _sent(page, "preview_sphere")[-1]
    assert sent["promote_id"] == world.things["The Doctrine of Separation"]
    assert sent["template"] == "religion"
    preview.get_by_role("button", name="Accept").click()
    sphere = _opened(page, "The Doctrine of Separation")
    sphere.get_by_test_id("sphere-template").filter(
        has_text="sphere · religion"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Owls stand apart." in _drawer_of(sphere, "Tenets").inner_text()

    # a place takes on the nation template and stays a place
    sphere.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-place").click()
    place = _open_thing(page, "Tsardom of Moscavia")
    place.get_by_test_id("make-sphere").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("promoting").filter(has_text="Tsardom of Moscavia").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    box.get_by_test_id("sphere-template-picker").get_by_role(
        "button", name="Nation"
    ).click()
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("sphere-preview")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert (
        _sent(page, "preview_sphere")[-1]["promote_id"]
        == world.things["Tsardom of Moscavia"]
    )
    preview.get_by_role("button", name="Accept").click()
    place = _opened(page, "Tsardom of Moscavia")
    place.get_by_test_id("sphere-template").filter(has_text="sphere · nation").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert place.get_by_test_id("thing-kind").inner_text().strip() == "place"
    assert _drawer_of(place, "Tenets").is_visible()
    # it's a sphere now: no "Make it a sphere…"; its place facts still list
    assert place.get_by_test_id("make-sphere").count() == 0
    assert place.get_by_role("button", name="Add fact").is_visible()

    # both are in the Spheres list, each under its template
    place.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-sphere").click()
    religions = page.get_by_test_id("sphere-group").filter(has_text="Religions")
    religions.get_by_test_id("thing-card").filter(
        has_text="The Doctrine of Separation"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)
    nations = page.get_by_test_id("sphere-group").filter(has_text="Nations")
    assert (
        nations.get_by_test_id("thing-card")
        .filter(has_text="Tsardom of Moscavia")
        .is_visible()
    )
    assert page.console_errors == []


def test_end_item(app, page):
    name = _world_name("Feathers")
    culture = {
        "kind": "sphere",
        "name": "Moscavian culture",
        "fields": {
            "template": "culture",
            "drawers": [_drawer(CUSTOMS, "practices", "Customs and Holidays")],
        },
        "facts": [
            {
                "category": "statement",
                "text": "Owls greet the dawn in silence.",
                "origin": {"drawer": CUSTOMS},
            }
        ],
    }
    dance = {
        "kind": "lore",
        "name": "The Feather Dance",
        "part_of": {"sphere": "Moscavian culture", "drawer": CUSTOMS},
        "facts": [{"category": "general", "text": "Danced at the first snow."}],
    }
    northern = {
        "kind": "sphere",
        "name": "The Northern Folkways",
        "fields": {"template": "culture", "drawers": []},
        "links": {"parent": "Moscavian culture"},
    }
    dawn = {
        "kind": "sphere",
        "name": "The White Dawn",
        "fields": {"template": "religion", "drawers": []},
    }
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[culture, dance, northern, dawn]
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)

    # a branch shows its parent's drawer and items as inherited, with no
    # "End this…": they end in the sphere they come from
    branch = _sphere_card(page, "The Northern Folkways")
    customs = _drawer_of(branch, "Customs and Holidays")
    customs.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "inherited" in customs.get_by_test_id("drawer-inherited").inner_text()
    item = customs.get_by_test_id("drawer-item").filter(has_text="The Feather Dance")
    assert "inherited" in item.get_attribute("class")
    assert item.get_by_test_id("end-item").count() == 0

    # on the culture itself, the White Dawn ends the dance in 1015
    branch.get_by_role("button", name="Back").click()
    thing = _sphere_card(page, "Moscavian culture")
    customs = _drawer_of(thing, "Customs and Holidays")
    item = customs.get_by_test_id("drawer-item").filter(has_text="The Feather Dance")
    item.get_by_test_id("end-item").click()
    form = customs.get_by_test_id("end-item-form")
    form.get_by_label("Ended in (year)").fill("1015")
    form.get_by_test_id("end-by").locator(".v-field").click()
    page.get_by_role("option", name="The White Dawn").click()
    form.get_by_role("button", name="End it").click()
    item.wait_for(state="hidden", timeout=TIMEOUT_MS)
    sent = _sent(page, "end_item")[-1]
    assert sent["thing_id"] == world.things["The Feather Dance"]
    assert sent["by"] == world.things["The White Dawn"]
    assert sent["at"]["precision"] == "year"
    # the statement is still held
    assert "Owls greet the dawn in silence." in customs.inner_text()

    # the ban is on the White Dawn's timeline
    thing.get_by_role("button", name="Back").click()
    dawn_page = _sphere_card(page, "The White Dawn")
    timeline = dawn_page.get_by_test_id("sphere-timeline")
    timeline.filter(has_text="The Feather Dance").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "1015" in timeline.inner_text()
    assert page.console_errors == []


BRANCHES = "b4a2c4e5"


def _already_tied(page, character: str):
    """Tie `character` from the White Dawn's People though it's tied to it
    already (an ended tie): the error that leaves on screen."""
    sphere = _sphere_card(page, "The White Dawn")
    people = _drawer_of(sphere, "People")
    people.get_by_test_id("drawer-add").click()
    people.get_by_label("Character").click()
    page.get_by_role("option", name=character).click()
    people.get_by_test_id("drawer-add-form").get_by_role(
        "button", name="Add", exact=True
    ).click()
    stale = page.get_by_role("alert").filter(has_text="already tied")
    stale.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert not _sent(page, "set_ties")
    sphere.get_by_role("button", name="Back").click()
    return stale


def test_part_of_editor_and_new_branch(app, page, fixed_sphere):
    name = _world_name("Branches")
    dawn = {
        **WHITE_DAWN,
        "fields": {
            **WHITE_DAWN["fields"],
            "drawers": [
                *WHITE_DAWN["fields"]["drawers"],
                _drawer(BRANCHES, "branches", "Schisms"),
            ],
        },
    }
    reformed = {
        "kind": "sphere",
        "name": "The Reformed Dawn",
        "fields": {"template": "religion", "drawers": []},
        "links": {"parent": "The White Dawn"},
    }
    # tied to the White Dawn once, in the past: not among its People now
    marfa = {
        "kind": "character",
        "name": "Marfa",
        "ties": [
            {"sphere": "The White Dawn", "role": "novice", "since": 1001, "until": 1010}
        ],
    }
    seed_fm_world(
        app.root, name, present_year=1026, things=[dawn, COUNCIL, reformed, marfa]
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)

    # tying Marfa again from the sphere: an error left on screen
    stale = _already_tied(page, "Marfa")

    # the council moves from Hierarchy to Doctrines; the old error doesn't
    # make the move look refused
    page.get_by_test_id("kind-lore").click()
    council = _open_thing(page, "The Council of Elders")
    part_of = council.get_by_test_id("part-of")
    assert "Hierarchy" in part_of.inner_text()
    part_of.get_by_test_id("part-of-edit").click()
    editor = part_of.get_by_test_id("part-of-form")
    editor.get_by_test_id("part-of-drawer").locator(".v-field").click()
    # only the drawers a lore entry may go in, and Unsorted
    options = page.get_by_role("option")
    expect(options).to_have_count(4)
    assert "Holy Sites" not in " ".join(options.all_inner_texts())
    page.get_by_role("option", name="Doctrines").click()
    editor.get_by_role("button", name="Save").click()
    part_of.filter(has_text="Doctrines").wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(editor).to_have_count(0)
    # sending cleared it
    expect(stale).to_have_count(0)

    # a tie saved with an old error on screen closes its form too
    council.get_by_role("button", name="Back").click()
    stale = _already_tied(page, "Marfa")
    page.get_by_test_id("kind-character").click()
    character = _open_thing(page, "Marfa")
    ties = character.get_by_test_id("ties-section")
    tie = ties.get_by_test_id("tie").filter(has_text="The White Dawn")
    assert "until 1010" in tie.inner_text()
    tie.get_by_role("button", name="Edit tie").click()
    form = tie.get_by_test_id("tie-form")
    form.get_by_label("Role").fill("lapsed novice")
    assert stale.is_visible()
    form.get_by_role("button", name="Save").click()
    tie.filter(has_text="Lapsed novice of").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(form).to_have_count(0)
    saved = _sent(page, "set_ties")[-1]["ties"][0]
    # the years left alone keep their stored dates
    assert saved["role"] == "lapsed novice"
    assert saved["until"]["precision"] == "year"

    # a sphere can't be part of its own branch: the refusal shows
    council.get_by_role("button", name="Back").click()
    sphere = _sphere_card(page, "The White Dawn")
    part_of = sphere.get_by_test_id("part-of")
    part_of.get_by_test_id("part-of-edit").click()
    editor = part_of.get_by_test_id("part-of-form")
    editor.get_by_test_id("part-of-sphere").locator(".v-field").click()
    page.get_by_role("option", name="The Reformed Dawn").click()
    editor.get_by_role("button", name="Save").click()
    refused = editor.get_by_test_id("part-of-refused")
    refused.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "inside it" in refused.inner_text()
    assert "no sphere" in part_of.inner_text()
    editor.get_by_role("button", name="Cancel").click()
    editor.wait_for(state="hidden", timeout=TIMEOUT_MS)

    # "+ New branch": a prompt, the preview in the drawer, then the branch
    schisms = _drawer_of(sphere, "Schisms")
    assert "The Reformed Dawn" in schisms.inner_text()
    fixed_sphere(
        {
            "branch": {
                "name": "The Forge Dawn",
                "summary": "Smiths who keep the Dawn at the anvil.",
                "aka": [],
                "timeline": [],
                "drawers": [],
                "drops": [],
                "items": [{"drawer": "Doctrines", "text": "The forge is a dawn too."}],
                "names": [],
            }
        }
    )
    schisms.get_by_test_id("drawer-add").click()
    schisms.get_by_label("Describe the branch").fill("the smiths' Dawn")
    schisms.get_by_role("button", name="Preview").click()
    preview = schisms.get_by_test_id("sphere-preview")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert _sent(page, "preview_branch")[-1]["prompt"] == "the smiths' Dawn"
    # the owner rejects the council for this branch
    preview.get_by_test_id("branch-parent-item").filter(
        has_text="The Council of Elders"
    ).get_by_role("checkbox").uncheck()
    preview.get_by_role("button", name="Accept").click()
    branch = _opened(page, "The Forge Dawn")
    branch.get_by_test_id("sphere-parent").filter(has_text="The White Dawn").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    accepted = _sent(page, "accept_sphere")[-1]["preview"]
    assert len(accepted["drops"]) == 1
    doctrines = _drawer_of(branch, "Doctrines")
    assert "The forge is a dawn too." in doctrines.inner_text()
    assert (
        "The Council of Elders" not in branch.get_by_test_id("sphere-page").inner_text()
    )
    assert page.console_errors == []
