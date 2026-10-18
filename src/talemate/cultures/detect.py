"""Post-snapshot detection for the Culture agent: new place names, new
glossary names, and parsing the place and additions replies.

Pure functions: plain data in, plain data out. The Culture agent
(`talemate.agents.culture.snapshot`) is the only caller that talks to a
model or writes world files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

from talemate.cultures.generator import name_fits
from talemate.cultures.models import (
    Culture,
    CultureShare,
    GlossaryEntry,
    GlossaryOrigin,
    Place,
    PlayAddition,
    new_id,
)
from talemate.cultures.naming import guess_culture_for_name
from talemate.cultures.places import effective_mix, set_shares
from talemate.cultures.scene_context import SceneCultures
from talemate.cultures.words import (
    _CONNECTORS,
    _LEADING_STOP_WORDS,
    _is_common_word,
    _strip_possessive,
    all_common_words,
    clean_name,
    first_mention,
    is_insult_phrase,
    is_proper_item_name,
    looks_like_name,
)

if TYPE_CHECKING:
    from talemate.character import Character

__all__ = [
    "NameFinding",
    "name_key",
    "location_place_name",
    "new_place_names",
    "find_new_names",
    "parse_places_reply",
    "parse_additions_reply",
]

PLACE_KINDS: tuple[str, ...] = get_args(Place.model_fields["kind"].annotation)

ADDITION_SECTIONS = ("customs", "food", "holidays")

# Characters that end a run of capitalised words in a location text.
_RUN_BREAK = re.compile(r"[,;:.!?()\[\]\"“”/]+")

# Prepositions capitalised only because they open the location text
# ("At Kesterholm"); dropped from the start of a run.
_LEADING_PREPOSITIONS = {
    "at", "in", "on", "near", "by", "inside", "outside", "under", "beside",
    "behind", "beyond", "from", "to", "into", "within", "around", "along",
    "across", "over", "above", "below", "off",
}  # fmt: skip

# Titles and forms of address that lead a person's name ("Old Hessa",
# "Captain Varn"); dropped before a place candidate is compared with the
# people the scene knows.
_PERSON_TITLES = {
    "old", "young", "little", "captain", "mother", "father", "master",
    "mistress", "lord", "lady", "sir", "dame", "madam", "mister", "brother",
    "sister", "aunt", "uncle", "granny", "gran", "grandfather", "grandmother",
    "elder", "widow", "goodwife", "goodman", "auntie", "cousin",
}  # fmt: skip

# A place candidate opening with one of these is a description of where
# something is ("Behind The Net-Racks"), not a place's name.
_DESCRIPTIVE_OPENERS = {
    "behind", "in", "at", "on", "near", "under", "beside", "by", "outside",
    "inside",
}  # fmt: skip

# Joins a generic head to a place in a descriptive phrase ("Fish Market In
# Ilsara", "The Docks Of The Dhunmouth").
_PLACE_JOINER = re.compile(r"\s+(?:in|at|of\s+the)\s+", re.IGNORECASE)

# Generic building words a place name may carry or drop ("Quillister
# House", "The Quillister", "The Quillister Inn" are one place).
_GENERIC_PLACE_WORDS = {"inn", "house", "tavern", "hall"}

# The second field of an infer-places line that means "not a place".
_SKIP_ANSWERS = {"skip", "skipped", "not a place"}


@dataclass
class NameFinding:
    text: str
    kind: Literal["person", "place", "thing"]
    culture_id: str | None
    doesnt_fit: bool
    first_used: str
    character_name: str | None
    place_id: str | None
    origin: GlossaryOrigin


def _strip_markup(text: str) -> str:
    """Drop markdown emphasis (`**Name**`, `_Name_`) from a reply field."""
    return text.replace("*", "").strip().strip("_").strip()


def _field(text: str) -> str:
    """A short reply field: markup and trailing punctuation removed."""
    return _strip_markup(text).rstrip(".,;:!?").strip()


def name_key(text: str) -> str:
    """Case-insensitive match key for a name: cleaned, without markup and
    without a leading "the" ("The Dhaer's Rest" and "Dhaer's Rest" match)."""

    key = clean_name(_strip_markup(text)).lower()
    if key.startswith("the "):
        key = key[4:].strip()
    return key


def _with_article(text: str, check) -> str | None:
    """`text`, cleaned, when `check` accepts it; or, for a leading "the"
    followed by a remainder `check` accepts, `"The " + remainder` (inns,
    ships and taverns are named like this). `None` otherwise."""

    cleaned = clean_name(text)
    if check(cleaned):
        return cleaned
    words = cleaned.split()
    if len(words) > 1 and words[0].lower() == "the":
        rest = " ".join(words[1:])
        if check(rest):
            return f"The {rest}"
    return None


def _capitalised_runs(text: str) -> list[str]:
    """Runs of capitalised words in `text`, with lowercase connectors
    allowed inside a run (never at its ends)."""

    runs: list[str] = []
    for segment in _RUN_BREAK.split(text):
        current: list[str] = []
        for word in segment.split():
            if word[:1].isupper():
                current.append(word)
            elif current and word.lower() in _CONNECTORS:
                current.append(word)
            else:
                if current:
                    runs.append(current)
                current = []
        if current:
            runs.append(current)

    result = []
    for words in runs:
        while words and words[0].lower() in _LEADING_PREPOSITIONS:
            words = words[1:]
        while (
            words and words[-1].lower() in _CONNECTORS and not words[-1][:1].isupper()
        ):
            words = words[:-1]
        if words:
            result.append(" ".join(words))
    return result


def location_place_name(location: str | None) -> str | None:
    """The first place-like name in a location text, or `None`."""

    for run in _capitalised_runs(location or ""):
        name = _with_article(run, looks_like_name)
        if name:
            return name
    return None


def _name_words(text: str) -> tuple[str, ...]:
    """`name_key(text)`'s words, each without a possessive."""
    return tuple(_strip_possessive(word) for word in name_key(text).split())


