"""Curation on the world screens: the create preview's sections (its own
facts with held-by tags, "Already in the world", "Belongs on other
entries", the same-thing question, "Move here from where they are now")
and the counts its Accept line gives; the merge dialog; the Timeline every
page has, with where each line is from and disagreeing dates to pick
between; a fact row's "Move to…" and "Held by…"; a being's existence; and
the world's curation settings.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`), the
facts' references written as `[[@Name|shown]]`. No model is asked
anything: previews come from the fixed preview file, read through the real
parsers (held-by names, elsewhere facts, move-in picks); a merge asks no
model. What the page sends is read back from a websocket spy.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_connections_create import _opened, _wait_sent
from e2e.worlds.test_new_scene import SEND_SPY_JS, _sent
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

DOCTRINES = "d0c71e5a"
MILITARY = "a11ed0ff"
KEY_TEXTS = "4e7a1e57"
RUNE_TIMELINE = "71e11e5a"
DIVISIONS = "d1015105"

CHURCH = {
    "kind": "sphere",
    "name": "Church of the Eternal Light",
    "fields": {
        "template": "religion",
        "drawers": [{"id": DOCTRINES, "type": "beliefs", "title": "Doctrines"}],
    },
    "facts": [
        {
            "category": "timeline",
            "text": "The Church was founded by the first Tsar, who declared the"
            " Eternal Light patron of the realm.",
            "since": 412,
        }
    ],
}

TSARDOM = {
    "kind": "sphere",
    "name": "Tsardom of Moscavia",
    "fields": {
        "template": "nation",
        "drawers": [{"id": MILITARY, "type": "structure", "title": "Military"}],
    },
    "facts": [{"category": "about", "text": "A cold realm of the north."}],
}

MOSKOV = {
    "kind": "place",
    "name": "Moskov",
    "facts": [
        {
            "category": "description",
            "text": "Moskov's churches are crowned with gilded onion domes.",
        },
        {
            "category": "description",
            "text": "The Tsar's palace has towering spires visible across the city.",
        },
        {"category": "general", "text": "Moskov holds a winter fair on the river."},
    ],
}

STEWARD = "The Tsar rules as the Light's earthly steward."
ANOINTED = "A new Tsar is anointed with candle-ash at the Synod."
FOUNDED = (
    "The Church was founded by the first Tsar, who declared the Eternal Light"
    " patron of the realm."
)
ON_MOSKOV = "Moskov stands where the Volga meets the Moskva."
ZAKONNIK = "The Zakonnik was revised after 994 for roosting rights."
ARMY = "A standing army is organised into regiments of winged soldiers."
TALON = "The White Talon trains in both aerial combat and ground tactics."


def _create(page, kind: str, prompt: str):
    page.get_by_test_id(f"kind-{kind}").click()
    box = page.get_by_test_id("create-box")
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    box.get_by_label("Describe it").fill(prompt)
    return box


def _preview_of(page, box):
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("create-preview")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    return preview


def _open_exactly(page, name: str):
    """Open the card named `name` exactly (not one whose name holds it)."""

    page.get_by_test_id("thing-card").filter(
        has_text=re.compile(rf"^\s*{re.escape(name)}\s*$")
    ).click()
    return _opened(page, name)


def _pick(page, field, option: str) -> None:
    """Pick `option` in a Vuetify select or autocomplete (`field`)."""

    field.locator(".v-field").click()
    page.get_by_role("option", name=option).first.click()


def test_preview_sections_and_accept_counts(app, page, fixed_preview):
    name = _world_name("Divine")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[CHURCH, TSARDOM, MOSKOV]
    )
    church, tsardom = (
        world.things["Church of the Eternal Light"],
        world.things["Tsardom of Moscavia"],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    box = _create(page, "lore", "The doctrine that the Tsar rules by the Light.")
    fixed_preview(
        {
            "name": "The Divine Right of the Tsar",
            "facts": [
                {
                    "category": "general",
                    "text": STEWARD,
                    "held_by": "Church of the Eternal Light",
                },
                {"category": "general", "text": ANOINTED},
                {
                    "category": "general",
                    "text": FOUNDED,
                    "ticked": False,
                    "repeat_of": {
                        "fact_id": "f0",
                        "owner_id": church,
                        "owner_name": "Church of the Eternal Light",
                        "text": FOUNDED,
                        "score": 1.0,
                    },
                },
            ],
            "prose": {"description": "The doctrine of the Tsar's right."},
            "elsewhere": [
                {"entry": "Moskov", "text": ON_MOSKOV},
                {"entry": "Tsardom of Moscavia", "text": ZAKONNIK},
                {"entry": "Tsardom of Moscavia", "text": ARMY},
                {"entry": "White Talon", "text": TALON},
            ],
        }
    )
    preview = _preview_of(page, box)

    # its facts, the held one tagged
    own = preview.get_by_test_id("preview-fact")
    expect(own).to_have_count(2)
    steward = own.filter(has_text=STEWARD)
    assert "held by Church of the Eternal Light" in steward.inner_text()
    assert steward.get_by_role("checkbox").is_checked()

    # already in the world: unticked, so collapsed, saying where it is
    repeats = preview.get_by_test_id("preview-repeats")
    assert "Already in the world" in repeats.text_content()
    expect(repeats.get_by_test_id("repeat-row")).to_have_count(0)
    repeats.get_by_role("button", name="Already in the world").click()
    founded = repeats.get_by_test_id("repeat-row").filter(has_text="founded")
    founded.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "≈ on Church of the Eternal Light" in founded.inner_text()
    assert not founded.get_by_role("checkbox").is_checked()

    # belongs on other entries, grouped, each ticked; the new stub says so
    elsewhere = preview.get_by_test_id("preview-elsewhere")
    groups = elsewhere.get_by_test_id("elsewhere-group")
    expect(groups).to_have_count(3)
    tsardom_group = groups.filter(has_text="Tsardom of Moscavia")
    expect(tsardom_group.get_by_test_id("elsewhere-row")).to_have_count(2)
    talon = groups.filter(has_text="White Talon")
    assert "new stub" in talon.inner_text()
    for row in elsewhere.get_by_test_id("elsewhere-row").all():
        assert row.get_by_role("checkbox").is_checked()

    counts = preview.get_by_test_id("accept-counts")
    expect(counts).to_have_text("writes 2 facts here, 4 elsewhere, 1 new stub")

    # a row's category can be changed, from its entry's kind's
    moskov_row = groups.filter(has_text="Moskov").get_by_test_id("elsewhere-row")
    _pick(page, moskov_row.get_by_test_id("elsewhere-category"), "description")

    # untick a group at once, and tick the repeat back in
    groups.filter(has_text="Moskov").get_by_role("button", name="Untick all").click()
    founded.get_by_role("checkbox").check()
    expect(counts).to_have_text("writes 3 facts here, 3 elsewhere, 1 new stub")

    # the inner part gets a body around it, named for it to start with
    talon.get_by_role("button", name="Part of a body not yet made…").click()
    outer = preview.get_by_test_id("outer-body-form")
    expect(outer.get_by_label("Name of the body")).to_have_value("White Talon's parent")
    outer.get_by_label("Name of the body").fill("The Tsar's Army")
    _pick(page, outer.get_by_test_id("outer-template"), "Order")
    _pick(page, outer.get_by_test_id("outer-sphere"), "Tsardom of Moscavia")
    outer.get_by_role("button", name="Add the body").click()
    sent = _wait_sent(page, "add_outer_body")
    assert (sent["preview_type"], sent["row_name"]) == ("create", "White Talon")
    assert sent["outer"]["name"] == "The Tsar's Army"
    assert sent["outer"]["template"] == "order"
    assert sent["outer"]["part_of"]["sphere"] == tsardom
    stubs = preview.get_by_test_id("preview-stubs")
    stubs.filter(has_text="The Tsar's Army").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(counts).to_have_text("writes 3 facts here, 3 elsewhere, 2 new stubs")

    preview.get_by_role("button", name="Accept").click()
    _opened(page, "The Divine Right of the Tsar")
    accepted = _sent(page, "accept_preview")[-1]["preview"]
    assert [f["ticked"] for f in accepted["facts"]] == [True, True, True]
    assert [(e["target_name"], e["ticked"]) for e in accepted["elsewhere"]] == [
        ("Moskov", False),
        ("Tsardom of Moscavia", True),
        ("Tsardom of Moscavia", True),
        ("White Talon", True),
    ]
    assert accepted["elsewhere"][0]["category"] == "description"
    assert accepted["elsewhere"][0]["target_id"] == world.things["Moskov"]

    # written onto the Tsardom, and not onto Moskov
    page.get_by_test_id("kind-sphere").click()
    tsardom_page = _open_thing(page, "Tsardom of Moscavia")
    tsardom_page.get_by_text(ZAKONNIK).first.wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    page.get_by_test_id("kind-place").click()
    moskov = _open_thing(page, "Moskov")
    expect(moskov.get_by_text(ON_MOSKOV)).to_have_count(0)
    assert page.console_errors == []


ASHENMERE = {
    "kind": "place",
    "name": "Ashenmere",
    "facts": [
        {"category": "description", "text": "A lake of grey water in the hills."}
    ],
}

CONCLAVE = {
    "kind": "lore",
    "name": "Runeweavers' Conclave",
    "facts": [{"category": "general", "text": "Keepers of the runic arts."}],
}


def test_same_thing_fill_existing(app, page, fixed_preview):
    name = _world_name("Ashen")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[ASHENMERE, CONCLAVE]
    )
    ashenmere = world.things["Ashenmere"]
    conclave = world.things["Runeweavers' Conclave"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    box = _create(page, "place", "Caves under a grey lake, full of old runes.")
    fixed_preview(
        {
            "name": "The Ashenmere Caves",
            "facts": [
                {"category": "description", "text": "Caves run under the lake."},
                {"category": "history", "text": "Runes cover the walls."},
            ],
            "prose": {"description": "Caves under the lake."},
            "elsewhere": [
                {"entry": "The Conclave", "text": "The Conclave guards the caves."}
            ],
            "verdict": {"verdict": "same", "why": "Both are the lake's caves."},
        }
    )
    preview = _preview_of(page, box)

    # one question at the top: the candidate's kind and summary, the AI's
    # verdict only as a hint, and nothing picked for the owner
    same = preview.get_by_test_id("same-thing")
    same.wait_for(state="visible", timeout=TIMEOUT_MS)
    candidate = same.get_by_test_id("same-candidate").filter(has_text="Ashenmere")
    assert "place" in candidate.inner_text()
    assert "A lake of grey water" in candidate.inner_text()
    hint = candidate.get_by_test_id("same-hint")
    assert "same" in hint.inner_text() and "lake's caves" in hint.inner_text()
    counts = preview.get_by_test_id("accept-counts")
    expect(counts).to_contain_text("writes 2 facts here")

    # a stub row asks too, defaulting to new
    stub_same = (
        preview.get_by_test_id("elsewhere-group")
        .filter(has_text="The Conclave")
        .get_by_test_id("stub-same")
    )
    assert "new" in stub_same.inner_text()
    # each choice shows the entry's summary, to tell two of a name apart
    stub_same.locator(".v-field").click()
    option = page.get_by_test_id("stub-same-option").filter(
        has_text="Runeweavers' Conclave"
    )
    expect(option).to_contain_text("Keepers of the runic arts.")
    option.click()
    expect(counts).to_contain_text("1 elsewhere")
    expect(counts).not_to_contain_text("new stub")

    # yes: the material goes onto Ashenmere, nothing new is made
    candidate.get_by_role("button", name="Yes, fill it").click()
    expect(counts).to_contain_text("writes 2 facts onto Ashenmere")
    preview.get_by_role("button", name="Accept").click()
    thing = _opened(page, "Ashenmere")
    sent = _sent(page, "accept_preview")[-1]
    assert sent["same_target_id"] == ashenmere
    assert sent["preview"]["elsewhere"][0]["new"]["same_target_id"] == conclave
    _fact(thing, "Caves run under the lake.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(thing.get_by_test_id("aka-editor")).to_contain_text("The Ashenmere Caves")
    assert page.console_errors == []


def test_move_in_on_part_of_entry(app, page, fixed_preview):
    name = _world_name("Domes")
    world = seed_fm_world(app.root, name, present_year=1026, things=[MOSKOV])
    moskov = world.things["Moskov"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    box = _create(page, "place", "The domes and spires of Moskov.")
    _pick(page, box.get_by_test_id("place-parent"), "Moskov")
    fixed_preview(
        {
            "name": "The Architecture of Moskov",
            "facts": [
                {
                    "category": "description",
                    "text": "Builders widen every doorway for roosting.",
                }
            ],
            "prose": {"description": "How Moskov is built."},
            "move_in": ["M1", "M2"],
        }
    )
    preview = _preview_of(page, box)

    # the broader entry's facts, all unticked (ruling C24), its picks first
    # and marked suggested, moved not copied
    move_in = preview.get_by_test_id("move-in")
    move_in.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "from Moskov" in move_in.inner_text()
    assert "Moved, not copied" in move_in.inner_text()
    rows = move_in.get_by_test_id("move-in-row")
    expect(rows).to_have_count(3)
    assert [row.get_by_role("checkbox").is_checked() for row in rows.all()] == [
        False,
        False,
        False,
    ]
    assert [row.get_by_test_id("move-in-suggested").count() for row in rows.all()] == [
        1,
        1,
        0,
    ]
    assert "winter fair" in rows.nth(2).inner_text()
    counts = preview.get_by_test_id("accept-counts")
    expect(counts).to_have_text("writes 1 fact here")

    # the owner moves the domes in and keeps the spires where they are
    rows.filter(has_text="onion domes").get_by_role("checkbox").check()
    expect(counts).to_have_text("writes 1 fact here, moves 1 in")
    preview.get_by_role("button", name="Accept").click()
    thing = _opened(page, "The Architecture of Moskov")
    sent = _sent(page, "accept_preview")[-1]["preview"]["move_in"]
    assert [(row["from_id"], row["ticked"]) for row in sent] == [
        (moskov, True),
        (moskov, False),
        (moskov, False),
    ]
    _fact(thing, "onion domes").wait_for(state="visible", timeout=TIMEOUT_MS)

    # gone from Moskov, the spires kept
    page.get_by_test_id("kind-place").click()
    moskov_page = _open_exactly(page, "Moskov")
    _fact(moskov_page, "spires").wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(_fact(moskov_page, "onion domes")).to_have_count(0)
    assert page.console_errors == []


CAVES = {
    "kind": "place",
    "name": "The Ashenmere Caves",
    "facts": [
        {
            "category": "description",
            "text": "Access is controlled by the Conclave, which keeps a garrison"
            " at the main entrance.",
        },
        {
            "category": "history",
            "text": "The earliest runic inscriptions were carved into its walls.",
        },
        {
            "category": "history",
            "text": "A Conclave party rediscovered the Ashenmere dialect.",
            "since": 950,
        },
    ],
}

ASHENMERE_FULL = {
    "kind": "place",
    "name": "Ashenmere",
    "facts": [
        {
            "category": "description",
            "text": "Access is open to licensed weavers since 947.",
        },
        {
            "category": "history",
            "text": "The earliest runic inscriptions were carved into its walls.",
        },
        {
            "category": "history",
            "text": "A Conclave party rediscovered the Ashenmere dialect.",
            "since": 947,
        },
    ],
}


def test_merge_dialog_names_pairs(app, page):
    name = _world_name("Merge")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[ASHENMERE_FULL, CAVES]
    )
    ashenmere, caves = world.things["Ashenmere"], world.things["The Ashenmere Caves"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    thing = _open_thing(page, "The Ashenmere Caves")

    thing.get_by_role("button", name="Merge into…").click()
    dialog = page.get_by_test_id("merge-dialog")
    dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
    _pick(page, dialog.get_by_test_id("merge-target"), "Ashenmere")
    sent = _wait_sent(page, "preview_merge")
    assert (sent["from_id"], sent["into_id"]) == (caves, ashenmere)

    # the name: the other one becomes an "also known as"
    names = dialog.get_by_test_id("merge-name")
    names.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert names.get_by_role("radio", name="Ashenmere", exact=True).is_checked()
    assert "also known as" in dialog.inner_text()

    # the facts, the repeat unticked and saying where it is already
    facts = dialog.get_by_test_id("merge-fact")
    expect(facts).to_have_count(3)
    repeat = facts.filter(has_text="earliest runic")
    assert not repeat.get_by_role("checkbox").is_checked()
    assert "already on Ashenmere" in repeat.inner_text()
    assert facts.filter(has_text="garrison").get_by_role("checkbox").is_checked()

    # the pair that disagrees: pick one, or keep both
    pair = dialog.get_by_test_id("merge-pair")
    expect(pair).to_have_count(1)
    assert "950" in pair.inner_text() and "947" in pair.inner_text()
    assert pair.get_by_role("radio", name="Keep both").is_checked()
    pair.get_by_role("radio", name="Ashenmere: A Conclave party").check()
    dialog.get_by_role("radio", name="End it").check()
    assert "facts" in dialog.get_by_test_id("merge-moves").inner_text()

    names.get_by_role("radio", name="The Ashenmere Caves").check()
    dialog.get_by_role("button", name="Merge", exact=True).click()
    merged = _opened(page, "The Ashenmere Caves")
    sent = _sent(page, "accept_merge")[-1]
    assert sent["main_name"] == "The Ashenmere Caves"
    assert list(sent["keep"].values()) == ["b"]
    assert sent["lose"] == "end"
    expect(merged.get_by_test_id("aka-editor")).to_contain_text("Ashenmere")
    _fact(merged, "garrison").wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(page.get_by_test_id("merge-dialog")).to_have_count(0)
    assert page.console_errors == []


RUNEWEAVING = {
    "kind": "sphere",
    "name": "Runeweaving",
    "fields": {
        "template": "field",
        "drawers": [
            {"id": KEY_TEXTS, "type": "knowledge", "title": "Key Texts"},
            {"id": RUNE_TIMELINE, "type": "events", "title": "Timeline"},
        ],
    },
    "facts": [
        {
            "category": "timeline",
            "text": "The First Codex of Aelberth is compiled.",
            "since": 217,
        },
        {
            "category": "statement",
            "text": "The Conclave keeps the oldest runes.",
            "since": 642,
            "origin": {"drawer": KEY_TEXTS},
        },
    ],
}

CODEX = {
    "kind": "lore",
    "name": "First Codex of Aelberth",
    "part_of": {"sphere": "Runeweaving", "drawer": KEY_TEXTS},
    "facts": [
        {
            "category": "general",
            "text": "The First Codex of Aelberth is compiled in Stonehold.",
            "since": 312,
        }
    ],
}


def test_timeline_gathers_and_flags(app, page):
    name = _world_name("Runes")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[RUNEWEAVING, CODEX]
    )
    rune = world.things["Runeweaving"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-sphere").click()
    thing = _open_thing(page, "Runeweaving")

    # gathered from its part, in date order, each saying where it's from
    timeline = thing.get_by_test_id("entry-timeline")
    lines = timeline.get_by_test_id("timeline-row")
    expect(lines).to_have_count(3)
    text = timeline.inner_text()
    assert text.index("217") < text.index("312") < text.index("642")
    codex_line = lines.filter(has_text="Stonehold")
    assert "from First Codex of Aelberth" in codex_line.inner_text()
    assert "here" in lines.filter(has_text="is compiled.").inner_text()

    # a statement filed in a drawer is edited there: read only here,
    # pointing at the drawer (ruling C21)
    statement = lines.filter(has_text="oldest runes")
    assert "in Key Texts" in statement.inner_text()
    expect(statement.get_by_test_id("sphere-fact-edit")).to_have_count(0)
    expect(
        lines.filter(has_text="is compiled.").get_by_test_id("sphere-fact-edit")
    ).to_have_count(1)

    # the two years for the Codex are flagged; the owner keeps 217
    flag = codex_line.get_by_test_id("line-disagrees")
    assert "disagrees with 217" in flag.text_content()
    flag.click()
    page.get_by_test_id("pick-option").filter(has_text="Keep 217, end this one").click()
    sent = _wait_sent(page, "pick_date")
    assert sent["mode"] == "end"
    assert sent["thing_id"] == rune
    expect(timeline.get_by_test_id("line-disagrees")).to_have_count(0)
    # ended: its span shows
    expect(lines.filter(has_text="Stonehold")).to_contain_text("312–1026")

    # every page has a Timeline: the Codex's own, its line ended
    codex_line.get_by_test_id("linked-ref").filter(
        has_text="First Codex of Aelberth"
    ).click()
    codex = _opened(page, "First Codex of Aelberth")
    own = codex.get_by_test_id("entry-timeline")
    expect(own.get_by_test_id("timeline-row")).to_contain_text(["312–1026"])
    assert page.console_errors == []


DIVINE = {
    "kind": "lore",
    "name": "The Divine Right of the Tsar",
    "facts": [
        {"category": "general", "text": ON_MOSKOV},
        {"category": "general", "text": STEWARD},
    ],
}


def test_move_fact_and_held_by(app, page):
    name = _world_name("Steward")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[CHURCH, MOSKOV, DIVINE]
    )
    church, moskov = world.things["Church of the Eternal Light"], world.things["Moskov"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-lore").click()
    thing = _open_thing(page, "The Divine Right of the Tsar")

    # Esc closes an inline editor
    thing.get_by_role("button", name="Add fact").click()
    thing.get_by_test_id("fact-form").get_by_label("Fact", exact=True).click()
    page.keyboard.press("Escape")
    expect(thing.get_by_test_id("fact-form")).to_have_count(0)

    # held by the Church: tagged on the row
    steward = _fact(thing, STEWARD)
    steward.get_by_test_id("fact-held-by").click()
    menu = page.get_by_test_id("fact-held-menu")
    _pick(page, menu.get_by_test_id("held-by-picker"), "Church of the Eternal Light")
    menu.get_by_role("button", name="Save").click()
    sent = _wait_sent(page, "set_held_by")
    assert sent["holder_id"] == church
    tag = _fact(thing, STEWARD).get_by_test_id("held-by-tag")
    expect(tag).to_have_text("held by Church of the Eternal Light")

    # and cleared again: world truth
    _fact(thing, STEWARD).get_by_test_id("fact-held-by").click()
    menu = page.get_by_test_id("fact-held-menu")
    menu.get_by_role("button", name="Clear").click()
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'set_held_by').length === 2"
    )
    assert _sent(page, "set_held_by")[-1]["holder_id"] is None
    expect(_fact(thing, STEWARD).get_by_test_id("held-by-tag")).to_have_count(0)

    # an off-topic fact moves to the entry it's about
    _fact(thing, ON_MOSKOV).get_by_test_id("fact-move").click()
    menu = page.get_by_test_id("fact-move-menu")
    _pick(page, menu.get_by_test_id("move-target"), "Moskov")
    menu.get_by_role("button", name="Move").click()
    sent = _wait_sent(page, "move_fact")
    assert sent["target_id"] == moskov
    expect(_fact(thing, ON_MOSKOV)).to_have_count(0)
    page.get_by_test_id("kind-place").click()
    moskov_page = _open_thing(page, "Moskov")
    _fact(moskov_page, ON_MOSKOV).wait_for(state="visible", timeout=TIMEOUT_MS)
    assert page.console_errors == []


ARMY_SPHERE = {
    "kind": "sphere",
    "name": "The Tsar's Army",
    "fields": {
        "template": "order",
        "drawers": [{"id": DIVISIONS, "type": "structure", "title": "Divisions"}],
    },
}

WHITE_TALON = {
    "kind": "lore",
    "name": "The White Talon",
    "part_of": {"sphere": "The Tsar's Army", "drawer": DIVISIONS},
    "facts": [{"category": "general", "text": "Trains in aerial combat."}],
}

LIGHT = {
    "kind": "being",
    "name": "The Eternal Light",
    "facts": [{"category": "nature", "text": "A light that never dims."}],
}

MAREN = {"kind": "character", "name": "Maren", "born": 1000}

DAWN_ORDER = {
    "kind": "sphere",
    "name": "Order of the Dawn",
    "fields": {
        "template": "order",
        "drawers": [{"id": "9e0b1e5a", "type": "people", "title": "Members"}],
    },
}


def _player_field(dialog):
    return dialog.locator(".v-select").filter(has_text="You play").locator(".v-field")


def test_being_existence(app, page):
    name = _world_name("Light")
    world = seed_fm_world(
        app.root,
        name,
        present_year=1026,
        things=[ARMY_SPHERE, WHITE_TALON, LIGHT, MAREN, DAWN_ORDER],
    )
    talon = world.things["The White Talon"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)

    # undecided: not offered as a player
    page.get_by_role("button", name="New scene").click()
    dialog = page.get_by_test_id("new-scene-dialog")
    _player_field(dialog).click()
    page.get_by_role("option", name="Maren").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(page.get_by_role("option", name="The Eternal Light")).to_have_count(0)
    page.keyboard.press("Escape")
    dialog.get_by_role("button", name="Close").click()

    _world_tab(page)
    page.get_by_test_id("kind-being").click()
    thing = _open_thing(page, "The Eternal Light")
    existence = thing.get_by_test_id("being-existence")
    assert "v-btn--active" in existence.get_by_role(
        "button", name="undecided"
    ).get_attribute("class")
    expect(thing.get_by_test_id("ties-section")).to_have_count(0)

    # made real: it can hold ties, within a part of the sphere
    existence.get_by_role("button", name="real").click()
    sent = _wait_sent(page, "set_field")
    assert (sent["field"], sent["value"]) == ("existence", "real")
    ties = thing.get_by_test_id("ties-section")
    ties.wait_for(state="visible", timeout=TIMEOUT_MS)
    ties.get_by_role("button", name="Add tie").click()
    form = ties.get_by_test_id("tie-form")
    _pick(page, form.get_by_test_id("tie-sphere"), "The Tsar's Army")
    form.get_by_label("Role").fill("patron")
    _pick(page, form.get_by_test_id("tie-within"), "The White Talon")
    form.get_by_role("button", name="Save").click()
    tie = ties.get_by_test_id("tie").filter(has_text="The Tsar's Army")
    tie.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(tie).to_contain_text("within The White Talon")
    saved = _sent(page, "set_ties")[-1]["ties"]
    assert saved[0]["within"] == talon

    # a sphere's People "+ Add" offers it now, as a character
    page.get_by_test_id("kind-sphere").click()
    order = _open_thing(page, "Order of the Dawn")
    order.get_by_test_id("drawer-add").click()
    _pick(
        page,
        order.get_by_test_id("drawer-add-form").locator(".v-autocomplete"),
        "The Eternal Light",
    )

    # real: now a player can be it
    page.get_by_role("tab", name="Worlds", exact=True).click()
    page.get_by_role("button", name="New scene").click()
    dialog = page.get_by_test_id("new-scene-dialog")
    _player_field(dialog).click()
    page.get_by_role("option", name="The Eternal Light").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert page.console_errors == []


def test_curation_settings(app, page):
    name = _world_name("Knobs")
    seed_fm_world(app.root, name, present_year=1026, things=[MAREN])
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-settings").click()
    settings = page.get_by_test_id("curation-settings")
    reach = settings.get_by_label("How far out (steps)")
    expect(reach).to_have_value("1", timeout=TIMEOUT_MS)
    reach.fill("2")
    settings.get_by_label("Repeat threshold").fill("0.5")
    settings.get_by_role("button", name="Save").click()
    sent = _wait_sent(page, "set_curation")
    assert sent["settings"] == {"reach": 2, "repeat_threshold": 0.5}
    expect(settings.get_by_test_id("curation-saved")).to_be_visible()
    assert page.console_errors == []
