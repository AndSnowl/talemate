"""Cleaning names in AI text under review (languages 4a): real names, AI
stock names and stock titles found and replaced by names from the language
in reach, the doubtful ones marked as suspect (spec
docs/superpowers/specs/2026-10-30-fantasymate-languages-4-design.md)."""

from __future__ import annotations


from talemate.prompts import Prompt
from talemate.worldplay import prose_gen
from talemate.worldplay.ai import world_ai_call

PROMPT_KIND = "analyze"

# canned replies by template name ("name-flags", "name-picks",
# "title-rewrites", "language-roles"), standing in for the model in the
# browser tests (`TALEMATE_TEST_FIXED_CLEAN`); None normally
fixed_replies: dict[str, str] | None = None


async def ask(client, template: str, vars: dict) -> str:
    """The reply to `world.<template>`: the fixed one when set, else the
    model's."""

    if fixed_replies is not None and template in fixed_replies:
        return fixed_replies[template]
    prose_gen.require_client(client)
    with world_ai_call():
        _response, extracted = await Prompt.request(
            f"world.{template}", client, PROMPT_KIND, vars=vars
        )
    return extracted["response"]
