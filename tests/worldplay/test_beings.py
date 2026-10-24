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
from talemate.world.entries import acts_in_world, existence
from talemate.world.filing import filings_of
from talemate.world.spheres import people, ties_of
from talemate.world.kinds import ENTRY_DRAWER_TYPES
from talemate.world.store import Source
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.context import world_context_block
from talemate.worldplay.create import (
    CREATE_KINDS,
    NAME_KINDS,
    CreatePreview,
    PreviewFact,
    PreviewException,
    PreviewFiling,
    accept_preview,
    name_guess,
)
from talemate.worldplay.setup import SceneSetup, SetupRef, plan_scene, start_scene

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
            "being",
            fields={
                "name": "The Eternal Light",
                "existence": "believed",
                "aka": [{"name": "the Light", "tag": "common", "everyday": True}],
            },
        )
        rev.add_fact(light, "worship", "Prayed to at dawn.")
        spirit = rev.create_thing(
            "being",
            fields={
                "name": "The River Spirit",
                "existence": "real",
                "ties": [_tie(church, "protector")],
                "filings": [{"target": church, "role": "protector"}],
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
    assert kind.categories == ["nature", "deeds", "worship", "ties", "general"]
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

    # filed as a doctrine, a custom or a rank, never as a place
    assert ENTRY_DRAWER_TYPES["being"] == ("beliefs", "practices", "structure")
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


async def test_unreal_being_matched_by_other_name(world, beings):
    """A believed being the model names by one of its other names ("the
    Light"), or without its article, is still never cast nor invented."""

    setup = await plan_scene(
        world,
        "Maren prays",
        {},
        None,
        START,
        None,
        reply={
            "player": "Maren",
            "characters": [{"name": "Light"}, {"name": "Eternal Light"}],
            "intro": "Dawn.",
        },
    )
    assert setup.characters == []
    assert setup.invented == []


async def test_start_scene_drops_what_cant_be_cast(world, beings):
    """A setup edited by the client may name a believed being: it's left
    out of the scene's characters. Played, it's refused before anything is
    written."""

    setup = SceneSetup(
        player=SetupRef(thing_id=beings["maren"]),
        characters=[
            SetupRef(thing_id=beings["light"]),
            SetupRef(thing_id=beings["wolf"]),
            SetupRef(thing_id=beings["spirit"]),
        ],
        start=START,
        intro="Dawn.",
    )
    scene_id = await start_scene(world, setup, None)
    record = world.scenes().get(scene_id)
    assert [e["thing_id"] for e in record.state["characters"]] == [
        beings["maren"],
        beings["spirit"],
    ]

    scenes = len(world.scenes().list())
    with pytest.raises(ValueError):
        await start_scene(
            world,
            setup.model_copy(update={"player": SetupRef(thing_id=beings["light"])}),
            None,
        )
    assert len(world.scenes().list()) == scenes


def _being_preview(church, existence):
    fields = {"existence": existence} if existence else {}
    return CreatePreview(
        kind="being",
        prompt="a river spirit",
        fields=fields,
        name="The Ford Spirit",
        facts=[PreviewFact(category="nature", text="A spirit of the ford.")],
        prose={"description": "A spirit."},
        filings=[
            PreviewFiling(
                target_id=church,
                target_name="The Church",
                role="patron",
                exceptions=[
                    PreviewException(text="It keeps no fast.", item="The Church")
                ],
                ticked=True,
            )
        ],
    )


def test_only_a_real_being_gets_exceptions(world, beings):
    """Any entry can be filed (Filing, Task 4), but only one that acts in
    the world -- a real being, as a character -- gets its row's "but..."
    exceptions; a believed or undecided being's are left out."""

    for setting in ("believed", None):
        thing_id = accept_preview(world, _being_preview(beings["church"], setting))
        view = world.view()
        (filing,) = filings_of(view, thing_id)
        assert (filing.target, filing.role, filing.exceptions) == (
            beings["church"],
            "patron",
            [],
        )
        assert not [f for f in view.thing(thing_id).facts if f.category == "ties"]

    thing_id = accept_preview(world, _being_preview(beings["church"], "real"))
    view = world.view()
    (filing,) = filings_of(view, thing_id)
    (exception,) = [f for f in view.thing(thing_id).facts if f.category == "ties"]
    assert filing.exceptions == [exception.fact_id]
    assert "ties" not in view.thing(thing_id).fields
