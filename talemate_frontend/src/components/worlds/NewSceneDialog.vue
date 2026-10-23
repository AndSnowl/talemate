<template>
    <v-dialog :model-value="modelValue" max-width="900" scrollable @update:model-value="close">
        <v-card class="new-scene" data-testid="new-scene-dialog">
            <v-card-title class="d-flex align-center">
                <span class="dialog-title">New scene</span>
                <v-spacer></v-spacer>
                <v-btn icon="mdi-close" variant="text" size="small" aria-label="Close" @click="close(false)"></v-btn>
            </v-card-title>

            <v-card-text>
                <template v-if="!showingSetup">
                    <div class="text-caption text-muted mb-1">
                        Who you are, where, doing what. Rough is fine; whatever you leave open comes from the world, or is invented.
                    </div>
                    <NameHighlightInput
                        ref="prompt"
                        v-model="prompt"
                        v-model:picks="picks"
                        v-model:refs="refs"
                        label="Storyline"
                        :show-label="false"
                        :at="start"
                        :invented="invented"
                        :placeholder="placeholder"
                        :disabled="worlds.setupPending"
                    />
                    <div class="text-caption text-muted mt-1">
                        <span class="legend matched">Blue</span> is a world thing (hover to change it), and
                        <span class="legend suggested">dotted</span> may be one.
                        <span class="legend new">Yellow</span> will be invented for this scene.
                        Right-click to add a reference.
                    </div>

                    <div class="d-flex flex-wrap align-center ga-2 mt-3">
                        <v-select
                            v-model="player"
                            label="You play"
                            :items="playerOptions"
                            item-title="name"
                            item-value="id"
                            density="compact"
                            variant="outlined"
                            hide-details
                            class="picker"
                            :disabled="worlds.setupPending"
                        ></v-select>
                        <v-select
                            v-model="startChoice"
                            label="Starts"
                            :items="startOptions"
                            item-title="title"
                            item-value="value"
                            density="compact"
                            variant="outlined"
                            hide-details
                            class="picker picker-wide"
                            :disabled="worlds.setupPending"
                        ></v-select>
                        <v-text-field
                            v-if="startChoice === CUSTOM_START"
                            v-model.number="startYear"
                            label="Year"
                            type="number"
                            min="1"
                            max="9999"
                            density="compact"
                            variant="outlined"
                            hide-details
                            class="picker-year"
                            :disabled="worlds.setupPending"
                        ></v-text-field>
                        <v-spacer></v-spacer>
                        <v-btn
                            color="accent"
                            variant="flat"
                            size="small"
                            prepend-icon="mdi-creation"
                            :loading="worlds.setupPending && mine"
                            :disabled="!prompt.trim() || worlds.setupPending || !validStart"
                            @click="setUp"
                        >Set up scene</v-btn>
                    </div>
                </template>

                <v-alert v-if="mine && worlds.setupError" type="error" variant="tonal" density="compact" class="mt-3">
                    {{ worlds.setupError }}
                </v-alert>

                <SceneSetupCards action="plan_scene" class="mt-1" />
            </v-card-text>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, formatDate } from './worldDates.js';
import { linkPayload } from './nameHighlights.js';
import { actsInWorld } from './worldKinds.js';
import NameHighlightInput from './NameHighlightInput.vue';
import SceneSetupCards from './SceneSetupCards.vue';

// the "Starts" choices that aren't a scene's end
const NOW_START = 'now';
const CUSTOM_START = 'custom';

