"""Names from a meaning or from an entry's facts (languages 4b-1): the
English read in code (probe 4b-1: "of", "the", plural, the last word as
the noun), the model asked only to split a one-word compound, to pick a
coined word, or to suggest a meaning from facts; the name engine builds
the words. Nothing is saved: coined words are saved when the owner picks
a name."""

from __future__ import annotations

import random
import re
from collections.abc import Callable

from talemate.languages.composed import PartRoll, roll_parts
from talemate.languages.entry import language_of
from talemate.languages.generator import roll
from talemate.languages.models import Language, NamePart
from talemate.languages.name_grammar import (
    Built,
    MeaningPhrase,
    build_phrase,
    lookup_word,
)
from talemate.languages.naming import PROMPT_KIND, _reply_object, pick
from talemate.prompts.base import Prompt
from talemate.world.view import WorldView
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call

__all__ = [
    "give_meaning",
    "part_meaning",
    "read_english",
    "resolve_words",
    "singular",
    "split_meaning",
    "suggest_for",
    "suggest_phrases",
]

# coined words offered for a new word: the model's pick and the others
CANDIDATES = 8
_FUNCTION = {"the", "of", "a", "an", "and"}


def _object(reply: str) -> dict:
    """The JSON object in a reply (the prompt starts it with "{")."""

    return _reply_object(reply if reply.lstrip().startswith("{") else "{" + reply)


def singular(word: str) -> str:
    """A plural English noun made singular, simply: stars, woods; berries;
    foxes, marshes."""

    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ches", "shes", "xes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _words(text: str) -> list[str]:
    """The text's words: split on spaces and hyphens, punctuation and
    digits dropped, a possessive's "'s" taken off (owl's → owl)."""

    out = []
    for raw in re.split(r"[\s\-]+", text.strip()):
        word = re.sub(r"['’]s$", "", raw.strip('.,;:!?"()[]'))
        word = re.sub(r"[^\w'’]|\d", "", word)
        if word:
            out.append(word)
    return out


def split_of(text: str) -> tuple[str, str] | None:
    """ "Court of Lakes" as ("Court", "Lakes"): the words before "of" and
    after it; None when "of" doesn't stand between two parts."""

    words = _words(text)
    lower = [w.lower() for w in words]
    if "of" not in lower[1:-1]:
        return None
    at = lower.index("of", 1)
    head = " ".join(w for w in words[:at] if w.lower() not in _FUNCTION)
    tail = " ".join(words[at + 1 :])
    return (head, tail) if head and tail else None


def read_english(
    text: str,
    compound: Callable[[str], dict] | None = None,
    *,
    language: Language | None = None,
) -> MeaningPhrase:
    """A meaning's structure read from the English (probe 4b-1, 19/20):
    "of" and "the" from its words, the last content word as the noun (made
    singular, and more than one when it was plural), the words after "of"
    in "Owl-of-Frost", "land" as the "land of" ending; a one-word compound
    ("Blackwater") goes to `compound`, the model."""

    words = _words(text)
    lower = [w.lower() for w in words]
    of = bool(lower) and (lower[0] == "of" or "of" in lower[1:-1])
    the = "the" in lower
    content = [w for w in lower if w not in _FUNCTION]
    ending = ""
    # "land" is the "land of" ending only where the language has one
    has_land = language is None or (
        language.name_grammar is not None
        and any(
            e.meaning.strip().lower() == "land of"
            for e in language.name_grammar.endings
        )
    )
    if (
        has_land
        and content
        and (content[-1] == "land" or (content[0] == "land" and "of" in lower))
    ):
        ending = "land of"
        content = [w for w in content if w != "land"]
        of = False
    if len(words) == 1 and len(content) == 1 and compound is not None and not ending:
        got = compound(content[0]) or {}
        describing = [
            str(d).lower() for d in got.get("describing") or [] if str(d).strip()
        ]
        if describing and got.get("noun"):
            return MeaningPhrase(
                noun=singular(str(got["noun"])), describing=describing, joined=True
            )
    if "of" in lower[1:-1]:
        at = lower.index("of", 1)
        content = [w for w in lower[at + 1 :] if w not in _FUNCTION]
    if not content:
        return MeaningPhrase(noun="")
    noun = content[-1]
    return MeaningPhrase(
        noun=singular(noun),
        describing=content[:-1],
        of=of,
        the=the,
        more_than_one=singular(noun) != noun,
        ending=ending,
    )


