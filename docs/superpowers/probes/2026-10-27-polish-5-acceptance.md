# Polish 5 (lists, grouping and errors): the owner's acceptance checklist

Date: 2026-10-27. Branch: `feature/polish-5-lists`.

The tests passed on this branch:
- the plain suite: 7640 passed, 6 skipped;
- the full e2e suite: 172 passed, `-n 4`;
- the frontend checks and the build.

## What to try, and what should happen

- [ ] **Open a world.** Every kind in the side tree starts folded. Its ▸ unfolds it, and an entry's ▸ unfolds what's filed in it. A folded entry shows how many it holds ("Kerensk 1").
- [ ] **Open an entry deep in the tree** (from search or a link). Its kind and every entry above it unfold, and nothing else does. Fold it back if you like.
- [ ] **Reload the app.** The tree is folded as you left it, per world.
- [ ] **Click a kind's name** (e.g. "Places"). Its page opens and the kind unfolds. Its **"+"** opens the page with the prompt box ready to type.
- [ ] **Search the tree:**
  - a name or another name;
  - `tag:city`;
  - `in:Velikoye`, or `in:"Night Court"` for names with spaces;
  - `stub`;
  - `when:1020`.

  The tree narrows to the matches, with their homes dimmed for context. Clearing the search puts your folds back. The modifiers are listed under the box while you type.
- [ ] **A stub in the tree** is one line, in the stub style. Hovering it says "not made yet".
- [ ] **A kind's page** shows, under the prompt box, "All places · N" with **group** (where / tag / none) and **sort** (name / recent / connected / date) right after it.
  - Each row is one line: "name · in Velikoye — its summary". A stub reads "· not made yet".
  - Places start grouped by where, other kinds by tag. Your choice is kept per kind.
  - The side search filters this list too.
- [ ] **Connected** on a place with characters, places and lore filed in it:
  - groups run by kind, characters first, with Other last;
  - inside a group, characters come before lore;
  - Other's drop tip shows on its heading only.
- [ ] **An error** (for example, a selection that cuts through a link):
  - it shows once, at the top of the page, and stays in view as you scroll;
  - Copy copies it, and × closes it;
  - the same error again shows "×2";
  - the app's popup doesn't repeat it;
  - opening another world closes it.
- [ ] **A draft's offers** ("Could move here", "File into this", an unticked repeat) are dimmed, not struck through. Untick a fact that came ticked: that one is struck through.
- [ ] **New stubs:** a stub with a "same as X?" dropdown has room under its kind dropdown.

## Changed on purpose

- **The tree's siblings are sorted by name,** entries before stubs, so their order is stable.
- **Connected no longer puts the biggest group first.** Groups run by kind, then by heading.
- **The error message** sits at the top of the page and is held in view when you scroll. When you're at the top, it takes its own room rather than covering what's under it.
- **The squashed prompt box (hubs item 19)** couldn't be reproduced in the tests, on old code or new. The box now measures itself again whenever its size changes, which guards against it.
- **Inside an "In Velikoye" group,** each row still says "in Velikoye". Say if that's redundant.

## Screenshots

The before and after shots are in `/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/b21eef1e-9287-4ae6-8b4d-11b813ef0e0d/scratchpad/p5/`. Each `cmp-*` image has the before first.
