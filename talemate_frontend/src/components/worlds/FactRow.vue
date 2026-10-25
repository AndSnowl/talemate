<template>
    <div class="fact-host" :data-testid="draft ? 'draft-fact' : null">
        <div class="fact d-flex align-center ga-2" :data-testid="draft ? null : 'fact-row'">
            <v-checkbox-btn
                v-if="draft"
                :model-value="fact.ticked !== false"
                density="compact"
                class="flex-grow-0"
                :aria-label="'Write ' + fact.text"
                @update:model-value="$emit('tick', $event)"
            ></v-checkbox-btn>
            <span class="flex-grow-1" :class="[{ dropped: draft && fact.ticked === false }, textClass]">
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
                <span v-if="fact.held_by" class="held" data-testid="held-by-tag">held by {{ fact.held_by.name || 'another entry' }}<v-btn
                    v-if="draft"
                    icon="mdi-close"
                    variant="text"
                    size="x-small"
                    density="compact"
                    :aria-label="'Not held: ' + fact.text"
                    @click="$emit('held', null)"
                ></v-btn></span>
                <span v-if="fact.local" class="text-caption text-muted"> · added here</span>
            </span>
            <v-chip v-if="fact.category" size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
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

// One fact row, the same on an entry's page and on its draft: the words
// linked (`LinkedText`; selected words open the selection menu, `select`;
// on a page a link can be re-pointed, `repoint`), whom it's held by, its
// category and dates, the fact menu (`FactRowActions`: ⋯ or a right-click)
// and the Edit and End buttons. On a draft (`draft`) it has its tick
// (`tick`), the holder can be cleared here, and nothing is sent: every
// action is emitted for the page to apply to the draft. Its form and a
// repeat's match go in the default slot, notes after its words in `notes`.
// `fact`: `{fact_id?, text, segments, category, valid_from, valid_until,
// held_by: {id, name} | null, ticked?, local?}`.
export default {
    name: 'FactRow',
    components: { FactRowActions, LinkedText },
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
   under it (a repeat's match, its form) read as one */
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

.dropped {
    color: rgb(var(--v-theme-muted));
}

.summary-text {
    font-size: 15px;
    line-height: 1.5;
}
</style>