async def _compound_reply(client, word: str) -> str:
    prose_gen.require_client(client)
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.name-compound", client, PROMPT_KIND, vars={"word": word}
        )
    return extracted["response"]


async def split_meaning(
    client,
    language: Language,
    text: str,
    slots: list[NamePart],
    *,
    reply: str | None = None,
    ask: Callable[[str], dict] | None = None,
) -> list[MeaningPhrase]:
    """The owner's meaning as phrases, one a meaning part (`slots`; none:
    one phrase for the whole text). Several parts share the meaning out by
    "," or "and"; a part left over gets an empty noun (it keeps its roll).
    The owner's words win over a slot's settings. Only a one-word
    compound asks the model (one call)."""

    pieces = [text]
    if len(slots) > 1:
        pieces = [p for p in re.split(r",|\band\b", text) if p.strip()]
        found = split_of(text) if len(pieces) == 1 else None
        if found is not None:
            # "Owl of Frost": the words before "of" for the plain part, the
            # rest for the part that takes "of"
            head, tail = found
            pieces = [head, f"of {tail}"]
            if slots[0].of and not slots[1].of:
                pieces.reverse()
    asked: dict[str, dict] = {}

    async def model(word: str) -> dict:
        if ask is not None:
            return ask(word)
        if reply is not None:
            return _object(reply)
        if client is None:
            return {}
        return _object(await _compound_reply(client, word))

    phrases: list[MeaningPhrase] = []
    for piece in pieces[: max(1, len(slots))]:
        single = re.fullmatch(r"\s*([^\W\d_]+)\s*", piece)
        # a word the dictionary has is its own noun, never split
        if (
            single
            and single.group(1).lower() not in asked
            and lookup_word(language, single.group(1)) is None
        ):
            asked[single.group(1).lower()] = await model(single.group(1))
        phrases.append(
            read_english(
                piece, compound=lambda w: asked.get(w.lower(), {}), language=language
            )
        )
    while len(phrases) < len(slots):
        phrases.append(MeaningPhrase(noun=""))
    return phrases


async def resolve_words(
    client,
    language: Language,
    meanings: list[str],
    *,
    what: str = "",
    reply: str | None = None,
    rng: random.Random | None = None,
) -> tuple[dict[str, str], set[str], dict[str, list[str]]]:
    """Each meaning's word: the dictionary's, else coined from the word
    rules, the model picking among `CANDIDATES` rolls. Returns the words,
    the coined ones, and each coined word's options (the pick first)."""

    rng = rng if rng is not None else random.Random()
    word_rules = language.word_generator()
    taken = {e.word.lower() for e in language.dictionary}
    words: dict[str, str] = {}
    new: set[str] = set()
    options: dict[str, list[str]] = {}
    for meaning in meanings:
        if not meaning or meaning in words:
            continue
        entry = lookup_word(language, meaning)
        if entry is not None:
            words[meaning] = entry.word.lower()
            continue
        if word_rules is None:
            raise ValueError("this language has no word rules to make new words")
        rolled = [
            c.lower()
            for c in roll(
                language, word_rules.id, count=CANDIDATES, rng=rng, exclude=taken
            )
        ]
        if not rolled:
            raise ValueError("the language's word rules made no new words")
        chosen, _why = await pick(
            client,
            language,
            rolled,
            f'the word for "{meaning}" ({what or meaning})',
            reply=reply,
        )
        chosen = chosen.lower()
        taken.add(chosen)
        words[meaning] = chosen
        new.add(chosen)
        options[chosen] = [chosen, *[c for c in rolled if c != chosen]]
    return words, new, options


