// Node-only checks for the pure theme engine (src/theme/). No Vue, no test
// framework — run directly with `node checks/theme.check.mjs` (see
// tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

import { isHex, normalizeHex, mix, contrastRatio } from '../src/theme/colorMath.js';
import { PALETTE_KEYS, ACCENT_KEYS } from '../src/theme/palette.js';
import { ALL_ROLES, TEXT_ROLES } from '../src/theme/roles.js';
import { BUILTIN_PRESETS, getPreset, DEFAULT_PRESET_ID } from '../src/theme/presets.js';
import { resolveTheme, toVuetifyColors, themeFromConfig } from '../src/theme/engine.js';
import { toHex, characterPaletteKey, dataColor, nodeColors } from '../src/theme/dataColors.js';
import { getMessageColor } from '../src/utils/messageColors.js';
import { LGraph, LGraphGroup } from 'litegraph.js';
import { convertGraphToJSON } from '../src/utils/exportGraph.js';
// Importing this for its side effects (rebuildThemeNodeColors() at module
// load, and the LGraphCanvas.prototype.drawGroups override) proves the
// litegraph utilities module itself is importable outside Vite (no `@/`
// aliases left unresolved) — see Task 4 fix round 1, finding 1.
import '../src/utils/litegraphUtils.js';

let passed = 0;
const failures = [];

function check(name, fn) {
    try {
        fn();
        passed += 1;
    } catch (err) {
        failures.push({ name, err });
    }
}

check('mix_endpoints', () => {
    assert.equal(mix('#000000', '#ffffff', 0), '#000000');
    assert.equal(mix('#000000', '#ffffff', 1), '#ffffff');
    assert.equal(mix('#000000', '#ffffff', 0.5), '#808080');
});

check('contrast_black_white', () => {
    assert.equal(Math.round(contrastRatio('#000000', '#ffffff')), 21);
});

check('normalize_hex', () => {
    assert.equal(normalizeHex('#FFF'), '#ffffff');
    assert.equal(normalizeHex('#12345'), null);
    assert.equal(normalizeHex('red'), null);
});

check('presets_complete', () => {
    const expectedIds = [
        'gruvbox-dark', 'gruvbox-light', 'nord', 'solarized-dark', 'solarized-light',
        'monokai', 'cb-red-green', 'cb-blue-yellow', 'cb-high-contrast',
    ];
    assert.deepEqual(BUILTIN_PRESETS.map((p) => p.id), expectedIds);
    for (const preset of BUILTIN_PRESETS) {
        for (const key of PALETTE_KEYS) {
            const value = preset.palette[key];
            assert.ok(isHex(value), `${preset.id}.palette.${key} = ${value} is not a hex value`);
        }
    }
});

check('gruvbox_dark_core', () => {
    const colors = resolveTheme(getPreset('gruvbox-dark')).colors;
    assert.equal(colors.accent, '#fe8019');
    assert.equal(colors.link, '#fabd2f');
    assert.equal(colors.scene, '#8ec07c');
    assert.equal(colors.surface, '#282828');
    assert.equal(colors.background, '#1d2021');
});

check('roles_resolve_every_role', () => {
    for (const preset of BUILTIN_PRESETS) {
        const colors = resolveTheme(preset).colors;
        for (const role of Object.keys(ALL_ROLES)) {
            assert.ok(isHex(colors[role]), `${preset.id}.colors.${role} = ${colors[role]} is not a hex value`);
        }
    }
});

check('vision_preset_remaps', () => {
    const roleRefs = resolveTheme(getPreset('cb-red-green')).roleRefs;
    assert.equal(roleRefs.success, 'blue');
    assert.equal(roleRefs.scene, 'blue');
});

check('override_palette_and_role', () => {
    const p = getPreset(DEFAULT_PRESET_ID);
    const overridden = resolveTheme(p, { palette: { orange: '#112233' }, roles: {} });
    assert.equal(overridden.colors.accent, '#112233');
    const roleOverridden = resolveTheme(p, { palette: {}, roles: { accent: 'blue' } });
    assert.equal(roleOverridden.colors.accent, p.palette.blue);
});

check('contrast_text_roles', () => {
    for (const preset of BUILTIN_PRESETS) {
        const resolved = resolveTheme(preset);
        const surfaces = ['bg', 'bg-alt', 'base1'];
        for (const role of TEXT_ROLES) {
            const textHex = resolved.colors[role];
            for (const surfaceKey of surfaces) {
                const surfaceHex = resolved.palette[surfaceKey];
                const ratio = contrastRatio(textHex, surfaceHex);
                assert.ok(
                    ratio >= 4.5,
                    `${preset.id}: role ${role} (${textHex}) against ${surfaceKey} (${surfaceHex}) is ${ratio.toFixed(2)}, below 4.5`,
                );
            }
        }
    }
});

check('vuetify_colors_include_palette', () => {
    const r = resolveTheme(getPreset(DEFAULT_PRESET_ID));
    const vuetifyColors = toVuetifyColors(r);
    assert.equal(vuetifyColors['pal-teal'], r.palette.teal);
});

check('config_none_is_default', () => {
    assert.equal(themeFromConfig(undefined).id, 'gruvbox-dark');
});

check('config_unknown_active_falls_back', () => {
    assert.equal(themeFromConfig({ active: 'custom-gone', custom: [] }).id, 'gruvbox-dark');
});

