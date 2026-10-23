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
// world cancels a running preview (or scene plan) without any reply, so
// opening (or creating) a world clears the preview, the scene setup and
// every spinner itself.
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
// `accepted`, so the character's box can carry on with it. A preview lists
// the inherited facts it was made with (`preview.inherited`);
// `setPreviewOverride` marks one as replaced by one of the preview's own
// facts before accepting.
//
// Stubs (names mentioned but not made yet): `stubs` is `list_stubs`'s list,
// ignored ones included (the Stubs tab filters them), asked for again
// whenever an edit, an accept, a delete or a started scene may have made,
// filled or re-counted one. `ignoreStub` and `changeStubKind` answer with
// the stub's page; the open page, if it's another thing, is fetched again,
// since its links to the stub change with it. `expandStub` leaves the page
// for the stub's kind, whose create box then expands it (`expanding`):
// the preview carries the stub's id, and accepting fills the stub in place.
// Expanding over an unaccepted preview asks first (`expandAsk`, answered
// by `confirmExpand` or `keepPreview`). Expanding also asks for
// `stub_suggestion`, the create box's starting prompt and the mention
// context (`stubSuggestion`). A preview of a new
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
// touches the rest of the fact. `referenceTargets` is what Add reference searches: every entry and
// live stub.
//
// Spheres: the create box of kind "sphere" previews a sphere's core
// (`previewSphere`: a template and a prompt, a stub it expands, or the
// thing "Make it a sphere…" promotes, `promoting`) into `spherePreview`;
// "+ New branch" on a sphere's page previews a branch (`previewBranch`)
// into `branchPreview`. Either is written by `accept_sphere`, which opens
// the sphere. Fill (`fillDrawer`) asks for one drawer's items at a time
// (`fill`); `acceptFill` writes those the owner kept. The page's sphere
// edits (`setDrawers`, `setPartOf`, `setTies`, `addException`,
// `endItem`) answer with the thing edited; when that's not the open page
// (a thing filed from the sphere's "+ Add"), the page is fetched again.
// `addTie` adds a tie from the sphere's side: the character is fetched
// first, since `set_ties` writes its whole list (`tieQueue`).
// `fetchSphere` keeps a sphere's payload in `sphereInfo` (for a Part of
// editor's drawers, or the items an exception can reject). A character
// preview's proposed ties can be dropped, whole or one exception at a
// time, before it's accepted (`dropPreviewTie`, `dropPreviewException`).
//
// History (the thing page's back arrow): `section` is the World tab's
// open section (a kind's list, or 'stubs'), and a page is `{section,
// thingId, at}` (`thingId` null for the section itself). Opening a page
// (`openThing`: a link, a card, a drawer item, a tie, a reference; a
// section from the side list, `showSection`; an accepted preview's page)
// pushes the page left onto `history`, unless it's the same page (a thing
// as of another date is the same page). `goBack` pops it without pushing,
// skipping things deleted (or re-pointed away) since (`gone`); with
// nothing left it shows the section. Each entry keeps the date its page
// was viewed as of, so back returns to it as it was. A world switch starts
// the history afresh.
//
// Re-pointing a stub: `repointStub` sends `repoint_stub`; the reply (in
// `stubRepointed`, for the Stubs page's note) forgets the stub, and a
// page on the stub opens the target instead.
//
// Curation: a preview is edited in place before it's accepted
// (`editPreview(type, changes)`, type 'create', 'sphere', 'branch' or
// 'fill'): its own facts' and items' ticks, the elsewhere facts (ticks,
// categories, a stub row's "same as X?"), the move-in and re-file rows. An
// accept sends the preview as the owner left it, ticks and all.
// `addOuterBody` asks `add_outer_body` to put a body the owner names
// around a part; the reply replaces that preview. The answer to "Is this
// X?" goes with the accept (`acceptPreview(..., {sameTargetId})`). Every
// accept's `notes` (what was left out, and why) land in `notes` for the
// World tab to show, as do a move's, a merge's and a date pick's. A merge
// (`previewMerge`, `acceptMerge`) keeps its preview in `merge`; the merged
// entry's page opens once it's done. `moveFact`, `setHeldBy` and
// `pickDate` edit a fact where its page shows it; `getCuration` and
// `setCuration` read and write the world's curation knobs (`curation`).
//
// No `@/` imports: the node checks (checks/worlds.check.mjs) load this file.

