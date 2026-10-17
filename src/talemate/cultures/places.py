"""Place nesting, effective culture mix, and place edits.

Places form a forest (via `Place.parent_id`); every function here is pure,
walks ancestor chains with a visited set (so even a corrupt file with a
cycle can't loop forever), and returns new lists rather than mutating its
input.
"""

from __future__ import annotations

from .models import Culture, CultureShare, Place

__all__ = [
    "PlaceError",
    "effective_mix",
    "country_of",
    "children",
    "reparent",
    "set_shares",
    "set_share",
    "delete_place",
    "describe_mix",
]


class PlaceError(ValueError):
    """Raised for an unknown place id, or a move that would create a cycle."""


def _find(places: list[Place], place_id: str | None) -> Place | None:
    if place_id is None:
        return None
    for place in places:
        if place.id == place_id:
            return place
    return None


def _replace(places: list[Place], place_id: str, **updates) -> list[Place]:
    """Return `places` with `place_id`'s fields updated to `updates`."""

    return [
        place.model_copy(update=updates) if place.id == place_id else place
        for place in places
    ]


def _distribute(items: list[tuple[str, int]], total: int) -> list[tuple[str, int]]:
    """Split `total` across `items` proportional to their weights.

    Uses largest-remainder rounding so the resulting integers sum exactly
    to `total`. Ties in the remainder are broken by original order.
    """

    weight_sum = sum(weight for _, weight in items)
    if total <= 0 or weight_sum <= 0:
        return [(key, 0) for key, _ in items]

    allocated: list[list] = []
    remainders: list[float] = []
    for key, weight in items:
        exact = weight * total / weight_sum
        floor_value = int(exact)
        allocated.append([key, floor_value])
        remainders.append(exact - floor_value)

    remaining = total - sum(value for _, value in allocated)
    order = sorted(range(len(items)), key=lambda i: (-remainders[i], i))
    for i in order[:remaining]:
        allocated[i][1] += 1

    return [(key, value) for key, value in allocated]


def effective_mix(
    places: list[Place], place_id: str
) -> tuple[list[CultureShare], Place | None]:
    """Return the culture mix that applies at `place_id`.

    Walks up from `place_id` to the nearest ancestor (or itself) that has
    its own cultures, and returns that mix along with the place it came
    from. Returns `([], None)` if no place in the chain has cultures.
    """

    visited: set[str] = set()
    current_id: str | None = place_id
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        place = _find(places, current_id)
        if place is None:
            return [], None
        if place.cultures:
            return list(place.cultures), place
        current_id = place.parent_id
    return [], None


def country_of(places: list[Place], place_id: str) -> Place | None:
    """Return the nearest ancestor (or self) of kind `country`, or `None`."""

    visited: set[str] = set()
    current_id: str | None = place_id
    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        place = _find(places, current_id)
        if place is None:
            return None
        if place.kind == "country":
            return place
        current_id = place.parent_id
    return None


def children(places: list[Place], place_id: str) -> list[Place]:
    """Return the direct children of `place_id`."""

    return [place for place in places if place.parent_id == place_id]


def reparent(
    places: list[Place], place_id: str, new_parent_id: str | None
) -> list[Place]:
    """Return `places` with `place_id` moved under `new_parent_id`.

    Raises `PlaceError` if either id is unknown, or if `new_parent_id` is
    `place_id` itself or one of its descendants (which would create a
    cycle).
    """

    if _find(places, place_id) is None:
        raise PlaceError(f"unknown place: {place_id}")

    if new_parent_id is not None:
        if _find(places, new_parent_id) is None:
            raise PlaceError(f"unknown place: {new_parent_id}")
        if _is_self_or_descendant(places, new_parent_id, place_id):
            raise PlaceError(
                f"cannot move {place_id} under its own descendant {new_parent_id}"
            )

    return _replace(places, place_id, parent_id=new_parent_id)


def _is_self_or_descendant(
    places: list[Place], candidate_id: str, place_id: str
) -> bool:
    """Return whether `candidate_id` is `place_id` or one of its descendants."""

    visited: set[str] = set()
    current_id: str | None = candidate_id
    while current_id is not None and current_id not in visited:
        if current_id == place_id:
            return True
        visited.add(current_id)
        parent = _find(places, current_id)
        current_id = parent.parent_id if parent else None
    return False


def set_shares(
    places: list[Place], place_id: str, shares: list[CultureShare]
) -> list[Place]:
    """Return `places` with `place_id`'s cultures replaced by `shares`.

    Zero (or negative) shares are dropped, and the remaining shares are
    normalised to integers summing to 100 (largest-remainder rounding).
    Marks the place `set_by="owner"` and `unsure=False`.
    """

    if _find(places, place_id) is None:
        raise PlaceError(f"unknown place: {place_id}")

    weighted = [(cs.culture_id, cs.share) for cs in shares if cs.share > 0]
    if weighted:
        allocated = _distribute(weighted, 100)
        new_cultures = [
            CultureShare(culture_id=culture_id, share=share)
            for culture_id, share in allocated
        ]
    else:
        new_cultures = []

    return _replace(
        places, place_id, cultures=new_cultures, set_by="owner", unsure=False
    )


