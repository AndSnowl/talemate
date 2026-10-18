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

from talemate.cultures.generator import fits
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
    clean_name,
    first_mention,
    is_proper_item_name,
    looks_like_name,
)

if TYPE_CHECKING:
    from talemate.character import Character

__all__ = [
    "NameFinding",
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


def _place_name_keys(place: Place) -> set[str]:
    keys = {place.name.lower()}
    if place.name.startswith("The "):
        keys.add(place.name[4:].lower())
    return keys


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


def new_place_names(
    location: str | None,
    snapshot_places: list[str],
    places: list[Place],
    character_names: list[str],
) -> list[str]:
    """Place names in the snapshot that the world doesn't know yet."""

    candidates: list[str] = []
    if location:
        candidates.extend(
            clean_name(run)
            for run in _capitalised_runs(location)
            if looks_like_name(run)
        )
    for key in snapshot_places:
        cleaned = clean_name(key)
        if looks_like_name(cleaned):
            candidates.append(cleaned)

    known: set[str] = set()
    for place in places:
        known |= _place_name_keys(place)
    known |= {name.lower() for name in character_names}

    result: list[str] = []
    for name in candidates:
        key = name.lower()
        if not name or key in known:
            continue
        known.add(key)
        result.append(name)
    return result


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

    known = {entry.text.lower() for entry in glossary}
    texts = [str(getattr(message, "message", "") or "") for message in messages]
    findings: list[NameFinding] = []

    def first_used(text: str) -> str:
        mention = first_mention(text, messages)
        return f"{story}, message {mention.id}" if mention is not None else story

    def add(text, kind, culture_id, origin, character_name=None, place_id=None):
        if not text or text.lower() in known:
            return
        if culture_id not in cultures:
            culture_id = None
        known.add(text.lower())
        findings.append(
            NameFinding(
                text=text,
                kind=kind,
                culture_id=culture_id,
                doesnt_fit=(
                    culture_id is not None
                    and not fits(cultures[culture_id].language, text)
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
        if not looks_like_name(text):
            continue
        character = scene_characters.get(text)
        own = getattr(character, "culture", None) if character is not None else None
        if own is not None and own.culture_id in cultures:
            culture_id = own.culture_id
        else:
            culture_id = guess_culture_for_name(cultures, scene, text).culture_id
        spare = offered_spares.get(text.lower())
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
    for key in items:
        text = clean_name(key)
        if not _capitalised_name(text) or not is_proper_item_name(text, texts):
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
    key = clean_name(name).lower()
    for place in places:
        if key in _place_name_keys(place):
            return place
    return None


def _find_culture(cultures, name: str) -> Culture | None:
    key = name.strip().lower()
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
) -> list[Place]:
    """Turn the infer-places reply into new places, one per name.

    Line format: `Name | kind | parent name or none | Culture share,
    Culture share or inherit | sure|unsure`. A name with no (usable) line
    is placed under the current place, inheriting, unsure.
    """

    wanted = {name.lower(): name for name in names}
    default_parent = current_place.id if current_place is not None else None
    parsed: dict[str, dict] = {}

    for line in _reply_lines(text):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            continue
        name = wanted.get(clean_name(parts[0]).lower())
        if name is None or name.lower() in parsed:
            continue
        parts += [""] * (5 - len(parts))
        kind_text, parent_text, shares_text, sure_text = parts[1:5]
        unsure = sure_text.lower() != "sure"

        kind = kind_text.lower()
        if kind not in PLACE_KINDS:
            kind, unsure = "poi", True

        shares: list[CultureShare] = []
        if shares_text.lower() not in ("inherit", "inherits"):
            shares, off = _parse_shares(shares_text, cultures)
            unsure = unsure or off

        parsed[name.lower()] = {
            "name": name,
            "kind": kind,
            "parent": parent_text,
            "shares": shares,
            "unsure": unsure,
        }

    ids = {name.lower(): new_id() for name in names}
    result: list[Place] = []
    for name in names:
        key = name.lower()
        info = parsed.get(key)
        if info is None:
            result.append(
                Place(
                    id=ids[key],
                    name=name,
                    kind="poi",
                    parent_id=default_parent,
                    set_by="ai",
                    unsure=True,
                )
            )
            continue

        unsure = info["unsure"]
        parent_text = info["parent"]
        parent_key = clean_name(parent_text).lower()
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
        if line.strip().upper() == "NONE":
            continue
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) < 3:
            continue
        culture = _find_culture(cultures_present, parts[0])
        section = _section(parts[1])
        addition_text = parts[2]
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
