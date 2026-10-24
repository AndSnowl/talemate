// The kinds the World tab shows, with their fact categories (mirroring
// `talemate.world.kinds.KINDS`). Races and mixes (`nested`) aren't listed
// at the top level: they're reached from their species page; Cultures
// (`viaSkill`) is listed but made through the culture skill. The Stubs,
// Tags and Settings tabs (`STUBS_TAB`, `TAGS_TAB`, `SETTINGS_TAB`) sit
// below the kinds.
//
// Beings (`talemate.world.kinds`, curation goal 8): a being's `existence`
// (`EXISTENCE`), and whether it acts in the world like a character
// (`actsInWorld`: only a real one is cast, played or counted as a person).

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
        // a god, a spirit, a legendary creature: real (it acts in the world
        // like a character), believed or undecided (`EXISTENCE`)
        kind: 'being',
        label: 'Beings',
        singular: 'being',
        icon: 'mdi-star-four-points-outline',
        categories: ['nature', 'deeds', 'worship', 'general'],
    },
    {
        // not a world kind: a pointer to the cultures feature (World Editor →
        // Cultures), whose cultures are made through the culture skill
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

// the World tab's tags (rename and merge), below the stubs
export const TAGS_TAB = { kind: 'tags', label: 'Tags', icon: 'mdi-tag-multiple-outline' };

// the World tab's settings (curation), below the tags
export const SETTINGS_TAB = { kind: 'settings', label: 'Settings', icon: 'mdi-tune-variant' };

// the kinds a stub's kind can be changed to: races and mixes are made from
// their species page, so a stub isn't guessed as one
export const STUB_KINDS = ['character', 'species', 'place', 'event', 'item', 'lore', 'being'];

// Why a stub of `kind` can't be expanded here (null when it can): a race
// or mix needs its species (or parents), which only its species page's
// create box gives it.
const NO_EXPAND_NOTES = {
    race: 'Make it from its species page',
    mix: 'Make it from its species page',
};

export function expandNote(kind) {
    return NO_EXPAND_NOTES[kind] || null;
}

// Whether a stub of `kind` can be expanded from its card or the Stubs tab.
export function canExpand(kind) {
    return !expandNote(kind);
}

// What expanding a stub of `kind` is called.
export function expandLabel(_kind) {
    return 'Expand';
}

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

// --- beings -------------------------------------------------------------------

// `talemate.world.kinds.EXISTENCE_VALUES`, and what an unset one reads as
export const EXISTENCE = ['real', 'believed', 'undecided'];
export const DEFAULT_EXISTENCE = 'undecided';

// A being's existence (`fields.existence` of its payload, or `existence`
// of its listing), the default when unset.
export function existenceOf(thing) {
    const value = thing?.existence ?? thing?.fields?.existence;
    return EXISTENCE.includes(value) ? value : DEFAULT_EXISTENCE;
}

// Whether `thing` (a payload or a listing) acts in the world like a
// character: a character, or a real being (`entries.acts_in_world`). Only
// these are cast in scenes, played, or counted as persons.
export function actsInWorld(thing) {
    return thing?.kind === 'character' || (thing?.kind === 'being' && existenceOf(thing) === 'real');
}

// --- same thing? ----------------------------------------------------------------

// A stub row's "same as" onto a thing of another kind (ruling C34: a
// stub's kind is only a guess, so its row offers every kind): the small
// "(a lore)" note beside its choice; '' for the same kind, or none known.
export function otherKindNote(rowKind, offer) {
    const kind = offer?.kind;
    if (!rowKind || !kind || rowKind === kind) {
        return '';
    }
    return `(${/^[aeiou]/i.test(kind) ? 'an' : 'a'} ${kind})`;
}

// A same-thing offer's candidate line ("Name (kind, tag; in Y; stub): its
// summary") without its name and kind, which show beside it: "in Y: its
// summary", or just the summary. A line of another shape is shown as it
// is.
export function offerSummary(offer) {
    let line = (offer?.line || '').trim();
    if (offer?.name && line.startsWith(offer.name)) {
        line = line.slice(offer.name.length).trim();
    }
    // its parenthesis, which may hold others ("in Velikoye (runs through)")
    let close = -1;
    if (line.startsWith('(')) {
        let depth = 0;
        for (let i = 0; i < line.length; i += 1) {
            depth += line[i] === '(' ? 1 : line[i] === ')' ? -1 : 0;
            if (depth === 0) {
                close = i;
                break;
            }
        }
    }
    const rest = close > 0 ? line.slice(close + 1) : '';
    if (close < 0 || (rest && !rest.startsWith(':'))) {
        return line;
    }
    // the kind (and its tag) first; "stub" is shown apart
    const bits = line.slice(1, close).split(';').map((bit) => bit.trim()).slice(1).filter((bit) => bit && bit !== 'stub');
    const summary = rest.slice(1).trim();
    if (!bits.length) {
        return summary;
    }
    return summary ? `${bits.join('; ')}: ${summary}` : bits.join('; ');
}

// --- inline editors -------------------------------------------------------------

// Whether Esc (`event`, its keydown) closes an inline editor: not when it
// closes a picker of it first (a select or autocomplete it came from) or
// an open menu or popover.
export function escapeCloses(event) {
    if (event?.target?.closest?.('.v-select, .v-autocomplete, .v-combobox')) {
        return false;
    }
    return typeof document === 'undefined' || !document.querySelector('.v-overlay--active');
}
