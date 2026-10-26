"""Connections while writing: the highlighted create prompt (re-picking a
name teaches its thing that other name), expanding a stub (its suggested
prompt and the context the AI gets), "fill the stub instead", the
right-click Add reference menu, editing a linked fact, and re-pointing a
link.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`), the
facts' references written as `[[@Name|shown]]`. No model is asked
anything: previews come from the fixed preview file. What the page sends
is read back from a websocket spy.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_new_scene import SEND_SPY_JS, _sent
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

MOSCAVIA = {"kind": "place", "name": "Tsardom of Moscavia", "stub": "live"}
KALMARA = {"kind": "place", "name": "Kalmara", "stub": "live"}

ORIGIN = "became owl-folk one day in 994"
NESTING = "nest along the Moscavia border"

OWL_FOLK = {
    "kind": "species",
    "name": "Owl-folk",
    "facts": [
        {
            "category": "origin",
            "text": "Everyone in the [[@Tsardom of Moscavia|Tsardom of Moscavia]]"
            " became owl-folk one day in 994.",
        },
        {
            "category": "general",
            "text": "Most nest along the [[@Tsardom of Moscavia|Moscavia]] border,"
            " near Iron Gate.",
        },
    ],
}

PLACE_PROSE = {"description": "A place by the river."}


def _preview(name: str, fact: str) -> dict:
    return {
        "name": name,
        "facts": [{"category": "description", "text": fact}],
        "prose": PLACE_PROSE,
    }


def _place_box(page):
    page.get_by_test_id("kind-place").click()
    box = page.get_by_test_id("create-box")
    box.wait_for(state="visible", timeout=TIMEOUT_MS)
    return box


def _create_and_wait(page, box):
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("draft-page")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    return preview


def _opened(page, name: str):
    thing = page.get_by_test_id("thing-page")
    thing.get_by_test_id("thing-name").filter(has_text=name).wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    return thing


def _wait_sent(page, action: str) -> dict:
    """The last `action` the page sent, once it has sent one."""
    page.wait_for_function(
        "(action) => window.__e2eSent.some((m) => JSON.parse(m).action === action)",
        arg=action,
        timeout=TIMEOUT_MS,
    )
    return _sent(page, action)[-1]


def _search_and_pick(page, query: str, name: str):
    search = page.get_by_test_id("reference-search")
    search.wait_for(state="visible", timeout=TIMEOUT_MS)
    search.get_by_role("textbox").fill(query)
    result = page.get_by_test_id("reference-result").filter(has_text=name)
    result.wait_for(state="visible", timeout=TIMEOUT_MS)
    text = result.inner_text()
    result.click()
    return text


MODE_IDS = {"link": "mode-link-only", "name": "mode-add-name"}


def _choose_mode(
    page,
    mode: str | None = None,
    *,
    rename_to: str | None = None,
    default: str | None = None,
):
    """The mode chooser after a link's target is picked (P4, ruling H2):
    `default` ("link" or "name") is the one marked; then "Rename to…"
    `rename_to`, else `mode`, else the marked one is chosen."""

    chooser = page.get_by_test_id("name-mode")
    chooser.wait_for(state="visible", timeout=TIMEOUT_MS)
    if default is not None:
        expect(chooser.get_by_test_id(MODE_IDS[default])).to_have_class(
            re.compile(r"v-list-item--active")
        )
    if rename_to is not None:
        chooser.get_by_test_id("mode-rename-option").filter(
            has_text=re.compile(f"^{re.escape(rename_to)}$")
        ).click()
    elif mode is not None:
        chooser.get_by_test_id(MODE_IDS[mode]).click()
    else:
        chooser.locator(".v-list-item--active").click()
    chooser.wait_for(state="hidden", timeout=TIMEOUT_MS)


def test_expand_stub_prefills_and_fills_it(app, page, fixed_preview):
    name = _world_name("Moscavia")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[MOSCAVIA, OWL_FOLK]
    )
    tsardom = world.things["Tsardom of Moscavia"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")

    # clicking the stub opens the place create box from it, its prompt
    # suggested from what mentions it
    _fact(owl, ORIGIN).get_by_test_id("linked-stub").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").filter(has_text="Tsardom of Moscavia").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    # (both of Owl-folk's mentions, in no set order)
    prompt = box.get_by_label("Describe it")
    expect(prompt).to_have_value(
        re.compile(r"^Tsardom of Moscavia: .*became owl-folk one day in 994"),
        timeout=TIMEOUT_MS,
    )
    assert "Most nest along the Moscavia border" in prompt.input_value()

    # the context the AI gets: collapsed, and opened shows the mention
    context = box.get_by_test_id("ai-context")
    context.get_by_text("Context the AI gets").click()
    group = context.get_by_test_id("context-group").filter(has_text="Owl-folk")
    group.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert ORIGIN in group.inner_text()

    # the preview expands the stub, and so does accepting it
    fixed_preview(_preview("Tsardom of Moscavia", "A cold realm of the north."))
    preview = _create_and_wait(page, box)
    assert _sent(page, "preview_thing")[-1]["stub_id"] == tsardom
    preview.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
    thing = _opened(page, "Tsardom of Moscavia")
    assert thing.get_by_test_id("stub-panel").count() == 0
    assert _sent(page, "accept_preview")[-1]["preview"]["stub_id"] == tsardom

    # the same id: Owl-folk's fact now links an entry
    thing.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    _fact(owl, ORIGIN).get_by_test_id("linked-ref").filter(
        has_text="Tsardom of Moscavia"
    ).wait_for(state="visible", timeout=TIMEOUT_MS)


def test_prompt_names_highlight_and_repick_adds_aka(app, page, fixed_preview):
    name = _world_name("Vasel")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[MOSCAVIA, OWL_FOLK]
    )
    tsardom = world.things["Tsardom of Moscavia"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    box = _place_box(page)
    box.get_by_label("Describe it").fill(
        "A riverside town in Moscavia where Owl-folk trade with barge crews."
    )

    # an exact name is matched; a partial one only suggested (dotted)
    owl = box.get_by_test_id("name-match").filter(has_text="Owl-folk")
    owl.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "matched" in owl.get_attribute("class")
    moscavia = box.get_by_test_id("name-match").filter(has_text="Moscavia")
    assert "suggested" in moscavia.get_attribute("class")

    # "did you mean": picking the stub matches it
    moscavia.hover()
    popover = page.get_by_test_id("name-popover").filter(has_text="Did you mean")
    popover.wait_for(state="visible", timeout=TIMEOUT_MS)
    popover.get_by_test_id("name-candidate").filter(
        has_text="Tsardom of Moscavia"
    ).click()
    popover.wait_for(state="hidden", timeout=TIMEOUT_MS)
    expect(moscavia).to_have_class(re.compile(r"\bmatched\b"))

    # the names the prompt names are part of the context shown
    context = box.get_by_test_id("ai-context")
    context.get_by_text("Context the AI gets").click()
    named = context.get_by_test_id("context-named")
    named.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "Tsardom of Moscavia" in named.inner_text()
    assert "Owl-folk" in named.inner_text()

    fixed_preview(_preview("Vasel Landing", "Barges tie up at its long quay."))
    preview = _create_and_wait(page, box)
    picks = _sent(page, "preview_thing")[-1]["picks"]
    assert picks == {"Moscavia": tsardom, "Owl-folk": world.things["Owl-folk"]}
    preview.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
    thing = _opened(page, "Vasel Landing")

    # the re-pick taught the stub the name as written: common, not everyday
    thing.get_by_role("button", name="Back").click()
    page.get_by_test_id("stub-item").filter(has_text="Tsardom of Moscavia").click()
    stub = _opened(page, "Tsardom of Moscavia")
    row = stub.get_by_test_id("aka-editor").get_by_test_id("aka-row")
    row.filter(has_text="Moscavia").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "common" in row.inner_text()
    assert row.count() == 1


def test_fill_stub_instead(app, page, fixed_preview):
    name = _world_name("Kalmara")
    world = seed_fm_world(app.root, name, present_year=1026, things=[KALMARA])
    kalmara = world.things["Kalmara"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    box = _place_box(page)
    box.get_by_label("Describe it").fill("A riverside town of reed-cutters.")

    # a preview named like a stub of its kind offers to fill that stub
    fixed_preview(_preview("Kalmara", "Reed-cutters work its shallows."))
    preview = _create_and_wait(page, box)
    fill = preview.get_by_role("button", name=re.compile("Fill the stub"))
    assert "Kalmara" in fill.text_content()
    fill.click()
    thing = _opened(page, "Kalmara")
    assert thing.get_by_test_id("stub-panel").count() == 0
    assert _sent(page, "accept_preview")[-1]["into_stub"] == kalmara

    # one Kalmara, an entry now, and no stub of it left
    thing.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-place").click()
    cards = page.get_by_test_id("thing-card").filter(has_text="Kalmara")
    cards.first.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert cards.count() == 1
    assert page.get_by_test_id("stub-item").filter(has_text="Kalmara").count() == 0


YELENA = {"kind": "character", "name": "Yelena", "stub": "live"}
VASHA = {"kind": "character", "name": "Vasha", "born": 1000}


def test_add_reference_menu_inserts_pick(app, page):
    name = _world_name("Vasel")
    world = seed_fm_world(app.root, name, present_year=1026, things=[YELENA, VASHA])
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-character").click()
    vasha = _open_thing(page, "Vasha")
    vasha.get_by_role("button", name="Add fact", exact=True).click()
    form = vasha.get_by_test_id("fact-form")
    text = form.get_by_label("Fact", exact=True)
    text.fill("Sailed north with ")

    # right-click: cut, copy and paste stay, and Add reference is added
    text.click(button="right")
    menu = page.get_by_test_id("reference-menu")
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    for item in ("Cut", "Copy", "Paste"):
        assert menu.get_by_text(item, exact=True).is_visible()
    menu.get_by_text("Add reference…").click()

    # the search covers stubs too; the name goes in at the cursor
    assert "stub" in _search_and_pick(page, "yel", "Yelena")
    expect(text).to_have_value("Sailed north with Yelena")
    form.get_by_role("button", name="Save").click()

    fact = _fact(vasha, "Sailed north with Yelena")
    fact.get_by_test_id("linked-stub").filter(has_text="Yelena").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert _sent(page, "add_fact")[-1]["picks"] == {"Yelena": world.things["Yelena"]}


def test_reference_menu_undo_redo_select_all_delete_and_shift_bypass(app, page):
    name = _world_name("Vasel")
    seed_fm_world(app.root, name, present_year=1026, things=[YELENA, VASHA])
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-character").click()
    vasha = _open_thing(page, "Vasha")
    vasha.get_by_role("button", name="Add fact", exact=True).click()
    form = vasha.get_by_test_id("fact-form")
    text = form.get_by_label("Fact", exact=True)
    text.click()
    text.press_sequentially("Sailed north")
    expect(text).to_have_value("Sailed north")

    # shift+right-click skips the custom menu, for the browser's own
    # (whose spell-check scripts can't see)
    menu = page.get_by_test_id("reference-menu")
    text.click(button="right", modifiers=["Shift"])
    expect(menu).not_to_be_visible()

    # Undo, through the menu, reverts all of what was just typed
    text.click(button="right")
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    menu.get_by_text("Undo", exact=True).click()
    expect(text).to_have_value("")

    # Redo brings it back
    text.click(button="right")
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    menu.get_by_text("Redo", exact=True).click()
    expect(text).to_have_value("Sailed north")

    # Select all, then Delete (each its own menu, since picking one closes
    # it), empties the field
    text.click(button="right", position={"x": 5, "y": 5})
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    menu.get_by_text("Select all", exact=True).click()
    text.click(button="right", position={"x": 5, "y": 5})
    menu.wait_for(state="visible", timeout=TIMEOUT_MS)
    menu.get_by_text("Delete", exact=True).click()
    expect(text).to_have_value("")


def test_edit_linked_fact_keeps_links_and_makes_stubs(app, page):
    name = _world_name("Moscavia")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[MOSCAVIA, OWL_FOLK]
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")

    # the form edits the words as they read, not the references
    _fact(owl, NESTING).get_by_role("button", name="Edit fact").click()
    form = owl.get_by_test_id("fact-form")
    text = form.get_by_label("Fact", exact=True)
    expect(text).to_have_value("Most nest along the Moscavia border, near Iron Gate.")

    # an unknown name offers a stub
    gate = form.get_by_test_id("name-unknown").filter(has_text="Iron Gate")
    gate.wait_for(state="visible", timeout=TIMEOUT_MS)
    gate.hover()
    unknown = page.get_by_test_id("unknown-popover")
    unknown.wait_for(state="visible", timeout=TIMEOUT_MS)
    unknown.get_by_test_id("stub-kind-option").filter(has_text="Place").click()

    text.fill("Many nest along the Moscavia border, near Iron Gate.")
    form.get_by_role("button", name="Save").click()

    # the new wording, the old link to the same stub, and the new stub
    fact = _fact(owl, "Many nest along the Moscavia border, near Iron Gate.")
    fact.get_by_test_id("linked-stub").filter(has_text="Iron Gate").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert fact.get_by_test_id("linked-stub").filter(has_text="Moscavia").count() == 1
    # the old link goes by position; a partial match like it would stay plain
    sent = _sent(page, "correct_fact")[-1]
    assert sent["text"] == "Many nest along the Moscavia border, near Iron Gate."
    assert sent["spans"] == [
        {"start": 20, "end": 28, "ref": world.things["Tsardom of Moscavia"]}
    ]
    assert "picks" not in sent
    made = _wait_sent(page, "make_stub")
    assert (made["text"], made["kind"]) == ("Iron Gate", "place")


MAREN_VOS = {"kind": "character", "name": "Maren Vos", "born": 990}
MAREN_HOLT = {"kind": "character", "name": "Maren Holt", "born": 992}
FERRY = {
    "kind": "place",
    "name": "Sallow Ferry",
    "facts": [
        {
            "category": "description",
            "text": "Run by [[@Maren Vos|Maren]] these days, not Maren Holt.",
        }
    ],
}


def test_repoint_link_keeps_words(app, page):
    name = _world_name("Sallow")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[MAREN_VOS, MAREN_HOLT, FERRY]
    )
    holt = world.things["Maren Holt"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    ferry = _open_thing(page, "Sallow Ferry")

    # the link's card offers Re-point, which searches as Add reference does
    link = _fact(ferry, "these days").get_by_test_id("linked-ref")
    link.hover()
    card = page.get_by_test_id("link-card")
    card.wait_for(state="visible", timeout=TIMEOUT_MS)
    card.get_by_role("button", name="Re-point…").click()
    _search_and_pick(page, "holt", "Maren Holt")
    _choose_mode(page)

    # that one reference, now meaning the other Maren; the known name
    # written plain stays plain
    sent = _wait_sent(page, "repoint_ref")
    assert (sent["occurrence"], sent["to_id"]) == (0, holt)
    fact = _fact(ferry, "Run by Maren these days, not Maren Holt.")
    link = fact.get_by_test_id("linked-ref")
    expect(link).to_have_count(1)
    expect(link).to_have_text("Maren")
    # the words are the same before the reply lands: its card names the
    # thing the link means now
    link.hover()
    expect(page.get_by_test_id("link-card").locator(".link-name")).to_have_text(
        "Maren Holt", timeout=TIMEOUT_MS
    )
    link.click()
    _opened(page, "Maren Holt")


ROWERS = {
    "kind": "place",
    "name": "Rowing Club",
    "facts": [
        {
            "category": "description",
            "text": "[[@Maren Vos|Maren]] rowed with [[@Maren Holt|Maren]].",
        }
    ],
}


def test_edit_keeps_same_name_links_apart(app, page):
    name = _world_name("Rowers")
    world = seed_fm_world(
        app.root, name, present_year=1026, things=[MAREN_VOS, MAREN_HOLT, ROWERS]
    )
    vos, holt = world.things["Maren Vos"], world.things["Maren Holt"]
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    page.get_by_test_id("kind-place").click()
    club = _open_thing(page, "Rowing Club")

    # two links written "Maren", to two Marens, each kept by its place
    _fact(club, "rowed with").get_by_role("button", name="Edit fact").click()
    form = club.get_by_test_id("fact-form")
    text = form.get_by_label("Fact", exact=True)
    expect(text).to_have_value("Maren rowed with Maren.")
    text.fill(" Maren rowed hard with Maren and Maren.")

    # picking a thing for the third, plain Maren picks it for that name,
    # leaving the two links theirs
    marks = form.get_by_test_id("name-match")
    expect(marks).to_have_count(3)
    marks.nth(2).hover()
    popover = page.get_by_test_id("name-popover").last
    popover.wait_for(state="visible", timeout=TIMEOUT_MS)
    popover.get_by_test_id("name-candidate").filter(has_text="Maren Vos").click()
    popover.wait_for(state="hidden", timeout=TIMEOUT_MS)
    form.get_by_role("button", name="Save").click()

    # the text is sent trimmed, its spans counted in it
    fact = _fact(club, "Maren rowed hard with Maren and Maren.")
    links = fact.get_by_test_id("linked-ref")
    expect(links).to_have_count(3)
    sent = _sent(page, "correct_fact")[-1]
    assert sent["text"] == "Maren rowed hard with Maren and Maren."
    assert sent["spans"] == [
        {"start": 0, "end": 5, "ref": vos},
        {"start": 22, "end": 27, "ref": holt},
    ]
    assert sent["picks"] == {"Maren": vos}
    links.nth(1).click()
    _opened(page, "Maren Holt")
