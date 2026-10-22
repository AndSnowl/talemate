# Curation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every fact gets one home. Generation sends facts about other entries to those entries, code flags repeats, near-duplicate entries are caught or merged, a more specific entry draws facts in from a broader one, every dated fact shows on a timeline, beliefs are marked as held, gods get a kind, and what is "near" an entry is computed from its links, with knobs.

**Architecture:**
- **Pure layer.** New modules in `src/talemate/world/` handle the measurable parts with no model calls:
  - nearness (`nearness.py`);
  - repeats and dates that disagree (`repeats.py`);
  - same-thing candidates (`sameness.py`);
  - entry timelines (`timelines.py`);
  - held-by (in `spheres.py`).
- **Model-facing layer.** `worldplay/` adds the reply parts (elsewhere, held-by, outer body, moving in, contradictions) to the existing preview flows. The wording comes from Task 3's probes.
- **Merge.** It generalises Re-point (`worldplay/repoint.py`) from stubs to full entries.
- **Frontend.** It gets the approved preview sections, a merge screen, a timeline on every page, and per-fact Move to… and Held by….

**Tech stack:** Python 3.11, SQLite (the world store), pydantic 2, Jinja2 through `Prompt.request`, Vue 3 + Vuetify, Pinia, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-22-fantasymate-curation-design.md` (36d6286c). It builds on the Spheres spec and the rulings P1–P23 and R1 in `.superpowers/sdd/2026-10-22-fantasymate-spheres/progress.md`. The evidence is `docs/superpowers/probes/2026-10-22-fact-placement.md`.

## Global Constraints

- **Branch:** work on `feature/spheres` in `.worktrees/spheres`. The plain-suite baseline is 7244 passed, 6 skipped, and it stays at **0 failed**.
- **Guix:** everything runs through `guix shell -m manifest.scm -- …` with `uv run --no-sync`.
- **Browser tests:** run them once at the end of a UI task with `pytest tests/e2e -m e2e -n 4`. Never use more than 4 workers, and check for orphaned apps first. While iterating, run only `tests/e2e/worlds`. Grep `tests/ai` for any changed UI ids.
- **Probes:**
  - Skyfall probes need the owner's go-ahead. Ask before Task 3 and Task 13.
  - Model calls run one at a time at `http://192.168.0.5:5001`.
  - Plain tests use `MockClient` only.
  - Hand labels are committed before any model call.
  - Raw output goes under `docs/superpowers/probes/raw/`.
- **`src/talemate/world/`** stays strict-mypy clean, with no imports from the rest of talemate.
- **World AI calls** go through `worldplay.ai.world_ai_call()`. They are parsed with `create.json_objects`. No raw `[[thing:…]]` text may appear in a prompt or a page.
- **No extra model calls** on ordinary turns or while typing. The only calls added to an accept are the same-thing verdict (at most one per preview, and only when both sides have facts) and the merge's contradiction check.
- **Multi-write actions** (accept, merge, move, re-file) are one revision each, so one undo reverses them.
- **Moving a fact between entries** copies it with a new id and removes the original in the same revision (ruling R1). Overrides that point at the old id are re-pointed to the copy.
- **Nothing is moved, merged or dropped without the owner's tick.** Repeats arrive unticked, never deleted.
- **Probe-mandated wording** from the Spheres probes (a)–(d) and from Task 3 changes only with new probe evidence.
- **Values from the spec:**
  - repeat threshold 0.4 (a world setting);
  - at most 5 same-thing candidates per preview;
  - probe pass bar of at least 80% right and at most 5% false moves or flags;
  - the "how far out" setting runs from 1 to 3 steps;
  - nearness target is under 50 ms per prompt at 1,000 entries.
- **Held-by** applies implicitly only to the beliefs drawers of the `religion` and `culture` templates.
- **The `being` kind** has an `existence` setting of `real`, `believed` or `undecided`. Only `real` beings can be cast in scenes.

## Review Focus

