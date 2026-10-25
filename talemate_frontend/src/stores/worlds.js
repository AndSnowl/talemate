// The fantasymate world screens' state (Worlds home, World tab, thing
// pages, create box), kept in step with the backend's `worlds` websocket
// router (src/talemate/server/worlds.py).
//
// Actions send `{type: 'worlds', action, ...}` through the function given
// to `connect`. Replies come back as `{type: 'worlds', action, data}`;
// TalemateApp registers `handleMessage` as one websocket message handler,
// and it fills the state. Errors arrive as `operation_done` with
// `error.message` (and as `preview_failed`/`prose_failed`).
//
// The backend holds one open world per connection and closes it when the
// connection goes, so a disconnect forgets the open world. Opening another
// world cancels a running draft (or scene plan) without any reply, and
// drops the session's drafts, so opening (or creating) a world clears the
// draft, the scene setup and every spinner itself.
//
// The open world's `now` (where creation dates things) moves with its
// scenes, so every scene listing, and every moved scene, asks for it again
// (`get_present`).
//
// Scenes: the new-scene dialog and "continue in a new scene" share one
// setup step (`setupRequest`, `sceneSetup`). A started scene's reply lands
// in `startedScene`; TalemateApp loads its `target` as Load Scene does.
//
// Deleting a thing: `requestDelete` asks for its references
// (`thing_references`); the reply lands in `deleteCheck`, which the
// confirmation dialog shows. `confirmDelete` deletes it; `thing_deleted`
// closes the dialog and the thing page: a race or mix goes back to its
// species page (`pageAfterDelete`), anything else to the kind list.
//
// Renaming: `renameThing` sends `set_field` "name", correcting the name
// value in effect at the viewing date (`currentNameFrom`) rather than
// adding a dated one; the reply refreshes the kind's list (and so the
// heritage list), so cards and links show the new name.
//
// Prose: `regenerateProse()` rewrites every section, and
// `regenerateProse(section)` just that one (`proseRegeneratingSection`).
//
// Heritage: every listing of a species, race or mix asks for
// `list_heritage` too, so `heritage` (each with its `species_ids`) stays in
// step for the character page's heritage links. `overrideFact` adds an own
// fact replacing an inherited one; it answers like any edit.
//
// Creating with a heritage: the create box's picker takes one or two
// parents. Two parents always go through a mix: `findMix` asks
// `find_mix`, and its reply (`mixFound`) says whether that mix exists. With
// none, the box drafts the mix first: `acceptPreview(changes, {open:
// false})` accepts it without opening its page and leaves the new thing in
// `accepted`, so the character's box can carry on with it. A draft lists
// the inherited facts it was made with (`preview.inherited`);
// `setPreviewOverride` marks one as replaced by one of the draft's own
// facts before accepting.
//
// Stubs (names mentioned but not made yet): `stubs` is `list_stubs`'s list,
// ignored ones included (the Stubs tab filters them), asked for again
// whenever an edit, an accept, a delete or a started scene may have made,
// filled or re-counted one. `ignoreStub` and `changeStubKind` answer with
// the stub's page; the open page, if it's another thing, is fetched again,
// since its links to the stub change with it. `expandStub` leaves the page
// for the stub's kind, whose create box then expands it (`expanding`):
// the draft carries the stub's id, and accepting fills the stub in place.
// Expanding over an unaccepted draft asks first (`expandAsk`, answered
// by `confirmExpand`, which discards it, or `keepPreview`). Expanding also
// asks for `stub_suggestion`, the create box's starting prompt and the
// mention context (`stubSuggestion`). A draft of a new
// thing named like a stub of its kind (`matching_stub_id`) can be accepted
// into that stub instead (`acceptPreview(changes, {intoStub})`).
// Other names: `setAka` writes the whole `aka` list (`set_field` "aka");
// `akaAdded`, `akaChanged`, `akaEveryday` and `akaRemoved` make the list.
// `addOtherName` teaches any thing another name (the owner re-picked a
// name for it): it fetches the thing, then writes its `aka` with the name
// added, as common and not everyday, unless it already has that name.
//
// Names in what the owner writes: `match_names` replies keep the
// `unknown` phrases too (`unknownFor`). Fact edits and previews take
// `picks` and `newNames` (see nameHighlights.js `linkPayload`), and a
// fact form's `spans` (its existing links, by position), sent only when
// there are any. `makeStub` makes a stub of a phrase in a fact, and
// `repointRef` points one reference of a fact at another thing; neither
// touches the rest of the fact. Selected words of a fact (the selection
// menu) are `makeStubFromText` ("Make a stub", and "… and expand now":
// `stubExpandAfter` opens its box once it's made) and `linkText`, by
// their UTF-16 offsets in its rendered text (ruling F18). `linkText` and
// `repointRef` take the owner's mode (P4, ruling H2, `NameModeMenu`): the
// words linked as written, kept and taught as another name (the reply's
// `aka_added`, shown as a note), or `useName`, one of the target's names
// in their place. `referenceTargets` is what Add reference searches: every entry and
// live stub.
//
// Filing and tags (the entry page, mockup v3): `addFiling`, `editFiling`
// ("End this" is an `until`), `removeFiling` and `addException` edit the
// open page's "In" rows; `setTag` gives any entry its tag (the page's own
// chip, or a Connected row dragged to another group, which may be another
// thing: its reply refreshes the open page); `listTags` keeps `tags`
// (`list_tags`) for the picker and the Tags tab, whose `renameTag` and
// `mergeTag` retag every entry (a filing's `show_under` too); `listRoles`
// keeps `roles` (`list_roles`), the roles in use, for the role picker. A group's "✎ Synopsis" (`groupSynopsis`)
// and "+ Add" (`groupAdd`, then `acceptGroupAdd` or `discardGroupAdd`)
// are kept per page and tag (`groupKey`) in `synopses` and `groupAdds`.
// "+ Add facts…" and "+ Add event…" (`addFacts`, `addEvent`) draft a few
// facts into `factDraft`, which `acceptFacts` writes as the owner left it.
//
// History (the thing page's back arrow): `section` is the World tab's
// open section (a kind's list, or 'stubs'), and a page is `{section,
// thingId, at}` (`thingId` null for the section itself). Opening a page
// (`openThing`: a link, a card, an "In" or Connected row, a reference; a
// section from the side list, `showSection`; an accepted preview's page)
// pushes the page left onto `history`, unless it's the same page (a thing
// as of another date is the same page). `goBack` pops it without pushing,
// skipping things deleted (or re-pointed away) since (`gone`); with
// nothing left it shows the section. Each entry keeps the date its page
// was viewed as of, so back returns to it as it was. A world switch starts
// the history afresh.
//
// Re-pointing a stub: `repointStub` sends `repoint_stub` (with `use_name`
// for the hard re-point, one of the target's names fetched first:
// `fetchNames`, `namesOf`); the reply (in `stubRepointed`, for the Stubs
// page's note) forgets the stub, and a page on the stub opens the target
// instead.
//
// Drafts (spec "The draft page"): Create asks `preview_thing`, and its
// reply is the draft (`draft`: `{key, version, versions, page, base,
// edited}`): `page` the page it will be, `base` the server's copy of what
// accept takes, `edited` that as the owner left it (the `preview`
// getter). The owner's edits (`editDraft`, `editPreview`) stay here until
// `acceptPreview` sends them with the draft's key. Regenerate, and Create
// after "Edit prompt" (`editPrompt`: the box shows its form, the draft
// kept), send the key back for a new version; "Version n of m ▾"
// (`useVersion`) restores one with `use_version`. The server gives back
// its own copy, so what the owner left on each version is kept for the
// session (`draftEdits`, key -> version -> `{base, edited}`) and rebased
// onto it (draftPage.js `rebaseDraft`); when the server drops its oldest
// version (five kept) the ones kept move down with it. "+ Add facts…",
// "+ Add event…" (`addDraftFacts`, one at a time: `adding`) and a
// selection (`draftSelection`) change the server's copy of the current
// version; each reply is rebased the same way. A reply for another
// draft, or one the server says came too late (another version current
// meanwhile), adds nothing. Discard (`discardPreview`) drops every
// version on the server too.
//
// Curation: a draft is edited in place before it's accepted
// (`editPreview('create', changes)`): its own facts' ticks, the elsewhere
// facts (ticks, categories, a stub row's "same as X?"), the Could move
// here rows. An accept sends the draft as the owner left it, ticks and
// all. The answer to "Same thing?" goes with the accept
// (`acceptPreview(..., {sameTargetId})`). Every
// accept's `notes` (what was left out, and why) land in `notes` for the
// World tab to show, as do a move's, a merge's and a date pick's. A merge
// (`previewMerge`, `acceptMerge`) keeps its preview in `merge`; the merged
// entry's page opens once it's done. `moveFact`, `setHeldBy` and
// `pickDate` edit a fact where its page shows it (`copyFact`, "Copy to…",
// keeps it there too); `getCuration` and
// `setCuration` read and write the world's curation knobs (`curation`).
//
// No `@/` imports: the node checks (checks/worlds.check.mjs) load this file.

import { defineStore } from 'pinia';

import { formatDate } from '../components/worlds/worldDates.js';
import { groupKey } from '../components/worlds/entryPage.js';
import { acceptable, nameKey, previewSegments, rebaseDraft } from '../components/worlds/draftPage.js';
import { HERITAGE_KINDS, LISTED_KINDS, overrideCategory } from '../components/worlds/worldKinds.js';

const ROUTER = 'worlds';

// as talemate.worldplay.persistence.world_target
const TARGET_PREFIX = 'world://';

// The `load_scene` path of a world scene.
export function worldTarget(worldPath, sceneId) {
    return `${TARGET_PREFIX}${worldPath}|${sceneId}`;
}

// Whether two wire dates (or nulls) are the same date; labels don't count.
function sameDate(a, b) {
    if (!a || !b) {
        return !a && !b;
    }
    return a.instant === b.instant && a.precision === b.precision;
}

