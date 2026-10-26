<template>
    <!-- one row for a page's fact and a draft's: a `SuggestionRow`, with
         its tick on a draft only; whom it's held by and "added here" on a
         second line, a repeat's match (drafts) under it -->
    <SuggestionRow
        class="fact-host"
        :tickable="draft"
        :ticked="!draft || fact.ticked !== false"
        :tick-label="'Write ' + fact.text"
        :testid="draft ? 'draft-fact' : 'fact-row'"
        @tick="$emit('tick', $event)"
    >
        <span :class="textClass">
            <LinkedText
                class="fact-text"
                :segments="fact.segments"
                :text="fact.text"
                :repoint="!draft"
                selectable
                :exclude="exclude"
                @repoint="$emit('repoint', $event)"
                @select="$emit('select', $event)"
            />
            <slot name="notes"></slot>
        </span>
        <template #end>
            <v-chip v-if="fact.category" size="x-small" label variant="tonal" color="muted" class="flex-0-0">{{ fact.category }}</v-chip>
            <span class="fact-date">{{ spanLabel(worlds.calendar, fact.valid_from, fact.valid_until) }}</span>
            <FactRowActions
                :fact="fact"
                :draft="draft"
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
            <span v-if="fact.held_by" class="held" data-testid="held-by-tag">held by {{ fact.held_by.name || 'another entry' }}<v-btn
                v-if="draft"
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
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { spanLabel } from './worldDates.js';
import FactRowActions from './FactRowActions.vue';
import LinkedText from './LinkedText.vue';
import SuggestionRow from './SuggestionRow.vue';

// One fact row, the same markup on an entry's page and on its draft (a
// `SuggestionRow` both times, so the two can't drift): the words linked
// (`LinkedText`; selected words open the selection menu, `select`; on a
// page a link can be re-pointed, `repoint`), its category and dates, the
// fact menu (`FactRowActions`: ⋯ or a right-click) and the Edit and End
// buttons, then whom it's held by and "added here" on a second line. A
// draft (`draft`) only adds to that: its tick (`tick`, the one dropped
// look for an unticked fact), the holder's × to clear it, a repeat's match
// (`match`), and nothing is sent: every action is emitted for the page to
// apply to the draft. Its form goes in the default slot, notes after its
// words in `notes`. `fact-host` marks the row for the fact menu's
// right-click. `fact`: `{fact_id?, text, segments, category, valid_from,
// valid_until, held_by: {id, name} | null, ticked?, local?}`.
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
.fact-date {
    flex: none;
    font-family: monospace;
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
    min-width: 80px;
    text-align: right;
}

.held {
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}

.summary-text {
    font-size: 15px;
    line-height: 1.5;
}
</style>
