"""The entry page (mockup v3, screens A, B, D and E): "In" rows with their
roles, dates and "but…"s, "+ In…" (which can make a stub); Connected,
what's filed in the entry grouped by tag, one line per row, each group
folding, a long one with a filter, its synopsis, its first five rows and
"show all", "✎ Synopsis" and "+ Add", and a row dragged to another group
taking its tag; "Mentioned in", folded; the Timeline's "Events ▾"; "+ Add
facts…" and "+ Add event…"; the tag chip and picker; and the Tags tab's
rename and merge.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`). No
model is asked anything: a fact draft, a synopsis and a group's "+ Add"
come from the fixed reply files, read through the real parsers. What the
page sends is read back from a websocket spy.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_connections_create import _opened, _wait_sent
from e2e.worlds.test_drafts import _draft
from e2e.worlds.test_new_scene import SEND_SPY_JS, _sent
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

# records what the app's backend socket receives (`seed.SOCKET_HOOK_JS`
# keeps its sockets)
RECEIVE_SPY_JS = """
() => {
    window.__e2eGot = [];
    for (const socket of window.__e2eSockets || []) {
        socket.addEventListener('message', (event) => window.__e2eGot.push(event.data));
    }
}
"""

TSARDOM = {"kind": "place", "name": "Tsardom of Moscavia", "fields": {"tag": "nation"}}

VELIKOYE = {
    "kind": "place",
    "name": "Velikoye",
    "fields": {"tag": "capital", "hint": "nation"},
    "filings": [{"target": "Tsardom of Moscavia", "since": 412}],
    "facts": [
        {
            "category": "description",
            "text": "The fortified capital of Moscavia, built where the river"
            " bends below a bluff.",
            "origin": {"summary": True},
        },
        {"category": "history", "text": "Walled in stone.", "since": 600},
    ],
}

SUMMARY = "The fortified capital of Moscavia"


def _in(target, role=None, since=None, until=None):
    return {"target": target, "role": role, "since": since, "until": until}


def _entry(kind, name, tag, filings, line=None, **extra):
    thing = {"kind": kind, "name": name, "fields": {"tag": tag}, "filings": filings}
    if line:
        thing["facts"] = [{"category": _CATEGORY[kind], "text": line}]
    thing["fields"].update(extra.pop("fields", {}))
    thing.update(extra)
    return thing


_CATEGORY = {
    "place": "description",
    "lore": "general",
    "character": "background",
    "being": "nature",
    "event": "summary",
}

MOSCAVIA = [
    TSARDOM,
    VELIKOYE,
    _entry(
        "place",
        "Khorol River",
        "river",
        [_in("Tsardom of Moscavia"), _in("Velikoye", "runs through")],
        "Freezes into the capital's winter road and moat.",
    ),
    _entry(
        "lore",
        "The Night Court",
        "institution",
        [_in("Velikoye", since=995)],
        "The nocturnal council.",
    ),
    _entry(
        "lore",
        "The Academy of the Chiseled Moon",
        "institution",
        [_in("Velikoye", since=1003)],
        "The runic academy.",
    ),
    _entry(
        "place",
        "Nocturnal Institute of Velikoye",
        "institution",
        [_in("Velikoye")],
        stub="live",
    ),
    _entry(
        "place",
        "Wattle Row",
        "district",
        [_in("Velikoye")],
        "The street of wattlemakers.",
        stub="live",
    ),
    _entry(
        "lore",
        "The Feather Dance",
        "custom",
        [_in("Velikoye", since=900, until=1015)],
        "A winter courtship dance.",
    ),
    _entry(
        "character",
        "Tsar Dmitry IV",
        "ruler",
        [
            _in("Tsardom of Moscavia", "sovereign", since=979),
            _in("Velikoye", "rules from here"),
        ],
        "The owl-tsar.",
    ),
    # a believed being filed in Velikoye is never one of its people; a
    # real one is
    _entry(
        "being",
        "The Eternal Light",
        "god",
        [_in("Velikoye", "worshipped")],
        "A light that never dims.",
        fields={"existence": "believed"},
    ),
    _entry(
        "being",
        "The Bluff Spirit",
        "spirit",
        [_in("Velikoye", "guards")],
        "Lives in the bluff.",
        fields={"existence": "real"},
    ),
    _entry(
        "event",
        "The Great Freeze",
        "disaster",
        [_in("Velikoye")],
    ),
    {
        "kind": "species",
        "name": "Owl-folk",
        "facts": [
            {"category": "origin", "text": "First nested at [[@Velikoye|Velikoye]]."}
        ],
    },
]

# the event's own dated fact, gathered on Velikoye's Timeline
MOSCAVIA[-2]["facts"] = [
    {"category": "summary", "text": "The Khorol froze to the sea floor.", "since": 990}
]


def _group(thing, heading: str):
    return (
        thing.get_by_test_id("entry-connected")
        .get_by_test_id("connected-group")
        .filter(
            has=thing.page.get_by_test_id("group-heading").get_by_text(
                heading, exact=True
            )
        )
    )


def _headings(thing) -> list[str]:
    return (
        thing.get_by_test_id("entry-connected")
        .get_by_test_id("group-heading")
        .all_inner_texts()
    )


def _row(scope, name: str):
    return scope.get_by_test_id("connected-row").filter(has_text=name)


def _open_velikoye(page, app, name: str, things=MOSCAVIA):
    world = seed_fm_world(app.root, name, present_year=1020, things=things)
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    return world, _open_thing(page, "Velikoye")


def _pick(page, field, option: str) -> None:
    """Pick `option` in a Vuetify select or autocomplete (`field`)."""

    field.locator(".v-field").click()
    page.get_by_role("option", name=option).first.click()


def test_velikoye_connected_by_tag(app, page):
    world, thing = _open_velikoye(page, app, _world_name("Velikoye"))

    # the header: its kind, its tag and the prompt hint it was written with
    assert thing.get_by_test_id("thing-kind").inner_text() == "place"
    expect(thing.get_by_test_id("tag-chip")).to_have_text("capital")
    assert "nation" in thing.get_by_test_id("thing-hint").inner_text()

    # "In": the Tsardom, since 412; then its summary
    rows = thing.get_by_test_id("entry-in").get_by_test_id("in-row")
    expect(rows).to_have_count(1)
    expect(rows).to_contain_text("Tsardom of Moscavia")
    expect(rows).to_contain_text("since 412")
    expect(thing.get_by_test_id("entry-summary")).to_contain_text(SUMMARY)

    # Connected, grouped by tag, largest group first
    headings = _headings(thing)
    assert headings[0] == "Institutions"
    assert set(headings) == {
        "Institutions",
        "Rivers",
        "Districts",
        "Customs",
        "Rulers",
        "Spirits",
        "Gods",
        "Disasters",
    }
    institutions = _group(thing, "Institutions")
    expect(institutions.get_by_test_id("group-count")).to_have_text("3")
    # one line per row: its name, its own summary, the filing's dates
    court = _row(institutions, "The Night Court")
    expect(court).to_contain_text("The nocturnal council.")
    expect(court).to_contain_text("since 995")
    institute = _row(institutions, "Nocturnal Institute of Velikoye")
    expect(institute).to_contain_text("stub")
    expect(_row(_group(thing, "Rivers"), "Khorol River")).to_contain_text(
        "runs through"
    )
    expect(_row(_group(thing, "Rulers"), "Tsar Dmitry IV")).to_contain_text(
        "rules from here"
    )
    # an ended filing shows at the latest telling with its dates
    expect(_row(_group(thing, "Customs"), "The Feather Dance")).to_contain_text(
        "900–1015"
    )
    # a believed god is shown, marked believed (ruling F24); a real spirit
    # isn't marked
    light = _row(_group(thing, "Gods"), "The Eternal Light")
    expect(light.get_by_test_id("connected-believed")).to_have_text("believed")
    spirit = _row(_group(thing, "Spirits"), "The Bluff Spirit")
    expect(spirit).to_be_visible()
    expect(spirit.get_by_test_id("connected-believed")).to_have_count(0)
    expect(thing.get_by_test_id("connected-count")).to_contain_text("10 entries")

    # a group folds
    customs = _group(thing, "Customs")
    customs.get_by_test_id("group-fold").click()
    expect(_row(customs, "The Feather Dance")).to_have_count(0)
    customs.get_by_test_id("group-fold").click()
    expect(_row(customs, "The Feather Dance")).to_be_visible()

    # Mentioned in: folded, then the Owl-folk
    mentioned = thing.get_by_test_id("entry-mentioned")
    expect(mentioned).to_contain_text("Mentioned in")
    expect(mentioned.get_by_test_id("mentioned-row")).to_have_count(0)
    mentioned.get_by_text("Mentioned in").click()
    expect(mentioned.get_by_test_id("mentioned-row")).to_have_text(["Owl-folk"])

    # the Timeline: every dated fact, or the events only
    timeline = thing.get_by_test_id("entry-timeline")
    expect(timeline.get_by_test_id("timeline-row")).to_have_count(2)
    timeline.get_by_test_id("timeline-filter").click()
    page.get_by_test_id("timeline-events").click()
    expect(timeline.get_by_test_id("timeline-row")).to_have_count(1)
    expect(timeline.get_by_test_id("timeline-row")).to_contain_text("froze to the sea")

    # a folded group is this page's own: the next page's starts unfolded
    _group(thing, "Rivers").get_by_test_id("group-fold").click()
    expect(_row(_group(thing, "Rivers"), "Khorol River")).to_have_count(0)
    thing.get_by_test_id("in-row").get_by_test_id("in-target-link").click()
    tsardom = _opened(page, "Tsardom of Moscavia")
    expect(_row(_group(tsardom, "Rivers"), "Khorol River")).to_be_visible()
    tsardom.get_by_role("button", name="Back").click()
    thing = _opened(page, "Velikoye")

    # a row opens its page, whose "In" lists both places (screen D)
    _row(_group(thing, "Rivers"), "Khorol River").get_by_test_id(
        "connected-name"
    ).click()
    river = _opened(page, "Khorol River")
    expect(river.get_by_test_id("in-row")).to_have_count(2)
    expect(river.get_by_test_id("in-row").filter(has_text="Velikoye")).to_contain_text(
        "Runs through Velikoye"
    )
    assert page.console_errors == []


def test_add_filing_and_role(app, page):
    name = _world_name("Dmitry")
    seed_fm_world(app.root, name, present_year=1020, things=MOSCAVIA)
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    world_things = page.get_by_test_id("world-list")
    thing = _open_thing(page, "Tsar Dmitry IV")
    entry_in = thing.get_by_test_id("entry-in")
    expect(entry_in.get_by_test_id("in-row")).to_have_count(2)

    # "+ In…": an entry the world has, with a role and a year
    entry_in.get_by_test_id("in-add").click()
    form = entry_in.get_by_test_id("in-add-form")
    form.get_by_test_id("in-target").locator("input").fill("Night Court")
    page.get_by_role("option", name="The Night Court").click()
    form.get_by_label("Role (optional)").fill("presides")
    form.get_by_label("Since (year)").fill("995")
    form.get_by_role("button", name="File it").click()
    sent = _wait_sent(page, "add_filing")
    assert sent["role"] == "presides"
    assert sent["since"]["precision"] == "year"
    court = entry_in.get_by_test_id("in-row").filter(has_text="The Night Court")
    expect(court).to_contain_text("Presides of The Night Court")
    expect(court).to_contain_text("since 995")

    # a name the world hasn't: a stub of it, filed here
    entry_in.get_by_test_id("in-add").click()
    form = entry_in.get_by_test_id("in-add-form")
    form.get_by_test_id("in-target").locator("input").fill("The Frost Council")
    page.get_by_role("option", name="Make a stub “The Frost Council”").click()
    expect(form.get_by_test_id("in-new-note")).to_contain_text("The Frost Council")
    form.get_by_role("button", name="File it").click()
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'add_filing').length === 2"
    )
    sent = _sent(page, "add_filing")[-1]
    assert sent["new_name"] == "The Frost Council"
    assert "target_id" not in sent
    expect(
        entry_in.get_by_test_id("in-row").filter(has_text="The Frost Council")
    ).to_be_visible()
    world_things.get_by_test_id("stub-item").filter(
        has_text="The Frost Council"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # the role changed, then "End this" in 1010: its span shows
    court = entry_in.get_by_test_id("in-row").filter(has_text="The Night Court")
    court.get_by_test_id("in-edit").click()
    edit = entry_in.get_by_test_id("in-edit-form")
    edit.get_by_label("Role").fill("presides over it")
    edit.get_by_role("button", name="Save").click()
    sent = _wait_sent(page, "edit_filing")
    assert sent["role"] == "presides over it"
    assert "since" not in sent and "until" not in sent
    expect(court).to_contain_text("Presides over it of The Night Court")
    court.get_by_test_id("in-end").click()
    end = entry_in.get_by_test_id("in-end-form")
    end.get_by_label("Year").fill("1010")
    end.get_by_role("button", name="End it").click()
    expect(court).to_contain_text("995–1010")
    assert _sent(page, "edit_filing")[-1]["until"]["precision"] == "year"

    # a person's "but…" shows under its row
    tsardom = entry_in.get_by_test_id("in-row").filter(has_text="Tsardom of Moscavia")
    tsardom.get_by_test_id("in-add-but").click()
    but = entry_in.get_by_test_id("in-but-form")
    but.get_by_label("How they differ").fill("Rules only in winter.")
    but.get_by_role("button", name="Add").click()
    expect(entry_in.get_by_test_id("in-but")).to_contain_text("Rules only in winter.")
    assert _wait_sent(page, "add_exception")["text"] == "Rules only in winter."

    # on the Court's page the Tsar is under Rulers, its role and span beside
    court.get_by_test_id("in-target-link").click()
    court_page = _opened(page, "The Night Court")
    row = _row(_group(court_page, "Rulers"), "Tsar Dmitry IV")
    expect(row).to_contain_text("presides over it")
    expect(row).to_contain_text("995–1010")
    court_page.get_by_role("button", name="Back").click()

    # removed: the row goes
    thing = _opened(page, "Tsar Dmitry IV")
    council = thing.get_by_test_id("in-row").filter(has_text="The Frost Council")
    council.get_by_test_id("in-remove").click()
    expect(council).to_have_count(0)
    assert page.console_errors == []


USTYUG = [
    {"kind": "place", "name": "Velikiy Ustyug", "fields": {"tag": "city"}},
    _entry("lore", "Postal HQ", "institution", [], "The owl post's seat."),
    _entry(
        "character",
        "Mikhail",
        "smith",
        [_in("Velikiy Ustyug", "native")],
        "Forges the post's rings.",
    ),
    _entry(
        "character",
        "Olga",
        "postal worker",
        [_in("Postal HQ", "carrier owl")],
        "Flies the winter route.",
    ),
    _entry(
        "character",
        "Vasha",
        "postal worker",
        [_in("Postal HQ", "carrier owl", since=995)],
        "A young carrier owl.",
    ),
]


def _picker(page):
    """The tag picker open now (one closed earlier may still be in the
    page, hidden)."""

    return page.locator('[data-testid="tag-picker"]:visible')


NOVGRAD = {"kind": "place", "name": "Novgrad", "fields": {"tag": "city"}}

ACADEMY = _entry(
    "place",
    "Novgrad Academy",
    "institution",
    [_in("Novgrad", role="located in", since=900)],
    "A seat of higher learning.",
)


def _in_section_above_facts(page, scope) -> None:
    """ "In" is a section of the left column, just above Facts: its
    heading above the Facts heading and inside the Facts column, "+ In…"
    in its heading's row, a row reading role first ("Located in
    Novgrad"), and no subtitle about the AI's suggestions."""

    heading = scope.get_by_test_id("in-heading")
    heading.wait_for(state="visible", timeout=TIMEOUT_MS)
    facts = scope.get_by_test_id("facts-heading").bounding_box()
    box = heading.bounding_box()
    assert box["y"] + box["height"] <= facts["y"]
    assert box["x"] >= facts["x"] - 1
    assert box["x"] + box["width"] <= facts["x"] + facts["width"] + 1
    add = heading.get_by_test_id("in-add").bounding_box()
    assert box["y"] <= add["y"] + add["height"] / 2 <= box["y"] + box["height"]
    assert add["x"] + add["width"] > box["x"] + box["width"] - 4
    row = scope.locator('[data-testid="in-row"], [data-testid="draft-in-row"]').filter(
        has_text="Novgrad"
    )
    expect(row.locator(".filed-as")).to_have_text(
        re.compile(r"^\s*located in\s+Novgrad\s*$", re.IGNORECASE)
    )
    expect(scope.get_by_text("AI's suggestions")).to_have_count(0)


