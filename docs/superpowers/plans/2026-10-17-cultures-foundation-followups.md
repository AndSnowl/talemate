# Cultures foundation: follow-ups

This note goes with the foundation plan (`2026-10-17-cultures-foundation.md`) and records what is still open after it was built on `feature/cultures-and-languages`. The frontend could only be checked by a successful build and by reading the code, because no browser runs on the build machine. The checks below therefore haven't been done yet.

## Manual checks to run in the browser

**Setup**
1. Open the World Editor. The **Cultures** tab is right after Suggestions.
2. Open a scene with no Shared World. The tab shows the "link a Shared World" prompt, and its button opens Scene → Shared World.

**Import and re-import**
3. Link a Shared World, then import `tests/cultures/data/taelrik.culture.json` with **Import culture**.
   - The preview counts match the file.
   - After import, the culture appears in the drawer.
4. Re-import the same file.
   - The dialog says "Updating".
   - It lists anything you edited in Talemate under "Will be replaced".
5. Import a broken `.json`. A red alert shows the error, and the dialog stays open.

**Culture and Language tabs**
6. Edit text on the Culture and Language tabs, leave each field, and reload the scene. The edits are still there.
7. Click **Keep** or **Drop** on a play addition, then edit a custom. The Keep or Drop is not undone.

**Glossary, dictionary and phrases**
8. On the Glossary tab:
   - The filter counts are correct.
   - **Looks right** moves an entry to Reviewed and selects the next unreviewed one.
   - Changing an entry's language to "No language yet" moves it to **Unassigned names**.
9. Open **Pick another** on an entry the AI named and click "Roll new". The new candidates appear only in that menu.
10. On the Dictionary tab, edit a word and leave the field. On the Phrases tab, add, edit and delete a phrase. Reload the scene: all the changes are still there.

**Generators**
11. On the Generators tab, click **Roll** on two cards. Each card shows only its own names.
12. Edit a pattern, then click **Roll** straight away. You get names back.
13. Type an invalid reject rule, e.g. `[`. You see a readable error, and nothing hangs.

**Places & regions**
14. Build this tree: The Taelrik Reach (country) → Birch Coast (region, Elsiri 90 / Taelrik 10) → Ilsara (village).
    - Birch Coast reads "about 9 in 10 Elsiri… Most also speak Taelrik, the language of The Taelrik Reach."
    - Ilsara inherits the same mix and the same sentence.
15. Drag a culture-share slider and release it. The shares add back up to 100.
16. Try to set The Taelrik Reach's parent to Ilsara. Ilsara isn't offered.
17. Delete a place that has children. You're asked where the children go, and they move there.

**Shared world and the skill**
18. Open two scenes that share the same world in two browser tabs. Edit in one, then edit in the other. Neither tab undoes the other's changes.
19. Design a small culture with the `culture-design` skill. Import it, export it, re-import it, and check nothing you made is lost.

## Known gaps left for later plans

- A save the server refuses (such as an invalid reject rule) leaves the field looking saved. The next update from the server reverts it. The error status is shown.
- A culture file that already contains an invalid generator blocks every edit to that culture until the generator is fixed.
- On the Culture tab, a play addition that arrives while you're mid-edit gets an empty edit box. Re-loading the culture's data also overwrites addition text you're still typing. This matters once plan 2 starts creating additions during play.
- Disk errors other than validation errors, such as a permission error, aren't caught by most write actions, so a spinner can hang.
- There's no button to delete a culture. The server action exists.
- The import preview shows place counts but not place names, and has no language-level chip.
- Export doesn't include unassigned names. The skill can read `glossary.json` from the world folder instead.
- The Cultures badge shows 0 until the tab has been opened once.
- Re-importing an older file can bring back an addition you dropped.
- The NLTK `punkt_tab` data is missing on the build machine. It causes 141 test failures elsewhere in the suite, none of them in cultures code.
