<template>
    <div class="sphere-timeline" data-testid="sphere-timeline">
        <div v-if="!timeline.length" class="empty">Nothing dated yet.</div>
        <SphereFactRow v-for="entry in timeline" :key="entry.fact_id" :fact-id="entry.fact_id" class="row" data-testid="timeline-row">
            <span class="year">{{ entry.date ? formatDate(worlds.calendar, entry.date) : '—' }}</span>
            <LinkedText :segments="entry.segments" />
        </SphereFactRow>
        <SphereFactAdd category="timeline" anchor="timeline" label="Add to the timeline" />
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';
import LinkedText from './LinkedText.vue';
import SphereFactAdd from './SphereFactAdd.vue';
import SphereFactRow from './SphereFactRow.vue';

// A sphere's Timeline: its dated facts in date order (undated first, as
// the backend gives them), each with its date, its names linked. Its own
// rows can be edited and removed, and "+ Add to the timeline" adds one (a
// `timeline` fact with a year); a branch's rows from its parent are read
// only.
export default {
    name: 'SphereTimeline',
    components: { LinkedText, SphereFactAdd, SphereFactRow },
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
    display: inline-block;
    margin-right: 8px;
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