def _meanings(phrase: MeaningPhrase) -> list[str]:
    return [m for m in [*phrase.describing, phrase.noun] if m]


def _with_options(built: Built, options: dict[str, list[str]]) -> list[dict]:
    return [
        {
            **part,
            **({"options": options[part["word"]]} if part["word"] in options else {}),
        }
        for part in built.parts
    ]


def _phrase_rolls(
    language: Language,
    phrase: MeaningPhrase,
    words: dict[str, str],
    new: set[str],
    options: dict[str, list[str]],
) -> list[Built]:
    """The phrase built, then built again with the next option of every
    coined word together (the rolls a meaning part shows; owner,
    2026-11-05: each new word rerolls, not only the first)."""

    first = build_phrase(language, phrase, words, frozenset(new))
    first.parts = _with_options(first, options)
    rolls = [first]
    coined = [m for m, w in words.items() if w in options]
    if coined:
        lists = {m: options[words[m]] for m in coined}
        for i in range(1, max(len(v) for v in lists.values())):
            swapped = {m: lists[m][i % len(lists[m])] for m in coined}
            alt = build_phrase(
                language,
                phrase,
                {**words, **swapped},
                frozenset({*new, *swapped.values()}),
            )
            if alt.text not in {r.text for r in rolls}:
                rolls.append(alt)
    return rolls


async def _fill_parts(
    client,
    language: Language,
    rule_id: str,
    phrases: dict[int, MeaningPhrase],
    *,
    pinned: dict[int, str] | None,
    shape: int | None,
    what: str,
    reply: str | None,
) -> dict:
    shape, parts = roll_parts(language, rule_id, pinned=pinned, shape=shape)
    out: list[PartRoll] = []
    for part in parts:
        phrase = phrases.get(part.index)
        if (
            part.kind == "meaning"
            and not part.pinned
            and phrase is not None
            and phrase.noun
        ):
            words, new, options = await resolve_words(
                client, language, _meanings(phrase), what=what, reply=reply
            )
            part = part.model_copy(
                update={"rolls": _phrase_rolls(language, phrase, words, new, options)}
            )
        out.append(part)
    return {"shape": shape, "parts": [p.model_dump() for p in out]}


def _meaning_shape(language: Language, rule_id: str, shape: int | None) -> int | None:
    """The form a meaning goes into: `shape` when it has a meaning part,
    else the rule's first form that has one (owner, Test2: Find on a form
    without one only rerolled); `shape` as given when none has."""

    generator = next((g for g in language.generators if g.id == rule_id), None)
    if generator is None or not generator.shapes:
        return shape
    has = [
        i
        for i, form in enumerate(generator.shapes)
        if any(p.kind == "meaning" for p in form.parts)
    ]
    if shape is not None and shape in has:
        return shape
    return has[0] if has else shape


def _drop_fixed(
    language: Language, rule_id: str, shape: int | None, text: str
) -> tuple[str, bool]:
    """The meaning without the words a fixed word of the form already says
    ("owl of" when the form has Ul, "owl-of"), and whether those words
    ended in "of" (the rest is then that "of"'s noun)."""

    generator = next((g for g in language.generators if g.id == rule_id), None)
    if generator is None or shape is None or not 0 <= shape < len(generator.shapes):
        return text, False
    fixed = {p.word.lower() for p in generator.shapes[shape].parts if p.kind == "word"}
    words = _words(text)
    lower = [w.lower() for w in words]
    for meaning_words, entry, meaning in _phrase_entries(language):
        if (
            entry.word.lower() in fixed
            and tuple(lower[: len(meaning_words)]) == meaning_words
        ):
            rest = " ".join(words[len(meaning_words) :])
            return rest, meaning_words[-1] == "of"
    return text, False


