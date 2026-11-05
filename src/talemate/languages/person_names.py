"""People's names (languages 4b-2): a person's name built from their
language's rules, with parts inherited from their real connections, forms
by who they are (sex, rank), and the rest rolled or built from a meaning.
Also pet names, forms of address and kept titles. No model is asked:
sex, rank and a meaning come in as words, and the engine builds."""

from __future__ import annotations

import random
import re
from typing import Literal

from pydantic import BaseModel, Field

from talemate.languages.models import (
    AddressRow,
    GeneratorDef,
    KeptTitle,
    Language,
    NamePart,
)

__all__ = [
    "Connection",
    "MissingParent",
    "NamedPart",
    "PersonContext",
    "PersonName",
    "ROLE_SEX",
    "address_row",
    "build_person_name",
    "choose",
    "connections_of",
    "kept_title",
    "parent_for",
    "person_text",
    "pick_rule",
    "role_matches",
    "roll_pet_name",
    "stored_written",
    "written",
]

# a role word's sex, for telling a mother from a father
ROLE_SEX: dict[str, str] = {
    "mother": "woman",
    "father": "man",
    "daughter": "woman",
    "son": "man",
}
# the words that make a connection a parent's
PARENT_WORDS: tuple[str, ...] = (
    "son of",
    "daughter of",
    "child of",
    "parent",
    "mother",
    "father",
)
# the uses a people rule has
PEOPLE_USES = ("character", "people")


class Connection(BaseModel):
    """An entry the person is connected to: its role (a filing's role, or
    a relationship fact's text), its name, and its own name parts and
    "built as" when it has them."""

    role: str
    thing_id: str
    name: str
    parts: dict[str, str] = Field(default_factory=dict)
    built_as: dict[str, str] = Field(default_factory=dict)


class PersonContext(BaseModel):
    """Who a name is being built for: what they're built as, who they're
    connected to, and their own parts (for a pet name)."""

    thing_id: str | None = None
    built_as: dict[str, str] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    own: dict[str, str] = Field(default_factory=dict)


class NamedPart(BaseModel):
    label: str
    text: str
    source: Literal["rolled", "typed", "meaning", "inherited", "word"] = "rolled"
    from_id: str = ""
    from_role: str = ""
    working: list = Field(default_factory=list)


class MissingParent(BaseModel):
    """A parent the name implies but the world doesn't have: the rolled
    part, and a full name for the stub, built with that part pinned."""

    role: str
    label: str
    text: str
    name: str
    sex: str


class PersonName(BaseModel):
    rule_id: str
    shape: int
    parts: list[NamedPart]
    built_as: dict[str, str]
    name: str
    missing: list[MissingParent] = Field(default_factory=list)


def role_matches(role_words: list[str], role: str) -> bool:
    """Whether any of `role_words` is a whole word (or words) of `role`."""

    text = role.lower()
    return any(
        re.search(rf"\b{re.escape(word.strip().lower())}\b", text)
        for word in role_words
        if word.strip()
    )


def _parts_of(state) -> tuple[dict[str, str], dict[str, str]]:
    stored = state.fields.get("name_parts")
    if not isinstance(stored, dict):
        return {}, {}
    parts = {
        str(p.get("label")): str(p.get("text"))
        for p in stored.get("parts") or []
        if isinstance(p, dict) and p.get("label")
    }
    return parts, dict(stored.get("built_as") or {})


def connections_of(
    view,
    thing_id: str | None,
    filings: list[tuple[str, str | None]],
    facts: list[tuple[str, list[str]]],
) -> list[Connection]:
    """The person's connections: their filings (`(target_id, role)`), and
    each entry a relationship fact links (`(text, refs)`, the text as its
    role). The person themself, and entries the world no longer has, are
    left out."""

    found: list[Connection] = []
    pairs = [(target, role or "") for target, role in filings]
    pairs += [(ref, text) for text, refs in facts for ref in refs]
    for target, role in pairs:
        if not target or target == thing_id:
            continue
        state = view.thing(target)
        if state is None:
            continue
        parts, built_as = _parts_of(state)
        found.append(
            Connection(
                role=role,
                thing_id=target,
                name=str(state.fields.get("name") or ""),
                parts=parts,
                built_as=built_as,
            )
        )
    return found


def choose(language: Language, read: dict[str, str]) -> dict[str, str]:
    """Each choice the language lists, as read when it's one of them (any
    case), else the list's first; a language with no choices keeps what
    was read."""

    choices = language.people_names.choices if language.people_names else {}
    if not choices:
        return {k: v for k, v in read.items() if v}
    out: dict[str, str] = {}
    for key, values in choices.items():
        if not values:
            continue
        wanted = str(read.get(key) or "").strip().lower()
        out[key] = next((v for v in values if v.lower() == wanted), values[0])
    return out


