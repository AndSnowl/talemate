// The kinds the World tab shows, with their fact categories (mirroring
// `talemate.world.kinds.KINDS`). The legacy culture kind (`viaSkill`) is
// listed, but can't be opened or created here: a new culture is a sphere
// (the culture template), and an old culture stub is made one ("Make it a
// sphere…"). Races and mixes
// (`nested`) aren't listed at the top level: they're reached from their
// species page. The Stubs tab (`STUBS_TAB`) sits below the kinds.
//
// Spheres (`talemate.world.spheres`): the templates (`SPHERE_TEMPLATES`,
// each with whether it acts in the world), the drawer types, the Spheres
// list grouped by template (`sphereGroups`), the drawers a thing may be
// filed in (`partOfDrawers`) and what "Make it a sphere…" is offered on
// (`canPromote`).
//
// Beings (`talemate.world.kinds`, curation goal 8): a being's `existence`
// (`EXISTENCE`), and whether it acts in the world like a character
// (`actsInWorld`: only a real one is cast, played or tied).

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

// the World tab's settings (curation), below the stubs
export const SETTINGS_TAB = { kind: 'settings', label: 'Settings', icon: 'mdi-tune-variant' };

// the kinds a stub's kind can be changed to: races and mixes are made from
// their species page, so a stub isn't guessed as one; a culture is a
// legacy kind (a culture is a sphere now)
export const STUB_KINDS = ['character', 'species', 'place', 'event', 'item', 'lore', 'being', 'sphere'];

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

// What expanding a stub of `kind` is called: a legacy culture stub is
// made a culture sphere (`worlds.expandStub`).
export function expandLabel(kind) {
    return kind === 'culture' ? 'Make it a sphere…' : 'Expand';
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

// `talemate.world.kinds.WRITTEN_DRAWER_TYPES`: the drawer types whose
// content is written (entries filed there and statements: Fill, "+ Add",
// a preview's items); people, events and branches are the app's own
export const WRITTEN_DRAWER_TYPES = ['places', 'practices', 'beliefs', 'knowledge', 'structure'];

const ENTRY_TYPES = ['practices', 'beliefs', 'knowledge', 'structure'];

// `talemate.world.kinds.ENTRY_DRAWER_TYPES`: the drawer types a thing of
// each kind may be filed in, its keys the kinds a sphere's drawer can hold
// (`PART_OF_KINDS`); a character is in a sphere through its ties instead
export const ENTRY_DRAWER_TYPES = {
    lore: ENTRY_TYPES,
    place: ['places'],
    item: ENTRY_TYPES,
    event: ENTRY_TYPES,
    sphere: ENTRY_TYPES,
    // a god in its faith's Doctrines, a spirit in a culture's customs
    being: ['beliefs', 'practices', 'structure'],
};

// `talemate.world.kinds.PART_OF_KINDS`
export const PART_OF_KINDS = Object.keys(ENTRY_DRAWER_TYPES);

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
// (`ENTRY_DRAWER_TYPES`): a place in a places drawer, anything else in one
// that holds entries; none for a kind no drawer holds.
export function drawerTypesFor(kind) {
    return ENTRY_DRAWER_TYPES[kind] || [];
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

// `drawersPayload(drawers)` with the own drawer `id` moved `delta` (-1 up,
// 1 down) among the sphere's own drawers, inherited ones kept after them;
// null when it can't move that way.
export function drawersMoved(drawers, id, delta) {
    const own = (drawers || []).filter((d) => !d.inherited && d.id !== UNSORTED).map((d) => d.id);
    const payload = drawersPayload(drawers);
    const mine = payload.filter((d) => own.includes(d.id));
    const rest = payload.filter((d) => !own.includes(d.id));
    const index = mine.findIndex((d) => d.id === id);
    const to = index + delta;
    if (index < 0 || to < 0 || to >= mine.length) {
        return null;
    }
    [mine[index], mine[to]] = [mine[to], mine[index]];
    return [...mine, ...rest];
}

// `drawersPayload(drawers)` without the drawer `id` (its items show under
// Unsorted then).
export function drawersDropped(drawers, id) {
    return drawersPayload(drawers).filter((d) => d.id !== id);
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
// character: a character, or a real being (`spheres.acts_in_world`). Only
// these are cast in scenes, played, or tied to spheres.
export function actsInWorld(thing) {
    return thing?.kind === 'character' || (thing?.kind === 'being' && existenceOf(thing) === 'real');
}

// --- same thing? ----------------------------------------------------------------

// Whether "Make X a sphere…" is offered on a same-thing offer (a
// `SameOffer`: `{kind, stub}`), as `canPromote` offers it on a page: a lore
// entry, a place, or a stub of any kind but sphere -- by its `stub` flag,
// never by the words of its line.
export function promotableOffer(offer) {
    if (!offer || offer.kind === 'sphere') {
        return false;
    }
    return offer.kind === 'lore' || offer.kind === 'place' || !!offer.stub;
}

// A same-thing offer's candidate line ("Name (kind; part of Y, in its Z
// drawer; stub): its summary") without its name and kind, which show
// beside it: "part of Y, in its Z drawer: its summary", or just the
// summary. A line of another shape is shown as it is.
export function offerSummary(offer) {
    let line = (offer?.line || '').trim();
    if (offer?.name && line.startsWith(offer.name)) {
        line = line.slice(offer.name.length).trim();
    }
    const found = /^\(([^)]*)\)(?::\s*([\s\S]*))?$/.exec(line);
    if (!found) {
        return line;
    }
    // the kind (and a sphere's template) first; "stub" is shown apart
    const bits = found[1].split(';').map((bit) => bit.trim()).slice(1).filter((bit) => bit && bit !== 'stub');
    const summary = (found[2] || '').trim();
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
