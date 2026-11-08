// The parts of a composed name rule (languages 4b-1), as the Names
// chapter and the Name it builder show them: another rule by its name, a
// fixed word as itself, a meaning part by what it takes ("a meaning ·
// plural"), as the server's `composed._label` says.
export function partLabel(part, generators = []) {
    if (part?.label) return part.label;
    if (part?.kind === 'word') return part.word || '';
    if (part?.kind === 'rule') {
        return generators.find((g) => g.id === part.rule)?.name || '(missing rule)';
    }
    let label = part?.slot === 'describing_noun' ? 'a description' : 'a meaning';
    if (part?.of) label += ' · of';
    if ((part?.forms || []).includes('more_than_one')) label += ' · plural';
    if ((part?.forms || []).includes('the')) label += ' · the';
    if (part?.ending) label += ` · ${part.ending}`;
    return label;
}

// a new part of `kind`, as the parts editor adds it
export function newPart(kind = 'meaning') {
    return { kind, rule: '', word: '', slot: 'noun', forms: [], of: false, joined: false, ending: '', hint: '', optional: false, label: '', roles: [], take: '', english: '', person_forms: [] };
}

// Renaming part of an entry's name (owner, 2026-11-04): the words picked
// (`picked`, indices into the name's words) are replaced, the others kept
// where they are; the new name goes where the first picked word was.
// "King Zakan III" with Zakan picked and Velmar → "King Velmar III".
export function composeName(fullName, picked, name) {
    const words = (fullName || '').split(/\s+/).filter(Boolean);
    const chosen = new Set(picked || []);
    const first = Math.min(...[...chosen]);
    const out = [];
    words.forEach((word, i) => {
        if (!chosen.has(i)) out.push(word);
        else if (i === first) out.push(name);
    });
    return out.join(' ');
}

// what the rename will give, as the panel shows it under the name's
// words: "King + new name + III", kept words that stand together as one
// piece ("Commander + new name + of the Watch"); "" when no word is picked
export function resultLine(fullName, picked) {
    const chosen = new Set(picked || []);
    if (!chosen.size) return '';
    const words = (fullName || '').split(/\s+/).filter(Boolean);
    const first = Math.min(...chosen);
    const pieces = [];
    let kept = [];
    words.forEach((word, i) => {
        if (!chosen.has(i)) {
            kept.push(word);
            return;
        }
        if (kept.length) pieces.push(kept.join(' '));
        kept = [];
        if (i === first) pieces.push('new name');
    });
    if (kept.length) pieces.push(kept.join(' '));
    return pieces.join(' + ');
}

// A people rule's part as the Names chapter's chips say it (languages
// 4b-2): where a connection part takes from, a person's own part, a fixed
// word with its English writing, and forms by who the person is.
export function ruleChipLabel(part, generators = []) {
    let label;
    if (part?.kind === 'connection') {
        const roles = (part.roles || []).join(', then ') || 'a connection';
        label = `from ${roles} · ${part.take || 'whole name'}`;
    } else if (part?.kind === 'own') {
        label = `own ${part.take || 'name'}`;
    } else if (part?.kind === 'word') {
        label = part.english ? `${part.word} → “${part.english}”` : part.word || '';
    } else {
        label = partLabel(part, generators);
    }
    const by = [...new Set((part?.person_forms || []).flatMap((f) => Object.keys(f.when || {})))];
    return by.length ? `${label} · forms by ${by.join(', ')}` : label;
}

// who a people rule is for, as its row says it: "for: woman · noble"
export function forPersonLine(generator) {
    const values = Object.values(generator?.for_person || {});
    return values.length ? `for: ${values.join(' · ')}` : '';
}

// Name it's rule dropdown (languages 4c): the main rules first, then a
// "Pieces" header and the rules other rules are made of
export function ruleMenuItems(rules) {
    const items = (rules || []).filter((r) => r.main !== false).map((r) => ({ title: r.name, value: r.id }));
    const pieces = (rules || []).filter((r) => r.main === false).map((r) => ({ title: r.name, value: r.id }));
    return pieces.length ? [...items, { type: 'subheader', title: 'Pieces' }, ...pieces] : items;
}

// a main rule (a whole name) or a piece other rules are made of, as the
// server's `person_names.is_main` says: the file's `main` first; else a
// rule used as another's part, or one for words or pet names, is a piece
export function isMainRule(generator, generators = []) {
    if (generator?.main === true || generator?.main === false) return generator.main;
    if (['words', 'pet names'].includes(generator?.use)) return false;
    const used = new Set(
        generators.flatMap((g) => (g.shapes || []).flatMap((s) => (s.parts || []).filter((p) => ['rule', 'connection'].includes(p.kind) && p.rule).map((p) => p.rule))),
    );
    return !used.has(generator?.id);
}

const ROMAN = /^[IVXLCDM]+$/;

// what's wrong with a regnal number the owner typed, or '' (languages 4c:
// the narrator's, always a Roman numeral)
export function regnalError(text) {
    const value = (text || '').trim();
    return !value || ROMAN.test(value) ? '' : 'A regnal number is a Roman numeral, such as III.';
}

// A person's whole name renamed (languages 4c): `properPart` (the words
// marked) becomes `built`; narrator words stay where they were, except an
// English title the rule's own word stands for (`titleWords`, "tsar" for
// "Gosmar"), and, when the rule builds its own "of <house>"
// (`buildsOf`), an "of <place>" right after the name. The regnal number
// goes after the built name: `regnal` when given, the name's own when it's
// '', none when it's null.
export function personRename(fullName, properPart, built, { titleWords = [], buildsOf = false, regnal = '' } = {}) {
    const words = (fullName || '').split(/\s+/).filter(Boolean);
    const proper = (properPart || '').split(/\s+/).filter(Boolean);
    let at = words.findIndex((_, i) => proper.length && proper.every((p, j) => words[i + j] === p));
    if (at < 0) at = words.length;
    const drop = new Set(titleWords.map((t) => t.toLowerCase()));
    const numeral = words.find((w) => ROMAN.test(w)) || '';
    const before = words.slice(0, at).filter((w) => !drop.has(w.toLowerCase()) && !ROMAN.test(w));
    let after = words.slice(at + proper.length).filter((w) => !ROMAN.test(w));
    if (buildsOf && after[0]?.toLowerCase() === 'of') {
        let end = 1;
        while (end < after.length && /^[\p{Lu}]/u.test(after[end])) end += 1;
        after = after.slice(end);
    }
    const number = regnal === null ? '' : regnal || numeral;
    return [...before, built, ...(number ? [number] : []), ...after].join(' ');
}
