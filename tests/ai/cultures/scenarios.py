"""The AI world for the cultures AI tests and the overnight evaluation.

Two cultures (`tests/ai/data/`): Taelrik river-folk and Elsiri coast-folk,
with clearly different name sounds. Places, with fixed ids:

    reach (country) taelrik 100
    ├── veldhaer (town)                    inherits
    ├── dhunmouth (city)                   taelrik 60 / elsiri 40
    └── birch (region)                     elsiri 90 / taelrik 10
        └── ilsara (village)               inherits

Three scenarios put a scene in a Taelrik town, an Elsiri pocket and a
mixed city. `seed_scenario` writes one of them into a running isolated
app's root (see `tests/e2e/seed.py`).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from e2e.seed import SeededWorld, place_culture, place_places, seed_world

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TAELRIK_FILE = DATA_DIR / "taelrik.culture.json"
ELSIRI_FILE = DATA_DIR / "elsiri.culture.json"
CULTURE_FILES = (TAELRIK_FILE, ELSIRI_FILE)


def _shares(**shares: int) -> list[dict]:
    return [
        {"culture_id": culture_id, "share": share}
        for culture_id, share in shares.items()
    ]


PLACES: list[dict] = [
    {
        "id": "reach",
        "name": "The Taelrik Reach",
        "kind": "country",
        "parent_id": None,
        "cultures": _shares(taelrik=100),
    },
    {
        "id": "veldhaer",
        "name": "Veldhaer",
        "kind": "town",
        "parent_id": "reach",
        "cultures": [],
    },
    {
        "id": "dhunmouth",
        "name": "Dhunmouth",
        "kind": "city",
        "parent_id": "reach",
        "cultures": _shares(taelrik=60, elsiri=40),
    },
    {
        "id": "birch",
        "name": "Birch Coast",
        "kind": "region",
        "parent_id": "reach",
        "cultures": _shares(elsiri=90, taelrik=10),
    },
    {
        "id": "ilsara",
        "name": "Ilsara",
        "kind": "village",
        "parent_id": "birch",
        "cultures": [],
    },
]


@dataclasses.dataclass
class Scenario:
    key: str
    place_id: str
    intro: str
    location: str
    # culture id -> share of the scene's place, as the cultures mix resolves it
    expected: dict[str, int]


SCENARIOS: dict[str, Scenario] = {
    scenario.key: scenario
    for scenario in (
        Scenario(
            key="taelrik_town",
            place_id="veldhaer",
            intro=(
                "Rain drums on the shutters of the Quillister inn in Veldhaer, "
                "a ferry town on the grey river. Bargemen crowd the long "
                "tables, steam rising from their oiled coats, and the "
                "innkeeper's boy runs between them with jugs of reed beer."
            ),
            location="The Quillister inn in Veldhaer",
            expected={"taelrik": 100},
        ),
        Scenario(
            key="elsiri_pocket",
            place_id="ilsara",
            intro=(
                "Morning fog lies over the fish market in Ilsara, a small "
                "village on the Birch Coast. Stalls of salt fish and kelp "
                "line the shingle, gulls quarrel over scraps, and somewhere "
                "behind the net-racks someone is singing."
            ),
            location="The fish market in Ilsara, on the Birch Coast",
            expected={"elsiri": 90, "taelrik": 10},
        ),
        Scenario(
            key="mixed_city",
            place_id="dhunmouth",
            intro=(
                "The harbour of Dhunmouth is loud with gulls and winches. "
                "River barges unload beside coastal boats, dockhands shout "
                "over one another in two languages, and the smell of tar "
                "and smoked eel hangs over the quays."
            ),
            location="The harbour of Dhunmouth",
            expected={"taelrik": 60, "elsiri": 40},
        ),
    )
}

# (hint, content) pairs for creating NPCs, alternating female and male.
# None of them names a culture: the culture has to come from the place.
NPC_ROLES: list[tuple[str, str]] = [
    ("the fishwife", "A loud woman selling eels from a barrow."),
    ("the ferryman", "A gruff old man who works the river ferry."),
    ("the innkeeper", "A stout woman who runs the taproom with a firm hand."),
    ("the net-mender", "A quiet young man who mends nets by the water."),
    ("the healer", "An old woman who sells herbs and sets broken bones."),
    ("the toll-keeper", "A thin, suspicious man who collects the bridge toll."),
    ("the singer", "A young woman who sings for coins at the market."),
    ("the smith", "A broad man with burn-scarred forearms who shoes horses."),
    ("the widow", "A sharp-tongued widow who rents out rooms above her shop."),
    ("the boy", "A barefoot boy who runs errands for anyone who pays."),
]

TRAIT_CHARACTER = {
    "name": "Hadrik",
    "description": (
        "A broad-shouldered dockhand. He curses in Taelrik whenever "
        "something goes wrong."
    ),
    "culture": {"culture_id": "taelrik", "set_by": "owner"},
}

KNOWN_NAMES_MESSAGE = (
    "Old Brannoch waved from the deck of the Grey Gull, a battered river barge."
)

ADDITION_MESSAGE = (
    "As every Taelrik ferryman does, Brannoch spat over the rail before landing."
)


def seed_scenario(
    root: Path,
    project: str,
    scenario: Scenario,
    *,
    with_trait_character: bool = False,
    messages: list[str] = (),
    location: str | None = None,
) -> SeededWorld:
    """Seed ``scenario`` as project ``project`` in a running app's ``root``.

    Creates the scene (intro, location, ``messages`` as narrator messages,
    and Hadrik when ``with_trait_character``), imports both AI cultures and
    saves `PLACES` (replacing the places the imports created). ``location``
    overrides the scenario's own location.
    """
    world = seed_world(
        root,
        project=project,
        intro=scenario.intro,
        location=location if location is not None else scenario.location,
        messages=[{"text": text} for text in messages],
        characters=[TRAIT_CHARACTER] if with_trait_character else [],
    )
    for culture_file in CULTURE_FILES:
        place_culture(world, culture_file)
    place_places(world, PLACES)
    return world
