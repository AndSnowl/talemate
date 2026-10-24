"""Throwaway probe: curation wording on Skyfall (Curation plan, Task 3).

Five probes on a copy of the owner's acceptance world, against hand labels
committed before any model call
(`docs/superpowers/probes/raw/2026-10-22-curation-labels.json`):

1. **Elsewhere with nearness candidates** (`--only p1`): the app's
   create-thing, sphere-core and Fill calls, run through the app's own
   `create.preview_thing`, `spheres.preview_sphere` and
   `spheres.fill_drawer` (so the context is the app's), with the
   templates gaining an "Entries near this one" list from `near()` and an
   `"elsewhere"` reply list (`{"entry", "text", "held_by"}`). Variants
   r1, r2, r3 (reach 1-3, 12 entries) and r3w (reach 3, 24 entries); a
   variant whose list is the same as an earlier one's isn't sent again.
2. **Moving in** (`--only p2`): a new entry that is part of a broader one
   gets the broader entry's facts, labelled M1..., and picks the ones that
   belong on it in the same create reply (`"move_in"`, ruling Q1).
3. **Contradictions** (`--only p3`): a merge check, one call per pair of
   entries (A1..., B1...), the reply listing the pairs that can't both be
   true.
4. **Held by** (`--only p4`): a per-fact `"held_by"` name in the create
   reply (and on every elsewhere item): probe 1's create runs plus the
   Eternal Light created as a `being`.
5. **The outer body** (`--only p5`): the create reply's own `"part_of"`
   (`{"entry", "drawer"}`) and a `"part_of"` per name, which may name a
   new body listed in "names"; the White Talon and the Frosted Wing as
   stubs (the White Talon put back to one, world "w5"), with negatives.
   **same** (`--only same`): the same-thing verdict, a separate small
   call, on a new entry's preview facts against an existing entry.

Every create, core and Fill call is made by the app's own preview function
at the app's own kind (`creative_instruction_2048`, `_1024`: the
creative_instruction preset, 0.85); the probe only prepends its templates
(the app's, with the additions) and adds their variables through a wrapper
around `Prompt.request`. Prose isn't written (`_preview_prose` off). The
merge check and the same-thing verdict are judgements, sent at `analyze`
(the analytical preset, 0.7), as the fact placement probe's were. Every
call's prompt, reply, seconds and KoboldCpp token counts go to the output
JSON after the call.

The world is copied to a temp folder; the snapshot is never written.

Not a test: it calls the network. Approved by the owner ("you have
permission to use skyfall for those two tasks"); one GPU, one call at a
time::

    guix shell -m manifest.scm -- bash -c 'HF_HUB_OFFLINE=1 \\
        LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib \\
        uv run --no-sync python scripts/dev/probe_curation.py OUT.json \\
        [--only labels p1 p2 p3 p4 p5 same] [--runs 2] [--dry]'

Scoring: `scripts/dev/probe_curation_score.py`. Findings:
`docs/superpowers/probes/2026-10-22-curation.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import probe_heritage_play as harness  # noqa: E402  (config, recording client)

import talemate.worldplay.create as create  # noqa: E402
import talemate.worldplay.spheres as wp_spheres  # noqa: E402
from talemate.prompts.base import PrependTemplateDirectories, Prompt  # noqa: E402
from talemate.world import entries, spheres  # noqa: E402
from talemate.world.names import everyday_name  # noqa: E402
from talemate.worldplay.links import name_key  # noqa: E402
from talemate.world.nearness import near  # noqa: E402
from talemate.world.sameness import same_candidates  # noqa: E402
from talemate.world.store import Source, World  # noqa: E402
from talemate.world.view import WorldView  # noqa: E402
from talemate.worldplay.ai import world_ai_call  # noqa: E402
from talemate.worldplay.mentions import gather_mentions, suggested_prompt  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(
    "/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/"
    "66f9fa9e-6364-4353-bfde-ff936563332e/scratchpad/acceptance-snapshot/world"
)
LABELS = REPO / "docs/superpowers/probes/raw/2026-10-22-curation-labels.json"
TEMPLATES = REPO / "src/talemate/prompts/templates/world"
TOKENCOUNT_URL = f"{harness.KOBOLDCPP_URL}/api/extra/tokencount"
JUDGE_KIND = "analyze"  # analytical preset, 0.7, 500 reply tokens
LINE_CHARS = 130
BEING_CATEGORIES = ["nature", "deeds", "worship", "general"]

# --- the template additions ---------------------------------------------------

NEARBY_BLOCK = """{%- if nearby %}

Entries near this one in the world:
{% for line in nearby -%}
- {{ line }}
{% endfor %}
{%- endif %}"""

BROADER_BLOCK = """{%- if broader %}

