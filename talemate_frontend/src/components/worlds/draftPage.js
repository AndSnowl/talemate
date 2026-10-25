// The draft page's pure logic (spec "The draft page", mockup v2 screens 3
// and 4, v3 screen C). No Vue, no store: the node checks
// (checks/worlds.check.mjs) load this file.
//
// A draft is the page the entry will be (`preview_thing`'s reply, the
// thing payload's shape) plus `preview`, the data `accept_preview` takes.
// The server keeps each version's copy (`base` here) and adds to it on a
// draft's "+ Add facts…" and selections; the owner's ticks and edits live
// on the client (`edited`) until Accept, which sends them. So each reply
// that changes the server's copy is rebased: the owner's changes to the
// old copy (`rebaseDraft`) carried onto the new one. A restored version
// (`use_version` gives back the server's copy, without the owner's edits)
// is rebased the same way from what the client kept of it for the
// session.
//
// Rows the owner adds (an "+ in…" filing, a fact "+ also here", a fact
// moved onto another page, a "Move existing here") are `local`: kept
// after the server's own. A server fact the owner removes (or moves) stays
// in its place, `removed` and unticked, so the server's indices (what a
// selection names, `index`) hold.

import { kindInfo } from './worldKinds.js';

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

// Whether selected `words` (the rendered text `before` them, in the fact)
// look like a proper name, so a link's mode chooser defaults to "Add as
// another name" (ruling H2) rather than "Link only": a word with a capital
// that isn't there only because the sentence starts with it (the backend's
// capital rule, `links._capitalised`, past a leading article), and words
// that aren't already one of the target's `names`.
export function wordsAreAName(words, before = '', names = []) {
    const key = nameKey(words);
    if (!key || (names || []).some((name) => nameKey(name) === key)) {
        return false;
    }
    let tokens = (words || '').trim().split(/\s+/).filter(Boolean);
    const sentenceStart = !/[\p{L}\p{N}]/u.test(before || '') || /[.!?:;]["'”’)\]]*\s*$/u.test(before || '');
    if (tokens.length > 1 && ARTICLES.includes(tokens[0].toLowerCase())) {
        tokens = tokens.slice(1);
    } else if (sentenceStart) {
        tokens = tokens.slice(1);
    }
    return tokens.some((token) => /^[^\p{L}]*\p{Lu}/u.test(token));
}

function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Whether `words` are written with a capital past a leading article, as
// accept's linking wants a pick or new name written (`links.link_text`).
function capitalised(words) {
    let tokens = words.trim().split(/\s+/).filter(Boolean);
    if (tokens.length > 1 && ARTICLES.includes(tokens[0].toLowerCase())) {
        tokens = tokens.slice(1);
    }
    return /^[^\p{L}]*\p{Lu}/u.test(tokens[0] || '');
}

// A text as `LinkedText` segments: the names it invents (`newNames`, a
// draft's `new_names`: each name, the ways the text writes it and its
// other names) marked `fresh`, since they become stubs on accept; the rest
// plain. Found as accept links them: in any case, where the text writes
// them with a capital past a leading article ("the Boyar Council" for
// "The Boyar Council"); one the owner selected (`anyCase`) as written.
// Earliest match first, then the longest.
export function previewSegments(text, newNames = []) {
    const spans = [];
    for (const found of newNames) {
        const spellings = [found.name, ...(found.written || []), ...(found.aka || []).map((entry) => entry.name)];
        for (const spelling of spellings.filter(Boolean)) {
            const pattern = new RegExp(`(?<![\\p{L}\\p{N}])${escapeRegExp(spelling)}(?![\\p{L}\\p{N}])`, 'giu');
            for (const match of text.matchAll(pattern)) {
                if (found.anyCase || capitalised(match[0])) {
                    spans.push({ start: match.index, end: match.index + match[0].length, kind: found.kind });
                }
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

// `segments` (a draft fact's, linked by the server) with the draft's new
// names marked `fresh` in their plain runs (a `self` run, the page's own
// name, kept as it is); a name a new name has (its
// same-as answered) is left plain, since it links an entry then. A name
// the owner selected (`selected`, the draft's `selected_names`, ruling
// F26) is found in any case, as accept will link it.
export function freshSegments(segments, newNames = [], selected = []) {
    const owned = new Set((selected || []).map(nameKey));
    const fresh = (newNames || [])
        .filter((row) => !row.same_target_id)
        .map((row) => (owned.has(nameKey(row.name)) ? { ...row, anyCase: true } : row));
    return (segments || []).flatMap((segment) => (segment.ref || segment.self || !fresh.length ? [segment] : previewSegments(segment.text, fresh)));
}

// A "For other pages" row's segments: as the server rendered it
// (`rendered`, the draft's `elsewhere`: `[{index, text, segments}]`) when
// it rendered these words, else its new names highlighted here
// (`previewSegments`).
export function elsewhereSegments(row, index, rendered = [], newNames = []) {
    const found = (rendered || []).find((entry) => entry.index === index);
    if (found && found.text === row.text) {
        return found.segments;
    }
    return previewSegments(row.text || '', newNames);
}

function same(a, b) {
    return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

// what the owner changed on a row: `edited`'s fields that differ from
// `base`'s
function changes(base, edited) {
    const out = {};
    for (const [key, value] of Object.entries(edited || {})) {
        if (!same(base?.[key], value)) {
            out[key] = value;
        }
    }
    return out;
}

// how a list's rows are told apart from one version of the server's copy
// to the next: by position (the server only ever appends), or by a key
const ROW_KEYS = {
    facts: null,
    elsewhere: null,
    filings: (row) => filingKey(row),
    new_names: (row) => nameKey(row.name),
    file_into: (row) => row.thing_id,
    move_here: (row) => `${row.fact_id}|${row.repeat ? 'repeat' : 'near'}`,
};

function rebaseRows(oldBase, oldEdited, newBase, key, fresh) {
    oldBase = oldBase || [];
    oldEdited = oldEdited || [];
    newBase = newBase || [];
    if (!key) {
        const server = oldEdited.filter((row) => !row.local);
        const local = oldEdited.filter((row) => row.local);
        const rows = newBase.map((row, index) => (index < oldBase.length && index < server.length
            ? { ...row, ...changes(oldBase[index], server[index]) }
            : row));
        return [...rows, ...local];
    }
    const before = new Map(oldBase.map((row) => [key(row), row]));
    const edited = new Map(oldEdited.map((row) => [key(row), row]));
    const now = new Set(newBase.map(key));
    const rows = newBase
        // a row the owner took out stays out
        .filter((row) => !(before.has(key(row)) && !edited.has(key(row))))
        .map((row) => {
            const k = key(row);
            return before.has(k) && edited.has(k) && !fresh.includes(k)
                ? { ...row, ...changes(before.get(k), edited.get(k)) }
                : row;
        });
    const local = oldEdited.filter((row) => !before.has(key(row)) && !now.has(key(row)));
    return [...rows, ...local];
}

// The owner's changes to `oldBase` (as `oldEdited`) carried onto
// `newBase`, the server's copy since: a field the owner changed keeps the
// owner's value, any other takes the server's; rows as `ROW_KEYS` match
// them, the owner's own rows kept after the server's. `fresh`: the new
// names (by `nameKey`) the server has just said anew (a selection made a
// stub of those words), which take the server's row as it is.
export function rebaseDraft(oldBase, oldEdited, newBase, { fresh = [] } = {}) {
    if (!oldBase || !oldEdited) {
        return newBase;
    }
    const out = { ...newBase };
    const keys = new Set([...Object.keys(newBase), ...Object.keys(oldEdited)]);
    for (const key of keys) {
        if (key in ROW_KEYS) {
            out[key] = rebaseRows(oldBase[key], oldEdited[key], newBase[key], ROW_KEYS[key], fresh);
        } else if (!same(oldBase[key], oldEdited[key])) {
            out[key] = oldEdited[key];
        }
    }
    return out;
}

// The preview to accept: the owner's draft without the page's own keys
// (those starting with "_").
export function acceptable(edited) {
    return Object.fromEntries(Object.entries(edited || {}).filter(([key]) => !key.startsWith('_')));
}

// A category of `kind` for a fact that had `category`: its own when the
// kind has it, else the kind's first (as the server's `default_category`
// would pick one).
export function categoryFor(kind, category) {
    const categories = (kindInfo(kind)?.categories || []).filter((c) => c !== 'statement' && c !== 'timeline');
    if (!categories.length || categories.includes(category)) {
        return category;
    }
    return categories.includes('general') ? 'general' : categories[0];
}

// The draft's own facts as its page lists them: `{index (into `edited.facts`),
// fact, segments, local, edited (its words changed here), serverIndex}`,
// a removed one left out. Its segments are as accept will link it (P6):
// the server's render of the owner's copy (`rendered`, `draft_render`'s
// reply: `facts: [{index, text, segments}]`) when it rendered these words,
// else the server's copy's own (its names linked, its new names marked
// fresh), else, for words the owner wrote or rewrote here and not yet
// rendered, plain words with the draft's new names marked fresh.
export function draftFactRows(page, edited, rendered = null) {
    const served = new Map((page?.facts || []).filter((fact) => fact.draft).map((fact) => [fact.index, fact]));
    const drawn = new Map((rendered?.facts || []).map((row) => [row.index, row]));
    const newNames = edited?.new_names || [];
    return (edited?.facts || []).flatMap((fact, index) => {
        if (fact.removed) {
            return [];
        }
        const server = fact.local ? null : served.get(index);
        const rewritten = !server || server.text !== fact.text;
        const render = drawn.get(index);
        let segments;
        if (render && render.text === fact.text) {
            segments = render.segments;
        } else if (!rewritten) {
            segments = server.segments;
        } else {
            segments = freshSegments([{ text: fact.text, ref: null, stub: false }], newNames, edited?.selected_names);
        }
        return [{
            index,
            fact,
            local: !!fact.local,
            edited: rewritten,
            // what a selection names: the server's fact, as the server has it
            serverIndex: rewritten ? null : index,
            segments,
        }];
    });
}

// `rows` with the row at `index` changed (`changes` merged in).
function changedAt(rows, index, change) {
    return (rows || []).map((row, i) => (i === index ? { ...row, ...change } : row));
}

// --- the owner's edits, each a change to `edited` -----------------------------

// a fact's tick
export function tickFact(edited, index, ticked) {
    return { facts: changedAt(edited.facts, index, { ticked }) };
}

// "Remove": left in place (the server's index holds), unticked and hidden
export function removeFact(edited, index) {
    return { facts: changedAt(edited.facts, index, { ticked: false, removed: true }) };
}

// a fact the owner edited here: its words, category or date
export function editFact(edited, index, change) {
    return { facts: changedAt(edited.facts, index, change) };
}

// an "elsewhere" row for `target` (`{id, name, kind}`) made from `fact`
function elsewhereRow(fact, target) {
    return {
        target_id: target.id,
        target_name: target.name,
        new: null,
        category: categoryFor(target.kind, fact.category),
        text: fact.text,
        since: fact.since ?? null,
        held_by: fact.held_by ?? null,
        held_by_name: fact.held_by_name ?? null,
        ticked: true,
        repeat_of: null,
        local: true,
    };
}

// "Copy to…" a draft fact: a fact for that page too ("For other pages")
export function copyFactTo(edited, index, target) {
    return { elsewhere: [...(edited.elsewhere || []), elsewhereRow(edited.facts[index], target)] };
}

// "Move to…" a draft fact: a fact for that page, no longer one of this
// page's
export function moveFactTo(edited, index, target) {
    return { ...copyFactTo(edited, index, target), ...removeFact(edited, index) };
}

// "Held by…" a draft fact (`holder` `{id, name}`, or null: world truth)
export function holdFact(edited, index, holder) {
    return { facts: changedAt(edited.facts, index, { held_by: holder?.id || null, held_by_name: holder?.name || null }) };
}

// A repeat's four ways (`how`, P8), each named by the fact it keeps:
// 'new' ("Keep new": this one ticked, and the world's fact it repeats
// removed on accept, `replaces_repeat`), 'existing' ("Keep existing": this
// one unticked), 'both' ("Keep both": this one ticked, the world's left
// where it is) or 'move' ("Move existing here": the world's fact moves
// here, a `repeat` "Could move here" row, and this one isn't written).
export function settleRepeat(edited, index, how) {
    const fact = edited.facts[index];
    const repeat = fact.repeat_of;
    const others = (edited.move_here || []).filter((row) => !(row.repeat && row.fact_id === repeat?.fact_id));
    const facts = changedAt(edited.facts, index, {
        ticked: how === 'new' || how === 'both',
        moveRepeat: how === 'move',
        replaces_repeat: how === 'new',
    });
    if (how !== 'move' || !repeat?.fact_id) {
        return { facts, move_here: others };
    }
    const row = {
        fact_id: repeat.fact_id,
        from_id: repeat.owner_id,
        from_name: repeat.owner_name || null,
        text: repeat.text,
        ticked: true,
        repeat: true,
        local: true,
    };
    return { facts, move_here: [...others, row] };
}

// Which of `settleRepeat`'s ways a repeating draft fact is settled in now
// (one at the untick threshold comes unticked: 'existing').
export function repeatChoice(fact) {
    if (fact?.moveRepeat) {
        return 'move';
    }
    if (fact?.ticked === false) {
        return 'existing';
    }
    return fact?.replaces_repeat ? 'new' : 'both';
}

// "+ also here": an "elsewhere" row's fact is one of this page's too
export function alsoHere(edited, row) {
    const fact = {
        category: categoryFor(edited.kind, row.category),
        text: row.text,
        since: row.since ?? null,
        overrides: [],
        held_by: row.held_by ?? null,
        held_by_name: row.held_by_name ?? null,
        ticked: true,
        repeat_of: null,
        local: true,
    };
    return { facts: [...(edited.facts || []), fact] };
}

// an "elsewhere" row's target changed to `target` (`{id, name, kind}`)
export function retarget(edited, index, target) {
    const row = edited.elsewhere[index];
    return {
        elsewhere: changedAt(edited.elsewhere, index, {
            target_id: target.id,
            target_name: target.name,
            new: null,
            repeat_of: null,
            category: categoryFor(target.kind, row.category),
        }),
    };
}

// An "In" row's key: its target's id, or `new:<name>` for one on a name
// the world hasn't (`new_name`, a stub accept makes).
export function filingKey(row) {
    return row.target_id || `new:${nameKey(row.new_name?.name || row.target_name)}`;
}

// an "In" row's tick, role or since
export function changeFiling(edited, key, change) {
    return { filings: (edited.filings || []).map((row) => (filingKey(row) === key ? { ...row, ...change } : row)) };
}

// "+ in… 🔎" on a draft: the owner's own filing, ticked, in an entry the
// world has (`{id, name}`) or, like the page's, a new stub of a typed name
// (`{newName, kind, tag}`); one already there is ticked (and given the
// role) instead
export function addFiling(edited, target, { role = null, since = null } = {}) {
    const filings = edited.filings || [];
    const row = target.newName
        ? {
            target_id: null,
            new_name: { name: target.newName, kind: target.kind || 'lore', tag: target.tag || null },
            target_name: target.newName,
        }
        : { target_id: target.id, target_name: target.name };
    const key = filingKey(row);
    if (filings.some((found) => filingKey(found) === key)) {
        return changeFiling(edited, key, { ticked: true, ...(role ? { role } : {}), ...(since ? { since } : {}) });
    }
    return {
        filings: [...filings, { ...row, role, since, within: null, exceptions: [], ticked: true, local: true }],
    };
}

// a draft "In" row removed: the owner's own goes, the AI's is unticked
export function removeFiling(edited, key) {
    const filings = edited.filings || [];
    return {
        filings: filings
            .filter((row) => !(row.local && filingKey(row) === key))
            .map((row) => (filingKey(row) === key ? { ...row, ticked: false } : row)),
    };
}

// The draft's kind changed (I3): its own facts' categories become ones
// the new kind has (`categoryFor`). The "For other pages" rows keep
// theirs: those are the target's kind's.
export function changeKind(edited, kind) {
    return {
        kind,
        facts: (edited.facts || []).map((fact) => ({ ...fact, category: categoryFor(kind, fact.category) })),
    };
}

// a "File into this" row's tick
export function tickFileInto(edited, thingId, ticked) {
    return { file_into: (edited.file_into || []).map((row) => (row.thing_id === thingId ? { ...row, ticked } : row)) };
}

// a "Could move here" row's tick
export function tickMoveHere(edited, factId, ticked) {
    return { move_here: (edited.move_here || []).map((row) => (row.fact_id === factId && !row.repeat ? { ...row, ticked } : row)) };
}

// a new name's kind, tag, "same as…" or "in…" (`change`)
export function changeNewName(edited, name, change) {
    const key = nameKey(name);
    return { new_names: (edited.new_names || []).map((row) => (nameKey(row.name) === key ? { ...row, ...change } : row)) };
}

// The words a "Could move here" row highlights: the draft's own name and
// other names (each also without its article, in any case), as
// `LinkedText` segments marking them (`fresh`, in the stub colour, as the
// name it will be).
export function namedSegments(text, edited) {
    const spellings = new Set();
    for (const name of [edited?.name, ...(edited?.aka || []).map((entry) => entry?.name)]) {
        const words = (name || '').trim().split(/\s+/).filter(Boolean);
        if (!words.length) {
            continue;
        }
        spellings.add(words.join(' '));
        if (words.length > 1 && ARTICLES.includes(words[0].toLowerCase())) {
            spellings.add(words.slice(1).join(' '));
        }
    }
    const spans = [];
    for (const spelling of spellings) {
        const pattern = new RegExp(`(?<![\\p{L}\\p{N}])${escapeRegExp(spelling)}(?![\\p{L}\\p{N}])`, 'giu');
        for (const match of (text || '').matchAll(pattern)) {
            spans.push({ start: match.index, end: match.index + match[0].length });
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
        segments.push({ text: text.slice(span.start, span.end), ref: null, stub: false, fresh: true, kind: edited?.kind });
        at = span.end;
    }
    if (at < (text || '').length) {
        segments.push({ text: text.slice(at), ref: null, stub: false });
    }
    return segments;
}

// The bar's versions: `{version, label, current}`, newest first.
export function versionRows(versions, current) {
    return [...(versions || [])].reverse().map((row) => ({
        version: row.version,
        label: `v${row.version} · ${row.name}`,
        prompt: row.prompt,
        current: row.version === current,
    }));
}
