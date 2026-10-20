<template>
    <v-menu v-model="open" :close-on-content-click="false" location="bottom start">
        <template #activator="{ props }">
            <v-btn
                v-bind="props"
                :variant="compact ? 'text' : 'outlined'"
                size="small"
                :disabled="disabled"
                append-icon="mdi-pencil"
                class="start-date"
                data-testid="scene-start-date"
                title="Edit start date"
                @click="fill"
            >
                <span v-if="!compact" class="text-muted mr-1">starts</span>
                <span class="world-date">{{ formatDate(worlds.calendar, scene.start) }}</span>
            </v-btn>
        </template>
        <v-card class="pa-3" min-width="300" data-testid="scene-start-editor">
            <div class="text-caption text-muted mb-2">Move this scene's start. Its messages move with it.</div>
            <div class="d-flex ga-2">
                <v-text-field v-model.number="year" label="Year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details></v-text-field>
                <v-select v-model="month" label="Month" :items="monthOptions" item-title="title" item-value="value" clearable density="compact" variant="outlined" hide-details></v-select>
                <v-text-field v-if="month" v-model.number="day" label="Day" type="number" min="1" max="31" density="compact" variant="outlined" hide-details class="day"></v-text-field>
            </div>
            <div class="d-flex ga-2 mt-3">
                <v-btn color="accent" variant="flat" size="small" :disabled="!valid" :loading="!!worlds.pending.reposition_scene" @click="move">Move</v-btn>
                <v-btn variant="text" size="small" @click="open = false">Cancel</v-btn>
            </div>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, dateParts, formatDate } from './worldDates.js';

// A world scene's start date, with a picker to move it
// (`reposition_scene`): on the Worlds home's scene cards and in the scene
// view. `scene` is a `list_scenes` item.
export default {
    name: 'SceneStartDate',
    props: {
        scene: { type: Object, required: true },
        disabled: { type: Boolean, default: false },
        // just the date, for the scene toolbar
        compact: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { open: false, year: null, month: null, day: null };
    },
    computed: {
        monthOptions() {
            const names = this.worlds.calendar?.month_names || [];
            return names.map((title, index) => ({ title, value: index + 1 }));
        },
        valid() {
            const inRange = (value, low, high) => Number.isInteger(value) && value >= low && value <= high;
            const dayOk = !this.month || this.day === null || this.day === '' || inRange(this.day, 1, 31);
            return inRange(this.year, 1, 9999) && dayOk;
        },
    },
    methods: {
        formatDate,
        // start from the scene's own date, to the precision it has
        fill() {
            const start = this.scene.start;
            const parts = dateParts(start);
            this.year = parts.year;
            this.month = start.precision === 'year' ? null : parts.month;
            this.day = ['year', 'month'].includes(start.precision) ? null : parts.day;
        },
        move() {
            if (!this.valid) {
                return;
            }
            const day = this.month && Number.isInteger(this.day) ? this.day : null;
            this.worlds.repositionScene(this.scene.id, dateOf(this.year, this.month || null, day));
            this.open = false;
        },
    },
};
</script>

<style scoped>
.world-date {
    color: rgb(var(--v-theme-date));
}

.day {
    max-width: 80px;
}
</style>
