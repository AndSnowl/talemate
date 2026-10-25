// The entry page's pure logic (mockup v3, screens A, B, D and E): its
// "In" rows' dates, Connected's groups (folded, filtered, the first few
// rows then "show all"), the tag picker's choices, the Timeline's
// "Events ▾" filter and the World tab's list (places under their most
// precise filed place). No Vue, no store: the node checks
// (checks/worlds.check.mjs) load this file.

import { formatDate } from './worldDates.js';

// the rows a long group shows before "show all"; a group with more is
// long, and has a filter box
export const GROUP_SHOWN = 5;

// the heading of the untagged entries' group (`filing.OTHER_HEADING`)
export const OTHER_HEADING = 'Other';

// The other names a page's (or a draft's) header lists beside its name
// (final review M8: the spec's header shows "the other names"): every
// other name but the everyday one, which reads "usually called …"
// instead, each with its index into `aka` (a draft's can be removed there
// before accept: accepted, an other name becomes a link word).
export function headerNames(aka) {
    return (aka || []).flatMap((entry, index) => (
        entry && !entry.everyday && String(entry.name ?? '').trim()
            ? [{ name: entry.name, index }]
            : []
    ));
}

// How the delete dialog names a field that refers to the thing
// (`references._field_entries`): a filing into it (or within it) is
// "filed in it" (final review M2); the other thing fields read as their
// names.
const REFERENCE_FIELD_LABELS = { filings: 'filed in it', parents: 'a parent' };

export function referenceFieldLabel(field) {
    return REFERENCE_FIELD_LABELS[field] || field;
}

// A tag as the backend stores it (`kinds.normalise_tag`): its first
// comma-separated part, trimmed and lowercased (ruling F8).
export function normaliseTag(value) {
    return String(value ?? '').split(',', 1)[0].trim().toLowerCase();
}

function plural(word) {
    if (/(s|x|z|ch|sh)$/.test(word)) {
        return `${word}es`;
    }
    if (word.length > 1 && word.endsWith('y') && !'aeiou'.includes(word[word.length - 2])) {
        return `${word.slice(0, -1)}ies`;
    }
    return `${word}s`;
}

// A group's heading for a tag (`filing.tag_heading`): its last word
// pluralised, capitalised; "Other" for none.
export function tagHeading(tag) {
    const words = String(tag ?? '').trim().split(' ');
    if (!words[words.length - 1]) {
        return OTHER_HEADING;
    }
    words[words.length - 1] = plural(words[words.length - 1]);
    const heading = words.join(' ');
    return heading.slice(0, 1).toUpperCase() + heading.slice(1);
}

// A filing's (or a Connected row's) dates as the page shows them: "since
// 979", an ended one its span "900–1015", "until 1015" with no start, ''
// for none.
export function filingDates(calendar, filing) {
    const since = filing?.since ? formatDate(calendar, filing.since) : '';
    const until = filing?.until ? formatDate(calendar, filing.until) : '';
    if (since && until) {
        return `${since}–${until}`;
    }
    if (since) {
        return `since ${since}`;
    }
    return until ? `until ${until}` : '';
}

// How many entries Connected holds, over its groups.
export function connectedCount(groups) {
    return (groups || []).reduce((sum, group) => sum + group.rows.length, 0);
}

// The key a group's synopsis and "+ Add" are kept under: the page and
// the tag ('' for the untagged group, and for the page's own "+ Add").
export function groupKey(thingId, tag) {
    return `${thingId}|${tag ?? ''}`;
}

function rowText(row) {
    const line = (row.line_segments || []).map((segment) => segment.text).join('');
    return `${row.name} ${row.role || ''} ${line}`.toLowerCase();
}

// What a group shows: `{long, rows, hidden}`. A long group (more than
// `limit` rows) has a filter box: the rows matching it (name, role or
// line, any case), every one of them once filtered; unfiltered, the first
// `limit` until "show all". `hidden` is how many are left out.
export function groupView(rows, { filter = '', showAll = false, limit = GROUP_SHOWN } = {}) {
    const all = rows || [];
    const long = all.length > limit;
    const query = long ? filter.trim().toLowerCase() : '';
    const matched = query ? all.filter((row) => rowText(row).includes(query)) : all;
    const shown = showAll || query || !long ? matched : matched.slice(0, limit);
    return { long, rows: shown, hidden: all.length - shown.length };
}

// The tag a row dragged from the group `fromTag` and dropped on the group
// `toTag` is given (`set_tag`'s; null: the untagged group), or undefined
// when it's dropped where it is.
export function dropTag(fromTag, toTag) {
    const to = toTag ?? null;
    return (fromTag ?? null) === to ? undefined : to;
}

// What a Connected row moved from the group `fromTag` to `toTag` changes,
// or null when it's dropped where it is: a row whose filing shows under a
// group (`show_under`) changes only that (`{showUnder}`, null: back under
// the entry's own tag); any other row, the entry's tag (`{tag}`, as
// `dropTag`), which moves it on every page it's filed in.
export function rowMove(row, fromTag, toTag) {
    const to = dropTag(fromTag, toTag);
    if (to === undefined) {
        return null;
    }
    return row?.show_under ? { showUnder: to } : { tag: to };
}

