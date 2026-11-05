"""A person's name in the world (languages 4b-2): their name parts read
and written, the context their name is built in (their language, their
connections, what they're built as), titles, pet names and the names
others call them. The engine is `talemate.languages.person_names`."""

from __future__ import annotations

import random

from talemate.languages.entry import language_of
from talemate.languages.lookup import default_language, languages_for
from talemate.languages.person_names import (
    PersonContext,
    choose,
    connections_of,
    kept_title,
    roll_pet_name,
    written,
)
from talemate.world.filing import filings_of
from talemate.world.store import Revision, World
from talemate.worldplay.repoint import drop_other_names, rename_everywhere

__all__ = [
    "add_title",
    "calls_out",
    "draft_context",
    "kept_title_offer",
    "person_context",
    "person_language",
    "remove_title",
    "set_built_as",
    "set_part",
    "set_pet_name",
    "stored_parts",
]

# the keys a stored part keeps
_PART_KEYS = ("label", "text", "source", "from_id", "from_role")


def person_language(view, thing_id: str | None):
    """The person's language entry: the one their name parts were built
    in, else the language naming starts from for them; None without one."""

    state = view.thing(thing_id) if thing_id else None
    stored = state.fields.get("name_parts") if state is not None else None
    if isinstance(stored, dict):
        found = view.thing(str(stored.get("language") or ""))
        if found is not None and found.kind == "language":
            return found
    if state is None:
        return None
    language_id = default_language(languages_for(view, thing_id))
    return view.thing(language_id) if language_id else None


def _own(stored: object) -> dict[str, str]:
    if not isinstance(stored, dict):
        return {}
    return {
        str(p.get("label")): str(p.get("text"))
        for p in stored.get("parts") or []
        if isinstance(p, dict) and p.get("label")
    }


def person_context(
    view, thing_id: str, *, built_as: dict[str, str] | None = None
) -> PersonContext:
    """The context a person's name is built in: their live filings and
    relationship facts' links, what they're built as (stored, unless
    given), and their own parts."""

    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")
    stored = state.fields.get("name_parts")
    filings = [(f.target, f.role) for f in filings_of(view, thing_id)]
    facts = [
        (f.text, list(f.refs)) for f in state.facts if f.category == "relationship"
    ]
    if built_as is None:
        built_as = (
            dict(stored.get("built_as") or {}) if isinstance(stored, dict) else {}
        )
    return PersonContext(
        thing_id=thing_id,
        built_as=built_as,
        connections=connections_of(view, thing_id, filings, facts),
        own=_own(stored),
    )


def draft_context(view, draft: dict) -> PersonContext:
    """The context for a person on a draft: its `filings` (`[target_id,
    role]`), relationship `facts` (`[text, refs]`) and `built_as`."""

    filings = [
        (str(row[0]), str(row[1] or "")) for row in draft.get("filings") or [] if row
    ]
    facts = [
        (str(row[0]), [str(r) for r in row[1] or []])
        for row in draft.get("facts") or []
        if row
    ]
    return PersonContext(
        built_as=dict(draft.get("built_as") or {}),
        connections=connections_of(view, None, filings, facts),
    )


def stored_parts(
    language_id: str,
    rule_id: str,
    shape: int,
    built_as: dict[str, str],
    parts: list[dict],
) -> dict:
    """`name_parts` as the store keeps them: each part's known keys, empty
    `from_` keys left out."""

    kept = []
    for part in parts:
        row = {k: str(part.get(k) or "") for k in _PART_KEYS}
        row = {k: v for k, v in row.items() if v or k in ("label", "text", "source")}
        row["source"] = row.get("source") or "typed"
        kept.append(row)
    return {
        "language": language_id,
        "rule": rule_id,
        "shape": int(shape),
        "built_as": {str(k): str(v) for k, v in built_as.items()},
        "parts": kept,
    }


def _stored(view, thing_id: str) -> dict:
    state = view.thing(thing_id)
    stored = state.fields.get("name_parts") if state is not None else None
    if not isinstance(stored, dict):
        raise ValueError("this person's name isn't in parts")
    return stored


def set_part(rev: Revision, world: World, thing_id: str, index: int, text: str) -> None:
    """One part's text, typed by the owner: the name is written again from
    the parts and renamed everywhere."""

    view = world.view()
    stored = _stored(view, thing_id)
    parts = [dict(p) for p in stored["parts"]]
    text = " ".join(text.split())
    if not text:
        raise ValueError("a name part can't be blank")
    if not 0 <= index < len(parts):
        raise ValueError("there's no such name part")
    parts[index] = {"label": parts[index]["label"], "text": text, "source": "typed"}
    language = language_of(view.thing(stored["language"]))
    name = written(
        language, stored["rule"], stored["shape"], [p["text"] for p in parts]
    )
    rename_everywhere(rev, world, thing_id, name)
    rev.set_field(thing_id, "name_parts", {**stored, "parts": parts}, None)


