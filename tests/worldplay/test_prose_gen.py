"""Reference-entry prose: background facts for consistency, the chosen
generation kind, and the template's own prefill/background rendering.

Driven by the acceptance-run probe (docs/superpowers/probes/2026-10-20-prose-register.md):
Vasha's generated description came back as a short story, and his
personality section -- given only his personality facts -- turned him
human. The fix gives each section the thing's other facts as background
(for consistency only), writes at a lower, more factual kind, and primes
the reply with "<name> is" rather than just the name."""

from talemate.prompts import Prompt
from talemate.world.calendar import Calendar, Era
from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay import prose_gen

from conftest import MockClient, MockClientContext, client_responses


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


async def test_generate_section_passes_other_categories_as_background(world):
    """Vasha's personality section is generated from his personality facts
    alone, but his speech fact -- a different category -- is still sent, as
    background, so the model doesn't lose track of what he is. His
    appearance fact is the one exception: left out of personality's
    background entirely, so the model stops restating it instead of
    writing personality (acceptance probe:
    docs/superpowers/probes/2026-10-21-personality-and-actions.md)."""

    with world.revision(Source.manual(note="setup")) as rev:
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        rev.add_fact(vasha, "appearance", "A large owl-like creature.")
        rev.add_fact(vasha, "speech", "Speaks in a low rumble.")
        rev.add_fact(vasha, "personality", "Quiet and observant.")

    client = MockClient("test")
    async with MockClientContext():
        _queue("Vasha is quiet and observant.")
        text = await prose_gen.generate_section(
            world, vasha, "personality", None, client
        )

    assert text == "Vasha is quiet and observant."
    assert len(client.prompt_history) == 1
    prompt = str(client.prompt_history[0]["prompt"])
    # the personality fact is in the entry's own facts
    assert "Quiet and observant." in prompt
    # the speech fact -- a different category -- is background only
    assert "Speaks in a low rumble." in prompt
    assert "for consistency only" in prompt
    # the appearance fact is left out of personality's background entirely
    assert "A large owl-like creature." not in prompt


async def test_generate_section_background_includes_core_fields(world):
    """A place's single `description` section covers every one of its fact
    categories, so there are no "other" facts to carry as background --
    but its core fields (here, its own `kind` and `name`) still are."""

    with world.revision(Source.manual(note="setup")) as rev:
        lowmere = rev.create_thing(
            "place", fields={"name": "Lowmere", "kind": "harbor town"}
        )
        rev.add_fact(lowmere, "description", "Half its streets are flooded.")

    client = MockClient("test")
    async with MockClientContext():
        _queue("Lowmere is half flooded.")
        await prose_gen.generate_section(world, lowmere, "description", None, client)

    prompt = str(client.prompt_history[0]["prompt"])
    assert "A harbor town." in prompt
    assert "Named Lowmere." in prompt


async def test_generate_section_background_includes_born(world):
    with world.revision(Source.manual(note="setup")) as rev:
        vasha = rev.create_thing(
            "character", fields={"name": "Vasha", "born": WorldDate.of(978)}
        )
        rev.add_fact(vasha, "appearance", "A large owl-like creature.")
        rev.add_fact(vasha, "personality", "Quiet and observant.")

    client = MockClient("test")
    async with MockClientContext():
        _queue("Vasha is quiet and observant.")
        await prose_gen.generate_section(world, vasha, "personality", None, client)

    prompt = str(client.prompt_history[0]["prompt"])
    assert "Born in 978." in prompt


async def test_generate_section_background_born_uses_the_world_calendar(world):
    """Review-round fix: the global constraint is that a date is always
    formatted by the world's `Calendar` (eras and all), the way
    `characters.py`'s own `born` label already is -- the background was
    instead formatting it as a bare `to_datetime().year`, which skips the
    era rename `Calendar.format` applies."""

    world.set_calendar(
        Calendar(eras=[Era(name="Age of Rivers", abbreviation="AR", start_year=300)])
    )
    with world.revision(Source.manual(note="setup")) as rev:
        vasha = rev.create_thing(
            "character", fields={"name": "Vasha", "born": WorldDate.of(305)}
        )
        rev.add_fact(vasha, "appearance", "A large owl-like creature.")
        rev.add_fact(vasha, "personality", "Quiet and observant.")

    client = MockClient("test")
    async with MockClientContext():
        _queue("Vasha is quiet and observant.")
        await prose_gen.generate_section(world, vasha, "personality", None, client)

    prompt = str(client.prompt_history[0]["prompt"])
    # 305 is the 6th year of the Age of Rivers (start_year=300)
    assert "Born in 6 AR." in prompt
    assert "305" not in prompt


