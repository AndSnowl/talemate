"""What in a world uses one thing, checked before that thing is deleted.

`thing_references` gathers three kinds of use, each as named,
human-readable entries for the delete dialog:

- other things' facts that reference it (`[[thing:<id>]]`), on any story
  date;
- other things' `thing`, `things` and `shares` fields that point at it
  (a character's `heritage`, a race's `species`, a mix's `parents`, ...),
  on any story date (a value set once and since replaced still renders as
  unknown on the dates it held);
- scenes that use it as the player, a character, the place or pulled-in
  lore.
"""

from __future__ import annotations

import structlog

from talemate.world.kinds import get_kind
from talemate.world.store import World

log = structlog.get_logger("talemate.worldplay.references")

__all__ = ["thing_references"]


def _points_at(field_type: str, value: object, thing_id: str) -> bool:
    if field_type == "thing":
        return value == thing_id
    if field_type == "things" and isinstance(value, list):
        return thing_id in value
    if field_type == "shares" and isinstance(value, list):
        return any(
            isinstance(share, dict) and share.get("thing_id") == thing_id
            for share in value
        )
    return False


def _fact_entries(world: World, thing_id: str) -> list[dict]:
    view = world.view()
    return [
        {
            "thing_id": owner,
            "thing_name": view.name_of(owner) or "",
            "text": view.render(fact.text),
        }
        for owner, fact in view.referencing(thing_id, any_date=True)
        if owner != thing_id
    ]


def _field_entries(world: World, thing_id: str) -> list[dict]:
    view = world.view()
    entries = []
    for state in view.things():
        if state.id == thing_id:
            continue
        types = {spec.name: spec.type for spec in get_kind(state.kind).fields}
        fields = {
            entry.field
            for entry in world.timeline(state.id)
            if entry.change == "field"
            and entry.field is not None
            and _points_at(types.get(entry.field, ""), entry.value, thing_id)
        }
        for field in sorted(fields):
            entries.append(
                {
                    "thing_id": state.id,
                    "thing_name": view.name_of(state.id) or "",
                    "field": field,
                }
            )
    return entries


def _scene_roles(record_state: dict, player: str | None, thing_id: str) -> list[str]:
    roles = []
    if player == thing_id:
        roles.append("player")
    characters = record_state.get("characters") or []
    if any(
        isinstance(entry, dict) and entry.get("thing_id") == thing_id
        for entry in characters
    ):
        roles.append("character")
    if record_state.get("place_thing_id") == thing_id:
        roles.append("place")
    if thing_id in (record_state.get("pulled_in") or []):
        roles.append("lore")
    return roles


def _scene_entries(world: World, thing_id: str) -> list[dict]:
    return [
        {"scene_id": record.id, "name": record.name, "role": role}
        for record in world.scenes().list()
        for role in _scene_roles(record.state, record.player_thing_id, thing_id)
    ]


def thing_references(world: World, thing_id: str) -> dict[str, list[dict]]:
    """Everything in `world` that uses `thing_id`, as of the head revision:
    `{"facts": [{thing_id, thing_name, text}], "fields": [{thing_id,
    thing_name, field}], "scenes": [{scene_id, name, role}]}`. A fact's
    text is rendered with names; a scene's role is `player`, `character`,
    `place` or `lore`."""

    return {
        "facts": _fact_entries(world, thing_id),
        "fields": _field_entries(world, thing_id),
        "scenes": _scene_entries(world, thing_id),
    }
