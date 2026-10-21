<template>
    <div class="referenced-in" data-testid="referenced-in">
        <div class="text-overline text-muted">Referenced in</div>
        <div class="row d-flex ga-2">
            <span class="row-label">Entries</span>
            <span v-if="!entries.length" class="text-muted">None yet.</span>
            <span v-else>
                <template v-for="(entry, index) in entries" :key="entry.key">
                    <span v-if="index" class="text-muted"> · </span>
                    <a class="thing-link" href="#" :title="entry.title" @click.prevent="worlds.openThing(entry.id)">{{ entry.name }}</a>
                    <span class="text-muted"> ({{ entry.how }})</span>
                </template>
            </span>
        </div>
        <div class="row d-flex ga-2">
            <span class="row-label">Scenes</span>
            <span v-if="!scenes.length" class="text-muted">None yet.</span>
            <div v-else class="d-flex flex-wrap ga-2">
                <v-chip
                    v-for="scene in scenes"
                    :key="scene.id"
                    size="small"
                    variant="tonal"
                    color="scene"
                    prepend-icon="mdi-movie-open"
                    @click="scene.start && $emit('view-at', scene.start)"
                >
                    {{ scene.name }}<span v-if="scene.start" class="text-muted">&nbsp;· {{ formatDate(worlds.calendar, scene.start) }}</span>
                </v-chip>
            </div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';

const FIELD_LABELS = { heritage: 'heritage', species: 'species', parents: 'parent', origin: 'origin' };

// What uses a species, race or mix (`referenced_in`): the entries whose
// fields or facts name it, and the scenes it's in, including the scenes of
// characters whose lineage includes it (`member_scenes`).
export default {
    name: 'ThingReferencedIn',
    props: {
        references: { type: Object, required: true },
    },
    emits: ['view-at'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        entries() {
            const entries = [];
            const seen = new Set();
            const add = (id, name, how, title = '') => {
                const key = `${id}|${how}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    entries.push({ key, id, name, how, title });
                }
            };
            for (const field of this.references.fields || []) {
                add(field.thing_id, field.thing_name, FIELD_LABELS[field.field] || field.field);
            }
            for (const fact of this.references.facts || []) {
                add(fact.thing_id, fact.thing_name, 'fact', fact.text);
            }
            return entries;
        },
        // the member scenes (dated), then any other scene using it
        scenes() {
            const scenes = [...(this.references.member_scenes || [])];
            const ids = new Set(scenes.map((scene) => scene.id));
            for (const scene of this.references.scenes || []) {
                if (!ids.has(scene.scene_id)) {
                    ids.add(scene.scene_id);
                    scenes.push({ id: scene.scene_id, name: scene.name, start: null });
                }
            }
            return scenes;
        },
    },
    methods: {
        formatDate,
    },
};
</script>

<style scoped>
.row {
    margin: 4px 0;
}

.row-label {
    min-width: 80px;
    font-weight: 600;
    color: rgb(var(--v-theme-muted));
}

.thing-link {
    color: rgb(var(--v-theme-link));
    text-decoration: underline dotted;
}
</style>
