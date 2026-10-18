"""AI test: the "Cultures and names" section reaches the narrator's prompt.

Opt-in (see tests/ai/conftest.py); this test is auto-marked `ai`. It checks
that the section was injected and that the prompt actually carries it and
the spare names it offered -- not the section's wording.
"""

from __future__ import annotations

from ai.cultures.scenarios import SCENARIOS, seed_scenario
from talemate.cultures.context import SPARE_NAMES_PREFIX


def test_narrator_prompt_contains_culture_section(ai_app, session):
    world = seed_scenario(
        ai_app.root,
        "ai-context-taelrik",
        SCENARIOS["taelrik_town"],
        with_trait_character=True,
    )
    session.wait_client_ready()
    session.load_scene(world.scene_path)

    mark = session.mark()
    # Not `session.narrate()`: loading a scene can push an unsolicited,
    # untagged "narrator" message shortly after (the scene's intro being
    # replayed), which races with this request and would make `narrate()`
    # return on that stale message instead of waiting for this one. A
    # `prompt_sent` for the narrator is specific to this call and only
    # arrives once it's actually done, so waiting for that -- while still
    # recording every message seen along the way, including any
    # `context_injected` -- can't be fooled by the stray message.
    session.send(
        {"type": "narrator", "action": "narrate_environment", "narrative_direction": ""}
    )

    def failed(message: dict) -> bool:
        return message.get("type") == "narrator" and message.get("action") == (
            "operation_done"
        )

    session.wait_for(
        lambda m: m.get("type") == "prompt_sent"
        and (m.get("data") or {}).get("agent_type") == "narrator",
        timeout=600,
        error=failed,
    )

    narrator_events = [
        event
        for event in session.events("context_injected", mark)
        if event.get("agent") == "narrator"
    ]
    assert narrator_events, "no context_injected event for the narrator"
    event = next(
        (e for e in narrator_events if "Veldhaer" in (e.get("text") or "")), None
    )
    assert event is not None, [e.get("text") for e in narrator_events]

    spares = event.get("spares") or []
    assert spares, "no spare names were offered"

    narrator_prompts = session.prompts("narrator", mark)
    assert narrator_prompts, "no narrator prompt recorded"
    prompt_text = narrator_prompts[0].get("prompt") or ""

    assert SPARE_NAMES_PREFIX in prompt_text
    for spare in spares:
        assert spare["text"] in prompt_text, (spare["text"], prompt_text)
