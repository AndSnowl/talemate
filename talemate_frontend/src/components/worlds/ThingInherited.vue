<template>
    <div class="thing-inherited">
        <div class="d-flex align-center mt-4 mb-1">
            <span class="text-overline text-muted">Inherited</span>
            <span class="text-caption text-muted ml-2">shown dimmed; any can be overridden</span>
        </div>
        <div v-if="!inherited.length" class="text-body-2 text-muted">Nothing inherited at this date.</div>
        <template v-for="fact in inherited" :key="fact.fact_id">
            <div class="fact d-flex align-center ga-2" :class="{ overridden: fact.overridden_by }" data-testid="inherited-fact">
                <span class="flex-grow-1 inherited-text">
                    <s v-if="fact.overridden_by"><LinkedText :segments="fact.segments" :text="fact.rendered" /></s>
                    <LinkedText v-else :segments="fact.segments" :text="fact.rendered" />
                    <span v-if="fact.overridden_by" class="replaced ml-2">replaced by its own fact</span>
                </span>
                <v-chip size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
                <v-chip
                    size="x-small"
                    variant="outlined"
                    color="link"
                    data-testid="inherited-source"
                    @click="worlds.openThing(fact.source_id)"
                >{{ fact.source_name }}</v-chip>
                <v-btn
                    v-if="!fact.overridden_by"
                    variant="text"
                    size="x-small"
                    data-testid="override-button"
                    @click="$emit('override', fact)"
                >Override</v-btn>
            </div>
            <div v-if="form && form.mode === 'override' && form.factId === fact.fact_id" class="my-2">
                <ThingFactForm :form="form" :categories="categories" :busy="busy" @save="$emit('save')" @cancel="$emit('cancel')" />
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import LinkedText from './LinkedText.vue';
import ThingFactForm from './ThingFactForm.vue';

// What a character, race or mix inherits from its heritage (`inherited`),
// dimmed, each with a chip naming (and opening) the page it comes from. An
// inherited fact can be overridden: ThingPage owns the override form, shown
// here under its fact. A fact an own fact replaces is struck through.
export default {
    name: 'ThingInherited',
    components: { LinkedText, ThingFactForm },
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
};
</script>

<style scoped>
.fact {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 2px 0;
}

.fact .v-chip,
.fact .v-btn {
    flex: none;
}

.inherited-text {
    opacity: 0.6;
}

.overridden .inherited-text {
    opacity: 0.45;
}

.replaced {
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
}
</style>
