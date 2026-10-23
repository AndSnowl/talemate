<template>
    <v-card variant="flat" class="curation-settings pa-4" data-testid="curation-settings">
        <div class="text-subtitle-1 mb-1">Curation settings</div>
        <div class="text-caption text-muted mb-3">How much of the world a prompt brings in, and when a new fact counts as one the world already holds.</div>
        <div v-if="!form" class="d-flex justify-center pa-4">
            <v-progress-circular indeterminate color="accent"></v-progress-circular>
        </div>
        <v-form v-else @submit.prevent="save">
            <div v-for="knob in knobs" :key="knob.key" class="knob d-flex align-center flex-wrap ga-3 mb-2">
                <v-text-field
                    v-model.number="form[knob.key]"
                    :label="knob.label"
                    type="number"
                    :min="knob.min"
                    :max="knob.max"
                    :step="knob.step"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field"
                    :error="!valid(knob)"
                ></v-text-field>
                <span class="text-caption text-muted flex-grow-1">{{ knob.help }} <span class="default">(default {{ defaults[knob.key] }})</span></span>
            </div>
            <div class="d-flex align-center ga-2 mt-3">
                <v-btn type="submit" color="accent" variant="flat" size="small" :loading="!!worlds.pending.set_curation" :disabled="!allValid || !changed">Save</v-btn>
                <v-btn variant="text" size="small" :disabled="!!worlds.pending.set_curation" @click="toDefaults">Defaults</v-btn>
                <span v-if="worlds.curationSaved && !changed" class="text-caption text-muted" data-testid="curation-saved">Saved.</span>
            </div>
        </v-form>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// `talemate.world.curation.CurationSettings`, with their ranges
const KNOBS = [
    { key: 'reach', label: 'How far out (steps)', min: 1, max: 3, step: 1, integer: true, help: 'Steps through links a create, Fill or scene looks for nearby entries.' },
    { key: 'entries', label: 'Entries per prompt', min: 0, max: null, step: 1, integer: true, help: 'The most nearby entries a prompt brings in.' },
    { key: 'facts_per_entry', label: 'Facts per entry', min: 0, max: null, step: 1, integer: true, help: 'The most facts of each it brings.' },
    { key: 'repeat_threshold', label: 'Repeat threshold', min: 0, max: 1, step: 0.05, integer: false, help: 'Word overlap at which a new fact shows as one the world already holds.' },
    { key: 'repeat_untick_threshold', label: 'Untick repeats at', min: 0, max: 1, step: 0.05, integer: false, help: 'Word overlap at which a repeat arrives unticked; below it, it stays ticked.' },
    { key: 'date_threshold', label: 'Date disagreement at', min: 0, max: 1, step: 0.05, integer: false, help: 'Word overlap at which two dated facts with different years show as disagreeing on a timeline.' },
    { key: 'timeline_reach', label: 'Timeline reach (steps)', min: 0, max: 3, step: 1, integer: true, help: 'How far out a timeline gathers dated facts from its parts.' },
];

// The World tab's curation settings (spec goal 10): the knobs the world
// keeps (`get_curation`), each with its range and default; Save sends only
// the ones changed (`set_curation`), Defaults puts the form back to the
// defaults (saved on Save). A knob out of range can't be saved.
export default {
    name: 'CurationSettings',
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { form: null, knobs: KNOBS };
    },
    computed: {
        settings() {
            return this.worlds.curation?.settings || null;
        },
        defaults() {
            return this.worlds.curation?.defaults || {};
        },
        // the knobs the form changes
        changes() {
            if (!this.form || !this.settings) {
                return {};
            }
            return Object.fromEntries(KNOBS.filter((knob) => this.form[knob.key] !== this.settings[knob.key]).map((knob) => [knob.key, this.form[knob.key]]));
        },
        changed() {
            return Object.keys(this.changes).length > 0;
        },
        allValid() {
            return KNOBS.every((knob) => this.valid(knob));
        },
    },
    watch: {
        // the world's knobs, as asked for or as saved
        settings: {
            handler(settings) {
                this.form = settings ? { ...settings } : null;
            },
            immediate: true,
        },
    },
    mounted() {
        this.worlds.curationSaved = false;
        this.worlds.getCuration();
    },
    methods: {
        valid(knob) {
            const value = this.form?.[knob.key];
            if (typeof value !== 'number' || Number.isNaN(value)) {
                return false;
            }
            if (knob.integer && !Number.isInteger(value)) {
                return false;
            }
            return value >= knob.min && (knob.max === null || value <= knob.max);
        },
        save() {
            if (this.allValid && this.changed) {
                this.worlds.setCuration(this.changes);
            }
        },
        toDefaults() {
            this.form = { ...this.form, ...this.defaults };
        },
    },
};
</script>

<style scoped>
.curation-settings {
    background: rgb(var(--v-theme-raised));
    max-width: 820px;
}

.field {
    flex: none;
    width: 200px;
}

.default {
    opacity: 0.8;
}
</style>
