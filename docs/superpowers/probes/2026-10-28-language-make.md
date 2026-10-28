# Probe: making a language with a local model (2026-10-28)

**Why.** This is probe 1 of the languages design (part 2). Can a local instruct model turn a plain prompt into a working language: sound rules in the generator's pattern syntax, a word list with definitions, and phrases? The answer decides whether languages are made in the app, or by Claude outside it and imported.

**The setup.**
- **Harness:** `scripts/dev/probe_language_make.py`. Scoring is in `scripts/dev/language_probe_metrics.py` (tested).
- **Labels:** `raw/2026-10-28-language-make-labels.json`, committed before any call (9b4fb7f3). It has 251 real Russian words and names, 19 linguistics terms, and 5 cases:
  - `russian`: "a unique but recognizably Russian language";
  - `compound-desc`: "fantasy-sounding English compound names";
  - `compound-examples`: from Duskhollow, Thornfield, Ashmere, Ravenford and Briarwick;
  - `daughter`: of `russian`, "isolated in the mountains for five hundred years";
  - `ask-russian`: the `russian` prompt, asking questions first.
- **Calls:** each case ran twice, through koboldcpp's chat endpoint (each model's own chat template), followed by three small jobs on `russian`: definitions, a pick and a coined word.
- **Models,** one call at a time (owner's advance approval; models switched with koboldcpp's admin reload, and Skyfall restored at the end):
  - **Skyfall-31B-v4.2** (Q4_K_M): run `skyfall`.
  - **Qwen3.8-27B** (Q5_K_M):
    - run `qwen`: default thinking, 6,000 tokens. Every reply ran out of tokens while still reasoning, so none parsed.
    - run `qwen-nothink`: thinking switched off (`enable_thinking: false`).
    - run `qwen-think`: thinking on, 16,000 tokens, in `raw/2026-10-28-language-make-think.json`. 9 of 10 language calls still ran out of tokens, at about 6.5 minutes each.
- **Raw output:** `raw/2026-10-28-language-make.json` (runs `skyfall`, `qwen`, `qwen-nothink`).

**What "dictionary fit" means.** It's the share of the language's own dictionary words that its own generator could have made. For the English compound styles it reads 0 by design, since a single part like "dusk" isn't a whole compound.

## Results

| Case | Skyfall | Qwen, thinking off |
|---|---|---|
| russian | loads; fit 0.15 / 0.00; **dictionary is real Russian** (otets, voda, zemlya, khleb, zima) | v1 loads, fit 0.68, invented words (vark, zolm, keth); v2 ran out of tokens |
| compound-desc | loads; weight marker `*n` copied in literally ("Thornwick *n") | loads; two-word pairs ("Wind Spy", "Priest Farm") |
| compound-examples | loads; good (Briar-wick, Ash-mere, Raven-hollow) | loads; good (Briarhollow, Ironwick, Ravenvale, Misthollow) |
| daughter | loads; same real-Russian dictionary as its parent | loads; names drift, but the dictionary is copied from the parent unchanged |
| ask-russian | loads; `*n` and `|` misused, so names break ("Mshoovknch|nnesnt|tzh*n") | loads; one version's places generator is empty |

**Samples: `russian`, version 1.**
- **Skyfall ("Ruskalan"):**
  - people: Nithoz, Maky-avik, Chara, Lirizh, Luri-inyl, Tylaf, Rymij, Dyzhor;
  - places: Totfi-tharm, Jozhgo-khathn, Lijru-merr, Sh-yvgy-thyll, Lojsh-or, Kr-surji.
- **Qwen ("Ostrovian"):**
  - people: Livu, Khaluz, Finyk, Muthuk, Myvek, Nisyth, Nefos;
  - places: Zithu, Zida, Selu, Bokes, Zhuzhidu, Thusymo, Kavyti, Zelyne, Dosizh.

**Questions in `ask` mode.** Both models asked four plain questions, with no jargon.
- **Skyfall:** "How Russian-sounding do you want it to be?", "noble and grand, or rough and earthy?", and also asked about a writing script and diacritics.
- **Qwen:** "hard and strong, or soft and flowing?", "old and ancient, or modern?", "What is the main vibe you want people to feel?"

**Small jobs** (both models):

| Job | Skyfall | Qwen, thinking off |
|---|---|---|
| definitions (10 rolled names) | rich, made from invented roots ("'tugzh' iron + 'el' river") | plain one-liners, not tied to the dictionary ("Lotar is the deep shadow cast by the moon at night") |
| pick (20 candidates, a capital) | picked one in the list, with a reason | picked one in the list, with a reason |
| coin "Free Provinces" | **real Russian**: "Svobodnaya Provinciya" | wrong: "Shil Zolm Keth" ("wind water stone") |

**The owner's grades:** *pending.* The questions:
1. Does either `russian` sound recognizably Russian without being Russian?
2. Does `daughter` sound related to its parent?
3. Do the compound styles read like Duskhollow?
4. Are the definitions usable?

## Findings

1. **Neither local model makes a usable Russian-flavoured language on its own.**
   - Skyfall writes real Russian vocabulary even when told not to.
   - Qwen invents words, but its names lose the Russian flavour, and one of its two attempts ran out of tokens.
   - Both get the pattern syntax wrong in some replies (Skyfall's literal `*n` and `|`, and an empty generator from Qwen).
2. **English compound naming styles work locally,** especially from examples: both models produced Duskhollow-like names. Growing a style ("more parts") is probably safe in the app.
3. **Thinking mode is impractical.** Qwen with thinking runs past 16,000 tokens (about 6.5 minutes) per language. Without thinking it answers in about 45 seconds.
4. **Daughters fail on both models.** Neither changed the parent's words by the drift.
5. **Small jobs:**
   - picking among rolled names works on both;
   - definitions work, best on Skyfall;
   - coining a translation fails on both (real Russian, or nonsense).
6. **Plain questions work on both models.**

## Decision (my recommendation, for the owner to confirm)

- **Full languages and daughters are made outside the app by Claude** (the spec's fallback), and imported.
  - So `.claude/skills/culture-design/` is **kept**, and the part-3 plan reworks it into the language-design skill, with the new import format.
  - Part 3 builds the import into a language entry.
- **Naming styles made of English parts can be made in the app,** from a description or from examples, with the local model (Skyfall or Qwen without thinking).
- **In the app, either way:** picking among rolled names, and one-sentence definitions (Skyfall).
- **Coining words for a name's translation** ("Free Provinces" in Sorauan) is better done by rolling from the language's rules plus the model picking, or by the owner. The model shouldn't write the words itself. Part 3's design should reflect this.
- **Any in-app model call** that asks for a language in the pattern syntax must validate the reply with `validate_language` and the fit check, and retry or report, because both models sometimes break the syntax.
