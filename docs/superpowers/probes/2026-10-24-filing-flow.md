# Probe: filing in a real session (Filing plan, Task 12)

Date: 2026-10-24. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client (the `--ai` app's config, so each call ran at the app's own kind and preset). Calls ran one at a time: one lock around the client, because the router's prose refreshes for different entries would otherwise overlap. The owner approved Skyfall for this task ("you have permissions to use skyfall for any tasks").

- **Script:** `scripts/dev/probe_filing_flow.py`. It drives the real `worlds` router (`WorldsPlugin`) in a fresh world (present year 1000), with Task 11's session (`tests/worldplay/test_filing_end_to_end.py`), plus the unprobed items this task measures. It has four modes:
  - `--fake` checks the harness with canned replies;
  - `--score` produces the code scores;
  - `--replay LABEL` answers recorded calls while each prompt is unchanged;
  - `--scene-of LABEL` re-runs a run's scene, with the same setup, on a copy of its world.
- **Labels:** `raw/2026-10-24-filing-flow-labels.json`. They were committed in 9d5ab28b before any model call, and amended once before any model call (99f307dd: Koroleva's prompt no longer names "pre-Blinding" lore, which this fresh world lacks). They hold the owner policy, the expected and "either" homes and "File into" rows, the acceptable tags, and the judging rules.
- **Raw output:** `raw/2026-10-24-filing-flow.json`. It has three runs: `run 1`, `run 1 scene, fixed` and `run 2`. Each records its steps (both versions of every draft, the owner's choices, the accepts), every call (uid, kind, prompt, reply, seconds, KoboldCpp's own prompt and reply token counts from `/api/extra/perf`) and the code `scores`.
- **The runs:**
  - **Run 1:** 101 calls, 26.8 minutes.
  - **Two fixes** followed run 1 (see "Fixes").
  - **`run 1 scene, fixed`:** run 1's scene again, on a copy of its world, with the same setup (4 calls). This is the before/after on the same case.
  - **Run 2:** the whole session again with the fixes in (96 calls, 25.3 minutes). It replayed run 1's recorded replies while the prompts matched, but its fourth prompt (the Tsardom's) already differed, so 92 of its calls are new: it is a second sample of the whole session.
- **Worlds:** under this session's scratchpad (`ff-run1/root`, `ff-run2/root`). The owner's live world was never touched.

## The owner's policy (labels, `owner_policy`)

- **Two versions of every draft.** Each create draft is generated twice: v1, then Regenerate with its draft key, which gives v2. Both are scored. v1 is then restored (`use_version 1`) and accepted, so each world follows its v1s. Wattles is discarded instead.
- **"In":** a row is ticked only when its target is "expected". "Either" rows stay unticked. An expected home the model missed is added with "+ in…", as Task 11's owner did.
- **"File into this":** a row is ticked only when it is "expected".
- **Everything else as it arrives:** new names, elsewhere items, repeats, "Could move here", same-thing offers left "new", the tag chip unchanged.
- **Stubs:** an entry is expanded from its stub when one matches; otherwise it is made from a fallback prompt with the create box's picks. Task 11's own prompts are used verbatim. One addition, made before any model call: a draft that offers "fill the stub instead" (`matching_stub_id`) fills it.
- **The regiments:** the White Talon and the Frosted Wing label the Host "either", so the owner leaves them unfiled in it. That lets the Host's own draft measure "File into this" and ruling F6.
- **"+ Add" with no tag:** the owner clears Velikoye's row tags before accepting, so that its untagged group, and so its "other entries" synopsis, exists.

Each choice is recorded in its step's `choices`.

## What happened (the session's shape)

Skyfall seldom named the session's entries as stubs. So most entries came from the labels' fallback prompts, recorded per step as `from`:
- the Tsardom came from its stub;
- the Night Court filled a stub of its own name, "Nocturnal Duma", in run 1;
- the rest came from prompts.

## Summary

The bar is at least 80% right and at most 5% false.

