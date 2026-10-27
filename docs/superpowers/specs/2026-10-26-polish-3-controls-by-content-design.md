# Polish 3: Controls sit next to what they act on

Date: 2026-10-26. Status: design, awaiting the owner's approval.

This is the third area of the polish pass. Areas 1 (suggestion lists, d68fd6ff) and 2 (drafts edit like saved pages, 2a2438b6) are merged.

The evidence comes from:
- `feedback/2026-10-25-polish1/triage.md` (the "Area 3" section and "Notes added 2026-10-26"), untracked, in the main checkout;
- `feedback/2026-10-24-hubs1/triage.md` polish items 25, 27 and 29;
- this conversation;
- a mockup the owner approved, option **A**: `.superpowers/brainstorm/16159-1793061039/content/area3-summary.html` (uncommitted).

## The owner's standing rules

These bind every area. They are kept in the owner's memory notes and in the area 2 spec.
1. **Controls sit next to what they act on.** A title and its control are left-aligned together. Right-aligning a row's or heading's controls works only in an area half the screen wide or less, such as "FACTS" with "+ Add facts" in the Facts column. In a full-width area, right-aligned controls end up "an entire postal code away" from their text.
2. **Things that look the same are one component, never a copy.**
3. **The screen the owner approved is the model.** Change only what is listed here. Check everything else against screenshots taken before the change.
4. **Move only the part that needs the room.** When one piece needs a different width or place, move that piece alone, not its whole section.

## Goals

1. **The summary row heads the left column** (mockup A).
   - The entry's summary fact, today a full-width row under the title (`ThingPage.vue`, `data-testid="entry-summary"`), becomes the **first row of the left column**, above Other names.
   - It is a fact row like the others (the shared `FactRow` / `FactLine`), with its text slightly larger as it is today (`summary-text`), and its buttons at the column's right.
   - Its edit form opens in place, as today.
   - *My call:* "first" means literally first, above the field rows (a character's born date, heritage link), the being-existence toggle and the species/race/mix numbers. The owner chose the version where the summary leads the page.
   - Drafts show no summary row, today or after (`summaryFact` is null on a draft).
2. **Connected moves into the right column, under "Appears in".**
   - `EntryConnected` moves out of the full-width area below the columns into the right column, after Description and "Appears in" (or "Referenced in" on heritage pages).
   - Its "+ Add" then sits at the right of a half-width heading, like Facts.
   - The groups (`ConnectedGroup`) fit the column. *My call:* they stack one per row in the column, where today they flow in two columns.
   - *My call:* **Mentioned in** (`EntryMentionedIn`) moves with it, directly under Connected, since both list other entries tied to this one.
   - *My call:* **on a stub's draft, they move to the same place,** because a draft is "the page it will be".
     - They sit in the right column under Description. On a draft that column has no "Appears in", and it stays hidden there as today.
     - The draft-only sections (For other pages, Could move here, New stubs, File into this, the foot bar) stay where they are, so Connected now sits beside them in the right column instead of after them.
3. **Timeline: "+ Add event…" sits right after the "Events ▾" dropdown.** The Timeline stays full width, and its heading's controls follow the title, as the rule says for a full-width area.
4. **"Fill the stub X instead" moves next to Accept.**
   - It is another way to accept, so it becomes a second button in the draft bar, right next to Accept, reading "Fill stub X".
   - The banner under the draft bar ("There is a stub named X already.") goes away. The bar's counts line mentions the stub ("a stub named X exists").
   - It keeps its current behaviour, its lock while a nested draft is open, and its test id (`fill-stub-instead`).
   - Where the page draft has a foot Accept (area 1), the foot gets it too.
5. **"Add fact" no longer drops an open edit.** While a fact's edit form is open on a saved page or a draft, "Add fact" is turned off, with the reason "save or cancel the edit first" as its title. This closes ruling R4 from area 2.
6. **The sweep: every other full-width heading or row whose control sits at the far edge** gets the same treatment, either moved into a half-width column or given the control right after its title.
   - Candidates found by a first look: the Stubs tab (`StubsTab.vue`), the Tags tab (`TagsTab.vue`), the worlds home (`WorldsHome.vue`), and the create box's own heading (`CreateBox.vue`).
   - The builder checks each one at 1280 and 1920 px and lists it in the plan as **fix** or **fine as is**, with the reason. The owner can strike any of them while reading the plan.
   - Dialogs (`MergeDialog`, `ThingDeleteDialog`, `ExpandAskDialog`, `NewSceneDialog`) are narrow by nature, so they're fine as is unless the check shows otherwise.

## Non-goals

- **Names and pickers** belong to area 4: reference search by other names, and "House of Solarius".
- **Connected's grouping and sorting** (by kind, then by tag), **the tree's depth**, **"not made yet"** and **errors** belong to area 5. This area only moves Connected.
- **New features**, such as race and mix stubs that can be expanded, "died", and changing an entry's kind.
- **No server changes** are expected.

## Anti-goals

The work fails, even if it technically works, if:
- anything on a saved page or a draft changes beyond what's listed here;
- the same thing is built twice;
- a control ends up farther from its content than it is today, anywhere.

## Today

- **`ThingPage.vue` layout:**
  - the header and its strip come first;
  - then the summary at full width (around lines 197-212);
  - then two `v-col md=6` columns: the left one holds numbers, Other names, In, Facts, Inherited, Races, Mixes and Named stubs; the right one holds Description and either Appears in or Referenced in;
  - then, at full width: the heritage draft area, Connected, Mentioned in and Timeline (around lines 545-552).
- `DraftBar.vue` builds the bar on `SuggestionBar` (area 1). The "Fill the stub instead" banner is in `ThingPage.vue` (lines 6-20).
- `EntryTimeline.vue` has the heading `text-overline` + "Events ▾" + `v-spacer` + `EntryAddFacts event`.

## Left to the builder

- **Markup.** Within the rules above, choose the markup. Keep test ids where the element survives, and grep `tests/e2e` and `tests/ai` for any that change.
- **The sweep list** and its fix / fine verdicts.
- **Screenshots before and after** at 1280 and 1920 px of:
  - a saved place page (Velikoye-like, with filings, facts and Connected groups);
  - a species page;
  - a page draft;
  - the Stubs and Tags tabs.

  Compare them, name every difference, and send the after shots to the owner.
