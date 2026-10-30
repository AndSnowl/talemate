"""The name lists (languages 4a): names to replace (real names, AI
clichés, stock titles) and names to keep. The app's lists ship in
`data/name_lists.json` and, once edited, live in the config; each world
adds its own and can turn the app's rows off (`World.name_lists`)."""

from __future__ import annotations

import json
from fnmatch import fnmatchcase
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from talemate.config.schema import NameListsConfig
from talemate.config.state import get_config, save_config

__all__ = [
    "LIST_KINDS",
    "ListRow",
    "NameLists",
    "WorldNameLists",
    "app_lists",
    "edit",
    "effective",
    "match",
    "rows",
]

LIST_KINDS = ("real", "cliche", "title", "keep")
ACTIONS = ("add", "remove", "make_global", "turn_off", "turn_on", "remove_everywhere")
SHIPPED = Path(__file__).resolve().parents[1] / "data" / "name_lists.json"


class NameLists(BaseModel):
    real: list[str] = []
    cliche: list[str] = []
    title: list[str] = []
    keep: list[str] = []


class WorldNameLists(NameLists):
    # the app's rows turned off in this world, as "<kind>:<name>"
    off: list[str] = []


class ListRow(BaseModel):
    name: str
    kind: str
    scope: Literal["app", "world"]
    off: bool = False


@cache
def _shipped() -> NameLists:
    return NameLists.model_validate(json.loads(SHIPPED.read_text()))


def app_lists() -> NameLists:
    """The app's lists: the config's once edited, else the shipped ones."""

    stored = get_config().name_lists
    if stored is None:
        return _shipped().model_copy(deep=True)
    return NameLists.model_validate(stored.model_dump())


def _save_app(names: NameLists) -> None:
    get_config().name_lists = NameListsConfig.model_validate(names.model_dump())
    save_config()


def _key(name: str) -> str:
    """A name as compared: lower-cased, without a leading "the" or a
    trailing possessive."""

    key = " ".join(name.split()).lower()
    if key.startswith("the "):
        key = key[4:]
    for end in ("'s", "’s"):
        if key.endswith(end):
            key = key[: -len(end)]
    return key


def match(lists: NameLists, kind: str, name: str) -> bool:
    """Whether `name` is on the `kind` list; a title may hold `*`."""

    key = _key(name)
    for entry in getattr(lists, kind):
        wanted = _key(entry)
        if wanted == key or ("*" in wanted and fnmatchcase(key, wanted)):
            return True
    return False


def _has(names: list[str], name: str) -> bool:
    return any(_key(n) == _key(name) for n in names)


def _without(names: list[str], name: str) -> list[str]:
    return [n for n in names if _key(n) != _key(name)]


def _off_key(kind: str, name: str) -> str:
    return f"{kind}:{_key(name)}"


def effective(world) -> NameLists:
    """What applies in `world`: the app's rows it hasn't turned off, and
    its own."""

    app, own = app_lists(), world.name_lists()
    off = set(own.off)
    return NameLists(
        **{
            kind: [n for n in getattr(app, kind) if _off_key(kind, n) not in off]
            + [n for n in getattr(own, kind) if not _has(getattr(app, kind), n)]
            for kind in LIST_KINDS
        }
    )


def rows(world) -> list[ListRow]:
    """Every row for the Names page: the app's (marked off where turned
    off here) and the world's."""

    app, own = app_lists(), world.name_lists()
    off = set(own.off)
    found = []
    for kind in LIST_KINDS:
        found += [
            ListRow(name=n, kind=kind, scope="app", off=_off_key(kind, n) in off)
            for n in getattr(app, kind)
        ]
        found += [
            ListRow(name=n, kind=kind, scope="world")
            for n in getattr(own, kind)
            if not _has(getattr(app, kind), n)
        ]
    return found


def edit(world, action: str, kind: str, name: str) -> None:
    """One change to the lists; an unknown action or kind, or an empty
    name, is refused (ValueError), writing nothing."""

    name = " ".join((name or "").split())
    if action not in ACTIONS:
        raise ValueError(f"unknown name-list action: {action!r}")
    if kind not in LIST_KINDS:
        raise ValueError(f"unknown name list: {kind!r}")
    if not name:
        raise ValueError("a name is needed")
    own = world.name_lists()
    names = getattr(own, kind)
    if action == "add":
        if not _has(names, name):
            setattr(own, kind, [*names, name])
    elif action == "remove":
        setattr(own, kind, _without(names, name))
    elif action == "make_global":
        app = app_lists()
        if not _has(getattr(app, kind), name):
            setattr(app, kind, [*getattr(app, kind), name])
            _save_app(app)
        setattr(own, kind, _without(names, name))
    elif action == "turn_off":
        if _off_key(kind, name) not in own.off:
            own.off = [*own.off, _off_key(kind, name)]
    elif action == "turn_on":
        own.off = [k for k in own.off if k != _off_key(kind, name)]
    elif action == "remove_everywhere":
        app = app_lists()
        setattr(app, kind, _without(getattr(app, kind), name))
        _save_app(app)
        own.off = [k for k in own.off if k != _off_key(kind, name)]
    world.set_name_lists(own)
