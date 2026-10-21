# Probe: personality prose and `@` action following (2026-10-21)

Model: koboldcpp/Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client (the `--ai`
app's config, default agent settings, so the conversation agent uses the screenplay format).
Script: `scripts/dev/probe_personality_actions.py`. Raw output, with every prompt and reply of
the 40 calls: `raw/2026-10-21-personality-and-actions.json`.

Both probes come from the owner's acceptance run of plan B:

- "the personality section [is] just creating new physical descriptions rather than focusing on
  personality. Perhaps only non appearance tags should be in the context when generating the
  personality?"
- `@` actions are followed less faithfully than in stock Talemate: "my character being curious
  about something because that was in its personality, even though in the action I said I was
  trying to ignore [it] even with a stated reason."

## The world

- **Tova**, a Snowy owl-folk born 492 (Owl-folk: wings for arms, talons used as hands, yellow
  eyes, beak; instincts: crepuscular, turns the whole head to look). Her own facts:
  - appearance: a notched left wing, brass spectacles on her beak, ink-stained breast feathers;
  - background: keeps the books at the Lantern Post; grew up in the northern rookeries;
  - personality: endlessly curious; meticulous, hates leaving work unfinished; fiercely loyal to
    Ilse; wary of strangers;
  - speech: speaks softly, in precise words.
- **Marn**, a Half-orc born 489. Half-orc is a mix of Lowlander (a race of Human) and Orc, so he
  inherits skin, tusks, height and build, and the Orc instincts (keen smell, quick to anger when
  cornered). His own facts:
  - appearance: a broken tusk and a shaved head, burn scars, a smith's apron;
  - background: runs the Wetherby forge; raised by his Lowlander mother;
  - personality: gentle with animals; slow to trust and holds grudges; laughs loudly;
  - speech: blunt, deep rumble.

## Probe 1: what the personality section is given

The section's own facts were the same in every run: the character's personality facts plus its
inherited instincts (`prose_gen._section_facts`). Only the background ("who the character is,
for consistency only; do NOT describe these here") changed:

- **A, today's** (`generate_section`): every other own fact (appearance, background, speech),
  the heritage line, every inherited `physical` and `variation` fact, name and born.
- **B, no appearance**: A without the character's own `appearance` facts and the `physical` and
  `variation` facts inherited from a species, race or mix. It keeps the heritage line
  ("Heritage: Snowy, Owl-folk."), name, born, and the background and speech facts.
- **C, identity only**: the heritage line, name and born.

Sentences were counted by hand as being about appearance when they describe the body, the face,
clothes or gear. Turning the whole head is an instinct in the section's facts, so it isn't
counted.

| Background | Runs | Sentences about appearance | Identity | Register |
|---|---|---|---|---|
| A, today's | Tova 3, Marn 3 | **15 of 37 (41%)**, in every run | kept | 6/6 entries |
| B, no appearance | Tova 3, Marn 3 | **1 of 33 (3%)** | kept | 6/6 entries |
| C, identity only | Tova 2, Marn 2 | 0 of 21 | Marn once "As an orc" | 4/4 entries, more invention |

**A reproduces the owner's complaint.** Every run restates the background as description:

- Tova's plumage, yellow eyes, spectacles, ink-stained feathers, notched wing, and once "uses
  the talons of her feet to grip quill and ledger alike";
- Marn's grey-green skin, height, tusk, shaved head, scars and apron (4 of 6 sentences in one
  run).

The "do NOT describe these" line doesn't hold against 9 to 14 vivid body lines. The runs also
open with the background ("Tova is the bookkeeper at the Lantern Post…").

**B fixes it, and identity holds.**

- Tova is "a Snowy Owl-folk" or "an Owl-folk" in all three runs, with no human words.
- Marn is "a half-orc" each time. His orcish traits are told as temperament ("his orcish blood
  makes him quick to anger when cornered").
- The one slip: Marn B3 rebuilt a body from the heritage name ("broad-shouldered and
  thick-limbed… greenish-brown skin and prominent tusks"). It also gave him a forge cat.
- B still opens with the job, from the background facts, in one or two sentences. That's
  context, not appearance.

**C goes too far.** With nothing to anchor it, the model invents more:

- Tova becomes "a meticulous accountant and devoted attendant to Ilse" and "a formidable
  observer";
- Marn "can detect lies through shifts in scent" and spends "quiet hours tending to wounded
  creatures";
- the half-orc is called "an orc" once.

### Recommendation (probe 1)

Use background B for a character's `personality` section:

- leave out the character's own `appearance` facts;
- leave out every `physical` and `variation` fact inherited from a species, race or mix;
- by the same logic, leave out a culture's `dress` facts (not probed: no culture here);
- keep the identity lines: `Heritage: …`, `Named …`, `Born in …`;
- keep the character's other facts (`background`, `speech`, `relationship`, …) and the rest of
  what it inherits.

The `description` section's background stays as it is. All six B runs still open with the job
(a background fact), which is acceptable. The rule matters for play too: the sheet's
`personality` attribute is this prose. Tova's (an A run) was the same appearance paragraph as her
description, plus "turns her whole head to regard anything that catches her attention" (see
probe 2).

## Probe 2: `@` actions

**The real path.** In `scene/process-input`, an input that starts with `@` (after the editor
trims `"*`) gets the `@` stripped. It then runs `agents/conversation/Generate` for the player's
character, with the text as its `instruction`, so the input goes to
`ConversationAgent.converse(actor, instruction=…)`. The raw text never enters the history. In
`conversation/dialogue.jinja2` the instruction becomes the last line of the acting
instructions: `(Instructions for Tova's next part in the scene: …)`. The screenplay task around it
is stock:

- "Portray the character exactly as defined… creative freedom to fill in gaps";
- "You may chose to have Tova respond to the conversation, or… perform a new action that is in
  line with Tova's character".

**The scene.** Tova is the player, at the Lantern Post's counting desk at dusk. The intro plants
three hooks: a strange humming from the cellar door, the merchant Corvin's ticking brass device,
and the evening street. Then Ilse (an invented human) asks for the ledger to be done before dark
and Corvin's room seen to, and leaves for the stables. Each run started from that same history.

**The actions.** Each one goes against curiosity or an instinct, with a stated reason:

1. "I ignore the strange humming coming from the cellar door -- I promised Ilse I'd finish the
   ledger before dark -- and keep writing."
2. "I don't ask Corvin about the ticking brass device on his belt; it's none of my business and
   Ilse warned me he's touchy about it. I just tell him the room is two silver a night and hand
   him the key."
3. "It's dusk and I'd normally be wide awake, but the flight in this morning wore me out, so I
   close the ledger, tuck my head down and try to doze at the desk instead of watching the
   street."

**The variants.**

- **A**: today's World block.
- **B**: the cast header reworded to "Who is here, by heritage (what their bodies are like, so
  descriptions stay true to them; instincts are tendencies, not orders -- what Tova does is what
  the player says Tova does, and the player's stated actions take precedence):".
- **C**: no cast lines.

After those, **A+late** reran actions 2 and 3 under A with the acting instructions moved after
the scene history. Early in a scene (history under 1024 tokens) the template puts them before
the history, so the last thing the model reads is Ilse's line.

| Variant | Action 1 | Action 2 | Action 3 | Followed fully | Unasked trait-driven additions |
|---|---|---|---|---|---|
| A, today's | partly, yes | partly, partly | partly, no | 1/6 | 4/6 |
| B, bodies only | yes, yes | no, partly | no, partly | 2/6 | 2/6 |
| C, no cast lines | yes, yes | partly, partly | no, no | 2/6 | 5/6 |
| A+late | — | no, no | partly, partly | 0/4 | 4/4 |

What the judgements mean:

- **"Followed fully"** means every part of the action is done.
- **Trait-driven additions** are glances at the cellar or "a mental note to ask Ilse about it"
  (curiosity), sizing up the device, or keeping on working because "She would finish. She always
  finished." (meticulous).

Notes:

- **Action 1 is followed** in 5 of 6 runs, and B's runs are the best: "She did not turn toward
  it. She had promised." It's the only action that agrees with Ilse's request, which is the last
  line of the history.
- **Actions 2 and 3 are never fully followed (0 of 16).**
  - Tova never names the price or hands over the key. She answers Ilse, finishes the column,
    turns toward the cellar and walks to the counter, and the 192-token reply runs out.
  - She never dozes. Tired, she finishes the ledger anyway. In one B run she starts
    investigating a draft from the cellar instead, and in both A+late runs she turns to listen to
    the humming.
  - She does respect the "don't ask about the device" part when she reaches Corvin ("She said
    nothing about the device. Ilse had made that clear enough.").
- **The cellar hook gets pulled in under every variant.** C has no cast lines and no instinct
  text in the World block, and still turns her head to the cellar and stays curious. So does
  every A+late run. The pull comes from the scene's hooks and the sheet, which every variant
  carries:
  - "endlessly curious";
  - the sheet's personality prose, "turns her whole head to regard anything that catches her
    attention".
- **Moving the instruction late didn't help** (0/4, all four drifting to the cellar). Placement
  isn't the lever either.
- **Bodies hold in all 22 runs** (talons, wings, beak, yellow eyes; no hands). That is the job
  the cast lines are there for.

### Recommendation (probe 2)

**Cast lines aren't the cause.** Removing them (C) changed nothing measurable, and the
reworded header (B) is within noise (2/6 against 1/6 fully followed, with n=2 per cell). Keep
the cast lines and their wording.

Two things do weigh on `@` actions, and both are outside the World block:

- **The player's sheet.** Its personality is appearance-heavy, and its instinct prose is turned
  into a hook ("turns her whole head to regard anything that catches her attention"). Probe 1's
  background rule removes the appearance restatement.
- **The stock `@` path itself.** It is only a parenthetical "(Instructions for X's next part…)"
  inside a screenplay task that invites "a new action that is in line with X's character", with
  the model also answering the last line of the history.

Following actions faithfully needs an action-specific prompt: turn the player's stated thoughts
and actions into prose, in order, with nothing the action didn't ask for. The spec's "player's
action comes first" note already puts that in the runner work. A stock comparison, the same
scene as a plain non-world Talemate scene, wasn't run; it would be the next probe if the owner
wants the stock-versus-ours gap measured directly.