1. **A moved, merged or elsewhere fact keeps its dates, overrides and held-by after undo and redo.** Owned by Tasks 5, 8 and 9 (a redo test in each).
2. **A world with no links:** a fresh world, or an entry with no references. Nearness, timelines and the candidate lists must return nothing, never fail. Owned by Tasks 1 and 10 (`test_isolated_entry`).
3. **An elsewhere fact whose target is deleted between preview and accept** is dropped with a note, and the accept still succeeds. Owned by Task 5 (`test_elsewhere_target_deleted_before_accept`).
4. **Two candidates with the same name** (two "Moskov"s, or a stub and a full entry): the owner sees which is which, with kind and summary. Owned by Task 6 (`test_same_name_candidates_are_told_apart`).
5. **A held fact edited by the owner keeps its held-by,** and clearing it works. Owned by Task 4 (`test_correct_keeps_held_by`, `test_clear_held_by`).

---

### Task 1: Nearness

**Files:**
- Create: `src/talemate/world/nearness.py`, `scripts/dev/nearness_bench.py`
- Modify: `src/talemate/world/store.py` (a settings accessor on `World`)
- Test: `tests/world/test_nearness.py`

**Interfaces:**
- Produces:
  - `class Near(BaseModel)` with fields `thing_id: str`, `score: float` and `steps: int`.
  - `near(view: WorldView, thing_id: str, *, reach: int = 2, limit: int = 20) -> list[Near]`:
    - returns live things, excluding `thing_id`, ordered by score descending and then by name;
    - a step is any of: a fact reference in either direction, `part_of` in either direction, a place `parent` or child, a tie (character ↔ sphere), or a heritage field (`heritage`, `species`, `parents`);
    - the score of a path is the product of its links' weights, and each thing keeps its best path;
    - *starting weights* (the builder may tune them, but must say so): `part_of` 1.0, parent/child 1.0, tie 0.8, a reference 0.6, heritage 0.5.
  - `CurationSettings(BaseModel)`:
    - `reach: int = 2` (1–3);
    - `entries: int = 12`;
    - `facts_per_entry: int = 6`;
    - `repeat_threshold: float = 0.4`;
    - `timeline_reach: int = 2`.
  - `World.curation() -> CurationSettings` and `World.set_curation(s: CurationSettings) -> None`, stored in the `meta` table under key `curation`.
- [ ] **Step 1: Write the failing tests:**
  - `test_near_follows_links_both_ways`
  - `test_near_scores_part_of_above_reference`
  - `test_near_respects_reach_and_limit`
  - `test_isolated_entry` (returns `[]`)
  - `test_deleted_things_never_near`
  - `test_curation_settings_round_trip`
- [ ] **Step 2: Run** `pytest tests/world/test_nearness.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** with set-based SQL over `fact_refs` and `field_values` at the view's revision and date, then a best-first walk in Python. Write `scripts/dev/nearness_bench.py`, which builds synthetic worlds of 1,000 and 3,000 things (about 8 facts and 3 refs each, with part_of trees) and times `near()` with the default knobs. This is the spec's probe 6.
- [ ] **Step 4: Run the bench.**
  - Record the timings in `docs/superpowers/probes/<run-date>-nearness-cost.md`.
  - If 1,000 entries take more than 50 ms, add a stored adjacency table and maintain it inside revisions, with a test that undo keeps it in step. Record the choice.
  - Then run `pytest tests/world -q`, mypy on `src/talemate/world`, and the full plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(world): nearness from links, with curation settings`.

### Task 2: Repeats, dates that disagree, same-thing candidates

**Files:**
- Create: `src/talemate/world/repeats.py`, `src/talemate/world/sameness.py`
- Test: `tests/world/test_repeats.py`, `tests/world/test_sameness.py`

