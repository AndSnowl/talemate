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
            <OuterBodyForm v-if="!row.same_target_id" :row-name="row.name" @submit="worlds.addOuterBody(type, row.name, $event)" />
        </div>
    </div>
</template>

<script>
import { rowChanged, useWorldsStore } from '@/stores/worlds.js';
import OuterBodyForm from './OuterBodyForm.vue';
import SameThingAsk from './SameThingAsk.vue';

// The stubs a preview would make (its `new_names`: names its facts use
// that the world hasn't, and the outer bodies the owner named), each with
// its kind and where it's filed, a "same as X?" choice when the world may
// have it already (new by default: no model call), and "Part of a body
// not yet made…". Changes emit `update` with the whole list.
export default {
    name: 'PreviewStubs',
    components: { OuterBodyForm, SameThingAsk },
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
            const kind = row.kind === 'sphere' && row.template ? `${row.template} sphere` : row.kind;
            const parts = [kind];
            const home = row.part_of;
            if (home?.name) {
                parts.push(`part of ${home.name}`);
            } else if (home?.sphere) {
                const sphere = this.worlds.referenceTargets.find((target) => target.id === home.sphere);
                const drawers = this.worlds.sphereInfo[home.sphere]?.sphere?.drawers || [];
                const drawer = drawers.find((d) => d.id === home.drawer)?.title;
                parts.push(`part of ${sphere?.name || 'a sphere'}${drawer ? ` — ${drawer}` : ''}`);
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
