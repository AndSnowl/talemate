"""Species, race and mix pages, and what a character inherits.

The world is seeded through `talemate.world` (`seed.seed_fm_world`): the
Owl-folk species, its Snowy race, Vasha, a Snowy character, and Old
Moss, an owl-folk past the species' lifespan. No model is asked anything.
"""

from __future__ import annotations

import re

from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _fact,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)
from e2e.seed import seed_fm_world


def _measure(name: str, low: float, high: float) -> dict:
    return {"name": name, "min": low, "max": high, "unit": "ft"}


OWL_FOLK = {
    "kind": "species",
    "name": "Owl-folk",
    "fields": {
        "lifespan": 70,
        "adult_age": 12,
        "measures": [_measure("height", 3, 4), _measure("wingspan", 7, 9)],
    },
    "facts": [
        {
            "category": "physical",
            "text": "Wings in place of arms; taloned feet serve as hands.",
        },
        {"category": "instinct", "text": "Most alert at dusk and dawn."},
    ],
}

SNOWY = {
    "kind": "race",
    "name": "Snowy",
    "links": {"species": "Owl-folk"},
    "fields": {"measures": [_measure("wingspan", 8.5, 9)]},
    "facts": [
        {"category": "physical", "text": "White plumage flecked with grey."},
        {"category": "physical", "text": "Yellow eyes."},
    ],
}

VASHA = {
    "kind": "character",
    "name": "Vasha",
    "born": 978,
    "links": {"heritage": "Snowy"},
    "facts": [{"category": "personality", "text": "Quiet and observant."}],
}


# past the Owl-folk lifespan of 70 in 1026: flagged, never refused
OLD_MOSS = {
    "kind": "character",
    "name": "Old Moss",
    "born": 940,
    "links": {"heritage": "Owl-folk"},
}


def _inherited(thing, text: str):
    return thing.get_by_test_id("inherited-fact").filter(has_text=text)


def test_species_page_and_inheritance(app, page):
    name = _world_name("Frosthollow")
    seed_fm_world(
        app.root, name, present_year=1026, things=[OWL_FOLK, SNOWY, VASHA, OLD_MOSS]
    )
    _open_world(page, name)
    _world_tab(page)

    # races and mixes aren't listed at the top level, only species
    assert page.get_by_test_id("kind-species").is_visible()
    assert page.get_by_test_id("kind-race").count() == 0
    assert page.get_by_test_id("kind-mix").count() == 0

    # the species page: its numbers, and its races
    page.get_by_test_id("kind-species").click()
    owl = _open_thing(page, "Owl-folk")
    lifespan = owl.get_by_test_id("numbers-lifespan")
    lifespan.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert "70 years" in lifespan.inner_text()
    assert "12" in owl.get_by_test_id("numbers-adult_age").inner_text()
    measures = owl.get_by_test_id("numbers-measures").inner_text()
    assert "wingspan" in measures.lower() and "7–9 ft" in measures
    races = owl.get_by_test_id("races-section")
    assert owl.get_by_test_id("mixes-section").is_visible()

    # a race page: its unset lifespan is the species', shown as inherited;
    # its own wingspan wins over the species'
    races.get_by_text("Snowy").click()
    snowy = page.get_by_test_id("thing-page")
    snowy.get_by_test_id("thing-name").filter(has_text="Snowy").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    race_lifespan = snowy.get_by_test_id("numbers-lifespan")
    assert "70 years" in race_lifespan.inner_text()
    assert "inherited" in race_lifespan.inner_text()
    assert "8.5–9 ft" in snowy.get_by_test_id("numbers-measures").inner_text()
    # who uses the race: Vasha, through his heritage
    assert "Vasha" in snowy.get_by_test_id("referenced-in").inner_text()

    # setting the race's own lifespan replaces the inherited one
    race_lifespan.get_by_role("button", name="Edit lifespan").click()
    race_lifespan.get_by_label("Lifespan").fill("65")
    race_lifespan.get_by_role("button", name="Save").click()
    race_lifespan.filter(has_text="65 years").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert "inherited" not in race_lifespan.inner_text()

    # Vasha's page: heritage links, his life stage, inherited facts dimmed
    # with where they came from
    snowy.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-character").click()
    vasha = _open_thing(page, "Vasha")
    assert "age 48 · adult" in vasha.get_by_test_id("field-born").inner_text()
    assert vasha.get_by_test_id("past-lifespan").count() == 0
    heritage = vasha.get_by_test_id("field-heritage")
    assert "Owl-folk" in heritage.inner_text() and "Snowy" in heritage.inner_text()

    wings = _inherited(vasha, "Wings in place of arms")
    wings.wait_for(state="visible", timeout=TIMEOUT_MS)
    assert wings.get_by_test_id("inherited-source").inner_text() == "Owl-folk"
    eyes = _inherited(vasha, "Yellow eyes.")
    assert eyes.get_by_test_id("inherited-source").inner_text() == "Snowy"

    # Override opens the fact form filled in; saving strikes the inherited
    # fact through
    eyes.get_by_test_id("override-button").click()
    form = vasha.get_by_test_id("fact-form")
    text = form.get_by_label("Fact", exact=True)
    assert text.input_value() == "Yellow eyes."
    text.fill("Blue eyes")
    form.get_by_role("button", name="Save").click()

    _fact(vasha, "Blue eyes").wait_for(state="visible", timeout=TIMEOUT_MS)
    eyes.get_by_text("replaced by its own fact").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    assert eyes.locator("s").inner_text() == "Yellow eyes."
    assert eyes.get_by_test_id("override-button").count() == 0
    assert _inherited(vasha, "White plumage").get_by_test_id("override-button").count()

    # a source chip opens the page the fact comes from
    wings.get_by_test_id("inherited-source").click()
    page.get_by_test_id("thing-name").filter(
        has_text=re.compile("^Owl-folk$")
    ).wait_for(state="visible", timeout=TIMEOUT_MS)

    # an age past the lifespan shows a warning chip by the life stage
    page.get_by_role("button", name="Back").click()
    page.get_by_test_id("kind-character").click()
    moss = _open_thing(page, "Old Moss")
    born = moss.get_by_test_id("field-born")
    assert "age 86 · elder" in born.inner_text()
    assert born.get_by_test_id("past-lifespan").is_visible()
