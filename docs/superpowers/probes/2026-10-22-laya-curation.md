# Probe: curation judgement calls on Laya, against Skyfall

Date: 2026-10-22. Model: Laya 0.4.7, English checkpoint (`convaiinnovations/laya`, 421M), on the CPU (torch 2.14.1+cpu, 8 threads). It ran in a throwaway venv in the session scratchpad, not the project's. Nothing in `src/`, `pyproject.toml` or `uv.lock` was changed, and no `tests/ai` were run. The owner asked whether Laya could make the curation probe's "qualitative judgement calls" better than Skyfall, and pointed to the Laya integration guide.

- Script: `scripts/dev/probe_laya_curation.py`. Flags: `--only same names contra held movein elsewhere`, `--variants S1 ...`, `--dry` (prints the states), `--rescore` (scores the saved rows again, with no model).
- Raw output: `raw/2026-10-22-laya-curation.json`. For every judgement it holds:
  - the cases with their truth;
  - every phrasing, with an example state;
  - one row per call: probabilities, seconds and token counts;
  - the scores.
- Cases: the **same** cases as the Skyfall probe (`2026-10-22-curation.md`). The texts are taken from the prompts and replies recorded in `raw/2026-10-22-curation.json`. The truth comes from `raw/2026-10-22-curation-labels.json` and the hand codes in that probe's `judged`. No world was opened and no new labels were written.

**How it was run.** The model was loaded once and warmed up with two throwaway calls per phrasing. Each case is then one `predict` call with one question, so the latency is per question. Laya is deterministic, so each case ran once; Skyfall ran each case twice. I compare shares, not counts.

**States and truncation.** The checkpoint reads 512 tokens.
- Every text is cut at a word boundary: facts at 220 characters, descriptions at 160, and elsewhere sentences at 260, with "…" marking the cut.
- The same-thing state keeps the first 1–3 facts per side. The summary fact comes first.
- Years in "(In 687)" brackets are kept for contradictions and stripped for moving in.
- The largest input was 380 tokens, a same-thing call. None of the 6,055 calls was truncated (`usage.truncated` and `state_tokens_dropped` are 0 throughout).

**Phrasings.** Each judgement had three phrasings in round 1. Round 2 added two or three more, after I saw the round 1 scores. **The best phrasing was picked on the same labels it is scored on**, from 2 to 6 tries, so every "best" number below is optimistic.

**The confident split.** Two views are given.
- **Top probability.** The guide's rule: the answer counts as confident when its top probability is at least *t*. I report *t* = 0.8 or 0.9.
- **Cascade.** Below `lo` Laya clears the case, above `hi` it flags it, and anything between goes to the owner (escalated).
  - `lo` is the highest value that clears no labelled positive (miss 0).
  - `hi` is the lowest value whose flags are at least 90% right. Where no value reaches that, there is no `hi` and nothing is flagged automatically.
  - The thresholds were fit on the test set, so the numbers are optimistic. **LOCO** fits them on every other case group (each pair, entry or Fill drawer) and applies them to the one held out. That is the honest version, and it is the one I quote.

**Sample size.** The positive class is small everywhere:
- 4 same pairs;
- 9 contradictions (11 labelled A–B pairs);
- 20 bare beliefs;
- 5 facts that should move in;
- 13 elsewhere items that are false under the owner's reading.

One case is 5–25 points. Treat everything here as a direction, not a measurement.

## Summary

