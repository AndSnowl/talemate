// Export/import of a custom theme as a standalone JSON file (the
// "fantasymate-theme" file format — see Global Constraints and
// task-9-brief.md).
//
// `exportTheme` takes a CustomTheme-shaped object (the backend's
// `CustomTheme` schema: {id, name, base, dark, palette, roles} — see
// src/talemate/config/schema.py) and produces the file's JSON contents.
// `parseThemeFile` is the inverse: given a file's text, it validates and
// returns a CustomTheme-without-id, ready for the caller to assign a fresh
// `id` (import) before pushing it onto `appearance.theme.custom`.

import { isHex, normalizeHex } from './colorMath.js';
import { PALETTE_KEYS } from './palette.js';
import { ALL_ROLES } from './roles.js';
import { getPreset } from './presets.js';

export const THEME_FILE_FORMAT = 'fantasymate-theme';
export const THEME_FILE_VERSION = 1;

/** Build a `fantasymate-theme` file's JSON contents from a CustomTheme-shaped object (its `id` is dropped). */
export function exportTheme(customTheme) {
    return {
        format: THEME_FILE_FORMAT,
        version: THEME_FILE_VERSION,
        name: customTheme.name,
        dark: customTheme.dark,
        base: customTheme.base,
        palette: { ...(customTheme.palette || {}) },
        roles: { ...(customTheme.roles || {}) },
    };
}

/**
 * Parse and validate a `fantasymate-theme` file's text.
 *
 * On success, `theme` is a CustomTheme-without-id: `{name, base, dark,
 * palette, roles}`, with `palette` and `roles` left sparse exactly as the
 * file had them (resolving them against `base` is `resolveTheme`'s job —
 * see engine.js — not this function's).
 *
 * Validation, in order:
 *  - the text must be valid JSON;
 *  - `format` must be `'fantasymate-theme'`;
 *  - `name` must be a non-empty string;
 *  - `base` must name a known built-in preset;
 *  - every `palette` key must be one of PALETTE_KEYS, with a value that is
 *    (after `normalizeHex`) a valid hex colour;
 *  - every `roles` entry whose role id isn't one of the engine's roles
 *    (ALL_ROLES) is ignored silently; the rest must target a PALETTE_KEYS
 *    entry.
 */
export function parseThemeFile(text) {
    let data;
    try {
        data = JSON.parse(text);
    } catch (err) {
        return { ok: false, error: `Not valid JSON: ${err.message}` };
    }

    if (!data || typeof data !== 'object' || Array.isArray(data)) {
        return { ok: false, error: 'Not valid JSON: expected an object' };
    }

    if (data.format !== THEME_FILE_FORMAT) {
        return { ok: false, error: `Unknown theme file format: ${JSON.stringify(data.format)}` };
    }

    if (!data.name || typeof data.name !== 'string') {
        return { ok: false, error: 'Missing theme name' };
    }

    const base = data.base;
    const basePreset = typeof base === 'string' ? getPreset(base) : undefined;
    if (!basePreset) {
        return { ok: false, error: `Unknown base preset: ${JSON.stringify(base)}` };
    }

    const palette = {};
    for (const [key, value] of Object.entries(data.palette || {})) {
        if (!PALETTE_KEYS.includes(key)) {
            return { ok: false, error: `Unknown palette key: ${key}` };
        }
        const normalized = normalizeHex(value);
        if (!normalized || !isHex(normalized)) {
            return { ok: false, error: `Invalid colour for ${key}: ${value}` };
        }
        palette[key] = normalized;
    }

    const roles = {};
    for (const [roleId, target] of Object.entries(data.roles || {})) {
        if (!Object.prototype.hasOwnProperty.call(ALL_ROLES, roleId)) {
            // Unknown role id — ignore silently.
            continue;
        }
        if (!PALETTE_KEYS.includes(target)) {
            return { ok: false, error: `Unknown palette key for role ${roleId}: ${target}` };
        }
        roles[roleId] = target;
    }

    const dark = typeof data.dark === 'boolean' ? data.dark : basePreset.dark;

    return {
        ok: true,
        theme: { name: data.name, dark, base, palette, roles },
    };
}