// the words a role can end with and take no "of" (`held.ROLE_PREPOSITIONS`)
const ROLE_PREPOSITIONS = ['in', 'of', 'by', 'at', 'for', 'to', 'from', 'with', 'on', 'under', 'through', 'over', 'into', 'across', 'within', 'as'];

// What an "In" row reads before its target, the entry's way, as the
// character sheet's line has it (`held.filed_as`): the role capitalised
// and "of" ("Native of"), one that ends with a preposition as it is
// ("Took place in", "Branch of"), one that opens "of", "Of"; a person
// `within` a part of the target, "in" ("Trooper in"). '' for no role.
export function roleLead(role, { within = false } = {}) {
    const words = String(role ?? '').split(/\s+/).filter(Boolean);
    if (!words.length) {
        return '';
    }
    const text = words.join(' ');
    const lead = text.slice(0, 1).toUpperCase() + text.slice(1);
    const folded = words.map((word) => word.toLowerCase());
    if (folded[0] === 'of') {
        return 'Of';
    }
    if (ROLE_PREPOSITIONS.includes(folded[folded.length - 1])) {
        return lead;
    }
    return `${lead} ${within ? 'in' : 'of'}`;
}

// The tag picker's choices for `query` (`tags`: `list_tags`' `{tag,
// heading, count}`): the tags in use that hold it, then whether "+ new tag"
// is offered (the query, normalised, is no tag in use). `current` (the
// entry's own tag) is left out.
export function tagChoices(tags, query, current = null) {
    const clean = normaliseTag(query);
    const matches = (tags || []).filter((item) => item.tag !== current && (!clean || item.tag.includes(clean)));
    const fresh = !!clean && clean !== current && !(tags || []).some((item) => item.tag === clean);
    return { matches, fresh: fresh ? clean : null };
}

// The Timeline's lines for "Events ▾": every dated fact ('all'), or
// ('events') only the lines from event entries, the page's own included
// when it's an event (`eventIds`: the event entries' ids).
export function timelineShown(lines, mode, eventIds = []) {
    if (mode !== 'events') {
        return lines || [];
    }
    const events = new Set(eventIds);
    return (lines || []).filter((line) => events.has(line.owner_id));
}

// A listed thing's first listed home (`filed_in`'s first id that's in
// `byId`), or null for none. This is the plain, single-step walk that
// `ancestorsAbove` climbs to find what a home itself sits in; it never
// calls `mostPreciseHome`, so a cycle between two homes can't recurse.
function firstListedHome(id, byId) {
    const thing = byId.get(id);
    return (thing?.filed_in || []).find((homeId) => byId.has(homeId)) ?? null;
}

// Every listed id that `id`'s home chain reaches, climbing `firstListedHome`
// (`held.ancestorsAbove`): cycle-safe, a seen-set stops a loop of homes
// each filed in the next.
function ancestorsAbove(id, byId) {
    const seen = new Set();
    let current = firstListedHome(id, byId);
    while (current && !seen.has(current)) {
        seen.add(current);
        current = firstListedHome(current, byId);
    }
    return seen;
}

// The most precise of a thing's listed homes (`held.mostPreciseHome`,
// final review §6): among `filedIn`'s listed ids, drop any home that
// another of them already sits in (its own `filed_in` chain, climbed
// cycle-safe by `ancestorsAbove`); of what's left, the first filed. null
// for no listed home.
export function mostPreciseHome(filedIn, byId) {
    const homes = (filedIn || []).filter((id) => byId.has(id));
    if (homes.length <= 1) {
        return homes[0] ?? null;
    }
    const remaining = homes.filter((home) => (
        !homes.some((other) => other !== home && ancestorsAbove(other, byId).has(home))
    ));
    return remaining[0] ?? homes[0];
}

// The World tab's list of one kind, for `query` (its name holds it, any
// case; all with none): `[{thing, depth}]` in the listing's order, entries
// before stubs, and for places each one under its most precise listed
// home (`mostPreciseHome`), indented (`depth`), however deep. A place in
// no listed place, or one that would close a loop, sits at the top.
export function kindList(things, query = '', { nest = false } = {}) {
    const clean = query.trim().toLowerCase();
    const listed = (things || []).filter((thing) => !clean || thing.name.toLowerCase().includes(clean));
    const ordered = [...listed.filter((thing) => !thing.stub), ...listed.filter((thing) => thing.stub)];
    if (!nest) {
        return ordered.map((thing) => ({ thing, depth: 0 }));
    }
    const byId = new Map(ordered.map((thing) => [thing.id, thing]));
    const parentOf = (thing) => mostPreciseHome(thing.filed_in, byId);
    const children = new Map();
    const roots = [];
    for (const thing of ordered) {
        // a loop of places (each in the next) has no top: each sits there
        let parent = parentOf(thing);
        const seen = new Set([thing.id]);
        for (let up = parent; up; up = parentOf(byId.get(up))) {
            if (seen.has(up)) {
                parent = null;
                break;
            }
            seen.add(up);
        }
        if (parent) {
            children.set(parent, [...(children.get(parent) || []), thing]);
        } else {
            roots.push(thing);
        }
    }
    const out = [];
    const walk = (thing, depth) => {
        out.push({ thing, depth });
        for (const child of children.get(thing.id) || []) {
            walk(child, depth + 1);
        }
    };
    roots.forEach((thing) => walk(thing, 0));
    return out;
}
