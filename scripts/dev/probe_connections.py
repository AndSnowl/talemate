"""Throwaway probe: names, mention context, duplicates and everyday names
(fantasymate connections, Task 3).

A world in a temp dir: the Owl-folk species (an origin fact naming the
"Tsardom of Moscavia" in 994, then body, instincts, variation and general
facts), its Snowy race, and Humans. Creates go through the real
`create.preview_thing` on Talemate's own KoboldCpp client (the `--ai` app's
config, as `probe_heritage_play` sets it up), with a copy of
`world/create-thing.jinja2` put in front through
`PrependTemplateDirectories`. The copy adds, for every create:

- `"aka"` (the thing's own other names, tagged) and `"names"` (the proper
  names its facts use, each with a kind and its own `aka`) to the reply's
  example and rules;
- the probe's context block, if any, just before the calendar line.

Section prose isn't written (`create._preview_prose` is stubbed), so each
create is one call. The reply `parse_create_reply` reads is recorded.

1. **Names and kinds.** A country, a character (a Human) and a species, 3
   runs each. The model's `names` are compared with
   `names.unknown_proper_phrases` on the same facts, and with both
   together, against hand labels (`LABELS`, filled in after the run;
   `--score` recomputes the scores into the JSON).
2. **Context from mentions.** The Tsardom of Moscavia expanded from its
   stub (name decided, the suggested prompt), 3 runs each with (a) the
   mentioning fact only, (b) plus the Owl-folk's key facts (physical,
   instinct, origin, capped at 8) and (c) plus all their facts.
3. **Duplicates.** "A river town where Moscavian Owls trade with barge
   crews", 3 runs each without and with the Owl-folk matched into a
   "Named in this prompt" block.
4. **Everyday names.** The `aka` the creates above suggest are tagged by
   hand from the JSON. Then a scene in Barrowford, a river town of the
   Tsardom (pulled in as lore), with Ilse (human) and Brannoc (owl-folk),
   loaded through its `world://` target: 3 narrator turns
   (`progress_story`, each from the same history) under three World
   blocks -- the Tsardom's name alone, "Tsardom of Moscavia (usually
   called Moscavia)", and that plus a line asking for everyday names.
   Full-name and everyday-name uses are counted. `--only 4b` is a
   follow-up with directions that ask for the country's name outright.
5. **Everyday names in create prompts** (`--only 5`, a follow-up): "an
   amber market town on a lake in Moscavia" with the Tsardom matched to
   "Moscavia" and shown as "Tsardom of Moscavia (place, usually called
   Moscavia)", 3 runs without and with a line asking for everyday names
   in the facts.

Every call's prompt and reply goes to the output JSON after each call. Not
a test: it calls the network. The owner approved this plan's Skyfall
probes (one GPU: calls run one after another)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_connections.py OUT.json \\
        [--only 1 2 3 4] [--score] [--dry]'

Findings: docs/superpowers/probes/2026-10-21-connections.md.
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
import talemate.worldplay.create as create  # noqa: E402
from talemate.context import ActiveScene  # noqa: E402
from talemate.prompts.base import PrependTemplateDirectories  # noqa: E402
from talemate.scene_message import CharacterMessage  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.names import unknown_proper_phrases  # noqa: E402
from talemate.world.store import Source, World  # noqa: E402
from talemate.worldplay.persistence import close_world_scene  # noqa: E402
from talemate.worldplay.setup import plan_scene, start_scene  # noqa: E402

PRESENT = WorldDate.of(1020)
RUNS = 3
KEY_CATEGORIES = ("physical", "instinct", "origin")
KEY_CAP = 8

ORIGIN_MENTION = (
    "In 994, every person in the Tsardom of Moscavia awoke as owl-folk "
    "overnight, in what Moscavians call the Night of Feathers."
)
OWL_FACTS = [
    ("origin", ORIGIN_MENTION),
    (
        "origin",
        "No one knows what caused the change; owl-folk children have hatched "
        "from eggs ever since.",
    ),
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
    ("instinct", "Owl-folk go utterly still and silent when startled."),
    ("variation", "Owl-folk plumage ranges from snowy white to barred brown and grey."),
    (
        "general",
        "Owl-folk stand four to five feet tall and weigh little for their size, "
        "with hollow bones.",
    ),
    (
        "general",
        "The oldest owl-folk remember the human lives they had before 994, and "
        "some still mourn their hands.",
    ),
]
SNOWY_FACTS = [
    ("variation", "Snowy owl-folk have white plumage flecked with black."),
    (
        "physical",
        "Snowy owl-folk are feathered down to their talons and shrug off cold.",
    ),
]
HUMAN_FACTS = [
    ("physical", "Humans have bare skin, hair on their heads and two hands."),
    ("instinct", "Humans seek company and grow restless when kept alone for long."),
]
TSARDOM_FACTS = [
    (
        "description",
        "The Tsardom of Moscavia is a northern realm of pine forest, bog and "
        "slow brown rivers.",
    ),
    (
        "history",
        "Since the Night of Feathers in 994, nearly all Moscavians are owl-folk.",
    ),
    ("law", "The Tsar rules from Kremova, a city of towers and roosting galleries."),
    (
        "general",
        "Barges carry timber, furs and amber down the Vesna to the southern ports.",
    ),
]

# --- the template copy -----------------------------------------------------

AKA_EXAMPLE = '"aka": [{"name": "...", "tag": "common", "everyday": true}], '
NAMES_EXAMPLE = ', "names": [{"name": "...", "kind": "place", "aka": []}]'
NAMES_RULES = """- "aka": other names for this {{ kind }} itself, if it has any, each {"name", "tag", "everyday"}. "tag" is "proper" for another formal name, or "common" for what people in the world actually call it day to day (a short form, a nickname). Set "everyday" true on the one common name people use most, false on the rest. "name" stays the most formal name. An empty list is fine.
- "names": after the facts, every proper name your facts use, other than this {{ kind }}'s own: people, places, peoples and species, named events, named groups and named objects, new or already in the world. Each is {"name", "kind", "aka"}: "name" in full, as your facts write it; "kind" one of character, place, species, race, culture, event, item, lore (a group, order or faction is lore); "aka" any other names your facts use for the same thing. Proper names only: never a description such as "the postmaster", "a war" or "his mother" -- but "Yelena" in "his mother Yelena" is a name. An empty list is fine.
"""


def probe_template(context_block: str) -> str:
    """`world/create-thing.jinja2` with the names additions and
    `context_block` (plain text) before the calendar line."""

    source = (
        Path(create.__file__).parents[1]
        / "prompts"
        / "templates"
        / "world"
        / "create-thing.jinja2"
    )
    lines = source.read_text().split("\n")
    out = []
    examples = 0
    for line in lines:
        if line.startswith('{"name": "...",'):
            examples += 1
            assert line.endswith("}"), line
            line = line.replace('"facts": [', AKA_EXAMPLE + '"facts": [', 1)
            line = line[:-1] + NAMES_EXAMPLE + "}"
        if line.startswith("No commentary, no markdown fences"):
            out.extend(NAMES_RULES.rstrip("\n").split("\n"))
            out.append("")
        if line.startswith("The world's calendar:") and context_block:
            out.extend(context_block.rstrip("\n").split("\n"))
            out.append("")
        out.append(line)
    assert examples == 4, examples
    text = "\n".join(out)
    assert "No commentary" in text and NAMES_RULES.split("\n")[0] in text
    return text


def mention_block(world: World, ids: dict[str, str], variant: str) -> str:
    """Probe 2's context: (a) "Mentioned elsewhere" only; (b) plus "About
    those" with the key facts; (c) plus every other fact."""

    lines = [
        "Mentioned elsewhere in the world (keep these true):",
        f"- Owl-folk (species, origin): {ORIGIN_MENTION}",
    ]
    if variant == "a":
        return "\n".join(lines)
    view = world.view(PRESENT)
    others = [
        fact
        for fact in view.thing(ids["owl_folk"]).facts
        if fact.text != ORIGIN_MENTION
    ]
    if variant == "b":
        ordered = [f for c in KEY_CATEGORIES for f in others if f.category == c]
        chosen = ordered[:KEY_CAP]
    else:
        chosen = others
    lines.append("")
    lines.append(
        "About those (they already exist in the world; let the {kind} reflect "
        "them -- a place is shaped by the people who live there):".replace(
            "{kind}", "place"
        )
    )
    lines.append("Owl-folk (species):")
    lines.extend(f"- {fact.text}" for fact in chosen)
    return "\n".join(lines)