| Measure | Score (run 1 + run 2) | Verdict |
|---|---|---|
| Tag | 32/60 right (53%); fitting tag in use reused 15/20 (75%) | **FALLBACK**: the editable chip (ruling F8) stays |
| "In", either side | found 41/60 (68%); 41/52 (79%) where a near list existed; false 0/60 | **FALLBACK**: shown, unticked (F7) stays |
| "In", strict | false 19/60 (32%) | (the "either" rows offered) |
| Thin stubs | 4/96 (4.2%); F5 dropped 22 titles, 1 wrongly | **PASS** with the F5 filter |
| "File into this" | expected 6/8 (75%); false 2/16 (12.5%) either side, 10/16 strict | **FALLBACK**: unticked (F7) stays |
| Group synopsis | 83/88 claims supported (94%); 0 invented names, dates or numbers; over 70 words 12/14 | **PASS** (the length cap is ignored) |
| Repeats (final worlds) | 0.7: 3/194 and 0/191; 0.5: 13 and 5; 0.4: 34 and 20 | far below the curation world |
| On-topic own facts | 318/324 (98%) | as the curation run (98%) |
| No world context | 5 of 6 such drafts contradict the world | **new problem**, see below |
| Scene: F4 role rule as ruled | Koroleva touched 1/2 runs; Chief Scribe invented 4/4 when she wasn't | **FAIL** as ruled; **PASS** with fix 2 (2/2, 0 invented) |
| F6 sibling reach | the Frosted Wing in the Host's list 4/4 (rank 6/17, 5/14), by a link, not as a sibling | **PASS** for reach; the sibling-only path wasn't exercised |
| Character "In" with exceptions | Koroleva: written 3/4, a sensible item 3/3, also restated as a fact 3/3; Vasha: none 4/4 (right) | **FALLBACK**: unticked, the owner edits |
| "+ Add facts" / "+ Add event" | 39/39 facts on the prompt; 0 repeats; 20/20 dated 997 | **PASS** |
| Group "+ Add" with no tag | 12/12 rows right; count 8/8; tags fit 12/12; 0 duplicates | **PASS** |
| The "other entries" label | 4/4 synopses read it right; their claims 19/19 | **PASS** |
| `nearby` (mentioned_in) | shown, no row duplicated an entry | **PASS** |
| World block filing lines | used as character 2/2 where shown; never recited; no flooding | **PASS** |

"Run 1 + run 2" means 2 versions × 15 drafts × 2 runs = 60 draft versions. The scene, synopsis, "+ Add" and fact numbers pool both runs.

## Fixes (run red first; plain suite 7475 passed, 0 failed)

1. **3469ae78 `fix(worldplay): the create prompt asks for the tag without a near list`.**
   - **The fault:** the create template's "tag" rule sat inside `{% if nearby %}`. A prompt that names no entry in full gets no "Entries near this one" list, and with it went the tag rule, although the example object still asks for `"tag"`.
   - **Run 1's evidence:**
     - Runic Magic's replies wrote "lore", a kind, so no tag (2/2);
     - the Order's wrote "institution" (2/2), and the White Talon's "military" (2/2), both taken from the tags line;
     - none of these is a fitting tag.
   - **The fix:** the rule now shows on every branch but species and race. "In" and "file_into" still need the list.
   - **Test:** `test_tag_rule_without_entries_near`, red first.
   - **After (run 2, same cases):** the rule was present in all 6 of these prompts, but the tags were no better: Runic Magic "lore" 2/2, the Order "scholarly society" and "institution", the White Talon "military institution" 2/2. **The render is fixed; no gain in the score was measured.**
