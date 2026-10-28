# Probe: language awareness in scenes (2026-10-28)

**Why.** This is probe 3 of the languages design (part 2). Part 4 adds a short note to the scene's context saying who can understand whom, derived from characters' languages. The question: does the scene model act on a one-line note?

**The setup.**
- **Model:** Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client, with its own narrator and conversation agents and templates.
- **Harness:** `scripts/dev/probe_language_scene.py`, committed before any call (80ed9a9e). It reuses `probe_heritage_play`'s loading and play loop.
- **Raw output:** `raw/2026-10-28-language-scene.json` (18 turns, 18 calls).
- **The scene:** Mira (the player, a young Sorauan herb-seller) meets Ivan (an invented Moscavian border guard with a broken cart wheel) at a border inn. Their sheets say nothing about language.
- **The turns:** 6 per variant, 3 narrator and 3 conversation turns for Ivan. Mira's player lines are fixed, fluent English ("Excuse me, are you heading north? I can pay for a ride.").
- **Three variants,** each a fresh world. The note is appended to the World block, where part 4's note would go:
  - `none`: no note;
  - `barrier`: "Ivan and Mira share no language: they can't simply talk.";
  - `similar`: "Ivan's Moscavian is close to Mira's Sorauan: they understand each other with effort."
- **Cues:** each turn was keyword-scanned for misunderstanding: gesture, understand, repeat or slowly, foreign or tongue or accent, and puzzled.

## Results

Cue counts (all six turns summed):

| Variant | gesture | understand | repeat/slow | foreign | puzzled |
|---|---|---|---|---|---|
| none | 2 | 0 | 7 | 0 | 2 |
| barrier | 19 | 4 | 9 | 2 | 1 |
| similar | 5 | 2 | 3 | 1 | 3 |

**none.** Fluent talk throughout, as expected. Ivan banters ("Heading north," he repeats, like he's tasting the words. "Depends on what you mean by north.").

**barrier.** The note shows clearly, mostly in the narration:
- "He'd been expecting gestures. Signs. Not words."
- He corrects her "slow and deliberate, like he's talking to a child".
- Mira "holds up three fingers. Three days' work."
- "Her hands know things her mouth sometimes struggles to say."

But Ivan still answers in full English sentences, and the deal gets made. The fixed player lines don't help: Mira speaks fluently, so the model has to reconcile that with the note.

**similar.** The first turns carry it ("His Moscavian had a rough edge", "rolling the word around like it tasted strange"), then it fades. By turn 3 it's an ordinary conversation.

**The owner's verdict:** *pending.* Read the turns in the raw file, under `variants.<name>.turns[].output`.

## Findings

1. **One line in the World block moves the scene, but doesn't hold it.** The barrier shows up as gestures and slow speech, and the similar-language effect fades after two turns.
2. **Part 4's note should be stronger than a World-block line:**
   - Put it in each affected character's own instructions (the conversation agent reads the speaker's sheet every turn).
   - Phrase it as what the character *does*: "Ivan doesn't understand Sorauan: he answers in Moscavian and gestures." That works better than describing the situation.
   - Repeat it each turn, rather than once in the setup.
   - Part 4's plan should probe these three changes.
3. **The player's own lines matter.** When the player writes fluent English for a character who can't speak the other's language, the model follows the player. That's arguably right (the player decides what their character says). With the right-click *Make a phrase…* in the scene box, the player can write Mira's line in Sorauan.
4. **The note costs nothing to build.** It comes straight from the characters' languages and the similar-language links, so part 4 can ship it early and tune the wording.
