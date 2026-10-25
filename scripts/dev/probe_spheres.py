"""Throwaway probe: sphere core, Fill, ties and context in play
(fantasymate spheres, Task 3).

Four probes on Talemate's own KoboldCpp client (the `--ai` app's config, as
`probe_heritage_play` sets it up), each prompt sent through
`Prompt.request` inside `world_ai_call`, as the world screens send theirs.
The sphere prompts are probe templates written to a temp folder and put in
front through `PrependTemplateDirectories`; their context blocks come from
the real Connections helpers (`gather_mentions`, `_found_in_prompt`,
`_named_in_prompt`, `entry_label`, `suggested_prompt`) and the real
`spheres.key_facts`.

Two worlds, present year 1020: **fresh** (the Owl-folk species, its Snowy
race, Humans, the Tsardom of Moscavia with its everyday name "Moscavia",
Kremova, and the White Dawn as a religion-sphere stub that a Tsardom fact
mentions) and **full** (the same, with the White Dawn a whole sphere --
drawers, items, timeline, the Council of Elders, the Pale Spire as a holy
site in Kremova -- and Moscavian culture as a culture sphere).

1. **The core** (`--only 1`): one sphere per template (religion: the White
   Dawn from its stub with the suggested prompt; nation: the Tsardom
   promoted, its facts as context; order, culture, field, other: from a
   prompt), 2 runs each. Reply: name, summary, aka, timeline, a drawer
   outline (typed, titled, 2-4 items each) and names. Checked: complete
   JSON, reply tokens (KoboldCpp's own count), drawer types and titles.
2. **Fill and order** (`--only 2`), 2 runs each:
   - `fill-hierarchy`: Fill the full White Dawn's Hierarchy, which holds
     the Council of Elders and a "Dawn-priests" statement: no rival
     council, no repeat;
   - `fill-rites`: Fill its Rites, which hold the Dawn Vigil and the
     Feather Offering: no repeats;
   - `core-after-council`: the fresh world's White Dawn stub expanded after
     the Council of Elders was made `part_of` it: written around it.
3. **Ties** (`--only 3`): two Snowy owl-folk characters made through the
   real `create.preview_thing` (a copy of `create-thing.jinja2` with a
   spheres block, items labelled S1..., and a `ties` reply key), the full
   world's two spheres in the block, 2 runs each. A sphere the prompt names
   is shown in the spheres block only (`_named_in_prompt` leaves spheres
   out), as Task 6 would.
4. **Context in play** (`--only 4`): a scene at the Pale Spire with Ilse
   (human) and Sister Yeva (owl-folk), three cumulative narrator turns
   (`progress_story`), under three World blocks: `none` (the place's own
   facts name the White Dawn only), `plain` (its key facts as a lore-style
   entry) and `guarded` (the same under a lead line asking to bring it in
   only where the scene calls for it). 2 runs. Keyword scan per turn.

Every call's prompt and reply goes to the output JSON after each call.
Not a test: it calls the network. The owner approved this plan's Skyfall
probes (one GPU: calls run one after another)::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_spheres.py OUT.json \\
        [--only 1 2 3 4] [--dry]'

Findings: docs/superpowers/probes/2026-10-22-spheres.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

# the heritage play probe's harness: config, recording client, loading
import probe_heritage_play as harness  # noqa: E402

import talemate.instance as instance  # noqa: E402
import talemate.worldplay.context as context  # noqa: E402
import talemate.worldplay.create as create  # noqa: E402
from talemate.context import ActiveScene  # noqa: E402
from talemate.prompts.base import PrependTemplateDirectories, Prompt  # noqa: E402
from talemate.scene_message import CharacterMessage, NarratorMessage  # noqa: E402
from talemate.world import spheres  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.kinds import TEMPLATE_AGENT  # noqa: E402
from talemate.world.names import everyday_name  # noqa: E402
from talemate.world.store import Source, World  # noqa: E402
from talemate.worldplay.ai import world_ai_call  # noqa: E402
from talemate.worldplay.mentions import (  # noqa: E402
    entry_label,
    gather_mentions,
    suggested_prompt,
)
from talemate.worldplay.persistence import close_world_scene  # noqa: E402
from talemate.worldplay.setup import SetupRef, plan_scene, start_scene  # noqa: E402

PRESENT = WorldDate.of(1020)
RUNS = 2
CORE_KIND = "creative_instruction_2048"
FILL_KIND = "creative_instruction_1024"
TOKENCOUNT_URL = f"{harness.KOBOLDCPP_URL}/api/extra/tokencount"

# --- the world ---------------------------------------------------------------

OWL_FACTS = [
    (
        "origin",
        "In 994, every person in the [[thing:{tsardom}|Tsardom of Moscavia]] "
        "awoke as owl-folk overnight, in what Moscavians call the Night of "
        "Feathers.",
    ),
    ("physical", "Owl-folk have broad feathered wings in place of arms."),
    (
        "physical",
        "Owl-folk use the talons of their feet as hands: to grip, carry, "
        "write and eat.",
    ),
    ("physical", "Owl-folk have large, forward-facing yellow eyes."),
    (
        "instinct",
        "Owl-folk are crepuscular: drowsy at midday, most alert at dusk and dawn.",
    ),
    ("instinct", "Owl-folk go utterly still and silent when startled."),
    ("variation", "Owl-folk plumage ranges from snowy white to barred brown and grey."),
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
    (
        "law",
        "The Tsar rules from [[thing:{kremova}|Kremova]], a city of towers and "
        "roosting galleries.",
    ),
    (
        "law",
        "[[thing:{dawn}|The White Dawn]] is the Tsardom's state church, and "
        "teaches that the Night of Feathers was a purification.",
    ),
    (
        "general",
        "Barges carry timber, furs and amber down the Vesna to the southern ports.",
    ),
]
KREMOVA_FACTS = [
    (
        "description",
        "Kremova is the capital of the Tsardom, a city of towers and roosting "
        "galleries on the Vesna.",
    ),
]

# the full White Dawn: drawer ids, then (drawer, kind, name, facts) items
DOCTRINES, HIERARCHY, RITES, PEOPLE, HOLY_SITES, EVENTS = (
    "d0000001",
    "d0000002",
    "d0000003",
    "d0000004",
    "d0000005",
    "d0000006",
)
DAWN_ABOUT = (
    "The White Dawn is the state church of the Tsardom of Moscavia; it "
    "teaches that the Night of Feathers in 994 was a purification sent by "
    "the Dawn."
)
DAWN_STATEMENTS = [
    (
        DOCTRINES,
        "Snowy owl-folk, white as the first light, are the purest of the "
        "transformed and the closest to the Dawn.",
    ),
    (
        DOCTRINES,
        "The Night of Feathers was a purification: those who were changed "
        "were cleansed, and those left human were passed over.",
    ),
    (HIERARCHY, "Dawn-priests lead each parish and answer to the Council."),
    (
        RITES,
        "On each anniversary of the Night of Feathers, every believer offers "
        "a moulted feather to the altar flame.",
    ),
]
COUNCIL_FACTS = [
    (
        "general",
        "The Council of Elders is the ruling body of the White Dawn: seven "
        "snowy owl-folk elders seated in Kremova.",
    ),
    ("general", "The Council meets at every new moon to rule on doctrine."),
]
DAWN_THINGS = [
    (
        DOCTRINES,
        "lore",
        "The Doctrine of Separation",
        [
            (
                "general",
                "The Doctrine of Separation forbids the faithful to marry or "
                "share a roost with humans.",
            )
        ],
    ),
    (HIERARCHY, "lore", "The Council of Elders", COUNCIL_FACTS),
    (
        RITES,
        "lore",
        "The Dawn Vigil",
        [
            (
                "general",
                "At every dawn the faithful gather in silence on high "
                "galleries to watch the first light.",
            )
        ],
    ),
]
PALE_SPIRE_FACTS = [
    (
        "description",
        "The Pale Spire is a white stone tower in Kremova, the holiest site of "
        "[[thing:{dawn}|the White Dawn]].",
    ),
    (
        "description",
        "Its open galleries face east, over the rooftops of Kremova.",
    ),
]
DAWN_TIMELINE = [
    (870, "Founded by the hermit Orel in the northern forests."),
    (994, "Declared the Night of Feathers a purification."),
    (1007, "Raised the Pale Spire in Kremova as its seat."),
    (1019, "Issued the Doctrine of Separation."),
]
CUSTOMS, LEGENDS, C_PEOPLE, C_EVENTS = "c0000001", "c0000002", "c0000003", "c0000004"
CULTURE_ABOUT = (
    "Moscavian culture is the way of life of the owl-folk of Moscavia: old "
    "human customs reshaped by wings, talons and night-waking."
)
CULTURE_STATEMENTS = [
    (CUSTOMS, "Moscavians greet one another with a slow bow of the head."),
    (
        CUSTOMS,
        "Households keep their windows unshuttered at dusk, the hour of waking.",
    ),
    (LEGENDS, "Moscavians hold that a silent house is a happy one."),
    (LEGENDS, "Old songs say the Tsar's line was the first to change."),
]
FEATHER_DANCE_FACTS = [
    (
        "general",
        "The Feather Dance is a winter dance of circling wings held on the "
        "longest night.",
    )
]
CULTURE_TIMELINE = [
    (1015, "The Feather Dance was banned in Kremova by the White Dawn."),
]


def _drawer(drawer_id: str, type_: str, title: str) -> dict[str, str]:
    return {"id": drawer_id, "type": type_, "title": title}


def _add(rev, kind: str, fields: dict, facts, **refs) -> str:
    thing = rev.create_thing(kind, fields)
    for category, text in facts:
        rev.add_fact(thing, category, text.format(**refs))
    return thing


def build_world(root: Path, full: bool) -> tuple[World, dict[str, str]]:
    """The fresh world (`full` false) or the full one."""

    world = World.create("Spheres probe", root=root)
    world.set_present(PRESENT)
    ids: dict[str, str] = {}
    with world.revision(Source.manual(note="probe")) as rev:
        tsardom = rev.create_thing(
            "place",
            {
                "name": "Tsardom of Moscavia",
                "kind": "country",
                "aka": [{"name": "Moscavia", "tag": "common", "everyday": True}],
            },
        )
        kremova = rev.create_thing(
            "place", {"name": "Kremova", "kind": "city", "parent": tsardom}
        )
        if full:
            dawn = rev.create_thing(
                "sphere",
                {
                    "name": "The White Dawn",
                    "template": "religion",
                    "agent": True,
                    "drawers": [
                        _drawer(DOCTRINES, "beliefs", "Doctrines"),
                        _drawer(HIERARCHY, "structure", "Hierarchy"),
                        _drawer(RITES, "practices", "Rites and Ceremonies"),
                        _drawer(PEOPLE, "people", "People"),
                        _drawer(HOLY_SITES, "places", "Holy Sites"),
                        _drawer(EVENTS, "events", "Timeline"),
                    ],
                },
            )
        else:
            dawn = rev.create_thing(
                "sphere",
                {
                    "name": "The White Dawn",
                    "template": "religion",
                    "stub": {"ignored": False},
                },
            )
        refs = {"tsardom": tsardom, "kremova": kremova, "dawn": dawn}
        for category, text in TSARDOM_FACTS:
            rev.add_fact(tsardom, category, text.format(**refs))
        for category, text in KREMOVA_FACTS:
            rev.add_fact(kremova, category, text.format(**refs))
        owl = _add(
            rev,
            "species",
            {"name": "Owl-folk", "lifespan": 60, "adult_age": 16},
            OWL_FACTS,
            **refs,
        )
        snowy = _add(rev, "race", {"name": "Snowy", "species": owl}, SNOWY_FACTS)
        human = _add(
            rev,
            "species",
            {"name": "Human", "lifespan": 75, "adult_age": 18},
            HUMAN_FACTS,
        )
        ids.update(
            tsardom=tsardom,
            kremova=kremova,
            dawn=dawn,
            owl_folk=owl,
            snowy=snowy,
            human=human,
        )
        if full:
            rev.add_fact(dawn, "about", DAWN_ABOUT)
            for drawer, text in DAWN_STATEMENTS:
                rev.add_fact(dawn, "statement", text, origin={"drawer": drawer})
            for drawer, kind, name, facts in DAWN_THINGS:
                key = name.split()[-1].lower()
                ids[key] = _add(
                    rev,
                    kind,
                    {"name": name, "part_of": {"sphere": dawn, "drawer": drawer}},
                    facts,
                )
            ids["pale_spire"] = _add(
                rev,
                "place",
                {
                    "name": "The Pale Spire",
                    "kind": "temple",
                    "parent": kremova,
                    "part_of": {"sphere": dawn, "drawer": HOLY_SITES},
                },
                PALE_SPIRE_FACTS,
                **refs,
            )
            for year, text in DAWN_TIMELINE:
                rev.add_fact(dawn, "timeline", text, valid_from=WorldDate.of(year))

            culture = rev.create_thing(
                "sphere",
                {
                    "name": "Moscavian culture",
                    "template": "culture",
                    "agent": False,
                    "drawers": [
                        _drawer(CUSTOMS, "practices", "Customs and Holidays"),
                        _drawer(LEGENDS, "beliefs", "Beliefs and Legends"),
                        _drawer(C_PEOPLE, "people", "People"),
                        _drawer(C_EVENTS, "events", "Timeline"),
                    ],
                },
            )
            rev.add_fact(culture, "about", CULTURE_ABOUT)
            for drawer, text in CULTURE_STATEMENTS:
                rev.add_fact(culture, "statement", text, origin={"drawer": drawer})
            ids["feather_dance"] = _add(
                rev,
                "lore",
                {
                    "name": "The Feather Dance",
                    "part_of": {"sphere": culture, "drawer": CUSTOMS},
                },
                FEATHER_DANCE_FACTS,
            )
            for year, text in CULTURE_TIMELINE:
                rev.add_fact(culture, "timeline", text, valid_from=WorldDate.of(year))
            ids["culture"] = culture
    return world, ids


def add_council_to_stub(world: World, ids: dict[str, str]) -> None:
    """Probe 2's child-first case: the Council of Elders, made (expanded
    first) `part_of` the White Dawn stub, in a drawer the stub doesn't have
    yet (so it resolves under Unsorted)."""

    with world.revision(Source.manual(note="probe: council first")) as rev:
        ids["council"] = _add(
            rev,
            "lore",
            {
                "name": "The Council of Elders",
                "part_of": {"sphere": ids["dawn"], "drawer": HIERARCHY},
            },
            COUNCIL_FACTS,
        )


# --- the probe templates -------------------------------------------------------

TEMPLATE_LABELS = {
    "religion": "religion (a faith or church)",
    "nation": "nation",
    "order": "order (an academy, guild, order, council or other body)",
    "culture": "culture",
    "field": "field of knowledge or magic",
    "other": "sphere",
}
# the drawer types the core and Fill write; people, events and branches
# are kept by the app (ties, the timeline, "+ New branch")
TYPE_HELP = {
    "places": "its territory and sites: where it holds sway, is seated, or holy sites",
    "practices": "rites, ceremonies, customs, holidays, techniques",
    "beliefs": "doctrines, values, attitudes, laws, myths and legends",
    "knowledge": "what is known or studied, and its frontier",
    "structure": "ranks, offices, councils, divisions",
}

_NAMES_RULE = (
    '- "names": after the rest, every proper name your {where} use, other '
    "than {own}: people, places, peoples and species, named events, named "
    'groups and named objects, new or already in the world. Each is {{"name", '
    '"kind", "aka"}}: "name" in full, as you wrote it; "kind" one of '
    'character, place, species, race, sphere, event, item, lore; "aka" any '
    "other names you used for the same thing. A faith or church, an order, "
    "academy, guild or council, a culture, or a field of knowledge or magic "
    'is "sphere", with a "template": religion, order, culture or field, '
    "only these (a country or realm is a place; a rank or office is lore). Proper names only: never a description "
    'such as "the postmaster" or "a war", nor a title on its own such as '
    '"the Tsar", nor a people\'s adjective such as "Moscavian" on its own. '
    "An empty list is fine."
)

CONTEXT_BLOCKS = """{%- if mentions %}

