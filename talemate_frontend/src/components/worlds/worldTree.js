// The World tab's lists (polish 5): the side tree, its search with text
// modifiers, and a kind's full list on its own page. Pure: the components
// only draw what these return.

import { OTHER_HEADING, mostPreciseHome, tagHeading } from './entryPage.js';

// The order kinds come in, wherever entries of several kinds are listed
// together (Connected sorts by it too, on the server).
export const KIND_ORDER = ['character', 'species', 'race', 'mix', 'place', 'event', 'item', 'lore', 'being'];

// The heading of a kind's list grouped by where, for entries filed nowhere
export const NOWHERE_HEADING = 'Nowhere';

// A search box's text as `{words, tag, inName, stub, when}`: `tag:city`
// (the entry's own tag), `in:Velikoye` or `in:"Night Court"` (filed in it,
// at any depth), `stub` (not made yet), `when:1020` (in the world that
// year). Anything else, a malformed or unknown modifier too, is plain
// words, matched against names.
export function parseSearch(text) {
    const found = { words: '', tag: null, inName: null, stub: false, when: null };
    const words = [];
    for (const token of String(text || '').match(/\S+?:"[^"]*"|\S+/g) || []) {
        let match;
        if ((match = token.match(/^tag:([^"\s]+)$/i))) {
            found.tag = match[1].toLowerCase();
        } else if ((match = token.match(/^in:"([^"]+)"$/i) || token.match(/^in:([^"\s]+)$/i))) {
            found.inName = match[1].trim().split(/\s+/).join(' ').toLowerCase();
        } else if (/^stub$/i.test(token)) {
            found.stub = true;
        } else if ((match = token.match(/^when:(-?\d+)$/i))) {
            found.when = Number(match[1]);
        } else {
            words.push(token);
        }
    }
    found.words = words.join(' ');
    return found;
}

// Whether a parsed search asks for anything at all
export function searching(search) {
    return !!search && (!!search.words || search.tag !== null || search.inName !== null || search.stub || search.when !== null);
}

// Whether `thing` (a `list_things` entry) answers `search`: every part
// that's set must hold. `byName`: a lowercased name or other name -> id;
// `filedIn(id)`: the ids an entry is filed in (to follow homes upward).
export function matchesSearch(thing, search, { byName = new Map(), filedIn = () => [] } = {}) {
    const words = (search.words || '').trim().toLowerCase();
    if (words && ![thing.name, ...(thing.aka || [])].some((name) => name.toLowerCase().includes(words))) {
        return false;
    }
    if (search.tag !== null && (thing.tag || '').toLowerCase() !== search.tag) {
        return false;
    }
    if (search.stub && !thing.stub) {
        return false;
    }
    if (search.inName !== null && !filedUnder(thing, byName.get(search.inName), filedIn)) {
        return false;
    }
    if (search.when !== null && !inWorldAt(thing, search.when)) {
        return false;
    }
    return true;
}

// whether `thing` is filed in `targetId`, directly or inside something
// that is, in any of its filings
function filedUnder(thing, targetId, filedIn) {
    if (!targetId) {
        return false;
    }
    const seen = new Set();
    const queue = [...(thing.filed_in || [])];
    while (queue.length) {
        const id = queue.shift();
        if (id === targetId) {
            return true;
        }
        if (!seen.has(id)) {
            seen.add(id);
            queue.push(...filedIn(id));
        }
    }
    return false;
}

// `when:`: a character (or a born being) from its birth on; an event over
// its span; anything without a span of its own, always
function inWorldAt(thing, year) {
    const span = thing.span;
    if (!span || span.from === null || span.from === undefined) {
        return true;
    }
    if (thing.kind === 'event') {
        return span.from <= year && year <= (span.until ?? span.from);
    }
    return span.from <= year;
}

// Each entry's parent in the side tree (id -> id or null): its most
// precise home among `things`; an entry whose homes loop back to it sits
// at the top (judged on the homes as filed). Without `nest`, all at the top.
export function treeParents(things, nest = true) {
    const byId = new Map((things || []).map((thing) => [thing.id, thing]));
    const parents = new Map();
    for (const thing of things || []) {
        parents.set(thing.id, nest ? mostPreciseHome(thing.filed_in, byId) : null);
    }
    const filed = new Map(parents);
    for (const thing of things || []) {
        const seen = new Set([thing.id]);
        for (let up = filed.get(thing.id); up; up = filed.get(up)) {
            if (up === thing.id) {
                parents.set(thing.id, null);
                break;
            }
            if (seen.has(up)) {
                break;
            }
            seen.add(up);
        }
    }
    return parents;
}

// The ids above `id` in its kind's side tree, nearest first: what opens
// when its page is opened
export function homesAbove(things, id) {
    const parents = treeParents(things);
    const out = [];
    for (let up = parents.get(id); up && !out.includes(up); up = parents.get(up)) {
        out.push(up);
    }
    return out;
}

const FOLDS_KEY = 'fantasymate:tree-open:';

// The kinds and entries the owner unfolded in a world's side tree, kept in
// the browser: `{kinds, entries}` (Sets). Empty when nothing is kept or
// the storage can't be read (a private window); never throws.
export function loadFolds(worldId, storage = globalThis.localStorage) {
    try {
        const kept = JSON.parse(storage?.getItem(FOLDS_KEY + worldId) || 'null');
        if (kept && Array.isArray(kept.kinds) && Array.isArray(kept.entries)) {
            return { kinds: new Set(kept.kinds), entries: new Set(kept.entries) };
        }
    } catch {
        // a bad value or no storage: start folded
    }
    return { kinds: new Set(), entries: new Set() };
}

