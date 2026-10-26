<template>
    <!-- an inherited fact's one line: a fact line, its words dimmed, a
         chip naming its source after them -->
    <FactLine
        class="inherited-line"
        :class="{ overridden }"
        :fact="line"
        :actions="actions"
        :dropped="overridden"
        text-class="inherited-text"
        @override="$emit('override')"
    >
        <template #notes>
            <v-chip
                size="x-small"
                variant="outlined"
                color="link"
                class="inherited-source ml-2"
                data-testid="inherited-source"
                @click="worlds.openThing(fact.source_id)"
            >{{ fact.source_name }}</v-chip>
            <slot></slot>
        </template>
    </FactLine>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import FactLine from './FactLine.vue';

// One inherited fact's line, the one markup for a saved page's
// inherited facts (`ThingInherited`) and a draft's (`ThingPage`): drawn
// as an own fact is (`FactLine`: its words, here dimmed, then its
// category and dates in the same places), with a chip naming (and
// opening) the page it comes from after its words, then whatever the
// default slot adds. `overridden`: replaced by an own fact, struck
// through and dimmer. `actions`: what sits where an own fact's buttons
// go, `override` (an "Override" button, `override`) or `none`.
// `fact`: an `inherited` item as a page sends it (`rendered`,
// `segments`, `category`, `valid_from`, `valid_until`, `source_id`,
// `source_name`, `held_by`).
export default {
    name: 'InheritedLine',
    components: { FactLine },
    props: {
        fact: { type: Object, required: true },
        actions: {
            type: String,
            default: 'override',
            validator: (value) => ['override', 'none'].includes(value),
        },
        overridden: { type: Boolean, default: false },
    },
    emits: ['override'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        // the fact as the fact line takes it
        line() {
            return { ...this.fact, text: this.fact.rendered };
        },
    },
};
</script>

<style scoped>
/* dimmed, all but its source chip */
.inherited-line :deep(.inherited-text > :not(.inherited-source)) {
    opacity: 0.6;
}

.inherited-line.overridden :deep(.inherited-text > :not(.inherited-source)) {
    opacity: 0.45;
}
</style>
