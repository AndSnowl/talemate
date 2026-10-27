# Polish 4: Names and Pickers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the owner's choice for UI work) — or superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- One shared entry search that finds other names, and shows which one matched.
- Name highlighting in every prompt box.
- Selections that contain a whole link can become a stub or a link.
- Re-point with four choices.
- One stub hover card everywhere.
- Re-pointing to a remade entry works.

**Architecture:**
- **Server:** listings carry `aka`; `named_stubs` carries the full stub details; a new re-point link mode, `retitle`; the selection span check lets a selection contain whole links; dead links become words on every fact rewrite.
- **Frontend:** a shared `searchEntries` and an `EntryResult` row component, used by every picker; `NameHighlightInput` in the remaining prompts; `NameModeMenu` with four choices; `NamedStubs` and the other stub-name spots on the fact-style `LinkedText` stub card.

**Tech Stack:** Python 3.11 with pydantic (`src/talemate/server/worlds.py`, `src/talemate/worldplay/`); Vue 3, Vuetify 3 and Pinia; pytest; Playwright e2e; node checks.

**Spec:** `docs/superpowers/specs/2026-10-27-polish-4-names-and-pickers-design.md`

## Global Constraints

- **Owner rules:**
  - controls sit next to their content;
  - one component, never a copy;
  - the approved screen is the model: check the rest against before and after screenshots at 1280 and 1920 px;
  - move only the part that needs the room.
- **Execution is inline, with screenshots sent after each visible change.**
- **Re-point choices**, in this order and with these labels:
  - "Add as another name";
  - "Use the entry's name";
  - "Rename the entry to these words";
  - "Link only".
- **A search result** shows the main name in normal text. When an other name matched, it shows that other name small and dim underneath.
- **No automatic "named after" tie** when a selection containing a link becomes a stub.
- **Keep test ids.** Grep `tests/e2e` and `tests/ai` for any that change; never run `tests/ai`.
- **Running things:** use `guix shell -m manifest.scm -- …`, and always `uv run --no-sync`.
  - The e2e suite runs with `-n 4` at most.
  - `test_tags_rename_merge` is a known flake.

## Review Focus

1. **An other name shared by two entries.** Both show, each with that name dim under it. Pinned in Task 2, the node check `searchEntries lists every entry an other name matches`.
2. **Retitling an entry to a name another entry already uses.** It is refused with a clear note, and nothing is written. Pinned in Task 4, `test_repoint_retitle_refuses_a_name_in_use`.
3. **A selection that contains a whole link and also cuts into another.** It is still refused with "the selection cuts through a link". Pinned in Task 3, `test_selection_containing_a_link_but_cutting_another_is_refused`.
4. **A fact with two dead links, one of them inside the re-pointed words.** Both become words, and the re-point succeeds. Pinned in Task 5, `test_repoint_with_dead_links_in_the_fact`.
5. **A stub card on an entry page before the Stubs page was ever opened.** It shows the tag, kind and mentions. Pinned in Task 6, `test_named_stubs_card_is_full_without_stubs_page`.

---

### Task 1: The server sends other names and full stub details

**Files:** `src/talemate/server/worlds.py` (`handle_list_things` around line 2620; `handle_list_heritage`; `links.named_stubs` around line 1448); tests in `tests/server/test_worlds_plugin.py`.

**Interfaces — Produces:**
- Every `list_things` and `list_heritage` entry gains `aka: list[str]`, its other names (the names only). A stub's entry gets `aka: []`.
- The `named_stubs` rows become `{id, name, kind, tag, mentions, ignored}`, the same shape as a `list_stubs` row.

- [ ] Write the failing tests:
  - `test_list_things_carries_other_names`: an entry with other names "Owls" and "Moscavian Owls" lists `aka == ["Owls", "Moscavian Owls"]`.
  - `test_named_stubs_rows_are_full`: the page payload's `named_stubs` row has `tag`, `mentions` (a count) and `ignored`.
- [ ] Run them and confirm they fail.
- [ ] Implement. Reuse the code that builds a `list_stubs` row.
- [ ] Run the tests and confirm they pass, then the plain suite.
- [ ] Commit with the message `feat(worlds): listings carry other names; named stubs carry full rows`.

### Task 2: One entry search, one result row, in every picker

**Files:**
- `talemate_frontend/src/components/worlds/nameHighlights.js`: `searchEntries` replaces `searchReferences`.
- Create `EntryResult.vue`.
- `stores/worlds.js`: `referenceTargets` carries `aka`.
- The pickers: `ReferenceMenu.vue`, `EntryIn.vue` (~209), `FactRowActions.vue` (~155-159), `MergeDialog.vue` (~129), `SameThingAsk.vue` (~142), and PreviewElsewhere's retarget, which goes through ReferenceMenu.
- Tests: `talemate_frontend/checks/worlds.check.mjs` and e2e.

