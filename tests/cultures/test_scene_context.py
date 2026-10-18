from talemate.character import Character
from talemate.cultures.models import CharacterCulture
from talemate.cultures.scene_context import match_place, resolve_scene_cultures

from ._fixtures import build_cultures, build_places


def test_match_place_word_boundary_and_depth():
    places = build_places()

    place = match_place(places, "The tavern in Veldhaer", [])
    assert place.id == "veldhaer"

    place = match_place(places, "Ilsara, on the Birch Coast", [])
    assert place.id == "ilsara"

    place = match_place(places, "Veldhaerton market", [])
    assert place is None

    place = match_place(places, "Taelrik Reach border", [])
    assert place.id == "reach"


def test_match_place_falls_back_to_snapshot_places():
    places = build_places()

    place = match_place(places, None, ["dhunmouth"])
    assert place.id == "dhunmouth"


def test_resolve_orders_mix_then_characters():
    places = build_places()
    cultures = build_cultures()
    character = Character(name="Thrava", culture=CharacterCulture(culture_id="ghun"))

    sc = resolve_scene_cultures(
        cultures,
        places,
        location="Market day in Dhunmouth",
        snapshot_places=[],
        characters=[character],
    )

    assert sc.place.id == "dhunmouth"
    assert [c.id for c in sc.cultures] == ["taelrik", "elsiri", "vaskari", "ghun"]


def test_resolve_uses_fallback_place():
    places = build_places()
    cultures = build_cultures()

    sc = resolve_scene_cultures(
        cultures,
        places,
        location="Somewhere unmapped",
        snapshot_places=[],
        characters=[],
        fallback_place_id="ilsara",
    )

    assert sc.place.id == "ilsara"
    assert sc.mix_source.id == "birch"
