<template>
    <div class="thing-inherited">
        <div class="d-flex align-center mt-4 mb-1">
            <span class="text-overline text-muted">Inherited</span>
            <span class="text-caption text-muted ml-2">shown dimmed; any can be overridden</span>
        </div>
        <div v-if="!inherited.length" class="text-body-2 text-muted">Nothing inherited at this date.</div>
        <template v-for="fact in inherited" :key="fact.fact_id">
            <div class="inherited-row" :class="{ overridden: fact.overridden_by }" data-testid="inherited-fact">
                <FactLine
                    :fact="lineOf(fact)"
                    :actions="fact.overridden_by ? 'none' : 'override'"
                    :dropped="!!fact.overridden_by"
                    text-class="inherited-text"
                    @override="$emit('override', fact)"
                >
                    <!-- its source chip after its words, keeping its
                         category and dates in a page fact's places -->
                    <template #notes>
                        <v-chip
                            size="x-small"
                            variant="outlined"
                            color="link"
                            class="inherited-source ml-2"
                            data-testid="inherited-source"
                            @click="worlds.openThing(fact.source_id)"
                        >{{ fact.source_name }}</v-chip>
                        <span v-if="fact.overridden_by" class="replaced ml-2">replaced by its own fact</span>
                    </template>
                </FactLine>
            </div>
            <div v-if="form && form.mode === 'override' && form.factId === fact.fact_id" class="my-2">
                <ThingFactForm :form="form" :categories="categories" :busy="busy" @save="$emit('save')" @cancel="$emit('cancel')" />
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import FactLine from './FactLine.vue';
import ThingFactForm from './ThingFactForm.vue';

// What a character, race or mix inherits from its heritage (`inherited`),
// each drawn as an own fact is (`FactLine`: its words, here dimmed, then
// its category and dates in the same places), with a chip naming (and
// opening) the page it comes from after its words and an "Override"
// button where an own fact's buttons are. ThingPage owns the override
// form, shown here under its fact. A fact an own fact replaces is struck
// through, with no Override.
export default {
    name: 'ThingInherited',
    components: { FactLine, ThingFactForm },
    props: {
        inherited: { type: Array, required: true },
        // ThingPage's open fact form, or null
        form: { type: Object, default: null },
        categories: { type: Array, required: true },
        busy: { type: Boolean, default: false },
    },
    emits: ['override', 'save', 'cancel'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    methods: {
        // the fact as the fact line takes it
        lineOf(fact) {
            return { ...fact, text: fact.rendered };
        },
    },
};
</script>

<style scoped>
.inherited-row {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

/* dimmed, all but its source chip */
.inherited-row :deep(.inherited-text > :not(.inherited-source)) {
    opacity: 0.6;
}

.inherited-row.overridden :deep(.inherited-text > :not(.inherited-source)) {
    opacity: 0.45;
}

.replaced {
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
}
</style>
