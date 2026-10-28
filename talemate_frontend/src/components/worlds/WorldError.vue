<template>
    <!-- the one error message (polish 5): pinned in view, kept until
         closed, its text selectable and copyable -->
    <div v-if="shown" class="world-error d-flex align-start ga-2" role="alert" data-testid="world-error">
        <v-icon color="error" size="small" class="mt-1">mdi-alert-circle</v-icon>
        <span class="error-text">{{ worlds.error }}</span>
        <span v-if="worlds.errorCount > 1" class="error-count" data-testid="world-error-count">×{{ worlds.errorCount }}</span>
        <v-btn variant="text" size="x-small" :prepend-icon="copied ? 'mdi-check' : 'mdi-content-copy'" @click="copy">Copy</v-btn>
        <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Close" @click="worlds.clearError()"></v-btn>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// The worlds screens' error (`worlds.error`), at the top of the page and
// held there (sticky) however far the page is scrolled; it stays until
// closed (×) or a world is opened, a new one replaces it and the same one
// again shows "×2". The Merge dialog shows its own errors inside it.
export default {
    name: 'WorldError',
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { copied: false };
    },
    computed: {
        shown() {
            return !!this.worlds.error && !this.worlds.merge;
        },
    },
    watch: {
        'worlds.error'() {
            this.copied = false;
        },
    },
    methods: {
        async copy() {
            try {
                await navigator.clipboard.writeText(this.worlds.error || '');
                this.copied = true;
            } catch {
                // no clipboard: the text can still be selected by hand
            }
        },
    },
};
</script>

<style scoped>
/* sticky: in the page's flow at the top (covering nothing), then held
   in view under the app bar as the page scrolls */
.world-error {
    position: sticky;
    top: 72px;
    z-index: 2100;
    width: fit-content;
    margin: 0 auto 8px;
    max-width: min(760px, calc(100vw - 32px));
    padding: 8px 8px 8px 12px;
    border-radius: 6px;
    border: 1px solid rgb(var(--v-theme-error));
    background: rgb(var(--v-theme-surface));
    box-shadow: 0 4px 16px rgba(var(--v-theme-on-surface), 0.12);
}

.error-text {
    user-select: text;
    white-space: pre-wrap;
    word-break: break-word;
    padding-top: 2px;
}

.error-count {
    color: rgb(var(--v-theme-error));
    font-weight: 600;
    padding-top: 2px;
}
</style>