**Interfaces — Produces:**
- `searchEntries(targets, query, limit = 8) -> [{target, matched: string|null}]`.
  - It matches a target's `name` or any of its `aka`, case-insensitively, by substring.
  - It ranks a name match before an other-name match, and a starts-with match before a contains match.
  - `matched` is the other name that matched, or `null` when the main name did.
- `EntryResult.vue` takes the props `target` and `matched`. It shows the name, a kind chip and a stub style as today, and `matched` small and dim underneath.
- Each picker's autocomplete uses Vuetify's `custom-filter` (or `:items` already filtered) with `searchEntries`, and draws its items with `EntryResult`.

- [ ] Write the failing tests:
  - Node checks:
    - `searchEntries finds an entry by its other name and says which`;
    - `searchEntries ranks name matches first`;
    - `searchEntries lists every entry an other name matches`.
  - E2E, `test_pickers_find_other_names`: in "Link to…" (the selection menu), "+ In…" and "Move to…", typing "Moscavian Owls" lists "Moscavian Owl-folk", with "Moscavian Owls" dim beneath it.
- [ ] Run them and confirm they fail.
- [ ] Implement, replacing each hand-built filter. `searchReferences` goes, and its callers move to `searchEntries`.
- [ ] Run the tests, `tests/e2e/worlds -n 4` and the frontend checks, and confirm they pass. Take before and after screenshots of each picker open, and send them.
- [ ] Commit with the message `feat(worlds-ui): one entry search that finds other names`.

### Task 3: A selection that contains a whole link

**Files:** `src/talemate/server/worlds.py`: the span check around lines 1930-1952 (`_raw_span`), `make_stub_from_text`, `link_text` and the draft selection twins. Tests in `tests/server/test_worlds_plugin.py`, plus one e2e test.

- [ ] Write the failing tests:
  - `test_selection_containing_a_link_becomes_a_stub`: in "Its five houses include the House of [[@id|Solarius]].", selecting "House of Solarius" and making a stub writes `[[@stub|House of Solarius]]`. The Solarius link is gone from that text, and Solarius's entry is untouched.
  - `test_selection_containing_a_link_links`: the same selection linked to an existing entry.
  - `test_selection_containing_a_link_but_cutting_another_is_refused`: a selection that contains one link but cuts through another is refused with "the selection cuts through a link".
  - The same two cases on a draft fact.
- [ ] Run them and confirm they fail.
- [ ] Implement.
  - A link fully inside the selection is allowed; its words count as plain words of the selection.
  - A selection that partly covers a link is still refused.
  - When the new link is written, the old links fully inside it are replaced. No automatic filing.
- [ ] Run the tests and confirm they pass. Add e2e `test_house_of_solarius_stub` (select across the link, then "Make a stub").
- [ ] Commit with the message `feat(worlds): a selection may hold whole links; the longer name wins`.

### Task 4: Re-point offers four choices

**Files:**
- `src/talemate/server/worlds.py`: `LinkMode` gains `"retitle"`, `_link_mode`, the re-point handlers.
- `src/talemate/worldplay/repoint.py`: `plan_repoint`, `repoint_stub`.
- `NameModeMenu.vue`, `StubRepointButton.vue`, `LinkedText.vue` (the re-point flow), `SelectionMenu.vue` (Link to…).
- The note that says "added as another name": find it with `grep -rn "another name" talemate_frontend/src src/talemate`.
- Tests: `tests/server/test_worlds_plugin.py`, `tests/worldplay/`, e2e.

**Interfaces — Produces:**
- `LinkMode = Literal["link", "name", "rename", "retitle"]`.
- `retitle`:
  - the target entry's main name becomes the selected words (or the stub's name);
  - its old main name joins its other names;
  - all of this in the re-point's single revision.
- It is refused, writing nothing, when another live entry already has those words as its main name or an other name. The note reads "<words> is already the name of <entry>".

- [ ] Write the failing tests:
  - `test_repoint_retitle_renames_the_target`: re-pointing the words "Pure-line Moscavians" to "Snowy Moscavian Owls" with `retitle` gives the entry the main name "Pure-line Moscavians", with "Snowy Moscavian Owls" among its other names.
  - The same with a stub re-point.
  - `test_repoint_retitle_refuses_a_name_in_use`.
  - E2E: the re-point menu lists the four labels, in the order from Global Constraints. After a re-point or rename, no "added as another name" note shows.
