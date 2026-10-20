<template>
    <div class="worlds-home pa-4" data-testid="worlds-home">
        <v-alert v-if="worlds.error" type="error" variant="tonal" density="compact" class="mb-4" closable @click:close="worlds.clearError()">
            {{ worlds.error }}
        </v-alert>

        <v-row>
            <v-col cols="12" md="5">
                <div class="d-flex align-center">
                    <span class="text-overline text-muted">Worlds</span>
                    <v-spacer></v-spacer>
                    <v-btn icon="mdi-refresh" variant="text" size="small" density="comfortable" aria-label="Refresh worlds" @click="refresh"></v-btn>
                </div>

                <div v-if="!worlds.worlds.length" class="empty-hint pa-4 mb-3 text-body-2">
                    No worlds yet. Make one below.
                </div>
                <v-list v-else density="compact" class="world-list mb-3" bg-color="transparent">
                    <v-list-item
                        v-for="world in worlds.worlds"
                        :key="world.id"
                        :active="world.id === worlds.currentWorld?.id"
                        color="accent"
                        rounded
                        data-testid="world-row"
                        prepend-icon="mdi-earth"
                    >
                        <v-list-item-title>{{ world.name }}</v-list-item-title>
                        <template #append>
                            <v-chip v-if="world.id === worlds.currentWorld?.id" size="x-small" label color="accent" variant="tonal">open</v-chip>
                            <v-btn
                                v-else
                                size="small"
                                variant="text"
                                color="accent"
                                :loading="worlds.pending.open_world && openingPath === world.path"
                                :disabled="!!worlds.pending.open_world"
                                @click="open(world)"
                            >Open</v-btn>
                        </template>
                    </v-list-item>
                </v-list>

                <v-card variant="tonal" class="pa-3 create-world">
                    <div class="text-subtitle-2 mb-2">New world</div>
                    <v-form @submit.prevent="create">
                        <v-row dense>
                            <v-col cols="8">
                                <v-text-field v-model="newName" label="Name" density="compact" variant="outlined" hide-details></v-text-field>
                            </v-col>
                            <v-col cols="4">
                                <v-text-field v-model.number="newYear" label="Present year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details></v-text-field>
                            </v-col>
                        </v-row>
                        <v-btn
                            type="submit"
                            class="mt-3"
                            color="accent"
                            variant="flat"
                            size="small"
                            prepend-icon="mdi-plus"
                            :loading="!!worlds.pending.create_world"
                            :disabled="!newName.trim() || !validYear"
                        >Create world</v-btn>
                    </v-form>
                </v-card>
            </v-col>

            <v-col cols="12" md="7">
                <div v-if="!worlds.currentWorld" class="empty-hint pa-6 text-body-2">
                    Open a world to see its scenes, and browse it in the World tab.
                </div>
                <div v-else data-testid="open-world">
                    <div class="d-flex align-center ga-2 mb-1">
                        <span class="text-h5 world-name">{{ worlds.currentWorld.name }}</span>
                        <v-spacer></v-spacer>
                        <v-btn size="small" variant="flat" color="accent" prepend-icon="mdi-movie-open-plus" @click="newScene = true">New scene</v-btn>
                        <v-btn size="small" variant="tonal" color="accent" prepend-icon="mdi-earth-box" @click="$emit('open-world-tab')">Browse world</v-btn>
                    </div>
                    <div class="text-caption text-muted mb-4">
                        Present: <span class="world-date">{{ formatDate(worlds.calendar, worlds.currentWorld.present) }}</span>
                    </div>

                    <div class="text-overline text-muted">Scenes</div>
                    <div v-if="!worlds.scenes.length" class="empty-hint pa-4 text-body-2">
                        No scenes in this world yet.
                    </div>
                    <v-card
                        v-for="scene in worlds.scenes"
                        :key="scene.id"
                        variant="tonal"
                        class="pa-3 mb-2 scene-card"
                        data-testid="world-scene"
                    >
                        <div class="d-flex align-center ga-2">
                            <div>
                                <div class="text-subtitle-1">{{ scene.name }}</div>
                                <div class="text-caption text-muted d-flex align-center flex-wrap ga-1">
                                    <SceneStartDate :scene="scene" compact />
                                    <span v-if="scene.premise">{{ scene.premise }}</span>
                                </div>
                            </div>
                            <v-spacer></v-spacer>
                            <v-btn size="small" color="accent" variant="flat" prepend-icon="mdi-play" @click="play(scene)">Play</v-btn>
                        </div>
                    </v-card>
                </div>
            </v-col>
        </v-row>

        <NewSceneDialog v-if="worlds.currentWorld" v-model="newScene" />
    </div>
</template>

<script>
import { useWorldsStore, worldTarget } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';
import NewSceneDialog from './NewSceneDialog.vue';
import SceneStartDate from './SceneStartDate.vue';

// The Worlds home: list worlds, create one, open one, and play the open
// world's scenes, or start a new one from a prompt. Play asks TalemateApp
// to load the scene's `world://` target, the same way Load Scene loads a
// file. Each scene's start date can be moved from its card.

export default {
    name: 'WorldsHome',
    components: { NewSceneDialog, SceneStartDate },
    props: {
        visible: { type: Boolean, default: false },
    },
    emits: ['play-scene', 'open-world-tab'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            newName: '',
            newYear: 1000,
            openingPath: null,
            newScene: false,
        };
    },
    computed: {
        validYear() {
            return Number.isInteger(this.newYear) && this.newYear >= 1 && this.newYear <= 9999;
        },
    },
    watch: {
        // worlds can be made elsewhere (another window, a skill): look again
        // whenever the home is shown
        visible(visible) {
            if (visible) {
                this.refresh();
            }
        },
    },
    methods: {
        formatDate,
        refresh() {
            this.worlds.listWorlds();
            if (this.worlds.currentWorld) {
                this.worlds.listScenes();
            }
        },
        open(world) {
            this.openingPath = world.path;
            this.worlds.openWorld(world.path);
        },
        create() {
            if (!this.newName.trim() || !this.validYear) {
                return;
            }
            this.worlds.createWorld(this.newName.trim(), this.newYear);
            this.newName = '';
        },
        play(scene) {
            this.$emit('play-scene', worldTarget(this.worlds.currentWorld.path, scene.id));
        },
    },
};
</script>

<style scoped>
.worlds-home {
    max-width: 1200px;
    margin: 0 auto;
}

.world-name {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}

.world-date {
    color: rgb(var(--v-theme-date));
}

.empty-hint {
    background: rgba(var(--v-theme-on-surface), 0.03);
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
    color: rgb(var(--v-theme-muted));
}
</style>
