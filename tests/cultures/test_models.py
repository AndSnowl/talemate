import pytest
from pydantic import ValidationError

from talemate.cultures import Culture, Language, Place, slugify


def test_slugify_strips_diacritics():
    assert slugify("Ghûn") == "ghun"
    assert slugify("Hollow Choir") == "hollow-choir"


def test_culture_file_ignores_unknown_and_defaults_missing():
    culture = Culture.model_validate(
        {
            "id": "t",
            "name": "Taelrik",
            "language": {"name": "Taelrik", "level": "full"},
            "law": "x",
        }
    )
    assert culture.customs == []
    assert culture.language.generators == []
    assert not hasattr(culture, "law")


def test_level_rejects_unknown_value():
    with pytest.raises(ValidationError):
        Language(name="x", level="partial")


def test_place_kind_values():
    kinds = [
        "country",
        "region",
        "city",
        "town",
        "village",
        "building",
        "poi",
        "terrain",
    ]
    for kind in kinds:
        Place(id="p", name="Place", kind=kind)

    with pytest.raises(ValidationError):
        Place(id="p", name="Place", kind="castle")
