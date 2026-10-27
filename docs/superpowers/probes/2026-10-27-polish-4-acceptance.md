# Polish 4 (names and pickers): the owner's acceptance checklist

Date: 2026-10-27. Branch: `feature/polish-4-names`.

The tests passed on this branch:
- the plain suite: 7633 passed, 6 skipped;
- the full e2e suite: 161 passed, `-n 4`;
- the frontend checks and the build.

## What to try, and what should happen

- [ ] **Search by another name.** Give an entry another name (for example the Owl-folk, "Moscavian Owls"). Then type that name into each picker:
  - a fact's selection → "Link to an entry… 🔎";
  - "+ In…" (and "Within" when editing a person's filing);
  - a fact's ⋯ → Move to…, Copy to…, Held by…;
  - Merge into…;
  - a draft stub's "same as… 🔎".

  Each one finds the entry. Its own name shows normally, with "Moscavian Owls" small and dim underneath. "+ In…" no longer offers "Make a stub 'Moscavian Owls'", since an entry already goes by that name.
- [ ] **House of Solarius.** In a fact where "Solarius" is already a link, select "House of Solarius", then use "Make a stub" or "Link to…". It works, and the whole phrase becomes one link: the longer name wins. Solarius isn't filed under or tied to the house. A selection that cuts through part of a link is still refused.
- [ ] **Re-point offers four choices**, in this order:
  1. "Add as another name";
  2. "Use the entry's name";
  3. "Rename the entry to these words";
  4. "Link only".

  Pick "Rename the entry to these words": the entry takes the words as its name, and keeps its old name as another name. If another entry already goes by those words, it's refused with "X is already the name of Y". After any re-point, no "Added as another name" note pops up.
- [ ] **One stub card.** Hover a name in "Stubs this entry named", or a stub in Connected: it shows the same card as a stub in a fact, with tag, kind, mentions, Expand, Ignore and "Re-point…". Here "Re-point…" moves the whole stub, as on the Stubs page.
- [ ] **Names in every prompt.** Type a known name into a "but…", Connected's "+ Add", "+ Add facts…" or a draft's prompt: it highlights as in the create box, and you can re-pick it from its hover.
- [ ] **The re-point bug.** Delete an entry that a fact links, remake it, then re-point a stub from that fact to it. It works now, and the old link reads as plain words.

## Changed on purpose

- **"Link to…" results** show the kind on a small line under the name ("place · stub"), like the other pickers, instead of chips.
- **The prompt boxes** (but…, + Add, + Add facts…, the draft prompt) look like the create box's: the label sits above the box, and the text is a little smaller.
- **Clicking a stub's name in Connected** now does what it does in a fact (Expand), not open its page.
- **The notes "Added as another name: …"** after a link, and "X is now also known as …" after a stub re-point, are gone.
- **Other short notes left as they were, for you to strike:** Merge's "now also known as …", "Copied to X", and "Moved to X".
- **"Rename the entry to these words" is off on a draft.** Like "Use the entry's name", it waits until the draft is accepted.

## Screenshots

The before and after shots are in `/tmp/claude-1000/-home-skeleton-Projects-Web-talemate/b21eef1e-9287-4ae6-8b4d-11b813ef0e0d/scratchpad/p4/`. Each `cmp-*` image has the before on the left and the after on the right.
