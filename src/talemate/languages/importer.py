"""Bringing a language into the world, as a new entry or a new version of
one, and taking it back out (languages 3a).

- `parse_language_text` reads a whole file or a chat reply with prose or a
  code fence around the JSON: the first balanced JSON object that is a
  language file, or a bare language (wrapped).
- `preview_import` runs the shared check and, for a new version, the diff.
  Words already used as entries' names are fixed: a new version that drops
  or redefines one gets it back, listed in `kept_used`.
- `apply_import` writes it, refusing anything with a blocking problem. A new
  version keeps the entry's own name.
"""

from __future__ import annotations

import re

import json

from pydantic import BaseModel, ValidationError

from talemate.languages.changes import merge_change
from talemate.languages.check import CheckReport, check_language
from talemate.languages.entry import fields_of, language_of, languages, used_words
from talemate.languages.models import DictionaryEntry, Language, LanguageFile
from talemate.world.store import Revision
from talemate.world.view import WorldView

__all__ = [
    "ImportPreview",
    "LanguageDiff",
    "LanguageParseError",
    "apply_import",
    "export_language",
    "parse_language_text",
    "preview_import",
]


class LanguageParseError(ValueError):
    """The text holds no language the app can read."""


class PhraseLine(BaseModel):
    original: str
    translation: str


class PhraseChange(BaseModel):
    """One category of phrases that changed: all of it, before and after."""

    category: str
    before: list[PhraseLine] = []
    after: list[PhraseLine] = []


class LanguageDiff(BaseModel):
    words_added: list[str] = []
    words_removed: list[str] = []
    words_changed: list[str] = []
    phrases_added: list[str] = []
    phrases_removed: list[str] = []
    phrases_changed: list[str] = []
    phrase_changes: list[PhraseChange] = []
    generators_changed: bool = False
    # name rules the new version doesn't have (by name), never dropped
    # silently
    rules_removed: list[str] = []
    grammar_added: list[str] = []
    grammar_changed: list[str] = []
    grammar_removed: list[str] = []
    # how it sounds, before and after, when it changed
    sound_before: str | None = None
    sound_after: str | None = None
    kept_used: list[str] = []
    # a change's parts the owner had also edited meanwhile: theirs stayed
    kept_edits: list[str] = []
    samples_before: dict[str, list[str]] = {}
    samples_after: dict[str, list[str]] = {}


class ImportPreview(BaseModel):
    file: LanguageFile
    report: CheckReport
    diff: LanguageDiff | None = None


def _json_objects(text: str):
    """Every balanced top-level `{...}` in `text` that parses as JSON, in
    order (brackets inside strings don't count)."""

    start = text.find("{")
    while start != -1:
        depth, in_string, escape = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        # a model's reply may break a line inside a string
                        yield json.loads(text[start : i + 1], strict=False)
                    except ValueError:
                        pass
                    break
        start = text.find("{", start + 1) if depth else text.find("{", i + 1)


def parse_language_text(text: str) -> LanguageFile:
    """The language in `text`: a file, or a reply with prose around it."""

    problem: str | None = None
    for data in _json_objects(text):
        if not isinstance(data, dict):
            continue
        try:
            return LanguageFile.model_validate(data)
        except ValidationError as exc:
            if "language" in data:
                problem = problem or _where(exc)
        try:
            return LanguageFile(language=Language.model_validate(data))
        except ValidationError as exc:
            if "name" in data and "level" in data:
                problem = problem or _where(exc)
            continue
    if problem:
        # a language file was there, with something that doesn't fit:
        # say where, so whoever made it can fix it
        raise LanguageParseError(f"The language file has a problem: {problem}")
    raise LanguageParseError(
        "There's no language in this text. Paste the whole file the assistant made."
    )


def _where(exc: ValidationError) -> str:
    """The first problem in `exc`, as "where: what"."""

    error = exc.errors()[0]
    where = " → ".join(str(part) for part in error.get("loc", ()))
    return f"{where}: {error.get('msg', 'not valid')}"


def _by_word(language: Language) -> dict[str, DictionaryEntry]:
    return {e.word.lower(): e for e in language.dictionary}


def _meaning_keys(entry: DictionaryEntry) -> set[str]:
    """A word's meanings as compared: order and case don't count."""

    return {m.lower() for m in entry.meanings}


def _diff(
    old: Language, new: Language, kept: list[str], kept_edits: list[str] = ()
) -> LanguageDiff:
    old_words, new_words = _by_word(old), _by_word(new)
    old_sections = {s.title.lower(): s for s in old.grammar}
    new_sections = {s.title.lower(): s for s in new.grammar}
    new_rules = {g.id for g in new.generators}
    old_phrases = {p.id: p for p in old.phrases}
    new_phrases = {p.id: p for p in new.phrases}

    def lines(lang: Language, category: str) -> list[PhraseLine]:
        return [
            PhraseLine(original=p.original, translation=p.translation)
            for p in lang.phrases
            if p.category == category
        ]

    touched = {
        p.category
        for p in [*old.phrases, *new.phrases]
        if old_phrases.get(p.id) != new_phrases.get(p.id)
    }
    # in the order the language lists them, the new version's first
    categories = list(dict.fromkeys(p.category for p in [*new.phrases, *old.phrases]))

    def rules(lang: Language) -> str:
        return json.dumps(
            [lang.categories, [g.model_dump() for g in lang.generators]], sort_keys=True
        )

    return LanguageDiff(
        words_added=[w for w in new_words if w not in old_words],
        words_removed=[w for w in old_words if w not in new_words],
        words_changed=[
            w
            for w in new_words
            if w in old_words
            and _meaning_keys(new_words[w]) != _meaning_keys(old_words[w])
        ],
        phrases_added=[i for i in new_phrases if i not in old_phrases],
        phrases_removed=[i for i in old_phrases if i not in new_phrases],
        phrases_changed=[
            i
            for i in new_phrases
            if i in old_phrases and new_phrases[i] != old_phrases[i]
        ],
        phrase_changes=[
            PhraseChange(category=c, before=lines(old, c), after=lines(new, c))
            for c in categories
            if c in touched
        ],
        generators_changed=rules(old) != rules(new),
        rules_removed=[g.name for g in old.generators if g.id not in new_rules],
        grammar_added=[
            s.title for k, s in new_sections.items() if k not in old_sections
        ],
        grammar_changed=[
            s.title
            for k, s in new_sections.items()
            if k in old_sections and s != old_sections[k]
        ],
        grammar_removed=[
            s.title for k, s in old_sections.items() if k not in new_sections
        ],
        sound_before=old.sound if old.sound != new.sound else None,
        sound_after=new.sound if old.sound != new.sound else None,
        kept_used=kept,
        kept_edits=list(kept_edits),
        samples_before=check_language(old).samples,
        samples_after=check_language(new).samples,
    )


