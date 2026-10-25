# Probe: untagged stubs tagged with their kind's name (2026-10-24)

**Why.** The Task 2 review found that lore and event entries in Test2 (The Blinding, Corners of the Earth, The First Consolidation) came back untagged. The model wrote the kind's name as the tag ("lore", "event"), and `clean_tag` drops kind names without saying so.

**The setup.**
- **Model:** Skyfall-31B-v4.2-i1-Q4_K_M, at http://192.168.0.5:5001, one call at a time, with the owner's standing permission.
- **Harness:** `scripts/dev/probe_tags_kind_names.py`.
- **Labels:** `raw/2026-10-24-tags-kind-names-labels.json`, committed before any call (5f1080b4).
- **Raw output:** `raw/2026-10-24-tags-kind-names.json`, runs `before` and `after`.
- **The world:** a fresh scratch world, present year 1000, with three entries: the Tsardom (nation), Velikoye (capital) and the Academy.
- **The stubs:** six untagged stubs, each named in one fact of those entries:
  - lore: Boyar Council, Rite of First Flight, Corners of the Earth;
  - event: The Blinding, First Consolidation, Siege of Velikoye.
- **The calls:** each stub was expanded through the app's own `create.preview_thing`, with its suggested prompt (as Expand starts the box) and `ask_same=False`. Prose was skipped; it asks nothing about the tag. There were 2 versions per stub, so 12 calls per run.

**The wording added** to the create-thing tag rule, right after the existing rule:

> The tag is never the kind's own name (lore, event, place, …): say what sort of {{ kind }} it is, such as custom, law, battle, festival.

## Results

In the tables, "raw" is the reply's `"tag"` as written, and "stored" is the tag after `clean_tag`.

| Stub | Before: raw | Before: stored | After: raw | After: stored |
|---|---|---|---|---|
| Boyar Council v1 | institution | institution | institution | institution |
| Boyar Council v2 | institution | institution | institution | institution |
| Rite of First Flight v1 | custom | custom | custom | custom |
| Rite of First Flight v2 | custom | custom | custom | custom |
| Corners of the Earth v1 | doctrine | doctrine | geographic doctrine | geographic doctrine |
| Corners of the Earth v2 | geography | geography | cartographic doctrine | cartographic doctrine |
| The Blinding v1 | **event, historical** | historical | **event, transformation** | transformation |
| The Blinding v2 | **event** | **none** | **event** | **none** |
| First Consolidation v1 | **event** | **none** | unification | unification |
| First Consolidation v2 | **event, political** | political | unification event | unification event |
| Siege of Velikoye v1 | siege | siege | siege, battle | siege |
| Siege of Velikoye v2 | siege | siege | siege | siege |

**Counts** (out of 6 per kind):

| | Before | After |
|---|---|---|
| Lore whose raw tag starts with the kind's name | 0 | 0 |
| Event whose raw tag starts with the kind's name | **4** | **2** |
| Event stored untagged | 2 | 1 |
| Event stored with a vague second part ("historical", "political") | 2 | 0 |
| Stored tag in my hand-labelled "fits" list, lore | 6 | 4 |
| Stored tag in my hand-labelled "fits" list, event | 2 | 4 |
| Stored tag in my hand-labelled "fits" list, all | 8 of 12 | 8 of 12 |

**How to read these numbers:**
- **Lore** did not have the kind-name problem here, in either run.
- **Corners of the Earth** dropped from 2 fits to 0 after the change only because "geographic doctrine" and "cartographic doctrine" are not on my list. Read by hand, they fit at least as well as "doctrine" and "geography".
- **Event** is where the problem was: 4 of 6 replies wrote "event". After the line, 2 of 6 did, all from The Blinding. The Blinding v2 is still stored untagged.
- **"unification event"** is kept, since only an exact kind name is dropped. It still leans on the kind's word.

**The verdict.** The kind-name problem is real for events and was absent for lore here. The line halves it (4 → 2 of 6) but does not remove it, and The Blinding still hit it twice. 12 calls per run are too few to measure anything finer. The line is kept.

**Not probed:**
- species, race and mix tags (the rule now reaches them, in the generic wording);
- the "tag" on the species and race names items.

**Logging.** `clean_tag` now logs each part it drops as `create.tag_dropped` at debug, with the value and the entry's kind. A draft left untagged now shows the reason in the log.
