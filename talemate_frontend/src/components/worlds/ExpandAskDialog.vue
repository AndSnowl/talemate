<template>
    <v-dialog :model-value="!!stub" max-width="480" @update:model-value="worlds.keepPreview()">
        <v-card v-if="stub" data-testid="expand-ask">
            <v-card-title class="d-flex align-center ga-2">
                <v-icon color="warning">mdi-alert</v-icon>
                Discard the preview?
            </v-card-title>
            <v-card-text>
                The preview of <strong>{{ previewName }}</strong> hasn't been accepted.
                {{ stub.promote ? 'Making' : 'Expanding' }} <strong>{{ stub.name }}</strong>{{ stub.promote ? ' a sphere' : '' }} discards it.
            </v-card-text>
            <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn variant="text" @click="worlds.keepPreview()">Keep the preview</v-btn>
                <v-btn color="accent" variant="flat" @click="worlds.confirmExpand()">Discard and {{ stub.promote ? 'go on' : 'expand' }}</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// Asks before expanding a stub (`worlds.expandAsk`) would drop a preview
// the owner hasn't accepted yet.
export default {
    name: 'ExpandAskDialog',
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        stub() {
            return this.worlds.expandAsk;
        },
        previewName() {
            return (this.worlds.preview || this.worlds.spherePreview)?.name || 'this thing';
        },
    },
};
</script>