| # | Judgement | Skyfall | Laya, best phrasing | Laya, confident split (LOCO) | Recommendation |
|---|---|---|---|---|---|
| 1 | Same thing? (8 pairs) | 14/16 (88%); same pairs 8/8; "same" for not-same 2/8 (25%) | S5: 7/8 (88%); same pairs 3/4; "same" for not-same 0/4. The best of 5 tries. | 3/8 decided, 1 of them wrong | **Don't use Laya** |
| 6 | Same thing by name alone | not asked | 4/8 (chance) under both phrasings | 0–1/8 | **Don't use Laya** |
| 2 | Contradictions (474 A×B pairs, 7 merges) | found 14/18 (78%); clean facts flagged 8–9% | C2/C5: found 7/9 (78%); clean facts flagged 24/91 (26%); false pairs 18/462 (4%) | clears 47% of pairs, misses 1 of 11 labelled pairs; never flags automatically | **Use Laya to rank and to clear, never to decide.** Alongside the overlap rule it shows 9/9 in 76 pairs |
| 3 | Held by (270 facts) | bare beliefs 4/20 (20%); plain facts marked 9/250 (4%) | H4: 12/20 (60%); 5/250 (2%) | auto-clears 85%, misses 4 of 20 beliefs | **Better than Skyfall, still under the bar.** Use it as an unticked suggestion only |
| 4 | Moving in (60 facts, 5 cases) | moves 10/10; stays moved 8/110 (7%) | M4: moves 4/5; stays moved 2/55 (4%). M2: 5/5 and 8/55, with the best ranking (AUC 1.0) | M2: 58/60 decided, all right; 1 move and 1 stay escalated | **Laya when confident, the owner otherwise** (the pre-tick option of probe 2). It needs a fresh set to confirm |
| 5 | Elsewhere check (225 items) | (no model check; the post-hoc code filter caught 10/11 Fill false moves and dropped no right item) | E5: false caught 12/13; right items flagged 66/212 (31%). E1–E4 rank below chance | 58% decided, 1 miss | **Don't use Laya.** Keep the code filter |

**Latency.** The mean was 0.29 s per question and the median 0.26 s, over 6,055 calls. The range was 0.21–0.81 s mean per phrasing (the same-thing states are the longest), with a 2.4 s worst case.
- The machine was busy: load average 9–15 from other work the whole time.
- A smoke test in the same conditions measured 0.38 s with 8 threads and 1.1 s with 16, so the run used 8.
- Against Skyfall, this is 3–5× faster than its 2.2 s same-thing call, and 15× faster per question than its 3.6–4.2 s merge call. One Laya question still costs a quarter of a second on this CPU, though. A merge of a 12-fact entry with another of 12 is 144 questions, about 40 s, unless a code prefilter cuts the pairs first.

**Load.** The first load took 24 s, of which 17 s was the 808 MB download. Loads from the cache took 2.8 s.

**Overall.**
- **Laya is not a general replacement for Skyfall's judgements.** It is clearly better at one: held by, tagging 60% of bare beliefs against 20%, with fewer false tags.
- **It is useful as a ranker in two:**
  - contradictions, where it adds what word overlap misses;
  - moving in, where its order is near perfect on this tiny set.
- **It is no better than chance or code at three:**
  - the same-thing check, with facts or by name;
  - the elsewhere check.
- **The confident split rarely flags automatically.** On these sets Laya is confident about "no" far more often than about "yes". In practice the cascade clears the obvious negatives and passes the rest, including nearly every positive, to the owner. Moving in is the exception.

## 1. Same thing?

**Setup.** Probe 5b's eight pairs. The state is the two entries' names and kinds, plus their first facts:

```
Entry A: The Ashenmere Caves (place)
- The Ashenmere Caves are a vast network of limestone caves …
- The earliest known runic inscriptions …
Entry B: Ashenmere (place)
- …
```

| Phrasing | Question | Right | Same pairs | "Same" for not-same | AUC |
|---|---|---|---|---|---|
| S1 | choice same / part / different, with Skyfall's option descriptions, 3 facts | 5/8 | 1/4 | 0/4 | 0.81 |
| S2 | noul "one and the same thing under two names?", 3 facts | 5/8 | 3/4 | 2/4 | 0.81 |
| S3 | choice "the same thing / a part / a different thing", 2 facts | 2/8 | 1/4 | 3/4 | 0.44 |
| S4 (r2) | noul as S2, summary fact only | 6/8 | 4/4 | 2/4 | 0.94 |
| **S5 (r2)** | choice same / not the same ("though one may contain, serve or be named after the other"), 2 facts | **7/8** | 3/4 | **0/4** | 0.75 |

**Best phrasing (S5):**

```
{"type": "choice", "instructions": "Are A and B the same thing?",
 "criteria": {"same": "yes: A and B are one thing written up twice",
              "not the same": "no: A and B are two things, though one may contain, serve or be named after the other"}}
```

