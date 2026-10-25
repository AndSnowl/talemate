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


# markdown emphasis as a model writes it into a fact (hubs round 1, P2):
# `***x***`, then `**x**`/`__x__`, then `*x*`/`_x_`. A marker opens only after
# a non-word character and before a non-space, and closes only after a
# non-space and before a non-word character, so a lone asterisk ("Sir
# *Bob"), arithmetic ("2*3*4", "a * b * c") and snake_case stay as they
# are. Emphasis never crosses a line break.
_EMPHASIS = [
    re.compile(r"(?<![\w*])\*\*\*(?=[^\s*])([^\n*]*?[^\s*])\*\*\*(?![\w*])"),
    re.compile(r"(?<![\w*])\*\*(?=[^\s*])([^\n]*?[^\s*])\*\*(?![\w*])"),
    re.compile(r"(?<!\w)__(?=[^\s_])([^\n]*?[^\s_])__(?!\w)"),
    re.compile(r"(?<![\w*])\*(?=[^\s*])([^\n*]*?[^\s*])\*(?![\w*])"),
    re.compile(r"(?<!\w)_(?=[^\s_])([^\n_]*?[^\s_])_(?!\w)"),
]
# a reference stands in as this while emphasis is scrubbed: no marker
# character, and never written by a model
_HOLD = "{}"
_HELD = re.compile("(\\d+)")


def scrub_emphasis(text: str) -> str:
    """`text` without markdown emphasis (`*x*`, `**x**`, `_x_`, `__x__`),
    keeping the words inside it: "*Boyar Council*" is "Boyar Council".
    A reference token is never touched, nor are the words it shows, though
    emphasis around one goes ("*[[thing:...|Boyar Council]]*"). For fact
    text only: a scene's or prose's emphasis is the writer's own."""

    tokens: list[str] = []

    def hold(match: re.Match[str]) -> str:
        tokens.append(match.group(0))
        return _HOLD.format(len(tokens) - 1)

    held = REF_PATTERN.sub(hold, text)
    for pattern in _EMPHASIS:
        held = pattern.sub(r"\1", held)

    def back(match: re.Match[str]) -> str:
        # a placeholder the text held already (no reference of ours) stays
        index = int(match.group(1))
        return tokens[index] if index < len(tokens) else match.group(0)

    return _HELD.sub(back, held)