def test_in_section_above_facts(app, page, fixed_preview):
    """On a saved page and on a draft alike."""

    name = _world_name("InSection")
    seed_fm_world(app.root, name, present_year=1020, things=[NOVGRAD, ACADEMY])
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    _in_section_above_facts(page, _open_thing(page, "Novgrad Academy"))

    fixed_preview(
        {
            "name": "Novgrad Observatory",
            "facts": [{"category": "description", "text": "A tower of brass lenses."}],
            "in": [{"entry": "Novgrad", "role": "located in"}],
            "prose": {"description": "A brass tower over Novgrad."},
        }
    )
    draft = _draft(page, "place", "Novgrad's observatory.")
    _in_section_above_facts(page, draft)
    assert page.console_errors == []


def test_file_with_show_under_and_role_picker(app, page):
    """Vasha, a postal worker, filed in his hometown as a native: the role
    picked from the roles in use, the group he shows under there picked
    from the tag pool. His In row reads "Native of Velikiy Ustyug"; on the
    town's page he is under Natives, not Postal workers, until the filing
    goes back to his own tag."""

    name = _world_name("Ustyug")
    world = seed_fm_world(app.root, name, present_year=1020, things=USTYUG)
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    thing = _open_thing(page, "Vasha")
    entry_in = thing.get_by_test_id("entry-in")
    post = entry_in.get_by_test_id("in-row").filter(has_text="Postal HQ")
    expect(post.get_by_test_id("in-role-text")).to_have_text("Carrier owl of")
    # no group named: it shows under the entry's own tag
    expect(post.get_by_test_id("in-show-under")).to_have_text(
        "shows under postal worker"
    )

    entry_in.get_by_test_id("in-add").click()
    form = entry_in.get_by_test_id("in-add-form")
    form.get_by_test_id("in-target").locator("input").fill("Ustyug")
    page.get_by_role("option", name="Velikiy Ustyug").click()
    # the role picker: the roles in use, most used first; a hint to relate
    role = form.get_by_label("Role (optional)")
    _wait_sent(page, "list_roles")
    role.click()
    expect(role).to_have_attribute("placeholder", "native, member, branch of…")
    options = page.get_by_role("option")
    expect(options.filter(has_text="carrier owl")).to_have_count(1)
    page.get_by_role("option", name="native", exact=True).click()
    # "shows under": the tag picker, a new tag made in it
    form.get_by_test_id("in-show-under").click()
    picker = _picker(page)
    picker.get_by_test_id("tag-search").locator("input").fill("Native")
    new = picker.get_by_test_id("tag-new")
    expect(new).to_contain_text("new tag “native”")
    new.click()
    expect(form.get_by_test_id("in-show-under")).to_have_text("shows under native")
    form.get_by_role("button", name="File it").click()
    sent = _wait_sent(page, "add_filing")
    assert (sent["target_id"], sent["role"], sent["show_under"]) == (
        world.things["Velikiy Ustyug"],
        "native",
        "native",
    )

    # read the entry's way
    town = entry_in.get_by_test_id("in-row").filter(has_text="Velikiy Ustyug")
    expect(town).to_contain_text("Native of Velikiy Ustyug")
    expect(town.get_by_test_id("in-show-under")).to_have_text("shows under native")

    # on the town's page: under Natives, not Postal workers (Mikhail, a
    # native too but naming no group, is under his own tag)
    town.get_by_test_id("in-target-link").click()
    ustyug = _opened(page, "Velikiy Ustyug")
    natives = _group(ustyug, "Natives")
    expect(_row(natives, "Vasha")).to_contain_text("native")
    assert "Postal workers" not in _headings(ustyug)
    assert "Smiths" in _headings(ustyug)
    ustyug.get_by_role("button", name="Back").click()

    # back to his own tag: under Postal workers there
    thing = _opened(page, "Vasha")
    town = (
        thing.get_by_test_id("entry-in")
        .get_by_test_id("in-row")
        .filter(has_text="Velikiy Ustyug")
    )
    town.get_by_test_id("in-show-under").click()
    _picker(page).get_by_test_id("tag-clear").click()
    sent = _wait_sent(page, "edit_filing")
    assert (sent["target_id"], sent["show_under"]) == (
        world.things["Velikiy Ustyug"],
        None,
    )
    expect(town.get_by_test_id("in-show-under")).to_have_text(
        "shows under postal worker"
    )
    town.get_by_test_id("in-target-link").click()
    ustyug = _opened(page, "Velikiy Ustyug")
    expect(_row(_group(ustyug, "Postal workers"), "Vasha")).to_be_visible()
    assert "Natives" not in _headings(ustyug)
    assert page.console_errors == []


