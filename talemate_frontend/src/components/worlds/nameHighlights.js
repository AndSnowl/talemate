// The name highlights of a prompt or fact the owner writes
// (`NameHighlightInput`: the new-scene prompt, the create box, the fact
// form): which spans are world thing names (from the backend's
// `match_names`), which thing the owner picked for each, which are only
// suggested, which names will be invented, and which unknown capitalised
// phrases the owner wants made stubs. Also the references the owner made
// by hand (`refs`: Add reference), a fact's existing links when it's
// edited (`links`, kept by position: the n-th time their words are
// written), and which reference of a fact's raw text a link is. No Vue or `@/`
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
// kind}]`). An existing link of an edited fact (`linked`, from
// `locateLinks`) is `{text, ref, linked: true, linkIndex, match, state}`,
// its match (one at the very same place) attached, and wins over anything
// else there: 'matched', or 'new' once the owner turned that link to new
// (its ref `NEW_THING`); name picks don't touch it.
// Overlapping spans keep the earlier one, then the longer. `matches` and
// `unknown` are `match_names` items for this very `text`.
export function promptSegments(text, matches, picks, inventedNames = [], { refs = {}, unknown = [], stubs = [], linked = [] } = {}) {
    const astral = /[\uD800-\uDFFF]/.test(text);
    const offset = (codePoints) => (astral ? utf16Offset(text, codePoints) : codePoints);
    const linkedSpans = linked.map((link) => ({
        ...link,
        linked: true,
        match: matches.find((match) => offset(match.start) === link.start && offset(match.end) === link.end) || null,
        state: link.ref.id === NEW_THING ? 'new' : 'matched',
    }));
    const free = (span) => !linkedSpans.some((link) => span.start < link.end && link.start < span.end);
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
        ...linkedSpans,
        ...[
            ...matchSpans,
            ...refSpans,
            ...nameSpans(text, inventedNames).map((span) => ({ ...span, match: null, state: 'new' })),
            ...unknownSpans,
        ].filter(free),
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
        if (span.linked) {
            segment.linked = true;
            segment.linkIndex = span.index;
        }
        segments.push(segment);
        at = span.end;
    }
    if (at < text.length) {
        segments.push({ text: text.slice(at), start: at, end: text.length });
    }
    return segments;
}

// The words `key` (a pickKey) as `text` first writes them, or null.
function writtenIn(text, key) {
    const words = key.split(' ').filter(Boolean).map(escapeRegExp);
    if (!words.length) {
        return null;
    }
    const found = text.match(new RegExp(`(?<![\\p{L}\\p{N}_])${words.join('\\s+')}(?![\\p{L}\\p{N}_])`, 'iu'));
    return found ? found[0] : null;
}