// `{worldPath, sceneId}` of a world scene's path, or null for any other.
export function parseWorldTarget(path) {
    if (typeof path !== 'string' || !path.startsWith(TARGET_PREFIX)) {
        return null;
    }
    const rest = path.slice(TARGET_PREFIX.length);
    const sep = rest.lastIndexOf('|');
    if (sep <= 0 || sep === rest.length - 1) {
        return null;
    }
    return { worldPath: rest.slice(0, sep), sceneId: rest.slice(sep + 1) };
}

// Whether two parent pairs are the same two ids, in either order.
export function sameParents(a, b) {
    return a.length === 2 && b.length === 2 && ((a[0] === b[0] && a[1] === b[1]) || (a[0] === b[1] && a[1] === b[0]));
}

// The heritage a prompt's `match_names` matches name, for pre-filling the
// picker: the first species, race or mix named, preferring a race or mix
// over its own species ("a Snowy owl-folk" is Snowy). Null if none.
export function heritageFromMatches(matches, heritage) {
    const byId = new Map(heritage.map((item) => [item.id, item]));
    const named = [];
    for (const match of matches) {
        const found = match.candidates.find((candidate) => byId.has(candidate.id));
        if (found && !named.includes(found.id)) {
            named.push(found.id);
        }
    }
    const ancestors = new Set(
        named.flatMap((id) => byId.get(id).species_ids.filter((speciesId) => speciesId !== id)),
    );
    return named.find((id) => !ancestors.has(id)) || null;
}

// Which of a preview's own facts replaces the inherited fact `row` when the
// owner marks it: the first of the category an override of it would take,
// else the first own fact (-1 when there are none).
export function defaultOverrideIndex(preview, row) {
    const category = overrideCategory(preview.kind, row.category);
    const index = preview.facts.findIndex((fact) => fact.category === category);
    return index >= 0 ? index : preview.facts.length ? 0 : -1;
}

// The `valid_from` of `timeline`'s name value in effect at `at` (null for
// the latest), as a wire date without its label; null for an undated one.
// Renaming corrects that value in place.
export function currentNameFrom(timeline, at) {
    // the timeline runs in date order, undated first: the last name value
    // on or before `at` is the one in effect
    const until = at ? at.instant : Infinity;
    let from = null;
    for (const entry of timeline || []) {
        if (entry.change === 'field' && entry.field === 'name' && (!entry.date || entry.date.instant <= until)) {
            from = entry.date ? { instant: entry.date.instant, precision: entry.date.precision } : null;
        }
    }
    return from;
}

// A heritage thing's species id: itself for a species, else the first of
// its `species_ids` that isn't itself (null if unknown).
function speciesOf(heritage, id) {
    const entry = heritage.find((item) => item.id === id);
    if (!entry) {
        return null;
    }
    return entry.kind === 'species' ? entry.id : entry.species_ids.find((speciesId) => speciesId !== id) || null;
}

// The page to open once `thing` is deleted: a race's species; a mix's
// species page it was opened from (`openedFrom`), else its first parent's
// species. Null (back to the kind list) for any other kind.
export function pageAfterDelete(thing, heritage, openedFrom) {
    if (thing?.kind === 'race') {
        return thing.fields?.species || null;
    }
    if (thing?.kind === 'mix') {
        const mixSpecies = heritage.find((item) => item.id === thing.id)?.species_ids || [];
        if (openedFrom && mixSpecies.includes(openedFrom)) {
            return openedFrom;
        }
        const first = (thing.fields?.parents || [])[0];
        return first ? speciesOf(heritage, first) : null;
    }
    return null;
}

// The note on a link that taught its target other names (P4's "add as
// another name": `link_text`, `repoint_ref`).
export function otherNamesNote(names) {
    return `Added as another name: ${names.join(', ')}`;
}

// The Stubs page's (and the target page's) note on a `stubRepointed`.
export function repointedNote(done) {
    const links = `${done.links} link${done.links === 1 ? '' : 's'}`;
    const facts = done.factsMoved ? `, which took ${done.factsMoved} fact${done.factsMoved === 1 ? '' : 's'} from it` : '';
    const names = done.akaAdded.length ? ` ${done.target.name} is now also known as ${done.akaAdded.join(', ')}.` : '';
    const notes = done.notes.map((note) => ` ${note}.`).join('');
    return `${done.stubName}: ${links} now point to ${done.target.name}${facts}.${names}${notes}`;
}

// the most pages the back arrow remembers
const HISTORY_CAP = 50;

// Whether two pages (`{section, thingId, at}`) are the same: the same
// thing, whatever its date, or the same section with no thing open.
export function samePage(a, b) {
    if (!a || !b) {
        return false;
    }
    if (a.thingId || b.thingId) {
        return a.thingId === b.thingId;
    }
    return a.section === b.section;
}

// `history` once `current` is left for `next`: `current` pushed, unless
// `next` is the same page or `current` is on top already; the oldest
// dropped past `cap`. Unchanged, it's the same array.
export function historyPushed(history, current, next, cap = HISTORY_CAP) {
    if (!current || samePage(current, next) || samePage(history.at(-1), current)) {
        return history;
    }
    return [...history, current].slice(-cap);
}

// `{page, history}`: the page back goes to (null when none is left) and
// the history after it, skipping pages whose thing `isGone`.
export function historyBack(history, isGone) {
    const rest = [...history];
    while (rest.length) {
        const page = rest.pop();
        if (!(page.thingId && isGone(page.thingId))) {
            return { page, history: rest };
        }
    }
    return { page: null, history: [] };
}

// An `aka` entry as the backend keeps it, `everyday` always set.
function akaEntry(entry) {
    return { name: entry.name, tag: entry.tag === 'proper' ? 'proper' : 'common', everyday: !!entry.everyday };
}

function cleanName(name) {
    return (name || '').split(/\s+/).filter(Boolean).join(' ');
}

// `aka` with another name (tagged `tag`, not everyday); unchanged for a
// blank name, or one it (or the main name `mainName`) already has.
export function akaAdded(aka, name, tag = 'common', mainName = '') {
    const clean = cleanName(name);
    const taken = [mainName, ...aka.map((entry) => entry.name)].map((n) => cleanName(n).toLowerCase());
    if (!clean || taken.includes(clean.toLowerCase())) {
        return aka;
    }
    return [...aka.map(akaEntry), { name: clean, tag, everyday: false }];
}

// `aka` with entry `index` renamed and/or retagged (`{name?, tag?}`); a
// name tagged proper is no longer the everyday one. A blank name, or one
// another entry has, leaves it unchanged.
export function akaChanged(aka, index, changes) {
    const entries = aka.map(akaEntry);
    const entry = { ...entries[index] };
    if ('name' in changes) {
        const clean = cleanName(changes.name);
        const taken = entries.some((other, i) => i !== index && other.name.toLowerCase() === clean.toLowerCase());
        if (!clean || taken) {
            return aka;
        }
        entry.name = clean;
    }
    if ('tag' in changes) {
        entry.tag = changes.tag;
        if (entry.tag !== 'common') {
            entry.everyday = false;
        }
    }
    entries[index] = entry;
    return entries;
}

// `aka` with entry `index` made the everyday name (only a common one can
// be, and only one is), or no longer it if it was.
export function akaEveryday(aka, index) {
    const target = akaEntry(aka[index]);
    const on = !target.everyday && target.tag === 'common';
    return aka.map((entry, i) => ({ ...akaEntry(entry), everyday: on && i === index }));
}

export function akaRemoved(aka, index) {
    return aka.filter((_entry, i) => i !== index).map(akaEntry);
}

// a draft's texts, its new names marked (the setup cards use it too)
export { nameKey, previewSegments };

// replies to these clear their own spinner (`pending[action]`)
const EDIT_ACTIONS = ['add_fact', 'correct_fact', 'end_fact', 'remove_fact', 'set_field', 'override_fact', 'make_stub', 'repoint_ref', 'set_held_by'];

// filing and tag edits: each answers with the thing it changed, which may
// not be the open page (a Connected row retagged by a drag)
const FILING_EDITS = ['add_filing', 'edit_filing', 'remove_filing', 'add_exception', 'set_tag', 'accept_group_add', 'accept_facts'];

// The facts a thing page lists under Facts: not its summary, which heads
// the page, nor the "but…" exceptions its "In" rows show.
export function listedFacts(thing) {
    const exceptions = new Set((thing?.in || []).flatMap((row) => row.exceptions.map((e) => e.fact_id)));
    return (thing?.facts || []).filter((fact) => !exceptions.has(fact.fact_id) && !fact.summary);
}

// A wire date as a request takes it (no label), or null.
export function dateIn(date) {
    return date ? { instant: date.instant, precision: date.precision } : null;
}

// --- curation -----------------------------------------------------------------

function plural(count, one, many = `${one}s`) {
    return `${count} ${count === 1 ? one : many}`;
}

// What accepting a preview would write: `{facts, elsewhere, stubs,
// movedIn}` -- its own facts ticked, the elsewhere facts ticked, the new
// stubs it'd make (its new names, the new entries a ticked elsewhere fact
// goes onto; not one the owner marked as some thing already), and the
// facts moving in, ticked.
export function previewCounts(preview) {
    const ticked = (rows) => (rows || []).filter((row) => row.ticked !== false);
    const elsewhere = ticked(preview?.elsewhere);
    const stubs = new Set();
    for (const row of preview?.new_names || []) {
        if (!row.same_target_id) {
            stubs.add(nameKey(row.name));
        }
    }
    for (const row of elsewhere) {
        if (row.new && !row.new.same_target_id) {
            stubs.add(nameKey(row.new.name));
        }
    }
    return {
        facts: ticked(preview?.facts).length,
        elsewhere: elsewhere.length,
        stubs: stubs.size,
        movedIn: (preview?.move_here || []).filter((row) => row.ticked).length,
        // "Keep new": the world's facts these replace, removed on accept
        replaced: ticked(preview?.facts).filter((fact) => fact.replaces_repeat && fact.repeat_of).length,
    };
}

