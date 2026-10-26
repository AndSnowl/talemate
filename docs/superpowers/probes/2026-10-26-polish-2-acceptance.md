# Polish 2 (drafts edit like pages): the owner's acceptance checklist

Date: 2026-10-26. Branch `feature/polish-2-drafts`. Tasks 1-7 and the final
review's fixes are built; this is what the owner should try before calling
it accepted. The plain suite (7621 passed, 6 skipped), the full e2e suite
(147 passed, `-n 4`, no flakes this run) and ruff on the changed Python are all clean as of this
branch.

Try it in a world that has the Tsardom of Moscavia seeded, with a
Moscavian Owl-folk species and a Novgrad Academy place — the owner's usual
test world, or the worked examples below.

## What to try, and what should happen

- [ ] **Start a race draft from the Owl-folk species page.** Click "+ New
  race", describe it, Create. The draft comes back spanning the whole
  entry — from the navigation column to the right edge, the same width
  and two-column layout (facts on the left, description on the right) as
  any saved entry page — instead of squeezed into the species page's left
  column. A "+ New mix" draft gets the same treatment.

- [ ] **Edit a race draft's numbers, the way you would on its saved
  page.** On that "Snowy Owl-folk" draft, Lifespan shows the species'
  value, dimmed, with "inherited" next to it — click "Edit lifespan",
  type a number of your own, Save: the dimming and "inherited" are gone,
  it's now the draft's own value. The same works for "Adult at" and any
  measures. Nothing is sent to the server until you Accept; after Accept,
  the saved race page shows exactly the value you set.

