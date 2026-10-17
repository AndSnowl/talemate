export const LEVEL_LABELS = {
    full: 'Full language',
    naming: 'Naming rules',
    description: 'Description only',
};

export function levelLabel(level) {
    const label = LEVEL_LABELS[level] || level;
    return label.toLowerCase();
}

const KIND_META = {
    person: { color: 'primary', icon: 'mdi-account' },
    place: { color: 'teal', icon: 'mdi-map-marker' },
    thing: { color: 'amber', icon: 'mdi-shape' },
    word: { color: 'blue', icon: 'mdi-translate' },
};

export function kindMeta(kind) {
    return KIND_META[kind] || { color: 'muted', icon: 'mdi-help' };
}

export function originMeta(origin) {
    if (origin && (origin.by === 'ai' || origin.by === 'ai_free')) {
        return { label: 'AI', icon: 'mdi-robot-outline' };
    }
    if (origin && origin.by === 'import') {
        return { label: 'import', icon: 'mdi-file-upload-outline' };
    }
    return { label: 'you', icon: 'mdi-pencil' };
}

export const PLACE_KINDS = [
    'country',
    'region',
    'city',
    'town',
    'village',
    'building',
    'poi',
    'terrain',
];

const PLACE_KIND_LABELS = {
    country: 'Country',
    region: 'Region',
    city: 'City',
    town: 'Town',
    village: 'Village',
    building: 'Building',
    poi: 'Point of interest',
    terrain: 'Terrain',
};

export function placeKindLabel(kind) {
    return PLACE_KIND_LABELS[kind] || kind;
}
