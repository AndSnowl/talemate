<template>
    <div class="sec name-grammar" data-testid="name-grammar">
        <div class="sh">
            <span class="text-overline text-muted">Grammar for names</span>
            <v-spacer></v-spacer>
            <v-btn v-if="hasGrammar" variant="text" size="small" color="accent" data-testid="name-grammar-change" @click="$emit('fill')">Change it…</v-btn>
        </div>
        <template v-if="!hasGrammar">
            <div class="text-body-2 text-muted">No grammar for names yet: names are built in your word order.</div>
            <div class="d-flex flex-wrap ga-2 mt-2">
                <v-btn size="small" variant="outlined" color="accent" prepend-icon="mdi-auto-fix" data-testid="name-grammar-fill" @click="$emit('fill')">Fill them in from the grammar</v-btn>
                <v-btn size="small" variant="text" data-testid="name-grammar-start" @click="startEmpty">Write them myself</v-btn>
            </div>
        </template>
        <div v-for="row in rows" :key="row.key" class="row" data-testid="name-grammar-row">
            <div class="d-flex align-baseline ga-3">
                <span class="label">{{ row.label }}</span>
                <span class="rule">{{ row.rule }}</span>
                <v-spacer></v-spacer>
                <span v-if="row.error" class="text-caption text-error" data-testid="name-grammar-error">can't build: {{ row.error }}</span>
                <span v-else class="text-caption text-muted example" data-testid="name-grammar-example">{{ row.example }}</span>
                <v-btn icon="mdi-pencil" size="x-small" variant="text" density="comfortable" :aria-label="'Edit ' + row.label" data-testid="name-grammar-edit" @click="startEdit(row.key)"></v-btn>
            </div>
            <!-- the row's own small form -->
            <div v-if="editing === row.key" class="form d-flex align-center flex-wrap ga-2 mt-1">
                <template v-if="row.key === 'describing'">
                    <v-select v-model="draft.describing" :items="SIDES_NOUN" density="compact" variant="outlined" hide-details class="field" data-testid="name-grammar-describing"></v-select>
                </template>
                <template v-else-if="row.key === 'joining'">
                    <v-select v-model="draft.joining" :items="JOINING" density="compact" variant="outlined" hide-details class="field"></v-select>
                    <v-checkbox v-model="draft.clip_first" label="clip the first word to its first syllable" density="compact" hide-details></v-checkbox>
                </template>
                <template v-else-if="row.key === 'of'">
                    <v-select v-model="draft.of.how" :items="OF_HOW" density="compact" variant="outlined" hide-details class="small"></v-select>
                    <v-text-field v-model="draft.of.text" label="word or ending" density="compact" variant="outlined" hide-details class="small"></v-text-field>
                    <v-select v-if="draft.of.how === 'word'" v-model="draft.of.word_side" :items="SIDES_ITS" density="compact" variant="outlined" hide-details class="small"></v-select>
                    <v-checkbox v-model="draft.of.the" label="its noun takes “the”" density="compact" hide-details></v-checkbox>
                </template>
                <template v-else-if="row.key === 'the' || row.key === 'more_than_one'">
                    <ChangeList v-model="draft[row.key]" />
                </template>
                <template v-else-if="row.key.startsWith('ending:')">
                    <v-text-field v-model="endingDraft.ending" label="ending" density="compact" variant="outlined" hide-details class="small"></v-text-field>
                    <v-text-field v-model="endingDraft.meaning" label="means" density="compact" variant="outlined" hide-details class="small"></v-text-field>
                    <ChangeList v-model="endingDraft.changes" />
                    <v-btn size="small" variant="text" color="delete" @click="removeEnding">Remove</v-btn>
                </template>
                <v-btn size="small" color="accent" variant="flat" @click="save">Save</v-btn>
                <v-btn size="small" variant="text" @click="editing = null">Cancel</v-btn>
            </div>
        </div>
        <div v-if="hasGrammar" class="d-flex flex-wrap ga-2 mt-1">
            <v-btn v-if="!grammar.of" size="small" variant="text" color="accent" prepend-icon="mdi-plus" @click="addOf">“of”</v-btn>
            <v-btn v-if="!grammar.the?.length" size="small" variant="text" color="accent" prepend-icon="mdi-plus" @click="addForm('the')">“the”</v-btn>
            <v-btn v-if="!grammar.more_than_one?.length" size="small" variant="text" color="accent" prepend-icon="mdi-plus" @click="addForm('more_than_one')">More than one</v-btn>
            <v-btn size="small" variant="text" color="accent" prepend-icon="mdi-plus" data-testid="name-grammar-add-ending" @click="addEnding">Ending</v-btn>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import ChangeList from './NameGrammarChanges.vue';

