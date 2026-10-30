<template>
    <v-menu
        :model-value="modelValue"
        :target="target"
        location="bottom start"
        :close-on-content-click="false"
        @update:model-value="$emit('update:modelValue', $event)"
    >
        <v-card class="reference-menu" min-width="250" data-testid="reference-menu">
            <LanguageNameMenu
                v-if="mode"
                :mode="mode"
                :thing-id="contextThingId"
                :kind="contextKind || 'place'"
                :selected="selectedText"
                :scene="contextScene"
                @insert="insert"
                @done="$emit('update:modelValue', false)"
            />
            <v-list v-else-if="!searching" density="compact">
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
                <v-list-item v-if="references" prepend-icon="mdi-link-variant" title="Add reference…" @click="searching = true"></v-list-item>
                <template v-if="languageNaming">
                    <v-divider></v-divider>
                    <!-- rework a language to fit the entry this box is on -->
                    <v-list-item
                        v-if="contextThingId && contextKind !== 'language'"
                        prepend-icon="mdi-auto-fix"
                        title="Change a language to fit this…"
                        data-testid="menu-change-language"
                        @click="changeLanguage"
                    ></v-list-item>
                    <v-list-item v-if="!hasSelection" prepend-icon="mdi-alphabetical-variant" title="Make a name…" data-testid="menu-make-name" @click="mode = 'name'"></v-list-item>
                    <v-list-item prepend-icon="mdi-format-quote-open" title="Make a phrase…" data-testid="menu-make-phrase" @click="mode = 'phrase'"></v-list-item>
                    <template v-if="hasSelection && selectedText.trim()">
                        <v-list-item prepend-icon="mdi-book-plus-outline" :title="`Add &quot;${selectedText.trim()}&quot; to a language…`" data-testid="menu-add-word" @click="mode = 'word'"></v-list-item>
                        <v-list-item prepend-icon="mdi-dice-multiple-outline" title="Reroll this part…" data-testid="menu-reroll-part" @click="mode = 'reroll'"></v-list-item>
                    </template>
                </template>
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
import LanguageNameMenu from './LanguageNameMenu.vue';
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
    components: { EntryResult, LanguageNameMenu },
    props: {
        modelValue: { type: Boolean, default: false },
        target: { type: [Array, Object, String], default: null },
        searchOnly: { type: Boolean, default: false },
        hasSelection: { type: Boolean, default: false },
        // thing ids never offered (the thing whose fact it is, the link's own)
        exclude: { type: Array, default: () => [] },
        searchLabel: { type: String, default: 'Find an entry or stub' },
        // right-click naming from a language (languages 3a): the page the
        // box is on (its languages are in reach), the kind names are
        // rolled for, and the selection the menu opened with
        languageNaming: { type: Boolean, default: false },
        contextThingId: { type: String, default: null },
        contextKind: { type: String, default: null },
        selectedText: { type: String, default: '' },
        // a scene's message box: the languages in reach are the scene's
        contextScene: { type: Boolean, default: false },
        // false where a box takes no references (a scene's message)
        references: { type: Boolean, default: true },
    },
    emits: ['update:modelValue', 'cut', 'copy', 'paste', 'delete', 'undo', 'redo', 'selectAll', 'pick', 'insert'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { searching: this.searchOnly, query: '', mode: null };
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
                this.mode = null;
            }
        },
    },
    methods: {
        changeLanguage() {
            this.worlds.openLanguageChange({ originId: this.contextThingId });
            this.$emit('update:modelValue', false);
        },
        act(action) {
            this.$emit(action);
            this.$emit('update:modelValue', false);
        },
        insert(text) {
            this.$emit('insert', text);
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
