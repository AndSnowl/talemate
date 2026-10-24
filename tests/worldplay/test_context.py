"""Tests for `talemate.worldplay.context`: the "World" instruction built
from a scene's world record, its injection into narrator/conversation
prompts, and keeping active characters fresh across time passage."""

import pytest

import talemate.emit.async_signals as async_signals
import talemate.instance as instance
from talemate.agents.conversation import ConversationAgentEmission
from talemate.character import Character
from talemate.tale_mate import Actor
from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay.characters import character_from_world
from talemate.worldplay.context import WorldSceneContext, connect, world_context_block

from conftest import MockScene, bootstrap_scene


def test_world_context_block_has_goal_place_lore(world):
    with world.revision(Source.manual(note="setup")) as rev:
        place_id = rev.create_thing("place", fields={"name": "Veldhaer"})
        rev.add_fact(place_id, "description", "A harbor town built on stilts.")
        lore_id = rev.create_thing("lore", fields={"name": "The River Treaty"})
        rev.add_fact(lore_id, "general", "Signed after the flood of 301.")

    scenes = world.scenes()
    scene_id = scenes.create(
        "Test Scene", WorldDate.of(310), goal="Find the missing envoy"
    )
    scenes.update(scene_id, state={"place_thing_id": place_id, "pulled_in": [lore_id]})
    record = scenes.get(scene_id)

    block = world_context_block(world, record, WorldDate.of(310))

    assert "Find the missing envoy" in block
    assert "Veldhaer" in block
    assert "A harbor town built on stilts." in block
    assert "The River Treaty" in block
    assert "Signed after the flood of 301." in block


def test_world_context_block_renders_linked_facts(world):
    """Facts made from a prompt are linked; the World block reads them as
    written, never as raw references."""

    from talemate.world.refs import ref

    with world.revision(Source.manual(note="setup")) as rev:
        place_id = rev.create_thing("place", fields={"name": "Veldhaer"})
        lore_id = rev.create_thing("lore", fields={"name": "The River Treaty"})
        rev.add_fact(place_id, "history", f"Bound by {ref(lore_id, 'the Treaty')}.")
        rev.add_fact(lore_id, "general", f"Signed in {ref(place_id)}.")
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(310))
    scenes.update(scene_id, state={"place_thing_id": place_id, "pulled_in": [lore_id]})

    block = world_context_block(world, scenes.get(scene_id), WorldDate.of(310))
    assert "Bound by the Treaty." in block
    assert "Signed in Veldhaer." in block
    assert "[[thing:" not in block


def test_world_context_block_lists_heritage_bodies(world, heritage_world):
    """The heritage play probe (docs/superpowers/probes/2026-10-20-
    heritage-play.md): the narrator's prompts carry no character sheets,
    so the World block names each character's heritage with its body and
    instincts, resolved in code as of the scene's date -- a world
    character's with its own overrides applied, an invented one's from
    the heritage it was given. A character with no heritage isn't listed,
    and neither is a culture's lore."""

    h = heritage_world
    with world.revision(Source.manual(note="later")) as rev:
        rev.add_fact(
            h.owl_folk,
            "physical",
            "Grows a winter ruff.",
            valid_from=WorldDate.of(1000),
        )

    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(999), goal="Cross the river")
    scenes.update(
        scene_id,
        state={
            "characters": [
                {"thing_id": h.vasha, "active": True},
                {"local_id": "rill", "active": True},
                {"local_id": "ilse", "active": True},
            ]
        },
    )
    scenes.set_local_things(
        scene_id,
        [
            {
                "local_id": "rill",
                "kind": "character",
                "data": {"name": "Rill", "world_heritage_id": h.snowy},
            },
            {"local_id": "ilse", "kind": "character", "data": {"name": "Ilse"}},
        ],
    )
    record = scenes.get(scene_id)

    block = world_context_block(world, record, WorldDate.of(999))
    vasha, rill = (
        line for line in block.splitlines() if line.startswith(("- Vasha", "- Rill"))
    )

    assert vasha.startswith("- Vasha (Snowy, a race of Owl-folk)")
    assert "Blue eyes." in vasha
    assert "White plumage." in vasha
    assert "Wings in place of arms." in vasha
    assert "Yellow eyes." not in vasha
    assert "Hunts at dusk." in vasha
    assert "Name their boats." not in block
    assert "winter ruff" not in block

    assert rill.startswith("- Rill (Snowy, a race of Owl-folk)")
    assert "Yellow eyes." in rill
    assert "Wings in place of arms." in rill
    assert "Hunts at dusk." in rill
    assert "Ilse" not in block

    # the scene's clock passes the dated species fact: the cast follows
    later = world_context_block(world, record, WorldDate.of(1000))
    assert later.count("Grows a winter ruff.") == 2


