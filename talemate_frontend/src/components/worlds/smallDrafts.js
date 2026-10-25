// Small drafts (the store's `smallDrafts`): a page's "+ Add facts…" or
// "+ Add event…" draft, a Connected group's "+ Add" draft and a page
// draft's nested fact draft, each held and versioned on the server
// (`talemate.server.world_drafts`) under its own key. The owner's edits
// are kept per version for the session (`smallEdits`, key -> version ->
// `{base, edited}`), as a page draft's are (`draftEdits`), and put back
// when that version is used again, as long as the server's copy is the
// one they were made on.
//
// Pure: no Vue, no `@/` imports (the node checks load it).

const FACTS = 'facts:';
const GROUP = 'group:';
const NESTED = 'nested:';

// One fact-or-event draft per page (`world_drafts.facts_key`).
export function factsKey(thingId) {
    return `${FACTS}${thingId}`;
}

// One group-add draft per page and group, the page's own "+ Add" under
// tag '' (`world_drafts.group_key`).
export function groupDraftKey(thingId, tag) {
    return `${GROUP}${thingId}:${tag || ''}`;
}

// One nested fact draft per page draft (`world_drafts.nested_key`).
export function nestedKey(pageKey) {
    return `${NESTED}${pageKey}`;
}

// The page draft a nested draft's key names (`world_drafts.page_key`).
export function pageKeyOf(key) {
    return key.slice(NESTED.length);
}

// A key's kind of small draft: 'facts', 'group' or 'nested' (as the
// server's `use_small_version` names it), or null for any other key (a
// page draft's).
export function smallKind(key) {
    if (typeof key !== 'string') {
        return null;
    }
    for (const prefix of [FACTS, GROUP, NESTED]) {
        if (key.startsWith(prefix)) {
            return prefix.slice(0, -1);
        }
    }
    return null;
}

// The bar's versions of a small draft: `{version, label, prompt,
// current}`, newest first, labelled as `versionRows` labels a page
// draft's ("v2 · its bells", an event's year after its prompt).
export function smallVersionRows(versions, current) {
    return [...(versions || [])].reverse().map((row) => ({
        version: row.version,
        label: `v${row.version} · ${row.prompt}${row.year != null ? ` (${row.year})` : ''}`,
        prompt: row.prompt,
        current: row.version === current,
    }));
}

// `smallEdits` with what the owner left on `draft`'s open version kept
// (unchanged when it has no version yet).
export function keepSmallEdits(smallEdits, draft) {
    if (!draft?.key || draft.version == null || !draft.base) {
        return smallEdits;
    }
    return {
        ...smallEdits,
        [draft.key]: { ...(smallEdits[draft.key] || {}), [draft.version]: { base: draft.base, edited: draft.edited } },
    };
}

// `smallEdits` once the server dropped the oldest version of `key` (the
// ones kept move down with it).
export function smallEditsShifted(smallEdits, key) {
    const kept = smallEdits[key] || {};
    return {
        ...smallEdits,
        [key]: Object.fromEntries(Object.entries(kept).filter(([n]) => Number(n) > 1).map(([n, value]) => [Number(n) - 1, value])),
    };
}

// `smallEdits` without `key`'s.
export function smallEditsDropped(smallEdits, key) {
    const { [key]: _gone, ...rest } = smallEdits;
    return rest;
}

function deepEqual(a, b) {
    if (a === b) {
        return true;
    }
    if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null || Array.isArray(a) !== Array.isArray(b)) {
        return false;
    }
    const keys = Object.keys(a);
    if (keys.length !== Object.keys(b).length) {
        return false;
    }
    return keys.every((key) => Object.prototype.hasOwnProperty.call(b, key) && deepEqual(a[key], b[key]));
}

// What the owner sees of version `version` of `key` once the server gives
// back its copy `base`: the edits kept for it, when they were made on
// that same copy; else the server's copy as it is.
export function restoredEdited(smallEdits, key, version, base) {
    const kept = smallEdits?.[key]?.[version];
    return kept && deepEqual(kept.base, base) ? kept.edited : base;
}
