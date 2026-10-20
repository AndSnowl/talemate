<template>
    <v-btn
        class="mx-1"
        size="small"
        variant="tonal"
        color="accent"
        prepend-icon="mdi-page-next-outline"
        :disabled="disabled"
        @click="open = true"
    >Continue in a new scene</v-btn>

    <v-dialog v-model="open" max-width="900" scrollable>
        <v-card data-testid="continue-scene-dialog">
            <v-card-title class="d-flex align-center">
                <span class="dialog-title">Continue in a new scene</span>
                <v-spacer></v-spacer>
                <v-btn icon="mdi-close" variant="text" size="small" aria-label="Close" @click="open = false"></v-btn>
            </v-card-title>
            <v-card-text>
                <template v-if="!showingSetup">
                    <div class="text-caption text-muted mb-2">
                        The next scene starts where this one ends: same date, place and people, with a summary of what happened. Say what it's about.
                    </div>
                    <v-textarea
                        v-model="goal"
                        label="Next goal"
                        rows="2"
                        auto-grow
                        density="compact"
                        variant="outlined"
                        hide-details
                        :disabled="worlds.setupPending"
                    ></v-textarea>
                    <div class="d-flex mt-3">
                        <v-spacer></v-spacer>
                        <v-btn
                            color="accent"
                            variant="flat"
                            size="small"
                            prepend-icon="mdi-creation"
                            :loading="worlds.setupPending && mine"
                            :disabled="!goal.trim() || worlds.setupPending"
                            @click="setUp"
                        >Set up next scene</v-btn>
                    </div>
                </template>

                <v-alert v-if="mine && worlds.setupError" type="error" variant="tonal" density="compact" class="mt-3">
                    {{ worlds.setupError }}
                </v-alert>

                <SceneSetupCards action="continue_scene" class="mt-1" />
            </v-card-text>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import SceneSetupCards from './SceneSetupCards.vue';

// "Continue in a new scene", in the scene view of a loaded world scene: ask
// for the next goal, plan the next scene from where this one ended
// (`continue_scene`), and show the same setup step as a new scene. Start
// writes it and TalemateApp loads it.
export default {
    name: 'ContinueSceneButton',
    components: { SceneSetupCards },
    props: {
        sceneId: { type: String, required: true },
        disabled: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { open: false, goal: '' };
    },
    computed: {
        mine() {
            return this.worlds.setupRequest?.action === 'continue_scene';
        },
        showingSetup() {
            return this.mine && !!this.worlds.sceneSetup;
        },
    },
    watch: {
        open(open) {
            if (!open && this.mine) {
                this.worlds.closeSetup();
            }
        },
        'worlds.startedScene'(started) {
            if (started && this.open) {
                this.goal = '';
                this.open = false;
            }
        },
    },
    methods: {
        setUp() {
            if (this.goal.trim()) {
                this.worlds.continueScene(this.sceneId, this.goal.trim());
            }
        },
    },
};
</script>

<style scoped>
.dialog-title {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}
</style>