def _people_rules(language: Language) -> list[GeneratorDef]:
    return [g for g in language.generators if g.use in PEOPLE_USES]


def pick_rule(language: Language, built_as: dict[str, str]) -> GeneratorDef:
    """The people rule for who the person is: the one whose `for_person`
    matches most, none contradicted; plain before composed on a tie."""

    from talemate.languages.naming import generator_for

    best: tuple[int, int, GeneratorDef] | None = None
    for generator in _people_rules(language):
        wanted = generator.for_person
        if any(k in built_as and built_as[k] != v for k, v in wanted.items()):
            continue
        if any(k not in built_as for k in wanted):
            continue
        key = (len(wanted), 0 if not generator.shapes else -1)
        if best is None or key > best[:2]:
            best = (*key, generator)
    if best is not None:
        return best[2]
    return generator_for(language, "character")


def _parent_like(connection: Connection) -> bool:
    return role_matches(list(PARENT_WORDS), connection.role)


def parent_for(part: NamePart, ctx: PersonContext) -> Connection | None:
    """The connection a part takes from. For each of its role words, in
    the language's order: a connection whose role says it, else a parent
    whose own "built as" sex fits it. Then, for a parent's part, the first
    parent."""

    parents = [c for c in ctx.connections if _parent_like(c)]
    for word in part.roles:
        for connection in ctx.connections:
            if role_matches([word], connection.role):
                return connection
        sex = ROLE_SEX.get(word.lower())
        for connection in parents:
            if sex and connection.built_as.get("sex") == sex:
                return connection
    parental = any(w.lower() in ROLE_SEX or w.lower() == "parent" for w in part.roles)
    return parents[0] if parental and parents else None


def person_text(
    language: Language, part: NamePart, text: str, built_as: dict[str, str]
) -> str:
    """`text` in the part's form for who the person is: the first form
    whose `when` all match."""

    from talemate.languages.name_grammar import _apply_changes, vowels_of

    if not text:
        return text
    for form in part.person_forms:
        if all(built_as.get(k) == v for k, v in form.when.items()):
            return _apply_changes(form.changes, vowels_of(language), text)
    return text


def inherited_text(part: NamePart, parent: Connection) -> str:
    """What a connection part takes from `parent`: its part by label, else
    its last word for a labelled part, else its whole name."""

    if not part.take:
        return parent.name
    if part.take in parent.parts:
        return parent.parts[part.take]
    words = parent.name.split()
    return words[-1] if words else ""


def written(language: Language, rule_id: str, shape: int, texts: list[str]) -> str:
    """The name as written: the parts' texts joined, a fixed word written
    in English where its part says so; missing parts left out."""

    from talemate.languages.composed import MISSING_RULE, _generator

    generator = _generator(language, rule_id)
    parts: list[NamePart | None] = []
    if (
        generator is not None
        and generator.shapes
        and 0 <= shape < len(generator.shapes)
    ):
        parts = list(generator.shapes[shape].parts)
    out: list[str] = []
    for index, text in enumerate(texts):
        part = parts[index] if index < len(parts) else None
        if part is not None and part.kind == "word" and part.english:
            text = part.english
        if text and text != MISSING_RULE:
            out.append(text)
    return " ".join(out)


def _meaning_built(language: Language, meaning: str, rng: random.Random):
    """A meaning built in the language without the model: each word from
    the dictionary, a random dictionary noun where it has none."""

    from talemate.languages.name_grammar import build_phrase, lookup_word, real_words
    from talemate.languages.naming_meaning import read_english

    phrase = read_english(meaning, language=language)
    if not phrase.noun:
        return None
    nouns = real_words(language, "noun")
    words: dict[str, str] = {}
    for wanted in [phrase.noun, *phrase.describing]:
        entry = lookup_word(language, wanted)
        if entry is None:
            if not nouns:
                return None
            entry = rng.choice(nouns)
        words[wanted] = entry.word
    return build_phrase(language, phrase, words)