NATIVES = [
    {"kind": "place", "name": "Velikiy Ustyug", "fields": {"tag": "city"}},
    _entry(
        "character",
        "Vasha",
        "postal worker",
        [{**_in("Velikiy Ustyug"), "show_under": "native"}],
        "A young carrier owl.",
    ),
    _entry("character", "Mikhail", "smith", [_in("Velikiy Ustyug")], "A smith."),
    {
        "kind": "lore",
        "name": "The Bell Fair",
        "filings": [_in("Velikiy Ustyug")],
        "facts": [{"category": "general", "text": "A summer fair."}],
    },
]


def test_add_and_drag_into_a_show_under_group(app, page, fixed_group_add):
    """H5: the town's Natives exist only through Vasha's `show_under`.
    "+ Add" there drafts natives that keep their own tag and show under
    Natives; dragging Mikhail the smith onto it changes only his filing
    here, never his tag. "Other" says a row dropped there goes back under
    its own tag."""

    name = _world_name("Natives")
    world = seed_fm_world(app.root, name, present_year=1020, things=NATIVES)
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    town = _open_thing(page, "Velikiy Ustyug")
    natives = _group(town, "Natives")
    expect(_row(natives, "Vasha")).to_be_visible()

    fixed_group_add(
        {
            "entries": [
                {
                    "name": "Old Fyodor",
                    "kind": "character",
                    "tag": "ferryman",
                    "line": "Ferries the Sukhona.",
                }
            ]
        }
    )
    natives.get_by_test_id("group-add-button").click()
    form = natives.get_by_test_id("group-add")
    form.get_by_test_id("group-add-prompt").locator("textarea").first.fill("a native")
    form.get_by_test_id("group-add-draft").click()
    sent = _wait_sent(page, "group_add")
    assert (sent["tag"], sent["show_under"]) == ("native", True)
    row = form.get_by_test_id("group-add-row")
    expect(row).to_have_count(1)
    expect(row).to_contain_text("ferryman")
    expect(row.get_by_test_id("group-add-row-show-under")).to_have_text(
        "shows under Natives"
    )
    form.get_by_test_id("group-add-accept").click()
    sent = _wait_sent(page, "accept_group_add")
    assert [(r["tag"], r["show_under"]) for r in sent["rows"]] == [
        ("ferryman", "native")
    ]
    expect(_row(_group(town, "Natives"), "Old Fyodor")).to_be_visible()
    assert "Ferrymen" not in _headings(town)

    # Mikhail dragged onto Natives: his filing shows under it, his tag
    # stays "smith"
    _row(_group(town, "Smiths"), "Mikhail").drag_to(
        _group(town, "Natives").get_by_test_id("group-heading")
    )
    sent = _wait_sent(page, "edit_filing")
    assert (sent["thing_id"], sent["target_id"], sent["show_under"]) == (
        world.things["Mikhail"],
        world.things["Velikiy Ustyug"],
        "native",
    )
    expect(_row(_group(town, "Natives"), "Mikhail")).to_be_visible()
    assert "Smiths" not in _headings(town)
    assert _sent(page, "set_tag") == []

    # "Other": dropping a row there puts it back under its own tag
    expect(_group(town, "Other")).to_have_attribute(
        "title", re.compile("back under its own tag")
    )
    assert page.console_errors == []


