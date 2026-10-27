<template>
    <div class="entry-in" :data-testid="draft ? 'draft-in' : 'entry-in'">
        <!-- a section like Facts: its heading muted, "+ In…" at its right
             (the column is half the page wide) -->
        <div class="d-flex align-center mt-4 mb-1" data-testid="in-heading">
            <span class="text-overline text-muted">In</span>
            <v-spacer></v-spacer>
            <v-btn v-if="!adding" variant="text" size="small" color="accent" prepend-icon="mdi-plus" data-testid="in-add" @click="startAdd">In…</v-btn>
        </div>

        <!-- "+ In…": an entry the world has, or a new stub of that name -->
        <div v-if="adding" class="in-form pa-2 mb-2" data-testid="in-add-form" @keydown.esc="escape($event)">
            <div class="d-flex align-center flex-wrap ga-2">
                <EntryAutocomplete
                    v-model="adding.target"
                    v-model:search="adding.search"
                    :targets="targetItems"
                    :extras="newItems"
                    label="In…"
                    placeholder="search the world, or type a new name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="in-target"
                    data-testid="in-target"
                ></EntryAutocomplete>
                <template v-if="adding.target === NEW">
                    <v-select v-model="adding.kind" :items="kindItems" label="Kind" density="compact" variant="outlined" hide-details class="in-small" data-testid="in-new-kind"></v-select>
                    <v-text-field v-model="adding.tag" label="Tag" density="compact" variant="outlined" hide-details class="in-small" data-testid="in-new-tag"></v-text-field>
                </template>
                <v-combobox v-model="adding.role" :items="roleItems" label="Role (optional)" :placeholder="ROLE_HINT" density="compact" variant="outlined" hide-details class="in-role" data-testid="in-role"></v-combobox>
                <TagChip local testid="in-show-under" label="Shows under" prefix="shows under" :tag="adding.showUnder" :fallback="thing.tag" empty-text="Other" clear-text="its own tag" @pick="adding.showUnder = $event"></TagChip>
                <v-text-field v-model.number="adding.since" label="Since (year)" type="number" density="compact" variant="outlined" hide-details class="in-year" data-testid="in-since"></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :disabled="!addValid" :loading="!draft && !!worlds.pending.add_filing" @click="saveAdd">File it</v-btn>
                <v-btn variant="text" size="small" @click="adding = null">Cancel</v-btn>
            </div>
            <div v-if="adding.target === NEW" class="text-caption text-muted mt-1" data-testid="in-new-note">Makes a stub “{{ newName }}”{{ draft ? ' on accept' : '' }}, filed here, to expand later.</div>
        </div>

        <div v-if="!rows.length && !adding" class="text-body-2 text-muted">Filed in nothing yet.</div>
        <!-- each row as a fact's: the same text size, the same dashed
             separator under it and what's shown under it -->
        <div v-for="row in rows" :key="keyOf(row)" class="in-host">
            <div class="in-row d-flex align-center flex-wrap" :class="{ ended: !!row.until }" :data-testid="rowTestId(row)">
                <!-- a draft's own row: ticked as it came (the AI's unticked) -->
                <v-checkbox-btn
                    v-if="row.draft"
                    :model-value="!!row.ticked"
                    density="compact"
                    class="flex-grow-0 in-tick"
                    :aria-label="'File in ' + row.target_name"
                    @update:model-value="$emit('change', keyOf(row), { ticked: $event })"
                ></v-checkbox-btn>
                <!-- "Located in Novgrad": the role, then its target -->
                <span class="in-text">
                    <span class="filed-as"><span v-if="lead(row)" class="role" data-testid="in-role-text">{{ lead(row) }}</span> <span v-if="row.new_name" class="stub-name">{{ row.target_name }}</span><a v-else class="thing-link" :class="{ dropped: row.draft && !row.ticked }" href="#" data-testid="in-target-link" @click.prevent="worlds.openThing(row.target_id)">{{ row.target_name }}</a></span>
                    <span v-if="row.new_name" class="note"> · new stub, {{ [row.new_name.kind, row.new_name.tag].filter(Boolean).join(', ') }}</span>
                    <span v-if="row.within_id" class="note"> · within <a class="thing-link" href="#" @click.prevent="worlds.openThing(row.within_id)">{{ row.within_name }}</a><span v-if="row.within_holds === false" class="within-stale" data-testid="in-within-stale"> (no longer part of {{ row.target_name }})</span></span>
                </span>
                <!-- its date, group and buttons at the row's right -->
                <span class="in-end d-flex align-center ga-2">
                    <span v-if="dates(row)" class="when" data-testid="in-dates">{{ dates(row) }}</span>
                    <span v-if="draft && !row.draft" class="note">already filed</span>
                    <TagChip
                        v-if="!draft || row.draft"
                        local
                        testid="in-show-under"
                        label="Shows under"
                        prefix="shows under"
                        :tag="row.show_under"
                        :fallback="thing.tag"
                        empty-text="Other"
                        clear-text="its own tag"
                        @pick="showUnder(row, $event)"
                    ></TagChip>
                    <template v-if="!draft || row.draft">
                        <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit filing" data-testid="in-edit" @click="startEdit(row)"></v-btn>
                        <v-btn v-if="!draft && !row.until" icon="mdi-timer-off-outline" variant="text" size="x-small" density="comfortable" aria-label="End this" data-testid="in-end" @click="startEnd(row)"></v-btn>
                        <v-btn v-if="!draft && persons" icon="mdi-comment-alert-outline" variant="text" size="x-small" density="comfortable" aria-label="Add a but…" data-testid="in-add-but" @click="startBut(row)"></v-btn>
                        <v-btn icon="mdi-delete-outline" variant="text" size="x-small" density="comfortable" aria-label="Remove filing" data-testid="in-remove" :disabled="!draft && !!worlds.pending.remove_filing" @click="remove(row)"></v-btn>
                    </template>
                </span>
            </div>
            <div v-for="but in row.exceptions" :key="but.fact_id" class="but" data-testid="in-but">
                <i>but…</i> <LinkedText :segments="but.segments" />
            </div>

            <!-- edit one filing: only what changes is sent -->
            <div v-if="editing && editing.targetId === keyOf(row)" class="in-form pa-2 mb-2" data-testid="in-edit-form" @keydown.esc="escape($event)">
                <div class="d-flex align-center flex-wrap ga-2">
                    <v-combobox v-model="editing.role" :items="roleItems" label="Role" :placeholder="ROLE_HINT" density="compact" variant="outlined" hide-details class="in-role" autofocus></v-combobox>
                    <v-text-field v-model.number="editing.since" label="Since (year)" type="number" density="compact" variant="outlined" hide-details class="in-year"></v-text-field>
                    <v-text-field v-if="!draft" v-model.number="editing.until" label="Until (year)" type="number" density="compact" variant="outlined" hide-details class="in-year"></v-text-field>
                    <EntryAutocomplete
                        v-if="persons && !row.new_name"
                        v-model="editing.within"
                        :targets="withinItems(row)"
                        label="Within (a part of it)"
                        clearable
                        density="compact"
                        variant="outlined"
                        hide-details
                        class="in-target"
                    ></EntryAutocomplete>
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
                <NameHighlightInput v-model="butting.text" v-model:picks="butting.picks" label="How they differ" :show-label="false" :rows="1" dense autofocus class="flex-grow-1" @keydown.enter.exact="onButEnter($event, row)" />
                <v-btn color="accent" variant="flat" size="small" :disabled="!butting.text.trim()" :loading="!!worlds.pending.add_exception" @click="saveBut(row)">Add</v-btn>
                <v-btn variant="text" size="small" @click="butting = null">Cancel</v-btn>
            </div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, dateParts } from './worldDates.js';
