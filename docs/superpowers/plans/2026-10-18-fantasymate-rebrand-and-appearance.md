# Fantasymate Rebrand and Appearance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the app as "fantasymate" and give it a Doom-Emacs-style theme system: a palette and
roles, gruvbox dark by default, nine presets, and themes of your own, recolouring the whole app.

**Architecture:** A pure-JS theme engine (`talemate_frontend/src/theme/`) turns a preset plus
overrides into a resolved theme: palette hexes plus one hex per role. The engine writes that into
a single Vuetify theme named `fantasymate` at runtime. Components use only role names or
`pal-<key>` colour names. Colours that arrive as data (character colours, node colours, agent
message colours) are remapped at render time and never rewritten on disk. The backend stores the
active theme id and the user's own themes in `Appearance.theme`.

**Tech Stack:** Vue 3, Vuetify 3.12, plain ES modules checked with `node:assert`
(`talemate_frontend/checks/*.check.mjs`), pydantic config, pytest, and Playwright e2e
(`tests/e2e`).

**Spec:** `docs/superpowers/specs/2026-10-18-fantasymate-rebrand-and-appearance-design.md`.
Mockups: https://claude.ai/artifact/LqRTBAiCE7hYS4sA7mMxaF (the Appearance artboard holds
starting hex values for every preset).

## Global Constraints

- **Do not start until the cultures work on `feature/cultures-story` is merged to main.** Then
  branch `feature/fantasymate-appearance` from main.
- Run everything through Guix from the repo root: `guix shell -m manifest.scm -- …`. Use
  `uv run --no-sync` (never plain `uv run`). Run pnpm as `npx --yes corepack@0.34.0 pnpm` from
  inside `talemate_frontend`. About 141 plain-suite failures are environment-only (NLTK
  `punkt_tab`), so judge by the tests you touched.
- Visual-only rename: the Python package, `talemate` module paths, config file and folder,
  websocket message names, CLI, scene file format, component and file names, and log names all
  stay Talemate.
- Never rewrite stored colour data. Character colours, `node_color`/`title_color` in backend
  files and saved node modules, and agent `message.data.color` are remapped at render time only.
- Palette keys, exactly and in this order: `bg`, `bg-alt`, `base1`, `base2`, `base3`, `base4`,
  `fg`, `fg-alt`, `grey`, `red`, `orange`, `yellow`, `green`, `teal`, `blue`, `magenta`.
- Accent keys (used for character and data colours): `red`, `orange`, `yellow`, `green`, `teal`,
  `blue`, `magenta`.
- Core roles and defaults: `accent`→orange, `link`→yellow, `scene`→teal, `foreign`→magenta,
  `narrator`→fg-alt, `charname`→orange, `you`→blue, `date`→blue, `success`→green,
  `warning`→yellow, `danger`→red.
- Default preset id: `gruvbox-dark`. Preset ids: `gruvbox-dark`, `gruvbox-light`, `nord`,
  `solarized-dark`, `solarized-light`, `monokai`, `cb-red-green`, `cb-blue-yellow`,
  `cb-high-contrast`.
- Contrast: under every built-in preset, every text role reaches **4.5:1** against `bg`,
  `bg-alt` and `base1`.
- Built-in presets are read-only. Changes are made on a duplicate.
- Theme file format id: `fantasymate-theme`, version `1`.
- Wordmark: "fantasymate", lower case, Alegreya Bold, coloured with the `link` role.

## Review Focus

1. **A theme file that is malformed:** not JSON, the wrong `format`, a bad hex, or missing palette
   keys. It is rejected with a readable message, and the user's themes stay unchanged. → Task 9
   test `parse_rejects_*`.
2. **An `active` id that names a deleted custom theme or an unknown preset**, for example a config
   from a newer version. The theme falls back to gruvbox dark, and nothing crashes or goes blank.
   → Task 1 test `config_unknown_active_falls_back`.
3. **A custom theme saved before a palette key or role existed.** The missing values are filled
   from its base preset. → Task 1 test `config_custom_fills_missing_from_base`.
4. **Character colours stored as `#fff`, `#FFF`, a Vuetify name (`deep-purple-lighten-3`), or
   rubbish.** Each one gets a stable accent, the same character gets the same colour on every
   load, and nothing throws. → Task 4 tests `character_key_*`.
5. **Typing a partial hex (`#fe8`) into the palette editor, or leaving Settings with an unsaved
   theme.** A partial value is never applied. Leaving Settings brings back the saved theme
   through `appearance-preview-clear`. → Task 9 e2e `test_unsaved_theme_reverts_on_leave`.

## File Structure