async def test_generate_section_uses_the_analyze_kind(world):
    """A reference entry restates known facts -- it isn't an invention, so
    it's asked for at a lower, more factual kind than "create"."""

    with world.revision(Source.manual(note="setup")) as rev:
        lowmere = rev.create_thing("place", fields={"name": "Lowmere"})
        rev.add_fact(lowmere, "description", "Half its streets are flooded.")

    client = MockClient("test")
    async with MockClientContext():
        _queue("Lowmere is half flooded.")
        await prose_gen.generate_section(world, lowmere, "description", None, client)

    assert client.prompt_history[0]["kind"] == prose_gen.PROSE_PROMPT_KIND
    assert prose_gen.PROSE_PROMPT_KIND == "analyze"


async def test_render_section_empty_check_matches_the_new_prefill(world):
    """The template primes the reply with "<name> is"; a reply that adds
    nothing past that prefix comes back empty, the same way an empty
    "<name>"-only reply used to."""

    client = MockClient("test")
    async with MockClientContext():
        _queue("Vasha is")
        text = await prose_gen.render_section(
            "character", "Vasha", "personality", ["Quiet."], client
        )

    assert text == ""


def test_template_renders_prefill_and_background_block():
    vars = {
        "facts": ["Quiet and observant by nature."],
        "background": ["A large owl-like creature.", "Named Vasha."],
        "kind": "character",
        "section": "personality",
        "name": "Vasha",
    }
    text = Prompt.get("world.thing-prose", vars).render()

    assert (
        "Who the character is (for consistency only; do NOT describe these here):"
        in text
    )
    assert "A large owl-like creature." in text
    assert "Named Vasha." in text
    assert "Facts for this entry:" in text
    assert "Quiet and observant by nature." in text
    assert "<|BOT|>Vasha is" in text


def test_template_omits_background_block_when_empty():
    vars = {
        "facts": ["Half its streets are flooded."],
        "background": [],
        "kind": "place",
        "section": "description",
        "name": "Lowmere",
    }
    text = Prompt.get("world.thing-prose", vars).render()

    assert "Who the" not in text
    assert "for consistency only" not in text
    assert "<|BOT|>Lowmere is" in text


# -- inheritance (phase 2 plan B) --------------------------------------------


def _capture_requests(monkeypatch) -> list[dict]:
    """Replace the prose request with one that records its vars and
    answers "<name> is drawn."."""

    requests: list[dict] = []

    async def fake_request(template, client, kind, vars):
        requests.append(vars)
        return "", {"response": f"{vars['name']} is drawn."}

    monkeypatch.setattr(prose_gen.Prompt, "request", fake_request)
    return requests


def test_inherited_categories():
    assert prose_gen.inherited_categories("description") == {
        "species": ("physical", "variation"),
        "race": ("physical", "variation"),
        "mix": ("physical", "variation"),
        "culture": ("dress",),
    }
    assert prose_gen.inherited_categories("personality") == {
        "species": ("instinct",),
        "race": ("instinct",),
        "mix": ("instinct",),
        "culture": ("customs", "belief"),
    }


async def test_character_description_includes_inherited_physical(
    world, heritage_world, monkeypatch
):
    requests = _capture_requests(monkeypatch)

    await prose_gen.generate_section(
        world, heritage_world.vasha, "description", None, object()
    )

    facts = requests[0]["facts"]
    assert facts == ["Blue eyes.", "White plumage.", "Wings in place of arms."]
    assert "Yellow eyes." not in facts
    # the instinct fact belongs to personality: background only; the
    # culture's customs aren't inherited (cultures left the lineage)
    background = requests[0]["background"]
    assert "Hunts at dusk." in background
    assert "Name their boats." not in background
    assert "Yellow eyes." not in background


