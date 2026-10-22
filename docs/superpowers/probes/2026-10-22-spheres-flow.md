# Probe: the owner's spheres session on Skyfall

Date: 2026-10-22. Model: koboldcpp, Skyfall-31B-v4.2-i1-Q4_K_M, through Talemate's own KoboldCpp client (the `--ai` app's config, default agent settings). Calls ran one at a time. This is Spheres Task 10: the owner's measure from the spec ("How the owner will judge it"), run through the same code path the world screens use.

- Script: `scripts/dev/probe_spheres_flow.py`. It drives the real `worlds` router (`WorldsPlugin`), with the real client on every agent:
  - `preview_thing`, `accept_preview`, `stub_suggestion`, `make_stub`, `add_fact`;
  - `preview_sphere`, `accept_sphere`, `fill_drawer`, `accept_fill`;
  - `match_names`, `plan_scene`, `start_scene`.

  The scene is then loaded through its `world://` target and narrated with `progress_story`, as `probe_heritage_play` does. No fixed reply is used (`TALEMATE_TEST_FIXED_SPHERE` is not set).
- Raw output: `raw/2026-10-22-spheres-flow.json`. `runs` holds four runs, each with:
  - every call (prompt, reply, seconds);
  - each step's payloads (the thing, a sphere's drawers and items, part of, ties, stubs);
  - the World block, and each turn's prompt and output.

  `judged` holds the counts below.
- What's approximated:
  - scene planning's world index uses the tests' trigram embedding, not the app's ChromaDB one;
  - agents run with their default config;
  - there is no frontend.

## The runs

| Run | What | Calls | Why |
|---|---|---|---|
| 1 (stopped) | the owl-folk, then the Tsardom from its suggested prompt alone | 7 | The Tsardom named **no faith at all**. Its 12 facts covered law (the Zakonnik code), the Tsar, trade and farming. I stopped it: the probe's faith match had picked the Zakonnik, a law code, on "dawn-to-dusk". |
| 2 | the Tsardom only, with the owner's words "It has a state church." added to the suggested prompt; the names wording as it was | 4 | **The guess failed:** the reply listed "State Church of the Holy Radiance" as `"kind": "lore"`, as the old names rule says ("a group, order or faction is lore"). |
| 3 | the full session after the names wording fix (Fix 2) | 24 | the session below |
| 4 | the scene step again after the stub prompt fix (Fix 3). Steps 1–5 were replayed from run 3's recorded replies, so only planning, its stub previews and the turns called the model. | 12 live | the affected step, re-run |

