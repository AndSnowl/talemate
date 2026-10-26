<template>
    <div class="thing-numbers">
        <div v-for="row in rows" :key="row.field" class="field d-flex align-center ga-2" :data-testid="'numbers-' + row.field">
            <span class="field-label">{{ row.label }}</span>
            <template v-if="editing === row.field">
                <v-text-field
                    v-model.number="draft"
                    :label="row.label"
                    type="number"
                    min="0"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="number-input"
                ></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!validNumber(draft)" @click="saveNumber(row.field)">Save</v-btn>
                <v-btn variant="text" size="small" :disabled="busy" @click="cancel">Cancel</v-btn>
            </template>
            <template v-else>
                <span :class="{ inherited: row.inherited }">{{ row.text }}</span>
                <span v-if="row.inherited" class="inherited-note">inherited</span>
                <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" :aria-label="'Edit ' + row.label.toLowerCase()" @click="startNumber(row)"></v-btn>
            </template>
        </div>

        <div class="field d-flex ga-2" data-testid="numbers-measures">
            <span class="field-label">Measures</span>
            <div v-if="editing === 'measures'" class="flex-grow-1">
                <div v-for="(measure, index) in measuresDraft" :key="index" class="d-flex align-center ga-2 mb-2">
                    <v-text-field v-model="measure.name" label="Measure" density="compact" variant="outlined" hide-details class="measure-name"></v-text-field>
                    <v-text-field v-model.number="measure.min" label="Min" type="number" min="0" density="compact" variant="outlined" hide-details class="measure-number"></v-text-field>
                    <v-text-field v-model.number="measure.max" label="Max" type="number" min="0" density="compact" variant="outlined" hide-details class="measure-number"></v-text-field>
                    <v-text-field v-model="measure.unit" label="Unit" density="compact" variant="outlined" hide-details class="measure-unit"></v-text-field>
                    <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Remove measure" @click="measuresDraft.splice(index, 1)"></v-btn>
                </div>
                <div class="d-flex ga-2">
                    <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addMeasure">Add measure</v-btn>
                    <v-spacer></v-spacer>
                    <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!measuresValid" @click="saveMeasures">Save</v-btn>
                    <v-btn variant="text" size="small" :disabled="busy" @click="cancel">Cancel</v-btn>
                </div>
            </div>
            <template v-else>
                <div class="flex-grow-1">
                    <div v-if="!measures.length" class="text-muted">none</div>
                    <div v-for="measure in measures" :key="measure.name" class="measure">
                        <span class="measure-label">{{ measure.name }}</span>
                        <span :class="{ inherited: measure.inherited }">{{ measure.text }}</span>
                        <span v-if="measure.inherited" class="inherited-note">inherited</span>
                    </div>
                </div>
                <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit measures" @click="startMeasures"></v-btn>
            </template>
        </div>
    </div>
</template>

<script>
import { formatNumber, ownMeasures, rangeText } from './worldNumbers.js';

const NUMBER_FIELDS = [
    { field: 'lifespan', label: 'Lifespan', unit: ' years' },
    { field: 'adult_age', label: 'Adult at', unit: '' },
];

function isNumber(value) {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

// A species, race or mix's numbers: lifespan, adulthood and measures, each
// editable. `fields` are its own values, `numbers` the resolved ones: on a
// race or mix an unset value shows the one it inherits (resolved along its
// lineage), dimmed. A save emits `set(field, value)`: the page writes it
// (`set_field`), a draft keeps it (`setDraftNumber`). The editor closes
// once `fields` change after a save: the page's reply, or the draft's
// copy at once; a save that fails (`busy` ends, no new fields) keeps it.
export default {
    name: 'ThingNumbers',
    props: {
        fields: { type: Object, required: true },
        numbers: { type: Object, default: null },
        busy: { type: Boolean, default: false },
    },
    emits: ['set'],
    data() {
        return {
            // the field being edited, its number draft, the measures draft
            editing: null,
            draft: null,
            measuresDraft: [],
            sent: false,
        };
    },
    computed: {
        rows() {
            return NUMBER_FIELDS.map(({ field, label, unit }) => {
                const own = this.fields[field];
                // its own value as soon as it's set (a draft's numbers
                // are rendered again a moment later)
                const value = own ?? this.numbers?.[field];
                return {
                    field,
                    label,
                    own,
                    text: value == null ? 'not set' : formatNumber(value) + unit,
                    inherited: own == null && value != null,
                };
            });
        },
        measures() {
            const own = Object.fromEntries(ownMeasures(this.fields).map((m) => [m.name, m]));
            const resolved = { ...(this.numbers?.measures || {}), ...own };
            return Object.entries(resolved).map(([name, range]) => ({
                name,
                text: rangeText(range),
                inherited: !(name in own),
            }));
        },
        measuresValid() {
            return this.measuresDraft.every(
                (m) => m.name?.trim() && m.unit?.trim() && isNumber(m.min) && isNumber(m.max) && m.min <= m.max,
            );
        },
    },
    watch: {
        // the reply to this editor's own save
        fields() {
            if (this.sent) {
                this.cancel();
            }
        },
        busy(now) {
            // the save failed (no reply replaced the fields): keep the editor
            if (!now) {
                this.sent = false;
            }
        },
    },
    methods: {
        validNumber: isNumber,
        cancel() {
            this.editing = null;
            this.sent = false;
        },
        startNumber(row) {
            this.editing = row.field;
            this.draft = row.own ?? this.numbers?.[row.field] ?? null;
        },
        saveNumber(field) {
            if (!isNumber(this.draft)) {
                return;
            }
            this.$emit('set', field, this.draft);
            this.sent = true;
        },
        startMeasures() {
            this.editing = 'measures';
            this.measuresDraft = ownMeasures(this.fields).map((measure) => ({ ...measure }));
        },
        addMeasure() {
            this.measuresDraft.push({ name: '', min: null, max: null, unit: 'ft' });
        },
        saveMeasures() {
            if (!this.measuresValid) {
                return;
            }
            const measures = this.measuresDraft.map((m) => ({ name: m.name.trim(), min: m.min, max: m.max, unit: m.unit.trim() }));
            this.$emit('set', 'measures', measures);
            this.sent = true;
        },
    },
};
</script>

<style scoped>
.field {
    margin: 4px 0;
}

.field-label {
    min-width: 80px;
    font-weight: 600;
    color: rgb(var(--v-theme-muted));
}

.inherited {
    opacity: 0.6;
}

.measure .inherited-note {
    margin-left: 6px;
}

.inherited-note {
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
}

.measure-label {
    display: inline-block;
    min-width: 80px;
    text-transform: capitalize;
}

.number-input {
    max-width: 140px;
}

.measure-name {
    flex: 2 1 120px;
}

.measure-number {
    flex: 1 1 70px;
}

.measure-unit {
    flex: 1 1 60px;
}
</style>
