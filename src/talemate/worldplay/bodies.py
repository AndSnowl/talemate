"""Bodies within bodies (spec goal 9): the owner names the outer body.

A division such as the White Talon belongs to an army, which is its own
`order` sphere, and the army is part of the Tsardom. When only the inner
part has been mentioned, the curation probe's probe 5 found the model never
proposes the outer body (0 of 8 runs; docs/superpowers/probes/
2026-10-22-curation.md), so the spec's fallback is built (ruling C10): no
model call and no prompt wording. The preview asks the owner to name it,
pre-filled as `outer_name` gives it ("<inner part>'s parent"), and
`add_outer_body` puts it into the preview:

- the part (the entry the preview writes, such as the White Talon stub
  being expanded (ruling C11); a new name the preview would make a stub
  of; or a named item of a sphere's core or Fill) is filed in the outer
  body:
  `part_of = {"name": <outer>, "drawer": <drawer>}`. A new stub sphere has
  no drawers until it's expanded, so that's Unsorted, unless the outer
  name is a sphere the world has (then its drawer for the row's kind);
- the outer body becomes a new name of kind `sphere`, with its template
  and its own `part_of`: where the owner put it, or, by default, where the
  part is filed now (an item's drawer of the sphere, the expanded stub's
  filing);
- every entry the world has filed in the drawer the outer body goes into
  (the Frosted Wing in the Tsardom's Military) gets a re-file row, all
  unticked: no model judges which are its siblings, the owner ticks them;
- the entry itself put into an outer body keeps what may move in from the
  home it still sits in through the body (ruling C13), unless the owner
  files the body elsewhere, and a body the world has adds its own facts,
  unticked (`create.offer_move_in`, spec goal 2).

Accept (`create.accept_preview`, `spheres.accept_sphere`,
`spheres.accept_fill`) makes the chain outer first and files it in one
revision with the ticked re-file rows (`create.file_chain`), refusing a
cycle.
"""

from __future__ import annotations

from typing import Any, NamedTuple, TypeVar

from pydantic import BaseModel

from talemate.world import spheres
from talemate.world.kinds import PART_OF_KINDS, SPHERE_TEMPLATES, UNSORTED_DRAWER_ID
from talemate.world.store import World
from talemate.world.view import ThingState, WorldView
from talemate.worldplay.create import (
    CreatePreview,
    ElsewhereFact,
    home_name,
    offer_move_in,
)
from talemate.worldplay.links import NewName, existing_id, name_key
from talemate.worldplay.spheres import FillPreview, SpherePreview, _item_kind

P = TypeVar("P", CreatePreview, SpherePreview, FillPreview)


class OuterBody(BaseModel):
    """The body the owner names around a part: its name, its sphere
    template, and where it's filed (`{"sphere", "drawer"}`, a sphere the
    world has), or None for where the part is filed now."""

    name: str
    template: str
    part_of: dict[str, str] | None = None


def outer_name(inner: str) -> str:
    """The outer body's name, pre-filled for the owner to change: the
    spec's "<inner part>'s parent"."""

    return f"{' '.join(inner.split())}'s parent"


def _rows(preview: CreatePreview | FillPreview) -> list[NewName]:
    """The preview's new names: its own (with the outer bodies) and its
    elsewhere items' new targets."""

    elsewhere: list[ElsewhereFact] = preview.elsewhere
    return [*preview.new_names, *(e.new for e in elsewhere if e.new is not None)]


def _items(preview: CreatePreview | FillPreview) -> list[dict[str, Any]]:
    if isinstance(preview, (SpherePreview, FillPreview)):
        return preview.items
    return []


def _own_sphere(preview: CreatePreview | FillPreview) -> dict[str, str]:
    """How the sphere a named item sits in is named in a `part_of`: Fill's
    sphere, the stub or thing a core expands or promotes, else the new
    sphere by its name."""

    if isinstance(preview, FillPreview):
        if preview.sphere_id is None:
            raise ValueError("a Fill preview needs its sphere_id")
        return {"sphere": preview.sphere_id}
    target = preview.stub_id or getattr(preview, "promote_id", None)
    return {"sphere": target} if target else {"name": preview.name}


