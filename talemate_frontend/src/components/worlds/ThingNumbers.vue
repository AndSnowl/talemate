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
import { useWorldsStore } from '@/stores/worlds.js';
import { formatNumber, ownMeasures, rangeText } from './worldNumbers.js';

const NUMBER_FIELDS = [
    { field: 'lifespan', label: 'Lifespan', unit: ' years' },
    { field: 'adult_age', label: 'Adult at', unit: '' },
];

function isNumber(value) {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

// A species, race or mix page's numbers: lifespan, adulthood and measures,
// each editable (`set_field`). On a race or mix page an unset value shows
// the one it inherits (`numbers`, resolved along its lineage), dimmed.
export default {
    name: 'ThingNumbers',
    setup() {
        return { worlds: useWorldsStore() };
    },
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
        thing() {
            return this.worlds.thing;
        },
        busy() {
            return !!this.worlds.pending.set_field;
        },
        rows() {
            return NUMBER_FIELDS.map(({ field, label, unit }) => {
                const value = this.thing.numbers?.[field];
                const own = this.thing.fields[field];
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
            const own = new Set(ownMeasures(this.thing.fields).map((measure) => measure.name));
            return Object.entries(this.thing.numbers?.measures || {}).map(([name, range]) => ({
                name,
                text: rangeText(range),
                inherited: !own.has(name),
            }));
        },
        measuresValid() {
            return this.measuresDraft.every(
                (m) => m.name?.trim() && m.unit?.trim() && isNumber(m.min) && isNumber(m.max) && m.min <= m.max,
            );
        },
    },
    watch: {
        thing(thing, before) {
            // another thing, or the reply to this editor's own save
            if (!thing || thing.id !== before?.id || this.sent) {
                this.cancel();
            }
        },
        busy(now) {
            // the save failed (no reply replaced the thing): keep the editor
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
            this.draft = row.own ?? this.thing.numbers?.[row.field] ?? null;
        },
        saveNumber(field) {
            if (!isNumber(this.draft)) {
                return;
            }
            this.worlds.setField(field, this.draft);
            this.sent = true;
        },
        startMeasures() {
            this.editing = 'measures';
            this.measuresDraft = ownMeasures(this.thing.fields).map((measure) => ({ ...measure }));
        },
        addMeasure() {
            this.measuresDraft.push({ name: '', min: null, max: null, unit: 'ft' });
        },
        saveMeasures() {
            if (!this.measuresValid) {
                return;
            }
            const measures = this.measuresDraft.map((m) => ({ name: m.name.trim(), min: m.min, max: m.max, unit: m.unit.trim() }));
            this.worlds.setField('measures', measures);
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
