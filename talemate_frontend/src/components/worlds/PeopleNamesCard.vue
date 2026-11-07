<template>
    <div class="sec people-names" data-testid="people-names-card">
        <div class="sh">
            <span class="text-overline text-muted">People's names</span>
            <span v-if="found?.sample" class="text-caption text-muted ml-2">e.g. {{ found.sample }}</span>
            <v-spacer></v-spacer>
            <v-btn v-if="hasPeople" variant="text" size="small" color="accent" @click="$emit('change')">Change it…</v-btn>
        </div>
        <template v-if="!hasPeople">
            <div class="text-body-2 text-muted">No people's-name rules yet: people get names from the rules above, nothing passed down.</div>
            <div class="d-flex flex-wrap ga-2 mt-2">
                <v-btn size="small" variant="outlined" color="accent" prepend-icon="mdi-auto-fix" data-testid="people-names-fill" @click="$emit('fill')">Fill them in from the grammar</v-btn>
                <v-btn size="small" variant="text" data-testid="people-names-start" @click="write({ choices: { sex: ['man', 'woman'] }, kept_titles: [], address: [] })">Write them myself</v-btn>
            </div>
        </template>
        <template v-else>
            <!-- what a person's name depends on: the first of each the default -->
            <div v-for="(values, key) in people.choices" :key="'c' + key" class="row" data-testid="people-names-choice">
                <div class="d-flex align-baseline ga-3">
                    <span class="label">{{ key }}</span>
                    <template v-if="editing === 'c:' + key">
                        <v-text-field v-model="text" density="compact" variant="outlined" hide-details class="field" placeholder="the first is the default" @keydown.enter="saveChoice(key)"></v-text-field>
                        <v-btn size="small" color="accent" variant="flat" @click="saveChoice(key)">Save</v-btn>
                        <v-btn size="small" variant="text" @click="editing = null">Cancel</v-btn>
                    </template>
                    <template v-else>
                        <span class="rule">{{ values.join(' · ') }}</span>
                        <span class="text-caption text-muted">default {{ values[0] }}</span>
                        <v-btn icon="mdi-pencil" size="x-small" variant="text" density="comfortable" :aria-label="'Edit ' + key" @click="start('c:' + key, values.join(', '))"></v-btn>
                    </template>
                </div>
            </div>

            <!-- titles kept in the language's own word -->
            <div class="row" data-testid="people-names-kept">
                <div class="d-flex align-baseline flex-wrap ga-3">
                    <span class="label">kept titles</span>
                    <span v-if="!people.kept_titles.length && editing !== 'k'" class="rule text-muted">none: every title is written in English</span>
                    <v-chip
                        v-for="(title, i) in people.kept_titles"
                        :key="title.word"
                        size="small"
                        closable
                        @click:close="removeKept(i)"
                    ><span class="foreign">{{ title.word }}</span>&nbsp;“{{ title.meaning }}”</v-chip>
                    <template v-if="editing === 'k'">
                        <v-text-field v-model="kept.word" label="its word" density="compact" variant="outlined" hide-details class="small"></v-text-field>
                        <v-text-field v-model="kept.meaning" label="in English" density="compact" variant="outlined" hide-details class="small" @keydown.enter="saveKept"></v-text-field>
                        <v-btn size="small" color="accent" variant="flat" :disabled="!kept.word.trim() || !kept.meaning.trim()" @click="saveKept">Add</v-btn>
                        <v-btn size="small" variant="text" @click="editing = null">Cancel</v-btn>
                    </template>
                    <v-btn v-else size="x-small" variant="text" color="accent" prepend-icon="mdi-plus" @click="editing = 'k'; kept = { word: '', meaning: '' }">Kept title</v-btn>
                </div>
            </div>

            <!-- forms of address: how each kind of relationship says a name -->
            <div class="text-caption text-muted mt-2">How people are addressed (used in scenes):</div>
            <div v-for="(row, i) in found?.address || []" :key="'a' + i" class="row" data-testid="people-names-address">
                <div v-if="editing === 'a:' + i" class="d-flex align-center flex-wrap ga-2">
                    <v-text-field v-model="addressDraft.kind" label="kind" density="compact" variant="outlined" hide-details class="small"></v-text-field>
                    <v-text-field v-model="addressDraft.roles" label="role words" placeholder="mother, brother" density="compact" variant="outlined" hide-details class="field"></v-text-field>
                    <v-text-field v-model="addressDraft.uses" label="uses" placeholder="given, title, pet name" density="compact" variant="outlined" hide-details class="field" data-testid="people-names-address-uses"></v-text-field>
                    <v-checkbox v-model="addressDraft.default" label="for anyone else" density="compact" hide-details></v-checkbox>
                    <v-btn size="small" color="accent" variant="flat" data-testid="people-names-address-save" @click="saveAddress(i)">Save</v-btn>
                    <v-btn size="small" variant="text" color="delete" @click="removeAddress(i)">Remove</v-btn>
                    <v-btn size="small" variant="text" @click="editing = null">Cancel</v-btn>
                </div>
                <div v-else class="d-flex align-baseline ga-3">
                    <span class="label">{{ row.kind }}<span v-if="row.default" class="text-muted"> (anyone else)</span></span>
                    <span class="rule">{{ row.uses.join(' + ') }}<span v-if="row.roles.length" class="text-caption text-muted"> · {{ row.roles.join(', ') }}</span></span>
                    <span class="text-caption text-muted example" data-testid="people-names-address-example">{{ row.example }}</span>
                    <v-btn icon="mdi-pencil" size="x-small" variant="text" density="comfortable" :aria-label="'Edit ' + row.kind" data-testid="people-names-address-edit" @click="startAddress(i, row)"></v-btn>
                </div>
            </div>
            <v-btn size="small" variant="text" color="accent" prepend-icon="mdi-plus" class="mt-1" @click="addAddress">Address</v-btn>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