def _sphere_drawers(
    view: WorldView, preview: CreatePreview | FillPreview, home: dict[str, str]
) -> list[spheres.Drawer]:
    """The drawers of the sphere `home` names: the world's, or a core
    preview's own for the sphere it makes or expands."""

    if isinstance(preview, SpherePreview) and (
        "name" in home or home.get("sphere") in (preview.stub_id, preview.promote_id)
    ):
        return [spheres.Drawer.model_validate(d) for d in preview.drawers]
    sphere = home.get("sphere")
    return spheres.drawers(view, sphere) if sphere else []


def _checked_home(view: WorldView, home: dict[str, str]) -> dict[str, str]:
    """The owner's `{"sphere", "drawer"}` for the outer body: a live sphere,
    and a drawer of it a sphere goes in, or Unsorted."""

    sphere_id, drawer_id = home.get("sphere"), home.get("drawer")
    state = view.thing(sphere_id) if isinstance(sphere_id, str) else None
    if state is None or not spheres.is_sphere(state):
        raise ValueError(f"not a sphere: {sphere_id}")
    if drawer_id != UNSORTED_DRAWER_ID:
        drawer = next(
            (d for d in spheres.drawers(view, state.id) if d.id == drawer_id), None
        )
        if drawer is None:
            raise ValueError(f"the sphere has no drawer {drawer_id}")
        if spheres.entry_drawer([drawer], "sphere", drawer.id) != drawer.id:
            raise ValueError(f"a sphere doesn't go in a {drawer.type} drawer")
    return {"sphere": state.id, "drawer": str(drawer_id)}


def _refile_row(
    state: ThingState, to: dict[str, str], skip: set[str]
) -> dict[str, Any] | None:
    if state.id in skip:
        return None
    return {
        "thing_id": state.id,
        "from": state.fields.get("part_of"),
        "to": dict(to),
        "ticked": False,
    }


def _refile_rows(
    view: WorldView,
    preview: CreatePreview | FillPreview,
    home: dict[str, str],
    to: dict[str, str],
    skip: set[str],
) -> list[dict[str, Any]]:
    """An unticked re-file row for each entry filed in the drawer `home`
    names: the world's own items of that sphere (not a branch's inherited
    ones); for a core's own sphere (the stub or thing it expands or
    promotes), the entries it adopts into that drawer; none for a sphere
    the core makes anew."""

    drawer = home.get("drawer")
    rows: list[dict[str, Any]] = []
    if "name" in home:
        return []
    sphere_id = home.get("sphere")
    if not isinstance(sphere_id, str):
        return []
    if isinstance(preview, SpherePreview) and sphere_id in (
        preview.stub_id,
        preview.promote_id,
    ):
        for adopted in preview.adopted:
            state = view.thing(adopted["thing_id"])
            if state is not None and adopted["drawer_id"] == drawer:
                if (row := _refile_row(state, to, skip)) is not None:
                    rows.append(row)
        return rows
    for item in spheres.items(view, sphere_id):
        if item.thing_id is None or item.inherited or item.drawer_id != drawer:
            continue
        state = view.thing(item.thing_id)
        if state is not None and (row := _refile_row(state, to, skip)) is not None:
            rows.append(row)
    return rows


class _Part(NamedTuple):
    """The part the outer body goes around: the preview's own entry, a new
    name, or a named item."""

    kind: str
    name: str
    # its `part_of` in the preview, before this call
    previous: dict[str, str] | None
    # where it's filed now, the outer body's default home
    now: dict[str, str] | None
    # the thing the world has it as, if any
    thing_id: str | None
    row: NewName | None = None
    item: dict[str, Any] | None = None


def _entry_target(preview: CreatePreview | FillPreview) -> str | None:
    """The stub or thing the preview writes into, if any."""

    if isinstance(preview, CreatePreview):
        return preview.stub_id or getattr(preview, "promote_id", None)
    return None