**Against Skyfall.** Skyfall scored 88%, 8/8 on same pairs and 2/8 false. S5 scores 88%, 3/4 on same pairs and 0/4 false.
- **S5 misses S1**, the Ashenmere Caves and Ashenmere. Those are the two near-identical write-ups, the easiest pair for Skyfall. Laya gave "same" only 0.14.
- **S5 gets S7 right** (the conflated Eternal Light and the Church). That is the pair Skyfall called "same" twice.

**Small changes swing it.** Three facts against two, a choice against a noul: these swing the result by 3–5 pairs out of 8. The `part` option attracts same pairs under S1 and S3. The ranking is best when only the summary fact is shown (S4, AUC 0.94), but S4 calls everything above 0.65 "same", including the Feast of the Illumination and the cathedral in Moskov.

**Confident split.**
- At top probability ≥ 0.6, S5 is confident on 7/8 pairs and right on 6 of them.
- No answer reaches 0.8.
- LOCO decides 3/8 pairs and gets 1 wrong.

The probabilities sit at 0.55–0.65 on this question, so a threshold can't be trusted.

**Latency.** 0.41–0.81 s mean. These are the longest states, at 160–380 tokens.

**Recommendation: don't use Laya.** On 8 pairs, with the phrasing chosen after 5 tries, "88% and 0 false" is noise around chance-plus. It misses the plainest same pair. The probe 5b fallback stands: **owner only**.

## 6. Same thing by name alone (optional)

**Setup.** The same eight pairs, with names and kinds only, for example "Entry A: Patriarch (lore)" against "Entry B: The Patriarch of Moskov (lore)".

| Phrasing | Right | Same pairs | False | AUC |
|---|---|---|---|---|
| N1 choice same / part / different | 4/8 | 0/4 | 0/4 | 0.38 |
| N2 noul "do the names A and B name one and the same thing?" | 4/8 | 2/4 | 2/4 | 0.50 |

**Chance.** N1 calls every same pair "part", for example the Patriarch against the Patriarch of Moskov. N2 calls the Moskov / Cathedral of the Eternal Light, Moskov pair "same" at 0.86.

**Recommendation: don't use Laya.** Code's `same_candidates`, which works on name tokens, does this better and costs nothing.

## 2. Contradictions (the merge check)

**Setup.** Probe 3's seven merges, every A fact against every B fact: 474 pairs.
- 11 pairs are labelled contradictions. They are 9 contradictions, since two of them list alternative facts.
- 1 pair is the bonus (the Conclave in 312 against its founding in 642). It is not scored.
- The state is the two facts, "Fact A: … / Fact B: …".

**Measures.**
- **Skyfall's own:** contradictions found out of 9, and clean facts that appear in a flagged pair which is no contradiction, out of 91 clean facts.
- **Pair level:** the same flags counted per pair.

| Phrasing | Question | Found | Clean facts flagged | False pairs | AUC |
|---|---|---|---|---|---|
| C1 | choice agree / contradict / unrelated (each described) | 8/9 | 64/91 (70%) | 120/462 (26%) | 0.92 |
| **C2** | noul "Do fact A and fact B contradict each other, so that both cannot be true?" | **7/9 (78%)** | **24/91 (26%)** | **18/462 (4%)** | 0.86 |
| C3 | as C1, with "Two records of one thing, X and Y, are being merged" | 8/9 | 85/91 | 311/462 | 0.71 |
| C4 (r2) | C1 plus "The two facts give different years / the same year", from code | 8/9 | 64/91 | 132/462 | 0.93 |
| C5 (r2) | C2 plus the same year line | 7/9 | 24/91 | 18/462 | 0.89 |
| C6 (r2) | choice same claim / added detail / conflict / unrelated | 8/9 | 63/91 | 80/462 | 0.89 |

**Best phrasing (C2; C5 is the same with a line from code):**

```
Fact A: <fact, cut at 220 characters>
Fact B: <fact, cut at 220 characters>
[C5 only: "The two facts give different years." when both are dated]
{"type": "noul", "instructions": "Do fact A and fact B contradict each other, so that both cannot be true?",
 "criteria": {"true": "they cannot both be true", "false": "both can be true at once"}}
```