| File | Responsibility |
|---|---|
| `talemate_frontend/src/theme/colorMath.js` (create) | hex parsing, mix/darken/lighten, luminance, contrast, hue/saturation |
| `talemate_frontend/src/theme/palette.js` (create) | `PALETTE_KEYS`, `ACCENT_KEYS` |
| `talemate_frontend/src/theme/roles.js` (create) | core, neutral, message and legacy roles with default refs; `TEXT_ROLES` |
| `talemate_frontend/src/theme/presets.js` (create) | `BUILTIN_PRESETS`, `getPreset`, `DEFAULT_PRESET_ID` |
| `talemate_frontend/src/theme/engine.js` (create) | `resolveTheme`, `resolveRef`, `toVuetifyColors`, `themeFromConfig` |
| `talemate_frontend/src/theme/store.js` (create) | `currentTheme` ref, `applyTheme` |
| `talemate_frontend/src/theme/dataColors.js` (create) | remapping data colours: `toHex`, `nearestAccent`, `characterPaletteKey`, `dataColor`, `nodeColors` |
| `talemate_frontend/src/theme/themeFile.js` (create) | `exportTheme`, `parseThemeFile` |
| `talemate_frontend/src/components/FmWordmark.vue` (create) | the text wordmark |
| `talemate_frontend/src/components/AppConfigAppearanceTheme.vue` (create) | the Theme settings page |
| `talemate_frontend/checks/theme.check.mjs` (create) | node checks for everything under `src/theme/` |
| `talemate_frontend/checks/themeColors.check.mjs` (create) | sweep guard: no hard-coded colours outside `src/theme/` |
| `tests/dev/test_frontend_checks.py` (modify) | run both new checks |
| `src/talemate/config/schema.py` (modify) | `CustomTheme`, `ThemeSettings`, `Appearance.theme` |
| `tests/test_config_theme.py` (create) | config round trip |
| `tests/e2e/theme/` (create) | e2e for theme application, settings page, and branding |

---

### Task 1: Theme engine core and presets

**Files:**
- Create: `talemate_frontend/src/theme/colorMath.js`, `palette.js`, `roles.js`, `presets.js`, `engine.js`
- Create: `talemate_frontend/checks/theme.check.mjs`
- Modify: `tests/dev/test_frontend_checks.py`

**Interfaces:**
- Produces:
  - `colorMath.js`:
    - `isHex(s: string): boolean` (only `#rrggbb`, any case)
    - `normalizeHex(s): string|null` (accepts `#rgb` and `#rrggbb`, returns lower-case `#rrggbb`)
    - `mix(a: hex, b: hex, t: number): hex` (t=0 gives a)
    - `darken(hex, t)` = `mix(hex,'#000000',t)`
    - `lighten(hex, t)` = `mix(hex,'#ffffff',t)`
    - `contrastRatio(a, b): number` (WCAG 2)
    - `hueOf(hex): number` (0–360)
    - `saturationOf(hex): number` (HSL, 0–1)
  - `palette.js`: `PALETTE_KEYS: string[]`, `ACCENT_KEYS: string[]` (from Global Constraints).
  - `roles.js`:
    - A role ref is a palette key string or `{ pal: string, darken?: number, lighten?: number, mix?: { with: string, t: number } }`.
    - `CORE_ROLES: {id, label, ref}[]` (the 11 core roles, in the order above).
    - `NEUTRAL_ROLES`:
      - `background`→bg-alt, `surface`→bg, `raised`→base1, `surface-variant`→base2
      - `border`→base3, `strong`→base4
      - `on-surface`→fg, `on-background`→fg, `muted`→grey
    - `MESSAGE_ROLES`: `quotes`, `parentheses`, `brackets`, `emphasis`, `entities`, `director`,
      `context_investigation`, `information`.
    - `LEGACY_ROLES`: every key now in `plugins/vuetify.js` that is not already named above.
    - `ALL_ROLES` = all of the above, as `{ id: ref }`.
    - `TEXT_ROLES: string[]`: `on-surface`, `muted`, `narrator`, `link`, `scene`, `foreign`,
      `charname`, `you`, `date`, `success`, `warning`, `danger`, the message roles, and every
      `highlight1`–`7`.
  - `presets.js`:
    - `BUILTIN_PRESETS: {id, name, dark: boolean, group: 'main'|'vision', palette: {key: hex}, roles: {role: ref}}[]`
    - `getPreset(id): preset|undefined`
    - `DEFAULT_PRESET_ID = 'gruvbox-dark'`
  - `engine.js`:
    - `resolveRef(ref, palette): hex`
    - `resolveTheme(preset, overrides = {palette: {}, roles: {}}): Resolved`, where
      `Resolved = {id, name, dark, palette: {key: hex}, roleRefs: {role: ref}, colors: {role: hex}}`
    - `toVuetifyColors(resolved): {[name]: hex}`: every role, plus `pal-<key>` for every palette key.
    - `themeFromConfig(themeSettings | undefined): Resolved`