**Interfaces:**
- Consumes: Task 1 (`near`).
- Produces:
  - `content_words(text: str) -> set[str]`: lowercased words, with stop-words and words of 2 letters or fewer dropped. The stop list lives in `repeats.py`.
  - `overlap(a: str, b: str) -> float`: the probe's measure, `|A∩B| / min(|A|,|B|)` over content words (see the probe doc's "Code instead of model" section, and keep it identical to that).
  - `class Repeat(BaseModel)`: `index: int`, `fact_id: str`, `owner_id: str`, `score: float`.
  - `find_repeats(view, texts: list[str], owner_ids: list[str], threshold: float) -> list[Repeat]`: for each text, the best match among the live facts of `owner_ids` at or above `threshold`.
  - `class Disagreement(BaseModel)`: `a: str`, `b: str` (fact ids), `years: tuple[int, int]`.
  - `disagreeing_dates(view, fact_ids: list[str], threshold: float) -> list[Disagreement]`: pairs of dated facts with overlap at or above `threshold` and different start years.
  - `class SameCandidate(BaseModel)`: `thing_id: str`, `reason: Literal["word","inside","aka"]`, `score: float`.
  - `same_candidates(view, name: str, *, near_ids: Sequence[str], limit: int = 5) -> list[SameCandidate]`:
    - candidates are things that share a name word, contain the name, are contained in it, or have a matching other name;
    - search near things first, plus things anywhere that match by name;
    - common words never count as a shared word: articles and words used in more than 5% of the world's names (so "Tsar" doesn't match everything).
- [ ] **Step 1: Write the failing tests,** using the probe's own pairs as fixtures:
  - `test_overlap_matches_probe_measure`: the 947 rediscovery restatements score ≥ 0.4; a clean fact scores < 0.4.
  - `test_find_repeats_picks_best_owner`
  - `test_disagreeing_dates_codex_217_vs_312`
  - `test_same_candidates_ashenmere_caves`
  - `test_same_candidates_conclave_inside_runeweavers_conclave`
  - `test_common_word_not_a_candidate`
  - `test_same_name_candidates_are_told_apart`: two "Moskov"s both returned, distinguishable by id and kind.
  - `test_no_candidates_in_empty_world`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/world -q`, mypy, and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(world): repeats, disagreeing dates and same-thing candidates in code`.

### Task 3: Probes 1–5 on Skyfall (owner-gated)

**Files:**
- Create:
  - `scripts/dev/probe_curation.py`
  - `docs/superpowers/probes/<run-date>-curation.md`
  - `docs/superpowers/probes/raw/<run-date>-curation.json`
  - `docs/superpowers/probes/raw/<run-date>-curation-labels.json`

**Interfaces:**
- Consumes: Tasks 1 and 2. It uses the copy of the owner's acceptance world at the scratchpad path `acceptance-snapshot/world`, and the harness from `scripts/dev/probe_fact_placement.py`.
- Produces: the findings doc. For each probe it gives the exact prompt wording to use (as Jinja blocks with named variables), the reply shape, the scores against the pass bar (at least 80% right, at most 5% false), and PASS or FALLBACK. Tasks 4–9 copy this wording verbatim.
  1. **Elsewhere with nearness candidates.**
     - Covers `create-thing.jinja2`, the sphere core and Fill.
     - Candidates come from `near()` at reach 1, 2 and 3. The reply gains `"elsewhere": [{"entry": "<name>", "text": "...", "held_by": "<name>"|null}]`.
     - Score how many facts end up on topic and the prompt size.
     - Recommend default knobs.
  2. **Moving in.** Given a new entry that is part of a broader one, pick which of the broader entry's facts belong on the new one.
  3. **Contradictions.** For a merge pair, find the facts that disagree, without flagging facts that only differ.
  4. **Held by.** Mark facts that are beliefs of a named entry (the Church and its god), without marking world facts.
  5. **The outer body.**
     - From "regiments such as the White Talon", propose `{"name","kind","template","part_of":{"entry","drawer"}}` for the inner part and for a new outer body, chained to the Tsardom.
     - Also test the same-thing verdict on a new entry's preview facts against an existing entry with facts.
- [ ] **Step 1: Ask the owner for the go-ahead.**
- [ ] **Step 2: Hand-label the cases and commit the labels** before any model call.
- [ ] **Step 3: Run each probe twice, at the app's temperatures.** Write the JSON after every call.
- [ ] **Step 4: Write the findings doc.** A probe that misses the bar says FALLBACK and names the fallback from the spec's "Pass bars and fallbacks".
- [ ] **Step 5: Commit**: `docs(probe): curation wording on Skyfall`.

