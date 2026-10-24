"""Throwaway probe: fact placement ("one fact, one home") and the
same-thing check, on the owner's acceptance world.

The owner's acceptance session found good facts filed badly: the 947
rediscovery of the Ashenmere rune dialect in five entries, a doctrine's
expansion mostly about the Tsardom, Ashenmere and The Ashenmere Caves as
two entries, a god made as a field sphere. This probe measures whether the
model can file each new fact before anything is built:

- **labels** (`--only labels`): checks the hand labels
  (`docs/superpowers/probes/raw/2026-10-22-fact-placement-labels.json`,
  committed before any model call) against the world: every new fact of
  every labelled entry has a label, and every fact a label says it
  restates existed when the entry was accepted. No model call.
- **A, placement after generation** (`--only A`): one call per entry, at
  the world as it stood the revision before the entry's expansion
  (`World.view(rev=...)`): the entry, its new facts N1..., the world's
  entries E1... (name, kind, sphere template, part of, one line) and the
  candidate homes' existing facts F1... The reply files each N: home
  ("this", an E label, or a new entry with a kind -- "being" among them),
  the F it restates, the timeline(s) it belongs on, its year.
  Candidate rule: the entry itself, the sphere it's part of, that
  sphere's other items (siblings), the entries whose facts mention it
  (link to it), and every entry whose name or other name a new fact
  writes (or links).
- **A2** (`--only A2`): A again, with homes and timelines written as
  entry names and an example of placeholders only: A's example labels
  were real ones, and its "E2" (Valdmark) was copied as a timeline.
- **B, placement at generation** (`--only B`): The Divine Right of the
  Tsar and Deepcarving re-expanded from their stubs through the real
  `create.preview_thing` (the stub's suggested prompt, its mentions, the
  names it finds), on a copy of the world undone back to the revision
  before each expansion. `control` runs use the app's create-thing
  template unchanged; `tagged` runs a copy that also lists the E entries,
  asks each fact's "subject" and takes facts for other entries in a
  separate "elsewhere" list. Prose isn't written (`_preview_prose` off).
  `combine` then runs A on each tagged run's own facts.
- **same** (`--only same`): each labelled pair (entries, a statement
  line, or a name only mentioned) judged same / part of / contains /
  different, from each side's name, kind and a few facts.
- **kinds** (`--only kinds`): what an entry is, offered the app's kinds
  plus "being" (a god, spirit or legendary creature) and the sphere
  templates, with what it's part of: the Eternal Light and White Talon as
  stubs (only their mentions) and with their present facts, and three
  controls.
- **score** (`--only score`): scores everything against the labels,
  with the code-side checks (token-overlap restatement detector, name
  overlap for same-thing candidates). No model call.

Every call is made through `Prompt.request` inside `world_ai_call` on
Talemate's own KoboldCpp client (the `--ai` app's config, as
`probe_heritage_play` sets it up), probe templates inline here. A, same
and kinds use the "analyze" kinds (the analytical preset, temperature
0.7, as the app's prose calls); B uses the app's create kind
(creative_instruction, 0.85). Each call's prompt, reply, seconds and
KoboldCpp's token counts go to the output JSON after the call.

The world is a copy of the snapshot, in a temp folder: the snapshot and
the live app are never written.

Not a test: it calls the network. Approved by the owner for this probe
("Let's try out the placement idea"); one GPU, calls one after another::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_fact_placement.py OUT.json \\
        [--only labels kinds same A A2 B combine score] [--runs 2] [--dry]'

Findings: docs/superpowers/probes/2026-10-22-fact-placement.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

# the heritage play probe's harness: config, recording client
import probe_heritage_play as harness  # noqa: E402

import talemate.worldplay.create as create  # noqa: E402
from talemate.prompts.base import PrependTemplateDirectories, Prompt  # noqa: E402
from talemate.world import entries, spheres  # noqa: E402
from talemate.world.names import everyday_name  # noqa: E402
from talemate.world.store import World  # noqa: E402
from talemate.world.view import WorldView  # noqa: E402
from talemate.worldplay.ai import world_ai_call  # noqa: E402
from talemate.worldplay.mentions import (  # noqa: E402
    gather_mentions,
    mentions,
    suggested_prompt,
)

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(
    "/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/"
    "66f9fa9e-6364-4353-bfde-ff936563332e/scratchpad/acceptance-snapshot/world"
)
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-22-fact-placement-labels.json"
TOKENCOUNT_URL = f"{harness.KOBOLDCPP_URL}/api/extra/tokencount"
PLACE_KIND = "analyze_long"  # analytical preset, 2048 reply tokens
SHORT_KIND = "analyze"  # analytical preset, 500 reply tokens
B_ENTRIES = ["The Divine Right of the Tsar", "Deepcarving"]
SUMMARY_CHARS = 130

# --- templates -----------------------------------------------------------------

PLACE_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
You keep a fantasy world's records tidy: every fact lives in exactly one place. New facts were just written for {{ entry }}. Before they are saved, decide where each one belongs.

The world's entries, labelled E1, E2... ({{ entry }} is {{ self_label }}):
{% for line in entries -%}
- {{ line }}
{% endfor %}
What some of these entries already say, labelled F1, F2...:
{% for heading, facts in groups -%}
{{ heading }}:
{% for label, text in facts -%}
- {{ label }}: {{ text }}
{% endfor -%}
{% endfor %}
The new facts for {{ entry }}, labelled N1, N2...:
{% for label, text in new -%}
- {{ label }}: {{ text }}
{% endfor %}
For each new fact decide:
- "home": the entry the fact is mainly about. "this" when it is mainly about {{ entry }} itself. When it is mainly about another entry in the list (a realm, a church, a people, another technique, a place), that entry's label, such as "E5": the fact is offered to that entry instead. When it is mainly about something with no entry yet (a person, a group, an event, a text, a god), {"new": "its name", "kind": "..."}, where "kind" is one of: character, place, species, race, item, event, lore, being (a god, spirit or legendary creature), or sphere (a faith, order, culture, field of knowledge or nation).
- "restates": the label of an F fact that already says the same thing, such as "F12", or null. A fact that only adds an example or a small detail to an F fact still restates it; one that adds a real new claim doesn't.
- "timeline": when the fact is a dated event -- something that happened at a known time (a founding, a discovery, a decree, a war) -- the labels of the entries whose timeline it belongs on, such as ["E2"]; otherwise null. A lasting state ("it is taught at...") is no event.
- "year": that event's year as a bare number, or null.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"placements": [{"fact": "N1", "home": "this", "restates": null, "timeline": null, "year": null}, {"fact": "N2", "home": "E5", "restates": "F12", "timeline": ["E2"], "year": 947}, {"fact": "N3", "home": {"new": "...", "kind": "character"}, "restates": null, "timeline": null, "year": null}]}

One placement per new fact, in order: every N exactly once. No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""

# A2: the same, but homes and timelines are written as entry names, and
# the example holds placeholders only (A's example "E2", "E5" and "F12"
# were real labels, and "E2" -- Valdmark -- was copied as a timeline)
PLACE2_TEMPLATE = (
    PLACE_TEMPLATE.replace(
        'that entry\'s label, such as "E5": the fact is offered',
        "that entry's name, exactly as the list writes it: the fact is offered",
    )
    .replace(
        'the labels of the entries whose timeline it belongs on, such as ["E2"]',
        "the names of the entries whose timeline it belongs on, as the list writes them",
    )
    .replace(
        '{"fact": "N2", "home": "E5", "restates": "F12", "timeline": ["E2"], "year": 947}',
        '{"fact": "N2", "home": "<an entry\'s name>", "restates": "<an F label>", '
        '"timeline": ["<an entry\'s name>"], "year": 1234}',
    )
    .replace('such as "F12", or null', "or null")
)
assert PLACE2_TEMPLATE.count("<an entry's name>") == 2
assert 'such as "E5"' not in PLACE2_TEMPLATE and '["E2"]' not in PLACE2_TEMPLATE

SAME_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
A fantasy world's records may hold one thing twice, under two names. Decide how A relates to B.

A: {{ a_label }}
{% for text in a_facts -%}
- {{ text }}
{% endfor %}
B: {{ b_label }}
{% for text in b_facts -%}
- {{ text }}
{% endfor %}
The relations:
- "same": A and B are one and the same thing, written twice (the two should be merged).
- "part_of": A is a part of B (a hall inside a city, a chapter of a guild).
- "contains": B is a part of A.
- "different": two distinct things, even if closely tied (a saint and the shrine named after her, a river and the town on its banks, a battle and the field it was fought on).
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"relation": "different", "why": "One short sentence."}

No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""

KIND_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
Decide what kind of entry "{{ name }}" is in a fantasy world's records.

{% if mentions -%}
It has no entry of its own yet. What the world says about it:
{%- else -%}
What its entry says:
{%- endif %}
{% for text in facts -%}
- {{ text }}
{% endfor %}
The kinds:
- character: one person;
- place: a land, city, site or building;
- species or race: a people, as a body (a race is a variety of a species);
- item: an object;
- event: something that happened once;
- lore: a law, custom, rank or office, text, script or language, or any other group or faction;
- being: a god, spirit or legendary creature (one being, not a people);
- sphere: a body or field the world holds in many parts, with a "template": religion (a faith or church), nation (a country or realm), order (an order, academy, guild or council), culture, or field (a field of knowledge or magic).

The entries it may be part of: {{ parents | join(", ") }}.
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"kind": "sphere", "template": "order", "part_of": "...", "why": "One short sentence."}

"template" only for a sphere, else null. "part_of": the entry above it belongs in, or null. No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""

# B: the app's create-thing template, with the E list, a "subject" per
# fact and a separate "elsewhere" list
_B_FACTS_OLD = (
    '"text": "One claim, in a full sentence.", "since": "YEAR"}, '
    '{"category": "{{ categories[-1] }}", "text": "Another claim."}], '
    '"names": [{"name": "...", "kind": "place", "aka": []}]{% if spheres %}'
)
_B_FACTS_NEW = (
    '"text": "One claim, in a full sentence.", "since": "YEAR", "subject": "this"}, '
    '{"category": "{{ categories[-1] }}", "text": "Another claim.", "subject": "this"}], '
    '"names": [{"name": "...", "kind": "place", "aka": []}], '
    '"elsewhere": [{"entry": "E5", "text": "A claim mainly about that entry, in a full sentence."}]'
    "{% if spheres %}"
)
_B_RULE_ANCHOR = '- "aka": other names for this {{ kind }} itself'
_B_RULES = (
    '- "subject": in each fact, what it is mainly about: "this" for the '
    "{{ kind }} itself, or the label of another entry in the list above, "
    'such as "E5". Keep "facts" to claims mainly about the {{ kind }} itself.\n'
    '- "elsewhere": after the names, what you would add about other entries '
    'in the list above, each {"entry": its label, "text": one claim in a full '
    "sentence}. An empty list is fine.\n"
)
_B_LIST_ANCHOR = "\nThe world's calendar: it is now"


def b_template(entries: list[str], self_label: str) -> str:
    """The create-thing template with B's additions; `entries` are baked in."""

    source = (
        REPO / "src/talemate/prompts/templates/world/create-thing.jinja2"
    ).read_text()
    assert source.count(_B_FACTS_OLD) == 1
    assert source.count(_B_RULE_ANCHOR) == 1
    assert source.count(_B_LIST_ANCHOR) == 1
    block = (
        f"\nThe world's entries, labelled E1, E2... (the {{{{ kind }}}} being "
        f"written is {self_label}):\n"
        + "".join(f"- {line}\n" for line in entries).replace("{", "(").replace("}", ")")
    )
    return (
        source.replace(_B_FACTS_OLD, _B_FACTS_NEW)
        .replace(_B_RULE_ANCHOR, _B_RULES + _B_RULE_ANCHOR)
        .replace(_B_LIST_ANCHOR, block + _B_LIST_ANCHOR)
    )


