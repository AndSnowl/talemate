<template>
    <div v-if="planned" class="scene-setup" data-testid="scene-setup">
        <div class="text-subtitle-2 mb-2">Setup (shown before you play)</div>
        <div class="cards">
            <v-card variant="flat" class="setup-card pa-3" data-testid="setup-who">
                <div class="card-title">Who</div>
                <div>{{ refName(planned.player) }} (you)</div>
                <div v-for="(ref, index) in planned.characters" :key="index">
                    {{ refName(ref) }}
                    <v-chip v-if="ref.local" size="x-small" label variant="tonal" color="warning" class="ml-1">invented</v-chip>
                </div>
            </v-card>
            <v-card variant="flat" class="setup-card pa-3" data-testid="setup-where">
                <div class="card-title">Where</div>
                <template v-if="planned.place">
                    <div>{{ refName(planned.place) }}</div>
                    <v-chip size="x-small" label variant="tonal" :color="planned.place.local ? 'warning' : 'muted'" class="mt-1">
                        {{ planned.place.local ? 'invented' : 'from world' }}
                    </v-chip>
                </template>
                <div v-else class="text-muted">Nowhere in particular</div>
            </v-card>
            <v-card variant="flat" class="setup-card pa-3" data-testid="setup-when">
                <div class="card-title">When</div>
                <div class="world-date">{{ formatDate(worlds.calendar, planned.start) }}</div>
            </v-card>
            <v-card variant="flat" class="setup-card pa-3" data-testid="setup-goal">
                <div class="card-title">Goal</div>
                <div>{{ planned.goal || '—' }}</div>
            </v-card>
            <v-card variant="flat" class="setup-card pa-3" data-testid="setup-pulled-in">
                <div class="card-title">Pulled in</div>
                <div v-if="!planned.pulled_in.length" class="text-muted">Nothing else from the world</div>
                <div v-for="id in planned.pulled_in" :key="id">{{ names[id] || id }}</div>
            </v-card>
            <v-card variant="flat" class="setup-card pa-3" data-testid="setup-invented">
                <div class="card-title">Invented</div>
                <div v-if="!planned.invented.length" class="text-muted">Nothing; all from the world</div>
                <div v-for="(invented, index) in planned.invented" :key="index">{{ invented }}</div>
                <div v-if="planned.invented.length" class="text-caption text-muted mt-1">These stay in this scene.</div>
            </v-card>
        </div>

        <div v-if="planned.intro" class="intro mt-3 pa-3">
            <div class="card-title">Opens with</div>
            <div class="prose">{{ planned.intro }}</div>
        </div>

        <div class="d-flex flex-wrap ga-2 mt-3">
            <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-play" :loading="starting" @click="worlds.startScene()">Start</v-btn>
            <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" :disabled="starting" @click="worlds.regenerateSetup()">Regenerate setup</v-btn>
            <v-btn variant="outlined" size="small" prepend-icon="mdi-pencil" :disabled="starting" @click="worlds.discardSetup()">Edit</v-btn>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';

// The setup step before play, shared by the new-scene dialog and "continue
// in a new scene": who, where, when, the goal, what was pulled in from the
// world and what was invented, with Start, Regenerate and Edit (back to the
// prompt). Shows the store's setup for `action` (plan_scene or
// continue_scene) only, so each dialog shows its own.
export default {
    name: 'SceneSetupCards',
    props: {
        action: { type: String, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        mine() {
            return this.worlds.setupRequest?.action === this.action;
        },
        planned() {
            return this.mine ? this.worlds.sceneSetup?.setup || null : null;
        },
        names() {
            return this.worlds.sceneSetup?.names || {};
        },
        starting() {
            return !!this.worlds.pending.start_scene;
        },
    },
    methods: {
        formatDate,
        refName(ref) {
            if (ref.thing_id) {
                return this.names[ref.thing_id] || ref.thing_id;
            }
            return ref.local?.name || '';
        },
    },
};
</script>

<style scoped>
.cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 8px;
}

.setup-card,
.intro {
    background: rgb(var(--v-theme-raised));
    border-radius: 6px;
    font-size: 13px;
}

.card-title {
    color: rgb(var(--v-theme-accent));
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
}

.prose {
    line-height: 1.5;
    white-space: pre-wrap;
}

.world-date {
    color: rgb(var(--v-theme-date));
}
</style>