### Task 4: Held by, and the being kind

**Files:**
- Modify:
  - `src/talemate/world/kinds.py` (the `being` kind);
  - `src/talemate/world/spheres.py` (`held_by`);
  - `src/talemate/worldplay/context.py` and `worldplay/characters.py` (scene rendering);
  - `src/talemate/worldplay/setup.py` (real beings can be cast);
  - `src/talemate/worldplay/create.py` (`CREATE_KINDS`/`NAME_KINDS` gain `being`; the reply's `held_by` per fact).
- Test: `tests/world/test_held_by.py`, `tests/worldplay/test_beings.py`

**Interfaces:**
- Consumes: Task 3 probe 4's wording, or its fallback (hand tagging only).
- Produces:
  - **Storage:** held-by is stored as fact origin `{"held_by": <thing_id>}`. It survives correction because the store copies `origin_json`.
  - **`held_by(view, fact: FactState, owner: ThingState) -> str | None`:**
    - returns the explicit origin holder;
    - otherwise, for a `statement` in a beliefs drawer of a `religion` or `culture` sphere, returns that sphere;
    - otherwise returns None.
  - **The `being` kind:**
    - `KindSpec(name="being", fields=[name text, existence text, born date], categories=["nature","deeds","worship","general"])`;
    - `existence` must be one of `real`, `believed` or `undecided`; the default is `undecided`;
    - name guesses of `god`, `spirit`, `deity` and `being` map to `being`.
  - **Scene context:** a held fact renders as "<Holder> holds that <text>". A being that isn't `real` is never cast, and its facts reach a scene only through the context of whatever refers to it.
  - **`PreviewFact.held_by: str | None`** (a thing id), parsed from the reply's per-fact `held_by` name.
- [ ] **Step 1: Write the failing tests:**
  - `test_held_by_origin`
  - `test_religion_beliefs_statement_is_held`
  - `test_nation_laws_not_held`
  - `test_doctrine_entry_not_held_implicitly`
  - `test_correct_keeps_held_by`
  - `test_clear_held_by`
  - `test_held_fact_renders_as_belief_in_scene`
  - `test_being_existence_values`
  - `test_believed_being_never_cast`
  - `test_real_being_castable`
  - `test_create_reply_held_by_maps_to_thing`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/world tests/worldplay -q`, mypy, and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(world): held-by facts and the being kind`.

### Task 5: Elsewhere facts and repeats in previews

**Files:**
- Modify:
  - `src/talemate/worldplay/create.py` (`CreatePreview`, `preview_thing`, `accept_preview`/`_write_preview`, context through `near`);
  - `src/talemate/worldplay/spheres.py` (`preview_sphere`, `fill_drawer`, `accept_sphere`, `accept_fill`);
  - the templates `world/create-thing.jinja2`, `world/sphere-core.jinja2` and `world/sphere-fill.jinja2`, with Task 3 probe 1's wording.
- Test: `tests/worldplay/test_curation_preview.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - **`class ElsewhereFact(BaseModel)`:**
    - `target_id: str | None` (an existing thing);
    - `target_name: str`;
    - `new: NewName | None` (a stub to make, with its `kind`, `template` and `part_of` from Task 7);
    - `category: str`;
    - `text: str`;
    - `since: WorldDate | None`;
    - `held_by: str | None`;
    - `ticked: bool = True`.
  - **`PreviewFact`** gains `repeat_of: dict | None` (`{fact_id, owner_id, owner_name}`) and `ticked: bool = True`. A repeat starts unticked.
  - **`CreatePreview`** gains `elsewhere: list[ElsewhereFact]`.
  - **Fill items** gain `repeat_of`, `ticked` and `elsewhere`. The return shape becomes `FillPreview(items, elsewhere)`; update the router in Task 11.
  - **`default_category(kind: str, dated: bool) -> str`:** sphere gives `about`, or `timeline` when dated; place gives `general`, or `history` when dated; every other kind gives `general`. It never returns a category that heritage passes down.
  - **The candidate list** comes from `near(view, focus, reach=settings.reach, limit=settings.entries)`. The focus is the stub, the prompt's named things, or the sphere. Today's context (named in the prompt, mentions) stays first.
  - **Accept:**
    - writes only ticked own facts;
    - writes each ticked elsewhere fact to its target with `default_category` (or the owner's choice), `since` and `held_by`;
    - makes `new` stubs;
    - does all of this in the existing revision;
    - drops an elsewhere fact whose target was deleted, and adds a note to the result.
- [ ] **Step 1: Write the failing tests,** with MockClient replies taken from Task 3's raw output:
  - `test_elsewhere_facts_parsed_and_grouped`
  - `test_accept_writes_elsewhere_to_targets_one_revision`
  - `test_elsewhere_new_target_makes_stub`
  - `test_repeat_starts_unticked_and_is_not_written`
  - `test_ticked_repeat_is_written`
  - `test_default_category_never_heritage`
  - `test_elsewhere_target_deleted_before_accept`
  - `test_fill_elsewhere_and_repeats`
  - `test_candidates_come_from_nearness`
  - `test_undo_then_redo_elsewhere_accept`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`, then the plain suite. Expected: 0 failed. Grep `tests/ai` for the template wording you changed.
- [ ] **Step 5: Commit**: `feat(worldplay): elsewhere facts and repeats in create and Fill previews`.

### Task 6: Same thing? before anything new

**Files:**
- Modify: `src/talemate/worldplay/create.py`, `src/talemate/worldplay/spheres.py` (promotion links Sites lines to existing places)
- Create: `src/talemate/worldplay/sameness.py` (the model verdict)
- Test: `tests/worldplay/test_same_thing.py`

**Interfaces:**
- Consumes: Task 2 (`same_candidates`), plus Task 3 probe 5's verdict wording, or the fallback (owner only).
- Produces:
  - **`CreatePreview.same_as: list[SameCandidate]`** for the entry being created, plus a `verdict: dict[str, Literal["same","part","different"]] | None` from one model call. The call is made only when the top candidate and the preview both have facts.
  - **`NewName.same_as: list[SameCandidate]`** for each new stub. There is no model call for these, and the default is new.
  - **Accept with `same_target_id`:**
    - no new thing is written;
    - the preview's ticked facts become additions to the target;
    - the preview name becomes a `common` aka on the target;
    - a stub row marked same is linked to that thing, not created.
  - **Promotion:** a Sites line whose name matches an existing place links to it and files it, instead of becoming a statement.
- [ ] **Step 1: Write the failing tests:**
  - `test_preview_offers_same_candidate_with_verdict`
  - `test_no_verdict_call_when_candidate_bare_stub`
  - `test_accept_into_same_target_adds_facts_and_aka`
  - `test_stub_row_same_links_existing`
  - `test_promotion_links_existing_capital`
  - `test_at_most_five_candidates`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay -q`, then the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): same thing? before a new entry or stub`.

### Task 7: Bodies within bodies

**Files:**
- Modify:
  - `src/talemate/worldplay/create.py` (the chain in elsewhere `new`);
  - `src/talemate/world/kinds.py` (the tie gains an optional `within`);
  - `src/talemate/world/spheres.py` (people and `ties_of` read `within`);
  - `src/talemate/worldplay/characters.py` (the tie line gains "within <item>").
- Test: `tests/worldplay/test_bodies.py`

**Interfaces:**
- Consumes: Task 5 (`ElsewhereFact.new`), plus Task 3 probe 5's chain shape, or the fallback (the owner names the outer body).
- Produces:
  - **`NewName.part_of: {"name": str, "drawer": str} | None`:** a new stub can point at another new stub or at an existing sphere. On accept the chain is made in order, outer first.
  - **`CreatePreview.refile: list[{thing_id, from: part_of, to: part_of, ticked}]`:** when an outer body is proposed and existing items that are its siblings are filed in the target's drawer (the White Talon and the Frosted Wing in the Military drawer), they are offered to move into the outer body's drawer. Accept files them with `part_of_since`.
  - **The tie** gains `within: str | None`, an item thing id of that sphere, validated as live and part of it.
  - **The tie line** reads: "Trooper in the Tsar's Army, within the White Talon (since 1012)".
- [ ] **Step 1: Write the failing tests:**
  - `test_inner_part_proposes_outer_chain`
  - `test_chain_made_outer_first_on_accept`
  - `test_siblings_refiled_into_outer_body`
  - `test_tie_within_item`
  - `test_tie_within_must_be_part_of_sphere`
  - `test_tie_line_reads_within`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/world tests/worldplay -q`, mypy, and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): bodies within bodies, re-filing, and ties within a part`.

### Task 8: Facts move in to a more specific entry

**Files:**
- Modify: `src/talemate/worldplay/create.py`, plus a template block from Task 3 probe 2
- Test: `tests/worldplay/test_move_in.py`

**Interfaces:**
- Consumes: Task 3 probe 2's wording, or the fallback (all the broader entry's facts listed, unticked).
- Produces:
  - **`CreatePreview.move_in: list[{fact_id, from_id, text, ticked}]`:** offered when the new entry has `part_of` or a `parent`. It covers only the broader entry's own facts, picked in the same create call (no extra call). With the fallback, every fact is listed unticked.
  - **Accept:** each ticked fact is copied to the new entry with a new id, keeping its dates, origin and held-by. The original is removed, and its overrides are re-pointed (R1). This happens in the accept revision.
  - **`move_fact(world, fact_id, target_id) -> str`:** the same copy-and-remove for a single fact. It is used by the fact row's "Move to…" in Task 11.