**Against Skyfall.** Skyfall found 78% of contradictions and flagged 8–9% of clean facts. C2 also finds 78%, but flags 26% of clean facts, three times Skyfall's rate.
- The choice phrasings find one more contradiction, but flag most of the clean facts.
- **Missed by C2:**
  - the Codex's 217 against 312. This is the date clash, and both of its alternative pairs were missed. With the year line (C5), "contradict" rose only from 0.04 to 0.10 and from 0.30 to 0.35;
  - the Moskov population, "overwhelmingly pure-line" against "mostly eared" (0.03).
- **The C3 framing hurts.** Telling Laya the two records are one thing being merged pushed it to call most pairs contradictions.

**Against the code baseline.** The overlap rule (≥ 0.4) shows 45 pairs and catches 6/9 contradictions.
- **At the same budget.** Per merge, show Laya's top *k* pairs, where *k* is how many pairs overlap shows for that merge (45 in all). C2 catches 7/9.
- **Union.** Overlap's pairs plus C2's top *k* catch **9/9 in 76 pairs** of 474. That is the best result in this probe. It catches what each misses:
  - overlap misses "black talon on crimson", "a General" and "a lake in the far south";
  - Laya misses the date and population clashes, which overlap catches.
- **Laya only on the overlap pairs** (code first). C1 ranks those 44 pairs well (AUC 0.97). The overlap pairs only hold 6/9, though, so this caps recall.

**Confident split.**
- At top probability ≥ 0.9, C2 is confident on 384–399/473 pairs (81–84%) and right on 98% of them. Nearly all of those are confident "no".
- At ≥ 0.9, only 4 of the 11 labelled pairs are confident, and 3 of those 4 are confidently wrong (C5).
- **Cascade, LOCO.** `lo` ≈ 0.03 clears 47% of pairs, misses 1 of 11 labelled pairs and escalates the other 10. There is never a `hi`: no flag threshold is 90% right.

**Latency.** 0.24–0.33 s mean per pair. A 12 × 12 merge is about 35–45 s on this CPU, longer than Skyfall's one 4 s call. With overlap first and Laya only on what overlap misses, there are still about 140 pairs per merge to ask. That cost is the main argument against using Laya here.

**Recommendation: use Laya to rank, never to decide.**
- In a merge, show the overlap pairs plus Laya's top-*k* by P(contradict), unflagged, side by side.
- Don't show the model's yes/no.
- Never auto-merge on Laya's "no" alone: the cascade misses 1 in 11.

This is a step up from code-only (6/9 → 9/9), and it needs no LLM. It costs a quarter-second per pair on this CPU. If that is too slow, overlap alone stays the fallback.

## 3. Held by

**Setup.** Probe 4's set exactly: probe 1's create facts and elsewhere items, plus the being runs.
- 20 bare beliefs (b), 250 plain facts (p) and 69 attributed facts (a, which are not scored).
- The state is "A statement from the entry X, in a fantasy world's records:" followed by the text.
- Scoring: a belief is right when flagged, a plain fact is false when flagged.

| Phrasing | Question | Beliefs flagged | Plain flagged | Attributed flagged | AUC |
|---|---|---|---|---|---|
| H1 | choice belief / attributed / plain (each described) | 5/20 | 54/250 | 60/69 | 0.62 |
| H2 | noul "present a religious belief … as plain fact, without saying who believes it?" | 8/20 | 14/250 (6%) | 31/69 | 0.84 |
| H3 | choice divine / worldly | 20/20 | 165/250 | 68/69 | 0.89 |
| **H4 (r2)** | noul "Does the statement say, as plain fact, what a god did, wants, chose or blessed?" | **12/20 (60%)** | **5/250 (2%)** | 11/69 | **0.95** |
| H5 (r2) | H2 without the "from the entry X" line | 10/20 | 40/250 | 42/69 | 0.81 |

**Best phrasing (H4):**

```
A statement from the entry The Divine Right of the Tsar, in a fantasy world's records:
The Tsar of Moscavia rules by the grace of the Eternal Light, serving as the earthly steward of the Tsardom.
{"type": "noul", "instructions": "Does the statement say, as plain fact, what a god did, wants, chose or blessed?"}
```

**Against Skyfall.** Skyfall tagged 4/20 beliefs (20%) and 9/250 plain facts (4%). H4 tags 12/20 (60%) and 5/250 (2%): three times the recall, with half the false rate.
- Unlike Skyfall's tag, H4 also leaves most attributed facts alone (11/69 flagged), which is what the rubric's "plain fact" wording asks.
- It still misses the 80% bar on recall.