def _meaning_slots(
    language: Language, rule_id: str, shape: int | None
) -> list[tuple[int, NamePart]]:
    generator = next((g for g in language.generators if g.id == rule_id), None)
    if generator is None or not generator.shapes:
        return []
    shape = shape if shape is not None and 0 <= shape < len(generator.shapes) else 0
    return [
        (i, p)
        for i, p in enumerate(generator.shapes[shape].parts)
        if p.kind == "meaning"
    ]


async def give_meaning(
    view: WorldView,
    client,
    language_id: str,
    text: str,
    *,
    rule_id: str | None = None,
    pinned: dict[int, str] | None = None,
    shape: int | None = None,
    reply: str | None = None,
) -> dict:
    """Names for the owner's meaning. With a composed rule (`rule_id`):
    `{shape, parts}`, its meaning parts built from the meaning (each
    coined word's other options as more rolls), the rest rolled, pins
    kept. Without: `{candidates: [{name, built_from}]}`, the phrase built
    in the language's order and, with more than one word, joined too."""

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        raise ValueError("there's no such language")
    language = language_of(state)
    if rule_id:
        shape = _meaning_shape(language, rule_id, shape)
        slots = _meaning_slots(language, rule_id, shape)
        text, after_of = _drop_fixed(language, rule_id, shape, text)
        phrases = await split_meaning(
            client, language, text, [p for _i, p in slots], reply=reply
        )
        if after_of and phrases:
            grammar = language.name_grammar
            the = grammar.of.the if grammar is not None and grammar.of else False
            phrases[0] = phrases[0].model_copy(update={"of": False, "the": the})
        found = {i: phrase for (i, _p), phrase in zip(slots, phrases)}
        return await _fill_parts(
            client,
            language,
            rule_id,
            found,
            pinned=pinned,
            shape=shape,
            what=text,
            reply=reply,
        )
    phrased = await _with_phrase_words(client, language, text, reply)
    if phrased is not None:
        return {"candidates": [phrased]}
    found = split_of(text)
    if found is not None:
        return {"candidates": [await _x_of_y(client, language, text, found, reply)]}
    (phrase,) = await split_meaning(client, language, text, [], reply=reply)
    if not phrase.noun:
        return {"candidates": []}
    words, new, options = await resolve_words(
        client, language, _meanings(phrase), what=text, reply=reply
    )
    built = build_phrase(language, phrase, words, frozenset(new))
    candidates = [{"name": built.text, "built_from": _with_options(built, options)}]
    if phrase.describing and not phrase.joined and not phrase.of:
        joined = build_phrase(
            language, phrase.model_copy(update={"joined": True}), words, frozenset(new)
        )
        if joined.text != built.text:
            candidates.insert(
                0, {"name": joined.text, "built_from": _with_options(joined, options)}
            )
    return {"candidates": candidates}


def _phrase_entries(language: Language) -> list[tuple[tuple[str, ...], object]]:
    """Dictionary words whose meaning is two or more words ("owl-of"),
    as (the meaning's words, the entry), longest first."""

    found = []
    for entry in language.dictionary:
        for meaning in entry.meanings:
            words = tuple(w.lower() for w in _words(meaning))
            if len(words) >= 2:
                found.append((words, entry, meaning))
    return sorted(found, key=lambda item: -len(item[0]))


