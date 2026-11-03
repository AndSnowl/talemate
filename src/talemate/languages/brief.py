"""The brief: what any outside assistant is given to make a language
(languages 3b). It's the same text for every route: Claude Code on this
computer, or any chat assistant the owner pastes it into."""

from pathlib import Path

from talemate.languages.completeness import CORE_MEANINGS, PHRASE_CATEGORIES
from talemate.languages.making import MakeRequest
from talemate.languages.models import GRAMMAR_TOPICS, PARTS_OF_SPEECH
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


QUICK_EVERYDAY = 40
# topics whose forms a table shows
_TABLE_TOPICS = ("nouns", "pronouns", "verbs", "adjectives", "numbers")


def _topics() -> str:
    return "; ".join(f"`{topic}` ({title})" for topic, title in GRAMMAR_TOPICS)


_FORMS_NOTE = (
    "The forms of be and have (am, is, was; has, had) belong in the `verbs` "
    'section\'s table, not as words of their own. If the language shows "the" '
    'and "a" by changing the noun, say how in the `nouns` section instead of '
    "making words for them."
)


def _parts() -> str:
    listed = "; ".join(
        f"`{part}` ({example})" for part, _label, example in PARTS_OF_SPEECH
    )
    return (
        "Give every word a `part`, one of: "
        f'{listed}. Small words have parts too: "in" is a `preposition`, '
        '"and" a `conjunction`.'
    )


def _sections() -> list[str]:
    return [
        _parts(),
        "",
        _FORMS_NOTE,
        "",
        "The grammar is a list of sections. Each has a `title`, a `topic` "
        "(one of the ids below, or `other`), plain `text`, `tables` (each a "
        "`caption`, `columns` and `rows` of cells) and `examples` (each an "
        "`original`, a word-by-word `breakdown` of [word, meaning] pairs, and "
        "a `translation`). Explain everything plainly: whenever you use a "
        "grammar term, say what it means in everyday words.",
        "",
        f"The topics: {_topics()}.",
    ]


def _what(size: str) -> list[str]:
    structural = ", ".join(CORE_MEANINGS["structural"])
    if size == "quick":
        everyday = ", ".join(CORE_MEANINGS["everyday"][:QUICK_EVERYDAY])
        return [
            "## What to make",
            "",
            "A quick core. The owner will fill in the rest later, so keep to this:",
            f"- a word for each of these structural meanings: {structural}",
            f"- a word for each of these everyday meanings: {everyday}",
            "- one phrase each for greeting, farewell, blessing and curse",
            "- a short grammar section for each topic below, with tables only "
            "for `pronouns` and `verbs`",
            "- name rules for characters and places",
            "",
            *_sections(),
        ]
    everyday = ", ".join(CORE_MEANINGS["everyday"])
    tables = ", ".join(f"`{t}`" for t in _TABLE_TOPICS)
    return [
        "## What to make",
        "",
        "A full language, complete enough to use and to read:",
        f"- a word for each of these structural meanings: {structural}",
        f"- a word for each of these everyday meanings: {everyday}",
        "- words for the places and peoples in The world, if any",
        f"- at least 3 phrases in each category: {', '.join(PHRASE_CATEGORIES)}",
        "- a grammar section for every topic below, each with at least one "
        f"example, and a table where the topic has forms ({tables})",
        "- more sections (topic `other`) for anything unusual this language "
        'does, such as "the" joined onto the end of a noun',
        "- name rules for characters, places, items and groups, and one for "
        "what its people are called (a demonym rule)",
        "",
        *_sections(),
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
        '- A meaning is 1–3 words, as in a dictionary ("wind", "great fort"), '
        "never a sentence. A word can have several meanings.",
        "- A word made only to be a name may have no meaning.",
        "- Use no real words or names from the language it sounds like "
        "(its `flavour`): every word is invented.",
        "- A full language needs a `words` generator, whose patterns the "
        "dictionary's own words follow.",
        *_name_grammar_rules(),
    ]