def named_block(world: World, ids: dict[str, str]) -> str:
    """Probe 3's "Named in this prompt": the Owl-folk matched to "Moscavian
    Owls", with every fact, as scene setup shows a matched thing."""

    view = world.view(PRESENT)
    lines = [
        "Named in this prompt (these already exist in the world: use them as "
        "they are, and never invent a new one in their place):",
        '"Moscavian Owls" means Owl-folk (species):',
    ]
    lines.extend(f"- {fact.text}" for fact in view.thing(ids["owl_folk"]).facts)
    return "\n".join(lines)


CREATE_EVERYDAY_LINE = (
    'Where a name is followed by "usually called ...", write that everyday '
    "name in the facts, and keep the full name for formal uses such as "
    "titles and laws."
)


def everyday_named_block(world: World, tsardom: str, line: bool) -> str:
    """Probe 5's "Named in this prompt": the Tsardom, with its everyday
    name, matched to "Moscavia"; with `line`, the everyday-name rule."""

    view = world.view(PRESENT)
    lines = [
        "Named in this prompt (these already exist in the world: use them as "
        "they are, and never invent a new one in their place):",
        '"Moscavia" means Tsardom of Moscavia (place, usually called Moscavia):',
    ]
    lines.extend(f"- {fact.text}" for fact in view.thing(tsardom).facts)
    if line:
        lines.extend(["", CREATE_EVERYDAY_LINE])
    return "\n".join(lines)