import { defineStore } from 'pinia';

import { formatDate } from '../components/worlds/worldDates.js';
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

function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// A preview fact's text as `LinkedText` segments: the names it invents
// (`newNames`, the preview's `new_names`: each name, the ways the text
// writes it and its other names) marked `fresh`, since they become stubs
// on accept; the rest plain. Earliest match first, then the longest.
export function previewSegments(text, newNames = []) {
    const spans = [];
    for (const found of newNames) {
        const spellings = [found.name, ...(found.written || []), ...(found.aka || []).map((entry) => entry.name)];
        for (const spelling of spellings.filter(Boolean)) {
            const pattern = new RegExp(`(?<![\\p{L}\\p{N}])${escapeRegExp(spelling)}(?![\\p{L}\\p{N}])`, 'gu');
            for (const match of text.matchAll(pattern)) {
                spans.push({ start: match.index, end: match.index + match[0].length, kind: found.kind });
            }
        }
    }
    spans.sort((a, b) => a.start - b.start || b.end - a.end);
    const segments = [];
    let at = 0;
    for (const span of spans) {
        if (span.start < at) {
            continue;
        }
        if (span.start > at) {
            segments.push({ text: text.slice(at, span.start), ref: null, stub: false });
        }
        segments.push({ text: text.slice(span.start, span.end), ref: null, stub: false, fresh: true, kind: span.kind });
        at = span.end;
    }
    if (at < text.length) {
        segments.push({ text: text.slice(at), ref: null, stub: false });
    }
    return segments;
}

// replies to these clear their own spinner (`pending[action]`)
const EDIT_ACTIONS = ['add_fact', 'correct_fact', 'end_fact', 'remove_fact', 'set_field', 'override_fact', 'make_stub', 'repoint_ref', 'set_held_by'];

// sphere edits: each answers with the thing it changed, which may not be
// the open page
const SPHERE_EDITS = ['set_drawers', 'set_part_of', 'set_ties', 'add_exception', 'end_item', 'accept_fill', 'add_statement'];

// what a sphere page shows in its drawers, Timeline and summary rather
// than among its facts
const SPHERE_FACT_CATEGORIES = ['statement', 'timeline', 'about'];

// The facts a thing page lists under Facts: on a sphere page (a place
// sphere too) not its statements, timeline and about facts, which show
// (and are edited) where they belong; on a character's not its "but…"
// exceptions, which its Ties show.
export function listedFacts(thing) {
    const exceptions = new Set((thing?.ties || []).flatMap((tie) => tie.exceptions.map((e) => e.fact_id)));
    return (thing?.facts || []).filter(
        (fact) => !exceptions.has(fact.fact_id) && !(thing.sphere && SPHERE_FACT_CATEGORIES.includes(fact.category)),
    );
}

// the message when a character is tied from a sphere it's tied to already
export const ALREADY_TIED = 'already tied; edit the tie on its page';

// A wire date as a request takes it (no label), or null.
export function dateIn(date) {
    return date ? { instant: date.instant, precision: date.precision } : null;
}

// A character's (or real being's) payload `ties` as `set_ties` takes
// them, each with the part of its sphere it's `within` (null: the sphere
// as a whole).
export function tiesPayload(ties) {
    return (ties || []).map((tie) => ({
        sphere_id: tie.sphere_id,
        role: tie.role || '',
        since: dateIn(tie.since),
        until: dateIn(tie.until),
        within: tie.within || null,
    }));
}

// The items of a sphere payload an exception can depart from: `{title,
// value}`, value `{thing_id}` or `{fact_id}`, each once, in drawer order.
export function rejectableItems(sphere) {
    const items = [];
    for (const drawer of sphere?.drawers || []) {
        for (const item of drawer.items) {
            const value = item.thing_id ? { thing_id: item.thing_id } : { fact_id: item.fact_id };
            items.push({ title: item.name, value });
        }
    }
    return items;
}