def test_change_tag_moves_group(app, page):
    world, thing = _open_velikoye(page, app, _world_name("Retag"))
    expect(_row(_group(thing, "Rivers"), "Khorol River")).to_be_visible()

    # the river's own tag chip: another tag in use, from the picker
    _row(_group(thing, "Rivers"), "Khorol River").get_by_test_id(
        "connected-name"
    ).click()
    river = _opened(page, "Khorol River")
    river.get_by_test_id("tag-chip").click()
    picker = page.get_by_test_id("tag-picker")
    picker.get_by_test_id("tag-search").locator("input").fill("dis")
    option = picker.get_by_test_id("tag-option").filter(has_text="district")
    expect(option).to_contain_text("1 entry")
    option.click()
    sent = _wait_sent(page, "set_tag")
    assert (sent["thing_id"], sent["tag"]) == (world.things["Khorol River"], "district")
    expect(river.get_by_test_id("tag-chip")).to_have_text("district")

    # back on Velikoye it moved to Districts, and Rivers is gone
    river.get_by_role("button", name="Back").click()
    thing = _opened(page, "Velikoye")
    expect(_row(_group(thing, "Districts"), "Khorol River")).to_be_visible()
    assert "Rivers" not in _headings(thing)

    # a new tag, made in the picker
    thing.get_by_test_id("tag-chip").first.click()
    picker = page.get_by_test_id("tag-picker")
    picker.get_by_test_id("tag-search").locator("input").fill("Royal Seat, old")
    new = picker.get_by_test_id("tag-new")
    expect(new).to_contain_text("new tag “royal seat”")
    new.click()
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'set_tag').length === 2"
    )
    assert _sent(page, "set_tag")[-1]["tag"] == "royal seat"
    expect(thing.get_by_test_id("tag-chip").first).to_have_text("royal seat")

    # dragging a row to another group gives it that group's tag
    _row(_group(thing, "Districts"), "Wattle Row").drag_to(
        _group(thing, "Institutions").get_by_test_id("group-heading")
    )
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'set_tag').length === 3"
    )
    sent = _sent(page, "set_tag")[-1]
    assert (sent["thing_id"], sent["tag"]) == (
        world.things["Wattle Row"],
        "institution",
    )
    expect(_row(_group(thing, "Institutions"), "Wattle Row")).to_be_visible()
    expect(_group(thing, "Institutions").get_by_test_id("group-count")).to_have_text(
        "4"
    )

    # by keyboard: a row's "move to group" menu
    move = _row(_group(thing, "Institutions"), "Wattle Row").get_by_test_id(
        "connected-move"
    )
    move.focus()
    page.keyboard.press("Enter")
    page.get_by_test_id("connected-move-option").filter(has_text="Customs").click()
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'set_tag').length === 4"
    )
    assert _sent(page, "set_tag")[-1]["tag"] == "custom"
    expect(_row(_group(thing, "Customs"), "Wattle Row")).to_be_visible()

    # the list is reached by keyboard: Enter on an entry opens it
    card = page.get_by_test_id("thing-card").filter(has_text="Tsar Dmitry IV")
    card.focus()
    page.keyboard.press("Enter")
    _opened(page, "Tsar Dmitry IV")
    assert page.console_errors == []


