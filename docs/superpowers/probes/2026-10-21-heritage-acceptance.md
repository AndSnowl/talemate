# Phase 2B heritage: owner acceptance run

Dates: 2026-10-20 to 2026-10-21. Branch `feature/phase-2b-heritage`. The first run was at 3e7cc82e and the last at 83079130. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M.

## Result

**Accepted.** The owner ran the session the spec describes in a fresh world:
- made two species and several races;
- made places;
- generated characters, including a mix;
- played a scene.

The owner confirmed that every fix below works. One example of inheritance in action: an owl-folk origin fact, "everyone in the Tsardom of Moscavia became this race suddenly one day 6 years ago", was dated 994 correctly.

## Hiccups found and fixed

| # | The owner's report | Cause | Fix |
|---|---|---|---|
| 1 | The create preview's inherited checkboxes read backwards (checked meant replaced, under a title "Inherited") | Wording and control mismatch | 977f0811: ticked means kept, and unticking reveals "Replaced by" |
| 2 | Making a mixed character seemed to require leaving the character section, which lost the prompt | The mix draft replaced the character form (`v-if`/`v-else`), and its notice read like "go elsewhere" | edec5a9b: the draft opens below the form and the prompt stays on screen |
| 3 | No way to regenerate description and personality separately | Only a whole-page regenerate existed | 8ac76a8a, 20a781f6: a Regenerate per section |
| 4 | No way to rename a species, race or other entry | Not built | 20a781f6, b312bb44: rename in place for every kind |
| 5 | Deleting a race went back to the species list | Back navigation went to the kind list | 20a781f6: returns to the race's species page |
| 6 | Personality prose described appearance | Appearance facts were in the personality section's background | Probe (f76e7a32): appearance sentences fell from 41% to 3% without them, with no identity drift. Fixed in 3377cd79 and 83079130 |

## Investigated, not fixed here

- **`@` actions followed less faithfully than in stock Talemate.** The probe (`2026-10-21-personality-and-actions.md`) shows plan B's cast lines aren't the cause. Stock Talemate passes the action only as a weak "(Instructions for X's next part…)" line, and appearance-heavy personality prose gave the model hooks to improvise from. A dedicated action-to-prose prompt belongs in the scene-runner work; the main spec records this under "The player's action comes first".

## Ideas recorded for later

- **Connections between entries.** Names in facts are detected, highlighted and linked. Things not made yet become stubs. Create prompts reuse the scene prompt's name matching. A right-click "Add reference" opens a search in place. Later, the owner could ask the AI about the world. The owner chose this as the next slice, ahead of cultures; see the main spec's "Connections between entries".
- **Cultures** move to their own slice, as fact-based entries written by the local model with a language-only import. See plan B's spec.
