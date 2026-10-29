// The grammar topics a full language covers, with their plain titles, in
// the brief's order (talemate.languages.models.GRAMMAR_TOPICS).
export const TOPICS = [
    ['sounds', 'Sounds and stress'],
    ['word_order', 'Word order'],
    ['nouns', 'Nouns'],
    ['pronouns', 'Pronouns'],
    ['verbs', 'Verbs'],
    ['adjectives', 'Adjectives'],
    ['questions', 'Questions and "not"'],
    ['numbers', 'Numbers'],
    ['word_building', 'How words are built'],
    ['names', 'How names are built'],
    ['politeness', 'Politeness and registers'],
];
export const TOPIC_ORDER = Object.fromEntries(TOPICS.map(([id], i) => [id, i]));
export const TOPIC_TITLES = Object.fromEntries(TOPICS);

// a language's grammar sections; an older language's grammar text is one
export function grammarSections(rules) {
    const grammar = rules?.grammar;
    if (!grammar) return [];
    if (typeof grammar === 'string') return [{ title: 'Grammar', topic: 'other', text: grammar }];
    return grammar;
}

// an older language's grammar text: one plain "Grammar" section, not
// something unusual
export function isPlainGrammar(section) {
    return section.topic === 'other' && section.title === 'Grammar';
}
