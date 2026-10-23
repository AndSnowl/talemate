<template>
    <!-- a stub row's small "same as X?" choice: new unless the owner picks -->
    <v-select
        v-if="variant === 'row'"
        :model-value="chosen || NEW"
        :items="rowItems"
        density="compact"
        variant="outlined"
        hide-details
        class="stub-same"
        data-testid="stub-same"
        :aria-label="`Is ${name} one the world has?`"
        @update:model-value="$emit('choose', $event === NEW ? null : $event)"
    >
        <template #selection="{ item }">
            <span class="text-caption">{{ item.raw.value === NEW ? 'new' : `same as ${item.raw.name}` }}</span>
            <span v-if="item.raw.note" class="text-caption text-muted ml-1" data-testid="stub-same-kind">{{ item.raw.note }}</span>
        </template>
        <template #item="{ props: itemProps, item }">
            <v-list-item v-bind="itemProps" :subtitle="item.raw.summary" data-testid="stub-same-option"></v-list-item>
        </template>
    </v-select>

    <!-- the entry's own question, at the top of its preview -->
    <div v-else class="same-ask pa-2 mb-3" data-testid="same-thing">
        <div class="mb-1">
            Is <b>“{{ name }}”</b> the same as {{ offers.length === 1 ? 'this' : 'one of these' }}?
            <span class="text-caption text-muted">{{ variant === 'promote' ? 'If so, make that one a sphere instead.' : 'If so, its facts go there, and its name becomes another name of it.' }}</span>
        </div>
        <div
            v-for="offer in offers"
            :key="offer.thing_id"
            class="candidate d-flex align-center flex-wrap ga-2"
            :class="{ chosen: chosen === offer.thing_id }"
            data-testid="same-candidate"
        >
            <span class="candidate-name">{{ offer.name }}</span>
            <v-chip size="x-small" label variant="tonal" color="muted">{{ offer.kind }}</v-chip>
            <v-chip v-if="offer.stub" size="x-small" label variant="outlined" color="foreign">stub</v-chip>
            <span v-if="kindNote(offer)" class="text-caption text-muted" data-testid="same-kind-note">{{ kindNote(offer) }}</span>
            <span class="text-caption text-muted flex-grow-1">{{ summary(offer) }}</span>
            <span v-if="hint(offer)" class="hint text-caption" data-testid="same-hint" :title="'A hint, not a default'">
                <v-icon size="x-small" icon="mdi-robot-outline"></v-icon>
                AI's hint: {{ hint(offer).verdict }}<template v-if="hint(offer).why"> — {{ hint(offer).why }}</template>
            </span>
            <template v-if="variant === 'promote'">
                <v-btn v-if="offer.kind === 'sphere'" variant="outlined" size="x-small" @click="worlds.openThing(offer.thing_id)">Open {{ offer.name }}</v-btn>
                <v-btn v-else-if="promotableOffer(offer)" variant="outlined" size="x-small" prepend-icon="mdi-orbit" @click="$emit('promote', offer)">Make {{ offer.name }} a sphere…</v-btn>
            </template>
            <v-btn
                v-else
                :variant="chosen === offer.thing_id ? 'flat' : 'outlined'"
                :color="chosen === offer.thing_id ? 'accent' : undefined"
                size="x-small"
                :aria-pressed="chosen === offer.thing_id"
                @click="$emit('choose', offer.thing_id)"
            >Yes, fill it</v-btn>
        </div>
        <div v-if="variant !== 'promote'" class="d-flex align-center ga-2 mt-1">
            <v-btn
                :variant="chosen ? 'outlined' : 'flat'"
                :color="chosen ? undefined : 'accent'"
                size="x-small"
                :aria-pressed="!chosen"
                @click="$emit('choose', null)"
            >No, it's new</v-btn>
            <span v-if="chosen" class="text-caption text-muted">Nothing new is made: it goes onto {{ chosenName }}.</span>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { offerSummary, otherKindNote, promotableOffer } from './worldKinds.js';

// the row choice's value for "new"
const NEW = '__new__';

// "Same thing?" (curation goal 4): what the world has that a new entry or
// stub may already be (`same_as`, `SameOffer`s: name, kind, its candidate
// line, so two of one name can be told apart; a stub marked so).
// - `entry`: the question at the top of a create preview. The AI's
//   verdict (`verdict`, id -> {verdict, why}) is only a hint beside its
//   candidate, never a default: the answer starts as "new". "Yes, fill
//   it" emits `choose` with the thing's id, "No, it's new" with null.
// - `promote`: a sphere's core can't be accepted onto an entry (ruling
//   C9): a lore entry, place or stub it may be is offered "Make X a
//   sphere…" (`promote`, the offer); a sphere it may be is opened.
// - `row`: a stub row's small "same as X?" choice, "new" by default. A
//   stub's kind is a guess, so it offers every kind; a choice of another
//   kind than the row's (`kind`) shows "(a lore)" beside it (ruling C34).
export default {
    name: 'SameThingAsk',
    props: {
        // the new entry's (or stub's) name
        name: { type: String, required: true },
        offers: { type: Array, required: true },
        verdict: { type: Object, default: null },
        // the thing picked, or null for new
        chosen: { type: String, default: null },
        variant: { type: String, default: 'entry' },
        // the entry's or row's own kind, for the note on another kind
        kind: { type: String, default: null },
    },
    emits: ['choose', 'promote'],
    setup() {
        return { worlds: useWorldsStore(), NEW };
    },
    computed: {
        rowItems() {
            return [
                { title: 'new', value: NEW, name: '', summary: 'a stub of its own' },
                ...this.offers.map((offer) => ({
                    title: `same as ${offer.name} (${offer.kind}${offer.stub ? ', stub' : ''})`,
                    value: offer.thing_id,
                    name: offer.name,
                    note: otherKindNote(this.kind, offer),
                    summary: offerSummary(offer),
                })),
            ];
        },
        chosenName() {
            return this.offers.find((offer) => offer.thing_id === this.chosen)?.name || '';
        },
    },
    methods: {
        // its candidate line without its name and kind (shown beside it)
        summary(offer) {
            return offerSummary(offer);
        },
        // an entry's stub candidate of another kind (ruling C35): "(a lore)"
        kindNote(offer) {
            return otherKindNote(this.kind, offer);
        },
        hint(offer) {
            return this.verdict?.[offer.thing_id] || null;
        },
        promotableOffer,
    },
};
</script>

<style scoped>
.same-ask {
    border: 1px solid rgb(var(--v-theme-warning));
    border-radius: 6px;
}

.candidate {
    padding: 3px 6px;
    border-radius: 4px;
}

.candidate.chosen {
    background: rgba(var(--v-theme-accent), 0.12);
}

.candidate-name {
    font-weight: 600;
    color: rgb(var(--v-theme-link));
}

.hint {
    color: rgb(var(--v-theme-muted));
    font-style: italic;
}

.stub-same {
    flex: none;
    width: 210px;
}

.stub-same :deep(.v-field__input) {
    min-height: 30px;
    padding-top: 2px;
    padding-bottom: 2px;
}
</style>
