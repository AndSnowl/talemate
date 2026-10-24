"""Group synopses and group "+ Add" (Filing plan, Task 8).

A page's Connected section groups what's filed in it by tag
(`world.filing.connected`). Each group gets:

- **Synopsis** (`group_synopsis`): a short AI summary of the group, cached
  as the page's prose section `synopsis:<tag>` (`world.prose`). A group has
  no "as of" date of its own -- only "now" -- so it's cached as the single
  open stretch, and its freshness is a content key (`prose.content_key`,
  built from the current members' labels and facts, and the page's own
  summary) rather than the usual story-time staleness: unlike an ordinary
  prose section, a filing or tag change (`world.prose.UNRENDERED_FIELDS`)
  must invalidate it, and that's a change to a *member*, which the page's
  own timeline never sees. Probe 3 passed
  (docs/superpowers/probes/2026-10-23-filing.md), so synopses are on;
  `SYNOPSIS_ENABLED` is the flag a probe fallback would clear, which makes
  `group_synopsis` return "" without asking the model or touching the
  cache.
- **"+ Add"** (`group_add`): up to 3 new entries from the owner's prompt
  (probe 6's wording, v2), as draft rows (ticked, for the owner to amend);
  `accept_group_add` writes the ticked ones as stubs in one revision, filed
  in the page with the row's tag, the row's line their first fact and
  their summary (ruling F22: `{"summary": True}`). `tag=None` is the
  page's own top-level "+ Add" (no tag preset, the spec's "same with no
  tag preset"); the probed wording is unprobed for that case, so the
  template adapts rather than forcing a false tag onto it (and a row's own
  tag, cleaned, is kept rather than overridden). Either way, a name whose
  kind or tag is a title word is dropped (ruling F5), in the draft and
  again on accept -- the client's copy is never trusted.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic import BaseModel

from talemate.prompts import Prompt
from talemate.world import entries
from talemate.world.filing import (
    OTHER_HEADING,
    Filing,
    connected,
    mentioned_in,
    tag_heading,
    tag_of,
)
from talemate.world.prose import content_key
from talemate.world.store import Source, World
from talemate.world.view import ThingState, WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call
from talemate.worldplay.create import (
    TITLE_WORDS,
    clean_tag,
    current_date,
    default_category,
    json_objects,
)
from talemate.worldplay.held import held_text
from talemate.worldplay.links import FALLBACK_KIND, link_text

log = structlog.get_logger("talemate.worldplay.groups")

__all__ = [
    "ALLOWED_KINDS",
    "GroupAddRow",
    "SYNOPSIS_ENABLED",
    "accept_group_add",
    "group_add",
    "group_synopsis",
]

# Probe 3 passed (docs/superpowers/probes/2026-10-23-filing.md): synopses
# are written. A probe fallback (the spec's "a failure falls back to ...
# off (synopsis)") clears this, and `group_synopsis` then returns ""
# without asking the model or reading/writing the cache.
SYNOPSIS_ENABLED = True

SYNOPSIS_PROMPT_KIND = "analyze"
ADD_PROMPT_KIND = "creative_instruction_1024"

# a member's own facts shown, beyond its summary (probe 3's "up to 5")
MEMBER_FACTS = 5
# a stub member's "mentioned by" lines, at most (probe 3's "up to 3")
STUB_MENTIONS = 3
# the page's own facts shown to group-add, beyond its summary
PAGE_FACTS_SHOWN = 8
# "Other entries near it", at most
NEARBY_SHOWN = 12

# a group-add reply's entries, at most (probe 6's "never more than 3")
MAX_ADD_ROWS = 3

# the kinds group-add's reply may use (probe 6's wording)
ALLOWED_KINDS: tuple[str, ...] = (
    "character",
    "place",
    "species",
    "race",
    "event",
    "item",
    "lore",
)


class GroupAddRow(BaseModel):
    """One of `group_add`'s draft rows: a new entry's `name`, `kind` and
    `line` (its first fact and summary on accept), and its `tag` (the
    group's, or, with no tag preset, its own); `ticked` for the owner to
    amend before `accept_group_add`."""

    name: str
    kind: str
    tag: str | None = None
    line: str
    ticked: bool = True


# --- synopsis ---------------------------------------------------------------


def _group_section(tag: str | None) -> str:
    return f"synopsis:{tag}" if tag is not None else "synopsis:"


def _group_label(tag: str | None) -> str:
    """The group's name, lowercase and mid-sentence ("rivers", "other
    entries"), for "the {{ group }} filed in {{ page }}"."""

    if tag is not None:
        return tag_heading(tag).lower()
    return f"{OTHER_HEADING.lower()} entries"


def _group_rows(
    view: WorldView, thing_id: str, tag: str | None
) -> list[tuple[ThingState, Filing]]:
    """The live, unignored rows of one tag group filed in `thing_id`, at
    the latest telling (an ended filing counted too, as the page shows
    it)."""

    for group in connected(view, thing_id, include_ended=True):
        if group.tag != tag:
            continue
        rows = []
        for row_id, filing in group.rows:
            state = view.thing(row_id)
            if state is not None and not state.stub_ignored:
                rows.append((state, filing))
        return rows
    return []


def _member_label(view: WorldView, state: ThingState, filing: Filing) -> str:
    bits = [state.kind]
    tag = tag_of(state)
    if tag:
        bits.append(tag)
    if filing.role:
        bits.append(filing.role)
    return f"{view.name_of(state.id) or ''} ({', '.join(bits)})"


def _own_facts(view: WorldView, state: ThingState, limit: int) -> list[str]:
    """`state`'s summary, then up to `limit` of its own undated facts, the
    most-linked first (as a scene's touched entries are shown,
    `worldplay.context._touched_entry`), each rendered as belief when it's
    held."""

    head = entries.summary_fact(state)
    own = sorted(
        (
            fact
            for fact in state.facts
            if fact.valid_from is None
            and not entries.is_summary_fact(fact)
            and (head is None or fact.fact_id != head.fact_id)
        ),
        key=lambda fact: (-len(set(fact.refs)), fact.created),
    )[:limit]
    chosen = ([head] if head is not None else []) + own
    return [held_text(view, fact, state) for fact in chosen]


def _stub_facts(view: WorldView, thing_id: str) -> list[str]:
    """Up to `STUB_MENTIONS` "(stub) mentioned by X: ..." lines, from what
    else references the stub (`view.referencing`)."""

    lines = []
    for owner_id, fact in view.referencing(thing_id):
        name = view.name_of(owner_id) or ""
        lines.append(f"(stub) mentioned by {name}: {view.render(fact.text)}")
        if len(lines) == STUB_MENTIONS:
            break
    return lines


def _member_payload(
    view: WorldView, state: ThingState, filing: Filing
) -> dict[str, object]:
    facts = (
        _stub_facts(view, state.id)
        if state.is_stub
        else _own_facts(view, state, MEMBER_FACTS)
    )
    return {"label": _member_label(view, state, filing), "facts": facts}


def _page_summary(world: World, view: WorldView, thing_id: str) -> str:
    cached = world.prose().get(thing_id, "description", None)
    return entries.summary(view, thing_id, cached.text if cached is not None else None)


def _parse_synopsis(reply: str) -> str:
    for obj in json_objects(reply):
        value = obj.get("synopsis")
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""


def _encode_synopsis(key: str, synopsis: str) -> str:
    return json.dumps({"key": key, "synopsis": synopsis})


def _decode_synopsis(text: str) -> tuple[str | None, str]:
    """`(key, synopsis)` from what `group_synopsis` cached, or `(None,
    "")` for anything that doesn't parse as its own shape (a section
    `group_synopsis` has never written to, or one some other caller did)."""

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None, ""
    if isinstance(obj, dict) and isinstance(obj.get("synopsis"), str):
        key = obj.get("key")
        return (key if isinstance(key, str) else None), obj["synopsis"]
    return None, ""


async def group_synopsis(
    world: World, thing_id: str, tag: str | None, client: Any
) -> str:
    """The group's synopsis (probe 3's wording, the `analyze` kind),
    cached as the page's prose section `synopsis:<tag>`. Fresh when a
    content key built from the group's current members (their labels and
    facts) and the page's own summary matches what's cached; stale
    otherwise, including nothing cached yet. "" with no members to
    summarise, or with `SYNOPSIS_ENABLED` off: nothing is asked and
    nothing is cached either way. A missing `thing_id` is a `KeyError`."""

    if not SYNOPSIS_ENABLED:
        return ""
    view = world.view()
    if view.thing(thing_id) is None:
        raise KeyError(f"no such entry: {thing_id}")
    rows = _group_rows(view, thing_id, tag)
    if not rows:
        return ""

    members = [_member_payload(view, state, filing) for state, filing in rows]
    page_summary = _page_summary(world, view, thing_id)
    key = content_key(tag, page_summary, [(m["label"], m["facts"]) for m in members])

    section = _group_section(tag)
    cache = world.prose()
    cached = cache.get(thing_id, section, None)
    if cached is not None:
        stored_key, stored_synopsis = _decode_synopsis(cached.text)
        if stored_key == key:
            return stored_synopsis

    prose_gen.require_client(client)
    page_name = view.name_of(thing_id) or ""
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.group-synopsis",
            client,
            SYNOPSIS_PROMPT_KIND,
            vars={
                "group": _group_label(tag),
                "page": page_name,
                "page_summary": page_summary,
                "members": members,
            },
        )
    synopsis = _parse_synopsis(extracted["response"])
    cache.put(thing_id, section, None, None, _encode_synopsis(key, synopsis))
    log.info("groups.synopsis", thing_id=thing_id, tag=tag, members=len(members))
    return synopsis


