"""Reference tokens inside fact text.

A fact's text may reference other things with a `[[thing:<id>]]` token,
rendered with the referenced thing's name on the viewing date.
"""

import re

import structlog

log = structlog.get_logger("talemate.world.refs")

REF_PATTERN = re.compile(r"\[\[thing:([0-9a-f]{32})\]\]")


def ref(thing_id: str) -> str:
    """Format a reference token for `thing_id`."""

    return f"[[thing:{thing_id}]]"


def parse_refs(text: str) -> list[str]:
    """Return the thing ids referenced in `text`, in first-seen order, with
    duplicates removed."""

    seen: dict[str, None] = {}
    for match in REF_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return list(seen)