def test_world_context_block_names_heritage_without_missing_names(
    world, heritage_world
):
    """Final review: a mix whose parent was deleted names only the parent
    that's left, and a heritage with no name of its own at the scene's
    date isn't shown as "(, a race of ...)"."""

    h = heritage_world
    with world.revision(Source.manual(note="setup")) as rev:
        lowlander = rev.create_thing("race", fields={"name": "Lowlander"})
        orc = rev.create_thing("species", fields={"name": "Orc"})
        half_orc = rev.create_thing(
            "mix", fields={"name": "Half-orc", "parents": [lowlander, orc]}
        )
        rev.add_fact(half_orc, "physical", "Small tusks.")
        brenna = rev.create_thing(
            "character", fields={"name": "Brenna", "heritage": half_orc}
        )
        nameless = rev.create_thing("race", fields={"species": h.owl_folk})
        rev.set_field(nameless, "name", "Tawny", WorldDate.of(2000))
        kit = rev.create_thing(
            "character", fields={"name": "Kit", "heritage": nameless}
        )
    with world.revision(Source.manual(note="drop orc")) as rev:
        rev.remove_thing(orc)

    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(999), goal="Cross the river")
    scenes.update(
        scene_id,
        state={
            "characters": [
                {"thing_id": brenna, "active": True},
                {"thing_id": kit, "active": True},
            ]
        },
    )
    block = world_context_block(world, scenes.get(scene_id), WorldDate.of(999))
    lines = block.splitlines()

    assert any(
        line.startswith("- Brenna (Half-orc, a mix of Lowlander):") for line in lines
    )
    assert any(line.startswith("- Kit (a race of Owl-folk):") for line in lines)
    assert " and )" not in block
    assert "(," not in block


@pytest.mark.asyncio
async def test_inject_adds_world_instruction(world):
    with world.revision(Source.manual(note="setup")) as rev:
        place_id = rev.create_thing("place", fields={"name": "Veldhaer"})

    scenes = world.scenes()
    scene_id = scenes.create(
        "Test Scene", WorldDate.of(310), goal="Find the missing envoy"
    )
    scenes.update(scene_id, state={"place_thing_id": place_id})
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)
    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)

    conversation = instance.get_agent("conversation")
    emission = ConversationAgentEmission(
        agent=conversation, character=Character(name="Anyone"), response=""
    )
    await async_signals.get("agent.conversation.inject_instructions").send(emission)

    instructions = [i for i in emission.dynamic_instructions if i.title == "World"]
    assert len(instructions) == 1
    assert "Find the missing envoy" in instructions[0].content
    assert "Veldhaer" in instructions[0].content


@pytest.mark.asyncio
async def test_since_lines_after_time_passage(world):
    """Review Focus 1: a scene at 313-12-15, a time passage of P30D into
    314 crosses the stretch boundary the cached description was generated
    for. `refresh_characters` must still pick up the since line -- and
    must never touch the model to do it."""

    with world.revision(Source.manual(note="create Mira")) as rev:
        thing_id = rev.create_thing(
            "character",
            fields={"name": "Mira", "born": WorldDate.of(280)},
            valid_from=WorldDate.of(280),
        )
        rev.add_fact(
            thing_id,
            "appearance",
            "A scar across her cheek.",
            valid_from=WorldDate.of(314),
        )

    # The real stretch boundaries for this thing are (None, 280), (280,
    # 314) and (314, None) -- cached here for the (280, 314) one (fix
    # round 1 / Critical 2: an earlier version of this test used the
    # fabricated, non-real pair (None, 314), which happened to still
    # match on lookup and so never exercised the cache walk-back bug).
    world.prose().put(
        thing_id,
        "description",
        WorldDate.of(280),
        WorldDate.of(314),
        "A quiet trader with a steady gaze.",
    )

    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(313, 12, 15))
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)

    character = character_from_world(world, thing_id, record.start, is_player=False)
    assert "scar" not in character.description
    character.color = "#abc123"  # a per-scene field refresh must not touch

    conversation = instance.get_agent("conversation")
    actor = Actor(character=character, agent=conversation)
    actor.scene = scene
    scene.actors.append(actor)
    scene.active_characters.append(character.name)
    scene.character_data[character.name] = character

    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)

    world_state = instance.get_agent("world_state")
    await world_state.advance_time("P30D")

    refreshed = scene.get_character("Mira")
    assert refreshed is not character
    assert "Since 314: A scar across her cheek." in refreshed.description

    # fix round 1 / Critical 4: a per-scene field survives the refresh.
    assert refreshed.color == "#abc123"
    # fix round 1 (small fix): the agent's own pointer is updated too.
    assert actor.agent.character is refreshed

    # No queued responses in `scene.mock_client` -- a call to `send_prompt`
    # would have appended to `prompt_history` regardless of what it
    # returned, so an empty history proves the model was never touched.
    assert scene.mock_client.prompt_history == []


