"""Kind specs: the fixed set of thing kinds and their fields.

A `KindSpec` names a kind's fields and the fact categories it accepts.
`KINDS` is the whole catalog; adding a kind later is one entry here.
"""

import re
from typing import Literal

import structlog
from pydantic import BaseModel

from .dates import WorldDate

log = structlog.get_logger("talemate.world.kinds")

_THING_ID_RE = re.compile(r"^[0-9a-f]{32}$")

FieldType = Literal["text", "date", "thing", "shares", "json"]


class FieldSpec(BaseModel):
    name: str
    type: FieldType


class KindSpec(BaseModel):
    name: str
    fields: list[FieldSpec]
    categories: list[str]


def _fields(*pairs: tuple[str, FieldType]) -> list[FieldSpec]:
    return [FieldSpec(name=name, type=type_) for name, type_ in pairs]


KINDS: dict[str, KindSpec] = {
    "character": KindSpec(
        name="character",
        fields=_fields(
            ("name", "text"),
            ("born", "date"),
            ("culture", "thing"),
            ("voice", "json"),
            ("color", "text"),
        ),
        categories=[
            "appearance",
            "personality",
            "background",
            "ability",
            "relationship",
            "speech",
        ],
    ),
    "place": KindSpec(
        name="place",
        fields=_fields(
            ("name", "text"),
            ("kind", "text"),
            ("parent", "thing"),
            ("cultures", "shares"),
        ),
        categories=["description", "history", "law", "general"],
    ),
    "culture": KindSpec(
        name="culture",
        fields=_fields(
            ("name", "text"),
            ("language", "json"),
        ),
        categories=["customs", "food", "dress", "belief", "general"],
    ),
    "item": KindSpec(
        name="item",
        fields=_fields(
            ("name", "text"),
            ("owner", "thing"),
        ),
        categories=["description", "history", "power", "general"],
    ),
    "event": KindSpec(
        name="event",
        fields=_fields(
            ("name", "text"),
            ("when", "date"),
            ("until", "date"),
            ("place", "thing"),
        ),
        categories=["summary", "consequence", "general"],
    ),
    "lore": KindSpec(
        name="lore",
        fields=_fields(("name", "text")),
        categories=["general"],
    ),
}


def get_kind(name: str) -> KindSpec:
    """Look up a kind by name, raising `KeyError` for an unknown one."""

    try:
        return KINDS[name]
    except KeyError:
        raise KeyError(f"unknown kind: {name!r}") from None


def _field_spec(kind: KindSpec, field: str) -> FieldSpec:
    for spec in kind.fields:
        if spec.name == field:
            return spec
    raise ValueError(f"{kind.name!r} has no field {field!r}")


def validate_field(kind: KindSpec, field: str, value: object) -> None:
    """Raise `ValueError` if `field` isn't on `kind`, or `value` doesn't fit
    its type."""

    spec = _field_spec(kind, field)

    if spec.type == "text":
        if not isinstance(value, str):
            raise ValueError(f"{field!r} must be a string")
    elif spec.type == "date":
        if isinstance(value, WorldDate):
            return
        if isinstance(value, dict):
            try:
                WorldDate(**value)
            except Exception as exc:
                raise ValueError(f"{field!r} must be a valid date") from exc
            return
        raise ValueError(f"{field!r} must be a WorldDate or its dict form")
    elif spec.type == "thing":
        if not isinstance(value, str) or not _THING_ID_RE.match(value):
            raise ValueError(f"{field!r} must be a 32-hex thing id")
    elif spec.type == "shares":
        if not isinstance(value, list):
            raise ValueError(f"{field!r} must be a list of shares")
        for share in value:
            if (
                not isinstance(share, dict)
                or not isinstance(share.get("thing_id"), str)
                or not _THING_ID_RE.match(share.get("thing_id", ""))
                or not isinstance(share.get("share"), (int, float))
            ):
                raise ValueError(
                    f"{field!r} entries must be "
                    '{"thing_id": <32-hex>, "share": <number>}'
                )
    elif spec.type == "json":
        # any JSON-serializable value is accepted
        pass
