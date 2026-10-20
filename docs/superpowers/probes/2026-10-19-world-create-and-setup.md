# Probe: create from a prompt, and scene setup (plan 2A, Task 3)

Date: 2026-10-19. Model: koboldcpp/Skyfall-31B-v4.2-i1-Q4_K_M. Scripts:
`scripts/dev/probe_world_create.py` and `scripts/dev/probe_scene_setup.py` (at 27374b67), with
the prompts in `scripts/dev/probe_data/world_prompts.json`. Both ran without crashing (exit 0);
the create probe recorded two parse errors, covered below. The create run took about 4 minutes.

## Create from a prompt (7 prompts: 3 characters, 2 places, 2 lore)

| Result | Count |
|---|---|
| Parsed facts | 5 of 7 (2 parse failures, see below) |
| Facts per thing | 6–17 |
| The owner's phrases kept (judged by a second call) | 15 of 15 where parsed |

**What worked:** the invention is exactly what the owner asked for. These are all the model's
own additions:
- "a disgraced duelist" became an exiled Ashenmere fencing master who killed a younger opponent
  he'd been warned not to face;
- the mountain shrine got a history, a vanished hermit order and painted murals;
- the river treaty got a name, a year, collection pillars and tax rates.

Nothing the owner wrote was dropped.

**What needs fixing in the plan 2A templates (Tasks 7 and 8):**
1. **The fact shape drifts.** About half the replies used the category as the key
   (`{"appearance": "…"}`) instead of `{"category": …, "text": …}`. The parser must accept both
   shapes and normalise them; the prompt should show one exact example.
2. **Truncated replies.** The two parse failures (the ferryman, and the half-flooded town)
   were long lists cut off before the closing `]`. Raise `max_tokens` for creation, cap the fact
   count in the prompt (about 8–12), and recover the complete objects from a truncated list
   rather than failing the whole reply.
3. **Dates are free text and off-calendar.** `since` came back as "young adulthood",
   "childhood" and "ten years ago", or as invented absolute years (1734, 1147) unrelated to the
   world's calendar. For creation:
   - give the model the world's current year and calendar;
   - ask for `since` only as a year in that calendar, or leave it out;
   - treat anything else as an open start ("always");
   - for characters, ask for an age and derive the born year from the scene or world date.
4. **"Prose" came back as a story, not a description.** For characters the prose prompt
   produced a short scene, with dialogue, action and other people. The thing-prose template
   must ask for a present-tense descriptive profile of the thing itself: no plot, no dialogue,
   no other characters acting.
5. **Coherence.** The herbalist was "sharp-tongued", but an invented background fact said she
   "lost her tongue to a magistrate's knife" while she speaks in the prose. A cheap fix: the
   creation prompt asks the model to keep the invented facts consistent with each other and with
   the owner's prompt. A coherence check is a candidate for the decision model later (plan F).
6. **The "invented" count is unreliable.** Judged by the same model, it reported 0 invented
   facts for characters that were clearly mostly invented. Don't build features on that
   self-judgement; it's the same lesson as the phase-0 probe.

## Scene setup (3 storyline prompts against a world of 2 characters, 1 place, 1 lore)

| Result | Count |
|---|---|
| Named world things recognised as world things (checked in code) | 8 of 8 |
| Self-reports correct | 8 of 8 |
| Invented things | 2 (a "Warden Patrol" group, a new character "Daveth Brin") |

**What worked:** this is strong.
- The model used the world's characters and its place by name, and invented only what the
  prompt left open.
- It picked a sensible player when the prompt didn't name one (prompt 3).
- It wrote goals that match the prompts.
- Its intros drew on the place's facts, such as the half-flooded streets.

**For Task 8:**
- Keep the probe's JSON shape.
- Pass the player from the UI picker when one is set, rather than letting the model choose.
- Invented groups ("Warden Patrol") aren't characters. The setup should allow invented
  extras that aren't characters, or keep them only in the intro.

## Summary

Creation and scene setup are both viable on this model. The prompt-side fixes are about
shape, length, dates and prose register, not ability. The schema needs no change, consistent
with the main spec's guiding principle.
