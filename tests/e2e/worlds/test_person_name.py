"""A person's page (languages 4b-2, Task 6; mockup frame B): the Name
section's labelled parts and where they came from, editing a part, what
others call them on the relationship it belongs to (only what differs),
and a title made from a meaning."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from _people_names_helpers import DRASSONAIS
from talemate.languages.entry import fields_of
from talemate.languages.models import DictionaryEntry

from e2e.seed import seed_fm_world
from e2e.worlds.test_new_scene import SEND_SPY_JS
from e2e.worlds.test_world_tab import (
    TIMEOUT_MS,
    _open_thing,
    _open_world,
    _world_name,
    _world_tab,
)

pytestmark = pytest.mark.e2e

LANGUAGE = DRASSONAIS.model_copy(
    update={
        "dictionary": [DictionaryEntry(word="chef", meanings=["chief"], part="noun")]
    }
)


def _parts(*texts, house_from=None):
    labels = ["given", "of", "house"]
    sources = ["rolled", "word", "inherited" if house_from else "typed"]
    parts = [
        {"label": label, "text": text, "source": source}
        for label, text, source in zip(labels, texts, sources)
    ]
    if house_from:
        parts[2] |= {"from": house_from, "from_role": "daughter of"}
    return parts


def world(app, page, stem):
    name = _world_name(stem)
    seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": "Drassonais",
                "fields": {"name": "Drassonais", **fields_of(LANGUAGE)},
            },
            {
                "kind": "place",
                "name": "Duchy of Drassone",
                "languages": [{"language": "Drassonais", "role": "official"}],
            },
            {
                "kind": "character",
                "name": "Eilhaud of Drassone",
                "filings": [{"target": "Duchy of Drassone", "role": "duke"}],
                "name_parts": {
                    "language": "Drassonais",
                    "rule": "noble-men",
                    "shape": 0,
                    "built_as": {"sex": "man", "rank": "noble"},
                    "parts": _parts("Eilhaud", "di", "Drassone"),
                },
            },
            {"kind": "character", "name": "Tiboud"},
            {"kind": "character", "name": "Aurande"},
            {
                "kind": "character",
                "name": "Maëlis of Drassone",
                "filings": [{"target": "Eilhaud of Drassone", "role": "daughter of"}],
                "fields": {
                    "aka": [
                        {
                            "name": "Maë",
                            "tag": "proper",
                            "everyday": False,
                            "kind": "own",
                            "by": "Tiboud",
                        },
                        {
                            "name": "Maëlisette",
                            "tag": "proper",
                            "everyday": False,
                            "kind": "pet",
                            "rule": "pets",
                        },
                    ]
                },
                "name_parts": {
                    "language": "Drassonais",
                    "rule": "noble-women",
                    "shape": 0,
                    "built_as": {"sex": "woman", "rank": "noble"},
                    "parts": _parts(
                        "Maëlis", "di", "Drassone", house_from="Eilhaud of Drassone"
                    ),
                },
                "facts": [
                    {
                        "category": "relationship",
                        "text": "Sister of [[@Tiboud|Tiboud]].",
                    },
                    {
                        "category": "relationship",
                        "text": "Daughter of [[@Aurande|Aurande]].",
                    },
                ],
            },
        ],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    return _open_thing(page, "Maëlis of Drassone")


def _section(page):
    section = page.get_by_test_id("person-name")
    expect(section).to_be_visible(timeout=TIMEOUT_MS)
    return section


def _fact(page, text):
    return page.locator(".fact-host").filter(has_text=text).first


def test_name_section_shows_parts_and_their_source(app, page):
    world(app, page, "Person parts")
    section = _section(page)
    parts = section.get_by_test_id("person-name-part")
    expect(parts).to_have_count(3)
    expect(parts.nth(0)).to_contain_text("Maëlis")
    expect(parts.nth(1)).to_contain_text("of")
    expect(parts.nth(2)).to_contain_text("Drassone")
    expect(parts.nth(2)).to_contain_text("from her father Eilhaud of Drassone")
    expect(section.get_by_test_id("person-name-rule")).to_contain_text(
        "Drassonais · noble-women"
    )
    expect(section.get_by_test_id("person-pet")).to_have_text("Maëlisette")
    expect(section.get_by_test_id("person-pet-name")).to_contain_text("used by family")


def test_editing_a_part_renames_the_page(app, page):
    world(app, page, "Person edit")
    section = _section(page)
    section.get_by_test_id("person-name-part-edit").first.click()
    field = section.get_by_test_id("person-name-part-input").locator("input")
    field.fill("Ysolde")
    field.press("Enter")
    expect(page.get_by_test_id("thing-name")).to_have_text(
        "Ysolde of Drassone", timeout=TIMEOUT_MS
    )
    expect(section.get_by_test_id("person-name-part").nth(0)).to_contain_text("typed")


def test_calls_her_shows_only_what_differs(app, page):
    world(app, page, "Person calls")
    _section(page)
    sister = _fact(page, "Sister of Tiboud")
    expect(sister.get_by_test_id("calls-line-fold")).to_contain_text("calls her: Maë")
    daughter = _fact(page, "Daughter of Aurande")
    expect(daughter.get_by_test_id("calls-line-fold")).to_have_count(0)


def test_a_built_as_change_keeps_the_name(app, page):
    world(app, page, "Person built as")
    section = _section(page)
    section.get_by_test_id("person-built-as-rank").click()
    page.get_by_role("option", name="common").or_(
        page.locator(".v-list-item").filter(has_text="common")
    ).first.click()
    expect(section.get_by_test_id("person-built-as-rank")).to_have_text(
        "common", timeout=TIMEOUT_MS
    )
    expect(page.get_by_test_id("thing-name")).to_have_text("Maëlis of Drassone")


def test_title_from_a_meaning_opens_name_it_and_saves_a_title(app, page):
    world(app, page, "Person title")
    section = _section(page)
    section.get_by_test_id("person-title-add").click()
    section.get_by_test_id("person-title-meaning").click()
    panel = page.get_by_test_id("name-it")
    expect(panel).to_be_visible(timeout=TIMEOUT_MS)
    panel.get_by_test_id("name-it-meaning").locator("input").fill("chief")
    panel.get_by_test_id("name-it-find").click()
    candidate = panel.get_by_test_id("name-it-candidate").first
    expect(candidate).to_contain_text("Chef", timeout=TIMEOUT_MS)
    candidate.locator(".name").click()
    expect(
        section.get_by_test_id("person-title").filter(has_text="Chef")
    ).to_have_count(1, timeout=TIMEOUT_MS)
    expect(page.get_by_test_id("thing-name")).to_have_text("Maëlis of Drassone")


# --- Name it on a person (Task 7) ---------------------------------------------


def _builder(page):
    page.get_by_test_id("name-it-thing").click()
    panel = page.get_by_test_id("name-it")
    expect(panel.get_by_test_id("name-builder-part")).to_have_count(
        3, timeout=TIMEOUT_MS
    )
    return panel


def test_name_it_on_a_person_pins_the_inherited_house(app, page):
    world(app, page, "Person name it")
    panel = _builder(page)
    house = panel.get_by_test_id("name-builder-part").nth(2)
    expect(house.get_by_test_id("name-builder-inherited-pin")).to_be_visible()
    expect(house).to_contain_text("inherited")
    expect(panel.get_by_test_id("name-it-built")).to_have_text(
        "Maëlis of Drassone", timeout=TIMEOUT_MS
    )


def test_reroll_keeps_inherited_parts(app, page):
    world(app, page, "Person reroll")
    panel = _builder(page)
    # the given name, pinned as it is, let go
    panel.get_by_test_id("name-builder-part").nth(0).get_by_test_id(
        "name-builder-pin"
    ).click()
    for _ in range(20):
        panel.get_by_test_id("name-it-reroll").click()
        page.wait_for_timeout(300)
        built = panel.get_by_test_id("name-it-built").inner_text()
        assert built.endswith(" of Drassone")
        if not built.startswith("Maëlis"):
            break
    assert not built.startswith("Maëlis")


def test_use_this_name_stores_parts(app, page):
    world(app, page, "Person use")
    panel = _builder(page)
    panel.get_by_test_id("name-builder-part").nth(0).get_by_test_id(
        "name-builder-pin"
    ).click()
    panel.get_by_test_id("name-it-reroll").click()
    rolls = panel.get_by_test_id("name-builder-part").nth(0)
    other = (
        rolls.get_by_test_id("name-builder-roll").filter(has_not_text="Maëlis").first
    )
    expect(other).to_be_visible(timeout=TIMEOUT_MS)
    given = other.inner_text().strip()
    other.click()
    panel.get_by_test_id("name-it-use").click()
    expect(page.get_by_test_id("thing-name")).to_have_text(
        f"{given} of Drassone", timeout=TIMEOUT_MS
    )
    section = _section(page)
    expect(section.get_by_test_id("person-name-part").nth(0)).to_contain_text(given)
    expect(section.get_by_test_id("person-name-part").nth(2)).to_contain_text(
        "from her father Eilhaud of Drassone"
    )


def test_draft_marks_the_name_and_name_it_builds_it(
    app, page, fixed_preview, fixed_clean
):
    from e2e.worlds.test_drafts import _draft

    world(app, page, "Person draft")
    fixed_preview(
        {
            "name": "Elise",
            "person": {
                "sex": "woman",
                "rank": "noble",
                "name_meaning": "",
                "title": "Lady",
            },
            "facts": [
                {
                    "category": "background",
                    "text": "Elise grew up at the Drassonais court.",
                },
                {"category": "personality", "text": "Elise is quiet and watchful."},
            ],
            "prose": {},
        }
    )
    fixed_clean(
        {
            "language-roles": {
                "languages": [{"language": "Drassonais", "role": "official"}]
            },
            "name-flags": {"names": []},
        }
    )
    draft = _draft(page, "character", "a Drassonais noblewoman of the court")
    # drafts only mark (owner, 2026-11-06): the model's name stays, and
    # Name it builds one from the rules
    flag = draft.get_by_test_id("draft-name-flag")
    expect(flag).to_contain_text("Name it can build it", timeout=TIMEOUT_MS)
    assert flag.locator(".name-flagged").inner_text().strip() == "Elise"
    flag.get_by_test_id("draft-name-flag-name-it").click()
    panel = page.get_by_test_id("name-it")
    expect(panel.get_by_test_id("name-builder-part")).to_have_count(
        3, timeout=TIMEOUT_MS
    )
    expect(panel.get_by_test_id("name-it-built")).to_contain_text(
        " of ", timeout=TIMEOUT_MS
    )


def test_a_drafted_person_has_the_name_section_and_keeps_its_titles(
    app, page, fixed_preview, fixed_clean
):
    """Owner, 2026-11-05: titles (and the rest of the Name section) on a
    draft as on the page."""

    from e2e.worlds.test_drafts import _draft

    world(app, page, "Person draft titles")
    fixed_preview(
        {
            "name": "Elise",
            "person": {
                "sex": "woman",
                "rank": "noble",
                "name_meaning": "",
                "title": "Lady",
            },
            "facts": [
                {
                    "category": "background",
                    "text": "Elise grew up at the Drassonais court.",
                }
            ],
            "prose": {},
        }
    )
    fixed_clean(
        {
            "language-roles": {
                "languages": [{"language": "Drassonais", "role": "official"}]
            },
            "name-flags": {"names": []},
        }
    )
    draft = _draft(page, "character", "a Drassonais noblewoman of the court")
    section = draft.get_by_test_id("person-name")
    expect(section.get_by_test_id("person-name-none")).to_be_visible(timeout=TIMEOUT_MS)
    expect(
        section.get_by_test_id("person-title").filter(has_text="Lady")
    ).to_have_count(1)
    section.get_by_test_id("person-title-add").click()
    field = section.get_by_test_id("person-title-input").locator("input")
    field.fill("Warden")
    field.press("Enter")
    expect(
        section.get_by_test_id("person-title").filter(has_text="Warden")
    ).to_have_count(1, timeout=TIMEOUT_MS)
    draft.get_by_test_id("draft-bar").get_by_role("button", name="Accept").click()
    expect(page.get_by_test_id("draft-page")).to_have_count(0, timeout=TIMEOUT_MS)
    accepted = _section(page)
    expect(
        accepted.get_by_test_id("person-title").filter(has_text="Warden")
    ).to_have_count(1, timeout=TIMEOUT_MS)


def test_name_it_lists_main_rules_before_pieces(app, page):
    """Languages 4c: main rules first, then "Pieces" in Name it's dropdown."""

    world(app, page, "Person rule menu")
    page.get_by_test_id("name-it-thing").click()
    panel = page.get_by_test_id("name-it")
    panel.get_by_test_id("name-it-rule").click()
    menu = page.locator(".v-overlay--active .v-list")
    expect(menu.get_by_text("Pieces")).to_be_visible(timeout=TIMEOUT_MS)
    items = menu.locator(".v-list-item, .v-list-subheader").all_inner_texts()
    at = next(i for i, t in enumerate(items) if "Pieces" in t)
    assert "noble-women" in items[:at] and "women-given" in items[at:]


