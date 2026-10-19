<template>
  <span class="fm-wordmark" :class="'fm-wordmark--' + size">fantasymate</span>
</template>

<script>
// The fantasymate wordmark: lower-case product name, Alegreya Bold,
// coloured with the `link` theme role (never a hard-coded colour — see
// talemate_frontend/checks/themeColors.check.mjs).
export default {
  name: 'FmWordmark',
  props: {
    // 'sm' (20px) for the app bar, 'lg' (72px) for the empty-state backdrop.
    size: {
      type: String,
      default: 'sm',
      validator: (value) => ['sm', 'lg'].includes(value),
    },
  },
};
</script>

<style scoped>
.fm-wordmark {
  font-family: 'Alegreya', serif;
  font-weight: 700;
  color: rgb(var(--v-theme-link));
  white-space: nowrap;
  line-height: 1;
}

.fm-wordmark--sm {
  font-size: 20px;
}

.fm-wordmark--lg {
  font-size: 72px;
}
</style>