import { filingDates, normaliseTag, roleLead } from './entryPage.js';
import { filingKey } from './draftPage.js';
import { linkPayload } from './nameHighlights.js';
import { STUB_KINDS, actsInWorld, escapeCloses, kindInfo } from './worldKinds.js';
import EntryAutocomplete from './EntryAutocomplete.vue';
import LinkedText from './LinkedText.vue';
import NameHighlightInput from './NameHighlightInput.vue';
import TagChip from './TagChip.vue';

// the target choice that makes a stub of the typed name, and its title
const NEW = '__new__';
const NEW_LABEL = 'Make a stub “';
// the role field's hint: a role says how the entry relates to the target,
// not what it is (that's its tag)
const ROLE_HINT = 'native, member, branch of…';

function yearOf(date) {
    return date ? dateParts(date).year : null;
}

// The entry page's "In" (mockup v3, screens A, B and D; laid out as in
// the polish-2 mockup "in-section"): a section of the page's left column
// just above Facts, its heading in the Facts heading's style with "+ In…"
// at its right, and one row per filing (`thing.in`, ended ones too), as
// a fact's row is (the same text size and dashed separator), with its
// target, role and dates
// ("since 979", "900–1015"), and for a person (a character or real being)
// the part of the target it's "within" and its "but…" exceptions under it.
// A part that has moved out of the target is marked "(no longer part of
// …)" (`within_holds` false; final review M3).
// Each row can be edited (`edit_filing`: only what changes is sent),
// ended ("End this": its `until`) or removed (`remove_filing`); a person's
// gets "+ but…" (`add_exception`). "+ In…" searches the world's entries
// and live stubs; a name the world hasn't makes a stub of it, with a kind
// and tag, filed here (`add_filing {new_name}`).
// A row reads the entry's way, as the character sheet does: "Native of
// Velikiy Ustyug" (`roleLead`). The role field offers the roles in use
// (`list_roles`), free text still allowed. Each row's "shows under" chip
// (the tag picker) names the group it shows under on the target's page
// (`show_under`), the entry's own tag while none is picked; "+ In…" can
// pick one too.
//
// On a draft (`draft`, the page's draft mode) nothing is sent: its own
// rows (`draft: true`) carry their tick, the AI's coming unticked (ruling
// F7); "+ In…" (an entry, or a stub of a typed name, made on accept),
// edit (role, since, within), "shows under" and remove are emitted for
// the draft (`add(target, {role, since, showUnder})`, `change(key,
// changes)`, `show-under(key, tag)`, `remove(key)`; a row's key is its
// target's id, or `new:<name>`). The draft's only addition to the page's
// rows is the tick. A stub's filings so far show as they are.
export default {
    name: 'EntryIn',
    components: { EntryAutocomplete, LinkedText, NameHighlightInput, TagChip },
    props: {
        // the page's payload (a draft's: its rows as the owner left them)
        thing: { type: Object, required: true },
        draft: { type: Boolean, default: false },
    },
    emits: ['add', 'change', 'remove', 'show-under'],
    setup() {
        return { worlds: useWorldsStore(), NEW, ROLE_HINT };
    },
    data() {
        // `sent`: a form's request is out; its reply closes the forms
        return { adding: null, editing: null, ending: null, butting: null, sent: false };
    },
    computed: {
        rows() {
            return this.thing.in || [];
        },
        // the roles in use, for the role picker
        roleItems() {
            return (this.worlds.roles || []).map((item) => item.role);
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
        // every entry and live stub but this one and those it's in
        targetItems() {
            const filed = new Set(this.rows.filter((row) => !row.draft || row.ticked).map((row) => row.target_id));
            return this.worlds.referenceTargets.filter((target) => target.id !== this.thing.id && !filed.has(target.id));
        },
        // "Make a stub" for a typed name the world hasn't
        newItems() {
            const name = this.newName.toLowerCase();
            const known = this.targetItems.some((target) => [target.name, ...(target.aka || [])].some((each) => each.toLowerCase() === name));
            return name && !known ? [{ id: NEW, name: `${NEW_LABEL}${this.newName}”`, subtitle: 'a new entry, to expand later' }] : [];
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
        lead(row) {
            return roleLead(row.role, { within: !!row.within_id });
        },
        // the group the filing shows under on its target's page (null: the
        // entry's own tag)
        showUnder(row, tag) {
            if ((tag || null) === (row.show_under || null)) {
                return;
            }
            if (this.draft) {
                this.$emit('show-under', this.keyOf(row), tag || null);
            } else {
                this.worlds.editFiling(row.target_id, { show_under: tag || null });
                this.sent = true;
            }
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
            // a role of null, not '': a combobox holding '' counts as filled
            // and hides its hint
            this.adding = { target: null, search: '', typed: '', kind: 'lore', tag: '', role: null, since: null, showUnder: null };
            this.worlds.listRoles();
        },
        saveAdd() {
            const adding = this.adding;
            if (!this.addValid) {
                return;
            }
            const filing = { role: (adding.role || '').trim() || null, since: this.year(adding.since) };
            const showUnder = adding.showUnder || null;
            if (this.draft) {
                const target = adding.target === NEW
                    ? { newName: this.newName, kind: adding.kind, tag: normaliseTag(adding.tag) || null }
                    : this.worlds.referenceTargets.find((item) => item.id === adding.target);
                if (target) {
                    this.$emit('add', target, { ...filing, showUnder });
                }
                this.adding = null;
                return;
            }
            if (adding.target === NEW) {
                this.worlds.addFiling({ newName: this.newName, kind: adding.kind, tag: normaliseTag(adding.tag) || null, ...filing, showUnder });
            } else {
                this.worlds.addFiling({ targetId: adding.target, ...filing, showUnder });
            }
            this.sent = true;
        },
        startEdit(row) {
            this.adding = null;
            this.ending = null;
            this.editing = {
                targetId: this.keyOf(row),
                role: row.role || null,
                since: yearOf(row.since),
                until: yearOf(row.until),
                within: row.within_id,
            };
            this.worlds.listRoles();
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
            const role = (editing.role || '').trim() || null;
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
            this.butting = { targetId: row.target_id, text: '', picks: {} };
        },
        // Enter adds it (not mid-composition: an IME's Enter picks a word)
        onButEnter(event, row) {
            if (event.isComposing) {
                return;
            }
            event.preventDefault();
            this.saveBut(row);
        },
        saveBut(row) {
            const text = this.butting?.text.trim();
            if (text) {
                const links = linkPayload(this.worlds.matchesFor(this.butting.text, this.worlds.thingAt), this.butting.picks, {}, this.butting.text);
                this.worlds.addException(row.target_id, text, null, links);
                this.sent = true;
            }
        },
    },
};
</script>

<style scoped>
/* a row and what's shown under it (its "but…"s, a form) read as one, the
   dashed separator under them all, as under a fact */
.in-host {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

/* a fact line's padding; the text is a fact's size (inherited, not set) */
.in-row {
    padding: 2px 0;
    column-gap: 8px;
}

.in-row.ended {
    opacity: 0.75;
}

.in-tick {
    flex: none;
}

/* the words take the room; the date, group and buttons keep to the
   row's right edge, dropping under the words when they can't fit */
.in-text {
    flex: 1 1 auto;
    min-width: 0;
}

.in-end {
    flex: none;
    margin-left: auto;
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
    color: rgb(var(--v-theme-muted));
}

.note {
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
