"""Throwaway probe: creating species, races, mixes and characters with heritage
(fantasymate phase 2 plan B, Task 4).

Asks the local model, through koboldcpp's OpenAI-compatible endpoint (plain
`urllib`, prefill `{`, temperature 0.8, calls run one after another), to:

1. draft a species from a one-line prompt: facts in the five heritage
   categories plus `lifespan`, `adult_age` and `measures`;
2. draft a race inside its species, with the species' facts listed as
   `F1...Fn` and the reply marking the ones it replaces in `"overrides"`;
3. draft a Half-orc mix from Lowlander and Orc, with the blending probe's
   guided rule (docs/superpowers/probes/2026-10-20-heritage-blending.md);
4. create a Snowy owl-folk character whose prompt says "blue eyes" against
   the inherited facts, where F(yellow eyes) should be overridden;
5. create a character of a Lowlander x Half-orc mix (a quarter-orc, itself
   drafted from the first parsed Half-orc entry of case 3) whose prompt
   says "red hair".

The prompts mirror `world/create-thing.jinja2` (its TASK and FORMAT
sections, the "since" and "inherent traits" rules, the JSON shape); the
wording settled here goes into Tasks 6 and 7's templates. Replies are read
with the shared non-strict `talemate.worldplay.create.json_objects`.

Writes every call's prompt, reply and analysis to the output JSON after
each call, so a killed run keeps what it got. Not a test: it calls the
network. The owner granted koboldcpp access for this plan's probes::

    guix shell -m manifest.scm -- uv run --no-sync \\
        python scripts/dev/probe_heritage_create.py OUT.json \\
        [--variant a|b|c|d] [--only CASE ...] [--entries EARLIER.json]

`--variant` picks the prompt wording (see `VARIANT`); `--entries` reuses an
earlier run's drafted Half-orc and Quarter-orc instead of drafting them
again. Findings: docs/superpowers/probes/2026-10-20-heritage-create.md.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from typing import Any

from talemate.worldplay.create import json_objects

URL = "http://192.168.0.5:5001/v1/chat/completions"
RUNS = 3

HERITAGE_CATEGORIES = ["origin", "physical", "instinct", "variation", "general"]
CHARACTER_CATEGORIES = [
    "appearance",
    "personality",
    "background",
    "ability",
    "relationship",
    "speech",
]

# the world's calendar, as the create template shows it
NOW_LABEL = "3 Rainmoot 812 AE"
NOW_YEAR = 812
ERA = "Age of Embers"
MONTHS = [
    "Frostwane",
    "Thawmonth",
    "Rainmoot",
    "Greening",
    "Highsun",
    "Goldfall",
    "Harvest",
    "Leafturn",
    "Mistmonth",
    "Darkening",
    "Deepcold",
    "Yearsend",
]

# --- the owner's world --------------------------------------------------------
# Each thing: kind, name, facts as (id, category, text), numbers, the facts
# of more general layers its own facts override, and its lineage links.

WORLD: dict[str, dict[str, Any]] = {
    "human": {
        "kind": "species",
        "name": "Human",
        "lifespan": 75,
        "adult_age": 18,
        "measures": [{"name": "height", "min": 5, "max": 6.5, "unit": "ft"}],
        "facts": [
            (
                "human-1",
                "physical",
                "Humans have smooth, nearly hairless skin, with hair growing mainly on the head.",
            ),
            (
                "human-2",
                "physical",
                "Humans have rounded ears, small flat teeth and no tusks, claws or feathers.",
            ),
            (
                "human-3",
                "physical",
                "Humans have brown, black, fair or red hair and brown, grey, blue or green eyes.",
            ),
            (
                "human-4",
                "instinct",
                "Humans instinctively seek company and grow restless when kept alone for long.",
            ),
        ],
    },
    "lowlander": {
        "kind": "race",
        "name": "Lowlander",
        "species": "human",
        "measures": [{"name": "height", "min": 5, "max": 5.7, "unit": "ft"}],
        "facts": [
            (
                "low-1",
                "physical",
                "Lowlanders are the shorter, stockier humans of the river plains.",
            ),
            (
                "low-2",
                "physical",
                "Lowlanders have olive to brown skin, dark brown or black hair and dark eyes.",
            ),
        ],
    },
    "orc": {
        "kind": "species",
        "name": "Orc",
        "lifespan": 60,
        "adult_age": 14,
        "measures": [
            {"name": "height", "min": 6, "max": 7, "unit": "ft"},
            {"name": "tusk length", "min": 1.5, "max": 2.5, "unit": "in"},
        ],
        "facts": [
            (
                "orc-1",
                "physical",
                "Orcs are broad and heavily muscled, with grey-green skin.",
            ),
            (
                "orc-2",
                "physical",
                "Orcs have a heavy brow ridge, pointed ears and two lower tusks that jut above the upper lip.",
            ),
            ("orc-3", "physical", "Orcs have coarse black hair."),
            (
                "orc-4",
                "physical",
                "Orcs have yellow or amber eyes that see well in dim light.",
            ),
            (
                "orc-5",
                "instinct",
                "Orcs have a strong territorial instinct and bristle when strangers enter their space uninvited.",
            ),
        ],
    },
    "owlfolk": {
        "kind": "species",
        "name": "Owl-folk",
        "lifespan": 70,
        "adult_age": 12,
        "measures": [
            {"name": "height", "min": 3, "max": 4, "unit": "ft"},
            {"name": "wingspan", "min": 7, "max": 9, "unit": "ft"},
        ],
        "facts": [
            (
                "owl-1",
                "physical",
                "Owl-folk are fully feathered, with a pair of wings in place of arms.",
            ),
            (
                "owl-2",
                "physical",
                "Owl-folk have a round facial disc, a hooked beak and large forward-facing eyes.",
            ),
            (
                "owl-3",
                "physical",
                "Owl-folk have taloned feet that serve as hands for fine work.",
            ),
            (
                "owl-4",
                "physical",
                "Owl-folk plumage is mottled brown and grey, for camouflage against bark.",
            ),
            (
                "owl-5",
                "physical",
                "Owl-folk have light, hollow bones and can turn their heads nearly all the way around.",
            ),
            (
                "owl-6",
                "instinct",
                "Owl-folk are instinctively crepuscular, most alert at dusk and dawn, and freeze motionless when startled.",
            ),
        ],
    },
    "snowy": {
        "kind": "race",
        "name": "Snowy",
        "species": "owlfolk",
        "measures": [{"name": "wingspan", "min": 8.5, "max": 9, "unit": "ft"}],
        "facts": [
            ("snowy-1", "physical", "Snowy owl-folk are the largest owl-folk."),
            (
                "snowy-2",
                "physical",
                "Snowy owl-folk have white plumage flecked with grey or black.",
                ["owl-4"],
            ),
            ("snowy-3", "physical", "Snowy owl-folk have bright yellow eyes."),
            (
                "snowy-4",
                "instinct",
                "Snowy owl-folk hunt by day as readily as by dusk in the long northern summers.",
            ),
        ],
    },
}


def _fact(entry: tuple) -> tuple[str, str, str, list[str]]:
    fact_id, category, text, *rest = entry
    return fact_id, category, text, (rest[0] if rest else [])


def lineage(thing_id: str) -> list[str]:
    """The thing and its ancestors, most specific first, each once: a
    race's species; a mix's parent A chain, then parent B chain."""

    order: list[str] = []

    def visit(tid: str) -> None:
        if tid in order or tid not in WORLD:
            return
        order.append(tid)
        thing = WORLD[tid]
        if thing["kind"] == "race":
            visit(thing["species"])
        elif thing["kind"] == "mix":
            for parent in thing["parents"]:
                visit(parent)

    visit(thing_id)
    return order


def inherited(thing_id: str) -> list[tuple[str, str, str, str]]:
    """`(fact_id, source_name, category, text)` for every fact `thing_id`
    and its ancestors hold, with any fact a lineage layer overrides
    dropped -- what a character of `thing_id` inherits."""

    chain = lineage(thing_id)
    overridden = {o for tid in chain for e in WORLD[tid]["facts"] for o in _fact(e)[3]}
    out = []
    for tid in chain:
        for entry in WORLD[tid]["facts"]:
            fact_id, category, text, _ = _fact(entry)
            if fact_id not in overridden:
                out.append((fact_id, WORLD[tid]["name"], category, text))
    return out


def heritage_label(thing_id: str) -> str:
    thing = WORLD[thing_id]
    if thing["kind"] == "race":
        return f"{thing['name']} (a race of {WORLD[thing['species']]['name']})"
    if thing["kind"] == "mix":
        a, b = (WORLD[p]["name"] for p in thing["parents"])
        return f"{thing['name']} (a mix of {a} and {b})"
    return f"{thing['name']} (a species)"


# --- the prompts --------------------------------------------------------------
# One TASK and one FORMAT section each, as `world/create-thing.jinja2`.


def calendar_line() -> str:
    return (
        f"The world's calendar: it is now {NOW_LABEL}, year {NOW_YEAR} of the {ERA}. "
        f"The months are {', '.join(MONTHS)}."
    )


SINCE_RULES = (
    '- "since" is optional. Give it only when a fact started at a known time, and only as a year '
    f'of this calendar, as a bare number no later than {NOW_YEAR}; "YEAR" in the example stands '
    'for that number. Leave it out otherwise: never a phrase like "childhood" or "ten years ago".\n'
    '- Leave "since" out for an inherent trait that has always been true -- a species, the '
    "appearance someone is born with, a lifelong temperament -- rather than dating it to the "
    "present year."
)

NUMBER_RULES = (
    '- "lifespan": how long they typically live, in years, as a number.\n'
    '- "adult_age": the age in years at which they are grown, as a number.\n'
    '- "measures": their typical body ranges, each {"name", "min", "max", "unit"} with min and '
    "max as numbers: always height, plus any other measure that matters for this body (wingspan, "
    "tail length, tusk length...)."
)


def inherited_block(
    rows: list[tuple[str, str, str, str]],
) -> tuple[str, dict[str, str]]:
    """The inherited facts as `- F1 (Source, category): text` lines, and
    the label -> fact id map."""

    lines, labels = [], {}
    for i, (fact_id, source, category, text) in enumerate(rows, 1):
        labels[f"F{i}"] = fact_id
        lines.append(f"- F{i} ({source}, {category}): {text}")
    return "\n".join(lines), labels


# Variant "a" is the first wording; "b" is the revision after run 1:
# placeholder numbers, no "since" for heritage kinds, and a stricter
# override rule with an empty "overrides" list in the example; "c" is "b"
# plus, for characters, an explicit check of the prompt against the
# inherited facts; "d" (races only) is "c" with the overrides asked as one
# top-level "no_longer_true" list after the facts instead of per fact.
VARIANT = "a"

HERITAGE_SINCE_RULE_B = (
    '- Leave "since" out: these facts describe the {what} for as long as it has existed, and are '
    "never dated."
)

NUMBERS_PLACEHOLDER_B = (
    "- The 0s in the example are placeholders: give real numbers that fit this {what} and the "
    "owner's prompt."
)


def override_rules(who: str) -> str:
    if VARIANT == "a":
        return OVERRIDE_RULES
    return (
        '- "overrides": the labels of the inherited facts this fact makes untrue for this '
        f'{who}, such as ["F4"]. Use it only for a real contradiction: if an inherited fact says '
        f'"grey fur" and this {who} has black fur, the black-fur fact overrides it. A fact that '
        "adds detail to an inherited fact, builds on it or simply fits with it overrides nothing: "
        '"scarred paws" fits "padded paws", so no label. '
        + (
            "A blended trait overrides the parent facts it replaces, on either side; a fact that "
            "fits both parents has an empty list."
            if who == "mix"
            else "Most facts have an empty list; a reply usually overrides between none and two "
            "inherited facts."
        )
    )


def no_longer_true_rule(source: str, who: str) -> str:
    return (
        f'- "no_longer_true": after the facts, the labels of the {source} that are untrue for '
        f'this {who} now that your facts hold, such as ["F4"]. An inherited fact your facts only '
        "add detail to stays true and isn't listed; an empty list is fine when nothing changes.\n"
    )


def since_rules(what: str | None) -> str:
    """The create template's "since" rules; for a heritage kind in
    variant b, a plain "leave it out"."""

    if VARIANT == "a" or what is None:
        return SINCE_RULES
    return HERITAGE_SINCE_RULE_B.format(what=what)


def numbers_example(name: str = "...") -> str:
    if VARIANT == "a":
        return (
            '{"name": "'
            + name
            + '", "lifespan": 80, "adult_age": 16, "measures": [{"name": '
            '"height", "min": 5, "max": 6, "unit": "ft"}], '
        )
    return (
        '{"name": "' + name + '", "lifespan": 0, "adult_age": 0, "measures": [{"name": '
        '"height", "min": 0, "max": 0, "unit": "ft"}], '
    )


def overrides_example() -> str:
    return '"overrides": ["F1"]' if VARIANT == "a" else '"overrides": []'


def placeholder_rule(what: str) -> str:
    return "" if VARIANT == "a" else NUMBERS_PLACEHOLDER_B.format(what=what) + "\n"


OVERRIDE_RULES = (
    '- "overrides" is optional, on any fact: the labels of the inherited facts that this fact '
    'replaces or contradicts, such as "overrides": ["F2"]. Give it only when your fact and the '
    "inherited one can't both be true. Leave it out otherwise -- most facts override nothing."
)


def species_prompt(prompt: str) -> str:
    return (
        "<|SECTION:TASK|>\n"
        "You create a new species for a fantasy world from the owner's short prompt. Treat the "
        "prompt as intent, not a spec: invent plausible detail generously to fill it out, turning a "
        "rough idea into a fleshed-out one. Keep everything the owner wrote.\n\n"
        "Keep the facts consistent with each other and with the owner's prompt: an invented fact "
        "must never contradict the prompt or another fact.\n\n"
        "A species' facts describe the whole species (typical traits and ranges), not one person. "
        "Instincts are inborn tendencies; leave learned customs out, they belong to cultures.\n\n"
        f"Owner's prompt:\n{prompt}\n\n{calendar_line()}\n<|CLOSE_SECTION|>\n"
        "<|SECTION:FORMAT|>\n"
        "Reply with only one JSON object, shaped exactly like this example:\n"
        + numbers_example()
        + '"facts": [{"category": "origin", "text": "One claim, in a full sentence."'
        + (', "since": "YEAR"' if VARIANT == "a" else "")
        + '}, {"category": "general", "text": "Another claim."}]}\n\n'
        "- \"name\": the species' name. Invent one if the prompt doesn't give it.\n"
        f"{NUMBER_RULES}\n"
        f"{placeholder_rule('species')}"
        '- "facts": between 8 and 12 facts, one claim each. "category" is one of: '
        f"{', '.join(HERITAGE_CATEGORIES)}. physical: the body; instinct: inborn tendencies; "
        "variation: how members differ from each other; origin: where they come from.\n"
        f"{since_rules('species')}\n\n"
        "No commentary, no markdown fences, just the JSON object.\n"
        "<|CLOSE_SECTION|>"
    )


def race_prompt(prompt: str, species_id: str) -> tuple[str, dict[str, str]]:
    species = WORLD[species_id]
    block, labels = inherited_block(inherited(species_id))
    user = (
        "<|SECTION:TASK|>\n"
        f"You create a new race of the {species['name']} species for a fantasy world from the "
        "owner's short prompt. Treat the prompt as intent, not a spec: invent plausible detail "
        "generously to fill it out. Keep everything the owner wrote.\n\n"
        f"Every member of the race already has the {species['name']} facts below. Write only what "
        f"sets this race apart from other {species['name']}: never restate a species fact. Keep "
        "the race consistent with its species: it has the same kind of body, varied.\n\n"
        + (
            "Instincts are inborn tendencies; leave learned customs out (settlements, government, "
            "crafts), they belong to cultures.\n\n"
            "Before writing, check every detail of the owner's prompt against the species facts. "
            "Each detail a species fact contradicts (another colour, another size, a missing trait) "
            "gets a fact of its own"
            + (
                ', and that species fact goes in "no_longer_true".\n\n'
                if VARIANT == "d"
                else ', with that species fact\'s label in "overrides".\n\n'
            )
            if VARIANT in ("c", "d")
            else ""
        )
        + f"Owner's prompt:\n{prompt}\n\n"
        f"{species['name']} numbers: {numbers_resolved(species_id)}.\n"
        f"{species['name']} facts (inherited):\n{block}\n\n"
        f"{calendar_line()}\n<|CLOSE_SECTION|>\n"
        "<|SECTION:FORMAT|>\n"
        "Reply with only one JSON object, shaped exactly like this example:\n"
        + (
            '{"name": "...", "measures": [{"name": "height", "min": 5, "max": 6, "unit": "ft"}], '
            if VARIANT == "a"
            else '{"name": "...", "measures": [{"name": "wingspan", "min": 0, "max": 0, "unit": "ft"}], '
        )
        + '"facts": [{"category": "physical", "text": "One claim, in a full sentence."}, '
        + (
            '{"category": "variation", "text": "Another claim."}], "no_longer_true": []}\n\n'
            if VARIANT == "d"
            else '{"category": "variation", "text": "Another claim.", '
            + overrides_example()
            + "}]}\n\n"
        )
        + "- \"name\": the race's name. Use the prompt's name if it gives one.\n"
        f'- "lifespan", "adult_age" and "measures": give each only where this race differs from '
        f"{species['name']} (a measure narrower or outside the species' range); leave out any "
        "that is the same, it is inherited. lifespan and adult_age are years, as numbers; each "
        f'measure is {{"name", "min", "max", "unit"}}, using the species\' measure names.\n'
        f"{placeholder_rule('race')}"
        '- "facts": between 4 and 8 facts, one claim each, only what is specific to this race. '
        f'"category" is one of: {", ".join(HERITAGE_CATEGORIES)}.\n'
        + (
            no_longer_true_rule("species facts", "race")
            if VARIANT == "d"
            else f"{override_rules('race')}\n"
        )
        + f"{since_rules('race')}\n\n"
        "No commentary, no markdown fences, just the JSON object.\n"
        "<|CLOSE_SECTION|>"
    )
    return user, labels


MIX_RULE = (
    "Blend the two parents into ONE consistent kind of body, the way real mixed parentage looks:\n"
    "- Show clear traits of both sides, each softened or in between (e.g. shorter tusks, a skin "
    "tone between the two).\n"
    "- For the numbers, pick values in between the two parents'.\n"
    "- Never list two traits that contradict each other.\n"
    "- When the blend replaces a parent's trait (shorter tusks than the orc parent, tusks where "
    "the other parent has none), mark that parent fact as overridden."
)


def mix_prompt(
    name: str, parents: tuple[str, str], prompt: str
) -> tuple[str, dict[str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    sections = []
    for side, parent in zip("AB", parents):
        start = len(rows)
        rows += [r for r in inherited(parent) if r[0] not in {x[0] for x in rows}]
        block, _ = inherited_block(rows)
        lines = block.splitlines()[start:]
        sections.append(
            f"Parent {side}: {heritage_label(parent)}. Numbers: {numbers_resolved(parent)}.\n"
            + "\n".join(lines)
        )
    _, labels = inherited_block(rows)
    owner = f"Owner's prompt:\n{prompt}\n\n" if prompt else ""
    user = (
        "<|SECTION:TASK|>\n"
        f"You draft a new mix for a fantasy world: the {name}s, people of mixed parentage from the "
        "two parents below. Its facts describe the mix as a whole (typical traits and ranges), not "
        "one person. Every member already inherits the parents' facts, except the ones you mark "
        "as overridden: write what the blend itself looks like, and don't restate a parent fact "
        "that holds unchanged.\n\n"
        f"{MIX_RULE}\n\n"
        f"{owner}"
        + "\n\n".join(sections)
        + f"\n\n{calendar_line()}\n<|CLOSE_SECTION|>\n"
        "<|SECTION:FORMAT|>\n"
        "Reply with only one JSON object, shaped exactly like this example:\n"
        + numbers_example(name)
        + (
            '"facts": [{"category": "physical", "text": "One claim, in a full sentence."}, '
            '{"category": "instinct", "text": "Another claim."}], "no_longer_true": []}\n\n'
            if VARIANT == "d"
            else '"facts": [{"category": "physical", "text": "One claim, in a full sentence.", '
            + overrides_example()
            + '}, {"category": "instinct", "text": "Another claim."}]}\n\n'
        )
        + f'- "name": "{name}".\n'
        f"{NUMBER_RULES} Use the parents' measure names.\n"
        f"{placeholder_rule('mix')}"
        '- "facts": between 5 and 8 facts, one claim each. "category" is one of: '
        f"{', '.join(HERITAGE_CATEGORIES)}.\n"
        + (
            no_longer_true_rule("parents' facts", "mix")
            if VARIANT == "d"
            else f"{override_rules('mix')}\n"
        )
        + f"{since_rules('mix')}\n\n"
        "No commentary, no markdown fences, just the JSON object.\n"
        "<|CLOSE_SECTION|>"
    )
    return user, labels


def resolve_numbers(thing_id: str) -> dict[str, Any]:
    """The numbers a thing ends up with, field by field and measure by
    measure: its own; else a race's species'; else a mix's parents'
    average (or the one parent that has it)."""

    thing = WORLD[thing_id]
    if thing["kind"] == "species":
        bases = []
    elif thing["kind"] == "race":
        bases = [resolve_numbers(thing["species"])]
    else:
        bases = [resolve_numbers(p) for p in thing["parents"]]
    out: dict[str, Any] = {}
    for key in ("lifespan", "adult_age"):
        values = [b[key] for b in bases if b.get(key) is not None]
        if thing.get(key) is not None:
            out[key] = thing[key]
        elif values:
            out[key] = round(sum(values) / len(values), 1)
    measures: dict[str, dict[str, Any]] = {}
    names = [m["name"] for b in bases for m in b["measures"]]
    for name in dict.fromkeys(names):
        found = [m for b in bases for m in b["measures"] if m["name"] == name]
        measures[name] = {
            "name": name,
            "min": round(sum(m["min"] for m in found) / len(found), 2),
            "max": round(sum(m["max"] for m in found) / len(found), 2),
            "unit": found[0]["unit"],
        }
    for m in thing.get("measures") or []:
        measures[m["name"]] = m
    out["measures"] = list(measures.values())
    return out


def numbers_resolved(thing_id: str) -> str:
    n = resolve_numbers(thing_id)
    parts = []
    if n.get("lifespan") is not None:
        parts.append(f"lifespan {n['lifespan']:g} years")
    if n.get("adult_age") is not None:
        parts.append(f"adult at {n['adult_age']:g}")
    parts += [
        f"{m['name']} {m['min']:g}-{m['max']:g} {m['unit']}" for m in n["measures"]
    ]
    return ", ".join(parts)


def character_prompt(prompt: str, heritage_id: str) -> tuple[str, dict[str, str]]:
    block, labels = inherited_block(inherited(heritage_id))
    user = (
        "<|SECTION:TASK|>\n"
        "You create a new character for a fantasy world from the owner's short prompt. Treat the "
        "prompt as intent, not a spec: invent plausible detail generously to fill it out, turning a "
        "rough idea into a fleshed-out one. Keep everything the owner wrote.\n\n"
        "Keep the facts consistent with each other and with the owner's prompt: an invented fact "
        "must never contradict the prompt or another fact.\n\n"
        f"The character is {heritage_label(heritage_id)}, and already has every inherited fact "
        "below. Write only what is unique to this character: never restate an inherited fact. "
        "Where the owner's prompt differs from an inherited fact, the prompt wins: write the "
        "character's own fact and mark the inherited one it overrides.\n\n"
        + (
            "Before writing, check every detail of the owner's prompt against the inherited facts. "
            "Each detail an inherited fact contradicts (another eye or hair colour, another size, a "
            "missing trait) gets a fact of its own"
            + (
                ', and that inherited fact goes in "no_longer_true". '
                if VARIANT == "d"
                else ', with that inherited fact\'s label in "overrides". '
            )
            + "Check the whole list: the contradicted fact may come from any layer of "
            "the heritage, the species' facts at the bottom included.\n\n"
            if VARIANT in ("c", "d")
            else ""
        )
        + f"Owner's prompt:\n{prompt}\n\n"
        f"Heritage numbers: {numbers_resolved(heritage_id)}.\n"
        f"Inherited facts:\n{block}\n\n"
        f"{calendar_line()}\n<|CLOSE_SECTION|>\n"
        "<|SECTION:FORMAT|>\n"
        "Reply with only one JSON object, shaped exactly like this example:\n"
        + (
            '{"name": "...", "age": 34, "facts": [{"category": "appearance", "text": "One claim, in a '
            'full sentence."}, {"category": "background", "text": "Another claim.", "since": "YEAR"}], '
            '"no_longer_true": []}\n\n'
            if VARIANT == "d"
            else '{"name": "...", "age": 34, "facts": [{"category": "appearance", "text": "One claim, in a '
            f'full sentence.", {overrides_example()}}}, {{"category": "background", "text": "Another '
            'claim.", "since": "YEAR"}]}\n\n'
        )
        + "- \"name\": the character's name. Invent one if the prompt doesn't give it.\n"
        '- "age": how old the character is now, in years, as a number.\n'
        '- "facts": between 8 and 12 facts, one claim each. "category" is one of: '
        f"{', '.join(CHARACTER_CATEGORIES)}.\n"
        + (
            no_longer_true_rule("inherited facts", "character")
            if VARIANT == "d"
            else f"{override_rules('character')}\n"
        )
        + f"{since_rules(None)}\n\n"
        "No commentary, no markdown fences, just the JSON object.\n"
        "<|CLOSE_SECTION|>"
    )
    return user, labels


# --- the model ----------------------------------------------------------------


def render(prompt: str) -> str:
    """Section markers as Talemate's default "titles" sectioning shows
    them to the model: `## Task`, `## Format`."""

    prompt = re.sub(
        r"<\|SECTION:(\w+)\|>", lambda m: f"\n## {m.group(1).capitalize()}", prompt
    )
    return (
        prompt.replace("<|CLOSE_SECTION|>\n", "")
        .replace("<|CLOSE_SECTION|>", "")
        .strip()
    )


def chat(
    user: str, temperature: float = 0.8, max_tokens: int = 1600
) -> tuple[str, float]:
    user = render(user)
    prefill = "{"
    messages = [
        {"role": "system", "content": "You are a helpful worldbuilding assistant."},
        {"role": "user", "content": user},
        {"role": "assistant", "content": prefill},
    ]
    body = json.dumps(
        {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    ).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.loads(r.read())["choices"][0]["message"]["content"]
    if "</think>" in out:
        out = out.split("</think>", 1)[1]
    return prefill + out, time.monotonic() - start


# --- reading a reply ----------------------------------------------------------


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


_STOP = set(
    "a an and the of to in for with by on at as is are be or from their they them its it this that than".split()
)


def _words(text: str) -> set[str]:
    """Content words, singular-ish, without the heritage names: every fact
    of a layer says "Owl-folk" or "Half-orcs", which says nothing about its
    topic."""

    names = {
        w.rstrip("s")
        for thing in WORLD.values()
        for w in re.findall(r"[a-z]+", thing["name"].lower())
    }
    words = {w.rstrip("s") for w in re.findall(r"[a-z]+", text.lower())}
    return {w for w in words if w not in _STOP and len(w) > 2 and w not in names}


def _overlap(a: str, b: str) -> int:
    return len(_words(a) & _words(b))


def analyse(
    reply: str,
    categories: list[str],
    labels: dict[str, str],
    inherited_texts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """What a Task 6 parser would make of `reply`: the wrapper's name, age
    and numbers, the facts (with their categories and override labels
    mapped to fact ids), and what it would drop."""

    objects = json_objects(reply)
    wrapper = next((o for o in objects if isinstance(o.get("facts"), list)), None)
    result: dict[str, Any] = {"parsed": wrapper is not None}
    if wrapper is None:
        return result
    result["name"] = wrapper.get("name")
    result["age"] = wrapper.get("age")
    for key in ("lifespan", "adult_age"):
        if key in wrapper:
            result[key] = (
                _number(wrapper[key])
                if _number(wrapper[key]) is not None
                else f"BAD {wrapper[key]!r}"
            )
    if "measures" in wrapper:
        good, bad = [], []
        for m in (
            wrapper["measures"]
            if isinstance(wrapper["measures"], list)
            else [wrapper["measures"]]
        ):
            ok = (
                isinstance(m, dict)
                and isinstance(m.get("name"), str)
                and _number(m.get("min")) is not None
                and _number(m.get("max")) is not None
                and isinstance(m.get("unit"), str)
            )
            (good if ok else bad).append(m)
        result["measures"] = good
        if bad:
            result["bad_measures"] = bad
    facts, bad_categories, unknown_labels = [], [], []
    for f in wrapper["facts"]:
        if not isinstance(f, dict) or not isinstance(f.get("text"), str):
            continue
        category = str(f.get("category", "")).strip().lower()
        if category not in categories:
            bad_categories.append(category)
        overrides = f.get("overrides") or []
        if isinstance(overrides, str):
            overrides = [overrides]
        mapped = []
        for label in overrides:
            label = str(label).strip()
            if label in labels:
                mapped.append(f"{label}={labels[label]}")
            else:
                unknown_labels.append(label)
        facts.append(
            {
                "category": category,
                "text": f["text"],
                "since": f.get("since"),
                "overrides": mapped,
            }
        )
    result["facts"] = facts
    result["fact_count"] = len(facts)
    result["bad_categories"] = bad_categories
    result["unknown_override_labels"] = unknown_labels
    if isinstance(wrapper.get("no_longer_true"), list):
        result["no_longer_true"] = [str(x) for x in wrapper["no_longer_true"]]
        for label in result["no_longer_true"]:
            if label not in labels:
                unknown_labels.append(label)
    top = [labels[x] for x in result.get("no_longer_true", []) if x in labels]
    if top and inherited_texts:
        # where Task 6 would attach each listed label: the own fact sharing
        # the most content words with the inherited one
        result["attached"] = {
            fact_id: max(
                range(len(facts)),
                key=lambda i: _overlap(facts[i]["text"], inherited_texts[fact_id]),
            )
            for fact_id in top
        }
    result["overridden"] = sorted(
        {m.split("=")[1] for f in facts for m in f["overrides"]} | set(top)
    )
    return result


# --- the cases ----------------------------------------------------------------

SPECIES_PROMPT = "Owl-folk: small feathered people with wings instead of arms, who hunt at dusk in the old forests."
RACE_CASES = [
    (
        "race / Snowy in Owl-folk",
        "Snowy: the largest owl-folk, white-plumaged, from the frozen north.",
        "owlfolk",
        {"owl-4"},
    ),
    (
        "race / Highlander in Human",
        "Highlanders: tall, pale, red-haired humans of the northern hills.",
        "human",
        set(),
    ),
]
SNOWY_PROMPT = (
    "A Snowy owl-folk courier with blue eyes, twenty-two, who carries letters between mountain "
    "villages and talks too much."
)
QUARTER_PROMPT = "A dockhand with red hair, thirty, who runs dice games on the side and owes money to everyone."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument(
        "--only", nargs="*", default=None, help="case label prefixes to run"
    )
    ap.add_argument(
        "--variant", choices=["a", "b", "c", "d"], default="a", help="prompt wording"
    )
    ap.add_argument(
        "--entries",
        help="an earlier run's JSON: reuse its Half-orc and Quarter-orc entries",
    )
    args = ap.parse_args()
    global VARIANT
    VARIANT = args.variant
    runs: list[dict[str, Any]] = []

    def wanted(label: str) -> bool:
        return args.only is None or any(label.startswith(p) for p in args.only)

    def record(
        label: str,
        i: int,
        user: str,
        categories: list[str],
        labels: dict[str, str],
        expected: set[str] | None,
    ):
        reply, seconds = chat(user)
        texts = {
            fact_id: text
            for tid in WORLD
            for (fact_id, _c, text, *_r) in WORLD[tid]["facts"]
        }
        result = analyse(reply, categories, labels, texts)
        if expected is not None and result.get("parsed"):
            got = set(result["overridden"])
            result["override_correct"] = sorted(got & expected)
            result["override_missed"] = sorted(expected - got)
            result["override_spurious"] = sorted(got - expected)
        runs.append(
            {
                "label": label,
                "run": i,
                "seconds": round(seconds, 1),
                "prompt": user,
                "labels": labels,
                "reply": reply,
                "analysis": result,
            }
        )
        print(
            f"\n===== {label} #{i} ({seconds:.0f}s)\n{reply}\n--- {json.dumps({k: v for k, v in result.items() if k != 'facts'})}",
            flush=True,
        )
        with open(args.out, "w") as fh:
            json.dump(runs, fh, indent=2)
        return result

    if wanted("species"):
        for i in range(RUNS):
            record(
                "species / Owl-folk",
                i,
                species_prompt(SPECIES_PROMPT),
                HERITAGE_CATEGORIES,
                {},
                None,
            )

    for label, prompt, species_id, expected in RACE_CASES:
        if wanted(label):
            for i in range(RUNS):
                user, labels = race_prompt(prompt, species_id)
                record(label, i, user, HERITAGE_CATEGORIES, labels, expected)

    if wanted("character / Snowy"):
        for i in range(RUNS):
            user, labels = character_prompt(SNOWY_PROMPT, "snowy")
            record(
                "character / Snowy, blue eyes",
                i,
                user,
                CHARACTER_CATEGORIES,
                labels,
                {"snowy-3"},
            )

    if args.entries:
        with open(args.entries) as fh:
            used = next(
                r for r in json.load(fh) if r.get("label") == "world entries used"
            )
        WORLD["halforc"], WORLD["quarterorc"] = used["halforc"], used["quarterorc"]
        _quarter_characters(record)
        _save_world(args.out, runs)
        return

    if not wanted("mix") and not wanted("character / Quarter"):
        return

    # case 3: Half-orc from Lowlander and Orc, no owner prompt; the first
    # parsed entry becomes the world's Half-orc
    half_orc = None
    for i in range(RUNS):
        user, labels = mix_prompt("Half-orc", ("lowlander", "orc"), "")
        result = record(
            "mix / Half-orc from Lowlander x Orc",
            i,
            user,
            HERITAGE_CATEGORIES,
            labels,
            None,
        )
        if half_orc is None and result.get("parsed"):
            half_orc = result
    if half_orc is None:
        print("no Half-orc entry parsed; stopping")
        return
    WORLD["halforc"] = _as_thing("Half-orc", ("lowlander", "orc"), half_orc, "halforc")

    # the quarter-orc entry: Lowlander x Half-orc, with an owner prompt
    quarter = None
    for i in range(RUNS):
        user, labels = mix_prompt(
            "Quarter-orc",
            ("lowlander", "halforc"),
            "Mostly human to look at; the orc blood shows only a little.",
        )
        result = record(
            "mix / Quarter-orc from Lowlander x Half-orc",
            i,
            user,
            HERITAGE_CATEGORIES,
            labels,
            None,
        )
        if quarter is None and result.get("parsed"):
            quarter = result
    if quarter is None:
        print("no Quarter-orc entry parsed; stopping")
        return
    WORLD["quarterorc"] = _as_thing(
        "Quarter-orc", ("lowlander", "halforc"), quarter, "quarterorc"
    )

    _quarter_characters(record)
    _save_world(args.out, runs)


def _save_world(out: str, runs: list[dict[str, Any]]) -> None:
    with open(out, "w") as fh:
        json.dump(
            runs
            + [
                {
                    "label": "world entries used",
                    "halforc": WORLD["halforc"],
                    "quarterorc": WORLD["quarterorc"],
                }
            ],
            fh,
            indent=2,
            default=list,
        )


def _quarter_characters(record: Any) -> None:
    # expected overrides for "red hair": every surviving inherited fact that
    # gives hair colours red isn't among (Human's "brown, black, fair or red
    # hair" allows red, so it stands)
    hair = {
        r[0]
        for r in inherited("quarterorc")
        if re.search(r"\bhair\b", r[3])
        and re.search(r"black|brown|dark", r[3])
        and not re.search(r"\bred\b", r[3])
    }
    for i in range(RUNS):
        user, labels = character_prompt(QUARTER_PROMPT, "quarterorc")
        record(
            "character / Quarter-orc, red hair",
            i,
            user,
            CHARACTER_CATEGORIES,
            labels,
            hair,
        )


def _as_thing(
    name: str, parents: tuple[str, str], result: dict[str, Any], prefix: str
) -> dict[str, Any]:
    """A drafted mix reply as a world entry, its override labels already
    mapped to parent fact ids."""

    facts = []
    for i, f in enumerate(result["facts"], 1):
        overrides = [m.split("=")[1] for m in f["overrides"]]
        facts.append((f"{prefix}-{i}", f["category"], f["text"], overrides))
    thing = {"kind": "mix", "name": name, "parents": list(parents), "facts": facts}
    for key in ("lifespan", "adult_age", "measures"):
        if isinstance(result.get(key), (int, float, list)):
            thing[key] = result[key]
    return thing


if __name__ == "__main__":
    main()
