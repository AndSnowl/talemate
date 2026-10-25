# Filing ("hubs"): the owner's acceptance

The Filing plan's Task 13 had two acceptance rounds with the owner, plus fixes in between.

## Round 1 (2026-10-24)

The owner ran the app with Skyfall on a fresh root, in two worlds.

- **Verdict:** "This is overall a huge improvement over spheres, structures get built out naturally and you can following them down the chain."
- **Feedback:** `~/Projects/Web/talemate/feedback/2026-10-24-hubs1/feedback.txt`.
- **Triage:** `triage.md` in the same folder sorts the feedback into P1–P9 (before main), the UI polish pass (next), and later items.
- **World review:** `world-review.md` in the same folder looks at how the owner used it.
- **The main concern:** peer relations (Vasha and his hometown). The owner decided on "show under" per filing, plus a role picker.

P1–P9 were built under `docs/superpowers/plans/2026-10-24-fantasymate-hubs-round1.md` (SDD, rulings H1–H6), with a final review and a fix wave.

## Round 2 (2026-10-25)

The owner retested every fix. Two problems came up and were fixed, reviewed and retested:

- **Ruling H7, highlighting.** An entry's own name is now highlighted on its own page and draft, as "this page" and display only. A name whose stored form starts lowercase but has a capital ("river Vilya") now matches when written exactly as stored. A name with no capital at all never matches this way.
- **Rulings H8 and H9, "+ Add facts" / "+ Add event".** The model is now asked for new names, and they become stubs. On Skyfall this went from 0 to 11 of 12 names, with 0 false. The tag rule is copied from create-thing; long tags went from 5 of 11 to 0 of 8 (`2026-10-25-add-facts-names.md`).

**Verdict:** "Alright I've tried all the fixes, and they are all good."

## Carried forward

These are in the feedback folder's `triage.md`:

- **UI polish pass (next):**
  - layout and controls near their content;
  - editing species and race drafts;
  - reference search by other names;
  - a vetted "+ Add facts" mini-draft;
  - a "shows under" chip on drafts;
  - a "re-link this page's facts" action.
- **Later:**
  - a cascading delete;
  - fact tags, and promoting a fact to an entry;
  - other views;
  - the questions system;
  - a prompt probe on real-world names bleeding in.