# --- "+ Add" -----------------------------------------------------------------


def _clean_kind(value: object) -> str:
    kind = value.strip().lower() if isinstance(value, str) else ""
    return kind if kind in ALLOWED_KINDS else FALLBACK_KIND


def _is_title(kind: str, tag: str | None) -> bool:
    """Ruling F5: a name whose kind or tag is a title word is dropped."""

    return kind in TITLE_WORDS or (tag or "") in TITLE_WORDS


def _parse_add_entries(reply: str) -> list[dict[str, Any]]:
    for obj in json_objects(reply):
        value = obj.get("entries")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _group_and_filed(
    view: WorldView, thing_id: str, tag: str | None
) -> tuple[list[str], list[str]]:
    """`(members, filed)` for the group-add prompt: the names already in
    this tag's group (`tag=None` is the untagged/"Other" one -- the
    page's own top-level "+ Add" acts on it), and, as "Name (tag)", what
    else is filed in the page, an ignored stub left out of both."""

    members: list[str] = []
    filed: list[str] = []
    for group in connected(view, thing_id, include_ended=True):
        for row_id, _filing in group.rows:
            state = view.thing(row_id)
            if state is None or state.stub_ignored:
                continue
            name = view.name_of(row_id) or ""
            if group.tag == tag:
                members.append(name)
            elif group.tag is not None:
                filed.append(f"{name} ({group.tag})")
            else:
                filed.append(name)
    return members, filed


