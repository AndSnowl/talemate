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
    "is_main",
    "connections_of",
    "fact_role",
    "kept_title",
    "parent_for",
    "person_text",
    "pick_rule",
    "role_matches",
    "roll_pet_name",
    "people_rows",
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
# (a filing's role is the person's in the parent's entry: "daughter")
PARENT_WORDS: tuple[str, ...] = (
    "son of",
    "daughter of",
    "child of",
    "son",
    "daughter",
    "child",
    "parent",
    "mother",
    "father",
)
# a part's labels that mean the given name (a parent with no parts gives
# its first word for one)
GIVEN_LABELS = frozenset({"given", "first", "forename", "personal"})
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
    # the entry's kind; "" when not known
    kind: str = ""


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
    for text, refs in facts:
        for ref in refs:
            pairs.append((ref, fact_role(text, ref, refs)))
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
                kind=state.kind,
            )
        )
    return found


def fact_role(text: str, ref: str, refs: list[str]) -> str:
    """A relationship fact's words for one entry it links: the whole text
    when it links one; otherwise the words from the link before it to the
    end of its own (final review I5: "rival of Varro, and the daughter of
    Eilhaud" makes only Eilhaud a parent)."""

    if len(set(refs)) <= 1:
        return text
    links = list(re.finditer(r"\[\[thing:([0-9a-f]{32})\|[^\]]*\]\]", text))
    for i, link in enumerate(links):
        if link.group(1) == ref:
            start = links[i - 1].end() if i else 0
            return text[start : link.end()]
    return text


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


def _building_blocks(language: Language) -> set[str]:
    """The rules other rules use as a part (or roll a connection from):
    pieces of a name, never a person's whole name."""

    return {
        part.rule
        for generator in language.generators
        for shape in generator.shapes
        for part in shape.parts
        if part.kind in ("rule", "connection") and part.rule
    }


def pick_rule(language: Language, built_as: dict[str, str]) -> GeneratorDef:
    """The people rule for who the person is: the one whose `for_person`
    matches most, none contradicted. A rule another rule uses as a part is
    a piece of a name, never picked while a whole-name rule fits (probe
    4b-2); on a tie, plain before composed."""

    from talemate.languages.naming import generator_for

    blocks = _building_blocks(language)
    best: tuple[int, int, int, int, GeneratorDef] | None = None
    for generator in _people_rules(language):
        wanted = generator.for_person
        if any(k in built_as and built_as[k] != v for k, v in wanted.items()):
            continue
        if any(k not in built_as for k in wanted):
            continue
        passes_down = any(
            part.kind == "connection"
            for shape in generator.shapes
            for part in shape.parts
        )
        key = (
            0 if generator.id in blocks else 1,
            len(wanted),
            # a rule that passes a name down wins a tie (final review I6)
            1 if passes_down else 0,
            0 if not generator.shapes else -1,
        )
        if best is None or key > best[:4]:
            best = (*key, generator)
    if best is not None:
        return best[4]
    return generator_for(language, "character")


# the kinds a parent can be (a realm "daughter of the sovereign" names
# isn't one, acceptance 4b-2)
PARENT_KINDS = ("character", "being")


# the uses whose rules are never a whole name by default (languages 4c)
PIECE_USES = ("words", "pet names")


def is_main(language: Language, generator: GeneratorDef) -> bool:
    """A main rule (a whole name: a person's, a place's…) or a piece other
    rules are made of: the file's say first; else a rule another rule uses
    as a part, or one for ordinary words or pet names, is a piece."""

    if generator.main is not None:
        return generator.main
    if generator.use in PIECE_USES:
        return False
    return generator.id not in _building_blocks(language)


def _parent_like(connection: Connection) -> bool:
    if connection.kind and connection.kind not in PARENT_KINDS:
        return False
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
            try:
                return _apply_changes(form.changes, vowels_of(language), text)
            except ValueError:
                # a change the engine can't read (the check names it):
                # the text as it is, never a broken name
                return text
    return text


def with_ending(language: Language, part: NamePart, text: str) -> str:
    """`text` with the part's ending ("small, dear"), when the language's
    grammar for names has it (owner, 2026-11-05: Zhelvan's pet names)."""

    from talemate.languages.name_grammar import apply_ending, vowels_of

    grammar = language.name_grammar
    if not text or not part.ending or grammar is None:
        return text
    try:
        return apply_ending(grammar, vowels_of(language), text, part.ending)
    except (KeyError, ValueError):
        return text


def inherited_text(part: NamePart, parent: Connection) -> str:
    """What a connection part takes from `parent`: its part by label; for
    a parent with no parts, the first word for a given name, else the last
    (a family or house name); with no label, its whole name."""

    if not part.take:
        return parent.name
    if part.take in parent.parts:
        return parent.parts[part.take]
    words = parent.name.split()
    if not words:
        return ""
    return words[0] if part.take.lower() in GIVEN_LABELS else words[-1]


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
        # the parent's own part that the child's takes (final review I4)
        at = _label_index(language, stub_rule, part.take or label)
        if at is None:
            stub = build_person_name(
                language,
                PersonContext(built_as=wanted),
                rule_id=stub_rule.id,
                rng=rng,
                offer_missing=False,
            )
            # no slot for it: a given name is the stub's name, anything
            # else follows a rolled one
            given = (part.take or label).lower() in GIVEN_LABELS
            name = (
                parts[index].text
                if given
                else f"{stub.name} {parts[index].text}".strip()
            )
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
    # a rule that gives the name back as it is makes no pet name
    # (acceptance 4b-2)
    if not name or name in own.values():
        return None
    return name, rule.id


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


def people_rows(language: Language) -> dict:
    """A language's people's names for the Names chapter (languages 4b-2):
    its choices, kept titles and address rows, each row with an example
    built from a sample person (the first rule that's for someone, rolled
    with its own choices); a use with nothing to show reads "[use]"."""

    people = language.people_names
    for_someone = next((g for g in _people_rules(language) if g.for_person), None)
    built_as = dict(for_someone.for_person) if for_someone else choose(language, {})
    rng = random.Random(0)
    sample = (
        build_person_name(
            language,
            PersonContext(built_as=built_as),
            rule_id=for_someone.id if for_someone else None,
            rng=rng,
            offer_missing=False,
        )
        if _people_rules(language)
        else None
    )
    parts = {p.label: p.text for p in sample.parts} if sample else {}
    pet = roll_pet_name(language, parts, rng) if parts else None

    def example(row: AddressRow) -> str:
        words = []
        for use in row.uses:
            if use == "pet name":
                words.append(pet[0] if pet else "[pet name]")
            elif use in parts and parts[use]:
                words.append(parts[use])
            else:
                words.append(f"[{use}]")
        return " ".join(words)

    return {
        "has_people": people is not None,
        "choices": dict(people.choices) if people else {},
        "kept_titles": [t.model_dump() for t in people.kept_titles] if people else [],
        "address": [
            {**row.model_dump(), "example": example(row)}
            for row in (people.address if people else [])
        ],
        "sample": sample.name if sample else "",
    }
