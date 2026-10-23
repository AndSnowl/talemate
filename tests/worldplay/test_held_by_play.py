"""Held by in play: a held fact reaches a scene as belief ("<Holder> holds
that ..."), and a create reply's per-fact `held_by` name maps to the
entry it names."""

import json

from talemate.world.calendar import Calendar
from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.spheres import with_held_by
from talemate.world.store import Source
from talemate.worldplay.characters import attributes_itself, held_text
from talemate.worldplay.context import world_context_block
from talemate.worldplay.create import accept_preview, parse_create_reply, preview_thing

from conftest import MockClient, MockClientContext, client_responses

AT = WorldDate.of(1020)


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


def _scene(world, **state):
    scenes = world.scenes()
    scene_id = scenes.create("Test Scene", AT, goal="Keep the vigil")
    scenes.update(scene_id, state=state)
    return world_context_block(world, scenes.get(scene_id), AT)


def test_attributes_itself():
    """A text already saying who holds it isn't wrapped again."""

    names = ["The White Dawn", "the Dawn"]
    assert attributes_itself("The White Dawn teaches that owls are pure.", names)
    assert attributes_itself("As the Dawn holds, owls are pure.", names)
    assert attributes_itself("Many say the white dawn believes in owls.", names)
    assert not attributes_itself("Owls are pure.", names)
    assert not attributes_itself("The White Dawning teaches nothing.", names)
    assert not attributes_itself("The White Dawn was founded in 900.", names)


def test_held_fact_renders_as_belief_in_scene(world, spheres_world):
    """A held fact goes to the narrator as belief: "<Holder> holds that
    <text>", its first letter lowered unless it opens with a name. A
    statement in the Dawn's Doctrines is held by the Dawn; the Tsardom's
    Laws are plain; a text that already attributes itself is left as it
    is; a held lore fact is held in the lore entry too."""

    s = spheres_world
    with world.revision(Source.manual()) as rev:
        light = rev.create_thing("lore", fields={"name": "The Night of Feathers"})
        rev.add_fact(
            light,
            "general",
            "Every owl lost its sight for a night.",
            origin=with_held_by(None, s.dawn),
        )
        rev.add_fact(
            light,
            "general",
            f"{ref(s.kremova)} burned for three days.",
            origin=with_held_by(None, s.dawn),
        )
        rev.add_fact(
            light,
            "general",
            "The White Dawn teaches that the night was a judgement.",
            origin=with_held_by(None, s.dawn),
        )
        rev.add_fact(light, "general", "It fell in the year 994.")

    block = _scene(world, place_thing_id=s.dawn_peak, pulled_in=[s.dawn, light])

    assert "- The White Dawn holds: Snowy owl-folk are the purest of the folk." in block
    assert "The White Dawn holds that every owl lost its sight for a night." in block
    assert "The White Dawn holds that Kremova burned for three days." in block
    assert "The White Dawn teaches that the night was a judgement." in block
    assert "holds that the White Dawn teaches" not in block
    assert "It fell in the year 994." in block
    assert "holds that it fell" not in block

    tsardom = _scene(world, place_thing_id=s.kremova)
    assert "- Only owl-folk may hold land." in tsardom
    assert "holds that only" not in tsardom


def test_held_text_plain_and_deleted_holder(world, spheres_world):
    """A plain fact renders as it is; so does one whose holder is gone."""

    s = spheres_world
    with world.revision(Source.manual()) as rev:
        lore = rev.create_thing("lore", fields={"name": "The Vigil"})
        held = rev.add_fact(
            lore, "general", "Owls keep the vigil.", origin={"held_by": s.guild}
        )
    view = world.view()
    owner = view.thing(lore)
    fact = next(f for f in owner.facts if f.fact_id == held)
    assert held_text(view, fact, owner) == "The Iron Guild holds: Owls keep the vigil."

    with world.revision(Source.manual()) as rev:
        rev.remove_thing(s.guild)
    view = world.view()
    owner = view.thing(lore)
    fact = next(f for f in owner.facts if f.fact_id == held)
    assert held_text(view, fact, owner) == "Owls keep the vigil."