async def _with_phrase_words(
    client, language: Language, text: str, reply
) -> dict | None:
    """A meaning using a word that means several words (Varovni's ul,
    "owl-of"; owner, Test2): that word stands for them, and what follows
    a word meaning "…of" is its noun ("owl of the sun" → Ul Svelm). None
    when the meaning uses no such word."""

    entries = _phrase_entries(language)
    if not entries:
        return None
    words = _words(text)
    lower = [w.lower() for w in words]
    pieces: list = []
    i = 0
    matched = False
    while i < len(lower):
        hit = next(
            (
                (len(t), entry, meaning)
                for t, entry, meaning in entries
                if tuple(lower[i : i + len(t)]) == t
            ),
            None,
        )
        if hit is not None:
            n, entry, meaning = hit
            pieces.append((entry, meaning))
            i += n
            matched = True
        else:
            if pieces and isinstance(pieces[-1], list):
                pieces[-1].append(words[i])
            else:
                pieces.append([words[i]])
            i += 1
    if not matched:
        return None
    grammar = language.name_grammar
    phrases: list = []
    for index, piece in enumerate(pieces):
        if isinstance(piece, tuple):
            phrases.append(piece)
            continue
        phrase = read_english(" ".join(piece), language=language)
        before = pieces[index - 1] if index else None
        if isinstance(before, tuple) and _words(before[1])[-1].lower() == "of":
            # the noun of a word meaning "…of": "the" as the of-rule says
            the = grammar.of.the if grammar is not None and grammar.of else False
            phrase = phrase.model_copy(update={"of": False, "the": the})
        phrases.append(phrase if phrase.noun else None)
    meanings = [
        m for p in phrases if isinstance(p, MeaningPhrase) for m in _meanings(p)
    ]
    resolved, new, options = await resolve_words(
        client, language, meanings, what=text, reply=reply
    )
    texts: list[str] = []
    parts: list[dict] = []
    for phrase in phrases:
        if phrase is None:
            continue
        if isinstance(phrase, tuple):
            entry, meaning = phrase
            texts.append(entry.word[:1].upper() + entry.word[1:])
            parts.append(
                {
                    "word": entry.word.lower(),
                    "meaning": meaning,
                    "new": False,
                    "steps": [],
                }
            )
            continue
        built = build_phrase(language, phrase, resolved, frozenset(new))
        texts.append(built.text)
        parts += _with_options(built, options)
    return {"name": " ".join(texts), "built_from": parts}


async def _x_of_y(
    client, language: Language, text: str, found: tuple[str, str], reply
) -> dict:
    """ "Court of Lakes": the head built, the "of" phrase built, in the
    order the language's of-rule puts them (after, unless it says
    before)."""

    head = read_english(found[0], language=language)
    tail = read_english(f"of {found[1]}", language=language)
    words, new, options = await resolve_words(
        client, language, [*_meanings(head), *_meanings(tail)], what=text, reply=reply
    )
    first = build_phrase(language, head, words, frozenset(new))
    second = build_phrase(language, tail, words, frozenset(new))
    of = language.name_grammar.of if language.name_grammar else None
    pair = (
        [second, first] if of is not None and of.place == "before" else [first, second]
    )
    return {
        "name": " ".join(b.text for b in pair),
        "built_from": [p for b in pair for p in _with_options(b, options)],
    }


async def _suggest_reply(
    client, language: Language, name: str, facts: list[str], hint: str
) -> str:
    prose_gen.require_client(client)
    with world_ai_call():
        _response, extracted = await Prompt.request(
            "world.name-suggest",
            client,
            PROMPT_KIND,
            vars={
                "language": language.name,
                "name": name,
                "facts": facts,
                "hint": hint,
            },
        )
    return extracted["response"]


async def suggest_phrases(
    client,
    language: Language,
    parts: list[NamePart],
    facts: list[str],
    *,
    name: str = "",
    reply: str | None = None,
) -> list[MeaningPhrase | None]:
    """A meaning from the entry's facts for each meaning part (None for
    the other parts): ONE common noun the model picks (probe 4b-1), made
    singular; the part's own forms, "of", joining and ending."""

    out: list[MeaningPhrase | None] = []
    for part in parts:
        if part.kind != "meaning":
            out.append(None)
            continue
        if reply is None:
            reply_text = await _suggest_reply(client, language, name, facts, part.hint)
        else:
            reply_text = reply
        noun = str(_object(reply_text).get("noun") or "").strip().split()
        out.append(
            MeaningPhrase(
                noun=singular(noun[-1]) if noun else "",
                of=part.of,
                the="the" in part.forms,
                more_than_one="more_than_one" in part.forms,
                joined=part.joined,
                ending=part.ending,
            )
        )
    return out


