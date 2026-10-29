"""The brief every outside route gets (languages 3b-1, Task 2)."""

import json
import re
from pathlib import Path

from talemate.languages.brief import BRIEF_FILE_NAME, write_brief
from talemate.languages.making import MakeRequest, QuestionAnswer
from talemate.world.store import Source

SCHEMA = Path("src/talemate/languages/language.schema.json")
LABELS = Path("docs/superpowers/probes/raw/2026-10-28-language-make-labels.json")
REQUEST = "a unique but recognizably Russian language for the Tsardom of Moscavia"


def _blocks(brief):
    return re.findall(r"```json\n(.*?)\n```", brief, re.S)


def test_the_brief_file_name():
    assert BRIEF_FILE_NAME == "brief.md"


def test_a_brief_carries_the_request_and_answers():
    request = MakeRequest(
        text=REQUEST,
        answers=[QuestionAnswer(question="How Russian should it sound?", answer="Very")],
    )
    brief = write_brief(None, request)
    assert brief.startswith("# Make a language for a fantasy world")
    assert "## What the owner asked for" in brief
    assert REQUEST in brief
    assert "- Q: How Russian should it sound? / A: Very" in brief


def test_decide_for_me_is_said_plainly():
    brief = write_brief(None, MakeRequest(text=REQUEST, decide_for_me=True))
    assert "The owner said: decide for me." in brief


def test_the_world_section_lists_chosen_entries_facts(world):
    with world.revision(Source.manual()) as rev:
        tsardom = rev.create_thing("place", {"name": "Tsardom of Moscavia"})
        rev.add_fact(tsardom, "description", "Cold northern realm.")
        gone = rev.create_thing("place", {"name": "Gone"})
    with world.revision(Source.manual()) as rev:
        rev.remove_thing(gone)
    brief = write_brief(world.view(), MakeRequest(text=REQUEST, context_ids=[tsardom]))
    assert "## The world" in brief
    assert "### Tsardom of Moscavia (place)" in brief
    assert "- description: Cold northern realm." in brief

    assert "## The world" not in write_brief(world.view(), MakeRequest(text=REQUEST))
    assert "## The world" not in write_brief(
        world.view(), MakeRequest(text=REQUEST, context_ids=[gone])
    )


def test_the_file_section_has_the_schema_and_example():
    brief = write_brief(None, MakeRequest(text=REQUEST))
    assert "## The file" in brief
    blocks = _blocks(brief)
    assert json.loads(blocks[0]) == json.loads(SCHEMA.read_text())
    example = json.loads(blocks[1])
    assert example["format"] == "fantasymate.language"
    assert "1–3 words" in brief and "never a sentence" in brief
    assert "no real words" in brief.lower()
    assert "`words` generator" in brief


def test_the_check_section_follows_the_route():
    with_check = write_brief(None, MakeRequest(text=REQUEST), check_command="./check")
    assert "## Check it" in with_check
    assert "`./check " in with_check and "on its own line" in with_check
    copied = write_brief(None, MakeRequest(text=REQUEST))
    assert "./check" not in copied
    assert "one ```json code block" in copied


def test_the_brief_has_no_jargon():
    jargon = json.loads(LABELS.read_text())["jargon"]
    brief = write_brief(None, MakeRequest(text=REQUEST, decide_for_me=True))
    # the schema and example are the file's own shape; the prose around them
    # is what the owner and the assistant read as instructions
    prose = re.sub(r"```json\n.*?\n```", "", brief, flags=re.S)
    found = [j for j in jargon if re.search(rf"\b{re.escape(j)}\b", prose, re.I)]
    assert found == []
