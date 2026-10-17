import json
import subprocess
import sys
from pathlib import Path

import pytest

from talemate.cultures.exchange import (
    CultureFile,
    ImportFormatError,
    apply_import,
    export_culture,
    preview_import,
)
from talemate.cultures.models import (
    Culture,
    CultureShare,
    GlossaryEntry,
    GlossaryOrigin,
    Language,
    Place,
)
from talemate.cultures.store import WorldStore

FIXTURE_PATH = Path(__file__).parent / "data" / "taelrik.culture.json"


def fixture_raw() -> str:
    return FIXTURE_PATH.read_text()


def make_store(tmp_path) -> WorldStore:
    return WorldStore(tmp_path)


def make_culture(culture_id: str, name: str) -> Culture:
    return Culture(
        id=culture_id, name=name, language=Language(name=name, level="naming")
    )


def make_glossary_entry(
    entry_id: str,
    text: str,
    language: str | None,
    status: str = "unreviewed",
    meaning: str = "",
    edited_by_owner: bool = False,
    renderings: dict[str, str] | None = None,
    kind: str = "word",
) -> GlossaryEntry:
    return GlossaryEntry(
        id=entry_id,
        text=text,
        language=language,
        kind=kind,
        meaning=meaning,
        renderings=renderings or {},
        origin=GlossaryOrigin(by="owner"),
        status=status,
        edited_by_owner=edited_by_owner,
    )


def test_preview_new_culture(tmp_path):
    store = make_store(tmp_path)

    preview = preview_import(store, fixture_raw())

    assert preview.culture_id == "taelrik"
    assert preview.culture_name == "Taelrik"
    assert preview.is_update is False
    assert preview.counts == {
        "words": 4,
        "phrases": 4,
        "generators": 3,
        "glossary": 3,
        "places": 2,
    }
    assert preview.name_clash is None


def test_preview_matches_unassigned_case_insensitive(tmp_path):
    store = make_store(tmp_path)
    store.save_glossary(
        [make_glossary_entry("g1", "veldhaer", language=None, kind="place")]
    )

    preview = preview_import(store, fixture_raw())
    assert preview.claimed_unassigned == ["veldhaer"]

    apply_import(store, fixture_raw(), today="2026-10-17")

    entries = store.load_glossary()
    claimed = next(e for e in entries if e.text == "veldhaer")
    assert claimed.language == "taelrik"
    assert claimed.status == "unreviewed"


def test_preview_flags_name_clash_with_other_id(tmp_path):
    store = make_store(tmp_path)
    store.save_culture(make_culture("river-folk", "Taelrik"))

    preview = preview_import(store, fixture_raw())
    assert preview.name_clash == "river-folk"

    # Apply still imports under the file's own id.
    culture = apply_import(store, fixture_raw(), today="2026-10-17")
    assert culture.id == "taelrik"
    assert "river-folk" in store.load_cultures()


def test_bad_json_and_bad_schema(tmp_path):
    store = make_store(tmp_path)

    with pytest.raises(ImportFormatError):
        preview_import(store, "{")

    with pytest.raises(ImportFormatError, match="culture"):
        preview_import(store, json.dumps({"culture": {"name": 1}}))


def test_reimport_keeps_additions_and_reviewed_entries(tmp_path):
    store = make_store(tmp_path)
    apply_import(store, fixture_raw(), today="2026-10-17")

    # The owner keeps a play addition recorded during a story.
    culture = store.load_cultures()["taelrik"]
    from talemate.cultures.models import PlayAddition

    kept_addition = PlayAddition(
        id="kept-1",
        section="customs",
        text="Ferrymen spit over the rail.",
        status="reviewed",
    )
    culture = culture.model_copy(update={"additions": [kept_addition]})

    # The owner also edits a dictionary entry directly in the store.
    edited_dictionary = [
        entry.model_copy(update={"meaning": "a changed meaning"})
        if entry.word == "dhaer"
        else entry
        for entry in culture.language.dictionary
    ]
    culture = culture.model_copy(
        update={
            "language": culture.language.model_copy(
                update={"dictionary": edited_dictionary}
            )
        }
    )
    store.save_culture(culture)
    assert (
        store.load_cultures()["taelrik"].language.dictionary[0].meaning
        == "a changed meaning"
    )

    # The owner reviews Kethrun with an edited meaning.
    glossary = store.load_glossary()
    glossary = [
        entry.model_copy(
            update={"status": "reviewed", "meaning": "the owner's meaning"}
        )
        if entry.text == "Kethrun"
        else entry
        for entry in glossary
    ]
    store.save_glossary(glossary)

    preview = preview_import(store, fixture_raw())
    assert "Kethrun" in preview.conflicts

    apply_import(store, fixture_raw(), today="2026-10-18")

    reimported = store.load_cultures()["taelrik"]
    assert [a.id for a in reimported.additions] == ["kept-1"]

    kethrun = next(e for e in store.load_glossary() if e.text == "Kethrun")
    assert kethrun.meaning == "the owner's meaning"

    # A core-section change is still applied from the file.
    assert reimported.language.dictionary[0].word == "dhaer"
    assert reimported.language.dictionary[0].meaning == "ford, river crossing"