def test_create_reply_held_by_maps_to_thing(world, spheres_world):
    """A reply's per-fact `held_by` naming a known entry (by its name or
    other name, ignoring a leading article) maps to its id; an unknown name
    or null is dropped. Accept writes it as the fact's origin."""

    s = spheres_world
    holders = {"the white dawn": s.dawn, "moscavia": s.tsardom}
    reply = json.dumps(
        {
            "name": "The Night of Feathers",
            "facts": [
                {
                    "category": "general",
                    "text": "Every owl lost its sight.",
                    "held_by": "The White Dawn",
                },
                {"general": "It fell in 994.", "held_by": None},
                {
                    "category": "general",
                    "text": "Stars fell.",
                    "held_by": "The Unknown Sect",
                },
            ],
        }
    )
    _name, _age, facts = parse_create_reply(
        reply, "lore", Calendar(), 1020, holder=lambda name: holders.get(name.lower())
    )
    assert [(f.text, f.held_by) for f in facts] == [
        ("Every owl lost its sight.", s.dawn),
        ("It fell in 994.", None),
        ("Stars fell.", None),
    ]


async def test_preview_held_by_written_on_accept(world, spheres_world):
    """Through a preview: the holder is matched against the world (its
    everyday name too), and accept writes `{"held_by": id}`."""

    s = spheres_world
    reply = json.dumps(
        {
            "name": "The Night of Feathers",
            "facts": [
                {
                    "category": "general",
                    "text": "Every owl lost its sight.",
                    "held_by": "White Dawn",
                },
                {
                    "category": "general",
                    "text": "The river froze.",
                    "held_by": "Moscavia",
                },
                {"category": "general", "text": "It fell in 994."},
            ],
            "names": [],
        }
    )
    client = MockClient("test")
    async with MockClientContext():
        _queue(reply, "A night of blindness.")
        preview = await preview_thing(world, "lore", "a night of blindness", {}, client)
    assert [f.held_by for f in preview.facts] == [s.dawn, s.tsardom, None]

    thing_id = accept_preview(world, preview)
    facts = sorted(world.view().thing(thing_id).facts, key=lambda f: f.created)
    assert [(f.text, (f.origin or {}).get("held_by")) for f in facts] == [
        ("Every owl lost its sight.", s.dawn),
        ("The river froze.", s.tsardom),
        ("It fell in 994.", None),
    ]


def test_repoint_carries_held_by(world, spheres_world):
    """A stub merged into its entry hands over what it held: a fact held by
    the stub is held by the entry after, and so is a belief the stub held
    of itself, moved with its facts."""

    from talemate.worldplay.repoint import repoint_stub

    s = spheres_world
    with world.revision(Source.manual()) as rev:
        stub = rev.create_thing(
            "sphere", fields={"name": "The Dawn Faith", "stub": {"ignored": False}}
        )
        lore = rev.create_thing("lore", fields={"name": "The Vigil"})
        held = rev.add_fact(
            lore,
            "general",
            "Owls keep the vigil.",
            origin={"held_by": stub, "drawer": "d0000001"},
        )
        rev.add_fact(stub, "about", "It sees all.", origin={"held_by": stub})

    repoint_stub(world, stub, s.dawn)

    view = world.view()
    fact = next(f for f in view.thing(lore).facts if f.fact_id == held)
    assert fact.origin == {"held_by": s.dawn, "drawer": "d0000001"}
    moved = next(f for f in view.thing(s.dawn).facts if f.text == "It sees all.")
    assert moved.origin == {"held_by": s.dawn}


