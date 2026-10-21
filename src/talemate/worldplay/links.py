"""Linking names in text, and making stubs for the names it invents.

`link_text` turns the names `world.names.find_names` finds in a piece of
text into references that keep the words written: "Moscavia's border"
becomes `[[thing:<id>|Moscavia]]'s border`, which renders back to the
same words; a possessive stays outside the reference, so a full name with
one still follows a rename. The owner's picks and the stubs just made (`new_names`) link too,
and win over the automatic match. A suggested (partial) match is left as
plain text unless picked, and text already inside a reference is never
touched.

`link_text` given an `owner` (the thing whose facts the text is) leaves
that thing's own names plain: a thing never links to itself.

`make_stubs` makes one stub per new name a generation lists, unless the
world (or the same call) already has that name: one name invented twice
is one stub with two mentions. `existing_id` is the same reuse rule on its
own, and `clean_aka` the tidying a list of other names gets.
"""

from __future__ import annotations

import re
from collections.abc import Set as AbstractSet
from typing import NamedTuple

import structlog
from pydantic import BaseModel

from talemate.world.kinds import AKA_TAGS, HERITAGE_KINDS, KINDS
from talemate.world.names import ARTICLES, find_names
from talemate.world.refs import REF_PATTERN, ref
from talemate.world.store import Revision
from talemate.world.view import WorldView

log = structlog.get_logger("talemate.worldplay.links")

__all__ = [
    "NewName",
    "clean_aka",
    "existing_id",
    "link_text",
    "make_stubs",
    "name_key",
    "name_keys",
]

# the kind a new name gets when the model gave none we know
FALLBACK_KIND = "lore"


class NewName(BaseModel):
    """A proper name a generation used that may not exist yet: its name in
    full, its kind, and any other names (`aka` entries) for it. `written`
    holds the other ways the text writes it that aren't other names: the
    name without its article ("Night of Feathers" for "The Night of
    Feathers"), or the part of it the text uses ("Vladislav I" for "Tsar
    Vladislav I")."""

    name: str
    kind: str
    aka: list[dict] = []
    written: list[str] = []


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def name_key(name: str) -> str:
    """A name as compared for reuse: normalised, without a leading article
    ("The Hollow" is "hollow")."""

    words = _norm(name).split()
    if len(words) > 1 and words[0] in ARTICLES:
        words = words[1:]
    return " ".join(words)


def _capitalised(written: str) -> bool:
    words = written.split()
    if len(words) > 1 and words[0].casefold() in ARTICLES:
        words = words[1:]
    return bool(words) and words[0][:1].isupper()


# ---------------------------------------------------------------------------
# link_text


# (start, end, thing id): a name's span, without any `'s`
_Span = tuple[int, int, str]


def _explicit_spans(text: str, chosen: dict[str, str]) -> list[_Span]:
    """Every whole-word occurrence of a picked or new name (normalised key
    to thing id) in `text`. A name written with a capital matches only text
    written with one, so a stub "Hope" never links "I hope"."""

    spans: list[_Span] = []
    for key, thing_id in chosen.items():
        words = key.split()
        if not words:
            continue
        pattern = re.compile(
            r"(?<!\w)" + r"\s+".join(map(re.escape, words)) + r"(?!\w)",
            re.IGNORECASE,
        )
        for hit in pattern.finditer(text):
            if _norm(hit.group(0)) != key or not _capitalised(hit.group(0)):
                continue
            spans.append((hit.start(), hit.end(), thing_id))
    return spans


def _link_plain(
    view: WorldView, text: str, chosen: dict[str, str], owner: str | None
) -> str:
    """Link the names in `text`, which holds no references. A name that
    means `owner` stays plain."""

    matched: list[_Span] = []
    for match in find_names(view, text):
        thing_id = chosen.get(_norm(match.text))
        if thing_id is None and not match.suggested:
            thing_id = match.candidates[0].id
        if thing_id == owner:
            thing_id = None
        # a suggestion left alone, or the owner's own name, still holds its
        # words
        matched.append((match.start, match.end, thing_id or ""))

    # a picked or new name inside a longer name ("Maren" in "Maren Vos")
    # leaves that name to its own match
    explicit = [
        span
        for span in _explicit_spans(text, chosen)
        if not any(
            m_start <= span[0]
            and span[1] <= m_end
            and (m_start, m_end) != (span[0], span[1])
            for m_start, m_end, _id in matched
        )
    ]

    # earliest first, then longest, an explicit name before a match
    spans = sorted(
        [(s, e, i, 0) for s, e, i in explicit] + [(s, e, i, 1) for s, e, i in matched],
        key=lambda span: (span[0], -span[1], span[3]),
    )
    out: list[str] = []
    taken = 0
    for start, end, thing_id, _priority in spans:
        if start < taken:
            continue
        out.append(text[taken:start])
        out.append(ref(thing_id, text[start:end]) if thing_id else text[start:end])
        taken = end
    out.append(text[taken:])
    return "".join(out)


def link_text(
    view: WorldView,
    text: str,
    *,
    picks: dict[str, str] | None = None,
    new_names: dict[str, str] | None = None,
    owner: str | None = None,
) -> str:
    """`text` with every name in it linked to its thing, keeping the words
    written as the reference's shown text (a trailing `'s` stays outside
    it).

    - `picks` maps a written name to the thing the owner picked for it; it
      wins over the automatic match, and links a suggested match too;
    - `new_names` maps a written name to a stub (`make_stubs`), for names
      `view` doesn't know yet;
    - any other match links to its best candidate, except a suggested
      (partial) one, which stays plain text;
    - with `owner`, the thing the text is a fact of, a name that would link
      to it (its name, other names, or a pick or new name for it) stays
      plain text: a thing never links to itself.

    Text inside an existing reference isn't touched, so linking twice
    changes nothing."""

    chosen = {_norm(name): thing_id for name, thing_id in (new_names or {}).items()}
    chosen.update({_norm(name): thing_id for name, thing_id in (picks or {}).items()})
    chosen.pop("", None)
    if owner is not None:
        chosen = {
            key: thing_id for key, thing_id in chosen.items() if thing_id != owner
        }

    out: list[str] = []
    end = 0
    for existing in REF_PATTERN.finditer(text):
        out.append(_link_plain(view, text[end : existing.start()], chosen, owner))
        out.append(existing.group(0))
        end = existing.end()
    out.append(_link_plain(view, text[end:], chosen, owner))
    return "".join(out)


