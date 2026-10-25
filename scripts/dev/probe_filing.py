"""Throwaway probe: filing, tags and prompt hints on Skyfall (Filing plan, Task 1).

Six probes on a copy of the owner's Curation acceptance world, against hand
labels committed before any model call
(`docs/superpowers/probes/raw/2026-10-23-filing-labels.json`). The labels
also hold the hand-made presentation of that world under the new model:
every entry a plain entry (the sphere kind gone: a nation is a place, a
council or order is lore) with one hand-picked tag and its filings ("in",
with roles), and the thin role and topic stubs left out.

1. **The create reply** (`--only p1`): the app's own `create.preview_thing`
   (so the Mentioned / About / Named blocks and the heritage branch are the
   app's), with its template swapped for the filing one (`create_template`:
   `tag`, `in`, `file_into`, names with `tag` and `in`, "only named things
   become entries"; no `move_in`, no sphere kind) and its variables changed
   through a wrapper on `Prompt.request`: the "Entries near this one" lines
   are plain entries ("Name (kind, tag; usually called X; in A (role), B;
   stub): summary"), the tags in use are listed, and no spheres block. Each
   case re-makes an entry of the world as a stub (its facts, part_of and
   other names removed; entries its own write made, removed).
2. **File into** (`--only p2`): the same call, with the White Talon and the
   Frosted Wing seeded as regiments.
3. **Group synopsis** (`--only p3`): a new small prompt, at `analyze`.
4. **Prompt hints** (`--only p4`): the create call with a hint, and a
   `belief` category under the religion and culture hints.
5. **The scene world block** (`--only p5`): the owner's scene (Vasha at the
   Academy) played two narrator turns with Talemate's own narrator, the
   "World" instruction built from filings (`filing_block`), against today's
   block (`p5old`).
6. **Group "+ Add"** (`--only p6`): a new small prompt, at Fill's kind.

Every call goes through Talemate's KoboldCpp client (the `--ai` app's
config) at the app's own kinds: create `creative_instruction_3072`, "+ Add"
`creative_instruction_1024` (Fill's; both the creative_instruction preset),
the synopsis `analyze` (analytical, as prose is written). Each call's
prompt, reply, seconds and KoboldCpp token counts go to the output JSON
after the call. The world is copied to a temp folder for every case.

Not a test: it calls the network. Approved by the owner ("you have
permissions to use skyfall for any tasks"); one GPU, one call at a time::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_filing.py OUT.json \\
        [--only p1 p2 p3 p4 p5 p5old p6] [--cases ...] [--runs 2] [--dry]'

`--dry` prints each prompt instead of sending it. Findings:
`docs/superpowers/probes/2026-10-23-filing.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_heritage_play as harness  # noqa: E402  (config, recording client)
import probe_curation as curation  # noqa: E402  (count_tokens, reply_object)

import talemate.instance as instance  # noqa: E402
import talemate.worldplay.context as wp_context  # noqa: E402
import talemate.worldplay.create as create  # noqa: E402
from talemate.context import ActiveScene  # noqa: E402
from talemate.prompts.base import PrependTemplateDirectories, Prompt  # noqa: E402
from talemate.scene_message import NarratorMessage  # noqa: E402
from talemate.world import entries, spheres  # noqa: E402
from talemate.world.dates import WorldDate  # noqa: E402
from talemate.world.names import everyday_name  # noqa: E402
from talemate.world.refs import ref  # noqa: E402
from talemate.world.store import Source, World  # noqa: E402
from talemate.world.view import WorldView  # noqa: E402
from talemate.worldplay.ai import world_ai_call  # noqa: E402
from talemate.worldplay.links import name_key  # noqa: E402
from talemate.worldplay.mentions import mentions as all_mentions  # noqa: E402
from talemate.worldplay.mentions import suggested_prompt  # noqa: E402
from talemate.worldplay.persistence import close_world_scene  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(
    "/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/"
    "66f9fa9e-6364-4353-bfde-ff936563332e/scratchpad/filing/world"
)
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-23-filing-labels.json"
TEMPLATES = REPO / "src/talemate/prompts/templates/world"
SYNOPSIS_KIND = "analyze"
ADD_KIND = "creative_instruction_1024"
LINE_CHARS = 130
OWN_FACTS = 5
TIMELINE_LINES = 3
ENTRY_LINES = 8
TIMELINE_REACH = 2
# how many entries the create prompt lists as near
CANDIDATES = 24

# --- the create template ----------------------------------------------------------

HINT_BLOCK = """{%- if hint %}

Prompt hint, picked by the owner: {{ hint }} Write what fits the prompt and the world; leave out what doesn't.
{%- endif %}
"""

TAGS_BLOCK = """{%- if tags %}

