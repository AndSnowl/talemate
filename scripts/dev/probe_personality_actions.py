"""Throwaway probe: personality prose and `@` action following (fantasymate
phase 2 plan B, the owner's acceptance run).

Probe 1, personality prose describing appearance. A world in a temp dir
with Tova (a Snowy owl-folk bookkeeper) and Marn (a Half-orc smith, of a
mix of Lowlander and Orc), each with appearance, background, personality
and speech facts. Each one's personality section is rendered through
`prose_gen.render_section` (the real `world/thing-prose.jinja2`, at the
"analyze" kind) from the section's real facts (`prose_gen._section_facts`)
with three backgrounds:

- A: today's, exactly as `generate_section` builds it;
- B: today's without appearance-type lines -- the character's own
  `appearance` facts and the `physical` and `variation` facts it inherits
  from a species, race or mix -- keeping the identity lines (heritage,
  name, born) and the rest of its facts;
- C: the identity lines alone.

Probe 2, `@` action following. An `@ ...` line from the player goes
through the `scene/process-input` module, which strips the `@` and runs
`agents/conversation/Generate` for the player's character with the text
as its `instruction` -- that is, `ConversationAgent.converse(actor,
instruction=...)`, which this probe calls directly. Tova is the player, at
the Lantern Post with Ilse and Corvin (invented humans), after an intro
that plants three hooks (a humming cellar door, Corvin's brass device,
dusk). Three actions go against her curiosity or her kind's instincts,
with a stated reason; each runs twice from the same history under:

- A: today's World block, with its cast lines;
- B: the cast lines' header reworded to cover bodies only, with the
  player's stated actions taking precedence;
- C: no cast lines (the World block without them, as stock-like as a
  world scene gets).

`--only late` is a follow-up: actions 2 and 3 under A again, twice each,
with the acting instructions (which carry the action) moved after the
scene history. `conversation/dialogue.jinja2` puts them before the history
while it is under 1024 tokens, as it is early in a scene; the follow-up
renders a copy of that template with the threshold at 0, through
`PrependTemplateDirectories`. It appends to an existing OUT.json.

Every call's prompt and reply goes to the output JSON. Not a test: it
calls the network. One GPU, so calls run one after another::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_personality_actions.py OUT.json'

Findings: docs/superpowers/probes/2026-10-21-personality-and-actions.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

# the heritage play probe's harness: config, recording client, loading
import probe_heritage_play as harness  # noqa: E402

import talemate.instance as instance  # noqa: E402
import talemate.worldplay.context as context  # noqa: E402
from talemate.context import ActiveScene  # noqa: E402
from talemate.prompts.base import PrependTemplateDirectories  # noqa: E402
from talemate.world import heritage  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.kinds import HERITAGE_KINDS  # noqa: E402
from talemate.world.store import Source, World  # noqa: E402
from talemate.worldplay import prose_gen  # noqa: E402
from talemate.worldplay.characters import character_from_world  # noqa: E402
from talemate.worldplay.persistence import close_world_scene  # noqa: E402
from talemate.worldplay.setup import plan_scene, start_scene  # noqa: E402

START = WorldDate.of(520)
PROSE_REPEATS = {"A": 3, "B": 3, "C": 2}
ACTION_REPEATS = 2

OWL_FACTS = [
    ("physical", "Owl-folk have broad feathered wings in place of arms."),
    (
        "physical",
        "Owl-folk use the talons of their feet as hands: to grip, carry, "
        "write and eat.",
    ),
    ("physical", "Owl-folk have large, forward-facing yellow eyes."),
    ("physical", "Owl-folk have a hooked beak and soft, silent feathers."),
    (
        "instinct",
        "Owl-folk are crepuscular: drowsy at midday, most alert at dusk and dawn.",
    ),
    (
        "instinct",
        "Owl-folk turn their whole head to look at something, rather than "
        "moving their eyes.",
    ),
]
SNOWY_FACTS = [
    ("variation", "Snowy owl-folk have white plumage flecked with black."),
    (
        "physical",
        "Snowy owl-folk are feathered down to their talons and shrug off cold.",
    ),
]
TOVA_FACTS = [
    ("appearance", "Tova's left wing bears a ragged notch from an old snare."),
    ("appearance", "Tova wears small brass spectacles perched on her beak."),
    ("appearance", "Tova's breast feathers are stained with ink."),
    ("background", "Tova keeps the books at the Lantern Post, a courier waystation."),
    ("background", "Tova grew up in the northern rookeries."),
    ("personality", "Tova is endlessly curious."),
    (
        "personality",
        "Tova is meticulous with numbers and hates leaving work unfinished.",
    ),
    ("personality", "Tova is fiercely loyal to Ilse."),
    ("personality", "Tova is wary of strangers."),
    ("speech", "Speaks softly, in precise, careful words."),
]

HUMAN_FACTS = [
    ("physical", "Humans have bare skin and hair on their heads."),
]
LOWLANDER_FACTS = [
    ("variation", "Lowlanders are stocky, with ruddy skin and brown hair."),
]
ORC_FACTS = [
    (
        "physical",
        "Orcs have grey-green skin, tusks jutting from the lower jaw and heavy brows.",
    ),
    ("physical", "Orcs stand head and shoulders taller than humans."),
    ("instinct", "Orcs have a keen sense of smell."),
    ("instinct", "Orcs are quick to anger when cornered."),
]
HALF_ORC_FACTS = [
    ("variation", "Half-orcs have small tusks and skin from olive to grey-green."),
]
MARN_FACTS = [
    ("appearance", "Marn has a broken left tusk and a shaved head."),
    ("appearance", "Marn has burn scars across both forearms."),
    ("appearance", "Marn wears a scorched leather smith's apron."),
    ("background", "Marn runs the forge in Wetherby."),
    ("background", "Marn was raised by his Lowlander mother."),
    ("personality", "Marn is patient and gentle with animals."),
    ("personality", "Marn is slow to trust and holds grudges."),
    ("personality", "Marn laughs loudly and often."),
    ("speech", "Speaks bluntly, in a deep rumble."),
]

SETUP = {
    "player": "Tova",
    "characters": [
        {"name": "Tova"},
        {
            "name": "Ilse",
            "facts": [
                "A young human woman who runs the Lantern Post.",
                "Tova's closest friend.",
            ],
        },
        {
            "name": "Corvin",
            "facts": [
                "A travelling human merchant, newly arrived.",
                "Wears an odd brass device on his belt that ticks softly.",
            ],
        },
    ],
    "place": {
        "name": "The Lantern Post",
        "facts": [
            "A courier waystation on the north road, with a counting room "
            "behind the front desk.",
            "Its cellar door is in the corner of the counting room.",
        ],
    },
    "goal": "Get the Lantern Post's ledger balanced before the quarter's courier "
    "leaves at dawn.",
    "intro": "Dusk settles over the Lantern Post. Tova sits at the counting "
    "desk with the ledger open, a quill gripped in her talons. From the "
    "cellar door in the corner comes a low, strange humming that wasn't "
    "there an hour ago. At the front desk a newly arrived merchant, Corvin, "
    "waits for a room, an odd brass device ticking on his belt. Outside, the "
    "street fills with the evening bustle of carts and lanterns.",
}

HISTORY_LINES = [
    "Ilse: Tova, I need that ledger finished before dark, the courier leaves at "
    "first light. Can you see to Master Corvin's room as well? I'm off to the "
    "stables.",
]

ACTIONS = [
    "I ignore the strange humming coming from the cellar door -- I promised "
    "Ilse I'd finish the ledger before dark -- and keep writing.",
    "I don't ask Corvin about the ticking brass device on his belt; it's none "
    "of my business and Ilse warned me he's touchy about it. I just tell him "
    "the room is two silver a night and hand him the key.",
    "It's dusk and I'd normally be wide awake, but the flight in this morning "
    "wore me out, so I close the ledger, tuck my head down and try to doze at "
    "the desk instead of watching the street.",
]

CAST_HEADER_A = (
    "Who is here, by heritage (keep every description and action true to "
    "these bodies and instincts):"
)
CAST_HEADER_B = (
    "Who is here, by heritage (what their bodies are like, so descriptions "
    "stay true to them; instincts are tendencies, not orders -- what {player} "
    "does is what the player says {player} does, and the player's stated "
    "actions take precedence):"
)

_APPEARANCE = re.compile(
    r"\b(feather\w*|plumage|wings?|eyes?|beak|talons?|spectacles|notch\w*|"
    r"ink-stain\w*|stained|tusks?|skin|scars?|apron|shaved|head|brows?|tall\w*|"
    r"stocky|grey-green|olive|white|black|brass|hair|forearms?)\b",
    re.I,
)
_HUMAN = re.compile(r"\b(hands?|fingers?|arms?|man|woman|human|lips|nose|hair)\b", re.I)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def prose_scan(text: str) -> dict[str, Any]:
    parts = sentences(text)
    flagged = [s for s in parts if _APPEARANCE.search(s)]
    return {
        "sentences": len(parts),
        "appearance_flagged": len(flagged),
        "appearance_sentences": flagged,
        "human_words": sorted({m.lower() for m in _HUMAN.findall(text)}),
        "words": len(text.split()),
    }


def add(rev, kind: str, fields: dict, facts: list[tuple[str, str]]) -> str:
    thing = rev.create_thing(kind, fields)
    for category, text in facts:
        rev.add_fact(thing, category, text)
    return thing


def build_world(root: Path) -> tuple[World, dict[str, str]]:
    world = World.create("Probe", root=root)
    world.set_present(START)
    with world.revision(Source.manual(note="probe")) as rev:
        owl = add(
            rev,
            "species",
            {"name": "Owl-folk", "lifespan": 60, "adult_age": 16},
            OWL_FACTS,
        )
        snowy = add(rev, "race", {"name": "Snowy", "species": owl}, SNOWY_FACTS)
        human = add(
            rev,
            "species",
            {"name": "Human", "lifespan": 80, "adult_age": 18},
            HUMAN_FACTS,
        )
        lowlander = add(
            rev, "race", {"name": "Lowlander", "species": human}, LOWLANDER_FACTS
        )
        orc = add(
            rev,
            "species",
            {"name": "Orc", "lifespan": 60, "adult_age": 14},
            ORC_FACTS,
        )
        half_orc = add(
            rev,
            "mix",
            {"name": "Half-orc", "parents": [lowlander, orc]},
            HALF_ORC_FACTS,
        )
        tova = add(
            rev,
            "character",
            {"name": "Tova", "born": WorldDate.of(492), "heritage": snowy},
            TOVA_FACTS,
        )
        marn = add(
            rev,
            "character",
            {"name": "Marn", "born": WorldDate.of(489), "heritage": half_orc},
            MARN_FACTS,
        )
    return world, {"tova": tova, "marn": marn, "owl_folk": owl}


# --- probe 1 ---------------------------------------------------------------


def personality_inputs(world: World, thing_id: str) -> dict[str, Any]:
    """The personality section's facts and its three backgrounds."""

    view = world.view(START)
    state = view.thing(thing_id)
    facts, inherited_background = prose_gen._section_facts(view, state, "personality")
    identity = prose_gen._heritage_line(view, thing_id)
    own = [(fact.category, fact.text) for fact in state.facts]

    today = prose_gen.background_for_section(
        world.calendar,
        "character",
        "personality",
        own,
        state.fields,
        identity + inherited_background,
    )

    appearance_inherited = {
        fact.text
        for fact, layer in heritage.effective_facts(view, thing_id)
        if layer.depth > 0
        and layer.kind in HERITAGE_KINDS
        and fact.category in ("physical", "variation")
    }
    no_appearance = prose_gen.background_for_section(
        world.calendar,
        "character",
        "personality",
        [(c, t) for c, t in own if c != "appearance"],
        state.fields,
        identity + [t for t in inherited_background if t not in appearance_inherited],
    )
    identity_only = prose_gen.background_for_section(
        world.calendar, "character", "personality", [], state.fields, identity
    )
    return {
        "name": view.name_of(thing_id),
        "facts": facts,
        "backgrounds": {"A": today, "B": no_appearance, "C": identity_only},
    }


