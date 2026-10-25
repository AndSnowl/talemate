# Polish 1: One way to review suggestions

Date: 2026-10-25. Status: design, awaiting the owner's approval.

This is the first area of the polish pass that follows the Filing ("hubs") merge (89cb82f1). The owner's brief for the pass: "combine making the UI feel better with making the code more maintainable … inconsistency in areas that should be consistent … fixing something like that means code deduplication and UX improvements at the same time … The goal is a readable UI with clear consistent rules." The pass goes one area at a time, and each area is finished before the next is designed.

The evidence comes from:
- the owner's feedback, `feedback/2026-10-24-hubs1/feedback.txt`, which is untracked and lives in the main checkout;
- the triage of that feedback, `triage.md` in the same folder ("The UI polish pass" and "Done for round 2" lists);
- a read-through of the code (2026-10-25), summarised under "Today" below.

The mockup the owner approved is `.superpowers/brainstorm/8167-1792948114/content/suggestion-list.html`. It is not committed. The owner chose **B**: a row's placement controls go on a second line under its text.

### Where this sits in the pass

Order of the areas (*my call*; the owner said "follow the order you like the best"):
1. **This one:** one way to review suggestions.
2. Drafts edit like saved pages: other names, lifespan and "adult at" on drafts; the show-under chip on drafts; the preview that lags after a refused accept.
3. Section headers and row buttons: one header and one set of row actions.
4. Names and pickers: one entry picker that matches other names; name highlighting in every prompt box.
5. Lists, grouping and errors: where Connected goes, grouping by kind then tag, how far the tree is expanded, "not made yet", one error style.

Each later area gets its own short brainstorm and its own design. Don't build ahead into them here, except where this design says so.

## Intent

Whenever the AI suggests something, the owner reviews it the same way: tick what to keep, settle repeats, then write. Today about eight places show suggestions to tick, each built separately, and each does it a little differently.
- On a page draft, a repeat gets four choices. In "+ Add facts" on a saved page it gets only "≈ already…". In "For other pages" it's a bare caption.
- On a page draft you can regenerate and go back to an earlier version. In "+ Add facts" and Connected's "+ Add", a bad result means unticking it all and typing the prompt again. The owner: "I'd like the ability to regenerate these without having to first delete them all one by one and trying again with a prompt that was not saved."
- The prompt hides behind "Edit prompt", and the way back ("Back to the draft") is hard to find. In "+ Add facts" the prompt is a one-line box that's "very small".
- "also here" sits on the far right of its row. The owner: "controls related to fact location and whether or not to keep it in the draft should go on the left side, like the check box." After seeing the mockups, the owner chose to put them on a second line under the text.
- The dotted line between facts runs between a fact and its repeat match. That "makes it seem like the similar to section belongs to the fact below rather than the fact above".

The fix is one rule set, built once and used everywhere.

## Goals

- One **suggestion row** and one **suggestion bar** (described under "The rules"), used by every place that hands the owner AI suggestions to tick.
- **"+ Add facts", "+ Add event" and Connected's "+ Add" get the same feature set as a page draft:** a kept prompt, Regenerate, "Version n of m", Discard, and repeat choices. The owner: "it should be the same feature set."
- **On a draft page, "+ Add facts" arrives as its own small draft,** nested in the page draft and reviewed with the same bar and rows. Writing it moves its ticked facts into the page draft. Nothing reaches the world until the page draft is accepted, as today.
- **Less code:** the hand-built tick lists, the nine copies of the `.dropped` style, and the repeated `.heading` and `.match` styles collapse into the shared pieces.

## Non-goals

- Section headers and row buttons on saved pages, such as "+ in…" and the In row actions. That's area 3. This area only touches rows that carry a tick.
- Making the species and race number and other-name editors work on drafts. That's area 2.
- The entry picker behind "→ page ▾". It keeps today's picker; area 4 replaces every picker at once.
- Changing what the AI is asked or how it answers. Prompts, models and probes are untouched.

## Anti-goals

The work fails, even if it technically works, if:
- **anything is written to the world before an explicit Write or Accept,** anywhere;
- **a list behaves differently from the others** in where the tick is, how a dropped row looks, where a repeat match sits, or which repeat choices it offers, unless this design names the difference;
- **a page draft loses something it has today:** versions, picks, edits, held-by, move or copy, or selection actions on a draft fact.

## Today

All paths are under `talemate_frontend/src/components/worlds/` unless they name another folder.

The lists that hand out suggestions to tick:

| Place | Built in | Has a bar? | Repeats |
|---|---|---|---|
| Page draft facts | ThingPage.vue (FactRow `draft` + PreviewRepeats) | DraftBar: versions, Regenerate, Edit prompt, Discard, Accept | four choices |
| "+ Add facts" / "+ Add event", saved page | EntryAddFacts.vue (own rows) | none: "Write N", Discard | "≈ already…" caption only |
| "+ Add facts" on a draft page | EntryAddFacts `onDraft` → `addDraftFacts`; facts join the draft directly, unvetted | no | n/a |
| Connected "+ Add" | GroupAddForm.vue (own rows, editable name) | none: "Add N", Discard | none |
| For other pages | PreviewElsewhere.vue (own rows) | part of the page draft | bare caption |
| New names | PreviewStubs.vue | part of the page draft or the fact draft | n/a |
| File into this | inline in ThingPage.vue (~438) | part of the page draft | n/a |
| Inherited (untick to replace) | inline in ThingPage.vue (~300) | part of the page draft | n/a |
| Could move here | MoveHere.vue | part of the page draft | n/a |

