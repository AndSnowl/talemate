// The kinds the World tab shows, with their fact categories (mirroring
// `talemate.world.kinds.KINDS`). Cultures are listed but made through the
// culture skill, so they can't be opened or created here.

export const WORLD_KINDS = [
    {
        kind: 'character',
        label: 'Characters',
        singular: 'character',
        icon: 'mdi-account',
        categories: ['appearance', 'personality', 'background', 'ability', 'relationship', 'speech'],
    },
    {
        kind: 'place',
        label: 'Places',
        singular: 'place',
        icon: 'mdi-map-marker',
        categories: ['description', 'history', 'law', 'general'],
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

// the kinds the store lists and the create box offers
export const LISTED_KINDS = WORLD_KINDS.filter((k) => !k.viaSkill).map((k) => k.kind);

export function kindInfo(kind) {
    return WORLD_KINDS.find((k) => k.kind === kind);
}