Mentioned elsewhere in the world (keep these true):
{% for lead, text in mentions -%}
- {{ lead }}: {{ text }}
{% endfor %}
{%- if about %}
About those (they already exist in the world; let the {{ label }} reflect them):
{% for heading, facts in about -%}
{{ heading }}:
{% for text in facts -%}
- {{ text }}
{% endfor %}
{%- endfor %}
{%- endif %}
{%- endif %}
{%- if named %}

Named in this prompt (these already exist in the world: use them as they are, and never invent a new one in their place):
{% for written, heading, facts in named -%}
"{{ written }}" means {{ heading }}:
{% for text in facts -%}
- {{ text }}
{% endfor %}
{%- endfor %}
{%- endif %}"""

ITEM_RULE = (
    '- Each item is {"name", "text", "kind"}. When the item is a thing of '
    "its own that could get its own entry (a rite, an office, a council, a "
    'doctrine, a text, a site), "name" is its proper name, such as "the '
    'Dawn Vigil", and "kind" is lore, place (a site), item (an object) or '
    'event. For a plain statement ("Priests may not marry."), leave "name" '
    'empty and "kind" out. "text" is one short sentence, under 20 words.'
)

CORE_TEMPLATE = (
    """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
You create a new {{ label }} for a fantasy world from the owner's short prompt. Treat the prompt as intent, not a spec: invent plausible detail generously to fill it out, turning a rough idea into a fleshed-out one. Keep everything the owner wrote.

