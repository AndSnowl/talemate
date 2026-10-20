<template>
    <div class="thing-page" data-testid="thing-page">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <v-btn variant="text" size="small" prepend-icon="mdi-arrow-left" @click="worlds.closeThing()">Back</v-btn>
            <template v-if="thing">
                <span class="text-h5 thing-name" data-testid="thing-name">{{ thing.name }}</span>
                <v-chip size="x-small" label variant="tonal" color="muted" :prepend-icon="info?.icon">{{ thing.kind }}</v-chip>
                <v-spacer></v-spacer>

                <v-menu v-model="asOfMenu" :close-on-content-click="false" location="bottom end">
                    <template #activator="{ props }">
                        <v-btn v-bind="props" variant="outlined" size="small" append-icon="mdi-menu-down" data-testid="as-of-button" @click="openAsOf">
                            viewing:&nbsp;<span class="world-date">{{ viewingLabel }}</span>
                        </v-btn>
                    </template>
                    <v-card class="pa-3" min-width="260" data-testid="as-of-picker">
                        <div class="text-caption text-muted mb-2">View this {{ info?.singular || 'thing' }} as of a date</div>
                        <div class="d-flex ga-2">
                            <v-text-field v-model.number="asOfYear" label="Year" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details></v-text-field>
                            <v-select v-model="asOfMonth" label="Month" :items="monthOptions" item-title="title" item-value="value" clearable density="compact" variant="outlined" hide-details></v-select>
                        </div>
                        <div class="d-flex ga-2 mt-3">
                            <v-btn color="accent" variant="flat" size="small" :disabled="!validYear(asOfYear)" @click="applyAsOf">View</v-btn>
                            <v-btn variant="text" size="small" @click="viewAt(null)">Latest</v-btn>
                        </div>
                    </v-card>
                </v-menu>

                <v-btn
                    variant="outlined"
                    size="small"
                    prepend-icon="mdi-refresh"
                    :loading="worlds.proseRegenerating === thing.id"
                    @click="worlds.regenerateProse()"
                >Regenerate prose</v-btn>
            </template>
        </div>

        <div v-if="!thing" class="d-flex justify-center pa-8">
            <v-progress-circular indeterminate color="accent"></v-progress-circular>
        </div>

        <template v-else>
            <div class="timeline-strip d-flex flex-wrap align-center ga-1 mb-4" data-testid="timeline-strip">
                <v-chip
                    v-for="(point, index) in timelinePoints"
                    :key="index"
                    size="small"
                    :variant="point.reached ? 'tonal' : 'outlined'"
                    :color="point.scene ? 'scene' : (point.reached ? 'date' : 'muted')"
                    :prepend-icon="point.scene ? 'mdi-movie-open' : undefined"
                    @click="viewAt(point.date)"
                >
                    <span class="point-date">{{ point.dateLabel }}</span>
                    <span class="point-text">{{ point.text }}</span>
                </v-chip>
                <v-chip size="small" :variant="thing.at ? 'outlined' : 'tonal'" color="date" @click="viewAt(null)">latest</v-chip>
            </div>

            <v-row>
                <v-col cols="12" md="6">
                    <div v-for="field in shownFields" :key="field.name" class="field d-flex ga-2" :data-testid="'field-' + field.name">
                        <span class="field-label">{{ field.label }}</span>
                        <a v-if="field.thingId" class="thing-link" href="#" @click.prevent="worlds.openThing(field.thingId)">{{ field.text }}</a>
                        <span v-else>{{ field.text }}</span>
                    </div>

                    <div class="d-flex align-center mt-4 mb-1">
                        <span class="text-overline text-muted">Facts</span>
                        <v-spacer></v-spacer>
                        <v-btn v-if="!form || form.factId" variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="startAdd">Add fact</v-btn>
                    </div>

                    <div v-if="form && !form.factId" class="mb-2">
                        <ThingFactForm :form="form" :categories="categories" :busy="editing" @save="saveForm" @cancel="form = null" />
                    </div>

                    <div v-if="!thing.facts.length" class="text-body-2 text-muted">No facts true at this date.</div>
                    <template v-for="fact in thing.facts" :key="fact.fact_id">
                        <div class="fact d-flex align-center ga-2" data-testid="fact-row">
                            <span class="flex-grow-1">{{ fact.rendered }}</span>
                            <v-chip size="x-small" label variant="tonal" color="muted">{{ fact.category }}</v-chip>
                            <span class="fact-date">{{ spanLabel(worlds.calendar, fact.valid_from, fact.valid_until) }}</span>
                            <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit fact" @click="startEdit(fact)"></v-btn>
                            <v-btn v-if="!fact.valid_until" icon="mdi-timer-off-outline" variant="text" size="x-small" density="comfortable" aria-label="End fact" @click="startEnd(fact)"></v-btn>
                        </div>
                        <div v-if="form && form.factId === fact.fact_id" class="my-2">
                            <ThingFactForm :form="form" :categories="categories" :busy="editing" @save="saveForm" @cancel="form = null" @remove="removeFact(fact)" />
                        </div>
                    </template>
                </v-col>

                <v-col cols="12" md="6">
                    <div v-for="(prose, section) in thing.prose" :key="section" class="mb-3">
                        <div class="d-flex align-center ga-2">
                            <span class="text-overline text-muted">{{ section }} (generated)</span>
                            <v-chip v-if="prose.stale" size="x-small" label variant="tonal" color="warning">out of date</v-chip>
                        </div>
                        <div class="prose pa-3">
                            <span v-if="prose.text">{{ prose.text }}</span>
                            <span v-else class="text-muted">Not written yet.</span>
                        </div>
                    </div>

                    <div class="text-overline text-muted">Appears in</div>
                    <div v-if="!thing.appears_in.length" class="text-body-2 text-muted">No scenes yet.</div>
                    <div v-else class="d-flex flex-wrap ga-2">
                        <v-chip v-for="scene in thing.appears_in" :key="scene.id" size="small" variant="tonal" color="scene" prepend-icon="mdi-movie-open" @click="viewAt(scene.start)">
                            {{ scene.name }}&nbsp;<span class="text-muted">· {{ formatDate(worlds.calendar, scene.start) }}</span>
                        </v-chip>
                    </div>
                </v-col>
            </v-row>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { ageAt, dateOf, dateParts, formatDate, spanLabel } from './worldDates.js';
