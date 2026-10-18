// Pure story-highlight logic shared by the scene renderer and the
// cultures UI: turning a scene's foreign-word lexicon into highlight
// mentions, keying glossary names for lookup, and folding the `cultures`
// websocket messages into a small piece of reactive state.
//
// Relative imports only — no Vue, no `@/` imports — so this module can be
// loaded from plain node (see `checks/culturesStory.check.mjs`).

export const FOREIGN_KIND = 'foreign';

// Characters stripped from the ends of a candidate phrase before it's
// considered for matching. Mirrors talemate.cultures.lexicon's
// `_KEY_STRIP_CHARS`.
const STRIP_CHARS = ' .,;:!?…"“”‘\'()';
const STRIP_START_RE = new RegExp(`^[${STRIP_CHARS}]+`);
const STRIP_END_RE = new RegExp(`[${STRIP_CHARS}]+$`);

function stripEnds(s) {
    return s.replace(STRIP_START_RE, '').replace(STRIP_END_RE, '');
}

// Return the empty, just-loaded shape of the cultures story state.
export function emptyStoryState() {
    return {
        counts: {},
        story: {
            available: false,
            lexicon: [],
            names: [],
            characters: [],
            places: [],
        },
        pendingReview: null,
        reviewSeq: 0,
    };
}

