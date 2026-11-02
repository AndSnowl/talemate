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
    return { kind, rule: '', word: '', slot: 'noun', forms: [], of: false, joined: false, ending: '', hint: '', optional: false, label: '' };
}