// The Accept line: "writes 3 facts here, 4 elsewhere, 1 new stub"
// (`onto`: the entry the owner said it is, "writes 3 facts onto
// Ashenmere").
export function countsLine(counts, onto = null) {
    const parts = [`writes ${plural(counts.facts, 'fact')} ${onto ? `onto ${onto}` : 'here'}`];
    if (counts.elsewhere) {
        parts.push(`${counts.elsewhere} elsewhere`);
    }
    if (counts.stubs) {
        parts.push(plural(counts.stubs, 'new stub'));
    }
    if (counts.movedIn) {
        parts.push(`moves ${counts.movedIn} in`);
    }
    if (counts.replaced) {
        parts.push(`replaces ${counts.replaced}`);
    }
    return parts.join(', ');
}

// A preview's elsewhere facts grouped by the entry they're for, in the
// order each entry first comes: `{key, name, targetId, new, rows: [index]}`
// (`new` the first row's new name, for an entry not made yet).
export function elsewhereGroups(rows) {
    const groups = [];
    const byKey = new Map();
    (rows || []).forEach((row, index) => {
        const key = row.target_id || `new:${nameKey(row.new?.name || row.target_name)}`;
        let group = byKey.get(key);
        if (!group) {
            group = { key, name: row.target_name, targetId: row.target_id || null, new: row.new || null, rows: [] };
            byKey.set(key, group);
            groups.push(group);
        }
        group.rows.push(index);
    });
    return groups;
}

// `rows` with those at `indices` ticked (or not); the rest as they are.
export function rowsTicked(rows, indices, ticked) {
    const picked = new Set(indices);
    return (rows || []).map((row, index) => (picked.has(index) ? { ...row, ticked } : row));
}

// The "Could move here" rows the owner set (`moveIn`, a draft's
// `move_here`, from MoveHere) and the draft's own facts to go with them
// (ruling C24's other half): an own fact repeating a move the owner ticks
// (its `repeat_of.fact_id`) is unticked, marked `untickedByMove`, so the
// claim isn't written twice; unticking the move ticks it again. A fact the
// owner unticked themselves is left as it is. `{move_here, facts}`.
export function moveInEdit(preview, moveIn) {
    const ticked = new Set((moveIn || []).filter((row) => row.ticked).map((row) => row.fact_id));
    const facts = (preview?.facts || []).map((fact) => {
        const repeats = fact.repeat_of?.fact_id;
        if (fact.untickedByMove && !ticked.has(fact.untickedByMove)) {
            const { untickedByMove, ...rest } = fact;
            return { ...rest, ticked: true };
        }
        if (repeats && ticked.has(repeats) && fact.ticked !== false && !fact.untickedByMove) {
            return { ...fact, ticked: false, untickedByMove: repeats };
        }
        return fact;
    });
    return { move_here: moveIn || [], facts };
}

// `rows` with row `index` changed (`changes` merged in).
export function rowChanged(rows, index, changes) {
    return (rows || []).map((row, i) => (i === index ? { ...row, ...changes } : row));
}

// The elsewhere rows of the new entry `name` (by name key) answered "same
// as `targetId`" (null: new): each row's `new.same_target_id`.
export function elsewhereSame(rows, name, targetId) {
    const key = nameKey(name);
    return (rows || []).map((row) => (row.new && nameKey(row.new.name) === key
        ? { ...row, new: { ...row.new, same_target_id: targetId } }
        : row));
}

// A timeline line's dates as the page shows them: its start, and once it
// has ended its span ("900–1010", ruling C18); "—" for an undated one.
export function lineDates(calendar, line) {
    if (!line?.date) {
        return '—';
    }
    const from = formatDate(calendar, line.date);
    return line.until ? `${from}–${formatDate(calendar, line.until)}` : from;
}

// fact id -> the other lines (shown on this timeline) it disagrees with on
// the year, as the server worked it out; an ended fact disagrees with
// nothing there (ruling C22), so a pick that ends one settles its flag.
export function disagreements(lines) {
    const byId = new Map((lines || []).map((line) => [line.fact_id, line]));
    const found = {};
    for (const line of byId.values()) {
        const others = (line.disagrees_with || []).map((id) => byId.get(id)).filter(Boolean);
        if (others.length) {
            found[line.fact_id] = others;
        }
    }
    return found;
}

// `accept_merge`'s request from a `preview_merge` preview and the owner's
// picks: the main name, each pair's keep ("a", "b" or "both"), what a
// losing fact gets ("remove" or "end"), the other names kept, and the
// from-side facts' ticks (`ticked`: fact id -> bool).
export function mergeRequest(preview, { mainName, keep = {}, lose = 'remove', akas = null, ticked = {} }) {
    const facts = preview.facts.map((fact) => (fact.fact_id in ticked ? { ...fact, ticked: ticked[fact.fact_id] } : fact));
    return {
        preview: { ...preview, facts },
        main_name: mainName,
        keep: Object.fromEntries(preview.pairs.map((pair) => [pair.key, keep[pair.key] || 'both'])),
        lose,
        ...(akas ? { akas } : {}),
    };
}

// `{picks, new_names, spans}` for a request, leaving out the empty ones
function linkFields(picks = {}, newNames = [], spans = []) {
    return {
        ...(Object.keys(picks).length ? { picks } : {}),
        ...(newNames.length ? { new_names: newNames } : {}),
        ...(spans.length ? { spans } : {}),
    };
}

function emptyThings() {
    return Object.fromEntries(LISTED_KINDS.map((kind) => [kind, []]));
}

function worldState() {
    // everything that belongs to the open world
    return {
        // the open section: a kind's list, or 'stubs'
        section: 'character',
        // the pages left, oldest first (`{section, thingId, at}`), and the
        // things deleted or re-pointed away since, which back skips
        history: [],
        gone: [],
        // the last `repoint_stub` done: `{stubName, target: {id, name},
        // links, akaAdded, factsMoved, notes}`, until the owner moves on
        stubRepointed: null,
        // the thing page `goBack` opened, until it loads: if it fails to,
        // it's gone and back goes on
        backOpening: null,
        things: emptyThings(),
        // every species, race and mix: `list_heritage`'s `{id, kind, name,
        // species_ids}`
        heritage: [],
        // the thing page: which thing, its payload, and the date it's viewed as of
        selectedThingId: null,
        // the thing page open before this one (a deleted mix goes back to
        // the species page it came from)
        openedFrom: null,
        thing: null,
        thingAt: null,
        scenes: [],
        // the create box: the request being drafted (`{kind, prompt,
        // fields, stubId, picks, newNames, repicks}`), whether a version is
        // being drafted, and why the last one failed
        previewRequest: null,
        previewPending: false,
        previewError: null,
        // the open draft (see "Drafts" in the module comment): `{key,
        // version, versions, page, base, edited, adding, accepting,
        // selecting}`, or null
        draft: null,
        // whether the create box shows the draft (false after "Edit
        // prompt", until the next version or "Back to the draft")
        draftShown: true,
        // draft key -> version -> `{base, edited}`: what the owner left on
        // each version this session, restored when it's used again
        draftEdits: {},
        // thing id -> its names (`[name, ...other names]`), for "Rename
        // to…", once asked for (`fetchNames`)
        namesOf: {},
        namesWanted: [],
        // the last names asked for that failed (the thing is gone)
        namesFailed: null,
        // "Make a stub and expand now": the stub's `{kind, name}`, until
        // its `make_stub_from_text` reply opens its create box
        stubExpandAfter: null,
        // the parents a `find_mix` is out for, and the last reply taken
        // (`{parents, mix_id}`)
        mixLookup: null,
        mixFound: null,
        // whether the next accepted preview opens its page; when it doesn't,
        // the new thing (`{id, kind, name}`) lands in `accepted`
        acceptOpens: true,
        accepted: null,
        // the id of the thing whose prose is being regenerated, and the one
        // section asked for (null: every section)
        proseRegenerating: null,
        proseRegeneratingSection: null,
        // the new-scene prompt's names: the lookup in flight (`{text, at}`),
        // and the last `match_names` reply taken (`{text, at, matches}`).
        // A new lookup drops the old reply, so stale spans never show.
        nameLookup: null,
        nameMatches: null,
        // the setup step: the request (`{action, data}`, plan_scene or
        // continue_scene) and its reply (`{setup, names}`)
        setupRequest: null,
        setupPending: false,
        sceneSetup: null,
        setupError: null,
        // the last `start_scene` reply: `{scene_id, target, scene}`
        startedScene: null,
        // the delete dialog's thing: the `thing_references` reply
        // (`{id, kind, name, references: {facts, fields, scenes}}`)
        deleteCheck: null,
        // `list_stubs`'s `{id, name, kind, first_mentioned, mentions,
        // ignored}`, ignored ones included
        stubs: [],
        // the stub the create box of its kind expands: `{id, kind, name}`
        expanding: null,
        // a stub to expand once the owner agrees to drop the unaccepted
        // preview: `{id, kind, name}`
        expandAsk: null,
        // another box's Create, waiting for the owner to agree to drop the
        // open draft: `{kind, prompt, fields, stubId, links}`
        createAsk: null,
        // the last `stub_suggestion` reply: `{id, prompt, context}`
        stubSuggestion: null,
        // thing id -> the other names to add to it once it's fetched
        akaQueue: {},
        // `list_tags`: `{tag, heading, count}` of every tag in use
        tags: [],
        // `list_roles`: `{role, count}` of every filing role in use
        roles: [],
        // the last rename or merge answered: `{from, to}`
        tagsChanged: null,
        // `groupKey(page, tag)` -> a group's synopsis asked for: `{pending,
        // text, error}`
        synopses: {},
        // `groupKey(page, tag)` -> a group's "+ Add": `{prompt, pending,
        // rows, error}` (the page's own "+ Add" under tag null)
        groupAdds: {},
        // "+ Add facts…"/"+ Add event…": `{thingId, mode: 'facts'|'event',
        // prompt, year, pending, draft, facts, error}`
        factDraft: null,
        // the last reply's notes to show: `{action, notes}`
        notes: null,
        // the merge dialog's: `{fromId, intoId, preview, pending}`
        merge: null,
        // the world's curation knobs (`{settings, defaults}`), and whether
        // the last `set_curation` is answered
        curation: null,
        curationSaved: false,
        pending: {},
    };
}

// the function actions send with; set by `connect`
let send = null;