Keep everything consistent with itself, with the owner's prompt and with what the world already holds below.

{% if agent -%}
The {{ template }} acts in the world: it decides, rules, declares or teaches, so its timeline is what it has said and done.
{%- else -%}
The {{ template }} is a body of knowledge or custom that is acted upon, so its timeline is how it has changed: what began, changed or was banned, proven or disproven.
{%- endif %}

Owner's prompt:
{{ prompt }}
{%- if known %}

Already known about it (keep these true; they stay on its page):
{% for text in known -%}
- {{ text }}
{% endfor %}
{%- endif %}
{%- if part_of %}

Already part of it (these exist and keep their place in it: write the {{ template }} around them, never list them again as items, and never invent a rival or a second one beside them):
{% for heading, facts in part_of -%}
{{ heading }}:
{% for text in facts -%}
- {{ text }}
{% endfor %}
{%- endfor %}
{%- endif %}
"""
    + CONTEXT_BLOCKS
    + """

Its drawers. A {{ template }} starts with these (type: title):
{% for type, title in start_drawers -%}
- {{ type }}: {{ title }}
{% else -%}
- (none: pick what it needs)
{% endfor %}
The drawer types:
{% for type, help in types -%}
- {{ type }}: {{ help }}
{% endfor %}
The world's calendar: it is now {{ now_label }}, year {{ now_year }}. The months are {{ month_names | join(", ") }}.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"name": "...", "summary": "Two sentences.", "aka": [{"name": "...", "tag": "common", "everyday": true}], "timeline": [{"year": YEAR, "text": "What happened, in one short sentence."}], "drawers": [{"type": "beliefs", "title": "..."}, {"type": "practices", "title": "..."}], "items": [{"drawer": "the drawer's title", "name": "...", "text": "One short sentence.", "kind": "lore"}, {"drawer": "the drawer's title", "name": "", "text": "A plain statement, in one short sentence."}], "names": [{"name": "...", "kind": "place", "aka": []}]}

