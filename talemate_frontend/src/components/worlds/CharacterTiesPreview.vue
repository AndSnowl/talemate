<template>
    <div v-if="preview.ties && preview.ties.length" class="character-ties-preview">
        <div class="text-caption text-muted text-uppercase mt-3">Ties</div>
        <div v-for="(tie, tieIndex) in preview.ties" :key="tie.sphere_id + tieIndex" class="preview-tie" data-testid="preview-tie">
            <div class="d-flex align-center ga-1">
                <span class="flex-grow-1">{{ tieLead(tie.role) }} <span class="tie-sphere">{{ tie.sphere }}</span><span v-if="tie.since" class="text-muted"> · since {{ formatDate(worlds.calendar, tie.since) }}</span></span>
                <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Drop tie" @click="worlds.dropPreviewTie(tieIndex)"></v-btn>
            </div>
            <template v-if="tie.exceptions.length">
                <div class="but"><i>but…</i></div>
                <div v-for="(exception, index) in tie.exceptions" :key="index" class="but d-flex align-center ga-1" data-testid="preview-tie-exception">
                    <span class="flex-grow-1">
                        – <LinkedText :segments="previewSegments(exception.text, preview.new_names)" :text="exception.text" />
                        <span class="text-muted"> (departs from {{ exception.item }})</span>
                    </span>
                    <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Drop exception" @click="worlds.dropPreviewException(tieIndex, index)"></v-btn>
                </div>
            </template>
            <div v-else class="but text-muted">no exceptions</div>
        </div>
    </div>
</template>

<script>
import { previewSegments, useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';
import { tieLead } from './worldKinds.js';
import LinkedText from './LinkedText.vue';

// A character preview's proposed ties to spheres already in the world:
// each with its role, sphere and date, and its "but…" exceptions (each
// with the item it departs from). The owner can drop a whole tie or one
// exception before accepting (`worlds.dropPreviewTie`,
// `dropPreviewException`), so a tie that no longer fits never blocks the
// accept.
export default {
    name: 'CharacterTiesPreview',
    components: { LinkedText },
    props: {
        // the store's preview (`CreatePreview`)
        preview: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    methods: { formatDate, previewSegments, tieLead },
};
</script>

<style scoped>
.preview-tie {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    padding: 6px 10px;
    margin: 6px 0;
}

.preview-tie .v-btn {
    flex: none;
}

.tie-sphere {
    color: rgb(var(--v-theme-link));
}

.but {
    margin: 2px 0 0 14px;
}
</style>