2. **7be888e0 `fix(worldplay): a compound filing role is named by its parts`.**
   - **The fault (ruling F4's rule):** a person filed in a touched entry is touched only when the setup names their filing role, whole and in order. Skyfall gave Anastasiya Koroleva compound roles: "senior member and Chief Scribe" (run 1 v1, and run 2 v1) and "Chief Scribe and member" (run 1 v2). A goal saying "the Chief Scribe" never names such a role.
   - **Run 1's evidence:**
     - she wasn't touched;
     - the planner invented a local "Chief Scribe Elara Voss";
     - the narrator invented the Chief Scribe 4 of 4 turns, a bearded man, twice named (Dmitri Yefimov);
     - Koroleva's own lines ("She rose to the position of Chief Scribe in 995") sat in the block, gathered under Runic Magic.

     This is probe 5's v1 failure again.
   - **The fix:** a role joined by "and", ",", ";", "/" or "&" is named by any of its parts, still as whole words. A generic part ("member") touches no one.
   - **Test:** `test_a_compound_role_is_named_by_its_parts`, red first.
   - **Before/after on the same case** (`run 1 scene, fixed`: the same world copy and the same setup):
     - Koroleva is touched, and her block entry carries her filing line ("Senior member and Chief Scribe of the Order of the Talon-Scribe, but: …");
     - the narrator tells the Chief Scribe as Anastasiya Koroleva in every turn she appears (3/3: by the door plate, and twice in person, with her grey hair, her styli calluses and her secret carving), and invents no one (0/4);
     - in the fourth turn she isn't on stage.
   - **Run 2:** she is touched under the new rule. The old rule would also have touched her (the planner's goal said "Chief Scribe Koroleva"), so run 2 doesn't separate the two rules. The narrator told her right 2/2, invented 0/4.
   - **This refines ruling F4.** It changes the matching rule, not prompt wording, and the controller should rule on it. Reverting is one function.

Prompt wording was not changed.

## Measures

### Tag (bar 80%): FALLBACK, the editable chip stays (F8)

- **Run 1:** 19/30. **Run 2:** 13/30. **Pooled:** 32/60 (53%). Task 1's labels gave 64%.
- **With a near list (and so the tag rule) in both runs:** 32/44 (73%).
- **Reuse:** where a fitting tag was in use, it was reused 15/20 (75%).
- **What goes wrong:**
  - **The species branch never asks for a tag.** The owl-folk were untagged 4/4. Its example object has no `"tag"`, so no species ever gets one, though the constraints say every kind has one. This is a design gap, not fixed here.
  - **The Night Court is "institution" 4/4,** as in Task 1. The labels want council or court.
  - **A kind or "person" as the tag:** Koroleva "character" (run 1 v1), "person" ×2 and "person, scribe" (run 2). Vasha "person, courier", "character".
    - Ruling F8's comma rule keeps the first part, "person", where "scribe" and "courier" were right.
    - Suggested: skip a first part that is a kind, "person" or "lore" (the probe's own untested suggestion).
  - **Two-word compounds:** "military institution" took hold in run 2 (the Frosted Wing v2, the Host 2/2, the White Talon 2/2) once it was in the tags line.

### "In" (bar 80% right, 5% false): FALLBACK, shown unticked (F7) stays

- **Found:** 41/60 (68%) over every draft version. 8 of the 19 misses are drafts with no near list (the Order and the White Talon, 2 versions × 2 runs), which can file nowhere. **Where a list existed: 41/52 (79%)**, the same as Task 1's 73–79%.
- **The same miss as Task 1:** the Academy is never filed in Runic Magic (0/4), so the owner adds it.
- **The rest vary run to run.** Plumage Signaling found the Night Court 2/4 and the owl-folk 1/4, and the Khorol found Velikoye 2/4.
- **Either side: 0 false of 60.**
  - Six rows the labels don't key were judged "either": the Academy in the Quill of Teaching (its own division), the Frosted Wing in the "Taloned Host" ×2 and the "Krylaya Gvardiya", the Host in the Krylaya Gvardiya, and Vasha in the Grand Scriptorium.
  - The Tsardom "in" the owl-folk ("home of") is the plausible pair reversed.
- **Strict: 19/60 (32%).** These are the "either" rows offered, mostly the Academy in the Order (4/4) and the Tsardom.
- **Roles were sane:** "flows through", "capital city", "standing army", "located in", "practised in". One was overlong: "the default communication mode used in its proceedings".

### Thin stubs (bar 5%): PASS with the F5 filter

- **Rate:** 4 of 96 stubs were thin (4.2%): run 1 3/59, run 2 1/37. The four, judged by the labels' thin rule:
  - **"Ataman of the Quill":** a title, but the model tagged it "institution", so F5 let it through;
  - **"Frostwarden"** and **"Frostward":** the practitioners' name, tagged "institution";
  - **"Gorath Vaelin":** a war cry.
- **F5 dropped 22 names** whose kind or tag is office, title or rank: Tsar, Holy Patriarch, Arch-Talon, volostnik, Nochnoy Predsedatel, Voinovo… One drop was wrong: "Bureau of Plumage and Accouterment", a named bureau tagged "office", in the discarded Wattles.
- **Curation world:** not measured there.

### "File into this" (bar as "In"): FALLBACK, unticked (F7) stays

- **The Host's expected regiments:** 6/8 over its four versions. Each v2 offered both the White Talon and the Frosted Wing; each v1 offered only the White Talon, so the accepted world never filed the Frosted Wing in the Host.
- **False, either side: 2/16 (12.5%).** Both are run 1's Host offering the "Taloned Host" stub into itself: once with no role, once as its "parent institution" (a duplicate of the Host, judged false).
- **Strict: 10/16.** These also count:
  - the owl-folk offered into the Tsardom (3 of 4 versions);
  - the Night Court's v1 and v2 offering Velikoye into the Court, which is the Court's seat reversed;
  - Plumage Signaling v2 (run 2) putting all three of its homes into "File into this", reversed, and none under "In".
- **The code source** (near entries whose facts name the entry) added no false row this time. Task 11's Khorol and Night Court rows didn't recur.

### Group synopsis (bar 80%): PASS

- **Groups (8 asked twice each):**
  - Velikoye's landmarks (run 1);
  - Velikoye's untagged group (2/2 runs);
  - the Tsardom's militaries (2/2 runs);
  - the Tsardom's rivers (run 1);
  - the Tsardom's institutions (run 2).
- **Claims:** 83/88 supported (94%), counted per claim against the members' lines and the page summary, as probe 3. Task 1 had 30/32.
- **The 5 wrong:**
  - the Taloned Host "established after the Turning" (×2, from the Frostwing Host's line);
  - the Night Court "shares the eastern quarter with" the academies, and "forming a corridor of learning" with them (two claims);
  - the White Talon "stationed at Karrath Hold" (it trains there).
- **Invented names, dates or numbers:** none.
- **Length:** the cap ("at most 70 words") was kept 2/14 times (65 and 70 words); the others ran to 73–107. Task 1 saw one overrun of 6.
- **Cost:** 4.1 s, about 870 prompt and 128 reply tokens.
- **Stale after a new member:** the router shows `null` when a group gains a member (Task 11's check). Here neither run had a cached group that gained one (the Academy and the Night Court were tagged differently in run 1), so this rests on the MockClient test.

### Repeats: far below the curation world

The final worlds, scored with the code's overlap (`world.repeats.overlap`):

| | Curation, old | Curation, new | Filing run 1 | Filing run 2 |
|---|---|---|---|---|
| Facts | 229 | 190 | 194 | 191 |
| Flagged at 0.7 | 76 (33%) | 16 (8%) | 3 (1.5%) | 0 |
| Flagged at 0.5 | 133 (58%) | 50 (26%) | 13 (6.7%) | 5 (2.6%) |
| Flagged at 0.4 | 163 (71%) | 71 (37%) | 34 (17.5%) | 20 (10.5%) |

- **Run 1's three hits at 0.7** are relation claims written on both pages (the Duma's hall, its nocturnal schedule) and one Velikoye self-repeat.
- **Like for like?** The comparison is fair in kind (both are whole sessions from a fresh world, scored the same way), but not in shape. This session has no move-in, and filing writes nothing onto another entry's facts. The curation doc's two new kinds of repeat (moved facts beside a later restatement, and relation claims on both sides) mostly can't happen here. Read the gap as "the filing pipeline restates far less", not as "the model got better".

### Duplicate entries

These pairs were hand-checked from `same_candidates` and the stubs.
- **Run 1 (4):**
  - Ataman Sable Korven / Sable Korven;
  - Border Wars / Border Wars of 987;
  - the Taloned Host / the Frostwing Host (the realm's army twice; the Host's own elsewhere item even calls the Taloned Host "an older name sometimes used interchangeably");
  - Velikigrad (a stub of Velikoye's old name) / Velikoye.
- **Run 2 (1):** Velgrad, called "the imperial capital" by the Order and the place Koroleva trained at the Academy, against Velikoye.
- **Curation, before its merge:** 5 against 5.
- **Like for like:** comparable in count only. The worlds differ in size and shape (73 and 51 things here; 66 in the curation run).

### On-topic own facts: as the curation run

- **Score:** 318/324 own facts (98%) are mainly about their entry, judged by the curation labels' rule (either side), over every accepted v1 draft (run 1 157/161, run 2 161/163).
- **The 6 misses:** the owl-folk's "the Tsardom continues to function…" (×2), the Tsardom's fact about the Duma's hours, its fact about owl-folk births and its fact about the academies' scholars, and the Duma's (unticked) "daytime is reserved for rest".
- **The curation run:** 69/70 (99%); its 5 comparable entries 57/58 (98%), against the old world's 44/56 (79%).
- **Like for like:** only the White Talon was made in both runs, from different prompts. Here it scored 11/11 and 12/12 on topic, but see the next section.

### New: a draft with no world context contradicts the world (5 of 6)

- **When it happens:** a prompt that names no entry in full ("Runic Magic of the Tsardom: …", "The Order of the Talon-Scribe, the order of rune scribes that keeps and teaches the Tsardom's runes", "The White Talon, the heavy regiment of the Frostwing Host" before the Host exists) gets no picks. The stub is new, so there are no seeds, and `filing_candidates` returns nothing. The prompt then has no "Entries near this one", no "In", no "file_into", no elsewhere, and no world at all beyond the tags line.
- **What it costs:**
  - the White Talon is "the standing army of the Kingdom of Aelthar" (run 1) and "of the Kingdom of Valdenmere" (run 2), and run 1's v1, the version accepted, made 15 stubs of that invented kingdom;
  - the Order's seat is "the capital city of Khorov" (run 1) and "the imperial capital of Velgrad" (run 2);
  - run 2's Runic Magic is "in the Tsardom of Kaelith", trained "in the capital city of Morozgrad";
  - only run 1's Runic Magic stayed consistent.
- **The planner and the narrator then had several capitals to choose from.**
- **The curation run had the same branch** (Runeweaving from a prompt, with no near list), so this isn't a regression. Every other curation create had a stub or a `part_of`.
- **It's design (F6's candidates come from the context, and an empty context gives none), so it isn't fixed here.** Two options:
  - offer the prompt's partial matches (`find_names` suggestions, such as "Tsardom" in "of the Tsardom") as context;
  - with no context at all, list the world's most-filed entries.

  The owner would also see it: a create box whose prompt names "the Tsardom" shows it only as a suggestion. Task 13's acceptance will meet this.

### Scene: ruling F4's whole-word role rule (the Chief Scribe case)

- **As ruled:** FAIL on run 1. Koroleva's compound role wasn't named, and the Chief Scribe was invented 4/4, as above.
- **With fix 2:** PASS. She was touched 2/2 (run 1's same-setup re-run and run 2), told right in every appearance (3/3 and 2/2), and invented 0/8.
- **The whole-word half of the rule:** no role in either world matched the setup only as a substring (`roles_substring_only` empty both runs), so there is no evidence on it either way.
- **The touched sets:**
  - **Run 1:** Velikoye, Runic Magic, the Tsardom, the Order, "Verkhov" (a stub town the planner pulled in), and Koroleva once fixed.
  - **Run 2:** the same four, plus "Volga" and "Moskva" (rivers the planner pulled in), plus Koroleva.
  - **Never** Vasha, the Academy or the Tsar, as labelled.
- **The planner** invented its own Chief Scribe in run 1 ("Elara Voss"). In run 2 it wrote Koroleva as an invented local character ("Chief Scribe Anastasiya Koroleva", no thing id) rather than as the world's entry. That's scene planning's reuse, outside filing (concern 3).

### F6 sibling reach: PASS for reach; the sibling-only path not exercised

- **Neither run had a Frostwing Host stub,** so the Host came from its fallback prompt both times. Run 1's White Talon v1 never listed it as a name, and run 2's v1 didn't either.
- **Reach:** the Frosted Wing was in the Host's "Entries near this one" in 4/4 versions (rank 6 of 17 in run 1, 5 of 14 in run 2). It got there **by a link**: the prompt's pick, the Tsardom, is a seed, and the Frosted Wing is filed in it. The sibling-only path (a stub with no filing whose mentioner's home holds the Frosted Wing) never came up on the model. It rests on `test_candidates_reach_siblings_and_parts_within`.
- **Offers:** being in the list, it was offered into the Host in 2/4 versions (each v2), with the role "elite regiment" or "specialized regiment".

### Character "In" with exceptions: FALLBACK (unticked; the owner edits)

- **Koroleva** (her prompt states a departure: "In secret she still carves runes the Order no longer approves"):
  - an exception was written in 3/4 versions;
  - each one's "rejects" names the Order's oath item, S5 ("transmit the runes faithfully without alteration", run 1; "the Oath of the Flawless Stroke", run 2), and its text departs from it: 3/3 sensible on its own;
  - but every one is also restated as an own fact ("In a hidden workshop beneath her quarters, she carves runes…"), which the wording forbids ("Write each exception only there, never again as one of the facts"). By the labels' full rule that's 0/3, and the World block then tells it twice;
  - run 2's v2 wrote no exception.
- **Vasha** (no departure in his prompt): no exception 4/4, which is right. The model made Vasha a woman 4/4; his prompt gives no sex.
- **Suggested:** drop or untick an own fact that repeats an exception's text, as repeats are flagged (a code rule, untested).

### "+ Add facts" and "+ Add event": PASS

- **Requests (each run twice per session):**
  - Velikoye, "its winter markets and what they sell": 4, 5, 5 and 5 facts;
  - the Tsardom, 997, "a failed uprising of the human nobles against the owl-folk Tsar": 5 facts each time.
- **Score:** 39/39 facts on the prompt and about the entry, 0 flagged repeats, 0 contradictions judged. Each run names a Tsar where the Tsardom's facts name none, which is invention, not contradiction. Every event fact is dated 997 (20/20, by code).
- **The categories fit the kind:** a place's "description" and "general"; a nation's "history".
- **Cost:** 11.1 s, about 1,020 prompt and 377 reply tokens.

### Group "+ Add" with tag=None, the "other entries" label, `nearby`: PASS

- **Requests (each run twice per session):**
  - Velikoye, "two taverns where owl-folk and humans drink together": 2 rows each time;
  - the Order, "a chapter house of the Order in another city of the Tsardom": 1 row each time.
- **Score:** 12/12 rows named, of kind place, with their own fitting tag ("tavern" 8/8; "chapter house" 3/4, plus "chapter-house"), and none a duplicate. The count was followed 8/8.
- **The "other entries" label:** the untagged group's synopses (after the owner cleared the tavern rows' tags) read "the other entries filed in Velikoye" as what it holds ("two taverns", "two establishments in Velikoye's drinking culture"), 4/4. Their claims were all supported (19/19).
- **`nearby` (the router's `mentioned_in`, up to 12 names):** it gave, for example, "Velikigrad; Nocturnal Duma; The Turning; The Frostwing Host; Plumage Signaling". No row duplicated any entry, listed or not.
- **Cost:** 5.6 s, about 920 prompt and 178 reply tokens.

### The World block's filing lines for touched persons (Task 11's fix 2): PASS

- **Where shown:** Koroleva's line appeared in the fixed run-1 scene and in run 2 ("Senior member and Chief Scribe of the Order of the Talon-Scribe, but: …").
- **Used as character, never recited:** she sweeps a half-carved tablet under a cloth; she has spent fifteen years reconstructing a pre-Fire rune variant from Vostov's notes.
- **No flooding:** every detail used is tied to the direction.
- **Cost:** her entry adds about 320 prompt tokens (2,710 → 3,057 and 3,717 → 4,034 on the same turns).
- **Two block issues not fixed (no narrator misuse seen):**
  - Lines gathered from another entry lose their subject. Under Runic Magic, run 1's block read "In 975: She entered the Order…" and "In 995: She rose to the position of Chief Scribe…" (Koroleva's, gathered two steps down while she wasn't touched). Under the Tsardom it read "In 1000: The regiment enjoys a reputation…" (the Frosted Wing's).
  - The model dates states at the present year ("In 1000: In the year 1000, Moscavia stands as…"), the curation run's clutter again.

### How the scene uses its context (rubric of probe 5)

- **Details used, tied to the action:** the crescent halls and courtyard workbenches, the grey-and-ochre robes and talon-styli, the Kolyma view, the Oath of the Unbroken Line examination notices, the Moonwell Library, Plumage Studies.
- **Contradictions:**
  - run 1 before the fix: the invented Chief Scribe (4/4), against Koroleva's facts in the block;
  - after the fix: one small one, her hair "close-cropped" against her entry's "pulled back tightly";
  - run 2: none judged.
- **Flooding:** none. No turn recites lore the direction didn't call for.
- **Cost:** narrator turns took 15 s, at 2,700–4,000 prompt tokens and the 512 cap.

## Cost

Both runs, mean, from KoboldCpp's own counts:

| Call | Calls | Seconds | Prompt tokens | Reply tokens |
|---|---|---|---|---|
| create (`creative_instruction_3072`) | 60 | 37.4 (24.7–54.3) | 2,627 (max 4,122) | 1,279 (max 1,882) |
| prose (`thing-prose`) | 89 | 5.4 | 810 | 171 |
| same-thing verdict | 8 | 2.3 | 813 | 56 |
| add facts / event (`creative_instruction_2048`) | 8 | 11.1 | 1,021 | 377 |
| group "+ Add" (`creative_instruction_1024`) | 8 | 5.6 | 921 | 178 |
| group synopsis (`analyze`) | 14 | 4.1 | 873 | 128 |
| scene setup | 2 | 16.8 | 2,100 | 529 |
| narrator turn (`narrate_512`) | 12 | 15.2 | 3,250–4,030 | 497 |

- **A whole session** with two versions of every draft is about 100 calls and 25–27 minutes of model time.
- **The curation run** took 42 calls and 9.4 minutes, with one version per draft.

## Concerns, for the controller

1. **A draft with no world context contradicts the world (5/6).** See its section above. This is the biggest cohesion problem the session showed. It's a design question for ruling F6: what a create prompt is shown when nothing in it names an entry.
2. **Fix 2 refines ruling F4.** Compound roles are matched by their parts. It has a same-case before/after (invented 4/4 → 0/4) and one more run.
3. **Scene planning doesn't reuse the Chief Scribe.** It invented one (run 1), or wrote Koroleva as a local character instead of the world's entry (run 2). Filing can't fix this.
4. **Tags are 53%.** Three code-side gaps:
   - species are never asked for a tag;
   - F8's comma rule keeps "person" from "person, scribe";
   - a kind name ("lore", "character") falls to no tag rather than to the second part.
5. **Exceptions are restated as own facts 3/3.** The block and the page then tell them twice. A code rule (untick an own fact that repeats an exception) is suggested.
6. **Gathered timeline lines lose their subject** ("She rose to the position of Chief Scribe…" under Runic Magic). Not fixed: no narrator misuse was seen, so a wording change would have no evidence behind it.
7. **The synopsis length cap is ignored** (12/14 over 70 words). The claims stay accurate.
8. **The harness's run 1 group-add record:** the owner's tag-clearing step overwrote the recorded rows' tags in run 1 (fixed in the script for run 2). The model's tags in run 1 are in the raw replies (`calls[i].response`): "tavern" 4/4, "chapter house" 2/2.
