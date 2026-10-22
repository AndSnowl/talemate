<template>
    <div class="ties-section mt-4" data-testid="ties-section">
        <div class="d-flex align-center mb-1">
            <span class="text-overline text-muted">Ties</span>
            <v-spacer></v-spacer>
            <v-btn v-if="!form || form.index !== null" variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="startAdd">Add tie</v-btn>
        </div>

        <div v-if="form && form.index === null" class="tie">
            <TieForm :form="form" :spheres="sphereOptions" :busy="saving" @save="saveTie" @cancel="form = null" />
        </div>

        <div v-if="!ties.length && !form" class="text-body-2 text-muted">Tied to no sphere.</div>
        <div v-for="(tie, index) in ties" :key="tie.sphere_id + index" class="tie" :class="{ ended: !!tie.until }" data-testid="tie">
            <div class="d-flex align-center ga-1">
                <span class="flex-grow-1">
                    {{ tieLead(tie.role) }}
                    <LinkedText :segments="[{ text: tie.sphere_name, ref: tie.sphere_id, stub: isStub(tie.sphere_id) }]" />
                    <span v-if="dates(tie)" class="text-muted"> · {{ dates(tie) }}</span>
                </span>
                <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit tie" @click="startEdit(tie, index)"></v-btn>
                <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Remove tie" :disabled="saving" @click="removeTie(index)"></v-btn>
            </div>
            <TieForm v-if="form && form.index === index" :form="form" :spheres="sphereOptions" :busy="saving" class="mt-1" @save="saveTie" @cancel="form = null" />

            <template v-if="tie.exceptions.length">
                <div class="but"><i>but…</i></div>
                <div v-for="but in tie.exceptions" :key="but.fact_id" class="but d-flex align-center ga-1" data-testid="tie-exception">
                    <span class="flex-grow-1">– <LinkedText :segments="but.segments" /></span>
                    <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Remove exception" :disabled="!!worlds.pending.remove_fact" @click="worlds.removeFact(but.fact_id)"></v-btn>
                </div>
            </template>
            <div v-else class="but text-muted">no exceptions</div>

            <div v-if="exception && exception.sphereId === tie.sphere_id" class="but exception-form d-flex align-center flex-wrap ga-2 mt-1" data-testid="exception-form" @keydown.esc="exception = null">
                <v-text-field
                    v-model="exception.text"
                    label="But…"
                    placeholder="doesn't believe snowy owl-folk are superior"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="flex-grow-1"
                    @keydown.enter="saveException"
                ></v-text-field>
                <v-select
                    v-model="exception.rejects"
                    :items="rejectOptions(tie.sphere_id)"
                    :loading="!worlds.sphereInfo[tie.sphere_id]"
                    label="Departs from"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="picker"
                    data-testid="exception-rejects"
                ></v-select>
                <v-btn color="accent" variant="flat" size="small" :loading="!!worlds.pending.add_exception" :disabled="!exception.text.trim()" @click="saveException">Save</v-btn>
                <v-btn variant="text" size="small" @click="exception = null">Cancel</v-btn>
            </div>
            <div v-else class="but">
                <v-btn variant="text" size="x-small" prepend-icon="mdi-plus" @click="startException(tie)">Add exception</v-btn>
            </div>
        </div>
    </div>
</template>

<script>
import { dateIn, rejectableItems, tiesPayload, useWorldsStore } from '@/stores/worlds.js';
import { dateOf, dateParts, formatDate } from './worldDates.js';
import { tieLead } from './worldKinds.js';
import LinkedText from './LinkedText.vue';
import TieForm from './TieForm.vue';

// "the sphere as a whole": an exception departing from no one item
const WHOLE = 'whole';

function yearOf(date) {
    return date ? dateParts(date).year : null;
}

