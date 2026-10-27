# Polish 4: Names and pickers

Date: 2026-10-27. Status: design, awaiting the owner's approval.

This is the fourth area of the polish pass. Areas 1 to 3 are merged (latest a82ddec3).

The evidence comes from:
- `feedback/2026-10-25-polish1/triage.md`: the "Area 4" section and "Notes added 2026-10-26, after area 3";
- `feedback/2026-10-24-hubs1/triage.md`, polish items 7 and 30;
- this conversation.

**Execution: inline (native), with screenshots after every visible change.** This is the owner's standing preference for UI work.

## The owner's standing rules

These bind every area.
1. Controls sit next to what they act on.
2. Things that look the same are one component, never a copy.
3. The screen the owner approved is the model. Change only what's listed here, and check the rest against screenshots taken before the change.
4. Move only the part that needs the room.

## Goals

1. **One entry picker that also finds other names.**
   - Every place that searches for an entry uses one picker component with one search rule:
     - "Link to…" and "+ In…";
     - "Move to…", "Copy to…" and "Held by…" (`FactRowActions`);
     - Merge into (`MergeDialog`);
     - "Same as…" (`SameThingAsk`, PreviewStubs);
     - "Write it on…" (PreviewElsewhere's retarget);
     - Re-point (`ReferenceMenu`).
   - Typing a name that is one of an entry's **other names** finds that entry. The result shows the main name in normal text, and the matching other name **small and dim underneath**, as the owner asked.
   - *My call:* the store's `referenceTargets` gains each entry's other names, so the search has them. That needs a server change: the thing listings (`list_things` and `list_heritage`) carry each entry's `aka`, and stay in step when other names change.
   - *My call:* "one picker" means **one search rule and one result row**, shared. Every place keeps its own control in its own spot (rule 3):
     - "+ In…" keeps its inline field in its row, with its "make a new stub" option;
     - the popup searches keep their popups.
     - All of them call the same search, and draw a result with the same row: the main name, plus the matching other name small and dim.
   - *My call:* the stub row's small "same as X?" dropdown picks from the AI's few candidates; it isn't a search, so it is exempt. The search beside it ("same as… 🔎") uses the shared search.
   - Each place keeps its own exclusions, such as the page itself or entries already filed.
2. **Names highlighted in every prompt box.**
   - The prompt boxes that don't highlight names today switch to the create box's highlighting input (`NameHighlightInput`):
     - Connected's "+ Add" prompt (`GroupAddForm`);
     - the "+ Add facts…" and "+ Add event…" prompts (`EntryAddFacts`);
     - an In row's "but…" exceptions;
     - the draft bar's prompt.
   - Known names show as they do in the create box, so the owner sees what the AI will be given (hubs triage item 30).
   - Where the create box sends name picks with its prompt, the other prompts send them too, where their requests already accept them. Otherwise the names are highlighted for display only. *My call:* the plan says which, prompt by prompt.
3. **A selection that contains a whole link can become a stub or a link.**
   - Example: in the Academy of Northern Lights, select "House of Solarius" where "Solarius" is already linked to the character.
   - "Make a stub" or "Link to…" on that selection works, and the longer name wins in that text.
   - Today this fails with "the selection cuts through a link". It still fails when a selection cuts *through* part of a link.
   - **No automatic tie:** the house does not get filed as "named after Solarius". The owner: "it's fine if it doesn't happen; it's up to the AI or user to build connections."
4. **Re-point offers four choices.** Re-pointing selected words, or a stub, to an entry offers:
   1. **Add as another name** (today's): the words stay, link to the entry, and become one of its other names.
   2. **Use the entry's name in the text** (today's "rename to"): the words become one of the entry's names, its main name or any other name.
   3. **Rename the entry to these words** (new): the entry's main name becomes the selected words. *My call:* its old main name is kept as an other name, so nothing that mentions it breaks, and the change shows in the same history as any rename.
   4. **Link only** (today's): the words, or the stub, link to the entry, and the entry learns no new name. The owner chose to keep it.
   - The "added as another name" note that pops up after a re-point goes away. *My call:* check the other notes after an action for the same kind of chatter, and list any found in the plan for the owner to strike.
5. **One hover card for a stub.**
   - Today "Stubs this entry named" (`NamedStubs`) draws its names as bare links, so hovering gives a thinner card with no "Re-point…". A stub name in a fact gives the full card: tag, kind, mentions and "Re-point…".
   - Every place that shows a stub name uses the fact version: one name-plus-card component, `LinkedText`'s stub segment and `StubCard`.
   - *My call:* the entry page's `named_stubs` payload carries each stub's tag, kind, mentions and whether it's ignored, so the card is full without the Stubs page having been opened.
   - The builder sweeps every place a stub name appears (NamedStubs, the Stubs page, Connected rows, In rows, the tree, previews) and lists each in the plan. The only difference a place may keep is whether re-pointing applies there.
6. **Bug: re-pointing to an entry that was deleted and remade fails.** The error is "Error during repoint_stub: fact references unknown or removed thing: …".
   - **Likely cause** (*my reading*, to be confirmed with a failing test first): `repoint_stub` rewrites facts whose text still holds a link to the deleted entry. The store's reference check (`world/store.py`, `_check_refs`) refuses any fact that links to a removed thing.
   - **Fix:** when an action rewrites a fact's text, a link to a removed thing turns into its plain words. That is the same rule P5 gave selections ("a link to a deleted entry acts as plain text"). It applies to every rewrite path that hits it, not just re-point.

## Non-goals

- **Area 5:** Connected's grouping, the tree's depth, "not made yet", errors, the strike-through on offers, and the "New stubs" padding.
- **Later features:** expanding race and mix stubs, "died", changing an entry's kind, rethinking delete as a cascade.
- **No change to what the AI is asked,** beyond prompts gaining the name picks their request already supports.

## Anti-goals

The work fails, even if it technically works, if:
- a search finds an entry by its other name but doesn't show which name matched;
- a picker anywhere still searches by main name only;
- a stub name anywhere shows a different card from a fact's;
- a re-point or rename silently loses a name that mentions used.

## Today (from a code read, 2026-10-25 and 2026-10-27)

- **Pickers:** about six hand-built autocompletes over `referenceTargets` (`{id, name, kind, stub}`):
  - `EntryIn.vue` (~209);
  - `FactRowActions.vue` (~155-159);
  - `MergeDialog.vue` (~129);
  - `SameThingAsk.vue` (~142);
  - `ReferenceMenu` / `searchReferences` (`nameHighlights.js` ~406).

  None of them match other names.
- **Highlighting:** `NameHighlightInput` is used only by CreateBox, ThingFactForm, NewSceneDialog and ReferenceMenu.
- **Stub cards:** `LinkedText.vue` draws a stub segment with a hover `StubCard`, and adds "Re-point…" only when its `repoint` prop is set. `NamedStubs.vue` draws `LinkedText` without `repoint`, from bare `{text, ref, stub}` segments.
- **Re-point:** `handle_repoint_stub` (`server/worlds.py`), `worldplay/repoint.py` (`repoint_stub`, `plan_repoint`), `NameModeMenu.vue`, `StubRepointButton.vue`.

## Left to the builder

- The picker component's name and its props. It may grow out of `ReferenceMenu`.
- The prompt-by-prompt list for goal 2, and the sweep list for goal 5.
- The repro test for goal 6, which comes before the fix.
- Screenshots before and after for every visible change, sent to the owner as each lands.