def _find_part(
    view: WorldView, preview: CreatePreview | FillPreview, wanted: str
) -> _Part:
    if isinstance(preview, CreatePreview) and name_key(preview.name) == wanted:
        target = _entry_target(preview)
        filed = view.thing(target).fields.get("part_of") if target else None
        if preview.part_of is not None and "sphere" in preview.part_of:
            now: dict[str, str] | None = dict(preview.part_of)
        elif isinstance(filed, dict) and isinstance(filed.get("sphere"), str):
            now = {"sphere": filed["sphere"], "drawer": str(filed.get("drawer"))}
        else:
            now = None
        return _Part(preview.kind, preview.name, preview.part_of, now, target)
    row = next((r for r in _rows(preview) if name_key(r.name) == wanted), None)
    if row is not None:
        # a new name is filed nowhere yet, unless in a sphere the world has
        previous = row.part_of
        now = dict(previous) if previous and "sphere" in previous else None
        known = row.same_target_id or existing_id(view, row.name, row.kind)
        return _Part(row.kind, row.name, previous, now, known, row=row)
    item = next(
        (
            i
            for i in _items(preview)
            if i.get("name") and name_key(str(i["name"])) == wanted
        ),
        None,
    )
    if item is None:
        raise ValueError(f"no entry, new name or item {wanted!r} in the preview")
    return _Part(
        _item_kind(view, item) or "lore",
        str(item["name"]),
        item.get("part_of"),
        # an item sits in its drawer of the sphere
        {**_own_sphere(preview), "drawer": item["drawer_id"]},
        item.get("thing_id") or None,
        item=item,
    )


def _home_in_preview(preview: CreatePreview | FillPreview, key: str) -> object:
    """The `part_of` the preview gives the thing named `key`: the entry's,
    a new name's or an item's."""

    if isinstance(preview, CreatePreview) and name_key(preview.name) == key:
        return preview.part_of
    for row in _rows(preview):
        if name_key(row.name) == key:
            return row.part_of
    for item in _items(preview):
        if name_key(str(item.get("name") or "")) == key:
            return item.get("part_of")
    return None


def _inside_by_name(
    preview: CreatePreview | FillPreview, start: str, part: str
) -> bool:
    """Whether the thing named `start` (a name key) is the part, or sits in
    it, through the `part_of` names the preview gives."""

    seen: set[str] = set()
    current: str | None = start
    while current is not None and current not in seen:
        if current == part:
            return True
        seen.add(current)
        current = home_name(_home_in_preview(preview, current))
    return False


