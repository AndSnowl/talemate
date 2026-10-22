"""Kind specs: the fixed set of thing kinds and their fields.

A `KindSpec` names a kind's fields and the fact categories it accepts.
`KINDS` is the whole catalog; adding a kind later is one entry here.

Every kind also has three fields of its own:
- `aka`, its other names: a list of `{"name": str, "tag": "proper" |
  "common", "everyday": bool}`, with at most one everyday name, which must
  be a common one. The main name (`name`) is always the most proper;
- `stub`, present while the thing is a stub (a name mentioned but not made
  yet): `{"ignored": bool}`.
- `part_of`, the sphere drawer the thing currently belongs to, or `None`:
  `{"sphere": <32-hex thing id>, "drawer": <8-hex drawer id>}`. A dated
  `None` value ends the membership. The drawer may be `UNSORTED_DRAWER_ID`
  instead: the thing is part of the sphere, in no drawer yet (a child
  expanded before its sphere has drawers).
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
_SHARED_FIELDS: tuple[tuple[str, FieldType], ...] = (
    ("aka", "json"),
    ("stub", "json"),
    ("part_of", "json"),
)

AKA_TAGS: tuple[str, ...] = ("proper", "common")

# a sphere's (or sphere-shaped place's) template, and whether it acts as an
# agent (has its own stance and can act) under that template
SPHERE_TEMPLATES: tuple[str, ...] = (
    "religion",
    "nation",
    "order",
    "culture",
    "field",
    "other",
)

TEMPLATE_AGENT: dict[str, bool] = {
    "religion": True,
    "nation": True,
    "order": True,
    "culture": False,
    "field": False,
    "other": False,
}

# a sphere's fixed drawers, in no particular order here -- a sphere's own
# `drawers` field value carries the display order
DRAWER_TYPES: tuple[str, ...] = (
    "people",
    "places",
    "practices",
    "beliefs",
    "knowledge",
    "structure",
    "branches",
    "events",
)

_DRAWER_ID_RE = re.compile(r"^[0-9a-f]{8}$")

# the drawer id of "no drawer yet": `spheres.UNSORTED`'s, never a real
# drawer's (those are 8-hex)
UNSORTED_DRAWER_ID = "unsorted"


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
            ("ties", "json"),
        ),
        categories=[
            "appearance",
            "personality",
            "background",
            "ability",
            "relationship",
            "speech",
            "ties",
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
            ("template", "text"),
            ("agent", "json"),
            ("drawers", "json"),
        ),
        categories=["description", "history", "law", "general", "statement"],
    ),
    "sphere": KindSpec(
        name="sphere",
        fields=_fields(
            ("name", "text"),
            ("template", "text"),
            ("agent", "json"),
            ("drawers", "json"),
            ("parent", "thing"),
            ("drops", "things"),
            ("language", "json"),
        ),
        categories=["timeline", "about", "statement"],
    ),
    # legacy: readable in old worlds, no longer created or guessed
    # (Task 4). `language` on `sphere` carries what a `culture` held.
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

# kinds kept in KINDS so old worlds still read, but no longer created or
# guessed in fresh ones (superseded by the sphere kind)
LEGACY_KINDS: tuple[str, ...] = ("culture",)


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
        if field == "template" and value not in SPHERE_TEMPLATES:
            raise ValueError(f"{field!r} must be one of {SPHERE_TEMPLATES}")
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
        elif field == "agent":
            if not isinstance(value, bool):
                raise ValueError(f"{field!r} must be a bool")
        elif field == "drawers":
            _validate_drawers(field, value)
        elif field == "part_of":
            _validate_part_of(field, value)
        elif field == "ties":
            _validate_ties(field, value)
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


def _validate_drawers(field: str, value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list of drawers")
    ids: list[str] = []
    for drawer in value:
        if (
            not isinstance(drawer, dict)
            or set(drawer) != {"id", "type", "title"}
            or not isinstance(drawer.get("id"), str)
            or not _DRAWER_ID_RE.match(drawer.get("id", ""))
            or drawer.get("type") not in DRAWER_TYPES
            or not isinstance(drawer.get("title"), str)
            or not drawer["title"].strip()
        ):
            raise ValueError(
                f"{field!r} entries must be "
                '{"id": <8-hex>, "type": <drawer type>, "title": non-blank str}'
            )
        ids.append(drawer["id"])
    if len(set(ids)) != len(ids):
        raise ValueError(f"{field!r} ids must be unique")


def _validate_part_of(field: str, value: object) -> None:
    if value is None:
        return
    if (
        not isinstance(value, dict)
        or set(value) != {"sphere", "drawer"}
        or not isinstance(value.get("sphere"), str)
        or not _THING_ID_RE.match(value["sphere"])
        or not isinstance(value.get("drawer"), str)
        or not (
            _DRAWER_ID_RE.match(value["drawer"])
            or value["drawer"] == UNSORTED_DRAWER_ID
        )
    ):
        raise ValueError(
            f'{field!r} must be {{"sphere": <32-hex>, "drawer": <8-hex>}} or null'
        )


def _validate_world_date_or_null(field: str, key: str, value: object) -> None:
    if value is None or isinstance(value, WorldDate):
        return
    if isinstance(value, dict):
        try:
            WorldDate(**value)
        except Exception as exc:
            raise ValueError(f"{field!r} {key} must be a valid date") from exc
        return
    raise ValueError(f"{field!r} {key} must be a WorldDate, its dict form, or null")


def _validate_ties(field: str, value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list of ties")
    for tie in value:
        if (
            not isinstance(tie, dict)
            or set(tie) != {"sphere", "role", "since", "until"}
            or not isinstance(tie.get("sphere"), str)
            or not _THING_ID_RE.match(tie["sphere"])
            or not isinstance(tie.get("role"), str)
        ):
            raise ValueError(
                f"{field!r} entries must be "
                '{"sphere": <32-hex>, "role": str, "since": WorldDate|null, '
                '"until": WorldDate|null}'
            )
        _validate_world_date_or_null(field, "since", tie.get("since"))
        _validate_world_date_or_null(field, "until", tie.get("until"))
