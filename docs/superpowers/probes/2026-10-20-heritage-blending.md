# Probe: blending mixed heritage at character creation

Date: 2026-10-20. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, temperature 0.8 (0.7 for the mix entry). Run at the owner's request during the plan B brainstorm.

- Script: `raw/2026-10-20-heritage-blending.py`.
- Raw output: `raw/2026-10-20-heritage-blending.json`, plus the follow-up in `raw/2026-10-20-heritage-blending-quarter-via-entry.json`.

## Setup

**The world:**
- **Humans,** with two races:
  - Lowlander: short and stocky, olive skin, dark hair;
  - Highlander: tall, pale, freckled, red hair, grey or green eyes.
- **Orcs:** 6–7 ft, grey-green skin, two-inch tusks, heavy brow, pointed ears, amber eyes.
- **Owl-folk,** with a Snowy race: 3–4 ft, wings in place of arms, facial disc, beak, talons used as hands.

**The prompt:** the same character prompt in every run, "A blacksmith's apprentice in a frontier town, nineteen years old, quick-tempered but loyal to her master". The create prompt mirrors `world/create-thing.jinja2`, plus a heritage block with each share and that species' or race's facts.

**Two rule styles:**
- **Plain:** "build the character from it".
- **Guided:** blend in proportion into one body. A half shows both sides softened; a quarter shows the larger share plus one or two subtle traits of the smaller. Pick weighted in-between numbers, and never list traits that contradict.

## Findings

1. **Halves blend well on the spot, with either style.** Half-orcs came out consistent across all six runs: grey-green or olive skin, short tusks, a softened brow, amber eyes, coarse dark hair. Guided runs put the height between the two parents (5'7"–5'10"). Plain runs leaned to the Lowlander side (5'6"–5'7").
2. **Mixed race within one species also works.** Half Lowlander and half Highlander gave an in-between build, olive-tan skin with freckles, auburn hair and green-tinged eyes, consistently.
3. **Quarters don't work on the spot.** A quarter-orc looked like a half-orc, with tusks, brow, ears and amber eyes in every run, even with the guided rule. The model also got the lineage wrong, giving the character an "Orc father" when the father should be a half-orc. A quarter Highlander showed every Highlander trait.
4. **A written mix entry is the most consistent.** The AI wrote a sensible "Half-orc" entry from the two species: height 5.5–6.5 ft, tusks of half an inch to an inch, adulthood at 15–18, a lifespan of 60–75, and blended instincts (sociable but territorial). Three characters made from it matched closely: 5'7"–5'9", grey-green skin, half-inch tusks, a heavy but softened brow.
5. **Quarters work when built as a half of a mix entry.** A quarter-orc, made as half Lowlander and half of the Half-orc entry, came out softer in all three runs:
   - a single half-inch tusk;
   - skin grey-green only in places;
   - the lineage right ("her half-orc father").
6. **Human and owl-folk give no abominations, but no consistency either.** The four runs ranged from a human with feather tufts, owl eyes and talons, to a fully feathered body with a small rounded beak. Plain run #1 contradicted itself: it gave her nine-foot wings while also giving her hands in gloves, when owl-folk wings replace arms.
7. **Names repeat (side finding).** "Maren" or "Brenna" appeared in most runs, and "Maren Ashwing" came out in all four owl-folk runs. Creation needs a naming source, which is the cultures' name pool in phase 4.

## Implications for plan B

- A character's heritage can be up to two parents, each a species, a race or a mix entry, and the AI blends the halves well.
- Mixes the owner wants to reuse are their own entries, and the AI can draft one from its two parents. A quarter is then half of a mix entry, which the model handles; a free-form "1/4" share isn't offered.
- Very different species, such as human and owl-folk, should go through a mix entry, so the owner settles the body plan once.
