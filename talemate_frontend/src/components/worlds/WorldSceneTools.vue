<template>
    <div v-if="target" class="d-flex align-center" data-testid="world-scene-tools">
        <SceneStartDate v-if="record" :scene="record" :disabled="disabled" compact />
        <ContinueSceneButton :scene-id="target.sceneId" :disabled="disabled || !worldOpen" />
        <span v-if="!worldOpen" class="text-caption text-muted ml-1" data-testid="world-not-open">
            {{ worlds.pending.open_world ? "Opening the scene's world…" : "The scene's world isn't open" }}
        </span>
    </div>
</template>

<script>
import { parseWorldTarget, useWorldsStore } from '@/stores/worlds.js';
import ContinueSceneButton from './ContinueSceneButton.vue';
import SceneStartDate from './SceneStartDate.vue';

// The scene toolbar's world-scene tools, shown only when the loaded scene
// is a world scene (its path is a `world://` target): its start date (to
// move it) and "continue in a new scene". Both act on the open world, so
// the scene's world is opened if another one is; until it is, Continue is
// disabled and says why.
export default {
    name: 'WorldSceneTools',
    components: { ContinueSceneButton, SceneStartDate },
    props: {
        // TalemateApp's scene: `scene.data` is the scene status
        scene: { type: Object, default: null },
        disabled: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        scenePath() {
            return this.scene?.data?.path || null;
        },
        target() {
            return parseWorldTarget(this.scenePath);
        },
        worldOpen() {
            return !!this.target && this.worlds.currentWorld?.path === this.target.worldPath;
        },
        record() {
            if (!this.worldOpen) {
                return null;
            }
            return this.worlds.scenes.find((scene) => scene.id === this.target.sceneId) || null;
        },
    },
    watch: {
        // by path, not by `target`: every scene status makes a new object
        scenePath: {
            handler() {
                this.ensureWorld();
            },
            immediate: true,
        },
        'worlds.connected'() {
            this.ensureWorld();
        },
    },
    methods: {
        ensureWorld() {
            if (!this.target || !this.worlds.connected || this.worldOpen || this.worlds.pending.open_world) {
                return;
            }
            this.worlds.openWorld(this.target.worldPath);
        },
    },
};
</script>