- [ ] **Step 1: Write the failing tests:**
  - `test_move_in_offered_for_part_of_new_entry`
  - `test_move_in_copies_and_removes`
  - `test_move_in_keeps_dates_origin_held_by`
  - `test_move_in_repoints_overrides`
  - `test_move_fact_single`
  - `test_undo_redo_move_in`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Share the copy-and-remove helper with `repoint.py`'s `_move_facts`, which should become a public `copy_facts(rev, view, fact_ids, target_id, *, plain_self_links) -> dict[str, str]` in `worldplay/repoint.py`.
- [ ] **Step 4: Run** `pytest tests/worldplay tests/world -q`, then the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): facts move in to a more specific entry; move one fact`.

### Task 9: Merge

**Files:**
- Create: `src/talemate/worldplay/merge.py`, plus a template block from Task 3 probe 3
- Modify: `src/talemate/worldplay/repoint.py` (the shared mover)
- Test: `tests/worldplay/test_merge.py`

**Interfaces:**
- Consumes: Task 2 (`find_repeats`), Task 8 (`copy_facts`), Task 3 probe 3, or the fallback (high-overlap pairs, no model).
- Produces:
  - **`class MergePreview(BaseModel)`:**
    - `from_id`, `into_id`;
    - `names: list[str]`, which the owner picks the main name from;
    - `facts: list[{fact_id, text, repeat_of, ticked}]`;
    - `pairs: list[{a: fact_id, b: fact_id}]`;
    - `moves: dict` (counts of links, filings, ties, fields).
  - **`async preview_merge(world, from_id, into_id, client) -> MergePreview`**, which makes one model call for the pairs.
  - **`accept_merge(world, preview, *, main_name: str, keep: dict[str, Literal["a","b","both"]]) -> RepointResult`.** In one revision it:
    - moves the ticked facts with `copy_facts`;
    - ends or removes the losing side of each pair, as the owner chose;
    - rewrites every reference, field, part_of and tie through `repoint.py`'s rewriter, generalised from a stub to any thing;
    - sets the main name, with the other becoming a `common` aka;
    - removes `from_id`.
  - **Refusals:** the same as `repoint_stub`'s, checked before writing, plus merging a thing into itself.
- [ ] **Step 1: Write the failing tests:**
  - `test_merge_preview_names_facts_pairs`
  - `test_merge_moves_links_and_fields`
  - `test_merge_main_name_choice_other_becomes_aka`
  - `test_merge_pair_keep_choices`
  - `test_merge_repeats_unticked`
  - `test_merge_refusals_write_nothing`
  - `test_undo_redo_merge`
  - `test_repoint_stub_unchanged`, so the old tests keep passing.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/worldplay tests/server -q`, then the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worldplay): merge one entry into another`.

### Task 10: Every dated fact on a timeline

**Files:**
- Create: `src/talemate/world/timelines.py`
- Modify: `src/talemate/worldplay/spheres.py` (`_timeline_lines` and key facts read from it), `src/talemate/worldplay/context.py`
- Test: `tests/world/test_timelines.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces:
  - **`class TimelineLine(BaseModel)`:** `fact_id`, `owner_id`, `date: WorldDate`, `text`, `here: bool`, `disagrees_with: list[str]`.
  - **`entry_timeline(view, thing_id, *, reach: int, threshold: float) -> list[TimelineLine]`**, in date order:
    - the entry's own dated facts (any `valid_from`, plus `timeline` facts);
    - for a sphere, also:
      - the dated facts of its parts (`part_of` descendants, and the place tree for a place sphere) up to `reach` steps;
      - any dated fact that references it or one of those parts;
      - tied characters' dated facts that reference it.
    - mere nearness never adds a line.
  - **`disagrees_with`** comes from `disagreeing_dates` and is computed on read. Nothing is stored.
  - **`spheres.timeline`** stays for its current callers, or is replaced by this. The builder decides and lists the callers.
  - **Scene context** (spec goal 10): `world_context_block` keeps today's rules first (the scene's place, what's named, members present, touched spheres). It then adds the top `near()` entries of the scene's place and cast as lore lines, within `settings.entries` and `settings.facts_per_entry`. Two rules from the spheres probe (d) still hold: its block wording is unchanged, and an entry shown once is never shown again.
  - **Tests:** `test_scene_context_adds_near_lore_within_knobs` and `test_scene_context_unchanged_when_no_links`.