def _tsar_world(app, page, stem):
    """A sovereign rule that says "Gosmar" (tsar), and Tsar Aleksi III with
    no name parts (languages 4c)."""

    from talemate.languages.models import GeneratorDef, NamePart, NameShape

    lang = LANGUAGE.model_copy(deep=True)
    lang.people_names.kept_titles.append({"word": "Gosmar", "meaning": "tsar"})
    lang.generators.append(
        GeneratorDef(
            id="sovereign",
            name="The sovereign",
            use="character",
            description="the tsar and his heirs",
            shapes=[
                NameShape(
                    parts=[
                        NamePart(kind="word", word="Gosmar", label="title"),
                        NamePart(kind="rule", rule="men-given", label="given"),
                    ]
                )
            ],
        )
    )
    lang = lang.model_validate(lang.model_dump())
    name = _world_name(stem)
    seed_fm_world(
        app.root,
        name,
        things=[
            {
                "kind": "language",
                "name": "Drassonais",
                "fields": {"name": "Drassonais", **fields_of(lang)},
            },
            {
                "kind": "place",
                "name": "Duchy of Drassone",
                "languages": [{"language": "Drassonais", "role": "official"}],
            },
            {
                "kind": "character",
                "name": "Tsar Aleksi III",
                "filings": [{"target": "Duchy of Drassone", "role": "sovereign"}],
            },
        ],
    )
    page.evaluate(SEND_SPY_JS)
    _open_world(page, name)
    _world_tab(page)
    _open_thing(page, "Tsar Aleksi III")