# --- the world -------------------------------------------------------------


def add(rev, kind: str, fields: dict, facts: list[tuple[str, str]]) -> str:
    thing = rev.create_thing(kind, fields)
    for category, text in facts:
        rev.add_fact(thing, category, text)
    return thing


def build_world(root: Path) -> tuple[World, dict[str, str]]:
    world = World.create("Probe", root=root)
    world.set_present(PRESENT)
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
            {"name": "Human", "lifespan": 75, "adult_age": 18},
            HUMAN_FACTS,
        )
    return world, {"owl_folk": owl, "snowy": snowy, "human": human}


# --- creating --------------------------------------------------------------


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


_last_reply: list[str] = []
_parse = create.parse_create_reply


def _recording_parse(reply, *args, **kwargs):
    _last_reply.append(reply)
    return _parse(reply, *args, **kwargs)


def reply_object(reply: str) -> dict[str, Any]:
    objects = create.json_objects(reply) or create.json_objects("{" + reply)
    best = max(objects, key=lambda o: len(json.dumps(o)), default={})
    return best


async def one_create(
    world: World,
    client,
    tmp: Path,
    kind: str,
    prompt: str,
    fields: dict[str, Any],
    block: str,
) -> dict[str, Any]:
    folder = Path(tempfile.mkdtemp(dir=tmp))
    (folder / "create-thing.jinja2").write_text(probe_template(block))
    _last_reply.clear()
    error = None
    preview = None
    calls_before = len(client.calls)
    try:
        with PrependTemplateDirectories([str(folder)]):
            preview = await create.preview_thing(world, kind, prompt, fields, client)
    except Exception as exc:  # a bad reply is a finding, not a crash
        error = repr(exc)
    reply = _last_reply[-1] if _last_reply else ""
    obj = reply_object(reply) if reply else {}
    facts = [f.text for f in preview.facts] if preview else []
    view = world.view(PRESENT)
    code = sorted(
        {u.text for text in facts for u in unknown_proper_phrases(view, text)}
    )
    return {
        "kind": kind,
        "prompt": prompt,
        "fields": {k: str(v) for k, v in fields.items()},
        "call": calls_before,
        "error": error,
        "reply": reply,
        "name": preview.name if preview else obj.get("name"),
        "facts": facts,
        "aka": obj.get("aka"),
        "names": obj.get("names"),
        "code_phrases": code,
        "context_block": block,
    }


PROBE1 = [
    (
        "country",
        "place",
        "a cold southern kingdom of salt marshes and lighthouses, ruled by a "
        "council of bishops",
        {},
    ),
    (
        "character",
        "character",
        "a retired river pilot who lost her husband in a flood and now raises "
        "her grandson",
        {"heritage": "human"},
    ),
    (
        "species",
        "species",
        "otter-folk who live in floating villages on great inland lakes",
        {},
    ),
]

