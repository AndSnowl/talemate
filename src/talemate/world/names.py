"""The name index: where a world's things are named in a piece of text.

Plain code, no model, so it can run while the owner types. One index
serves scene setup's prompt highlights, fact linking and prose links.

`find_names` matches, case-insensitively and as whole words, with a
trailing `'s` allowed and longer names tried first:

- every thing's main name and every one of its other names (`aka`);
- a character's first name on its own ("Maren" for "Maren Vos"), unless
  it's a leading article; a leading title (`TITLE_WORDS`) is skipped, so
  "Tsar Alexei II" is "Alexei", never "Tsar";
- one capitalised word of five or more letters from a multi-word main
  name ("Moscavia" for "Tsardom of Moscavia"), but no title word. That's
  only a *suggested* match, offered after any real one;
- an adjective form of a one-word main or other name of four letters or
  more ("Moscavian" for Moscavia, "Kalmaran" for Kalmara) of a place,
  sphere, species or race (`ADJECTIVE_KINDS`; "Julian" never means Julia):
  the name, or the name less a final vowel, with one of
  `ADJECTIVE_ENDINGS`. It ranks after the other names.

A stub whose name is a common word ("Hope") mustn't link the "hope" in
"I hope", so a stub, like another name ("the Pier") or a suggestion,
matches only text written with a capital letter (a leading article may
stay lowercase: "the Drowned Stag"). A stub the owner ignored isn't
matched at all. An adjective form needs a capital too. The main name (and a character's first name) of an
entry that isn't a stub matches in any case, as scene setup always has.

`unknown_proper_phrases` finds the capitalised phrases no match covers
("Yelena", "Night of Feathers"), as suggestions for new stubs. Without a
model it can't tell a name from a capitalised word, so a sentence's
capitalised first word on its own, a lone pronoun and leading articles
are left out.
"""

import re
from collections.abc import Sequence
from typing import Literal

import structlog
from pydantic import BaseModel

from .view import ThingState, WorldView

log = structlog.get_logger("talemate.world.names")

Via = Literal["name", "aka", "first_name", "adjective", "partial"]

# leading words never matched on their own as a character's first name,
# and stripped from the front of an unknown phrase
ARTICLES = {"the", "a", "an"}

# words of rank or address that may open a character's name ("Tsar Alexei
# II", "Grand Prince Dmitri I"): never a first name, never suggested alone
TITLE_WORDS = set(
    (
        "tsar tsarina tsaritsa czar king queen prince princess grand duke "
        "duchess archduke archduchess emperor empress lord lady sir dame "
        "count countess baron baroness earl khan sultan emir shah regent "
        "boyar voivode hetman saint st father mother brother sister bishop "
        "archbishop patriarch abbot abbess captain general admiral marshal "
        "commander chancellor master mistress elder high dr mr mrs ms"
    ).split()
)

# the shortest word of a longer name that's suggested on its own
PARTIAL_MIN_LETTERS = 5

# the endings an adjective form adds to a name, or to the name less a
# final vowel; and the shortest name that has adjective forms ("Uz" has
# none)
ADJECTIVE_ENDINGS = ("n", "an", "ian", "ish", "ese")
ADJECTIVE_MIN_LETTERS = 4
# the kinds whose names have adjective forms
ADJECTIVE_KINDS = frozenset({"place", "sphere", "species", "race"})
_VOWELS = "aeiou"

# lowercase words an unknown phrase may run across ("Night of Feathers")
_CONNECTORS = {"of", "the"}

# capitalised words that are never an unknown phrase on their own
_PRONOUNS = {
    "i",
    "me",
    "my",
    "mine",
    "you",
    "your",
    "yours",
    "he",
    "him",
    "his",
    "she",
    "her",
    "hers",
    "it",
    "its",
    "we",
    "us",
    "our",
    "ours",
    "they",
    "them",
    "their",
    "theirs",
}