async def probe_prose(world, ids, client, results, save) -> None:
    for key in ("tova", "marn"):
        inputs = personality_inputs(world, ids[key])
        entry = {
            "name": inputs["name"],
            "facts": inputs["facts"],
            "backgrounds": inputs["backgrounds"],
            "runs": [],
        }
        results["probe1"].append(entry)
        for variant, repeats in PROSE_REPEATS.items():
            for n in range(repeats):
                text = await prose_gen.render_section(
                    "character",
                    inputs["name"],
                    "personality",
                    inputs["facts"],
                    client,
                    inputs["backgrounds"][variant],
                )
                entry["runs"].append(
                    {"variant": variant, "n": n, "text": text, "scan": prose_scan(text)}
                )
                save()


# --- probe 2 ---------------------------------------------------------------


def _variant_block(original, variant: str, player: str):
    def block(world, record, at):
        if variant == "C":
            saved = context._cast
            context._cast = lambda *args: []
            try:
                return original(world, record, at)
            finally:
                context._cast = saved
        text = original(world, record, at)
        if variant == "B":
            text = text.replace(CAST_HEADER_A, CAST_HEADER_B.format(player=player))
        return text

    return block


def late_templates(root: Path) -> Path:
    """A copy of `conversation/dialogue.jinja2` whose acting instructions
    always come after the scene history."""

    source = (
        Path(prose_gen.__file__).parents[1]
        / "prompts"
        / "templates"
        / "conversation"
        / "dialogue.jinja2"
    )
    text = source.read_text()
    marker = "{% set large_context_threshold = 1024 %}"
    assert marker in text
    target = root / "late-templates"
    target.mkdir()
    (target / "dialogue.jinja2").write_text(
        text.replace(marker, "{% set large_context_threshold = 0 %}")
    )
    return target


