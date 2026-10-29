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
        answers=[
            QuestionAnswer(question="How Russian should it sound?", answer="Very")
        ],
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


# --- 3b-2a: a full language, or a quick core -------------------------------

from talemate.languages.completeness import CORE_MEANINGS  # noqa: E402
from talemate.languages.making import effective_size  # noqa: E402
from talemate.languages.models import GRAMMAR_TOPICS  # noqa: E402


def _what_to_make(brief):
    return brief.split("## What to make", 1)[1].split("\n## ", 1)[0]


def test_a_full_brief_lists_every_core_meaning():
    part = _what_to_make(write_brief(None, MakeRequest(text=REQUEST), size="full"))
    for meaning in CORE_MEANINGS["structural"] + CORE_MEANINGS["everyday"]:
        assert re.search(rf"(^|[ ,]){re.escape(meaning)}(,|$|\n)", part, re.M), meaning
    assert "at least 3" in part


def test_a_quick_brief_keeps_to_the_core():
    part = _what_to_make(write_brief(None, MakeRequest(text=REQUEST), size="quick"))
    for meaning in CORE_MEANINGS["structural"]:
        assert meaning in part
    everyday = [
        m for m in CORE_MEANINGS["everyday"] if re.search(rf"[ ,]{m}(,|\n|$)", part)
    ]
    assert len(everyday) <= 40
    assert "fill in the rest later" in part


def test_both_briefs_describe_grammar_sections_and_topics():
    for size in ("full", "quick"):
        brief = write_brief(None, MakeRequest(text=REQUEST), size=size)
        for topic, _title in GRAMMAR_TOPICS:
            assert f"`{topic}`" in brief, (size, topic)
        assert "tables" in brief and "examples" in brief


def test_effective_size_follows_the_route():
    assert effective_size(MakeRequest(text="x"), "claude_code") == "full"
    assert effective_size(MakeRequest(text="x"), "brief") == "full"
    assert effective_size(MakeRequest(text="x"), "in_app") == "quick"
    assert effective_size(MakeRequest(text="x", size="full"), "in_app") == "full"


def test_a_full_brief_still_has_no_jargon():
    jargon = json.loads(LABELS.read_text())["jargon"]
    brief = write_brief(None, MakeRequest(text=REQUEST), size="full")
    prose = re.sub(r"```json\n.*?\n```", "", brief, flags=re.S)
    found = [j for j in jargon if re.search(rf"\b{re.escape(j)}\b", prose, re.I)]
    assert found == []


def test_the_brief_asks_for_a_part_on_every_word():
    from talemate.languages.models import PARTS_OF_SPEECH

    brief = write_brief(None, MakeRequest(text=REQUEST), size="full")
    assert "every word a `part`" in brief
    for part, _label, _example in PARTS_OF_SPEECH:
        assert f"`{part}`" in brief


# --- 3b-2b: change and fill briefs -------------------------------------------

from talemate.languages.completeness import fill_step  # noqa: E402
from talemate.languages.models import LanguageFile  # noqa: E402

SAMPLE_FILE = LanguageFile.model_validate(
    json.loads(Path("tests/languages/data/sample.language.json").read_text())
)


def test_a_change_brief_carries_the_language_and_the_request():
    request = MakeRequest(
        kind="change", target_id="x", text="redo the curses around debts"
    )
    brief = write_brief(None, request, current=SAMPLE_FILE)
    assert brief.startswith("# Change a language for a fantasy world")
    assert "## What to change" in brief and "redo the curses around debts" in brief
    assert "## The language now" in brief
    blocks = _blocks(brief)
    assert any(
        json.loads(b).get("language", {}).get("name") == "Velskar" for b in blocks
    )
    assert "Return the whole file with your changes" in brief
    assert "Keep the language's name" in brief


def test_a_change_brief_lists_the_used_words():
    request = MakeRequest(kind="change", target_id="x", text="more words")
    brief = write_brief(None, request, current=SAMPLE_FILE, used=["veltasun", "kor"])
    assert "keep them exactly as they are: veltasun, kor" in brief


def test_a_fill_brief_lists_what_is_missing():
    from talemate.languages.completeness import completeness

    request = MakeRequest(kind="fill", target_id="x", text="")
    brief = write_brief(None, request, current=SAMPLE_FILE)
    assert "## What to add" in brief
    for meaning in completeness(SAMPLE_FILE.language).meanings_missing:
        assert meaning in brief
    assert "Keep everything else as it is" in brief


def test_fill_step_order_and_none_when_complete():
    from talemate.languages.models import Language

    assert fill_step(SAMPLE_FILE.language) == "words"
    assert fill_step(Language(name="x", level="naming")) is None
