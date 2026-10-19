// Node-only checks for the pure theme engine (src/theme/). No Vue, no test
// framework — run directly with `node checks/theme.check.mjs` (see
// tests/dev/test_frontend_checks.py for the pytest wrapper).

import assert from 'node:assert/strict';

import { isHex, normalizeHex, mix, contrastRatio } from '../src/theme/colorMath.js';
import { PALETTE_KEYS, ACCENT_KEYS } from '../src/theme/palette.js';
import { ALL_ROLES, TEXT_ROLES } from '../src/theme/roles.js';
import { BUILTIN_PRESETS, getPreset, DEFAULT_PRESET_ID } from '../src/theme/presets.js';
import { resolveTheme, toVuetifyColors, toVuetifyVariables, themeFromConfig } from '../src/theme/engine.js';
import { createTheme } from 'vuetify/lib/composables/theme.js';
import { exportTheme, parseThemeFile } from '../src/theme/themeFile.js';
import { toHex, characterPaletteKey, dataColor, nodeColors, nodeEditorColors } from '../src/theme/dataColors.js';
import { getMessageColor } from '../src/utils/messageColors.js';
import { SceneTextParser } from '../src/utils/sceneMessageRenderer.js';
import { LGraph, LGraphGroup, LGraphNode, LiteGraph, LGraphCanvas } from 'litegraph.js';
import { convertGraphToJSON } from '../src/utils/exportGraph.js';
import { themeExtensions } from '../src/theme/codemirrorTheme.js';
import { EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
// Importing this for its side effects (rebuildThemeNodeColors() at module
// load, and the LGraphCanvas.prototype.drawGroups override) proves the
// litegraph utilities module itself is importable outside Vite (no `@/`
// aliases left unresolved) — see Task 4 fix round 1, finding 1.
import { rebuildThemeNodeColors, reapplyNodeColors, applyThemeToCanvas } from '../src/utils/litegraphUtils.js';

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

// Final fix 1: Vuetify merges its own default theme (error, info,
// surface-bright, ...) into a theme only once, at createVuetify time, so
// applyTheme's wholesale `theme.colors = toVuetifyColors(...)` must itself
// carry every key Vuetify's defaults define — and the same for
// `theme.variables` (border-color, theme-code, ...).
const vuetifyDefaults = createTheme().themes.value;

check('vuetify_colors_cover_vuetify_defaults', () => {
    const expected = new Set([
        ...Object.keys(vuetifyDefaults.dark.colors),
        ...Object.keys(vuetifyDefaults.light.colors),
    ]);
    assert.ok(expected.has('error') && expected.has('surface-bright'));
    for (const preset of BUILTIN_PRESETS) {
        const colors = toVuetifyColors(resolveTheme(preset));
        for (const key of expected) {
            assert.ok(isHex(colors[key]), `${preset.id}: Vuetify colour ${key} = ${colors[key]} is not a hex value`);
        }
    }
});

check('vuetify_variables_cover_vuetify_defaults', () => {
    const expected = new Set([
        ...Object.keys(vuetifyDefaults.dark.variables),
        ...Object.keys(vuetifyDefaults.light.variables),
    ]);
    for (const preset of BUILTIN_PRESETS) {
        const variables = toVuetifyVariables(resolveTheme(preset));
        for (const key of expected) {
            assert.ok(variables[key] !== undefined, `${preset.id}: Vuetify variable ${key} is missing`);
        }
    }
});

check('vuetify_variables_follow_theme', () => {
    for (const preset of BUILTIN_PRESETS) {
        const r = resolveTheme(preset);
        const v = toVuetifyVariables(r);
        // Borders/dividers are drawn from border-color at low opacity, so
        // it must be the theme's text colour (dark on light, light on dark).
        assert.ok(
            contrastRatio(v['border-color'], r.palette.bg) >= 4.5,
            `${preset.id}: border-color ${v['border-color']} does not stand out from bg ${r.palette.bg}`,
        );
        assert.ok(
            contrastRatio(v['theme-on-code'], v['theme-code']) >= 4.5,
            `${preset.id}: inline code text ${v['theme-on-code']} on ${v['theme-code']} is below 4.5`,
        );
        const defaults = (r.dark ? vuetifyDefaults.dark : vuetifyDefaults.light).variables;
        for (const [key, value] of Object.entries(defaults)) {
            if (key.endsWith('-opacity')) {
                assert.equal(v[key], value, `${preset.id}: ${key} should be Vuetify's ${r.dark ? 'dark' : 'light'} default`);
            }
        }
    }
});

check('vuetify_error_follows_danger', () => {
    const p = getPreset(DEFAULT_PRESET_ID);
    assert.equal(resolveTheme(p).colors.error, resolveTheme(p).colors.danger);
    const overridden = resolveTheme(p, { palette: {}, roles: { danger: 'magenta' } });
    assert.equal(overridden.colors.error, p.palette.magenta);
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

// Final fix 2: the node editor stays readable under every preset —
// LiteGraph's own global text/widget/default colours follow the theme, and
// its text reaches 4.5:1 on every node title bar and body.
check('node_editor_text_contrast', () => {
    for (const preset of BUILTIN_PRESETS) {
        const r = resolveTheme(preset);
        const c = nodeEditorColors(r);
        const values = [...ACCENT_KEYS.map((k) => r.palette[k]), null];
        for (const value of values) {
            const { title, body } = nodeColors(value, r);
            const label = value ?? 'neutral';
            for (const [what, text, bg] of [
                ['title text on title', c.NODE_TITLE_COLOR, title],
                ['node text on body', c.NODE_TEXT_COLOR, body],
            ]) {
                const ratio = contrastRatio(text, bg);
                assert.ok(ratio >= 4.5, `${preset.id} ${label}: ${what} (${text} on ${bg}) is ${ratio.toFixed(2)}`);
            }
        }
        for (const [what, text, bg] of [
            ['widget text', c.WIDGET_TEXT_COLOR, c.WIDGET_BGCOLOR],
            ['widget label', c.WIDGET_SECONDARY_TEXT_COLOR, c.WIDGET_BGCOLOR],
            ['default title', c.NODE_TITLE_COLOR, c.NODE_DEFAULT_COLOR],
            ['default body', c.NODE_TEXT_COLOR, c.NODE_DEFAULT_BGCOLOR],
        ]) {
            const ratio = contrastRatio(text, bg);
            assert.ok(ratio >= 4.5, `${preset.id}: ${what} (${text} on ${bg}) is ${ratio.toFixed(2)}`);
        }
    }
});

check('node_editor_litegraph_constants_follow_theme', () => {
    const light = resolveTheme(getPreset('gruvbox-light'));
    try {
        rebuildThemeNodeColors(light);
        const c = nodeEditorColors(light);
        for (const [key, value] of Object.entries(c)) {
            if (key === 'link_type_colors') continue;
            assert.equal(LiteGraph[key], value, `LiteGraph.${key}`);
        }
        assert.equal(LiteGraph.NODE_TEXT_COLOR, light.colors['on-surface']);
        assert.equal(LGraphCanvas.link_type_colors['-1'], c.EVENT_LINK_COLOR);

        const canvas = { setDirty() {} };
        applyThemeToCanvas(canvas, light);
        assert.equal(canvas.node_title_color, c.NODE_TITLE_COLOR);
        assert.equal(canvas.default_link_color, c.LINK_COLOR);
        assert.equal(canvas.clear_background_color, light.palette['bg-alt']);
    } finally {
        rebuildThemeNodeColors(resolveTheme(getPreset(DEFAULT_PRESET_ID)));
    }
});

check('unstyled_node_gets_neutral_colors_on_reapply', () => {
    const graph = new LGraph();
    const node = new LGraphNode('plain');
    graph.add(node);
    const light = resolveTheme(getPreset('gruvbox-light'));
    reapplyNodeColors(graph, light);
    const neutral = nodeColors(null, light);
    assert.equal(node.color, neutral.title);
    assert.equal(node.bgcolor, neutral.body);
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

// Fix round 1, finding 1/2: SceneTextParser (the single choke point every
// message component and AppConfigAppearanceScene.vue's preview renders
// through) must resolve a style's raw stored colour the same way
// getMessageColor does — not use it verbatim. Relies on the live
// currentTheme being gruvbox-dark (its default with no applied config —
// see theme/store.js), same preset asserted against here.
check('scene_text_parser_legacy_quotes_color_is_unset', () => {
    const r = resolveTheme(getPreset('gruvbox-dark'));
    const parser = new SceneTextParser({ quotes: { color: '#FFFFFF' } });
    const html = parser.parse('"hi"');
    assert.ok(
        html.includes(`color: ${r.colors.quotes};`),
        `expected quotes to render the quotes role colour (${r.colors.quotes}), got: ${html}`,
    );
});

check('scene_text_parser_palette_key_quotes_color', () => {
    const r = resolveTheme(getPreset('gruvbox-dark'));
    const parser = new SceneTextParser({ quotes: { color: 'teal' } });
    const html = parser.parse('"hi"');
    assert.ok(
        html.includes(`color: ${r.palette.teal};`),
        `expected quotes to render the palette teal colour (${r.palette.teal}), got: ${html}`,
    );
});

// Fix round 1 (Task 8B review): CodeMirror's editors must follow the active
// theme instead of a fixed `oneDark` — see codemirrorTheme.js. Builds the
// extensions for both a dark and a light preset and confirms each one
// actually threads CodeMirror's own `EditorView.darkTheme` facet through
// correctly (not just that `resolveTheme(...).dark` itself is right).
check('codemirror_theme_extensions_build_and_match_dark_flag', () => {
    const darkResolved = resolveTheme(getPreset('gruvbox-dark'));
    const lightResolved = resolveTheme(getPreset('gruvbox-light'));
    assert.equal(darkResolved.dark, true);
    assert.equal(lightResolved.dark, false);

    const darkState = EditorState.create({ extensions: themeExtensions(darkResolved) });
    const lightState = EditorState.create({ extensions: themeExtensions(lightResolved) });
    assert.equal(darkState.facet(EditorView.darkTheme), true);
    assert.equal(lightState.facet(EditorView.darkTheme), false);
});

// Task 9: themeFile.js's export/import round trip and validation. See
// task-9-brief.md Step 1.
check('export_parse_round_trip', () => {
    const t = {
        id: 'custom-x',
        name: 'Mine',
        base: 'nord',
        dark: true,
        palette: { ...getPreset('nord').palette, orange: '#aa5500' },
        roles: { accent: 'teal' },
    };
    const parsed = parseThemeFile(JSON.stringify(exportTheme(t)));
    assert.ok(parsed.ok, parsed.error);
    assert.deepEqual(parsed.theme.palette, t.palette);
    assert.deepEqual(parsed.theme.roles, t.roles);
});

check('parse_rejects_not_json', () => {
    const parsed = parseThemeFile('not json{');
    assert.equal(parsed.ok, false);
    assert.ok(parsed.error.includes('JSON'), parsed.error);
});

check('parse_rejects_wrong_format', () => {
    const parsed = parseThemeFile(JSON.stringify({ format: 'other' }));
    assert.equal(parsed.ok, false);
});

check('parse_rejects_bad_hex', () => {
    const parsed = parseThemeFile(JSON.stringify({
        format: 'fantasymate-theme',
        version: 1,
        name: 'Bad',
        base: 'gruvbox-dark',
        palette: { orange: 'tomato' },
    }));
    assert.equal(parsed.ok, false);
    assert.ok(parsed.error.includes('orange'), parsed.error);
});

check('parse_fills_missing_palette_from_base', () => {
    const parsed = parseThemeFile(JSON.stringify({
        format: 'fantasymate-theme',
        version: 1,
        name: 'Partial',
        base: 'nord',
        palette: { orange: '#aa5500' },
    }));
    assert.ok(parsed.ok, parsed.error);
    const resolved = themeFromConfig({
        active: 'custom-partial',
        custom: [{ id: 'custom-partial', ...parsed.theme }],
    });
    assert.equal(resolved.palette.bg, getPreset('nord').palette.bg);
    assert.equal(resolved.palette.orange, '#aa5500');
});

check('parse_rejects_unknown_role_target', () => {
    const parsed = parseThemeFile(JSON.stringify({
        format: 'fantasymate-theme',
        version: 1,
        name: 'BadRole',
        base: 'gruvbox-dark',
        roles: { accent: 'chartreuse' },
    }));
    assert.equal(parsed.ok, false);
});

check('parse_ignores_unknown_role_id', () => {
    const parsed = parseThemeFile(JSON.stringify({
        format: 'fantasymate-theme',
        version: 1,
        name: 'UnknownRoleId',
        base: 'gruvbox-dark',
        roles: { not_a_real_role: 'teal' },
    }));
    assert.ok(parsed.ok, parsed.error);
    assert.ok(!Object.prototype.hasOwnProperty.call(parsed.theme.roles, 'not_a_real_role'));
});

check('parse_rejects_missing_name', () => {
    const parsed = parseThemeFile(JSON.stringify({
        format: 'fantasymate-theme',
        version: 1,
        base: 'gruvbox-dark',
    }));
    assert.equal(parsed.ok, false);
});

check('parse_rejects_unknown_base', () => {
    const parsed = parseThemeFile(JSON.stringify({
        format: 'fantasymate-theme',
        version: 1,
        name: 'BadBase',
        base: 'not-a-preset',
    }));
    assert.equal(parsed.ok, false);
});

check('export_theme_shape', () => {
    const t = {
        id: 'custom-x',
        name: 'Mine',
        base: 'gruvbox-dark',
        dark: true,
        palette: { orange: '#aa5500' },
        roles: {},
    };
    const exported = exportTheme(t);
    assert.deepEqual(exported, {
        format: 'fantasymate-theme',
        version: 1,
        name: 'Mine',
        dark: true,
        base: 'gruvbox-dark',
        palette: { orange: '#aa5500' },
        roles: {},
    });
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