export function saveFolds(worldId, { kinds, entries }, storage = globalThis.localStorage) {
    try {
        storage?.setItem(FOLDS_KEY + worldId, JSON.stringify({ kinds: [...kinds], entries: [...entries] }));
    } catch {
        // storage refused: the folds last as long as the page
    }
}

// The side tree of one kind: `[{thing, depth, folded, childCount,
// context}]`, plus `{more: {parentId, count}, depth}` rows. Entries come
// before stubs, each by name; with `nest`, each sits
// once under its most precise home among them (a loop has no top). All
// folded but `opened` (the owner's) and `openPath` (above the open page);
// an open entry shows its first `limit` children, then "more", unless
// it's in `showAll`. With a `search` that asks something, only matches
// show, with their homes as `context`, everything open.
export function sideTree(things, { nest = false, search = null, opened = new Set(), openPath = new Set(), showAll = new Set(), limit = 10, ctx = null } = {}) {
    const listed = things || [];
    const byName = (a, b) => a.name.localeCompare(b.name);
    const ordered = [...listed.filter((thing) => !thing.stub).sort(byName), ...listed.filter((thing) => thing.stub).sort(byName)];
    const parents = treeParents(ordered, nest);
    const children = new Map();
    const roots = [];
    for (const thing of ordered) {
        const parent = parents.get(thing.id);
        if (parent) {
            children.set(parent, [...(children.get(parent) || []), thing]);
        } else {
            roots.push(thing);
        }
    }
    const active = searching(search);
    const matched = new Set();
    const visible = new Set();
    if (active) {
        const context = ctx || searchContext(listed);
        for (const thing of ordered) {
            if (matchesSearch(thing, search, context)) {
                matched.add(thing.id);
                for (let id = thing.id; id && !visible.has(id); id = parents.get(id)) {
                    visible.add(id);
                }
            }
        }
    }
    const out = [];
    const walk = (thing, depth) => {
        if (active && !visible.has(thing.id)) {
            return;
        }
        const kids = (children.get(thing.id) || []).filter((kid) => !active || visible.has(kid.id));
        const open = active || opened.has(thing.id) || openPath.has(thing.id);
        out.push({ thing, depth, folded: kids.length > 0 && !open, childCount: kids.length, context: active && !matched.has(thing.id) });
        if (!open) {
            return;
        }
        const shown = active || showAll.has(thing.id) ? kids : kids.slice(0, limit);
        for (const kid of shown) {
            walk(kid, depth + 1);
        }
        if (shown.length < kids.length) {
            out.push({ more: { parentId: thing.id, count: kids.length - shown.length }, depth: depth + 1 });
        }
    };
    for (const root of roots) {
        walk(root, 0);
    }
    return out;
}

// what `matchesSearch` needs, from the entries at hand (the World tab
// passes every kind's, so `in:` reaches across kinds)
export function searchContext(things) {
    const byId = new Map((things || []).map((thing) => [thing.id, thing]));
    const byName = new Map();
    for (const thing of things || []) {
        for (const name of [thing.name, ...(thing.aka || [])]) {
            const key = String(name).trim().split(/\s+/).join(' ').toLowerCase();
            if (key && !byName.has(key)) {
                byName.set(key, thing.id);
            }
        }
    }
    return { byName, filedIn: (id) => byId.get(id)?.filed_in || [] };
}

const SORTS = {
    name: () => 0,
    recent: (a, b) => (b.changed_rev ?? 0) - (a.changed_rev ?? 0),
    connected: (a, b) => (b.connections ?? 0) - (a.connections ?? 0),
    date: (a, b) => {
        if (a.sort_date == null || b.sort_date == null) {
            return (a.sort_date == null) - (b.sort_date == null);
        }
        return a.sort_date - b.sort_date;
    },
};

// A kind's full list (its own page): `[{key, heading, rows}]`. By `where`
// (its most precise home of any kind, "In Velikoye"; none last,
// "Nowhere"), by `tag` (Connected's headings; untagged last, "Other"),
// or `none` (one group, no heading). Rows sorted by `sort`, then name.
export function groupList(things, { by = 'tag', sort = 'name', byId = new Map() } = {}) {
    const order = SORTS[sort] || SORTS.name;
    const rows = [...(things || [])].sort((a, b) => order(a, b) || a.name.localeCompare(b.name));
    if (by === 'none') {
        return [{ key: 'all', heading: null, rows }];
    }
    const groups = new Map();
    for (const thing of rows) {
        let key;
        let heading;
        if (by === 'where') {
            const home = mostPreciseHome(thing.filed_in, byId);
            key = home ? `in:${home}` : 'nowhere';
            heading = home ? `In ${byId.get(home).name}` : NOWHERE_HEADING;
        } else {
            key = thing.tag ? `tag:${thing.tag}` : 'other';
            heading = thing.tag ? tagHeading(thing.tag) : OTHER_HEADING;
        }
        if (!groups.has(key)) {
            groups.set(key, { key, heading, rows: [] });
        }
        groups.get(key).rows.push(thing);
    }
    const last = (group) => group.key === 'nowhere' || group.key === 'other';
    return [...groups.values()].sort((a, b) => last(a) - last(b) || a.heading.localeCompare(b.heading));
}

// "in Velikoye" (its most precise home), "in Velikoye +1" when it's filed
// in more, '' when in nothing listed
export function whereLabel(thing, byId) {
    const homes = (thing.filed_in || []).filter((id) => byId.has(id));
    if (!homes.length) {
        return '';
    }
    const home = mostPreciseHome(homes, byId);
    const others = homes.length - 1;
    return `in ${byId.get(home).name}${others ? ` +${others}` : ''}`;
}
