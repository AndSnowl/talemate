<template>
    <v-dialog :model-value="!!check" max-width="560" scrollable @update:model-value="cancel">
        <v-card v-if="check" data-testid="delete-dialog">
            <v-card-title class="d-flex align-center ga-2">
                <v-icon color="danger">mdi-delete-alert</v-icon>
                Delete {{ check.name }}?
            </v-card-title>
            <v-card-text>
                <p class="mb-3" data-testid="delete-ramifications">
                    Deleting <strong>{{ check.name }}</strong> removes it from the world.
                    Anything that refers to it will show it as
                    <span class="unknown">⟨unknown⟩</span>, and scenes that use it will
                    load without it. Scenes open right now keep it until they're
                    reloaded. It stays in the world's history, but there's no way to
                    restore it from the app yet.
                </p>

                <div v-if="!total" class="text-body-2 text-muted" data-testid="delete-no-references">
                    Nothing else in the world refers to it.
                </div>
                <template v-else>
                    <v-alert type="warning" variant="tonal" density="compact" class="mb-3" data-testid="delete-referenced">
                        {{ check.name }} is used in {{ total }} {{ total === 1 ? 'place' : 'places' }}.
                    </v-alert>
                    <div v-if="refs.facts.length" class="mb-2" data-testid="delete-ref-facts">
                        <div class="text-overline text-muted">Facts</div>
                        <div v-for="(entry, index) in refs.facts" :key="'f' + index" class="ref-row" data-testid="delete-ref">
                            <span class="ref-owner">{{ entry.thing_name }}:</span> {{ entry.text }}
                        </div>
                    </div>
                    <div v-if="refs.fields.length" class="mb-2" data-testid="delete-ref-fields">
                        <div class="text-overline text-muted">Fields</div>
                        <div v-for="(entry, index) in refs.fields" :key="'d' + index" class="ref-row" data-testid="delete-ref">
                            <span class="ref-owner">{{ entry.thing_name }}</span>
                            <span class="text-muted"> · {{ fieldLabel(entry.field) }}</span>
                        </div>
                    </div>
                    <div v-if="refs.scenes.length" data-testid="delete-ref-scenes">
                        <div class="text-overline text-muted">Scenes</div>
                        <div v-for="(entry, index) in refs.scenes" :key="'s' + index" class="ref-row" data-testid="delete-ref">
                            <v-icon size="x-small" color="scene">mdi-movie-open</v-icon>
                            {{ entry.name }}<span class="text-muted"> · {{ ROLE_LABELS[entry.role] || entry.role }}</span>
                        </div>
                    </div>
                </template>
            </v-card-text>
            <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn variant="text" :disabled="busy" @click="cancel">Cancel</v-btn>
                <v-btn color="danger" variant="flat" prepend-icon="mdi-delete" :loading="busy" @click="worlds.confirmDelete()">Delete</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { referenceFieldLabel } from './entryPage.js';

const ROLE_LABELS = { player: 'the player', character: 'a character', place: 'the place', lore: 'pulled-in lore' };

// The "are you sure?" dialog for deleting the open thing: shown while the
// store holds its reference check (`deleteCheck`). It always says what a
// delete does, and lists what uses the thing, as facts, fields and scenes.
export default {
    name: 'ThingDeleteDialog',
    setup() {
        return { worlds: useWorldsStore(), ROLE_LABELS };
    },
    computed: {
        check() {
            return this.worlds.deleteCheck;
        },
        refs() {
            return this.check?.references || { facts: [], fields: [], scenes: [] };
        },
        total() {
            return this.refs.facts.length + this.refs.fields.length + this.refs.scenes.length;
        },
        busy() {
            return !!this.worlds.pending.delete_thing;
        },
    },
    methods: {
        fieldLabel(field) {
            return referenceFieldLabel(field);
        },
        cancel() {
            if (!this.busy) {
                this.worlds.cancelDelete();
            }
        },
    },
};
</script>

<style scoped>
.unknown {
    color: rgb(var(--v-theme-muted));
}

.ref-row {
    padding: 2px 0;
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

.ref-owner {
    font-weight: 600;
}
</style>
