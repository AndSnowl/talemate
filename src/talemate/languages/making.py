"""Making a language from inside the app (languages 3b): the route
settings, and the job that runs a route."""

from typing import Literal

from pydantic import BaseModel

__all__ = ["MakeSettings"]

Route = Literal["claude_code", "in_app", "brief"]


class MakeSettings(BaseModel):
    """How languages are made, from the language agent's settings: on
    Claude Code on this computer, on the agent's own model, or by copying
    the brief to any assistant."""

    route: Route = "claude_code"
    claude_command: str = "claude"
    claude_model: str = ""