CUSTOMS = [
    ("The Feather Dance", "A winter courtship dance."),
    ("Wattles", "Ornamental throat-feather bands."),
    ("Wattle removal before meals", "Bands come off at table."),
    ("The Moulting Fast", "No meat while the feathers drop."),
    ("Perch Right", "Elders roost highest."),
    ("The Dusk Call", "A cry at dusk from every roof."),
    ("Egg Naming", "A chick is named before it hatches."),
    ("The Long Glide", "A youth's first flight off the bluff."),
]

SYNOPSIS = "Velikoye's customs follow the owl-folk's year, from moult to glide."


def test_big_group_folds(app, page, fixed_group_synopsis):
    things = [
        TSARDOM,
        VELIKOYE,
        *[_entry("lore", n, "custom", [_in("Velikoye")], line) for n, line in CUSTOMS],
        _entry("place", "Khorol River", "river", [_in("Velikoye")], "A river."),
    ]
    world, thing = _open_velikoye(page, app, _world_name("Customs"), things)
    customs = _group(thing, "Customs")

    # a long group: its filter box, its first five rows, then "show all"
    expect(customs.get_by_test_id("group-count")).to_have_text("8")
    expect(customs.get_by_test_id("group-filter")).to_be_visible()
    expect(customs.get_by_test_id("connected-row")).to_have_count(5)
    show_all = customs.get_by_test_id("group-show-all")
    expect(show_all).to_have_text("show all 8")
    show_all.click()
    expect(customs.get_by_test_id("connected-row")).to_have_count(8)
    customs.get_by_test_id("group-show-fewer").click()
    expect(customs.get_by_test_id("connected-row")).to_have_count(5)

    # the filter finds by name or line, among all of them
    customs.get_by_test_id("group-filter").locator("input").fill("glide")
    expect(customs.get_by_test_id("connected-row")).to_have_count(1)
    expect(customs.get_by_test_id("connected-row")).to_contain_text(
        "The Long Glide — A youth's first flight off the bluff."
    )
    customs.get_by_test_id("group-filter").locator("input").fill("")
    expect(customs.get_by_test_id("connected-row")).to_have_count(5)

    # a short group has neither
    rivers = _group(thing, "Rivers")
    expect(rivers.get_by_test_id("group-filter")).to_have_count(0)
    expect(rivers.get_by_test_id("group-show-all")).to_have_count(0)

    # "✎ Synopsis": asked for, then shown after the filter, before the rows
    fixed_group_synopsis({"synopsis": SYNOPSIS})
    customs.get_by_test_id("group-synopsis-button").click()
    sent = _wait_sent(page, "group_synopsis")
    assert (sent["thing_id"], sent["tag"], sent["force"]) == (
        world.things["Velikoye"],
        "custom",
        False,
    )
    synopsis = customs.get_by_test_id("group-synopsis")
    expect(synopsis).to_have_text(SYNOPSIS)
    order = customs.evaluate(
        """(group) => ['group-filter', 'group-synopsis', 'connected-row'].map(
            (id) => [...group.querySelectorAll('*')].indexOf(
                group.querySelector(`[data-testid="${id}"]`)))"""
    )
    assert order == sorted(order)

    # shown again when the page is opened again; asking again forces it
    thing.get_by_test_id("in-row").get_by_test_id("in-target-link").click()
    _opened(page, "Tsardom of Moscavia").get_by_role("button", name="Back").click()
    thing = _opened(page, "Velikoye")
    expect(_group(thing, "Customs").get_by_test_id("group-synopsis")).to_have_text(
        SYNOPSIS
    )
    _group(thing, "Customs").get_by_test_id("group-synopsis-button").click()
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'group_synopsis').length === 2"
    )
    assert _sent(page, "group_synopsis")[-1]["force"] is True

    # folded: only its heading
    _group(thing, "Customs").get_by_test_id("group-fold").click()
    expect(_group(thing, "Customs").get_by_test_id("connected-row")).to_have_count(0)
    expect(_group(thing, "Customs").get_by_test_id("group-synopsis")).to_have_count(0)
    assert page.console_errors == []


