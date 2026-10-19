// Resolves a preset (plus optional overrides) into concrete colours, and
// builds a Vuetify-ready colour map from the result. Also reads the
// `appearance.theme` config shape into a resolved theme.

import { isHex, normalizeHex, darken, lighten, mix } from './colorMath.js';
import { PALETTE_KEYS } from './palette.js';
import { ALL_ROLES, ROLE_ALIASES } from './roles.js';
import { getPreset, DEFAULT_PRESET_ID } from './presets.js';

/** Resolve a role ref (a palette key, or a derived `{pal, darken, lighten, mix}`) to a hex colour. */
export function resolveRef(ref, palette) {
    if (typeof ref === 'string') {
        return palette[ref];
    }
    let hex = palette[ref.pal];
    if (ref.mix) {
        const withHex = palette[ref.mix.with] ?? ref.mix.with;
        hex = mix(hex, withHex, ref.mix.t);
    }
    if (typeof ref.darken === 'number') {
        hex = darken(hex, ref.darken);
    }
    if (typeof ref.lighten === 'number') {
        hex = lighten(hex, ref.lighten);
    }
    return hex;
}

function sanitizePaletteOverrides(overrides, knownKeys) {
    const out = {};
    for (const [key, value] of Object.entries(overrides || {})) {
        if (!knownKeys.includes(key)) continue;
        if (!isHex(value)) continue;
        out[key] = normalizeHex(value);
    }
    return out;
}

function isValidRef(ref, palette) {
    if (typeof ref === 'string') {
        return Object.prototype.hasOwnProperty.call(palette, ref);
    }
    if (ref && typeof ref === 'object' && typeof ref.pal === 'string') {
        return Object.prototype.hasOwnProperty.call(palette, ref.pal);
    }
    return false;
}

function sanitizeRoleOverrides(overrides, palette) {
    const out = {};
    for (const [role, ref] of Object.entries(overrides || {})) {
        if (!isValidRef(ref, palette)) continue;
        out[role] = ref;
    }
    return out;
}

/**
 * Resolve a preset into concrete colours. `overrides.palette` replaces
 * individual palette entries; `overrides.roles` replaces individual role
 * refs. Invalid overrides (unknown palette key, non-hex value, or a role
 * ref naming an unknown palette key) are ignored.
 */
export function resolveTheme(preset, overrides = { palette: {}, roles: {} }) {
    const paletteOverrides = sanitizePaletteOverrides(overrides.palette, PALETTE_KEYS);
    const palette = { ...preset.palette, ...paletteOverrides };

    const roleRefs = { ...ALL_ROLES, ...(preset.roles || {}) };
    const roleOverrides = sanitizeRoleOverrides(overrides.roles, palette);
    Object.assign(roleRefs, roleOverrides);

    for (const [alias, target] of Object.entries(ROLE_ALIASES)) {
        const setExplicitly =
            Object.prototype.hasOwnProperty.call(preset.roles || {}, alias)
            || Object.prototype.hasOwnProperty.call(roleOverrides, alias);
        if (!setExplicitly) {
            roleRefs[alias] = roleRefs[target];
        }
    }

    const colors = {};
    for (const [role, ref] of Object.entries(roleRefs)) {
        colors[role] = resolveRef(ref, palette);
    }

    return {
        id: preset.id,
        name: preset.name,
        dark: preset.dark,
        palette,
        roleRefs,
        colors,
    };
}

/** Every role's resolved colour, plus `pal-<key>` for every palette entry — ready for a Vuetify theme's `colors` map. */
export function toVuetifyColors(resolved) {
    const out = {};
    for (const [role, hex] of Object.entries(resolved.colors)) {
        out[role] = hex;
    }
    for (const [key, hex] of Object.entries(resolved.palette)) {
        out[`pal-${key}`] = hex;
    }
    return out;
}

// Vuetify's default opacities per light/dark (node_modules/vuetify/lib/
// composables/theme.js's genDefaults), pinned here so a theme swap can
// replace `theme.variables` wholesale. checks/theme.check.mjs compares
// these against Vuetify's own defaults.
const VUETIFY_OPACITIES = {
    light: {
        'border-opacity': 0.12,
        'high-emphasis-opacity': 0.87,
        'medium-emphasis-opacity': 0.60,
        'disabled-opacity': 0.38,
        'idle-opacity': 0.04,
        'hover-opacity': 0.04,
        'focus-opacity': 0.12,
        'selected-opacity': 0.08,
        'activated-opacity': 0.12,
        'pressed-opacity': 0.12,
        'dragged-opacity': 0.08,
    },
    dark: {
        'border-opacity': 0.12,
        'high-emphasis-opacity': 1,
        'medium-emphasis-opacity': 0.70,
        'disabled-opacity': 0.50,
        'idle-opacity': 0.10,
        'hover-opacity': 0.04,
        'focus-opacity': 0.12,
        'selected-opacity': 0.08,
        'activated-opacity': 0.12,
        'pressed-opacity': 0.16,
        'dragged-opacity': 0.08,
    },
};

/**
 * The Vuetify theme `variables` map for `resolved`: Vuetify's own
 * light/dark opacities, plus border, inline-code and kbd colours drawn
 * from the theme (borders/dividers use the text colour at
 * `border-opacity`, as Vuetify's own defaults do with black/white).
 */
export function toVuetifyVariables(resolved) {
    const colors = resolved.colors;
    return {
        'border-color': colors['on-surface'],
        ...(resolved.dark ? VUETIFY_OPACITIES.dark : VUETIFY_OPACITIES.light),
        'theme-kbd': colors['surface-variant'],
        'theme-on-kbd': colors['on-surface'],
        'theme-code': colors.raised,
        'theme-on-code': colors['on-surface'],
    };
}

/**
 * Resolve the config's `appearance.theme` setting ({active, custom: [...]})
 * into a theme. Falls back to the default preset when `active` names
 * neither a custom theme nor a built-in preset.
 */
export function themeFromConfig(themeSettings) {
    const activeId = themeSettings?.active;
    const custom = themeSettings?.custom || [];

    if (activeId) {
        const customEntry = custom.find((c) => c.id === activeId);
        if (customEntry) {
            const basePreset = getPreset(customEntry.base) || getPreset(DEFAULT_PRESET_ID);
            const resolved = resolveTheme(basePreset, {
                palette: customEntry.palette || {},
                roles: customEntry.roles || {},
            });
            return {
                ...resolved,
                id: customEntry.id,
                name: customEntry.name,
                dark: customEntry.dark,
            };
        }

        const preset = getPreset(activeId);
        if (preset) {
            return resolveTheme(preset);
        }
    }

    return resolveTheme(getPreset(DEFAULT_PRESET_ID));
}
