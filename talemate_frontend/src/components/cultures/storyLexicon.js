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

// Turn the scene's foreign-word lexicon (Task 1-3's `story.lexicon`) into
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

// Index `story.names` (Task 3's `NameInfo[]`) by every text a story
// mention might carry: the name's own text, each culture rendering's
// text, and the character name it belongs to (when any). The first entry
// to claim a key wins.
export function buildNameIndex(names) {
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
        state.story = { ...emptyStoryState().story, ...data.data };
        return null;
    }

    return null;
}