import { kindInfo } from './worldKinds.js';
import ThingFactForm from './ThingFactForm.vue';

// fields shown elsewhere (the name), not shown in the slice (cultures), or
// not for reading (voice, colour)
const HIDDEN_FIELDS = ['name', 'culture', 'cultures', 'voice', 'color'];

const FIELD_LABELS = { born: 'Born', kind: 'Kind', parent: 'Inside', owner: 'Owner', place: 'Place', when: 'When', until: 'Until' };

const EDIT_ACTIONS = ['add_fact', 'correct_fact', 'end_fact', 'remove_fact'];

function yearOf(date) {
    return date ? dateParts(date).year : null;
}

function cut(text, length = 28) {
    return text.length > length ? text.slice(0, length - 1).trimEnd() + '…' : text;
}

// A thing's page: core fields, the facts true at the viewing date (add,
// edit, end), the generated prose with Regenerate, the "viewing as of"
// date, a timeline strip of its dated changes and scenes, and the scenes
// it appears in.
export default {
    name: 'ThingPage',
    components: { ThingFactForm },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            asOfMenu: false,
            asOfYear: null,
            asOfMonth: null,
            // the open fact form: {mode: 'add'|'edit'|'end', factId?, ...}
            form: null,
        };
    },
    computed: {
        thing() {
            return this.worlds.thing;
        },
        info() {
            return this.thing ? kindInfo(this.thing.kind) : null;
        },
        categories() {
            return this.info?.categories || [];
        },
        // the date the page shows: its own, or the world's "now" for latest
        viewingDate() {
            return this.thing?.at || this.worlds.currentWorld?.now || null;
        },
        viewingLabel() {
            return this.thing?.at ? formatDate(this.worlds.calendar, this.thing.at) : 'latest';
        },
        monthOptions() {
            const names = this.worlds.calendar?.month_names || [];
            return names.map((title, index) => ({ title, value: index + 1 }));
        },
        editing() {
            return EDIT_ACTIONS.some((action) => this.worlds.pending[action]);
        },
        shownFields() {
            const calendar = this.worlds.calendar;
            const fields = [];
            for (const [name, value] of Object.entries(this.thing.fields)) {
                if (HIDDEN_FIELDS.includes(name) || value == null) {
                    continue;
                }
                const field = { name, label: FIELD_LABELS[name] || name };
                if (typeof value === 'object' && 'instant' in value) {
                    field.text = formatDate(calendar, value);
                    if (name === 'born' && this.viewingDate) {
                        field.text += ` (age ${ageAt(value, this.viewingDate)})`;
                    }
                } else if (typeof value === 'string' && /^[0-9a-f]{32}$/.test(value)) {
                    field.thingId = value;
                    field.text = this.thingName(value);
                } else {
                    field.text = String(value);
                }
                fields.push(field);
            }
            return fields;
        },
        // the dated changes, the birth and the scenes, in date order; a
        // point is "reached" when it's on or before the viewing date
        timelinePoints() {
            const calendar = this.worlds.calendar;
            const points = [];
            const born = this.thing.fields.born;
            if (born && typeof born === 'object') {
                points.push({ date: born, text: 'born' });
            }
            for (const entry of this.thing.timeline) {
                if (!entry.date || (entry.change === 'field' && entry.field === 'name' && !entry.value)) {
                    continue;
                }
                let text;
                if (entry.change === 'fact_start') {
                    text = cut(entry.text || '');
                } else if (entry.change === 'fact_end') {
                    text = 'ends: ' + cut(entry.text || '', 22);
                } else {
                    text = entry.field;
                }
                points.push({ date: entry.date, text });
            }
            for (const scene of this.thing.appears_in) {
                points.push({ date: scene.start, text: `“${cut(scene.name, 24)}”`, scene: true });
            }
            const at = this.thing.at ? this.thing.at.instant : Infinity;
            return points
                .sort((a, b) => a.date.instant - b.date.instant)
                .map((point) => ({
                    ...point,
                    dateLabel: formatDate(calendar, point.date),
                    reached: point.date.instant <= at,
                }));
        },
    },
    watch: {
        thing(thing, before) {
            // another thing, or the reply to the form's own edit
            if (!thing || thing.id !== before?.id || this.form?.sent) {
                this.form = null;
            }
        },
        editing(now) {
            // the edit failed (no reply replaced the thing): keep the form
            if (!now && this.form?.sent) {
                this.form = { ...this.form, sent: false };
            }
        },
    },
    methods: {
        formatDate,
        spanLabel,
        validYear(year) {
            return Number.isInteger(year) && year >= 1 && year <= 9999;
        },
        thingName(id) {
            for (const list of Object.values(this.worlds.things)) {
                const found = list.find((thing) => thing.id === id);
                if (found) {
                    return found.name;
                }
            }
            return id.slice(0, 8);
        },
        openAsOf() {
            const parts = this.viewingDate ? dateParts(this.viewingDate) : null;
            this.asOfYear = parts ? parts.year : null;
            this.asOfMonth = this.thing?.at && this.thing.at.precision !== 'year' ? parts.month : null;
        },
        applyAsOf() {
            if (!this.validYear(this.asOfYear)) {
                return;
            }
            this.viewAt(dateOf(this.asOfYear, this.asOfMonth || null));
        },
        viewAt(date) {
            this.asOfMenu = false;
            const at = date ? { instant: date.instant, precision: date.precision } : null;
            this.worlds.viewThingAt(at);
        },
        startAdd() {
            this.form = { mode: 'add', category: this.categories[0], text: '', fromYear: null, untilYear: null };
        },
        startEdit(fact) {
            this.form = {
                mode: 'edit',
                factId: fact.fact_id,
                category: fact.category,
                text: fact.text,
                fromYear: yearOf(fact.valid_from),
                untilYear: yearOf(fact.valid_until),
                original: fact,
            };
        },
        startEnd(fact) {
            this.form = { mode: 'end', factId: fact.fact_id, untilYear: yearOf(this.viewingDate) };
        },
        saveForm() {
            const form = this.form;
            const year = (value) => (this.validYear(value) ? dateOf(value) : null);
            if (form.mode === 'add') {
                this.worlds.addFact(form.category, form.text.trim(), year(form.fromYear), year(form.untilYear));
            } else if (form.mode === 'end') {
                this.worlds.endFact(form.factId, dateOf(form.untilYear));
            } else {
                const original = form.original;
                const changes = {};
                if (form.text.trim() !== original.text) {
                    changes.text = form.text.trim();
                }
                if (form.category !== original.category) {
                    changes.category = form.category;
                }
                // a year left as it was keeps the stored date (and its precision)
                const sameYear = (date, value) => yearOf(date) === (this.validYear(value) ? value : null);
                if (!sameYear(original.valid_from, form.fromYear)) {
                    changes.valid_from = year(form.fromYear);
                }
                if (!sameYear(original.valid_until, form.untilYear)) {
                    changes.valid_until = year(form.untilYear);
                }
                if (!Object.keys(changes).length) {
                    this.form = null;
                    return;
                }
                this.worlds.correctFact(form.factId, changes);
            }
            this.form = { ...form, sent: true };
        },
        removeFact(fact) {
            this.worlds.removeFact(fact.fact_id);
            this.form = { ...this.form, sent: true };
        },
    },
};
</script>

<style scoped>
.thing-name {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}

.world-date {
    color: rgb(var(--v-theme-date));
}

.point-date {
    font-family: monospace;
    font-size: 11px;
    margin-right: 6px;
}

.point-text {
    font-size: 12px;
}

.field {
    margin: 4px 0;
}

.field-label {
    min-width: 80px;
    font-weight: 600;
    color: rgb(var(--v-theme-muted));
}

.thing-link {
    color: rgb(var(--v-theme-link));
    text-decoration: underline dotted;
}

.fact {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 2px 0;
}

.fact .v-chip,
.fact .v-btn {
    flex: none;
}

.fact-date {
    flex: none;
    font-family: monospace;
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
    min-width: 80px;
    text-align: right;
}

.prose {
    background: rgb(var(--v-theme-raised));
    border-radius: 6px;
    line-height: 1.5;
    white-space: pre-wrap;
}
</style>
