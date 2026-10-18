// Node-only checks for the pure theme engine (src/theme/). No Vue, no test
// framework — run directly with `node checks/theme.check.mjs` (see
// tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

import { isHex, normalizeHex, mix, contrastRatio } from '../src/theme/colorMath.js';
import { PALETTE_KEYS } from '../src/theme/palette.js';
import { ALL_ROLES, TEXT_ROLES } from '../src/theme/roles.js';
import { BUILTIN_PRESETS, getPreset, DEFAULT_PRESET_ID } from '../src/theme/presets.js';
import { resolveTheme, toVuetifyColors, themeFromConfig } from '../src/theme/engine.js';

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