TSARDOM_PROMPT = (
    "The Tsardom of Moscavia: the country where, in 994, everyone turned into "
    "owl-folk overnight."
)
TOWN_PROMPT = "a river town where Moscavian Owls trade with barge crews"


async def probe1(world, ids, client, tmp, results, save) -> None:
    for label, kind, prompt, fields in PROBE1:
        fields = {k: ids.get(v, v) for k, v in fields.items()}
        for n in range(RUNS):
            entry = await one_create(world, client, tmp, kind, prompt, fields, "")
            entry.update(case=label, n=n)
            results["probe1"].append(entry)
            save()


async def probe2(world, ids, client, tmp, results, save) -> None:
    for variant in ("a", "b", "c"):
        block = mention_block(world, ids, variant)
        for n in range(RUNS):
            entry = await one_create(
                world,
                client,
                tmp,
                "place",
                TSARDOM_PROMPT,
                {"name": "Tsardom of Moscavia"},
                block,
            )
            entry.update(variant=variant, n=n, scan=inhabitant_scan(entry["facts"]))
            results["probe2"].append(entry)
            save()


async def probe3(world, ids, client, tmp, results, save) -> None:
    for variant in ("none", "matched"):
        block = named_block(world, ids) if variant == "matched" else ""
        for n in range(RUNS):
            entry = await one_create(
                world, client, tmp, "place", TOWN_PROMPT, {}, block
            )
            entry.update(variant=variant, n=n)
            results["probe3"].append(entry)
            save()


EVERYDAY_PROMPT = "an amber market town on a lake in Moscavia"


async def probe5(world, ids, client, tmp, results, save) -> None:
    """Everyday names in create prompts: does the parenthetical, or it plus
    a rule line, make facts say "Moscavia" rather than the full name?"""

    with world.revision(Source.manual(note="probe")) as rev:
        tsardom = add(rev, "place", {"name": "Tsardom of Moscavia"}, TSARDOM_FACTS)
    for variant in ("everyday", "everyday+line"):
        block = everyday_named_block(world, tsardom, variant == "everyday+line")
        for n in range(RUNS):
            entry = await one_create(
                world, client, tmp, "place", EVERYDAY_PROMPT, {}, block
            )
            entry.update(
                variant=variant, n=n, counts=name_counts(" ".join(entry["facts"]))
            )
            results.setdefault("probe5", []).append(entry)
            save()


_INHABITANT = {
    "owl": r"\bowl",
    "feather": r"feather|plumage",
    "roost_perch": r"\broost|\bperch",
    "talon_wing": r"\btalon|\bwing",
    "dusk_night": r"\bdusk\b|\bdawn\b|\bnight\b|twilight|crepuscular",
    "night_of_feathers": r"night of feathers|\b994\b",
    "human": r"\bhumans?\b",
}


def inhabitant_scan(facts: list[str]) -> dict[str, int]:
    """How many facts touch each inhabitant theme."""

    return {
        key: sum(1 for text in facts if re.search(pattern, text, re.I))
        for key, pattern in _INHABITANT.items()
    }


# --- probe 4: everyday names in narration --------------------------------

SETUP = {
    "player": "Ilse",
    "characters": [
        {
            "name": "Ilse",
            "facts": ["A young human trader come upriver to buy amber."],
        },
        {
            "name": "Brannoc",
            "facts": [
                "Keeps the Wet Perch, the bargemen's tavern on the quay.",
                "Old and broad, with a voice like a creaking branch.",
            ],
            "heritage": "Owl-folk",
        },
    ],
    "place": {
        "name": "Barrowford",
        "facts": [
            "A river town on the Vesna in the south of the Tsardom of Moscavia.",
            "Barges tie up three deep along its timber quays.",
        ],
    },
    "goal": "Find an amber seller who will deal with a foreigner.",
    "intro": "Dusk on the quays of Barrowford. Ilse steps off the barge as the "
    "lanterns come on and the owl-folk of the town wake for the evening.",
}
HISTORY_LINES = [
    "Ilse: Brannoc, who in this town sells amber to outsiders? And what's the "
    "news from upriver?",
]
DIRECTIONS = [
    "Brannoc answers with the news: a proclamation from the Tsar's court has "
    "raised the river tolls. Describe the tavern's reaction.",
    "Brannoc tells Ilse, in a few sentences, how the whole country changed on "
    "the night everyone became owl-folk.",
    "Describe the view from the quay as night deepens: the river, the barges "
    "and the dark forests of the country stretching north.",
]
# the follow-up ("--only 4b"): the first directions rarely named the
# country at all, so these ask for its name outright
NAMED_DIRECTIONS = [
    "Brannoc welcomes Ilse to his country, calling it by name, and tells her "
    "what a foreigner should know about it.",
    "A herald on the quay reads out a proclamation from the Tsar's court to "
    "the people of the realm, naming the realm. Describe it and the crowd's "
    "reaction.",
    "Ilse writes a few lines home about the country she has arrived in, "
    "naming it. Show the letter.",
]
EVERYDAY_HEADING = "Tsardom of Moscavia (usually called Moscavia)"
EVERYDAY_LINE = (
    "In narration and dialogue, call things by their everyday names: where a "
    'name is followed by "usually called ...", use that name, and keep the '
    "full name for formal moments."
)
BLOCK_VARIANTS = ("plain", "everyday", "everyday+line")


