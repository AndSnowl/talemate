<template>
    <div class="sphere-timeline" data-testid="sphere-timeline">
        <div v-if="!timeline.length" class="empty">Nothing dated yet. Add a timeline fact to start it.</div>
        <div v-for="entry in timeline" :key="entry.fact_id" class="row d-flex ga-2">
            <span class="year">{{ entry.date ? formatDate(worlds.calendar, entry.date) : '—' }}</span>
            <span class="flex-grow-1"><LinkedText :segments="entry.segments" /></span>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';
import LinkedText from './LinkedText.vue';

// A sphere's Timeline: its dated facts in date order (undated first, as
// the backend gives them), each with its date, its names linked.
export default {
    name: 'SphereTimeline',
    components: { LinkedText },
    props: {
        // the sphere payload's `timeline`: `[{fact_id, date, segments}]`
        timeline: { type: Array, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    methods: { formatDate },
};
</script>

<style scoped>
.row {
    margin: 3px 0;
    line-height: 1.5;
}

.year {
    flex: none;
    min-width: 48px;
    font-variant-numeric: tabular-nums;
    color: rgb(var(--v-theme-date));
}

.empty {
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
    padding: 6px 10px;
    margin-top: 4px;
    font-size: 13px;
    color: rgb(var(--v-theme-muted));
}
</style>
