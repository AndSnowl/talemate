<template>
    <div v-if="rows.length" class="mt-3" data-testid="preview-stubs">
        <div class="heading">New stubs</div>
        <div v-for="(row, index) in rows" :key="row.name" class="stub-row" data-testid="preview-stub">
            <div class="d-flex align-center flex-wrap ga-2">
                <span class="stub-name">{{ row.name }}</span>
                <span class="text-caption text-muted">{{ line(row) }}</span>
                <SameThingAsk
                    v-if="row.same_as && row.same_as.length"
                    variant="row"
                    :name="row.name"
                    :kind="row.kind"
                    :offers="row.same_as"
                    :chosen="row.same_target_id || null"
                    @choose="$emit('update', rowChanged(rows, index, { same_target_id: $event }))"
                />
            </div>
        </div>
    </div>
</template>

<script>
import { rowChanged, useWorldsStore } from '@/stores/worlds.js';
import SameThingAsk from './SameThingAsk.vue';

// The stubs a preview would make (its `new_names`: names its facts use
// that the world hasn't), each with its kind and tag and a "same as X?"
// choice when the world may have it already (new by default: no model
// call). Changes emit `update` with the whole list.
export default {
    name: 'PreviewStubs',
    components: { SameThingAsk },
    props: {
        rows: { type: Array, required: true },
        type: { type: String, required: true },
    },
    emits: ['update'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    methods: {
        rowChanged,
        line(row) {
            if (row.same_target_id) {
                return 'no stub: it links the entry picked';
            }
            // its kind, and its tag when it has one
            const parts = [row.kind];
            if (row.tag) {
                parts.push(row.tag);
            }
            return parts.join(', ');
        },
    },
};
</script>

<style scoped>
.heading {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

.stub-row {
    padding: 2px 0;
}

.stub-name {
    font-weight: 600;
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}
</style>