check('config_custom_fills_missing_from_base', () => {
    const resolved = themeFromConfig({
        active: 'custom-1',
        custom: [{
            id: 'custom-1',
            name: 'Mine',
            base: 'nord',
            dark: true,
            palette: { orange: '#aa5500' },
            roles: {},
        }],
    });
    assert.equal(resolved.palette.orange, '#aa5500');
    assert.equal(resolved.palette.bg, getPreset('nord').palette.bg);
    assert.equal(resolved.name, 'Mine');
});

check('to_hex_forms', () => {
    assert.equal(toHex('#FFF'), '#ffffff');
    assert.equal(toHex('deep-purple-lighten-3'), '#b39ddb');
    assert.equal(toHex('nonsense'), null);
});

check('character_key_white_uses_name_hash', () => {
    const fromWhite = characterPaletteKey('#fff', 'Marta');
    assert.ok(ACCENT_KEYS.includes(fromWhite), `${fromWhite} is not an accent key`);
    assert.equal(characterPaletteKey(null, 'Marta'), fromWhite);
    assert.equal(characterPaletteKey('#FFFFFF', 'Marta'), fromWhite);
});

check('character_key_stable', () => {
    assert.equal(
        characterPaletteKey('nonsense', 'Ilsa Varn'),
        characterPaletteKey('nonsense', 'Ilsa Varn'),
    );
});

check('character_key_from_vuetify_name', () => {
    const gruvboxDark = resolveTheme(getPreset('gruvbox-dark'));
    assert.equal(characterPaletteKey('red-lighten-3', 'x', gruvboxDark), 'red');
});

check('data_color_grey_is_muted', () => {
    const r = resolveTheme(getPreset(DEFAULT_PRESET_ID));
    assert.equal(dataColor('#9e9e9e', r), r.colors.muted);
});

check('node_colors_follow_theme', () => {
    const gruvboxDark = resolveTheme(getPreset('gruvbox-dark'));
    const nord = resolveTheme(getPreset('nord'));
    const nordColors = nodeColors('#572e44', nord);
    const gruvboxColors = nodeColors('#572e44', gruvboxDark);
    assert.notDeepEqual(nordColors, gruvboxColors);
    assert.ok(isHex(nordColors.title) && isHex(nordColors.body));
    assert.ok(isHex(gruvboxColors.title) && isHex(gruvboxColors.body));
});

// Pins the name-hash fallback to a concrete value (not just "stable across
// two calls") so a change to the hash or to ACCENT_KEYS's order is caught.
check('character_key_hash_is_pinned', () => {
    assert.equal(characterPaletteKey(null, 'Marta'), 'magenta');
});

// A single-word Vuetify family name with a shade suffix (as opposed to the
// two-word `deep-purple-lighten-3` case already covered above).
check('to_hex_single_word_family_with_shade', () => {
    assert.equal(toHex('red-lighten-3'), '#ef9a9a');
});

// Fix round 1, finding 1/2: a group's `.color` must be the single source
// of truth for its raw/exported colour. LiteGraph's own "Change Color"
// menu (node_modules/litegraph.js/build/litegraph.js's
// LGraphCanvas.onMenuNodeColors) and "Create Group from Selection"
// (recentNodes.js/groupInteractions.js) both just assign `group.color`
// directly (or `delete` it for "No color") — never anything else — so if
// litegraphUtils.js's theme remap ever stashes the raw value somewhere
// other than `.color` itself (as a prior version of this fix did, in a
// `rawColor` field), a colour picked after the group was created/loaded
// would silently fail to round-trip through export.
check('group_color_is_raw_single_source_of_truth', () => {
    const graph = new LGraph();
    const group = new LGraphGroup();
    group.pos = [0, 0];
    group.size = [200, 100];
    graph.add(group);

    // Simulates picking a colour from LiteGraph's "Change Color" menu
    // after the group already exists.
    group.color = '#ff00ff';
    let exported = convertGraphToJSON(graph);
    assert.equal(exported.groups[0].color, '#ff00ff');

    // Simulates "No color" (LGraphCanvas.onMenuNodeColors's
    // `delete node.color`).
    delete group.color;
    exported = convertGraphToJSON(graph);
    assert.ok(
        !exported.groups[0].color,
        `expected no stored colour after "No color", got ${exported.groups[0].color}`,
    );
});

// Task 5: message colours fold into the theme — getMessageColor resolves
// against an explicit resolved theme (never the live `currentTheme`
// singleton here, so these checks don't depend on load order / applied
// theme state).
check('message_color_empty_uses_role', () => {
    const r = resolveTheme(getPreset('gruvbox-dark'));
    assert.equal(
        getMessageColor({ scene: { narrator_messages: {} } }, 'narrator', r),
        r.colors.narrator,
    );
});

check('message_color_legacy_default_is_unset', () => {
    const r = resolveTheme(getPreset('gruvbox-dark'));
    assert.equal(
        getMessageColor({ scene: { quotes: { color: '#FFFFFF' } } }, 'quotes', r),
        r.colors.quotes,
    );
});

check('message_color_palette_name', () => {
    const r = resolveTheme(getPreset('gruvbox-dark'));
    assert.equal(
        getMessageColor({ scene: { quotes: { color: 'teal' } } }, 'quotes', r),
        r.palette.teal,
    );
});

check('message_color_user_hex_kept', () => {
    const r = resolveTheme(getPreset('gruvbox-dark'));
    assert.equal(
        getMessageColor({ scene: { quotes: { color: '#123456' } } }, 'quotes', r),
        '#123456',
    );
});

if (failures.length > 0) {
    for (const { name, err } of failures) {
        console.error(`FAIL ${name}`);
        console.error(err && err.stack ? err.stack : err);
    }
    process.exit(1);
} else {
    console.log(`ok ${passed}`);
    process.exit(0);
}