const SIDES_NOUN = [
    { title: 'before the noun', value: 'before' },
    { title: 'after the noun', value: 'after' },
];
const SIDES_ITS = [
    { title: 'before its noun', value: 'before' },
    { title: 'after its noun', value: 'after' },
];
const JOINING = [
    { title: 'describing word first', value: 'describing_first' },
    { title: 'main word first', value: 'main_first' },
];
const OF_HOW = [
    { title: 'a word', value: 'word' },
    { title: 'an ending', value: 'ending' },
];

function plain(value) {
    return JSON.parse(JSON.stringify(value ?? null));
}

// The Names chapter's Grammar for names (languages 4b-1, mockup
// docs/superpowers/mockups/2026-11-02-languages-4b1-names-chapter.html):
// each rule in plain words with the example the engine builds from it
// (the server's `language_name_grammar`), edited row by row and saved in
// the language's rules. With none: "Fill them in from the grammar"
// (`fill`, a Change it… run) or "Write them myself".
export default {
    name: 'NameGrammarCard',
    components: { ChangeList },
    props: {
        thing: { type: Object, required: true },
    },
    emits: ['fill'],
    setup() {
        return { worlds: useWorldsStore(), SIDES_NOUN, SIDES_ITS, JOINING, OF_HOW };
    },
    data() {
        return { editing: null, draft: null, endingDraft: null };
    },
    computed: {
        rulesField() {
            return this.thing.fields?.rules || {};
        },
        grammar() {
            return this.rulesField.name_grammar || null;
        },
        hasGrammar() {
            return !!this.grammar;
        },
        rows() {
            const found = this.worlds.nameGrammar[this.thing.id];
            return this.hasGrammar ? found?.rows || [] : [];
        },
    },
    watch: {
        grammar: {
            immediate: true,
            handler() {
                this.worlds.loadNameGrammar(this.thing.id);
            },
        },
    },
    methods: {
        startEdit(key) {
            this.draft = {
                describing: 'before',
                joining: 'describing_first',
                clip_first: false,
                the: [],
                more_than_one: [],
                endings: [],
                ...plain(this.grammar),
            };
            this.draft.of = this.draft.of || { how: 'word', text: '', word_side: 'before', place: 'after', the: false };
            this.endingDraft = key.startsWith('ending:')
                ? plain(this.draft.endings.find((e) => `ending:${e.ending}` === key)) || { ending: '', meaning: '', changes: [] }
                : null;
            this.editing = key;
        },
        write(grammar) {
            this.worlds.setField('rules', { ...plain(this.rulesField), name_grammar: grammar });
        },
        save() {
            const grammar = this.draft;
            if (!grammar.of?.text?.trim()) grammar.of = null;
            if (this.endingDraft) {
                const key = this.editing.slice('ending:'.length);
                const at = grammar.endings.findIndex((e) => e.ending === key);
                const ending = { ...this.endingDraft, ending: this.endingDraft.ending.replace(/^-/, '').trim() };
                if (at >= 0) grammar.endings.splice(at, 1, ending);
                else grammar.endings.push(ending);
            }
            this.editing = null;
            this.write(grammar);
        },
        removeEnding() {
            const key = this.editing.slice('ending:'.length);
            this.draft.endings = this.draft.endings.filter((e) => e.ending !== key);
            this.endingDraft = null;
            this.editing = null;
            this.write(this.draft);
        },
        startEmpty() {
            this.write({ describing: 'before', joining: 'describing_first', clip_first: false, of: null, the: [], more_than_one: [], endings: [] });
        },
        addOf() {
            this.write({ ...plain(this.grammar), of: { how: 'word', text: 'of', word_side: 'before', place: 'after', the: false } });
        },
        addForm(form) {
            this.write({ ...plain(this.grammar), [form]: [{ when: '', kind: 'ending', text: form === 'the' ? 'a' : 's', drop: '' }] });
        },
        addEnding() {
            const grammar = plain(this.grammar);
            grammar.endings = [...(grammar.endings || []), { ending: 'new', meaning: 'a meaning', example: '', changes: [] }];
            this.write(grammar);
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
</style>
