<template>
    <div class="entry-timeline" data-testid="entry-timeline">
        <div class="d-flex align-center flex-wrap ga-2">
            <span class="text-overline text-muted">Timeline</span>
            <v-menu location="bottom start">
                <template #activator="{ props }">
                    <v-btn v-bind="props" variant="text" size="x-small" append-icon="mdi-menu-down" data-testid="timeline-filter">{{ mode === 'events' ? 'Events only' : 'Events' }}</v-btn>
                </template>
                <v-list density="compact">
                    <v-list-item title="All dated facts" :active="mode === 'all'" data-testid="timeline-all" @click="mode = 'all'"></v-list-item>
                    <v-list-item title="Events only" :active="mode === 'events'" data-testid="timeline-events" @click="mode = 'events'"></v-list-item>
                </v-list>
            </v-menu>
            <slot name="actions"></slot>
        </div>
        <slot></slot>
        <div v-if="!shown.length" class="empty">{{ lines.length ? 'No events among them.' : 'Nothing dated yet.' }}</div>
        <div v-for="(line, index) in shown" :key="line.fact_id || 'draft-' + index" class="line d-flex align-center ga-2" :class="{ ended: !!line.until }" data-testid="timeline-row">
            <!-- disagrees with another line: a warning sign right before
                 the row, its menu the other line in full and the picks -->
            <v-menu v-if="flags[line.fact_id]" location="bottom start">
                <template #activator="{ props }">
                    <v-btn
                        v-bind="props"
                        icon="mdi-alert"
                        variant="text"
                        size="x-small"
                        density="comfortable"
                        color="warning"
                        class="flex-grow-0"
                        data-testid="line-disagrees"
                        :title="`Disagrees with ${others(line)}`"
                        :aria-label="`Disagrees with ${others(line)}: pick one`"
                    ></v-btn>
                </template>
                <v-card min-width="280" max-width="520" data-testid="pick-date">
                    <template v-for="other in flags[line.fact_id]" :key="other.fact_id">
                        <div class="disagrees-with pa-3 pb-1 text-body-2" data-testid="disagrees-with">
                            <div class="text-caption text-muted">Disagrees with</div>
                            <span class="year">{{ lineDates(worlds.calendar, other) }}</span>
                            <LinkedText :segments="other.segments" />
                        </div>
                        <v-list density="compact">
                            <v-list-item
                                v-for="choice in choices(line, other)"
                                :key="choice.label"
                                :title="choice.label"
                                data-testid="pick-option"
                                :disabled="!!worlds.pending.pick_date"
                                @click="worlds.pickDate(choice.keep, choice.drop, choice.mode)"
                            ></v-list-item>
                        </v-list>
                    </template>
                </v-card>
            </v-menu>
            <!-- the sign's room on the other rows, so the years line up -->
            <span v-else-if="anyFlag" class="flag-room flex-grow-0"></span>
            <span class="flex-grow-1">
                <span class="year">{{ lineDates(worlds.calendar, line) }}</span>
                <LinkedText :segments="line.segments" />
                <span class="source text-caption">
                    <template v-if="line.here"> · here</template>
                    <template v-else> · from <LinkedText :segments="[{ text: line.owner_name, ref: line.owner_id, stub: false }]" /></template>
                </span>
            </span>
        </div>
    </div>
</template>

<script>
import { disagreements, lineDates, useWorldsStore } from '@/stores/worlds.js';
import { timelineShown } from './entryPage.js';
import LinkedText from './LinkedText.vue';

// An entry's Timeline (curation goal 6): its dated facts in date order
// (`entry_timeline`), each with its date -- an ended one its span,
// "900–1010" (ruling C18) -- and where it's from: "here", or the entry it's
// gathered from, linked. Shown, not copied: each line lives on one entry
// (the page's Facts edit its own). "Events ▾" shows every dated fact (the
// default) or only the lines from event entries (`timelineShown`). Two
// running lines that say much the same with different years are flagged
// ("disagrees with 217"); the flag's menu picks one, ending or removing
// the other (`pick_date`). The `actions` slot holds the page's "+ Add
// event…" (its form and draft wrap onto their own line under the
// heading); the default slot anything to show above the lines.
export default {
    name: 'EntryTimeline',
    components: { LinkedText },
    props: {
        // `[{fact_id, owner_id, owner_name, date, until, segments, here,
        // disagrees_with}]`
        lines: { type: Array, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { mode: 'all' };
    },
    computed: {
        flags() {
            return disagreements(this.lines);
        },
        anyFlag() {
            return Object.keys(this.flags).length > 0;
        },
        eventIds() {
            return (this.worlds.things.event || []).map((thing) => thing.id);
        },
        shown() {
            return timelineShown(this.lines, this.mode, this.eventIds);
        },
    },
    methods: {
        lineDates,
        others(line) {
            return this.flags[line.fact_id].map((other) => lineDates(this.worlds.calendar, other)).join(', ');
        },
        // the picks between `line` and `other`: keep one, end or remove
        // the other
        choices(line, other) {
            const theirs = lineDates(this.worlds.calendar, other);
            return [
                { label: `Keep ${theirs}, end this one`, keep: other.fact_id, drop: line.fact_id, mode: 'end' },
                { label: `Keep ${theirs}, remove this one`, keep: other.fact_id, drop: line.fact_id, mode: 'remove' },
                { label: `Keep this one, end ${theirs}`, keep: line.fact_id, drop: other.fact_id, mode: 'end' },
                { label: `Keep this one, remove ${theirs}`, keep: line.fact_id, drop: other.fact_id, mode: 'remove' },
            ];
        },
    },
};
</script>

<style scoped>
/* an x-small icon button's width (comfortable density) */
.flag-room {
    width: 28px;
}

.line {
    margin: 3px 0;
    line-height: 1.5;
}

.line.ended {
    opacity: 0.75;
}

.year {
    flex: none;
    display: inline-block;
    margin-right: 8px;
    min-width: 48px;
    font-variant-numeric: tabular-nums;
    color: rgb(var(--v-theme-date));
}

.source {
    color: rgb(var(--v-theme-muted));
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
