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

A character's (or real being's) `ties` are a list of `{"sphere": <32-hex>,
"role": str, "since": date|null, "until": date|null}`, each with an
optional `"within"`: the thing id of the part of that sphere it belongs
in (the White Talon of the Tsar's Army), never the sphere itself. Whether
it's live and part of the sphere is read through a view
(`spheres.within_sphere`).

Every kind also has a `tag` (text), the one word saying what the entry is
("river", "custom", "ruler"): lowercase and singular, normalised when
written (`normalise_field`), and its `filings`: a list of `{"target":
<32-hex>, "role": str|null, "since": date|null, "until": date|null,
"within": <32-hex>|null, "exceptions": [fact id...]}`, the entries it is
filed in (`filing.py` reads them). `within` is a part of the target (never
the target itself), and no target may appear twice. What needs the world
to check (a filing into itself, a `within` that doesn't sit in its target,
a cycle) is `filing.check_filings`, which the store runs on every write.
These sit beside `part_of`, `ties` and the place `parent` until those go.
And its `hint` (text): the prompt hint it was written with, if any
(`create.hint_names`), stored when its draft is accepted.

A `being` (a god, a spirit, a legendary creature) has an `existence`:
`real` (it acts in the world like a character: it can be cast in scenes
and hold ties), `believed` (only ever spoken of) or `undecided` (treated
as believed until the owner decides), `DEFAULT_EXISTENCE` when unset.
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
    ("tag", "text"),
    ("filings", "json"),
    ("hint", "text"),
)

AKA_TAGS: tuple[str, ...] = ("proper", "common")

# a being's `existence` values, and what an unset one reads as
EXISTENCE_VALUES: tuple[str, ...] = ("real", "believed", "undecided")
DEFAULT_EXISTENCE = "undecided"

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

# the drawer types whose content is written (by the core, Fill or the
# owner): entries filed there and statements. The rest are the app's own:
# people come from ties, events are the timeline, branches are spheres
# with a parent
WRITTEN_DRAWER_TYPES: tuple[str, ...] = (
    "places",
    "practices",
    "beliefs",
    "knowledge",
    "structure",
)

# the written drawer types that hold entries other than places
_ENTRY_TYPES: tuple[str, ...] = ("practices", "beliefs", "knowledge", "structure")

# the drawer types a thing of each kind may be filed in (`part_of`): a
# place in a places drawer, any other entry in one that holds entries. Its
# keys are the kinds that can be part of a sphere at all; a character
# never is (people come from ties). Any of them may sit in Unsorted too.
ENTRY_DRAWER_TYPES: dict[str, tuple[str, ...]] = {
    "lore": _ENTRY_TYPES,
    "place": ("places",),
    "item": _ENTRY_TYPES,
    "event": _ENTRY_TYPES,
    "sphere": _ENTRY_TYPES,
    # a god in its faith's Doctrines, a spirit in a culture's customs, a
    # guardian in an order's ranks
    "being": ("beliefs", "practices", "structure"),
}

# the kinds that can be part of a sphere, in a drawer
PART_OF_KINDS: tuple[str, ...] = tuple(ENTRY_DRAWER_TYPES)

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
        # a place sphere's timeline, about and statement facts too
        categories=[
            "description",
            "history",
            "law",
            "general",
            "statement",
            "timeline",
            "about",
        ],
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
    # `belief`: what a faith, culture or order teaches, held by the entry
    # itself (`entries.held_by`); offered only under those prompt hints
    "lore": KindSpec(
        name="lore",
        fields=_fields(("name", "text")),
        categories=["general", "belief"],
    ),
    # a god, a spirit, a legendary creature; `ties` count only while its
    # `existence` is real (`entries.acts_in_world`)
    "being": KindSpec(
        name="being",
        fields=_fields(
            ("name", "text"),
            ("existence", "text"),
            ("born", "date"),
            ("ties", "json"),
        ),
        # `ties`: a real being's exceptions to its ties, as a character's
        categories=["nature", "deeds", "worship", "ties", "general"],
    ),
}


HERITAGE_KINDS: tuple[str, ...] = ("species", "race", "mix")

# the fact categories only a sphere uses: a place holds them once it takes
# on a template, but a plain place is never written them from a prompt
SPHERE_CATEGORIES: tuple[str, ...] = ("timeline", "about", "statement")

# kinds kept in KINDS so old worlds still read, but no longer created or
# guessed in fresh ones (superseded by the sphere kind)
LEGACY_KINDS: tuple[str, ...] = ("culture",)


# where a fact goes on a kind that lacks its category: a kind's plain and
# dated fallbacks, where they differ from "general" (a sphere's `about`
# and `timeline`, a place's `history` when dated, a character's
# `background`), then a catch-all, then the kind's first
_FALLBACK_CATEGORIES: dict[str, tuple[str, str]] = {
    "sphere": ("about", "timeline"),
    "place": ("general", "history"),
    "character": ("background", "background"),
}
_CATCH_ALL_CATEGORIES: tuple[str, ...] = ("general", "about")


