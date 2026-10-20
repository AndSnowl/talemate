"""Reference-entry prose: background facts for consistency, the chosen
generation kind, and the template's own prefill/background rendering.

Driven by the acceptance-run probe (docs/superpowers/probes/2026-10-20-prose-register.md):
Vasha's generated description came back as a short story, and his
personality section -- given only his personality facts -- turned him
human. The fix gives each section the thing's other facts as background
(for consistency only), writes at a lower, more factual kind, and primes
the reply with "<name> is" rather than just the name."""

from talemate.prompts import Prompt
from talemate.world.dates import WorldDate
from talemate.world.store import Source
from talemate.worldplay import prose_gen

from conftest import MockClient, MockClientContext, client_responses


def _queue(*responses: str) -> None:
    for response in responses:
        client_responses.get().append(response)


async def test_generate_section_passes_other_categories_as_background(world):
    """Vasha's personality section is generated from his personality facts
    alone, but his appearance fact -- a different category -- is still
    sent, as background, so the model doesn't lose track of what he is."""

    with world.revision(Source.manual(note="setup")) as rev:
        vasha = rev.create_thing("character", fields={"name": "Vasha"})
        rev.add_fact(vasha, "appearance", "A large owl-like creature.")
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
    # the appearance fact -- a different category -- is background only
    assert "A large owl-like creature." in prompt
    assert "for consistency only" in prompt


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
    assert "Born in the year 978." in prompt


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
