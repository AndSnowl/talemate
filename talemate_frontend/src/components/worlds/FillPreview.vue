<template>
    <div class="fill-preview mt-2 pa-2" data-testid="fill-preview">
        <v-progress-linear v-if="fill.pending" indeterminate color="accent"></v-progress-linear>
        <v-alert v-else-if="fill.error" type="error" variant="tonal" density="compact">{{ fill.error }}</v-alert>
        <template v-else>
            <div v-if="!fill.items.length" class="text-body-2 text-muted">Nothing new to add.</div>
            <div v-for="row in ownItems" :key="row.index" class="fill-item" data-testid="fill-item">
                <div class="d-flex align-center flex-wrap ga-2">
                    <v-checkbox-btn
                        :model-value="row.item.ticked !== false"
                        density="compact"
                        class="flex-grow-0"
                        :aria-label="'Keep ' + (row.item.name || row.item.text)"
                        @update:model-value="changeItem(row.index, { ticked: $event })"
                    ></v-checkbox-btn>
                    <span class="flex-grow-1" :class="{ dropped: row.item.ticked === false }">
                        <template v-if="row.item.name"><LinkedText :segments="nameSegments(row.item)" :text="row.item.name" /><span class="text-muted"> — </span></template>
                        <LinkedText :segments="previewSegments(row.item.text, row.item.names || [])" :text="row.item.text" />
                        <span v-if="row.item.held_by_name" class="held" data-testid="held-by-tag">held by {{ row.item.held_by_name }}</span>
                    </span>
                    <SameThingAsk
                        v-if="row.item.same_as && row.item.same_as.length"
                        variant="row"
                        :name="row.item.name"
                        :offers="row.item.same_as"
                        :chosen="row.item.same_target_id || null"
                        @choose="changeItem(row.index, { same_target_id: $event })"
                    />
                </div>
                <div v-if="row.item.repeat_of" class="match text-caption" data-testid="fact-match">≈ on {{ row.item.repeat_of.owner_name || 'the sphere' }}: {{ row.item.repeat_of.text }}</div>
                <OuterBodyForm
                    v-if="row.item.name && !row.item.thing_id && !row.item.same_target_id"
                    :row-name="row.item.name"
                    @submit="worlds.addOuterBody('fill', row.item.name, $event)"
                />
            </div>
            <PreviewRepeats :rows="repeatRows" @tick="(index, ticked) => changeItem(index, { ticked })" />
            <PreviewElsewhere :rows="fill.elsewhere || []" type="fill" @update="worlds.editPreview('fill', { elsewhere: $event })" />
            <PreviewStubs :rows="fill.new_names || []" type="fill" @update="worlds.editPreview('fill', { new_names: $event })" />
            <MoveInSection :refile="fill.refile || []" @update-refile="worlds.editPreview('fill', { refile: $event })" />
        </template>
        <div class="d-flex align-center flex-wrap ga-2 mt-2">
            <v-btn
                color="accent"
                variant="flat"
                size="small"
                prepend-icon="mdi-check"
                :disabled="!fill.items || !anything || !!worlds.pending.add_outer_body"
                :loading="!!worlds.pending.accept_fill"
                @click="worlds.acceptFill()"
            >Accept</v-btn>
            <v-btn variant="outlined" size="small" :disabled="!!worlds.pending.accept_fill" @click="worlds.discardFill()">Discard</v-btn>
            <span v-if="fill.items" class="text-caption text-muted" data-testid="accept-counts">{{ countsText }}</span>
        </div>
    </div>
</template>

<script>
import { countsLine, previewCounts, previewSegments, rowChanged, useWorldsStore } from '@/stores/worlds.js';
import LinkedText from './LinkedText.vue';
import MoveInSection from './MoveInSection.vue';
import OuterBodyForm from './OuterBodyForm.vue';
import PreviewElsewhere from './PreviewElsewhere.vue';
import PreviewRepeats from './PreviewRepeats.vue';
import PreviewStubs from './PreviewStubs.vue';
import SameThingAsk from './SameThingAsk.vue';

// Fill's reply for one drawer (`worlds.fill`, the Fill preview): its
// items, each ticked as it came (names a new stub would get shown as
// such; a named one the world may have already asks "same as X?", and can
// be put in a body not yet made); the items that repeat one the sphere
// holds, under "Already in the world"; the facts it wrote about other
// entries; the outer bodies and re-file rows. Every tick is the store's
// (`worlds.editPreview('fill', ...)`); Accept writes the preview as the
// owner left it, Discard drops it all.
export default {
    name: 'FillPreview',
    components: { LinkedText, MoveInSection, OuterBodyForm, PreviewElsewhere, PreviewRepeats, PreviewStubs, SameThingAsk },
    props: {
        // `{pending, items, elsewhere, new_names, refile, error}`
        fill: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        rows() {
            return (this.fill.items || []).map((item, index) => ({ index, item }));
        },
        // the items that didn't come unticked as repeats (`fill.shelved`:
        // those show under "Already in the world")
        ownItems() {
            const shelved = this.fill.shelved || [];
            return this.rows.filter((row) => !shelved.includes(row.index));
        },
        repeatRows() {
            const shelved = this.fill.shelved || [];
            return this.rows
                .filter((row) => shelved.includes(row.index))
                .map((row) => ({ index: row.index, text: row.item.name ? `${row.item.name} — ${row.item.text}` : row.item.text, ticked: row.item.ticked, repeat_of: row.item.repeat_of }));
        },
        counts() {
            return previewCounts({ items: this.fill.items, elsewhere: this.fill.elsewhere, new_names: this.fill.new_names, refile: this.fill.refile });
        },
        countsText() {
            return countsLine(this.counts, null, 'item');
        },
        // something to write
        anything() {
            return this.counts.here + this.counts.elsewhere + this.counts.refiled > 0;
        },
    },
    methods: {
        previewSegments,
        changeItem(index, changes) {
            this.worlds.editPreview('fill', { items: rowChanged(this.fill.items, index, changes) });
        },
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
    color: rgb(var(--v-theme-muted));
}

.match {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}

.held {
    margin-left: 6px;
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}
</style>
