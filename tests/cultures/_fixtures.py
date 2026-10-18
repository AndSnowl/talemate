"""Shared test fixtures for the cultures test suite.

The place/culture tree built here is used by `test_places.py`,
`test_scene_context.py`, and anything else that needs a small, realistic
mix of nested places and cultures to exercise against:

    reach (country) taelrik 100
    ├── veldhaer (town)
    ├── dhunmouth (city) taelrik 55 / elsiri 30 / vaskari 15
    └── birch (region) elsiri 90 / taelrik 10
        └── ilsara (village)
"""

from talemate.cultures.models import Culture, CultureShare, Language, Place


def place(id, name, kind, parent_id=None, cultures=None) -> Place:
    return Place(
        id=id,
        name=name,
        kind=kind,
        parent_id=parent_id,
        cultures=cultures or [],
    )


def build_places() -> list[Place]:
    return [
        place(
            "reach",
            "The Taelrik Reach",
            "country",
            cultures=[CultureShare(culture_id="taelrik", share=100)],
        ),
        place("veldhaer", "Veldhaer", "town", parent_id="reach"),
        place("quillister", "Quillister House", "building", parent_id="veldhaer"),
        place(
            "dhunmouth",
            "Dhunmouth",
            "city",
            parent_id="reach",
            cultures=[
                CultureShare(culture_id="taelrik", share=55),
                CultureShare(culture_id="elsiri", share=30),
                CultureShare(culture_id="vaskari", share=15),
            ],
        ),
        place(
            "birch",
            "Birch Coast",
            "region",
            parent_id="reach",
            cultures=[
                CultureShare(culture_id="elsiri", share=90),
                CultureShare(culture_id="taelrik", share=10),
            ],
        ),
        place("ilsara", "Ilsara", "village", parent_id="birch"),
        place(
            "khaz",
            "Khaz-Rull",
            "terrain",
            cultures=[CultureShare(culture_id="ghun", share=100)],
        ),
    ]


def culture(id, name, language_name) -> Culture:
    return Culture(
        id=id,
        name=name,
        language=Language(name=language_name, level="naming"),
    )


def build_cultures() -> dict[str, Culture]:
    by_id = [
        culture("taelrik", "Taelrik", "Taelrik"),
        culture("elsiri", "Elsiri", "Elsiri"),
        culture("vaskari", "Vaskari", "Vaskari"),
        culture("ghun", "Hollow Choir", "Ghûn"),
    ]
    return {c.id: c for c in by_id}