def test_group_add_rows(app, page, fixed_group_add, fixed_facts):
    world, thing = _open_velikoye(page, app, _world_name("Adds"))

    # a group's "+ Add": draft rows in the group, ticked, a name editable
    fixed_group_add(
        {
            "entries": [
                {
                    "name": "The Icewrights",
                    "kind": "lore",
                    "tag": "institution",
                    "line": "A guild of ice-road pilots.",
                },
                {
                    "name": "The Owl Post",
                    "kind": "lore",
                    "tag": "institution",
                    "line": "Carries the Tsar's letters.",
                },
            ]
        }
    )
    institutions = _group(thing, "Institutions")
    institutions.get_by_test_id("group-add-button").click()
    form = institutions.get_by_test_id("group-add")
    form.get_by_test_id("group-add-prompt").locator("textarea").first.fill(
        "two more guilds"
    )
    form.get_by_test_id("group-add-draft").click()
    sent = _wait_sent(page, "group_add")
    assert (sent["tag"], sent["prompt"]) == ("institution", "two more guilds")
    rows = form.get_by_test_id("group-add-row")
    expect(rows).to_have_count(2)
    rows.nth(1).get_by_role("checkbox").uncheck()
    rows.nth(0).locator(".draft-name input").fill("The Ice Guild")
    form.get_by_test_id("group-add-accept").click()
    sent = _wait_sent(page, "accept_group_add")
    assert [(r["name"], r["ticked"]) for r in sent["rows"]] == [
        ("The Ice Guild", True),
        ("The Owl Post", False),
    ]
    # written as a stub filed here, its line its summary
    row = _row(_group(thing, "Institutions"), "The Ice Guild")
    expect(row).to_contain_text("A guild of ice-road pilots.")
    expect(_group(thing, "Institutions").get_by_test_id("group-count")).to_have_text(
        "4"
    )
    expect(thing.get_by_test_id("entry-connected")).not_to_contain_text("The Owl Post")

    # the page's own "+ Add": no tag preset, each row its own
    fixed_group_add(
        {
            "entries": [
                {
                    "name": "The Bluff Stair",
                    "kind": "place",
                    "tag": "landmark",
                    "line": "A thousand steps cut in the bluff.",
                }
            ]
        }
    )
    connected = thing.get_by_test_id("entry-connected")
    connected.get_by_test_id("connected-add").click()
    form = connected.get_by_test_id("group-add").first
    form.get_by_test_id("group-add-prompt").locator("textarea").first.fill("a landmark")
    form.get_by_test_id("group-add-draft").click()
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'group_add').length === 2"
    )
    assert _sent(page, "group_add")[-1]["tag"] is None
    expect(form.get_by_test_id("group-add-row")).to_have_count(1)
    form.get_by_test_id("group-add-accept").click()
    expect(_row(_group(thing, "Landmarks"), "The Bluff Stair")).to_be_visible()

    # a row naming an entry the world has reuses it, which keeps its own
    # tag: the note says where it's listed (final review M4)
    fixed_group_add(
        {
            "entries": [
                {
                    "name": "The Bluff Stair",
                    "kind": "place",
                    "tag": "institution",
                    "line": "The stair-keepers' hall.",
                }
            ]
        }
    )
    institutions = _group(thing, "Institutions")
    institutions.get_by_test_id("group-add-button").click()
    form = institutions.get_by_test_id("group-add")
    form.get_by_test_id("group-add-prompt").locator("textarea").first.fill("the stair")
    form.get_by_test_id("group-add-draft").click()
    expect(form.get_by_test_id("group-add-row")).to_have_count(1)
    form.get_by_test_id("group-add-accept").click()
    expect(page.get_by_test_id("accept-notes")).to_contain_text(
        "The Bluff Stair was in the world already: it keeps its tag "
        "\u201clandmark\u201d, so it's listed under Landmarks, not Institutions"
    )
    expect(_row(_group(thing, "Landmarks"), "The Bluff Stair")).to_be_visible()

    # "+ Add facts…": a small draft to tick, written on Accept
    fixed_facts(
        {
            "facts": [
                {"category": "law", "text": "Nobody may fly over the palace."},
                {"category": "general", "text": "Its bells ring at dusk."},
            ]
        }
    )
    thing.get_by_test_id("add-facts").click()
    thing.get_by_test_id("add-facts-form").get_by_label("What to add").fill("its laws")
    thing.get_by_test_id("add-draft").click()
    draft = thing.get_by_test_id("fact-draft")
    expect(draft.get_by_test_id("fact-draft-row")).to_have_count(2)
    draft.get_by_test_id("fact-draft-row").nth(1).get_by_role("checkbox").uncheck()
    draft.get_by_test_id("fact-draft-accept").click()
    sent = _wait_sent(page, "accept_facts")
    assert [f["ticked"] for f in sent["draft"]["facts"]] == [True, False]
    _fact(thing, "Nobody may fly over the palace.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(_fact(thing, "Its bells ring at dusk.")).to_have_count(0)

    # "+ Add event…": its facts dated the year, on the Timeline
    fixed_facts({"facts": [{"category": "history", "text": "The bluff gave way."}]})
    timeline = thing.get_by_test_id("entry-timeline")
    timeline.get_by_test_id("add-event").click()
    timeline.get_by_label("What happened").fill("the bluff collapse")
    timeline.get_by_test_id("add-year").locator("input").fill("1012")
    timeline.get_by_test_id("add-draft").click()
    sent = _wait_sent(page, "add_event")
    assert sent["year"] == 1012
    timeline.get_by_test_id("fact-draft-accept").click()
    expect(
        timeline.get_by_test_id("timeline-row").filter(has_text="The bluff gave way.")
    ).to_contain_text("1012")
    assert page.console_errors == []


def test_group_add_regenerate_keeps_prompt(app, page, fixed_group_add):
    """A group's "+ Add" has a page draft's feature set (plan "polish-1"):
    an edited row's name, the prompt kept and editable in the bar,
    Regenerate from it, "Version n of m", each version's edits kept, and
    Add sends the accepted draft's key."""

    world, thing = _open_velikoye(page, app, _world_name("GroupAddVersions"))
    fixed_group_add(
        {
            "entries": [
                {
                    "name": "The Icewrights",
                    "kind": "lore",
                    "tag": "institution",
                    "line": "A guild of ice-road pilots.",
                },
                {
                    "name": "The Owl Post",
                    "kind": "lore",
                    "tag": "institution",
                    "line": "Carries the Tsar's letters.",
                },
            ]
        }
    )
    institutions = _group(thing, "Institutions")
    institutions.get_by_test_id("group-add-button").click()
    form = institutions.get_by_test_id("group-add")
    form.get_by_test_id("group-add-prompt").locator("textarea").first.fill(
        "two more guilds"
    )
    form.get_by_test_id("group-add-draft").click()
    _wait_sent(page, "group_add")
    rows = form.get_by_test_id("group-add-row")
    expect(rows).to_have_count(2)
    versions = form.get_by_test_id("group-add-versions")
    expect(versions).to_contain_text("Version 1 of 1")
    rows.nth(0).locator(".draft-name input").fill("The Ice Guild")

    # the prompt, kept and edited in the bar, then Regenerate
    prompt = form.get_by_test_id("group-add-prompt").locator("textarea").first
    expect(prompt).to_have_value("two more guilds")
    prompt.fill("one more guild")
    fixed_group_add(
        {
            "entries": [
                {
                    "name": "The Stair Wardens",
                    "kind": "lore",
                    "tag": "institution",
                    "line": "Keeps the bluff stair.",
                }
            ]
        }
    )
    form.get_by_test_id("group-add-regenerate").click()
    expect(versions).to_contain_text("Version 2 of 2")
    sent = _sent(page, "group_add")[-1]
    assert sent["regenerate"] is True
    assert sent["prompt"] == "one more guild"
    expect(rows).to_have_count(1)
    expect(rows.nth(0).locator(".draft-name input")).to_have_value("The Stair Wardens")

    # version 1 again, the edited name back
    versions.click()
    page.get_by_test_id("group-add-version").filter(has_text="v1").click()
    expect(versions).to_contain_text("Version 1 of 2")
    expect(rows).to_have_count(2)
    expect(rows.nth(0).locator(".draft-name input")).to_have_value("The Ice Guild")

    form.get_by_test_id("group-add-accept").click()
    sent = _wait_sent(page, "accept_group_add")
    assert sent["draft_key"] == f"group:{world.things['Velikoye']}:institution"
    assert [r["name"] for r in sent["rows"]] == ["The Ice Guild", "The Owl Post"]
    expect(_row(_group(thing, "Institutions"), "The Ice Guild")).to_be_visible()
    assert page.console_errors == []


def test_added_facts_bring_new_names(app, page, fixed_facts):
    """Ruling H8: "+ Add facts" shows the names its facts bring as ticked
    New stubs rows (kind, tag); Accept makes stubs of the ticked ones and
    links them, an unticked one staying plain words."""

    world, thing = _open_velikoye(page, app, _world_name("Names"))
    fixed_facts(
        {
            "facts": [
                {"category": "general", "text": "Tsar Ivan III rebuilt its walls."},
                {"category": "general", "text": "Tsar Alexei II first fortified it."},
            ],
            "names": [
                {"name": "Tsar Ivan III", "kind": "character", "tag": "ruler"},
                {"name": "Tsar Alexei II", "kind": "character", "tag": "ruler"},
            ],
        }
    )
    thing.get_by_test_id("add-facts").click()
    thing.get_by_test_id("add-facts-form").get_by_label("What to add").fill("its Tsars")
    thing.get_by_test_id("add-draft").click()
    draft = thing.get_by_test_id("fact-draft")
    rows = draft.get_by_test_id("new-name-row")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("Tsar Ivan III")
    expect(rows.nth(0).get_by_test_id("new-name-tag").locator("input")).to_have_value(
        "ruler"
    )
    # ticked, a name shows as the stub it will be; unticked, plain
    facts = draft.get_by_test_id("fact-draft-row")
    expect(facts.nth(1).get_by_test_id("linked-new")).to_have_text("Tsar Alexei II")
    rows.nth(1).get_by_test_id("new-name-tick").get_by_role("checkbox").uncheck()
    expect(rows.nth(1).get_by_test_id("new-name-plain")).to_be_visible()
    expect(facts.nth(1).get_by_test_id("linked-new")).to_have_count(0)
    expect(facts.nth(0).get_by_test_id("linked-new")).to_have_text("Tsar Ivan III")
    draft.get_by_test_id("fact-draft-accept").click()
    sent = _wait_sent(page, "accept_facts")
    assert [n["ticked"] for n in sent["draft"]["new_names"]] == [True, False]
    _fact(thing, "Tsar Ivan III rebuilt its walls.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(
        _fact(thing, "Tsar Ivan III rebuilt its walls.").get_by_test_id("linked-stub")
    ).to_have_text("Tsar Ivan III")
    expect(
        _fact(thing, "Tsar Alexei II first fortified it.").get_by_test_id("linked-stub")
    ).to_have_count(0)
    assert page.console_errors == []


def test_tags_rename_merge(app, page):
    things = [
        TSARDOM,
        VELIKOYE,
        _entry("lore", "The Academy", "school", [_in("Velikoye")], "Runes taught."),
        _entry("lore", "The Night Court", "institution", [_in("Velikoye")], "Council."),
        _entry("lore", "The Archive", "institution", [_in("Velikoye")], "Old books."),
    ]
    world, thing = _open_velikoye(page, app, _world_name("Tags"), things)
    # the tab asks for the tags when it opens: wait for that reply, so it
    # can't land on a form opened meanwhile
    page.evaluate(RECEIVE_SPY_JS)
    page.get_by_test_id("kind-tags").click()
    page.wait_for_function(
        "() => window.__e2eGot.some((m) => m.includes('\"list_tags\"'))",
        timeout=TIMEOUT_MS,
    )
    tab = page.get_by_test_id("tags-tab")
    rows = tab.get_by_test_id("tag-row")
    expect(rows.filter(has_text="institution")).to_contain_text("2 entries")
    expect(rows.filter(has_text="institution")).to_contain_text("Institutions")
    expect(rows.filter(has_text="school")).to_contain_text("1 entry")

    # renaming onto a tag in use is offered as a merge instead
    rows.filter(has_text="school").get_by_test_id("tag-rename").click()
    field = tab.get_by_test_id("tag-rename-field").locator("input")
    field.fill("Institution")
    expect(tab.get_by_test_id("tag-rename-taken")).to_contain_text("merge into it")
    expect(tab.get_by_role("button", name="Rename", exact=True)).to_be_disabled()

    # rename: every entry carrying it
    field.fill("academy")
    tab.get_by_role("button", name="Rename", exact=True).click()
    sent = _wait_sent(page, "rename_tag")
    assert (sent["old"], sent["new"]) == ("school", "academy")
    expect(rows.filter(has_text="academy")).to_contain_text("1 entry")
    expect(rows.filter(has_text="school")).to_have_count(0)

    # merge into another tag
    rows.filter(has_text="academy").get_by_test_id("tag-merge").click()
    _pick(page, tab.get_by_test_id("tag-merge-into"), "institution")
    tab.get_by_role("button", name="Merge", exact=True).click()
    sent = _wait_sent(page, "merge_tag")
    assert (sent["from"], sent["into"]) == ("academy", "institution")
    expect(rows.filter(has_text="institution")).to_contain_text("3 entries")
    expect(rows).to_have_count(3)

    # the page groups by the new tags
    page.get_by_test_id("thing-card").filter(has_text="Velikoye").click()
    thing = _opened(page, "Velikoye")
    expect(_group(thing, "Institutions").get_by_test_id("group-count")).to_have_text(
        "3"
    )
    assert "Schools" not in _headings(thing)
    assert page.console_errors == []


def test_summary_heads_left_column(app, page):
    """Polish 3: the summary is the first row of the left column, above
    Other names, its buttons inside the column; it edits in place."""

    world, thing = _open_velikoye(page, app, _world_name("Summary"))
    summary = thing.get_by_test_id("entry-summary")
    expect(summary).to_contain_text(SUMMARY)
    box = summary.bounding_box()
    facts = thing.get_by_test_id("facts-heading").bounding_box()
    aka = thing.get_by_test_id("aka-editor").bounding_box()
    # in the left column: the Facts heading's x and right edge
    assert abs(box["x"] - facts["x"]) <= 1
    assert box["x"] + box["width"] <= facts["x"] + facts["width"] + 1
    # first in the column: above Other names
    assert box["y"] < aka["y"]
    edit = summary.get_by_role("button", name="Edit fact")
    ebox = edit.bounding_box()
    assert ebox["x"] + ebox["width"] <= facts["x"] + facts["width"] + 1
    assert summary.locator(".summary-text").count() == 1
    edit.click()
    expect(summary.get_by_test_id("fact-form")).to_be_visible()


def test_connected_in_right_column(app, page):
    """Polish 3: Connected (and Mentioned in, just below it) sit in the
    right column under Appears in; its groups stack inside the column,
    "+ Add" on the heading row."""

    world, thing = _open_velikoye(page, app, _world_name("RightCol"))
    connected = thing.get_by_test_id("entry-connected")
    expect(connected.get_by_test_id("connected-row").first).to_be_visible()
    appears = thing.get_by_text("Appears in", exact=True).bounding_box()
    cbox = connected.bounding_box()
    assert cbox["x"] >= appears["x"] - 1
    assert cbox["y"] > appears["y"]
    right = cbox["x"] + cbox["width"]
    groups = connected.get_by_test_id("connected-group")
    assert groups.count() >= 3
    xs = set()
    for index in range(groups.count()):
        g = groups.nth(index).bounding_box()
        assert g["x"] + g["width"] <= right + 1
        xs.add(round(g["x"]))
    # stacked: one per row
    assert len(xs) == 1
    add = connected.get_by_test_id("connected-add").bounding_box()
    assert add["x"] + add["width"] <= right + 1
    assert abs(add["y"] - cbox["y"]) < 30
    mentioned = thing.get_by_test_id("entry-mentioned").bounding_box()
    assert abs(mentioned["x"] - cbox["x"]) <= 1
    assert mentioned["y"] > cbox["y"]


def test_add_event_by_timeline_filter(app, page):
    """Polish 3: "+ Add event…" follows the Timeline's "Events ▾"."""

    world, thing = _open_velikoye(page, app, _world_name("AddEventBy"))
    timeline = thing.get_by_test_id("entry-timeline")
    filt = timeline.get_by_test_id("timeline-filter").bounding_box()
    add = timeline.get_by_test_id("add-event").bounding_box()
    assert 0 <= add["x"] - (filt["x"] + filt["width"]) <= 24


def test_add_fact_off_while_editing(app, page):
    """Polish 3: "Add fact" waits while a fact's edit form is open (a
    fact's or the summary's), so it never drops an unsaved edit."""

    world, thing = _open_velikoye(page, app, _world_name("AddWaits"))
    add = thing.get_by_test_id("facts-heading").get_by_role(
        "button", name="Add fact", exact=True
    )
    expect(add).to_be_enabled()
    row = thing.get_by_test_id("fact-row").filter(has_text="Walled in stone")
    row.get_by_role("button", name="Edit fact").click()
    expect(add).to_be_disabled()
    expect(add).to_have_attribute("title", "save or cancel the edit first")
    thing.get_by_test_id("fact-form").get_by_role("button", name="Cancel").click()
    expect(add).to_be_enabled()
    thing.get_by_test_id("entry-summary").get_by_role(
        "button", name="Edit fact"
    ).click()
    expect(add).to_be_disabled()


def test_sweep_controls_follow_their_titles(app, page):
    """Polish 3 sweep: on the full-width Stubs and Tags pages and in the
    create box, a control follows what it acts on instead of the far
    edge."""

    world, thing = _open_velikoye(page, app, _world_name("Sweep"))
    # the create box: Create right after its pickers
    page.get_by_test_id("kind-character").click()
    box = page.get_by_test_id("create-box").first
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    picker = box.locator(".picker").last.bounding_box()
    create = box.get_by_role("button", name="Create").bounding_box()
    assert 0 <= create["x"] - (picker["x"] + picker["width"]) <= 24
    # Stubs: "show ignored" right after the title line
    page.get_by_test_id("kind-stubs").click()
    tab = page.get_by_test_id("stubs-tab")
    tab.wait_for(state="visible", timeout=TIMEOUT_MS)
    note = tab.get_by_text("named but not made yet").bounding_box()
    ignored = tab.get_by_label("show ignored").bounding_box()
    assert 0 <= ignored["x"] - (note["x"] + note["width"]) <= 48
    # Tags: rename right after the tag's line
    page.get_by_test_id("kind-tags").click()
    rows = page.get_by_test_id("tags-tab").get_by_test_id("tag-row")
    rows.first.wait_for(state="visible", timeout=TIMEOUT_MS)
    row = rows.first
    caption = row.locator(".text-caption").first.bounding_box()
    rename = row.get_by_test_id("tag-rename").bounding_box()
    assert 0 <= rename["x"] - (caption["x"] + caption["width"]) <= 24


def test_add_fact_back_when_edited_fact_is_removed(app, page):
    """Polish 3 final review: removing the fact whose edit form is open
    (from its ⋯ menu) drops that form too, so "Add fact" comes back
    instead of staying off with no form to cancel."""

    world, thing = _open_velikoye(page, app, _world_name("AddBack"))
    add = thing.get_by_test_id("facts-heading").get_by_role(
        "button", name="Add fact", exact=True
    )
    row = thing.get_by_test_id("fact-row").filter(has_text="Walled in stone")
    row.get_by_role("button", name="Edit fact").click()
    expect(add).to_be_disabled()
    row.get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-remove").click()
    expect(
        thing.get_by_test_id("fact-row").filter(has_text="Walled in stone")
    ).to_have_count(0)
    expect(add).to_be_enabled()