# ---------------------------------------------------------------------------
# make_stubs


class _Known(NamedTuple):
    """A thing new names may reuse: its id, kind and every name key."""

    id: str
    kind: str
    keys: list[str]


def _known_things(view: WorldView) -> list[_Known]:
    known = []
    for state in view.things():
        keys = [name_key(view.name_of(state.id) or "")]
        aka = state.fields.get("aka")
        for entry in aka if isinstance(aka, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                keys.append(name_key(entry["name"]))
        known.append(_Known(id=state.id, kind=state.kind, keys=[k for k in keys if k]))
    return known


def _contains(key: str, part: str) -> bool:
    """Whether `part` is a whole-word run of `key` (hyphens count as part
    of a word: "Owl-folkish" doesn't contain "Owl-folk")."""

    return re.search(r"(?<![\w-])" + re.escape(part) + r"(?![\w-])", key) is not None


def _reuse(known: list[_Known], key: str, kind: str) -> str | None:
    """The thing a new name means already, if any: one with that name or
    other name (whatever its kind: the world's kind wins), else the one
    whose longest name the new name contains, when both are a species,
    race or mix ("Moscavian Owl-folk" is the Owl-folk). Other kinds reuse
    only an exact name: "Lake Solnech" isn't the town called "Solnech"."""

    for thing in known:
        if key in thing.keys:
            return thing.id
    best: tuple[int, str] | None = None
    for thing in known:
        if kind not in HERITAGE_KINDS or thing.kind not in HERITAGE_KINDS:
            continue
        for part in thing.keys:
            if _contains(key, part) and (best is None or len(part) > best[0]):
                best = (len(part), thing.id)
    return best[1] if best else None


def existing_id(view: WorldView, name: str, kind: str) -> str | None:
    """The thing `name` (of `kind`) already means in `view`, by the rule
    `make_stubs` reuses things by: a main or other name, ignoring case and
    a leading article, whatever its kind; or, for a species, race or mix,
    the species, race or mix whose name it contains. `None` when it's
    new."""

    key = name_key(" ".join(name.split()))
    return _reuse(_known_things(view), key, _norm(kind)) if key else None


def name_keys(view: WorldView, skip: str | None = None) -> set[str]:
    """Every main and other name in `view`, as compared for reuse, leaving
    out the thing `skip`'s own."""

    return {
        key for thing in _known_things(view) if thing.id != skip for key in thing.keys
    }


def clean_aka(
    entries: list[dict], own_name: str, taken: AbstractSet[str] = frozenset()
) -> list[dict[str, object]]:
    """`entries` in the shape `aka` holds: an unknown tag becomes proper,
    only the first everyday common name stays everyday, and a name that is
    the thing's own (`own_name`), a repeat, or one of the name keys in
    `taken` (`name_keys`: other things' names) is dropped."""

    cleaned: list[dict[str, object]] = []
    seen = {name_key(own_name)}
    everyday = False
    for entry in entries:
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        name = " ".join(name.split())
        key = name_key(name)
        if key in seen or key in taken:
            continue
        seen.add(key)
        tag = entry.get("tag")
        tag = tag if tag in AKA_TAGS else "proper"
        is_everyday = entry.get("everyday") is True and tag == "common" and not everyday
        everyday = everyday or is_everyday
        cleaned.append({"name": name, "tag": tag, "everyday": is_everyday})
    return cleaned


def make_stubs(rev: Revision, view: WorldView, names: list[NewName]) -> dict[str, str]:
    """Make a stub for each of `names` the world doesn't have yet, in `rev`,
    and return each written name (whitespace tidied), each of its other
    names and each of its `written` forms, mapped to its thing's id.

    A name that `view` (or an earlier name in `names`) already has, as a
    main or other name and ignoring case and a leading article, reuses that
    entry or stub, as does a species, race or mix name containing the name
    of another species, race or mix. Any
    other name becomes a thing of its kind (`lore` for a kind we don't
    know) with its name, other names and `stub={"ignored": False}`."""

    known = _known_things(view)
    made: dict[str, str] = {}
    for new in names:
        written = " ".join(new.name.split())
        key = name_key(written)
        if not key:
            continue
        kind = _norm(new.kind)
        if kind not in KINDS:
            kind = FALLBACK_KIND

        forms = [" ".join(form.split()) for form in new.written]
        thing_id = _reuse(known, key, kind)
        if thing_id is not None:
            for form in (written, *forms):
                made.setdefault(form, thing_id)
            continue

        taken = {k for thing in known for k in thing.keys}
        aka = clean_aka(new.aka, written, taken)
        thing_id = rev.create_thing(
            kind, fields={"name": written, "aka": aka, "stub": {"ignored": False}}
        )
        others = [str(entry["name"]) for entry in aka]
        known.append(_Known(id=thing_id, kind=kind, keys=[key, *map(name_key, others)]))
        for name in (written, *others, *forms):
            made.setdefault(name, thing_id)
        log.debug("make_stubs.created", name=written, kind=kind, id=thing_id)
    return made
