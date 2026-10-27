# Polish 3 (controls next to what they act on): the owner's acceptance checklist

Date: 2026-10-26. Branch: `feature/polish-3-controls`.

The tests passed on this branch:
- the plain suite: 7621 passed, 6 skipped;
- the full e2e suite: 154 passed, `-n 4`;
- the frontend checks and the build.

## What to try, and what should happen

- [ ] **Open Velikoye** (or any entry with a summary). The summary, "The fortified capital of Moscavia…", is now the first row of the left column, above Other names, a little larger than other facts. Its type, date, ⋯, edit and end sit at the column's right. Edit it: the form opens in place.
- [ ] **Connected moves to the right column.**
  - It sits under "Appears in" ("Referenced in" on a species page), with its groups stacked one per row, and "+ Add" at the right of its heading.
  - "Mentioned in" sits directly below it.
  - On a stub's draft they sit in the same place, under the draft's Description.
- [ ] **Timeline:** "+ Add event…" now sits right after the "Events ▾" dropdown, not at the far right.
- [ ] **Draft a place named like an existing stub** (for example "Kalmara" when a Kalmara stub exists).
  - "Fill stub "Kalmara"" sits right next to Accept in the draft bar, and again at the foot by the second Accept.
  - The counts line ends with "a stub named Kalmara exists". The old banner is gone.
  - Open a nested "+ Add facts" while it's pending or held: "Fill stub" is off, with the same reason as Accept.
- [ ] **Open a fact's edit form** (or the summary's), then look at "Add fact". It's off, with the tooltip "save or cancel the edit first". Cancel, and it's back. The same applies on a draft while a draft fact's form is open.
- [ ] **Sweep:**
  - On the Stubs page, "show ignored" sits right after "named but not made yet".
  - On the Tags page, each tag's "rename" and "merge into…" follow its line.
  - In a create box, "Create" (and "Cancel") follow the pickers instead of the far right.

## Changed on purpose

- **The summary row is no longer full width under the title.** It's the first row of the left column, even above a character's born date or a species' Lifespan.
- **Connected and Mentioned in no longer span the page.** They live in the right column, and Connected's groups stack instead of flowing two to a row.
- **The "There is a stub named X already" banner is gone.** Its button lives by Accept.
- **Left as they were, on purpose:** the draft bar's buttons (approved in area 1), the worlds home (already half-width columns) and the dialogs (narrow).

## Screenshots

The before and after shots are in `/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/b21eef1e-9287-4ae6-8b4d-11b813ef0e0d/scratchpad/p3/`:
- `before-*` are from the base;
- `t1-*` to `t6-*` are after each task;
- `t6-*` is the final state.