async def part_meaning(
    view: WorldView,
    client,
    language_id: str,
    rule_id: str,
    shape: int,
    index: int,
    text: str,
    *,
    reply: str | None = None,
) -> dict:
    """One meaning part's rolls built from the owner's meaning, the rest of
    the name left alone (round 4, owner 2026-11-03): `{shape, index,
    rolls}`, the coined word's other options as more rolls. A fixed word of
    the form that already says some of it ("Ul", owl-of) isn't said
    twice."""

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        raise ValueError("there's no such language")
    language = language_of(state)
    generator = next((g for g in language.generators if g.id == rule_id), None)
    if generator is None or not 0 <= shape < len(generator.shapes):
        raise ValueError(f"no form {shape} of the name rule {rule_id!r}")
    parts = generator.shapes[shape].parts
    if not 0 <= index < len(parts) or parts[index].kind != "meaning":
        raise ValueError("that part doesn't take a meaning")
    text, after_of = _drop_fixed(language, rule_id, shape, text)
    ending = parts[index].ending
    if ending:
        # the part's own ending says that much ("town of"): only the rest
        # is translated, and the ending is kept (owner, 2026-11-05)
        said = {w for w in _words(ending.lower()) if w not in _FUNCTION}
        kept = [w for w in _words(text) if w.lower() not in said]
        while kept and kept[0].lower() in _FUNCTION:
            kept.pop(0)
        text = " ".join(kept) or text
    (phrase,) = await split_meaning(client, language, text, [parts[index]], reply=reply)
    if ending:
        phrase = phrase.model_copy(update={"ending": ending, "of": False})
    if after_of:
        grammar = language.name_grammar
        the = grammar.of.the if grammar is not None and grammar.of else False
        phrase = phrase.model_copy(update={"of": False, "the": the})
    if not phrase.noun:
        return {"shape": shape, "index": index, "rolls": []}
    words, new, options = await resolve_words(
        client, language, _meanings(phrase), what=text, reply=reply
    )
    rolls = _phrase_rolls(language, phrase, words, new, options)
    return {"shape": shape, "index": index, "rolls": [r.model_dump() for r in rolls]}


async def suggest_for(
    view: WorldView,
    client,
    language_id: str,
    rule_id: str,
    thing_id: str,
    *,
    shape: int | None = None,
    reply: str | None = None,
    pinned: dict[int, str] | None = None,
) -> dict:
    """✨ Suggest meanings from its facts: `{shape, fills}`, each meaning
    part of the form (by index) with rolls built from the meaning the
    model suggests for the entry; the other parts are left alone (round
    4). A form without meaning parts gets no fills."""

    state = view.thing(language_id)
    thing = view.thing(thing_id)
    if state is None or state.kind != "language" or thing is None:
        raise ValueError("there's no such entry or language")
    language = language_of(state)
    generator = next((g for g in language.generators if g.id == rule_id), None)
    if generator is None or not generator.shapes:
        return {"shape": shape, "fills": {}}
    shape = shape if shape is not None and 0 <= shape < len(generator.shapes) else 0
    slots = [
        (i, p)
        for i, p in enumerate(generator.shapes[shape].parts)
        if p.kind == "meaning"
    ]
    if not slots:
        return {"shape": shape, "fills": {}}
    name = view.name_of(thing_id) or ""
    facts = [f.text for f in thing.facts][:20]
    phrases = await suggest_phrases(
        client, language, [p for _i, p in slots], facts, name=name, reply=reply
    )
    fills: dict[str, list] = {}
    for (i, _p), phrase in zip(slots, phrases):
        if phrase is None or not phrase.noun:
            continue
        words, new, options = await resolve_words(
            client, language, _meanings(phrase), what=name, reply=reply
        )
        rolls = _phrase_rolls(language, phrase, words, new, options)
        fills[str(i)] = [r.model_dump() for r in rolls]
    return {"shape": shape, "fills": fills}
