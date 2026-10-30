<template>
    <div v-if="!draft || languageItems.length" class="entry-languages" data-testid="entry-languages">
        <!-- a section like In: its heading muted, "+ Add" at its right
             (the column is half the page wide) -->
        <div class="d-flex align-center mt-4 mb-1" data-testid="languages-heading">
            <span class="text-overline text-muted">Languages</span>
            <v-spacer></v-spacer>
            <v-btn v-if="!form" variant="text" size="small" color="accent" prepend-icon="mdi-plus" data-testid="languages-add" @click="startAdd">Add</v-btn>
        </div>

        <div v-if="form" class="languages-form pa-2 mb-2" data-testid="languages-form">
            <div class="d-flex align-center flex-wrap ga-2">
                <v-select
                    v-model="form.language"
                    :items="languageItems"
                    label="Language"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field-language"
                    data-testid="languages-language"
                ></v-select>
                <v-select
                    v-model="form.role"
                    :items="ROLES"
                    label="Role"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field-small"
                    data-testid="languages-role"
                ></v-select>
                <v-text-field
                    v-if="form.role === 'spoken'"
                    v-model.number="form.share"
                    label="Share %"
                    type="number"
                    min="0"
                    max="100"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field-year"
                    data-testid="languages-share"
                ></v-text-field>
                <v-select
                    v-if="isCharacter"
                    v-model="form.fluency"
                    :items="FLUENCIES"
                    label="Fluency"
                    density="compact"
                    variant="outlined"
                    hide-details
                    clearable
                    class="field-small"
                    data-testid="languages-fluency"
                ></v-select>
                <v-text-field v-model.number="form.since" label="Since (year)" type="number" density="compact" variant="outlined" hide-details class="field-year" data-testid="languages-since"></v-text-field>
                <v-text-field v-model.number="form.until" label="Until (year)" type="number" density="compact" variant="outlined" hide-details class="field-year" data-testid="languages-until"></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :disabled="!formValid" :loading="busy" @click="save">Save</v-btn>
                <v-btn variant="text" size="small" @click="form = null">Cancel</v-btn>
            </div>
            <div v-if="!languageItems.length" class="text-caption text-muted mt-1">This world has no languages yet: import one in the World tab's Languages.</div>
        </div>

        <!-- its own rows -->
        <div
            v-for="(row, index) in own"
            :key="index"
            class="languages-row d-flex align-center flex-wrap ga-2"
            data-testid="languages-row"
        >
            <a v-if="row.name" class="languages-name" href="#" @click.prevent="worlds.openThing(row.language)">{{ row.name }}</a>
            <span v-else class="text-muted font-italic">(deleted language)</span>
            <v-chip size="x-small" label variant="tonal">{{ row.role }}</v-chip>
            <span v-if="row.from_words" class="text-caption text-muted" data-testid="languages-from-words">from your words</span>
            <template v-if="row.role === 'spoken' && row.share != null">
                <span class="share-bar" :style="{ width: Math.max(2, row.share) * 0.8 + 'px' }"></span>
                <span class="text-caption">{{ row.share }}%</span>
            </template>
            <span v-if="row.fluency" class="text-caption text-muted">{{ row.fluency }}</span>
            <span v-if="dates(row)" class="text-caption text-muted">{{ dates(row) }}</span>
            <v-btn icon="mdi-pencil" size="x-small" variant="text" density="comfortable" :aria-label="'Edit ' + (row.name || 'row')" @click="startEdit(index)"></v-btn>
            <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" :aria-label="'Remove ' + (row.name || 'row')" :disabled="busy" @click="remove(index)"></v-btn>
        </div>

        <!-- nothing of its own: what it takes from where it's filed -->
        <div v-if="!own.length && inherited.length" class="text-body-2 text-muted" data-testid="languages-inherited">
            <template v-for="(group, gi) in inheritedGroups" :key="group.source">
                <span v-if="gi" class="mx-1">·</span>
                From {{ group.source }}: {{ group.rows.map(label).join(', ') }}
            </template>
            <v-btn size="x-small" variant="text" class="ml-1" :disabled="busy" @click="setItsOwn">Set its own</v-btn>
        </div>
        <!-- a draft with no language: cleaning waits for one (languages 4a) -->
        <div v-if="draft && !own.length && !form" class="d-flex align-center flex-wrap ga-2 text-body-2 text-muted">
            No language picked: real names in this draft are only marked.
            <v-btn size="small" variant="outlined" color="accent" prepend-icon="mdi-translate" data-testid="draft-pick-language" @click="startAdd('official')">Pick a language for this draft</v-btn>
        </div>
        <div v-else-if="!own.length && !inherited.length && !form" class="text-body-2 text-muted">None yet.</div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, dateParts } from './worldDates.js';

const ROLES = ['spoken', 'official', 'scholarly', 'ceremonial', 'trade', 'liturgical'];
const FLUENCIES = ['native', 'fluent', 'broken'];

