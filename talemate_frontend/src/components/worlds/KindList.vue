<template>
    <div class="kind-list mt-4" data-testid="kind-list">
        <div v-if="!all.length" class="empty-hint pa-4 text-body-2">No {{ label }} yet. Describe one above to create it.</div>
        <template v-else>
            <!-- the heading, then its controls right after it (rule 1) -->
            <div class="d-flex align-center flex-wrap ga-3 mb-1">
                <span class="list-title" data-testid="kind-list-title">All {{ label }} · {{ shown.length }}</span>
                <span class="d-flex align-center ga-1">
                    <span class="text-caption text-muted">group</span>
                    <v-btn-toggle :model-value="group" mandatory density="compact" variant="outlined" divided class="toggle" @update:model-value="setGroup">
                        <v-btn v-for="option in GROUPS" :key="option.value" :value="option.value" size="x-small" :data-testid="'group-' + option.value">{{ option.title }}</v-btn>
                    </v-btn-toggle>
                </span>
                <span class="d-flex align-center ga-1">
                    <span class="text-caption text-muted">sort</span>
                    <v-btn-toggle :model-value="sort" mandatory density="compact" variant="outlined" divided class="toggle" @update:model-value="setSort">
                        <v-btn v-for="option in SORTS" :key="option.value" :value="option.value" size="x-small" :data-testid="'sort-' + option.value">{{ option.title }}</v-btn>
                    </v-btn-toggle>
                </span>
            </div>
            <div v-for="section in groups" :key="section.key" class="group">
                <div v-if="section.heading" class="group-heading" data-testid="kind-list-heading">{{ section.heading }} · {{ section.rows.length }}</div>
                <!-- one line: the name, where it is, then its summary -->
                <div
                    v-for="thing in section.rows"
                    :key="thing.id"
                    class="kind-row"
                    role="button"
                    tabindex="0"
                    data-testid="kind-list-row"
                    @click="worlds.openThing(thing.id)"
                    @keydown.enter.prevent="worlds.openThing(thing.id)"
                ><span class="row-name" :class="{ stub: thing.stub }">{{ thing.name }}</span><span v-if="whereOf(thing)" class="row-where"> · {{ whereOf(thing) }}</span><span v-if="thing.stub" class="row-where"> · not made yet</span><span v-else-if="thing.line" class="row-line"> — {{ thing.line }}</span></div>
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { kindInfo } from './worldKinds.js';
import { groupList, matchesSearch, parseSearch, searchContext, whereLabel } from './worldTree.js';

const GROUPS = [
    { value: 'where', title: 'where' },
    { value: 'tag', title: 'tag' },
    { value: 'none', title: 'none' },
];
const SORTS = [
    { value: 'name', title: 'name' },
    { value: 'recent', title: 'recent' },
    { value: 'connected', title: 'connected' },
    { value: 'date', title: 'date' },
];
const KEPT_KEY = 'fantasymate:kind-list:';

// A kind's full list, under its create box (polish 5, mockup 2, row A):
// "All places · 41", then group (where / tag / none) and sort (name /
// recent / connected / date) right after the heading, then one line per
// entry: its name, "· in Velikoye" (`whereLabel`), "— its summary" (or
// "· not made yet" for a stub), nothing at the far edge. The side
// search (`query`) filters it too. The group and sort are kept per kind
// in the browser; places start grouped by where, the rest by tag.
export default {
    name: 'KindList',
    props: {
        kind: { type: String, required: true },
        query: { type: String, default: '' },
    },
    setup() {
        return { worlds: useWorldsStore(), GROUPS, SORTS };
    },
    data() {
        return { group: 'tag', sort: 'name' };
    },
    computed: {
        label() {
            return (kindInfo(this.kind)?.label || this.kind).toLowerCase();
        },
        everything() {
            return Object.values(this.worlds.things).flat();
        },
        byId() {
            return new Map(this.everything.map((thing) => [thing.id, thing]));
        },
        all() {
            return this.worlds.things[this.kind] || [];
        },
        shown() {
            const search = parseSearch(this.query || '');
            const ctx = searchContext(this.everything);
            return this.all.filter((thing) => matchesSearch(thing, search, ctx));
        },
        groups() {
            return groupList(this.shown, { by: this.group, sort: this.sort, byId: this.byId });
        },
    },
    watch: {
        kind: {
            immediate: true,
            handler(kind) {
                const kept = this.load(kind);
                this.group = kept.group || (kind === 'place' ? 'where' : 'tag');
                this.sort = kept.sort || 'name';
            },
        },
    },
    methods: {
        whereOf(thing) {
            return whereLabel(thing, this.byId);
        },
        load(kind) {
            try {
                const kept = JSON.parse(globalThis.localStorage?.getItem(KEPT_KEY + kind) || 'null');
                return kept && typeof kept === 'object' ? kept : {};
            } catch {
                return {};
            }
        },
        keep() {
            try {
                globalThis.localStorage?.setItem(KEPT_KEY + this.kind, JSON.stringify({ group: this.group, sort: this.sort }));
            } catch {
                // storage refused: the choice lasts as long as the page
            }
        },
        setGroup(value) {
            this.group = value;
            this.keep();
        },
        setSort(value) {
            this.sort = value;
            this.keep();
        },
    },
};
</script>

<style scoped>
.list-title {
    font-weight: 600;
    color: rgb(var(--v-theme-on-surface));
}

.toggle {
    height: 24px;
}

.group-heading {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgb(var(--v-theme-muted));
    margin: 12px 0 2px;
}

.kind-row {
    padding: 3px 0;
    border-bottom: 1px dashed rgba(var(--v-theme-on-surface), 0.12);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 14px;
}

.kind-row:hover,
.kind-row:focus-visible {
    background: rgba(var(--v-theme-on-surface), 0.04);
    outline: none;
}

.row-name {
    color: rgb(var(--v-theme-link));
}

.row-name.stub {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
    text-underline-offset: 2px;
}

.row-where {
    font-size: 12px;
    color: rgb(var(--v-theme-muted));
}

.row-line {
    color: rgba(var(--v-theme-on-surface), 0.75);
}

.empty-hint {
    border: 1px dashed rgba(var(--v-theme-on-surface), 0.2);
    border-radius: 6px;
}
</style>
