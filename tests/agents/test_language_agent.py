"""The global language agent: its client and how languages get made
(languages 3b-1, Task 1)."""

from talemate.agents.registry import AGENT_CLASSES
from talemate.languages.making import MakeSettings


def test_the_language_agent_is_registered():
    assert "language" in AGENT_CLASSES


def test_its_making_settings_default_to_claude_code():
    agent = AGENT_CLASSES["language"]()
    assert agent.make_settings() == MakeSettings(
        route="claude_code", claude_command="claude", claude_model=""
    )


def test_changed_settings_come_back():
    agent = AGENT_CLASSES["language"]()
    agent.actions["making"].config["route"].value = "in_app"
    agent.actions["making"].config["claude_model"].value = "sonnet"
    settings = agent.make_settings()
    assert (settings.route, settings.claude_model) == ("in_app", "sonnet")


def test_the_guidance_says_which_jobs_need_a_strong_model():
    agent = AGENT_CLASSES["language"]()
    guidance = agent.actions["making"].description
    assert "strong model" in guidance and "picking names" in guidance