- [ ] **Step 1: Write the failing checks** in `checks/theme.check.mjs`, following the
  `check(name, fn)` / `passed` / `failures` pattern and the closing `ok N` line of
  `checks/culturesStory.check.mjs`:
  - `mix_endpoints`:
    - `mix('#000000','#ffffff',0) === '#000000'`
    - `mix('#000000','#ffffff',1) === '#ffffff'`
    - `mix('#000000','#ffffff',0.5) === '#808080'`
  - `contrast_black_white`: `Math.round(contrastRatio('#000000','#ffffff')) === 21`
  - `normalize_hex`:
    - `normalizeHex('#FFF') === '#ffffff'`
    - `normalizeHex('#12345') === null`
    - `normalizeHex('red') === null`
  - `presets_complete`: every preset in `BUILTIN_PRESETS` has every `PALETTE_KEYS` entry as an
    `isHex` value, and the ids equal the nine ids in Global Constraints.
  - `gruvbox_dark_core`: `resolveTheme(getPreset('gruvbox-dark')).colors` has:
    - `accent === '#fe8019'`, `link === '#fabd2f'`, `scene === '#8ec07c'`
    - `surface === '#282828'`, `background === '#1d2021'`
  - `roles_resolve_every_role`: under every preset, every key of `ALL_ROLES` resolves to an
    `isHex` value.
  - `vision_preset_remaps`: in `resolveTheme(getPreset('cb-red-green')).roleRefs`,
    `success === 'blue'` and `scene === 'blue'`.
  - `override_palette_and_role`:
    - `resolveTheme(p, {palette: {orange: '#112233'}, roles: {}}).colors.accent === '#112233'`
    - `resolveTheme(p, {palette: {}, roles: {accent: 'blue'}}).colors.accent === p.palette.blue`
  - `contrast_text_roles`: for every preset, every `TEXT_ROLES` role reaches `>= 4.5` against
    `bg`, `bg-alt` and `base1`. The failure message names the preset, role, surface and ratio.
  - `vuetify_colors_include_palette`: `toVuetifyColors(r)['pal-teal'] === r.palette.teal`
  - `config_none_is_default`: `themeFromConfig(undefined).id === 'gruvbox-dark'`
  - `config_unknown_active_falls_back`: `themeFromConfig({active: 'custom-gone', custom: []}).id === 'gruvbox-dark'`
  - `config_custom_fills_missing_from_base`:
    - Input: `themeFromConfig({active: 'custom-1', custom: [{id: 'custom-1', name: 'Mine', base: 'nord', dark: true, palette: {orange: '#aa5500'}, roles: {}}]})`
    - The result has `palette.orange === '#aa5500'`, `palette.bg === getPreset('nord').palette.bg`, and `name === 'Mine'`.
- [ ] **Step 2: Add `test_theme_checks`** to `tests/dev/test_frontend_checks.py`. It runs
  `node checks/theme.check.mjs` and uses the same skip markers and asserts as
  `test_cultures_story_checks`. Run
  `guix shell -m manifest.scm -- uv run --no-sync pytest tests/dev/test_frontend_checks.py -v`.
  Expected: FAIL, because the theme modules don't exist.
- [ ] **Step 3: Implement `colorMath.js` and `palette.js`.**
- [ ] **Step 4: Implement `roles.js`.**
  - Pick legacy defaults so that under gruvbox dark the app reads as gruvbox:
    - `primary`→orange, `secondary`→yellow, `delete`→red
    - `muted`/`normal`/`mutedheader`→grey, `mutedbg`→base1
    - `card_border`/`avatar_border`→base2
    - `highlight1`–`7`→blue, magenta, green, red, yellow, orange, teal
    - `subdued1`–`7`→the same accents with `{darken: 0.45}`
    - `enabled`→green, `disabled`→red, `unsaved`/`dirty`→yellow
    - `nodeeditorbg`→bg-alt, `cornflowerblue`→blue
  - `dchat_*`, `hchat_*` and the remaining keys: your choice, as long as `contrast_text_roles`
    passes.
- [ ] **Step 5: Implement `presets.js`.** Start from the mockup's hex values (the Appearance
  artboard's `P` table; copy them across). Then adjust only the values that fail
  `contrast_text_roles`, keeping each scheme's hue. Add `group: 'vision'` and the role remaps for
  the three `cb-*` presets:
  - `cb-red-green`: `success`→blue, `scene`→blue, `danger`→red, with the Okabe–Ito palette from
    the mockup.
  - `cb-blue-yellow`: `link`→orange, `warning`→orange, `date`→magenta, `you`→teal.
  - `cb-high-contrast`: palette only.
- [ ] **Step 6: Implement `engine.js`.** In `themeFromConfig`:
  - If `active` names an entry in `custom`, use that entry's `base` preset, overlaid with its
    `palette` and `roles`. Its `name` and `dark` win.
  - Else, if `active` names a preset, use that preset.
  - Else, use `DEFAULT_PRESET_ID`.
  - Ignore override values that fail `isHex` or that name an unknown palette key.
- [ ] **Step 7: Run the checks.**
  `guix shell -m manifest.scm -- sh -c 'cd talemate_frontend && node checks/theme.check.mjs'`.
  Expected: `ok 13`, exit 0. Then run the pytest wrapper. Expected: PASS.
- [ ] **Step 8: Commit.** `git commit -m "feat(theme): palette, roles, presets and theme engine"`

### Task 2: Store the theme in the app config

**Files:**
- Modify: `src/talemate/config/schema.py` (next to `class Appearance`, about line 673)
- Test: `tests/test_config_theme.py`

