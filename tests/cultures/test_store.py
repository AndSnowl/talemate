import json

import pytest

from talemate.cultures.models import (
    Culture,
    CultureShare,
    GlossaryEntry,
    GlossaryOrigin,
    Language,
    Place,
    PlayAddition,
)
from talemate.cultures.store import (
    WorldStore,
    atomic_write_json,
    world_dir_for,
    world_dir_for_scene,
)
from talemate.tale_mate import Scene


def make_culture(culture_id: str = "taelrik", **addition_kwargs) -> Culture:
    additions = []
    if addition_kwargs:
        additions.append(PlayAddition(id="a1", **addition_kwargs))
    return Culture(
        id=culture_id,
        name="Taelrik",
        language=Language(name="Taelrik", level="naming"),
        additions=additions,
    )


def make_glossary_entry(
    entry_id: str, language: str | None, status: str = "unreviewed"
) -> GlossaryEntry:
    return GlossaryEntry(
        id=entry_id,
        text="Something",
        language=language,
        kind="word",
        origin=GlossaryOrigin(by="owner"),
        status=status,
    )


def test_world_dir_for(tmp_path):
    shared_context_path = tmp_path / "shared-context" / "grey-river.json"
    assert world_dir_for(shared_context_path) == (
        tmp_path / "shared-context" / "grey-river.world"
    )


def test_world_dir_for_scene_none_without_shared_context():
    scene = Scene()
    assert scene.shared_context is None
    assert world_dir_for_scene(scene) is None


def test_round_trip(tmp_path):
    store = WorldStore(tmp_path)

    culture = make_culture()
    places = [Place(id="p1", name="Grey River", kind="town")]
    glossary = [make_glossary_entry("g1", language="taelrik")]

    store.save_culture(culture)
    store.save_places(places)
    store.save_glossary(glossary)

    assert (tmp_path / "cultures" / "taelrik.json").exists()
    assert (tmp_path / "places.json").exists()
    assert (tmp_path / "glossary.json").exists()

    loaded_cultures = store.load_cultures()
    assert loaded_cultures == {"taelrik": culture}
    assert store.load_places() == places
    assert store.load_glossary() == glossary


def test_missing_files_load_empty(tmp_path):
    store = WorldStore(tmp_path)
    assert store.load_cultures() == {}
    assert store.load_places() == []
    assert store.load_glossary() == []


def test_bad_culture_file_skipped(tmp_path):
    store = WorldStore(tmp_path)
    good = make_culture(culture_id="good")
    store.save_culture(good)

    cultures_dir = tmp_path / "cultures"
    cultures_dir.mkdir(parents=True, exist_ok=True)
    (cultures_dir / "bad.json").write_text("{not json")

    loaded = store.load_cultures()
    assert loaded == {"good": good}


def test_atomic_write_leaves_old_file_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"value": 1})
    assert json.loads(path.read_text()) == {"value": 1}

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(json, "dump", boom)

    with pytest.raises(RuntimeError):
        atomic_write_json(path, {"value": 2})

    assert json.loads(path.read_text()) == {"value": 1}
    leftover_tmp_files = list(tmp_path.glob("*.tmp"))
    assert leftover_tmp_files == []


def test_snapshot_counts(tmp_path):
    store = WorldStore(tmp_path)

    culture = make_culture(section="customs", text="A custom")
    store.save_culture(culture)

    places = [
        Place(id="p1", name="Grey River", kind="town", unsure=True),
        Place(id="p2", name="Stonehall", kind="city"),
    ]
    store.save_places(places)

    glossary = [
        make_glossary_entry("g1", language="taelrik", status="unreviewed"),
        make_glossary_entry("g2", language="taelrik", status="unreviewed"),
        make_glossary_entry("g3", language="taelrik", status="reviewed"),
        make_glossary_entry("g4", language=None, status="unreviewed"),
    ]
    store.save_glossary(glossary)

    snapshot = store.snapshot()

    assert snapshot["counts"]["unreviewed_total"] == 5
    assert snapshot["counts"]["unreviewed_by_culture"] == {"taelrik": 2}
    assert snapshot["counts"]["unreviewed_unassigned"] == 1
    assert snapshot["counts"]["unsure_places"] == 1
    assert snapshot["counts"]["unreviewed_additions_by_culture"] == {"taelrik": 1}

    assert snapshot["cultures"][0]["id"] == "taelrik"
    assert snapshot["places"][0]["id"] == "p1"
    assert snapshot["glossary"][0]["id"] == "g1"


