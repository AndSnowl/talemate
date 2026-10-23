"""The `being` kind: gods, spirits and legendary creatures, with an
existence setting. Only a `real` being acts in the world like a
character: it can be cast in a scene and hold ties (curation spec, goal
8)."""

import pytest

from talemate.world.dates import WorldDate
from talemate.world.kinds import (
    DEFAULT_EXISTENCE,
    EXISTENCE_VALUES,
    get_kind,
    validate_field,
)
from talemate.world.spheres import acts_in_world, existence, people, ties_of
from talemate.world.store import Source
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.context import world_context_block
from talemate.worldplay.create import CREATE_KINDS, NAME_KINDS, name_guess
from talemate.worldplay.setup import SetupRef, plan_scene

START = WorldDate.of(1020)


def _tie(sphere, role):
    return {"sphere": sphere, "role": role, "since": None, "until": None}


@pytest.fixture
def beings(world):
    """The Church (a religion), Maren (a character), and three beings: the
    Eternal Light (believed), the River Spirit (real, tied to the Church),
    and the Grey Wolf (no existence set: undecided)."""

    with world.revision(Source.manual(note="beings")) as rev:
        church = rev.create_thing(
            "sphere", fields={"name": "The Church", "template": "religion"}
        )
        maren = rev.create_thing("character", fields={"name": "Maren"})
        light = rev.create_thing(
            "being", fields={"name": "The Eternal Light", "existence": "believed"}
        )
        rev.add_fact(light, "worship", "Prayed to at dawn.")
        spirit = rev.create_thing(
            "being",
            fields={
                "name": "The River Spirit",
                "existence": "real",
                "ties": [_tie(church, "protector")],
            },
        )
        rev.add_fact(spirit, "nature", "A shape of moving water.")
        wolf = rev.create_thing("being", fields={"name": "The Grey Wolf"})
    return {
        "church": church,
        "maren": maren,
        "light": light,
        "spirit": spirit,
        "wolf": wolf,
    }


def test_being_existence_values(world, beings):
    """`existence` is one of real, believed or undecided; unset reads as
    undecided. The being kind can be created and named; a god, a spirit
    or a deity guessed in a reply is a being."""

    kind = get_kind("being")
    assert kind.categories == ["nature", "deeds", "worship", "general"]
    assert [f.name for f in kind.fields][:3] == ["name", "existence", "born"]
    assert EXISTENCE_VALUES == ("real", "believed", "undecided")
    assert DEFAULT_EXISTENCE == "undecided"
    for value in EXISTENCE_VALUES:
        validate_field(kind, "existence", value)
    with pytest.raises(ValueError):
        validate_field(kind, "existence", "maybe")
    with pytest.raises(ValueError):
        with world.revision(Source.manual()) as rev:
            rev.set_field(beings["wolf"], "existence", "mythical", None)

    view = world.view()
    assert existence(view.thing(beings["wolf"])) == "undecided"
    assert existence(view.thing(beings["light"])) == "believed"
    assert existence(view.thing(beings["spirit"])) == "real"

    assert "being" in CREATE_KINDS
    assert "being" in NAME_KINDS
    for guess in ("god", "spirit", "deity", "being", "God"):
        assert name_guess(guess, None) == ("being", None)


def test_only_real_beings_act_and_hold_ties(world, beings):
    """A real being acts in the world: its ties count (the Church's
    people). Once it's believed, its tie is kept but hidden, as a tie to a
    deleted sphere is, and comes back when it's real again."""

    view = world.view()
    assert acts_in_world(view.thing(beings["maren"]))
    assert acts_in_world(view.thing(beings["spirit"]))
    assert not acts_in_world(view.thing(beings["light"]))
    assert not acts_in_world(view.thing(beings["wolf"]))
    assert not acts_in_world(view.thing(beings["church"]))
    assert [t.character_id for t in people(view, beings["church"])] == [
        beings["spirit"]
    ]
    assert [t.role for t in ties_of(view, beings["spirit"])] == ["protector"]

    with world.revision(Source.manual()) as rev:
        rev.set_field(beings["spirit"], "existence", "believed", None)
    view = world.view()
    assert people(view, beings["church"]) == []
    assert ties_of(view, beings["spirit"]) == []
    # kept, not dropped
    assert view.thing(beings["spirit"]).fields["ties"] == [
        _tie(beings["church"], "protector")
    ]

    with world.revision(Source.manual()) as rev:
        rev.set_field(beings["spirit"], "existence", "real", None)
    assert [t.role for t in ties_of(world.view(), beings["spirit"])] == ["protector"]


async def test_believed_being_never_cast(world, beings):
    """A believed or undecided being is never cast: not as a character the
    model names (nor invented in its place), not as a pick, never as the
    player. Nor is it pulled in as lore: its facts reach a scene only
    through what refers to it."""

    setup = await plan_scene(
        world,
        "Maren prays to the Eternal Light by the Grey Wolf's den",
        {"the Eternal Light": beings["light"], "the Grey Wolf": beings["wolf"]},
        None,
        START,
        None,
        reply={
            "player": "Maren",
            "characters": [
                {"name": "The Eternal Light"},
                {"name": "The Grey Wolf", "facts": ["A wolf."]},
            ],
            "intro": "Dawn.",
        },
    )
    assert setup.player == SetupRef(thing_id=beings["maren"])
    assert setup.characters == []
    assert setup.invented == []
    assert setup.pulled_in == []

    with pytest.raises(ValueError):
        await plan_scene(
            world,
            "The Light speaks",
            {},
            beings["light"],
            START,
            None,
            reply={"player": "Maren", "characters": [], "intro": "Dawn."},
        )

    scenes = world.scenes()
    scene_id = scenes.create("Old", START)
    scenes.update(scene_id, state={"pulled_in": [beings["light"]]})
    block = world_context_block(world, scenes.get(scene_id), START)
    assert "Prayed to at dawn." not in block


async def test_real_being_castable(world, beings):
    """A real being joins the characters: named by the model, picked by the
    owner, or played. It's built as a character, with its ties; it has no
    heritage, voice or color of its own, so it takes a character's
    defaults."""

    setup = await plan_scene(
        world,
        "Maren meets the River Spirit",
        {"the River Spirit": beings["spirit"]},
        None,
        START,
        None,
        reply={
            "player": "Maren",
            "characters": [{"name": "The River Spirit"}],
            "intro": "The river rises.",
        },
    )
    assert setup.characters == [SetupRef(thing_id=beings["spirit"])]
    assert setup.invented == []
    assert beings["spirit"] not in setup.pulled_in

    picked = await plan_scene(
        world,
        "Maren meets the River Spirit",
        {"the River Spirit": beings["spirit"]},
        None,
        START,
        None,
        reply={"player": "Maren", "characters": [], "intro": "The river rises."},
    )
    assert picked.characters == [SetupRef(thing_id=beings["spirit"])]

    played = await plan_scene(
        world,
        "The spirit wakes",
        {},
        beings["spirit"],
        START,
        None,
        reply={"player": "Maren", "characters": [], "intro": "The river rises."},
    )
    assert played.player == SetupRef(thing_id=beings["spirit"])

    character = character_from_world(world, beings["spirit"], START, is_player=False)
    assert character.name == "The River Spirit"
    assert character.base_attributes["ties"] == "Protector of the Church"