**Interfaces:**
- Produces:
  - `CustomTheme(pydantic.BaseModel)` with:
    - `id: str`, `name: str`
    - `base: str = "gruvbox-dark"`, `dark: bool = True`
    - `palette: dict[str, str] = {}`, `roles: dict[str, str] = {}`
  - `ThemeSettings(pydantic.BaseModel)` with `active: str = "gruvbox-dark"` and
    `custom: list[CustomTheme] = []`.
  - `Appearance.theme: ThemeSettings = ThemeSettings()`
  - The frontend reads this as `appConfig.appearance.theme`.

- [ ] **Step 1: Write the failing tests.**
  - `test_default_theme_is_gruvbox_dark`: `Config().appearance.theme.active == "gruvbox-dark"`
    and `custom == []`.
  - `test_theme_round_trips_through_yaml`: set `active="custom-1"` and add one `CustomTheme` with
    `palette={"orange": "#aa5500"}`. Then save and reload with the helpers and the isolation
    pattern from `tests/test_config_state.py`. Assert that the same values come back.
  - `test_config_without_theme_loads`: an `appearance` dict with only `scene` validates, and gets
    the default theme.
- [ ] **Step 2: Run them.**
  `guix shell -m manifest.scm -- uv run --no-sync pytest tests/test_config_theme.py -v`.
  Expected: FAIL (no attribute `theme`).
- [ ] **Step 3: Add the two models and the field.**
- [ ] **Step 4: Run them.** Expected: PASS. Also run `tests/test_config_state.py`. Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(config): store active theme and custom themes"`

### Task 3: Apply the theme across the app

**Files:**
- Create: `talemate_frontend/src/theme/store.js`
- Modify:
  - `talemate_frontend/src/plugins/vuetify.js`: replace the `dark` theme with `fantasymate`,
    built from `toVuetifyColors(themeFromConfig())`, and make it the default.
  - `talemate_frontend/src/components/TalemateApp.vue`: add a watcher on
    `effectiveAppearanceConfig` that calls `applyTheme`.
  - `talemate_frontend/src/App.vue`
- Test: `tests/e2e/theme/__init__.py`, `tests/e2e/theme/test_apply.py`

**Interfaces:**
- Consumes: `themeFromConfig`, `toVuetifyColors` (Task 1); `appConfig.appearance.theme` (Task 2).
- Produces:
  - `currentTheme: ShallowRef<Resolved>`
  - `applyTheme(vuetifyTheme, resolved): void`. It sets
    `vuetifyTheme.themes.value.fantasymate.dark` and `.colors`, then sets `currentTheme.value`.
  - TalemateApp calls it with `useTheme()`'s instance (or `this.$vuetify.theme`) whenever
    `effectiveAppearanceConfig.theme` changes, including the live preview.

- [ ] **Step 1: Write the failing e2e tests.** Write them in the style of
  `tests/e2e/cultures/test_tab_and_import.py`, using the `app` and `page` fixtures.
  - `test_default_theme_is_gruvbox_dark`: the computed background of `.v-application` is
    `rgb(29, 32, 33)` (`#1d2021`).
  - `test_theme_from_config_applies`: the `app` fixture is session-scoped, so don't edit
    `config.yaml` on disk. Set `appearance.theme.active = "nord"` through the same websocket
    config save that `AppSettings.vue` sends (copy its payload shape, using `send_backend` from
    `e2e.seed`). Reload the page. The `.v-application` background is nord's `bg-alt`. In a
    `finally`, set it back to `gruvbox-dark` so the other tests start from the default.
- [ ] **Step 2: Run them.**
  `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e/theme -m e2e -n0`.
  Expected: FAIL (the background is the old Vuetify dark).
- [ ] **Step 3: Implement `store.js`. Wire up `vuetify.js` and the TalemateApp watcher.** Remove
  `theme="dark"` props (`AssetView.vue`) and anything else that names the old `dark` theme.
  Point the `<body>` and `.v-application` backgrounds at `rgb(var(--v-theme-background))`.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(theme): apply the configured theme to the whole app"`

### Task 4: Remap data colours at render time

**Files:**
- Create: `talemate_frontend/src/theme/dataColors.js`
- Modify:
  - `talemate_frontend/src/components/SceneMessages.vue`: `borderColor: message.color` and the
    `color: data.color` assignments.
  - `talemate_frontend/src/components/CharacterMessage.vue`
  - `talemate_frontend/src/components/SceneMessageInput.vue` (`characterColors`)
  - `talemate_frontend/src/utils/litegraphUtils.js` and `talemate_frontend/src/utils/commentNode.js`
  - `talemate_frontend/src/components/NodeEditor.vue`
  - the director and help chat message components that use `message.data.color`
- Test: `talemate_frontend/checks/theme.check.mjs` (add checks)

