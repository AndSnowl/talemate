// Node-only sweep guard: walks talemate_frontend/src/**/*.{vue,js} (excluding
// src/theme/, the pure theme engine itself) and fails on hard-coded colours
// Vuetify colour-scale names (`color="grey-darken-3"`, `bg-red`, `text-white`,
// ...) or raw hex/rgba() values that the theme system (src/theme/) should be
// providing instead, via a role (`rgb(var(--v-theme-<role>))`) or the
// palette. No Vue, no test framework — run directly with
// `node checks/themeColors.check.mjs` (see tests/dev/test_frontend_checks.py
// for the pytest wrapper).
//
// Two escape hatches, both opt-in and deliberately small:
//   - PENDING: files not yet swept. Tasks 7-8 delete entries as they clean
//     each file; Task 8 leaves this empty.
//   - ALLOW: permanent exceptions, one `path:line-substring` per ruling,
//     each with a one-line comment saying why.

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const SRC_DIR = path.resolve('src');
const THEME_DIR = path.join(SRC_DIR, 'theme');

// --- Matchers ---------------------------------------------------------

// A Vuetify colour-scale name in a `color=`/`bg-`/`text-` position (task
// brief's regex, used verbatim).
const VUETIFY_COLOR_RE = /(?:color="|bg-|text-)(?:grey|blue-grey|black|white|red|pink|purple|deep-purple|indigo|blue|light-blue|cyan|teal|green|light-green|lime|yellow|amber|orange|deep-orange|brown)(?:-(?:lighten|darken|accent)-\d)?\b/;

// Fix round 1: VUETIFY_COLOR_RE only catches a colour name sitting literally
// next to `color="`/`bg-`/`text-`, so it misses one reached through a
// binding or plain JS: `:color="active ? 'primary' : 'grey'"`,
// `:color="item.color || 'grey'"`, `color: 'grey'`, `:class="['bg-grey-darken-4']"`.
// Second rule (controller ruling): a quoted string literal that is *exactly*
// a Vuetify colour-scale name (same hue list, optional
// `-(lighten|darken|accent)-N`), or `bg-`/`text-` of one, fails when the
// same line also contains a colour context token (`color`, `Color`, `bg`,
// `class`, or `text-`) — so `status: 'green'` (no such token on the line)
// and a bare role name like `'primary'` (not in the hue list at all) don't
// false-positive.
const QUOTED_COLOR_LITERAL_RE = /(['"`])(?:bg-|text-)?(?:grey|blue-grey|black|white|red|pink|purple|deep-purple|indigo|blue|light-blue|cyan|teal|green|light-green|lime|yellow|amber|orange|deep-orange|brown)(?:-(?:lighten|darken|accent)-\d)?\1/;

function hasColorContextToken(line) {
    return line.includes('color') || line.includes('Color') || line.includes('bg')
        || line.includes('class') || line.includes('text-');
}

function lineHasQuotedColorLiteral(line) {
    return hasColorContextToken(line) && QUOTED_COLOR_LITERAL_RE.test(line);
}

// A raw hex colour, or an rgb()/rgba() call with a literal first argument
// (as opposed to `rgb(var(--v-theme-accent))`, whose argument starts with
// `v`, not a digit, and so never matches `\s*\d`).
const HEX_RE = /#[0-9a-fA-F]{3,8}\b/g;
const RGBA_LITERAL_RE = /rgba?\(\s*\d/;

// The key (CSS property, HTML/Vue attribute, or JS object property) that
// must precede a hex value, with optional `:`/`=` and quoting, for that hex
// to count as a colour rather than an anchor/id/comment/etc.
const COLOR_KEY_RE = /([A-Za-z_$][\w$-]*)\s*[:=]\s*["']?["']?$/;

function isColorKey(key) {
    const k = key.toLowerCase();
    return k.includes('color') || k.includes('colour') || k.includes('fill')
        || k.includes('stroke') || k === 'style' || k.includes('background');
}

// `href="#top"`-style anchors: a hex-looking fragment right after
// `href="`/`href='` is never a colour, whatever else is true of it.
function isHrefAnchor(before) {
    return /href\s*=\s*["']$/.test(before);
}

// Decides whether one `#xxx` match in `line` is a colour value: a CSS
// declaration value (inside a <style> block, with a `:` earlier on the
// line — as opposed to a bare `#id {` selector, which has no colon before
// it), a color/bg/fill/stroke/style/background attribute or property value,
// or a string literal that is exactly a hex colour (immediately bounded by
// matching quotes, not merely somewhere inside a longer quoted string).
export function hexIsColor(line, index, hex, inStyleBlock) {
    const before = line.slice(0, index);
    const after = line.slice(index + hex.length);

    if (isHrefAnchor(before)) return false;

    if (inStyleBlock && before.includes(':')) return true;

    const window = before.slice(-60);
    const keyMatch = COLOR_KEY_RE.exec(window);
    if (keyMatch && isColorKey(keyMatch[1])) return true;

    const prevChar = before.slice(-1);
    const nextChar = after.slice(0, 1);
    if ((prevChar === '"' && nextChar === '"')
        || (prevChar === "'" && nextChar === "'")
        || (prevChar === '`' && nextChar === '`')) {
        return true;
    }

    return false;
}

function lineHasRawColor(line, inStyleBlock) {
    if (RGBA_LITERAL_RE.test(line)) return true;
    HEX_RE.lastIndex = 0;
    let m;
    while ((m = HEX_RE.exec(line))) {
        if (hexIsColor(line, m.index, m[0], inStyleBlock)) return true;
    }
    return false;
}

export function lineFails(line, inStyleBlock = false) {
    if (VUETIFY_COLOR_RE.test(line)) return true;
    if (lineHasQuotedColorLiteral(line)) return true;
    return lineHasRawColor(line, inStyleBlock);
}

// --- PENDING / ALLOW ----------------------------------------------------

// Files that still contain hard-coded colours, not yet swept onto the theme
// system. Seeded by running this check once with an empty PENDING and
// listing the files that failed (Task 6, step 1). Sweep tasks (7-8) delete
// entries as they clean each file; Task 8 leaves this empty.
const PENDING = new Set([]);

// Permanent exceptions: `path:line-substring`. Each entry needs a one-line
// comment saying why it is never swept.
const ALLOW = new Set([
    // messageColors.js's LEGACY_DEFAULT_COLORS: the canonical hex values
    // from before message colours followed the theme. Kept only to
    // *recognise* an old saved config (an exact-match hex means "unset, use
    // the theme role colour" — see getMessageColor) — never rendered as a
    // colour themselves.
    'src/utils/messageColors.js:"#A180AE"',
    'src/utils/messageColors.js:"#B39DDB"',
    'src/utils/messageColors.js:"#FF5722"',
    'src/utils/messageColors.js:"#FFECB3"',
    'src/utils/messageColors.js:"#D5C0A1"',
    'src/utils/messageColors.js:"#BA8574"',
    'src/utils/messageColors.js:"#FFFFFF"',
    'src/utils/messageColors.js:"#DB9DC2"',
    'src/utils/messageColors.js:"#DC5D5D"',
    'src/utils/messageColors.js:"#FFE082"',
    // AssetView.vue's two nav-arrow icons: they sit on a translucent black
    // overlay drawn over an arbitrary image, so they must stay light under
    // every theme, not follow it.
    'src/components/AssetView.vue:<v-icon color="white">',
    // AssetView.vue's two nav-arrow buttons: same reasoning as the icons
    // above — a translucent black scrim over an arbitrary image, kept dark
    // under every theme rather than following it.
    'src/components/AssetView.vue:color="rgba(0,0,0,0.5)"',
    // MessageAssetImage.vue's loading-overlay scrim dims an arbitrary,
    // not-yet-loaded asset image for the spinner's contrast — same
    // reasoning as the AssetView nav icons above.
    'src/components/MessageAssetImage.vue:scrim="rgba(0, 0, 0, 0.9)"',
    // DefaultCharacter.vue's initial `defaultCharacter.color`: a seed hex
    // value sent to the backend as the new default character's own stored
    // colour (not drawn anywhere in this dialog), remapped at render time
    // like any other character colour — never rewritten.
    "src/components/DefaultCharacter.vue:color: '#3362bb'",
    // CoverBBoxEditor.vue draws its dimming mask, crop-rectangle/handle
    // contrast shadows and hint label over an arbitrary cover image, so
    // (like AssetView/MessageAssetImage/SceneMessages above) they must
    // stay legible under every theme rather than follow it.
    'src/components/CoverBBoxEditor.vue:background: rgba(0, 0, 0, 0.45);',
    'src/components/CoverBBoxEditor.vue:box-shadow: 0 0 0 1px rgba(0,0,0,0.35);',
    'src/components/CoverBBoxEditor.vue:box-shadow: 0 0 0 2px rgba(0,0,0,0.25);',
    'src/components/CoverBBoxEditor.vue:background: rgba(0, 0, 0, 0.5);',
    'src/components/CoverBBoxEditor.vue:color: rgba(255,255,255,0.9);',
    // VisualAssetBadge.vue's icon colour matches its own unflagged CSS
    // `.asset-badge { color: white; }` label text: both are chosen for
    // reliable contrast against this badge's varied accent backgrounds
    // (primary/delete/defaultBadge), independent of theme.
    'src/components/VisualAssetBadge.vue:<v-icon size="x-small" color="white">',
    // litegraphUtils.js's stylePresets: the ModuleStyle node's built-in
    // "quick pick" presets. Picking one writes these literal hex values
    // into the node's own stored node_color/title_color properties (see
    // applyStylePreset) — exactly the "default node colour presets saved
    // into node files" case from Global Constraints; the node's rendered
    // colour is always remapped from them via nodeColors() afterwards,
    // never drawn from these literals directly.
    'src/utils/litegraphUtils.js:node_color: "#392c34",',
    'src/utils/litegraphUtils.js:title_color: "#572e44",',
    'src/utils/litegraphUtils.js:node_color: "#392f2c",',
    'src/utils/litegraphUtils.js:title_color: "#573a2e",',
    'src/utils/litegraphUtils.js:node_color: "#32422d",',
    'src/utils/litegraphUtils.js:title_color: "#44552f",',
    'src/utils/litegraphUtils.js:node_color: "#223040",',
    'src/utils/litegraphUtils.js:title_color: "#2e4657",',
    'src/utils/litegraphUtils.js:node_color: "#5f2323",',
    'src/utils/litegraphUtils.js:title_color: "#7f2e2e",',
    'src/utils/litegraphUtils.js:node_color: "#27233a",',
    'src/utils/litegraphUtils.js:title_color: "#3d315b",',
    'src/utils/litegraphUtils.js:node_color: "#1e3a38",',
    'src/utils/litegraphUtils.js:title_color: "#2d5a55",',
    // litegraphUtils.js's dynamic-socket +/- glyphs: drawn on top of the
    // success/danger-coloured add/remove buttons right next to them, so
    // (like VisualAssetBadge.vue's icon above) they stay white for
    // reliable contrast against those vivid accent fills, independent of
    // theme.
    'src/utils/litegraphUtils.js:ctx.strokeStyle = "#fff";',
    // recentNodes.js's "Create Group from Selection" submenu: these quoted
    // strings are lookup keys into LGraphCanvas.node_colors (built by
    // rebuildThemeNodeColors() from the current theme's accent palette —
    // see litegraphUtils.js), not literal colours themselves. They read
    // as Vuetify hue names only because that's litegraph's own historical
    // swatch-key vocabulary (see LEGACY_SWATCH_ALIASES); the group colour
    // actually stored (`preset.groupcolor`, in groupInteractions.js) is
    // already the theme-resolved hex.
    'src/utils/recentNodes.js:makeColorItem("Output", \'green\'),',
    'src/utils/recentNodes.js:makeColorItem("Process", \'pale_blue\'),',
    'src/utils/recentNodes.js:makeColorItem("Prepare", \'cyan\'),',
    'src/utils/recentNodes.js:makeColorItem("Validation", \'yellow\'),',
    'src/utils/recentNodes.js:makeColorItem("Function", \'brown\'),',
    'src/utils/recentNodes.js:makeColorItem("Special", \'purple\'),',
    'src/utils/recentNodes.js:makeColorItem("Error Handling", \'red\'),',
    'src/utils/recentNodes.js:makeColorItem("Input", \'blue\'),',
    'src/utils/recentNodes.js:makeColorItem("UX", \'teal\'),',
    // SceneMessages.vue: the scene-backdrop message panel's text-shadow
    // (scoped to .scene-backdrop-active, and inherited by character lines,
    // which have no shadow of their own) must stay dark so message text of
    // every colour stays legible over an arbitrary backdrop image,
    // whatever the active theme.
    'src/components/SceneMessages.vue:text-shadow: 1px 1px 2px #000000, 0 0 6px rgba(0, 0, 0, 0.85);',
    // SceneMessages.vue: the backdrop-indicator marker sits over the same
    // arbitrary backdrop image, so its drop-shadow must stay dark under
    // every theme for the same reason as the message panel shadow above.
    'src/components/SceneMessages.vue:filter: drop-shadow(0 0 3px rgba(0, 0, 0, 0.9));',
]);

function isAllowed(relPath, line) {
    const prefix = `${relPath}:`;
    for (const entry of ALLOW) {
        if (entry.startsWith(prefix) && line.includes(entry.slice(prefix.length))) {
            return true;
        }
    }
    return false;
}

// --- Walking the tree -----------------------------------------------------

function listFiles(dir, results = []) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (full === THEME_DIR) continue;
        if (entry.isDirectory()) {
            listFiles(full, results);
        } else if (/\.(vue|js)$/.test(entry.name)) {
            results.push(full);
        }
    }
    return results;
}

function toRelPath(filePath) {
    return path.relative(process.cwd(), filePath).split(path.sep).join('/');
}

// Returns `{relPath, line, text}` for every failing, non-allowed line of
// every non-PENDING file under src/ (excluding src/theme/).
export function scanRepo() {
    const offenders = [];
    for (const filePath of listFiles(SRC_DIR)) {
        const relPath = toRelPath(filePath);
        if (PENDING.has(relPath)) continue;
        const lines = fs.readFileSync(filePath, 'utf8').split('\n');
        let inStyle = false;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (/<style\b/.test(line)) inStyle = true;
            if (lineFails(line, inStyle) && !isAllowed(relPath, line)) {
                offenders.push({ relPath, line: i + 1, text: line.trim() });
            }
            if (/<\/style>/.test(line)) inStyle = false;
        }
    }
    return offenders;
}

// --- Self-tests for the matcher -------------------------------------------

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

// Vuetify colour-scale name: one true positive per position (`color=`,
// `bg-`, `text-`).
check('vuetify_color_attr_true_positive', () => {
    assert.ok(lineFails('<v-icon color="grey-darken-3">x</v-icon>'));
});

check('vuetify_bg_class_true_positive', () => {
    assert.ok(lineFails('<div class="bg-red-darken-2">x</div>'));
});

check('vuetify_text_class_true_positive', () => {
    assert.ok(lineFails('<span class="text-white">x</span>'));
});

// Raw hex: one true positive per colour context (CSS declaration value,
// attribute value, string literal).
check('hex_css_declaration_true_positive', () => {
    assert.ok(lineFails('  color: #ff0000;', true));
});

check('hex_attribute_true_positive', () => {
    assert.ok(lineFails('<path fill="#112233" />'));
});

check('hex_string_literal_true_positive', () => {
    assert.ok(lineFails("const c = '#ffffff';"));
});

// rgba()/rgb(): a literal call fails; the theme's CSS-var form does not.
check('rgba_literal_true_positive', () => {
    assert.ok(lineFails('box-shadow: 0 0 4px rgba(0, 0, 0, 0.5);'));
});

check('rgb_theme_var_is_not_a_failure', () => {
    assert.ok(!lineFails('color: rgb(var(--v-theme-accent));', true));
    assert.ok(!lineFails('background: rgba(var(--v-theme-surface), 0.5);', true));
});

// False positives named in the brief: an href anchor, and string
// concatenation starting with '#'.
check('href_anchor_is_not_a_failure', () => {
    assert.ok(!lineFails('<a href="#top">Top</a>'));
    // A stronger case: the fragment is itself hex-shaped (b/a/d are valid
    // hex digits), so only the href-attribute guard (not "not valid hex")
    // keeps this from failing.
    assert.ok(!lineFails('<a href="#bad">Bad</a>'));
});

check('hash_concatenation_is_not_a_failure', () => {
    assert.ok(!lineFails("const sel = '#' + id;"));
});

// Extra coverage for the other non-colour `#` uses the brief calls out: an
// HTML numeric entity, and a bare CSS id selector (no colon before it, as
// opposed to a declaration).
check('html_entity_is_not_a_failure', () => {
    assert.ok(!lineFails('const label = "&#9733;";'));
});

check('css_id_selector_is_not_a_failure', () => {
    assert.ok(!lineFails('#app {', true));
});

// A real declaration still fails even without "color" in the property name,
// as long as it's inside a <style> block with a colon before the hex.
check('css_declaration_without_color_in_key_true_positive', () => {
    assert.ok(lineFails('  border: 1px solid #cccccc;', true));
});

// Fix round 1: a Vuetify colour name reached through a ternary/binding or
// plain JS, not sitting literally next to `color="`/`bg-`/`text-`. The
// three real forms the controller named, plus the two extra forms from the
// ruling.
check('quoted_color_literal_in_ternary_binding_true_positive', () => {
    assert.ok(lineFails(`:color="active ? 'primary' : 'grey'"`));
});

check('quoted_color_literal_in_conditional_binding_true_positive', () => {
    assert.ok(lineFails(`:color="message.subtype === 'function_call' ? 'orange' : 'info'"`));
});

check('quoted_color_literal_in_fallback_binding_true_positive', () => {
    assert.ok(lineFails(`:color="item.color || 'grey'"`));
});

check('quoted_color_literal_object_property_true_positive', () => {
    assert.ok(lineFails("color: 'grey-darken-2',"));
});

check('quoted_color_literal_in_class_array_true_positive', () => {
    assert.ok(lineFails(`:class="['bg-grey-darken-4']"`));
});

// False positives: a quoted colour-shaped word with no colour context token
// on the line, and a bona fide theme role name (not in the Vuetify hue list
// at all).
check('quoted_literal_without_color_context_is_not_a_failure', () => {
    assert.ok(!lineFails("status: 'green',"));
});

check('quoted_role_name_is_not_a_failure', () => {
    assert.ok(!lineFails(":color=\"'primary'\""));
});

// The sweep itself: every file under src/ (outside src/theme/, PENDING and
// ALLOW) is clean.
check('no_unswept_hardcoded_colors', () => {
    const offenders = scanRepo();
    if (offenders.length > 0) {
        const lines = offenders.map((o) => `${o.relPath}:${o.line}: ${o.text}`);
        assert.fail(`hard-coded colour(s) found outside PENDING/ALLOW:\n${lines.join('\n')}`);
    }
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