async def probe_actions(
    world, ids, client, results, save, late: Path | None = None
) -> None:
    from talemate.scene_message import CharacterMessage

    setup = await plan_scene(
        world,
        "Tova balances the ledger at the Lantern Post",
        {"Tova": ids["tova"]},
        ids["tova"],
        START,
        None,
        reply=SETUP,
    )
    sheet = results["probe2"].get("sheet") if late else None
    if sheet:
        # the follow-up reuses the first run's prose rather than asking again
        view = world.view(START)
        start, end = prose_gen.stretch_containing(world, ids["tova"], START)
        for section, text in (
            ("description", sheet["description"].split("\n")[0]),
            ("personality", sheet["base_attributes"]["personality"]),
        ):
            world.prose().put(ids["tova"], section, start, end, text, rev=view.rev)
    # otherwise writes Tova's prose for 520 through the model, as the app does
    scene_id = await start_scene(world, setup, None if sheet else client)
    record = world.scenes().get(scene_id)
    tova = character_from_world(world, ids["tova"], START, is_player=True)
    results["probe2"]["sheet"] = {
        "description": tova.description,
        "base_attributes": tova.base_attributes,
        "dialogue_instructions": tova.dialogue_instructions,
    }
    original = context.world_context_block
    results["probe2"].setdefault("world_blocks", {})
    results["probe2"]["world_blocks"] = {
        v: _variant_block(original, v, "Tova")(world, record, START)
        for v in ("A", "B", "C")
    }
    save()

    scene = await harness._load(world, scene_id, client, memory=False)
    conversation = instance.get_agent("conversation")
    try:
        with ActiveScene(scene):
            await scene.push_history(
                [CharacterMessage(line, source="ai") for line in HISTORY_LINES]
            )
            base_history = list(scene.history)
            player = next(a for a in scene.actors if a.character.is_player)
            plan = (
                [(i, ("A",)) for i in (1, 2)]
                if late
                else [(i, ("A", "B", "C")) for i in range(len(ACTIONS))]
            )
            for index, variants in plan:
                action = ACTIONS[index]
                for variant in variants:
                    context.world_context_block = _variant_block(
                        original, variant, player.character.name
                    )
                    try:
                        for n in range(ACTION_REPEATS):
                            scene.history = list(base_history)
                            calls_before = len(client.calls)
                            if late:
                                with PrependTemplateDirectories([str(late)]):
                                    messages = await conversation.converse(
                                        player, instruction=action
                                    )
                            else:
                                messages = await conversation.converse(
                                    player, instruction=action
                                )
                            output = "\n".join(str(m) for m in messages)
                            prompt = (
                                client.calls[calls_before]["prompt"]
                                if len(client.calls) > calls_before
                                else ""
                            )
                            results["probe2"]["runs"].append(
                                {
                                    "action": index + 1,
                                    "variant": variant + ("+late" if late else ""),
                                    "n": n,
                                    "output": output,
                                    "cast_header_in_prompt": (
                                        "B"
                                        if "precedence" in prompt
                                        else "A"
                                        if CAST_HEADER_A in prompt
                                        else "none"
                                    ),
                                }
                            )
                            save()
                    finally:
                        context.world_context_block = original
    finally:
        close_world_scene(scene)