def build_person_name(
    language: Language,
    ctx: PersonContext,
    *,
    rule_id: str | None = None,
    shape: int | None = None,
    pinned: dict[int, str] | None = None,
    meaning: str = "",
    rng: random.Random | None = None,
    offer_missing: bool = True,
) -> PersonName:
    """A person's name: the rule for who they are (unless given), each
    part's first roll, inherited parts from their connections, `meaning`
    built into the first meaning part, and the parents the name implies
    but the world doesn't have."""

    from talemate.languages.composed import roll_parts

    rng = rng if rng is not None else random.Random()
    built_as = choose(language, ctx.built_as)
    ctx = ctx.model_copy(update={"built_as": built_as})
    rule = rule_id or pick_rule(language, built_as).id
    shape, rolls = roll_parts(
        language, rule, pinned=pinned, shape=shape, rng=rng, person=ctx
    )
    parts: list[NamedPart] = []
    meaning_done = False
    for roll in rolls:
        first = roll.rolls[0] if roll.rolls else None
        part = NamedPart(
            label=roll.label,
            text=first.text if first else "",
            source=roll.source,
            from_id=roll.from_id,
            from_role=roll.from_role,
            working=list(first.parts) if first else [],
        )
        if roll.kind == "meaning" and meaning and not meaning_done and not roll.pinned:
            meaning_done = True
            built = _meaning_built(language, meaning, rng)
            if built is not None:
                part = part.model_copy(
                    update={
                        "text": built.text,
                        "source": "meaning",
                        "working": built.parts,
                    }
                )
        parts.append(part)
    missing = (
        _missing(language, rule, shape, parts, built_as, rng) if offer_missing else []
    )
    return PersonName(
        rule_id=rule,
        shape=shape,
        parts=parts,
        built_as=built_as,
        name=written(language, rule, shape, [p.text for p in parts]),
        missing=missing,
    )


def _missing(
    language: Language,
    rule_id: str,
    shape: int,
    parts: list[NamedPart],
    built_as: dict[str, str],
    rng: random.Random,
) -> list[MissingParent]:
    from talemate.languages.composed import _generator

    generator = _generator(language, rule_id)
    if generator is None or not generator.shapes:
        return []
    found: list[MissingParent] = []
    for index, part in enumerate(generator.shapes[shape].parts):
        if part.kind != "connection" or parts[index].source == "inherited":
            continue
        role = next((w for w in part.roles if w.lower() in ROLE_SEX), None)
        if role is None or not parts[index].text:
            continue
        sex = ROLE_SEX[role.lower()]
        wanted = {**built_as, "sex": sex}
        stub_rule = pick_rule(language, choose(language, wanted))
        label = parts[index].label
        at = _label_index(language, stub_rule, label)
        if at is None:
            stub = build_person_name(
                language,
                PersonContext(built_as=wanted),
                rule_id=stub_rule.id,
                rng=rng,
                offer_missing=False,
            )
            name = f"{stub.name} {parts[index].text}".strip()
        else:
            stub = build_person_name(
                language,
                PersonContext(built_as=wanted),
                rule_id=stub_rule.id,
                shape=at[0],
                pinned={at[1]: parts[index].text},
                rng=rng,
                offer_missing=False,
            )
            name = stub.name
        found.append(
            MissingParent(
                role=role, label=label, text=parts[index].text, name=name, sex=sex
            )
        )
    return found


def _label_index(
    language: Language, generator: GeneratorDef, label: str
) -> tuple[int, int] | None:
    from talemate.languages.composed import _label

    for s, shape in enumerate(generator.shapes):
        for i, part in enumerate(shape.parts):
            if part.kind != "word" and _label(language, part) == label:
                return s, i
    return None


def stored_written(view, stored: object) -> str | None:
    """The name a person's stored `name_parts` write, by their language;
    None when they can't be read (no such language)."""

    from talemate.languages.entry import language_of

    if not isinstance(stored, dict):
        return None
    state = view.thing(str(stored.get("language") or ""))
    if state is None or state.kind != "language":
        return None
    texts = [str(p.get("text") or "") for p in stored.get("parts") or []]
    return written(
        language_of(state),
        str(stored.get("rule") or ""),
        int(stored.get("shape") or 0),
        texts,
    )


def roll_pet_name(
    language: Language, own: dict[str, str], rng: random.Random
) -> tuple[str, str] | None:
    """`(pet name, rule id)` from the language's first pet-name rule, built
    from the person's own parts; None without one."""

    from talemate.languages.composed import roll_parts

    rule = next((g for g in language.generators if g.use == "pet names"), None)
    if rule is None:
        return None
    shape, rolls = roll_parts(language, rule.id, rng=rng, person=PersonContext(own=own))
    texts = [r.rolls[0].text if r.rolls else "" for r in rolls]
    name = written(language, rule.id, shape, texts)
    return (name, rule.id) if name else None


def address_row(language: Language, role: str) -> AddressRow | None:
    """The address row for a relationship's role words, else the default
    row."""

    rows = language.people_names.address if language.people_names else []
    for row in rows:
        if role_matches(row.roles, role):
            return row
    return next((row for row in rows if row.default), None)


def kept_title(language: Language, english: str) -> KeptTitle | None:
    """The language's own word for an English title, when it keeps one."""

    wanted = english.strip().lower()
    titles = language.people_names.kept_titles if language.people_names else []
    return next((t for t in titles if t.meaning.strip().lower() == wanted), None)