def _name_grammar_rules() -> list[str]:
    """How the grammar for names and composed rules are written (languages
    4b-1); probe 4b-1's wording."""

    return [
        "- `name_grammar` is the grammar names are built with: where describing "
        'words go, how "of" is said, how joined words go, how "the" and '
        '"more than one" are formed (each a list of changes tried in order; '
        "the first whose condition holds is used), and the endings with a "
        "meaning from the word-building table.",
        "- A change's `kind` is `ending` (adds `text`), `swap` (takes off one "
        "of the `|`-listed endings in `drop`, then adds `text`), `word_before`, "
        "`word_after`, or `double` (the first syllable doubled). Its `when` is "
        '`""` (always), `after_vowel`, `after_consonant`, `before_vowel`, '
        '`plural` ("the" on a word made more than one), or `ends:a|o`.',
        "- A name rule can have `shapes` instead of patterns: a name made of "
        "parts, each another rule (`rule`), a fixed word (`word`), or a meaning "
        "(`meaning`: words of the language built from a meaning, with `forms`, "
        "`of` and a `hint` saying what it takes). Use it for naming customs "
        "the grammar describes, such as a name after a place or a deed.",
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


def _change(request: MakeRequest, current, used) -> list[str]:
    lines = ["## What to change", "", f"> {request.text.strip()}", ""]
    lines += _change_rules(used)
    return [*lines, "", *_now(current)]


def _change_rules(used) -> list[str]:
    lines = [
        "- Return the whole file with your changes, not just the changed parts.",
        "- Keep the language's name.",
        "- Keep everything the request doesn't ask you to change as it is.",
    ]
    if used:
        lines.append(
            "- These words name things in the world: keep them exactly as they "
            f"are: {', '.join(used)}"
        )
    return lines


def _now(current) -> list[str]:
    return [
        "## The language now",
        "",
        _json_block(current.model_dump_json(indent=2)),
    ]


def _fill(current, used) -> list[str]:
    from talemate.languages.completeness import completeness, fill_step

    step = fill_step(current.language)
    found = completeness(current.language)
    lines = ["## What to add", ""]
    if step == "words":
        lines.append(
            "Add a word (with its `part`) for each of these meanings: "
            f"{', '.join(found.meanings_missing)}"
        )
    elif step == "phrases":
        lines.append(
            "Add at least 3 phrases in each of these categories: "
            f"{', '.join(found.phrase_categories_missing)}"
        )
    elif step == "grammar":
        lines.append(
            "Write a grammar section for each of these topics, with a table "
            f"where it has forms: {', '.join(found.grammar_topics_missing)}"
        )
    else:
        lines.append("Nothing is missing: make no changes.")
    lines += ["", "Keep everything else as it is.", *_change_rules(used)]
    return [*lines, "", *_now(current)]


def _names(current, used) -> list[str]:
    lines = [
        "## What to add: the grammar for names",
        "",
        "Write `name_grammar` from this language's grammar sections and tables below.",
        "",
        "Then turn the language's naming customs into rules made of parts "
        "(`shapes`): a custom that puts words with a meaning into a name, such "
        'as a second name after the given name ("Owl-of-Stars") or a family '
        'named for its home ("of the Forest"), becomes its own rule, with a '
        "`meaning` part for the words that mean something. When an existing "
        "rule fakes such a custom with fixed words in its patterns, take those "
        "patterns out of it and keep its plain names. Change nothing else.",
        "",
        "Every rule must build the examples the language's tables give: if a "
        "table says a word's forms, the rules applied to that word give them.",
        "",
        *_name_grammar_rules(),
        "",
        *_change_rules(used),
    ]
    return [*lines, "", *_now(current)]


def write_brief(
    view: WorldView | None,
    request: MakeRequest,
    *,
    check_command: str | None = None,
    size: str = "full",
    current=None,
    used=(),
) -> str:
    """The brief for `request`: what was asked, the world it's for (the
    chosen entries' facts), the file format, and how to check it (with
    `check_command` where the assistant can run the app's check)."""

    if request.kind in ("change", "fill", "names") and current is not None:
        if request.kind == "change":
            body = _change(request, current, used)
        elif request.kind == "names":
            body = _names(current, used)
        else:
            body = _fill(current, used)
        head = [
            "# Change a language for a fantasy world",
            "",
            "The owner of a fantasy world wants a change to one of its "
            "languages. The language is below, as the file their app imports.",
        ]
    else:
        body = [*_asked(request), "", *_what(size)]
        head = [
            "# Make a language for a fantasy world",
            "",
            "The owner of a fantasy world wants a language for it, as a file "
            "their app can import: its sounds, words, phrases and naming rules.",
        ]
    lines = [
        *head,
        "",
        *body,
        "",
        *_world(view, request),
        *_file(),
        "",
        *_check(check_command),
    ]
    return "\n".join(lines).rstrip() + "\n"
