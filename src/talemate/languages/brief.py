"""The brief: what any outside assistant is given to make a language
(languages 3b). It's the same text for every route: Claude Code on this
computer, or any chat assistant the owner pastes it into."""

from pathlib import Path

from talemate.languages.making import MakeRequest
from talemate.world.view import WorldView

__all__ = ["BRIEF_FILE_NAME", "write_brief"]

BRIEF_FILE_NAME = "brief.md"

_HERE = Path(__file__).parent
SCHEMA_FILE = _HERE / "language.schema.json"
EXAMPLE_FILE = _HERE / "data" / "example.language.json"

FENCE = "```"


def _json_block(text: str) -> str:
    return f"{FENCE}json\n{text.strip()}\n{FENCE}"


def _asked(request: MakeRequest) -> list[str]:
    lines = ["## What the owner asked for", "", f"> {request.text.strip()}", ""]
    for qa in request.answers:
        if qa.answer.strip():
            lines.append(f"- Q: {qa.question.strip()} / A: {qa.answer.strip()}")
    if request.decide_for_me:
        lines.append("The owner said: decide for me.")
    return lines


def _world(view: WorldView | None, request: MakeRequest) -> list[str]:
    if view is None:
        return []
    entries = []
    for thing_id in request.context_ids:
        state = view.thing(thing_id)
        if state is None:
            continue
        entries.append(f"### {state.fields.get('name', '')} ({state.kind})")
        entries += [
            f"- {fact.category}: {view.render(fact.text)}" for fact in state.facts
        ]
        entries.append("")
    if not entries:
        return []
    return [
        "## The world",
        "",
        "The language belongs to these places and peoples; let it fit them.",
        "",
        *entries,
    ]


def _file() -> list[str]:
    return [
        "## The file",
        "",
        "Write one JSON file named after the language, `<name>.language.json` "
        "(lower case), valid against this schema:",
        "",
        _json_block(SCHEMA_FILE.read_text(encoding="utf-8")),
        "",
        "An example:",
        "",
        _json_block(EXAMPLE_FILE.read_text(encoding="utf-8")),
        "",
        "The rules:",
        "- A meaning is 1–3 words, as in a dictionary (\"wind\", \"great fort\"), "
        "never a sentence. A word can have several meanings.",
        "- A word made only to be a name may have no meaning.",
        "- Use no real words or names from the language it sounds like "
        "(its `flavour`): every word is invented.",
        "- A full language needs a `words` generator, whose patterns the "
        "dictionary's own words follow.",
    ]


def _check(check_command: str | None) -> list[str]:
    if check_command:
        return [
            "## Check it",
            "",
            f"Run `{check_command} <name>.language.json` on its own line (no "
            "other commands with it), and fix the file until it reports no "
            "problems that must be fixed.",
        ]
    return [
        "## Check it",
        "",
        "If you can run code, check that the JSON parses. Return the whole "
        f"file in one {FENCE}json code block, or as a file the owner can "
        "download.",
    ]


def write_brief(
    view: WorldView | None, request: MakeRequest, *, check_command: str | None = None
) -> str:
    """The brief for `request`: what was asked, the world it's for (the
    chosen entries' facts), the file format, and how to check it (with
    `check_command` where the assistant can run the app's check)."""

    lines = [
        "# Make a language for a fantasy world",
        "",
        "The owner of a fantasy world wants a language for it, as a file "
        "their app can import: its sounds, words, phrases and naming rules.",
        "",
        *_asked(request),
        "",
        *_world(view, request),
        *_file(),
        "",
        *_check(check_command),
    ]
    return "\n".join(lines).rstrip() + "\n"