def _variant_block(original, variant: str):
    def block(world, record, at):
        text = original(world, record, at)
        if variant == "plain":
            return text
        assert "\nTsardom of Moscavia\n" in text, text
        text = text.replace("\nTsardom of Moscavia\n", f"\n{EVERYDAY_HEADING}\n", 1)
        if variant == "everyday+line":
            text = text.replace("[world]\n", f"[world]\n{EVERYDAY_LINE}\n", 1)
        return text

    return block


def name_counts(text: str) -> dict[str, int]:
    full = len(re.findall(r"Tsardom of Moscavia", text))
    moscavia = len(re.findall(r"\bMoscavia\b", text))
    return {
        "full": full,
        "everyday": moscavia - full,
        "moscavian": len(re.findall(r"\bMoscavians?\b", text)),
        "the_tsardom": len(re.findall(r"\b[Tt]he Tsardom\b(?! of)", text)),
    }


async def probe4(
    world, ids, client, results, save, directions=DIRECTIONS, key="runs"
) -> None:
    with world.revision(Source.manual(note="probe")) as rev:
        tsardom = add(rev, "place", {"name": "Tsardom of Moscavia"}, TSARDOM_FACTS)
    setup = await plan_scene(
        world, "Ilse buys amber in Barrowford", {}, None, PRESENT, None, reply=SETUP
    )
    setup.pulled_in = [tsardom]
    scene_id = await start_scene(world, setup, None)
    record = world.scenes().get(scene_id)
    original = context.world_context_block
    results["probe4"]["world_blocks"] = {
        v: _variant_block(original, v)(world, record, PRESENT) for v in BLOCK_VARIANTS
    }
    save()

    scene = await harness._load(world, scene_id, client, memory=False)
    narrator = instance.get_agent("narrator")
    try:
        with ActiveScene(scene):
            await scene.push_history(
                [CharacterMessage(line, source="player") for line in HISTORY_LINES]
            )
            base_history = list(scene.history)
            for variant in BLOCK_VARIANTS:
                context.world_context_block = _variant_block(original, variant)
                try:
                    for index, direction in enumerate(directions):
                        scene.history = list(base_history)
                        calls_before = len(client.calls)
                        text = await narrator.progress_story(
                            narrative_direction=direction
                        )
                        prompt = (
                            client.calls[calls_before]["prompt"]
                            if len(client.calls) > calls_before
                            else ""
                        )
                        results["probe4"].setdefault(key, []).append(
                            {
                                "variant": variant,
                                "turn": index + 1,
                                "direction": direction,
                                "output": text,
                                "counts": name_counts(text),
                                "heading_in_prompt": EVERYDAY_HEADING in prompt,
                                "line_in_prompt": EVERYDAY_LINE in prompt,
                            }
                        )
                        save()
                finally:
                    context.world_context_block = original
    finally:
        close_world_scene(scene)


# --- scoring -----------------------------------------------------------------

