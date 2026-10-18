// The app's single "fantasymate" Vuetify theme: live state plus the
// function that pushes a resolved theme (see engine.js) into Vuetify's
// runtime theme object.

import { shallowRef } from 'vue';
import { themeFromConfig, toVuetifyColors } from './engine.js';

/** The currently-applied resolved theme (see engine.js's `themeFromConfig`). */
export const currentTheme = shallowRef(themeFromConfig());

/**
 * Push `resolved` into Vuetify's live "fantasymate" theme (a raw theme
 * instance — `useTheme()`'s return value, or the vuetify plugin's own
 * `.theme`; NOT `this.$vuetify.theme`, which Vuetify wraps in `reactive()`
 * and which therefore auto-unwraps `.themes` to its value, breaking
 * `.themes.value`), and record it as the current theme.
 */
export function applyTheme(vuetifyTheme, resolved) {
    const theme = vuetifyTheme.themes.value.fantasymate;
    theme.dark = resolved.dark;
    theme.colors = toVuetifyColors(resolved);
    currentTheme.value = resolved;
}
