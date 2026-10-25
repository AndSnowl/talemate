"""Where a thing is mentioned, the context that gives a stub being expanded,
and the prompt suggested for it."""

from talemate.world.dates import WorldDate
from talemate.world.refs import ref
from talemate.world.store import Source
from talemate.worldplay.mentions import (
    ABOUT_ENTRIES,
    KEY_FACTS,
    MENTION_FACTS,
    gather_mentions,
    mention_context,
    mentions,
    suggested_prompt,
)

ORIGIN = (
    "In 994, every person in the {tsardom} awoke as owl-folk overnight, in what "
    "Moscavians call the Night of Feathers."
)


def _owl_world(world):
    """The Tsardom of Moscavia stub, mentioned by the Owl-folk's origin fact
    among its twelve facts. Returns `(tsardom, owls, origin fact id)`."""

    with world.revision(Source.manual(note="setup")) as rev:
        tsardom = rev.create_thing(
            "place", fields={"name": "Tsardom of Moscavia", "stub": {"ignored": False}}
        )
        owls = rev.create_thing("species", fields={"name": "Owl-folk"})
        # added out of category order: key facts come in physical, instinct,
        # origin, variation, general order
        for i in range(2):
            rev.add_fact(owls, "general", f"General {i}.")
        rev.add_fact(owls, "variation", "Variation 0.")
        origin = rev.add_fact(
            owls, "origin", ORIGIN.format(tsardom=ref(tsardom, "Tsardom of Moscavia"))
        )
        rev.add_fact(owls, "origin", "Children have hatched from eggs ever since.")
        for i in range(3):
            rev.add_fact(owls, "instinct", f"Instinct {i}.")
        for i in range(4):
            rev.add_fact(owls, "physical", f"Physical {i}.")
    return tsardom, owls, origin


def test_mentions_render_and_skip_the_thing_itself(world):
    tsardom, owls, origin = _owl_world(world)
    with world.revision(Source.manual(note="more")) as rev:
        rev.add_fact(tsardom, "general", f"The {ref(tsardom)} is cold.")
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        # an ended fact still counts as a mention
        ended = rev.add_fact(
            vasha,
            "background",
            f"Left {ref(tsardom, 'Moscavia')} as a child.",
            valid_from=WorldDate.of(990),
            valid_until=WorldDate.of(1000),
        )
    view = world.view(None)

    found = mentions(view, tsardom)
    assert [(m.owner_id, m.fact_id) for m in found] == [(owls, origin), (vasha, ended)]
    first = found[0]
    assert first.owner_name == "Owl-folk"
    assert first.owner_kind == "species"
    assert first.category == "origin"
    assert first.text == ORIGIN.format(tsardom="Tsardom of Moscavia")
    assert found[1].text == "Left Moscavia as a child."


def _heads(texts: list[str]) -> list[str]:
    """The first word of each fact text: its category in these tests (facts
    of one category have no set order among themselves)."""

    return [text.split()[0] for text in texts]


def test_mentions_and_context_capped(world):
    tsardom, owls, origin = _owl_world(world)
    view = world.view(None)

    # one mentioning species: its mention, then its key facts in category
    # order without the mentioning fact, capped at 8
    [(heading, facts)] = mention_context(view, tsardom)
    assert heading == "Owl-folk (species)"
    assert facts[0] == ORIGIN.format(tsardom="Tsardom of Moscavia")
    assert _heads(facts[1:]) == [*["Physical"] * 4, *["Instinct"] * 3, "Children"]

    gathered = gather_mentions(view, tsardom)
    assert [m.fact_id for m in gathered.mentioned] == [origin]
    assert [(a.id, a.name, a.kind) for a in gathered.about] == [
        (owls, "Owl-folk", "species")
    ]
    assert gathered.about[0].facts == facts[1:]
    assert len(gathered.about[0].facts) == KEY_FACTS == 8

    # five more entries mention it. Most mentions come first (ties by name),
    # up to 12 mentions; only the first three entries get key facts, places
    # in their own category order
    with world.revision(Source.manual(note="many")) as rev:
        town = rev.create_thing("place", fields={"name": "Barrowford"})
        rev.add_fact(town, "general", "General: a town of barges.")
        rev.add_fact(town, "law", "Law: no flying after dark.")
        rev.add_fact(town, "description", "Description: grey roofs.")
        for i in range(3):
            rev.add_fact(town, "history", f"History: raided by the {ref(tsardom)} {i}.")
        for n in reversed(range(4)):
            other = rev.create_thing("lore", fields={"name": f"Lore {n}"})
            for i in range(3 if n == 0 else 2):
                rev.add_fact(
                    other, "general", f"Lore {n} names the {ref(tsardom)} {i}."
                )
            rev.add_fact(other, "general", f"Key: lore {n}.")
    view = world.view(None)

    gathered = gather_mentions(view, tsardom)
    assert len(gathered.mentioned) == MENTION_FACTS == 12
    # Barrowford and Lore 0 (3 each), Lore 1-3 (2 each), Owl-folk (1): the
    # cap cuts the Owl-folk's mention
    assert [m.owner_name for m in gathered.mentioned] == [
        *["Barrowford"] * 3,
        *["Lore 0"] * 3,
        *["Lore 1"] * 2,
        *["Lore 2"] * 2,
        *["Lore 3"] * 2,
    ]
    assert len(gathered.about) == ABOUT_ENTRIES == 3
    assert [a.name for a in gathered.about] == ["Barrowford", "Lore 0", "Lore 1"]
    assert _heads(gathered.about[0].facts) == ["Description:", "Law:", "General:"]
    assert gathered.about[1].facts == ["Key: lore 0."]

    context = mention_context(view, tsardom)
    assert [heading for heading, _facts in context] == [
        "Barrowford (place)",
        "Lore 0 (lore)",
        "Lore 1 (lore)",
        "Lore 2 (lore)",
        "Lore 3 (lore)",
    ]
    assert _heads(context[0][1]) == [
        *["History:"] * 3,
        "Description:",
        "Law:",
        "General:",
    ]
    assert sorted(context[3][1]) == [
        "Lore 2 names the Tsardom of Moscavia 0.",
        "Lore 2 names the Tsardom of Moscavia 1.",
    ]
    assert sum(len(facts) for _heading, facts in context) == 12 + 3 + 1 + 1


