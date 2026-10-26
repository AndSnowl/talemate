<template>
    <div v-if="shown.length" class="move-here mt-3" data-testid="move-here">
        <div class="suggestion-heading">Could move here <span class="text-muted">· facts on nearby pages that name {{ draft.name }}</span></div>
        <SuggestionRow
            v-for="row in shown"
            :key="row.fact_id"
            :ticked="!!row.ticked"
            :tick-label="'Move here ' + row.text"
            testid="move-here-row"
            @tick="$emit('tick', row.fact_id, $event)"
        >
            <LinkedText :segments="namedSegments(row.text, draft)" :text="row.text" />
            <span class="from text-caption"> · on {{ row.from_name || 'a nearby entry' }}</span>
        </SuggestionRow>
        <div class="note text-caption">Moved, not copied: a ticked one leaves the page it's on.</div>
    </div>
</template>

<script>
import { namedSegments } from './draftPage.js';
import LinkedText from './LinkedText.vue';
import SuggestionRow from './SuggestionRow.vue';

// "Could move here" (spec "The draft page" 5): facts on any nearby page
// that name the entry being drafted (`move_here`, found by code), each
// with that name highlighted and where it is now. Every row comes
// unticked (ruling F7), a `SuggestionRow`; a ticked one is moved, not
// copied, on Accept. The draft's own "Move existing here" rows (`repeat`)
// show with their fact instead. A tick emits `tick(factId, ticked)`.
export default {
    name: 'MoveHere',
    components: { LinkedText, SuggestionRow },
    props: {
        // the draft's preview as the owner left it (`move_here`, its name)
        draft: { type: Object, required: true },
    },
    emits: ['tick'],
    computed: {
        shown() {
            return (this.draft.move_here || []).filter((row) => !row.repeat);
        },
    },
    methods: { namedSegments },
};
</script>

<style scoped>
.from {
    color: rgb(var(--v-theme-muted));
}

.note {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}
</style>
