"""Reference tokens inside fact text.

A fact's text may reference other things with a `[[thing:<id>]]` token,
rendered with the referenced thing's name on the viewing date, or with a
`[[thing:<id>|<shown>]]` token that keeps the words actually written
("Moscavia" for the Tsardom of Moscavia). A shown text holds no `]]` and no
line break; `WorldView.render` decides what it renders as.
"""

import re

import structlog

log = structlog.get_logger("talemate.world.refs")

# group 1 is the thing id, group 2 the shown text (None when there's none)
REF_PATTERN = re.compile(r"\[\[thing:([0-9a-f]{32})(?:\|((?:(?!\]\])[^\n])+))?\]\]")


def ref(thing_id: str, shown: str | None = None) -> str:
    """Format a reference token for `thing_id`, keeping `shown` as the
    written text when given. Raises `ValueError` for a shown text the token
    couldn't hold: empty, or with `]]`, a trailing `]` or a line break."""

    if shown is None:
        return f"[[thing:{thing_id}]]"
    if not shown or "]]" in shown or shown.endswith("]") or "\n" in shown:
        raise ValueError(f"a reference can't show {shown!r}")
    return f"[[thing:{thing_id}|{shown}]]"


def parse_refs(text: str) -> list[str]:
    """Return the thing ids referenced in `text`, in first-seen order, with
    duplicates removed."""

    seen: dict[str, None] = {}
    for match in REF_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return list(seen)
