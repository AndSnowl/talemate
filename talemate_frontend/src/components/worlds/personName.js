import { pickName } from './nameMarks.js';

// A person's name in parts (languages 4b-2), as their page shows it: the
// name written from its parts, where each part came from, and the names
// others call them (frame B: on the relationship they belong to).

const MISSING = '(missing rule)';

// the parts' texts joined, a fixed word written in English where the rule
// says so (`english`: part index → its English writing); missing parts
// left out, as the server's `person_names.written`
export function writtenName(parts, english = {}) {
    return (parts || [])
        .map((part, i) => english[i] || part.text)
        .filter((text) => text && text !== MISSING)
        .join(' ');
}

function numbered(name, regnal) {
    return regnal ? `${name} ${regnal}` : name;
}

// the names used by an entry this fact links (a relationship's "calls
// her" line); a name everyone uses (no `by`) isn't one
export function callsFor(calls, fact) {
    const refs = new Set(fact?.refs || []);
    return (calls || []).filter((call) => call.by && refs.has(call.by));
}

const PARENT = /\b(son|daughter|child|mother|father|parent)\b/i;

// "her", "him" or "them", from what the name is built as
export function pronounOf(builtAs) {
    return { woman: 'her', man: 'him' }[builtAs?.sex] || 'them';
}

function possessive(pronoun) {
    return { her: 'her', him: 'his', them: 'their' }[pronoun] || 'their';
}

// where a part's text came from: an inherited part names its source
// ("from her father Eilhaud of Drassone"; `sources`: id → {name, sex})
export function partSourceLine(part, sources = {}, pronoun = 'them') {
    if (part?.source === 'inherited') {
        const from = sources[part.from_id];
        const role = part.from_role || '';
        // its source is gone (deleted or merged away): no name, no link
        if (!from) return PARENT.test(role) ? `from ${possessive(pronoun)} parent, no longer in the world` : 'from a connection no longer in the world';
        const name = from.name;
        if (!PARENT.test(role)) return `from ${name}`;
        const said = /\bmother\b/i.test(role) ? 'mother' : /\bfather\b/i.test(role) ? 'father' : null;
        const parent = said || { woman: 'mother', man: 'father' }[from.sex] || 'parent';
        return `from ${possessive(pronoun)} ${parent} ${name}`;
    }
    return { typed: 'typed', meaning: 'from a meaning', word: 'fixed word' }[part?.source] || 'rolled';
}

// the other names without a kind: titles, pet names and what others call
// a person are shown by the Name section and the relationships
export function plainAka(aka) {
    return (aka || []).filter((entry) => !entry.kind);
}

// the rows a drafted person's Name it is built from: the ticked ones,
// and the model's parent rows, which arrive unticked (final review I8);
// `[target_id, role]`
export function draftParentRows(filings) {
    return (filings || [])
        .filter((f) => f.target_id && (f.ticked || PARENT.test(f.role || '')))
        .map((f) => [f.target_id, f.role || '']);
}

// a title's next place with the name (none → before → after → none), as
// `person_title_add` takes it, its language and meaning kept (I13)
export function titleShownChange(title) {
    const next = { before: 'after', after: null }[title.shown] ?? (title.shown ? null : 'before');
    return {
        name: title.name,
        shown: next,
        ...(title.language ? { language_id: title.language } : {}),
        ...(title.meaning ? { meaning: title.meaning } : {}),
    };
}

// A drafted person's Name section edits the draft itself, as the page's
// edits write the entry (owner, 2026-11-05): `change` is one of `{part:
// [index, text]}`, `{title}`, `{removeTitle}`, `{builtAs}` or `{pet}`;
// `english`: part index → its English writing. The draft's changes
// (`editDraft`'s), or null.
export function draftNameEdit(edited, change, english = {}) {
    const stored = edited?.fields?.name_parts;
    const aka = (edited?.aka || []).map((a) => ({ ...a }));
    if ((change.part || change.regnal !== undefined) && stored) {
        const parts = change.part
            ? stored.parts.map((p, i) => (i === change.part[0] ? { label: p.label, text: change.part[1], source: 'typed' } : { ...p }))
            : stored.parts.map((p) => ({ ...p }));
        const regnal = change.regnal !== undefined ? change.regnal.trim() : stored.regnal || '';
        const before = numbered(writtenName(stored.parts, english), stored.regnal || '');
        const after = numbered(writtenName(parts, english), regnal);
        // the narrator words around the written name stay (4c)
        const name = edited.name.includes(before) ? edited.name.replace(before, after) : after;
        const next = { ...stored, parts, ...(regnal ? { regnal } : {}) };
        if (!regnal) delete next.regnal;
        return { ...pickName(edited, edited.name, name), name, fields: { ...edited.fields, name_parts: next } };
    }
    if (change.title) {
        const { name, shown, language_id: language, meaning } = change.title;
        const kept = aka.filter((a) => a.name.toLowerCase() !== name.toLowerCase());
        const others = shown ? kept.map(({ shown: _shown, ...rest }) => rest) : kept;
        const entry = { name, tag: 'proper', everyday: false, kind: 'title', ...(language ? { language } : {}), ...(meaning ? { meaning } : {}), ...(shown ? { shown } : {}) };
        return { aka: [...others, entry] };
    }
    if (change.removeTitle) {
        return { aka: aka.filter((a) => !(a.kind === 'title' && a.name === change.removeTitle)) };
    }
    if (change.builtAs && stored) {
        return { fields: { ...edited.fields, name_parts: { ...stored, built_as: { ...change.builtAs } } } };
    }
    if (change.pet) {
        return { aka: [...aka.filter((a) => !(a.kind === 'pet' && !a.by)), { name: change.pet, tag: 'proper', everyday: false, kind: 'pet' }] };
    }
    return null;
}
