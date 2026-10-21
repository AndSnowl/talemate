// The name highlights of a prompt or fact the owner writes
// (`NameHighlightInput`: the new-scene prompt, the create box, the fact
// form): which spans are world thing names (from the backend's
// `match_names`), which thing the owner picked for each, which are only
// suggested, which names will be invented, and which unknown capitalised
// phrases the owner wants made stubs. Also the references the owner made
// by hand (`refs`: Add reference, and a fact's existing links when it's
// edited), and re-pointing one link in a fact's raw text. No Vue or `@/`
// imports, so the node checks (checks/worlds.check.mjs) can load this file.

// a pick meaning "treat this name as new", never a thing id
export const NEW_THING = '__new__';

// The key a name's pick is kept under: every spelling of one name
// ("Maren", "maren") shares its pick, as the backend's matching does.
export function pickKey(text) {
    return text.split(/\s+/).filter(Boolean).join(' ').toLowerCase();
}

// The thing id picked for `match`: the owner's pick among its candidates,
// else a reference the owner made for that name (`refs`: pickKey -> `{id,
// text}`, which may be any thing), else the best candidate. `NEW_THING`
// when the owner treats the name as new, and for a suggested (partial)
// match the owner hasn't picked a thing for.
export function pickedId(match, picks, refs = {}) {
    const key = pickKey(match.text);
    const picked = picks[key];
    if (picked === NEW_THING) {
        return NEW_THING;
    }
    if (picked && match.candidates.some((candidate) => candidate.id === picked)) {
        return picked;
    }
    if (refs[key]) {
        return refs[key].id;
    }
    if (match.suggested) {
        return NEW_THING;
    }
    return match.candidates[0]?.id || NEW_THING;
}

// How `match` shows: 'matched' (a world thing), 'new' (treated as new) or
// 'suggested' (a partial match nobody has picked or turned down yet).
export function matchState(match, picks, refs = {}) {
    const key = pickKey(match.text);
    if (match.suggested && !(key in picks) && !refs[key]) {
        return 'suggested';
    }
    return pickedId(match, picks, refs) === NEW_THING ? 'new' : 'matched';
}