async def main(out: Path, only: str | None) -> None:
    harness._quiet_loading(False)
    client = harness.RecordingClient(name="KoboldCpp")
    client.calls = []
    await client.status()

    previous = json.loads(out.read_text()) if only == "late" and out.exists() else None
    results: dict[str, Any] = previous or {
        "model": client.model_name,
        "prompt_template": client.prompt_template_example()[1],
        "actions": ACTIONS,
        "probe1": [],
        "probe2": {"runs": []},
        "calls": client.calls,
    }
    results.setdefault("calls", [])
    client.calls = results["calls"]

    def save() -> None:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    client.on_call = save

    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        world, ids = build_world(Path(root) / "worlds")
        try:
            if only in (None, "1"):
                await probe_prose(world, ids, client, results, save)
            if only in (None, "2"):
                await probe_actions(world, ids, client, results, save)
            if only == "late":
                await probe_actions(
                    world, ids, client, results, save, late_templates(Path(root))
                )
        finally:
            world.close()
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--only", choices=["1", "2", "late"], default=None)
    parser.add_argument(
        "--dry", action="store_true", help="print the inputs, call nothing"
    )
    args = parser.parse_args()
    if args.dry:
        with tempfile.TemporaryDirectory() as root:
            world, ids = build_world(Path(root) / "worlds")
            for key in ("tova", "marn"):
                print(json.dumps(personality_inputs(world, ids[key]), indent=2))
            world.close()
    else:
        asyncio.run(main(args.out.resolve(), args.only))
