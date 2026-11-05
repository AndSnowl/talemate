"""Merging a change onto a language as it is now (languages 3b-2).

A change is briefed on one version of a language (the base) and takes
minutes; meanwhile the owner may edit it. The change is applied only where
the owner left things as they were. Where both touched the same word,
phrase, grammar section, name rule or setting, the owner's version stays
and is reported as a kept edit."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from pydantic import BaseModel

from talemate.languages.models import Language

__all__ = ["MergeResult", "merge_change"]


class MergeResult(BaseModel):
    language: Language
    kept_edits: list[str]


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    dump = getattr(a, "model_dump", None)
    if dump is not None:
        return dump(mode="json") == b.model_dump(mode="json")
    return a == b


def _pick(base: Any, change: Any, current: Any) -> tuple[Any, bool]:
    """One part's merged value, and whether the owner's edit was kept over
    the change."""

    if _same(change, base):
        return current, False
    if _same(current, base) or _same(current, change):
        return change, False
    return current, True


def _keyed(
    items: Iterable[Any], key: Callable[[Any], str]
) -> dict[tuple[str, int], Any]:
    """`items` by (key, occurrence): two words spelled alike, or two
    sections with one title, are the first and the second, each merged
    with its counterpart, so neither is lost."""

    seen: dict[str, int] = {}
    keyed = {}
    for item in items:
        k = key(item)
        keyed[(k, seen.get(k, 0))] = item
        seen[k] = seen.get(k, 0) + 1
    return keyed


def _merge_keyed(
    base: Iterable[Any],
    change: Iterable[Any],
    current: Iterable[Any],
    key: Callable[[Any], str],
    label: Callable[[str], str],
    kept: list[str],
) -> list[Any]:
    b, c, u = _keyed(base, key), _keyed(change, key), _keyed(current, key)
    order = list(u) + [k for k in c if k not in u]
    merged = []
    for k in order:
        value, kept_edit = _pick(b.get(k), c.get(k), u.get(k))
        if kept_edit:
            kept.append(label(k[0]))
        if value is not None:
            merged.append(value)
    return merged


def merge_change(base: Language, change: Language, current: Language) -> MergeResult:
    """`change` (briefed on `base`) applied onto `current`, part by part:
    words by word, phrases by id, grammar sections by title, name rules by
    id, sound groups by key, and the settings one by one. The name and
    depth stay current's."""

    kept: list[str] = []
    words = _merge_keyed(
        base.dictionary, change.dictionary, current.dictionary,
        lambda e: e.word.lower(), lambda k: f"word {k}", kept,
    )  # fmt: skip
    phrases = _merge_keyed(
        base.phrases, change.phrases, current.phrases,
        lambda p: p.id, lambda k: f"phrase {k}", kept,
    )  # fmt: skip
    titles = {s.title.lower(): s.title for s in [*current.grammar, *change.grammar]}
    grammar = _merge_keyed(
        base.grammar, change.grammar, current.grammar,
        lambda s: s.title.lower(), lambda k: f"grammar {titles.get(k, k)}", kept,
    )  # fmt: skip
    generators = _merge_keyed(
        base.generators, change.generators, current.generators,
        lambda g: g.id, lambda k: f"name rule {k}", kept,
    )  # fmt: skip
    categories = {}
    for k in list(current.categories) + [
        k for k in change.categories if k not in current.categories
    ]:
        value, kept_edit = _pick(
            base.categories.get(k), change.categories.get(k), current.categories.get(k)
        )
        if kept_edit:
            kept.append(f"sound group {k}")
        if value is not None:
            categories[k] = value
    settings = {}
    for field, label in (
        ("sound", "how it sounds"),
        ("syllable_notes", "syllable notes"),
        ("flavour", "sounds like"),
        ("writable", "written"),
        ("name_grammar", "grammar for names"),
        ("people_names", "people's names"),
    ):
        value, kept_edit = _pick(
            getattr(base, field), getattr(change, field), getattr(current, field)
        )
        if kept_edit:
            kept.append(label)
        settings[field] = value
    language = current.model_copy(
        update={
            "dictionary": words,
            "phrases": phrases,
            "grammar": grammar,
            "generators": generators,
            "categories": categories,
            **settings,
        }
    )
    return MergeResult(language=language, kept_edits=kept)