def add_outer_body(
    world: World,
    preview: P,
    row_name: str,
    outer: OuterBody,
    *,
    as_sphere: bool = False,
) -> P:
    """Put the outer body the owner named around the part `row_name` (the
    entry the preview writes, ruling C11; a new name of it; an elsewhere
    item's new target; or a named item of a sphere's core or Fill), and
    return the preview: the part is filed in it, the body is a new
    `sphere` name with its template and filing, and each entry filed where
    the body goes gets an unticked re-file row, as does a new name the
    owner marked as an entry filed elsewhere. Naming another body for the
    same part replaces the first (with its re-file rows); a body already
    named for another part is shared, and a new name the preview lists of
    another kind becomes it only `as_sphere`. Writes nothing, asks no
    model.

    A `ValueError` for: no such part; a part of a kind no drawer holds; an
    unknown template; a body named as the entry being made, or another
    kind's name (without `as_sphere`); a body that is the part or sits in
    it, by the preview's names or the world's filings; or a filing that
    isn't a sphere's drawer a sphere goes in."""

    view = world.view()
    name = " ".join(outer.name.split()) or outer_name(row_name)
    key = name_key(name)
    if outer.template not in SPHERE_TEMPLATES:
        raise ValueError(f"no such sphere template: {outer.template!r}")
    wanted = name_key(row_name)
    if not wanted or wanted == key:
        raise ValueError("a part can't be its own outer body")
    part = _find_part(view, preview, wanted)
    if isinstance(preview, CreatePreview) and name_key(preview.name) == key:
        raise ValueError(f"the outer body can't be {preview.name}, the entry itself")
    if part.kind not in PART_OF_KINDS:
        raise ValueError(f"a {part.kind} can't be part of a sphere")
    # where the outer body goes: the owner's filing, else where the part
    # is filed now
    home = (
        _checked_home(view, outer.part_of)
        if outer.part_of is not None
        else (dict(part.now) if part.now is not None else None)
    )

    # no cycle: the body isn't the part nor inside it, and nor is its home
    if _inside_by_name(preview, key, wanted) or (
        home is not None
        and "name" in home
        and _inside_by_name(preview, name_key(home["name"]), wanted)
    ):
        raise ValueError(f"{name} would be inside {part.name}")
    known = existing_id(view, name, "sphere")
    if part.thing_id is not None:
        inside = known is not None and spheres.sits_in(view, known, part.thing_id)
        if home is not None and isinstance(home.get("sphere"), str):
            inside = inside or spheres.sits_in(view, home["sphere"], part.thing_id)
        if inside:
            raise ValueError(f"{name} would be inside {part.name}")

    named = next((n for n in _rows(preview) if name_key(n.name) == key), None)
    if named is not None and named.kind != "sphere" and not as_sphere:
        raise ValueError(
            f"{named.name} is listed as a {named.kind}: make it a sphere first"
        )

    if home is not None:
        drawers = _sphere_drawers(view, preview, home)
        home["drawer"] = spheres.entry_drawer(drawers, "sphere", home["drawer"], name)

    # the part's drawer in the body: a sphere the world has gives one for
    # its kind; a new stub has none yet
    known_state = view.thing(known) if known is not None else None
    inner_drawer = UNSORTED_DRAWER_ID
    if known_state is not None and spheres.is_sphere(known_state):
        inner_drawer = spheres.entry_drawer(
            spheres.drawers(view, known_state.id), part.kind, None, part.name
        )
    to = {"name": name, "drawer": inner_drawer}

    # a body named before for this part gives way
    before = home_name(part.previous)
    if before is not None and before != key:
        _drop_outer(preview, before, wanted)

    if part.row is not None:
        part.row.part_of = dict(to)
    elif part.item is not None:
        part.item["part_of"] = dict(to)
    else:
        assert isinstance(preview, CreatePreview)
        preview.part_of = dict(to)

    # the body's own row: a name the preview lists already becomes it
    named = next((n for n in _rows(preview) if name_key(n.name) == key), None)
    if named is None:
        preview.new_names.append(
            NewName(name=name, kind="sphere", template=outer.template, part_of=home)
        )
    else:
        named.kind, named.template = "sphere", outer.template
        if outer.part_of is not None or named.part_of is None:
            named.part_of = home

    # never the entry the preview fills, nor the thing the part is
    skip = {t for t in (_entry_target(preview), part.thing_id) if t}
    taken = {r.get("thing_id") for r in preview.refile}
    rows = _refile_rows(view, preview, home, to, skip) if home is not None else []
    # a new name marked as an entry filed somewhere: moved only if ticked
    target = part.row.same_target_id if part.row is not None else None
    state = view.thing(target) if target else None
    if state is not None and state.fields.get("part_of") is not None:
        rows.append(
            {
                "thing_id": state.id,
                "from": state.fields.get("part_of"),
                "to": dict(to),
                "ticked": False,
            }
        )
    preview.refile.extend(r for r in rows if r["thing_id"] not in taken)
    if isinstance(preview, CreatePreview) and part.row is None and part.item is None:
        # the outer body is the entry's broader one now: its facts may move
        # in, or none, when it's new (`create.offer_move_in`); a sphere
        # core's too (ruling C32)
        offer_move_in(view, preview)
    return preview


def _drop_outer(preview: CreatePreview | FillPreview, key: str, part: str) -> None:
    """Take out the outer body `key` (a name key) the part `part` had, and
    its re-file rows, unless another part is still filed in it."""

    entry = isinstance(preview, CreatePreview) and (
        name_key(preview.name) != part and home_name(preview.part_of) == key
    )
    still = (
        entry
        or any(
            name_key(r.name) != part and home_name(r.part_of) == key
            for r in _rows(preview)
        )
        or any(
            name_key(str(i.get("name") or "")) != part
            and home_name(i.get("part_of")) == key
            for i in _items(preview)
        )
    )
    if still:
        return
    preview.new_names = [n for n in preview.new_names if name_key(n.name) != key]
    preview.refile = [r for r in preview.refile if home_name(r.get("to")) != key]
