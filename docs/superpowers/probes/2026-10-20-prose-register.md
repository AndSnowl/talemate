# Probe: prose register and identity drift (acceptance run, 2026-10-20)

Model: koboldcpp/Skyfall-31B-v4.2-i1-Q4_K_M, through the chat endpoint. The input was the owner's
"Vasha" (owl-folk courier) facts. The raw replies are in `raw/2026-10-20-prose-register.json`;
the scratch script is in the session scratchpad.

## Why the probe was run

In the acceptance app, Vasha's generated description came back as a short story three times
("Vasha stands at the edge of the cliff…"), around 300+ words. His personality section turned
him into a human man, with weathered hands, grey eyes and a cloak, because that section only
received the personality facts.

## Results (14 runs)

| Variant | Register | Identity | Words |
|---|---|---|---|
| A: today's template (prefill "Vasha", temp 0.8) | 4/4 stories | personality 2/2 human | 180–225 |
| B: strict reference-entry prompt (prefill "Vasha is", rules, ≤90 words, temp 0.5) | 4/4 profiles | description owl; personality neutral | 79–91 |
| C: B, plus the other facts as "for consistency only" background (temp 0.5) | 2/2 profiles | owl-folk kept | 46–55 |
| C at temp 0.8 | 4/4 profiles | kept, though appearance details sometimes repeated in personality | 48–106 |

## Decisions for the fix

- Prime the reply with "<name> is"; give it reference-entry rules (not a scene, present tense,
  no setting, actions, dialogue or other characters, use only the facts); cap it at about 90
  words.
- Give each section the thing's other facts as background, for consistency only.
- Write prose at a lower temperature (about 0.5). Creation keeps its creative preset.
- The creation prompt leaves `since` off inherent traits (species, appearance one is born with),
  so they're open-start rather than dated at the present year.