**Interfaces:**
- Consumes: `colorMath`, `ACCENT_KEYS`, `currentTheme` (Task 3).
- Produces:
  - `toHex(value: string): hex|null`. It handles `#rgb`/`#rrggbb` and Vuetify names such as
    `red` or `deep-purple-lighten-3`, using `vuetify/util/colors` (kebab name → camelCase family,
    and `lighten-3` → `lighten3`).
  - `nearestAccent(hex, palette): accentKey|null`. It returns `null` when `saturationOf(hex) < 0.2`.
    Otherwise it returns the accent whose `hueOf` is circularly nearest.
  - `characterPaletteKey(stored: string|null, name: string): accentKey`. It returns
    `nearestAccent(toHex(stored))` if that isn't null. Otherwise it returns
    `ACCENT_KEYS[hash(name) % 7]`, where the hash is a fixed string hash (FNV-1a 32-bit).
  - `dataColor(value, resolved = currentTheme.value): hex|null`:
    - empty input gives `null`
    - a saturated value gives the accent's hex
    - a low-saturation value gives `colors.muted`, or `colors['on-surface']` when its lightness is above 0.85
  - `nodeColors(value, resolved = currentTheme.value): {title: hex, body: hex}`:
    - `title = mix(accentHex, palette.bg, 0.65)`, `body = mix(accentHex, palette.bg, 0.8)`
    - for an unsaturated value, `title = palette.base2` and `body = palette.base1`

- [ ] **Step 1: Write the failing checks.**
  - `to_hex_forms`:
    - `toHex('#FFF') === '#ffffff'`
    - `toHex('deep-purple-lighten-3') === '#b39ddb'`
    - `toHex('nonsense') === null`
  - `character_key_white_uses_name_hash`:
    - `characterPaletteKey('#fff', 'Marta')` is in `ACCENT_KEYS`
    - it equals `characterPaletteKey(null, 'Marta')`
    - it equals `characterPaletteKey('#FFFFFF', 'Marta')`
  - `character_key_stable`: computing `characterPaletteKey('nonsense', 'Ilsa Varn')` twice gives
    the same result.
  - `character_key_from_vuetify_name`: under gruvbox dark,
    `characterPaletteKey('red-lighten-3', 'x') === 'red'`.
  - `data_color_grey_is_muted`: `dataColor('#9e9e9e', r) === r.colors.muted`
  - `node_colors_follow_theme`: `nodeColors('#572e44', nord)` differs from `nodeColors('#572e44', gruvboxDark)`, and both are `isHex`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement `dataColors.js`.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Wire it in.**
  - Character colours go through `palette[characterPaletteKey(stored, name)]` in
    CharacterMessage, the SceneMessages border, and SceneMessageInput.
  - Agent and chat message colours go through `dataColor`.
  - Litegraph:
    - Node `color`/`bgcolor` go through `nodeColors` when the node is drawn (in the code that
      reads `node_color`/`title_color`).
    - The `LGraphCanvas.node_colors` entries and canvas background are rebuilt from the current
      theme. Re-run that rebuild when `currentTheme` changes.
  - No backend file changes.
- [ ] **Step 6: Check by eye** in the isolated app
  (`uv run --no-sync python scripts/dev/talemate_app.py start`) with a seeded scene. Character
  names should be in gruvbox accents, and the node editor should show warm tinted nodes. Stop
  the app.
- [ ] **Step 7: Commit.** `git commit -m "feat(theme): remap character, node and agent colours to the palette"`

### Task 5: Fold message colours into the theme

**Files:**
- Modify:
  - `talemate_frontend/src/utils/messageColors.js`
  - `talemate_frontend/src/utils/sceneMessageRenderer.js` (its hex literals)
  - `talemate_frontend/src/components/AppConfigAppearanceScene.vue`
- Test: `talemate_frontend/checks/theme.check.mjs` (add checks)

**Interfaces:**
- Consumes: `currentTheme`, `PALETTE_KEYS`, `isHex`.
- Produces:
  - `DEFAULT_APPEARANCE_COLORS` is renamed `LEGACY_DEFAULT_COLORS`. Same values, now used only
    to recognise old saved defaults.
  - `MESSAGE_ROLE: {[typ]: role}` maps:
    - narrator→`narrator`, actor→`charname`, director→`director`, time→`date`
    - context_investigation→`context_investigation`, information→`information`
    - quotes, parentheses, brackets, emphasis, entities→the role of the same name
  - `getMessageColor(appearanceConfig, typ, resolved = currentTheme.value): hex`, where `cfg.color` is:
    - a palette key: the palette hex
    - an `isHex` value equal (any case) to `LEGACY_DEFAULT_COLORS[typ]`: the role colour (the "counts as unset" rule)
    - any other hex: that hex
    - empty: the role colour
  - `getMessageStyle` keeps its signature and uses the new `getMessageColor`.

- [ ] **Step 1: Write the failing checks.**
  - `message_color_empty_uses_role`: `getMessageColor({scene: {narrator_messages: {}}}, 'narrator', r) === r.colors.narrator`
  - `message_color_legacy_default_is_unset`: a config with `quotes: {color: '#FFFFFF'}` gives `r.colors.quotes`
  - `message_color_palette_name`: `{color: 'teal'}` gives `r.palette.teal`
  - `message_color_user_hex_kept`: `{color: '#123456'}` gives `'#123456'`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement `messageColors.js`.** Update the imports in `sceneMessageRenderer.js`
  and in every other importer of `DEFAULT_APPEARANCE_COLORS`, and replace their hex literals with
  `currentTheme` lookups.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Update the Messages page.**
  - `hydrateMarkupStyle` seeds `color: null`, not the legacy hex.
  - The colour control lists the `PALETTE_KEYS` swatches first, then "Custom…", which opens the
    existing `v-color-picker`. A palette key is stored as the colour.
  - The black preview `v-card` uses `color="surface"`.
  - Reset still sets `null`.
