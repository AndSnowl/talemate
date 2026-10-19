import { createApp } from 'vue'
import App from './App.vue'
import vuetify from './plugins/vuetify'
import { loadFonts } from './plugins/webfontloader'

// The fantasymate wordmark font (see FmWordmark.vue). Bundled so the app
// works offline.
import '@fontsource/alegreya/700.css'

loadFonts()

createApp(App)
  .use(vuetify)
  .mount('#app')
