<template>
    <v-autocomplete
        v-bind="$attrs"
        :search="searchText"
        :items="items"
        :custom-filter="keep"
        item-title="name"
        item-value="id"
        @update:search="onSearch"
    >
        <template #item="{ props: itemProps, item }">
            <EntryResult v-bind="itemProps" :target="item.raw" :matched="matchedOf(item.raw)"></EntryResult>
        </template>
    </v-autocomplete>
</template>

<script>
import EntryResult from './EntryResult.vue';
import { entryMatch, searchEntries } from './nameHighlights.js';

// The entry search as an autocomplete field ("+ In…", Move, Copy and Held
// by, Within, Merge into, "Same as…"): `targets` (`referenceTargets`
// items, each place leaving out its own) searched by `searchEntries`,
// other names too, ranked as it ranks them, each drawn with
// `EntryResult`. `extras` are always listed after them (the "+ In…"
// field's "Make a new stub"). Every other attribute (v-model, label,
// density…) goes to the field; `v-model:search` is optional.
export default {
    name: 'EntryAutocomplete',
    components: { EntryResult },
    inheritAttrs: false,
    props: {
        targets: { type: Array, default: () => [] },
        extras: { type: Array, default: () => [] },
        search: { type: String, default: undefined },
    },
    emits: ['update:search'],
    data() {
        return { typed: '' };
    },
    computed: {
        searchText() {
            return this.search ?? this.typed;
        },
        query() {
            return (this.searchText || '').trim();
        },
        // the matches first, as ranked; the rest stay listed (Vuetify
        // drops them through `keep`, and needs the picked one to show it)
        items() {
            if (!this.query) {
                return [...this.targets, ...this.extras];
            }
            const found = searchEntries(this.targets, this.query, Infinity).map((result) => result.target);
            const shown = new Set(found);
            return [...found, ...this.targets.filter((target) => !shown.has(target)), ...this.extras];
        },
    },
    methods: {
        onSearch(value) {
            this.typed = value;
            this.$emit('update:search', value);
        },
        keep(value, query, item) {
            const raw = item?.raw;
            return !!raw && (this.extras.includes(raw) || entryMatch(raw, query) !== undefined);
        },
        matchedOf(raw) {
            return this.query && !this.extras.includes(raw) ? entryMatch(raw, this.query) ?? null : null;
        },
    },
};
</script>