def test_name_it_on_tsar_aleksi_iii_gives_the_whole_name(app, page):
    """Languages 4c: the sovereign rule says "Gosmar" (tsar), so "Tsar
    Aleksi III" becomes "Gosmar <name> III": the English title goes, the
    number stays."""

    import re

    _tsar_world(app, page, "Person tsar")
    page.get_by_test_id("name-it-thing").click()
    panel = page.get_by_test_id("name-it")
    panel.get_by_test_id("name-it-rule").click()
    page.locator(".v-overlay--active .v-list-item").filter(
        has_text="The sovereign"
    ).first.click()
    expect(panel.get_by_test_id("name-it-built")).to_contain_text(
        "Gosmar", timeout=TIMEOUT_MS
    )
    expect(panel.get_by_test_id("name-it-regnal").locator("input")).to_have_value("III")
    panel.get_by_test_id("name-it-use").click()
    expect(page.get_by_test_id("thing-name")).to_have_text(
        re.compile(r"^Gosmar \w+ III$"), timeout=TIMEOUT_MS
    )


def test_name_it_opens_on_the_models_pick(app, page, fixed_language):
    """Languages 4c: Name it on an unpicked person asks the model, switches
    to its pick and says why."""

    fixed_language({"rule": "sovereign", "sex": "man", "rank": "sovereign"})
    _tsar_world(app, page, "Person pick")
    page.get_by_test_id("name-it-thing").click()
    panel = page.get_by_test_id("name-it")
    expect(panel.get_by_test_id("name-it-picked")).to_contain_text(
        "the tsar and his heirs", timeout=TIMEOUT_MS
    )
    expect(panel.get_by_test_id("name-it-built")).to_contain_text(
        "Gosmar", timeout=TIMEOUT_MS
    )