@pytest.mark.asyncio
async def test_refresh_characters_keeps_existing_when_thing_deleted(world):
    """Review-round fix: `agent.world_state.time` fires `refresh_characters`
    for every active character on every time skip (and
    `server/worlds.py`'s `_refresh_loaded` calls it directly from
    `reposition_scene`). A character whose world thing has since been
    deleted must not blow up that signal -- `character_from_world` raises
    KeyError for it, so the actor keeps its last-built character, with a
    warning logged (the same pattern `persistence._character_data` uses
    on load)."""

    with world.revision(Source.manual(note="create Mira")) as rev:
        thing_id = rev.create_thing("character", fields={"name": "Mira"})

    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(313, 12, 15))
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)

    character = character_from_world(world, thing_id, record.start, is_player=False)

    conversation = instance.get_agent("conversation")
    actor = Actor(character=character, agent=conversation)
    actor.scene = scene
    scene.actors.append(actor)
    scene.active_characters.append(character.name)
    scene.character_data[character.name] = character

    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)

    with world.revision(Source.manual(note="deleted Mira")) as rev:
        rev.remove_thing(thing_id)

    world_state = instance.get_agent("world_state")
    await world_state.advance_time("P30D")  # must not raise

    assert actor.character is character
    assert actor.agent.character is character
    assert scene.get_character("Mira") is character


@pytest.mark.asyncio
async def test_connect_does_not_leak_between_scenes(world):
    """Fix round 1 / Critical 3: `connect` used to add a per-scene closure
    that was never disconnected, so a second scene's signal traffic would
    still carry the first scene's "World" block. The handlers are
    module-level now, resolved from `emission.agent.scene` -- which is
    whichever scene most recently claimed the (process-wide) agent
    instance, the same as real scene loading."""

    scenes = world.scenes()
    scene_id = scenes.create(
        "Scene A", WorldDate.of(310), goal="Find the missing envoy"
    )
    record = scenes.get(scene_id)

    scene_a = MockScene()
    bootstrap_scene(scene_a)
    scene_a.world_context = WorldSceneContext(world=world, record=record)
    connect(scene_a)

    scene_b = MockScene()
    bootstrap_scene(scene_b)  # re-points every agent's `.scene` at scene_b
    connect(scene_b)  # scene_b never gets a `world_context`

    conversation = instance.get_agent("conversation")

    emission_b = ConversationAgentEmission(
        agent=conversation, character=Character(name="Anyone"), response=""
    )
    await async_signals.get("agent.conversation.inject_instructions").send(emission_b)
    assert emission_b.dynamic_instructions == []

    # make the (shared) agent "live" in scene A again, the way loading a
    # scene would, and fire the same signal: exactly one "World"
    # instruction, not two, even though `connect` ran twice.
    conversation.scene = scene_a
    emission_a = ConversationAgentEmission(
        agent=conversation, character=Character(name="Anyone"), response=""
    )
    await async_signals.get("agent.conversation.inject_instructions").send(emission_a)
    world_instructions = [
        i for i in emission_a.dynamic_instructions if i.title == "World"
    ]
    assert len(world_instructions) == 1