// The new-scene dialog: one storyline prompt, with the world thing names in
// it highlighted as you type (`NameHighlightInput`), each pick changeable
// from its hover popover; who you play and when it starts; then "Set up
// scene" (`plan_scene`) shows the setup step, whose Start writes the scene
// (`start_scene`). TalemateApp loads the started scene.
export default {
    name: 'NewSceneDialog',
    components: { NameHighlightInput, SceneSetupCards },
    props: {
        modelValue: { type: Boolean, default: false },
    },
    emits: ['update:modelValue'],
    setup() {
        return { worlds: useWorldsStore(), CUSTOM_START };
    },
    data() {
        return {
            prompt: '',
            // pickKey(name) -> thing id or NEW_THING
            picks: {},
            // pickKey(name) -> {id, text}: references added by hand
            refs: {},
            player: null,
            startChoice: NOW_START,
            startYear: null,
            placeholder: 'Maren has headed out from Sallowford to forage for bleakcap, but finds more than she bargained for…',
            // the names the last setup invented (kept after Edit)
            lastInvented: [],
        };
    },
    computed: {
        mine() {
            return this.worlds.setupRequest?.action === 'plan_scene';
        },
        showingSetup() {
            return this.mine && !!this.worlds.sceneSetup;
        },
        matches() {
            return this.worlds.matchesFor(this.prompt, this.start);
        },
        // names the last setup invented, highlighted where the prompt has them
        invented() {
            const setup = this.mine ? this.worlds.sceneSetup?.setup : null;
            return setup?.invented || this.lastInvented;
        },
        playerOptions() {
            // a character, or a real being (only those act in the world)
            const beings = (this.worlds.things.being || []).filter((thing) => !thing.stub && actsInWorld(thing));
            return [{ id: null, name: 'Let the setup choose' }, ...(this.worlds.things.character || []), ...beings];
        },
        startOptions() {
            const calendar = this.worlds.calendar;
            const now = this.worlds.currentWorld?.now;
            return [
                { title: `Now (${formatDate(calendar, now)})`, value: NOW_START },
                ...this.worlds.scenes.map((scene) => ({
                    title: `After “${scene.name}” (${formatDate(calendar, scene.end)})`,
                    value: scene.id,
                })),
                { title: 'A year…', value: CUSTOM_START },
            ];
        },
        start() {
            if (this.startChoice === NOW_START) {
                return null;
            }
            if (this.startChoice === CUSTOM_START) {
                return this.validYear(this.startYear) ? dateOf(this.startYear) : null;
            }
            const scene = this.worlds.scenes.find((s) => s.id === this.startChoice);
            return scene ? { instant: scene.end.instant, precision: scene.end.precision } : null;
        },
        validStart() {
            return this.startChoice !== CUSTOM_START || this.validYear(this.startYear);
        },
    },
    watch: {
        modelValue(open) {
            if (open) {
                this.$nextTick(() => this.$refs.prompt?.focus());
            }
        },
        'worlds.sceneSetup'(planned) {
            if (planned && this.mine) {
                this.lastInvented = planned.setup.invented || [];
            }
        },
        // the scene started: TalemateApp loads it, so the dialog is done
        'worlds.startedScene'(started) {
            if (started && this.modelValue) {
                this.reset();
                this.$emit('update:modelValue', false);
            }
        },
    },
    methods: {
        validYear(year) {
            return Number.isInteger(year) && year >= 1 && year <= 9999;
        },
        setUp() {
            if (!this.prompt.trim() || !this.validStart) {
                return;
            }
            const links = linkPayload(this.matches, this.picks, this.refs, this.prompt);
            this.worlds.planScene(this.prompt.trim(), links.picks, this.player, this.start, links.newNames);
        },
        reset() {
            this.prompt = '';
            this.picks = {};
            this.refs = {};
            this.player = null;
            this.startChoice = NOW_START;
            this.startYear = null;
            this.lastInvented = [];
        },
        close(open) {
            if (open) {
                return;
            }
            if (this.mine) {
                this.worlds.closeSetup();
            }
            this.$emit('update:modelValue', false);
        },
    },
};
</script>

<style scoped>
.dialog-title {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}

.legend {
    padding: 0 2px;
    border-radius: 2px;
}

.legend.matched {
    background: rgba(var(--v-theme-highlight1), 0.25);
    border-bottom: 2px solid rgb(var(--v-theme-highlight1));
}

.legend.suggested {
    border-bottom: 2px dotted rgb(var(--v-theme-highlight1));
}

.legend.new {
    background: rgba(var(--v-theme-warning), 0.2);
    border-bottom: 2px solid rgb(var(--v-theme-warning));
}

.picker {
    max-width: 220px;
    min-width: 180px;
}

.picker-wide {
    max-width: 320px;
}

.picker-year {
    max-width: 110px;
}
</style>