async def test_personality_includes_instinct_not_customs(
    world, heritage_world, monkeypatch
):
    requests = _capture_requests(monkeypatch)

    await prose_gen.generate_section(
        world, heritage_world.vasha, "personality", None, object()
    )

    facts = requests[0]["facts"]
    # the culture's customs no longer pass down: cultures left the lineage
    assert facts == ["Quiet and observant.", "Hunts at dusk."]
    # the heritage line keeps identity in view; the body does not (acceptance
    # probe: docs/superpowers/probes/2026-10-21-personality-and-actions.md)
    assert "Heritage: Snowy, Owl-folk." in requests[0]["background"]
    assert "Wings in place of arms." not in requests[0]["background"]


async def test_personality_background_excludes_appearance_and_inherited_body(
    world, heritage_world, monkeypatch
):
    """The personality section's background leaves out Vasha's own
    appearance fact and the species'/race's physical and variation facts
    he inherits -- the owner's acceptance-run complaint was that these made
    the model restate appearance instead of writing personality. The
    heritage line and his other facts (here, a background fact) still get
    through, so identity survives (acceptance probe:
    docs/superpowers/probes/2026-10-21-personality-and-actions.md)."""

    with world.revision(Source.manual(note="more")) as rev:
        rev.add_fact(heritage_world.vasha, "background", "Keeps the lighthouse log.")

    requests = _capture_requests(monkeypatch)
    await prose_gen.generate_section(
        world, heritage_world.vasha, "personality", None, object()
    )

    background = requests[0]["background"]
    assert "Blue eyes." not in background
    assert "Wings in place of arms." not in background
    assert "White plumage." not in background
    assert "Heritage: Snowy, Owl-folk." in background
    assert "Keeps the lighthouse log." in background


async def test_description_background_still_includes_inherited_body(
    world, heritage_world, monkeypatch
):
    """The description section's background is unchanged by the
    personality fix -- it still carries whatever the character inherits
    that isn't mapped to description's own facts (here, the species'
    instinct; the culture's customs aren't inherited since cultures left
    the lineage)."""

    requests = _capture_requests(monkeypatch)
    await prose_gen.generate_section(
        world, heritage_world.vasha, "description", None, object()
    )

    background = requests[0]["background"]
    assert "Hunts at dusk." in background
    assert "Name their boats." not in background


async def test_species_page_prose_uses_all_facts(world, heritage_world, monkeypatch):
    requests = _capture_requests(monkeypatch)
    with world.revision(Source.manual()) as rev:
        rev.add_fact(heritage_world.owl_folk, "origin", "First flew from the north.")

    assert prose_gen.sections_for("species") == ("description",)
    await prose_gen.ensure_prose(world, heritage_world.owl_folk, None, object())

    assert len(requests) == 1
    assert sorted(requests[0]["facts"]) == [
        "First flew from the north.",
        "Hunts at dusk.",
        "Wings in place of arms.",
    ]


async def test_race_prose_gets_inherited_facts_as_background(
    world, heritage_world, monkeypatch
):
    requests = _capture_requests(monkeypatch)

    await prose_gen.generate_section(
        world, heritage_world.snowy, "description", None, object()
    )

    assert sorted(requests[0]["facts"]) == ["White plumage.", "Yellow eyes."]
    background = requests[0]["background"]
    assert "Wings in place of arms." in background
    assert "Hunts at dusk." in background
    assert "Heritage: Owl-folk." in background


async def test_ensure_prose_regenerates_after_species_change(
    world, heritage_world, monkeypatch
):
    requests = _capture_requests(monkeypatch)
    vasha = heritage_world.vasha

    await prose_gen.ensure_prose(world, vasha, None, object())
    assert len(requests) == 2
    await prose_gen.ensure_prose(world, vasha, None, object())
    assert len(requests) == 2

    with world.revision(Source.manual()) as rev:
        rev.add_fact(heritage_world.owl_folk, "physical", "Silent flight.")
    await prose_gen.ensure_prose(world, vasha, None, object())

    assert len(requests) == 4
    assert "Silent flight." in requests[2]["facts"]


async def test_ensure_prose_regenerates_after_race_deleted(
    world, heritage_world, monkeypatch
):
    requests = _capture_requests(monkeypatch)
    vasha = heritage_world.vasha

    await prose_gen.ensure_prose(world, vasha, None, object())
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(heritage_world.snowy)
    await prose_gen.ensure_prose(world, vasha, None, object())

    assert len(requests) == 4
    # the race is gone, and its species with it
    assert requests[2]["facts"] == ["Blue eyes."]


