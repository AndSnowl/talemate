"""Kind specs: the fixed set of thing kinds and their fields.

A `KindSpec` names a kind's fields and the fact categories it accepts.
`KINDS` is the whole catalog; adding a kind later is one entry here.

Every kind also has fields of its own:
- `aka`, its other names: a list of `{"name": str, "tag": "proper" |
  "common", "everyday": bool}`, with at most one everyday name, which must
  be a common one. The main name (`name`) is always the most proper;
- `stub`, present while the thing is a stub (a name mentioned but not made
  yet): `{"ignored": bool}`;
- `tag` (text), the one word saying what the entry is ("river", "custom",
  "ruler"): lowercase and singular, normalised when written
  (`normalise_field`);
- `filings`: a list of `{"target": <32-hex>, "role": str|null, "since":
  date|null, "until": date|null, "within": <32-hex>|null, "exceptions":
  [fact id...], "show_under": str|null}`, the entries it is filed in
  (`filing.py` reads them); `show_under` is the group it shows under on
  the target's page, a tag (stored normalised), else the entry's own.
  `within` is a part of the target (never the target itself), and no
  target may appear twice. What needs the world to check (a filing into
  itself, a `within` that doesn't sit in its target, a cycle) is
  `filing.check_filings`, which the store runs on every write;
- `hint` (text): the prompt hint it was written with, if any
  (`create.hint_names`), stored when its draft is accepted;
- `agent` (bool): whether it acts as an agent (has its own stance and can
  act), which the prompt hint it was written with sets by default
  (`HINT_AGENT`).

A `being` (a god, a spirit, a legendary creature) has an `existence`:
`real` (it acts in the world like a character: it can be cast in scenes
and be filed with a role), `believed` (only ever spoken of) or `undecided` (treated
as believed until the owner decides), `DEFAULT_EXISTENCE` when unset.
"""

import re
from typing import Literal

import structlog
from pydantic import BaseModel

from .dates import WorldDate

log = structlog.get_logger("talemate.world.kinds")

_THING_ID_RE = re.compile(r"^[0-9a-f]{32}$")

FieldType = Literal["text", "date", "thing", "json", "number", "things"]


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
    ("tag", "text"),
    ("filings", "json"),
    ("hint", "text"),
    ("agent", "json"),
    ("languages", "json"),
)

AKA_TAGS: tuple[str, ...] = ("proper", "common")

# a being's `existence` values, and what an unset one reads as
EXISTENCE_VALUES: tuple[str, ...] = ("real", "believed", "undecided")
DEFAULT_EXISTENCE = "undecided"

# whether an entry written with a prompt hint acts as an agent (has its
# own stance and can act) by default; an entry with no hint, or one not
# listed, doesn't
HINT_AGENT: dict[str, bool] = {
    "religion": True,
    "nation": True,
    "order": True,
    "field": False,
}


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
        # what it is ("river", "city") is its tag
        fields=_fields(("name", "text")),
        # its timeline, summary (`about`) and statement facts too, which a
        # prompt never writes (`UNPROMPTED_CATEGORIES`)
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
    "item": KindSpec(
        name="item",
        fields=_fields(
            ("name", "text"),
        ),
        categories=["description", "history", "power", "general"],
    ),
    "event": KindSpec(
        name="event",
        fields=_fields(
            ("name", "text"),
            ("when", "date"),
            ("until", "date"),
        ),
        categories=["summary", "consequence", "general"],
    ),
    # `belief`: what a faith or order teaches, held by the entry
    # itself (`entries.held_by`); offered only under those prompt hints
    "lore": KindSpec(
        name="lore",
        fields=_fields(("name", "text")),
        categories=["general", "belief"],
    ),
    # a language or naming style (languages 3a): its technical part lives
    # in fields of its own, read by `talemate.languages.entry`
    "language": KindSpec(
        name="language",
        fields=_fields(
            ("name", "text"),
            ("depth", "text"),
            ("flavour", "text"),
            ("sound", "text"),
            ("rules", "json"),
            ("words", "json"),
            ("phrases", "json"),
            ("descends_from", "thing"),
            ("similar", "json"),
        ),
        categories=["general", "history", "about", "statement", "timeline"],
    ),
    # a god, a spirit, a legendary creature; it acts in the world only
    # while its `existence` is real (`entries.acts_in_world`)
    "being": KindSpec(
        name="being",
        fields=_fields(
            ("name", "text"),
            ("existence", "text"),
            ("born", "date"),
        ),
        # `ties`: a real being's exceptions to its filings, as a character's
        categories=["nature", "deeds", "worship", "ties", "general"],
    ),
}


HERITAGE_KINDS: tuple[str, ...] = ("species", "race", "mix")

# the order kinds come in wherever entries of several kinds are listed
# together (Connected, polish 5); the World tab's `KIND_ORDER` matches it
KIND_ORDER: tuple[str, ...] = (
    "character",
    "species",
    "race",
    "mix",
    "place",
    "event",
    "item",
    "lore",
    "language",
    "being",
)


def kind_rank(kind: str) -> int:
    """Where `kind` comes in `KIND_ORDER` (any other kind last)."""

    return KIND_ORDER.index(kind) if kind in KIND_ORDER else len(KIND_ORDER)


# the fact categories a place holds that a prompt never writes it: its
# timeline, its summary (`about`, `entries.summary_fact`) and statements
UNPROMPTED_CATEGORIES: tuple[str, ...] = ("timeline", "about", "statement")


