<template>
    <v-menu
        :model-value="modelValue"
        :target="target"
        location="bottom start"
        :close-on-content-click="false"
        @update:model-value="$emit('update:modelValue', $event)"
    >
        <v-card class="reference-menu" min-width="250" data-testid="reference-menu">
            <v-list v-if="!searching" density="compact">
                <v-list-item prepend-icon="mdi-content-cut" title="Cut" :disabled="!hasSelection" @click="act('cut')"></v-list-item>
                <v-list-item prepend-icon="mdi-content-copy" title="Copy" :disabled="!hasSelection" @click="act('copy')"></v-list-item>
                <v-list-item prepend-icon="mdi-content-paste" title="Paste" @click="act('paste')"></v-list-item>
                <v-list-item prepend-icon="mdi-delete-outline" title="Delete" :disabled="!hasSelection" @click="act('delete')"></v-list-item>
                <v-divider></v-divider>
                <v-list-item prepend-icon="mdi-undo" title="Undo" @click="act('undo')"></v-list-item>
                <v-list-item prepend-icon="mdi-redo" title="Redo" @click="act('redo')"></v-list-item>
                <v-divider></v-divider>
                <v-list-item prepend-icon="mdi-select-all" title="Select all" @click="act('selectAll')"></v-list-item>
                <v-divider></v-divider>
                <v-list-item prepend-icon="mdi-link-variant" title="Add reference…" @click="searching = true"></v-list-item>
                <v-divider></v-divider>
                <div class="px-4 py-2 text-caption text-muted" data-testid="spell-check-hint">Spell check: Shift+right-click</div>
            </v-list>
            <div v-else class="pa-2" data-testid="reference-search">
                <v-text-field
                    v-model="query"
                    :label="searchLabel"
                    prepend-inner-icon="mdi-magnify"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    @keydown.enter.prevent="results.length && pick(results[0].target)"
                ></v-text-field>
                <v-list density="compact" class="results">
                    <EntryResult
                        v-for="result in results"
                        :key="result.target.id"
                        :target="result.target"
                        :matched="result.matched"
                        data-testid="reference-result"
                        @click="pick(result.target)"
                    ></EntryResult>
                    <v-list-item v-if="query.trim() && !results.length" disabled title="Nothing by that name"></v-list-item>
                </v-list>
            </div>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import EntryResult from './EntryResult.vue';
import { searchEntries } from './nameHighlights.js';

// The right-click menu of a text box the owner writes in
// (`NameHighlightInput`): the browser's Cut, Copy, Paste and Delete, Undo
// and Redo, Select all, which it emits for the box to do, and "Add
// reference…", which turns the menu into a search over the world's
// entries and live stubs (`worlds.referenceTargets`) and emits the thing
// picked. `searchOnly` opens straight on the search (re-pointing a link,
// from `LinkedText`). A last muted line points to the browser's own menu
// (Shift+right-click), since browsers give scripts no spell-check API.
// Shown at `target`, a point (`[x, y]`) or an element.
export default {
    name: 'ReferenceMenu',
    components: { EntryResult },
    props: {
        modelValue: { type: Boolean, default: false },
        target: { type: [Array, Object, String], default: null },
        searchOnly: { type: Boolean, default: false },
        hasSelection: { type: Boolean, default: false },
        // thing ids never offered (the thing whose fact it is, the link's own)
        exclude: { type: Array, default: () => [] },
        searchLabel: { type: String, default: 'Find an entry or stub' },
    },
    emits: ['update:modelValue', 'cut', 'copy', 'paste', 'delete', 'undo', 'redo', 'selectAll', 'pick'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { searching: this.searchOnly, query: '' };
    },
    computed: {
        results() {
            const targets = this.worlds.referenceTargets.filter((target) => !this.exclude.includes(target.id));
            return searchEntries(targets, this.query);
        },
    },
    watch: {
        modelValue(open) {
            if (open) {
                this.searching = this.searchOnly;
                this.query = '';
            }
        },
    },
    methods: {
        act(action) {
            this.$emit(action);
            this.$emit('update:modelValue', false);
        },
        pick(target) {
            this.$emit('pick', target);
            this.$emit('update:modelValue', false);
        },
    },
};
</script>

<style scoped>
.reference-menu {
    background: rgb(var(--v-theme-raised));
}

.results {
    max-height: 260px;
    overflow-y: auto;
    background: transparent;
}
</style>
