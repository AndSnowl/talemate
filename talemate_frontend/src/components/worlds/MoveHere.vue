<template>
    <div v-if="shown.length" class="move-here mt-3" data-testid="move-here">
        <div class="heading">Could move here <span class="text-muted">· facts on nearby pages that name {{ draft.name }}</span></div>
        <div v-for="row in shown" :key="row.fact_id" class="d-flex align-center ga-2 row" data-testid="move-here-row">
            <v-checkbox-btn
                :model-value="!!row.ticked"
                density="compact"
                class="flex-grow-0"
                :aria-label="'Move here ' + row.text"
                @update:model-value="$emit('tick', row.fact_id, $event)"
            ></v-checkbox-btn>
            <span class="flex-grow-1" :class="{ dropped: !row.ticked }">
                <LinkedText :segments="namedSegments(row.text, draft)" :text="row.text" />
                <span class="from text-caption"> · on {{ row.from_name || 'a nearby entry' }}</span>
            </span>
        </div>
        <div class="note text-caption">Moved, not copied: a ticked one leaves the page it's on.</div>
    </div>
</template>

<script>
import { namedSegments } from './draftPage.js';
import LinkedText from './LinkedText.vue';

// "Could move here" (spec "The draft page" 5): facts on any nearby page
// that name the entry being drafted (`move_here`, found by code), each
// with that name highlighted and where it is now. Every row comes
// unticked (ruling F7); a ticked one is moved, not copied, on Accept. The
// draft's own "Move existing here" rows (`repeat`) show with their fact
// instead. A tick emits `tick(factId, ticked)`.
export default {
    name: 'MoveHere',
    components: { LinkedText },
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
.heading {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

.row {
    padding: 2px 0;
}

.from {
    color: rgb(var(--v-theme-muted));
}

.dropped {
    color: rgb(var(--v-theme-muted));
}

.note {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}
</style>
