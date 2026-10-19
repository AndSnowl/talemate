// Remaps raw, stored colour values (character colours, litegraph node/group
// colours, agent/chat message colours) onto the current theme's accent
// palette at render time. Never writes back to the stored value — see
// Global Constraints ("remapped at render time only").

import * as vuetifyColors from 'vuetify/util/colors';
import { isHex, normalizeHex, mix, hueOf, saturationOf, lightnessOf } from './colorMath.js';
import { ACCENT_KEYS } from './palette.js';
import { currentTheme } from './store.js';

// Multi-word Vuetify colour family names (kebab-case -> camelCase). Every
// other family name is already a plain lower-case word (red, orange, teal,
// ...) so no translation is needed for those.
const FAMILY_ALIASES = {
    'deep-purple': 'deepPurple',
    'light-blue': 'lightBlue',
    'deep-orange': 'deepOrange',
    'light-green': 'lightGreen',
    'blue-grey': 'blueGrey',
};

const TWO_WORD_FAMILY_RE = /^(deep-purple|light-blue|deep-orange|light-green|blue-grey)(?:-(.+))?$/;

/**
 * Resolves `#rgb`/`#rrggbb` (any case) and Vuetify colour names (`red`,
 * `deep-purple-lighten-3`, ...) to a normalised `#rrggbb` hex string.
 * Returns null for anything else (including empty/non-string input).
 */
export function toHex(value) {
    if (typeof value !== 'string' || value === '') return null;

    const direct = normalizeHex(value);
    if (direct) return direct;

    const name = value.trim().toLowerCase();

    let familyKey;
    let shadeName;

    const twoWord = name.match(TWO_WORD_FAMILY_RE);
    if (twoWord) {
        familyKey = FAMILY_ALIASES[twoWord[1]];
        shadeName = twoWord[2];
    } else {
        const dash = name.indexOf('-');
        familyKey = dash === -1 ? name : name.slice(0, dash);
        shadeName = dash === -1 ? undefined : name.slice(dash + 1);
    }

    const family = vuetifyColors[familyKey];
    if (!family) return null;

    const shadeKey = shadeName ? shadeName.replace(/-/g, '') : 'base';
    const hex = family[shadeKey];
    return hex ? normalizeHex(hex) : null;
}

function circularHueDistance(a, b) {
    const diff = Math.abs(a - b) % 360;
    return diff > 180 ? 360 - diff : diff;
}

/**
 * The accent key (see palette.js's ACCENT_KEYS) whose hue in `palette` is
 * circularly nearest to `hex`'s hue. Returns null when `hex` isn't a hex
 * colour, or its saturation is below 0.2 (too close to grey to carry a
 * meaningful hue).
 */
export function nearestAccent(hex, palette) {
    if (!isHex(hex)) return null;
    if (saturationOf(hex) < 0.2) return null;

    const hue = hueOf(hex);
    let best = null;
    let bestDistance = Infinity;
    for (const key of ACCENT_KEYS) {
        const distance = circularHueDistance(hue, hueOf(palette[key]));
        if (distance < bestDistance) {
            bestDistance = distance;
            best = key;
        }
    }
    return best;
}

// FNV-1a 32-bit over the UTF-16 code units of `str`, unsigned.
function fnv1aHash(str) {
    let hash = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
        hash ^= str.charCodeAt(i);
        hash = Math.imul(hash, 0x01000193);
    }
    return hash >>> 0;
}

/**
 * The accent key (see palette.js's ACCENT_KEYS) a character should be
 * coloured with. Prefers the stored colour's nearest accent (under
 * `resolved`'s palette); falls back to a stable hash of `name` when the
 * stored colour is missing/unsaturated (e.g. the backend's default
 * `"#fff"`).
 */
export function characterPaletteKey(stored, name, resolved = currentTheme.value) {
    const hex = toHex(stored);
    const accent = hex ? nearestAccent(hex, resolved.palette) : null;
    if (accent) return accent;
    return ACCENT_KEYS[fnv1aHash(name) % 7];
}

/**
 * The colour a character's name and message border are drawn in: the
 * `you` role for the player character, else the accent picked by
 * characterPaletteKey.
 */
export function characterColor(stored, name, isPlayer = false, resolved = currentTheme.value) {
    if (isPlayer) return resolved.colors.you;
    return resolved.palette[characterPaletteKey(stored, name, resolved)];
}

/** Whether `name` is the player character in a scene status payload (`scene.data.characters[].is_player`). */
export function isPlayerCharacter(scene, name) {
    const characters = scene?.data?.characters;
    if (!name || !Array.isArray(characters)) return false;
    return characters.some((c) => c?.name === name && c.is_player === true);
}

/**
 * Remaps a raw data colour (hex or Vuetify colour name) onto the current
 * theme: a saturated value becomes its nearest accent's hex; an
 * unsaturated one becomes `colors.muted`, or `colors['on-surface']` when
 * it's very light. Empty/unresolvable input gives null.
 */
export function dataColor(value, resolved = currentTheme.value) {
    const hex = toHex(value);
    if (!hex) return null;

    const accent = nearestAccent(hex, resolved.palette);
    if (accent) return resolved.palette[accent];

    return lightnessOf(hex) > 0.85 ? resolved.colors['on-surface'] : resolved.colors.muted;
}

/**
 * The litegraph title/body colours for a stored node colour, remapped onto
 * the current theme. Saturated values are mixed from their nearest
 * accent's hex toward `palette.bg`; unsaturated/unresolvable ones fall
 * back to the neutral `base2`/`base1` pair.
 */
export function nodeColors(value, resolved = currentTheme.value) {
    const palette = resolved.palette;
    const hex = toHex(value);
    const accent = hex ? nearestAccent(hex, palette) : null;

    if (!accent) {
        return { title: palette.base2, body: palette.base1 };
    }

    const accentHex = palette[accent];
    return {
        // 0.7 (not less): keeps the title text (`on-surface`) at 4.5:1 on
        // every accent's title bar — see checks' node_editor_text_contrast.
        title: mix(accentHex, palette.bg, 0.7),
        body: mix(accentHex, palette.bg, 0.8),
    };
}

/**
 * LiteGraph's own global colours (`LiteGraph.*` constants, keyed by their
 * LiteGraph names) for `resolved`: node text, default (unstyled) node
 * colours, widgets and links. Text uses `on-surface`/`muted`, which reach
 * 4.5:1 on every nodeColors() title/body and on the widget background
 * (see checks' node_editor_text_contrast).
 */
export function nodeEditorColors(resolved = currentTheme.value) {
    const colors = resolved.colors;
    const neutral = nodeColors(null, resolved);
    return {
        NODE_TITLE_COLOR: colors['on-surface'],
        NODE_SELECTED_TITLE_COLOR: colors['on-surface'],
        NODE_TEXT_COLOR: colors['on-surface'],
        NODE_DEFAULT_COLOR: neutral.title,
        NODE_DEFAULT_BGCOLOR: neutral.body,
        NODE_DEFAULT_BOXCOLOR: colors.strong,
        NODE_BOX_OUTLINE_COLOR: colors['on-surface'],
        WIDGET_BGCOLOR: resolved.palette['bg-alt'],
        WIDGET_OUTLINE_COLOR: colors.border,
        WIDGET_TEXT_COLOR: colors['on-surface'],
        WIDGET_SECONDARY_TEXT_COLOR: colors.muted,
        LINK_COLOR: colors.muted,
        EVENT_LINK_COLOR: colors.accent,
        CONNECTING_LINK_COLOR: colors.success,
    };
}
