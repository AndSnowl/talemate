<template>
    <v-menu v-model="moving" :close-on-content-click="false" location="bottom end">
        <template #activator="{ props }">
            <v-btn
                v-bind="props"
                icon="mdi-arrow-right-bold-box-outline"
                variant="text"
                size="x-small"
                density="comfortable"
                aria-label="Move to…"
                title="Move to…"
                data-testid="fact-move"
                @click="target = null"
            ></v-btn>
        </template>
        <v-card class="pa-3" min-width="300" data-testid="fact-move-menu" @keydown.esc="escape($event, 'moving')">
            <div class="text-caption text-muted mb-2">Move this fact onto the entry it's about. It leaves this page.</div>
            <v-autocomplete
                v-model="target"
                :items="targets"
                item-title="name"
                item-value="id"
                label="Move to"
                density="compact"
                variant="outlined"
                hide-details
                autofocus
                data-testid="move-target"
            >
                <template #item="{ props: itemProps, item }">
                    <v-list-item v-bind="itemProps" :subtitle="item.raw.stub ? `${item.raw.kind} · stub` : item.raw.kind"></v-list-item>
                </template>
            </v-autocomplete>
            <div class="d-flex ga-2 mt-3">
                <v-btn color="accent" variant="flat" size="small" :disabled="!target" :loading="!!worlds.pending.move_fact" @click="move">Move</v-btn>
                <v-btn variant="text" size="small" @click="moving = false">Cancel</v-btn>
            </div>
        </v-card>
    </v-menu>
    <v-menu v-model="holding" :close-on-content-click="false" location="bottom end">
        <template #activator="{ props }">
            <v-btn
                v-bind="props"
                icon="mdi-account-voice"
                variant="text"
                size="x-small"
                density="comfortable"
                aria-label="Held by…"
                title="Held by…"
                data-testid="fact-held-by"
                @click="holder = fact.held_by?.id || null"
            ></v-btn>
        </template>
        <v-card class="pa-3" min-width="300" data-testid="fact-held-menu" @keydown.esc="escape($event, 'holding')">
            <div class="text-caption text-muted mb-2">A belief someone holds rather than the world's truth: in a scene, the faithful speak of it as fact, but the narration doesn't confirm it.</div>
            <v-autocomplete
                v-model="holder"
                :items="holders"
                item-title="name"
                item-value="id"
                label="Held by"
                density="compact"
                variant="outlined"
                hide-details
                autofocus
                data-testid="held-by-picker"
            ></v-autocomplete>
            <div class="d-flex ga-2 mt-3">
                <v-btn color="accent" variant="flat" size="small" :disabled="!holder" :loading="!!worlds.pending.set_held_by" @click="setHolder(holder)">Save</v-btn>
                <v-btn v-if="fact.held_by" variant="outlined" size="small" :disabled="!!worlds.pending.set_held_by" @click="setHolder(null)">Clear</v-btn>
                <v-btn variant="text" size="small" @click="holding = false">Cancel</v-btn>
            </div>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { escapeCloses } from './worldKinds.js';

// A fact row's curation actions (curation goals 1 and 7), for one of the
// open page's own facts:
// - "Move to…": the fact moves onto another entry (`move_fact`: copied
//   with a new id and removed here, one revision);
// - "Held by…": any other entry (a faith, a people, a character) holds it
//   as a belief (`set_held_by`), or Clear makes it the world's truth again.
// Each opens a small menu; Esc closes it (once its picker's list is shut).
export default {
    name: 'FactRowActions',
    props: {
        // the fact row (`{fact_id, held_by}`)
        fact: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { moving: false, target: null, holding: false, holder: null };
    },
    computed: {
        // every entry and live stub but the page's own
        targets() {
            return this.worlds.referenceTargets.filter((target) => target.id !== this.worlds.selectedThingId);
        },
        // every other entry (not a stub): any live entry may hold a belief
        holders() {
            return this.worlds.referenceTargets.filter((target) => !target.stub && target.id !== this.worlds.selectedThingId);
        },
    },
    methods: {
        // Esc closes the menu, unless it closes its picker's list first
        escape(event, menu) {
            if (escapeCloses(event)) {
                this[menu] = false;
            }
        },
        move() {
            if (this.target) {
                this.worlds.moveFact(this.fact.fact_id, this.target);
                this.moving = false;
            }
        },
        setHolder(id) {
            this.worlds.setHeldBy(this.fact.fact_id, id);
            this.holding = false;
        },
    },
};
</script>
