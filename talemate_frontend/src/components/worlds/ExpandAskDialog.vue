<template>
    <v-dialog :model-value="!!stub || !!create" max-width="480" @update:model-value="worlds.keepPreview()">
        <v-card v-if="stub || create" :data-testid="stub ? 'expand-ask' : 'discard-ask'">
            <v-card-title class="d-flex align-center ga-2">
                <v-icon color="warning">mdi-alert</v-icon>
                Discard the draft?
            </v-card-title>
            <v-card-text>
                The draft of <strong>{{ previewName }}</strong> hasn't been accepted.
                <template v-if="stub">Expanding <strong>{{ stub.name }}</strong> discards it.</template>
                <template v-else>Creating a new {{ createKind }} discards it.</template>
            </v-card-text>
            <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn variant="text" @click="worlds.keepPreview()">Keep the draft</v-btn>
                <v-btn v-if="stub" color="accent" variant="flat" @click="worlds.confirmExpand()">Discard and expand</v-btn>
                <v-btn v-else color="accent" variant="flat" @click="worlds.confirmCreate()">Discard and create</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { kindInfo } from './worldKinds.js';

// Asks before a draft the owner hasn't accepted yet is dropped: expanding
// a stub (`worlds.expandAsk`) or creating in another kind's box
// (`worlds.createAsk`). The discard drops it on the server too.
export default {
    name: 'ExpandAskDialog',
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        stub() {
            return this.worlds.expandAsk;
        },
        create() {
            return this.worlds.createAsk;
        },
        createKind() {
            return kindInfo(this.create?.kind)?.singular || this.create?.kind || 'entry';
        },
        previewName() {
            return this.worlds.preview?.name || 'this thing';
        },
    },
};
</script>
