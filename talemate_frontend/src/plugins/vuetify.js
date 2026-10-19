// Styles
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

// Vuetify
import { createVuetify } from 'vuetify'
import { themeFromConfig, toVuetifyColors, toVuetifyVariables } from '@/theme/engine.js'

// Seed the "fantasymate" theme from the default preset. TalemateApp's
// `effectiveAppearanceConfig` watcher (see theme/store.js's `applyTheme`)
// replaces these colours as soon as the real app config (or a live
// Settings preview) arrives.
const initialTheme = themeFromConfig();

export default createVuetify({
  theme : {
    defaultTheme: 'fantasymate',
    themes: {
      fantasymate: {
        dark: initialTheme.dark,
        colors: toVuetifyColors(initialTheme),
        variables: toVuetifyVariables(initialTheme),
      }
    }
  }
})
