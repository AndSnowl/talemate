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
        const from = sources[part.from_id] || {};
        const name = from.name || 'a connection';
        const role = part.from_role || '';
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
