<template>
    <div class="tie-form d-flex align-center flex-wrap ga-2" data-testid="tie-form" @keydown.esc="$emit('cancel')">
        <v-select
            v-model="form.sphereId"
            :items="spheres"
            item-title="name"
            item-value="id"
            label="Sphere"
            density="compact"
            variant="outlined"
            hide-details
            class="picker"
            :disabled="busy"
            data-testid="tie-sphere"
        ></v-select>
        <v-select
            v-if="form.sphereId"
            v-model="form.within"
            :items="withinOptions"
            item-title="name"
            item-value="id"
            label="Within (optional)"
            clearable
            density="compact"
            variant="outlined"
            hide-details
            class="picker"
            :loading="!sphereInfo"
            :disabled="busy"
            data-testid="tie-within"
        ></v-select>
        <v-text-field v-model="form.role" label="Role" placeholder="practitioner, elder, courier…" density="compact" variant="outlined" hide-details class="picker" :disabled="busy"></v-text-field>
        <v-text-field v-model.number="form.since" label="Since (year)" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year" :disabled="busy"></v-text-field>
        <v-text-field v-model.number="form.until" label="Until (year)" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year" :disabled="busy"></v-text-field>
        <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!valid" @click="$emit('save')">Save</v-btn>
        <v-btn variant="text" size="small" :disabled="busy" @click="$emit('cancel')">Cancel</v-btn>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

function validYear(year) {
    return year === null || year === '' || (Number.isInteger(year) && year >= 1 && year <= 9999);
}

// A tie's form: its sphere, the part of it the tie is within (one of the
// entries filed in it, optional: the White Talon of the Tsar's Army), role
// and dates (years). `form` is the Ties section's, edited in place; Save
// and Cancel are emitted, Esc cancels.
export default {
    name: 'TieForm',
    props: {
        // `{sphereId, role, since, until}`
        form: { type: Object, required: true },
        // the spheres to pick from (`list_things` "sphere" entries)
        spheres: { type: Array, required: true },
        busy: { type: Boolean, default: false },
    },
    emits: ['save', 'cancel'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        sphereInfo() {
            return this.form.sphereId ? this.worlds.sphereInfo[this.form.sphereId] || null : null;
        },
        // the entries filed in the sphere's drawers (not its statements),
        // each once
        withinOptions() {
            const found = new Map();
            for (const drawer of this.sphereInfo?.sphere?.drawers || []) {
                for (const item of drawer.items || []) {
                    if (item.thing_id && !found.has(item.thing_id)) {
                        found.set(item.thing_id, { id: item.thing_id, name: item.name });
                    }
                }
            }
            return [...found.values()];
        },
        valid() {
            const { since, until } = this.form;
            const ordered = !Number.isInteger(since) || !Number.isInteger(until) || since <= until;
            return !!this.form.sphereId && validYear(since) && validYear(until) && ordered && !this.busy;
        },
    },
    watch: {
        // another sphere: its parts, and no part of the old one
        'form.sphereId': {
            handler(id, before) {
                if (before !== undefined && id !== before) {
                    this.form.within = null;
                }
                if (id) {
                    this.worlds.fetchSphere(id);
                }
            },
            immediate: true,
        },
    },
};
</script>

<style scoped>
.picker {
    min-width: 180px;
    max-width: 240px;
}

.year {
    max-width: 130px;
}
</style>