def test_suggested_prompt_from_mentions(world):
    tsardom, _owls, _origin = _owl_world(world)
    view = world.view(None)

    assert suggested_prompt(view, tsardom) == (
        "Tsardom of Moscavia: " + ORIGIN.format(tsardom="Tsardom of Moscavia")
    )

    with world.revision(Source.manual(note="more")) as rev:
        town = rev.create_thing("place", fields={"name": "Barrowford"})
        # dated, so they come in this order
        rev.add_fact(
            town,
            "general",
            f"A river town in the south of {ref(tsardom, 'Moscavia')}",
            valid_from=WorldDate.of(1000),
        )
        for i in range(6):
            rev.add_fact(
                town,
                "history",
                f"In year {i}, barges from {ref(tsardom, 'Moscavia')} carried amber, "
                "salt and furs down the long river to the sea.",
                valid_from=WorldDate.of(1001 + i),
            )
        lonely = rev.create_thing(
            "lore", fields={"name": "Silence", "stub": {"ignored": False}}
        )
    view = world.view(None)

    # the most-mentioning entry first; a fact without a full stop gets one;
    # cut at the end of a whole sentence, within 400 characters
    prompt = suggested_prompt(view, tsardom)
    assert prompt.startswith(
        "Tsardom of Moscavia: A river town in the south of Moscavia. "
        "In year 0, barges from Moscavia carried amber"
    )
    assert 300 < len(prompt) <= 400
    assert prompt.endswith("down the long river to the sea.")

    # a stub nothing mentions suggests its bare name
    assert suggested_prompt(view, lonely) == "Silence"


def test_suggested_prompt_without_a_sentence_end(world):
    with world.revision(Source.manual(note="setup")) as rev:
        stub = rev.create_thing(
            "place", fields={"name": "St. Sophia", "stub": {"ignored": False}}
        )
        town = rev.create_thing("place", fields={"name": "Barrowford"})
        rev.add_fact(
            town, "general", f"Pilgrims walk to {ref(stub)} " + "and on " * 80 + "."
        )
    prompt = suggested_prompt(world.view(None), stub)
    # "St." isn't a sentence end: with none, the cut is at a whole word
    assert prompt.startswith("St. Sophia: Pilgrims walk to St. Sophia and on")
    assert prompt.endswith("and on…")
    assert len(prompt) <= 400


def test_context_names_carry_everyday_names(world):
    tsardom, owls, _origin = _owl_world(world)
    with world.revision(Source.manual(note="aka")) as rev:
        rev.set_field(
            owls,
            "aka",
            [{"name": "Owls", "tag": "common", "everyday": True}],
            None,
        )
    view = world.view(None)

    [(heading, _facts)] = mention_context(view, tsardom)
    assert heading == "Owl-folk (species, usually called Owls)"
    gathered = gather_mentions(view, tsardom)
    assert gathered.mentioned[0].owner_everyday == "Owls"
    assert gathered.about[0].everyday == "Owls"


def test_heritage_origin_facts_outlast_the_cap(world):
    """A heritage's origin facts are history -- often of the very place
    being expanded -- so the key-fact cap never cuts them: the connections
    flow run (docs/superpowers/probes/2026-10-21-connections-flow.md) lost
    the species' "capital in Moscow" origin fact to the cap, and the
    Tsardom expanded from its stub put its capital elsewhere."""

    with world.revision(Source.manual(note="setup")) as rev:
        tsardom = rev.create_thing(
            "place", fields={"name": "Tsardom of Moscavia", "stub": {"ignored": False}}
        )
        owls = rev.create_thing("species", fields={"name": "Owl-folk"})
        rev.add_fact(owls, "origin", ORIGIN.format(tsardom=ref(tsardom)))
        for n in range(5):
            rev.add_fact(owls, "physical", f"Physical {n}.")
        for n in range(3):
            rev.add_fact(owls, "instinct", f"Instinct {n}.")
        rev.add_fact(owls, "origin", "Origin: Moscavia's capital was Moscow.")
        rev.add_fact(owls, "general", "General: hollow bones.")

    [(_, facts)] = mention_context(world.view(None), tsardom)
    # the mention, the first 8 key facts, then the origin fact the cap cut;
    # the general fact stays cut
    assert _heads(facts[1:]) == [*["Physical"] * 5, *["Instinct"] * 3, "Origin:"]


