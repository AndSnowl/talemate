"""`thing_references`: everything in a world that uses one thing, checked
before that thing is deleted."""

from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.worldplay.references import thing_references


def _seed(world):
    with world.revision(Source.manual(note="seed")) as rev:
        vasha = rev.create_thing("character", {"name": "Vasha"})
        oskar = rev.create_thing("character", {"name": "Oskar"})
        harbour = rev.create_thing("place", {"name": "The Harbour"})
        hollow = rev.create_thing("lore", {"name": "The Hollow Crown"})
    return vasha, oskar, harbour, hollow


def test_an_unused_thing_has_no_references(world):
    vasha, *_ = _seed(world)

    assert thing_references(world, vasha) == {"facts": [], "fields": [], "scenes": []}


def test_facts_of_other_things_that_reference_it(world):
    vasha, oskar, harbour, _ = _seed(world)
    with world.revision(Source.manual()) as rev:
        rev.add_fact(oskar, "relationship", f"Owes {ref(vasha)} a life-debt.")
        # ended facts still name it
        rev.add_fact(
            harbour,
            "history",
            f"Ruled by {ref(vasha)}.",
            valid_from=WorldDate.of(300),
            valid_until=WorldDate.of(310),
        )
        # its own facts don't count
        rev.add_fact(vasha, "personality", f"{ref(vasha)} is proud.")

    found = thing_references(world, vasha)["facts"]

    assert sorted(found, key=lambda entry: entry["thing_name"]) == [
        {"thing_id": oskar, "thing_name": "Oskar", "text": "Owes Vasha a life-debt."},
        {"thing_id": harbour, "thing_name": "The Harbour", "text": "Ruled by Vasha."},
    ]


def test_fields_that_point_at_it(world):
    vasha, oskar, harbour, _ = _seed(world)
    with world.revision(Source.manual()) as rev:
        quay = rev.create_thing("place", {"name": "The Quay", "parent": harbour})
        old_town = rev.create_thing(
            "place",
            {"name": "Old Town", "cultures": [{"thing_id": harbour, "share": 1}]},
        )
        lantern = rev.create_thing("item", {"name": "Lantern", "owner": harbour})
    # a field that pointed at it once, then moved on, still counts
    with world.revision(Source.manual()) as rev:
        rev.set_field(lantern, "owner", oskar, WorldDate.of(320))

    found = thing_references(world, harbour)["fields"]

    assert sorted(found, key=lambda entry: entry["thing_name"]) == [
        {"thing_id": lantern, "thing_name": "Lantern", "field": "owner"},
        {"thing_id": old_town, "thing_name": "Old Town", "field": "cultures"},
        {"thing_id": quay, "thing_name": "The Quay", "field": "parent"},
    ]
    assert thing_references(world, vasha)["fields"] == []


def test_scenes_that_use_it(world):
    vasha, oskar, harbour, hollow = _seed(world)
    scenes = world.scenes()
    played = scenes.create("The Ferryman", WorldDate.of(312), player_thing_id=vasha)
    cast = scenes.create(
        "At the Quay",
        WorldDate.of(313),
        state={
            "characters": [{"thing_id": vasha}, {"thing_id": oskar}],
            "place_thing_id": harbour,
            "pulled_in": [hollow],
        },
    )

    found = thing_references(world, vasha)["scenes"]
    assert sorted(found, key=lambda entry: entry["name"]) == [
        {"scene_id": cast, "name": "At the Quay", "role": "character"},
        {"scene_id": played, "name": "The Ferryman", "role": "player"},
    ]
    assert thing_references(world, harbour)["scenes"] == [
        {"scene_id": cast, "name": "At the Quay", "role": "place"},
    ]
    assert thing_references(world, hollow)["scenes"] == [
        {"scene_id": cast, "name": "At the Quay", "role": "lore"},
    ]


def test_references_count_parents_and_heritage(world):
    with world.revision(Source.manual(note="seed")) as rev:
        human = rev.create_thing("species", {"name": "Human"})
        orc = rev.create_thing("species", {"name": "Orc"})
        lowlander = rev.create_thing("race", {"name": "Lowlander", "species": human})
        half_orc = rev.create_thing(
            "mix", {"name": "Half-orc", "parents": [lowlander, orc]}
        )
        brenna = rev.create_thing("character", {"name": "Brenna", "heritage": half_orc})

    assert thing_references(world, orc)["fields"] == [
        {"thing_id": half_orc, "thing_name": "Half-orc", "field": "parents"},
    ]
    assert thing_references(world, lowlander)["fields"] == [
        {"thing_id": half_orc, "thing_name": "Half-orc", "field": "parents"},
    ]
    assert thing_references(world, half_orc)["fields"] == [
        {"thing_id": brenna, "thing_name": "Brenna", "field": "heritage"},
    ]