On the server (`src/talemate/server/worlds.py`):
- **Page drafts** are versioned and held on the server: `_drafts`, `_new_version`, `_touch`, `_draft_out`, `handle_use_version`, `handle_discard_preview`, and `draft_key`.
- **Fact drafts** (`handle_add_facts`, `handle_add_event`, `handle_accept_facts`, `FactDraft`) are held on the client, have no versions, and keep no prompt for regenerating.
- **Group-add rows** (`handle_group_add`, `handle_accept_group_add`) are held on the client the same way.
- **Repeat choices** (new, existing, both, move) are settled only in the page-draft accept path (`_check_repeat_moves`; `settleRepeat` in draftPage.js).
- **"+ Add facts" on a draft page** (`_draft_added`) appends straight into the draft's current version.

## The rules

### The suggestion bar

Every reviewable batch of suggestions has one bar: a page draft, a fact draft, an event draft, or a group-add draft. From left to right:
- a label chip, such as "Draft", "Facts draft" or "Event draft";
- "Version n of m ▾";
- a spacer;
- Regenerate, Discard, and the primary button (Accept, or "Write N" / "Add N").

Under that row, the **prompt** is always visible in a real multi-line text box. It is several lines tall and grows with its text, so it's never "very small". Editing the prompt and pressing Regenerate makes a new version from the edited prompt. **"Edit prompt" and "Back to the draft" go away.**
- An event draft also shows its **year** beside the prompt, and the year can be edited the same way.
- The line under the bar ("Nothing is written until you accept", plus the counts) stays for page drafts. Smaller drafts can show a short count line.
- The primary button appears **again at the foot of the list** (mockup), so it's never far away.

What a page draft's prompt box edits, when the draft came from the create box with pickers: *my call* is that the bar edits the prompt text only. The create box's pickers (such as "Born (year)") stay as the draft's settings, and Regenerate reuses them. The builder decides how the create box and the bar share a prompt for a page draft. A page draft must never end up with two visible prompt boxes.

### The suggestion row

The first line holds the tick, then the text, with names linked and new stubs in the stub colour, as each list does today. The category chip and the date sit at the right, as today.
- **Placement controls go on a second line under the text** (owner, mockup B), starting at the text's left edge. These are "→ page ▾" and "+ also here" today. Any future control that moves or copies the row, or changes where it lands, goes there too.
- **Notes about the row** go on the same second line or right under it, before any repeat match: "held by …", "added here", a Connected row's tag and "shows under …".
- **A dropped (unticked) row** is struck through and dimmed in every list, from one shared style. A row that is "replaced" (Inherited) uses the same look.
- **A repeat match** hangs under its own row, indented to the text with a left rule (mockup). It shows "≈ already on **Owner**: "…"" and the repeat choices. The choice labels are **Keep new, Keep existing, Keep both, Move existing here**, as P8 settled. The dotted separator comes **after** the match, never between a row and its match.
- **Repeat choices are the same in every list that can find repeats.** Today that's page draft facts, fact drafts, event drafts and For other pages. A choice that can't apply is shown disabled with its reason, as PreviewRepeats does today. It is never hidden.
- **Row-specific editing** stays where the list needs it:
  - a page draft fact keeps its ⋯ menu and its selection actions;
  - a Connected row keeps its editable name;
  - Inherited keeps its "Replaced by" picker.

Each of these lives in the row's own slot. Area 3 tidies the buttons themselves.

### The nested fact draft on a draft page

"+ Add facts…" and "+ Add event…" on a draft page open a **fact draft nested in the page draft**: indented under the Facts heading, with its own bar and rows. It replaces today's direct append.
- Its **Write N** moves the ticked facts, and the new names they bring, into the page draft's facts, where they become ordinary draft rows.
- Its Discard drops it. Its Regenerate and versions work as anywhere else.
- Writing it changes the page draft only. Nothing reaches the world until the page draft is accepted, as today.
- How the moved facts relate to the page draft's versions is the builder's call. A new page-draft version for the addition is the natural reading, because it keeps "Version n of m" honest.

### Which lists get a bar

- **Own bar:** page draft, fact draft, event draft, group-add draft (Connected's "+ Add" and the page's top-level "+ Add"), and the nested fact draft.
- **No bar, but suggestion rows:** the sections inside a page draft. These are For other pages, New names, File into this, Inherited and Could move here. They're written by the page draft's Accept.
- **MergeDialog's tick rows:** if they're tick-to-keep rows, they use the shared row. *Builder's call* after reading it. If they're a different kind of choice, leave them.