def test_reimport_never_deletes_talemate_only_entries(tmp_path):
    store = make_store(tmp_path)
    apply_import(store, fixture_raw(), today="2026-10-17")

    glossary = store.load_glossary()
    glossary.append(make_glossary_entry("owner-1", "Owner's Word", language="taelrik"))
    store.save_glossary(glossary)

    apply_import(store, fixture_raw(), today="2026-10-18")

    texts = {e.text for e in store.load_glossary()}
    assert "Owner's Word" in texts


def test_foreign_rendering_applied(tmp_path):
    store = make_store(tmp_path)
    store.save_glossary(
        [make_glossary_entry("g1", "Kasrool", language="elsiri", kind="place")]
    )

    preview = preview_import(store, fixture_raw())
    assert preview.warnings == []

    apply_import(store, fixture_raw(), today="2026-10-17")

    entry = next(e for e in store.load_glossary() if e.text == "Kasrool")
    assert entry.renderings["taelrik"] == "Khaz-Rull"

    # An unknown name produces a warning rather than failing.
    raw = json.loads(fixture_raw())
    raw["foreign_renderings"].append({"name": "Unknown Thing", "rendering": "Whatsit"})
    preview2 = preview_import(store, json.dumps(raw))
    assert any("Unknown Thing" in w for w in preview2.warnings)


def test_places_shares_merged(tmp_path):
    store = make_store(tmp_path)
    dhunmouth = Place(
        id="dhunmouth-1",
        name="Dhunmouth",
        kind="city",
        cultures=[CultureShare(culture_id="elsiri", share=100)],
    )
    store.save_places([dhunmouth])

    preview = preview_import(store, fixture_raw())
    assert preview.places_existing == ["Dhunmouth"]
    assert preview.places_new == ["The Taelrik Reach"]

    apply_import(store, fixture_raw(), today="2026-10-17")

    places = store.load_places()
    by_name = {p.name: p for p in places}

    dhunmouth = by_name["Dhunmouth"]
    shares = {cs.culture_id: cs.share for cs in dhunmouth.cultures}
    assert shares == {"taelrik": 55, "elsiri": 45}

    reach = by_name["The Taelrik Reach"]
    assert reach.kind == "country"


def test_export_round_trip(tmp_path):
    store = make_store(tmp_path)
    apply_import(store, fixture_raw(), today="2026-10-17")

    exported = export_culture(store, "taelrik")

    fresh_store = make_store(tmp_path / "fresh")
    apply_import(fresh_store, exported, today="2026-10-18")

    original = store.load_cultures()["taelrik"]
    reimported = fresh_store.load_cultures()["taelrik"]
    assert original.model_copy(update={"imported_at": ""}) == reimported.model_copy(
        update={"imported_at": ""}
    )

    original_texts = {e.text for e in store.load_glossary()}
    reimported_texts = {e.text for e in fresh_store.load_glossary()}
    assert original_texts == reimported_texts

    original_places = {
        p.name: {cs.culture_id: cs.share for cs in p.cultures}
        for p in store.load_places()
    }
    reimported_places = {
        p.name: {cs.culture_id: cs.share for cs in p.cultures}
        for p in fresh_store.load_places()
    }
    assert original_places == reimported_places


def test_schema_file_up_to_date():
    schema_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "talemate"
        / "cultures"
        / "culture.schema.json"
    )
    committed = json.loads(schema_path.read_text())
    assert committed == CultureFile.model_json_schema()


def test_import_sanitises_culture_id(tmp_path):
    store = make_store(tmp_path)
    raw = json.loads(fixture_raw())
    raw["culture"]["id"] = "../evil"
    sanitised_raw = json.dumps(raw)

    preview = preview_import(store, sanitised_raw)
    assert preview.culture_id == "evil"

    culture = apply_import(store, sanitised_raw, today="2026-10-17")
    assert culture.id == "evil"

    cultures_dir = store.cultures_dir
    saved_path = cultures_dir / "evil.json"
    assert saved_path.exists()
    assert saved_path.resolve().parent == cultures_dir.resolve()


def test_malformed_generator_pattern_rejected(tmp_path):
    store = make_store(tmp_path)
    raw = json.loads(fixture_raw())
    raw["culture"]["language"]["generators"][0]["patterns"] = ["C(V"]
    malformed_raw = json.dumps(raw)

    with pytest.raises(ImportFormatError, match="Given names"):
        preview_import(store, malformed_raw)

    with pytest.raises(ImportFormatError, match="Given names"):
        apply_import(store, malformed_raw, today="2026-10-17")

    # Nothing was written for the rejected file.
    assert store.load_cultures() == {}