- [ ] Run them and confirm they fail.
- [ ] Implement:
  - the backend mode;
  - `NameModeMenu` gets the fourth item, defaulting as today;
  - remove the "added as another name" note.
  - List in the ledger any other action notes of the same informational kind; don't change them.
- [ ] Run the tests and confirm they pass, then the plain suite and `tests/e2e/worlds`. Take screenshots of the menu, and send them.
- [ ] Commit with the message `feat(worlds): re-point can rename the entry to the words`.

### Task 5: Dead links become words on a rewrite

**Files:** `src/talemate/worldplay/repoint.py` and wherever a fact's text is rewritten (search for the `rev.set_fact_text` / `rewrite` call sites); `src/talemate/server/worlds.py` (`_dead_links_as_words`, which is reused). Tests in `tests/worldplay/` and `tests/server/`.

- [ ] Write the failing test, `test_repoint_with_dead_links_in_the_fact`:
  - Make entry A and link a fact on stub S's citing page to it, then delete A.
  - Remake A as A2.
  - Re-point S to A2: today this raises "fact references unknown or removed thing".
  - Assert the re-point succeeds, and the dead link's words remain as plain text.
- [ ] Run it and confirm it fails, with exactly the owner's error.
- [ ] Implement. Put one helper, `words_for_dead_links(view, text) -> str` (whole text), in front of every write of rewritten fact text in repoint, move, copy and merge. It reuses `_dead_links_as_words`' rule, moved to a shared module.
- [ ] Run the test and confirm it passes, then the plain suite.
- [ ] Commit with the message `fix(worlds): rewritten facts drop dead links to their words`.

### Task 6: One stub card everywhere

**Files:** `NamedStubs.vue` and the sweep list below; `LinkedText.vue` (`stubOf` prefers the segment's own full row). Tests: e2e.

The sweep, from a code read. Strike any of these while reading:

| Place | Today | Change |
|---|---|---|
| Stubs this entry named (`NamedStubs`) | a bare stub link, a thin card, no Re-point | `LinkedText` with `repoint`, segments carrying the full row (Task 1) |
| A stub name in a fact (`FactLine` → `LinkedText`) | the full card | (the model) |
| The Stubs page (`StubsTab`) | `StubCard` on the page | the same component, no change |
| A stub's own page (`ThingPage` stub panel) | `StubCard onPage` | the same component, no change |
| Connected rows, In rows, the tree | plain links | the builder checks each one: a stub there uses `LinkedText`'s stub segment (re-point off where it doesn't apply) |

- [ ] Write the failing e2e test, `test_named_stubs_card_is_full_without_stubs_page`: on an entry page, without opening the Stubs page first, hovering a name in "Stubs this entry named" shows `stub-card` with `stub-tag`, `stub-kind` and `stub-mentions`, plus a "Re-point…" button, the same as hovering that stub in a fact.
- [ ] Run it and confirm it fails.
- [ ] Implement, and fix any other spot the sweep marks.
- [ ] Run `tests/e2e/worlds` and confirm it passes. Take screenshots of both cards, and send them.
- [ ] Commit with the message `feat(worlds-ui): one stub card wherever a stub is named`.

### Task 7: Names highlighted in every prompt

**Files:** `GroupAddForm.vue`, `EntryAddFacts.vue`, `EntryIn.vue` ("but…"), `SuggestionBar.vue` / `DraftBar.vue` (the draft prompt). They use `NameHighlightInput` in place of `v-textarea`, keeping the auto-grow and the test ids. Tests: e2e.

- [ ] Write the failing e2e test, `test_prompts_highlight_names`: typing "Velikoye" into the Connected "+ Add" prompt, the "+ Add facts" prompt, a "but…" field and a page draft's prompt shows it highlighted as a known name. Use the selector the create box test uses.
- [ ] Run it and confirm it fails.
- [ ] Implement.
  - For each prompt, record in the ledger whether its request accepts name picks (`picks`): send them where it does, and display only where it doesn't.
  - Keep the IME and Enter behaviour.
- [ ] Run `tests/e2e/worlds` and confirm it passes. Take screenshots, and send them.
- [ ] Commit with the message `feat(worlds-ui): every prompt box highlights names`.

### Task 8: Verification

- [ ] Grep `tests/ai` for every changed id or label.
- [ ] Run the plain suite, the frontend checks, the build and `tests/e2e -n 4`.
- [ ] Write the acceptance checklist, `docs/superpowers/probes/2026-10-27-polish-4-acceptance.md`, and commit it.
- [ ] Run the final whole-branch review (most capable model), then do one fix pass.
