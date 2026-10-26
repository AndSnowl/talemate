# Polish 1 (suggestion lists): the owner's acceptance checklist

Date: 2026-10-25. Branch `feature/polish-1-suggestions`. Tasks 1–11 are built; this
is what the owner should try before calling it accepted. The plain suite (7614
passed), the e2e suite (139 passed, `-n 4`, no flakes) and ruff on the changed
Python are all clean as of this branch.

Try it in a world that has the Tsardom of Moscavia (or Velikoye) seeded, the
owner's usual test world.

## What to try, and what should happen

- [ ] **"+ Add facts" on a saved page** (e.g. Velikoye). Click it: the prompt
  box is a real, roomy multi-line box, not a one-line field. Ask for facts,
  then edit the prompt and press Regenerate: a new version appears
  ("Version n of m ▾"), and the earlier version is still reachable from the
  dropdown. If a drafted fact repeats one Velikoye already has, its match
  hangs under its own row with the four choices; Keep new writes the new
  fact and drops the old one.
- [ ] **"+ Add facts" on a draft page.** Start a draft (e.g. a new place),
  click "+ Add facts": it comes back as its own small draft, indented under
  Facts, with its own bar (ticks, Regenerate, Discard, Write). While it's
  open, the page draft's Accept, Regenerate and version switch are off,
  with the reason "write or discard the added facts first". Tick/untick
  facts, press Write: the ticked facts land in the page draft as a new
  draft version, and the nested draft goes away.
- [ ] **Connected's "+ Add"** on an entry page. Add a fact, then Regenerate:
  the prompt it used is still sitting in the box, not lost.
- [ ] **"For other pages" on a draft.** Its "→ page ▾" and "+ also here"
  sit on a second line under the row's text, not on the far right. A row
  that repeats a fact already on its target page gets the same four
  choices (Keep new, Keep existing, Keep both, Move existing here), with
  Move existing here disabled and labelled "already on that page".
- [ ] **Every list looks and behaves the same.** Compare a page draft's
  facts, "+ Add facts", Connected's "+ Add" and "For other pages" side by
  side: where the tick sits, the struck-through/dimmed look of a dropped
  row, where a repeat's match hangs (under its own row, on a left rule),
  and the dashed separator (always after the match, never between a row
  and its match).

## Changed on purpose (eyeball these — they're meant to look different from before)

- Rows the AI offered unticked — Could move here, File into this, a merge's
  facts — are now struck through like any other dropped row, instead of
  sitting there plain but unticked.
- A New name's same-as / in… / rename controls sit on a second line under
  the name, not beside it.
- The bar's prompt label reads "Prompt" on a page draft ("Edit prompt" and
  "Back to the draft" are gone; the prompt is always on screen).
- "+ Add facts" and "+ Add event" on the same page now share one draft:
  starting one while the other is open is blocked until the open one is
  written or discarded.
- "Move existing here" on a fact or event draft is disabled with "already
  on this page" when the repeat is a fact already on the page doing the
  asking (an elsewhere row's own version of this says "already on that
  page").
