"""Connections on the world pages: linked text in facts, stubs (their hover
card, the Stubs tab, the kind lists and a stub's own page), other names,
and the stubs a scene setup will fill in.

The worlds are seeded through `talemate.world` (`seed.seed_fm_world`), the
facts' references written as `[[@Name|shown]]`. No model is asked
anything: scene setups and stub previews come from the fixed setup and
preview files.
"""

from __future__ import annotations


from playwright.sync_api import expect

from e2e.seed import seed_fm_world
from e2e.worlds.test_new_scene import _new_scene_dialog
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

MOSCAVIA = {"kind": "place", "name": "Tsardom of Moscavia", "stub": "live"}

OWL_FOLK = {
    "kind": "species",
    "name": "Owl-folk",
    "facts": [
        {
            "category": "origin",
            "text": "Everyone in the [[@Tsardom of Moscavia|Tsardom of Moscavia]]"
            " became owl-folk one day in 994.",
        },
        {"category": "physical", "text": "Fully feathered, with wings for arms."},
    ],
}

ORIGIN = "became owl-folk one day in 994"


def _stubs_tab(page):
    page.get_by_test_id("kind-stubs").click()
    tab = page.get_by_test_id("stubs-tab")
    tab.wait_for(state="visible", timeout=TIMEOUT_MS)
    return tab


def _stub_card(page, link):
    link.hover()
    card = page.get_by_test_id("stub-card")
    card.wait_for(state="visible", timeout=TIMEOUT_MS)
    return card


def test_stub_links_tab_and_aka(app, page):
    name = _world_name("Moscavia")
    seed_fm_world(app.root, name, present_year=1026, things=[MOSCAVIA, OWL_FOLK])
    _open_world(page, name)
    _world_tab(page)

    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")

    # the origin fact links the stub, in the stub style
    origin = _fact(owl, ORIGIN)
    stub = origin.get_by_test_id("linked-stub")
    stub.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert stub.inner_text() == "Tsardom of Moscavia"
    assert origin.get_by_test_id("linked-ref").count() == 0
    # and the entry lists it among the stubs it named
    assert "Tsardom of Moscavia" in owl.get_by_test_id("named-stubs").inner_text()

    # hovering it: not made yet, its kind, one mention, Expand and Ignore
    card = _stub_card(page, stub)
    text = card.inner_text()
    assert "not made yet" in text
    assert "place" in text
    assert "1 mention" in text
    assert card.get_by_role("button", name="Expand").is_enabled()
    card.get_by_role("button", name="Ignore").click()

    # ignored: the fact reads as plain text, and the section drops it
    origin.get_by_test_id("linked-stub").wait_for(state="detached", timeout=TIMEOUT_MS)
    assert "Tsardom of Moscavia" in origin.inner_text()
    assert owl.get_by_test_id("named-stubs").count() == 0

    # the Stubs tab leaves it out, until "show ignored"
    owl.get_by_role("button", name="Back").click()
    tab = _stubs_tab(page)
    rows = tab.get_by_test_id("stub-row")
    assert rows.filter(has_text="Tsardom of Moscavia").count() == 0
    tab.get_by_label("show ignored").check()
    ignored = rows.filter(has_text="Tsardom of Moscavia")
    ignored.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "ignored" in ignored.inner_text()
    assert "Owl-folk" in ignored.inner_text()

    # another name for the Owl-folk: saved, and shown when the page reopens
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    aka = owl.get_by_test_id("aka-editor")
    aka.get_by_role("button", name="Add other name").click()
    aka.get_by_label("Other name").fill("Moscavian Owls")
    aka.get_by_role("button", name="Add", exact=True).click()
    aka.get_by_test_id("aka-row").filter(has_text="Moscavian Owls").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    owl.get_by_role("button", name="Back").click()
    owl = _open_thing(page, "Owl-folk")
    row = owl.get_by_test_id("aka-editor").get_by_test_id("aka-row")
    row.filter(has_text="Moscavian Owls").wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "common" in row.inner_text()


