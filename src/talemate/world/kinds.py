"""Kind specs: the fixed set of thing kinds and their fields.

A `KindSpec` names a kind's fields and the fact categories it accepts.
`KINDS` is the whole catalog; adding a kind later is one entry here.

Every kind also has two fields of its own:
- `aka`, its other names: a list of `{"name": str, "tag": "proper" |
  "common", "everyday": bool}`, with at most one everyday name, which must
  be a common one. The main name (`name`) is always the most proper;
- `stub`, present while the thing is a stub (a name mentioned but not made
  yet): `{"ignored": bool}`.
"""

import re
from typing import Literal

import structlog
from pydantic import BaseModel

from .dates import WorldDate

log = structlog.get_logger("talemate.world.kinds")

_THING_ID_RE = re.compile(r"^[0-9a-f]{32}$")

FieldType = Literal["text", "date", "thing", "shares", "json", "number", "things"]


class FieldSpec(BaseModel):
    name: str
    type: FieldType


class KindSpec(BaseModel):
    name: str
    fields: list[FieldSpec]
    categories: list[str]


# the fields every kind has, after its own
_SHARED_FIELDS: tuple[tuple[str, FieldType], ...] = (("aka", "json"), ("stub", "json"))

AKA_TAGS: tuple[str, ...] = ("proper", "common")


def _fields(*pairs: tuple[str, FieldType]) -> list[FieldSpec]:
    return [
        FieldSpec(name=name, type=type_) for name, type_ in (*pairs, *_SHARED_FIELDS)
    ]


_HERITAGE_CATEGORIES = ["origin", "physical", "instinct", "variation", "general"]

KINDS: dict[str, KindSpec] = {
    "character": KindSpec(
        name="character",
        fields=_fields(
            ("name", "text"),
            ("born", "date"),
            ("culture", "thing"),
            ("voice", "json"),
            ("color", "text"),
            ("heritage", "thing"),
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
    "species": KindSpec(
        name="species",
        fields=_fields(
            ("name", "text"),
            ("origin", "thing"),
            ("lifespan", "number"),
            ("adult_age", "number"),
            ("measures", "json"),
        ),
        categories=list(_HERITAGE_CATEGORIES),
    ),
    "race": KindSpec(
        name="race",
        fields=_fields(
            ("name", "text"),
            ("species", "thing"),
            ("lifespan", "number"),
            ("adult_age", "number"),
            ("measures", "json"),
        ),
        categories=list(_HERITAGE_CATEGORIES),
    ),
    "mix": KindSpec(
        name="mix",
        fields=_fields(
            ("name", "text"),
            ("parents", "things"),
            ("lifespan", "number"),
            ("adult_age", "number"),
            ("measures", "json"),
        ),
        categories=list(_HERITAGE_CATEGORIES),
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


HERITAGE_KINDS: tuple[str, ...] = ("species", "race", "mix")


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
    elif spec.type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field!r} must be a number")
        if value < 0:
            raise ValueError(f"{field!r} must be >= 0")
    elif spec.type == "things":
        if not isinstance(value, list):
            raise ValueError(f"{field!r} must be a list of thing ids")
        for thing_id in value:
            if not isinstance(thing_id, str) or not _THING_ID_RE.match(thing_id):
                raise ValueError(f"{field!r} entries must be 32-hex thing ids")
        if len(set(value)) != len(value):
            raise ValueError(f"{field!r} must not repeat a thing id")
        if field == "parents" and len(value) != 2:
            raise ValueError(f"{field!r} must have exactly 2 parents")
    elif spec.type == "json":
        if field == "measures":
            _validate_measures(field, value)
        elif field == "aka":
            _validate_aka(field, value)
        elif field == "stub":
            _validate_stub(field, value)
        # otherwise any JSON-serializable value is accepted


def _validate_measures(field: str, value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list of measures")
    for measure in value:
        if (
            not isinstance(measure, dict)
            or not isinstance(measure.get("name"), str)
            or isinstance(measure.get("min"), bool)
            or not isinstance(measure.get("min"), (int, float))
            or isinstance(measure.get("max"), bool)
            or not isinstance(measure.get("max"), (int, float))
            or not isinstance(measure.get("unit"), str)
        ):
            raise ValueError(
                f"{field!r} entries must be "
                '{"name": str, "min": number, "max": number, "unit": str}'
            )


def _validate_aka(field: str, value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list of other names")
    everyday = 0
    for entry in value:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"name", "tag", "everyday"}
            or not isinstance(entry["name"], str)
            or not entry["name"].strip()
            or entry["tag"] not in AKA_TAGS
            or not isinstance(entry["everyday"], bool)
        ):
            raise ValueError(
                f"{field!r} entries must be "
                '{"name": str, "tag": "proper" | "common", "everyday": bool}'
            )
        if entry["everyday"]:
            if entry["tag"] != "common":
                raise ValueError(f"{field!r}: the everyday name must be common")
            everyday += 1
    if everyday > 1:
        raise ValueError(f"{field!r} may have at most one everyday name")


def _validate_stub(field: str, value: object) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"ignored"}
        or not isinstance(value["ignored"], bool)
    ):
        raise ValueError(f'{field!r} must be {{"ignored": bool}}')