Tags in use in the world (each entry has one tag saying what it is), with how many entries carry each:
{{ tags | join(", ") }}
{%- endif %}"""

FILING_EXAMPLE = (
    '{% if nearby %}, "in": [{"entry": "<an entry\'s name>", "role": "a few words"}], '
    '"file_into": [{"entry": "<an entry\'s name>", "role": null}]{% endif %}'
)
NAMES_EXAMPLE_OLD = '"names": [{"name": "...", "kind": "place", "aka": []}]'
NAMES_EXAMPLE_NEW = (
    '"names": [{"name": "...", "kind": "place", "tag": "...", "in": null, "aka": []}]'
)

NAMES_RULE_OLD_START = '- "names": after the facts, every proper name'
NAMES_RULE_NEW = (
    '- "names": after the facts, every proper name your facts use, other than this '
    "{{ kind }}'s own: people, places, peoples and species, named events, named groups "
    'and named objects, new or already in the world. Each is {"name", "kind", "tag", '
    '"in", "aka"}: "name" in full, as your facts write it; "kind" one of character, '
    "place, species, race, event, item, lore (a country, realm or city is a place; a "
    "faith, order, council, guild, culture, field of knowledge or magic, law, script or "
    'language is lore); "tag" what it is, as for the {{ kind }}; "in" the name of the '
    "entry it belongs in (this {{ kind }}, an entry listed above, or another of your "
    'names), or null; "aka" any other names your facts use for the same thing. Proper '
    'names only: never a description such as "the postmaster", "a war" or "his mother", '
    'nor a title on its own such as "the Tsar" or "the High Bishop", nor a people\'s '
    'adjective such as "Moscavian" on its own -- but "Yelena" in "his mother Yelena" '
    "is a name. An empty list is fine.\n"
    "- Only named things become entries. A role, rank or office (a harbour master, "
    "the keeper of the seals), a topic (grain tariffs, winter trade) or a practice "
    "without a proper name of its own (the evening bell, night sessions) is never one "
    'of the "names": it stays a fact of the {{ kind }}.'
)

FILING_RULES = (
    "\n{%- if nearby %}\n"
    '- "tag": one or two words for what the {{ kind }} is, such as river, ruler, '
    "custom, institution, regiment, capital or doctrine. Use a tag from the tags in "
    "use when one fits; make a new one only when none does.\n"
    '- "in": the entries listed above that the {{ kind }} belongs in, each {"entry", '
    '"role"}: "entry" the entry\'s name as the list writes it; "role" a few words for '
    'how it belongs there ("flows through", "sovereign", "practitioner", "branch of", '
    '"taught here"), or null. A thing can be in several entries: a road in each realm '
    "it crosses, a temple in its city and in the faith it serves. Only entries from "
    "the list; an empty list is fine.\n"
    '- "file_into": the entries listed above that belong in this {{ kind }}: its '
    'parts, members, branches or what it holds, each {"entry", "role"}, "role" how '
    "that entry belongs in this {{ kind }}, or null. Never an entry you put in "
    '"in". Only entries from the list; an empty list is fine.\n'
    "{%- endif %}"
    '\n{%- if "belief" in categories %}\n'
    '- "belief": a fact that says what the {{ kind }}\'s followers believe or teach '
    "(that the dead return as stars, that the river's spirit grants the harvest), "
    "rather than plain truth of the world. Its rites as practised, its clergy, places, "
    "ranks and history are plain truth, in the other categories.\n"
    "{%- endif %}"
)

BROADER_BLOCK = """{%- if broader %}

