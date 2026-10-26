# Polish 2: Drafts edit like saved pages

Date: 2026-10-25. Status: design, awaiting the owner's approval.

This is the second area of the polish pass. Area 1, "one way to review suggestions", is merged as d68fd6ff. The pass's brief, in the owner's words: "combine making the UI feel better with making the code more maintainable … the goal is a readable UI with clear consistent rules."

The evidence comes from:
- `feedback/2026-10-25-polish1/triage.md` (area 2 section), untracked, in the main checkout;
- the area 2 list from `feedback/2026-10-24-hubs1/triage.md` ("species and race drafts reuse the saved page");
- the owner's screenshots in this conversation: a race draft squeezed into the species page's left column, and the Novgrad Academy draft with an easy-to-miss "In" row;
- a mockup the owner approved: `.superpowers/brainstorm/13741-1792986504/content/in-section.html` (uncommitted). It was approved with one correction: rows read "located in Novgrad", not "Novgrad · located in".

## The owner's standing rules

These were set during area 1 and bind this area too.
1. **Controls sit next to what they act on.** A title and its control are left-aligned together. Right-aligning a row's or heading's controls works only in an area half the screen wide or less, such as "FACTS" with "+ Add facts" in the Facts column. In a full-width area, right-aligned controls end up far from their text.
2. **Things that look the same are one component, never a copy.** The owner's words: "it seems weird to have something that should be visually the same written twice".
3. **When merging copies, the screen the owner approved is the model.** Make the other copies match it. Don't rebuild the approved one. In area 1 the saved page's fact row was rebuilt and broke, and it had to be put back.

## Intent

A draft is "the page it will be", and drafts and saved pages are meant to share one page (Filing spec, `2026-10-23-fantasymate-filing-design.md`). In practice the draft is still missing pieces the saved page has, and some draft pieces look different or sit in the wrong place:
- **Missing editors.** A species or race draft can't set its lifespan, "adult at" or measures, and its other names can only be removed, never added or edited. The owner: "only remove one or more of the AI's suggestions … I can't view or edit the lifespan or adult as value. Both of these could ideally use the same set up as viewing the saved draft, going with that reuse principle."
- **No hand-written fact.** A draft offers "+ Add facts…" (the AI) but not "+ Add fact" (by hand). The owner: "Draft is supposed to be sharing UI with created page, but only one of the two add facts buttons are present when drafting."
- **Race drafts are squeezed.** A race draft is drawn inside the species page's left column, so a whole race page, description included, is crammed into half the width. The owner: "it should span from the navigation column to the right side just like the species entry, or any other entry."
- **"In" is easy to miss.** The owner: "Located in Novgrad is a pretty important thing to see. Its font seems smaller than facts, it should be just above facts as a clear section; remove this AI speak subtitle … Also that '+ IN' button and edit and delete buttons are on the other side of the entire screen."
- **No show-under chip on drafts.** A filing's "shows under" can be set only after accepting (hubs triage leftover).
- **A preview lag.** After a refused Accept, the draft preview can lag one edit behind until the next edit (hubs triage leftover).

## Goals

1. **Race and mix drafts span the entry's width.** On a species page, the Races and Mixes sections move out of the left column, below both columns, at the full width of the entry, from the navigation column to the right edge. A race or mix draft created there gets the same width and the same two-column layout as any entry page: facts on the left, description on the right.
   - *My call:* the accepted-race and accepted-mix cards in those sections move down with them.
   - *My call:* they sit directly below the two columns, before Connected. When area 5 moves Connected into the space under the description, it moves up into the right column, so this placement doesn't conflict with it.
2. **Drafts get the saved page's editors, as the same components:**
   - species, race and mix drafts get **Lifespan, Adult at and Measures** (today `ThingNumbers`, saved pages only).
     - *My call:* mix is included because saved mix pages already show them, which keeps a draft the same as its saved page.
   - every draft gets the full **Other names** section (today `ThingAka`, saved pages only): "+ Add other name", common or proper, everyday, edit and remove;
   - every draft gets **"+ Add fact"** (by hand) next to "+ Add facts…".

   Each is one component that edits either a saved entry or a draft. It is never a draft copy.
3. **The In section is rebuilt as in the approved mockup, on drafts and saved pages alike, as one component:**
   - It sits **just above Facts, in the left column**, as a section of its own like Facts. Its text is the same size as the facts.
   - **"+ In…" sits at the right of the "In" heading**, the same pattern as "Facts" with "+ Add facts…". Each row's **edit and delete sit at the right of that row**, inside the half-width column.
   - **Rows read role first: "located in Novgrad".** With no role, the row is just the place's name.
   - **The subtitle "the AI's suggestions come unticked, yours ticked" is removed.** The AI's suggested filings still arrive unticked.
   - The **"Is X the same as an entry you already have?"** box moves up, directly under the name row, since it asks about the name.