def _keep_used(
    old: Language, new: Language, used: set[str]
) -> tuple[Language, list[str]]:
    """`new` with every used word's old meanings kept: a word the new
    version drops is put back, and one it redefines keeps its old meanings
    first, then the new ones (adding a meaning never replaces one). Also
    which words lost something and were kept."""

    old_words, new_words = _by_word(old), _by_word(new)
    kept: list[str] = []
    merged: dict[str, DictionaryEntry] = {}
    for w in sorted(used):
        if w not in old_words:
            continue
        before = old_words[w]
        after = new_words.get(w)
        if after is None:
            kept.append(w)
            merged[w] = before
            continue
        if not _meaning_keys(before) <= _meaning_keys(after):
            kept.append(w)
        have = _meaning_keys(before)
        merged[w] = after.model_copy(
            update={
                "meanings": [
                    *before.meanings,
                    *(m for m in after.meanings if m.lower() not in have),
                ],
                "part": before.part or after.part,
                "notes": before.notes or after.notes,
            }
        )
    if not merged:
        return new, []
    dictionary = [merged.pop(e.word.lower(), e) for e in new.dictionary]
    dictionary += list(merged.values())
    return new.model_copy(update={"dictionary": dictionary}), kept


def preview_import(
    view: WorldView,
    text: str,
    target_id: str | None = None,
    base_text: str | None = None,
) -> ImportPreview:
    """What importing `text` would give: the file, its check and, onto
    `target_id`, the diff. With `base_text` (the version a change was
    briefed on), `text` is a change: it's merged onto the language as it is
    now, keeping the owner's edits made meanwhile (`merge_change`)."""

    file = parse_language_text(text)
    diff = None
    if target_id is not None:
        state = view.thing(target_id)
        if state is None or state.kind != "language":
            raise ValueError("there's no language to update")
        old = language_of(state, view)
        changed, kept_edits = file.language, []
        if base_text is not None:
            merged = merge_change(parse_language_text(base_text).language, changed, old)
            changed, kept_edits = merged.language, merged.kept_edits
        new, kept = _keep_used(old, changed, used_words(view, target_id))
        file = file.model_copy(update={"language": new})
        diff = _diff(old, new, kept, kept_edits)
    return ImportPreview(file=file, report=check_language(file.language), diff=diff)


def _language_named(view: WorldView, name: str | None) -> str | None:
    if not name:
        return None
    wanted = name.strip().lower()
    for state in languages(view):
        if str(state.fields.get("name", "")).strip().lower() == wanted:
            return state.id
    return None


def _about(name: str, description: str) -> str:
    """A new language's own fact: what it is, and its file's description's
    first sentence."""

    first = re.split(r"(?<=[.!?])\s+", " ".join(description.split()), maxsplit=1)[0]
    about = f"{name} is a language of this world."
    return f"{about} {first}" if first else about


def apply_import(
    rev: Revision, view: WorldView, preview: ImportPreview, target_id: str | None = None
) -> str:
    """Write the previewed language as a new entry, or onto `target_id`;
    its parent and similar languages are linked by name when they exist."""

    if not preview.report.ok:
        raise ValueError("this language has problems that must be fixed first")
    language = preview.file.language
    fields: dict[str, object] = fields_of(language)
    parent = _language_named(view, preview.file.parent)
    if parent is not None:
        fields["descends_from"] = parent
    similar = []
    for link in language.similar:
        other = _language_named(view, link.name)
        if other is not None and other != target_id:
            similar.append({"target": other, "degree": link.degree})
    if similar:
        fields["similar"] = similar
    if target_id is None:
        made = rev.create_thing("language", {"name": language.name, **fields})
        # the model knows it's a language, not a thing (languages 4a revised)
        rev.add_fact(made, "general", _about(language.name, preview.file.description))
        return made
    for field, value in fields.items():
        rev.set_field(target_id, field, value, None)
    return target_id


def export_language(view: WorldView, language_id: str) -> LanguageFile:
    """The language entry as a file."""

    state = view.thing(language_id)
    if state is None or state.kind != "language":
        raise ValueError("there's no such language")
    parent_id = state.fields.get("descends_from")
    parent = view.thing(parent_id) if isinstance(parent_id, str) else None
    return LanguageFile(
        language=language_of(state, view),
        parent=str(parent.fields.get("name")) if parent is not None else None,
    )
