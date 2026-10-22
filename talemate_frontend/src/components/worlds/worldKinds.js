// The kinds the World tab shows, with their fact categories (mirroring
// `talemate.world.kinds.KINDS`). Cultures are listed but made through the
// culture skill, so they can't be opened or created here. Races and mixes
// (`nested`) aren't listed at the top level: they're reached from their
// species page. The Stubs tab (`STUBS_TAB`) sits below the kinds.
//
// Spheres (`talemate.world.spheres`): the templates (`SPHERE_TEMPLATES`,
// each with whether it acts in the world), the drawer types, the Spheres
// list grouped by template (`sphereGroups`), the drawers a thing may be
// filed in (`partOfDrawers`) and what "Make it a sphere…" is offered on
// (`canPromote`).

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
        kind: 'sphere',
        label: 'Spheres',
        singular: 'sphere',
        icon: 'mdi-orbit',
        categories: ['timeline', 'about', 'statement'],
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
export const STUB_KINDS = ['character', 'species', 'place', 'event', 'item', 'lore', 'sphere', 'culture'];

// Why a stub of `kind` can't be expanded here (null when it can): a culture
// waits for the cultures slice; a race or mix needs its species (or
// parents), which only its species page's create box gives it.
const NO_EXPAND_NOTES = {
    culture: 'Cultures arrive in the next slice',
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

// --- spheres ------------------------------------------------------------------

// `talemate.world.kinds.SPHERE_TEMPLATES` and `TEMPLATE_AGENT`, in order,
// with the Spheres list's group headings
export const SPHERE_TEMPLATES = [
    { template: 'religion', label: 'Religion', plural: 'Religions', agent: true },
    { template: 'nation', label: 'Nation', plural: 'Nations', agent: true },
    { template: 'order', label: 'Order', plural: 'Orders', agent: true },
    { template: 'culture', label: 'Culture', plural: 'Cultures', agent: false },
    { template: 'field', label: 'Field', plural: 'Fields', agent: false },
    { template: 'other', label: 'Other', plural: 'Other spheres', agent: false },
];

// `talemate.world.kinds.DRAWER_TYPES`
export const DRAWER_TYPES = ['people', 'places', 'practices', 'beliefs', 'knowledge', 'structure', 'branches', 'events'];

// the drawer of "no drawer yet" (`UNSORTED_DRAWER_ID`)
export const UNSORTED = 'unsorted';

// the kinds a sphere's drawer can hold (`create.PART_OF_KINDS`); a
// character is in a sphere through its ties instead
export const PART_OF_KINDS = ['lore', 'place', 'item', 'event', 'sphere'];

// the drawer types that hold entries a thing can be filed in
const ITEM_DRAWER_TYPES = ['practices', 'beliefs', 'knowledge', 'structure'];

// A template's entry, `other`'s for an unknown or missing one.
export function templateInfo(template) {
    return SPHERE_TEMPLATES.find((t) => t.template === template) || SPHERE_TEMPLATES[SPHERE_TEMPLATES.length - 1];
}

// The Spheres list (`list_things` "sphere" entries, place spheres
// included) as `[{template, label, things}]` in template order, leaving out
// empty groups; an unknown or missing template is `other`. Each group keeps
// the listing's order, stubs among the rest.
export function sphereGroups(things) {
    return SPHERE_TEMPLATES.map((info) => ({
        template: info.template,
        label: info.plural,
        things: (things || []).filter((thing) => templateInfo(thing.template).template === info.template),
    })).filter((group) => group.things.length);
}

// The drawer types a `kind` thing may be filed in, as the backend allows
// (`create.drawer_types_for`): a place in a places drawer, anything else
// in one that holds entries.
export function drawerTypesFor(kind) {
    return kind === 'place' ? ['places'] : ITEM_DRAWER_TYPES;
}

// The drawers of a sphere (its payload's `drawers`) a `kind` thing may be
// filed in, as `{id, title}`, then Unsorted, always allowed.
export function partOfDrawers(drawers, kind) {
    const allowed = drawerTypesFor(kind);
    const found = (drawers || [])
        .filter((drawer) => drawer.id !== UNSORTED && allowed.includes(drawer.type))
        .map((drawer) => ({ id: drawer.id, title: drawer.title }));
    return [...found, { id: UNSORTED, title: 'Unsorted' }];
}

// Whether "Make it a sphere…" is offered on `thing` (a payload): a lore
// entry, a place that isn't a sphere yet, or a stub of any kind but
// sphere (that one's expanded as it is).
export function canPromote(thing) {
    if (!thing || thing.sphere) {
        return false;
    }
    if (thing.kind === 'lore' || thing.kind === 'place') {
        return true;
    }
    return !!thing.stub && thing.kind !== 'sphere';
}

// "Practitioner of", "Of": a tie's role leading its sphere's name.
export function tieLead(role) {
    const clean = (role || '').trim();
    return clean ? `${clean[0].toUpperCase()}${clean.slice(1)} of` : 'Of';
}

// A sphere's drawers for `set_drawers`: every drawer shown but Unsorted,
// as `{id, type, title}` (the backend keeps an inherited one sent back
// unchanged as inherited).
export function drawersPayload(drawers) {
    return (drawers || []).filter((drawer) => drawer.id !== UNSORTED).map(({ id, type, title }) => ({ id, type, title }));
}