function plain(value) {
    return JSON.parse(JSON.stringify(value ?? null));
}

function words(text) {
    return String(text || '').split(',').map((w) => w.trim()).filter(Boolean);
}

// The Names chapter's People's names (languages 4b-2): the choices a
// person's name depends on, the titles kept in the language's own word,
// and the forms of address, each row with an example built from a sample
// person (the server's `language_people_names`), edited row by row and
// saved in the language's rules. With none: "Fill them in from the
// grammar" (`fill`, a Change it… run) or "Write them myself".
export default {
    name: 'PeopleNamesCard',
    props: {
        thing: { type: Object, required: true },
    },
    emits: ['fill', 'change'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { editing: null, text: '', kept: { word: '', meaning: '' }, addressDraft: null };
    },
    computed: {
        rulesField() {
            return this.thing.fields?.rules || {};
        },
        people() {
            return this.rulesField.people_names || null;
        },
        hasPeople() {
            return !!this.people;
        },
        found() {
            return this.worlds.peopleNames[this.thing.id] || null;
        },
    },
    watch: {
        rulesField: {
            immediate: true,
            handler() {
                this.worlds.loadPeopleNames(this.thing.id);
            },
        },
    },
    methods: {
        write(people) {
            this.worlds.setField('rules', { ...plain(this.rulesField), people_names: people });
            this.editing = null;
        },
        start(key, text) {
            this.editing = key;
            this.text = text;
        },
        saveChoice(key) {
            const people = plain(this.people);
            const values = words(this.text);
            if (values.length) people.choices[key] = values;
            else delete people.choices[key];
            this.write(people);
        },
        saveKept() {
            const people = plain(this.people);
            people.kept_titles.push({ word: this.kept.word.trim(), meaning: this.kept.meaning.trim() });
            this.write(people);
        },
        removeKept(i) {
            const people = plain(this.people);
            people.kept_titles.splice(i, 1);
            this.write(people);
        },
        startAddress(i, row) {
            this.addressDraft = { kind: row.kind, roles: row.roles.join(', '), uses: row.uses.join(', '), default: row.default };
            this.editing = 'a:' + i;
        },
        addAddress() {
            const people = plain(this.people);
            people.address.push({ kind: 'friends', roles: ['friend'], uses: ['given'], default: false });
            this.write(people);
        },
        saveAddress(i) {
            const people = plain(this.people);
            const draft = this.addressDraft;
            const row = { kind: draft.kind.trim() || 'someone', roles: words(draft.roles), uses: words(draft.uses), default: !!draft.default };
            // one row is for anyone else
            if (row.default) people.address.forEach((r) => { r.default = false; });
            people.address.splice(i, 1, row);
            this.write(people);
        },
        removeAddress(i) {
            const people = plain(this.people);
            people.address.splice(i, 1);
            this.write(people);
        },
    },
};
</script>

<style scoped>
.row {
    padding: 4px 0;
    border-bottom: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
}
.label {
    flex: 0 0 140px;
    color: rgb(var(--v-theme-muted, var(--v-theme-on-surface)));
}
.rule {
    flex: 1 1 auto;
}
.example {
    font-style: italic;
}
.field {
    flex: 0 1 220px;
}
.small {
    flex: 0 1 150px;
}
.foreign {
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
}
</style>