def set_share(
    places: list[Place], place_id: str, culture_id: str, share: int
) -> list[Place]:
    """Return `places` with one culture's share at `place_id` set exactly.

    `share` is clamped to 0..100. The place's other shares are scaled
    proportionally (largest-remainder rounding) to fill the remainder; a
    culture new to the place is added at `share`. If the place has no
    other shares to scale, the single culture is set to 100 instead (there
    is nothing to make up the remainder from), or, for a share of 0,
    removed, leaving the place with no cultures of its own. Marks the
    place `set_by="owner"` and `unsure=False`.
    """

    place = _find(places, place_id)
    if place is None:
        raise PlaceError(f"unknown place: {place_id}")

    share = max(0, min(100, share))
    others = [cs for cs in place.cultures if cs.culture_id != culture_id]

    if not others:
        new_cultures = (
            [CultureShare(culture_id=culture_id, share=100)] if share > 0 else []
        )
    else:
        remainder = 100 - share
        weight_sum = sum(cs.share for cs in others)
        if weight_sum > 0:
            weighted = [(cs.culture_id, cs.share) for cs in others]
        else:
            weighted = [(cs.culture_id, 1) for cs in others]
        scaled = _distribute(weighted, remainder)
        new_cultures = [CultureShare(culture_id=culture_id, share=share)] + [
            CultureShare(culture_id=culture_id_, share=share_)
            for culture_id_, share_ in scaled
        ]
        new_cultures = [cs for cs in new_cultures if cs.share > 0]

    return _replace(
        places, place_id, cultures=new_cultures, set_by="owner", unsure=False
    )


def delete_place(
    places: list[Place], place_id: str, move_children_to: str | None
) -> list[Place]:
    """Return `places` without `place_id`, re-parenting its children.

    Raises `PlaceError` if `move_children_to` is unknown, or is `place_id`
    itself or one of its descendants (the children would be left pointing
    at a deleted place, or in a cycle).
    """

    if _find(places, place_id) is None:
        raise PlaceError(f"unknown place: {place_id}")
    if move_children_to is not None:
        if _find(places, move_children_to) is None:
            raise PlaceError(f"unknown place: {move_children_to}")
        if _is_self_or_descendant(places, move_children_to, place_id):
            raise PlaceError(
                f"cannot move the children of {place_id} into itself or one of "
                f"its own descendants ({move_children_to})"
            )

    result = []
    for place in places:
        if place.id == place_id:
            continue
        if place.parent_id == place_id:
            place = place.model_copy(update={"parent_id": move_children_to})
        result.append(place)
    return result


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def describe_mix(
    places: list[Place], cultures: dict[str, Culture], place_id: str
) -> str:
    """Return the plain-language sentence describing `place_id`'s culture mix."""

    mix, source = effective_mix(places, place_id)
    if not mix or source is None:
        return ""

    ordered = sorted(mix, key=lambda cs: -cs.share)
    own_dominant = ordered[0].culture_id

    # Compare against the mix *around* the source of this place's mix, so a
    # place that inherits from a pocket (a village in a region whose people
    # differ from the country's) gets the suffix too, not just the pocket.
    suffix = ""
    if source.parent_id is not None:
        parent_mix, parent_source = effective_mix(places, source.parent_id)
        if parent_mix and parent_source is not None:
            parent_dominant_share = max(parent_mix, key=lambda cs: cs.share)
            if parent_dominant_share.culture_id != own_dominant:
                parent_culture = cultures.get(parent_dominant_share.culture_id)
                if parent_culture is not None:
                    suffix = (
                        f" Most also speak {parent_culture.language.name}, "
                        f"the language of {parent_source.name}."
                    )

    if len(ordered) == 1:
        culture = cultures.get(ordered[0].culture_id)
        if culture is None:
            return ""
        return (
            f"New people here are {culture.name}, named from {culture.language.name}."
            + suffix
        )

    def name_of(cs: CultureShare) -> str:
        culture = cultures.get(cs.culture_id)
        return culture.name if culture is not None else cs.culture_id

    tenths = [(cs, round(cs.share / 10)) for cs in ordered]
    shown = [(cs, tenth) for cs, tenth in tenths if tenth > 0]

    if tenths[0][1] >= 10 or len(shown) <= 1:
        # "10 in 10 X and 0 in 10 Y" reads wrong: the top culture is nearly
        # everyone, so say that, and name the rest as "a few".
        joined = f"almost all {name_of(ordered[0])}, a few " + _join(
            [name_of(cs) for cs in ordered[1:]]
        )
    else:
        entries = [f"{tenth} in 10 {name_of(cs)}" for cs, tenth in shown]
        entries[0] = f"about {entries[0]}"
        joined = _join(entries)

    text = (
        f"New people here are drawn from the mix: {joined}. "
        "Each is named from their own culture's language."
    )

    return text + suffix
