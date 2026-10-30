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
that thing's own names plain: a thing never links to itself. Names the
owner treats as new (`as_new`, `is_new`) never link to what the world
already has, and `make_stubs` never reuses an existing thing for one.

`link_text` given `spans` (a fact form's existing links, by position)
deals with them first: each links its words to its own thing, or keeps
them plain, whatever the names in them would match. Edits that must change
nothing but what they name don't run `link_text`: `link_phrase` links one
plain phrase (a stub just made of it), and `repoint_ref` points one
reference at another thing, keeping its words.

`make_stubs` makes one stub per new name a generation lists, unless the
world (or the same call) already has that name: one name invented twice
is one stub with two mentions. `existing_id` is the same reuse rule on its
own, and `clean_aka` the tidying a list of other names gets.

A new name may carry `same_as`, the things the world already has it could
be (`SameOffer`, curation's "same as X?"), and the owner's answer,
`same_target_id`: the name is then that thing's, and no stub is made for
it (`create.accept_preview`).
"""

from __future__ import annotations

import re
from collections.abc import Collection
from collections.abc import Set as AbstractSet
from typing import NamedTuple

import structlog
from pydantic import BaseModel

from talemate.world.kinds import AKA_TAGS, HERITAGE_KINDS, KINDS
from talemate.world.names import ARTICLES, Aliases, find_names
from talemate.world.refs import REF_PATTERN, ref
from talemate.world.sameness import SameCandidate
from talemate.world.store import Revision
from talemate.world.view import WorldView

log = structlog.get_logger("talemate.worldplay.links")

__all__ = [
    "LinkSpan",
    "NewName",
    "SameOffer",
    "clean_aka",
    "existing_id",
    "is_new",
    "link_phrase",
    "link_text",
    "make_stubs",
    "name_key",
    "name_keys",
    "repoint_ref",
]

# the kind a new name gets when the model gave none we know
FALLBACK_KIND = "lore"


class SameOffer(SameCandidate):
    """A thing a new name could be the same as (`world.sameness`), as the
    preview shows it: its name and kind, its line in the "Entries near this
    one" list (`create.filing_line`: kind and tag, other name, where it's filed, stub, its
    summary or first fact), so two of one name can be told apart, whether
    it has facts of its own (only then is a verdict asked), and whether
    it's a stub."""

    name: str
    kind: str
    line: str
    has_facts: bool
    stub: bool = False


class NameFiling(BaseModel):
    """Where a new name's stub is filed on accept (its reply's `"in"`): an
    entry the world has (`target_id`), the entry being written
    (`this_entry`, resolved to its id on accept, whatever the owner
    renamed it to), or, by `name`, another new name of the same accept.
    Ticked: it's written when the name itself becomes a stub (ruling
    F12)."""

    target_id: str | None = None
    this_entry: bool = False
    name: str | None = None
    role: str | None = None
    ticked: bool = True


class NewName(BaseModel):
    """A proper name a generation used that may not exist yet: its name in
    full, its kind, and any other names (`aka` entries) for it. `written`
    holds the other ways the text writes it that aren't other names: the
    name without its article ("Night of Feathers" for "The Night of
    Feathers"), or the part of it the text uses ("Vladislav I" for "Tsar
    Vladislav I").

    `tag` is the stub's tag (what it is: "fortification"), and `filing`
    the one filing its stub is given (`NameFiling`), when ticked."""

    name: str
    kind: str
    aka: list[dict] = []
    written: list[str] = []
    # the things it could be the same as, best first; and the owner's
    # answer: None (the default) is "new", a stub on accept
    same_as: list[SameOffer] = []
    same_target_id: str | None = None
    tag: str | None = None
    filing: NameFiling | None = None
    # the name cleaning replaced with this one ("Novgorod"), shown as
    # "replaced Novgorod"; and whether cleaning made this stub itself (a
    # name the reply didn't list), so undoing the cleaning drops it
    replaced: str = ""
    from_cleaning: bool = False


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def name_key(name: str) -> str:
    """A name as compared for reuse: normalised, without a leading article
    ("The Hollow" is "hollow")."""

    words = _norm(name).split()
    if len(words) > 1 and words[0] in ARTICLES:
        words = words[1:]
    return " ".join(words)


def is_new(name: str, as_new: Collection[str]) -> bool:
    """Whether `name` is one the owner treats as new: one of `as_new`, or
    a longer name starting with one ("Maren Vos" when "Maren" is new), as
    scene setup reads its own "treat as new" names. Compared as
    `name_key`s."""

    key = name_key(name)
    if not key:
        return False
    for new in as_new:
        new_key = name_key(new)
        if new_key and (key == new_key or key.startswith(new_key + " ")):
            return True
    return False


def _capitalised(written: str) -> bool:
    words = written.split()
    if len(words) > 1 and words[0].casefold() in ARTICLES:
        words = words[1:]
    return bool(words) and words[0][:1].isupper()


# ---------------------------------------------------------------------------
# link_text


# (start, end, thing id): a name's span, without any `'s`
_Span = tuple[int, int, str]


def _explicit_spans(
    text: str, chosen: dict[str, str], lowercase: Collection[str] = ()
) -> list[_Span]:
    """Every whole-word occurrence of a picked or new name (normalised key
    to thing id) in `text`, a hyphenated word counting as one. A name
    written with a capital matches only text written with one, so a stub
    "Hope" never links "I hope"; one the owner selected on a draft
    (`lowercase`, normalised keys: "the north pass") matches as written."""

    spans: list[_Span] = []
    for key, thing_id in chosen.items():
        words = key.split()
        if not words:
            continue
        # a hyphen joins a word: "Owl" isn't in "Owl-folk"
        pattern = re.compile(
            r"(?<![\w-])" + r"\s+".join(map(re.escape, words)) + r"(?![\w-])",
            re.IGNORECASE,
        )
        for hit in pattern.finditer(text):
            if _norm(hit.group(0)) != key:
                continue
            if key not in lowercase and not _capitalised(hit.group(0)):
                continue
            spans.append((hit.start(), hit.end(), thing_id))
    return spans


def _link_plain(
    view: WorldView,
    text: str,
    chosen: dict[str, str],
    owner: str | None,
    as_new: Collection[str],
    lowercase: Collection[str] = (),
    aliases: Aliases | None = None,
    made: AbstractSet[str] = frozenset(),
) -> str:
    """Link the names in `text`, which holds no references. A name that
    means `owner` stays plain, and so does a match for a name treated as
    new (`as_new`) unless it's chosen. `lowercase`: the chosen names
    written without a capital (`_explicit_spans`); `aliases`, the view's
    `alias_table` when the caller built it. `made`: the ids of the new
    names' stubs, which a match written without a capital (a stub stored
    lowercase-led, "al-Qadir", found as written) never links: a new name
    links lowercase only as the owner selected it (ruling F26)."""

    matched: list[_Span] = []
    for match in find_names(view, text, aliases=aliases):
        thing_id = chosen.get(_norm(match.text))
        if thing_id is None and not match.suggested and not is_new(match.text, as_new):
            thing_id = match.candidates[0].id
        if (
            thing_id in made
            and _norm(match.text) not in lowercase
            and not _capitalised(match.text)
        ):
            thing_id = None
        if thing_id == owner:
            thing_id = None
        # a suggestion left alone, or the owner's own name, still holds its
        # words
        matched.append((match.start, match.end, thing_id or ""))

    # a picked or new name inside a longer name ("Maren" in "Maren Vos")
    # leaves that name to its own match
    explicit = [
        span
        for span in _explicit_spans(text, chosen, lowercase)
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


class LinkSpan(BaseModel):
    """A span of `link_text`'s text (code-point offsets) whose words link
    to `ref`, or stay plain with no `ref`."""

    start: int
    end: int
    ref: str | None = None


def _checked_spans(
    text: str, spans: Collection[LinkSpan]
) -> list[tuple[int, int, str | None]]:
    """`spans` in order as `(start, end, ref)`, refusing an empty,
    out-of-range or overlapping one, or one touching a reference."""

    taken = [(m.start(), m.end()) for m in REF_PATTERN.finditer(text)]
    checked: list[tuple[int, int, str | None]] = []
    end = 0
    for span in sorted(spans, key=lambda span: span.start):
        if not 0 <= span.start < span.end <= len(text) or span.start < end:
            raise ValueError(f"a link can't span {span.start}-{span.end}")
        if any(span.start < t_end and t_start < span.end for t_start, t_end in taken):
            raise ValueError("a link can't overlap a reference")
        checked.append((span.start, span.end, span.ref))
        end = span.end
    return checked


def link_text(
    view: WorldView,
    text: str,
    *,
    picks: dict[str, str] | None = None,
    new_names: dict[str, str] | None = None,
    owner: str | None = None,
    as_new: Collection[str] = (),
    spans: Collection[LinkSpan] = (),
    lowercase: Collection[str] = (),
    aliases: Aliases | None = None,
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
      plain text: a thing never links to itself;
    - a name the owner treats as new (`as_new`, by `is_new`) never links
      to the thing the world already has by that name: only a pick or a
      new name for it links it.
    - a pick or new name links only where the text writes it with a
      capital, unless it's one the owner selected on a draft
      (`lowercase`, the draft's `selected_names`, ruling F26): those link
      as written.

    - `spans` (code-point offsets into `text`) come first: each links its
      words to its `ref`, or keeps them plain when it has none, and
      nothing else touches them. An empty, out-of-range or overlapping
      span, or one crossing a reference, raises `ValueError`.

    Text inside an existing reference isn't touched, so linking twice
    changes nothing. `aliases` is `names.alias_table(view)`, for a caller
    linking many texts against one view: building it loads the whole
    world (I1)."""

    if spans:
        out: list[str] = []
        end = 0
        for start, stop, thing_id in _checked_spans(text, spans):
            out.append(
                link_text(
                    view,
                    text[end:start],
                    picks=picks,
                    new_names=new_names,
                    owner=owner,
                    as_new=as_new,
                    lowercase=lowercase,
                    aliases=aliases,
                )
            )
            words = text[start:stop]
            out.append(ref(thing_id, words) if thing_id else words)
            end = stop
        out.append(
            link_text(
                view,
                text[end:],
                picks=picks,
                new_names=new_names,
                owner=owner,
                as_new=as_new,
                lowercase=lowercase,
                aliases=aliases,
            )
        )
        return "".join(out)

    chosen = {_norm(name): thing_id for name, thing_id in (new_names or {}).items()}
    chosen.update({_norm(name): thing_id for name, thing_id in (picks or {}).items()})
    chosen.pop("", None)
    # the owner's own selections link as written, capital or not
    allowed = {_norm(name) for name in lowercase}
    made = frozenset((new_names or {}).values())
    if owner is not None:
        chosen = {
            key: thing_id for key, thing_id in chosen.items() if thing_id != owner
        }

    out: list[str] = []
    end = 0
    for existing in REF_PATTERN.finditer(text):
        out.append(
            _link_plain(
                view,
                text[end : existing.start()],
                chosen,
                owner,
                as_new,
                allowed,
                aliases,
                made,
            )
        )
        out.append(existing.group(0))
        end = existing.end()
    out.append(
        _link_plain(view, text[end:], chosen, owner, as_new, allowed, aliases, made)
    )
    return "".join(out)


# ---------------------------------------------------------------------------
# targeted links


def link_phrase(text: str, phrase: str, thing_id: str) -> str:
    """`text` with the first whole-word occurrence of `phrase` outside any
    reference made a reference to `thing_id`, keeping its words; nothing
    else changes. Raises `ValueError` if there's none."""

    pattern = re.compile(
        r"(?<!\w)" + r"\s+".join(map(re.escape, phrase.split())) + r"(?!\w)"
    )
    plain_from = 0
    for found in [*REF_PATTERN.finditer(text), None]:
        plain_to = found.start() if found is not None else len(text)
        hit = pattern.search(text, plain_from, plain_to)
        if hit is not None:
            return text[: hit.start()] + ref(thing_id, hit.group(0)) + text[hit.end() :]
        if found is not None:
            plain_from = found.end()
    raise ValueError(f"the text doesn't name {phrase!r} to link")


def repoint_ref(text: str, occurrence: int, to_id: str, rendered: str) -> str:
    """`text` with its `occurrence`-th reference (0-based, in order)
    pointing at `to_id`, keeping its shown words (`rendered`, the words a
    reference without any rendered as). Raises `ValueError` if there's no
    such reference."""

    for index, found in enumerate(REF_PATTERN.finditer(text)):
        if index == occurrence:
            shown = found.group(2) or rendered
            return text[: found.start()] + ref(to_id, shown) + text[found.end() :]
    raise ValueError(f"no reference {occurrence} to re-point")


# ---------------------------------------------------------------------------
# make_stubs


class _Known(NamedTuple):
    """A thing new names may reuse: its id, kind and every name key."""

    id: str
    kind: str
    keys: list[str]


def _known_things(view: WorldView) -> list[_Known]:
    known = []
    # names only: no facts loaded
    for state in view.things(facts=False):
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


def _reuse(
    known: list[_Known], key: str, kind: str, *, held: bool = False
) -> str | None:
    """The thing a new name means already, if any: one with that name or
    other name (whatever its kind: the world's kind wins), else the one
    whose longest name the new name contains, when both are a species,
    race or mix ("Moscavian Owl-folk" is the Owl-folk). With `held`, a
    species, race or mix name held whole by just one other's name is that
    one too ("Owl-folk" is the Owl-folk of Moscavia). Other kinds reuse
    only an exact name: "Lake Solnech" isn't the town called "Solnech"."""

    for thing in known:
        if key in thing.keys:
            return thing.id
    if kind not in HERITAGE_KINDS:
        return None
    heritages = [thing for thing in known if thing.kind in HERITAGE_KINDS]
    best: tuple[int, str] | None = None
    for thing in heritages:
        for part in thing.keys:
            if _contains(key, part) and (best is None or len(part) > best[0]):
                best = (len(part), thing.id)
    if best is not None:
        return best[1]
    if held:
        holders = {
            thing.id
            for thing in heritages
            if any(_contains(part, key) for part in thing.keys)
        }
        if len(holders) == 1:
            return holders.pop()
    return None


def existing_id(
    view: WorldView, name: str, kind: str, *, held: bool = False
) -> str | None:
    """The thing `name` (of `kind`) already means in `view`, by the rule
    `make_stubs` reuses things by: a main or other name, ignoring case and
    a leading article, whatever its kind; or, for a species, race or mix,
    the species, race or mix whose name it contains -- or, with `held`,
    the only one whose name holds it. `None` when it's new."""

    key = name_key(" ".join(name.split()))
    if not key:
        return None
    return _reuse(_known_things(view), key, _norm(kind), held=held)


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
        clean: dict[str, object] = {"name": name, "tag": tag, "everyday": is_everyday}
        language = entry.get("language")
        if isinstance(language, str) and re.fullmatch(r"[0-9a-f]{32}", language):
            # a name given in one of the world's languages (languages 3a)
            clean["language"] = language
        cleaned.append(clean)
    return cleaned


def make_stubs(
    rev: Revision,
    view: WorldView,
    names: list[NewName],
    *,
    fresh: Collection[str] = (),
) -> dict[str, str]:
    """Make a stub for each of `names` the world doesn't have yet, in `rev`,
    and return each written name (whitespace tidied), each of its other
    names and each of its `written` forms, mapped to its thing's id.

    A name that `view` (or an earlier name in `names`) already has, as a
    main or other name and ignoring case and a leading article, reuses that
    entry or stub, as does a species, race or mix name containing the name
    of another species, race or mix, or held whole by just one's name
    ("Owl-folk" for the Owl-folk of Moscavia). Any other name becomes a
    thing of its kind (`lore` for a kind we don't know) with its name,
    other names, its tag and `stub={"ignored": False}`; a lowercase
    leading "the" isn't part of a new stub's name
    ("the Kremlin" makes "Kremlin"), though it still maps as written.

    A name the owner treats as new (`fresh`, by `is_new`) never reuses a
    thing `view` has, only one an earlier name in `names` made."""

    known = _known_things(view)
    # the things this call makes, the only ones a fresh name may reuse
    made_here: list[_Known] = []
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
        pool = made_here if is_new(written, fresh) else known
        thing_id = _reuse(pool, key, kind, held=True)
        if thing_id is not None:
            for form in (written, *forms):
                made.setdefault(form, thing_id)
            continue

        words = written.split()
        name = " ".join(words[1:]) if len(words) > 1 and words[0] == "the" else written
        taken = {k for thing in known for k in thing.keys}
        aka = clean_aka(new.aka, name, taken)
        fields: dict[str, object] = {
            "name": name,
            "aka": aka,
            "stub": {"ignored": False},
        }
        if new.tag:
            fields["tag"] = new.tag
        thing_id = rev.create_thing(kind, fields=fields)
        others = [str(entry["name"]) for entry in aka]
        thing = _Known(id=thing_id, kind=kind, keys=[key, *map(name_key, others)])
        known.append(thing)
        made_here.append(thing)
        for mapped in (written, name, *others, *forms):
            made.setdefault(mapped, thing_id)
        log.debug("make_stubs.created", name=written, kind=kind, id=thing_id)
    return made