EVERYDAY_LINE = (
    "In narration and dialogue, call things by their everyday names: where a "
    'name is followed by "usually called ...", use that name, and keep the '
    "full name for formal moments."
)


def test_context_block_uses_everyday_name(world):
    """A place or touched entry with an everyday name is shown "<main>
    (usually called <everyday>)" ("<main> (<tag or kind>, usually called
    <everyday>)" for a touched one), and the block opens with the line asking
    for everyday names (connections probe, recommendation (d))."""

    aka = [
        {"name": "Moscavia", "tag": "common", "everyday": True},
        {"name": "The Owl Throne", "tag": "proper", "everyday": False},
    ]
    with world.revision(Source.manual(note="setup")) as rev:
        place_id = rev.create_thing("place", fields={"name": "Barrowford"})
        rev.add_fact(place_id, "description", "A river town on the Vesna.")
        tsardom = rev.create_thing(
            "lore", fields={"name": "Tsardom of Moscavia", "aka": aka}
        )
        rev.add_fact(tsardom, "general", "Ruled by the Tsar.")
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(310))
    scenes.update(scene_id, state={"place_thing_id": place_id, "pulled_in": [tsardom]})

    block = world_context_block(world, scenes.get(scene_id), WorldDate.of(310))
    lines = block.splitlines()
    assert lines[0] == "[world]"
    assert lines[1] == EVERYDAY_LINE
    assert "Place: Barrowford\n" in block
    assert "Tsardom of Moscavia (lore, usually called Moscavia)\n" in block

    # with no everyday name anywhere, no line
    with world.revision(Source.manual(note="no aka")) as rev:
        rev.set_field(tsardom, "aka", [], None)
    block = world_context_block(world, scenes.get(scene_id), WorldDate.of(310))
    assert EVERYDAY_LINE not in block
    assert "usually called" not in block


