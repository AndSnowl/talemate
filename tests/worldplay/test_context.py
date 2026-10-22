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
    """A place or lore entry with an everyday name is shown "<main>
    (usually called <everyday>)", and the block opens with the line asking
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
    assert "Tsardom of Moscavia (usually called Moscavia)\n" in block

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


# --- spheres -------------------------------------------------------------------

SPHERES_LEAD = (
    "Spheres this scene touches (faiths, nations, orders, cultures): keep what "
    "they hold true, and bring it in only where the scene calls for it."
)

DAWN_BLOCK = (
    "The White Dawn (religion)\n"
    "- The White Dawn is the state church of Moscavia.\n"
    "- The Doctrine of Separation forbids the faithful to marry humans.\n"
    "- Snowy owl-folk are the purest of the folk.\n"
    "- The Council of Elders: Seven elders seated in Kremova.\n"
    "- In 994: Declared the Night of Feathers a purification.\n"
    "- In 1019: Issued the Doctrine of Separation.\n"
)

TSARDOM_BLOCK = (
    "Tsardom of Moscavia (nation, usually called Moscavia)\n"
    "- A northern realm of owl-folk.\n"
    "- Only owl-folk may hold land.\n"
    "- In 990: Crowned the first Tsar.\n"
)


def _sphere_scene(world, **state):
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", WorldDate.of(1020), goal="Keep the vigil")
    scenes.update(scene_id, state=state)
    return world_context_block(world, scenes.get(scene_id), WorldDate.of(1020))


def _present(*thing_ids):
    return [{"thing_id": thing_id, "active": True} for thing_id in thing_ids]


def test_context_touched_sphere_key_facts(world, spheres_world):
    """A sphere the scene touches is one block of its key facts, after the
    lore and before who is here, under the probe's (d) lead line: the
    summary (its cached description prose), its top items (a thing item
    whose text opens with its name as the text alone), then its latest
    timeline facts dated "In <year>". Named (pulled in) and holding the
    place (Dawn Peak, a holy site), it's still there once, and never also
    as a lore entry."""

    s = spheres_world
    block = _sphere_scene(world, place_thing_id=s.dawn_peak, pulled_in=[s.dawn])

    assert f"\n{SPHERES_LEAD}\n{DAWN_BLOCK}" in block
    assert block.count("The White Dawn") == 2  # the heading and the summary
    assert block.count("Snowy owl-folk are the purest") == 1
    assert "A faith of the dawn." not in block
    assert "[[thing:" not in block
    assert block.endswith(DAWN_BLOCK + "\n[end of world]")


def test_pulled_in_item_shows_once(world, spheres_world):
    """An item of a touched sphere that's pulled in as lore (the Doctrine
    of Separation, named by the scene) shows once, as the lore entry with
    all its facts, after which the sphere's key facts leave it out (the
    spheres Task 10 session: the Council of Elders showed twice)."""

    s = spheres_world
    block = _sphere_scene(
        world, place_thing_id=s.dawn_peak, pulled_in=[s.dawn, s.separation]
    )

    separation = "The Doctrine of Separation forbids the faithful to marry humans."
    assert block.count(separation) == 1
    # shown as lore, before the spheres
    assert block.index(f"The Doctrine of Separation\n- {separation}") < block.index(
        SPHERES_LEAD
    )
    without = DAWN_BLOCK.replace(f"- {separation}\n", "")
    assert f"\n{SPHERES_LEAD}\n{without}" in block


def test_context_touched_by_territory_and_members(world, spheres_world):
    """The Tsardom holds Kremova, the scene's place; Vasha, present, is a
    practitioner of the Dawn; Brenna, present, an elder of the Council,
    nested in the Dawn: the Council brings its parent's summary only, and
    not when the parent is in the block itself. Territory, then named,
    then members."""

    s = spheres_world
    block = _sphere_scene(
        world, place_thing_id=s.kremova, characters=_present(s.vasha, s.brenna)
    )
    council = "The Council of Elders (order)\n- Seven elders seated in Kremova.\n"
    assert f"{SPHERES_LEAD}\n{TSARDOM_BLOCK}\n{DAWN_BLOCK}\n{council}" in block
    assert block.count(SPHERES_LEAD) == 1

    block = _sphere_scene(
        world, place_thing_id=s.kremova, characters=_present(s.brenna)
    )
    council = (
        "The Council of Elders (order)\n"
        "- Part of the White Dawn: The White Dawn is the state church of "
        "Moscavia.\n"
        "- Seven elders seated in Kremova.\n"
    )
    assert f"{SPHERES_LEAD}\n{TSARDOM_BLOCK}\n{council}" in block
    assert "The White Dawn (religion)" not in block

    # an inactive character is no member present; an ended tie neither
    block = _sphere_scene(
        world,
        place_thing_id=s.dawn_peak,
        characters=[{"thing_id": s.brenna, "active": False}],
    )
    assert "The Council of Elders (order)" not in block


def test_place_sphere_context_once(world, spheres_world):
    """The scene's place is itself a sphere (the Tsardom): it shows once,
    as the place, its own place facts followed by its key facts, never
    again as a sphere block."""

    s = spheres_world
    block = _sphere_scene(world, place_thing_id=s.tsardom)

    assert (
        "Place: Tsardom of Moscavia (usually called Moscavia)\n"
        "- Cold forests and frozen rivers.\n"
        "- A northern realm of owl-folk.\n"
        "- Only owl-folk may hold land.\n"
        "- In 990: Crowned the first Tsar.\n"
    ) in block
    assert "(nation" not in block
    assert SPHERES_LEAD not in block
    assert block.count("Only owl-folk may hold land.") == 1
    assert block.count("Crowned the first Tsar.") == 1

    # with other spheres touched, still once
    block = _sphere_scene(
        world,
        place_thing_id=s.tsardom,
        pulled_in=[s.dawn],
        characters=_present(s.vasha),
    )
    assert block.count("Only owl-folk may hold land.") == 1
    assert "(nation" not in block
    assert block.count("The White Dawn (religion)") == 1


def test_untouched_sphere_not_in_context(world, spheres_world):
    """A sphere nothing touches never shows: not the Iron Guild, and with
    nothing touched at all, no lead line either."""

    s = spheres_world
    block = _sphere_scene(world, place_thing_id=s.dawn_peak)
    assert "Iron Guild" not in block
    assert "Smiths of the far south." not in block

    with world.revision(Source.manual(note="elsewhere")) as rev:
        elsewhere = rev.create_thing("place", fields={"name": "The Southern Wastes"})
    block = _sphere_scene(world, place_thing_id=elsewhere)
    assert SPHERES_LEAD not in block
    assert "Iron Guild" not in block
    assert "White Dawn" not in block
    assert "Moscavia" not in block


@pytest.mark.asyncio
async def test_no_extra_model_calls_on_turn(world, spheres_world):
    """Spheres in play cost no model call: the World instruction (narrator
    and conversation) carries the touched spheres, and a time passage
    rebuilds Vasha's sheet with her tie line, all from what's stored."""

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
    assert TSARDOM_BLOCK in instruction.content
    assert DAWN_BLOCK in instruction.content

    world_state = instance.get_agent("world_state")
    await world_state.advance_time("P30D")
    assert (
        scene.get_character("Vasha")
        .base_attributes["ties"]
        .startswith("Practitioner of the White Dawn (since 1010), but: ")
    )

    assert scene.mock_client.prompt_history == []


def test_named_place_sphere_context_once(world, spheres_world, monkeypatch):
    """Ruling P10: the Tsardom, named in the prompt (pulled in) while the
    scene is at Dawn Peak, outside it, shows once as a sphere block and
    never as lore. Who holds the place is found from one snapshot
    (`spheres.holders`), never by asking each sphere's territory."""

    from talemate.world import spheres as world_spheres

    def no_territory(*_args, **_kwargs):
        raise AssertionError("territory asked per sphere")

    monkeypatch.setattr(world_spheres, "territory", no_territory)

    s = spheres_world
    block = _sphere_scene(world, place_thing_id=s.dawn_peak, pulled_in=[s.tsardom])
    assert f"{SPHERES_LEAD}\n{DAWN_BLOCK}\n{TSARDOM_BLOCK}" in block
    assert block.count("Tsardom of Moscavia") == 1
    assert block.count("Only owl-folk may hold land.") == 1
    assert "Cold forests and frozen rivers." not in block