YELENA = {"kind": "character", "name": "Yelena", "stub": "live"}
OLD_RITE = {"kind": "lore", "name": "Old Rite", "stub": "live"}
VASHA = {
    "kind": "character",
    "name": "Vasha",
    "born": 1000,
    "facts": [
        {
            "category": "background",
            "text": "Raised by her mother [[@Yelena|Yelena]], who kept the"
            " [[@Old Rite|Old Rite]].",
        }
    ],
}

YELENA_PREVIEW = {
    "name": "Yelena",
    "facts": [{"category": "background", "text": "A ferrywoman of the Vasel."}],
    "prose": {"appearance": "", "personality": "", "background": ""},
}


def test_stub_lists_page_and_expand(app, page, fixed_preview):
    name = _world_name("Vasel")
    seed_fm_world(app.root, name, present_year=1026, things=[YELENA, OLD_RITE, VASHA])
    _open_world(page, name)
    _world_tab(page)

    # events and items are kinds of their own
    assert page.get_by_test_id("kind-event").is_visible()
    assert page.get_by_test_id("kind-item").is_visible()

    # the Characters list: Vasha, then Yelena dimmed under "Stubs"
    page.get_by_test_id("kind-character").click()
    page.get_by_test_id("thing-card").filter(has_text="Vasha").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert page.get_by_test_id("thing-card").filter(has_text="Yelena").count() == 0
    stub_item = page.get_by_test_id("stub-item").filter(has_text="Yelena")
    assert "not made yet" in stub_item.inner_text()

    # a stub's own page: its card and what mentions it
    stub_item.click()
    yelena = page.get_by_test_id("thing-page")
    panel = yelena.get_by_test_id("stub-panel")
    panel.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "1 mention" in panel.inner_text()
    mention = yelena.get_by_test_id("stub-mention")
    assert "Vasha" in mention.inner_text()
    assert "Raised by her mother Yelena" in mention.inner_text()

    # Vasha's page
    mention.get_by_text("Vasha").click()
    vasha = page.get_by_test_id("thing-page")
    vasha.get_by_test_id("thing-name").filter(has_text="Vasha").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    fact = _fact(vasha, "Raised by her mother")

    # expanding Yelena: her kind's create box, from the stub
    card = _stub_card(
        page, fact.get_by_test_id("linked-stub").filter(has_text="Yelena")
    )
    card.get_by_role("button", name="Expand").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").filter(has_text="Yelena").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    # the prompt is suggested from her mention
    expect(box.get_by_label("Describe it")).to_have_value(
        "Yelena: Raised by her mother Yelena, who kept the Old Rite.",
        timeout=TIMEOUT_MS,
    )

    # accepting fills the stub: the same page, now an entry, and Vasha's
    # fact links to it
    fixed_preview(YELENA_PREVIEW)
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("draft-page")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    preview.get_by_role("button", name="Accept").click()
    yelena = page.get_by_test_id("thing-page")
    yelena.get_by_test_id("thing-name").filter(has_text="Yelena").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert yelena.get_by_test_id("stub-panel").count() == 0
    assert _fact(yelena, "A ferrywoman of the Vasel").count() == 1
    yelena.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-character").click()
    page.get_by_test_id("thing-card").filter(has_text="Yelena").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    vasha = _open_thing(page, "Vasha")
    fact = _fact(vasha, "Raised by her mother")
    fact.get_by_test_id("linked-ref").filter(has_text="Yelena").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )


