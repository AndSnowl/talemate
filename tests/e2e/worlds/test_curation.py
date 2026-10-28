"""Curation on the world screens: the draft page's sections (its own facts
with held-by tags and a repeat's match, "For other pages", the same-thing
question) and the counts its Accept line gives; the merge dialog; the
Timeline every page has, with where each line is from and disagreeing
dates to pick between; a fact menu's "Move to…" and "Held by…"; a being's
existence; and the world's curation settings.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`), the
facts' references written as `[[@Name|shown]]`. No model is asked
anything: drafts come from the fixed preview file, read through the real
parsers (held-by names, elsewhere facts); a merge asks no model. What the
page sends is read back from a websocket spy.
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

CHURCH = {
    "kind": "lore",
    "name": "Church of the Eternal Light",
    "fields": {"hint": "religion"},
    "facts": [
        {
            "category": "general",
            "text": "The Church was founded by the first Tsar, who declared the"
            " Eternal Light patron of the realm.",
            "since": 412,
        }
    ],
}

TSARDOM = {
    "kind": "place",
    "name": "Tsardom of Moscavia",
    "fields": {"hint": "nation"},
    "facts": [{"category": "description", "text": "A cold realm of the north."}],
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
    preview = page.get_by_test_id("draft-page")
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
    church = world.things["Church of the Eternal Light"]
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
    own = preview.get_by_test_id("draft-fact")
    expect(own).to_have_count(3)
    steward = own.filter(has_text=STEWARD)
    assert "held by Church of the Eternal Light" in steward.inner_text()
    assert steward.get_by_role("checkbox").is_checked()

    # already in the world: unticked, saying where it is (shown among the
    # facts with its match, no longer in a collapsed section of its own)
    founded = own.filter(has_text="founded")
    match = founded.get_by_test_id("fact-match")
    assert "≈ already on Church of the Eternal Light" in match.inner_text()
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

    # untick a group at once, and keep the repeat after all
    groups.filter(has_text="Moskov").get_by_role("button", name="Untick all").click()
    founded.get_by_role("button", name="Keep both").click()
    expect(counts).to_have_text("writes 3 facts here, 3 elsewhere, 1 new stub")

    preview.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
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
    page.get_by_test_id("kind-place").click()
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

    # one question, a search left empty for new: the candidate's kind and
    # summary under it, the AI's verdict only as a hint, nothing picked
    same = preview.get_by_test_id("same-thing")
    same.wait_for(state="visible", timeout=TIMEOUT_MS)
    candidate = same.get_by_test_id("same-candidate").filter(has_text="Ashenmere")
    assert "place" in candidate.inner_text()
    assert "A lake of grey water" in candidate.inner_text()
    hint = candidate.get_by_test_id("same-hint")
    assert "same" in hint.inner_text() and "lake's caves" in hint.inner_text()
    expect(same.get_by_test_id("same-search").locator("input")).to_have_value("")
    assert "Leave it empty if it's new" in same.inner_text()
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
    candidate.get_by_role("button", name="Same as this").click()
    expect(counts).to_contain_text("writes 2 facts onto Ashenmere")
    preview.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
    thing = _opened(page, "Ashenmere")
    sent = _sent(page, "accept_preview")[-1]
    assert sent["same_target_id"] == ashenmere
    assert sent["preview"]["elsewhere"][0]["new"]["same_target_id"] == conclave
    _fact(thing, "Caves run under the lake.").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(thing.get_by_test_id("aka-editor")).to_contain_text("The Ashenmere Caves")
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
    "kind": "lore",
    "name": "Runeweaving",
    "fields": {"hint": "field"},
    "facts": [
        {
            "category": "general",
            "text": "The First Codex of Aelberth is compiled.",
            "since": 217,
        },
    ],
}

CODEX = {
    "kind": "lore",
    "name": "First Codex of Aelberth",
    "filings": [{"target": "Runeweaving"}],
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
    page.get_by_test_id("kind-lore").click()
    thing = _open_thing(page, "Runeweaving")

    # gathered from its part, in date order, each saying where it's from
    timeline = thing.get_by_test_id("entry-timeline")
    lines = timeline.get_by_test_id("timeline-row")
    expect(lines).to_have_count(2)
    text = timeline.inner_text()
    assert text.index("217") < text.index("312")
    codex_line = lines.filter(has_text="Stonehold")
    assert "from First Codex of Aelberth" in codex_line.inner_text()
    assert "here" in lines.filter(has_text="is compiled.").inner_text()

    # the two years for the Codex are flagged; the owner keeps 217
    flag = codex_line.get_by_test_id("line-disagrees")
    assert "Disagrees with 217" in flag.get_attribute("aria-label")
    # polish 3: a warning sign right before the row's date and text; the
    # years and the texts each line up in their own column, and the sign
    # sits on the year's line
    year_box = codex_line.locator(".year").bounding_box()
    assert flag.bounding_box()["x"] < year_box["x"]
    years = [lines.nth(i).locator(".year").bounding_box() for i in range(2)]
    texts = [lines.nth(i).locator(".line-text").bounding_box() for i in range(2)]
    assert abs(years[0]["x"] - years[1]["x"]) <= 1
    assert abs(texts[0]["x"] - texts[1]["x"]) <= 1
    assert texts[0]["x"] >= years[0]["x"] + years[0]["width"]
    # the sign's icon centred on the year's line, not riding high
    ibox = flag.locator(".v-icon").bounding_box()
    centre = ibox["y"] + ibox["height"] / 2
    assert abs(centre - (year_box["y"] + year_box["height"] / 2)) <= 2
    flag.click()
    # the menu shows the line it disagrees with in full, then the picks
    menu = page.get_by_test_id("pick-date")
    expect(menu.get_by_test_id("disagrees-with")).to_contain_text("217")
    expect(menu.get_by_test_id("disagrees-with")).to_contain_text("is compiled.")
    # the year and the text apart, not "217The…" (measured once the menu
    # has finished opening: it grows in, so wait until its size settles)
    year = menu.get_by_test_id("disagrees-with").locator(".year")
    other_year = year.bounding_box()
    for _ in range(30):
        page.wait_for_timeout(100)
        now = year.bounding_box()
        if now == other_year and now["width"] > 4:
            break
        other_year = now
    other_text = (
        menu.get_by_test_id("disagrees-with")
        .get_by_text("The First Codex")
        .bounding_box()
    )
    assert other_text["x"] - (other_year["x"] + other_year["width"]) >= 4
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
    thing.get_by_role("button", name="Add fact", exact=True).click()
    thing.get_by_test_id("fact-form").get_by_label("Fact", exact=True).click()
    page.keyboard.press("Escape")
    expect(thing.get_by_test_id("fact-form")).to_have_count(0)

    # held by the Church (the fact menu's "Held by…"): tagged on the row
    steward = _fact(thing, STEWARD)
    steward.get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-held-by").click()
    menu = page.get_by_test_id("fact-held-menu")
    _pick(page, menu.get_by_test_id("held-by-picker"), "Church of the Eternal Light")
    menu.get_by_role("button", name="Save").click()
    sent = _wait_sent(page, "set_held_by")
    assert sent["holder_id"] == church
    tag = _fact(thing, STEWARD).get_by_test_id("held-by-tag")
    expect(tag).to_have_text("held by Church of the Eternal Light")

    # and cleared again: world truth
    _fact(thing, STEWARD).get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-held-by").click()
    menu = page.get_by_test_id("fact-held-menu")
    menu.get_by_role("button", name="Clear").click()
    page.wait_for_function(
        "() => window.__e2eSent.filter((m) => JSON.parse(m).action === 'set_held_by').length === 2"
    )
    assert _sent(page, "set_held_by")[-1]["holder_id"] is None
    expect(_fact(thing, STEWARD).get_by_test_id("held-by-tag")).to_have_count(0)

    # an off-topic fact moves to the entry it's about
    _fact(thing, ON_MOSKOV).get_by_test_id("fact-menu-button").click()
    page.get_by_test_id("fact-menu").get_by_test_id("fact-move").click()
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


LIGHT = {
    "kind": "being",
    "name": "The Eternal Light",
    "facts": [{"category": "nature", "text": "A light that never dims."}],
}

MAREN = {"kind": "character", "name": "Maren", "born": 1000}


def _player_field(dialog):
    return dialog.locator(".v-select").filter(has_text="You play").locator(".v-field")


def test_being_existence(app, page):
    name = _world_name("Light")
    seed_fm_world(app.root, name, present_year=1026, things=[LIGHT, MAREN])
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

    # made real
    existence.get_by_role("button", name="real").click()
    sent = _wait_sent(page, "set_field")
    assert (sent["field"], sent["value"]) == ("existence", "real")

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
    date = settings.get_by_label("Date disagreement at")
    expect(date).to_have_value("0.5")
    date.fill("0.6")
    settings.get_by_role("button", name="Save").click()
    sent = _wait_sent(page, "set_curation")
    assert sent["settings"] == {
        "reach": 2,
        "repeat_threshold": 0.5,
        "date_threshold": 0.6,
    }
    expect(settings.get_by_test_id("curation-saved")).to_be_visible()
    assert page.console_errors == []