def _without_titles(words: tuple[str, ...]) -> tuple[str, ...]:
    """`words` without leading titles ("old", "captain"), never emptied."""
    while len(words) > 1 and words[0] in _PERSON_TITLES:
        words = words[1:]
    return words


def _names_a_person(name: str, people: set[tuple[str, ...]]) -> bool:
    """Whether a place candidate is really one of `people` (title-stripped
    word tuples): "Old Hessa" for Hessa, "Captain Varn" for Varn, or any
    candidate ending with a known person's name."""

    words = _name_words(name)
    if _without_titles(words) in people:
        return True
    return any(
        len(words) >= len(person) and words[-len(person) :] == person
        for person in people
    )


def new_place_names(
    location: str | None,
    snapshot_places: list[str],
    places: list[Place],
    character_names: list[str],
    person_names: list[str] = (),
) -> list[str]:
    """Place names in the snapshot that the world doesn't know yet.

    `character_names` are never places (exact match). `person_names` (the
    scene's characters and the glossary's persons) also rule out a
    candidate that, without leading titles and a possessive, is one of
    them, or that ends with one of their names: "Old Hessa's stall" is
    Hessa's, not a place called "Old Hessa".
    """

    candidates: list[str | None] = []
    if location:
        candidates.extend(
            _with_article(run, looks_like_name) for run in _capitalised_runs(location)
        )
    candidates.extend(_with_article(key, looks_like_name) for key in snapshot_places)

    place_keys = {name_key(place.name) for place in places}
    place_keys |= {_without_generic(key) for key in place_keys}
    known = set(place_keys)
    known |= {name_key(name) for name in character_names}
    people = {_without_titles(_name_words(name)) for name in person_names}
    people.discard(())

    result: list[str] = []
    for name in candidates:
        if not name:
            continue
        key = name_key(name)
        if (
            not key
            or key in known
            or _without_generic(key) in place_keys
            or _names_a_person(name, people)
            or _is_descriptive_place(name, place_keys)
        ):
            continue
        known.add(key)
        result.append(name)
    return result


def _without_generic(key: str) -> str:
    """A place key without a trailing generic building word ("quillister
    inn" -> "quillister"); unchanged when nothing would be left."""

    words = key.split()
    if len(words) > 1 and words[-1] in _GENERIC_PLACE_WORDS:
        return " ".join(words[:-1])
    return key


def _is_descriptive_place(name: str, place_keys: set[str]) -> bool:
    """Whether a place candidate describes a spot rather than naming a
    place: it opens with a preposition ("Behind The Net-Racks"), or joins
    a head of common words to a known place ("Fish Market In Ilsara")."""

    words = name.split()
    if words and words[0].lower() in _DESCRIPTIVE_OPENERS:
        return True
    parts = _PLACE_JOINER.split(name, maxsplit=1)
    if len(parts) != 2:
        return False
    head, tail = parts
    head_words = [word for word in head.split() if word.lower() != "the"]
    if not head_words or not all(_is_common_word(word) for word in head_words):
        return False
    tail_key = name_key(tail)
    return tail_key in place_keys or _without_generic(tail_key) in place_keys


def _capitalised_name(text: str) -> bool:
    """Every word capitalised (connectors aside) and no leading article:
    a proper-name shape, without `looks_like_name`'s common-word check."""

    words = text.split()
    if not words or words[0].lower() in _LEADING_STOP_WORDS:
        return False
    return all(
        word[:1].isupper() or (index > 0 and word.lower() in _CONNECTORS)
        for index, word in enumerate(words)
    )


