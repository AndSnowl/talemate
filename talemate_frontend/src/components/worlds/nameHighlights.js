// The new-scene prompt's name highlights: which spans of the prompt are
// world thing names (from the backend's `match_names`), which thing the
// owner picked for each, and which names will be invented. No Vue or `@/`
// imports, so the node checks (checks/worlds.check.mjs) can load this file.

// a pick meaning "treat this name as new", never a thing id
export const NEW_THING = '__new__';

// The key a name's pick is kept under: every spelling of one name
// ("Maren", "maren") shares its pick, as the backend's matching does.
export function pickKey(text) {
    return text.split(/\s+/).filter(Boolean).join(' ').toLowerCase();
}

// The thing id picked for `match`: the owner's pick, else the best
// candidate. `NEW_THING` when the owner treats the name as new.
export function pickedId(match, picks) {
    const picked = picks[pickKey(match.text)];
    if (picked === NEW_THING) {
        return NEW_THING;
    }
    if (picked && match.candidates.some((candidate) => candidate.id === picked)) {
        return picked;
    }
    return match.candidates[0]?.id || NEW_THING;
}

// `plan_scene`'s `picks`: each matched name (as written) -> its thing id,
// leaving out names treated as new.
export function picksPayload(matches, picks) {
    const payload = {};
    const seen = new Set();
    for (const match of matches) {
        const key = pickKey(match.text);
        const id = pickedId(match, picks);
        if (seen.has(key) || id === NEW_THING) {
            continue;
        }
        seen.add(key);
        payload[match.text] = id;
    }
    return payload;
}

// The backend's offsets count code points; JS strings count UTF-16 units.
function utf16Offset(text, codePoints) {
    let index = 0;
    for (let n = 0; n < codePoints && index < text.length; n += 1) {
        index += text.codePointAt(index) > 0xffff ? 2 : 1;
    }
    return index;
}

function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Where each of `names` (invented things) appears in `text`, as whole
// words, case-insensitively: `[{start, end}]`.
function nameSpans(text, names) {
    const spans = [];
    for (const name of names) {
        const words = name.split(/\s+/).filter(Boolean).map(escapeRegExp);
        if (!words.length) {
            continue;
        }
        const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])${words.join('\\s+')}(?![\\p{L}\\p{N}_])`, 'giu');
        for (const found of text.matchAll(pattern)) {
            spans.push({ start: found.index, end: found.index + found[0].length });
        }
    }
    return spans;
}

// `text` cut into segments for display, each with its `start` and `end`
// (JS string offsets): `{text}` plain, `{text, match,
// state: 'matched'}` for a name picked as a world thing, `{text, match,
// state: 'new'}` for one treated as new, and `{text, state: 'new'}` for an
// invented name (`inventedNames`, from the setup) the prompt mentions.
// Overlapping spans keep the earlier one. `matches` are `match_names`
// items for this very `text`.
export function promptSegments(text, matches, picks, inventedNames = []) {
    const astral = /[\uD800-\uDFFF]/.test(text);
    const offset = (codePoints) => (astral ? utf16Offset(text, codePoints) : codePoints);
    const spans = [
        ...matches.map((match) => ({
            start: offset(match.start),
            end: offset(match.end),
            match,
            state: pickedId(match, picks) === NEW_THING ? 'new' : 'matched',
        })),
        ...nameSpans(text, inventedNames).map((span) => ({ ...span, match: null, state: 'new' })),
    ].sort((a, b) => a.start - b.start || b.end - a.end);

    const segments = [];
    let at = 0;
    for (const span of spans) {
        if (span.start < at || span.end > text.length) {
            continue;
        }
        if (span.start > at) {
            segments.push({ text: text.slice(at, span.start), start: at, end: span.start });
        }
        segments.push({
            text: text.slice(span.start, span.end),
            start: span.start,
            end: span.end,
            match: span.match,
            state: span.state,
        });
        at = span.end;
    }
    if (at < text.length) {
        segments.push({ text: text.slice(at), start: at, end: text.length });
    }
    return segments;
}
