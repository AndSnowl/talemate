<template>
    <!-- one entry found by a search: its name (a stub's in the stub
         style), the other name that matched small and dim under it, then
         its kind, or the picker's own line -->
    <v-list-item data-testid="entry-result" v-bind="$attrs">
        <v-list-item-title :class="{ 'stub-name': target.stub }">{{ target.name }}</v-list-item-title>
        <div v-if="matched" class="entry-matched" data-testid="entry-matched">{{ matched }}</div>
        <v-list-item-subtitle v-if="line">{{ line }}</v-list-item-subtitle>
    </v-list-item>
</template>

<script>
import { kindInfo } from './worldKinds.js';

// The one result row of every entry search (`searchEntries`): the
// selection's "Link to an entry…", "+ In…", Move, Copy and Held by, Merge
// into and "Same as…". `target` is a `referenceTargets` item, or one
// shaped like it; `subtitle` (on the target or as a prop) replaces the
// kind line. Vuetify's item props pass through; its `title` is dropped,
// since the name is drawn here.
export default {
    name: 'EntryResult',
    inheritAttrs: false,
    props: {
        target: { type: Object, required: true },
        // the other name that matched, or null when its own name did
        matched: { type: String, default: null },
        subtitle: { type: String, default: null },
        // Vuetify's item title, drawn here instead
        title: { type: [String, Number], default: null },
    },
    computed: {
        line() {
            const own = this.subtitle ?? this.target.subtitle;
            if (own != null) {
                return own;
            }
            if (!this.target.kind) {
                return '';
            }
            const kind = kindInfo(this.target.kind)?.singular || this.target.kind;
            return this.target.stub ? `${kind} · stub` : kind;
        },
    },
};
</script>

<style scoped>
.entry-matched {
    font-size: 0.75rem;
    line-height: 1.1rem;
    color: rgb(var(--v-theme-muted));
}

.stub-name {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
    text-underline-offset: 2px;
}
</style>