async def test_held_fact_reaches_prose_prompt(world, spheres_world):
    """A held background fact reaches the description prompt as belief
    (ruling C3); a correction that only sets or clears held-by makes the
    cached prose stale, as a text edit would."""

    from talemate.worldplay import prose_gen

    s = spheres_world
    with world.revision(Source.manual()) as rev:
        oren = rev.create_thing("character", fields={"name": "Brother Oren"})
        miracle = rev.add_fact(
            oren,
            "background",
            "His touch healed a blind child.",
            origin=with_held_by(None, s.dawn),
        )
        rev.add_fact(oren, "appearance", "A grey-feathered owl.")

    client = MockClient("test")
    async with MockClientContext():
        _queue("Brother Oren is a grey owl.")
        await prose_gen.generate_section(world, oren, "description", None, client)
    prompt = str(client.prompt_history[0]["prompt"])
    assert "The White Dawn holds that his touch healed a blind child." in prompt
    assert "A grey-feathered owl." in prompt

    cache = world.prose()

    def stale() -> bool:
        return cache.stale(
            oren,
            "description",
            None,
            prose_gen.staleness_also(world, oren, "description", None),
        )

    assert not stale()
    fact = next(f for f in world.view().thing(oren).facts if f.fact_id == miracle)
    with world.revision(Source.manual()) as rev:
        rev.correct_fact(miracle, origin=with_held_by(fact.origin, None))
    assert stale()


def test_setup_prompt_shows_held_facts_as_belief(world, spheres_world):
    """The scene-setup prompt's world things carry a held fact as belief."""

    from talemate.worldplay.setup import _world_things

    s = spheres_world
    with world.revision(Source.manual()) as rev:
        lore = rev.create_thing("lore", fields={"name": "The Vigil"})
        rev.add_fact(
            lore, "general", "Owls see in the dark.", origin={"held_by": s.dawn}
        )
    groups = dict(_world_things(world.view(), [lore]))
    assert groups["Lore"][0]["facts"] == ["The White Dawn holds: Owls see in the dark."]


def test_held_by_a_character_or_a_being(world, spheres_world):
    """A character or a being can hold a fact too; a fact that already
    says the character believes it is left as it is."""

    s = spheres_world
    with world.revision(Source.manual()) as rev:
        light = rev.create_thing(
            "being", fields={"name": "The Eternal Light", "existence": "believed"}
        )
        lore = rev.create_thing("lore", fields={"name": "The Watch"})
        by_vasha = rev.add_fact(
            lore, "general", "The vigil is pointless.", origin={"held_by": s.vasha}
        )
        self_said = rev.add_fact(
            lore,
            "general",
            "Vasha believes the vigil is pointless.",
            origin={"held_by": s.vasha},
        )
        by_light = rev.add_fact(
            lore, "general", "The vigil pleases it.", origin={"held_by": light}
        )
    view = world.view()
    owner = view.thing(lore)
    texts = {f.fact_id: held_text(view, f, owner) for f in owner.facts}
    assert texts[by_vasha] == "Vasha holds that the vigil is pointless."
    assert texts[self_said] == "Vasha believes the vigil is pointless."
    assert texts[by_light] == "The Eternal Light holds that the vigil pleases it."


def test_held_text_forms(world, spheres_world):
    """Ruling C6: a held text with a subject of its own (a name, a pronoun,
    a determiner) follows "holds that", lowered unless it opens with a
    name; one opening with a verb or anything else follows "holds:",
    its first letter kept a capital."""

    s = spheres_world
    with world.revision(Source.manual()) as rev:
        rev.create_thing("being", fields={"name": "The Light"})
        lore = rev.create_thing("lore", fields={"name": "The Miracle"})
        texts = [
            "Healed a blind child.",
            "His touch healed a blind child.",
            "The Light chose the Tsar.",
            "Kremova burned for three days.",
            "healed the lame?",
        ]
        ids = [
            rev.add_fact(lore, "general", text, origin={"held_by": s.dawn})
            for text in texts
        ]
    view = world.view()
    owner = view.thing(lore)
    by_id = {f.fact_id: held_text(view, f, owner) for f in owner.facts}
    assert [by_id[fact_id] for fact_id in ids] == [
        "The White Dawn holds: Healed a blind child.",
        "The White Dawn holds that his touch healed a blind child.",
        "The White Dawn holds that the Light chose the Tsar.",
        "The White Dawn holds that Kremova burned for three days.",
        "The White Dawn holds: Healed the lame?",
    ]