export const useWorldsStore = defineStore('worlds', {
    state: () => ({
        connected: false,
        worlds: [],
        currentWorld: null,
        error: null,
        ...worldState(),
    }),

    getters: {
        calendar: (state) => state.currentWorld?.calendar || null,
        // the open draft's preview as the owner left it (null: none)
        preview: (state) => state.draft?.edited || null,
        // the `match_names` matches for exactly this text and date, if any
        matchesFor: (state) => (text, at) => {
            const found = state.nameMatches;
            return found && found.text === text && sameDate(found.at, at) ? found.matches : [];
        },
        // a heritage thing's lineage as links, most general first: its
        // species, then itself unless it is one (`[]` for an unknown id)
        heritageLinks: (state) => (id) => {
            const entry = state.heritage.find((item) => item.id === id);
            if (!entry) {
                return [];
            }
            const species = entry.species_ids
                .filter((speciesId) => speciesId !== id)
                .map((speciesId) => state.heritage.find((item) => item.id === speciesId))
                .filter(Boolean);
            return [...species, entry].map(({ id: linkId, name }) => ({ id: linkId, name }));
        },
        // the `match_names` unknown phrases for exactly this text and date
        unknownFor: (state) => (text, at) => {
            const found = state.nameMatches;
            return found && found.text === text && sameDate(found.at, at) ? found.unknown || [] : [];
        },
        // a stub's `list_stubs` entry, or null
        stubInfo: (state) => (id) => state.stubs.find((stub) => stub.id === id) || null,
        // what Add reference searches: `{id, name, kind, stub}` of every
        // listed entry, species, race and mix, and every live stub
        referenceTargets: (state) => {
            const byId = new Map();
            for (const things of Object.values(state.things)) {
                for (const thing of things) {
                    byId.set(thing.id, { id: thing.id, name: thing.name, kind: thing.kind, stub: !!thing.stub });
                }
            }
            for (const item of state.heritage) {
                if (!byId.has(item.id)) {
                    byId.set(item.id, { id: item.id, name: item.name, kind: item.kind, stub: false });
                }
            }
            for (const stub of state.stubs) {
                if (stub.ignored) {
                    byId.delete(stub.id);
                } else {
                    byId.set(stub.id, { id: stub.id, name: stub.name, kind: stub.kind, stub: true });
                }
            }
            return [...byId.values()];
        },
    },

    actions: {
        // --- the connection -----------------------------------------------

        connect(sendFn) {
            send = sendFn;
            this.connected = true;
            this.listWorlds();
        },

        disconnected() {
            this.connected = false;
            this.currentWorld = null;
            Object.assign(this, worldState());
        },

        request(action, data = {}) {
            if (!send) {
                return;
            }
            send({ type: ROUTER, action, ...data });
        },

        clearError() {
            this.error = null;
        },

        // --- worlds -------------------------------------------------------

        listWorlds() {
            this.request('list_worlds');
        },

        createWorld(name, presentYear) {
            this.resetWorld();
            this.pending = { create_world: true };
            this.request('create_world', { name, present_year: presentYear });
        },

        openWorld(path) {
            this.resetWorld();
            this.pending = { open_world: true };
            this.request('open_world', { path });
        },

        // a world switch cancels the backend's preview without a reply, so
        // nothing of the old world may wait for one
        resetWorld() {
            Object.assign(this, worldState());
        },

        // `get_present` along with them: a scene that started, continued or
        // moved can change the world's `now`
        listScenes() {
            this.request('list_scenes');
            this.refreshPresent();
        },

        refreshPresent() {
            this.request('get_present');
        },

        // the open world's present year (things are created at it before
        // any scene has moved past it)
        setPresent(year) {
            if (!this.currentWorld) {
                return;
            }
            this.pending = { ...this.pending, set_present: true };
            this.request('set_present', { year });
        },

        // --- scenes -------------------------------------------------------

        // `at`: the date the names are as of (null for the latest)
        matchNames(text, at = null) {
            this.nameMatches = null;
            if (!text.trim()) {
                this.nameLookup = null;
                return;
            }
            this.nameLookup = { text, at };
            this.request('match_names', { text, at });
        },

        // `picks`: a matched name (as written) -> thing id; `player` a
        // character id or null; `start` a date, or null for after the
        // latest scene; `newNames`: matched names treated as new
        planScene(prompt, picks = {}, player = null, start = null, newNames = []) {
            this.requestSetup('plan_scene', { prompt, picks, new_names: newNames, player, start });
        },

        continueScene(sceneId, goalPrompt) {
            this.requestSetup('continue_scene', { scene_id: sceneId, goal_prompt: goalPrompt });
        },

        requestSetup(action, data) {
            this.setupRequest = { action, data };
            this.sceneSetup = null;
            this.setupError = null;
            this.setupPending = true;
            this.request(action, data);
        },

        regenerateSetup() {
            const req = this.setupRequest;
            if (req) {
                this.requestSetup(req.action, req.data);
            }
        },

        // drop the setup, keeping the request so the prompt can be edited
        discardSetup() {
            this.sceneSetup = null;
            this.setupError = null;
            this.setupPending = false;
        },

        // forget the setup step altogether (its dialog closed)
        closeSetup() {
            this.discardSetup();
            this.setupRequest = null;
        },

        startScene() {
            if (!this.sceneSetup) {
                return;
            }
            this.setupError = null;
            this.pending = { ...this.pending, start_scene: true };
            this.request('start_scene', { setup: this.sceneSetup.setup });
        },

        repositionScene(sceneId, start) {
            this.pending = { ...this.pending, reposition_scene: true };
            this.request('reposition_scene', { scene_id: sceneId, start });
        },

        // --- things -------------------------------------------------------

        listThings(kind) {
            this.request('list_things', { kind });
        },

        listHeritage() {
            this.request('list_heritage');
        },

        // the page shown now, as the history keeps it
        currentPage() {
            return { section: this.section, thingId: this.selectedThingId, at: this.selectedThingId ? this.thingAt : null };
        },

        // the owner opens `next`: the page left goes on the history
        visit(next) {
            this.stubRepointed = null;
            this.history = historyPushed(this.history, this.currentPage(), { section: this.section, at: null, ...next });
        },

        // a section from the side list (a kind's list, or 'stubs')
        showSection(section) {
            this.visit({ section, thingId: null });
            this.section = section;
            this.closeThing();
        },

        // the back arrow: the page before, else the section home
        goBack() {
            const { page, history } = historyBack(this.history, (id) => this.gone.includes(id));
            this.history = history;
            if (!page) {
                this.closeThing();
                return;
            }
            this.section = page.section;
            if (page.thingId) {
                this.backOpening = page.thingId;
                this.showThing(page.thingId, page.at);
            } else {
                this.closeThing();
            }
        },

        // a page the owner opens (see the history, in the module comment)
        openThing(id, at = null) {
            this.visit({ thingId: id, at });
            this.showThing(id, at);
        },

        showThing(id, at = null) {
            if (id !== this.selectedThingId) {
                this.openedFrom = this.selectedThingId;
            }
            this.selectedThingId = id;
            this.thingAt = at;
            if (this.thing?.id !== id) {
                this.thing = null;
            }
            this.request('get_thing', { id, at });
        },

        closeThing() {
            this.deleteCheck = null;
            this.openedFrom = null;
            this.selectedThingId = null;
            this.thing = null;
            this.thingAt = null;
        },

        viewThingAt(at) {
            if (this.selectedThingId) {
                this.showThing(this.selectedThingId, at);
            }
        },

        // --- delete -------------------------------------------------------

        // check what uses the open thing, then ask (the dialog opens on
        // the reply)
        requestDelete() {
            if (!this.selectedThingId) {
                return;
            }
            this.deleteCheck = null;
            this.pending = { ...this.pending, thing_references: true };
            this.request('thing_references', { id: this.selectedThingId });
        },

        cancelDelete() {
            this.deleteCheck = null;
        },

        confirmDelete() {
            if (!this.deleteCheck) {
                return;
            }
            this.pending = { ...this.pending, delete_thing: true };
            this.request('delete_thing', { id: this.deleteCheck.id });
        },

        // --- create -------------------------------------------------------

        // `stubId`: the stub the draft expands (its kind's create box
        // opened from it); `picks` and `newNames`: the prompt's names, as
        // the owner left them; `repicks`: the owner's re-picks (`{id,
        // name}`), each thing taught its name once the draft is accepted.
        // A draft of the same kind (and stub) open already gets a new
        // version (its `draft_key` sent back: Regenerate, Edit prompt).
        previewThing(kind, prompt, fields = {}, stubId = null, { picks = {}, newNames = [], repicks = [] } = {}, { discard = false } = {}) {
            const draft = this.draft;
            // the same box's request (its kind and stub; the draft's own
            // kind may have been changed since)
            const before = this.previewRequest;
            const same = !!draft && !!before && before.kind === kind && (before.stubId || null) === (stubId || null);
            const key = same ? draft.key : null;
            if (draft && !key) {
                // another entry's draft: the owner is asked before it goes
                if (!discard) {
                    this.createAsk = { kind, prompt, fields, stubId, links: { picks, newNames, repicks } };
                    return;
                }
                this.discardPreview();
            }
            this.createAsk = null;
            this.previewRequest = { kind, prompt, fields, stubId, picks, newNames, repicks };
            this.previewError = null;
            this.previewPending = true;
            this.request('preview_thing', {
                kind,
                prompt,
                fields,
                ...(stubId ? { stub_id: stubId } : {}),
                ...linkFields(picks, newNames),
                ...(key ? { draft_key: key } : {}),
            });
        },

        // "↻ Regenerate": a new version from the same request
        regeneratePreview() {
            const req = this.previewRequest;
            if (req) {
                this.previewThing(req.kind, req.prompt, req.fields, req.stubId, req);
            }
        },

        // "Edit prompt": back to the create box, the draft kept; the next
        // Create is a new version of it
        editPrompt() {
            this.draftShown = false;
        },

        // back to the draft from the create box
        showDraft() {
            if (this.draft) {
                this.draftShown = true;
            }
        },

        // "Discard": the draft's every version goes (`discard_preview`),
        // nothing written; the request stays, so the prompt can be edited
        discardPreview() {
            const draft = this.draft;
            if (draft) {
                this.request('discard_preview', { draft_key: draft.key });
                const { [draft.key]: _gone, ...rest } = this.draftEdits;
                this.draftEdits = rest;
            }
            this.draft = null;
            this.draftShown = true;
            this.previewError = null;
            this.previewPending = false;
        },

        // forget the draft and its request (its box closed)
        cancelPreview() {
            this.discardPreview();
            this.previewRequest = null;
        },

        // what the owner left on the open version, kept for the session
        keepDraftEdits() {
            const draft = this.draft;
            if (!draft) {
                return;
            }
            this.draftEdits = {
                ...this.draftEdits,
                [draft.key]: { ...(this.draftEdits[draft.key] || {}), [draft.version]: { base: draft.base, edited: draft.edited } },
            };
        },

        // "Version n of m ▾": restore version `version` (`use_version`)
        useVersion(version) {
            const draft = this.draft;
            if (!draft || version === draft.version) {
                return;
            }
            this.keepDraftEdits();
            this.pending = { ...this.pending, use_version: true };
            this.request('use_version', { draft_key: draft.key, version });
        },

        // the owner's edits to the draft (`changes` merged into `edited`),
        // then rendered by the server as accept will write them
        editDraft(changes) {
            if (this.draft) {
                this.draft = { ...this.draft, edited: { ...this.draft.edited, ...changes } };
                this.renderDraft();
            }
        },

        // P6: the server links the owner's copy of the draft as accept
        // will (`draft_render`, writing nothing): its facts, prose and
        // timeline (`draft.rendered`). Each request is numbered (`seq`);
        // only the answer to the newest is kept. A copy the owner hasn't
        // changed is the server's page as it is.
        renderDraft() {
            const draft = this.draft;
            if (!draft) {
                return;
            }
            const seq = (draft.renderSeq || 0) + 1;
            this.draft = { ...draft, renderSeq: seq };
            if (draft.edited === draft.base) {
                this.draft = { ...this.draft, rendered: null };
                return;
            }
            this.request('draft_render', { draft_key: draft.key, seq, preview: acceptable(draft.edited) });
        },

        // "+ Add facts…" / "+ Add event…" on the draft: one at a time
        addDraftFacts(prompt, year = null) {
            const draft = this.draft;
            if (!draft || draft.adding) {
                return;
            }
            const action = year === null ? 'add_facts' : 'add_event';
            this.draft = { ...draft, adding: action, addError: null };
            this.request(action, { draft_key: draft.key, prompt, ...(year === null ? {} : { year }) });
        },

        // a selection in the draft's fact `index` (the server's), as
        // "Make a stub" (`kind`, `tag`) or "Link to…" (`targetId`)
        draftSelection(action, index, start, end, data) {
            const draft = this.draft;
            if (!draft || draft.selecting) {
                return;
            }
            this.draft = { ...draft, selecting: action };
            this.request(action, { draft_key: draft.key, index, start, end, ...data });
        },

        // a draft reply (`preview_thing`, `use_version`, a draft's
        // additions and selections): the page, its server copy, and the
        // owner's edits carried onto it (`how`: 'new' a new version,
        // 'restore' a version used again, 'rebase' this version changed)
        draftTaken(data, how, { fresh = [], done = null } = {}) {
            const { preview, draft_key: key, version, versions, ...page } = data;
            const before = this.draft;
            let edited = preview;
            if (how === 'new') {
                if (before && before.key === key) {
                    this.keepDraftEdits();
                    // the oldest version was dropped: the ones kept move down
                    if (versions.length === before.versions.length && version === versions.length) {
                        const kept = this.draftEdits[key] || {};
                        this.draftEdits = {
                            ...this.draftEdits,
                            [key]: Object.fromEntries(Object.entries(kept).filter(([n]) => Number(n) > 1).map(([n, value]) => [Number(n) - 1, value])),
                        };
                    }
                }
            } else if (how === 'restore') {
                const kept = this.draftEdits[key]?.[version];
                edited = kept ? rebaseDraft(kept.base, kept.edited, preview) : preview;
            } else if (before && before.key === key && before.version === version) {
                edited = rebaseDraft(before.base, before.edited, preview, { fresh });
            } else {
                const kept = this.draftEdits[key]?.[version];
                edited = kept ? rebaseDraft(kept.base, kept.edited, preview, { fresh }) : preview;
            }
            this.draft = {
                key,
                version,
                versions,
                page,
                base: preview,
                edited,
                // a draft's addition or selection still out stays so
                adding: done === 'adding' || !before ? null : before.adding,
                addError: null,
                accepting: false,
                selecting: done === 'selecting' || !before ? null : before.selecting,
                // the server's page is this copy's: rendered anew once
                // the owner's edits are on it
                rendered: null,
                renderSeq: before?.renderSeq || 0,
            };
            if (how === 'new') {
                this.draftShown = true;
            }
            if (edited !== preview) {
                this.renderDraft();
            }
        },

        // --- stubs --------------------------------------------------------

        listStubs() {
            this.request('list_stubs', { include_ignored: true });
        },

        ignoreStub(id, ignored = true) {
            this.pending = { ...this.pending, ignore_stub: true };
            this.request('ignore_stub', { id, ignored });
        },

        // point every link to the stub `stubId` at `targetId`; the stub's
        // names become the target's other names and the stub goes
        // `useName` (the hard re-point): one of the target's names, which
        // every link's words become
        // `mode` (`NameModeMenu`'s, always sent by the button): 'link'
        // ("Link only", ruling H2) teaches no names
        repointStub(stubId, targetId, useName = null, mode = null) {
            this.stubRepointed = null;
            this.pending = { ...this.pending, repoint_stub: true };
            this.request('repoint_stub', { stub_id: stubId, target_id: targetId, ...(mode ? { mode } : {}), ...(useName ? { use_name: useName } : {}) });
        },

        // thing `id`'s names (`namesOf[id]`: its name, then its other
        // names), fetched for "Rename to…" (`NameModeMenu`)
        fetchNames(id) {
            this.namesFailed = null;
            if (!this.namesWanted.includes(id)) {
                this.namesWanted = [...this.namesWanted, id];
            }
            this.request('get_thing', { id, at: null });
        },

        clearStubRepointed() {
            this.stubRepointed = null;
        },

        changeStubKind(id, kind) {
            this.pending = { ...this.pending, change_stub_kind: true };
            this.request('change_stub_kind', { id, kind });
        },

        // open the create box of `stub`'s kind (`{id, kind, name}`) to
        // expand it, leaving the page (and any other preview) behind; its
        // suggested prompt is asked for. An unaccepted preview isn't
        // dropped unasked: the stub waits in `expandAsk` for the owner to
        // `confirmExpand` or `keepPreview`.
        expandStub(stub, { discard = false } = {}) {
            const target = { id: stub.id, kind: stub.kind, name: stub.name };
            if (this.preview && !discard) {
                this.expandAsk = target;
                return;
            }
            this.expandAsk = null;
            this.cancelPreview();
            this.visit({ section: target.kind, thingId: null });
            this.section = target.kind;
            this.closeThing();
            this.expanding = target;
            this.stubSuggestion = null;
            this.request('stub_suggestion', { id: stub.id });
        },

        // the owner agreed to drop the preview: expand the stub waiting
        confirmExpand() {
            const stub = this.expandAsk;
            if (stub) {
                this.expandStub(stub, { discard: true });
            }
        },

        // the owner keeps the draft: the stub isn't expanded, nothing else
        // is created
        keepPreview() {
            this.expandAsk = null;
            this.createAsk = null;
        },

        // the owner agreed to drop the draft: create what was asked
        confirmCreate() {
            const ask = this.createAsk;
            if (ask) {
                this.previewThing(ask.kind, ask.prompt, ask.fields, ask.stubId, ask.links, { discard: true });
            }
        },

        stopExpanding() {
            this.expanding = null;
        },

        // --- filing and tags ----------------------------------------------

        // `thingId` (the open page when left out) answers the edit; the
        // open page's date goes with it only when it's that page
        filingEdit(action, thingId, data) {
            const id = thingId || this.selectedThingId;
            this.pending = { ...this.pending, [action]: true };
            this.request(action, { thing_id: id, at: id === this.selectedThingId ? this.thingAt : null, ...data });
        },

        // file the open page in `targetId`, or in a new stub `newName` (of
        // `kind`, with `tag`): `{targetId | newName, kind, tag, role, since,
        // until, within, showUnder}` (`showUnder`: the group it shows under
        // on the target's page, a tag; sent only when there is one)
        addFiling({ targetId = null, newName = null, kind = null, tag = null, role = null, since = null, until = null, within = null, showUnder = null }) {
            this.filingEdit('add_filing', null, {
                ...(targetId ? { target_id: targetId } : { new_name: newName, ...(kind ? { kind } : {}), ...(tag ? { tag } : {}) }),
                role: role || null,
                since: dateIn(since),
                until: dateIn(until),
                within,
                ...(showUnder ? { show_under: showUnder } : {}),
            });
        },

        // `changes`: only what changes of `{role, since, until, within,
        // show_under}` (null clears one; an `until` ends it, "End this"),
        // of the open page's filing, or `thingId`'s (a Connected row moved)
        editFiling(targetId, changes, thingId = null) {
            const data = { target_id: targetId };
            for (const [key, value] of Object.entries(changes)) {
                data[key] = key === 'since' || key === 'until' ? dateIn(value) : value;
            }
            this.filingEdit('edit_filing', thingId, data);
        },

        removeFiling(targetId) {
            this.filingEdit('remove_filing', null, { target_id: targetId });
        },

        // a "but…" under the open page's filing in `targetId`: it departs
        // from the entry as a whole (`rejects` null)
        addException(targetId, text, rejects = null) {
            this.pending = { ...this.pending, add_exception: true };
            this.request('add_exception', {
                character_id: this.selectedThingId,
                target_id: targetId,
                text,
                rejects,
                at: this.thingAt,
            });
        },

        // any entry's tag (null clears it)
        setTag(thingId, tag) {
            this.filingEdit('set_tag', thingId, { tag });
        },

        listTags() {
            this.request('list_tags');
        },

        // the role picker's choices
        listRoles() {
            this.request('list_roles');
        },

        renameTag(old, renamed) {
            this.pending = { ...this.pending, rename_tag: true };
            this.request('rename_tag', { old, new: renamed });
        },

        mergeTag(from, into) {
            this.pending = { ...this.pending, merge_tag: true };
            this.request('merge_tag', { from, into });
        },

        // --- groups -------------------------------------------------------

        // a group's synopsis (`force`: asked again, though one is cached)
        groupSynopsis(thingId, tag, force = false) {
            const key = groupKey(thingId, tag);
            this.synopses = { ...this.synopses, [key]: { ...(this.synopses[key] || {}), pending: true, error: null } };
            this.request('group_synopsis', { thing_id: thingId, tag: tag ?? null, force });
        },

        // "+ Add" in a group (tag null: the page's own)
        groupAdd(thingId, tag, prompt) {
            const key = groupKey(thingId, tag);
            this.groupAdds = { ...this.groupAdds, [key]: { prompt, pending: true, rows: null, error: null } };
            this.request('group_add', { thing_id: thingId, tag: tag ?? null, prompt });
        },

        // the owner's edits to a group's drafted rows (ticks, names)
        editGroupAdd(thingId, tag, rows) {
            const key = groupKey(thingId, tag);
            if (this.groupAdds[key]) {
                this.groupAdds = { ...this.groupAdds, [key]: { ...this.groupAdds[key], rows } };
            }
        },

        discardGroupAdd(thingId, tag) {
            const { [groupKey(thingId, tag)]: _gone, ...rest } = this.groupAdds;
            this.groupAdds = rest;
        },

        // the rows stay (`accepting`) until the server answers, so a
        // refusal leaves them as the owner left them
        acceptGroupAdd(thingId, tag) {
            const key = groupKey(thingId, tag);
            const found = this.groupAdds[key];
            if (!found?.rows || found.accepting) {
                return;
            }
            this.groupAdds = { ...this.groupAdds, [key]: { ...found, accepting: true } };
            this.pending = { ...this.pending, accept_group_add: true };
            this.request('accept_group_add', { thing_id: thingId, rows: found.rows });
        },

        // --- prompt additions ---------------------------------------------

        // "+ Add facts…" on the open page
        addFacts(prompt) {
            this.askFacts('add_facts', { prompt });
        },

        // "+ Add event…": its facts all dated `year`
        addEvent(prompt, year) {
            this.askFacts('add_event', { prompt, year });
        },

        askFacts(action, data) {
            if (!this.selectedThingId) {
                return;
            }
            const mode = action === 'add_event' ? 'event' : 'facts';
            this.factDraft = { thingId: this.selectedThingId, mode, prompt: data.prompt, year: data.year ?? null, pending: true, draft: null, facts: null, error: null };
            this.request(action, { thing_id: this.selectedThingId, at: this.thingAt, ...data });
        },

        // tick (or untick) the drafted fact `index`
        tickDraftFact(index, ticked) {
            const found = this.factDraft;
            if (!found?.draft) {
                return;
            }
            const facts = found.draft.facts.map((fact, i) => (i === index ? { ...fact, ticked } : fact));
            this.factDraft = {
                ...found,
                draft: { ...found.draft, facts },
                facts: found.facts.map((row) => (row.index === index ? { ...row, ticked } : row)),
            };
        },

        discardFacts() {
            this.factDraft = null;
        },

        // the draft stays (`accepting`) until the server answers
        acceptFacts() {
            const found = this.factDraft;
            if (!found?.draft || found.accepting) {
                return;
            }
            this.factDraft = { ...found, accepting: true };
            this.pending = { ...this.pending, accept_facts: true };
            this.request('accept_facts', { draft: found.draft, at: found.thingId === this.selectedThingId ? this.thingAt : null });
        },

        // the open thing's page asked for again, as of the date it's viewed at
        refreshThing() {
            if (this.selectedThingId) {
                this.request('get_thing', { id: this.selectedThingId, at: this.thingAt });
            }
        },

        // every kind's list (a create or a scene start may make stubs of any)
        listAllThings() {
            for (const kind of LISTED_KINDS) {
                this.listThings(kind);
            }
        },

        // `open: false` keeps the page where it is (the mix drafted for a
        // character): the new thing lands in `accepted` instead
        // `intoStub`: "fill the stub instead", the stub a preview made
        // without one fills; `sameTargetId`: "Is this X?" answered yes, the
        // entry the material goes onto. The owner's re-picks are taught to
        // their things once it's accepted (the `accept_preview` reply).
        // The draft stays (`accepting`) until the server answers, so a
        // refusal leaves it as the owner left it.
        acceptPreview(changes = {}, { open = true, intoStub = null, sameTargetId = null } = {}) {
            const draft = this.draft;
            if (!draft || draft.accepting) {
                return;
            }
            this.acceptOpens = open;
            this.accepted = null;
            this.draft = { ...draft, accepting: true };
            this.pending = { ...this.pending, accept_preview: true };
            this.request('accept_preview', {
                preview: acceptable({ ...draft.edited, ...changes }),
                draft_key: draft.key,
                ...(intoStub ? { into_stub: intoStub } : {}),
                ...(sameTargetId ? { same_target_id: sameTargetId } : {}),
            });
        },

        // --- curation -----------------------------------------------------

        // the owner's edits to the draft before it's accepted (`type`
        // 'create', the only preview)
        editPreview(type, changes) {
            if (type === 'create') {
                this.editDraft(changes);
            }
        },

        clearNotes() {
            this.notes = null;
        },

        // a reply's notes, shown until the owner closes them (none: the
        // last ones go)
        showNotes(action, notes) {
            this.notes = notes?.length ? { action, notes } : null;
        },

        // what merging `fromId` into `intoId` would do (`preview_merge`)
        previewMerge(fromId, intoId) {
            this.merge = { fromId, intoId, preview: null, pending: true };
            this.pending = { ...this.pending, preview_merge: true };
            this.request('preview_merge', { from_id: fromId, into_id: intoId });
        },

        // the owner's picks (`mergeRequest`'s)
        acceptMerge(choices) {
            if (!this.merge?.preview) {
                return;
            }
            this.pending = { ...this.pending, accept_merge: true };
            this.request('accept_merge', mergeRequest(this.merge.preview, choices));
        },

        closeMerge() {
            this.merge = null;
        },

        // move the open page's fact `factId` onto `targetId` (one revision)
        moveFact(factId, targetId) {
            this.pending = { ...this.pending, move_fact: true };
            this.request('move_fact', { fact_id: factId, target_id: targetId });
        },

        // copy the open page's fact `factId` onto `targetId`, keeping it
        // here (`copy_fact`, one revision)
        copyFact(factId, targetId) {
            this.pending = { ...this.pending, copy_fact: true };
            this.request('copy_fact', { fact_id: factId, target_id: targetId });
        },

        // selected words of the open page's fact `factId` (`start`/`end`
        // in UTF-16 code units of its rendered text, ruling F18) made a
        // stub of `kind` (and `tag`), linked there; `expand`: the stub's
        // create box opens once it's made ("Make a stub and expand now")
        makeStubFromText(factId, start, end, kind, tag = null, { expand = false, words = '' } = {}) {
            this.stubExpandAfter = expand ? { kind, name: words } : null;
            this.edit('make_stub_from_text', { fact_id: factId, start, end, kind, ...(tag ? { tag } : {}) });
        },

        // selected words of the open page's fact linked to `targetId`, in
        // the owner's `mode`: 'link' as written (the default), 'name'
        // taught as another name too, 'rename' with `useName`, one of its
        // names, in their place
        linkText(factId, start, end, targetId, { mode = 'link', useName = null } = {}) {
            this.edit('link_text', { fact_id: factId, start, end, target_id: targetId, mode, ...(useName ? { use_name: useName } : {}) });
        },

        // who holds the open page's fact `factId` as a belief (null: world
        // truth)
        setHeldBy(factId, holderId) {
            this.edit('set_held_by', { fact_id: factId, holder_id: holderId });
        },

        // a timeline disagreement settled: keep `keepId`'s date, and end or
        // remove `dropId` (`mode`); the reply carries the open page
        pickDate(keepId, dropId, mode) {
            this.pending = { ...this.pending, pick_date: true };
            this.request('pick_date', {
                keep_fact_id: keepId,
                drop_fact_id: dropId,
                mode,
                ...(this.selectedThingId ? { thing_id: this.selectedThingId, at: this.thingAt } : {}),
            });
        },

        getCuration() {
            this.request('get_curation');
        },

        // only the knobs that change (`set_curation` keeps the rest)
        setCuration(settings) {
            this.curationSaved = false;
            this.pending = { ...this.pending, set_curation: true };
            this.request('set_curation', { settings });
        },

        // mark the preview's inherited fact `factId` as replaced by its own
        // fact at `index` (null: not replaced)
        setPreviewOverride(factId, index) {
            if (!this.preview) {
                return;
            }
            const facts = this.preview.facts.map((fact, i) => {
                const overrides = (fact.overrides || []).filter((id) => id !== factId);
                return { ...fact, overrides: i === index ? [...overrides, factId] : overrides };
            });
            this.editDraft({ facts });
        },

        // the mix of two parents, if the world has one (`mixFound`)
        findMix(parents) {
            this.mixFound = null;
            this.mixLookup = { parents };
            this.request('find_mix', { parents });
        },

        // --- edits (each answers with the thing as of `thingAt`) -----------

        edit(action, data) {
            this.pending = { ...this.pending, [action]: true };
            this.request(action, { thing_id: this.selectedThingId, at: this.thingAt, ...data });
        },

        // `links`: `{picks, newNames, spans}` for the text's names
        addFact(category, text, validFrom = null, validUntil = null, { picks = {}, newNames = [], spans = [] } = {}) {
            this.edit('add_fact', { category, text, valid_from: validFrom, valid_until: validUntil, ...linkFields(picks, newNames, spans) });
        },

        // `changes` holds only what changes: text, category, valid_from,
        // valid_until (a null date makes that end open); `links` as
        // addFact's, for a changed text
        correctFact(factId, changes, { picks = {}, newNames = [], spans = [] } = {}) {
            this.edit('correct_fact', { fact_id: factId, ...changes, ...linkFields(picks, newNames, spans) });
        },

        // point the `occurrence`-th reference of the open thing's fact
        // `factId` at `toId`, in the owner's `mode` (`NameModeMenu`): 'link'
        // keeps its words, 'name' teaches them too (the server's default),
        // 'rename' writes `useName`, one of `toId`'s names, in their place
        repointRef(factId, occurrence, toId, { mode = null, useName = null } = {}) {
            this.edit('repoint_ref', { fact_id: factId, occurrence, to_id: toId, ...(mode ? { mode } : {}), ...(useName ? { use_name: useName } : {}) });
        },

        // make `text`, a phrase in the open thing's fact `factId`, a stub
        // of `kind`, and link it there
        makeStub(factId, text, kind) {
            this.edit('make_stub', { fact_id: factId, text, kind });
        },

        // teach thing `id` another name (common, not everyday): fetched
        // first, since `aka` is written whole
        addOtherName(id, name) {
            this.akaQueue = { ...this.akaQueue, [id]: [...(this.akaQueue[id] || []), name] };
            this.request('get_thing', { id, at: id === this.selectedThingId ? this.thingAt : null });
        },

        endFact(factId, until) {
            this.edit('end_fact', { fact_id: factId, until });
        },

        removeFact(factId) {
            this.edit('remove_fact', { fact_id: factId });
        },

        // an own fact replacing the inherited fact `factId`
        overrideFact(factId, category, text, { picks = {}, newNames = [], spans = [] } = {}) {
            this.edit('override_fact', { overridden_fact_id: factId, category, text, ...linkFields(picks, newNames, spans) });
        },

        // `value`: a number field's number, or `measures`' list of
        // `{name, min, max, unit}`. `validFrom`, if given, is the dated
        // value to correct (left out: the undated one).
        setField(field, value, validFrom = undefined) {
            this.edit('set_field', { field, value, ...(validFrom === undefined ? {} : { valid_from: validFrom }) });
        },

        // the open thing's other names: the whole list
        setAka(aka) {
            this.setField('aka', aka);
        },

        // a correction of the open thing's name (see the module comment)
        renameThing(name) {
            if (!this.thing) {
                return;
            }
            this.setField('name', name, currentNameFrom(this.thing.timeline, this.thingAt));
        },

        // `section`: just that one; left out, every section
        regenerateProse(section = null) {
            if (!this.selectedThingId) {
                return;
            }
            this.proseRegenerating = this.selectedThingId;
            this.proseRegeneratingSection = section;
            this.request('regenerate_prose', {
                id: this.selectedThingId,
                at: this.thingAt,
                ...(section ? { section } : {}),
            });
        },

        // --- replies ------------------------------------------------------

        worldOpened(info) {
            this.resetWorld();
            this.currentWorld = info;
            this.listAllThings();
            this.listStubs();
            this.listTags();
            this.listScenes();
        },

        // the queued other names of `thing` (a `get_thing` reply), written
        // if any is new to it
        writeOtherNames(thing) {
            const { [thing.id]: names, ...rest } = this.akaQueue;
            this.akaQueue = rest;
            const before = thing.aka || [];
            let aka = before;
            for (const name of names) {
                aka = akaAdded(aka, name, 'common', thing.name);
            }
            if (aka !== before) {
                this.request('set_field', {
                    thing_id: thing.id,
                    at: thing.id === this.selectedThingId ? this.thingAt : null,
                    field: 'aka',
                    value: aka,
                });
            }
        },

        // a filing or tag edit's reply (`data`, the thing it changed): the
        // open page takes it, or is fetched again when it's another thing
        // (a Connected row retagged); new stubs and tags may come with it
        filingEdited(action, data) {
            // an accepted draft is done with
            if (action === 'accept_facts' && this.factDraft?.accepting) {
                this.factDraft = null;
            }
            if (action === 'accept_group_add') {
                this.groupAdds = Object.fromEntries(Object.entries(this.groupAdds).filter(([key, value]) => !(value.accepting && key.startsWith(`${data.id}|`))));
            }
            if (data.id === this.selectedThingId && !this.thingAt) {
                this.pageTaken(data);
            } else {
                this.refreshThing();
            }
            if (action === 'remove_filing' || action === 'accept_group_add') {
                this.showNotes(action, data.notes);
            }
            this.listStubs();
            this.listAllThings();
            if (action === 'set_tag' || action === 'accept_group_add' || action === 'add_filing' || action === 'edit_filing') {
                this.listTags();
            }
        },

        // the open page's payload, as a reply brings it: the synopses asked
        // for this session give way to its own (null when one went stale),
        // all but those still being asked for
        pageTaken(data) {
            this.thing = data;
            const prefix = `${data.id}|`;
            this.synopses = Object.fromEntries(Object.entries(this.synopses).filter(([key, value]) => !key.startsWith(prefix) || value.pending));
        },

        clearPending(action) {
            if (this.pending[action]) {
                const { [action]: _done, ...rest } = this.pending;
                this.pending = rest;
            }
        },

        handleMessage(message) {
            if (message?.type !== ROUTER) {
                return;
            }
            const data = message.data;
            const action = message.action;

            switch (action) {
                case 'list_worlds':
                    this.worlds = data.worlds;
                    break;
                case 'create_world':
                    this.worldOpened(data);
                    this.listWorlds();
                    break;
                case 'open_world':
                    this.worldOpened(data);
                    break;
                case 'get_present':
                case 'set_present':
                    if (this.currentWorld) {
                        this.currentWorld = { ...this.currentWorld, ...data };
                    }
                    break;
                case 'list_things':
                    this.things = { ...this.things, [data.kind]: data.things };
                    if (HERITAGE_KINDS.includes(data.kind)) {
                        this.listHeritage();
                    }
                    break;
                case 'list_heritage':
                    this.heritage = data.things;
                    break;
                case 'list_stubs':
                    this.stubs = data.stubs;
                    break;
                case 'ignore_stub':
                case 'change_stub_kind': {
                    const before = this.stubInfo(data.id);
                    if (data.id === this.selectedThingId) {
                        this.thing = data;
                    } else {
                        // the open page's links to the stub change with it
                        this.refreshThing();
                    }
                    if (this.expanding?.id === data.id) {
                        this.expanding = { ...this.expanding, kind: data.kind };
                    }
                    for (const kind of new Set([before?.kind, data.kind])) {
                        if (LISTED_KINDS.includes(kind)) {
                            this.listThings(kind);
                        }
                    }
                    this.listStubs();
                    break;
                }
                case 'get_thing':
                    if (this.namesWanted.includes(data.id)) {
                        this.namesWanted = this.namesWanted.filter((id) => id !== data.id);
                        this.namesOf = { ...this.namesOf, [data.id]: [data.name, ...(data.aka || []).map((entry) => entry.name)] };
                    }
                    if (data.id === this.backOpening) {
                        this.backOpening = null;
                    }
                    if (data.id === this.selectedThingId) {
                        this.pageTaken(data);
                    }
                    if (this.akaQueue[data.id]) {
                        this.writeOtherNames(data);
                    }
                    break;
                case 'list_tags':
                    this.tags = data.tags;
                    break;
                case 'list_roles':
                    this.roles = data.roles;
                    break;
                case 'rename_tag':
                case 'merge_tag':
                    this.tags = data.tags;
                    // which rename or merge was answered (the Tags tab's form)
                    this.tagsChanged = action === 'rename_tag' ? { from: data.old, to: data.new } : { from: data.from, to: data.into };
                    // every page with that tag reads its new one
                    this.refreshThing();
                    this.listAllThings();
                    break;
                case 'group_synopsis':
                case 'group_synopsis_failed': {
                    const key = groupKey(data?.thing_id, data?.tag);
                    if (this.synopses[key]?.pending) {
                        this.synopses = {
                            ...this.synopses,
                            [key]: action === 'group_synopsis'
                                ? { pending: false, text: data.synopsis, error: null }
                                : { ...this.synopses[key], pending: false, error: message.message },
                        };
                    }
                    break;
                }
                case 'group_add':
                case 'group_add_failed': {
                    const key = groupKey(data?.thing_id, data?.tag);
                    const found = this.groupAdds[key];
                    if (found?.pending) {
                        this.groupAdds = {
                            ...this.groupAdds,
                            [key]: action === 'group_add'
                                ? { ...found, pending: false, rows: data.rows }
                                : { ...found, pending: false, error: message.message },
                        };
                    }
                    break;
                }
                case 'add_facts':
                case 'add_event':
                case 'add_facts_failed':
                case 'add_event_failed': {
                    if (data?.draft_key) {
                        // a draft's own: the updated draft (for a draft
                        // since dropped, nothing)
                        if (this.draft?.key !== data.draft_key) {
                            break;
                        }
                        if (action.endsWith('_failed')) {
                            this.draft = { ...this.draft, adding: null, addError: message.message };
                        } else {
                            this.draftTaken(data, 'rebase', { done: 'adding' });
                        }
                        break;
                    }
                    const found = this.factDraft;
                    if (!found?.pending || data?.draft_key || data?.thing_id !== found.thingId) {
                        break;
                    }
                    this.factDraft = action.endsWith('_failed')
                        ? { ...found, pending: false, error: message.message }
                        : { ...found, pending: false, draft: data.draft, facts: data.facts };
                    break;
                }
                case 'stub_suggestion':
                    if (this.expanding?.id === data.id) {
                        this.stubSuggestion = data;
                    }
                    break;
                case 'list_scenes':
                    this.scenes = data.scenes;
                    break;
                case 'thing_references':
                    // dropped if another thing was opened meanwhile
                    if (data.id === this.selectedThingId) {
                        this.deleteCheck = data;
                    }
                    break;
                case 'thing_deleted':
                    this.clearPending('delete_thing');
                    this.deleteCheck = null;
                    this.gone = [...this.gone, data.id];
                    this.listStubs();
                    if (data.id === this.selectedThingId) {
                        const back = pageAfterDelete(this.thing, this.heritage, this.openedFrom);
                        this.closeThing();
                        if (back) {
                            this.showThing(back);
                        }
                    }
                    break;
                case 'repoint_stub':
                    this.gone = [...this.gone, data.stub_id];
                    this.stubRepointed = {
                        stubName: data.stub_name,
                        target: { id: data.target.id, name: data.target.name },
                        links: data.links,
                        akaAdded: data.aka_added,
                        factsMoved: data.facts_moved || 0,
                        notes: data.notes || [],
                    };
                    if (data.stub_id === this.selectedThingId) {
                        // the stub's page is gone: the target's stands in
                        this.closeThing();
                        this.showThing(data.target.id);
                        this.thing = data.target;
                    } else if (data.target.id === this.selectedThingId && !this.thingAt) {
                        this.thing = data.target;
                    } else {
                        // the open page's links to the stub point elsewhere
                        this.refreshThing();
                    }
                    this.listStubs();
                    this.listAllThings();
                    break;
                case 'match_names':
                    // a reply for text (or a date) since changed is dropped
                    if (
                        this.nameLookup
                        && data.text === this.nameLookup.text
                        && sameDate(data.at, this.nameLookup.at)
                    ) {
                        this.nameMatches = { ...this.nameLookup, matches: data.matches, unknown: data.unknown || [] };
                        this.nameLookup = null;
                    }
                    break;
                case 'plan_scene':
                case 'continue_scene':
                    if (this.setupPending && this.setupRequest?.action === action) {
                        this.sceneSetup = data;
                        this.setupPending = false;
                    }
                    break;
                case 'plan_failed':
                case 'continue_failed':
                    if (this.setupPending) {
                        this.setupError = message.message;
                        this.setupPending = false;
                    }
                    break;
                case 'start_scene':
                    this.closeSetup();
                    this.startedScene = data;
                    this.listScenes();
                    // the stubs the setup used are filled in now
                    this.listAllThings();
                    this.listStubs();
                    break;
                case 'start_failed':
                    this.setupError = message.message;
                    this.clearPending('start_scene');
                    break;
                case 'reposition_scene':
                    this.scenes = this.scenes.map((scene) => (scene.id === data.id ? data : scene));
                    this.refreshPresent();
                    break;
                case 'preview_thing':
                    if (this.previewPending) {
                        this.previewPending = false;
                        this.draftTaken(data, 'new');
                    }
                    break;
                case 'use_version':
                    if (this.draft?.key === data.draft_key) {
                        this.draftTaken(data, 'restore');
                    }
                    break;
                case 'discard_preview':
                    break;
                case 'draft_render':
                    if (this.draft?.key === data.draft_key && this.draft.renderSeq === data.seq) {
                        const { draft_key: _key, seq: _seq, ...rendered } = data;
                        this.draft = { ...this.draft, rendered };
                    }
                    break;
                case 'make_stub_from_text':
                case 'link_text':
                    if (data.draft_key) {
                        if (this.draft?.key === data.draft_key) {
                            this.draftTaken(data, 'rebase', { done: 'selecting', fresh: data.new_name ? [nameKey(data.new_name)] : [] });
                        }
                    } else {
                        if (data.id === this.selectedThingId) {
                            this.pageTaken(data);
                        } else {
                            this.refreshThing();
                        }
                        if (data.aka_added?.length) {
                            this.showNotes(action, [otherNamesNote(data.aka_added)]);
                        }
                        this.listStubs();
                        this.listAllThings();
                        const expand = this.stubExpandAfter;
                        this.stubExpandAfter = null;
                        if (action === 'make_stub_from_text' && expand && data.stub_id) {
                            this.expandStub({ id: data.stub_id, kind: expand.kind, name: expand.name });
                        }
                    }
                    break;
                case 'copy_fact':
                    this.showNotes(action, [`Copied to ${data.target.name}`, ...(data.notes || [])]);
                    this.refreshThing();
                    break;
                case 'preview_failed':
                    if (this.previewPending) {
                        this.previewError = message.message;
                        this.previewPending = false;
                    }
                    break;
                case 'accept_preview':
                    // the owner's re-picks teach their things the names
                    for (const repick of this.previewRequest?.repicks || []) {
                        this.addOtherName(repick.id, repick.name);
                    }
                    if (this.draft) {
                        const { [this.draft.key]: _done, ...rest } = this.draftEdits;
                        this.draftEdits = rest;
                    }
                    this.draft = null;
                    this.draftShown = true;
                    this.previewRequest = null;
                    this.expanding = null;
                    this.showNotes(action, data.notes);
                    if (this.acceptOpens) {
                        this.visit({ thingId: data.id });
                        this.openedFrom = this.selectedThingId;
                        this.selectedThingId = data.id;
                        this.thingAt = null;
                        this.thing = data;
                    } else {
                        this.accepted = { id: data.id, kind: data.kind, name: data.name };
                    }
                    this.acceptOpens = true;
                    // the names its facts invent are stubs now, of any kind
                    this.listStubs();
                    this.listAllThings();
                    break;
                case 'preview_merge':
                    if (this.merge && this.merge.fromId === data.preview.from_id && this.merge.intoId === data.preview.into_id) {
                        this.merge = { ...this.merge, preview: data.preview, pending: false };
                    }
                    break;
                case 'accept_merge': {
                    this.merge = null;
                    this.gone = [...this.gone, data.from_id];
                    const into = data.into;
                    const lines = [
                        `Merged into ${data.main_name}: ${data.facts_moved} fact${data.facts_moved === 1 ? '' : 's'} and ${data.links} link${data.links === 1 ? '' : 's'} moved over`,
                        ...(data.aka_added?.length ? [`now also known as ${data.aka_added.join(', ')}`] : []),
                        ...(data.notes || []),
                    ];
                    this.showNotes(action, lines);
                    this.visit({ thingId: into.id });
                    this.openedFrom = null;
                    this.selectedThingId = into.id;
                    this.thingAt = null;
                    this.thing = into;
                    this.listStubs();
                    this.listAllThings();
                    break;
                }
                case 'move_fact':
                    this.showNotes(action, [`Moved to ${data.target.name}`, ...(data.notes || [])]);
                    if (data.target.id === this.selectedThingId && !this.thingAt) {
                        this.thing = data.target;
                    } else {
                        this.refreshThing();
                    }
                    this.listStubs();
                    break;
                case 'pick_date':
                    this.showNotes(action, data.notes);
                    if (data.thing && data.thing.id === this.selectedThingId) {
                        this.thing = data.thing;
                    } else {
                        this.refreshThing();
                    }
                    break;
                case 'get_curation':
                    this.curation = data;
                    break;
                case 'set_curation':
                    this.curation = data;
                    this.curationSaved = true;
                    break;
                case 'find_mix':
                    // a reply for parents since changed is dropped
                    if (this.mixLookup && sameParents(this.mixLookup.parents, data.parents)) {
                        this.mixFound = data;
                        this.mixLookup = null;
                    }
                    break;
                case 'prose_updated':
                    if (this.proseRegenerating === data.id) {
                        this.proseRegenerating = null;
                        this.proseRegeneratingSection = null;
                    }
                    if (data.id === this.selectedThingId) {
                        this.request('get_thing', { id: data.id, at: this.thingAt });
                    }
                    break;
                case 'prose_failed':
                    if (this.proseRegenerating === data?.id) {
                        this.proseRegenerating = null;
                        this.proseRegeneratingSection = null;
                    }
                    this.error = message.message;
                    break;
                case 'operation_done':
                    if (message.error) {
                        // the failed request can't be told apart, so every
                        // spinner stops. While the setup step waits, the
                        // error shows in its dialog, not behind it.
                        if (this.setupPending || this.pending.start_scene) {
                            this.setupError = message.error.message;
                        } else {
                            this.error = message.error.message;
                        }
                        this.pending = {};
                        // the failed request may be the delete (or its
                        // check): close its dialog, so the error shows
                        this.deleteCheck = null;
                        this.previewPending = false;
                        this.proseRegenerating = null;
                        this.proseRegeneratingSection = null;
                        this.setupPending = false;
                        // the failed request may be the name or mix lookup
                        this.nameLookup = null;
                        this.mixLookup = null;
                        this.acceptOpens = true;
                        // or a merge's preview
                        if (this.merge?.pending) {
                            this.merge = { ...this.merge, pending: false };
                        }
                        // or a group's synopsis or "+ Add", or a fact draft
                        this.synopses = Object.fromEntries(Object.entries(this.synopses).map(([key, value]) => [key, { ...value, pending: false }]));
                        this.groupAdds = Object.fromEntries(Object.entries(this.groupAdds)
                            .filter(([, value]) => !value.pending)
                            .map(([key, value]) => [key, { ...value, accepting: false }]));
                        if (this.factDraft?.pending) {
                            this.factDraft = null;
                        } else if (this.factDraft?.accepting) {
                            this.factDraft = { ...this.factDraft, accepting: false };
                        }
                        // or the draft's accept, addition or selection
                        if (this.draft) {
                            this.draft = { ...this.draft, accepting: false, adding: null, selecting: null };
                        }
                        this.stubExpandAfter = null;
                        if (this.namesWanted.length) {
                            this.namesFailed = this.namesWanted.at(-1);
                        }
                        this.namesWanted = [];
                        // the page back opened is gone: back goes on
                        const failed = this.backOpening;
                        this.backOpening = null;
                        if (failed && failed === this.selectedThingId) {
                            this.gone = [...this.gone, failed];
                            this.error = null;
                            this.goBack();
                        }
                    }
                    break;
                default:
                    if (FILING_EDITS.includes(action)) {
                        this.filingEdited(action, data);
                    } else if (EDIT_ACTIONS.includes(action) && data.id === this.selectedThingId) {
                        this.thing = data;
                        if (action === 'repoint_ref' && data.aka_added?.length) {
                            this.showNotes(action, [otherNamesNote(data.aka_added)]);
                            this.listAllThings();
                        }
                        // a linked fact (or a new name) changes the stubs' mentions
                        this.listStubs();
                        if (action === 'set_field') {
                            this.listThings(data.kind);
                        }
                    }
            }
            this.clearPending(action);
        },
    },
});
