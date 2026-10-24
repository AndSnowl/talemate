<template>
    <div class="entry-in" :data-testid="draft ? 'draft-in' : 'entry-in'">
        <div class="d-flex align-center ga-2">
            <span class="text-overline text-muted">In</span>
            <span v-if="draft" class="text-caption text-muted">the AI's suggestions come unticked, yours ticked</span>
            <v-spacer></v-spacer>
            <v-btn v-if="!adding" variant="outlined" size="x-small" prepend-icon="mdi-magnify" data-testid="in-add" @click="startAdd">+ in…</v-btn>
        </div>

        <!-- "+ in… 🔎": an entry the world has, or a new stub of that name -->
        <div v-if="adding" class="in-form pa-2 mb-2" data-testid="in-add-form" @keydown.esc="escape($event)">
            <div class="d-flex align-center flex-wrap ga-2">
                <v-autocomplete
                    v-model="adding.target"
                    v-model:search="adding.search"
                    :items="targetItems"
                    item-title="name"
                    item-value="id"
                    label="In…"
                    placeholder="search the world, or type a new name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="in-target"
                    data-testid="in-target"
                >
                    <template #item="{ props: itemProps, item }">
                        <v-list-item v-bind="itemProps" :subtitle="item.raw.subtitle"></v-list-item>
                    </template>
                </v-autocomplete>
                <template v-if="adding.target === NEW">
                    <v-select v-model="adding.kind" :items="kindItems" label="Kind" density="compact" variant="outlined" hide-details class="in-small" data-testid="in-new-kind"></v-select>
                    <v-text-field v-model="adding.tag" label="Tag" density="compact" variant="outlined" hide-details class="in-small" data-testid="in-new-tag"></v-text-field>
                </template>
                <v-text-field v-model="adding.role" label="Role (optional)" density="compact" variant="outlined" hide-details class="in-role" data-testid="in-role"></v-text-field>
                <v-text-field v-model.number="adding.since" label="Since (year)" type="number" density="compact" variant="outlined" hide-details class="in-year" data-testid="in-since"></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :disabled="!addValid" :loading="!draft && !!worlds.pending.add_filing" @click="saveAdd">File it</v-btn>
                <v-btn variant="text" size="small" @click="adding = null">Cancel</v-btn>
            </div>
            <div v-if="adding.target === NEW" class="text-caption text-muted mt-1" data-testid="in-new-note">Makes a stub “{{ newName }}”{{ draft ? ' on accept' : '' }}, filed here, to expand later.</div>
        </div>

        <div v-if="!rows.length && !adding" class="text-body-2 text-muted">Filed in nothing yet.</div>
        <template v-for="row in rows" :key="keyOf(row)">
            <div class="in-row d-flex align-center flex-wrap ga-2" :class="{ ended: !!row.until }" :data-testid="rowTestId(row)">
                <!-- a draft's own row: ticked as it came (the AI's unticked) -->
                <v-checkbox-btn
                    v-if="row.draft"
                    :model-value="!!row.ticked"
                    density="compact"
                    class="flex-grow-0"
                    :aria-label="'File in ' + row.target_name"
                    @update:model-value="$emit('change', keyOf(row), { ticked: $event })"
                ></v-checkbox-btn>
                <span v-if="row.new_name" class="stub-name">{{ row.target_name }}</span>
                <a v-else class="thing-link" :class="{ dropped: row.draft && !row.ticked }" href="#" data-testid="in-target-link" @click.prevent="worlds.openThing(row.target_id)">{{ row.target_name }}</a>
                <span v-if="row.new_name" class="text-caption text-muted">new stub · {{ [row.new_name.kind, row.new_name.tag].filter(Boolean).join(', ') }}</span>
                <span v-if="row.role" class="role" data-testid="in-role-text">{{ row.role }}</span>
                <span v-if="row.within_id" class="within">within <a class="thing-link" href="#" @click.prevent="worlds.openThing(row.within_id)">{{ row.within_name }}</a><span v-if="row.within_holds === false" class="within-stale" data-testid="in-within-stale"> (no longer part of {{ row.target_name }})</span></span>
                <span v-if="dates(row)" class="when" data-testid="in-dates">{{ dates(row) }}</span>
                <span v-if="draft && !row.draft" class="text-caption text-muted">· already filed</span>
                <v-spacer></v-spacer>
                <template v-if="!draft || row.draft">
                    <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit filing" data-testid="in-edit" @click="startEdit(row)"></v-btn>
                    <v-btn v-if="!draft && !row.until" icon="mdi-timer-off-outline" variant="text" size="x-small" density="comfortable" aria-label="End this" data-testid="in-end" @click="startEnd(row)"></v-btn>
                    <v-btn v-if="!draft && persons" icon="mdi-comment-alert-outline" variant="text" size="x-small" density="comfortable" aria-label="Add a but…" data-testid="in-add-but" @click="startBut(row)"></v-btn>
                    <v-btn icon="mdi-delete-outline" variant="text" size="x-small" density="comfortable" aria-label="Remove filing" data-testid="in-remove" :disabled="!draft && !!worlds.pending.remove_filing" @click="remove(row)"></v-btn>
                </template>
            </div>
            <div v-for="but in row.exceptions" :key="but.fact_id" class="but" data-testid="in-but">
                <i>but…</i> <LinkedText :segments="but.segments" />
            </div>

            <!-- edit one filing: only what changes is sent -->
            <div v-if="editing && editing.targetId === keyOf(row)" class="in-form pa-2 mb-2" data-testid="in-edit-form" @keydown.esc="escape($event)">
                <div class="d-flex align-center flex-wrap ga-2">
                    <v-text-field v-model="editing.role" label="Role" density="compact" variant="outlined" hide-details class="in-role" autofocus></v-text-field>
                    <v-text-field v-model.number="editing.since" label="Since (year)" type="number" density="compact" variant="outlined" hide-details class="in-year"></v-text-field>
                    <v-text-field v-if="!draft" v-model.number="editing.until" label="Until (year)" type="number" density="compact" variant="outlined" hide-details class="in-year"></v-text-field>
                    <v-autocomplete
                        v-if="persons && !row.new_name"
                        v-model="editing.within"
                        :items="withinItems(row)"
                        item-title="name"
                        item-value="id"
                        label="Within (a part of it)"
                        clearable
                        density="compact"
                        variant="outlined"
                        hide-details
                        class="in-target"
                    ></v-autocomplete>
                    <v-btn color="accent" variant="flat" size="small" :disabled="!editValid" :loading="!draft && !!worlds.pending.edit_filing" @click="saveEdit(row)">Save</v-btn>
                    <v-btn variant="text" size="small" @click="editing = null">Cancel</v-btn>
                </div>
            </div>
            <div v-if="ending && ending.targetId === row.target_id" class="in-form pa-2 mb-2 d-flex align-center flex-wrap ga-2" data-testid="in-end-form" @keydown.esc="escape($event)">
                <span class="text-caption text-muted">Ends in</span>
                <v-text-field v-model.number="ending.year" label="Year" type="number" density="compact" variant="outlined" hide-details class="in-year" autofocus></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :disabled="!validYear(ending.year)" :loading="!!worlds.pending.edit_filing" @click="saveEnd(row)">End it</v-btn>
                <v-btn variant="text" size="small" @click="ending = null">Cancel</v-btn>
            </div>
            <div v-if="butting && butting.targetId === row.target_id" class="in-form pa-2 mb-2 d-flex align-center flex-wrap ga-2" data-testid="in-but-form" @keydown.esc="escape($event)">
                <span class="text-caption text-muted"><i>but…</i></span>
                <v-text-field v-model="butting.text" label="How they differ" density="compact" variant="outlined" hide-details class="flex-grow-1" autofocus @keydown.enter="saveBut(row)"></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :disabled="!butting.text.trim()" :loading="!!worlds.pending.add_exception" @click="saveBut(row)">Add</v-btn>
                <v-btn variant="text" size="small" @click="butting = null">Cancel</v-btn>
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, dateParts } from './worldDates.js';
import { filingDates, normaliseTag } from './entryPage.js';
import { filingKey } from './draftPage.js';
import { STUB_KINDS, actsInWorld, escapeCloses, kindInfo } from './worldKinds.js';
import LinkedText from './LinkedText.vue';

