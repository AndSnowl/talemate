# Probe: fact round trip (phase 0)

Date: 2026-10-18. Model: koboldcpp/Skyfall-31B-v4.2-i1-Q4_K_M. Script:
`scripts/dev/probe_fact_roundtrip.py --rounds 3`. Four sample characters
(`scripts/dev/probe_data/characters.json`). Run time 3.5 minutes, no errors.

Each round turns facts into prose with `write_prose`, asks `check_prose` for
invented and dropped claims, then extracts facts from that prose again.

## Numbers

| Round | Facts (all samples) | Invented (as judged) | Dropped (as judged) |
|---|---|---|---|
| 0 (from the source text) | 23 | 0 | 1 |
| 1 | 40 | 0 | 0 |
| 2 | 54 | 0 | 0 |
| 3 | 54 | 0 | 0 |

The "drift" metric (exact text match of round-0 facts in the last round) came
out at 50–100% for every sample. It's meaningless, because the model rewords
facts every round even when it keeps their meaning. Drop it or replace it in
any later probe.

## What it showed

1. **The prose embellishes, and re-extraction turns the embellishment into
   facts.** Mira started as three facts ("wiry", "sharp-eyed", "trusts no one
   further than she can throw a knife"). The first prose gave her a body "like a
   coiled spring" and eyes like a hawk's. By round 3 she had 11 facts,
   including "catalogues every tell, hesitation, and bodily lie" and "keeps
   people at arm's length out of necessity, not coldness". None of these came
   from the owner. Across all samples, fact counts more than doubled (23 → 54).
2. **The invented-fact check, as prompted, doesn't work.** It reported zero
   invented claims while the prose was plainly adding detail. It also flagged a
   fact as dropped ("trusts no one further than she can throw a knife") that
   was in the prose word for word. A single "list what's invented" prompt is
   not a usable guard with this model.
3. **Exact wording in a fact survives.** Lyse's "puckered scar on her
   cheekbone" kept its wording through all three rounds of extraction. This
   supports the owner's plan: put the wording you care about in the fact.
4. **Extraction itself is good.** The round-0 facts from each source text were
   accurate, well categorised and complete. Parsing worked on every call.

## What this changes for phase 2 (prompts and flow, not the schema)

- **Never feed generated prose back into extraction automatically.** Prose is
  output only. Re-extracting from it is exactly how the facts snowball.
  "Adopt invented claims as facts" must stay a per-claim choice made by the
  owner, never the default.
- **Rein in the prose prompt.** Ask for a length tied to the number of facts,
  forbid new details, similes and backstory, and test that against this
  probe.
- **Redesign the invented-fact check before building it.** Candidates:
  - one yes/no question per prose sentence ("is this sentence fully supported
    by these facts?");
  - extracting claims from the prose first, then matching claims to facts.

  Probe both against this model, per the "probe the AI before building"
  principle.
- **Replace the drift metric** with a model-judged "same meaning" match, or
  a match by fact id, once facts have ids.

The schema in phase 1 is unaffected: facts stay the truth, as the spec says.