def _dominant(mix: list[CultureShare], cultures: dict[str, Culture]) -> str | None:
    known = [share for share in mix if share.culture_id in cultures]
    if not known:
        return None
    return max(known, key=lambda share: share.share).culture_id


def find_new_names(
    *,
    characters: list[str],
    items: list[str],
    places_found: list[tuple[str, str]],
    glossary: list[GlossaryEntry],
    cultures: dict[str, Culture],
    scene: SceneCultures,
    scene_characters: dict[str, "Character"],
    messages: list,
    offered_spares: dict[str, dict],
    story: str,
    places: list[Place] | None = None,
) -> list[NameFinding]:
    """Names in a snapshot that the glossary doesn't have yet.

    `places_found` holds `(name, place_id)` for this run's new places and
    the matched current place; `places` (the world's places, including
    new ones) gives each its effective culture, falling back to the
    scene's mix.
    """

    known = {name_key(entry.text) for entry in glossary}
    place_keys = {name_key(place.name) for place in places or []}
    place_keys |= {name_key(name) for name, _ in places_found}
    texts = [str(getattr(message, "message", "") or "") for message in messages]
    findings: list[NameFinding] = []

    def first_used(text: str) -> str:
        mention = first_mention(text, messages)
        return f"{story}, message {mention.id}" if mention is not None else story

    def add(text, kind, culture_id, origin, character_name=None, place_id=None):
        if not text or name_key(text) in known:
            return
        if culture_id not in cultures:
            culture_id = None
        known.add(name_key(text))
        findings.append(
            NameFinding(
                text=text,
                kind=kind,
                culture_id=culture_id,
                # a place or thing named in plain English words ("The Grey
                # Gull") is a common-tongue name, not a misfit
                doesnt_fit=(
                    culture_id is not None
                    and (kind == "person" or not all_common_words(text))
                    and not name_fits(cultures[culture_id].language, text)
                ),
                first_used=first_used(text),
                character_name=character_name,
                place_id=place_id,
                origin=origin,
            )
        )

    # persons
    for key in characters:
        text = clean_name(key)
        if not looks_like_name(text) or name_key(text) in place_keys:
            # a place the snapshot listed among the characters isn't a person
            continue
        character = scene_characters.get(text)
        own = getattr(character, "culture", None) if character is not None else None
        spare = offered_spares.get(text.lower())
        spare_culture = spare.get("culture_id") if spare is not None else None
        if spare_culture in cultures:
            # R11: a reused spare is in the language of its generator
            culture_id = spare_culture
        elif own is not None and own.culture_id in cultures:
            culture_id = own.culture_id
        else:
            culture_id = guess_culture_for_name(cultures, scene, text).culture_id
        if spare is not None:
            # R6: the offered batch isn't kept, so no candidates
            origin = GlossaryOrigin(
                by="ai", generator_id=spare.get("generator_id"), candidates=[]
            )
        else:
            origin = GlossaryOrigin(by="ai_free")
        add(text, "person", culture_id, origin, character_name=text)

    # things
    thing_culture = _dominant(scene.mix, cultures)

    def proper_item(text: str) -> bool:
        # an insult in common words ("The Stupid Bitch") is no item's name
        return (
            _capitalised_name(text)
            and not is_insult_phrase(text)
            and is_proper_item_name(text, texts)
        )

    for key in items:
        text = _with_article(key, proper_item)
        if not text:
            continue
        add(text, "thing", thing_culture, GlossaryOrigin(by="ai_free"))

    # places
    for name, place_id in places_found:
        text = clean_name(name)
        mix = effective_mix(places, place_id)[0] if places else scene.mix
        add(
            text,
            "place",
            _dominant(mix, cultures),
            GlossaryOrigin(by="ai_free"),
            place_id=place_id,
        )

    return findings


# replies


def _reply_lines(text: str) -> list[str]:
    lines = []
    for line in (text or "").splitlines():
        line = re.sub(r"</?[A-Za-z]+>", "", line)
        line = line.strip().lstrip("-*•").strip()
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if line:
            lines.append(line)
    return lines


def _find_place(places: list[Place], name: str) -> Place | None:
    key = name_key(name)
    for place in places:
        if name_key(place.name) == key:
            return place
    return None


def _find_culture(cultures, name: str) -> Culture | None:
    key = _field(name).lower()
    for culture in cultures:
        if key in (
            culture.name.lower(),
            culture.id.lower(),
            culture.language.name.lower(),
        ):
            return culture
    return None


_SHARE = re.compile(r"^(.+?)\s*[:=]?\s*(\d+)\s*%?$")