- [ ] **Step 1: Write the failing tests:**
  - `test_own_dated_facts_in_order`
  - `test_sphere_gathers_from_parts_947`
  - `test_reference_from_outside_counts`
  - `test_member_births_not_gathered`
  - `test_mention_only_neighbour_not_gathered`
  - `test_reach_limits_depth`
  - `test_codex_dates_disagree`
  - `test_isolated_entry`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/world tests/worldplay -q`, mypy, and the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(world): a timeline for every entry, gathered for spheres`.

### Task 11: Router

**Files:**
- Modify: `src/talemate/server/worlds.py`
- Test: `tests/server/test_worlds_plugin.py`

**Interfaces:**
- Consumes: Tasks 4–10.
- Produces:
  - **The preview payloads** carry `elsewhere`, `repeat_of`/`ticked`, `same_as`/`verdict`, `refile`, `move_in` and `held_by`. `accept_preview`, `accept_sphere` and `accept_fill` accept the owner's edits to all of these.
  - **The thing payload** gains:
    - `timeline: [{fact_id, owner_id, owner_name, date, segments, here, disagrees_with}]` for every kind;
    - per-fact `held_by: {id, name} | null`.
  - **New actions:**
    - `set_held_by {thing_id, fact_id, holder_id|null}`
    - `move_fact {fact_id, target_id}`
    - `preview_merge {from_id, into_id}`
    - `accept_merge {preview, main_name, keep}`
    - `get_curation`
    - `set_curation {settings}`
    - `pick_date {keep_fact_id, drop_fact_id, mode: "end"|"remove"}`
  - **Prose** follows the existing rule: it is scheduled only when its rendered input changes.