async def group_add(
    world: World, thing_id: str, tag: str | None, prompt: str, client: Any
) -> list[GroupAddRow]:
    """New entries for one tag group, or (`tag=None`) the page's own
    top-level "+ Add", from the owner's `prompt` (probe 6's wording, the
    `creative_instruction_1024` kind), writing nothing. At most
    `MAX_ADD_ROWS` ticked rows, each dropped if its name is blank or its
    kind or tag is a title word (ruling F5) -- `accept_group_add` checks
    again, never trusting this draft back from the client. A missing
    `thing_id` is a `KeyError`; a blank `prompt` a `ValueError`."""

    if not prompt.strip():
        raise ValueError("say what the new entries are")
    view = world.view()
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such entry: {thing_id}")
    prose_gen.require_client(client)

    calendar = world.calendar
    now = current_date(world)
    page_name = view.name_of(thing_id) or ""
    page_facts = _own_facts(view, state, PAGE_FACTS_SHOWN)
    members, filed = _group_and_filed(view, thing_id, tag)
    nearby = [
        view.name_of(owner_id) or ""
        for owner_id in mentioned_in(view, thing_id, include_ended=True)
    ][:NEARBY_SHOWN]

    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.group-add",
            client,
            ADD_PROMPT_KIND,
            vars={
                "tag": tag,
                "page": page_name,
                "prompt": prompt.strip(),
                "page_kind": state.kind,
                "page_tag": tag_of(state),
                "page_facts": page_facts,
                "members": members,
                "filed": filed,
                "nearby": nearby,
                "now_label": calendar.format(now),
                "now_year": now.to_datetime().year,
            },
        )

    rows: list[GroupAddRow] = []
    for raw in _parse_add_entries(extracted["response"])[:MAX_ADD_ROWS]:
        name = " ".join(str(raw.get("name") or "").split())
        line = " ".join(str(raw.get("line") or "").split())
        if not name or not line:
            continue
        kind = _clean_kind(raw.get("kind"))
        row_tag = tag if tag is not None else clean_tag(raw.get("tag"))
        if _is_title(kind, row_tag):
            continue
        rows.append(
            GroupAddRow(name=name, kind=kind, tag=row_tag, line=line, ticked=True)
        )
    log.info("groups.add", thing_id=thing_id, tag=tag, rows=len(rows))
    return rows