// Normalise `text` into the phrase variant(s) the renderer should match
// against story text: straight-apostrophe and (when the text has an
// apostrophe) curly-apostrophe. Returns `[]` when nothing is left after
// trimming whitespace and leading/trailing punctuation.
export function matchVariants(text) {
    if (typeof text !== 'string') return [];
    let s = text.replace(/[’‘]/g, "'");
    s = s.replace(/\s+/g, ' ');
    s = stripEnds(s).trim();
    if (!s) return [];
    const variants = [s];
    if (s.includes("'")) {
        variants.push(s.replace(/'/g, '’'));
    }
    return variants;
}

// Turn the scene's foreign-word lexicon (the `story` push's `lexicon`) into
// renderer mentions. Entries with no matchable variants are dropped.
export function foreignMentions(lexicon) {
    const mentions = [];
    for (const entry of lexicon || []) {
        const phrases = matchVariants(entry.text);
        if (phrases.length === 0) continue;
        mentions.push({
            name: entry.id,
            kind: FOREIGN_KIND,
            subkind: entry.kind,
            phrases,
        });
    }
    return mentions;
}

// A lookup key for a glossary name or a story mention's name: lowercase,
// trimmed, curly apostrophe folded to straight, trailing sentence
// punctuation dropped, and a trailing possessive `'s` dropped.
export function nameKey(text) {
    if (typeof text !== 'string') return '';
    let s = text.toLowerCase().trim().replace(/’/g, "'");
    s = s.replace(/[.,;:!?]+$/, '');
    s = s.replace(/'s$/, '');
    return s;
}

// Index `story.names` (`NameInfo[]`) by every text a story
// mention might carry: the name's own text, each culture rendering's
// text, and the character name it belongs to (when any). The first entry
// to claim a key wins.
//
// Memoised by the `names` array itself: every chip and open bubble asks
// for the index, and an unchanged story push keeps the same array.
const nameIndexCache = new WeakMap();

export function buildNameIndex(names) {
    if (Array.isArray(names) && nameIndexCache.has(names)) {
        return nameIndexCache.get(names);
    }
    const index = new Map();
    const addKey = (key, info) => {
        if (!key) return;
        if (!index.has(key)) index.set(key, info);
    };
    for (const info of names || []) {
        addKey(nameKey(info.text), info);
        for (const rendering of info.renderings || []) {
            addKey(nameKey(rendering.text), info);
        }
        addKey(nameKey(info.character_name), info);
    }
    if (Array.isArray(names)) nameIndexCache.set(names, index);
    return index;
}

// Return a new mentions array where every mention whose name resolves
// (via `nameKey`/`index`) to an `unreviewed` glossary entry carries
// `unreviewed: true`.
export function markUnreviewed(entityMentions, index) {
    return (entityMentions || []).map((mention) => {
        const info = index.get(nameKey(mention.name));
        if (info && info.status === 'unreviewed') {
            return { ...mention, unreviewed: true };
        }
        return mention;
    });
}

// Combine name mentions with foreign-word mentions, names first — so a
// name wins over a foreign entry with the same text (see
// `compileEntityMentions`'s first-wins dedupe).
export function combineMentions(entityMentions, foreign) {
    return [...(entityMentions || []), ...(foreign || [])];
}

// Find a lexicon entry by id in a `story` payload, or null.
export function findLexiconEntry(story, id) {
    if (!story || !Array.isArray(story.lexicon)) return null;
    return story.lexicon.find((entry) => entry.id === id) ?? null;
}

// A key's leading "the " (as `nameKey` would leave it, already lowercase),
// stripped — so a place can be matched whether or not the entity's own
// text and the place's stored name agree on carrying one.
function stripLeadingThe(key) {
    return key.startsWith('the ') ? key.slice(4) : key;
}

// Find the `CharacterInfo` for `entityName`, whatever its
// culture state — characterChip needs to see an uncultured/owner-cleared
// character too, unlike `findCharacterInfo` below.
function findCharacterInfoAny(characters, entityName) {
    const key = nameKey(entityName);
    return (characters || []).find((c) => nameKey(c.name) === key) ?? null;
}

// Find the `CharacterInfo` for `entityName`, but only
// when it has a culture assigned — an uncultured character gets no
// culture section at all.
function findCharacterInfo(characters, entityName) {
    const character = findCharacterInfoAny(characters, entityName);
    return character && character.culture_id != null ? character : null;
}

// Find the `PlaceInfo` for `entityName`, matching by
// `nameKey` and, failing that, with a leading "the " dropped from either
// side.
function findPlaceInfo(places, entityName) {
    const key = nameKey(entityName);
    const stripped = stripLeadingThe(key);
    for (const place of places || []) {
        const placeKey = nameKey(place.name);
        if (placeKey === key || stripLeadingThe(placeKey) === stripped) {
            return place;
        }
    }
    return null;
}

// Build the culture note shared by characters and places: "Worked out by
// the AI" (plus " · {reason}" when there is one) for `set_by: 'ai'`, "Set
// by you" for `set_by: 'owner'`, plus " · not sure" when `unsure`.
function cultureNote({ set_by: setBy, unsure, reason }) {
    let note = setBy === 'owner'
        ? 'Set by you'
        : (reason ? `Worked out by the AI · ${reason}` : 'Worked out by the AI');
    if (unsure) note += ' · not sure';
    return note;
}

// Build the review-note text for an unreviewed `NameInfo`: "Added by the
// AI, not reviewed yet." for an `ai`/`ai_free` origin, else "Not reviewed
// yet.", plus " Picked from {generator_name}." when that's known.
function reviewNote(info) {
    const base = (info.origin_by === 'ai' || info.origin_by === 'ai_free')
        ? 'Added by the AI, not reviewed yet.'
        : 'Not reviewed yet.';
    return info.generator_name ? `${base} Picked from ${info.generator_name}.` : base;
}

// Build the `NameLanguageSection`'s model for `entity` (`{name, kind}`,
// `kind` one of `character`/`item`/`place`): the glossary `NameInfo`
// looked up by name, plus — for a character or a place — what's known
// about its culture. `null` when there's neither.
export function nameSection(story, entity) {
    if (!story || !entity) return null;

    const index = buildNameIndex(story.names);
    const info = index.get(nameKey(entity.name)) ?? null;

    let culture = null;
    if (entity.kind === 'character') {
        const character = findCharacterInfo(story.characters, entity.name);
        if (character) {
            culture = {
                chips: [{ name: character.culture_name, color: character.color, share: null }],
                note: cultureNote(character),
                changeTarget: { type: 'people', character_name: character.name },
            };
        }
    } else if (entity.kind === 'place') {
        const place = findPlaceInfo(story.places, entity.name);
        if (place && Array.isArray(place.mix) && place.mix.length > 0) {
            culture = {
                chips: place.mix.map((cs) => ({ name: cs.culture_name, color: cs.color, share: cs.share })),
                note: place.own
                    ? cultureNote(place)
                    : `From ${place.source_name}`,
                changeTarget: { type: 'place', place_id: place.id },
            };
        }
    }

    if (!info && !culture) return null;

    const language = info && info.language_name
        ? { name: info.language_name, color: info.color }
        : null;
    const languageNote = language
        ? null
        : (info?.origin_by === 'ai_free' ? 'invented freely by the AI' : 'no language yet');

    const trueName = info && info.writable === false && info.true_name
        ? {
            language_name: info.language_name,
            text: info.true_name,
            renderings: info.renderings,
        }
        : null;

    const review = info && info.status === 'unreviewed'
        ? { note: reviewNote(info), target: { type: 'glossary', entry_id: info.id } }
        : null;

    return {
        info,
        language,
        languageNote,
        meaning: info ? info.meaning : '',
        trueName,
        culture,
        review,
    };
}

// Update `story` in place from `next`, field by field, keeping a field's
// old value when its content is unchanged. Most pushes change nothing, and
// a kept `lexicon`/`names` array keeps every derived mentions list (and
// the renderer's compiled regex, cached by array) the same, so the scene
// isn't re-rendered for nothing.
function mergeStory(story, next) {
    for (const key of Object.keys(story)) {
        if (!(key in next)) delete story[key];
    }
    for (const [key, value] of Object.entries(next)) {
        if (key in story && JSON.stringify(story[key]) === JSON.stringify(value)) continue;
        story[key] = value;
    }
}

// Fold one `cultures`/`system` websocket message into `state` (mutated in
// place). Returns a message to send back (e.g. a `get_story` request), or
// null when there's nothing to send.
export function applyCulturesMessage(state, data) {
    if (!data) return null;

    if (data.type === 'system' && data.id === 'scene.loading') {
        const empty = emptyStoryState();
        state.counts = empty.counts;
        state.story = empty.story;
        state.pendingReview = empty.pendingReview;
        return null;
    }

    if (data.type === 'system' && data.id === 'scene.loaded') {
        return { type: 'cultures', action: 'get_story' };
    }

    if (data.type === 'cultures' && data.action === 'counts') {
        state.counts = data.data || {};
        return null;
    }

    if (data.type === 'cultures' && data.action === 'world') {
        state.counts = data.data?.counts || {};
        return null;
    }

    if (data.type === 'cultures' && data.action === 'story') {
        mergeStory(state.story, { ...emptyStoryState().story, ...data.data });
        return null;
    }

    return null;
}

// Resolve a review `target` (one of the `{type, ...}` shapes carried by a
// `NameLanguageSection`/`ForeignWordCard` button, or a lexicon entry's
// own `target`) against the Cultures tab's own `world` payload, into
// where `WorldStateManagerCultures` should navigate — or `null` when the
// thing it points at is gone (deleted since the target was captured, or
// an unrecognised shape).
//
// `focus` fields are camelCase (the Cultures UI's own convention), even
// though the target's own fields (and `world`'s) are snake_case.
export function resolveReviewTarget(world, target) {
    if (!world || !target) return null;

    if (target.type === 'glossary') {
        const entry = (world.glossary || []).find((e) => e.id === target.entry_id);
        if (!entry) return null;
        if (entry.language === null) {
            return { type: 'unassigned', focus: { glossaryId: entry.id } };
        }
        const cultureExists = (world.cultures || []).some((c) => c.id === entry.language);
        if (!cultureExists) return null;
        return {
            type: 'culture',
            id: entry.language,
            focus: { subTab: 'glossary', glossaryId: entry.id },
        };
    }

    if (target.type === 'phrase') {
        const culture = (world.cultures || []).find((c) => c.id === target.culture_id);
        if (!culture) return null;
        const phrase = (culture.language?.phrases || []).find((p) => p.id === target.phrase_id);
        if (!phrase) return null;
        return {
            type: 'culture',
            id: culture.id,
            focus: { subTab: 'phrases', phraseId: phrase.id },
        };
    }

    if (target.type === 'place') {
        const place = (world.places || []).find((p) => p.id === target.place_id);
        if (!place) return null;
        return { type: 'places', focus: { placeId: place.id } };
    }

    if (target.type === 'people') {
        const key = nameKey(target.character_name);
        const character = (world.characters || []).find((c) => nameKey(c.name) === key);
        if (!character) return null;
        return { type: 'people', focus: { characterName: character.name } };
    }

    return null;
}

// Build a character's/place's "no culture yet" chip (rules 3-5 of
// `characterChip`, shared by `placeChip` for its own no-mix fallback):
// the glossary `NameInfo`'s own culture when it has one, else "No
// language" when `info` exists but carries none, else `null` (no chip at
// all).
function infoOnlyChip(info) {
    if (info && info.culture_name) {
        return { label: info.culture_name, color: info.color };
    }
    if (info && !info.language_name) {
        return { label: 'No language', color: 'grey' };
    }
    return null;
}

// Build the `CultureChip`'s model for a scene character: what the
// character's own culture assignment (`CharacterInfo`) says, falling
// back to what's known about its *name*'s culture (`NameInfo`) when the
// character has none of its own. `null` when there's nothing to show.
export function characterChip(story, name) {
    if (!story || !name) return null;

    const index = buildNameIndex(story.names);
    const info = index.get(nameKey(name)) ?? null;
    const character = findCharacterInfoAny(story.characters, name);

    let base = null;
    if (character && character.culture_id) {
        base = { label: character.culture_name, color: character.color };
    } else if (character && character.set_by === 'owner') {
        base = { label: 'No culture', color: 'grey' };
    } else {
        base = infoOnlyChip(info);
    }
    if (!base) return null;

    const unreviewed = Boolean(
        (info && info.status === 'unreviewed')
        || (character && character.set_by === 'ai' && character.unsure),
    );

    let target = null;
    if (info && info.status === 'unreviewed') {
        target = { type: 'glossary', entry_id: info.id };
    } else if (character && character.set_by === 'ai' && character.unsure) {
        target = { type: 'people', character_name: character.name };
    }

    return { ...base, unreviewed, target };
}

// Build the `CultureChip`'s model for a place: its effective culture mix
// (one name, or "{top} +{n-1}" in the top culture's colour) when it has
// one, falling back to the same rules `characterChip` uses when a
// character has no culture of its own. `null` when there's nothing to
// show.
export function placeChip(story, name) {
    if (!story || !name) return null;

    const index = buildNameIndex(story.names);
    const info = index.get(nameKey(name)) ?? null;
    const place = findPlaceInfo(story.places, name);
    const mix = place && Array.isArray(place.mix) ? place.mix : [];

    let base = null;
    if (mix.length === 1) {
        base = { label: mix[0].culture_name, color: mix[0].color };
    } else if (mix.length > 1) {
        base = { label: `${mix[0].culture_name} +${mix.length - 1}`, color: mix[0].color };
    } else {
        base = infoOnlyChip(info);
    }
    if (!base) return null;

    const unreviewed = Boolean((place && place.unsure) || (info && info.status === 'unreviewed'));
    // The glossary entry is the target only when *it* is unreviewed
    // (mirroring `characterChip`) — an unsure *place* with an already
    // reviewed name still targets the place, not a reviewed entry with
    // nothing left to review.
    const target = (info && info.status === 'unreviewed')
        ? { type: 'glossary', entry_id: info.id }
        : (place ? { type: 'place', place_id: place.id } : null);

    return { ...base, unreviewed, target };
}
