# Probe: heritage in play (2026-10-20)

Model: koboldcpp/Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client (the one
the `--ai` app configures; it picked the `KoboldAI.jinja2` prompt template and the default
presets). Script: `scripts/dev/probe_heritage_play.py`. Raw output, with every prompt and reply
of five runs: `raw/2026-10-20-heritage-play.json`.

## What was run

A small world in a temp dir:

- **Owl-folk** (species, lifespan 60, adult at 16):
  - physical: wings in place of arms; talons of the feet used as hands; yellow eyes; hooked
    beak and silent feathers;
  - instinct: crepuscular; turns the whole head to look; goes still and silent when startled.
- **Snowy** (a race of Owl-folk): white plumage flecked with black; feathered down to the
  talons, shrugs off cold.
- **Eira**, a Snowy born 470, whose own black eyes override the yellow ones.

A scene in 499 was planned with `setup.plan_scene` (a fixed setup reply) and started with
`setup.start_scene`, which had the model write Eira's prose for 499. The cast was Ilse (an
invented human, the player), Eira, and **Brannoc**, an invented innkeeper whose heritage is
Owl-folk. The scene was loaded through its `world://` target, so the character sheets come from
`character_from_world` and the "World" instruction from `world_context_block`, exactly as in
play.

Six turns used Talemate's real agents and templates:

| # | Turn | Ilse's line before it, or the direction |
|---|---|---|
| 1 | narrator `progress_story` | Ilse hands Eira the letter and a pen to sign the ledger |
| 2 | conversation, Eira | "Would you put these riding gloves on before you go?" |
| 3 | narrator `narrate_character`, Brannoc | Brannoc brings two mugs of cider |
| 4 | conversation, Brannoc | "Shall we shake hands on the room, then?" |
| 5 | narrator `progress_story` | Full night falls; how the owl-folk respond; a door bangs |
| 6 | conversation, Eira | "Don't you ever sleep at night?" |

**Approximations.** The agents ran with their default config, not the owner's. The world-state
agent and the director didn't run between turns, and there was no frontend. Runs B to D used the
app's ChromaDB memory agent on its default local embeddings, with long-term memory on as in the
app. Runs A and E used the tests' memory stub, with long-term memory off.

## Before the fix: the narrator can't see the bodies

| Run | Memory | Narrator turns (1, 3, 5) | Conversation turns (2, 4, 6) |
|---|---|---|---|
| A | off | 3/3 humanised | 3/3 owl-folk |
| B | ChromaDB | turn 1 humanised; turn 5 slips once | 3/3 owl-folk |

The conversation prompts list every character's sheet. They worked every time:

- Eira refused the gloves because they'd get in the way of her talons and her plumage keeps her
  warm.
- Brannoc offered a taloned foot to shake on the deal.
- Eira turned her whole head, drank holding the mug in both talons, and explained that her kind
  are crepuscular.

The narrator's prompts (`narrate-progress`, `narrate-character`) carry **no character sheets**.
They get the premise, the World block, the scene history, and whatever long-term memory
retrieves from the recent history.

- **Run A, with no memory.** Turn 1 had Eira turn the letter "in her fingers", sign with "her
  hand", and pull a case "from inside her jacket". Turn 3 described Brannoc as "a broad man",
  with hands, calloused fingers, a beard, grey-green eyes and a wool coat. Turn 5 gave him
  stubble and had him steady a candle "with two fingers", although the narration also had
  owl-folk regulars clicking their talons.
- **Run B, with memory.** Turn 1 came before any history that could pull the sheets out of
  memory, so the memory section was empty. Eira got practised fingers, held out "her hand",
  worked a drawstring "with her teeth and one hand", and had "rain-dark hair". By turn 3, memory
  surfaced the sheets and Brannoc came out right: wings, talons, beak. Turn 5 still had Eira
  hold a cup "between her hands".

So the first narration of a scene, and any narration where retrieval misses, writes the
owl-folk as humans. Nothing the character sheets or since lines do reaches the narrator.

## The fix: the World block names who is here, by heritage

The World instruction (`worldplay.context.world_context_block`) is injected into both the
narrator's and the conversation agent's prompts. It now ends with one line for each active
character (and the player) that has a heritage:

```
Who is here, by heritage (keep every description and action true to these bodies and instincts):
- Eira (Snowy, a race of Owl-folk): Eira's eyes are a deep, glossy black. Snowy owl-folk have white plumage flecked with black. Snowy owl-folk are feathered down to their talons and shrug off cold. Owl-folk have broad feathered wings in place of arms. Owl-folk use the talons of their feet as hands: to grip, carry, write and eat. Owl-folk have a hooked beak and soft, silent feathers. Instincts: Owl-folk go utterly still and silent when startled. Owl-folk turn their whole head to look at something, rather than moving their eyes. Owl-folk are crepuscular: drowsy at midday, most alert at dusk and dawn.
- Brannoc (Owl-folk, a species): Owl-folk have broad feathered wings in place of arms. Owl-folk have large, forward-facing yellow eyes. […]
```

How the lines are built:

- The facts are resolved in code as of the scene's current date. There are no model calls.
- A world character gets the `physical` and `variation` facts of its heritage layers, with
  overrides applied, led by its own facts that override one of them (Eira's black eyes in
  place of the yellow ones). Then come the `instinct` facts.
- An invented character gets the effective facts of the `world_heritage_id` it was started
  with.
- A culture's facts aren't listed. A character with no heritage, or one whose heritage was
  deleted, has no line.
- As the clock passes a dated species fact, the line follows it. The end-to-end test checks
  this with a species fact dated since 500.

Tests:

- `tests/worldplay/test_context.py::test_world_context_block_lists_heritage_bodies`;
- the cast assertions in `tests/worldplay/test_heritage_end_to_end.py`.

## After the fix

| Run | Memory | Narrator turns (1, 3, 5) | Conversation turns (2, 4, 6) |
|---|---|---|---|
| C | ChromaDB | 3/3 owl-folk | 3/3 owl-folk |
| D | ChromaDB | 3/3 owl-folk | 3/3 owl-folk |
| E | off | 3/3 owl-folk | 3/3 owl-folk |

**Bodies.** In all 18 turns, no owl-folk character has hands or fingers or wears gloves.

- Turn 1 now has Eira take the letter "with a careful grip of her left talons" (C), pinch it
  "between two talons" (D), or have "Eira's taloned feet" grip it (E). She signs with the pen or
  quill held in her talons, "with the careful, jerky precision of someone accustomed to writing
  with feet" (E).
- Turn 3 has Brannoc carry the mugs in his talons, "one in each foot" (D), with wings, a hooked
  beak and yellow eyes. Eira is never given yellow eyes.
- The word "hands" still turns up for owl-folk, but only in the characters' own speech about
  not having any ("Don't got hands to shake with, love. Talons…").
- There are small oddities, none of them human:
  - "wing-talons" and "feathered digits" in C, turn 1;
  - a tap on "her own forearm" plumage in C, turn 2;
  - Brannoc in reading spectacles in E;
  - in E, turn 2, Eira picks up a glove and flexes a foot inside it before turning it down
    ("Not wearing them.").

**Instincts.**

- An owl-folk turns, swivels or snaps the whole head in 12 of the 18 turns, or 14 if head
  tilts count. One slip: "one black eye swiveling up" in C, turn 1.
- The banging door in turn 5 made the owl-folk go "rigid" or "perfectly still" in all three
  runs, which is the startle instinct. In E, Eira opened her wings instead.
- Asked about sleep, Eira says her kind are crepuscular every time ("Dawn and dusk. Night's for
  resting. Day's for tolerating."). Twice she adds "night is for hunting" or "we sleep at noon",
  which is a looser reading of the fact.
- Brannoc's instincts came through as much as Eira's. He stayed still and watchful, and went
  rigid at the door.

## Decision

- **Keep the cast lines in the World block.** The conversation prompts didn't need them, because
  the sheets were already there. The narrator's prompts did, and they are where this went wrong
  in every run before the fix. The cast lines cost a few hundred tokens per prompt and no model
  calls.
- **Brannoc's description.** An invented character's description is still its own facts
  followed by its heritage's raw facts ("Owl-folk have broad feathered wings in place of
  arms."). That reads fine to the model and isn't worth a prose call at scene start.
- **Not covered here:**
  - mixes in play;
  - an invented character of a race, as opposed to a species;
  - the owner's own agent config;
  - long scenes, where the World block competes with a long history.

  The owner's acceptance run (Task 13) plays a mix.