**Confident split.**
- At top probability ≥ 0.8, H4 is confident on 210/270 facts (78%) and right on 206 (98%). Of the 20 beliefs, though, 18 are escalated and only 1 is confidently right. The confident answers are the plain facts.
- **Cascade, LOCO.** It clears 64% with no `hi`, missing 3 of 20 beliefs. Allowing 10% misses, it clears 85% and misses 4.
- So it works as a filter: clear the plain truth and show the owner the remaining 15–36%, which holds most of the beliefs.

**Latency.** 0.24 s mean, about 2.5 s for a 10-fact create.

**Recommendation: better than Skyfall, still under the bar.** If the owner wants `held_by` help at all, use Laya, not Skyfall: an unticked "believed by …?" suggestion on the facts H4 scores at 0.5 or more, with the holder picked by the owner. The holder isn't asked here, and Laya can't produce a name. Otherwise the probe 4 fallback (hand tagging plus the beliefs drawers) stands. 20 beliefs is a small set, and H4 was the fourth try.

## 4. Moving in

**Setup.** Probe 2's five cases. Each of the broader entry's facts is one question:
- 5 should move;
- 2 could go either way (not scored);
- 55 should stay.

The year bracket is stripped.

| Phrasing | Question / state | Moves found | Stays picked | AUC |
|---|---|---|---|---|
| M1 | choice mainly about it / in passing / not about it; new entry's name + description, then the fact | 5/5 | 12/55 | 0.98 |
| M2 | noul "Is the fact mainly about X?"; description + fact | 5/5 | 8/55 (15%) | **1.00** |
| M3 | choice the new entry / the broader entry | 0/5 | 5/55 | 0.44 |
| **M4 (r2)** | noul "Is the fact mainly about X?"; the fact alone ("A fact from the entry Moskov: …") | 4/5 | **2/55 (4%)** | 0.99 |
| M5 (r2) | noul "… rather than about Y as a whole?"; description + fact | 5/5 | 12/55 | 0.99 |

**Best phrasing.** M4 by argmax, M2 for the cascade:

```
[M2 only: "The Architecture of Moskov: the stone, timber and onion domes of the capital, …"]
A fact from the entry Moskov: <fact>
{"type": "noul", "instructions": "Is the fact mainly about The Architecture of Moskov?"}
```

**Against Skyfall.** Skyfall found 10/10 moves and moved 8/110 stays (7%), 4% without its one bad run.
- **M4** finds 4/5 and moves 2/55 (4%). It misses the Zakonnik's fact (0.40). Its two false picks are the Architecture's cathedral and "political centre" facts, which Skyfall's bad run also took.
- **M2** finds 5/5 with 8/55 false at 0.5. Its ranking is perfect, though: every move scores above every stay.

**Confident split.**
- M2 at top probability ≥ 0.8 is confident on 38/60 facts, all right, including all 5 moves.
- M4 at ≥ 0.8 is confident on 55/60, all right, including 3 of the 5 moves.
- **Cascade, LOCO (M2).** It decides 58/60 facts with none wrong, escalating 1 move and 1 stay. M4 decides 53/60, with 1 move missed.

**Latency.** 0.23–0.24 s per fact, so about 5 s for the Tsardom's 23 facts, against Skyfall's 0 extra seconds (its picks ride the create call).

**Recommendation: Laya when confident, the owner otherwise.** This is probe 2's "pre-tick" option, with Laya instead of Skyfall's picks:
- list every fact of the broader entry;
- pre-tick those M2 scores at 0.8 or more;
- order the rest by score.

This is the only judgement where Laya's flags were right when it was confident. It rests on 5 positives in 5 cases, with the phrasing chosen after 5 tries, so confirm it on a fresh case set before relying on it. The cost is a separate quarter-second per fact.

## 5. Elsewhere check (the "either side" reading)