- [ ] **Step 6: Commit.** `git commit -m "feat(theme): message colours follow theme roles"`

### Task 6: Sweep guard

**Files:**
- Create: `talemate_frontend/checks/themeColors.check.mjs`
- Modify: `tests/dev/test_frontend_checks.py` (add `test_theme_colors_check`)

**Interfaces:**
- Produces: `PENDING`, a `Set` of repo-relative paths still allowed to contain hard-coded colours.
  Each sweep task (7–8) deletes the paths it cleans. Task 8 leaves it empty.
- Produces: `ALLOW`, a `Set` of `path:line-substring` exceptions. It starts empty. Add an entry
  only with a one-line comment saying why.

The check walks `talemate_frontend/src/**/*.{vue,js}`, excluding `src/theme/`. A line fails when it
matches either of these:
- a Vuetify colour-scale name in a `color=`/`bg-`/`text-` position:
  `/(?:color="|bg-|text-)(?:grey|blue-grey|black|white|red|pink|purple|deep-purple|indigo|blue|light-blue|cyan|teal|green|light-green|lime|yellow|amber|orange|deep-orange|brown)(?:-(?:lighten|darken|accent)-\d)?\b/`
- a raw colour: `/#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d/`

These lines don't fail:
- lines in `PENDING` files
- `ALLOW` entries
- lines with `rgb(var(--v-theme-` or `rgba(var(--v-theme-`
- HTML entities and `#` anchors that aren't colours: require the hex match to sit in a CSS, style
  or `color` context, or exclude `href="#`.

**Sweep mapping** (use the role whose meaning fits, but these are the defaults):

| Found | Replace with |
|---|---|
| `grey-darken-4`, `black` as a background | `background` |
| `grey-darken-3` | `raised` |
| `grey-darken-2` | `surface-variant` |
| `grey-darken-1` | `border` (or `strong` for text) |
| `grey`, `grey-lighten-1`, `grey-lighten-2`, `text-grey*` | `muted` |
| `grey-lighten-3`, `white`, `text-white` | `on-surface` |
| `red*` | `danger` (or `delete` where the component means delete) |
| `green*` | `success` |
| `amber*`, `orange*` meaning caution | `warning` |
| `orange*`, `deep-orange*` meaning emphasis | `accent` |
| `deep-purple*` | `primary` |
| other hues (`teal`, `indigo`, `brown`…) | the nearest `pal-<accent>` |
| hex or `rgba()` in `<style>` | `rgb(var(--v-theme-<role>))` / `rgba(var(--v-theme-<role>), a)` |

- [ ] **Step 1: Write the check.** Seed `PENDING` with every file that fails right now. Generate
  the list by running the check once with an empty `PENDING` and printing the files that fail.
  Run the check. Expected: `ok`, exit 0.
- [ ] **Step 2: Prove that it bites.** Temporarily add `color="grey-darken-3"` to any file not
  in `PENDING`. Run the check. Expected: FAIL, naming that
  file and line. Revert.
- [ ] **Step 3: Add `test_theme_colors_check`** and run the pytest wrapper. Expected: PASS.
- [ ] **Step 4: Commit.** `git commit -m "test(theme): guard against hard-coded colours"`

### Task 7: Sweep the app shell, home, settings, scene and story

**Files:**
- Modify: every `PENDING` file in these groups:
  - `TalemateApp.vue`, `App.vue`, `SceneLanding.vue`, `IntroRecentScenes.vue`, `SceneBrowser.vue`, `NewSceneSetupModal.vue`
  - all `AppConfig*`/`AppSettings*` components, `OnboardingWizard.vue`, `WhatsNew.vue`, and the dialogs and alerts mounted by `TalemateApp.vue`
  - `SceneMessages.vue`, `CharacterMessage.vue`, `NarratorMessage.vue`, `TimePassageMessage.vue`, `ContextInvestigationMessage.vue`
  - every other `*Message.vue`, `SceneMessageInput.vue`, `SceneTools*.vue`, `AgentActivityBar.vue`, `MessageAssetImage.vue`, `CoverImage.vue`, `WorldState.vue`
- Modify: `talemate_frontend/checks/themeColors.check.mjs` (delete these paths from `PENDING`)

- [ ] **Step 1: Delete these paths from `PENDING`.** Run the check. Expected: FAIL, listing their
  lines.
- [ ] **Step 2: Replace each hit** using the sweep mapping. Delete the `.backdrop` logo image
  styles in `TalemateApp.vue`, so the backdrop is just `background` (Task 10 adds the wordmark).
- [ ] **Step 3: Run the check.** Expected: PASS. Then run
  `guix shell -m manifest.scm -- uv run --no-sync pytest tests/e2e -m e2e -n0`. Expected: no
  new failures compared with main.