{{ broader_name }} is the broader entry this {{ kind }} is part of. What {{ broader_name }} says now, labelled M1, M2...:
{% for label, text in broader -%}
- {{ label }}: {{ text }}
{% endfor %}
{%- endif %}"""

MOVE_IN_RULE = (
    "\n{%- if broader %}\n"
    "- \"move_in\": the labels of {{ broader_name }}'s facts above that are mainly about "
    "this {{ kind }}, so they belong on its page rather than on {{ broader_name }}'s. "
    "They move here: don't write them again in \"facts\". A fact that only mentions "
    "the {{ kind }} in passing stays where it is. An empty list is fine.\n"
    "{%- endif %}"
)


def _swap(source: str, old: str, new: str, count: int = 1) -> str:
    assert source.count(old) == count, (old[:70], source.count(old))
    return source.replace(old, new)


def create_template() -> str:
    source = (TEMPLATES / "create-thing.jinja2").read_text()
    # the hint after the owner's prompt, before the context blocks
    source = _swap(source, "{%- endif %}\n{%- if mentions %}", "{%- endif %}\n" + HINT_BLOCK + "{%- if mentions %}")
    # move-in goes (spec: "Could move here" is found by code alone)
    source = _swap(source, "\n" + BROADER_BLOCK, "\n" + TAGS_BLOCK)
    source = _swap(source, ', "move_in": ["<an M label>"]', "")
    source = _swap(source, MOVE_IN_RULE, "")
    # the sphere kind and its ties go
    source = _swap(
        source,
        '{% if spheres %}, "ties": [{"sphere": "...", "role": "practitioner", "since": "YEAR", "exceptions": [{"text": "One sentence.", "rejects": "S1"}]}]{% endif %}',
        "",
        count=2,
    )
    # tag after "aka"; in and file_into after the names, in the two
    # branches a filed entry is written in (heritage character, generic)
    source = _swap(
        source,
        '"aka": [{"name": "...", "tag": "common", "everyday": true}], "facts": [{"category": "{{ categories[0] }}"',
        '"aka": [{"name": "...", "tag": "common", "everyday": true}], "tag": "...", "facts": [{"category": "{{ categories[0] }}"',
        count=2,
    )
    source = _swap(
        source,
        NAMES_EXAMPLE_OLD + '{% if nearby %}, "elsewhere"',
        NAMES_EXAMPLE_NEW + FILING_EXAMPLE + '{% if nearby %}, "elsewhere"',
    )
    source = _swap(
        source,
        '"since": "YEAR"}], ' + NAMES_EXAMPLE_OLD + "}",
        '"since": "YEAR"}], ' + NAMES_EXAMPLE_NEW + FILING_EXAMPLE + "}",
    )
    # the names rule, without the sphere kind, plus the named-only rule
    start = source.index(NAMES_RULE_OLD_START)
    end = source.index("\n", start)
    source = source[:start] + NAMES_RULE_NEW + source[end:]
    # the filing rules after the elsewhere rules (and after the names, for
    # the heritage branch, which has no elsewhere block)
    source = _swap(source, "\n{%- if spheres %}\n- \"ties\"", FILING_RULES + "\n{%- if spheres %}\n- \"ties\"")
    return source


SYNOPSIS_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
Write the synopsis of one group on a page of a fantasy world's records: the {{ group }} filed in {{ page }}. It stands above the group's list and tells the reader at a glance what the group holds and how its members relate to each other and to {{ page }}.

Use only what the entries below say. Never add a name, date, number, rank or claim they don't give, and never guess at what a stub (an entry with little written yet) is.

{{ page }}: {{ page_summary }}

The {{ group }} filed in {{ page }}, each with its role there and what its entry says:
{% for member in members -%}
{{ member.label }}:
{% for text in member.facts -%}
- {{ text }}
{% endfor %}
{%- endfor %}
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"synopsis": "Two or three sentences."}

Two or three sentences, at most 70 words, naming each member once. No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""

ADD_COUNT_V1 = "Write what the owner asked for: between 1 and 3 new entries, each"
ADD_COUNT_V2 = (
    "Write what the owner asked for, as many as they asked for: one when they ask for one "
    '("a guild", "an inn"), and never more than 3. Each new entry is'
)
ADD_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
You add new entries to one group on a page of a fantasy world's records: the "{{ tag }}" group of {{ page }}. The owner asked for: {{ prompt }}

Write what the owner asked for: between 1 and 3 new entries, each tagged "{{ tag }}" and filed in {{ page }}. Each is a named thing with a proper name that fits the world, never a role, topic or practice without a name of its own. Keep each consistent with {{ page }} and the world, and never write again an entry the world already has (they are listed below).

{{ page }} ({{ page_kind }}{% if page_tag %}, {{ page_tag }}{% endif %}):
{% for text in page_facts -%}
- {{ text }}
{% endfor %}
Already in its "{{ tag }}" group: {% if members %}{{ members | join("; ") }}{% else %}nothing yet{% endif %}.
{%- if filed %}
Also filed in {{ page }}: {{ filed | join("; ") }}.
{%- endif %}
{%- if nearby %}
Other entries near it: {{ nearby | join("; ") }}.
{%- endif %}

The world's calendar: it is now {{ now_label }}, year {{ now_year }}.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"entries": [{"name": "...", "kind": "lore", "tag": "{{ tag }}", "line": "One claim saying what it is, in a full sentence."}]}

- "name": the entry's proper name, in full.
- "kind": one of character, place, species, race, event, item, lore (a faith, order, guild, council, custom, law or field of knowledge is lore).
- "tag": "{{ tag }}".
- "line": one sentence saying what it is and how it belongs in {{ page }}.

No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""

SCENE_TEMPLATE = """[world]
{% if everyday -%}
In narration and dialogue, call things by their everyday names: where a name is followed by "usually called ...", use that name, and keep the full name for formal moments.
{% endif -%}
{% if goal -%}
Goal: {{ goal }}
{% endif -%}
{% if place -%}
Place: {{ place.name }}{% if place.everyday %} (usually called {{ place.everyday }}){% endif %}
{% for fact in place.facts -%}
- {{ fact }}
{% endfor -%}
{% endif -%}
{% if touched %}
What this scene touches: keep what these say true, and bring it in only where the scene calls for it.
{% for entry in touched -%}
{{ entry.name }} ({{ entry.tag or entry.kind }}{% if entry.everyday %}, usually called {{ entry.everyday }}{% endif %})
{% for line in entry.lines -%}
- {{ line }}
{% endfor %}
{% endfor -%}
{% endif -%}
{% if cast %}
Who is here, by heritage (keep every description and action true to these bodies and instincts):
{% for member in cast -%}
- {{ member.name }}{% if member.heritage %} ({{ member.heritage }}){% endif %}:{% for fact in member.body %} {{ fact }}{% endfor %}{% if member.instincts %} Instincts:{% for fact in member.instincts %} {{ fact }}{% endfor %}{% endif %}
{% endfor -%}
{% endif -%}
[end of world]
"""


BELIEF_V2 = (
    '- "belief": every fact that says what the {{ kind }} teaches, holds or believes ("it '
    'teaches that...", "the faithful hold that...", "its doctrine says...") is a "belief", never '
    '"general". Plain truth of the world -- its rites as practised, its clergy, places, ranks and '
    "history -- goes in the other categories."
)
BELIEF_V1_START = '- "belief": a fact that says what'

# v2, after v1 missed the second home in a field or a people (the Academy in
# Runic Magic 0/2, Plumage Signaling in the Owl-folk 0/2), filed Wattles
# "in" its own parts, tagged the Frostwing Host "regiment" from its
# regiments, gave names the aka tags "proper"/"common", and offered the
# White Talon only through its name's "in"
V2_SWAPS = [
    (
        "Use a tag from the tags in use when one fits; make a new one only when none does.",
        "It says what the {{ kind }} itself is, not what its parts or members are. Use a tag "
        "from the tags in use when one fits; make a new one only when none does.",
    ),
    (
        '"tag" what it is, as for the {{ kind }};',
        '"tag" what it is, as for the {{ kind }} (never "proper" or "common": those are only '
        "for other names);",
    ),
    (
        "A thing can be in several entries: a road in each realm it crosses, a temple in its city "
        "and in the faith it serves. Only entries from the list; an empty list is fine.",
        "A thing can be in several entries: a road in each realm it crosses, a temple in its city "
        "and in the faith it serves. Look past places: a thing also belongs in the field, faith, "
        "order or council it is part of, and in the people or culture it comes from. Never one of "
        'the {{ kind }}\'s own parts: those go in "file_into". Only entries from the list; an '
        "empty list is fine.",
    ),
    (
        "parts, members, branches or what it holds, each",
        "parts, members, branches or what it holds (an entry the list or its facts call a part, "
        "unit, branch or member of this {{ kind }} belongs here), each",
    ),
]


def create_template_v2() -> str:
    source = create_template()
    for old, new in V2_SWAPS:
        source = _swap(source, old, new)
    # v2 belief rule, after v1 put 1 of 7 beliefs in "belief"
    start = source.index(BELIEF_V1_START)
    end = source.index("\n", start)
    return source[:start] + BELIEF_V2 + source[end:]


def write_templates(folder: Path) -> dict[str, str]:
    sources = {
        "create-thing": create_template(),
        "group-synopsis": SYNOPSIS_TEMPLATE,
        "group-add": ADD_TEMPLATE,
        "scene-context-filing": SCENE_TEMPLATE,
    }
    for name, text in sources.items():
        (folder / f"{name}.jinja2").write_text(text)
    return sources


# --- the presented world ----------------------------------------------------------------


class Probe:
    def __init__(self, labels: dict, root: Path) -> None:
        self.labels = labels
        self.world_labels: dict[str, dict] = {
            **labels["world"],
            **{
                name: {"tag": spec["tag"], "kind": spec["kind"], "in": spec["in"]}
                for name, spec in labels["seed_regiments"].items()
            },
        }
        self.root = root
        self.n = 0

    # the world copy for one case

    def open(self, remake: str | None = None, born: list[str] = (), seed: bool = False) -> World:
        self.n += 1
        target = self.root / f"world-{self.n}"
        shutil.copytree(SNAPSHOT, target)
        world = World.open(target)
        view = world.view()
        ids = {view.name_of(t.id): t.id for t in view.things()}
        with world.revision(Source.manual(note="probe: the filing presentation")) as rev:
            for name in dict.fromkeys([*self.labels["thin_left_out"], *born]):
                rev.remove_thing(ids[name])
            if remake:
                state = view.thing(ids[remake])
                for fact in state.facts:
                    rev.remove_fact(fact.fact_id)
                for field in ("part_of", "drawers", "template", "agent", "ties", "aka"):
                    if field in state.fields:
                        rev.remove_field_value(state.id, field, None)
                rev.set_field(state.id, "stub", {"ignored": False}, None)
                if state.kind == "sphere":
                    rev.change_stub_kind(state.id, "lore")
            if seed:
                for name, spec in self.labels["seed_regiments"].items():
                    thing_id = rev.create_thing(spec["kind"], {"name": name})
                    links = self.labels["seed_links"][name]
                    for year_text in spec["facts"]:
                        text = year_text
                        for linked in links:
                            if linked in text:
                                text = text.replace(linked, ref(ids[linked], linked), 1)
                        valid = WorldDate.of(998) if "in 998" in year_text else None
                        rev.add_fact(thing_id, "general", text, valid_from=valid)
        return world

    # how an entry is shown

    def label_of(self, name: str) -> dict:
        return self.world_labels.get(name, {"tag": None, "in": []})

    def kind_of(self, state) -> str:
        return self.label_of(self.name(state)).get("kind") or state.kind

    @staticmethod
    def name(state) -> str:
        return state.fields.get("name") or ""

    def filings(self, view: WorldView, name: str, skip: set[str]) -> list[dict]:
        live = {view.name_of(t.id) for t in view.things()}
        return [f for f in self.label_of(name)["in"] if f["entry"] in live and f["entry"] not in skip]

    def summary_fact(self, state):
        fact = entries.summary_fact(state) if spheres.is_sphere(state) else None
        if fact is None:
            for category in ("summary", "about", "description"):
                found = [f for f in state.facts if f.category == category]
                if found:
                    fact = min(found, key=lambda f: f.created)
                    break
        if fact is None and state.facts:
            fact = min(state.facts, key=lambda f: f.created)
        return fact

    def line(self, view: WorldView, state, skip: set[str]) -> str:
        name = view.name_of(state.id) or ""
        label = self.label_of(name)
        bits = [self.kind_of(state) + (f", {label['tag']}" if label.get("tag") else "")]
        everyday = everyday_name(state)
        if everyday:
            bits.append(f"usually called {everyday}")
        filed = self.filings(view, name, skip)
        if filed:
            bits.append(
                "in "
                + ", ".join(
                    f["entry"] + (f" ({f['role']})" if f.get("role") else "") for f in filed
                )
            )
        if state.is_stub:
            bits.append("stub")
        fact = self.summary_fact(state)
        text = curation._clip(view.render(fact.text), LINE_CHARS) if fact else "(nothing written yet)"
        return f"{name} ({'; '.join(bits)}): {text}"

    def candidates(self, view: WorldView, stub_id: str | None, picks: list[str], cap: int = CANDIDATES) -> list[str]:
        """Filing-based nearness, as the new app would have it: today's
        context first (the entries whose facts name the stub, most
        mentions first, then what the prompt names), then their neighbours
        one step away over filings (either way, weight 2) and fact references
        (either way, weight 1), the most-linked to that context first, at most `cap`; never
        the stub itself."""

        things = {t.id: t for t in view.things() if not t.stub_ignored}
        by_name = {view.name_of(t): state for t, state in things.items()}
        # a filing weighs 2, a fact reference 1 (the filing replaces part_of,
        # nearness's strongest link)
        links: dict[str, dict[str, int]] = {t: {} for t in things}

        def link(a: str, b: str, weight: int) -> None:
            links[a][b] = max(links[a].get(b, 0), weight)
            links[b][a] = max(links[b].get(a, 0), weight)

        for thing_id, state in things.items():
            for f in self.label_of(view.name_of(thing_id) or "")["in"]:
                target = by_name.get(f["entry"])
                if target is not None:
                    link(thing_id, target.id, 2)
            for fact in state.facts:
                for target in fact.refs:
                    if target in things and target != thing_id:
                        link(thing_id, target, 1)
        first: list[str] = []
        if stub_id is not None:
            counts = Counter(m.owner_id for m in all_mentions(view, stub_id) if m.owner_id in things)
            first += [t for t, _ in counts.most_common()]
        first += [p for p in picks if p not in first]
        seeds = set(first) | ({stub_id} if stub_id else set())
        score = Counter()
        for seed in seeds:
            for other, weight in links.get(seed, {}).items():
                if other not in seeds:
                    score[other] += weight
        ranked = sorted(score, key=lambda t: (-score[t], view.name_of(t) or ""))
        order = [t for t in [*first, *ranked] if t != stub_id]
        return list(dict.fromkeys(order))[:cap]

    def tags_in_use(self, view: WorldView, skip: set[str]) -> list[str]:
        counts = Counter(
            self.label_of(view.name_of(t.id) or "").get("tag")
            for t in view.things()
            if not t.stub_ignored and (view.name_of(t.id) or "") not in skip
        )
        counts.pop(None, None)
        return [f"{tag} ({n})" for tag, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    def resolve(self, view: WorldView, name: object) -> str | None:
        if not isinstance(name, str) or not name.strip():
            return None
        key = name_key(name)
        for state in view.things():
            names = [view.name_of(state.id) or ""]
            for entry in state.fields.get("aka") or []:
                if isinstance(entry, dict) and entry.get("name"):
                    names.append(str(entry["name"]))
            if key in {name_key(n) for n in names}:
                return view.name_of(state.id)
        return None


# --- calls ------------------------------------------------------------------------------

_HOOK: dict[str, Any] = {}
_SEEN: list[tuple[str, dict, str]] = []
_ORIGINAL_REQUEST = Prompt.request.__func__
DRY = [False]


class Printed(Exception):
    pass


async def _request(cls, uid, client, kind, vars=None, **kwargs):
    variables = dict(vars or {})
    hook = _HOOK.get(uid)
    if hook is not None:
        variables = hook(variables)
    if DRY[0]:
        print(f"===== {uid} ({kind})\n" + str(Prompt.get(uid, variables)))
        _SEEN.append((uid, variables, ""))
        raise Printed()
    response, extracted = await _ORIGINAL_REQUEST(cls, uid, client, kind, vars=variables, **kwargs)
    _SEEN.append((uid, variables, extracted.get("response", response)))
    return response, extracted


Prompt.request = classmethod(_request)


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


create._preview_prose = _no_prose


async def call(client, folder: Path, factory) -> dict:
    _SEEN.clear()
    before = len(client.calls)
    error = None
    started = time.monotonic()
    try:
        with PrependTemplateDirectories([str(folder)]):
            await factory()
    except Printed:
        error = "dry"
    except Exception as exc:  # a bad reply is a finding
        error = repr(exc)
    uid, variables, reply = _SEEN[-1] if _SEEN else (None, {}, "")
    out = curation._costed(client, before, reply) if not DRY[0] else {"reply": ""}
    out.update({"uid": uid, "error": None if error == "dry" else error, "wall": round(time.monotonic() - started, 1)})
    return out, variables


async def request(uid: str, client, kind: str, variables: dict):
    with world_ai_call():
        await Prompt.request(uid, client, kind, vars=variables)


# --- probes 1, 2, 4: the create reply ------------------------------------------------------------


def picks_in(view: WorldView, prompt: str, skip: set[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    lowered = prompt.casefold()
    for state in view.things():
        name = view.name_of(state.id) or ""
        if name in skip or state.stub_ignored:
            continue
        for written in [name, *(a.get("name") for a in state.fields.get("aka") or [] if isinstance(a, dict))]:
            if written and len(written) > 4 and written.casefold() in lowered and written not in found:
                found[written] = state.id
    # a longer name wins over one inside it
    return {w: i for w, i in found.items() if not any(w != o and w in o for o in found)}


def parse_create(probe: Probe, view: WorldView, reply: str) -> dict:
    obj = curation.reply_object(reply, "facts") or {}

    def filings(key: str) -> list[dict]:
        out = []
        for item in obj.get(key) or []:
            if isinstance(item, str):
                item = {"entry": item, "role": None}
            if not isinstance(item, dict):
                continue
            out.append(
                {"entry": item.get("entry"), "target": probe.resolve(view, item.get("entry")), "role": item.get("role")}
            )
        return out

    names = []
    for item in obj.get("names") or []:
        if not isinstance(item, dict):
            continue
        names.append(
            {
                "name": item.get("name"),
                "kind": item.get("kind"),
                "tag": item.get("tag"),
                "in": item.get("in"),
                "in_target": probe.resolve(view, item.get("in")),
                "exists": probe.resolve(view, item.get("name")),
            }
        )
    facts = [
        {"category": f.get("category"), "text": f.get("text"), "since": f.get("since")}
        for f in obj.get("facts") or []
        if isinstance(f, dict)
    ]
    return {
        "parsed": bool(obj),
        "name": obj.get("name"),
        "tag": obj.get("tag"),
        "in": filings("in"),
        "file_into": filings("file_into"),
        "names": names,
        "facts": facts,
        "elsewhere": obj.get("elsewhere"),
        "move_in": obj.get("move_in"),
        "keys": list(obj),
    }


def create_hook(probe: Probe, world: World, case_name: str | None, extra: dict):
    view = world.view()
    skip = {case_name} if case_name else set()

    def apply(variables: dict) -> dict:
        variables = dict(variables)
        stub_id = next((t.id for t in view.things() if view.name_of(t.id) == case_name), None) if case_name else None
        picks = extra.get("picks") or {}
        ids = probe.candidates(view, stub_id, list(picks.values()))
        variables["nearby"] = [probe.line(view, view.thing(t), skip) for t in ids]
        variables["nearby_names"] = [view.name_of(t) for t in ids]
        variables["tags"] = probe.tags_in_use(view, skip)
        variables["spheres"] = []
        variables["broader"] = []
        # the sphere kind goes: a former sphere reads as lore everywhere
        variables["mentions"] = [(lead.replace("(sphere, ", "(lore, "), text) for lead, text in variables.get("mentions") or []]
        variables["about"] = [(label.replace("(sphere, ", "(lore, ").replace("(sphere)", "(lore)"), facts) for label, facts in variables.get("about") or []]
        variables["named"] = [
            (written, label.replace("(sphere, ", "(lore, ").replace("(sphere)", "(lore)"), facts)
            for written, label, facts in variables.get("named") or []
        ]
        variables["hint"] = extra.get("hint") or ""
        if extra.get("belief") == "v2":
            # belief first, so the example's first fact is one
            variables["categories"] = ["belief", *variables["categories"]]
        elif extra.get("belief"):
            variables["categories"] = [*variables["categories"], "belief"]
        return variables

    return apply


async def run_create(probe: Probe, client, folder: Path, case: dict, hint_text: str | None = None, belief=False) -> dict:
    remake = case.get("entry") or case.get("stub")
    world = probe.open(remake=remake, born=case.get("born", []), seed=case.get("seed", False))
    try:
        view = world.view()
        extra: dict[str, Any] = {"hint": hint_text, "belief": belief}
        if remake:
            stub_id = next(t.id for t in view.things() if view.name_of(t.id) == remake)
            prompt = case.get("prompt") or suggested_prompt(view, stub_id)
            picks = picks_in(view, prompt, {remake}) if case.get("prompt") else {}
            extra["picks"] = picks
            factory = lambda: create.preview_thing(  # noqa: E731
                world, case["kind"], prompt, {}, client, stub_id=stub_id, picks=picks, ask_same=False
            )
        else:
            prompt = case["prompt"]
            picks = picks_in(view, prompt, set())
            extra["picks"] = picks
            factory = lambda: create.preview_thing(  # noqa: E731
                world, case["kind"], prompt, {}, client, picks=picks, ask_same=False
            )
        _HOOK["world.create-thing"] = create_hook(probe, world, remake, extra)
        out, variables = await call(client, folder, factory)
        out["prompt_text"] = prompt
        out["nearby"] = variables.get("nearby")
        out["nearby_names"] = variables.get("nearby_names")
        out["tags"] = variables.get("tags")
        out["parse"] = parse_create(probe, view, out.get("reply") or "")
        return out
    finally:
        world.close()


V2_CASES = {"p1v2": ["academy", "plumage", "nightcourt", "wattles", "khorol", "vasha"], "p2v2": ["host", "army", "pilots"]}


async def run_p1(probe, client, folder, results, save, runs, key, cases_only):
    cases = probe.labels["probe1" if key.startswith("p1") else "probe2"]["cases"]
    if key in V2_CASES:
        cases = {k: v for k, v in cases.items() if k in V2_CASES[key]}
    for case_key, case in cases.items():
        if cases_only and case_key not in cases_only:
            continue
        for run in range(runs):
            out = await run_create(probe, client, folder, case)
            results[key].append({"case": case_key, "run": run, **out})
            save()
            print(key, case_key, run, out.get("seconds"), out.get("error"), out["parse"].get("tag"),
                  [f["target"] or f["entry"] for f in out["parse"]["in"]],
                  [f["target"] or f["entry"] for f in out["parse"]["file_into"]], flush=True)


async def run_p4(probe, client, folder, results, save, runs, cases_only, key="p4"):
    hints = probe.labels["hints_draft"]
    for case_key, case in probe.labels["probe4"]["cases"].items():
        if cases_only and case_key not in cases_only:
            continue
        if key == "p4v2" and case_key not in ("religion", "culture"):
            continue
        hint = case.get("hint")
        belief = ("v2" if key == "p4v2" else True) if hint in ("religion", "culture") else False
        for run in range(runs):
            out = await run_create(probe, client, folder, case, hints[hint] if hint else None, belief=belief)
            results[key].append({"case": case_key, "run": run, "hint": hint, **out})
            save()
            print("p4", case_key, run, out.get("seconds"), out.get("error"),
                  Counter(f["category"] for f in out["parse"]["facts"]), flush=True)


# --- probe 3: the group synopsis -------------------------------------------------------------------


def key_facts(view: WorldView, state, limit: int = OWN_FACTS, skip_summary: bool = True) -> list[str]:
    """Up to `limit` of the entry's own facts, the most-linked first (most
    references, then oldest)."""

    summary = Probe.summary_fact(None, state) if skip_summary else None
    facts = [f for f in state.facts if summary is None or f.fact_id != summary.fact_id]
    facts.sort(key=lambda f: (-len(f.refs), f.created))
    return [view.render(f.text) for f in facts[:limit]]


def member_facts(probe: Probe, view: WorldView, state) -> list[str]:
    summary = probe.summary_fact(state)
    if summary is not None:
        return [view.render(summary.text), *key_facts(view, state)]
    found = all_mentions(view, state.id)
    return [f"(stub) mentioned by {m.owner_name}: {m.text}" for m in found[:3]] or ["(stub: nothing written yet)"]


async def run_p3(probe, client, folder, results, save, runs, cases_only):
    for case_key, case in probe.labels["probe3"]["cases"].items():
        if cases_only and case_key not in cases_only:
            continue
        world = probe.open()
        view = world.view()
        try:
            by_name = {view.name_of(t.id): t for t in view.things()}
            page = by_name[case["page"]]
            members = []
            for name, role in case["members"]:
                state = by_name[name]
                bits = [probe.kind_of(state), probe.label_of(name)["tag"]]
                if role:
                    bits.append(role)
                members.append({"label": f"{name} ({', '.join(b for b in bits if b)})", "facts": member_facts(probe, view, state)})
            page_summary = probe.summary_fact(page)
            variables = {
                "group": case["group"],
                "page": case["page"],
                "page_summary": view.render(page_summary.text) if page_summary else "",
                "members": members,
            }
            for run in range(runs):
                out, _ = await call(client, folder, lambda: request("world.group-synopsis", client, SYNOPSIS_KIND, variables))
                obj = curation.reply_object(out.get("reply") or "", "synopsis") or {}
                results["p3"].append({"case": case_key, "run": run, "vars": variables, "synopsis": obj.get("synopsis"), **out})
                save()
                print("p3", case_key, run, out.get("seconds"), obj.get("synopsis"), flush=True)
        finally:
            world.close()


# --- probe 6: group "+ Add" ----------------------------------------------------------------------------


async def run_p6(probe, client, folder, results, save, runs, cases_only, key="p6"):
    for case_key, case in probe.labels["probe6"]["cases"].items():
        if cases_only and case_key not in cases_only:
            continue
        world = probe.open()
        view = world.view()
        try:
            by_name = {view.name_of(t.id): t for t in view.things()}
            page = by_name[case["page"]]
            filed_here = [
                n for n, spec in probe.world_labels.items()
                if n in by_name and any(f["entry"] == case["page"] for f in spec["in"])
            ]
            members = [
                probe.line(view, by_name[n], set()) for n in filed_here if probe.label_of(n)["tag"] == case["tag"]
            ]
            filed = [f"{n} ({probe.label_of(n)['tag']})" for n in filed_here if probe.label_of(n)["tag"] != case["tag"]]
            near_ids = probe.candidates(view, page.id, [], 12)
            nearby = [view.name_of(t) for t in near_ids if view.name_of(t) not in filed_here]
            summary = probe.summary_fact(page)
            now = create.current_date(world)
            variables = {
                "tag": case["tag"],
                "page": case["page"],
                "page_kind": probe.kind_of(page),
                "page_tag": probe.label_of(case["page"])["tag"],
                "prompt": case["prompt"],
                "page_facts": ([view.render(summary.text)] if summary else []) + key_facts(view, page, 7),
                "members": members,
                "filed": filed,
                "nearby": nearby,
                "now_label": world.calendar.format(now),
                "now_year": now.to_datetime().year,
            }
            for run in range(runs):
                out, _ = await call(client, folder, lambda: request("world.group-add", client, ADD_KIND, variables))
                obj = curation.reply_object(out.get("reply") or "", "entries") or {}
                entries = [
                    {**e, "exists": probe.resolve(view, e.get("name"))}
                    for e in obj.get("entries") or [] if isinstance(e, dict)
                ]
                results[key].append({"case": case_key, "run": run, "vars": variables, "entries": entries, **out})
                save()
                print("p6", case_key, run, out.get("seconds"), [(e.get("name"), e.get("kind"), e.get("tag")) for e in entries], flush=True)
        finally:
            world.close()


# --- probe 5: the scene world block ------------------------------------------------------------------


def dated_line(view: WorldView, fact) -> str:
    year = fact.valid_from.to_datetime().year
    return f"In {year}: {view.render(fact.text)}"


def filing_block_vars(probe: Probe, world: World, record, at: WorldDate, roles: bool = False) -> dict:
    """The spec's rule ("Scene context"): the touched entries are what the
    scene's place is filed in, followed upward to the timeline reach; what
    each present character is filed in; and entries named in the setup.
    Each shows its summary, up to 5 of its own facts (the most-linked
    first) and its latest 3 timeline lines (dated facts of it and of what
    is filed in it, down to the timeline reach), at most 8 lines."""

    view = world.view(at)
    by_name = {view.name_of(t.id): t for t in view.things()}
    place_state = view.thing(record.state.get("place_thing_id") or "")
    place_name = view.name_of(place_state.id) if place_state else None
    touched: list[str] = []

    present = {view.name_of(e.get("thing_id") or "") for e in wp_context._present(record)}

    def add(name):
        # the present characters are told in the cast and their sheets
        if name in by_name and name != place_name and name not in present and name not in touched:
            touched.append(name)

    frontier = [place_name] if place_name else []
    for _ in range(TIMELINE_REACH):
        nxt = []
        for name in frontier:
            for f in probe.label_of(name)["in"]:
                add(f["entry"])
                nxt.append(f["entry"])
        frontier = nxt
    for entry in wp_context._present(record):
        name = view.name_of(entry.get("thing_id") or "")
        for f in probe.label_of(name or "")["in"]:
            add(f["entry"])
    for thing_id in record.state.get("pulled_in") or []:
        add(view.name_of(thing_id))
    setup_text = " ".join([record.goal or "", record.premise or ""]).casefold()
    for state in view.things():
        names = [view.name_of(state.id) or "", *(a.get("name") for a in state.fields.get("aka") or [] if isinstance(a, dict))]
        if any(n and len(n) > 4 and n.casefold() in setup_text for n in names):
            add(view.name_of(state.id))

    def filed_in(target: str) -> list[str]:
        return [n for n, spec in probe.world_labels.items() if n in by_name and any(f["entry"] == target for f in spec["in"])]

    if roles:
        # v2, after v1's narrator invented the Chief Scribe twice: a person
        # filed in a touched entry (or the place) with a role the setup
        # names is touched too
        for target in [place_name, *list(touched)]:
            for name in filed_in(target or ""):
                for f in probe.label_of(name)["in"]:
                    role = (f.get("role") or "").casefold()
                    if f["entry"] == target and role and role in setup_text and by_name[name].kind == "character":
                        add(name)

    entries = []
    for name in touched:
        state = by_name[name]
        summary = probe.summary_fact(state)
        lines = [view.render(summary.text)] if summary else []
        own = [f for f in state.facts if summary is None or f.fact_id != summary.fact_id]
        own.sort(key=lambda f: (-len(f.refs), f.created))
        chosen = own[:OWN_FACTS]
        lines += [view.render(f.text) for f in chosen]
        # the gathered timeline: dated facts of the entry and what's filed in it
        gathered, seen, frontier = [], {name}, [name]
        for _ in range(TIMELINE_REACH + 1):
            nxt = []
            for n in frontier:
                gathered += [f for f in by_name[n].facts if f.valid_from is not None]
                for child in filed_in(n):
                    if child not in seen:
                        seen.add(child)
                        nxt.append(child)
            frontier = nxt
        shown = {f.fact_id for f in chosen} | ({summary.fact_id} if summary else set())
        latest = sorted(
            (f for f in gathered if f.fact_id not in shown),
            key=lambda f: (f.valid_from.to_datetime().year, f.created),
        )[-TIMELINE_LINES:]
        lines += [dated_line(view, f) for f in latest]
        entries.append(
            {
                "name": name,
                "kind": probe.kind_of(state),
                "tag": probe.label_of(name)["tag"],
                "everyday": everyday_name(state),
                "lines": lines[:ENTRY_LINES],
            }
        )
    place = None
    if place_state is not None:
        place = {
            "name": place_name,
            "everyday": everyday_name(place_state),
            "facts": wp_context._facts(view, place_state, place_state.facts),
        }
    return {
        "goal": record.goal,
        "place": place,
        "touched": entries,
        "everyday": any(e["everyday"] for e in [*([place] if place else []), *entries]),
        "cast": wp_context._cast(world, record, view),
    }


async def run_p5(probe, client, folder, results, save, runs, key):
    scene_id = probe.labels["probe5"]["scene"]
    directions = probe.labels["probe5"]["directions"]
    original_block = wp_context.world_context_block
    for run in range(runs):
        # the old block reads the world as the app has it; the new one the
        # presented world (thin stubs left out)
        world = probe.open() if key in ("p5", "p5v2") else World.open(_copy_plain(probe))
        record = world.scenes().get(scene_id)
        if key in ("p5", "p5v2"):
            def block(w, r, when):
                with PrependTemplateDirectories([str(folder)]):
                    return str(Prompt.get("world.scene-context-filing", vars=filing_block_vars(probe, w, r, when, roles=key == "p5v2")))
            wp_context.world_context_block = block
        else:
            wp_context.world_context_block = original_block
        start = WorldDate.of(1000)
        shown_block = wp_context.world_context_block(world, record, start)
        entry = {
            "run": run,
            "block": shown_block,
            "block_lines": len([l for l in shown_block.splitlines() if l.strip()]),
            "block_tokens": curation.count_tokens(shown_block),
            "turns": [],
        }
        results[key].append(entry)
        save()
        if DRY[0]:
            print(shown_block)
            world.close()
            wp_context.world_context_block = original_block
            return
        scene = await harness._load(world, scene_id, client, memory=False)
        narrator = instance.get_agent("narrator")
        try:
            with ActiveScene(scene):
                for direction in directions:
                    before = len(client.calls)
                    started = time.monotonic()
                    text = await narrator.progress_story(narrative_direction=direction)
                    await scene.push_history([NarratorMessage(text, source="ai")])
                    calls = client.calls[before:]
                    for i, c in enumerate(calls):
                        c.setdefault("prompt_tokens", curation.count_tokens(c.get("prompt", "")))
                        c.setdefault("reply_tokens", curation.count_tokens(c.get("response", "") or ""))
                    entry["turns"].append(
                        {
                            "direction": direction,
                            "output": text,
                            "seconds": round(time.monotonic() - started, 1),
                            "calls": [before + i for i in range(len(calls))],
                            "kinds": [c.get("kind") for c in calls],
                            "prompt_tokens": [c.get("prompt_tokens") for c in calls],
                            "reply_tokens": [c.get("reply_tokens") for c in calls],
                        }
                    )
                    save()
                    print(key, run, round(time.monotonic() - started, 1), text[:200].replace("\n", " "), flush=True)
        finally:
            close_world_scene(scene)
            world.close()
            wp_context.world_context_block = original_block


def _copy_plain(probe: Probe) -> Path:
    probe.n += 1
    target = probe.root / f"world-{probe.n}"
    shutil.copytree(SNAPSHOT, target)
    return target


# --- main ------------------------------------------------------------------------------------------------


async def main(out: Path, only: list[str], runs: int, cases_only: list[str] | None, dry: bool) -> None:
    DRY[0] = dry
    labels = json.loads(LABELS.read_text())
    harness._quiet_loading(False)
    results: dict[str, Any] = (
        json.loads(out.read_text()) if out.exists() and not dry else {"probe": "filing", "date": "2026-10-23", "calls": []}
    )
    for key in ("p1", "p2", "p3", "p4", "p5", "p5old", "p6", "p1v2", "p2v2", "p4v2", "p5v2", "p6v2"):
        results.setdefault(key, [])

    def save() -> None:
        if not dry:
            out.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n")

    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        os.chdir(root)
        probe = Probe(labels, root_path)
        client = harness.RecordingClient(name="KoboldCpp")
        if not dry:
            await client.status()
            results["model"] = client.model_name
        client.calls = results["calls"]
        client.on_call = save
        folder = root_path / "templates"
        folder.mkdir()
        results["templates"] = write_templates(folder)
        folder2 = root_path / "templates-v2"
        folder2.mkdir()
        write_templates(folder2)
        (folder2 / "create-thing.jinja2").write_text(create_template_v2())
        (folder2 / "group-add.jinja2").write_text(_swap(ADD_TEMPLATE, ADD_COUNT_V1, ADD_COUNT_V2))
        results["templates"]["group-add-v2"] = _swap(ADD_TEMPLATE, ADD_COUNT_V1, ADD_COUNT_V2)
        results["templates"]["create-thing-v2"] = create_template_v2()
        for key in only:
            # a probe's earlier rows for the same cases are replaced
            if not dry and key in results and not cases_only:
                results[key] = []
            if key in ("p1", "p2"):
                await run_p1(probe, client, folder, results, save, runs, key, cases_only)
            elif key in ("p1v2", "p2v2"):
                await run_p1(probe, client, folder2, results, save, runs, key, cases_only)
            elif key == "p3":
                await run_p3(probe, client, folder, results, save, runs, cases_only)
            elif key == "p4":
                await run_p4(probe, client, folder, results, save, runs, cases_only)
            elif key == "p4v2":
                await run_p4(probe, client, folder2, results, save, runs, cases_only, "p4v2")
            elif key in ("p5", "p5old", "p5v2"):
                await run_p5(probe, client, folder, results, save, runs, key)
            elif key == "p6":
                await run_p6(probe, client, folder, results, save, runs, cases_only)
            elif key == "p6v2":
                await run_p6(probe, client, folder2, results, save, runs, cases_only, "p6v2")
            save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--only", nargs="+", default=["p1", "p2", "p3", "p4", "p5", "p5old", "p6"])
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.out.resolve(), args.only, args.runs, args.cases, args.dry))
