<template>
    <v-card variant="tonal" class="pa-3 fact-form" data-testid="fact-form" @keydown.esc="escape">
        <template v-if="form.mode === 'dates'">
            <div class="text-caption text-muted mb-2">When it's true: leave a year empty for an open start or end.</div>
            <div class="d-flex align-center flex-wrap ga-2">
                <v-text-field v-model.number="form.fromYear" label="From year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year" autofocus></v-text-field>
                <v-text-field v-model.number="form.untilYear" label="Until year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year"></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!datesValid" @click="$emit('save')">Save</v-btn>
                <v-btn variant="text" size="small" :disabled="busy" @click="$emit('cancel')">Cancel</v-btn>
            </div>
        </template>
        <template v-else-if="form.mode === 'end'">
            <div class="text-caption text-muted mb-2">The fact stops being true from this year on.</div>
            <div class="d-flex align-center ga-2">
                <v-text-field v-model.number="form.untilYear" label="Until year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year"></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!validYear(form.untilYear)" @click="$emit('save')">End</v-btn>
                <v-btn variant="text" size="small" :disabled="busy" @click="$emit('cancel')">Cancel</v-btn>
            </div>
        </template>
        <template v-else>
            <div v-if="form.mode === 'override'" class="text-caption text-muted mb-2">Replaces {{ form.replaces }}</div>
            <NameHighlightInput
                v-model="form.text"
                v-model:picks="form.picks"
                v-model:refs="form.refs"
                v-model:stubs="form.stubs"
                :linked="linked"
                @pick-link="pickLink"
                label="Fact"
                :rows="1"
                dense
:offer-stubs="!form.draft"
                :at="worlds.thingAt"
                :exclude="exclude"
                class="mb-2"
            />
            <div class="d-flex flex-wrap align-center ga-2">
                <v-select v-model="form.category" label="Category" :items="categories" density="compact" variant="outlined" hide-details class="category"></v-select>
                <template v-if="form.mode !== 'override'">
                    <v-text-field v-model.number="form.fromYear" label="From year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year"></v-text-field>
                    <v-text-field v-model.number="form.untilYear" label="Until year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year"></v-text-field>
                </template>
            </div>
            <div v-if="form.mode !== 'override'" class="text-caption text-muted mt-1">{{ form.category === 'timeline' ? 'A timeline fact needs its year (From).' : 'Leave a year empty for an open start or end.' }}</div>
            <div class="d-flex ga-2 mt-2">
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!valid" @click="$emit('save')">Save</v-btn>
                <v-btn variant="text" size="small" :disabled="busy" @click="$emit('cancel')">Cancel</v-btn>
                <v-spacer></v-spacer>
                <v-btn v-if="form.mode === 'edit' && removable" variant="text" size="small" color="danger" prepend-icon="mdi-delete" :disabled="busy" @click="$emit('remove')">Remove</v-btn>
            </div>
        </template>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { factFormValid, locateLinks } from './nameHighlights.js';
import { escapeCloses } from './worldKinds.js';
import NameHighlightInput from './NameHighlightInput.vue';

// The inline form ThingPage opens to add, edit (correct) or end a fact,
// change only its dates ("Change dates": `dates`), or to override an
// inherited one (text and category only: an override isn't dated). The
// same form edits a draft's fact (`form.draft`: no stubs offered, since
// the draft's text is linked by name on accept). It edits the `form` object ThingPage owns; ThingPage sends the
// change. The text is a `NameHighlightInput` (its names highlighted, open
// to re-picks, Add reference and "make a stub"), holding the fact's words
// as they read, with its links kept by position (`form.links`, found again
// in the text as it's edited); `form.picks`, `form.refs` (Add reference)
// and `form.stubs` are the owner's choices. Esc cancels it (unless it
// closes one of its own menus or popovers first).
function isYear(value) {
    return Number.isInteger(value) && value >= 1 && value <= 9999;
}

export default {
    name: 'ThingFactForm',
    components: { NameHighlightInput },
    props: {
        form: { type: Object, required: true },
        categories: { type: Array, required: true },
        busy: { type: Boolean, default: false },
        // false: an edited fact can't be removed here
        removable: { type: Boolean, default: true },
    },
    emits: ['save', 'cancel', 'remove'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        // the fact's existing links, where its text now has them
        linked() {
            return locateLinks(this.form.text || '', this.form.links || []);
        },
        // a thing's facts never reference the thing itself
        exclude() {
            return this.worlds.selectedThingId ? [this.worlds.selectedThingId] : [];
        },
        valid() {
            return factFormValid(this.form);
        },
        datesValid() {
            const ok = (year) => year === null || year === '' || year === undefined || isYear(year);
            return ok(this.form.fromYear) && ok(this.form.untilYear);
        },
    },
    methods: {
        validYear: isYear,
        // Esc closes the form, unless a menu or popover of it is open (Esc
        // closes that first)
        escape(event) {
            if (!this.busy && escapeCloses(event)) {
                this.$emit('cancel');
            }
        },
        // the owner re-picked one existing link (or turned it to new)
        pickLink({ index, id }) {
            this.form.links = this.form.links.map((link, i) => (i === index ? { ...link, ref: id } : link));
        },
    },
};
</script>

<style scoped>
.year {
    flex: 1 1 140px;
    max-width: 180px;
}

.category {
    flex: 1 1 180px;
    max-width: 240px;
}
</style>
