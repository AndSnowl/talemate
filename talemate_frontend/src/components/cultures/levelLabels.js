export const LEVEL_LABELS = {
    full: 'Full language',
    naming: 'Naming rules',
    description: 'Description only',
};

export function levelLabel(level) {
    const label = LEVEL_LABELS[level] || level;
    return label.toLowerCase();
}