- [ ] **Add and edit other names on any draft**, not just remove one of
  the AI's. "Other names" now has its own "+ Add other name" on a draft,
  same as a saved page: add one, mark it common or everyday, edit or
  remove it. The header's chips next to the draft's name (its "also
  known as" list) are read-only now — click one and nothing happens;
  manage them in Other names instead.

- [ ] **"+ Add fact" by hand on a draft.** Next to "+ Add facts…" (the
  AI), there is now "Add fact" (by hand) — the same button and form as a
  saved page's. Write a fact, Save: it lands in the draft as a ticked
  row, nothing sent yet. Accept, and the fact is on the saved page.

- [ ] **The "In" section on the Novgrad Academy page (saved) and on a new
  draft filed into Novgrad.** "In" is its own section, just above Facts,
  same text size as a fact row. "+ In…" sits at the right of the "In"
  heading, the same pattern as "Facts" / "+ Add facts…", now a plain
  accent-coloured "+ In…" text button (it was an outlined button with a
  magnifier). A row reads "located in Novgrad", role first, as saved rows
  already did (the mockup's draft wording "Novgrad · located in" was never
  built). There is no "the AI's suggestions come unticked, yours
  ticked" subtitle under it; the AI's own suggested filings still arrive
  unticked, you just aren't told so in words any more. Each row's edit
  and delete sit at the row's own right edge, inside the half-width
  column — not off at the far side of the screen.

- [ ] **"Shows under" on a draft's In row.** File the Owl-folk host "in"
  somewhere with a role, then click the row's "shows under" chip: pick an
  existing group or type a new one. Nothing is sent while you're still
  drafting; Accept, and the saved page's "In" row carries the group you
  picked, a brand-new group name included.

- [ ] **A refused Accept, then an edit.** Try to Accept a draft in a way
  that gets refused (e.g. a name collision), then make one more edit.
  The draft's preview now catches up to your latest edit instead of
  lagging one edit behind.

- [ ] **Compare an inherited fact (e.g. Vasha, a Snowy Owl-folk
  character, and "Wings in place of arms" inherited from Owl-folk) against
  one of his own facts.** They line up: same text position, same category
  chip, same date position. Where an own fact has its ⋯ / Edit / End
  buttons, the inherited fact has "Override" in that same spot, and the
  small chip naming where it came from ("Owl-folk") sits after the words,
  not off on its own. Inherited facts now also show their dates
  ("always", or e.g. "900 →") where an own fact's are.

- [ ] **A race draft's inherited facts.** On the Highlander draft from
  the Human species page, "Inherited (untick to replace)" lists each
  inherited fact on the same line as the saved race page: the words
  dimmed, the source chip ("Human") after them, the category chip and
  dates lined up with the draft's own facts. The "Kept" tick sits in
  front; untick one and its line is struck through, with "Replaced by"
  under it.

- [ ] **"+ Add facts" on a draft, narrow window (about 1280px).** The
  rows wrap onto more than one line, the same way a saved page's fact
  rows already do in a narrow window — the add-facts panel gets taller
  to match, instead of looking narrower than the rest.

- [ ] **Races and Mixes on the Owl-folk species page.** They sit below
  both columns, at the full width of the entry, not squeezed into the
  left column with the facts. Accepted race and mix cards moved down
  with them.

## Changed on purpose (eyeball these — they're meant to look different from before)

- The "In" section moved above Facts **on saved pages too**, with a new
  look: rows the same text size as facts (still role first, "located in
  Novgrad"), "+ In…" at the heading's right as an accent text button with
  a plus (it was an outlined button with a magnifier), and the "AI's
  suggestions come unticked, yours ticked" subtitle removed. This is the
  one approved change to how a saved page looks (owner rule 3).
- The draft header's "also known as" chips next to the name are read-only
  now — edit or remove other names in the Other names section instead.
- "Other names" (add, edit, everyday/common, remove) now appears on
  drafts of every kind, not only saved pages.
- "Shows under" on a draft's In rows and its "+ In…" form works the same
  way it does on a saved page, a brand-new tag name included.
- An inherited fact and an own fact line up: the inherited fact's
  "Override" sits where an own fact's ⋯/Edit/End buttons sit, and its
  source chip ("Owl-folk") moved to after the words instead of floating
  on its own.
- Inherited facts on a saved page now have a date column ("always", or
  the fact's dates), from the dates the page's inherited facts now carry.
  At about 1280px the Facts column is narrow, so their words wrap onto
  more lines and the Inherited block is taller than before.
- A draft's inherited facts ("Inherited (untick to replace)") now look
  like the saved page's: the same line (words dimmed, source chip after
  them, category and dates at the right), with the Kept tick in front.
  Before, they were plain text with the source chip where the category
  goes, and no category or date.
- The "+ Add facts" rows on a draft now wrap the same way saved fact rows
  do in a narrow (about 1280px) window — the panel gets taller there;
  before, these rows were wider and didn't wrap at that width.
- Races and Mixes (and their accepted race/mix cards) moved from the
  species page's left column to below both columns, at the entry's full
  width — the same placement a race or mix draft now gets.

## Screenshots for the owner

Before (`ae64af3e`, the branch's base) and after (the branch head) shots
at 1280 and 1920 px are kept in the session scratchpad (not committed),
under
`/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/b21eef1e-9287-4ae6-8b4d-11b813ef0e0d/scratchpad/`.
Each file is `before-<name>-<width>.png` or `after-<name>-<width>.png`.
- `t3/`: numbers and other names. `saved-species` (Human: numbers,
  other names, facts), `saved-race` (Lowlander: inherited numbers and
  facts), `draft-race`, `draft-species`, `draft-page` (a place draft's
  facts), `add-facts` ("+ Add facts" on a saved page).
- `t5/`: the fact line and inherited facts. The same screens, plus
  `saved-place` (Novgrad Academy), `draft-race-inherited-unticked` (the
  draft's inherited facts, one unticked), and clips of the Facts list
  (`*-facts-*`) and the Inherited block (`*-inherited-*`).
- `t6/`: the In section, saved Novgrad Academy and Velikoye pages.
- `t7/`: Races and Mixes at the species page's full width, with and
  without a race draft open, plus a non-species saved page.

Pixel diffs, before against after:
- The Facts list of the saved species, race and place pages is identical
  at both widths.
- The saved Inherited block differs, as intended (its date column, the
  source chip after the words).
- Whole saved pages differ only in height and position, from the In
  section's move and new look and the Inherited block's date column.
- The draft screens differ by design.