- [ ] **Step 4: Check by eye** under `gruvbox-dark` and `solarized-light`. Switch by editing
  `appearance.theme.active` in the isolated app's config and reloading. Check the home screen,
  a loaded scene, and Settings. Write down any surface still in the old grey and fix it.
- [ ] **Step 5: Commit.** `git commit -m "refactor(theme): app shell, settings and story use theme roles"`

### Task 8: Sweep the world editor, cultures, node editor, chats, and the rest

**Files:**
- Modify: every `WorldStateManager*`, `cultures/*`, `NodeEditor*`, `DirectorConsole*`,
  `HelpChat*`, `PackageManager*`, `Templates*`, `Prompts*`, `Debug*`, `AIClient*`, `AIAgent*`
  and `Visual*` file still in `PENDING`, and then whatever remains.
- Modify: `talemate_frontend/checks/themeColors.check.mjs` (`PENDING` ends empty)

- [ ] **Step 1: Empty `PENDING`.** Run the check. Expected: FAIL, listing the remaining lines.
- [ ] **Step 2: Replace each hit** using the sweep mapping. Culture colours that the user picks
  and stores (a culture's own `color`) are data, so pass them through `dataColor`, as in Task 4.
- [ ] **Step 3: Run the check.** Expected: PASS with `PENDING` empty. Then run the full e2e
  suite. Expected: no new failures compared with main.
- [ ] **Step 4: Check by eye** under `gruvbox-dark`, `gruvbox-light` and `cb-high-contrast`. Check
  the World Editor (every tab, including Cultures), the node editor, the director console, and
  the help chat.
- [ ] **Step 5: Commit.** `git commit -m "refactor(theme): remaining components use theme roles"`

### Task 9: Theme settings page, your own themes, import and export

**Files:**
- Create: `talemate_frontend/src/theme/themeFile.js`
- Create: `talemate_frontend/src/components/AppConfigAppearanceTheme.vue`
- Modify:
  - `talemate_frontend/src/utils/appSettingsRegistry.js`: a new first page in Appearance, with
    `id: 'appearance-theme'`, `title: 'Theme'`, `icon: 'mdi-palette-swatch-outline'`, and entries
    "Presets", "Palette", "Roles", "Your themes", "Import / export".
  - `talemate_frontend/src/components/AppSettings.vue`: a `v-window-item` for it, wired to
    `@changed="onAppearanceChanged"` like its siblings.
- Test: `talemate_frontend/checks/theme.check.mjs`, `tests/e2e/theme/test_settings.py`

**Interfaces:**
- Consumes: `BUILTIN_PRESETS`, `resolveTheme`, `themeFromConfig`, `PALETTE_KEYS`, `CORE_ROLES`;
  `app_config.appearance.theme`.
- Produces:
  - `exportTheme(customTheme): object`, giving
    `{format: 'fantasymate-theme', version: 1, name, dark, base, palette, roles}`.
  - `parseThemeFile(text): {ok: true, theme: CustomTheme-without-id} | {ok: false, error: string}`
  - The page edits `app_config.appearance.theme` in place and emits `changed`, so the existing
    preview and save flow applies it live (Task 3's watcher).

The layout follows the mockup's Appearance artboard:
- **Preset list.** Grouped Presets / Colour vision / Yours, with four swatches per entry. A click
  sets `active`. Your own themes get rename and delete. Deleting the active theme sets `active`
  to its `base`.
- **"Duplicate current as new".** It pushes
  `{id: 'custom-' + uuid, name: '<name> copy', base, dark, palette: {...resolved palette}, roles: {}}`
  and makes it active.
- **Palette strip.**
  - Clicking a swatch selects it.
  - The hex field applies only `isHex` values, so partial input waits.
  - `v-color-picker` sets the value.
  - "Used by" lists the roles that point at the selected key.
  - On a built-in preset, editing is disabled and a "Duplicate to edit" button shows.
- **Roles list.** Each core role has a `v-select` of `PALETTE_KEYS`. It's disabled on built-ins.
- **Preview card.** Tabs, a badge, a story excerpt with a world link, a scene-only link, a
  foreign word and a character name, and Send/Approved/Needs review/Reject chips. All of it is
  drawn from roles.
- **Import and export.** Export downloads `<name>.fantasymate-theme.json`. Import reads a file
  through `parseThemeFile`. A success adds a custom theme. A failure shows `error` in a `v-alert`
  and changes nothing.

- [ ] **Step 1: Write the failing checks.**
  - `export_parse_round_trip`: `parseThemeFile(JSON.stringify(exportTheme(t)))` is `ok`, and its
    palette and roles equal `t`'s.
  - `parse_rejects_not_json`: `ok === false` and `error` mentions "JSON".
  - `parse_rejects_wrong_format`: `{format: 'other'}` gives `ok === false`.
  - `parse_rejects_bad_hex`: palette `{orange: 'tomato'}` gives `ok === false`, and `error`
    names `orange`.
  - `parse_fills_missing_palette_from_base`: a file with only `{orange}` and `base: 'nord'` is
    `ok`, and `themeFromConfig` of it has nord's `bg`.
  - `parse_rejects_unknown_role_target`: roles `{accent: 'chartreuse'}` gives `ok === false`.
- [ ] **Step 2: Write the failing e2e tests** in `tests/e2e/theme/test_settings.py`:
  - `test_pick_preset_recolours_live`: open Settings → Appearance → Theme and click "Nord". The
    `.v-application` background becomes nord's `bg-alt` before saving.
  - `test_duplicate_edit_save_persists`:
    1. Duplicate, set `orange` to `#aa5500`, and save.
    2. Reload, and check that the custom theme is active and `--v-theme-accent` is `170,85,0`.
  - `test_unsaved_theme_reverts_on_leave`: pick "Monokai" without saving, then switch to the
    home tab. The background goes back to gruvbox `#1d2021`.
  - `test_import_bad_file_shows_error`: upload a file with `{"format": "x"}`. An error alert
    shows, and the "Yours" list is unchanged.
- [ ] **Step 3: Run both.** Expected: FAIL.
- [ ] **Step 4: Implement `themeFile.js`, the page, the registry entry, and the window item.**
- [ ] **Step 5: Run both.** Expected: PASS.
- [ ] **Step 6: Commit.** `git commit -m "feat(theme): theme settings page with custom themes and import/export"`

### Task 10: Rebrand (visual only)

**Files:**
- Create:
  - `talemate_frontend/src/components/FmWordmark.vue`: props `size: 'sm'|'lg'` (sm 20px for
    the app bar, lg 72px for the empty backdrop); colour `rgb(var(--v-theme-link))`.
  - `talemate_frontend/public/favicon.svg`: a lower-case "f" in `#fabd2f` on a rounded
    `#282828` square.
  - `talemate_frontend/public/favicon-loading.svg`: the same, with an `#fe8019` dot.
- Modify:
  - `talemate_frontend/index.html`: the `<title>` and the noscript text say fantasymate. The
    icon link is `/favicon.svg` with `type="image/svg+xml"`.
  - `talemate_frontend/src/components/TalemateApp.vue`:
    - The `.logo` image in the app bar becomes `<FmWordmark size="sm">`.
    - The empty-state backdrop shows `<FmWordmark size="lg">`, centred, at 0.15 opacity.
    - The favicon swap (around line 1367) uses the two `.svg` files.
  - `talemate_frontend/src/main.js`: import `@fontsource/alegreya/700.css`. Add the dependency
    with `npx --yes corepack@0.34.0 pnpm add @fontsource/alegreya`. My call: the font is bundled
    so the app works offline.
  - User-visible strings that name the product in:
    - `SceneLanding.vue`, `OnboardingWizard.vue`, `WhatsNew.vue`, `HelpChat.vue`,
      `VersionMismatchAlert.vue`, `AppSettings*.vue`, `ClientModal.vue`, `AgentModal.vue`,
      `CharacterCardImport.vue`, `PackageManager.vue`
    - `utils/appSettingsRegistry.js` (descriptions)
    - `cultures/ImportCultureDialog.vue`
    - Find them with `grep -rn "Talemate" talemate_frontend/src`. Change template text and UI
      string literals only. Leave comments, identifiers, file names, event names, and anything
      sent to the backend.
  - `mkdocs.yml`: `site_name: fantasymate documentation`.
  - `docs/index.md`, and `docs/getting-started/**`: product-name mentions in prose only. Leave
    command lines, paths and package names as they are.
- Test: `tests/e2e/theme/test_branding.py`

- [ ] **Step 1: Write the failing e2e tests.**
  - `test_title_is_fantasymate`: `page.title() == "fantasymate"`.
  - `test_wordmark_in_app_bar`: the app bar contains the text "fantasymate", and its computed
    `font-family` starts with `Alegreya`.
  - `test_no_talemate_on_home`: the home screen's `inner_text()` contains no "Talemate"
    (case-sensitive).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** For prompts sent to the AI (for example the help agent's
  templates), change the name only where the user reads it back in the UI. Leave the rest.
- [ ] **Step 4: Run them.** Expected: PASS. Run `node checks/themeColors.check.mjs`. Expected:
  PASS, which means the wordmark uses roles only. Build the docs into a temp dir
  (`mkdocs build -d "$(mktemp -d)"`), never into `site/`. Expected: success.
- [ ] **Step 5: Commit.** `git commit -m "feat(brand): show the app as fantasymate"`

### Task 11: Final pass

- [ ] **Step 1: Run every check and suite.**
  - `node checks/theme.check.mjs`
  - `node checks/themeColors.check.mjs`
  - `uv run --no-sync pytest`: the only failures should be the known NLTK ones.
  - `pytest tests/e2e -m e2e -n0`: no new failures.
  - `ruff check` and `ruff format --check` on the changed Python files.
- [ ] **Step 2: Have the owner check in the browser.** Ask the owner to open the isolated app
  and cycle through all nine presets: home, a scene, the World Editor, the node editor, Settings.
  Record anything they flag as a follow-up, or fix it now if it's a role mapping.
- [ ] **Step 3: Commit any fixes.** Then hand back for the whole-branch review.
