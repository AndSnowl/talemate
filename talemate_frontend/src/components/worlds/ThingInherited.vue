<template>
    <div class="thing-inherited">
        <div class="d-flex align-center mt-4 mb-1">
            <span class="text-overline text-muted">Inherited</span>
            <span class="text-caption text-muted ml-2">shown dimmed; any can be overridden</span>
        </div>
        <div v-if="!inherited.length" class="text-body-2 text-muted">Nothing inherited at this date.</div>
        <template v-for="fact in inherited" :key="fact.fact_id">
            <div class="inherited-row" data-testid="inherited-fact">
                <InheritedLine
                    :fact="fact"
                    :actions="fact.overridden_by ? 'none' : 'override'"
                    :overridden="!!fact.overridden_by"
                    @override="$emit('override', fact)"
                >
                    <span v-if="fact.overridden_by" class="replaced ml-2">replaced by its own fact</span>
                </InheritedLine>
            </div>
            <div v-if="form && form.mode === 'override' && form.factId === fact.fact_id" class="my-2">
                <ThingFactForm :form="form" :categories="categories" :busy="busy" @save="$emit('save')" @cancel="$emit('cancel')" />
            </div>
        </template>
    </div>
</template>

<script>
import InheritedLine from './InheritedLine.vue';
import ThingFactForm from './ThingFactForm.vue';

// What a character, race or mix inherits from its heritage (`inherited`),
// each on an inherited fact's line (`InheritedLine`: drawn as an own
// fact is, dimmed, with a chip naming its source) and an "Override"
// button where an own fact's buttons are. ThingPage owns the override
// form, shown here under its fact. A fact an own fact replaces is struck
// through, with no Override.
export default {
    name: 'ThingInherited',
    components: { InheritedLine, ThingFactForm },
    props: {
        inherited: { type: Array, required: true },
        // ThingPage's open fact form, or null
        form: { type: Object, default: null },
        categories: { type: Array, required: true },
        busy: { type: Boolean, default: false },
    },
    emits: ['override', 'save', 'cancel'],
};
</script>

<style scoped>
.inherited-row {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

.replaced {
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
}
</style>
