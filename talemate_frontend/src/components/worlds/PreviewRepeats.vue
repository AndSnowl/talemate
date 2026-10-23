<template>
    <div v-if="rows.length" class="preview-repeats mt-2" data-testid="preview-repeats">
        <div class="d-flex align-center ga-1">
            <v-btn
                variant="text"
                size="x-small"
                class="heading-btn px-1"
                :prepend-icon="open ? 'mdi-chevron-down' : 'mdi-chevron-right'"
                :aria-expanded="open"
                @click="open = !open"
            >Already in the world</v-btn>
            <span class="text-caption text-muted">({{ tickedCount }} of {{ rows.length }} ticked; not written unless you tick it)</span>
        </div>
        <template v-if="open">
            <div v-for="row in rows" :key="row.index" class="repeat" data-testid="repeat-row">
                <div class="d-flex align-center ga-2">
                    <v-checkbox-btn
                        :model-value="row.ticked !== false"
                        density="compact"
                        class="flex-grow-0"
                        :aria-label="'Write ' + row.text"
                        @update:model-value="$emit('tick', row.index, $event)"
                    ></v-checkbox-btn>
                    <span :class="{ dropped: row.ticked === false }">{{ row.text }}</span>
                </div>
                <div class="match text-caption">≈ on {{ row.repeat_of.owner_name || 'an entry' }}: {{ row.repeat_of.text }}</div>
            </div>
        </template>
    </div>
</template>

<script>
// "Already in the world" (curation goal 3): a preview's facts (or Fill's
// items) that repeat one the world holds, each with its match ("≈ on
// <entry>: <text>"). They come as the server ticked them -- unticked only
// when they're near copies -- and the owner can tick any back in. The
// section starts collapsed when every row in it is unticked. `rows` are
// `{index, text, ticked, repeat_of}` (`index` into the preview's list);
// a tick emits `tick(index, ticked)`.
export default {
    name: 'PreviewRepeats',
    props: {
        rows: { type: Array, required: true },
    },
    emits: ['tick'],
    data() {
        return { open: this.rows.some((row) => row.ticked !== false) };
    },
    computed: {
        tickedCount() {
            return this.rows.filter((row) => row.ticked !== false).length;
        },
    },
};
</script>

<style scoped>
.heading-btn {
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgb(var(--v-theme-muted));
}

.repeat {
    padding: 2px 0;
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

.match {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}

.dropped {
    color: rgb(var(--v-theme-muted));
}
</style>