def set_built_as(rev: Revision, world: World, thing_id: str, built_as: dict) -> None:
    """What the person's name is built as, through the language's choices;
    the name itself stays as it is."""

    view = world.view()
    stored = _stored(view, thing_id)
    language = language_of(view.thing(stored["language"]))
    chosen = choose(language, {str(k): str(v) for k, v in built_as.items()})
    rev.set_field(thing_id, "name_parts", {**stored, "built_as": chosen}, None)


def _aka(view, thing_id: str) -> list[dict]:
    state = view.thing(thing_id)
    if state is None:
        raise KeyError(f"no such thing: {thing_id}")
    return [dict(a) for a in state.fields.get("aka") or []]


def _name(name: str) -> str:
    name = " ".join(str(name or "").split())
    if not name:
        raise ValueError("a name can't be blank")
    return name


def add_title(
    rev: Revision,
    world: World,
    thing_id: str,
    name: str,
    *,
    language_id: str | None = None,
    meaning: str | None = None,
    by: str | None = None,
    shown: str | None = None,
) -> None:
    """A title the person holds; a shown one takes the place of the title
    shown before it."""

    name = _name(name)
    aka = [a for a in _aka(world.view(), thing_id) if a["name"].lower() != name.lower()]
    if shown:
        aka = [{k: v for k, v in a.items() if k != "shown"} for a in aka]
    entry: dict = {"name": name, "tag": "proper", "everyday": False, "kind": "title"}
    if language_id:
        entry["language"] = language_id
    if meaning:
        entry["meaning"] = meaning
    if by:
        entry["by"] = by
    if shown:
        entry["shown"] = shown
    rev.set_field(thing_id, "aka", [*aka, entry], None)


def remove_title(rev: Revision, world: World, thing_id: str, name: str) -> None:
    aka = [
        a
        for a in _aka(world.view(), thing_id)
        if not (a.get("kind") == "title" and a["name"].lower() == name.strip().lower())
    ]
    drop_other_names(rev, world, thing_id, aka)


def kept_title_offer(view, thing_id: str, english: str) -> dict:
    """The person's language's own word for an English title, offered:
    `{english, word, language_id}` (`word` None when it keeps none)."""

    state = person_language(view, thing_id)
    found = kept_title(language_of(state), english) if state is not None else None
    return {
        "english": english,
        "word": found.word if found else None,
        "language_id": state.id if state is not None else None,
    }


def set_pet_name(
    rev: Revision,
    world: World,
    thing_id: str,
    mode: str,
    name: str | None = None,
    by: str | None = None,
    rng: random.Random | None = None,
) -> None:
    """ "roll": the person's pet name from their language's rule, in place
    of the last one rolled; "set": `name` as what `by` calls them (or, with
    no `by`, their pet name)."""

    view = world.view()
    aka = _aka(view, thing_id)
    if mode == "roll":
        state = person_language(view, thing_id)
        if state is None:
            raise ValueError("this person has no language to make a pet name in")
        own = _own(view.thing(thing_id).fields.get("name_parts"))
        if not own:
            own = {"given": (view.name_of(thing_id) or "").split()[0]}
        found = roll_pet_name(language_of(state), own, rng or random.Random())
        if found is None:
            raise ValueError("this language has no rule for pet names")
        pet, rule = found
        aka = [a for a in aka if not (a.get("kind") == "pet" and not a.get("by"))]
        entry = {
            "name": pet,
            "tag": "proper",
            "everyday": False,
            "kind": "pet",
            "rule": rule,
        }
    elif mode == "set":
        name = _name(name or "")
        if by:
            aka = [a for a in aka if not (a.get("kind") == "own" and a.get("by") == by)]
            entry = {
                "name": name,
                "tag": "proper",
                "everyday": False,
                "kind": "own",
                "by": by,
            }
        else:
            aka = [a for a in aka if not (a.get("kind") == "pet" and not a.get("by"))]
            entry = {"name": name, "tag": "proper", "everyday": False, "kind": "pet"}
    else:
        raise ValueError(f"unknown pet name mode: {mode!r}")
    aka = [a for a in aka if a["name"].lower() != entry["name"].lower()]
    drop_other_names(rev, world, thing_id, [*aka, entry])


def calls_out(view, state) -> list[dict]:
    """The names others call the person (other names with a kind), each
    with who uses it; one used by an entry the world no longer has is
    left out."""

    out = []
    for entry in state.fields.get("aka") or []:
        kind = entry.get("kind")
        if not kind:
            continue
        by = entry.get("by") or ""
        by_name = ""
        if by:
            if view.thing(by) is None:
                continue
            by_name = view.name_of(by) or ""
        out.append(
            {
                "name": entry["name"],
                "kind": kind,
                "by": by,
                "by_name": by_name,
                "rule": entry.get("rule") or "",
                "meaning": entry.get("meaning") or "",
            }
        )
    return out