4. **Drafts show the show-under chip** on In rows and in the "+ In" form, as saved pages do. Setting it on a draft is written by Accept.
   - This needs a new field: `PreviewFiling` (`src/talemate/worldplay/create.py`) has no `show_under` today.
   - `accept_preview`'s filing writer then writes it the way `add_filing` does.
   - The server checks it as `edit_filing` does.
5. **The preview lag is fixed.** After a refused Accept, the draft preview renders again, so it always shows what Accept would write.
6. **The last two copies of the fact line are folded in.** Inherited facts (`ThingInherited`) and the "+ Add facts" draft's rows (`EntryAddFacts`) draw a fact through the shared `FactLine` that the saved page and the page draft use. Any extras stay around the shared line: an inherited fact's strike-through, "override" and source; a small draft's tick and repeat match.
   - *My call:* `FactLine` shows only the actions that apply where it's used.
     - Saved pages and page drafts keep ⋯, edit and end as now.
     - Inherited facts show their "Override" in that place instead.
     - "+ Add facts" rows show none, as today.
   - The text, category chip and date are always the same line.

## Non-goals

- **Section headers and row buttons outside the In section.** That's area 3, though the In section's buttons are fixed here. Area 3 brings the same rule to the rest.
- **Names and pickers:** reference search by other names, and "House of Solarius". That's area 4.
- **Connected's layout and grouping, the tree, "not made yet", and errors.** That's area 5.
- **New features:** "died" for characters, and changing an entry's kind.
- **Changing what the AI is asked.** The prompts themselves are untouched. Accept may take new data in two places:
  - a draft's numbers and other names, which already travel in `CreatePreview.fields` and `aka`;
  - a draft filing's `show_under` (goal 4).

## Anti-goals

The work fails, even if it technically works, if:
- **anything is written before Accept;**
- **a draft and a saved page show the same thing differently,** or the same thing is built twice;
- **a saved page loses or changes how it looks or works** in any way not listed above. The changes listed above are the In section moving and its new layout, which apply to saved pages too. Check saved pages against screenshots taken before the change.

## Today

All paths are under `talemate_frontend/src/components/worlds/` unless they name another folder.
- **`ThingPage.vue`** draws both drafts and saved pages.
  - `EntryIn` is rendered near line 187, full width above the two columns, and `SameThingAsk` comes right after it (~196).
  - The two `v-col cols="12" md="6"` columns start at ~229 and ~384.
  - In the left column, `ThingNumbers` and `ThingAka` render only `v-if="!draft"` (~259-260). The Facts heading has `EntryAddFacts` and "Add fact" (~270-271), and "Add fact" also has `v-if="!draft"`.
  - `HeritageSections` (the Races and Mixes sections, with their `CreateBox`) sits at the bottom of the left column (~379).
  - `ThingInherited` is at ~369.
- **`ThingNumbers` and `ThingAka`** read `worlds.thing` and write through `set_field`, so they can't target a draft. A draft's numbers live in `edited.fields`, which `HIDDEN_FIELDS` in ThingPage hides. The server's draft page payload sends `numbers` as nulls (`src/talemate/server/worlds.py`, the draft payload). On a draft, other names appear only as removable chips in the header.
- **`EntryIn.vue`:**
  - The heading is `text-overline` + a `v-spacer` + "+ in…".
  - A draft-only subtitle sits at line 5.
  - Rows use smaller text, with buttons after a spacer.
  - The `TagChip` for show-under has `v-if="!draft"` (lines 37 and 63).
  - The "until" year field also has `v-if="!draft"` (~92). *My call:* keep that as it is; a draft filing's end date is out of scope.
- **`FactLine.vue`** (area 1) is the one fact line. `FactRow` uses it for saved pages and page drafts.
- **Preview lag:** `acceptPreview` drops the queued render (`dropDraftRender`). On a refusal, the `operation_done` error branch in `stores/worlds.js` (~2469) clears `accepting` but never calls `renderDraft()` again.

## Left to the builder

- How `ThingNumbers` and `ThingAka` become two-mode components (value in, change out) and how a draft's numbers and other names travel through the draft's `edited` state to Accept. Read first how `accept_preview` writes `fields` and `aka` today.
- The exact markup of the new In section, within the mockup and the rules above. Keep existing test ids where the element survives, and grep `tests/e2e` and `tests/ai`.
- How `HeritageSections` moves below the columns without changing a non-species page.
- How `ThingInherited` and `EntryAddFacts` wrap `FactLine`.
- Test coverage for each goal. Every visible change gets an e2e assertion. Saved pages get screenshots before and after (at 1280 and 1920 px wide), compared, and sent to the owner.