async def test_species_fact_splits_the_cached_stretch(
    world, heritage_world, monkeypatch
):
    """A dated species fact is a boundary in the character's stretches, so
    the prose cached for a scene before it doesn't cover a scene after."""

    _capture_requests(monkeypatch)
    with world.revision(Source.manual()) as rev:
        rev.add_fact(
            heritage_world.owl_folk,
            "physical",
            "Grey crests.",
            valid_from=WorldDate.of(1000),
        )

    await prose_gen.generate_section(
        world, heritage_world.vasha, "description", WorldDate.of(990), object()
    )

    cached = world.prose().get(heritage_world.vasha, "description", WorldDate.of(990))
    assert cached is not None
    assert cached.stretch_end is not None
    assert cached.stretch_end.instant == WorldDate.of(1000).instant


async def test_sphere_description_leaves_out_statements_and_timeline(world):
    """Ruling P18: a sphere's description (its summary, ruling P1) is
    written from its `about` facts and its template, never from its
    statements or timeline -- in its facts or its background -- so Fill
    and dated declarations can't turn the summary into a retelling of its
    drawers (spheres Task 10 session: 53 words grew to 126)."""

    with world.revision(Source.manual(note="setup")) as rev:
        dawn = rev.create_thing(
            "sphere", fields={"name": "The White Dawn", "template": "religion"}
        )
        rev.add_fact(dawn, "about", "The state church of Moscavia.")
        rev.add_fact(dawn, "statement", "Snowy owl-folk are the purest of the folk.")
        rev.add_fact(
            dawn,
            "timeline",
            "Issued the Doctrine of Separation.",
            valid_from=WorldDate.of(1019),
        )

    client = MockClient("test")
    async with MockClientContext():
        _queue("The White Dawn is the state church of Moscavia.")
        await prose_gen.generate_section(world, dawn, "description", None, client)

    prompt = str(client.prompt_history[0]["prompt"])
    assert "The state church of Moscavia." in prompt
    assert "A religion sphere." in prompt
    assert "purest of the folk" not in prompt
    assert "Doctrine of Separation" not in prompt


async def test_place_sphere_description_leaves_out_statements_and_timeline(world):
    """A place that is a sphere is described from its place facts: its
    statements and timeline feed its sphere's key facts, not its prose."""

    with world.revision(Source.manual(note="setup")) as rev:
        tsardom = rev.create_thing(
            "place",
            fields={"name": "Moscavia", "kind": "country", "template": "nation"},
        )
        rev.add_fact(tsardom, "description", "A northern realm of pine forest.")
        rev.add_fact(tsardom, "statement", "Only owl-folk may hold land.")
        rev.add_fact(
            tsardom, "timeline", "Crowned the first Tsar.", valid_from=WorldDate.of(990)
        )

    client = MockClient("test")
    async with MockClientContext():
        _queue("Moscavia is a northern realm.")
        await prose_gen.generate_section(world, tsardom, "description", None, client)

    prompt = str(client.prompt_history[0]["prompt"])
    assert "A northern realm of pine forest." in prompt
    assert "A nation sphere." in prompt
    assert "Only owl-folk may hold land." not in prompt
    assert "Crowned the first Tsar." not in prompt


async def test_sphere_with_nothing_to_describe_keeps_its_summary(world):
    """A sphere whose summary came from its core has no fact its prose
    reads (P18): regenerating it (a rename, say) asks the model nothing
    and keeps the summary, rather than caching an empty one."""

    with world.revision(Source.manual(note="setup")) as rev:
        dawn = rev.create_thing(
            "sphere", fields={"name": "The White Dawn", "template": "religion"}
        )
        rev.add_fact(dawn, "statement", "Snowy owl-folk are the purest of the folk.")
    start, end = prose_gen.stretch_containing(world, dawn, None)
    world.prose().put(dawn, "description", start, end, "The church of the dawn.")
    with world.revision(Source.manual(note="rename")) as rev:
        rev.set_field(dawn, "name", "The Pale Dawn", None)

    client = MockClient("test")
    async with MockClientContext():
        text = await prose_gen.generate_section(
            world, dawn, "description", None, client
        )

    assert client.prompt_history == []
    assert text == "The church of the dawn."
    assert world.prose().get(dawn, "description", None).text == text