# capitalised words that are never part of an unknown phrase
_NEVER_NAMES = {
    "I",
    "AM",
    "PM",
    *("Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()),
    *(
        "January February March April May June July August September "
        "October November December"
    ).split(),
}

# common sentence openers, dropped from the front of a sentence's first
# phrase ("Then Yelena went" gives "Yelena")
_SENTENCE_OPENERS = set(
    (
        "then but when after and so if as while before since yet now there "
        "here this that later soon still once until though although because "
        "meanwhile suddenly finally perhaps maybe or nor for "
        "on in at by from some every each most many all"
    ).split()
)

# abbreviations whose full stop doesn't end a run ("Cathedral of St. Sophia")
_ABBREVIATIONS = {"St"}

# how a candidate ranks among others for the same text: lower is better
_RANKS: dict[str, int] = {
    "name": 0,
    "aka": 1,
    "first_name": 2,
    "adjective": 8,
    "partial": 9,
}
# added to the ranks of things that only share a longer name's first word
_FIRST_WORD_RANK = 3

# a word: letters, digits, inner hyphens and apostrophes ("Owl-folk",
# "Yelena's")
_WORD = re.compile(r"[^\W\d_][\w-]*(?:['’]\w+)*")
_POSSESSIVE = re.compile(r"['’]s$", re.IGNORECASE)
# what joins a possessive to the next word of the same name ("Cairn's Bend",
# "Bishops' Council"): the possessive's own ending, then whitespace
_POSSESSIVE_GAP = re.compile(r"['’][sS]?\s+")
# what may stand between a sentence's end and its first word
_LEAD_INS = " \t\"'“”‘’([{*_"
_SENTENCE_ENDS = ".!?\n"


class NameCandidate(BaseModel):
    """A thing a name in the text could mean, and how it was matched."""

    id: str
    name: str
    kind: str
    stub: bool = False
    via: Via = "name"


class NameMatch(BaseModel):
    """One name found in the text: its span, the text as written (without
    a trailing `'s`), and the things it could mean, best first.
    `suggested` when the only candidates are partial matches."""

    start: int
    end: int
    text: str
    candidates: list[NameCandidate]
    suggested: bool = False


class Unknown(BaseModel):
    """A capitalised phrase no match covers, as written."""

    start: int
    end: int
    text: str


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def everyday_name(state: ThingState) -> str | None:
    """The thing's everyday name (its `aka` entry marked `everyday`), or
    `None` if it has none."""

    for entry in _aka_entries(state):
        if entry.get("everyday") is True:
            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                return " ".join(name.split())
    return None


def _aka_entries(state: ThingState) -> list[dict[str, object]]:
    aka = state.fields.get("aka")
    if not isinstance(aka, list):
        return []
    return [entry for entry in aka if isinstance(entry, dict)]


def _letters(word: str) -> int:
    return sum(1 for ch in word if ch.isalpha())


def _partial_words(name: str, kind: str) -> list[str]:
    """The words of a multi-word main name suggested on their own:
    capitalised, five letters or more, no title word, and not a
    character's first name (that's a real match already)."""

    words = name.split()
    if len(words) < 2:
        return []
    first = _first_name(words) if kind == "character" else None
    return [
        word
        for word in words
        if word[:1].isupper()
        and _letters(word) >= PARTIAL_MIN_LETTERS
        and word != first
        and _title_key(word) not in TITLE_WORDS
    ]


def adjective_forms(name: str) -> list[str]:
    """The adjective forms of a one-word name of `ADJECTIVE_MIN_LETTERS` or
    more ("Moscavian", "Moscavish", ... for "Moscavia"), each once, never
    the name itself. Empty for a longer or shorter name."""

    words = name.split()
    if len(words) != 1 or _letters(name) < ADJECTIVE_MIN_LETTERS:
        return []
    stems = [name]
    if name[-1].casefold() in _VOWELS:
        stems.append(name[:-1])
    forms: list[str] = []
    for stem in stems:
        for ending in ADJECTIVE_ENDINGS:
            form = stem + ending
            if _norm(form) != _norm(name) and form not in forms:
                forms.append(form)
    return forms


def _title_key(word: str) -> str:
    return word.casefold().rstrip(".")


def _first_name(words: list[str]) -> str | None:
    """A character's first name among the words of its (multi-word) name:
    the first word past any leading titles ("Alexei" in "Tsar Alexei II").
    `None` for a one-word name, one opening with an article, or one of
    titles only."""

    if len(words) < 2 or words[0].casefold() in ARTICLES:
        return None
    rest = list(words)
    while rest and _title_key(rest[0]) in TITLE_WORDS:
        rest.pop(0)
    return rest[0] if rest else None


Aliases = dict[str, list[tuple[int, NameCandidate]]]


def _aliases(view: WorldView, extra: Sequence[ThingState] = ()) -> Aliases:
    """Every matchable alias (normalised) and the things it names, each
    with its rank: the view's things', then `extra`'s (things not in the
    view, named by their own `name` field)."""

    aliases: Aliases = {}

    def add(alias: str, state: ThingState, name: str, via: Via) -> None:
        key = _norm(alias)
        if not key:
            return
        candidate = NameCandidate(
            id=state.id, name=name, kind=state.kind, stub=state.is_stub, via=via
        )
        aliases.setdefault(key, []).append((_RANKS[via], candidate))

    pool = [(state, False) for state in view.things()]
    pool += [(state, True) for state in extra]
    for state, drafted in pool:
        if state.stub_ignored:
            continue
        own = state.fields.get("name") if drafted else None
        written = own if isinstance(own, str) else view.name_of(state.id)
        name = " ".join((written or "").split())
        if not name:
            continue
        add(name, state, name, "name")
        others = [
            other
            for entry in _aka_entries(state)
            if isinstance(other := entry.get("name"), str)
        ]
        for other in others:
            add(other, state, name, "aka")
        if state.kind in ADJECTIVE_KINDS:
            adjectives = {
                _norm(form)
                for written in [name, *others]
                for form in adjective_forms(" ".join(written.split()))
            }
            for form in sorted(adjectives):
                add(form, state, name, "adjective")
        words = name.split()
        first = _first_name(words) if state.kind == "character" else None
        if first is not None:
            add(first, state, name, "first_name")
        for word in _partial_words(name, state.kind):
            add(word, state, name, "partial")
    return aliases


def _candidates(aliases: Aliases, key: str) -> list[NameCandidate]:
    """The things `key` could mean, best first: main and other names,
    characters it's the first name of, then (for a multi-word name) others
    sharing its first word, so the owner can pick a different one, and
    last the things it's only part of the name of."""

    ranked = list(aliases.get(key, []))
    first = key.split()[0]
    if first != key:
        ranked += [
            (rank + _FIRST_WORD_RANK, c)
            for rank, c in aliases.get(first, [])
            if c.via != "partial"
        ]
    seen: set[str] = set()
    found: list[NameCandidate] = []
    for _rank, candidate in sorted(ranked, key=lambda rc: (rc[0], rc[1].name)):
        if candidate.id not in seen:
            seen.add(candidate.id)
            found.append(candidate)
    return found


def _capitalised(written: str) -> bool:
    """Whether `written` starts with a capital letter, past a leading
    article ("the Drowned Stag" is)."""

    words = written.split()
    if len(words) > 1 and words[0].casefold() in ARTICLES:
        words = words[1:]
    return bool(words) and words[0][:1].isupper()


def _needs_capital(candidate: NameCandidate) -> bool:
    """Only a main name (or a character's first name) of a thing that
    isn't a stub matches in any case; a stub, another name ("the Pier"),
    an adjective form or a partial needs a capital."""

    return candidate.stub or candidate.via in ("aka", "adjective", "partial")


def find_names(
    view: WorldView, text: str, *, extra: Sequence[ThingState] = ()
) -> list[NameMatch]:
    """Every name of the view's things in `text`, as they're named at the
    view's date, in order. Longer names are tried first, so overlapping
    names match once ("Maren Vos" never also as "Maren"). `extra` are
    things matched as if the view had them (an entry still being drafted,
    named by its `name` and `aka` fields)."""

    aliases = _aliases(view, extra)
    folded = text.casefold()

    # (start, end, end with any `'s`, written, candidates)
    found: list[tuple[int, int, int, str, list[NameCandidate]]] = []
    for alias in aliases:
        words = alias.split()
        if words[0] not in folded:
            continue
        pattern = re.compile(
            r"(?<!\w)(" + r"\s+".join(map(re.escape, words)) + r")(?:['’]s)?(?!\w)",
            re.IGNORECASE,
        )
        for hit in pattern.finditer(text):
            written = hit.group(1)
            if _norm(written) != alias:
                # a case mapping regex and casefold disagree on: not a match
                continue
            capital = _capitalised(written)
            candidates = [
                c
                for c in _candidates(aliases, alias)
                if capital or not _needs_capital(c)
            ]
            if candidates:
                found.append((hit.start(1), hit.end(1), hit.end(), written, candidates))

    matches: list[NameMatch] = []
    taken = 0
    for start, end, full_end, written, candidates in sorted(
        found, key=lambda f: (f[0], -f[1])
    ):
        if start < taken:
            continue
        taken = full_end
        matches.append(
            NameMatch(
                start=start,
                end=end,
                text=written,
                candidates=candidates,
                suggested=all(c.via == "partial" for c in candidates),
            )
        )
    return matches


def _sentence_initial(text: str, start: int) -> bool:
    """Whether the word at `start` opens `text` or a sentence in it."""

    i = start
    while i > 0 and text[i - 1] in _LEAD_INS:
        i -= 1
    return i == 0 or text[i - 1] in _SENTENCE_ENDS


def unknown_proper_phrases(view: WorldView, text: str) -> list[Unknown]:
    """The runs of capitalised words in `text` that no `find_names` match
    (suggested ones included) covers, without a trailing `'s` or leading
    articles. A run may cross lowercase "of" and "the" ("Night of the
    Feathers"). A sentence's capitalised first word on its own, a lone
    pronoun and a lone article are left out, and so is a common opener
    ("Then", "But", "On", "Some") in front of a sentence's first phrase.
    A run goes on across a possessive into another capitalised word
    ("Cairn's Bend", "Bishops' Council") and past the full stop of "St.".
    "I" (and its contractions), "AM", "PM", days and months never start or
    join a run."""

    covered = [(m.start, m.end) for m in find_names(view, text)]

    # (start, end, possessive) of each word, any `'s` cut off; a plural's
    # possessive ("Bishops'") counts too
    words: list[tuple[int, int, bool]] = []
    for hit in _WORD.finditer(text):
        possessive = _POSSESSIVE.search(hit.group(0))
        end = hit.start() + possessive.start() if possessive else hit.end()
        plural_possessive = hit.group(0)[-1] in "sS" and text[
            hit.end() : hit.end() + 1
        ] in ("'", "’")
        words.append((hit.start(), end, possessive is not None or plural_possessive))

    def base(i: int) -> str:
        """Word `i` without a contraction ("I'm" is "I")."""

        start, end, _ = words[i]
        return re.split(r"['’]", text[start:end], maxsplit=1)[0]

    def is_cap(i: int) -> bool:
        start, end, _ = words[i]
        # "I" is capitalised anywhere, so it says nothing about a name
        return (
            base(i) not in _NEVER_NAMES
            and text[start].isupper()
            and not any(start < c_end and c_start < end for c_start, c_end in covered)
        )

    def adjacent(i: int) -> bool:
        """Whether word `i` follows word `i - 1` across whitespace only, or
        across the full stop of an abbreviation ("St. Sophia")."""

        prev_start, prev_end, prev_possessive = words[i - 1]
        gap = text[prev_end : words[i][0]]
        if prev_possessive:
            return False
        if gap.isspace():
            return True
        return (
            text[prev_start:prev_end] in _ABBREVIATIONS
            and gap[:1] == "."
            and gap[1:].isspace()
        )

    def joins_possessive(i: int) -> bool:
        """Whether word `i` is a capitalised word right after a possessive
        word `i - 1`, as one name ("Cairn's Bend")."""

        _, prev_end, prev_possessive = words[i - 1]
        return (
            prev_possessive
            and _POSSESSIVE_GAP.fullmatch(text[prev_end : words[i][0]]) is not None
            and is_cap(i)
        )

    phrases: list[Unknown] = []
    i = 0
    while i < len(words):
        if not is_cap(i):
            i += 1
            continue
        run = [i]
        j = i + 1
        while j < len(words) and (adjacent(j) or joins_possessive(j)):
            if is_cap(j):
                run.append(j)
                j += 1
                continue
            # a connector, kept only when the run goes on past it
            k = j
            while (
                k < len(words)
                and adjacent(k)
                and not is_cap(k)
                and text[words[k][0] : words[k][1]] in _CONNECTORS
            ):
                k += 1
            if k > j and k < len(words) and adjacent(k) and is_cap(k):
                run.extend(range(j, k + 1))
                j = k + 1
                continue
            break
        i = j

        initial = _sentence_initial(text, words[run[0]][0])
        if len(run) == 1 and initial:
            continue
        if initial and base(run[0]).casefold() in _SENTENCE_OPENERS:
            run.pop(0)
        while run and text[words[run[0]][0] : words[run[0]][1]].casefold() in ARTICLES:
            run.pop(0)
        if not run:
            continue
        start, end = words[run[0]][0], words[run[-1]][1]
        phrase = text[start:end]
        if len(run) == 1 and base(run[0]).casefold() in _PRONOUNS:
            continue
        phrases.append(Unknown(start=start, end=end, text=phrase))
    return phrases
