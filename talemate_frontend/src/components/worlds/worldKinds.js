// The kinds the World tab shows, with their fact categories (mirroring
// `talemate.world.kinds.KINDS`). Cultures are listed but made through the
// culture skill, so they can't be opened or created here. Races and mixes
// (`nested`) aren't listed at the top level: they're reached from their
// species page. The Stubs tab (`STUBS_TAB`) sits below the kinds.

const HERITAGE_CATEGORIES = ['origin', 'physical', 'instinct', 'variation', 'general'];

export const WORLD_KINDS = [
    {
        kind: 'character',
        label: 'Characters',
        singular: 'character',
        icon: 'mdi-account',
        categories: ['appearance', 'personality', 'background', 'ability', 'relationship', 'speech'],
    },
    {
        kind: 'species',
        label: 'Species',
        singular: 'species',
        icon: 'mdi-dna',
        categories: HERITAGE_CATEGORIES,
    },
    {
        kind: 'race',
        label: 'Races',
        singular: 'race',
        icon: 'mdi-family-tree',
        categories: HERITAGE_CATEGORIES,
        nested: true,
    },
    {
        kind: 'mix',
        label: 'Mixes',
        singular: 'mix',
        icon: 'mdi-call-merge',
        categories: HERITAGE_CATEGORIES,
        nested: true,
    },
    {
        kind: 'place',
        label: 'Places',
        singular: 'place',
        icon: 'mdi-map-marker',
        categories: ['description', 'history', 'law', 'general'],
    },
    {
        kind: 'event',
        label: 'Events',
        singular: 'event',
        icon: 'mdi-calendar-star',
        categories: ['summary', 'consequence', 'general'],
    },
    {
        kind: 'item',
        label: 'Items',
        singular: 'item',
        icon: 'mdi-sword',
        categories: ['description', 'history', 'power', 'general'],
    },
    {
        kind: 'lore',
        label: 'Lore',
        singular: 'lore entry',
        icon: 'mdi-book-open-variant',
        categories: ['general'],
    },
    {
        kind: 'culture',
        label: 'Cultures',
        singular: 'culture',
        icon: 'mdi-account-group',
        categories: [],
        viaSkill: true,
    },
];

// the kinds the store lists
export const LISTED_KINDS = WORLD_KINDS.filter((k) => !k.viaSkill).map((k) => k.kind);

// the kinds the World tab lists (and the create box offers)
export const TOP_KINDS = WORLD_KINDS.filter((k) => !k.nested);

// the World tab's list of stubs, below the kinds
export const STUBS_TAB = { kind: 'stubs', label: 'Stubs', icon: 'mdi-help-circle-outline' };

// the kinds a stub's kind can be changed to: races and mixes are made from
// their species page, so a stub isn't guessed as one
export const STUB_KINDS = ['character', 'species', 'place', 'event', 'item', 'lore', 'culture'];

// Whether a stub of `kind` can be expanded here: a culture can't until the
// cultures slice (`EXPAND_LATER_NOTE` says so).
export function canExpand(kind) {
    return kind !== 'culture';
}

export const EXPAND_LATER_NOTE = 'Cultures arrive in the next slice';

// the kinds a character's heritage can be (`talemate.world.kinds.HERITAGE_KINDS`)
export const HERITAGE_KINDS = ['species', 'race', 'mix'];

// the kinds that inherit facts, and show what they inherit
export const INHERITING_KINDS = ['character', 'race', 'mix'];

// A character's category for its own fact overriding an inherited one,
// following how prose_gen sections them: body facts are appearance,
// instincts personality, the rest background. A heritage kind keeps the
// category.
const CHARACTER_CATEGORY = {
    physical: 'appearance',
    variation: 'appearance',
    instinct: 'personality',
    origin: 'background',
    general: 'background',
};

export function overrideCategory(kind, category) {
    const categories = kindInfo(kind)?.categories || [];
    if (categories.includes(category)) {
        return category;
    }
    const mapped = kind === 'character' ? CHARACTER_CATEGORY[category] : null;
    return mapped && categories.includes(mapped) ? mapped : categories[0];
}

export function kindInfo(kind) {
    return WORLD_KINDS.find((k) => k.kind === kind);
}