// A branch preview with the parent item `row` kept (`kept`) or dropped:
// a thing item goes in `drops`, a statement in `rejects`.
export function branchKept(preview, row, kept) {
    const key = row.thing_id ? 'drops' : 'rejects';
    const id = row.thing_id || row.fact_id;
    const others = (preview[key] || []).filter((other) => other !== id);
    return { ...preview, [key]: kept ? others : [...others, id] };
}

// --- curation -----------------------------------------------------------------

// the articles a name may lead with (`talemate.world.names.ARTICLES`)
const ARTICLES = ['the', 'a', 'an'];

// A name as the backend compares it (`links.name_key`): its words
// normalised, without a leading article.
export function nameKey(name) {
    const words = (name || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (words.length > 1 && ARTICLES.includes(words[0])) {
        words.shift();
    }
    return words.join(' ');
}

function plural(count, one, many = `${one}s`) {
    return `${count} ${count === 1 ? one : many}`;
}

// What accepting a preview (create, a sphere's core or Fill) would write:
// `{facts, items, here, elsewhere, stubs, movedIn, refiled}` -- its own
// facts ticked, its items ticked (a sphere's or Fill's: a statement, or
// one linking an entry the world has; a named new one counts only as the
// stub it makes), `here` the two together, the elsewhere facts ticked, the
// new stubs it'd make (its new names, the new entries a ticked elsewhere
// fact goes onto, its named new items; not one the owner marked as some
// thing already), and the facts moving in and entries re-filed, ticked.
export function previewCounts(preview) {
    const ticked = (rows) => (rows || []).filter((row) => row.ticked !== false);
    const isNewItem = (item) => !!item.name && !item.thing_id && !item.same_target_id;
    const elsewhere = ticked(preview?.elsewhere);
    const items = ticked(preview?.items);
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
    for (const item of items) {
        if (isNewItem(item)) {
            stubs.add(nameKey(item.name));
        }
    }
    const facts = ticked(preview?.facts).length;
    const kept = items.filter((item) => !isNewItem(item)).length;
    return {
        facts,
        items: kept,
        here: facts + kept,
        elsewhere: elsewhere.length,
        stubs: stubs.size,
        movedIn: (preview?.move_in || []).filter((row) => row.ticked).length,
        refiled: (preview?.refile || []).filter((row) => row.ticked).length,
    };
}

// The Accept line: "writes 3 facts here, 4 elsewhere, 1 new stub", "writes
// 1 fact and 2 items here" (`onto`: the entry the owner said it is,
// "writes 3 facts onto Ashenmere"); `noun` for what there's none of
// ("writes 0 items here" for Fill).
export function countsLine(counts, onto = null, noun = 'fact') {
    let what;
    if (counts.facts && counts.items) {
        what = `${plural(counts.facts, 'fact')} and ${plural(counts.items, 'item')}`;
    } else if (counts.items) {
        what = plural(counts.items, 'item');
    } else if (counts.facts) {
        what = plural(counts.facts, 'fact');
    } else {
        what = plural(0, noun);
    }
    const parts = [`writes ${what} ${onto ? `onto ${onto}` : 'here'}`];
    if (counts.elsewhere) {
        parts.push(`${counts.elsewhere} elsewhere`);
    }
    if (counts.stubs) {
        parts.push(plural(counts.stubs, 'new stub'));
    }
    if (counts.movedIn) {
        parts.push(`moves ${counts.movedIn} in`);
    }
    if (counts.refiled) {
        parts.push(`re-files ${counts.refiled}`);
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

// The indices of the rows (a preview's facts, Fill's items) that came
// unticked as repeats of what the world holds: "Already in the world"
// shows these, kept apart however the owner ticks them; a repeat that came
// ticked stays among the rest, showing its match.
export function shelvedRows(rows) {
    return (rows || []).flatMap((row, index) => (row.repeat_of && row.ticked === false ? [index] : []));
}

// `rows` with those at `indices` ticked (or not); the rest as they are.
export function rowsTicked(rows, indices, ticked) {
    const picked = new Set(indices);
    return (rows || []).map((row, index) => (picked.has(index) ? { ...row, ticked } : row));
}

// The move-in rows the owner set (`moveIn`, from MoveInSection) and the
// preview's own facts to go with them (ruling C24's other half): an own
// fact repeating a move the owner ticks (its `repeat_of.fact_id`) is
// unticked, marked `untickedByMove`, so the claim isn't written twice;
// unticking the move ticks it again. A fact the owner unticked themselves
// is left as it is. `{move_in, facts}`.
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
    return { move_in: moveIn || [], facts };
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
        // the create box: the request being previewed, and its reply
        previewRequest: null,
        previewPending: false,
        preview: null,
        previewError: null,
        // the indices of its facts that came unticked as repeats
        // (`shelvedRows`)
        previewShelved: [],
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
        // the last `stub_suggestion` reply: `{id, prompt, context}`
        stubSuggestion: null,
        // thing id -> the other names to add to it once it's fetched
        akaQueue: {},
        // the sphere create box: the request (`{template, prompt, fields,
        // stubId, promoteId, picks, newNames}`) and its preview
        spherePreviewRequest: null,
        spherePreviewPending: false,
        spherePreview: null,
        spherePreviewError: null,
        // the thing "Make it a sphere…" promotes: `{id, kind, name}`
        promoting: null,
        // "+ New branch": the request (`{parentId, prompt}`) and its preview
        branchRequest: null,
        branchPending: false,
        branchPreview: null,
        branchError: null,
        // which preview an `accept_sphere` is out for: 'sphere' or 'branch'
        sphereAccepting: null,
        // Fill, one drawer at a time: `{sphereId, drawerId, pending, items,
        // elsewhere, new_names, refile, shelved, error}` (the Fill
        // preview's parts; `shelved` as `previewShelved`)
        fill: null,
        // sphere id -> its payload, for editors that need its drawers
        sphereInfo: {},
        // the sphere ids a `get_thing` is out for, for `sphereInfo`
        sphereWanted: [],
        // character id -> the ties to add to it once it's fetched
        tieQueue: {},
        // the preview an `add_outer_body` is out for (`outerToken`): its
        // type ('create', 'sphere', 'branch' or 'fill') and which one it
        // was; a reply for one since replaced is dropped
        outerFor: null,
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

// how many Fills have been asked for: each Fill's `ask`, so a reply for an
// earlier Fill of the same drawer is told apart
let fillAsks = 0;

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

        // `stubId`: the stub the preview expands (its kind's create box
        // opened from it); `picks` and `newNames`: the prompt's names, as
        // the owner left them; `repicks`: the owner's re-picks (`{id,
        // name}`), each thing taught its name once the preview is accepted
        previewThing(kind, prompt, fields = {}, stubId = null, { picks = {}, newNames = [], repicks = [] } = {}) {
            this.previewRequest = { kind, prompt, fields, stubId, picks, newNames, repicks };
            this.preview = null;
            this.previewError = null;
            this.previewPending = true;
            this.request('preview_thing', {
                kind,
                prompt,
                fields,
                ...(stubId ? { stub_id: stubId } : {}),
                ...linkFields(picks, newNames),
            });
        },

        regeneratePreview() {
            const req = this.previewRequest;
            if (req) {
                this.previewThing(req.kind, req.prompt, req.fields, req.stubId, req);
            }
        },

        // drop the preview, keeping the request so the prompt can be edited
        discardPreview() {
            this.preview = null;
            this.previewError = null;
            this.previewPending = false;
        },

        // forget the preview and its request (its box closed)
        cancelPreview() {
            this.discardPreview();
            this.previewRequest = null;
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
        repointStub(stubId, targetId) {
            this.stubRepointed = null;
            this.pending = { ...this.pending, repoint_stub: true };
            this.request('repoint_stub', { stub_id: stubId, target_id: targetId });
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
            // a culture (a legacy kind) is made a culture sphere
            const target = stub.kind === 'culture'
                ? { id: stub.id, kind: 'sphere', name: stub.name, was: 'culture' }
                : { id: stub.id, kind: stub.kind, name: stub.name, ...(stub.was ? { was: stub.was } : {}) };
            if ((this.preview || this.spherePreview) && !discard) {
                this.expandAsk = target;
                return;
            }
            this.expandAsk = null;
            this.cancelPreview();
            this.cancelSpherePreview();
            this.promoting = null;
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
            if (stub?.promote) {
                this.makeSphere(stub, { discard: true });
            } else if (stub) {
                this.expandStub(stub, { discard: true });
            }
        },

        // the owner keeps the preview: the stub isn't expanded
        keepPreview() {
            this.expandAsk = null;
        },

        stopExpanding() {
            this.expanding = null;
        },

        // --- spheres ------------------------------------------------------

        // "Make it a sphere…": a stub is expanded as a sphere; a lore entry
        // or a place is promoted in the sphere create box
        // An unaccepted preview isn't dropped unasked (`expandAsk`, as
        // `expandStub`).
        makeSphere(thing, { discard = false } = {}) {
            if (thing.stub) {
                this.expandStub({ id: thing.id, kind: 'sphere', name: thing.name, was: thing.kind }, { discard });
                return;
            }
            if ((this.preview || this.spherePreview) && !discard) {
                this.expandAsk = { id: thing.id, kind: thing.kind, name: thing.name, promote: true };
                return;
            }
            this.expandAsk = null;
            this.cancelPreview();
            this.cancelSpherePreview();
            this.expanding = null;
            this.visit({ section: 'sphere', thingId: null });
            this.section = 'sphere';
            this.closeThing();
            this.promoting = { id: thing.id, kind: thing.kind, name: thing.name };
        },

        stopPromoting() {
            this.promoting = null;
        },

        // `stubId`: the stub it expands; `promoteId`: the thing it promotes
        previewSphere(template, prompt, fields = {}, { stubId = null, promoteId = null, picks = {}, newNames = [] } = {}) {
            this.spherePreviewRequest = { template, prompt, fields, stubId, promoteId, picks, newNames };
            this.spherePreview = null;
            this.spherePreviewError = null;
            this.spherePreviewPending = true;
            this.request('preview_sphere', {
                template,
                prompt,
                fields,
                ...(stubId ? { stub_id: stubId } : {}),
                ...(promoteId ? { promote_id: promoteId } : {}),
                ...linkFields(picks, newNames),
            });
        },

        regenerateSpherePreview() {
            const req = this.spherePreviewRequest;
            if (req) {
                this.previewSphere(req.template, req.prompt, req.fields, req);
            }
        },

        discardSpherePreview() {
            this.spherePreview = null;
            this.spherePreviewError = null;
            this.spherePreviewPending = false;
        },

        cancelSpherePreview() {
            this.discardSpherePreview();
            this.spherePreviewRequest = null;
        },

        acceptSphere(changes = {}) {
            if (!this.spherePreview) {
                return;
            }
            this.sphereAccepting = 'sphere';
            this.pending = { ...this.pending, accept_sphere: true };
            this.request('accept_sphere', { preview: { ...this.spherePreview, ...changes } });
        },

        previewBranch(parentId, prompt) {
            this.branchRequest = { parentId, prompt };
            this.branchPreview = null;
            this.branchError = null;
            this.branchPending = true;
            this.request('preview_branch', { parent_id: parentId, prompt });
        },

        discardBranch() {
            this.branchRequest = null;
            this.branchPreview = null;
            this.branchError = null;
            this.branchPending = false;
        },

        // keep (or drop) one of the parent's items in the branch preview
        setBranchKept(row, kept) {
            if (this.branchPreview) {
                this.branchPreview = branchKept(this.branchPreview, row, kept);
            }
        },

        acceptBranch(changes = {}) {
            if (!this.branchPreview) {
                return;
            }
            this.sphereAccepting = 'branch';
            this.pending = { ...this.pending, accept_sphere: true };
            this.request('accept_sphere', { preview: { ...this.branchPreview, ...changes } });
        },

        fillDrawer(sphereId, drawerId) {
            fillAsks += 1;
            this.fill = { sphereId, drawerId, ask: fillAsks, pending: true, items: null, error: null };
            this.request('fill_drawer', { sphere_id: sphereId, drawer_id: drawerId });
        },

        discardFill() {
            this.fill = null;
        },

        // Fill's preview as the owner left it: its items (each with its
        // tick), elsewhere facts, outer bodies and re-file rows
        acceptFill() {
            const fill = this.fill;
            if (!fill?.items) {
                return;
            }
            this.pending = { ...this.pending, accept_fill: true };
            this.request('accept_fill', {
                sphere_id: fill.sphereId,
                drawer_id: fill.drawerId,
                items: fill.items,
                elsewhere: fill.elsewhere || [],
                new_names: fill.new_names || [],
                refile: fill.refile || [],
            });
        },

        // a statement written by hand into one of a sphere's drawers;
        // `links` as addFact's
        addStatement(sphereId, drawerId, text, { picks = {}, newNames = [], spans = [] } = {}) {
            this.pending = { ...this.pending, add_statement: true };
            this.request('add_statement', {
                sphere_id: sphereId,
                drawer_id: drawerId,
                text,
                ...linkFields(picks, newNames, spans),
                at: this.thingAt,
            });
        },

        // the sphere's drawers, in order, as the page shows them (see
        // `drawersPayload`); one without an `id` is new
        setDrawers(sphereId, drawers) {
            this.pending = { ...this.pending, set_drawers: true };
            this.request('set_drawers', { sphere_id: sphereId, drawers, at: this.thingAt });
        },

        // file `thingId` in a sphere's drawer; a null `sphereId` takes it
        // out of every sphere
        setPartOf(thingId, sphereId, drawerId = 'unsorted') {
            this.pending = { ...this.pending, set_part_of: true };
            this.request('set_part_of', {
                thing_id: thingId,
                sphere_id: sphereId,
                ...(sphereId ? { drawer_id: drawerId } : {}),
                at: thingId === this.selectedThingId ? this.thingAt : null,
            });
        },

        // a character's whole ties list (`tiesPayload`'s shape)
        setTies(characterId, ties) {
            this.pending = { ...this.pending, set_ties: true };
            this.request('set_ties', {
                character_id: characterId,
                ties,
                at: characterId === this.selectedThingId ? this.thingAt : null,
            });
        },

        // a tie added from the sphere's side: `{sphere_id, role, since}`,
        // written once the character is fetched
        addTie(characterId, tie) {
            this.tieQueue = { ...this.tieQueue, [characterId]: [...(this.tieQueue[characterId] || []), tie] };
            this.pending = { ...this.pending, set_ties: true };
            this.request('get_thing', { id: characterId, at: null });
        },

        // `rejects`: `{thing_id}`, `{fact_id}` or null (the sphere as a whole)
        addException(characterId, sphereId, text, rejects = null) {
            this.pending = { ...this.pending, add_exception: true };
            this.request('add_exception', {
                character_id: characterId,
                sphere_id: sphereId,
                text,
                rejects,
                at: characterId === this.selectedThingId ? this.thingAt : null,
            });
        },

        // end the sphere's own `item` (a drawer item) at `at`, by `by` (any
        // thing id, or null)
        endItem(sphereId, item, at, by = null) {
            this.pending = { ...this.pending, end_item: true };
            this.request('end_item', {
                sphere_id: sphereId,
                ...(item.thing_id ? { thing_id: item.thing_id } : { fact_id: item.fact_id }),
                at,
                by,
            });
        },

        // the sphere's payload into `sphereInfo`
        fetchSphere(id) {
            if (!this.sphereWanted.includes(id)) {
                this.sphereWanted = [...this.sphereWanted, id];
            }
            this.request('get_thing', { id, at: null });
        },

        dropPreviewTie(index) {
            if (this.preview) {
                this.preview = { ...this.preview, ties: this.preview.ties.filter((_tie, i) => i !== index) };
            }
        },

        dropPreviewException(tieIndex, exceptionIndex) {
            if (!this.preview) {
                return;
            }
            const ties = this.preview.ties.map((tie, i) => (i === tieIndex
                ? { ...tie, exceptions: tie.exceptions.filter((_e, j) => j !== exceptionIndex) }
                : tie));
            this.preview = { ...this.preview, ties };
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
        acceptPreview(changes = {}, { open = true, intoStub = null, sameTargetId = null } = {}) {
            if (!this.preview) {
                return;
            }
            this.acceptOpens = open;
            this.accepted = null;
            this.pending = { ...this.pending, accept_preview: true };
            this.request('accept_preview', {
                preview: { ...this.preview, ...changes },
                ...(intoStub ? { into_stub: intoStub } : {}),
                ...(sameTargetId ? { same_target_id: sameTargetId } : {}),
            });
        },

        // --- curation -----------------------------------------------------

        // the preview of `type` ('create', 'sphere', 'branch', 'fill')
        previewOf(type) {
            if (type === 'create') {
                return this.preview;
            }
            if (type === 'sphere') {
                return this.spherePreview;
            }
            if (type === 'branch') {
                return this.branchPreview;
            }
            const fill = this.fill;
            return fill?.items
                ? { sphere_id: fill.sphereId, drawer_id: fill.drawerId, items: fill.items, elsewhere: fill.elsewhere || [], new_names: fill.new_names || [], refile: fill.refile || [] }
                : null;
        },

        // the owner's edits to a preview before it's accepted
        editPreview(type, changes) {
            if (!this.previewOf(type)) {
                return;
            }
            if (type === 'create') {
                this.preview = { ...this.preview, ...changes };
            } else if (type === 'sphere') {
                this.spherePreview = { ...this.spherePreview, ...changes };
            } else if (type === 'branch') {
                this.branchPreview = { ...this.branchPreview, ...changes };
            } else {
                this.fill = { ...this.fill, ...changes };
            }
        },

        // which preview of `type` is shown now: its request (a Fill: its
        // sphere and drawer), so a reply can tell it's still the one
        outerToken(type) {
            if (type === 'create') {
                return { type, request: this.previewRequest, pending: this.previewPending };
            }
            if (type === 'sphere') {
                return { type, request: this.spherePreviewRequest, pending: this.spherePreviewPending };
            }
            if (type === 'branch') {
                return { type, request: this.branchRequest, pending: this.branchPending };
            }
            return { type, request: this.fill ? `${this.fill.sphereId}:${this.fill.drawerId}:${this.fill.ask}` : null, pending: !!this.fill?.pending };
        },

        // whether an `add_outer_body` reply (`previewType` as sent) is for
        // the preview the token was taken for, still shown and not being
        // asked for again
        outerStillFor(token, previewType) {
            if (!token || (token.type === 'branch' ? 'sphere' : token.type) !== previewType) {
                return false;
            }
            const now = this.outerToken(token.type);
            return now.request === token.request && !now.pending && !!this.previewOf(token.type);
        },

        // put a body the owner names (`outer`: `{name, template,
        // part_of}`) around the part `rowName` of a preview; the reply
        // replaces that preview, if it's still the one shown
        addOuterBody(type, rowName, outer, asSphere = false) {
            const preview = this.previewOf(type);
            if (!preview) {
                return;
            }
            this.outerFor = this.outerToken(type);
            this.pending = { ...this.pending, add_outer_body: true };
            this.request('add_outer_body', {
                preview_type: type === 'branch' ? 'sphere' : type,
                preview,
                row_name: rowName,
                outer,
                as_sphere: asSphere,
            });
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
            this.preview = { ...this.preview, facts };
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
        // `factId` at `toId`, keeping its words
        repointRef(factId, occurrence, toId) {
            this.edit('repoint_ref', { fact_id: factId, occurrence, to_id: toId });
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

        // the queued ties of `character` (a `get_thing` reply) written,
        // after its own, unless it has a tie to that sphere already
        writeQueuedTies(character) {
            const { [character.id]: added, ...rest } = this.tieQueue;
            this.tieQueue = rest;
            const ties = tiesPayload(character.ties);
            const fresh = added.filter((tie) => !ties.some((other) => other.sphere_id === tie.sphere_id));
            if (fresh.length < added.length) {
                // tied already (an ended tie too): edited on its page
                this.error = ALREADY_TIED;
                this.clearPending('set_ties');
                return;
            }
            for (const tie of fresh) {
                ties.push({ sphere_id: tie.sphere_id, role: tie.role || '', since: dateIn(tie.since), until: null });
            }
            this.request('set_ties', { character_id: character.id, ties, at: null });
        },

        // a sphere edit's reply (`data`, the thing it changed): the open
        // page takes it, or is fetched again when it's another thing (filed
        // or tied from the page); a Fill's names, and linked text, may
        // make stubs
        sphereEdited(action, data) {
            // a reply comes as of the edit's date (end_item's, the
            // latest): a page viewed as of another date is fetched again
            if (data.id === this.selectedThingId && !this.thingAt) {
                this.thing = data;
            } else {
                this.refreshThing();
            }
            if (this.sphereInfo[data.id] && data.sphere) {
                this.sphereInfo = { ...this.sphereInfo, [data.id]: data };
            }
            if (action === 'accept_fill') {
                this.fill = null;
                this.showNotes(action, data.notes);
                this.listAllThings();
            }
            this.listStubs();
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
                    if (data.id === this.backOpening) {
                        this.backOpening = null;
                    }
                    if (data.id === this.selectedThingId) {
                        this.thing = data;
                    }
                    if (this.akaQueue[data.id]) {
                        this.writeOtherNames(data);
                    }
                    if (this.sphereWanted.includes(data.id)) {
                        this.sphereWanted = this.sphereWanted.filter((id) => id !== data.id);
                        this.sphereInfo = { ...this.sphereInfo, [data.id]: data };
                    }
                    if (this.tieQueue[data.id]) {
                        this.writeQueuedTies(data);
                    }
                    break;
                case 'preview_sphere':
                    if (this.spherePreviewPending) {
                        this.spherePreview = data;
                        this.spherePreviewPending = false;
                    }
                    break;
                case 'preview_sphere_failed':
                    if (this.spherePreviewPending) {
                        this.spherePreviewError = message.message;
                        this.spherePreviewPending = false;
                    }
                    break;
                case 'preview_branch':
                    if (this.branchPending) {
                        this.branchPreview = data;
                        this.branchPending = false;
                    }
                    break;
                case 'preview_branch_failed':
                    if (this.branchPending) {
                        this.branchError = message.message;
                        this.branchPending = false;
                    }
                    break;
                case 'accept_sphere':
                    if (this.sphereAccepting === 'branch') {
                        this.discardBranch();
                    } else {
                        this.cancelSpherePreview();
                        this.expanding = null;
                        this.promoting = null;
                    }
                    this.sphereAccepting = null;
                    this.showNotes(action, data.notes);
                    this.visit({ thingId: data.id });
                    this.openedFrom = this.selectedThingId;
                    this.selectedThingId = data.id;
                    this.thingAt = null;
                    this.thing = data;
                    this.listStubs();
                    this.listAllThings();
                    break;
                case 'fill_drawer':
                    if (this.fill?.pending && this.fill.sphereId === data.sphere_id && this.fill.drawerId === data.drawer_id) {
                        this.fill = {
                            ...this.fill,
                            pending: false,
                            items: data.items,
                            elsewhere: data.elsewhere || [],
                            new_names: data.new_names || [],
                            refile: data.refile || [],
                            shelved: shelvedRows(data.items),
                        };
                    }
                    break;
                case 'fill_failed':
                    if (this.fill?.pending && this.fill.drawerId === data?.drawer_id) {
                        this.fill = { ...this.fill, pending: false, error: message.message };
                    }
                    break;
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
                        this.preview = data;
                        this.previewShelved = shelvedRows(data.facts);
                        this.previewPending = false;
                    }
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
                    this.preview = null;
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
                case 'add_outer_body': {
                    // the preview it's for, if it's still the one shown
                    const token = this.outerFor;
                    this.outerFor = null;
                    const type = token?.type;
                    if (this.outerStillFor(token, data.preview_type)) {
                        const preview = data.preview;
                        if (type === 'fill') {
                            this.fill = {
                                ...this.fill,
                                items: preview.items,
                                elsewhere: preview.elsewhere || [],
                                new_names: preview.new_names || [],
                                refile: preview.refile || [],
                            };
                        } else {
                            this.editPreview(type, preview);
                        }
                    }
                    break;
                }
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
                        // or a sphere preview, a Fill or a queued tie
                        this.spherePreviewPending = false;
                        this.branchPending = false;
                        this.sphereAccepting = null;
                        if (this.fill?.pending) {
                            this.fill = { ...this.fill, pending: false, error: message.error.message };
                        }
                        this.tieQueue = {};
                        this.sphereWanted = [];
                        // or a merge's preview, or an outer body
                        if (this.merge?.pending) {
                            this.merge = { ...this.merge, pending: false };
                        }
                        this.outerFor = null;
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
                    if (SPHERE_EDITS.includes(action)) {
                        this.sphereEdited(action, data);
                    } else if (EDIT_ACTIONS.includes(action) && data.id === this.selectedThingId) {
                        this.thing = data;
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