function yearOf(date) {
    return date ? dateParts(date).year : null;
}

// A page's Languages section (languages 3a): its own rows (language, role,
// a share for a spoken one, a character's fluency, dates), or the languages
// it takes from what it's filed in, with "Set its own" to copy them in. On a
// draft (`draft`, languages 4a) the draft's rows, those found from the
// owner's words marked so; a change cleans the draft again, and with none,
// "Pick a language for this draft".
export default {
    name: 'EntryLanguages',
    props: {
        thing: { type: Object, required: true },
        // a draft's rows (languages 4a): shown and changed here, and
        // emitted as `change(rows)` instead of saved
        draft: { type: Boolean, default: false },
        rows: { type: Array, default: () => [] },
    },
    emits: ['change'],
    setup() {
        return { worlds: useWorldsStore(), ROLES, FLUENCIES };
    },
    data() {
        return { form: null };
    },
    computed: {
        own() {
            if (this.draft) {
                const names = new Map((this.worlds.things.language || []).map((t) => [t.id, t.name]));
                return this.rows.map((row) => ({ ...row, name: names.get(row.language) || '' }));
            }
            return this.thing.languages_own || [];
        },
        inherited() {
            return this.draft ? [] : (this.thing.languages_view || []).filter((r) => r.inherited);
        },
        inheritedGroups() {
            const groups = [];
            for (const row of this.inherited) {
                const source = row.source_name || '';
                let group = groups.find((g) => g.source === source);
                if (!group) groups.push((group = { source, rows: [] }));
                group.rows.push(row);
            }
            return groups;
        },
        isCharacter() {
            return this.thing.kind === 'character';
        },
        languageItems() {
            return (this.worlds.things.language || []).map((t) => ({ title: t.name, value: t.id }));
        },
        formValid() {
            const f = this.form;
            if (!f || !f.language || !f.role) return false;
            if (f.share != null && f.share !== '' && (f.share < 0 || f.share > 100)) return false;
            return !(f.since && f.until && f.until <= f.since);
        },
        busy() {
            return !!this.worlds.pending.set_field || (this.draft && !!this.worlds.pending.draft_languages);
        },
    },
    mounted() {
        if (!this.worlds.things.language) this.worlds.listThings('language');
    },
    methods: {
        label(row) {
            return row.role === 'spoken' && row.share != null ? `${row.name} (${row.share}%)` : `${row.name} (${row.role})`;
        },
        dates(row) {
            const since = yearOf(row.since);
            const until = yearOf(row.until);
            if (since && until) return `${since}–${until}`;
            if (since) return `since ${since}`;
            if (until) return `until ${until}`;
            return '';
        },
        startAdd(role = 'spoken') {
            this.form = { index: null, language: null, role: typeof role === 'string' ? role : 'spoken', share: null, fluency: null, since: null, until: null };
        },
        // the rows saved: on a page, its field; on a draft, back to it
        write(rows) {
            if (this.draft) {
                this.$emit('change', rows);
            } else {
                this.worlds.setField('languages', rows);
            }
        },
        startEdit(index) {
            const row = this.own[index];
            this.form = {
                index,
                language: row.language,
                role: row.role,
                share: row.share ?? null,
                fluency: row.fluency ?? null,
                since: yearOf(row.since),
                until: yearOf(row.until),
            };
        },
        stored(row) {
            // a row as the field stores it: no name, no empty keys
            const out = { language: row.language, role: row.role };
            if (row.role === 'spoken' && row.share != null && row.share !== '') out.share = Number(row.share);
            if (row.fluency) out.fluency = row.fluency;
            if (row.since) out.since = row.since;
            if (row.until) out.until = row.until;
            return out;
        },
        save() {
            const f = this.form;
            const row = this.stored({
                language: f.language,
                role: f.role,
                share: f.share,
                fluency: this.isCharacter ? f.fluency : null,
                since: f.since ? dateOf(f.since) : null,
                until: f.until ? dateOf(f.until) : null,
            });
            const rows = this.own.map(this.stored);
            if (f.index == null) rows.push(row);
            else rows[f.index] = row;
            this.write(rows);
            this.form = null;
        },
        remove(index) {
            this.write(this.own.filter((_, i) => i !== index).map(this.stored));
        },
        setItsOwn() {
            this.write(this.inherited.map((r) => this.stored({ language: r.language_id, role: r.role, share: r.share })));
        },
    },
};
</script>

<style scoped>
.languages-form {
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 4px;
}
.field-language {
    flex: 0 1 200px;
}
.field-small {
    flex: 0 1 150px;
}
.field-year {
    flex: 0 1 120px;
}
.languages-name {
    color: rgb(var(--v-theme-link, var(--v-theme-primary)));
    text-decoration: none;
}
.share-bar {
    display: inline-block;
    height: 8px;
    border-radius: 2px;
    background: rgb(var(--v-theme-success));
}
</style>
