# Polish 5: Lists, grouping and errors

Date: 2026-10-27. Status: design, awaiting the owner's approval.

This is the fifth and last area of the polish pass. Areas 1 to 4 are merged (latest f6d084a5).

The evidence comes from:
- `feedback/2026-10-25-polish1/triage.md`: "Area 5, lists and grouping" and the area 5 notes added after area 3;
- `feedback/2026-10-24-hubs1/triage.md`, polish items 13, 19, 23 and 33, plus the leftover about the "Other" group tooltip;
- this conversation;
- mockups the owner chose: the side tree "A" (`.superpowers/brainstorm/589-1793133581/content/tree-options.html`), kind page "2" (`kind-page.html`) and list row "A" (`list-rows.html`).

**Execution: inline (native), with screenshots after every visible change.** This is the owner's standing preference for UI work.

## The owner's standing rules

These bind every area.
1. Controls sit next to what they act on. Right-align only in areas half the screen wide or less.
2. Things that look the same are one component, never a copy.
3. The screen the owner approved is the model. Change only what's listed here, and check the rest against screenshots taken before the change.
4. Move only the part that needs the room.

## Why

The owner pictures worlds with 100 entries or more. Today's side list is always fully open, so it gets too big to use. The owner: "not with the only options being full expansion and collapse"; "I am not sure the tree can or should do absolutely everything". So the side tree does a few strong things, and a fuller list on each kind's page does the rest.

## Goals

### 1. The side tree folds (mockup A)

- **Kinds fold.**
  - *My call:* the ▸ / ▾ before a kind's name folds and unfolds it.
  - Clicking the name itself shows the kind's page (goal 3), as today, and unfolds the kind; it never folds it.
- **The "+" beside a kind's count** opens that kind's page with its prompt box focused. It's the way to "the prompt page for that entry type".
- **Entries fold.** An entry with others nested under it gets a ▸ / ▾. Folded, it shows a count of what's inside (e.g. "Kerensk 6").
  - *My call:* unfolded, it shows up to 10 of them, then "+ 9 more in Velikoye" (as mockup A shows), which shows the rest in place.
- **Folded by default.** Only the path to the page you're on opens by itself: its kind, and each entry above it. Everything else starts folded.
  - *My call:* the path opens when you arrive on a page. After that you may fold it like anything else; it opens again the next time you open a page on it.
- **What you fold or unfold is remembered**, per world, in the browser (`localStorage`). Losing it is harmless. The path to the open page always opens, whatever was saved.
- **No "expand everything" button.** Search covers that need (goal 2).
- **Nesting.** An entry sits under its most precise home, as it does today (hubs P9). Each entry appears **once** in the tree.
  - The owner rejected showing an entry under each place it's filed in: "it would clutter the side tree". The entry page's In and Connected show the other places.
  - *My call:* nesting works for every kind the same way, not places alone. An entry nests under an entry of its own kind that it's filed in, so lore filed in lore nests too. Kinds whose entries aren't filed in their own kind stay flat, as today.
- **A stub row is one line.** Its dashed stub style marks it. The words "not made yet" move to the row's tooltip, so the row never wraps (hubs item 13).

### 2. Search narrows the tree, with a few text modifiers

