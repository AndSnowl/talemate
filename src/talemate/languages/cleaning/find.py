"""Finding bad names in a draft's texts (languages 4a): the spots to judge,
the names that are never touched, and a verdict for each bad one."""

from __future__ import annotations

import re
from typing import Literal

import structlog
from pydantic import BaseModel

from talemate.languages.check import _real_words, stem
from talemate.languages.cleaning import ask
from talemate.languages.cleaning.languages import named_languages
from talemate.languages.cleaning.lists import NameLists, match
from talemate.languages.generator import name_fits
from talemate.languages.models import Language
from talemate.world.names import TITLE_WORDS, unknown_proper_phrases
from talemate.world.view import WorldView
from talemate.worldplay.create import json_objects

__all__ = ["Spot", "Verdict", "judge", "protected_names", "spots"]

log = structlog.get_logger("talemate.languages.cleaning")

PERSON_KINDS = {"character"}
# words naming what a place is ("the River X"); they stay as written
KIND_WORDS = set(
    "river lake mountains mountain sea coast isles isle island forest marsh "
    "marshes steppe pass bay gulf hills hill valley plains strait straits".split()
)
# a person's name stops at these: what follows is an epithet or an origin
NAME_STOPS = {"the", "of", "from"}
MIN_PART = 3
_NUMERAL = re.compile(r"^[IVXLC]+$")
_WORD = re.compile(r"[^\W\d_][\w'’-]*")
MAN_TITLES = set(
    "tsar czar king prince duke archduke emperor lord sir count baron earl "
    "khan sultan emir shah boyar voivode hetman father brother abbot "
    "master mr".split()
)
WOMAN_TITLES = set(
    "tsarina tsaritsa queen princess duchess archduchess empress lady dame "
    "countess baroness mother sister abbess mistress mrs ms".split()
)


class Spot(BaseModel):
    name: str
    full: str
    kind: str
    person: Literal["man", "woman", ""] = ""
    part: Literal["whole", "given", "family"] = "whole"
    texts: list[int] = []


class Verdict(BaseModel):
    spot: Spot
    action: Literal["replace", "rewrite", "suspect"]
    why: str


def _strip_possessive(text: str) -> str:
    return re.sub(r"['’]s?$", "", text)


def _person_of(full: str, texts: list[str], own: bool) -> str:
    words = [w.lower() for w in _WORD.findall(full)]
    if any(w in MAN_TITLES for w in words):
        return "man"
    if any(w in WOMAN_TITLES for w in words):
        return "woman"
    if own:
        joined = " ".join(texts).lower()
        he = len(re.findall(r"\b(he|his|him)\b", joined))
        she = len(re.findall(r"\b(she|her|hers)\b", joined))
        if he != she:
            return "man" if he > she else "woman"
    return ""


def _parts(full: str, kind: str) -> list[tuple[str, str]]:
    """The parts of a name to judge, with which part each is."""

    words = _WORD.findall(_strip_possessive(full))
    if kind in PERSON_KINDS:
        kept = []
        for word in words:
            if word.lower() in NAME_STOPS:
                break
            if (
                word.lower() in TITLE_WORDS
                or _NUMERAL.match(word)
                or len(word) < MIN_PART
            ):
                continue
            kept.append(word)
        if len(kept) <= 1:
            return [(w, "whole") for w in kept]
        return [(kept[0], "given")] + [(w, "family") for w in kept[1:]]
    words = [w for w in words if w.lower() not in KIND_WORDS]
    while words and words[0].lower() in ("the", "of"):
        words = words[1:]
    name = " ".join(words)
    return [(name, "whole")] if name else []


def protected_names(
    view: WorldView, prompt: str, language: Language | None, keep: list[str]
) -> set[str]:
    """Lower-cased names never replaced: the prompt's capitalised words and
    runs, every entry's names, the language's dictionary words, and the
    keep list. (Language names and their country forms are checked as
    spots are found.)"""

    found: set[str] = set()
    for run in re.findall(
        r"[A-Z][\w'’-]*(?:\s+(?:of\s+|the\s+)*[A-Z][\w'’-]*)*", prompt
    ):
        found.add(_strip_possessive(run).lower())
        found.update(w.lower() for w in _WORD.findall(run))
    for state in view.things(facts=False):
        names = [str(state.fields.get("name") or "")]
        names += [str(a.get("name", "")) for a in state.fields.get("aka") or []]
        found.update(n.lower() for n in names if n)
    if language is not None:
        found.update(e.word.lower() for e in language.dictionary)
    found.update(n.lower() for n in keep)
    found.discard("")
    return found


