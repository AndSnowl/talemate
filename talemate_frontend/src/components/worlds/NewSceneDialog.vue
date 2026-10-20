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
                    <div class="prompt-box">
                        <textarea
                            ref="prompt"
                            v-model="prompt"
                            class="prompt-input"
                            aria-label="Storyline"
                            rows="3"
                            :placeholder="placeholder"
                            :disabled="worlds.setupPending"
                            @input="grow"
                        ></textarea>
                        <div class="prompt-layer" aria-hidden="true">
                            <template v-for="segment in segments" :key="segment.start">
                                <v-menu v-if="segment.match" open-on-hover location="bottom start" :open-delay="100">
                                    <template #activator="{ props }">
                                        <mark
                                            v-bind="props"
                                            class="name"
                                            :class="segment.state"
                                            data-testid="name-match"
                                            @mousedown.prevent="caretAt(segment.end)"
                                        >{{ segment.text }}</mark>
                                    </template>
                                    <v-list density="compact" class="name-popover" data-testid="name-popover">
                                        <v-list-item
                                            v-for="candidate in segment.match.candidates"
                                            :key="candidate.id"
                                            :active="pickedId(segment.match) === candidate.id"
                                            :aria-selected="String(pickedId(segment.match) === candidate.id)"
                                            color="highlight1"
                                            data-testid="name-candidate"
                                            @click="pick(segment.match, candidate.id)"
                                        >
                                            <template #prepend>
                                                <v-icon size="small">{{ pickedId(segment.match) === candidate.id ? 'mdi-check' : 'mdi-blank' }}</v-icon>
                                            </template>
                                            <v-list-item-title>{{ candidate.name }}</v-list-item-title>
                                            <v-list-item-subtitle>{{ candidate.kind }}</v-list-item-subtitle>
                                        </v-list-item>
                                        <v-divider></v-divider>
                                        <v-list-item
                                            :active="pickedId(segment.match) === NEW_THING"
                                            color="warning"
                                            prepend-icon="mdi-pencil"
                                            @click="pick(segment.match, NEW_THING)"
                                        >
                                            <v-list-item-title>Treat as new</v-list-item-title>
                                        </v-list-item>
                                    </v-list>
                                </v-menu>
                                <mark v-else-if="segment.state" class="name new" data-testid="name-new">{{ segment.text }}</mark>
                                <template v-else>{{ segment.text }}</template>
                            </template>&#8203;
                        </div>
                    </div>
                    <div class="text-caption text-muted mt-1">
                        <span class="legend matched">Blue</span> is a world thing (hover to change it).
                        <span class="legend new">Yellow</span> will be invented for this scene.
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
import { NEW_THING, pickKey, pickedId, picksPayload, promptSegments } from './nameHighlights.js';
import SceneSetupCards from './SceneSetupCards.vue';

// how long typing pauses before the names are looked up
const MATCH_DEBOUNCE_MS = 300;

// the "Starts" choices that aren't a scene's end
const NOW_START = 'now';
const CUSTOM_START = 'custom';

