import structlog

from talemate.agents.base import Agent, AgentAction, AgentActionConfig
from talemate.agents.registry import register
from talemate.client import ClientBase
from talemate.languages.making import MakeSettings

__all__ = ["LanguageAgent"]

log = structlog.get_logger("talemate.agents.language")

GUIDANCE = (
    "A whole language (its dictionary, phrases and naming rules) needs a "
    "strong model: Claude Code, or a large model on an API. Small local "
    "models do well at picking names and writing short meanings, which "
    "always run here."
)


@register()
class LanguageAgent(Agent):
    """
    Language agent

    Makes languages and names with them, for every world: its client
    picks names and writes short meanings, and its settings say how whole
    languages are made. Nothing world-specific is kept here.
    """

    agent_type = "language"
    verbose_name = "Language"
    essential = False

    @classmethod
    def init_actions(cls) -> dict[str, AgentAction]:
        return {
            "making": AgentAction(
                label="Making languages",
                container=True,
                icon="mdi-translate",
                description=GUIDANCE,
                config={
                    "route": AgentActionConfig(
                        type="text",
                        label="Make whole languages with",
                        value="claude_code",
                        choices=[
                            {
                                "label": "Claude Code on this computer",
                                "value": "claude_code",
                            },
                            {"label": "This agent's model", "value": "in_app"},
                            {
                                "label": "Copy the brief (I'll use my own assistant)",
                                "value": "brief",
                            },
                        ],
                    ),
                    "claude_command": AgentActionConfig(
                        type="text",
                        label="Claude Code command",
                        value="claude",
                    ),
                    "claude_model": AgentActionConfig(
                        type="text",
                        label="Claude Code model (empty: its default)",
                        value="",
                    ),
                },
            )
        }

    def __init__(self, client: ClientBase | None = None, **kwargs):
        self.client = client
        self.scene = None
        self.is_enabled = True
        self.actions = LanguageAgent.init_actions()

    @property
    def enabled(self):
        return self.is_enabled

    @property
    def has_toggle(self):
        return False

    def make_settings(self) -> MakeSettings:
        config = self.actions["making"].config
        return MakeSettings(
            route=config["route"].value,
            claude_command=str(config["claude_command"].value or "claude"),
            claude_model=str(config["claude_model"].value or ""),
        )