def spots(
    view: WorldView,
    texts: list[str],
    listed: list[tuple[str, str]],
    protected: set[str],
) -> list[Spot]:
    """The names to judge in `texts`: the `listed` ones (the draft's own
    name first, then its new names, with their kinds), and capitalised
    runs the reply didn't list (taken as places). Title, kind and stop
    words stay out; a person's name is judged word by word; protected
    names, and names of the world's languages, are skipped."""

    found: dict[str, Spot] = {}

    def add(full: str, kind: str, own: bool) -> None:
        for name, part in _parts(full, kind):
            key = name.lower()
            if key in protected or full.lower() in protected:
                continue
            if named_languages(view, name):
                continue
            hits = [
                i
                for i, text in enumerate(texts)
                if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text)
            ]
            if key in found:
                continue
            found[key] = Spot(
                name=name,
                full=full,
                kind=kind,
                person=_person_of(full, texts, own) if kind in PERSON_KINDS else "",
                part=part,
                texts=hits,
            )

    listed_keys = set()
    for n, (full, kind) in enumerate(listed):
        add(full, kind, n == 0)
        listed_keys.add(full.lower())
    for text in texts:
        for unknown in unknown_proper_phrases(view, text):
            full = _strip_possessive(unknown.text)
            if full.lower() in listed_keys or any(
                full.lower() in k or k in full.lower() for k in listed_keys
            ):
                continue
            add(full, "place", False)
    return [s for s in found.values() if s.texts or s.full in dict(listed)]


def _context(spot: Spot, texts: list[str]) -> str:
    for i in spot.texts:
        if i < len(texts):
            return texts[i][:200]
    return spot.full


def _real_hit(language: Language, name: str) -> bool:
    real = _real_words(language.flavour)
    if not real:
        return False
    exact = {w.lower() for w in real}
    stems = {stem(w) for w in real}
    return any(
        w.lower() in exact or stem(w) in stems for w in re.findall(r"[^\W\d_]+", name)
    )


async def _flags(
    client, found: list[Spot], texts: list[str]
) -> dict[str, tuple[str, str]]:
    """The model's label and why per spot name; {} when the call fails."""

    try:
        reply = await ask(
            client,
            "name-flags",
            {"spots": [{"name": s.name, "context": _context(s, texts)} for s in found]},
        )
        objects = json_objects(reply)
        rows = objects[0].get("names") if objects else None
        if not isinstance(rows, list):
            raise ValueError("no names in the reply")
    except Exception as exc:
        log.warning("languages.clean_flag_failed", error=str(exc))
        return {}
    flags = {}
    for row in rows:
        if isinstance(row, dict) and row.get("name"):
            flags[str(row["name"]).lower()] = (
                str(row.get("label", "ok")),
                " ".join(str(row.get("why", "")).split()),
            )
    return flags


async def judge(
    client,
    found: list[Spot],
    lists: NameLists,
    language: Language | None,
    texts: list[str] | None = None,
) -> list[Verdict]:
    """A verdict for each bad spot, in order: a stock title on the list
    (rewrite); a real name or AI cliché on a list (replace); the model's
    flag (replace or rewrite, with its reason); a real word of the
    language's flavour (replace); a name that doesn't fit the language
    (suspect). With no language, every verdict is suspect and the model
    isn't asked."""

    texts = texts or []
    verdicts: list[Verdict] = []
    left: list[Spot] = []
    for spot in found:
        if match(lists, "title", spot.full) or match(lists, "title", spot.name):
            verdicts.append(Verdict(spot=spot, action="rewrite", why="a stock title"))
        elif match(lists, "real", spot.name) or match(lists, "real", spot.full):
            verdicts.append(
                Verdict(
                    spot=spot,
                    action="replace",
                    why="a real name, on the Real names list",
                )
            )
        elif match(lists, "cliche", spot.name) or match(lists, "cliche", spot.full):
            verdicts.append(Verdict(spot=spot, action="replace", why="an AI cliché"))
        else:
            left.append(spot)
    if language is None:
        return [
            Verdict(spot=v.spot, action="suspect", why="no language picked")
            for v in verdicts
        ]
    flags = await _flags(client, left, texts) if left else {}
    for spot in left:
        label, why = flags.get(spot.name.lower(), ("ok", ""))
        if label == "real":
            verdicts.append(
                Verdict(spot=spot, action="replace", why=why or "a real name")
            )
        elif label == "stock-title":
            verdicts.append(
                Verdict(spot=spot, action="rewrite", why=why or "a stock title")
            )
        elif _real_hit(language, spot.name):
            verdicts.append(
                Verdict(
                    spot=spot,
                    action="replace",
                    why=f"a real {language.flavour.capitalize()} word",
                )
            )
        elif not name_fits(language, spot.name):
            verdicts.append(
                Verdict(
                    spot=spot,
                    action="suspect",
                    why=f"doesn't sound like {language.name}",
                )
            )
    order = {id(s): i for i, s in enumerate(found)}
    return sorted(verdicts, key=lambda v: order[id(v.spot)])