def test_context_block_everyday_name_of_the_place(world):
    with world.revision(Source.manual(note="setup")) as rev:
        place_id = rev.create_thing(
            "place",
            fields={
                "name": "Tsardom of Moscavia",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(310))
    scenes.update(scene_id, state={"place_thing_id": place_id})

    block = world_context_block(world, scenes.get(scene_id), WorldDate.of(310))
    assert "Place: Tsardom of Moscavia (usually called Moscavia)" in block
    assert EVERYDAY_LINE in block


# --- touched entries, from filings (filing spec, "Scene context"; probe 5) -------

TOUCHED_LEAD = (
    "What this scene touches: keep what these say true, and bring it in only "
    "where the scene calls for it."
)

SCRIBE_GOAL = "Deliver a sealed letter to the Chief Scribe of the Talon-Scribe Order."
SCRIBE_PREMISE = "Vasha walks toward the Academy; a member of the Order lets her in."


def _scene(world, at, *, goal="", premise="", **state):
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", at, goal=goal, premise=premise)
    scenes.update(scene_id, state=state)
    return world_context_block(world, scenes.get(scene_id), at)


def _present(*thing_ids):
    return [{"thing_id": thing_id, "active": True} for thing_id in thing_ids]


def _headings(block):
    """The touched entries' headings, in order."""

    body = block.split(TOUCHED_LEAD, 1)[1] if TOUCHED_LEAD in block else ""
    return [
        line
        for line in body.splitlines()
        if line and not line.startswith(("- ", "[end"))
    ]


def _scribe_scene(world, s, **kwargs):
    return _scene(
        world,
        WorldDate.of(1000),
        goal=SCRIBE_GOAL,
        premise=SCRIBE_PREMISE,
        place_thing_id=s.academy,
        characters=_present(s.vasha),
        **kwargs,
    )


def test_scene_touched_by_filings(world, scribe_world):
    """What the scene touches: what its place is filed in, followed up to
    the timeline reach (the Academy is in Velikoye and Runic Magic,
    Velikoye in the Tsardom); what each present character is filed in
    (Vasha, a courier of the Postal Authority); what the setup names (the
    Order, in the goal); and (ruling F4) a character filed in one of
    those, or in the place, whose role the goal or premise names as whole
    words: Anastasiya, the Order's Chief Scribe. Not Ilya, a "member" (a
    generic role, though the premise says "member"), nor Oleg, the
    Order's "ward" (the premise's "toward" isn't the word), nor Vasha
    herself (her sheet covers her), nor the place."""

    s = scribe_world
    block = _scribe_scene(world, s)

    assert _headings(block) == [
        "Velikoye (city)",
        "Runic Magic (field)",
        "Tsardom of Moscavia (nation, usually called Moscavia)",
        "Northern Postal Authority (service)",
        "Talon-Scribe Order (order)",
        "Anastasiya Koroleva (character)",
    ]
    assert "- A tawny-brown owl-folk with burnt-orange eyes." in block
    # Wattle Row's opening, told by Velikoye and by Wattle Row (gathered
    # by Velikoye and, two steps up, by the Tsardom), shows once: as
    # Velikoye's own line (probe 5's note: dedupe by text overlap)
    assert block.count("Wattle Row opened its first workshops") == 1
    assert (
        "Velikoye (city)\n"
        "- The river capital.\n"
        "- In 998: Wattle Row opened its first workshops.\n"
    ) in block
    assert (
        "Tsardom of Moscavia (nation, usually called Moscavia)\n"
        "- A northern realm of owl-folk.\n"
        "- In 990: Crowned the first Tsar.\n\n"
    ) in block
    assert "Ilya" not in block and "Oleg" not in block
    assert "A snowy owl-folk." not in block
    assert block.count("A courtyard of training stones.") == 1

    # the role rule is whole words, either case: "chief scribes" isn't
    # "Chief Scribe"
    block = _scene(
        world,
        WorldDate.of(1000),
        goal="Bring the chief scribes their ink.",
        place_thing_id=s.academy,
        characters=_present(s.vasha),
        pulled_in=[s.order],
    )
    assert "Anastasiya" not in block
    block = _scene(
        world,
        WorldDate.of(1000),
        goal="Bring the CHIEF SCRIBE her ink.",
        place_thing_id=s.academy,
        pulled_in=[s.order],
    )
    assert "Anastasiya Koroleva (character)" in block

    # filed in the place itself counts too; a filing that has ended, or a
    # character who isn't here, doesn't touch anything
    with world.revision(Source.manual(note="the place")) as rev:
        rev.set_field(
            s.ilya,
            "filings",
            [_in_record(s.academy, "gatekeeper")],
            None,
        )
    block = _scene(
        world,
        WorldDate.of(1000),
        goal="Get past the gatekeeper.",
        place_thing_id=s.academy,
    )
    assert "Ilya (character)" in block
    # ended by the scene's date, the filing touches nothing
    with world.revision(Source.manual(note="ended")) as rev:
        rev.set_field(
            s.ilya,
            "filings",
            [_in_record(s.academy, "gatekeeper", until=WorldDate.of(990))],
            None,
        )
    block = _scene(
        world,
        WorldDate.of(1000),
        goal="Get past the gatekeeper.",
        place_thing_id=s.academy,
    )
    assert "Ilya" not in block
    block = _scene(
        world,
        WorldDate.of(1000),
        goal="Get past the gatekeeper.",
        place_thing_id=s.academy,
        characters=[{"thing_id": s.vasha, "active": False}],
    )
    assert "Northern Postal Authority" not in block


def _in_record(target, role=None, since=None, until=None, exceptions=()):
    return {
        "target": target,
        "role": role,
        "since": since.model_dump(mode="json") if since else None,
        "until": until.model_dump(mode="json") if until else None,
        "within": None,
        "exceptions": list(exceptions),
    }


def test_generic_roles_never_touch():
    """The role rule ignores generic roles, listed in one constant, and an
    empty one; it matches the rest as whole words, any case."""

    from talemate.worldplay.context import GENERIC_ROLES, role_named

    for role in ("member", "part", "in", "practitioner", "of this culture"):
        assert role in GENERIC_ROLES
        assert not role_named(role, f"Every {role} of the Order is here.")
    assert not role_named(None, "anything")
    assert not role_named("  ", "anything")
    assert role_named("Chief Scribe", "the chief  scribe reads it")
    assert not role_named("scribe", "the scribes read it")
    assert not role_named("ward", "she walks toward it")


def test_scene_block_wording(world):
    """Probe 5's block, each touched entry headed "<name> (<tag or kind>)"
    under the lead line: its summary, then up to 5 of its own facts, the
    most-linked first (a held one worded as held), then its latest 3
    timeline lines ("In <year>: ..."; "From <year> to <year>: ..." once
    ended, ruling C18), the same event told twice counted once (the
    Shrine's telling of the Doctrine gives way to the Dawn's own), and at
    most 8 lines in all: the timeline keeps its 3, the own facts give way.
    The goal, place and cast blocks are as before."""

    from talemate.world.refs import ref

    with world.revision(Source.manual(note="dawn")) as rev:
        peak = rev.create_thing("place", fields={"name": "Dawn Peak"})
        rev.add_fact(peak, "description", "A bare summit.")
        kremova = rev.create_thing("place", fields={"name": "Kremova"})
        dawn = rev.create_thing(
            "lore", fields={"name": "The White Dawn", "tag": "religion"}
        )
        rev.add_fact(dawn, "general", "The White Dawn is the state church.")
        rev.add_fact(dawn, "general", "Its priests wear white.")
        rev.add_fact(dawn, "general", f"Its seat is in {ref(kremova)}.")
        rev.add_fact(
            dawn,
            "general",
            f"Pilgrims climb from {ref(kremova)} to {ref(peak)}.",
        )
        rev.add_fact(dawn, "belief", "Snowy owl-folk are the purest of the folk.")
        rev.add_fact(dawn, "general", "Bells ring at first light.")
        rev.add_fact(dawn, "general", "It keeps no images.")
        rev.add_fact(
            dawn,
            "general",
            "Held the old spire.",
            valid_from=WorldDate.of(1001),
            valid_until=WorldDate.of(1010),
        )
        rev.add_fact(
            dawn,
            "general",
            "Declared the Night of Feathers a purification.",
            valid_from=WorldDate.of(994),
        )
        rev.add_fact(
            dawn,
            "general",
            "Issued the Doctrine of Separation.",
            valid_from=WorldDate.of(1019),
        )
        shrine = rev.create_thing(
            "lore",
            fields={"name": "The Shrine", "filings": [_in_record(dawn)]},
        )
        rev.add_fact(
            shrine,
            "general",
            "The White Dawn issued the Doctrine of Separation at the shrine.",
            valid_from=WorldDate.of(1019),
        )

    block = _scene(
        world,
        WorldDate.of(1020),
        goal="Keep the vigil.",
        place_thing_id=peak,
        pulled_in=[dawn],
    )
    assert block == (
        "[world]\n"
        "Goal: Keep the vigil.\n"
        "Place: Dawn Peak\n"
        "- A bare summit.\n"
        "\n"
        f"{TOUCHED_LEAD}\n"
        "The White Dawn (religion)\n"
        "- The White Dawn is the state church.\n"
        "- Pilgrims climb from Kremova to Dawn Peak.\n"
        "- Its seat is in Kremova.\n"
        "- Its priests wear white.\n"
        "- The White Dawn holds: Snowy owl-folk are the purest of the folk.\n"
        "- In 994: Declared the Night of Feathers a purification.\n"
        "- From 1001 to 1010: Held the old spire.\n"
        "- In 1019: Issued the Doctrine of Separation.\n"
        "\n"
        "[end of world]"
    )


def test_scene_place_and_touched_entries_show_once(world, scribe_world):
    """The scene's place shows once, as the place, though the setup names
    it (pulled in); an entry touched two ways (Velikoye, filed above the
    place and pulled in) is one block, and no fact is told twice."""

    s = scribe_world
    block = _scribe_scene(world, s, pulled_in=[s.academy, s.velikoye, s.order])
    assert block.count("The Academy") == 1
    assert "The Academy (" not in block
    assert block.count("Velikoye (city)") == 1
    assert block.count("The river capital.") == 1
    assert block.count("Talon-Scribe Order (order)") == 1

    # the place pulled in, with nothing else touched: the place alone
    block = _scene(
        world, WorldDate.of(1000), place_thing_id=s.tsardom, pulled_in=[s.tsardom]
    )
    assert "Place: Tsardom of Moscavia (usually called Moscavia)\n" in block
    assert TOUCHED_LEAD not in block
    assert block.count("A northern realm of owl-folk.") == 1


def test_untouched_entry_not_in_context(world):
    """An entry nothing touches never shows: one unlinked from the place,
    the cast and the setup, one merely mentioned by the place's facts, and
    a believed being even when named (it's only spoken of). With nothing
    touched there's no lead line."""

    from talemate.world.refs import ref

    with world.revision(Source.manual(note="setup")) as rev:
        place = rev.create_thing("place", fields={"name": "Veldhaer"})
        rev.add_fact(place, "description", "A harbor town built on stilts.")
        treaty = rev.create_thing("lore", fields={"name": "The River Treaty"})
        rev.add_fact(treaty, "general", "Signed after the flood of 301.")
        rev.add_fact(place, "history", f"Bound by {ref(treaty)}.")
        other = rev.create_thing("lore", fields={"name": "Far Mountains"})
        rev.add_fact(other, "general", "Snow all year.")
        mother = rev.create_thing(
            "being", fields={"name": "Sea Mother", "existence": "believed"}
        )
        rev.add_fact(mother, "nature", "A goddess of the deep.")
        maren = rev.create_thing("character", fields={"name": "Maren"})
        rev.add_fact(maren, "background", "A ferrywoman.")

    block = _scene(
        world,
        WorldDate.of(310),
        goal="Find the envoy",
        place_thing_id=place,
        characters=_present(maren),
        pulled_in=[mother],
    )
    assert block == (
        "[world]\n"
        "Goal: Find the envoy\n"
        "Place: Veldhaer\n"
        "- A harbor town built on stilts.\n"
        "- Bound by The River Treaty.\n"
        "[end of world]"
    )


def test_scene_timeline_gathers_what_is_filed(world, spheres_world):
    """A touched entry's timeline lines gather what's filed in it: Dawn
    Peak's raising, filed in the Dawn, is among the Dawn's latest lines,
    held as belief when it's held; with Dawn Peak the scene's place, its
    fact is told once, as the place's."""

    s = spheres_world
    with world.revision(Source.manual(note="later")) as rev:
        rev.add_fact(
            s.dawn_peak,
            "general",
            "The shrine on the peak was raised by the dawn's own light.",
            valid_from=WorldDate.of(1015),
            origin={"held_by": s.dawn},
        )
    at = WorldDate.of(1020)
    block = _scene(world, at, place_thing_id=s.kremova, characters=_present(s.vasha))
    assert (
        "- In 994: Declared the Night of Feathers a purification.\n"
        "- In 1015: The White Dawn holds that the shrine on the peak was raised "
        "by the dawn's own light.\n"
        "- In 1019: Issued the Doctrine of Separation.\n"
    ) in block

    block = _scene(world, at, place_thing_id=s.dawn_peak, characters=_present(s.vasha))
    assert block.count("shrine on the peak") == 1
    assert "- In 1015:" not in block


@pytest.mark.asyncio
async def test_no_extra_model_calls_on_turn(world, spheres_world):
    """Filings in play cost no model call: the World instruction (narrator
    and conversation) carries the touched entries, and a time passage
    rebuilds Vasha's sheet with her filing line, all from what's stored."""

    s = spheres_world
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(1020), goal="Keep the vigil")
    scenes.update(
        scene_id,
        state={"place_thing_id": s.kremova, "characters": _present(s.vasha)},
    )
    record = scenes.get(scene_id)

    scene = MockScene()
    bootstrap_scene(scene)
    character = character_from_world(world, s.vasha, record.start, is_player=False)
    conversation = instance.get_agent("conversation")
    actor = Actor(character=character, agent=conversation)
    actor.scene = scene
    scene.actors.append(actor)
    scene.active_characters.append(character.name)
    scene.character_data[character.name] = character
    scene.world_context = WorldSceneContext(world=world, record=record)
    connect(scene)

    emission = ConversationAgentEmission(
        agent=conversation, character=character, response=""
    )
    await async_signals.get("agent.conversation.inject_instructions").send(emission)
    [instruction] = [i for i in emission.dynamic_instructions if i.title == "World"]
    assert _headings(instruction.content) == [
        "Tsardom of Moscavia (place, usually called Moscavia)",
        "The White Dawn (sphere)",
    ]

    world_state = instance.get_agent("world_state")
    await world_state.advance_time("P30D")
    assert (
        scene.get_character("Vasha")
        .base_attributes["ties"]
        .startswith("Practitioner of the White Dawn (since 1010), but: ")
    )

    assert scene.mock_client.prompt_history == []
