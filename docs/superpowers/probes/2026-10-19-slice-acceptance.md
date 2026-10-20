# Phase 2A slice: owner acceptance run

Dates: 2026-10-19 to 2026-10-20. Branch `feature/phase-2a-slice`, first run at f0ebf00d, last at aef68877. The model was koboldcpp serving Skyfall-31B-v4.2-i1-Q4_K_M.

## Result

Accepted. All three acceptance tests pass:

1. **Parity with Simulation v2, bare setup:** a scene started from a prompt plays as it does in stock Talemate.
2. **Parity with world characters:** a world character (Vasha) is used as the player in a scene set up from a free-form prompt.
3. **Dated facts:** a scar fact dated mid-story appears in a scene set after its date and not in one set before.

## Hiccups found and fixed

| # | Symptom | Root cause | Fix |
|---|---------|------------|-----|
| 1 | Creating a thing from a prompt failed with "Scene is no longer active" | World-level AI calls run with no active scene; `ClientBase._send_prompt` refuses them, and MockClient skips the check, so tests missed it. A second crash followed: no active agent in `tune_prompt_parameters`. | 56df975f: `worldplay/ai.py` `world_ai_call()` lifts `requires_active_scene` and makes the creator agent active |
| 2 | Prose came out as short stories, and the personality section drifted to a human | The prose prompt asked for a description, and the model wrote a scene. A section built from one fact category had no identity context. | 93d26e9b (probe, `2026-10-20-prose-register.md`) and daf21459: a reference-entry prompt, the "analyze" kind, and the thing's other facts as background. Owner confirmed it's consistent at temp 0.7 |
| 3 | A duplicate character with no way to delete it | No delete feature existed | 831d55d3 and 1fe2f309: delete a thing, with a reference check across all story dates and a confirmation dialog (owner request, spec rule af94a05d on main) |
| 4 | Scene setup failed with "no scene setup found in the model's reply" | Strict JSON decoding rejects raw newlines inside strings, and the model's intro contained a paragraph break | 7a7b3444 and aef68877: a shared non-strict decoder for every reply parse, with the owner's real reply as a test fixture |

A hard browser refresh was needed after the last restart, because the browser was still running the old frontend.

## Noted for later

- **Scene titles:** the slice names a scene from its goal sentence, cut to 60 characters (`setup._scene_name`), so titles read as descriptions. Stock Talemate asks the model for a book-style title (`creator.generate_title`). The owner deferred this until the scene machinery is properly ported.
- **Invented named things** (e.g. Aldric, invented while generating Vasha): offer to create a full entry. It's in the spec as a later feature.
- **Moddable generators** alongside scene runners: in the spec.
