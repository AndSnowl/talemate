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
// No `@/` imports: the node checks (checks/worlds.check.mjs) load this file.

import { defineStore } from 'pinia';

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
const EDIT_ACTIONS = ['add_fact', 'correct_fact', 'end_fact', 'remove_fact', 'set_field', 'override_fact', 'make_stub', 'repoint_ref'];

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

        openThing(id, at = null) {
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
                this.openThing(this.selectedThingId, at);
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

        // the owner keeps the preview: the stub isn't expanded
        keepPreview() {
            this.expandAsk = null;
        },

        stopExpanding() {
            this.expanding = null;
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
        // without one fills. The owner's re-picks are taught to their
        // things once it's accepted (the `accept_preview` reply).
        acceptPreview(changes = {}, { open = true, intoStub = null } = {}) {
            if (!this.preview) {
                return;
            }
            this.acceptOpens = open;
            this.accepted = null;
            this.pending = { ...this.pending, accept_preview: true };
            this.request('accept_preview', {
                preview: { ...this.preview, ...changes },
                ...(intoStub ? { into_stub: intoStub } : {}),
            });
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
                    if (data.id === this.selectedThingId) {
                        this.thing = data;
                    }
                    if (this.akaQueue[data.id]) {
                        this.writeOtherNames(data);
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
                    this.listStubs();
                    if (data.id === this.selectedThingId) {
                        const back = pageAfterDelete(this.thing, this.heritage, this.openedFrom);
                        this.closeThing();
                        if (back) {
                            this.openThing(back);
                        }
                    }
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
                    if (this.acceptOpens) {
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
                    }
                    break;
                default:
                    if (EDIT_ACTIONS.includes(action) && data.id === this.selectedThingId) {
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
