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
                <v-divider></v-divider>
                <v-list-item prepend-icon="mdi-link-variant" title="Add reference…" @click="searching = true"></v-list-item>
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
                    @keydown.enter.prevent="results.length && pick(results[0])"
                ></v-text-field>
                <v-list density="compact" class="results">
                    <v-list-item v-for="target in results" :key="target.id" data-testid="reference-result" @click="pick(target)">
                        <v-list-item-title :class="{ 'stub-name': target.stub }">{{ target.name }}</v-list-item-title>
                        <template #append>
                            <v-chip size="x-small" label variant="tonal" color="muted" class="ml-2">{{ kindLabel(target.kind) }}</v-chip>
                            <v-chip v-if="target.stub" size="x-small" label variant="tonal" color="foreign" class="ml-1">stub</v-chip>
                        </template>
                    </v-list-item>
                    <v-list-item v-if="query.trim() && !results.length" disabled title="Nothing by that name"></v-list-item>
                </v-list>
            </div>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { searchReferences } from './nameHighlights.js';
import { kindInfo } from './worldKinds.js';

// The right-click menu of a text box the owner writes in
// (`NameHighlightInput`): the browser's Cut, Copy and Paste, which it
// emits for the box to do, and "Add reference…", which turns the menu into
// a search over the world's entries and live stubs
// (`worlds.referenceTargets`) and emits the thing picked. `searchOnly`
// opens straight on the search (re-pointing a link, from `LinkedText`).
// Shown at `target`, a point (`[x, y]`) or an element.
export default {
    name: 'ReferenceMenu',
    props: {
        modelValue: { type: Boolean, default: false },
        target: { type: [Array, Object, String], default: null },
        searchOnly: { type: Boolean, default: false },
        hasSelection: { type: Boolean, default: false },
        // thing ids never offered (the thing whose fact it is, the link's own)
        exclude: { type: Array, default: () => [] },
        searchLabel: { type: String, default: 'Find an entry or stub' },
    },
    emits: ['update:modelValue', 'cut', 'copy', 'paste', 'pick'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { searching: this.searchOnly, query: '' };
    },
    computed: {
        results() {
            const targets = this.worlds.referenceTargets.filter((target) => !this.exclude.includes(target.id));
            return searchReferences(targets, this.query);
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
        kindLabel(kind) {
            return kindInfo(kind)?.singular || kind;
        },
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

.stub-name {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
    text-underline-offset: 2px;
}
</style>
