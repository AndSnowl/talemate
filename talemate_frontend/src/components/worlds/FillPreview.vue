<template>
    <div class="fill-preview mt-2 pa-2" data-testid="fill-preview">
        <v-progress-linear v-if="fill.pending" indeterminate color="accent"></v-progress-linear>
        <v-alert v-else-if="fill.error" type="error" variant="tonal" density="compact">{{ fill.error }}</v-alert>
        <template v-else>
            <div v-if="!fill.items.length" class="text-body-2 text-muted">Nothing new to add.</div>
            <div v-for="(item, index) in fill.items" :key="index" class="d-flex align-center ga-2" data-testid="fill-item">
                <v-checkbox-btn v-model="kept[index]" density="compact" class="flex-grow-0" :aria-label="'Keep ' + (item.name || item.text)"></v-checkbox-btn>
                <span :class="{ dropped: !kept[index] }">
                    <template v-if="item.name"><LinkedText :segments="nameSegments(item)" :text="item.name" /><span class="text-muted"> — </span></template>
                    <LinkedText :segments="previewSegments(item.text, item.names || [])" :text="item.text" />
                </span>
            </div>
        </template>
        <div class="d-flex ga-2 mt-2">
            <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-check" :disabled="!fill.items || !keptItems.length" :loading="!!worlds.pending.accept_fill" @click="worlds.acceptFill(keptItems)">Accept</v-btn>
            <v-btn variant="outlined" size="small" :disabled="!!worlds.pending.accept_fill" @click="worlds.discardFill()">Discard</v-btn>
        </div>
    </div>
</template>

<script>
import { previewSegments, useWorldsStore } from '@/stores/worlds.js';
import LinkedText from './LinkedText.vue';

// Fill's reply for one drawer (`worlds.fill`): its items, each kept
// unless unticked, names a new stub would get shown as such; Accept writes
// the kept ones as given, Discard drops them all.
export default {
    name: 'FillPreview',
    components: { LinkedText },
    props: {
        // `{pending, items, error}`
        fill: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { kept: (this.fill.items || []).map(() => true) };
    },
    computed: {
        keptItems() {
            return (this.fill.items || []).filter((_item, index) => this.kept[index]);
        },
    },
    watch: {
        // a new reply: every item kept
        'fill.items'(items) {
            this.kept = (items || []).map(() => true);
        },
    },
    methods: {
        previewSegments,
        // a named item becomes a stub (or links the one it names)
        nameSegments(item) {
            return previewSegments(item.name, [{ name: item.name, kind: item.kind }]);
        },
    },
};
</script>

<style scoped>
.fill-preview {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
}

.dropped {
    text-decoration: line-through;
    color: rgb(var(--v-theme-muted));
}
</style>