**Setup.** Every elsewhere item from probe 1, v1 and v3 (225 scored). Under the owner's reading the truth is:
- **false (13 items):**
  - the 2 create items still false under the loose reading (the Divine Right's "doctrinal cornerstone…", the Illumination's "also known as the Blinding Transformation");
  - the 11 Fill false moves (a detail of the reply's own new item);
- **right (212 items):**
  - right items, codes r and n;
  - create and core relation claims (strict f, right on either side).

Wrong-entry items (w, x, 5 items) aren't scored.

**The state.** E1–E4 give the sentence, then A (the entry being written, with its first own fact or summary; in Fill, the new items with their one-line texts), then B (the target, with its nearby line). E5 gives the sentence alone, with every candidate home named as an option.

| Phrasing | Question | False caught | Right flagged | AUC |
|---|---|---|---|---|
| E1 | choice A itself / B itself / how A and B are tied | 6/13 | 133/212 | 0.42 |
| E2 | noul "mainly a description of A rather than of B?" | 4/13 | 97/212 | 0.38 |
| E3 | choice "whose page does it describe": A / B | 3/13 | 138/212 | 0.29 |
| E4 (r2) | noul "Is the subject of the sentence A?" | 7/13 | 163/212 | 0.39 |
| **E5 (r2)** | choice "Which entry does the sentence describe?", one option per home (the entry, or each new item, and the target); the sentence alone | **12/13** | 66/212 (31%) | 0.93 |

**E1–E4 rank below chance.** Given both entries' descriptions, Laya reads "A" into nearly everything that mentions A. The descriptions seem to pull it towards whichever entry the state describes at more length.

**E5 by prompt.**

| Prompt | False caught | Right flagged | Relation claims flagged |
|---|---|---|---|
| Fill | 10/11 | 4/37 | – |
| create | 2/2 | 22/62 | 21/35 |
| core | – | 18/77 | 1/1 |

**Fill.** E5 does what the post-hoc code filter does: it drops an item whose subject is one of the reply's new items. The code filter caught 10/11 with 0 right items dropped. E5 catches 10/11 and flags 4 right items. At top probability ≥ 0.9 it catches 9/11 and flags 1 right item. It adds nothing the code doesn't.

**Create and core.** E5 flags a third of the right items and two thirds of the relation claims. That is the strict reading, not the owner's: Laya can't tell "about A" from "ties A to B".

**Confident split.** E5 at ≥ 0.9 catches 10/13 and flags 14 right items. LOCO decides 58%, missing 1 and flagging 1. Under the cascade, 88 of the 94 escalated items are right items.

**Latency.** 0.22 s (E5) to 0.38 s (E1).

**Recommendation: don't use Laya.**
- **Fill:** keep the code filter (drop an item that opens with one of the reply's new items' names), which is at least as good and free.
- **Create:** the two loose-false items are 2 in 75. Under the either-side reading, nothing measured here needs a check.

## Setup notes

- **Venv.** `guix shell -m manifest.scm -- uv venv <scratch>/laya-venv --python 3.11`, then:
  - `uv pip install --index-url https://download.pytorch.org/whl/cpu torch`, which gave torch 2.14.1+cpu;
  - `uv pip install --exclude-newer 2026-10-15T00:00:00Z laya`, which gave laya 0.4.7 and transformers 5.19.
- **Install from the scratchpad.** Run from the worktree, uv picks up the project's `exclude-newer = "1 week"` and finds no Linux torch wheel. Installing from the scratchpad directory avoids that. The PyTorch CPU index has no upload dates, so the week's cooldown could not be checked for torch. Laya and the rest were held to a cutoff a week back.
- **Disk.** The venv is 914 MB and the model 808 MB (`HF_HOME=<scratch>/hf`). Only the English checkpoint was fetched, not the 2.3 GB bundle. That is about 1.7 GB in the scratchpad, nothing in the project.
- **Run.** `export LD_LIBRARY_PATH=$GUIX_ENVIRONMENT/lib USE_TF=0 HF_HUB_OFFLINE=1` inside the guix shell. `HF_HUB_DISABLE_XET` wasn't needed.
- **Warning.** Laya warns that the checkpoint's `choice:11+` temperature is out of range and clamps it to 0.5. No question here had more than 5 options, so the temperatures used were `choice:2` 1.91, `choice:3-5` 1.76 and `noul:2` 1.98. Calibration wasn't refit: there are too few positives.
- **Runs.** Round 1 took 19 minutes and round 2 13 minutes, at a 9–15 load average from other work on the machine.