- [ ] **Step 1: Write the failing tests:** one per action, plus `test_payload_timeline_every_kind` and `test_preview_payload_curation_fields`.
- [ ] **Step 2: Run** `pytest tests/server/test_worlds_plugin.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Add a fixed-reply hook for `preview_merge` (`TALEMATE_TEST_FIXED_SPHERE` gains a `merge` key) and extend the preview hooks, so the browser tests stay model-free.
- [ ] **Step 4: Run** the plain suite. Expected: 0 failed.
- [ ] **Step 5: Commit**: `feat(worlds): curation actions and payloads`.

### Task 12: Frontend

**Files:**
- Create in `talemate_frontend/src/components/worlds/`: `PreviewElsewhere.vue`, `PreviewRepeats.vue`, `SameThingAsk.vue`, `MoveInSection.vue`, `MergeDialog.vue`, `EntryTimeline.vue`, `CurationSettings.vue`
- Modify:
  - `CreateBox.vue`, `SpherePreviewCard.vue`, `FillPreview.vue`, `ThingPage.vue`;
  - `SphereTimeline.vue` (replaced by `EntryTimeline`, or wrapping it);
  - `ThingFactForm.vue` and the fact row (Move to…, Held by…);
  - `stores/worlds.js`, `worldKinds.js` (the `being` kind and existence).
- Test: `tests/e2e/worlds/test_curation.py`, `talemate_frontend/checks/worlds.check.mjs`

**Interfaces:**
- Consumes: Task 11.
- Produces: the approved mockup (`.superpowers/brainstorm/18418-1792707061/content/curation-preview.html`, copied to `.superpowers/sdd/2026-10-22-fantasymate-curation/mockup-curation.html`). It covers:
  - **the preview's sections:**
    - its facts, with held-by tags;
    - "Already in the world", unticked, which starts collapsed when everything in it is unticked;
    - "Belongs on other entries", grouped, with a category picker and "untick all";
    - the same-thing question at the top, and a "same as X?" choice on stub rows;
    - "Move here from where they are now";
    - re-file rows;
    - an Accept line that counts what will be written.
  - **The merge dialog**, opened from "Merge into…" on any entry.
  - **A Timeline section on every page,** showing where each line is from and flagging disagreements, with a pick-one action.
  - **Fact rows** gain "Move to…" and "Held by…".
  - **A being page** with an existence picker.
  - **Curation settings** in the World tab's settings.
  - **Test ids:**
    - `preview-elsewhere`
    - `preview-repeats`
    - `same-thing`
    - `move-in`
    - `merge-dialog`
    - `entry-timeline`
    - `fact-move`
    - `fact-held-by`
    - `curation-settings`
- [ ] **Step 1: Write the failing browser tests,** using fixed fixtures:
  - `test_preview_sections_and_accept_counts`
  - `test_same_thing_fill_existing`
  - `test_move_in_on_part_of_entry`
  - `test_merge_dialog_names_pairs`
  - `test_timeline_gathers_and_flags`
  - `test_move_fact_and_held_by`
  - `test_being_existence`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full browser suite (`-n 4`), the node checks, `vite build` and the `tests/ai` grep. Expected: PASS.
- [ ] **Step 5: Commit**: `feat(worlds): curation in previews, merge, timelines and fact rows`.

### Task 13: End to end, and a Skyfall session (owner-gated)

**Files:**
- Create: `tests/worldplay/test_curation_end_to_end.py`, `scripts/dev/probe_curation_flow.py`, `docs/superpowers/probes/<run-date>-curation-flow.md` and its raw JSON.

- [ ] **Step 1: Write the MockClient end-to-end test** through the router. It covers:
  - the Tsardom;
  - the church, whose Divine Right sends Moskov, army and law facts elsewhere;
  - the army chain from "regiments such as the White Talon";
  - Ashenmere, with the Caves caught as the same thing;
  - Runeweaving's timeline gathering the 947 event;
  - a merge;
  - a held fact in a scene.
- [ ] **Step 2: Run it,** then the plain suite. Expected: 0 failed.
- [ ] **Step 3: Ask the owner, then run the session on Skyfall.** Score:
  - facts on topic, against hand labels;
  - repeats;
  - duplicate entries;
  - the timeline.

  Compare with the 2026-10-22 acceptance world, using the same counts. Fix prompt assembly with tests if needed.
- [ ] **Step 4: Commit**: `test(worldplay): curation end to end; docs(probe): curation in a real session`.

### Task 14: The owner's acceptance run (owner-gated)

Start the isolated app on a fresh root with `--ai --lan`, and give the owner the URL. The owner runs the spec's session and judges it by "facts landing in the right places, less duplicates, more cohesive". Fix hiccups with root-caused, tested and reviewed fixes. Record the results in `docs/superpowers/probes/<run-date>-curation-acceptance.md`.