- "name": the {{ template }}'s name.{% if has_name %} Use the name already decided: "{{ name }}".{% else %} Invent one if the prompt doesn't give it.{% endif %}
- "summary": two sentences: what it is, whose it is, and what it stands for.
- "timeline": 2 to 4 moments in its history, oldest first, each {"year", "text"}. "year" is a year of this calendar, as a bare number no later than {{ now_year }}; "YEAR" in the example stands for that number.
- "drawers": its drawer outline. Start from the drawers above: keep each that fits, give it a title that suits this {{ template }}, and drop any it doesn't need; add a drawer of another type only if it clearly needs one. "type" is one of: {{ types | map(attribute=0) | join(", ") }}. Don't write people, a timeline or branches as drawers: the app keeps those.
- "items": 2 to 4 items for each drawer, drawer by drawer, each naming its drawer by its title in "drawer".
"""
    + ITEM_RULE
    + """
- "aka": other names for this {{ template }} itself, if it has any, each {"name", "tag", "everyday"}. "tag" is "proper" for another formal name, or "common" for what people in the world actually call it day to day. Set "everyday" true on the one common name people use most, false on the rest. An empty list is fine.
"""
    + _NAMES_RULE.format(
        where="summary, timeline and items",
        own="this {{ template }}'s own and its items' own names",
    )
    + """

Keep every text to one sentence. No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""
)

