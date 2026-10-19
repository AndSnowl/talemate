<template>
  <div id="app">
    <TalemateApp />
  </div>
</template>

<script>
import TalemateApp from './components/TalemateApp.vue'

export default {
  name: 'App',
  components: {
    TalemateApp
  }
}
</script>

<style>
/* The configured theme's background, everywhere Vuetify doesn't already
   paint it (Vuetify's own .v-application rule already uses this var, but
   html/body still default to the browser's white before #app mounts and
   for the viewport scroll margins around it). */
html, body {
  background: rgb(var(--v-theme-background));
}
</style>