def test_suggested_prompt_of_a_filed_stub(world):
    """A stub filed in an entry (the Dawn Vigil, a rite of the White Dawn)
    suggests its own fact first, then what it's filed in, as the sheet
    reads a filing ("Rite of the White Dawn."; "Part of ..." with no
    role), then what mentions it: in the spheres Task 10 session the
    Vigil's prompt led with a character's "but..." exception, and the
    model wrote the Vigil around her."""

    with world.revision(Source.manual(note="setup")) as rev:
        dawn = rev.create_thing("lore", fields={"name": "The White Dawn"})
        peak = rev.create_thing("place", fields={"name": "Dawn Peak"})
        vigil = rev.create_thing(
            "lore",
            fields={
                "name": "The Dawn Vigil",
                "stub": {"ignored": False},
                "filings": [
                    {"target": dawn, "role": "rite"},
                    {"target": peak, "role": "held at"},
                ],
            },
        )
        rev.add_fact(vigil, "general", "A silent prayer at first light")
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        rev.add_fact(
            vasha, "ties", f"She keeps {ref(vigil, 'the Dawn Vigil')} out of habit."
        )
    view = world.view(None)

    assert suggested_prompt(view, vigil) == (
        "The Dawn Vigil: A silent prayer at first light. Rite of the White "
        "Dawn. Held at Dawn Peak. She keeps the Dawn Vigil out of habit."
    )

    with world.revision(Source.manual(note="no role")) as rev:
        rev.set_field(vigil, "filings", [{"target": dawn}], None)
    assert "Part of the White Dawn." in suggested_prompt(world.view(None), vigil)


def _church_world(world):
    """A faith, the Church of the Deep, whose beliefs name the stub Veles;
    Veles' own fact is the church's belief too. Returns `(church, veles)`."""

    with world.revision(Source.manual(note="setup")) as rev:
        veles = rev.create_thing(
            "being", fields={"name": "Veles", "stub": {"ignored": False}}
        )
        church = rev.create_thing(
            "lore", fields={"name": "Church of the Deep", "hint": "religion"}
        )
        rev.add_fact(
            church, "belief", f"{ref(veles, 'Veles')} wept the rivers into being."
        )
        rev.add_fact(church, "belief", "The drowned are reborn as fish.")
        rev.add_fact(church, "general", "Its priests wear green.")
        rev.add_fact(
            veles,
            "nature",
            "Veles sleeps beneath the lake.",
            origin={"held_by": church},
        )
    return church, veles


def test_held_facts_reach_the_expand_context_as_held(world):
    """Final review I2: a faith's beliefs reach "Mentioned elsewhere",
    "About those" and the suggested prompt worded as held, never as world
    truth."""

    _church, veles = _church_world(world)
    view = world.view(None)
    ((heading, facts),) = mention_context(view, veles)
    assert heading == "Church of the Deep (lore)"
    assert "Church of the Deep holds that Veles wept the rivers into being." in facts
    assert "Church of the Deep holds that the drowned are reborn as fish." in facts
    assert "Its priests wear green." in facts
    assert "Veles wept the rivers into being." not in facts

    prompt = suggested_prompt(view, veles)
    assert prompt.startswith(
        "Veles: Church of the Deep holds that Veles sleeps beneath the lake."
    )
    assert "Church of the Deep holds that Veles wept the rivers into being." in prompt
    held = "Church of the Deep holds that Veles wept the rivers into being."
    assert "Veles wept the rivers" not in prompt.replace(held, "")


def test_key_facts_come_in_written_order_within_a_category(world):
    """Final review (T12 nondeterminism): within a category, "About those"
    lists an entry's facts in the order they were written, never in its
    random fact ids' order, so one world always gives one prompt."""

    with world.revision(Source.manual(note="setup")) as rev:
        stub = rev.create_thing(
            "place", fields={"name": "Kitezh", "stub": {"ignored": False}}
        )
        lake = rev.create_thing("place", fields={"name": "Lake Svetloyar"})
        rev.add_fact(lake, "general", f"{ref(stub, 'Kitezh')} sank beneath it.")
    texts = [f"Fact {i}." for i in range(8)]
    for text in texts:
        # one revision each, and several in one: both keep written order
        with world.revision(Source.manual(note=text)) as rev:
            rev.add_fact(lake, "general", text)
    with world.revision(Source.manual(note="more")) as rev:
        more = [f"More {i}." for i in range(3)]
        for text in more:
            rev.add_fact(lake, "description", text)
    (about,) = gather_mentions(world.view(None), stub).about
    # a place's descriptions come before its general facts
    assert about.facts == (more + texts)[:KEY_FACTS]