// The new-scene dialog: one storyline prompt, with the world thing names in
// it highlighted as you type (`match_names`), each pick changeable from its
// hover popover; who you play and when it starts; then "Set up scene"
// (`plan_scene`) shows the setup step, whose Start writes the scene
// (`start_scene`). TalemateApp loads the started scene.
//
// The highlights are a layer over the textarea, in the same font and box,
// with transparent text: only the marks show (and take the hover).
export default {
    name: 'NewSceneDialog',
    components: { SceneSetupCards },
    props: {
        modelValue: { type: Boolean, default: false },
    },
    emits: ['update:modelValue'],
    setup() {
        return { worlds: useWorldsStore(), NEW_THING, CUSTOM_START };
    },
    data() {
        return {
            prompt: '',
            // pickKey(name) -> thing id or NEW_THING
            picks: {},
            player: null,
            startChoice: NOW_START,
            startYear: null,
            placeholder: 'Maren has headed out from Sallowford to forage for bleakcap, but finds more than she bargained for…',
            matchTimer: null,
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
            return this.worlds.nameMatchesText === this.prompt ? this.worlds.nameMatches : [];
        },
        // names the last setup invented, highlighted where the prompt has them
        invented() {
            const setup = this.mine ? this.worlds.sceneSetup?.setup : null;
            return setup?.invented || this.lastInvented;
        },
        segments() {
            return promptSegments(this.prompt, this.matches, this.picks, this.invented);
        },
        playerOptions() {
            return [{ id: null, name: 'Let the setup choose' }, ...(this.worlds.things.character || [])];
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
        prompt() {
            this.scheduleMatch();
        },
        start() {
            this.scheduleMatch();
        },
        modelValue(open) {
            if (open) {
                this.$nextTick(() => this.$refs.prompt?.focus());
            }
        },
        showingSetup(showing) {
            // back from the setup (Edit): the textarea is drawn again
            if (!showing) {
                this.$nextTick(this.grow);
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
    beforeUnmount() {
        clearTimeout(this.matchTimer);
    },
    methods: {
        pickedId(match) {
            return pickedId(match, this.picks);
        },
        validYear(year) {
            return Number.isInteger(year) && year >= 1 && year <= 9999;
        },
        scheduleMatch() {
            clearTimeout(this.matchTimer);
            this.matchTimer = setTimeout(() => this.worlds.matchNames(this.prompt, this.start), MATCH_DEBOUNCE_MS);
        },
        pick(match, id) {
            this.picks = { ...this.picks, [pickKey(match.text)]: id };
        },
        caretAt(offset) {
            const input = this.$refs.prompt;
            if (input) {
                input.focus();
                input.setSelectionRange(offset, offset);
            }
        },
        grow() {
            const input = this.$refs.prompt;
            if (input) {
                input.style.height = 'auto';
                input.style.height = `${input.scrollHeight + 2}px`;
            }
        },
        setUp() {
            if (!this.prompt.trim() || !this.validStart) {
                return;
            }
            this.worlds.planScene(this.prompt.trim(), picksPayload(this.matches, this.picks), this.player, this.start);
        },
        reset() {
            this.prompt = '';
            this.picks = {};
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

.prompt-box {
    position: relative;
}

/* the textarea and the highlight layer share one box, font and wrapping */
.prompt-input,
.prompt-layer {
    font: inherit;
    font-size: 14px;
    line-height: 1.7;
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 4px;
    white-space: pre-wrap;
    overflow-wrap: break-word;
    word-break: normal;
    letter-spacing: normal;
}

.prompt-input {
    display: block;
    width: 100%;
    min-height: 84px;
    resize: none;
    overflow: hidden;
    color: rgb(var(--v-theme-on-surface));
    background: rgb(var(--v-theme-background));
    border-color: rgb(var(--v-theme-border));
    outline: none;
}

.prompt-input:focus {
    border-color: rgb(var(--v-theme-accent));
}

.prompt-layer {
    position: absolute;
    inset: 0;
    color: transparent;
    pointer-events: none;
    overflow: hidden;
}

.name {
    color: transparent;
    border-radius: 2px;
    pointer-events: auto;
    cursor: pointer;
}

.name.matched {
    background: rgba(var(--v-theme-highlight1), 0.25);
    border-bottom: 2px solid rgb(var(--v-theme-highlight1));
}

.name.new {
    background: rgba(var(--v-theme-warning), 0.2);
    border-bottom: 2px solid rgb(var(--v-theme-warning));
}

.name-popover {
    min-width: 220px;
}

.legend {
    padding: 0 2px;
    border-radius: 2px;
}

.legend.matched {
    background: rgba(var(--v-theme-highlight1), 0.25);
    border-bottom: 2px solid rgb(var(--v-theme-highlight1));
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