# hand labels, filled in after the run. Per probe 1 run ("case-n"): each
# proper name its facts use, other than the thing's own, as
# `main: (kinds, other spellings)` -- `kinds` the acceptable kinds,
# `|`-separated -- and `neutral`, phrases that are fairly read either way
# ("the Church") and count neither for nor against. Names already in the
# world (Owl-folk, Snowy, Human) aren't listed: they'd be linked, not
# stubbed.
LABELS: dict[str, dict[str, Any]] = {
    "country-0": {
        "entities": {
            "Synod of the Twelve Lanterns": ("lore", ["Synod"]),
            "Ashenmere": ("place", []),
            "Aldric Voss": ("character", []),
            "Saltwalk Rebellion": ("event", []),
            "Church of the Twelve Lanterns": ("lore", []),
        },
        "neutral": [],
    },
    "country-1": {
        "entities": {
            "Synod of Tides": ("lore", ["Synod"]),
            "Grimhaven": ("place", []),
            "River Sere": ("place", []),
            "Saint Aldric the Lightkeeper": (
                "character",
                ["Aldric of the Holy See", "Aldric"],
            ),
            "Saltmarch": ("culture|lore", ["Saltmarch clans"]),
            "Pale": ("place", []),
            "Great Fog": ("event", []),
        },
        "neutral": ["Church"],
    },
    "country-2": {
        "entities": {
            "Ecclesiastic Council of Bishops": ("lore", ["Bishops' Council"]),
            "Dunhallow": ("place", []),
            "Aldric of Voss": ("character", ["Bishop Aldric of Voss"]),
            "Frostspine Mountains": ("place", []),
            "Drowning of Saint Maren": ("event", []),
            "Greyfirth": ("place", []),
            "Spire of Tides": ("place|item", []),
        },
        "neutral": ["Church", "Saint Maren"],
    },
    "character-0": {
        "entities": {
            "Vennmark": ("place", []),
            "Northern Reaches": ("place", []),
            "Aldmark": ("place", []),
            "Brönn": ("place", []),
            "Mosswall": ("place", []),
            "Eirik Solvik": ("character", []),
            "Tobias": ("character", ["Tobias Solvik"]),
            "Great Spring Flood": ("event", ["Great Spring Flood of 1008"]),
        },
        "neutral": [],
    },
    "character-1": {
        "entities": {
            "Alderwick": ("place", []),
            "Great Thane": ("place", []),
            "Dunmore": ("place", []),
            "Tomas": ("character", ["Tomas Alderwick"]),
            "Cairn's Bend": ("place", []),
            "Edric": ("character", ["Edric Alderwick"]),
        },
        "neutral": [],
    },
    "character-2": {
        "entities": {
            "Greenwater River": ("place", ["Greenwater"]),
            "Ashenmere": ("place", []),
            "Thomas Hargrove": ("character", ["Thomas"]),
            "Daniel": ("character", ["Daniel Hargrove"]),
            "Millwright Lane": ("place", []),
        },
        "neutral": [],
    },
    "species-0": {
        "entities": {"Halivan Continent": ("place", [])},
        "neutral": [],
    },
    "species-1": {"entities": {}, "neutral": []},
    "species-2": {"entities": {}, "neutral": []},
}

KNOWN = {"owl-folk", "snowy", "human", "humans"}


def _norm(name: str) -> str:
    name = re.sub(r"['’]s?$", "", " ".join(name.split()))
    return re.sub(r"^(the|a|an) ", "", name, flags=re.I).casefold()


def _is_self(phrase: str, entry: dict[str, Any], words_too: bool) -> bool:
    """The thing's own name or one of its suggested other names -- or,
    with `words_too` (the code rule, which can't tell), words of its name
    ("Brinenmere" of "The Ecclesiarchy of Brinenmere")."""

    own = [entry.get("name") or ""] + [
        a.get("name", "") for a in entry.get("aka") or [] if isinstance(a, dict)
    ]
    own_n = {_norm(o) for o in own if o}
    words = {w for o in own_n for w in o.split()}
    p = _norm(phrase)
    return p in own_n or (words_too and set(p.split()) <= words)