def accept_group_add(world: World, thing_id: str, rows: list[GroupAddRow]) -> list[str]:
    """Write `rows`' ticked ones as stubs, in one revision: each filed in
    `thing_id` with its own `tag`, its `line` its first fact and its
    summary (ruling F22: `{"summary": True}`), its text linked as a
    hand-written fact's. Checked again here, never trusted from the
    client: a blank name, an unknown kind, or a kind/tag that's a title
    word (ruling F5) drops the row. Returns the new stubs' ids, in the
    order written. `thing_id` must be live (`KeyError`)."""

    view = world.view()
    if view.thing(thing_id) is None:
        raise KeyError(f"no such entry: {thing_id}")

    kept: list[tuple[str, str, str | None, str]] = []
    for row in rows:
        if not row.ticked:
            continue
        name = " ".join(row.name.split())
        line = " ".join(row.line.split())
        kind = row.kind.strip().lower()
        tag = clean_tag(row.tag) if row.tag else None
        if not name or not line or kind not in ALLOWED_KINDS:
            continue
        if _is_title(kind, tag):
            continue
        kept.append((name, kind, tag, line))

    written: list[str] = []
    if not kept:
        return written
    with world.revision(Source.manual(note="added from a group prompt")) as rev:
        for name, kind, tag, line in kept:
            fields: dict[str, object] = {
                "name": name,
                "filings": [
                    {
                        "target": thing_id,
                        "role": None,
                        "since": None,
                        "until": None,
                        "within": None,
                        "exceptions": [],
                    }
                ],
            }
            if tag:
                fields["tag"] = tag
            new_id = rev.create_thing(kind, fields=fields)
            rev.add_fact(
                new_id,
                default_category(kind, False),
                link_text(view, line, owner=new_id),
                origin={"summary": True},
            )
            written.append(new_id)
    log.info("groups.accept_add", thing_id=thing_id, written=len(written))
    return written
