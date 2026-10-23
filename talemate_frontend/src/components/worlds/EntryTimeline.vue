<template>
    <div class="entry-timeline" data-testid="entry-timeline">
        <div v-if="!lines.length" class="empty">Nothing dated yet.</div>
        <div v-for="line in lines" :key="line.fact_id" class="line" :class="{ ended: !!line.until }" data-testid="timeline-row">
            <SphereFactRow :fact-id="editable(line) ? line.fact_id : null" held-shown>
                <span class="year">{{ lineDates(worlds.calendar, line) }}</span>
                <LinkedText :segments="line.segments" />
                <span class="source text-caption">
                    <template v-if="line.here"> · here</template>
                    <template v-else> · from <LinkedText :segments="[{ text: line.owner_name, ref: line.owner_id, stub: false }]" /></template>
                    <template v-if="drawerOf(line)"> · in <a href="#" class="pointer" data-testid="line-drawer" @click.prevent="showItem(line)">{{ drawerOf(line) }}</a></template>
                </span>
                <template #actions>
                    <v-menu v-if="flags[line.fact_id]" location="bottom end">
                        <template #activator="{ props }">
                            <v-btn
                                v-bind="props"
                                variant="text"
                                size="x-small"
                                color="warning"
                                prepend-icon="mdi-alert"
                                data-testid="line-disagrees"
                                :aria-label="`Disagrees with ${others(line)}: pick one`"
                            >disagrees with {{ others(line) }}</v-btn>
                        </template>
                        <v-list density="compact" data-testid="pick-date">
                            <template v-for="other in flags[line.fact_id]" :key="other.fact_id">
                                <v-list-item
                                    v-for="choice in choices(line, other)"
                                    :key="choice.label"
                                    :title="choice.label"
                                    data-testid="pick-option"
                                    :disabled="!!worlds.pending.pick_date"
                                    @click="worlds.pickDate(choice.keep, choice.drop, choice.mode)"
                                ></v-list-item>
                            </template>
                        </v-list>
                    </v-menu>
                </template>
            </SphereFactRow>
        </div>
        <SphereFactAdd v-if="sphere" category="timeline" anchor="timeline" label="Add to the timeline" />
    </div>
</template>

<script>
import { disagreements, lineDates, useWorldsStore } from '@/stores/worlds.js';
import LinkedText from './LinkedText.vue';
import SphereFactAdd from './SphereFactAdd.vue';
import SphereFactRow from './SphereFactRow.vue';

// An entry's Timeline (curation goal 6): its dated facts in date order
// (`entry_timeline`; on a sphere page `sphere.timeline`, its undated
// timeline facts first), each with its date -- an ended one its span,
// "900–1010" (ruling C18) -- and where it's from: "here", or the entry it's
// gathered from, linked. Shown, not copied: each line lives on one entry.
// Two running lines that say much the same with different years are
// flagged ("disagrees with 217"); the flag's menu picks one, ending or
// removing the other (`pick_date`).
//
// On a sphere page (`sphere`) its own `timeline` facts are edited and
// removed here, and "+ Add to the timeline" adds one; a fact that also
// shows in a drawer is edited only there (ruling C21): its line is read
// only and points at the drawer item. Elsewhere every line is read only
// (the page's Facts edit its own).
export default {
    name: 'EntryTimeline',
    components: { LinkedText, SphereFactAdd, SphereFactRow },
    inject: { editor: { from: 'factEditor', default: null } },
    props: {
        // `[{fact_id, owner_id, owner_name, date, until, segments, here,
        // disagrees_with}]`
        lines: { type: Array, required: true },
        // a sphere page: its drawers (`sphere.drawers`), and its own
        // timeline facts editable here
        sphere: { type: Object, default: null },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        flags() {
            return disagreements(this.lines);
        },
        // a statement's fact id -> the title of the drawer it shows in
        drawerTitles() {
            const titles = {};
            for (const drawer of this.sphere?.drawers || []) {
                for (const item of drawer.items || []) {
                    if (!item.thing_id && item.fact_id) {
                        titles[item.fact_id] = drawer.title;
                    }
                }
            }
            return titles;
        },
    },
    methods: {
        lineDates,
        drawerOf(line) {
            return line.here ? this.drawerTitles[line.fact_id] || null : null;
        },
        // the page's own timeline fact, shown nowhere else
        editable(line) {
            if (!this.sphere || !line.here || this.drawerOf(line)) {
                return false;
            }
            const fact = this.editor?.ownFact(line.fact_id);
            return !!fact && fact.category === 'timeline';
        },
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
        // the drawer item it's edited in, brought into view
        showItem(line) {
            const found = document.getElementById(`sphere-item-${line.fact_id}`);
            if (found) {
                found.scrollIntoView({ block: 'center', behavior: 'smooth' });
                found.classList.add('pointed');
                setTimeout(() => found.classList.remove('pointed'), 1500);
            }
        },
    },
};
</script>

<style scoped>
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

.pointer {
    color: rgb(var(--v-theme-link));
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