Timing in run 3:
- creates and cores took 22–38 s each (the religion's core took 37.6 s);
- Fill took 11–12 s;
- prose took 5–6 s;
- narrator turns took 12–17 s.

The whole session took about 9.5 minutes.

## The session (run 3)

The world is fresh, with the present in 1020.

1. **The owl-folk:** the owner's plan B prompt. The Tsardom became a stub.
2. **The Tsardom**, expanded from its stub. The prompt was the suggested prompt plus "It has a state church."
   - Its names: **"Church of the Divine Sovanie": `sphere`, template `religion`**, so it became a religion sphere stub.
   - Also "Border Watch", which came as kind `order` and so became an order sphere stub (a border corps; the spec counts militaries as orders).
   - Also 12 others: 7 places, 3 characters, an event and an item.
3. **The council first.** The Tsardom named no council of the church. So the probe wrote one in by hand, as the owner would:
   - `add_fact` on the Tsardom: "The Council of Elders of Church of the Divine Sovanie rules on its doctrine from the capital.";
   - `make_stub` "Council of Elders", kind lore.

   It was expanded from its suggested prompt (11 facts). Then the church was expanded as a religion from its stub (one core call).
4. **Fill** of the church's Doctrines drawer, then of its Rites and Ceremonies drawer; every item was kept.
5. **Vasha:** "Vasha, an owl-folk courier raised in Church of the Divine Sovanie, who keeps The Dawn Vigil faithfully but thinks The Doctrine of Transcendence is nonsense". The rite and the doctrine were named from the core's own items. `match_names` picked the church, the Vigil, the doctrine and the owl-folk.
6. **A scene at the church's first holy site, the Hall of Lanterns.** It was planned by the model with the hall and Vasha picked, then started, loaded and narrated for 2 turns:
   - "Dawn breaks and the faithful begin The Dawn Vigil…";
   - "An elder notices Vasha and asks whether she still keeps the faith."

## Judged against "Passing means"

### Spheres come out with sensible, specific drawers: **pass**

The core gave 5 drawers of 4 types, plus the app's People and Timeline:

| Drawer | Items |
|---|---|
| Doctrines (beliefs) | The Doctrine of Transcendence, The Sanctity of the Owl-Form; 1 statement |
| Rites and Ceremonies (practices) | The Dawn Vigil, The Feast of Saint Ilarion, The Sovanie Remembrance |
| Holy Sites (places) | Hall of Lanterns, The Cathedral of the Transfigured; 1 statement ("every parish church…") |
| Hierarchy (structure) | **Council of Elders (adopted)**, Archpriests ("report to the Council of Elders"), Parish Priests |
| Scripture and Learning (knowledge) | The Sovanie Texts, The Archive of the Council; 1 statement |

- That is 14 items: 11 named, 3 statements. They made 10 new stubs. The Hall of Lanterns, an existing free stub, was linked in rather than made again.
- Every item belongs to this church and this world: the Sovanie, Saint Ilarion, the Amber Palace. None is generic filler.
- The timeline has 3 entries: 1014 (the Sovanie), 1018 (Elder Marfa elected Chair) and 1019 (the Council's first edict). There's no "now" entry and no year after 1020.
- **Fill:**
  - **Doctrines:** 4 new items (3 named, 1 statement) and **0 repeats**. One doctrine, the Doctrine of Boundaries, grew out of the Tsardom's sealed-borders fact.
  - **Rites:** 5 new items and 0 repeats: the Harvest Tithing, the Naming Rite, the Gliding Procession, the Vigil of the Untransformed, and the Border Blessing ("bless the Border Watch scouts").

### Following links grows them naturally: **pass, with one fault fixed and one left**

- **Guessing the religion:**
  - The Tsardom's mention of its church became a religion sphere stub only after Fix 2. Before it (run 2), it was a lore stub.
  - The owner would have had to pick "Make it a sphere…" and choose religion by hand.
  - In run 1 the Tsardom named no faith at all.
- **Item stubs:**
  - Item stubs the core made (the Dawn Vigil, the Hall of Lanterns) were filled at planning and kept their drawers. The holy site stayed `part_of` Holy Sites after expansion.
  - Elder Marfa, the Sovanie and the Hall were filled the same way.
- **The fault fixed (Fix 3), and what is left:** the Dawn Vigil's fill is covered under "The scene uses the sphere…" below.

### "Part of" works in either order: **pass (child first, on Skyfall); sphere first: pass**

- **Child first:**
  - The council was expanded while the church was a bare stub. It came out `part_of` the church, Unsorted, and the church stayed a stub with 0 facts.
  - Then the church's core:
    - adopted the council into **Hierarchy** (`adopted` = the council, in Hierarchy);
    - wrote the timeline around it (Elder Marfa elected Chair; the Council's first edict);
    - put Archpriests under it ("report to the Council of Elders").
  - **No rival council or synod was invented.** The council was made once (one "Council of Elders" in the world).
- **Sphere first:** stubs the core filed in drawers (the Hall of Lanterns, the Dawn Vigil) kept their drawers when they were expanded later.
- **Not exercised on Skyfall:** a council guessed as an *order sphere* and expanded first. Before this task, `preview_sphere` gave no child-first `part_of` at all; Fix 4 adds it. It is covered by MockClient only. With Fix 2, a council the Tsardom names alongside its church will often be guessed as an order sphere, so this path is live in Task 11.

### Character ties read well: **mostly pass**

- **The tie:** Courier of Church of the Divine Sovanie, since 1016. That fits her: changed in 1014, she joined the courier service at 22.
- **The exception:** "She faithfully observes the Dawn Vigil and all Church rites but privately considers the Doctrine of Transcendence to be unfounded theology rather than divine truth."
  - It rejects the right item: its label maps to **The Doctrine of Transcendence**.
  - The people drawer shows Vasha (courier).
- **Weak points:**
  - **The exception restates what she keeps**, so the sheet line reads "Courier of Church of the Divine Sovanie (since 1016), but: she faithfully observes the Dawn Vigil and all Church rites but privately considers…". It has two "but"s, and the first half isn't a departure.
  - **The exception is also restated in the facts:**
    - a personality fact: "Despite her private skepticism about the Doctrine of Transcendence, she has never missed a single Dawn Vigil…";
    - a second one: "…questions whether the walls are built on solid ground".

    The rule "Write each exception only there, never again as one of the facts" didn't hold. That's 1 of 1 character here; the Task 3 probe saw it in 2 of 4.
  - **Real-world drift:** Veliky Ustyug and Novogorod.
  - **Sample:** one character, one tie, one exception.

### The scene uses the sphere without flooding the context: **partial**

**The sphere's own block holds, once.** It is the church under the lead line, at the 8-line cap (301 words):
- the summary;
- the 2 doctrines;
- the Feast of Saint Ilarion;
- Archpriests;
- the 3 dated timeline lines.

No line of it is repeated anywhere in the block (0 duplicate lines out of 45). Fix 1 is visible in it: the Council of Elders and the Dawn Vigil, pulled in as lore, were left out of the key facts, and the next items took their slots (the Feast of Saint Ilarion, Archpriests).

**The narration used it well, with no recital:**
- **Run 3:**
  - Turn 1 had the Transcendence Prayer, "Grant us passage to the Radiant Threshold", and Vasha saying the words "Not because she believes them… but because twelve years of faithful repetition".
  - Turn 2 had an Elder of the Council: "Do you still say the words?".
- **Run 4:**
  - Turn 1 had the Hall's icon screen of Saint Ilarion, the liturgy, and Vasha's private doubt ("stars do not lean… saying nothing is the architecture of her survival").
  - Turn 2 had Elder Yelisei, "one of the original twelve", asking "do you still keep the faith?".
- No doctrine was quoted. No turn stalled on the church.

**But the whole World block is heavy, and two sphere-made things swell it:**

| Run 3 World block (2124 words, 45 lines) | words | lines |
|---|---|---|
| goal and place (the Hall of Lanterns, filled at planning) | 475 | 11 |
| **The Dawn Vigil** (an item stub, pulled in and filled at planning) | 472 | 13 |
| Council of Elders (pulled in, the goal names it) | 340 | 11 |
| the church's sphere block | 301 | 8 |
| who is here | 536 | 2 |

1. **The Dawn Vigil was written around Vasha (fixed in part, Fix 3).**
   - Its stub's own fact (the core's "A daily morning prayer service…") and its sphere never reached the create prompt. `suggested_prompt` started from mentions only, and the first mention was Vasha's exception. So the prompt was "The Dawn Vigil: She faithfully observes the Dawn Vigil… but privately considers the Doctrine of Transcendence…".
   - **8 of its 13 facts were about Vasha.** It also drifted to a "Church of Ilarion" and "Ilarion, the First Dawn".
   - **After Fix 3 (run 4):** the prompt leads with the stub's own fact and "Part of Church of the Divine Sovanie, under Rites and Ceremonies.". The Vigil now names its church correctly ("one of the primary rites and ceremonies of the Church of the Divine Sovanie"). But **4 of its 13 facts are still about Vasha**: her mentions still come after, and in "Mentioned elsewhere (keep these true)". It also repeats its own fact nearly word for word ("The Dawn Vigil is a daily morning prayer service…" next to "A daily morning prayer service…").
2. **The summary grew after Fill.**
   - The core's summary was 53 words. Accepting Fill on Doctrines kept a statement, and Task 8's rule (decision 2) then regenerated the church's description prose from all its facts. **The summary became 126 words**, retelling statements and the timeline: parish holy sites, clergy training, "All Sovy must live…", Elder Marfa.
   - It is the first key-fact line, so the sphere block's 8 lines are about 300 words instead of about 200. Some of the retold items also show as items, or in the lore.
   - Not changed here: it is a router prose-policy decision, not prompt assembly (see Concerns).
3. **Pulled-in lore shows in full.** The Council (11 facts), and in run 4 the Sovanie (11), are shown whole because the goal and the setup named them. This is the existing lore path, not spheres. Fix 1 keeps them from showing twice.

**Tie lines don't reach narrator prompts.** `progress_story`'s prompt has no character sheets, so Vasha's tie line (on her sheet, in `base_attributes["ties"]`) wasn't in either turn's prompt. Her doubt reached the narrator through the Dawn Vigil's lore facts instead. Ties reach conversation prompts, through the sheet. A conversation turn wasn't part of this probe, since Vasha was the player.

## Fixes made

**After the runs (Task 10 fix round 1, no Skyfall re-run):** rulings P18, P19 and P20 were applied after these runs, so the numbers above are from before them.
- **P18:** a sphere's description prose (its summary) is written without its statements and timeline facts.
- **P19:** `accept_fill` and `add_statement` schedule no prose for a sphere, and neither does an `end_item` `by` sphere's timeline fact.
- **P20:** a nested sphere with its own block is left out of its parent's key facts.

Together, P18 and P19 address the "summary grew after Fill" finding: Fill now leaves the core's summary as it is.

All are in worldplay prompt or context assembly, each with a test written first (RED, then GREEN).

1. **A sphere's item pulled in as lore shows once** (`worldplay/context.py`, `world/spheres.key_facts(skip=…)`).
   - Found by the MockClient end-to-end test: the Council of Elders, named by the goal, showed as lore and again as a Hierarchy key fact.
   - Key facts now leave out thing items shown as lore in the same block, and the next item takes the slot.
   - Task 7's `test_context_touched_sphere_key_facts` pinned the doubled line (the Doctrine of Separation was pulled in, and DAWN_BLOCK listed it too). It now pins the plain case, and `test_pulled_in_item_shows_once` covers the other.
   - Seen working in runs 3 and 4.
2. **The create prompt's names rule** (`world/create-thing.jinja2`): faiths, orders, academies, guilds, councils, cultures and fields are `"sphere"` with a `"template"`.
   - This is the sphere core's wording (probe-mandated by Task 3, and used by Fill and the branch prompt too), plus one extension: the core's closing "(a country or realm is a place; a rank or office is lore)" goes on with "; so is any other group or faction, and a law, code, script or language", carrying over what the old create-thing line said about those.
   - It replaces "culture … lore (a group, order or faction is lore; …)". "Any other group or faction" stays lore.
   - Evidence:
     - run 2: the state church came back as `lore`;
     - run 3: with the new rule, "Church of the Divine Sovanie" came back `sphere`/`religion`.
   - Task 4 had flagged this gap (its concern 9), and no task changed it. This line was Connections' wording, not one of Tasks 4, 6 or 7's probe-mandated texts. `create-mix.jinja2` still has the old line (unprobed; mixes rarely name groups).
   - Test: `test_create_prompt_names_faiths_and_orders_as_spheres`.
3. **A stub's suggested prompt leads with its own facts and its sphere** (`worldplay/mentions.suggested_prompt`): "<name>: <own facts> Part of <sphere>, under <drawer>. <mentions…>".
   - An item stub the core made carries its text as a fact. Before this, that fact never reached the create prompt (see "The Dawn Vigil" above).
   - Effect (run 3 → run 4):
     - the Vigil's facts about Vasha went from 8 of 13 to 4 of 13;
     - the church drift went away.
   - Stubs with no facts and no sphere (the Tsardom, the council, the church) get the same prompt as before.
   - Test: `test_suggested_prompt_of_a_sphere_item_stub`.
4. **Child-first `part_of` for a sphere stub** (`worldplay/spheres.preview_sphere`, `accept_sphere`).
   - A stub expanded as a sphere now joins the sphere it belongs in, as `preview_thing` already did: its mentions are all inside one sphere's items, or its prompt names a sphere stub.
   - A new guard, `create._sits_in`, refuses a link into a sphere that sits inside the stub, so there's no cycle when the parent is expanded after its child.
   - A branch (with a `parent`) never gets one.
   - Test: `test_child_first_sphere_stub_gets_part_of`. It covers the council as an order stub, then the church's core adopting it, with no cycle.

## Recommendations for Task 11 and later

- **Watch in the owner's run:**
  - a council the Tsardom names, now likely guessed as an order sphere and expanded first (Fix 4's path, MockClient only so far);
  - whether the Border Watch-style guesses (corps and guards as orders) are welcome.
- **The summary after Fill:** either `accept_fill` schedules no prose for a sphere (the core's summary stays, ruling P1), or a sphere's description prose leaves out `statement` and `timeline` facts. Today, one statement kept turns a 53-word summary into a 126-word retelling, which leads every scene's sphere block.
- **A character's facts in a rite's fill:** a stub filled at planning gets a character's tie facts as "Mentioned elsewhere (keep these true)", and writes them into the rite (4 of 13 facts after Fix 3). This is Connections' mention context. Leaving `ties`-category facts out of a non-character's mentions would cut part of it; the personality fact restating the exception would remain.
- **Exceptions:**
  - The `ties` rule could say the text is only the departure ("what they reject or do differently", not what they keep).
  - The "never again as one of the facts" line didn't hold here (1 of 1).
- **Tie lines in narration:** `progress_story` doesn't carry character sheets. If the owner wants ties in narration, the World block could carry the present characters' tie lines. That needs a probe first.