// `plan_scene`'s (and `preview_thing`'s) `picks`: each matched name (as
// written) -> its thing id, leaving out names treated as new.
export function picksPayload(matches, picks, refs = {}) {
    const payload = {};
    const seen = new Set();
    for (const match of matches) {
        const key = pickKey(match.text);
        const id = pickedId(match, picks, refs);
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

// `plan_scene`'s `new_names`: the matched names (as written) the owner
// treats as new, once each. A suggested match left alone isn't one: the
// model may still resolve it.
export function newNamesPayload(matches, picks, refs = {}) {
    const names = new Map();
    for (const match of matches) {
        const key = pickKey(match.text);
        const untouched = match.suggested && !(key in picks);
        if (!names.has(key) && !untouched && pickedId(match, picks, refs) === NEW_THING) {
            names.set(key, match.text);
        }
    }
    return [...names.values()];
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
// (JS string offsets): `{text}` plain; `{text, match, state}` for a matched
// name, `state` as `matchState` says; `{text, state: 'new'}` for an
// invented name (`inventedNames`, from the setup) the prompt mentions;
// `{text, ref, state: 'matched'}` for a name the owner referenced by hand
// (`refs`) that no match covers; and, with `unknown` (`match_names`'s
// unknown phrases), `{text, unknown, state: 'unknown'}`, or `state:
// 'stub'` once the owner asked for it to be made a stub (`stubs`, `[{text,
// kind}]`). Overlapping spans keep the earlier one, then the longer.
// `matches` and `unknown` are `match_names` items for this very `text`.
export function promptSegments(text, matches, picks, inventedNames = [], { refs = {}, unknown = [], stubs = [] } = {}) {
    const astral = /[\uD800-\uDFFF]/.test(text);
    const offset = (codePoints) => (astral ? utf16Offset(text, codePoints) : codePoints);
    const matchSpans = matches.map((match) => ({
        start: offset(match.start),
        end: offset(match.end),
        match,
        state: matchState(match, picks, refs),
    }));
    const matchedKeys = new Set(matches.map((match) => pickKey(match.text)));
    const refSpans = Object.entries(refs)
        .filter(([key]) => !matchedKeys.has(key) && picks[key] !== NEW_THING)
        .flatMap(([, ref]) => nameSpans(text, [ref.text]).map((span) => ({ ...span, match: null, ref, state: 'matched' })));
    const stubKeys = new Set(stubs.map((stub) => pickKey(stub.text)));
    const unknownSpans = unknown.map((phrase) => ({
        start: offset(phrase.start),
        end: offset(phrase.end),
        match: null,
        unknown: phrase,
        state: stubKeys.has(pickKey(phrase.text)) ? 'stub' : 'unknown',
    }));
    const spans = [
        ...matchSpans,
        ...refSpans,
        ...nameSpans(text, inventedNames).map((span) => ({ ...span, match: null, state: 'new' })),
        ...unknownSpans,
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
        const segment = {
            text: text.slice(span.start, span.end),
            start: span.start,
            end: span.end,
            match: span.match,
            state: span.state,
        };
        if (span.ref) {
            segment.ref = span.ref;
        }
        if (span.unknown) {
            segment.unknown = span.unknown;
        }
        segments.push(segment);
        at = span.end;
    }
    if (at < text.length) {
        segments.push({ text: text.slice(at), start: at, end: text.length });
    }
    return segments;
}

// What a fact edit or a preview sends for `text`'s names: `picks` (written
// name -> thing id: the matched names, then the owner's hand-made
// references no match covers) and `newNames` (names treated as new).
export function linkPayload(matches, picks, refs = {}) {
    const payload = picksPayload(matches, picks, refs);
    const covered = new Set([...matches.map((match) => pickKey(match.text))]);
    for (const [key, ref] of Object.entries(refs)) {
        if (!covered.has(key) && picks[key] !== NEW_THING) {
            payload[ref.text] = ref.id;
            covered.add(key);
        }
    }
    return { picks: payload, newNames: newNamesPayload(matches, picks, refs) };
}

// The owner's re-picks: each matched name (as written) the owner picked a
// candidate for by hand, as `{id, name}`, once per name. Each teaches that
// thing the name as another name.
export function repicks(matches, picks) {
    const found = [];
    const seen = new Set();
    for (const match of matches) {
        const key = pickKey(match.text);
        const picked = picks[key];
        if (seen.has(key) || !picked || picked === NEW_THING || !match.candidates.some((c) => c.id === picked)) {
            continue;
        }
        seen.add(key);
        found.push({ id: picked, name: match.text });
    }
    return found;
}

// as talemate.world.refs.REF_PATTERN: a thing id, then the shown text
const REF_PATTERN = /\[\[thing:([0-9a-f]{32})(?:\|((?:(?!\]\])[^\n])+))?\]\]/g;

// A fact's rendered text and its existing links, for editing it: `text`
// is its `segments` joined; `refs` holds each linked run's words (pickKey
// -> `{id, text}`), so saving links them to the same things again. Links
// to ignored stubs render as plain words, so the raw text's references to
// `ignoredIds` are added too.
export function factEditState(segments, rawText = '', ignoredIds = []) {
    const refs = {};
    for (const segment of segments || []) {
        if (segment.ref && !refs[pickKey(segment.text)]) {
            refs[pickKey(segment.text)] = { id: segment.ref, text: segment.text };
        }
    }
    const ignored = new Set(ignoredIds);
    for (const found of rawText.matchAll(REF_PATTERN)) {
        const [, id, shown] = found;
        if (shown && ignored.has(id) && !refs[pickKey(shown)]) {
            refs[pickKey(shown)] = { id, text: shown };
        }
    }
    const text = segments && segments.length ? segments.map((segment) => segment.text).join('') : rawText;
    return { text, refs };
}

// A fact's raw text with the link that is its rendered `segments[index]`
// pointing at `toId` instead, its shown words kept (a reference with none
// keeps the words it rendered as); null if that segment isn't a link.
// Links render in order, so it's the n-th reference to the same thing.
export function repointedText(rawText, segments, index, toId) {
    const segment = segments[index];
    if (!segment?.ref) {
        return null;
    }
    const nth = segments.slice(0, index).filter((other) => other.ref === segment.ref).length;
    let seen = 0;
    for (const found of rawText.matchAll(REF_PATTERN)) {
        if (found[1] !== segment.ref) {
            continue;
        }
        if (seen === nth) {
            const shown = found[2] ?? segment.text;
            return `${rawText.slice(0, found.index)}[[thing:${toId}|${shown}]]${rawText.slice(found.index + found[0].length)}`;
        }
        seen += 1;
    }
    return null;
}

// The Add reference search: `targets` (`{id, name, kind, stub}`) whose name
// holds `query`, ignoring case; names starting with it first, then by
// name; at most `limit`. Nothing for a blank query.
export function searchReferences(targets, query, limit = 8) {
    const wanted = query.trim().toLowerCase();
    if (!wanted) {
        return [];
    }
    return targets
        .filter((target) => target.name.toLowerCase().includes(wanted))
        .sort((a, b) => {
            const aStarts = a.name.toLowerCase().startsWith(wanted) ? 0 : 1;
            const bStarts = b.name.toLowerCase().startsWith(wanted) ? 0 : 1;
            return aStarts - bStarts || a.name.localeCompare(b.name);
        })
        .slice(0, limit);
}