// A character's Ties: each tie to a sphere with its role and dates ("Practitioner of
// the White Dawn · since 1010"), and only its "but…" exceptions, each a
// `ties` fact of the character (removable like any fact). "+ Add tie"
// picks a sphere, a role and dates; a tie can be edited or removed (the
// whole list is written, `set_ties`). "+ Add exception" writes one
// (`add_exception`), departing from one of the sphere's items (fetched
// with `worlds.fetchSphere`) or from the sphere as a whole. An ended tie
// is dimmed.
export default {
    name: 'TiesSection',
    components: { LinkedText, TieForm },
    props: {
        // the character's payload
        thing: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // the tie form: `{index (null: a new tie), sphereId, role,
            // since, until, sent}` (years)
            form: null,
            // the exception form: `{sphereId, text, rejects, sent}`
            exception: null,
        };
    },
    computed: {
        ties() {
            return this.thing.ties || [];
        },
        sphereOptions() {
            return this.worlds.things.sphere || [];
        },
        saving() {
            return !!this.worlds.pending.set_ties;
        },
    },
    watch: {
        // the reply to a save, or another page: the forms are done
        thing(thing, before) {
            if (thing.id !== before?.id || this.form?.sent) {
                this.form = null;
            }
            if (thing.id !== before?.id || this.exception?.sent) {
                this.exception = null;
            }
        },
        // a save that failed keeps its form (the spinner stops before the
        // page's prop is replaced, so only an error tells a failure apart)
        saving(now) {
            if (!now && this.form?.sent && this.worlds.error) {
                this.form = { ...this.form, sent: false };
            }
        },
        'worlds.pending.add_exception'(now) {
            if (!now && this.exception?.sent && this.worlds.error) {
                this.exception = { ...this.exception, sent: false };
            }
        },
    },
    methods: {
        tieLead,
        isStub(id) {
            return !!(this.worlds.things.sphere || []).find((entry) => entry.id === id)?.stub;
        },
        dates(tie) {
            const calendar = this.worlds.calendar;
            const parts = [];
            if (tie.since) {
                parts.push(`since ${formatDate(calendar, tie.since)}`);
            }
            if (tie.until) {
                parts.push(`until ${formatDate(calendar, tie.until)}`);
            }
            return parts.join(' · ');
        },
        startAdd() {
            this.exception = null;
            this.form = { index: null, sphereId: null, role: '', since: null, until: null, sent: false };
        },
        startEdit(tie, index) {
            this.exception = null;
            this.form = {
                index,
                sphereId: tie.sphere_id,
                role: tie.role || '',
                since: yearOf(tie.since),
                until: yearOf(tie.until),
                sent: false,
            };
        },
        saveTie() {
            const form = this.form;
            const original = form.index === null ? null : this.ties[form.index];
            // a year left as it was keeps the stored date (and its precision)
            const year = (value, stored) => {
                if (stored && yearOf(stored) === value) {
                    return dateIn(stored);
                }
                return Number.isInteger(value) ? dateOf(value) : null;
            };
            const ties = tiesPayload(this.ties);
            const tie = {
                sphere_id: form.sphereId,
                role: form.role.trim(),
                since: year(form.since, original?.since),
                until: year(form.until, original?.until),
            };
            if (form.index === null) {
                ties.push(tie);
            } else {
                ties[form.index] = tie;
            }
            this.worlds.setTies(this.thing.id, ties);
            this.form = { ...form, sent: true };
        },
        removeTie(index) {
            this.worlds.setTies(this.thing.id, tiesPayload(this.ties).filter((_tie, i) => i !== index));
        },
        startException(tie) {
            this.form = null;
            this.exception = { sphereId: tie.sphere_id, text: '', rejects: WHOLE, sent: false };
            this.worlds.fetchSphere(tie.sphere_id);
        },
        // the sphere's items as choices, keyed `thing:<id>` / `fact:<id>`
        rejectOptions(sphereId) {
            const items = rejectableItems(this.worlds.sphereInfo[sphereId]?.sphere).map((item) => ({
                title: item.title,
                value: item.value.thing_id ? `thing:${item.value.thing_id}` : `fact:${item.value.fact_id}`,
            }));
            return [{ title: 'the sphere as a whole', value: WHOLE }, ...items];
        },
        saveException() {
            const form = this.exception;
            if (!form.text.trim() || form.sent) {
                return;
            }
            const [key, id] = form.rejects === WHOLE ? [null, null] : form.rejects.split(':');
            const rejects = key === 'thing' ? { thing_id: id } : key === 'fact' ? { fact_id: id } : null;
            this.worlds.addException(this.thing.id, form.sphereId, form.text.trim(), rejects);
            this.exception = { ...form, sent: true };
        },
    },
};
</script>

<style scoped>
.tie {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    padding: 8px 10px;
    margin: 8px 0;
}

.tie.ended {
    opacity: 0.6;
}

.tie .v-btn {
    flex: none;
}

.but {
    margin: 2px 0 0 14px;
}

.picker {
    min-width: 200px;
    max-width: 260px;
}
</style>