FILL_TEMPLATE = (
    """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
You add items to one drawer of {{ name }}, a {{ label }} in a fantasy world. The owner asked to fill its "{{ drawer_title }}" drawer ({{ drawer_type }}: {{ drawer_help }}).

{{ name }} so far:
{{ summary }}
{% if timeline -%}
Timeline:
{% for line in timeline -%}
- {{ line }}
{% endfor -%}
{% endif -%}
{% for title, type, lines in drawers -%}
{{ title }} ({{ type }}){% if title == drawer_title %}, the drawer to fill{% endif %}:
{% for line in lines -%}
- {{ line }}
{% else -%}
- (empty)
{% endfor -%}
{% endfor %}
{%- if part_of %}
Part of it (these exist: build around them, and never invent a rival or a second one beside them):
{% for heading, facts in part_of -%}
{{ heading }}:
{% for text in facts -%}
- {{ text }}
{% endfor %}
{%- endfor %}
{%- endif %}
"""
    + CONTEXT_BLOCKS
    + """
{%- if guard %}

Already in {{ drawer_title }} (never write these again, under their own name or another):
{% for line in existing -%}
- {{ line }}
{% endfor %}
{%- endif %}

Write 3 to 5 new items for {{ drawer_title }} that fit with everything above. Never repeat an item already in any drawer, by its name or in other words; a new item may build on one.

The world's calendar: it is now {{ now_label }}, year {{ now_year }}. The months are {{ month_names | join(", ") }}.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"items": [{"name": "...", "text": "One sentence.", "kind": "lore"}, {"name": "", "text": "A plain statement, in one sentence."}], "names": [{"name": "...", "kind": "place", "aka": []}]}

"""
    + ITEM_RULE
    + "\n"
    + _NAMES_RULE.format(
        where="items",
        own="{{ name }}'s own and the new items' own names",
    )
    + """

No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""
)

# probe 2's last follow-up: the reply key says "new", a statement is
# just {"text"}, and the drawer's items are listed again before the ask
FILL2_TEMPLATE = (
    FILL_TEMPLATE.replace(
        '{"items": [{"name": "...", "text": "One sentence.", "kind": "lore"}, '
        '{"name": "", "text": "A plain statement, in one sentence."}]',
        '{"new_items": [{"name": "...", "text": "One short sentence.", '
        '"kind": "lore"}, {"text": "A plain statement, in one short sentence."}]',
    )
    .replace(
        'For a plain statement ("Priests may not marry."), leave "name" '
        'empty and "kind" out.',
        'For a plain statement ("Priests may not marry."), give only "text".',
    )
    .replace(
        "\nNo commentary, no markdown fences",
        '- "new_items": only what {{ drawer_title }} doesn\'t hold yet: the '
        "items listed under it above are already there, so never write them "
        "again.\n\nNo commentary, no markdown fences",
    )
)
assert "new_items" in FILL2_TEMPLATE and "give only" in FILL2_TEMPLATE
assert "doesn't hold yet" in FILL2_TEMPLATE


# probe 3: the character create template's additions
TIES_EXAMPLE = (
    ', "ties": [{"sphere": "...", "role": "practitioner", "since": "YEAR", '
    '"exceptions": [{"text": "One sentence.", "rejects": "S1"}]}]'
)
TIES_RULES = """- "ties": after the names, the spheres above this character belongs to, each {"sphere", "role", "since", "exceptions"}: "sphere" its name as written above; "role" a word or two for how they belong (practitioner, priest, elder, scholar, member); "since" the year they joined, as a bare number no later than {{ now_year }}, or left out. Only the spheres above: never invent one here. An empty list is fine.
- "exceptions": only where this character departs from the sphere, each {"text", "rejects"}: "text" one sentence on what they reject or do differently, and "rejects" the label of the item it departs from, such as "S3". The character already holds everything else the sphere holds, so never restate it, in an exception or in the facts. Most ties have no exception or one."""
SPHERES_HEAD = (
    "Spheres in the world (faiths, nations, orders, cultures, fields of "
    "knowledge) the character may belong to, each with what it holds, "
    "labelled S1, S2...:"
)


def ties_block(view, sphere_ids: list[str]) -> tuple[str, dict[str, Any]]:
    """The spheres block, and each label's item (`sphere`, `item`)."""

    lines = [SPHERES_HEAD]
    labels: dict[str, Any] = {}
    n = 0
    for sphere_id in sphere_ids:
        state = view.thing(sphere_id)
        template = state.fields.get("template")
        name = view.name_of(sphere_id)
        lines.append(f"{entry_label(name, str(template), everyday_name(state))}:")
        about = next((f for f in state.facts if f.category == "about"), None)
        if about is not None:
            lines.append(f"- {view.render(about.text)}")
        titles = {d.id: d.title for d in spheres.drawers(view, sphere_id)}
        for item in spheres.items(view, sphere_id):
            title = titles.get(item.drawer_id, "")
            if item.thing_id and view.thing(item.thing_id).kind == "place":
                continue
            n += 1
            label = f"S{n}"
            labels[label] = {
                "sphere": name,
                "item": item.name,
                "thing_id": item.thing_id,
                "fact_id": item.fact_id,
            }
            line = spheres._item_line(item)
            lines.append(f"- {label} ({title}): {line}")
    return "\n".join(lines), labels


def character_template(block: str) -> str:
    """`world/create-thing.jinja2` with the spheres block before the
    calendar line and `ties` in the heritage character's reply."""

    source = (
        Path(create.__file__).parents[1]
        / "prompts"
        / "templates"
        / "world"
        / "create-thing.jinja2"
    )
    out = []
    changed = 0
    for line in source.read_text().split("\n"):
        if line.startswith('{"name": "...", "age": 34'):
            assert line.endswith("}"), line
            line = line[:-1] + TIES_EXAMPLE + "}"
            changed += 1
        if line.startswith("No commentary, no markdown fences"):
            out.extend(TIES_RULES.split("\n"))
            out.append("")
        if line.startswith("The world's calendar:"):
            out.extend(block.split("\n"))
            out.append("")
        out.append(line)
    assert changed == 1, changed
    return "\n".join(out)


# --- helpers -----------------------------------------------------------------


def reply_tokens(text: str) -> int | None:
    """KoboldCpp's own token count for `text`."""

    body = json.dumps({"prompt": text}).encode()
    request = urllib.request.Request(
        TOKENCOUNT_URL, body, {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return int(json.loads(response.read())["value"])
    except Exception:  # a count is nice to have
        return None


def reply_object(reply: str, key: str) -> dict[str, Any] | None:
    """The reply's top-level object holding `key`, or None (truncated or
    malformed)."""

    for text in (reply, "{" + reply):
        for obj in create.json_objects(text):
            if key in obj:
                return obj
    return None


def calendar_vars(world: World) -> dict[str, Any]:
    now = create.current_date(world)
    return {
        "now_label": world.calendar.format(now),
        "now_year": now.to_datetime().year,
        "month_names": world.calendar.month_names,
    }


def connections_vars(
    view, prompt: str, stub_id: str | None, label: str
) -> dict[str, Any]:
    """The Connections context as `preview_thing` builds it: a stub's
    mentions and "About those", and the names the prompt uses."""

    gathered = gather_mentions(view, stub_id) if stub_id else None
    in_context = {stub_id} if stub_id else set()
    mentions_, about = [], []
    if gathered is not None:
        in_context |= {m.owner_id for m in gathered.mentioned}
        mentions_ = [
            (
                create._mention_lead(
                    m.owner_name, m.owner_kind, m.category, m.owner_everyday
                ),
                m.text,
            )
            for m in gathered.mentioned
        ]
        about = [
            (entry_label(a.name, a.kind, a.everyday), a.facts)
            for a in gathered.about
            if a.facts
        ]
    picks = create._found_in_prompt(view, prompt, {}, [], in_context)
    named = create._named_in_prompt(view, picks, stub_id)
    return {"mentions": mentions_, "about": about, "named": named, "label": label}


async def ask(client, folder: Path, uid: str, kind: str, variables: dict) -> str:
    """Send the probe template `uid` and return the raw reply."""

    with PrependTemplateDirectories([str(folder)]):
        with world_ai_call():
            response, _extracted = await Prompt.request(
                uid, client, kind, vars=variables
            )
    return response


def drawer_summary(obj: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not obj:
        return []
    found = []
    flat = [i for i in obj.get("items") or [] if isinstance(i, dict)]
    for drawer in obj.get("drawers") or []:
        if not isinstance(drawer, dict):
            continue
        # the flat shape ("items" naming their drawer), or the nested one
        own = drawer.get("items") or [
            i for i in flat if i.get("drawer") == drawer.get("title")
        ]
        found.append(
            {
                "type": drawer.get("type"),
                "title": drawer.get("title"),
                "items": len(own),
                "named": [i.get("name") for i in own if i.get("name")],
            }
        )
    titles = {d.get("title") for d in obj.get("drawers") or [] if isinstance(d, dict)}
    stray = [i for i in flat if i.get("drawer") not in titles]
    if stray:
        found.append(
            {
                "type": None,
                "title": "(no such drawer)",
                "items": len(stray),
                "named": [i.get("name") for i in stray],
            }
        )
    return found


# --- probe 1: the core ---------------------------------------------------------

CORES = [
    ("religion", "stub", None),
    (
        "nation",
        "promote",
        "The Tsardom of Moscavia as a nation: its government, its laws and its lands.",
    ),
    (
        "order",
        "new",
        "The Imperial Academy of Runecraft in Kremova, where owl-folk scholars "
        "study runic magic.",
    ),
    (
        "culture",
        "new",
        "Moscavian culture: the customs and ways of life of the owl-folk of Moscavia.",
    ),
    (
        "field",
        "new",
        "Runic magic: magic worked by carving runes, as practised in Moscavia.",
    ),
    (
        "other",
        "new",
        "The Amber Road: the river trade that carries Moscavian amber south, "
        "and the ways of those who work it.",
    ),
]


def core_vars(
    world: World, ids: dict[str, str], template: str, mode: str, prompt: str | None
) -> dict[str, Any]:
    view = world.view(PRESENT)
    stub_id = ids["dawn"] if mode == "stub" else None
    name = ""
    known: list[str] = []
    if mode == "stub":
        prompt = suggested_prompt(view, stub_id)
        name = view.name_of(stub_id) or ""
    elif mode == "promote":
        name = view.name_of(ids["tsardom"]) or ""
        known = [view.render(f.text) for f in view.thing(ids["tsardom"]).facts]
    part_of = []
    if stub_id:
        for item in spheres.items(view, stub_id):
            if item.thing_id:
                state = view.thing(item.thing_id)
                part_of.append(
                    (
                        entry_label(item.name, state.kind, everyday_name(state)),
                        [view.render(f.text) for f in state.facts],
                    )
                )
    variables = connections_vars(view, prompt, stub_id, TEMPLATE_LABELS[template])
    if mode == "promote":
        # the promoted place is the thing itself, not context about it
        variables["named"] = [n for n in variables["named"] if "Tsardom" not in n[1]]
    start = [
        (type_, title)
        for type_, title in spheres.TEMPLATE_DRAWERS[template]
        if type_ in TYPE_HELP
    ]
    variables.update(
        template=template if template != "other" else "sphere",
        agent=TEMPLATE_AGENT[template],
        prompt=prompt,
        has_name=bool(name),
        name=name,
        known=known,
        part_of=part_of,
        start_drawers=start,
        types=list(TYPE_HELP.items()),
        **calendar_vars(world),
    )
    return variables


async def one_core(client, folder, world, ids, template, mode, prompt) -> dict:
    variables = core_vars(world, ids, template, mode, prompt)
    calls_before = len(client.calls)
    reply = await ask(client, folder, "world.sphere-core", CORE_KIND, variables)
    obj = reply_object(reply, "drawers")
    call = client.calls[calls_before] if len(client.calls) > calls_before else {}
    return {
        "template": template,
        "style": "flat",
        "mode": mode,
        "prompt": variables["prompt"],
        "call": calls_before,
        "seconds": call.get("seconds"),
        "reply_tokens": reply_tokens(reply),
        "complete": obj is not None,
        "name": obj.get("name") if obj else None,
        "summary": obj.get("summary") if obj else None,
        "timeline": obj.get("timeline") if obj else None,
        "drawers": drawer_summary(obj),
        "names": obj.get("names") if obj else None,
        "reply": reply,
    }


async def probe1(client, folder, world, ids, results, save) -> None:
    for template, mode, prompt in CORES:
        for n in range(RUNS):
            entry = await one_core(client, folder, world, ids, template, mode, prompt)
            entry["n"] = n
            results["core"].append(entry)
            save()


# --- probe 2: Fill, and the core after the council ------------------------------


def fill_vars(world: World, sphere_id: str, drawer_id: str) -> dict[str, Any]:
    view = world.view(PRESENT)
    state = view.thing(sphere_id)
    template = state.fields["template"]
    drawers_ = spheres.drawers(view, sphere_id)
    sphere_items = spheres.items(view, sphere_id)
    target = next(d for d in drawers_ if d.id == drawer_id)

    def line(item) -> str:
        # a thing item with all its facts, so no separate "part of" block
        if item.thing_id is None:
            return item.text
        thing = view.thing(item.thing_id)
        return f"{item.name}: " + " ".join(view.render(f.text) for f in thing.facts)

    lines = [
        (
            drawer.title,
            drawer.type,
            [line(i) for i in sphere_items if i.drawer_id == drawer.id],
        )
        for drawer in drawers_
        if drawer.type in TYPE_HELP
    ]
    about = next(f for f in state.facts if f.category == "about")
    name = view.name_of(sphere_id) or ""
    variables = connections_vars(view, "", sphere_id, TEMPLATE_LABELS[template])
    # what's part of the sphere is in its drawers already
    members = {i.thing_id for i in sphere_items if i.thing_id}
    keep = [
        not lead.startswith(tuple(view.name_of(t) + " (" for t in members))
        for lead, _text in variables["mentions"]
    ]
    variables["mentions"] = [m for m, k in zip(variables["mentions"], keep) if k]
    variables["about"] = [
        a
        for a in variables["about"]
        if not a[0].startswith(tuple(view.name_of(t) + " (" for t in members))
    ]
    variables.update(
        name=name,
        template=template,
        drawer_title=target.title,
        drawer_type=target.type,
        drawer_help=TYPE_HELP[target.type],
        guard=False,
        existing=[
            line for title, _t, ls in lines if title == target.title for line in ls
        ],
        summary=view.render(about.text),
        timeline=[
            f"{f.valid_from.to_datetime().year}: {view.render(f.text)}"
            for f in spheres.timeline(view, sphere_id)
        ],
        drawers=lines,
        part_of=[],
        **calendar_vars(world),
    )
    return variables


async def one_fill(
    client, folder, world, sphere_id, drawer_id, case, guard=False, v2=False
) -> dict:
    variables = fill_vars(world, sphere_id, drawer_id)
    variables["guard"] = guard
    calls_before = len(client.calls)
    uid = "world.sphere-fill2" if v2 else "world.sphere-fill"
    reply = await ask(client, folder, uid, FILL_KIND, variables)
    obj = reply_object(reply, "new_items" if v2 else "items")
    if obj and v2:
        obj["items"] = obj["new_items"]
    call = client.calls[calls_before] if len(client.calls) > calls_before else {}
    return {
        "case": case,
        "call": calls_before,
        "seconds": call.get("seconds"),
        "reply_tokens": reply_tokens(reply),
        "complete": obj is not None,
        "existing": dict((t, lines) for t, _type, lines in variables["drawers"]).get(
            variables["drawer_title"]
        ),
        "items": obj.get("items") if obj else None,
        "names": obj.get("names") if obj else None,
        "reply": reply,
    }


async def probe2(client, folder, results, save, root: Path) -> None:
    full, full_ids = build_world(root / "full2", full=True)
    try:
        for case, drawer in (("fill-hierarchy", HIERARCHY), ("fill-rites", RITES)):
            for n in range(RUNS):
                entry = await one_fill(
                    client, folder, full, full_ids["dawn"], drawer, case
                )
                entry["n"] = n
                results["fill"].append(entry)
                save()
    finally:
        full.close()

    fresh, ids = build_world(root / "fresh2", full=False)
    try:
        add_council_to_stub(fresh, ids)
        for n in range(RUNS):
            entry = await one_core(client, folder, fresh, ids, "religion", "stub", None)
            entry.update(case="core-after-council", n=n)
            results["fill"].append(entry)
            save()
    finally:
        fresh.close()


async def probe2_guard(client, folder, results, save, root: Path) -> None:
    """The follow-up: Fill Rites again with the drawer's own items listed
    once more just before the ask, as "never write these again"."""

    full, full_ids = build_world(root / "full2g", full=True)
    try:
        for n in range(RUNS):
            entry = await one_fill(
                client, folder, full, full_ids["dawn"], RITES, "fill-rites-guard", True
            )
            entry["n"] = n
            results["fill"].append(entry)
            save()
    finally:
        full.close()


async def probe2_new(client, folder, results, save, root: Path) -> None:
    """The last follow-up: Fill Rites with `FILL2_TEMPLATE`."""

    full, full_ids = build_world(root / "full2n", full=True)
    try:
        for n in range(RUNS):
            entry = await one_fill(
                client,
                folder,
                full,
                full_ids["dawn"],
                RITES,
                "fill-rites-new-items",
                guard=True,
                v2=True,
            )
            entry["n"] = n
            results["fill"].append(entry)
            save()
    finally:
        full.close()


# --- probe 3: ties at character creation ----------------------------------------

CHARACTERS = [
    (
        "doubter",
        "Vasha, a snowy owl-folk courier who carries letters between the river "
        "towns. She was raised in the White Dawn and still keeps the vigils, "
        "but thinks the talk of snowy owl-folk being purer is nonsense.",
    ),
    (
        "bell-ringer",
        "An old snowy owl-folk bell-ringer at the Pale Spire in Kremova, who "
        "has danced the Feather Dance every winter of his life.",
    ),
]

_last_reply: list[str] = []
_parse = create.parse_create_reply


def _recording_parse(reply, *args, **kwargs):
    _last_reply.append(reply)
    return _parse(reply, *args, **kwargs)


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


_named = create._named_in_prompt


def _named_without_spheres(view, picks, skip):
    """`_named_in_prompt`, leaving out spheres: they're in the spheres
    block, labelled, as Task 6 would show them."""

    return [
        entry
        for entry in _named(view, picks, skip)
        if not entry[1].endswith("(sphere)") and "(sphere," not in entry[1]
    ]


async def probe3(client, tmp: Path, results, save, root: Path) -> None:
    create._preview_prose = _no_prose
    create.parse_create_reply = _recording_parse
    create._named_in_prompt = _named_without_spheres
    world, ids = build_world(root / "full3", full=True)
    view = world.view(PRESENT)
    block, labels = ties_block(view, [ids["dawn"], ids["culture"]])
    results["ties_labels"] = labels
    folder = tmp / "ties"
    folder.mkdir()
    (folder / "create-thing.jinja2").write_text(character_template(block))
    try:
        for case, prompt in CHARACTERS:
            for n in range(RUNS):
                _last_reply.clear()
                calls_before = len(client.calls)
                error = preview = None
                try:
                    with PrependTemplateDirectories([str(folder)]):
                        preview = await create.preview_thing(
                            world,
                            "character",
                            prompt,
                            {"heritage": ids["snowy"]},
                            client,
                        )
                except Exception as exc:  # a bad reply is a finding
                    error = repr(exc)
                reply = _last_reply[-1] if _last_reply else ""
                obj = reply_object(reply, "facts") or {}
                ties = obj.get("ties") or []
                for tie in ties:
                    for exc in tie.get("exceptions") or []:
                        exc["rejected_item"] = labels.get(exc.get("rejects"), {}).get(
                            "item"
                        )
                results["ties"].append(
                    {
                        "case": case,
                        "n": n,
                        "prompt": prompt,
                        "call": calls_before,
                        "error": error,
                        "reply_tokens": reply_tokens(reply),
                        "name": preview.name if preview else obj.get("name"),
                        "facts": [
                            {"category": f.category, "text": f.text}
                            for f in (preview.facts if preview else [])
                        ],
                        "ties": ties,
                        "reply": reply,
                    }
                )
                save()
    finally:
        world.close()
        create._named_in_prompt = _named


# --- probe 4: context in play ----------------------------------------------------

SETUP = {
    "player": "Ilse",
    "characters": [
        {
            "name": "Ilse",
            "facts": [
                "A young human trader carrying a sealed letter for the elders "
                "of the Pale Spire."
            ],
        },
        {
            "name": "Sister Yeva",
            "facts": [
                "A dawn-priestess of the Pale Spire, small and brown-barred, "
                "with a soft voice.",
            ],
            "heritage": "Owl-folk",
        },
    ],
    "place": {"name": "The Pale Spire", "facts": []},
    "goal": "Deliver the sealed letter to the elders.",
    "intro": "Before dawn, Ilse climbs the last stair of the Pale Spire as the "
    "faithful gather on the east gallery.",
}
HISTORY_LINES = [
    "Ilse: Excuse me -- I have a letter for the elders. Is this the right place?",
]
DIRECTIONS = [
    "Dawn breaks and the faithful on the gallery begin their morning "
    "observance. Describe it as Ilse watches from the edge.",
    "Sister Yeva notices that Ilse is human and comes over to ask why she is here.",
    "Ilse is hungry after the long climb. Sister Yeva points her down to the "
    "bakers' market below the spire; describe the walk down and the market.",
]
SCENE_VARIANTS = ("none", "plain", "guarded")
GUARDED_LEAD = (
    "Spheres this scene touches (faiths, nations, orders, cultures): keep "
    "what they hold true, and bring it in only where the scene calls for it."
)

_SCAN = {
    "white_dawn": r"white dawn",
    "vigil_silence": r"\bvigil\b|\bsilen",
    "first_light": r"first light",
    "purity_snowy": r"\bpur(e|est|ity|if)|\bsnowy\b",
    "separation_humans": r"separation|passed over|\bhumans?\b",
    "council_elders": r"council|\belders?\b",
    "feather_offering": r"moulted feather|altar flame|feather to",
    "night_of_feathers": r"night of feathers",
    "doctrine": r"\bdoctrine",
}


def scan(text: str) -> dict[str, int]:
    lowered = text.lower()
    return {key: len(re.findall(pattern, lowered)) for key, pattern in _SCAN.items()}


def sphere_lines(world: World, sphere_id: str, at: WorldDate) -> tuple[str, list[str]]:
    view = world.view(at)
    state = view.thing(sphere_id)
    heading = entry_label(
        view.name_of(sphere_id) or "", str(state.fields.get("template")), None
    )
    # key_facts' timeline lines carried no year when this ran (Task 7 dates
    # them since): the probe dated them itself
    lines = spheres.key_facts(view, sphere_id)
    latest = spheres.timeline(view, sphere_id)[-3:]
    dated = [
        f"In {f.valid_from.to_datetime().year}: {view.render(f.text)}"
        if f.valid_from
        else view.render(f.text)
        for f in latest
    ]
    return heading, lines[: len(lines) - len(latest)] + dated


def _variant_block(original, variant: str, sphere_id: str):
    def block(world, record, at):
        text = original(world, record, at)
        if variant == "none":
            return text
        heading, lines = sphere_lines(world, sphere_id, at)
        part = [""]
        if variant == "guarded":
            part.append(GUARDED_LEAD)
        part.append(heading)
        part.extend(f"- {line}" for line in lines)
        insert = "\n".join(part) + "\n"
        marker = "\nWho is here, by heritage"
        if marker in text:
            return text.replace(marker, "\n" + insert.rstrip("\n") + "\n" + marker, 1)
        return text.replace("[end of world]", insert.lstrip("\n") + "[end of world]")

    return block


async def probe4(client, results, save, root: Path) -> None:
    world, ids = build_world(root / "full4", full=True)
    setup = await plan_scene(
        world,
        "Ilse delivers a letter at the Pale Spire",
        {},
        None,
        PRESENT,
        None,
        reply=SETUP,
    )
    setup.place = SetupRef(thing_id=ids["pale_spire"])
    setup.pulled_in = [ids["tsardom"]]
    scene_id = await start_scene(world, setup, None)
    record = world.scenes().get(scene_id)
    original = context.world_context_block
    results["scene"]["world_blocks"] = {
        v: _variant_block(original, v, ids["dawn"])(world, record, PRESENT)
        for v in SCENE_VARIANTS
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
            for n in range(RUNS):
                for variant in SCENE_VARIANTS:
                    scene.history = list(base_history)
                    context.world_context_block = _variant_block(
                        original, variant, ids["dawn"]
                    )
                    try:
                        for index, direction in enumerate(DIRECTIONS):
                            calls_before = len(client.calls)
                            text = await narrator.progress_story(
                                narrative_direction=direction
                            )
                            await scene.push_history(
                                [NarratorMessage(text, source="ai")]
                            )
                            prompt = (
                                client.calls[calls_before]["prompt"]
                                if len(client.calls) > calls_before
                                else ""
                            )
                            results["scene"]["runs"].append(
                                {
                                    "n": n,
                                    "variant": variant,
                                    "turn": index + 1,
                                    "direction": direction,
                                    "output": text,
                                    "words": len(text.split()),
                                    "scan": scan(text),
                                    "block_in_prompt": "Separation" in prompt,
                                }
                            )
                            save()
                    finally:
                        context.world_context_block = original
    finally:
        close_world_scene(scene)
        world.close()


# --- main ----------------------------------------------------------------------


def write_templates(folder: Path) -> None:
    (folder / "sphere-core.jinja2").write_text(CORE_TEMPLATE)
    (folder / "sphere-fill.jinja2").write_text(FILL_TEMPLATE)
    (folder / "sphere-fill2.jinja2").write_text(FILL2_TEMPLATE)


async def main(out: Path, only: list[str]) -> None:
    harness._quiet_loading(False)
    client = harness.RecordingClient(name="KoboldCpp")
    await client.status()

    results: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {
            "probe": "spheres",
            "date": "2026-10-22",
            "model": client.model_name,
            "prompt_template": client.prompt_template_example()[1],
            "core": [],
            "fill": [],
            "ties": [],
            "scene": {"runs": []},
            "calls": [],
        }
    )
    client.calls = results["calls"]

    def save() -> None:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    client.on_call = save
    started = time.monotonic()

    with tempfile.TemporaryDirectory() as root:
        os.chdir(root)
        root_path = Path(root)
        folder = root_path / "templates"
        folder.mkdir()
        write_templates(folder)
        if "1" in only:
            world, ids = build_world(root_path / "fresh1", full=False)
            try:
                await probe1(client, folder, world, ids, results, save)
            finally:
                world.close()
        if "2" in only:
            await probe2(client, folder, results, save, root_path)
        if "2g" in only:
            await probe2_guard(client, folder, results, save, root_path)
        if "2n" in only:
            await probe2_new(client, folder, results, save, root_path)
        if "3" in only:
            await probe3(client, root_path, results, save, root_path)
        if "4" in only:
            await probe4(client, results, save, root_path)
    results.setdefault("minutes", {})[" ".join(only)] = round(
        (time.monotonic() - started) / 60, 1
    )
    save()


def dry() -> None:
    """Print each prompt's template variables rendered, calling nothing."""

    harness._quiet_loading(False)
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        folder = root_path / "templates"
        folder.mkdir()
        write_templates(folder)
        world, ids = build_world(root_path / "fresh", full=False)
        with PrependTemplateDirectories([str(folder)]):
            for template, mode, prompt in CORES[:2]:
                print(
                    Prompt.get(
                        "world.sphere-core",
                        core_vars(world, ids, template, mode, prompt),
                    )
                )
                print("=" * 70)
            add_council_to_stub(world, ids)
            print(
                Prompt.get(
                    "world.sphere-core", core_vars(world, ids, "religion", "stub", None)
                )
            )
            print("=" * 70)
        world.close()
        full, full_ids = build_world(root_path / "full", full=True)
        with PrependTemplateDirectories([str(folder)]):
            print(
                Prompt.get(
                    "world.sphere-fill", fill_vars(full, full_ids["dawn"], HIERARCHY)
                )
            )
            print("=" * 70)
        view = full.view(PRESENT)
        block, labels = ties_block(view, [full_ids["dawn"], full_ids["culture"]])
        print(block)
        print(json.dumps(labels, indent=1))
        print("=" * 70)
        for line in character_template(block).split("\n"):
            if "ties" in line or line.startswith('{"name": "...", "age": 34'):
                print(line)
        print("=" * 70)
        print("\n".join(sphere_lines(full, full_ids["dawn"], PRESENT)[1]))
        full.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path, nargs="?")
    parser.add_argument("--only", nargs="+", default=["1", "2", "3", "4"])
    parser.add_argument(
        "--dry", action="store_true", help="print prompts, call nothing"
    )
    args = parser.parse_args()
    if args.dry:
        dry()
    else:
        asyncio.run(main(args.out.resolve(), args.only))