def moved_category(kind: str, category: str, dated: bool) -> str:
    """The category a fact in `category` takes on a `kind` thing (a stub
    whose kind changes, a fact moved onto another entry): its own when the
    kind has it; else the kind's fallback (`dated` for a fact with a start
    date), a catch-all, or the kind's first category."""

    categories = get_kind(kind).categories
    if category in categories:
        return category
    plain, when = _FALLBACK_CATEGORIES.get(kind, ("general", "general"))
    fallback = when if dated else plain
    if fallback in categories:
        return fallback
    return next((c for c in _CATCH_ALL_CATEGORIES if c in categories), categories[0])


def kinds_can_be_one(a: str, b: str) -> bool:
    """Whether a thing of kind `a` and one of kind `b` can be one entry:
    only the same kind (a place and a sphere no longer can: a place
    "sphere" is a place with things filed in it). A merge folds only these
    (ruling C17), and an entry's same-thing candidates are only these
    (ruling C34)."""

    return a == b


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


def normalise_tag(value: str) -> str:
    """A tag as stored: its first comma-separated part (ruling F8),
    stripped and lowercased."""

    return value.split(",", 1)[0].strip().lower()


def normalise_field(field: str, value: object) -> object:
    """`value` as it's stored in `field`: a `tag` string is normalised
    (`normalise_tag`); everything else is kept as given."""

    if field == "tag" and isinstance(value, str):
        return normalise_tag(value)
    return value


def validate_field(kind: KindSpec, field: str, value: object) -> None:
    """Raise `ValueError` if `field` isn't on `kind`, or `value` doesn't fit
    its type."""

    spec = _field_spec(kind, field)

    if spec.type == "text":
        if not isinstance(value, str):
            raise ValueError(f"{field!r} must be a string")
        if field == "template" and value not in SPHERE_TEMPLATES:
            raise ValueError(f"{field!r} must be one of {SPHERE_TEMPLATES}")
        if field == "existence" and value not in EXISTENCE_VALUES:
            raise ValueError(f"{field!r} must be one of {EXISTENCE_VALUES}")
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
        elif field == "filings":
            _validate_filings(field, value)
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
            or set(tie) - {"within"} != {"sphere", "role", "since", "until"}
            or not isinstance(tie.get("sphere"), str)
            or not _THING_ID_RE.match(tie["sphere"])
            or not isinstance(tie.get("role"), str)
            or not (
                tie.get("within") is None
                or (
                    isinstance(tie["within"], str)
                    and _THING_ID_RE.match(tie["within"])
                    and tie["within"] != tie["sphere"]
                )
            )
        ):
            raise ValueError(
                f"{field!r} entries must be "
                '{"sphere": <32-hex>, "role": str, "since": WorldDate|null, '
                '"until": WorldDate|null}, and may have "within": <32-hex>|null '
                "(an item of that sphere, not the sphere itself)"
            )
        _validate_world_date_or_null(field, "since", tie.get("since"))
        _validate_world_date_or_null(field, "until", tie.get("until"))


FILING_KEYS: tuple[str, ...] = (
    "target",
    "role",
    "since",
    "until",
    "within",
    "exceptions",
)


def _validate_filings(field: str, value: object) -> None:
    """A list of filings, each with a 32-hex `target` and, optionally, the
    other `FILING_KEYS`; no target twice, and `within` never its target."""

    shape = (
        f"{field!r} entries must be "
        '{"target": <32-hex>, "role": str|null, "since": WorldDate|null, '
        '"until": WorldDate|null, "within": <32-hex>|null, '
        '"exceptions": [fact id...]}'
    )
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list of filings")
    targets: list[str] = []
    for filing in value:
        if (
            not isinstance(filing, dict)
            or "target" not in filing
            or not set(filing) <= set(FILING_KEYS)
            or not isinstance(filing["target"], str)
            or not _THING_ID_RE.match(filing["target"])
            or not (filing.get("role") is None or isinstance(filing["role"], str))
            or not (
                filing.get("within") is None
                or (
                    isinstance(filing["within"], str)
                    and _THING_ID_RE.match(filing["within"])
                )
            )
            or not isinstance(filing.get("exceptions", []), list)
            or not all(isinstance(e, str) for e in filing.get("exceptions", []))
        ):
            raise ValueError(shape)
        if filing.get("within") == filing["target"]:
            raise ValueError(f"{field!r}: within must be a part of the target")
        _validate_world_date_or_null(field, "since", filing.get("since"))
        _validate_world_date_or_null(field, "until", filing.get("until"))
        since, until = filing.get("since"), filing.get("until")
        if since is not None and until is not None:
            if WorldDate.model_validate(until) <= WorldDate.model_validate(since):
                raise ValueError(f"{field!r}: until must be after since")
        targets.append(filing["target"])
    if len(set(targets)) != len(targets):
        raise ValueError(f"{field!r} must not file into the same target twice")
