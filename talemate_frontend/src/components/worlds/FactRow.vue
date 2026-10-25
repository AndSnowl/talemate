<template>
    <!-- on a draft: a row to tick (`SuggestionRow`), whom it's held by
         and "added here" on a second line, a repeat's match under it -->
    <SuggestionRow
        v-if="draft"
        class="fact-host"
        :ticked="fact.ticked !== false"
        :tick-label="'Write ' + fact.text"
        testid="draft-fact"
        @tick="$emit('tick', $event)"
    >
        <span :class="textClass">
            <LinkedText
                class="fact-text"
                :segments="fact.segments"
                :text="fact.text"
                selectable
                :exclude="exclude"
                @select="$emit('select', $event)"
            />
            <slot name="notes"></slot>
        </span>
        <template #end>
            <v-chip v-if="fact.category" size="x-small" label variant="tonal" color="muted" class="flex-0-0">{{ fact.category }}</v-chip>
            <span class="fact-date">{{ spanLabel(worlds.calendar, fact.valid_from, fact.valid_until) }}</span>
            <FactRowActions
                :fact="fact"
                draft
                :exclude="exclude"
                @edit="$emit('edit')"
                @dates="$emit('dates')"
                @end="$emit('end')"
                @remove="$emit('remove')"
                @move="$emit('move', $event)"
                @copy="$emit('copy', $event)"
                @held="$emit('held', $event)"
            />
            <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" class="flex-0-0" aria-label="Edit fact" @click="$emit('edit')"></v-btn>
            <v-btn v-if="!fact.valid_until" icon="mdi-timer-off-outline" variant="text" size="x-small" density="comfortable" class="flex-0-0" aria-label="End fact" @click="$emit('end')"></v-btn>
        </template>
        <template v-if="fact.held_by || fact.local" #under>
            <span v-if="fact.held_by" class="held under-held" data-testid="held-by-tag">held by {{ fact.held_by.name || 'another entry' }}<v-btn
                icon="mdi-close"
                variant="text"
                size="x-small"
                density="compact"
                :aria-label="'Not held: ' + fact.text"
                @click="$emit('held', null)"
            ></v-btn></span>
            <span v-if="fact.local" class="text-caption text-muted"><template v-if="fact.held_by"> · </template>added here</span>
        </template>
        <template v-if="$slots.match" #match>
            <slot name="match"></slot>
        </template>
        <template #after>
            <slot></slot>
        </template>
    </SuggestionRow>

    <div v-else class="fact-host">
        <div class="fact d-flex align-center ga-2" data-testid="fact-row">
            <span class="flex-grow-1" :class="textClass">
                <LinkedText
                    class="fact-text"
                    :segments="fact.segments"
                    :text="fact.text"
                    repoint
                    selectable
                    :exclude="exclude"
                    @repoint="$emit('repoint', $event)"
                    @select="$emit('select', $event)"
                />
                <slot name="notes"></slot>
                <span v-if="fact.held_by" class="held" data-testid="held-by-tag">held by {{ fact.held_by.name || 'another entry' }}</span>
                <span v-if="fact.local" class="text-caption text-muted"> · added here</span>
            </span>
            <v-chip v-if="fact.category" size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
            <span class="fact-date">{{ spanLabel(worlds.calendar, fact.valid_from, fact.valid_until) }}</span>
            <FactRowActions
                :fact="fact"
                :exclude="exclude"
                @edit="$emit('edit')"
                @dates="$emit('dates')"
                @end="$emit('end')"
                @remove="$emit('remove')"
                @move="$emit('move', $event)"
                @copy="$emit('copy', $event)"
                @held="$emit('held', $event)"
            />
            <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit fact" @click="$emit('edit')"></v-btn>
            <v-btn v-if="!fact.valid_until" icon="mdi-timer-off-outline" variant="text" size="x-small" density="comfortable" aria-label="End fact" @click="$emit('end')"></v-btn>
        </div>
        <slot></slot>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { spanLabel } from './worldDates.js';
import FactRowActions from './FactRowActions.vue';
import LinkedText from './LinkedText.vue';
import SuggestionRow from './SuggestionRow.vue';

// One fact row, the same on an entry's page and on its draft: the words
// linked (`LinkedText`; selected words open the selection menu, `select`;
// on a page a link can be re-pointed, `repoint`), whom it's held by, its
// category and dates, the fact menu (`FactRowActions`: ⋯ or a right-click)
// and the Edit and End buttons. On a draft (`draft`) it has its tick
// (`tick`), the holder can be cleared here, and nothing is sent: every
// action is emitted for the page to apply to the draft. On a draft it's a
// `SuggestionRow` (the one dropped look for an unticked fact): the holder
// and "added here" on a second line, a repeat's match in `match`, under
// it. Its form goes in the default slot, notes after its words in `notes`.
// `fact`: `{fact_id?, text, segments, category, valid_from, valid_until,
// held_by: {id, name} | null, ticked?, local?}`.
export default {
    name: 'FactRow',
    components: { FactRowActions, LinkedText, SuggestionRow },
    props: {
        fact: { type: Object, required: true },
        draft: { type: Boolean, default: false },
        exclude: { type: Array, default: () => [] },
        textClass: { type: String, default: '' },
    },
    emits: ['tick', 'repoint', 'select', 'edit', 'dates', 'end', 'remove', 'move', 'copy', 'held'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    methods: { spanLabel },
};
</script>

<style scoped>
/* the separator goes under the whole row, so a fact and what's shown
   under it (a repeat's match, its form) read as one. `fact-host` is also
   the draft row's marker: the fact menu finds its row by it */
.fact-host {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

.fact {
    padding: 2px 0;
}

.fact .v-chip,
.fact .v-btn {
    flex: none;
}

.fact-date {
    flex: none;
    font-family: monospace;
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
    min-width: 80px;
    text-align: right;
}

.held {
    margin-left: 6px;
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}

.held.under-held {
    margin-left: 0;
}

.summary-text {
    font-size: 15px;
    line-height: 1.5;
}
</style>