def _parse_shares(
    text: str, cultures: dict[str, Culture]
) -> tuple[list[CultureShare], bool]:
    """`"Elsiri 70, Taelrik 30"` → shares, and whether anything was off."""

    shares: list[CultureShare] = []
    off = False
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        match = _SHARE.match(part)
        culture = _find_culture(cultures.values(), match.group(1)) if match else None
        if culture is None:
            off = True
            continue
        shares.append(CultureShare(culture_id=culture.id, share=int(match.group(2))))
    if not shares:
        off = True
    return shares, off


def parse_places_reply(
    text: str,
    names: list[str],
    places: list[Place],
    cultures: dict[str, Culture],
    current_place: Place | None,
    skipped: list[str] | None = None,
) -> list[Place]:
    """Turn the infer-places reply into new places, at most one per name.

    Line format: `Name | kind | parent name or none | Culture share,
    Culture share or inherit | sure|unsure`, or `Name | skip` for a name
    that isn't a place (appended to `skipped` when given). A name with no
    line is dropped this round; a later snapshot may propose it again.
    """

    wanted = {name_key(name): name for name in names}
    default_parent = current_place.id if current_place is not None else None
    parsed: dict[str, dict] = {}

    for line in _reply_lines(text):
        parts = [_field(part) for part in line.split("|")]
        if len(parts) < 2:
            continue
        name = wanted.get(name_key(parts[0]))
        if name is None or name_key(name) in parsed:
            continue
        if parts[1].lower() in _SKIP_ANSWERS:
            parsed[name_key(name)] = None
            if skipped is not None:
                skipped.append(name)
            continue
        parts += [""] * (5 - len(parts))
        kind_text, parent_text, shares_text, sure_text = parts[1:5]
        unsure = sure_text.strip(".! ").lower() != "sure"

        kind = kind_text.lower()
        if kind not in PLACE_KINDS:
            kind, unsure = "poi", True

        shares: list[CultureShare] = []
        if shares_text.lower() not in ("inherit", "inherits"):
            shares, off = _parse_shares(shares_text, cultures)
            unsure = unsure or off

        parsed[name_key(name)] = {
            "name": name,
            "kind": kind,
            "parent": parent_text,
            "shares": shares,
            "unsure": unsure,
        }

    ids = {name_key(name): new_id() for name in names if parsed.get(name_key(name))}
    result: list[Place] = []
    for name in names:
        key = name_key(name)
        info = parsed.get(key)
        if info is None:
            # skipped, or not answered
            continue

        unsure = info["unsure"]
        parent_text = info["parent"]
        parent_key = name_key(parent_text)
        if parent_key == "none":
            parent_id = None
        elif parent_key in ids and parent_key != key:
            parent_id = ids[parent_key]
        else:
            parent = _find_place(places, parent_text) if parent_text else None
            if parent is not None:
                parent_id = parent.id
            else:
                parent_id, unsure = default_parent, True

        place = Place(id=ids[key], name=name, kind=info["kind"], parent_id=parent_id)
        if info["shares"]:
            [place] = set_shares([place], place.id, info["shares"])
        result.append(place.model_copy(update={"set_by": "ai", "unsure": unsure}))
    return result


def _normalise(text: str) -> str:
    text = re.sub(r"[^\w\s]", "", text.lower())
    return " ".join(text.split())


def _section(text: str) -> str | None:
    key = text.strip().lower()
    for section in ADDITION_SECTIONS:
        if key == section or key == section.rstrip("s"):
            return section
    return None


def parse_additions_reply(
    text: str,
    cultures_present: list[Culture],
    source: str,
    limit: int = 3,
) -> list[tuple[str, PlayAddition]]:
    """Turn the find-additions reply into new, unreviewed play additions.

    Line format: `Culture | customs|food|holidays | text`. `NONE` or an
    empty reply gives `[]`. Texts already known to the culture (equal,
    containing or contained, after normalising) are dropped.
    """

    known: dict[str, list[str]] = {}
    for culture in cultures_present:
        texts = list(culture.customs) + [culture.food]
        texts += [holiday.name for holiday in culture.holidays]
        texts += [addition.text for addition in culture.additions]
        known[culture.id] = [n for n in (_normalise(t) for t in texts) if n]

    result: list[tuple[str, PlayAddition]] = []
    for line in _reply_lines(text):
        if _field(line).upper() == "NONE":
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        culture = _find_culture(cultures_present, parts[0])
        section = _section(_field(parts[1]))
        addition_text = _strip_markup(parts[2])
        normalised = _normalise(addition_text)
        if culture is None or section is None or not normalised:
            continue
        if any(
            normalised == existing or existing in normalised or normalised in existing
            for existing in known[culture.id]
        ):
            continue
        known[culture.id].append(normalised)
        result.append(
            (
                culture.id,
                PlayAddition(
                    id=new_id(),
                    section=section,
                    text=addition_text,
                    source=source,
                    status="unreviewed",
                ),
            )
        )
        if len(result) >= limit:
            break
    return result