// What a fact edit or a preview sends for `text`'s names: `picks` (written
// name -> thing id: the matched names, then the owner's hand-made
// references no match covers) and `newNames` (names treated as new). With
// `text`, the owner's own picks and "treat as new" for names `matches`
// doesn't cover (its lookup not back yet) go out too, as `text` writes
// them, so none is lost.
export function linkPayload(matches, picks, refs = {}, text = null) {
    const payload = picksPayload(matches, picks, refs);
    const newNames = newNamesPayload(matches, picks, refs);
    const covered = new Set([...matches.map((match) => pickKey(match.text))]);
    for (const [key, ref] of Object.entries(refs)) {
        if (!covered.has(key) && picks[key] !== NEW_THING) {
            payload[ref.text] = ref.id;
            covered.add(key);
        }
    }
    if (text !== null) {
        for (const [key, id] of Object.entries(picks)) {
            const written = covered.has(key) ? null : writtenIn(text, key);
            if (!written) {
                continue;
            }
            covered.add(key);
            if (id === NEW_THING) {
                newNames.push(written);
            } else {
                payload[written] = id;
            }
        }
    }
    return { picks: payload, newNames };
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

// Where `words` are written in `text` as whole words, case and all:
// their start offsets, in order.
function occurrences(text, words) {
    if (!words) {
        return [];
    }
    const pattern = new RegExp(`(?<![\\p{L}\\p{N}_])${escapeRegExp(words)}(?![\\p{L}\\p{N}_])`, 'gu');
    return [...text.matchAll(pattern)].map((found) => found.index);
}

// A fact's rendered text and its existing links, for editing it: `text`
// is its `segments` joined; `links` holds each linked run as `{text, ref,
// nth}`, `nth` the number of times its words are written before it, so
// the same link is found again in the edited text (`locateLinks`) and two
// links of the same words keep their own targets. Links to ignored stubs
// (`ignoredIds`) render as plain words, so they're read from the raw text.
export function factEditState(segments, rawText = '', ignoredIds = []) {
    const text = segments && segments.length ? segments.map((segment) => segment.text).join('') : rawText;
    const found = [];
    let at = 0;
    for (const segment of segments || []) {
        if (segment.ref) {
            found.push({ start: at, text: segment.text, ref: segment.ref });
        }
        at += segment.text.length;
    }
    const ignored = new Set(ignoredIds);
    if (ignored.size) {
        // walk the raw text along the rendered one; after a reference whose
        // rendered words aren't known (one with no shown text that doesn't
        // render as a link), the walk finds its place again from the
        // words that follow
        let rendered = 0;
        let raw = 0;
        let lost = false;
        for (const ref of rawText.matchAll(REF_PATTERN)) {
            const plain = rawText.slice(raw, ref.index);
            if (!lost) {
                if (!text.startsWith(plain, rendered)) {
                    break;
                }
                rendered += plain.length;
            } else if (plain) {
                const at = text.indexOf(plain, rendered);
                if (at < 0) {
                    break;
                }
                rendered = at + plain.length;
                lost = false;
            }
            raw = ref.index + ref[0].length;
            const live = found.find((link) => link.ref === ref[1] && (lost ? link.start >= rendered : link.start === rendered));
            if (live) {
                rendered = live.start + live.text.length;
                lost = false;
            } else if (ref[2]) {
                const at = lost ? text.indexOf(ref[2], rendered) : text.startsWith(ref[2], rendered) ? rendered : -1;
                if (at < 0) {
                    break;
                }
                if (ignored.has(ref[1])) {
                    found.push({ start: at, text: ref[2], ref: ref[1] });
                }
                rendered = at + ref[2].length;
                lost = false;
            } else {
                lost = true;
            }
        }
    }
    found.sort((a, b) => a.start - b.start);
    const links = found.map((link) => ({
        text: link.text,
        ref: link.ref,
        nth: occurrences(text, link.text).filter((start) => start < link.start).length,
    }));
    return { text, links };
}

// `links` (`factEditState`'s, each `ref` maybe changed by the owner since:
// another thing, or `NEW_THING` to keep its words plain) found again in
// `text`: each at the `nth` time its words are written, as `{start, end,
// index, ref: {id, text}}` (JS offsets; `index` into `links`), in order;
// one no longer written that often is gone, and of two at one place the
// first stays.
export function locateLinks(text, links) {
    const located = [];
    links.forEach((link, index) => {
        const start = occurrences(text, link.text)[link.nth];
        if (start !== undefined) {
            located.push({ start, end: start + link.text.length, index, ref: { id: link.ref, text: link.text, was: link.was } });
        }
    });
    located.sort((a, b) => a.start - b.start);
    return located.filter((link, index) => index === 0 || link.start >= located[index - 1].end);
}

// What a fact edit sends for `text` (exactly the text sent): its existing
// `links` as positional `spans` (`{start, end, ref}` in code points, as the
// backend counts; a link the owner turned to new has a null `ref`, keeping
// its words plain), which the backend applies first, then `linkPayload`'s
// name-keyed `picks` and `newNames` for the rest of the text.
export function factLinkPayload(text, matches, picks, refs, links) {
    const codePoints = (index) => [...text.slice(0, index)].length;
    const spans = locateLinks(text, links).map((link) => ({
        start: codePoints(link.start),
        end: codePoints(link.end),
        ref: link.ref.id === NEW_THING ? null : link.ref.id,
    }));
    return { ...linkPayload(matches, picks, refs, text), spans };
}

// Which reference of a fact's raw text (0-based, in order) its rendered
// `segments[index]` is; null if that segment isn't a link. Links render
// in order, so it's the n-th reference to the same thing.
export function refOccurrence(rawText, segments, index) {
    const segment = segments[index];
    if (!segment?.ref) {
        return null;
    }
    const nth = segments.slice(0, index).filter((other) => other.ref === segment.ref).length;
    let seen = 0;
    let occurrence = 0;
    for (const found of rawText.matchAll(REF_PATTERN)) {
        if (found[1] === segment.ref) {
            if (seen === nth) {
                return occurrence;
            }
            seen += 1;
        }
        occurrence += 1;
    }
    return null;
}

// The Add reference search: `targets` (`{id, name, kind, stub}`) whose name
// holds `query`, ignoring case; names starting with it first, then by
// name; at most `limit`. Nothing for a blank query.
// How `target` (`{name, aka}`) matches `query` (already lowercased and
// trimmed, or raw: it's normalised here): `null` when its own name holds
// it, the other name that holds it when only one of those does, and
// `undefined` when nothing does.
export function entryMatch(target, query) {
    const wanted = query.trim().toLowerCase();
    if (!wanted) {
        return undefined;
    }
    if (target.name.toLowerCase().includes(wanted)) {
        return null;
    }
    const others = target.aka || [];
    return others.find((name) => name.toLowerCase().startsWith(wanted))
        ?? others.find((name) => name.toLowerCase().includes(wanted));
}

// The one entry search every picker uses (polish 4): targets whose name,
// or one of whose other names (`aka`), holds `query`, as `{target,
// matched}` (`matched`: the other name that matched, or null). Its own
// name first, a starting match before one inside, then by name.
export function searchEntries(targets, query, limit = 8) {
    const wanted = query.trim().toLowerCase();
    if (!wanted) {
        return [];
    }
    const rank = ({ target, matched }) => {
        const name = (matched ?? target.name).toLowerCase();
        return (matched === null ? 0 : 2) + (name.startsWith(wanted) ? 0 : 1);
    };
    return targets
        .map((target) => ({ target, matched: entryMatch(target, wanted) }))
        .filter((found) => found.matched !== undefined)
        .sort((a, b) => rank(a) - rank(b) || a.target.name.localeCompare(b.target.name))
        .slice(0, limit);
}

function isFormYear(value) {
    return Number.isInteger(value) && value >= 1 && value <= 9999;
}

function isBlank(value) {
    return value === null || value === undefined || value === '';
}

// Whether a fact form (`{mode, text, category, fromYear, untilYear}`, as
// ThingFactForm edits it) can be saved: some text, a category, each year
// empty or a year, the end after the start. A `timeline` fact is a
// dated moment: it needs its year.
export function factFormValid(form) {
    const { text, category, fromYear, untilYear } = form;
    const yearOk = (value) => isBlank(value) || isFormYear(value);
    if (!text?.trim() || !category || !yearOk(fromYear) || !yearOk(untilYear)) {
        return false;
    }
    if (category === 'timeline' && form.mode !== 'override' && !isFormYear(fromYear)) {
        return false;
    }
    return !(isFormYear(fromYear) && isFormYear(untilYear) && untilYear <= fromYear);
}