def test_new_places_parent_resolved_regardless_of_order(tmp_path):
    store = make_store(tmp_path)
    raw = json.loads(fixture_raw())
    # List the child place before its parent.
    raw["places"] = list(reversed(raw["places"]))
    reordered_raw = json.dumps(raw)

    apply_import(store, reordered_raw, today="2026-10-17")

    places = store.load_places()
    by_name = {p.name: p for p in places}
    reach = by_name["The Taelrik Reach"]
    dhunmouth = by_name["Dhunmouth"]
    assert dhunmouth.parent_id == reach.id


def test_cli_validate_and_sample():
    result = subprocess.run(
        [sys.executable, "-m", "talemate.cultures.cli", "validate", str(FIXTURE_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    result = subprocess.run(
        [sys.executable, "-m", "talemate.cultures.cli", "sample", str(FIXTURE_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "✓" in result.stdout


@pytest.mark.parametrize(
    "field, value",
    [
        ("reject", ["["]),
        ("patterns", ["(" * 5000 + "CV" + ")" * 5000]),
    ],
)
def test_bad_reject_or_deep_nesting_rejected_on_import(tmp_path, field, value):
    store = make_store(tmp_path)
    raw = json.loads(fixture_raw())
    raw["culture"]["language"]["generators"][0][field] = value
    bad_raw = json.dumps(raw)

    with pytest.raises(ImportFormatError):
        preview_import(store, bad_raw)
    with pytest.raises(ImportFormatError):
        apply_import(store, bad_raw, today="2026-10-17")
    assert store.load_cultures() == {}


def test_cli_validate_reports_bad_reject(tmp_path):
    raw = json.loads(fixture_raw())
    raw["culture"]["language"]["generators"][0]["reject"] = ["["]
    bad_path = tmp_path / "bad.culture.json"
    bad_path.write_text(json.dumps(raw), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "talemate.cultures.cli", "validate", str(bad_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "reject" in result.stderr
    assert "Traceback" not in result.stderr


def test_preview_new_culture_replaces_nothing(tmp_path):
    preview = preview_import(make_store(tmp_path), fixture_raw())
    assert preview.replaced_sections == []
    assert preview.share_changes == []
    assert preview.additions_in_file == []


def test_preview_lists_sections_the_import_replaces(tmp_path):
    store = make_store(tmp_path)
    apply_import(store, fixture_raw(), today="2026-10-17")
    assert preview_import(store, fixture_raw()).replaced_sections == []

    culture = store.load_cultures()["taelrik"]
    culture = culture.model_copy(
        update={
            "description": "The owner's own description.",
            "language": culture.language.model_copy(
                update={"dictionary": culture.language.dictionary[:1]}
            ),
        }
    )
    store.save_culture(culture)

    preview = preview_import(store, fixture_raw())
    assert preview.replaced_sections == ["description", "dictionary"]


def test_preview_lists_share_changes(tmp_path):
    store = make_store(tmp_path)
    store.save_places(
        [
            Place(
                id="dhunmouth-1",
                name="Dhunmouth",
                kind="city",
                cultures=[
                    CultureShare(culture_id="taelrik", share=40),
                    CultureShare(culture_id="elsiri", share=60),
                ],
            )
        ]
    )

    preview = preview_import(store, fixture_raw())
    assert preview.share_changes == ["Dhunmouth: Taelrik 40% → 55%"]


def test_preview_lists_additions_already_in_file(tmp_path):
    from talemate.cultures.models import PlayAddition

    store = make_store(tmp_path)
    apply_import(store, fixture_raw(), today="2026-10-17")
    culture = store.load_cultures()["taelrik"]
    culture = culture.model_copy(
        update={
            "additions": [
                PlayAddition(
                    id="a1",
                    section="customs",
                    text="  Oaths are sworn with  WET hands. ",
                ),
                PlayAddition(id="a2", section="food", text="smoked eel"),
                PlayAddition(id="a3", section="holidays", text="Lantern Night"),
                PlayAddition(id="a4", section="customs", text="Spit for luck."),
                # In the file, but under a different section.
                PlayAddition(id="a5", section="food", text="Lantern Night"),
            ]
        }
    )
    store.save_culture(culture)

    preview = preview_import(store, fixture_raw())
    assert preview.additions_in_file == [
        "  Oaths are sworn with  WET hands. ",
        "smoked eel",
        "Lantern Night",
    ]

    # Apply never drops an addition by itself.
    apply_import(store, fixture_raw(), today="2026-10-18")
    kept = store.load_cultures()["taelrik"].additions
    assert [a.id for a in kept] == ["a1", "a2", "a3", "a4", "a5"]


def test_preview_name_clash_is_case_insensitive(tmp_path):
    store = make_store(tmp_path)
    store.save_culture(make_culture("river-folk", "TAELRIK"))
    assert preview_import(store, fixture_raw()).name_clash == "river-folk"


def test_duplicate_generator_ids_rejected_on_import(tmp_path):
    store = make_store(tmp_path)
    raw = json.loads(fixture_raw())
    generators = raw["culture"]["language"]["generators"]
    generators[1]["id"] = generators[0]["id"]

    with pytest.raises(ImportFormatError, match="duplicate"):
        preview_import(store, json.dumps(raw))