### Settled after the builder check

All four are *my calls*, following the rules above.
- **Repeat choices on a "For other pages" row.** "Here" is the row's target page, which is where the row is going. The choices are:
  - **Keep new:** writes the row and removes the target's existing fact. Page-draft accept gets a write path for this, checked on the server like the draft's own Keep new.
  - **Keep existing:** drops the row.
  - **Keep both:** writes it alongside the existing fact.
  - **Move existing here:** shown disabled, with the reason "already on that page".
- **Repeat choices in a fact or event draft on a saved page** mean what they mean on a page draft. "Here" is the page. Move existing here moves the repeat from its owner onto this page, in the same revision as the new facts. `accept_facts` shares the page draft's repeat-settling and checking code.
- **While a nested fact draft is open,** the page draft's Accept, Regenerate and version switch are off, with the reason "write or discard the added facts first". Discard still works and takes the nested draft with it. This matches today's rule of one addition at a time with the buttons off meanwhile, and it means an accept can never silently leave added facts behind.
- **Edits are kept per version** in fact, event and group-add drafts, as in page drafts: ticks, repeat choices, edited text, and a group-add row's name and tag. "The same feature set" means switching versions brings back what the owner did on each one.
- **Small drafts are kept like page drafts:**
  - there is at most one fact or event draft per page, and one group-add draft per page and group;
  - they survive navigating away and back within the session;
  - they're dropped on reload or on switching worlds;
  - they have their own least-recently-used limit, so they can never push out a page draft.

## Code shape

*My call*, refined by the builder.
- **Frontend.** A `SuggestionBar` and a `SuggestionRow` component, plus one repeat-match block, which can be PreviewRepeats generalised.
  - `SuggestionRow` owns the tick, the dropped style, the second line (a slot for placement controls and notes), the repeat-match slot and the separator.
  - Each list supplies only what's unique to it.
  - EntryAddFacts, GroupAddForm, PreviewElsewhere, PreviewStubs, MoveHere and ThingPage's inline File-into and Inherited lists are rebuilt on these. FactRow's `draft` mode becomes a `SuggestionRow` with FactRow's content in it, or FactRow uses `SuggestionRow` inside. Builder's call.
  - The `.dropped`, `.heading` and `.match` copies go.
- **Server.** Fact drafts and group-add drafts are held and versioned the way page drafts are: in the same store, with the same version and discard handlers, and each with its own key. One mechanism replaces three: kept versions, Regenerate from the kept or edited prompt, use version, and discard.
  - The nested fact draft is keyed to its page draft, so discarding the page draft discards it too.
  - The accept handlers stay separate, because they write different things, but they share the repeat-settling code. That makes a fact draft's Keep new, Keep existing, Keep both and Move existing here behave exactly as a page draft's.
  - The accept handlers keep checking everything on the server, never trusting the client, as they do today.
- **Store** (`stores/worlds.js`). The fact-draft and group-add state moves onto the same draft shape the page draft uses (versions, current version, prompt, pending, error), so the bar binds to one shape.

## Constraints

- **Hard fork.** No upstream compatibility to keep. The code-health rules in the main spec (`2026-10-18-fantasymate-world-data-model-design.md`, "Code health") apply.
- **Tests** run through the Guix manifest (`docs/dev/local-testing.md`):
  - The plain suite must stay at 0 failures.
  - Run the browser tests by area while iterating, and the full suite with `-n 4` (never more) once at the end of a task.
  - Test ids that change must be grepped in `tests/ai` as well as `tests/e2e`.
  - AI tests (koboldcpp) are run only after asking the owner.
- **Browser tests use the fixed-reply env vars** (`TALEMATE_TEST_FIXED_GROUP_ADD` and its siblings). Versioning and Regenerate for fact and group-add drafts need to work with them, for example by serving the same fixed reply again.
- **Drafts are session-held,** as page drafts are today. Losing them on reload is acceptable.
- Use the theme tokens for colour. No hard-coded colours.

## How the owner will judge it

Walk through a fresh session, using the owner's Tsardom example:
- On a saved page, "+ Add facts". The prompt box is roomy. The result can be regenerated, an earlier version brought back, and a repeat settled with Keep new.
- On a draft page, "+ Add facts" comes back as its own small draft, which can be ticked, regenerated, then written into the draft.
- Connected's "+ Add" can be regenerated and keeps its prompt.
- In For other pages, "→ page" and "also here" sit under the text, and a repeat there gets the four choices.
- Every list looks and behaves alike: the tick, the dropped look, a match hanging under its own fact, and the separator after it.

## Left to the builder

- Component names, prop shapes, and whether FactRow wraps or is wrapped by `SuggestionRow`.
- Server draft keys, and how the fixed-reply test env vars serve a regeneration.
- How the nested fact draft's Write maps onto page-draft versions (see above).
- How the create box and the bar share a page draft's prompt, provided only one prompt box is visible.
- MergeDialog, as noted above.
- Test ids. Keep the existing ones where the element survives, so the e2e and ai suites move as little as possible.