def test_stubs_list_shows_the_tag(app, page):
    """Hubs round 1, P3 (feedback line 8): a stub's tag shows in the Stubs
    list ("no tag" for none), on its link's hover card and in the expand
    box's header."""

    name = _world_name("Vasel")
    tagged = {**YELENA, "fields": {"tag": "ferrywoman"}}
    seed_fm_world(app.root, name, present_year=1026, things=[tagged, OLD_RITE, VASHA])
    _open_world(page, name)
    _world_tab(page)

    rows = _stubs_tab(page).get_by_test_id("stub-row")
    yelena = rows.filter(has_text="Yelena")
    yelena.wait_for(state="visible", timeout=TIMEOUT_MS)
    expect(yelena.get_by_test_id("stub-row-tag")).to_have_text("ferrywoman")
    expect(
        rows.filter(has_text="Old Rite").get_by_test_id("stub-row-tag")
    ).to_have_text("no tag")

    page.get_by_test_id("kind-character").click()
    vasha = _open_thing(page, "Vasha")
    fact = _fact(vasha, "Raised by her mother")
    card = _stub_card(
        page, fact.get_by_test_id("linked-stub").filter(has_text="Yelena")
    )
    expect(card.get_by_test_id("stub-tag")).to_have_text("ferrywoman")
    card.get_by_role("button", name="Expand").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").filter(has_text="Yelena").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    expect(box.get_by_test_id("from-stub-tag")).to_have_text("ferrywoman")


def test_setup_cards_show_stub_previews(app, page, fixed_setup, fixed_preview):
    name = _world_name("Vasel")
    seed_fm_world(app.root, name, present_year=1026, things=[YELENA, OLD_RITE, VASHA])
    fixed_setup(
        {
            "player": "Vasha",
            "characters": ["Yelena"],
            "place": {"name": "The ferry", "facts": ["A flat ferry."]},
            "goal": "Cross the river.",
            "intro": "The ferry creaks.",
        }
    )
    fixed_preview(YELENA_PREVIEW)
    _open_world(page, name)
    dialog = _new_scene_dialog(page, "Vasha crosses the river with Yelena.")
    dialog.get_by_role("button", name="Set up scene").click()
    stub = page.get_by_test_id("setup-stub-preview").filter(has_text="Yelena")
    stub.wait_for(state="visible", timeout=TIMEOUT_MS)
    text = stub.inner_text()
    assert "will be filled in" in text
    assert "A ferrywoman of the Vasel." in text


KALMARA_PREVIEW = {
    "name": "Kalmara",
    "facts": [{"category": "description", "text": "A river port."}],
    "prose": {"description": "A river port."},
}


def test_expanding_over_a_preview_asks_first(app, page, fixed_preview):
    """Expanding a stub while a draft waits to be accepted asks before
    dropping it: keeping it changes nothing; discarding it expands."""

    name = _world_name("Kalmara")
    seed_fm_world(app.root, name, present_year=1026, things=[YELENA, OLD_RITE, VASHA])
    _open_world(page, name)
    _world_tab(page)

    page.get_by_test_id("kind-place").click()
    box = page.get_by_test_id("create-box")
    box.get_by_label("Describe it").fill("a river port")
    fixed_preview(KALMARA_PREVIEW)
    box.get_by_role("button", name="Create").click()
    preview = page.get_by_test_id("draft-page")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)

    def expand_yelena():
        row = _stubs_tab(page).get_by_test_id("stub-row").filter(has_text="Yelena")
        row.get_by_role("button", name="Expand").click()
        dialog = page.get_by_test_id("expand-ask")
        dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
        assert "Kalmara" in dialog.inner_text()
        return dialog

    expand_yelena().get_by_role("button", name="Keep the draft").click()
    page.get_by_test_id("expand-ask").wait_for(state="hidden", timeout=TIMEOUT_MS)
    page.get_by_test_id("kind-place").click()
    preview = page.get_by_test_id("draft-page")
    preview.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "A river port." in preview.inner_text()

    expand_yelena().get_by_role("button", name="Discard and expand").click()
    box = page.get_by_test_id("create-box")
    box.get_by_test_id("from-stub").filter(has_text="Yelena").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert page.get_by_test_id("draft-page").count() == 0
