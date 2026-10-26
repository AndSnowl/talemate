<template>
    <!-- on a draft: the page's fact line (`FactLine`) with a tick in front
         (`SuggestionRow`), a repeat's match under it -->
    <SuggestionRow
        v-if="draft"
        class="fact-host fact-draft"
        :ticked="fact.ticked !== false"
        :dropped="false"
        :tick-label="'Write ' + fact.text"
        testid="draft-fact"
        @tick="$emit('tick', $event)"
    >
        <FactLine
            :fact="fact"
            draft
            :dropped="fact.ticked === false"
            :exclude="exclude"
            :text-class="textClass"
            v-on="lineListeners"
        >
            <template #notes><slot name="notes"></slot></template>
        </FactLine>
        <template v-if="$slots.match" #match>
            <slot name="match"></slot>
        </template>
        <template #after>
            <slot></slot>
        </template>
    </SuggestionRow>

    <div v-else class="fact-host">
        <FactLine
            :fact="fact"
            :exclude="exclude"
            :text-class="textClass"
            v-on="lineListeners"
        >
            <template #notes><slot name="notes"></slot></template>
        </FactLine>
        <slot></slot>
    </div>
</template>

<script>
import FactLine from './FactLine.vue';
import SuggestionRow from './SuggestionRow.vue';

// One fact row, on an entry's page and on its draft: the same fact line
// both times (`FactLine`, its words left, its category, dates, menu and
// Edit/End buttons at the right edge). A draft (`draft`) only adds to it:
// its tick (`tick`) in front, through `SuggestionRow` (the line takes the
// row's full width, not its `end`), a repeat's match (`match`) under it,
// and nothing is sent: every action is emitted for the page to apply to
// the draft. Its form goes in the default slot, notes after its words in
// `notes`. `fact-host` marks the row for the fact menu's right-click and
// draws the dashed separator under the row and whatever is shown under
// it. `fact`: `{fact_id?, text, segments, category, valid_from,
// valid_until, held_by: {id, name} | null, ticked?, local?}`.
export default {
    name: 'FactRow',
    components: { FactLine, SuggestionRow },
    props: {
        fact: { type: Object, required: true },
        draft: { type: Boolean, default: false },
        exclude: { type: Array, default: () => [] },
        textClass: { type: String, default: '' },
    },
    emits: ['tick', 'repoint', 'select', 'edit', 'dates', 'end', 'remove', 'move', 'copy', 'held'],
    computed: {
        // the line's actions, passed on as they are
        lineListeners() {
            const pass = (name) => (value) => this.$emit(name, value);
            return Object.fromEntries(
                ['repoint', 'select', 'edit', 'dates', 'end', 'remove', 'move', 'copy', 'held'].map((name) => [name, pass(name)]),
            );
        },
    },
};
</script>

<style scoped>
/* the separator goes under the whole row, so a fact and what's shown
   under it (a repeat's match, its form) read as one. `fact-host` is also
   the row's marker: the fact menu finds its row by it */
.fact-host {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

/* on a draft the fact line fills the row right of the tick, so its
   category, dates and buttons sit at the right edge as on the page */
.fact-draft :deep(.suggestion-text) {
    flex: 1 1 auto;
}
</style>