def test_snapshot_includes_effective_mix(tmp_path):
    store = WorldStore(tmp_path)

    store.save_culture(
        Culture(
            id="taelrik",
            name="Taelrik",
            language=Language(name="Taelrik", level="naming"),
        )
    )
    store.save_culture(
        Culture(
            id="elsiri",
            name="Elsiri",
            language=Language(name="Elsiri", level="naming"),
        )
    )

    places = [
        Place(
            id="reach",
            name="The Taelrik Reach",
            kind="country",
            cultures=[CultureShare(culture_id="taelrik", share=100)],
        ),
        Place(
            id="birch",
            name="Birch Coast",
            kind="region",
            parent_id="reach",
            cultures=[
                CultureShare(culture_id="elsiri", share=90),
                CultureShare(culture_id="taelrik", share=10),
            ],
        ),
        Place(id="ilsara", name="Ilsara", kind="village", parent_id="birch"),
    ]
    store.save_places(places)

    snapshot = store.snapshot()

    ilsara = next(p for p in snapshot["places"] if p["id"] == "ilsara")
    assert ilsara["effective"]["source_id"] == "birch"
    assert ilsara["effective"]["country_id"] == "reach"
    assert {cs["culture_id"] for cs in ilsara["effective"]["mix"]} == {
        "elsiri",
        "taelrik",
    }
    assert "Elsiri" in ilsara["effective"]["description"]


BAD_GLOSSARY_ENTRY = {"id": "bad-g", "text": 5, "kind": "nonsense"}
BAD_PLACE_ENTRY = {"id": "bad-p", "name": "Nowhere", "kind": "continent"}


def test_corrupt_glossary_entry_is_skipped_and_kept_on_save(tmp_path):
    store = WorldStore(tmp_path)
    store.save_glossary([make_glossary_entry("g1", language=None)])
    data = json.loads(store.glossary_path.read_text(encoding="utf-8"))
    data["entries"].append(BAD_GLOSSARY_ENTRY)
    store.glossary_path.write_text(json.dumps(data), encoding="utf-8")

    entries = store.load_glossary()
    assert [e.id for e in entries] == ["g1"]
    assert [g["id"] for g in store.snapshot()["glossary"]] == ["g1"]

    store.save_glossary(entries + [make_glossary_entry("g2", language=None)])

    saved = json.loads(store.glossary_path.read_text(encoding="utf-8"))["entries"]
    assert [e["id"] for e in saved] == ["g1", "g2", "bad-g"]
    assert saved[-1] == BAD_GLOSSARY_ENTRY


def test_corrupt_place_entry_is_skipped_and_kept_on_save(tmp_path):
    store = WorldStore(tmp_path)
    store.save_places([Place(id="p1", name="Veldhaer", kind="town")])
    data = json.loads(store.places_path.read_text(encoding="utf-8"))
    data["places"].append(BAD_PLACE_ENTRY)
    store.places_path.write_text(json.dumps(data), encoding="utf-8")

    places = store.load_places()
    assert [p.id for p in places] == ["p1"]
    assert [p["id"] for p in store.snapshot()["places"]] == ["p1"]

    store.save_places(places)

    saved = json.loads(store.places_path.read_text(encoding="utf-8"))["places"]
    assert saved[-1] == BAD_PLACE_ENTRY
    assert [p["id"] for p in saved] == ["p1", "bad-p"]


def test_unreadable_world_file_raises_readable_error(tmp_path):
    store = WorldStore(tmp_path)
    store.places_path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="places.json"):
        store.load_places()
    # And it is never overwritten while it can't be read.
    with pytest.raises(ValueError, match="places.json"):
        store.save_places([])
    assert store.places_path.read_text(encoding="utf-8") == "{"
