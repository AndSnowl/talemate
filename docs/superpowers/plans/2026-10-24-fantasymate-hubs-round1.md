# Hubs Round 1 Fixes: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task by task.

**Goal:** fix the pressing items from the owner's first hubs acceptance round (P1–P9), so the Filing work can go to main.

**Architecture:** these are small changes to the existing Filing code: `world/filing.py`, `worldplay/create.py`, `repoint.py`, `links.py`, `server/worlds.py` and the worlds components. There is no new subsystem.

**Spec:** docs/superpowers/specs/2026-10-23-fantasymate-filing-design.md, together with the owner's round-1 decisions in ~/Projects/Web/talemate/feedback/2026-10-24-hubs1/triage.md (the binding text for P1–P9). Context comes from feedback.txt and world-review.md in the same folder.

## Global Constraints
- The same constraints as the Filing plan apply: .superpowers/sdd/2026-10-23-fantasymate-filing/global-constraints.md, including the controller rulings.
- The plain suite stays at 0 failed.
- The browser suite runs with at most `-n 4`, once per UI task.
- No model calls.
- Grep `tests/ai` for any changed wording or test id.
- Fresh worlds only. A filing written before this change, with no `show_under`, reads as "use the entry's tag".

## Review Focus
- An existing filing without `show_under` must group exactly as today.
- A `show_under` tag is normalised like any tag (`normalise_tag`), and rename_tag and merge_tag must reach it.
- Scrubbing `*emphasis*` must never touch a `[[thing:…|…]]` link, an asterisk in a name, or scene text.
- A dead link (to a deleted thing) must render, select and re-link as plain text, and undo must bring the live link back.
- The tree must stay cycle-safe whatever the filings are.

---

### Task 1: P1, "show under" and the role picker

**Files:** `src/talemate/world/filing.py`, `kinds.py` (filing shape), `server/worlds.py`, `EntryIn.vue`, `ConnectedGroup.vue`/`EntryConnected.vue`, `stores/worlds.js`, and tests.

**Interfaces:**
- `Filing` gains `show_under: str | None`, a tag-pool value, normalised on write.
- `connected()` groups a row by `filing.show_under or entry tag`.
- `tags_in_use` counts `show_under` values.
- `rename_tag` and `merge_tag` rewrite `show_under` too.
- A new `roles_in_use(view) -> list[tuple[str, int]]` and a router action `list_roles`.
- `add_filing` and `edit_filing` accept `show_under`.
- On the In row, the role field offers the roles in use, and a "shows under" chip uses the tag picker.
- The character sheet line and the In row read "<Role> of <Target>". This line format already exists, so check it, and make the In row's role field hint at "native, member, branch of…".

**Tests:**
- `test_show_under_groups_row`
- `test_show_under_absent_groups_by_tag`
- `test_rename_tag_reaches_show_under`
- `test_roles_in_use_counts`
- e2e `test_file_with_show_under_and_role_picker`

### Task 2: P2 and P3, emphasis scrub and tags for untagged entries

**P2.** Strip markdown emphasis (`*x*`, `**x**`, `_x_`) from fact text on every fact write path: create accept, elsewhere, add_facts, group add and hand edits. Do it before name detection, so the names inside become detectable stubs. Never strip inside `[[thing:…]]`. Scene and narration text is untouched. Tests:
- `test_emphasis_scrubbed_from_facts`
- `test_emphasis_hid_names_now_found`, using "*Boyar Council*"
- `test_scene_text_keeps_emphasis`

**P3.** Expanding a stub with no tag asks for one, and species and race prompts ask for a tag too. The tag rule currently skips them; check the create-thing template. The stub's tag is shown:
- on the stub card;
- on hover over a stub link;
- in the Stubs list;
- in the expand prompt's header.

Tests:
- `test_untagged_stub_expand_asks_tag`
- `test_species_prompt_asks_tag`
- e2e: the Stubs list shows the tag

### Task 3: P4 and P5, re-point modes and dead links

**P4.** The link card and stub re-point offer two modes:
- **"Add as another name"** (the default): the stub's name and the link words become an aka, guarded as before.
- **"Rename to…":** pick one of the target's names. This is the hard re-point, `use_name`.

`link_text` on a plain selection (Pure-line Moscavians → Snowy Moscavian Owls) offers the same choice and adds the selected words as an aka when asked. Tests:
- `test_link_text_adds_other_name`
- `test_repoint_modes`
- e2e: the re-point mode picker

**P5.** A link whose target is deleted renders as plain text (already true) and counts as plain text for selection. `_raw_span` must not refuse a range through a dead link, and `make_stub_from_text` or `link_text` over it replaces it, in one revision. Undo restores the dead link. Tests:
- `test_selection_through_dead_link_allowed`
- `test_make_stub_over_dead_link_replaces_it`

### Task 4: P6, P7 and P8, draft fidelity and repeat choices

**P6.** On a draft:
- an edited fact keeps its highlights. The client renders names from the draft's known names (picks, new names and world names) the way accept will link them, or the server re-renders on edit.
- new stubs are highlighted in the prose and the facts.
- the timeline is built from the edited draft facts.

**P7.** A draft renamed before accept marks the accepted entry's prose as stale. It was written under the old name, so the prose cache entry is invalidated or flagged.

**P8.** Each fact that repeats an existing fact offers:
- Keep new (drop the existing one);
- Keep existing (drop this one);
- Keep both;
- Move existing here.

Each choice is labelled by which fact it keeps, and the controls sit next to the pair. The server checks "Keep new" like a repeat move: the existing fact is removed only if it is really the repeat match, as recorded in the draft versions the server holds.

Tests:
- e2e `test_draft_edit_keeps_highlights`
- `test_draft_timeline_follows_edits`
- `test_renamed_draft_prose_stale`
- `test_keep_new_drops_existing_checked`
- e2e: the repeat choices

### Task 5: P9, the most precise place in the tree

`kindList` (`entryPage.js`) and any server-side tree helper nest an entry under its most precise home: drop any home that another of its homes already sits in (a place chain, cycle-safe). If several remain, use the first filed. Node checks:
- the Postal HQ (filed in Novograd, the Tsardom and the Great Stone Halls) nests under the Great Stone Halls;
- a cycle doesn't hang.

---

After the tasks: the final whole-branch review of this round, one fix wave, then a short acceptance round 2 with the owner on a fresh root.
