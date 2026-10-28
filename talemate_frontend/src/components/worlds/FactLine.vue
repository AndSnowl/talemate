<template>
    <!-- the fact's one line: its words (and whom it's held by) on the
         left, its category, dates, menu and Edit/End buttons (or what
         `actions` puts there) at the right edge -->
    <div class="fact d-flex align-center ga-2" :data-testid="draft || actions !== 'full' ? null : 'fact-row'">
        <span class="flex-grow-1" :class="textClass">
            <LinkedText
                class="fact-text"
                :class="droppedClass"
                :segments="fact.segments"
                :text="fact.text"
                :repoint="!draft && actions === 'full'"
                :selectable="actions === 'full'"
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
        <template v-if="actions === 'full'">
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
        </template>
        <span v-else class="fact-actions-room d-flex justify-end">
            <!-- another line's (an inherited fact's, a small draft's): as
                 wide as the menu and Edit/End buttons, so its category and
                 dates sit where a page fact's do -->
            <v-btn
                v-if="actions === 'override'"
                variant="text"
                size="x-small"
                data-testid="override-button"
                @click="$emit('override')"
            >Override</v-btn>
        </span>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { spanLabel } from './worldDates.js';
import FactRowActions from './FactRowActions.vue';
import LinkedText from './LinkedText.vue';

// A fact's line, the one markup for an entry's page and its draft (both
// through `FactRow`): the words linked (`LinkedText`; selected words open
// the selection menu, `select`; on a page a link can be re-pointed,
// `repoint`), notes after them (`notes`), whom it's held by and "added
// here" inline, then the category, dates, the fact menu (`FactRowActions`:
// ⋯ or a right-click) and the Edit and End buttons at the right edge. On a
// draft (`draft`) the holder has a × to clear it (`held(null)`), the words
// read as dropped once unticked (`dropped`), and the page's actions go to
// the draft.
// `actions` is what sits at the right edge: `full` (the default) the menu
// and the Edit and End buttons; `override` an "Override" button
// (`override`), for an inherited fact; `none` nothing, for a small
// draft's row. Either of the last two keeps the buttons' room, so the
// category and dates line up with a page fact's, and its words can't be
// re-pointed or selected for the selection menu.
export default {
    name: 'FactLine',
    components: { FactRowActions, LinkedText },
    props: {
        fact: { type: Object, required: true },
        draft: { type: Boolean, default: false },
        dropped: { type: Boolean, default: false },
        exclude: { type: Array, default: () => [] },
        textClass: { type: String, default: '' },
        actions: {
            type: String,
            default: 'full',
            validator: (value) => ['full', 'override', 'none'].includes(value),
        },
    },
    emits: ['override', 'repoint', 'select', 'edit', 'dates', 'end', 'remove', 'move', 'copy', 'held'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        // how the fact came (polish 5): one that came unticked is an offer
        return { startedDropped: this.dropped };
    },
    computed: {
        // unticked: an offer is dimmed; a fact the owner unticked is struck
        // through, as "this won't be written"
        droppedClass() {
            if (!this.dropped) {
                return '';
            }
            return this.startedDropped ? 'suggestion-offer' : 'suggestion-dropped';
        },
    },
    methods: { spanLabel },
};
</script>

<style scoped>
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

/* the room of the menu and the Edit and End buttons: three x-small
   icon buttons (20px) and the two 8px gaps between them, never sized by
   what it holds (the Override button, 71px, fits inside: the heritage
   e2e test checks it) */
.fact-actions-room {
    flex: none;
    width: calc(3 * 20px + 2 * 8px);
    min-width: 0;
}

.held {
    margin-left: 6px;
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}

.summary-text {
    font-size: 15px;
    line-height: 1.5;
}
</style>