// the target choice that makes a stub of the typed name, and its title
const NEW = '__new__';
const NEW_LABEL = 'Make a stub “';

function yearOf(date) {
    return date ? dateParts(date).year : null;
}

// The entry page's "In" (mockup v3, screens A, B and D): one row per
// filing (`thing.in`, ended ones too), with its target, role and dates
// ("since 979", "900–1015"), and for a person (a character or real being)
// the part of the target it's "within" and its "but…" exceptions under it.
// A part that has moved out of the target is marked "(no longer part of
// …)" (`within_holds` false; final review M3).
// Each row can be edited (`edit_filing`: only what changes is sent),
// ended ("End this": its `until`) or removed (`remove_filing`); a person's
// gets "+ but…" (`add_exception`). "+ in… 🔎" searches the world's entries
// and live stubs; a name the world hasn't makes a stub of it, with a kind
// and tag, filed here (`add_filing {new_name}`).
//
// On a draft (`draft`, the page's draft mode) nothing is sent: its own
// rows (`draft: true`) carry their tick, the AI's coming unticked (ruling
// F7); "+ in…" (an entry, or a stub of a typed name, made on accept),
// edit (role, since, within) and remove are emitted for the draft
// (`add(target, {role, since})`, `change(key, changes)`, `remove(key)`;
// a row's key is its target's id, or `new:<name>`). A stub's filings so
// far show as they are.
export default {
    name: 'EntryIn',
    components: { LinkedText },
    props: {
        // the page's payload (a draft's: its rows as the owner left them)
        thing: { type: Object, required: true },
        draft: { type: Boolean, default: false },
    },
    emits: ['add', 'change', 'remove'],
    setup() {
        return { worlds: useWorldsStore(), NEW };
    },
    data() {
        // `sent`: a form's request is out; its reply closes the forms
        return { adding: null, editing: null, ending: null, butting: null, sent: false };
    },
    computed: {
        rows() {
            return this.thing.in || [];
        },
        persons() {
            return actsInWorld(this.thing);
        },
        kindItems() {
            return STUB_KINDS.map((kind) => ({ title: kindInfo(kind)?.singular || kind, value: kind }));
        },
        // the name typed in the search (not an item's title picked)
        newName() {
            return (this.adding?.typed || '').trim();
        },
        // every entry and live stub but this one and those it's in, then
        // "Make a stub" for a typed name the world hasn't
        targetItems() {
            const filed = new Set(this.rows.filter((row) => !row.draft || row.ticked).map((row) => row.target_id));
            const items = this.worlds.referenceTargets
                .filter((target) => target.id !== this.thing.id && !filed.has(target.id))
                .map((target) => ({ ...target, subtitle: target.stub ? `${target.kind} · stub` : target.kind }));
            const name = this.newName;
            const known = items.some((item) => item.name.toLowerCase() === name.toLowerCase());
            if (name && !known) {
                items.push({ id: NEW, name: `${NEW_LABEL}${name}”`, subtitle: 'a new entry, to expand later' });
            }
            return items;
        },
        addValid() {
            const adding = this.adding;
            if (!adding?.target || !this.validYearOrNone(adding.since)) {
                return false;
            }
            return adding.target !== NEW || !!this.newName;
        },
        editValid() {
            const editing = this.editing;
            return !!editing && this.validYearOrNone(editing.since) && this.validYearOrNone(editing.until);
        },
    },
    watch: {
        // a request failed (no reply replaced the page): the form stays,
        // and the next page update doesn't close it
        'worlds.error'(error) {
            if (error) {
                this.sent = false;
            }
        },
        // what the owner types (picking an item writes its title there)
        'adding.search'(value) {
            if (this.adding && value != null && !value.startsWith(NEW_LABEL) && this.adding.target !== NEW) {
                this.adding.typed = value;
            }
        },
        // the reply replaced the page: the forms are done
        thing(thing, before) {
            if (thing?.id !== before?.id || this.sent) {
                this.adding = null;
                this.editing = null;
                this.ending = null;
                this.butting = null;
                this.sent = false;
            }
        },
    },
    methods: {
        keyOf(row) {
            return filingKey(row);
        },
        rowTestId(row) {
            if (!this.draft) {
                return 'in-row';
            }
            return row.draft ? 'draft-in-row' : 'draft-in-kept';
        },
        remove(row) {
            if (this.draft) {
                this.$emit('remove', this.keyOf(row));
            } else {
                this.worlds.removeFiling(row.target_id);
            }
        },
        dates(row) {
            return filingDates(this.worlds.calendar, row);
        },
        validYear(year) {
            return Number.isInteger(year) && year >= 1 && year <= 9999;
        },
        validYearOrNone(year) {
            return year === null || year === '' || year === undefined || this.validYear(year);
        },
        year(value) {
            return this.validYear(value) ? dateOf(value) : null;
        },
        escape(event) {
            if (escapeCloses(event)) {
                this.adding = null;
                this.editing = null;
                this.ending = null;
                this.butting = null;
            }
        },
        startAdd() {
            this.editing = null;
            this.adding = { target: null, search: '', typed: '', kind: 'lore', tag: '', role: '', since: null };
        },
        saveAdd() {
            const adding = this.adding;
            if (!this.addValid) {
                return;
            }
            const filing = { role: adding.role.trim() || null, since: this.year(adding.since) };
            if (this.draft) {
                const target = adding.target === NEW
                    ? { newName: this.newName, kind: adding.kind, tag: normaliseTag(adding.tag) || null }
                    : this.worlds.referenceTargets.find((item) => item.id === adding.target);
                if (target) {
                    this.$emit('add', target, filing);
                }
                this.adding = null;
                return;
            }
            if (adding.target === NEW) {
                this.worlds.addFiling({ newName: this.newName, kind: adding.kind, tag: normaliseTag(adding.tag) || null, ...filing });
            } else {
                this.worlds.addFiling({ targetId: adding.target, ...filing });
            }
            this.sent = true;
        },
        startEdit(row) {
            this.adding = null;
            this.ending = null;
            this.editing = {
                targetId: this.keyOf(row),
                role: row.role || '',
                since: yearOf(row.since),
                until: yearOf(row.until),
                within: row.within_id,
            };
        },
        withinItems(row) {
            return this.worlds.referenceTargets.filter((target) => target.id !== row.target_id && target.id !== this.thing.id);
        },
        // only what changed: a year left as it was keeps its stored date
        saveEdit(row) {
            const editing = this.editing;
            if (!this.editValid) {
                return;
            }
            const changes = {};
            const role = editing.role.trim() || null;
            if (role !== (row.role || null)) {
                changes.role = role;
            }
            for (const key of ['since', 'until']) {
                const value = this.validYear(editing[key]) ? editing[key] : null;
                if (value !== yearOf(row[key])) {
                    changes[key] = this.year(value);
                }
            }
            if ((editing.within || null) !== (row.within_id || null)) {
                changes.within = editing.within || null;
            }
            if (!Object.keys(changes).length) {
                this.editing = null;
                return;
            }
            if (this.draft) {
                this.$emit('change', this.keyOf(row), changes);
                this.editing = null;
                return;
            }
            this.worlds.editFiling(row.target_id, changes);
            this.sent = true;
        },
        startEnd(row) {
            this.editing = null;
            const now = this.thing.at || this.worlds.currentWorld?.now;
            this.ending = { targetId: row.target_id, year: now ? dateParts(now).year : null };
        },
        // "End this": the filing's `until`
        saveEnd(row) {
            if (this.validYear(this.ending?.year)) {
                this.worlds.editFiling(row.target_id, { until: dateOf(this.ending.year) });
                this.sent = true;
            }
        },
        startBut(row) {
            this.butting = { targetId: row.target_id, text: '' };
        },
        saveBut(row) {
            const text = this.butting?.text.trim();
            if (text) {
                this.worlds.addException(row.target_id, text);
                this.sent = true;
            }
        },
    },
};
</script>

<style scoped>
.in-row {
    padding: 1px 0;
    font-size: 14px;
}

.in-row.ended {
    opacity: 0.75;
}

.thing-link {
    color: rgb(var(--v-theme-link));
    text-decoration: underline dotted;
}

.thing-link.dropped {
    color: rgb(var(--v-theme-muted));
}

.stub-name {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}

.role {
    font-size: 12px;
    font-style: italic;
    color: rgb(var(--v-theme-muted));
}

.within {
    font-size: 12px;
    color: rgb(var(--v-theme-muted));
}

.within-stale {
    font-style: italic;
}

.when {
    font-size: 11px;
    white-space: nowrap;
    color: rgb(var(--v-theme-date));
}

.but {
    margin-left: 22px;
    font-size: 13px;
}

.in-form {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
}

.in-target {
    min-width: 260px;
    max-width: 340px;
}

.in-role {
    max-width: 200px;
}

.in-small {
    max-width: 140px;
}

.in-year {
    max-width: 120px;
}

.v-btn {
    flex: none;
}
</style>