def score(results: dict[str, Any]) -> None:
    rows = []
    for entry in results["probe1"]:
        key = f"{entry['case']}-{entry['n']}"
        label = LABELS.get(key)
        if label is None:
            continue
        spellings = {}
        for main, (_kinds, others) in label["entities"].items():
            for spelling in [main, *others]:
                spellings[_norm(spelling)] = main
        neutral = {_norm(n) for n in label["neutral"]}

        def classify(phrases: list[str], code: frozenset[str]) -> dict[str, Any]:
            hits: set[str] = set()
            wrong: list[str] = []
            for phrase in phrases:
                p = _norm(phrase)
                if (
                    p in KNOWN
                    or p in neutral
                    or _is_self(phrase, entry, words_too=phrase in code)
                ):
                    continue
                if p in spellings:
                    hits.add(spellings[p])
                else:
                    wrong.append(phrase)
            total = len(label["entities"])
            listed = len(hits) + len(wrong)
            return {
                "hits": len(hits),
                "of": total,
                "wrong": sorted(set(wrong)),
                "missed": sorted(set(label["entities"]) - hits),
                "recall": round(len(hits) / total, 2) if total else None,
                "precision": round(len(hits) / listed, 2) if listed else None,
            }

        model_items = [
            item
            for item in entry.get("names") or []
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        model_names = [item["name"] for item in model_items]
        code = list(entry["code_phrases"])
        kind_right = kind_of = 0
        for item in model_items:
            main = spellings.get(_norm(item["name"]))
            if main is None:
                continue
            kind_of += 1
            kind_right += item.get("kind") in label["entities"][main][0].split("|")
        rows.append(
            {
                "run": key,
                "model": classify(model_names, frozenset()),
                "code": classify(code, frozenset(code)),
                "both": classify(
                    model_names + code, frozenset(code) - set(model_names)
                ),
                "kind_right": kind_right,
                "kind_of": kind_of,
            }
        )
    totals: dict[str, Any] = {}
    for rule in ("model", "code", "both"):
        hits = sum(r[rule]["hits"] for r in rows)
        of = sum(r[rule]["of"] for r in rows)
        wrong = sum(len(r[rule]["wrong"]) for r in rows)
        totals[rule] = {
            "hits": hits,
            "of": of,
            "wrong": wrong,
            "recall": round(hits / of, 2) if of else None,
            "precision": round(hits / (hits + wrong), 2) if hits + wrong else None,
        }
    totals["kinds"] = {
        "right": sum(r["kind_right"] for r in rows),
        "of": sum(r["kind_of"] for r in rows),
    }
    results["probe1_scores"] = rows
    results["probe1_totals"] = totals


# --- main --------------------------------------------------------------------


async def main(out: Path, only: list[str]) -> None:
    harness._quiet_loading(False)
    create._preview_prose = _no_prose
    create.parse_create_reply = _recording_parse
    client = harness.RecordingClient(name="KoboldCpp")
    client.calls = []
    await client.status()

    results: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {
            "probe": "connections",
            "date": "2026-10-21",
            "model": client.model_name,
            "prompt_template": client.prompt_template_example()[1],
            "probe1": [],
            "probe2": [],
            "probe3": [],
            "probe4": {"runs": []},
            "calls": [],
        }
    )
    client.calls = results["calls"]

    def save() -> None:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    client.on_call = save

    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        tmp = Path(root) / "templates"
        tmp.mkdir()
        world, ids = build_world(Path(root) / "worlds")
        try:
            if "1" in only:
                await probe1(world, ids, client, tmp, results, save)
            if "2" in only:
                await probe2(world, ids, client, tmp, results, save)
            if "3" in only:
                await probe3(world, ids, client, tmp, results, save)
            if "4" in only:
                await probe4(world, ids, client, results, save)
            if "5" in only:
                await probe5(world, ids, client, tmp, results, save)
            if "4b" in only:
                await probe4(
                    world, ids, client, results, save, NAMED_DIRECTIONS, "named_runs"
                )
        finally:
            world.close()
    score(results)
    save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--only", nargs="+", default=["1", "2", "3", "4"])
    parser.add_argument("--score", action="store_true", help="rescore OUT.json")
    parser.add_argument(
        "--dry", action="store_true", help="print the templates, call nothing"
    )
    args = parser.parse_args()
    if args.score:
        data = json.loads(args.out.read_text())
        score(data)
        args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(data["probe1_totals"], indent=2))
    elif args.dry:
        with tempfile.TemporaryDirectory() as root:
            world, ids = build_world(Path(root) / "worlds")
            print(probe_template(mention_block(world, ids, "b")))
            print("----")
            print(named_block(world, ids))
            world.close()
    else:
        asyncio.run(main(args.out.resolve(), args.only))
