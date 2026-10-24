"""Temporary (ruling F10): filings written beside the old structure.

The world's readers (nearness, timelines, held-by) read only filings now,
while the worldplay and server writers still write the old fields
(`part_of`, a place's or branch's `parent`, a character's `ties`) until
Task 4's single writer. A writer whose tests read the result through a
world reader opens its revision with `shadowed_revision` in place of
`World.revision`, which ends it with `shadow_revision`, so each thing whose
old fields the revision wrote has `filings` that say the same thing:

- `part_of` -> a filing into its sphere;
- `parent` -> a filing into the parent (a branch sphere's: role
  "branch of");
- each tie -> a filing into its sphere, with its role, dates and
  `within`.

The thing's filings are rebuilt from those fields alone (nothing else
writes filings yet), dated as the write was. A filing the store would
refuse (into a deleted entry, a cycle, a `within` that no longer holds)
is left out rather than failing the writer.

Held-by goes the same way: the old rule held a statement in a religion's
or a culture's beliefs drawer by its sphere unmarked, and `held_by` now
reads only what's marked (or a `belief` fact). So a writer of a sphere's
statements marks such a one held as it writes it (`statement_origin`),
as the spec has the religion hint mark its belief facts at write time.

Task 4 deletes this module.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import structlog
from pydantic import ValidationError

from talemate.world.dates import WorldDate
from talemate.world import spheres
from talemate.world.filing import Filing, check_filings
from talemate.world.store import Revision, Source, World, _decode_date
from talemate.world.view import WorldView

__all__ = [
    "HELD_TEMPLATES",
    "shadow_filings",
    "shadow_revision",
    "shadowed_revision",
    "statement_origin",
]

# the templates whose beliefs-drawer statements the old rule held by their
# sphere: a nation's beliefs drawer is its Laws (true as laws), and a
# field's theories stay plain claims
HELD_TEMPLATES: tuple[str, ...] = ("religion", "culture")

# the old fields a filing stands for
_OLD_FIELDS = ("part_of", "parent", "ties")

log = structlog.get_logger("talemate.worldplay.filing_shadow")


def _date(value: object) -> WorldDate | None:
    if value is None:
        return None
    try:
        return WorldDate.model_validate(value)
    except ValidationError:
        return None


def _derived(kind: str, fields: dict[str, object]) -> list[Filing]:
    """The filings the old fields say, one per target, in field order."""

    found: list[Filing] = []
    part_of = fields.get("part_of")
    if isinstance(part_of, dict) and isinstance(part_of.get("sphere"), str):
        found.append(Filing(target=str(part_of["sphere"])))
    parent = fields.get("parent")
    if isinstance(parent, str):
        found.append(
            Filing(target=parent, role="branch of" if kind == "sphere" else None)
        )
    ties = fields.get("ties")
    for raw in ties if isinstance(ties, list) else []:
        if not isinstance(raw, dict) or not isinstance(raw.get("sphere"), str):
            continue
        role = raw.get("role")
        within = raw.get("within")
        found.append(
            Filing(
                target=str(raw["sphere"]),
                role=role if isinstance(role, str) and role.strip() else None,
                since=_date(raw.get("since")),
                until=_date(raw.get("until")),
                within=within if isinstance(within, str) else None,
            )
        )
    unique: dict[str, Filing] = {}
    for filing in found:
        unique.setdefault(filing.target, filing)
    return list(unique.values())


def shadow_filings(
    world: World, rev: Revision, thing_id: str, since: WorldDate | None = None
) -> None:
    """Rewrite the thing's `filings` (in `rev`, from `since`, as its
    old-field write was dated) to match its `part_of`, `parent` and
    `ties` as the revision sees them at that date. A filing the store
    would refuse is dropped, with a log line."""

    view = world.view(at=since, rev=rev.rev)
    # the store checks filings at the latest telling of the revision
    latest = world.view(rev=rev.rev)
    state = view.thing(thing_id)
    if state is None:
        return
    wanted = _derived(state.kind, state.fields)
    kept: list[Filing] = []
    for filing in wanted:
        trial = [f.model_dump(mode="json") for f in [*kept, filing]]
        errors = check_filings(latest, thing_id, trial)
        if errors and filing.within is not None:
            # a part moved out since: filed in the target as a whole
            filing = filing.model_copy(update={"within": None})
            trial = [f.model_dump(mode="json") for f in [*kept, filing]]
            errors = check_filings(latest, thing_id, trial)
        if errors:
            log.warning(
                "filing_shadow.dropped",
                thing_id=thing_id,
                target=filing.target,
                errors=errors,
            )
            continue
        kept.append(filing)
    value = [f.model_dump(mode="json") for f in kept]
    current = state.fields.get("filings")
    if current == value or (current is None and not value):
        return
    try:
        rev.set_field(thing_id, "filings", value, since)
    except ValueError as error:
        log.warning("filing_shadow.refused", thing_id=thing_id, error=str(error))


def shadow_revision(world: World, rev: Revision) -> None:
    """`shadow_filings` for every live thing whose `part_of`, `parent` or
    `ties` this revision wrote, at each date it wrote them. Twice over:
    a tie `within` a part holds only once the part's own filing is
    written, whichever thing comes first."""

    rows = rev._conn.execute(
        "SELECT DISTINCT thing_id, valid_from, from_precision FROM field_values"
        " WHERE rev_added = ? AND field IN (?, ?, ?)"
        " ORDER BY thing_id, valid_from",
        (rev.rev, *_OLD_FIELDS),
    ).fetchall()
    for _ in range(2):
        for thing_id, valid_from, precision in rows:
            shadow_filings(world, rev, thing_id, _decode_date(valid_from, precision))


@contextmanager
def shadowed_revision(world: World, source: Source) -> Iterator[Revision]:
    """`world.revision(source)`, ended (when nothing raised) with
    `shadow_revision`, in the same revision: one undo takes both back."""

    with world.revision(source) as rev:
        yield rev
        shadow_revision(world, rev)


def statement_origin(
    view: WorldView, sphere_id: str, drawer_id: str
) -> dict[str, object]:
    """The origin of a statement written into the sphere's drawer: the
    drawer, and the sphere as its holder when the old rule held it (a
    beliefs drawer of a religion or a culture)."""

    origin: dict[str, object] = {"drawer": drawer_id}
    state = view.thing(sphere_id)
    if state is None or state.fields.get("template") not in HELD_TEMPLATES:
        return origin
    types = {d.id: d.type for d in spheres.drawers(view, sphere_id)}
    if types.get(drawer_id) == "beliefs":
        origin["held_by"] = sphere_id
    return origin
