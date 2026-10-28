// The right-click naming menu's pure parts (languages 3a): replacing the
// selection, the language naming starts from, and the picker's order.
// Node-checked in checks/languageMenu.check.mjs.

// `value` with `[start, end]` replaced by `text`
export function replaceSelection(value, [start, end], text) {
    return value.slice(0, start) + text + value.slice(end);
}

// The language naming starts from (as `languages.lookup.default_language`):
// an official one, else the spoken one with the largest share, else the
// first; null with none in reach.
export function defaultLanguageId(rows) {
    if (!rows || !rows.length) return null;
    const official = rows.find((r) => r.role === 'official');
    if (official) return official.language_id;
    const spoken = rows.filter((r) => r.role === 'spoken');
    if (spoken.length) {
        return spoken.reduce((best, r) => ((r.share || 0) > (best.share || 0) ? r : best)).language_id;
    }
    return rows[0].language_id;
}

// The picker's languages: those in reach of the page first (in their
// order), then the world's others, each `{id, name, phrases, inReach}`.
export function menuLanguages(menu) {
    const all = menu?.languages || [];
    const reach = [];
    for (const row of menu?.rows || []) {
        if (!reach.includes(row.language_id)) reach.push(row.language_id);
    }
    const byId = new Map(all.map((l) => [l.id, l]));
    const first = reach.filter((id) => byId.has(id)).map((id) => ({ ...byId.get(id), inReach: true }));
    const rest = all.filter((l) => !reach.includes(l.id)).map((l) => ({ ...l, inReach: false }));
    return [...first, ...rest];
}

// The row "Save on this page" adds: the language, spoken there
export function savedRow(languageId) {
    return { language: languageId, role: 'spoken' };
}