{{ broader_name }} is the broader entry this {{ kind }} is part of. What {{ broader_name }} says now, labelled M1, M2...:
{% for label, text in broader -%}
- {{ label }}: {{ text }}
{% endfor %}
{%- endif %}"""

ELSEWHERE_EXAMPLE = (
    '"elsewhere": [{"entry": "<an entry\'s name>", "text": "A claim mainly '
    'about that entry, in a full sentence.", "held_by": null}]'
)

HELD_BY_RULE = (
    '- "held_by", in {{ held_in }}: when the claim is what a faith, order, '
    "culture or person believes or teaches rather than plain truth of the "
    "world (that the dead are reborn as stars, that a river spirit grants "
    "the harvest), the name of the entry that believes it, as the list of "
    "entries near this one writes it; otherwise null. What happened, a law or "
    "rite as it is practised, and what a thing is or does are plain truth: "
    "null."
)


def elsewhere_rule(subject: str) -> str:
    return (
        '- "elsewhere": after the names, what you would add about other '
        'entries, each {"entry", "text", "held_by"}: "entry" the entry\'s name '
        "as the list of entries near this one writes it, or a new name you also "
        'list in "names"; "text" one claim in a full sentence. Never '
        f"{subject} itself. An empty list is fine."
    )


CREATE_RULES = (
    "\n{%- if nearby %}\n"
    '- Keep "facts" to claims mainly about the {{ kind }} itself: a claim '
    'mainly about another entry goes in "elsewhere".\n'
    + elsewhere_rule("the {{ kind }}")
    + "\n"
    + HELD_BY_RULE.replace("{{ held_in }}", "a fact or an elsewhere claim")
    + "\n"
    '- "part_of": what the {{ kind }} is part of, {"entry", "drawer"}: a sphere '
    "from the list of entries near this one and the title of one of its "
    'drawers, or a body you list in "names" and the title of the drawer that '
    "would hold the {{ kind }}.{% if part_of_now %} It is filed now under "
    "{{ part_of_now }}: keep that, unless it belongs inside a smaller body "
    "that is itself part of {{ part_of_sphere }}.{% endif %} null when it is "
    "part of nothing.\n"
    '- In "names", a body that is part of a sphere or of another body gets '
    '"part_of" the same way. When the {{ kind }} or a name belongs inside a '
    "body the world has no entry for yet, list that body in \"names\" too: a "
    '"sphere" with its "template", its own "part_of", and a name that fits '
    "the world.\n"
    "{%- endif %}\n"
    "{%- if broader %}\n"
    '- "move_in": the labels of {{ broader_name }}\'s facts above that are '
    "mainly about this {{ kind }}, so they belong on its page rather than on "
    "{{ broader_name }}'s. They move here: don't write them again in "
    '"facts". A fact that only mentions the {{ kind }} in passing stays where '
    "it is. An empty list is fine.\n"
    "{%- endif %}"
)

# probe 1 v3, after v1's elsewhere items were 41% false moves in creates and
# 19% in Fill, nearly all of them claims tying another entry to the one being
# written ("X is taught at Y", "unlike X, it...")
RELATION_RULE_CREATE = (
    '- A claim that ties another entry to the {{ kind }} ("it is taught at X", '
    '"unlike X, it...", "X uses it") is the {{ kind }}\'s own: it goes in '
    '"facts". "elsewhere" is only for what another entry\'s page should say '
    "even if the {{ kind }} didn't exist."
)
RELATION_RULE_FILL = (
    "- \"elsewhere\" is only for what another entry's page should say even if "
    "{{ name }}'s new items didn't exist: a claim about one of your new items, "
    "or tying another entry to one, is no elsewhere claim."
)


def create_template_v3() -> str:
    return _swap(
        create_template(),
        "\n" + HELD_BY_RULE.replace("{{ held_in }}", "a fact or an elsewhere claim"),
        "\n" + RELATION_RULE_CREATE + "\n"
        + HELD_BY_RULE.replace("{{ held_in }}", "a fact or an elsewhere claim"),
    )


def fill_template_v3() -> str:
    return _swap(
        fill_template(),
        "\n" + HELD_BY_RULE.replace("{{ held_in }}", "an elsewhere claim"),
        "\n" + RELATION_RULE_FILL + "\n"
        + HELD_BY_RULE.replace("{{ held_in }}", "an elsewhere claim"),
    )


# probe 5 v2, after v1 filed both regiments straight into the Tsardom in
# 4 of 4 runs: the body-within-a-body rule said outright, with examples
# that aren't the case under test
P5V2_RULE = (
    "\n{%- if nearby %}\n"
    "- A unit of a larger body: when the {{ kind }} is one of several units "
    "of a larger body that is not the sphere itself (one chapter of an order "
    "that serves a faith, one company of a guild that serves a city), its "
    '"part_of" is that larger body, not the sphere. When the world has no '
    'entry for that larger body, give it a fitting name, list it in "names" '
    'as a "sphere" with its "template" and its own "part_of" (the sphere '
    'and the drawer it belongs in), and set the {{ kind }}\'s "part_of" to it.\n'
    "{%- endif %}"
)


def create_template_v2() -> str:
    return _swap(
        create_template(),
        '\n{%- if spheres %}\n- "ties"',
        P5V2_RULE + '\n{%- if spheres %}\n- "ties"',
    )


CORE_RULES = (
    "{%- if nearby %}\n"
    "- Keep the summary, timeline and items to the {{ template }} itself: a "
    'claim mainly about another entry goes in "elsewhere".\n'
    + elsewhere_rule("the {{ template }}")
    + "\n"
    + HELD_BY_RULE.replace("{{ held_in }}", "an elsewhere claim")
    + "\n{%- endif %}"
)

FILL_RULES = (
    "{%- if nearby %}\n"
    '- Keep "new_items" to what belongs in {{ drawer_title }}: a claim mainly '
    'about another entry goes in "elsewhere".\n'
    + elsewhere_rule("{{ name }}")
    + "\n"
    + HELD_BY_RULE.replace("{{ held_in }}", "an elsewhere claim")
    + "\n{%- endif %}"
)

_FACTS_OLD = (
    '"text": "One claim, in a full sentence.", "since": "YEAR"}, '
    '{"category": "{{ categories[-1] }}", "text": "Another claim."}], '
    '"names": [{"name": "...", "kind": "place", "aka": []}]{% if spheres %}'
)
_FACTS_NEW = (
    '"text": "One claim, in a full sentence.", "since": "YEAR"'
    '{% if nearby %}, "held_by": null{% endif %}}, '
    '{"category": "{{ categories[-1] }}", "text": "Another claim."'
    '{% if nearby %}, "held_by": null{% endif %}}], '
    '"names": [{"name": "...", "kind": "place", "aka": []}]'
    "{% if nearby %}, " + ELSEWHERE_EXAMPLE + ', "part_of": {"entry": '
    '"<a sphere\'s name>", "drawer": "<one of its drawers>"}{% endif %}'
    '{% if broader %}, "move_in": ["<an M label>"]{% endif %}'
    "{% if spheres %}"
)
_NAMES_END = '"names": [{"name": "...", "kind": "place", "aka": []}]}'
_NAMES_END_NEW = (
    '"names": [{"name": "...", "kind": "place", "aka": []}]'
    "{% if nearby %}, " + ELSEWHERE_EXAMPLE + "{% endif %}}"
)


def _swap(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, (old[:60], source.count(old))
    return source.replace(old, new)


def create_template() -> str:
    source = (TEMPLATES / "create-thing.jinja2").read_text()
    source = _swap(
        source,
        "\nThe world's calendar: it is now",
        NEARBY_BLOCK + "\n" + BROADER_BLOCK + "\n\nThe world's calendar: it is now",
    )
    source = _swap(source, _FACTS_OLD, _FACTS_NEW)
    return _swap(
        source, '\n{%- if spheres %}\n- "ties"', CREATE_RULES + '\n{%- if spheres %}\n- "ties"'
    )


def core_template() -> str:
    source = (TEMPLATES / "sphere-core.jinja2").read_text()
    source = _swap(
        source,
        "\n\nIts drawers. A {{ template }} starts",
        "\n" + NEARBY_BLOCK + "\n\nIts drawers. A {{ template }} starts",
    )
    source = _swap(source, _NAMES_END, _NAMES_END_NEW)
    return _swap(
        source,
        "\n\nKeep every text to one sentence.",
        "\n" + CORE_RULES + "\n\nKeep every text to one sentence.",
    )


def fill_template() -> str:
    source = (TEMPLATES / "sphere-fill.jinja2").read_text()
    source = _swap(source, "\n{%- if existing %}", "\n" + NEARBY_BLOCK + "\n{%- if existing %}")
    source = _swap(source, _NAMES_END, _NAMES_END_NEW)
    return _swap(
        source,
        "\n\nNo commentary, no markdown fences, just the JSON object.",
        "\n" + FILL_RULES + "\n\nNo commentary, no markdown fences, just the JSON object.",
    )


CONTRA_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
Two entries of a fantasy world's records are being merged into one: {{ a_name }} and {{ b_name }}. Before their facts are combined, find the pairs that contradict each other: an A fact and a B fact that cannot both be true (two different years for the same event, two different holders of the same office, one says a thing stands and the other that it was destroyed). Facts that say the same thing in other words, that add a detail the other leaves out, or that are about different things, don't contradict.

{{ a_name }}, labelled A1, A2...:
{% for label, text in a_facts -%}
- {{ label }}: {{ text }}
{% endfor %}
{{ b_name }}, labelled B1, B2...:
{% for label, text in b_facts -%}
- {{ label }}: {{ text }}
{% endfor %}
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"contradictions": [{"a": "<an A label>", "b": "<a B label>", "why": "One short sentence."}]}

Each pair once. An empty list is fine when nothing contradicts. No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""

# v2, after v1 missed both date clashes (687/996, 217/312) and flagged
# details as contradictions: the clashing claims are named, and the
# bracketed years explained
CONTRA2_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
Two entries of a fantasy world's records are being merged into one: {{ a_name }} and {{ b_name }}. Before their facts are combined, find the pairs that contradict each other.

A pair contradicts only when an A fact and a B fact make claims about the same thing that cannot both be true: a different year for the same event, a different holder of the same office, a different place, colour, number or name for the same thing, or one saying a thing stands and the other that it is gone. Most pairs don't: two facts that say the same thing in other words, a fact that adds a detail the other leaves out, a fact that narrows the other ("mostly" against "some"), and facts about different things never contradict.

A year in brackets is when the fact's event happened ("In 687") or since when the fact has been true ("Since 312").

{{ a_name }}, labelled A1, A2...:
{% for label, text in a_facts -%}
- {{ label }}: {{ text }}
{% endfor %}
{{ b_name }}, labelled B1, B2...:
{% for label, text in b_facts -%}
- {{ label }}: {{ text }}
{% endfor %}
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"contradictions": [{"a": "<an A label>", "a_says": "the clashing claim, in a few words", "b": "<a B label>", "b_says": "the clashing claim, in a few words"}]}

Each pair once. An empty list is fine when nothing contradicts. No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""

SAME_TEMPLATE = """{#- Extractors:
  - response: AsIsExtractor()
-#}
<|SECTION:TASK|>
A new entry is about to be added to a fantasy world's records, and the world may already hold it under another name. Decide how the new entry A relates to B, an entry already in the world.

A, the new entry: {{ a_label }}
{% for text in a_facts -%}
- {{ text }}
{% endfor %}
B, already in the world: {{ b_label }}
{% for text in b_facts -%}
- {{ text }}
{% endfor %}
The answers:
- "same": A and B are one and the same thing: A's facts belong on B, and A's name becomes another name of B.
- "part": one is a part of the other (a hall inside a city, a chapter of a guild).
- "different": two distinct things, even if closely tied (a saint and the shrine named after her, a river and the town on its banks, a battle and the field it was fought on).
<|CLOSE_SECTION|>
<|SECTION:FORMAT|>
Reply with only one JSON object, shaped exactly like this example:
{"verdict": "different", "why": "One short sentence."}

No commentary, no markdown fences, just the JSON object.
<|CLOSE_SECTION|>
{{ set_prepared_response('{') }}
"""


def write_templates(folder: Path) -> None:
    (folder / "create-thing.jinja2").write_text(create_template())
    (folder / "sphere-core.jinja2").write_text(core_template())
    (folder / "sphere-fill.jinja2").write_text(fill_template())
    (folder / "cur-contra.jinja2").write_text(CONTRA_TEMPLATE)
    (folder / "cur-contra2.jinja2").write_text(CONTRA2_TEMPLATE)
    (folder / "cur-same.jinja2").write_text(SAME_TEMPLATE)


# --- worlds ----------------------------------------------------------------------


class Worlds:
    """Fresh copies of the snapshot: 'head', 'undo N' (every revision from
    N on undone), or 'w5' (the head with the White Talon a fact-less stub
    again)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.n = 0

    def open(self, spec: str) -> World:
        self.n += 1
        target = self.root / f"world-{self.n}"
        shutil.copytree(SNAPSHOT, target)
        world = World.open(target)
        if spec.startswith("undo "):
            rev = int(spec.split()[1])
            report = world.undo(
                list(range(rev, world.head_rev() + 1)), note="probe: before"
            )
            assert not report.conflicts, report.conflicts
        elif spec == "w5":
            view = world.view()
            talon = by_name(view, "White Talon")
            with world.revision(
                Source.manual(note="probe: the White Talon back to a stub")
            ) as rev:
                for fact in talon.facts:
                    rev.remove_fact(fact.fact_id)
                rev.set_field(talon.id, "stub", {"ignored": False}, None)
        else:
            assert spec == "head", spec
        return world


def by_name(view: WorldView, name: str):
    found = [t for t in view.things() if view.name_of(t.id) == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def fact_by_prefix(view: WorldView, prefix: str):
    for thing in view.things():
        for fact in thing.facts:
            if fact.fact_id.startswith(prefix):
                return thing, fact
    return None, None


def _clip(text: str, limit: int = LINE_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _drawer_title(view: WorldView, sphere_id: str, drawer_id: str | None) -> str | None:
    for drawer in spheres.drawers(view, sphere_id):
        if drawer.id == drawer_id:
            return drawer.title
    return None


def part_of_of(view: WorldView, state) -> tuple[str, str | None] | None:
    link = state.fields.get("part_of")
    if isinstance(link, dict) and isinstance(link.get("sphere"), str):
        return link["sphere"], link.get("drawer")
    return None


def dated(view: WorldView, fact) -> str:
    text = view.render(fact.text)
    if fact.valid_from is not None:
        year = fact.valid_from.to_datetime().year
        lead = "In" if fact.category == "timeline" else "Since"
        text = f"({lead} {year}) {text}"
    return text


# --- the candidate list -------------------------------------------------------------


def entry_line(view: WorldView, state) -> str:
    """One candidate: "Name (kind; usually called X; part of Y, in its Z
    drawer; drawers: ...; stub): its summary or first fact"."""

    template = state.fields.get("template")
    if spheres.is_sphere(state):
        bits = [
            f"sphere: {template}" if state.kind == "sphere" else f"{state.kind}, sphere: {template}"
        ]
    else:
        bits = [state.kind]
    everyday = everyday_name(state)
    if everyday:
        bits.append(f"usually called {everyday}")
    link = part_of_of(view, state)
    if link is not None:
        title = _drawer_title(view, link[0], link[1])
        bits.append(
            f"part of {view.name_of(link[0])}" + (f", in its {title} drawer" if title else "")
        )
    if spheres.is_sphere(state):
        titles = [
            d.title for d in spheres.drawers(view, state.id) if d.type in wp_spheres.TYPE_HELP
        ]
        if titles:
            bits.append("drawers: " + ", ".join(titles))
    if state.is_stub:
        bits.append("stub")
    fact = entries.summary_fact(state) if spheres.is_sphere(state) else None
    if fact is None and state.facts:
        fact = min(state.facts, key=lambda f: f.created)
    line = _clip(view.render(fact.text)) if fact is not None else "(nothing written yet)"
    return f"{view.name_of(state.id)} ({'; '.join(bits)}): {line}"


def candidates(
    view: WorldView,
    focus: list[str],
    first: list[str],
    reach: int,
    cap: int,
    exclude: set[str],
) -> tuple[list[str], list[dict]]:
    """Today's context entries first (`first`), then `near()` of each focus
    thing (best score kept), at most `cap`, never one in `exclude`."""

    best: dict[str, tuple[float, int]] = {}
    for thing_id in focus:
        for hit in near(view, thing_id, reach=reach, limit=1000):
            if hit.score > best.get(hit.thing_id, (0.0, 0))[0]:
                best[hit.thing_id] = (hit.score, hit.steps)
    ranked = sorted(
        best, key=lambda t: (-best[t][0], (view.name_of(t) or "").casefold(), t)
    )
    order: list[str] = []
    for thing_id in [*first, *ranked]:
        state = view.thing(thing_id)
        if (
            thing_id in order
            or thing_id in exclude
            or state is None
            or state.stub_ignored
        ):
            continue
        order.append(thing_id)
    order = order[:cap]
    lines = [entry_line(view, view.thing(t)) for t in order]
    info = [
        {
            "id": t,
            "name": view.name_of(t),
            "score": best.get(t, (None, None))[0],
            "steps": best.get(t, (None, None))[1],
            "first": t in first,
        }
        for t in order
    ]
    return lines, info


# --- calls ---------------------------------------------------------------------------


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


# the wrapper around Prompt.request: extra variables per template, and the
# last reply and variables seen
_EXTRA: dict[str, Any] = {}
_SEEN: list[tuple[str, dict, str]] = []
_ORIGINAL_REQUEST = Prompt.request.__func__


async def _request(cls, uid, client, kind, vars=None, **kwargs):
    variables = dict(vars or {})
    hook = _EXTRA.get(uid)
    if hook is not None:
        variables = hook(variables)
    if os.environ.get("PROBE_PRINT"):
        print(f"===== {uid} ({kind})\n" + str(Prompt.get(uid, variables)))
        raise RuntimeError("printed only")
    response, extracted = await _ORIGINAL_REQUEST(
        cls, uid, client, kind, vars=variables, **kwargs
    )
    _SEEN.append((uid, variables, extracted.get("response", response)))
    return response, extracted


Prompt.request = classmethod(_request)


async def _no_prose(*args, **kwargs) -> dict[str, str]:
    return {}


create._preview_prose = _no_prose


def _costed(client, before: int, reply: str) -> dict:
    call = client.calls[before] if len(client.calls) > before else {}
    cost = {
        "call": before,
        "kind": call.get("kind"),
        "seconds": call.get("seconds"),
        "prompt_tokens": count_tokens(call.get("prompt", "")),
        "reply_tokens": count_tokens(call.get("response", reply) or ""),
    }
    if call:
        call.update({k: v for k, v in cost.items() if k != "kind"})
    return {"reply": reply, **cost}


async def ask(client, folder: Path, uid: str, variables: dict) -> dict:
    before = len(client.calls)
    with PrependTemplateDirectories([str(folder)]):
        with world_ai_call():
            response, _ = await Prompt.request(uid, client, JUDGE_KIND, vars=variables)
    return _costed(client, before, response)


def resolve(view: WorldView, name: object) -> str | None:
    """The live thing a reply's name means (main or other name, bar case
    and a leading article), or None."""

    if not isinstance(name, str) or not name.strip():
        return None
    key = name_key(name)
    for state in view.things():
        if state.stub_ignored:
            continue
        names = [view.name_of(state.id) or ""]
        for entry in state.fields.get("aka") or []:
            if isinstance(entry, dict) and entry.get("name"):
                names.append(str(entry["name"]))
        if key in {name_key(n) for n in names}:
            return state.id
    return None


def read_elsewhere(view: WorldView, obj: dict | None) -> list[dict]:
    out = []
    for item in (obj or {}).get("elsewhere") or []:
        if not isinstance(item, dict):
            continue
        target = resolve(view, item.get("entry"))
        out.append(
            {
                "entry": item.get("entry"),
                "target_id": target,
                "target": view.name_of(target) if target else None,
                "text": item.get("text"),
                "held_by": item.get("held_by"),
                "held_by_id": resolve(view, item.get("held_by")),
            }
        )
    return out


async def run_preview(client, folder: Path, call, hook=None) -> dict:
    """Run one app preview (`call`, a coroutine factory) with the probe's
    templates and `hook` on the variables; the reply, its variables and
    cost, or the error."""

    _SEEN.clear()
    before = len(client.calls)
    error = result = None
    try:
        with PrependTemplateDirectories([str(folder)]):
            result = await call()
    except Exception as exc:  # a bad reply is a finding
        error = repr(exc)
    uid, variables, reply = _SEEN[-1] if _SEEN else (None, {}, "")
    out = _costed(client, before, reply)
    out.update(
        {
            "uid": uid,
            "error": error,
            "nearby": variables.get("nearby"),
            "broader": variables.get("broader"),
            "result": result,
        }
    )
    return out


# --- probe 1 ---------------------------------------------------------------------------


def _hook(extra: dict, drop_named: set[str] | None = None, overrides: dict | None = None):
    def apply(variables: dict) -> dict:
        variables = {**variables, **extra}
        if drop_named:
            variables["named"] = [
                n for n in variables.get("named") or [] if n[1].split(" (")[0] not in drop_named
            ]
        if overrides:
            variables.update(overrides)
        return variables

    return apply


def part_of_vars(view: WorldView, state) -> dict:
    link = part_of_of(view, state) if state is not None else None
    if link is None:
        return {"part_of_now": "", "part_of_sphere": ""}
    title = _drawer_title(view, link[0], link[1]) or "a drawer"
    sphere = view.name_of(link[0]) or ""
    return {"part_of_now": f"{sphere}, in its {title} drawer", "part_of_sphere": sphere}


def parse_create(view: WorldView, reply: str, broader_labels: dict | None) -> dict:
    obj = reply_object(reply, "facts") or {}
    facts = [
        {
            "text": f.get("text"),
            "category": f.get("category"),
            "since": f.get("since"),
            "held_by": f.get("held_by"),
            "held_by_id": resolve(view, f.get("held_by")),
        }
        for f in obj.get("facts") or []
        if isinstance(f, dict)
    ]
    move_in = obj.get("move_in")
    return {
        "name": obj.get("name"),
        "facts": facts,
        "elsewhere": read_elsewhere(view, obj),
        "names": obj.get("names"),
        "part_of": obj.get("part_of"),
        "move_in": move_in,
        "move_in_ids": [
            broader_labels.get(str(label).strip())
            for label in (move_in if isinstance(move_in, list) else [])
        ]
        if broader_labels
        else None,
        "parsed": bool(obj),
    }


def parse_core(view: WorldView, reply: str) -> dict:
    obj = reply_object(reply, "drawers") or {}
    return {
        "name": obj.get("name"),
        "summary": obj.get("summary"),
        "timeline": obj.get("timeline"),
        "drawers": obj.get("drawers"),
        "items": obj.get("items"),
        "elsewhere": read_elsewhere(view, obj),
        "names": obj.get("names"),
        "parsed": bool(obj),
    }


def parse_fill(view: WorldView, reply: str) -> dict:
    obj = reply_object(reply, "new_items") or {}
    return {
        "new_items": obj.get("new_items"),
        "elsewhere": read_elsewhere(view, obj),
        "names": obj.get("names"),
        "parsed": bool(obj),
    }


def case_setup(worlds: Worlds, key: str, spec: dict) -> tuple[World, dict]:
    """Open the case's world; the focus, first-listed and excluded things
    for its candidate list, and how to call the app's preview."""

    world = worlds.open(spec["world"])
    view = world.view()
    prompt_type = spec["prompt"]
    if prompt_type == "create-thing":
        stub = by_name(view, spec["stub"])
        gathered = gather_mentions(view, stub.id)
        first = [m.owner_id for m in gathered.mentioned]
        link = part_of_of(view, stub)
        if link:
            first.insert(0, link[0])
        setup = {
            "focus": [stub.id],
            "first": first,
            "exclude": {stub.id},
            "uid": "world.create-thing",
            "extra": part_of_vars(view, stub),
            "call": lambda: create.preview_thing(
                world,
                stub.kind,
                suggested_prompt(world.view(), stub.id),
                {},
                CLIENT[0],
                stub_id=stub.id,
                picks={},
            ),
            "prompt_text": suggested_prompt(view, stub.id),
        }
    elif prompt_type == "sphere-core":
        if "stub" in spec:
            target = by_name(view, spec["stub"])
            prompt = suggested_prompt(view, target.id)
            kwargs = {"stub_id": target.id}
        else:
            target = by_name(view, spec["promote"])
            prompt = ""
            kwargs = {"promote_id": target.id}
        gathered = gather_mentions(view, target.id)
        setup = {
            "focus": [target.id],
            "first": [m.owner_id for m in gathered.mentioned],
            "exclude": {target.id},
            "uid": "world.sphere-core",
            "extra": {},
            "call": lambda: wp_spheres.preview_sphere(
                world, spec["template"], prompt, {}, CLIENT[0], **kwargs
            ),
            "prompt_text": prompt,
        }
    else:
        sphere = by_name(view, spec["sphere"])
        drawer = next(d for d in spheres.drawers(view, sphere.id) if d.title == spec["drawer"])
        setup = {
            "focus": [sphere.id],
            "first": [],
            "exclude": {sphere.id},
            "uid": "world.sphere-fill",
            "extra": {},
            "call": lambda: wp_spheres.fill_drawer(world, sphere.id, drawer.id, CLIENT[0]),
            "prompt_text": None,
        }
    return world, setup


CLIENT: list[Any] = [None]


def _plain(result: Any) -> Any:
    if result is None:
        return None
    if hasattr(result, "model_dump"):
        dumped = result.model_dump(mode="json")
        return {k: dumped.get(k) for k in ("name", "items", "adopted", "part_of") if k in dumped}
    return result


async def run_p1(
    client, folder, worlds, labels, results, save, runs, only_cases=None, key_out="p1", only_variants=None
):
    variants = {
        k: v for k, v in labels["probe1"]["variants"].items() if not only_variants or k in only_variants
    }
    for key, spec in labels["probe1"]["cases"].items():
        if only_cases and key not in only_cases:
            continue
        world, setup = case_setup(worlds, key, spec)
        try:
            view = world.view()
            seen_lists: dict[tuple, str] = {}
            for variant, knobs in variants.items():
                lines, info = candidates(
                    view,
                    setup["focus"],
                    setup["first"],
                    knobs["reach"],
                    knobs["entries"],
                    setup["exclude"],
                )
                same_as = seen_lists.get(tuple(lines))
                if same_as is not None:
                    results["p1_lists"].append(
                        {"case": key, "variant": variant, "same_as": same_as, "candidates": info}
                    )
                    save()
                    continue
                seen_lists[tuple(lines)] = variant
                if key_out == "p1":
                    results["p1_lists"].append(
                        {"case": key, "variant": variant, "same_as": None, "candidates": info}
                    )
                _EXTRA.clear()
                _EXTRA[setup["uid"]] = _hook({"nearby": lines, **setup["extra"]})
                for n in range(runs):
                    if any(
                        r["case"] == key and r["variant"] == variant and r["n"] == n
                        for r in results[key_out]
                    ):
                        continue
                    out = await run_preview(client, folder, setup["call"])
                    reply = out["reply"] or ""
                    if spec["prompt"] == "create-thing":
                        parsed = parse_create(view, reply, None)
                    elif spec["prompt"] == "sphere-core":
                        parsed = parse_core(view, reply)
                    else:
                        parsed = parse_fill(view, reply)
                    out["result"] = _plain(out["result"])
                    results[key_out].append(
                        {"case": key, "variant": variant, "n": n, "prompt_text": setup["prompt_text"], **parsed, **out}
                    )
                    save()
        finally:
            _EXTRA.clear()
            world.close()


# --- probes 2, 4 (being) and 5: create calls at r2 -----------------------------------


def broader_vars(view: WorldView, name: str) -> tuple[list, dict]:
    state = by_name(view, name)
    facts = [
        f
        for f in sorted(state.facts, key=lambda f: f.created)
        if not (f.origin or {}).get("summary")
    ]
    pairs, labels = [], {}
    for i, fact in enumerate(facts, 1):
        label = f"M{i}"
        labels[label] = fact.fact_id[:8]
        pairs.append((label, dated(view, fact)))
    return pairs, labels


def create_cases(labels: dict) -> list[dict]:
    """The create runs of probes 2, 4 and 5, each once (the Zakonnik serves
    probes 2 and 5)."""

    cases = []
    for name, spec in labels["probe2"]["cases"].items():
        cases.append({"case": name, "probes": ["p2"], **spec})
    for name, spec in labels["probe5"]["positives"].items():
        cases.append({"case": name, "probes": ["p5"], "world": "w5", "stub": spec["stub"]})
    for name, spec in labels["probe5"]["negatives"].items():
        if not isinstance(spec, dict):
            continue
        existing = next((c for c in cases if c["case"] == name), None)
        if existing:
            existing["probes"].append("p5")
        else:
            cases.append({"case": name, "probes": ["p5"], "world": "w5", "stub": spec["stub"]})
    for name, spec in labels["probe5"]["positives"].items():
        cases.append(
            {"case": f"v2:{name}", "probes": ["p5v2"], "world": "w5", "stub": spec["stub"]}
        )
    being = labels["probe4"]["cases"]["being:The Eternal Light"]
    cases.append({"case": "being:The Eternal Light", "probes": ["p4"], **being})
    return cases


async def run_creates(client, folder, worlds, labels, results, save, runs, which):
    knobs = labels["probe1"]["variants"]["r2"]
    for case in create_cases(labels):
        if not set(case["probes"]) & set(which):
            continue
        world = worlds.open(case["world"])
        try:
            view = world.view()
            broader = broader_labels = None
            extra: dict[str, Any] = {}
            drop: set[str] = set()
            overrides: dict[str, Any] = {}
            if case.get("broader"):
                broader, broader_labels = broader_vars(view, case["broader"])
                extra.update({"broader": broader, "broader_name": case["broader"]})
                drop.add(case["broader"])
            if case.get("stub"):
                stub = by_name(view, case["stub"])
                gathered = gather_mentions(view, stub.id)
                first = [m.owner_id for m in gathered.mentioned]
                link = part_of_of(view, stub)
                if link:
                    first.insert(0, link[0])
                focus, exclude = [stub.id], {stub.id}
                extra.update(part_of_vars(view, stub))
                prompt = suggested_prompt(view, stub.id)
                kind = stub.kind
                kwargs = {"stub_id": stub.id, "picks": {}}
            else:
                picks = {name: by_name(view, name).id for name in case.get("picks", [])}
                focus = [*picks.values()]
                first = [*picks.values()]
                if case.get("broader"):
                    bid = by_name(view, case["broader"]).id
                    focus.append(bid)
                    first.insert(0, bid)
                exclude = set()
                if case["case"].startswith("being:"):
                    exclude.add(by_name(view, "Eternal Light").id)
                    overrides = {"kind": "being", "categories": BEING_CATEGORIES}
                extra.update({"part_of_now": "", "part_of_sphere": ""})
                prompt = case.get("prompt") or case["new"]["prompt"]
                kind = (case.get("new") or {}).get("kind", "lore")
                kwargs = {"picks": picks}
            lines, info = candidates(view, focus, first, knobs["reach"], knobs["entries"], exclude)
            extra["nearby"] = lines
            _EXTRA.clear()
            _EXTRA["world.create-thing"] = _hook(extra, drop, overrides)
            for n in range(runs):
                if any(r["case"] == case["case"] and r["n"] == n for r in results["creates"]):
                    continue

                def call(kind=kind, prompt=prompt, kwargs=kwargs):
                    return create.preview_thing(world, kind, prompt, {}, CLIENT[0], **kwargs)

                out = await run_preview(client, folder, call)
                parsed = parse_create(view, out["reply"] or "", broader_labels)
                out["result"] = None
                results["creates"].append(
                    {
                        "case": case["case"],
                        "probes": case["probes"],
                        "n": n,
                        "prompt_text": prompt,
                        "candidates": info,
                        "broader_labels": broader_labels,
                        **parsed,
                        **out,
                    }
                )
                save()
        finally:
            _EXTRA.clear()
            world.close()


# --- probe 3 ------------------------------------------------------------------------------


def contra_side(view: WorldView, spec: dict, letter: str) -> tuple[str, list, dict]:
    pairs, labels = [], {}
    if "entry" in spec:
        name = spec["entry"]
        state = by_name(view, name)
        facts = sorted(state.facts, key=lambda f: f.created)
        for i, fact in enumerate(facts, 1):
            labels[f"{letter}{i}"] = fact.fact_id[:8]
            pairs.append((f"{letter}{i}", dated(view, fact)))
        return name, pairs, labels
    name = spec["constructed"]
    if "facts" in spec:
        for i, prefix in enumerate(spec["facts"], 1):
            _, fact = fact_by_prefix(view, prefix)
            labels[f"{letter}{i}"] = prefix
            pairs.append((f"{letter}{i}", dated(view, fact)))
    else:
        for i, (key, text) in enumerate(spec["texts"].items(), 1):
            labels[f"{letter}{i}"] = key
            pairs.append((f"{letter}{i}", text))
    return name, pairs, labels


async def run_p3(client, folder, worlds, labels, results, save, runs, key_out="p3", uid="world.cur-contra"):
    world = worlds.open("head")
    try:
        view = world.view()
        for key, spec in labels["probe3"]["cases"].items():
            a_name, a_facts, a_labels = contra_side(view, spec["a"], "A")
            b_name, b_facts, b_labels = contra_side(view, spec["b"], "B")
            variables = {"a_name": a_name, "b_name": b_name, "a_facts": a_facts, "b_facts": b_facts}
            for n in range(runs):
                if any(r["case"] == key and r["n"] == n for r in results[key_out]):
                    continue
                out = await ask(client, folder, uid, variables)
                obj = reply_object(out["reply"], "contradictions") or {}
                pairs = [
                    {
                        "a": a_labels.get(str(p.get("a")).strip()),
                        "b": b_labels.get(str(p.get("b")).strip()),
                        "a_label": p.get("a"),
                        "b_label": p.get("b"),
                        "why": p.get("why"),
                        "a_says": p.get("a_says"),
                        "b_says": p.get("b_says"),
                    }
                    for p in obj.get("contradictions") or []
                    if isinstance(p, dict)
                ]
                results[key_out].append(
                    {
                        "case": key,
                        "n": n,
                        "a_labels": a_labels,
                        "b_labels": b_labels,
                        "pairs": pairs,
                        "parsed": bool(obj),
                        **out,
                    }
                )
                save()
    finally:
        world.close()


# --- same thing ------------------------------------------------------------------------------


def _label(view: WorldView, state) -> str:
    bits = [state.kind]
    if state.fields.get("template"):
        bits.append(f"sphere: {state.fields['template']}")
    link = part_of_of(view, state)
    if link:
        bits.append(f"part of {view.name_of(link[0])}")
    return f"{view.name_of(state.id)} ({', '.join(bits)})"


def same_sides(worlds: Worlds, pair: dict) -> tuple[dict, list]:
    a = pair["a"]
    world = worlds.open("head")
    try:
        head = world.view()
        state = by_name(head, a["expanded"])
        if a.get("facts_only") or a.get("rev") is None:
            new = sorted(state.facts, key=lambda f: f.created)
            before = head
        else:
            before = world.view(world.present(), rev=a["rev"] - 1)
            had = {f.fact_id for f in (before.thing(state.id).facts if before.thing(state.id) else [])}
            new = [f for f in sorted(state.facts, key=lambda f: f.created) if f.fact_id not in had]
        a_facts = [_clip(head.render(f.text), 260) for f in new[:6]]
        a_label = f"{a['expanded']} ({state.kind})"
        b_view = head if pair["b"].get("at_head") or a.get("rev") is None else before
        b_state = by_name(b_view, pair["b"]["entry"])
        b_facts = [
            _clip(b_view.render(f.text), 260)
            for f in sorted(b_state.facts, key=lambda f: f.created)[:6]
        ]
        candidates_found = [
            head.name_of(c.thing_id)
            for c in same_candidates(head, a["expanded"], near_ids=[], limit=5, exclude={state.id})
        ]
        variables = {
            "a_label": a_label,
            "a_facts": a_facts,
            "b_label": _label(b_view, b_state),
            "b_facts": b_facts,
        }
        return variables, candidates_found
    finally:
        world.close()


async def run_same(client, folder, worlds, labels, results, save, runs):
    for pair in labels["same_thing"]["pairs"]:
        variables, found = same_sides(worlds, pair)
        for n in range(runs):
            if any(r["pair"] == pair["id"] and r["n"] == n for r in results["same"]):
                continue
            out = await ask(client, folder, "world.cur-same", variables)
            obj = reply_object(out["reply"], "verdict") or {}
            results["same"].append(
                {
                    "pair": pair["id"],
                    "n": n,
                    "truth": pair["truth"],
                    "a": variables["a_label"],
                    "b": variables["b_label"],
                    "a_facts": len(variables["a_facts"]),
                    "b_facts": len(variables["b_facts"]),
                    "same_candidates": found,
                    "verdict": obj.get("verdict"),
                    "why": obj.get("why"),
                    **out,
                }
            )
            save()


# --- labels check -------------------------------------------------------------------------------


def check_labels(worlds: Worlds, labels: dict) -> list[str]:
    problems = []
    for spec_world in {"head", "w5"}:
        world = worlds.open(spec_world)
        view = world.view()
        names = {view.name_of(t.id) for t in view.things()}
        for case in labels["probe1"]["cases"].values():
            for home in case["homes"]:
                for name in home["homes"]:
                    if name not in names:
                        problems.append(f"p1 home {name!r} not in {spec_world}")
        world.close()
    for name, spec in labels["probe2"]["cases"].items():
        world = worlds.open(spec["world"])
        view = world.view()
        _, b_labels = broader_vars(view, spec["broader"])
        offered = set(b_labels.values())
        labelled = set(spec["move"]) | set(spec["either"]) | set(spec["stay"])
        if offered != labelled:
            problems.append(f"p2 {name}: offered-labelled {offered - labelled}, labelled-offered {labelled - offered}")
        world.close()
    world = worlds.open("head")
    view = world.view()
    for name, spec in labels["probe3"]["cases"].items():
        _, _, a = contra_side(view, spec["a"], "A")
        _, _, b = contra_side(view, spec["b"], "B")
        for c in spec["contradictions"] + spec.get("bonus", []):
            for x in c["a"]:
                if x not in a.values():
                    problems.append(f"p3 {name}: {x} not on A")
            for x in c["b"]:
                if x not in b.values():
                    problems.append(f"p3 {name}: {x} not on B")
    world.close()
    return problems


# --- main ------------------------------------------------------------------------------------


async def main(out: Path, only: list[str], runs: int, p1_cases: list[str] | None) -> None:
    labels = json.loads(LABELS.read_text())
    harness._quiet_loading(False)
    results: dict[str, Any] = (
        json.loads(out.read_text())
        if out.exists()
        else {"probe": "curation", "date": "2026-10-22", "calls": []}
    )
    for key in ("p1", "p1v3", "p1_lists", "creates", "p3", "p3v2", "same"):
        results.setdefault(key, [])

    def save() -> None:
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str) + "\n")

    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        os.chdir(root)
        worlds = Worlds(root_path)
        problems = check_labels(worlds, labels)
        if "labels" in only:
            print("\n".join(problems) or "labels: ok")
        assert not problems, problems
        if set(only) & {"p1", "p1v3", "p2", "p3", "p3v2", "p4", "p5", "p5v2", "same"}:
            client = harness.RecordingClient(name="KoboldCpp")
            await client.status()
            CLIENT[0] = client
            results["model"] = client.model_name
            client.calls = results["calls"]
            client.on_call = save
            folder = root_path / "templates"
            folder.mkdir()
            write_templates(folder)
            results["templates"] = {
                "create-thing": create_template(),
                "sphere-core": core_template(),
                "sphere-fill": fill_template(),
                "contra": CONTRA_TEMPLATE,
                "contra2": CONTRA2_TEMPLATE,
                "same": SAME_TEMPLATE,
            }
            started = time.monotonic()
            if "p3" in only:
                await run_p3(client, folder, worlds, labels, results, save, runs)
            if "p3v2" in only:
                await run_p3(
                    client, folder, worlds, labels, results, save, runs, "p3v2", "world.cur-contra2"
                )
            if "same" in only:
                await run_same(client, folder, worlds, labels, results, save, runs)
            which = [p for p in ("p2", "p4", "p5") if p in only]
            if which:
                await run_creates(client, folder, worlds, labels, results, save, runs, which)
            if "p5v2" in only:
                folder2 = root_path / "templates-v2"
                folder2.mkdir()
                write_templates(folder2)
                (folder2 / "create-thing.jinja2").write_text(create_template_v2())
                results["templates"]["create-thing-p5v2"] = create_template_v2()
                await run_creates(client, folder2, worlds, labels, results, save, runs, ["p5v2"])
            if "p1v3" in only:
                folder3 = root_path / "templates-v3"
                folder3.mkdir()
                write_templates(folder3)
                (folder3 / "create-thing.jinja2").write_text(create_template_v3())
                (folder3 / "sphere-fill.jinja2").write_text(fill_template_v3())
                results["templates"]["create-thing-p1v3"] = create_template_v3()
                results["templates"]["sphere-fill-p1v3"] = fill_template_v3()
                await run_p1(
                    client, folder3, worlds, labels, results, save, runs,
                    ["create:The Divine Right of the Tsar", "create:The Illumination",
                     "create:Deepcarving", "fill:Runeweaving/Sites"],
                    "p1v3", ["r2"],
                )
            if "p1" in only:
                await run_p1(client, folder, worlds, labels, results, save, runs, p1_cases)
            results.setdefault("minutes", {})[" ".join(only)] = round(
                (time.monotonic() - started) / 60, 1
            )
            save()


def dry(case: str | None) -> None:
    """Print the candidate lists of every probe 1 case and variant, and one
    rendered prompt of each template, calling nothing but the token counter."""

    labels = json.loads(LABELS.read_text())
    harness._quiet_loading(False)
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        worlds = Worlds(root_path)
        folder = root_path / "templates"
        folder.mkdir()
        write_templates(folder)
        for key, spec in labels["probe1"]["cases"].items():
            world, setup = case_setup(worlds, key, spec)
            view = world.view()
            for variant, knobs in labels["probe1"]["variants"].items():
                lines, info = candidates(
                    view, setup["focus"], setup["first"], knobs["reach"], knobs["entries"], setup["exclude"]
                )
                tokens = count_tokens("\n".join(lines))
                print(key, variant, len(lines), "tokens", tokens, [i["name"] for i in info])
            world.close()
        os.environ["PROBE_PRINT"] = "1"
        CLIENT[0] = object()
        create.prose_gen.require_client = lambda client: None
        wp_spheres.prose_gen.require_client = lambda client: None
        for key in [k for k in labels["probe1"]["cases"] if case is None or k == case]:
            spec = labels["probe1"]["cases"][key]
            world, setup = case_setup(worlds, key, spec)
            lines, _ = candidates(world.view(), setup["focus"], setup["first"], 2, 12, setup["exclude"])
            _EXTRA[setup["uid"]] = _hook({"nearby": lines, **setup["extra"]})
            with PrependTemplateDirectories([str(folder)]):
                try:
                    asyncio.run(setup["call"]())
                except RuntimeError:
                    pass
            world.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path, nargs="?")
    parser.add_argument("--only", nargs="+", default=["labels"])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--p1-cases", nargs="*")
    parser.add_argument("--dry", action="store_true", help="print lists, call no model")
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.dry:
        dry(args.case)
    else:
        out = args.out.resolve() if args.out else REPO / "docs/superpowers/probes/raw/2026-10-22-curation.json"
        asyncio.run(main(out, args.only, args.runs, args.p1_cases))