- **Plain words match names: main names and other names**, any case, anywhere in the name. Fact text is not searched (the owner).
- **Typing narrows the tree.** Matches show with their parents (dimmed, as context), and their kinds and parents unfold for as long as the search is on. Clearing the search puts back the folds you had.
- **Modifiers**, combinable with words and with each other (all must hold):
  - `tag:city` means the entry's own tag. *My call:* match the whole tag, any case.
  - `in:Velikoye` means filed in Velikoye in any way, at any depth (inside something that's inside it), not only at its most precise home. This keeps the "other wheres" findable. A name with spaces is written with quotes: `in:"Night Court"`.
  - `stub` means not made yet.
  - `when:1020` means the entry exists in that year, as the page's "viewing as of" year would count it.
    - *My call:* the year is the plain year number, as typed into "viewing as of", with no era suffix.
    - For a character, it means born by then. A being's existence holds then. An event's span holds 1020.
    - Places, lore, items and the rest have no span of their own, so they always match.
- *My call:* an unknown modifier, like `foo:bar`, is searched as plain words. A small hint under the box lists the modifiers when you focus it.

### 3. A kind's page: the prompt box, then the full list (mockup 2, row A)

- **The prompt box stays on top**, as today (CreateBox). Below it is the kind's full list, under a heading "All places · 41", which replaces today's "Pick one of the … on the left" hint.
- **Controls sit right after the heading**, left-aligned per rule 1:
  - **group by** where / tag / none.
    - "Where" means the entry's most precise home, of any kind (an item's owner, a place's city), shown as a flat group headed by that home's name, e.g. "In Velikoye · 9".
    - Each entry appears once, under its most precise home. Entries with no home go last, under "Nowhere".
    - *My call:* the default is "where" for places and tag for every other kind.
  - **sort by** name / recently changed / most connected / date.
    - "Most connected" means *my call:* the facts of other entries that mention it, plus the entries filed in it.
    - "Date" means a character's birth, an event's year, or any other entry's earliest dated fact. Entries with no date go last.
- **Each row is one line (mockup row A):** "**name** · in Velikoye — its summary".
  - The place is dim, right after the name, with the summary after it. A summary too long for one line is cut with "…".
  - Nothing sits at the far edge.
  - An entry filed in more than one place reads "in Velikoye +1" (*my call:* its most precise home, then the count of the others).
  - A stub reads "**Wattle Row** · in Velikoye · not made yet", in the stub style, with no summary.
- **Group headings** read like Connected's ("City · 5"). An untagged group is "Other", last.
- **Clicking a row** opens the entry, as the tree does.
- **The search box (goal 2) filters this list as well**, so the same modifiers work here.
- *My call:* the list remembers its group and sort per kind in the browser, like the tree's folds.
- **The server's kind lists carry what the list needs:** each entry's tag, its summary line (the same text Connected shows), its last-changed revision, its mention-and-filing count, and its date for sorting.

### 4. Connected sorts by kind, quietly

- **No kind headers.** It stays grouped by tag, as today (the owner: it "didn't need to be super apparent").
- **Groups are ordered by the earliest kind they hold**, in this order: characters, species, races, mixes, places, events, items, lore, beings. "Other" stays last. *My call:* the order is fixed, not a setting.
- **Rows within a group** are sorted by kind in the same order, then by name.
- Tags are one pool across kinds, so a group can mix kinds. Its characters then come first.

### 5. One error message that stays in view

It replaces both the in-page red banner (WorldTab, WorldsHome) and the popup that fades after 3 seconds, for the worlds screens.
- *My call:* it shows the worlds store's errors (`worlds.error`). The app-wide popup (`TalemateApp.vue`) keeps showing errors from the rest of the app, such as clients and scenes, but no longer repeats a worlds error the pinned message already shows.
- **It is pinned to the top of the window**, so you see it however far you've scrolled.
- **It stays until closed** with ×. It never fades on a timer.
- **It can be copied:** the text is selectable, and a copy button copies all of it.
- **There is one at a time.** A new error replaces the old one. The same error again shows "×2" (and so on) instead of a second message.
- **It closes itself when it no longer applies:** on switching world, or on leaving the Worlds screens. *My call:* not on every page change within a world, so you can still read it after the click that caused it.
- **The wording stays** the server's own (the owner: "the wording is fine").
- **The squashed prompt box is fixed** (hubs item 19, img2). A name box re-measures its height when it's shown again or when the layout around it changes, not only when you type.
- *My call:* the Merge dialog keeps its own error line inside the dialog, since the dialog covers the page. The scene setup error stays in its own dialog too.

### 6. Offer rows dim; dropped rows strike through

This reverses ruling R12 from area 2, for offers only.
- **A row that starts unticked** (an offer: "Could move here", "File into this", and any other row the AI suggests unticked) is dimmed, with no strike-through. Ticking it brings it to full colour. Unticking it again dims it again, still with no strike-through.
- **A row that starts ticked and that you untick** is struck through, as today ("this won't be written").
- This lives in the shared row (`SuggestionRow` / `FactLine`), once, so every list follows it.

### 7. Small fixes

- **"Same as" padding in New stubs.** A stub row's "same as X?" dropdown gets space under the type dropdown above it.
- **Connected's "Other" group tooltip** shows on its heading only, not over its rows.

## Non-goals

- Fact text in search.
- An entry shown under every place it's filed in.
- Kind headers in Connected.
- New views (a web of entries, a timeline of the world) and the later features: cascading delete, "died", changing an entry's kind, expanding race and mix stubs.
- Changes to the Stubs and Tags pages beyond what's listed.

## Anti-goals

The work fails, even if it technically works, if:
- the side tree opens fully by default, or forgets the folds you set;
- a list row puts anything at the far edge of a wide area;
- an error message vanishes before you've read or copied it;
- an offer still looks deleted before you've touched it.

## Today (from a code read)

- **The side list:**
  - `WorldTab.vue` draws each kind's list from `kindList(things, query, { nest: kind === 'place' })` in `entryPage.js`.
  - Only places nest, by `mostPreciseHome`.
  - Nothing folds.
  - Search matches main names only.
  - Stub rows add "not made yet" as text.
- **A kind's page** is `CreateBox` plus a one-line hint.
- **`list_things`** sends `{id, kind, name, aka, stub, filed_in, existence?}` per entry.
- **Errors:**
  - `worlds.error` shows as a closable `v-alert` in `WorldTab.vue` and `WorldsHome.vue`, and in `MergeDialog`.
  - `TalemateApp.vue` also shows a `v-snackbar` (3 seconds) for `operation_done` errors.
- **Connected:** groups are built on the server (`_connected_out`, `server/worlds.py`) and drawn by `ConnectedGroup.vue`.
- **Offer rows:** R12 (area 2) strikes through every unticked draft row.

## Left to the builder

- The markup, the store shape for folds, and the parser for the modifiers.
- Whether the date and connection counts come with `list_things` or with a separate request.
- Screenshots before and after for every visible change, sent to the owner as each lands. These cover:
  - the side tree, folded and while searching;
  - a kind's page with its list in each grouping;
  - Connected's new order;
  - the error message;
  - offer rows;
  - the New stubs padding.