# --- the world -------------------------------------------------------------------


def open_copy(root: Path, name: str = "world") -> World:
    """A fresh copy of the snapshot, opened."""

    target = root / name
    shutil.copytree(SNAPSHOT, target)
    return World.open(target)


def view_at(world: World, rev: int | None) -> WorldView:
    return world.view(world.present(), rev=rev)


def by_name(view: WorldView, name: str):
    found = [t for t in view.things() if view.name_of(t.id) == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def fact_by_prefix(view: WorldView, prefix: str):
    """`(owner, fact)` for the live fact whose id starts with `prefix`."""

    for thing in view.things():
        for fact in thing.facts:
            if fact.fact_id.startswith(prefix):
                return thing, fact
    return None, None


def _clip(text: str, limit: int = SUMMARY_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _parent(view: WorldView, state) -> str | None:
    link = state.fields.get("part_of")
    if isinstance(link, dict) and isinstance(link.get("sphere"), str):
        return link["sphere"]
    return None


def one_line(view: WorldView, state) -> str:
    """An entry's one line: its summary fact (a sphere), else its first
    fact, cut; a stub with no fact says so."""

    fact = entries.summary_fact(state) if spheres.is_sphere(state) else None
    if fact is None and state.facts:
        fact = min(state.facts, key=lambda f: f.created)
    if fact is None:
        return "(a stub: nothing written yet)"
    return _clip(view.render(fact.text))


def entry_list(
    view: WorldView, self_id: str | None
) -> tuple[list[str], dict[str, str]]:
    """The E list (every live, unignored entry in creation order) and each
    label's thing id."""

    things = sorted(
        (t for t in view.things() if not t.stub_ignored), key=lambda t: t.created
    )
    lines, labels = [], {}
    for i, state in enumerate(things, 1):
        label = f"E{i}"
        labels[label] = state.id
        bits = [state.kind]
        template = state.fields.get("template")
        if template:
            bits = [
                f"sphere: {template}"
                if state.kind == "sphere"
                else f"{state.kind}, sphere: {template}"
            ]
        everyday = everyday_name(state)
        if everyday:
            bits.append(f"usually called {everyday}")
        parent = _parent(view, state)
        if parent:
            bits.append(f"part of {view.name_of(parent)}")
        if state.is_stub:
            bits.append("stub")
        mark = " -- the entry being written" if state.id == self_id else ""
        lines.append(
            f"{label}: {view.name_of(state.id)} ({'; '.join(bits)}){mark}: {one_line(view, state)}"
        )
    return lines, labels


def _names_of(state, view: WorldView) -> list[str]:
    names = [view.name_of(state.id) or ""]
    for entry in state.fields.get("aka") or []:
        if isinstance(entry, dict) and entry.get("name"):
            names.append(str(entry["name"]))
    return [n for n in names if len(n) >= 4]


def _writes(text: str, name: str) -> bool:
    bare = re.sub(r"^the\s+", "", name, flags=re.I)
    return re.search(rf"\b{re.escape(bare)}\b", text, re.I) is not None


def candidates(
    view: WorldView, self_id: str, new_raw: list[str]
) -> tuple[list[str], dict[str, str]]:
    """The candidate homes, in order, and why each is one: the entry
    itself, the sphere it's part of, that sphere's other items, the
    entries whose facts mention it, and every entry a new fact names (by
    name, other name or link)."""

    why: dict[str, str] = {self_id: "self"}
    state = view.thing(self_id)
    parent = _parent(view, state) if state else None
    if parent:
        why.setdefault(parent, "parent sphere")
        for thing in view.things():
            if _parent(view, thing) == parent and thing.id != self_id:
                why.setdefault(thing.id, "sibling")
    for mention in mentions(view, self_id):
        why.setdefault(mention.owner_id, "mentions it")
    rendered = [view.render(text) for text in new_raw]
    for thing in sorted(view.things(), key=lambda t: t.created):
        if thing.stub_ignored or thing.id in why:
            continue
        linked = any(f"thing:{thing.id}" in text for text in new_raw)
        named = any(
            _writes(text, n) for text in rendered for n in _names_of(thing, view)
        )
        if linked or named:
            why[thing.id] = "linked" if linked else "named"
    return list(why), why


def fact_groups(
    view: WorldView, homes: list[str], skip: set[str]
) -> tuple[list[tuple[str, list[tuple[str, str]]]], dict[str, str]]:
    """The F list: each candidate's live facts (none in `skip`), grouped
    under its name, and each label's fact id."""

    groups, labels, n = [], {}, 0
    for thing_id in homes:
        state = view.thing(thing_id)
        if state is None:
            continue
        facts = []
        for fact in sorted(state.facts, key=lambda f: f.created):
            if fact.fact_id in skip:
                continue
            n += 1
            label = f"F{n}"
            labels[label] = fact.fact_id
            line = view.render(fact.text)
            if fact.category == "timeline" and fact.valid_from is not None:
                line = f"({fact.valid_from.to_datetime().year}, timeline) {line}"
            facts.append((label, line))
        if facts:
            groups.append((f"{view.name_of(thing_id)} ({state.kind})", facts))
    return groups, labels


# --- calls -----------------------------------------------------------------------


def count_tokens(text: str) -> int | None:
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
    for text in (reply, "{" + reply):
        for obj in create.json_objects(text):
            if key in obj:
                return obj
    return None


async def ask(client, folder: Path, uid: str, kind: str, variables: dict) -> dict:
    """Send the probe template `uid`; the reply with its call's cost."""

    before = len(client.calls)
    with PrependTemplateDirectories([str(folder)]):
        with world_ai_call():
            response, _ = await Prompt.request(uid, client, kind, vars=variables)
    return _costed(client, before, response)


def _costed(client, before: int, response: str) -> dict:
    call = client.calls[before] if len(client.calls) > before else {}
    cost = {
        "call": before,
        "seconds": call.get("seconds"),
        "prompt_tokens": count_tokens(call.get("prompt", "")),
        "reply_tokens": count_tokens(call.get("response", response) or ""),
    }
    if call:
        call.update(cost)
    return {"reply": response, **cost}


# --- A ------------------------------------------------------------------------------


def a_context(
    view: WorldView, self_id: str, new_raw: list[str], skip: set[str]
) -> dict:
    """A's template variables and label maps for `new_raw` facts of
    `self_id` at `view`."""

    entries, e_labels = entry_list(view, self_id)
    self_label = next(
        label for label, thing_id in e_labels.items() if thing_id == self_id
    )
    homes, why = candidates(view, self_id, new_raw)
    groups, f_labels = fact_groups(view, homes, skip)
    new = [(f"N{i}", view.render(text)) for i, text in enumerate(new_raw, 1)]
    return {
        "vars": {
            "entry": view.name_of(self_id),
            "self_label": self_label,
            "entries": entries,
            "groups": groups,
            "new": new,
        },
        "e_labels": e_labels,
        "f_labels": f_labels,
        "candidates": {view.name_of(h): why[h] for h in homes},
    }


def parse_placements(reply: str) -> list[dict] | None:
    obj = reply_object(reply, "placements")
    if obj is None or not isinstance(obj.get("placements"), list):
        return None
    return [p for p in obj["placements"] if isinstance(p, dict)]


def entry_facts(world: World, name: str, rev: int) -> tuple[str, list, list]:
    """`(id, existing, new)` for an entry expanded at `rev`: the facts it
    had the revision before, and those that came with the expansion."""

    head = view_at(world, None)
    state = by_name(head, name)
    before = view_at(world, rev - 1).thing(state.id)
    had = {f.fact_id for f in before.facts} if before else set()
    facts = sorted(state.facts, key=lambda f: f.created)
    return (
        state.id,
        [f for f in facts if f.fact_id in had],
        [f for f in facts if f.fact_id not in had],
    )


async def run_a(
    client, folder, world, labels, results, save, runs, key="A", uid="world.fp-place"
) -> None:
    for name, spec in labels["entries"].items():
        rev = spec["rev"]
        thing_id, existing, new = entry_facts(world, name, rev)
        view = view_at(world, rev - 1)
        ctx = a_context(view, thing_id, [f.text for f in new], set())
        for n in range(runs):
            out = await ask(client, folder, uid, PLACE_KIND, ctx["vars"])
            results[key].append(
                {
                    "entry": name,
                    "n": n,
                    "rev_before": rev - 1,
                    "new": {f"N{i}": f.fact_id for i, f in enumerate(new, 1)},
                    "e_labels": ctx["e_labels"],
                    "f_labels": ctx["f_labels"],
                    "candidates": ctx["candidates"],
                    "placements": parse_placements(out["reply"]),
                    **out,
                }
            )
            save()


# --- B ------------------------------------------------------------------------------

_last_reply: list[str] = []
_parse = create.parse_create_reply


def _recording_parse(reply, *args, **kwargs):
    _last_reply.append(reply)
    return _parse(reply, *args, **kwargs)


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


def undone_world(root: Path, tag: str, rev: int) -> World:
    """A copy of the world (folder `tag`-`rev`) with every revision from
    `rev` on undone."""

    world = open_copy(root, f"{tag}-{rev}")
    revs = list(range(rev, world.head_rev() + 1))
    report = world.undo(revs, note="probe: back to before the expansion")
    assert not report.conflicts, report.conflicts
    return world


async def run_b(client, tmp: Path, labels, results, save, runs) -> None:
    create._preview_prose = _no_prose
    create.parse_create_reply = _recording_parse
    for name in B_ENTRIES:
        rev = labels["entries"][name]["rev"]
        world = undone_world(tmp, "b", rev)
        try:
            view = world.view()
            stub = by_name(view, name)
            assert stub.is_stub, name
            prompt = suggested_prompt(view, stub.id)
            entries, e_labels = entry_list(view_at(world, None), stub.id)
            self_label = next(k for k, v in e_labels.items() if v == stub.id)
            folder = tmp / f"b-templates-{rev}"
            folder.mkdir()
            (folder / "create-thing.jinja2").write_text(b_template(entries, self_label))
            for variant in ("control", "tagged"):
                for n in range(runs):
                    _last_reply.clear()
                    before = len(client.calls)
                    error = preview = None
                    try:
                        if variant == "tagged":
                            with PrependTemplateDirectories([str(folder)]):
                                preview = await create.preview_thing(
                                    world,
                                    "lore",
                                    prompt,
                                    {},
                                    client,
                                    stub_id=stub.id,
                                    picks={},
                                )
                        else:
                            preview = await create.preview_thing(
                                world,
                                "lore",
                                prompt,
                                {},
                                client,
                                stub_id=stub.id,
                                picks={},
                            )
                    except Exception as exc:  # a bad reply is a finding
                        error = repr(exc)
                    reply = _last_reply[-1] if _last_reply else ""
                    obj = (
                        reply_object(reply, "facts")
                        or reply_object("{" + reply, "facts")
                        or {}
                    )
                    out = _costed(client, before, reply)
                    results["B"].append(
                        {
                            "entry": name,
                            "variant": variant,
                            "n": n,
                            "prompt_text": prompt,
                            "error": error,
                            "e_labels": e_labels,
                            "facts": [
                                {
                                    "text": f.get("text"),
                                    "subject": f.get("subject"),
                                    "category": f.get("category"),
                                    "since": f.get("since"),
                                }
                                for f in obj.get("facts") or []
                                if isinstance(f, dict)
                            ],
                            "elsewhere": obj.get("elsewhere"),
                            "names": obj.get("names"),
                            "preview_facts": [f.text for f in preview.facts]
                            if preview
                            else None,
                            **out,
                        }
                    )
                    save()
        finally:
            world.close()
    create.parse_create_reply = _parse


async def run_combine(client, folder: Path, tmp: Path, labels, results, save) -> None:
    """A on each tagged B run's own facts, at the same undone world."""

    for name in B_ENTRIES:
        rev = labels["entries"][name]["rev"]
        world = undone_world(tmp, "combine", rev)
        try:
            view = view_at(world, None)
            stub = by_name(view, name)
            existing = [f.fact_id for f in stub.facts]
            for run in [
                r
                for r in results["B"]
                if r["entry"] == name and r["variant"] == "tagged"
            ]:
                texts = [f["text"] for f in run["facts"] if f.get("text")]
                if not texts:
                    continue
                ctx = a_context(view, stub.id, texts, set())
                out = await ask(
                    client, folder, "world.fp-place", PLACE_KIND, ctx["vars"]
                )
                results["combine"].append(
                    {
                        "entry": name,
                        "b_run": run["n"],
                        "existing": existing,
                        "new_texts": texts,
                        "e_labels": ctx["e_labels"],
                        "f_labels": ctx["f_labels"],
                        "candidates": ctx["candidates"],
                        "placements": parse_placements(out["reply"]),
                        **out,
                    }
                )
                save()
        finally:
            world.close()


# --- same thing --------------------------------------------------------------------


def side(view: WorldView, spec: dict) -> tuple[str, list[str]]:
    """A side's label and up to four facts."""

    if "entry" in spec:
        state = by_name(view, spec["entry"])
        bits = [state.kind]
        if state.fields.get("template"):
            bits.append(f"sphere: {state.fields['template']}")
        parent = _parent(view, state)
        if parent:
            bits.append(f"part of {view.name_of(parent)}")
        if state.is_stub:
            bits.append("a stub")
        facts = sorted(state.facts, key=lambda f: f.created)
        texts = [_clip(view.render(f.text), 260) for f in facts[:4]]
        if not texts:
            texts = [
                _clip(m.text, 260)
                for m in gather_mentions(view, state.id).mentioned[:3]
            ]
            if texts:
                bits.append("no facts of its own yet; what mentions it")
        return f"{spec['entry']} ({', '.join(bits)})", texts
    if "line" in spec:
        owner, fact = fact_by_prefix(view, spec["line"])
        drawer = (fact.origin or {}).get("drawer")
        title = next(
            (d.title for d in spheres.drawers(view, owner.id) if d.id == drawer),
            "a drawer",
        )
        return (
            f'"{spec["name"]}", a line in the {title} drawer of {view.name_of(owner.id)}',
            [view.render(fact.text)],
        )
    texts = []
    for prefix in spec["facts"]:
        owner, fact = fact_by_prefix(view, prefix)
        texts.append(
            f"(in {view.name_of(owner.id)}) {_clip(view.render(fact.text), 260)}"
        )
    return (
        f'"{spec["mention"]}", a name written in facts, with no entry of its own',
        texts,
    )


async def run_same(client, folder, world, labels, results, save, runs) -> None:
    view = view_at(world, None)
    for i, pair in enumerate(labels["same_thing"]):
        a_label, a_facts = side(view, pair["a"])
        b_label, b_facts = side(view, pair["b"])
        variables = {
            "a_label": a_label,
            "a_facts": a_facts,
            "b_label": b_label,
            "b_facts": b_facts,
        }
        for n in range(runs):
            out = await ask(client, folder, "world.fp-same", SHORT_KIND, variables)
            obj = reply_object(out["reply"], "relation") or {}
            results["same"].append(
                {
                    "pair": i,
                    "n": n,
                    "a": a_label,
                    "b": b_label,
                    "truth": pair["relation"],
                    "relation": obj.get("relation"),
                    "why": obj.get("why"),
                    **out,
                }
            )
            save()


# --- kinds ---------------------------------------------------------------------------


async def run_kinds(client, folder, world, labels, results, save, runs) -> None:
    for case in labels["kinds"]:
        view = view_at(world, case["at_rev"])
        state = by_name(view, case["entry"])
        mentions = case["at_rev"] is not None
        if mentions:
            facts = [
                _clip(m.text, 300) for m in gather_mentions(view, state.id).mentioned
            ]
            facts += [_clip(view.render(f.text), 300) for f in state.facts]
        else:
            facts = [
                _clip(view.render(f.text), 300)
                for f in sorted(state.facts, key=lambda f: f.created)
            ]
        parents = [
            view.name_of(t.id)
            for t in sorted(view.things(), key=lambda t: t.created)
            if (spheres.is_sphere(t) or (t.kind == "place" and not t.is_stub))
            and t.id != state.id
            and not t.stub_ignored
        ]
        variables = {
            "name": case["entry"],
            "mentions": mentions,
            "facts": facts,
            "parents": parents,
        }
        for n in range(runs):
            out = await ask(client, folder, "world.fp-kind", SHORT_KIND, variables)
            obj = reply_object(out["reply"], "kind") or {}
            results["kinds"].append(
                {
                    "case": case["case"],
                    "n": n,
                    "truth": {k: case[k] for k in ("kind", "template", "part_of")},
                    "kind": obj.get("kind"),
                    "template": obj.get("template"),
                    "part_of": obj.get("part_of"),
                    "why": obj.get("why"),
                    **out,
                }
            )
            save()


# --- labels check -------------------------------------------------------------------


def check_labels(world: World, labels: dict) -> list[str]:
    """Problems with the labels: an unlabelled new fact, a label for no
    new fact, a restated fact that didn't exist at accept time, a home
    that names no entry."""

    problems = []
    head = view_at(world, None)
    names = {head.name_of(t.id) for t in head.things()}
    for name, spec in labels["entries"].items():
        rev = spec["rev"]
        _, existing, new = entry_facts(world, name, rev)
        before = view_at(world, rev - 1)
        if sorted(f.fact_id[:8] for f in existing) != sorted(spec["existing"]):
            problems.append(f"{name}: existing {[f.fact_id[:8] for f in existing]}")
        new_ids = {f.fact_id[:8] for f in new}
        labelled = {f["fact"] for f in spec["facts"]}
        for missing in new_ids - labelled:
            problems.append(f"{name}: unlabelled {missing}")
        for extra in labelled - new_ids:
            problems.append(f"{name}: label for no new fact {extra}")
        for f in spec["facts"]:
            for prefix in f["restates"] + f.get("partial", []):
                owner, _ = fact_by_prefix(before, prefix)
                if owner is None:
                    problems.append(
                        f"{name} {f['fact']}: {prefix} not live at rev {rev - 1}"
                    )
            for home in f["home"]:
                if home != "this" and not home.startswith("new:") and home not in names:
                    problems.append(f"{name} {f['fact']}: no entry {home!r}")
    return problems


# --- main ------------------------------------------------------------------------------


def write_templates(folder: Path) -> None:
    (folder / "fp-place.jinja2").write_text(PLACE_TEMPLATE)
    (folder / "fp-place2.jinja2").write_text(PLACE2_TEMPLATE)
    (folder / "fp-same.jinja2").write_text(SAME_TEMPLATE)
    (folder / "fp-kind.jinja2").write_text(KIND_TEMPLATE)


async def main(out: Path, only: list[str], runs: int) -> None:
    labels = json.loads(LABELS.read_text())
    harness._quiet_loading(False)
    results: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {"probe": "fact-placement", "date": "2026-10-22", "calls": []}
    )
    for key in ("A", "A2", "B", "combine", "same", "kinds"):
        results.setdefault(key, [])

    def save() -> None:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        os.chdir(root)
        world = open_copy(root_path)
        problems = check_labels(world, labels)
        if "labels" in only:
            print("\n".join(problems) or "labels: ok")
        assert not problems, problems
        if set(only) & {"A", "A2", "B", "same", "kinds", "combine"}:
            client = harness.RecordingClient(name="KoboldCpp")
            await client.status()
            results["model"] = client.model_name
            results["prompt_template"] = client.prompt_template_example()[1]
            client.calls = results["calls"]
            client.on_call = save
            folder = root_path / "templates"
            folder.mkdir()
            write_templates(folder)
            started = time.monotonic()
            if "kinds" in only:
                await run_kinds(client, folder, world, labels, results, save, runs)
            if "same" in only:
                await run_same(client, folder, world, labels, results, save, runs)
            if "A" in only:
                await run_a(client, folder, world, labels, results, save, runs)
            if "A2" in only:
                await run_a(
                    client,
                    folder,
                    world,
                    labels,
                    results,
                    save,
                    runs,
                    key="A2",
                    uid="world.fp-place2",
                )
            if "B" in only:
                await run_b(client, root_path, labels, results, save, runs)
            if "combine" in only:
                await run_combine(client, folder, root_path, labels, results, save)
            results.setdefault("minutes", {})[" ".join(only)] = round(
                (time.monotonic() - started) / 60, 1
            )
            save()
        if "score" in only:
            import probe_fact_placement_score as scoring

            results["scores"] = scoring.score(world, labels, results)
            save()
            print(
                json.dumps(results["scores"]["summary"], indent=1, ensure_ascii=False)
            )
        world.close()


def dry() -> None:
    """Print every A prompt's size, one A prompt, one same and one kind
    prompt, B's template, calling nothing but the token counter."""

    labels = json.loads(LABELS.read_text())
    harness._quiet_loading(False)
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        world = open_copy(root_path)
        folder = root_path / "templates"
        folder.mkdir()
        write_templates(folder)
        with PrependTemplateDirectories([str(folder)]):
            for name, spec in labels["entries"].items():
                thing_id, _, new = entry_facts(world, name, spec["rev"])
                view = view_at(world, spec["rev"] - 1)
                ctx = a_context(view, thing_id, [f.text for f in new], set())
                text = str(Prompt.get("world.fp-place", ctx["vars"]))
                print(
                    name,
                    "entries",
                    len(ctx["vars"]["entries"]),
                    "F",
                    len(ctx["f_labels"]),
                    "tokens",
                    count_tokens(text),
                    ctx["candidates"],
                )
                if name == "Deepcarving":
                    print(text)
            view = view_at(world, None)
            pair = labels["same_thing"][3]
            a_label, a_facts = side(view, pair["a"])
            b_label, b_facts = side(view, pair["b"])
            print(
                Prompt.get(
                    "world.fp-same",
                    {
                        "a_label": a_label,
                        "a_facts": a_facts,
                        "b_label": b_label,
                        "b_facts": b_facts,
                    },
                )
            )
        world.close()
        b = undone_world(root_path, "dry", 18)
        v = b.view()
        stub = by_name(v, "Deepcarving")
        print("B stub:", stub.is_stub, [f.text for f in stub.facts])
        print("B prompt:", suggested_prompt(v, stub.id))
        entries, labels_e = entry_list(view_at(b, None), stub.id)
        print(b_template(entries, "E1")[-4000:])
        b.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path, nargs="?")
    parser.add_argument(
        "--only",
        nargs="+",
        default=["labels", "kinds", "same", "A", "A2", "B", "combine", "score"],
    )
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument(
        "--dry", action="store_true", help="print prompts, call no model"
    )
    args = parser.parse_args()
    if args.dry:
        dry()
    else:
        asyncio.run(main(args.out.resolve(), args.only, args.runs))