# where a fact goes on a kind that lacks its category: a kind's plain and
# dated fallbacks, where they differ from "general" (a place's `history`
# when dated, a character's `background`), then a catch-all, then the
# kind's first
_FALLBACK_CATEGORIES: dict[str, tuple[str, str]] = {
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
    only the same kind. A merge folds only these (ruling C17), and an
    entry's same-thing candidates are only these (ruling C34)."""

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
        if field == "existence" and value not in EXISTENCE_VALUES:
            raise ValueError(f"{field!r} must be one of {EXISTENCE_VALUES}")
        if field == "depth" and value not in LANGUAGE_DEPTHS:
            raise ValueError(f"{field!r} must be one of {LANGUAGE_DEPTHS}")
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
        elif field == "filings":
            _validate_filings(field, value)
        elif field == "languages":
            _validate_languages(field, value)
        elif field == "rules":
            _validate_rules(field, value)
        elif field == "words":
            _validate_words(field, value)
        elif field == "phrases":
            _validate_phrases(field, value)
        elif field == "similar":
            _validate_similar(field, value)
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


LANGUAGE_DEPTHS: tuple[str, ...] = ("description", "naming", "full")
LANGUAGE_ROLES: tuple[str, ...] = (
    "spoken",
    "official",
    "scholarly",
    "ceremonial",
    "trade",
    "liturgical",
)
LANGUAGE_FLUENCIES: tuple[str, ...] = ("native", "fluent", "broken")
SIMILAR_DEGREES: tuple[str, ...] = ("close", "distant", "one-way")
LANGUAGE_ROW_KEYS: tuple[str, ...] = (
    "language",
    "role",
    "share",
    "fluency",
    "since",
    "until",
)


def _validate_languages(field: str, value: object) -> None:
    """Who speaks what: rows of `{"language": <32-hex>, "role", "share",
    "fluency", "since", "until"}`; a share (0-100) only on a spoken row;
    no row twice."""

    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list of language rows")
    seen: list[tuple[tuple[str, str], ...]] = []
    for row in value:
        if (
            not isinstance(row, dict)
            or not set(row) <= set(LANGUAGE_ROW_KEYS)
            or not isinstance(row.get("language"), str)
            or not _THING_ID_RE.match(row["language"])
            or row.get("role") not in LANGUAGE_ROLES
        ):
            raise ValueError(
                f'{field!r} rows must be {{"language": <32-hex>, "role": one of '
                f"{LANGUAGE_ROLES}, ...}}"
            )
        share = row.get("share")
        if share is not None:
            if row["role"] != "spoken":
                raise ValueError(f"{field!r}: only a spoken row has a share")
            if isinstance(share, bool) or not isinstance(share, (int, float)):
                raise ValueError(f"{field!r}: share must be a number")
            if not 0 <= share <= 100:
                raise ValueError(f"{field!r}: share must be between 0 and 100")
        if row.get("fluency") not in (None, *LANGUAGE_FLUENCIES):
            raise ValueError(f"{field!r}: fluency must be one of {LANGUAGE_FLUENCIES}")
        _validate_world_date_or_null(field, "since", row.get("since"))
        _validate_world_date_or_null(field, "until", row.get("until"))
        since, until = row.get("since"), row.get("until")
        if since is not None and until is not None:
            if WorldDate.model_validate(until) <= WorldDate.model_validate(since):
                raise ValueError(f"{field!r}: until must be after since")
        key = tuple(sorted((k, repr(v)) for k, v in row.items()))
        if key in seen:
            raise ValueError(f"{field!r} must not repeat a row")
        seen.append(key)


# what a language's `rules` field holds: its sound categories and name
# rules, plus the notes a full language carries with them
RULES_KEYS: tuple[str, ...] = (
    "categories",
    "generators",
    "syllable_notes",
    "grammar",
    "writable",
)


def _validate_rules(field: str, value: object) -> None:
    """A language's sound categories and name rules: they must load and
    parse (`talemate.languages.generator.validate_language`)."""

    from talemate.languages.generator import validate_language
    from talemate.languages.models import Language

    if not isinstance(value, dict) or not set(value) <= set(RULES_KEYS):
        raise ValueError(
            f'{field!r} must be {{"categories": ..., "generators": [...]}}'
        )
    try:
        validate_language(Language(name="rules", level="naming", **value))
    except Exception as exc:
        raise ValueError(f"{field!r}: {exc}") from exc


def _validate_entries(field: str, value: object, required: tuple[str, ...]) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list")
    for entry in value:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(key), str) and entry[key].strip() for key in required
        ):
            raise ValueError(f"{field!r} entries need non-blank {required}")


def _validate_words(field: str, value: object) -> None:
    _validate_entries(field, value, ("word", "meaning"))


def _validate_phrases(field: str, value: object) -> None:
    _validate_entries(field, value, ("id", "category", "original", "translation"))


def _validate_similar(field: str, value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field!r} must be a list")
    for link in value:
        if (
            not isinstance(link, dict)
            or not isinstance(link.get("target"), str)
            or not _THING_ID_RE.match(link["target"])
            or link.get("degree") not in SIMILAR_DEGREES
        ):
            raise ValueError(
                f'{field!r} entries must be {{"target": <32-hex>, "degree": one of '
                f"{SIMILAR_DEGREES}}}"
            )


FILING_KEYS: tuple[str, ...] = (
    "target",
    "role",
    "since",
    "until",
    "within",
    "exceptions",
    "show_under",
)


def _validate_filings(field: str, value: object) -> None:
    """A list of filings, each with a 32-hex `target` and, optionally, the
    other `FILING_KEYS`; no target twice, and `within` never its target."""

    shape = (
        f"{field!r} entries must be "
        '{"target": <32-hex>, "role": str|null, "since": WorldDate|null, '
        '"until": WorldDate|null, "within": <32-hex>|null, '
        '"exceptions": [fact id...], "show_under": str|null}'
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
                filing.get("show_under") is None
                or isinstance(filing["show_under"], str)
            )
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
