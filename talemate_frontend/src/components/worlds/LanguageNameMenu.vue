<template>
    <div class="language-name-menu pa-2" data-testid="language-name-menu">
        <div class="d-flex align-center ga-2 mb-2">
            <span class="text-subtitle-2">{{ title }}</span>
        </div>

        <!-- which language: the one in reach first, any other a pick away -->
        <div v-if="menu && languages.length" class="d-flex flex-wrap ga-1 mb-2" data-testid="language-picker">
            <v-chip
                v-for="language in languages"
                :key="language.id"
                size="small"
                :variant="language.id === languageId ? 'flat' : 'outlined'"
                :color="language.id === languageId ? 'primary' : undefined"
                :prepend-icon="language.inReach ? 'mdi-map-marker' : undefined"
                :title="nameless(language) ? 'No name rules: it can\'t make names' : language.inReach ? 'Spoken here' : ''"
                :disabled="nameless(language)"
                @click="languageId = language.id"
            >{{ language.name }}</v-chip>
        </div>
        <div v-if="menu && !languages.length" class="text-body-2 text-muted">This world has no languages yet: import one in the World tab's Languages.</div>
        <v-checkbox
            v-if="offerSave"
            v-model="saveOnPage"
            label="Save on this page: spoken here"
            density="compact"
            hide-details
            data-testid="language-save-on-page"
        ></v-checkbox>

        <!-- Make a name / Reroll this part: candidates with definitions -->
        <template v-if="(mode === 'name' || mode === 'reroll') && languageId">
            <div v-if="names?.pending" class="text-caption text-muted py-2">Making names…</div>
            <div v-else-if="names?.error" class="text-caption text-error py-2">{{ names.error }}</div>
            <v-list v-else density="compact" class="candidates">
                <v-list-item
                    v-for="candidate in names?.names || []"
                    :key="candidate.name"
                    data-testid="language-candidate"
                    @click="pickName(candidate)"
                >
                    <div class="d-flex align-baseline ga-2">
                        <span class="candidate-name" data-testid="language-candidate-name">{{ candidate.name }}</span>
                        <span v-if="candidate.definition" class="text-caption text-muted">{{ candidate.definition }}</span>
                    </div>
                </v-list-item>
            </v-list>
            <v-btn size="small" variant="text" prepend-icon="mdi-refresh" :disabled="names?.pending" @click="roll">Reroll</v-btn>
        </template>

        <!-- Make a phrase: the language's own phrases -->
        <template v-else-if="mode === 'phrase' && languageId">
            <div v-if="!phrases.length" class="text-body-2 text-muted">This language has no phrases yet.</div>
            <v-list v-else density="compact" class="candidates">
                <template v-for="group in phraseGroups" :key="group.category">
                    <v-list-subheader>{{ group.category }}</v-list-subheader>
                    <v-list-item v-for="phrase in group.items" :key="phrase.id" data-testid="language-phrase-pick" @click="pickPhrase(phrase)">
                        <div class="d-flex align-baseline ga-2">
                            <span class="candidate-name">{{ phrase.original }}</span>
                            <span class="text-caption text-muted">{{ phrase.translation }}</span>
                        </div>
                    </v-list-item>
                </template>
            </v-list>
        </template>

        <!-- Add a selected word: its meaning, suggested and editable -->
        <template v-else-if="mode === 'word' && languageId">
            <v-text-field
                v-model="meaning"
                :label="`What “${selected}” means`"
                :placeholder="definitionPending ? 'suggesting…' : ''"
                density="compact"
                variant="outlined"
                hide-details
                class="mb-2"
                data-testid="language-word-meaning"
                @keydown.enter="saveWord"
            ></v-text-field>
            <div class="d-flex ga-2">
                <v-btn size="small" color="primary" variant="tonal" :disabled="!meaning.trim()" @click="saveWord">Save</v-btn>
                <v-btn size="small" variant="text" @click="$emit('done')">Cancel</v-btn>
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { menuLanguages, savedRow } from './languageMenu.js';

const TITLES = {
    name: 'Make a name',
    reroll: 'Reroll this part',
    phrase: 'Make a phrase',
    word: 'Add a word',
};

// The right-click menu's language part (languages 3a): names rolled from a
// language with their definitions, the language's phrases, or a selected
// word added with its meaning. The language starts as the one in reach of
// the box's page; with none, it's picked, and can be saved on the page.
export default {
    name: 'LanguageNameMenu',
    props: {
        // 'name' | 'reroll' | 'phrase' | 'word'
        mode: { type: String, required: true },
        thingId: { type: String, default: null },
        kind: { type: String, default: 'place' },
        selected: { type: String, default: '' },
        // a scene's message box: the speaker's and the place's languages
        scene: { type: Boolean, default: false },
    },
    emits: ['insert', 'done'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { languageId: null, saveOnPage: false, meaning: '', seed: 0 };
    },
    computed: {
        title() {
            return this.mode === 'word' ? `Add “${this.selected}” to a language` : TITLES[this.mode];
        },
        menu() {
            const menu = this.worlds.languageMenu;
            if (!menu || !!menu.scene !== this.scene) return null;
            return (menu.thing_id || null) === (this.thingId || null) ? menu : null;
        },
        languages() {
            return menuLanguages(this.menu);
        },
        language() {
            return this.languages.find((l) => l.id === this.languageId) || null;
        },
        offerSave() {
            return !!(this.menu && !this.menu.rows.length && this.languageId && this.thingId && this.thingId === this.worlds.selectedThingId);
        },
        names() {
            const names = this.worlds.languageNames;
            return names && names.language_id === this.languageId ? names : null;
        },
        phrases() {
            return this.language?.phrases || [];
        },
        phraseGroups() {
            const groups = {};
            for (const phrase of this.phrases) (groups[phrase.category] ||= []).push(phrase);
            return Object.entries(groups).map(([category, items]) => ({ category, items }));
        },
        definition() {
            const d = this.worlds.languageDefinition;
            return d && d.word === this.selected ? d : null;
        },
        definitionPending() {
            return !!this.definition?.pending;
        },
    },
    watch: {
        menu(menu) {
            if (menu && !this.languageId) {
                const start = this.languages.find((l) => l.id === menu.default);
                this.languageId = start && !this.nameless(start) ? start.id : null;
            }
        },
        languageId(id) {
            if (!id) return;
            if (this.mode === 'name' || this.mode === 'reroll') this.roll();
            if (this.mode === 'word') this.worlds.suggestDefinition(id, this.selected, '', this.scene);
        },
        'definition.definition'(text) {
            if (text && !this.meaning) this.meaning = text;
        },
    },
    mounted() {
        this.worlds.loadLanguageMenu(this.thingId, this.scene);
    },
    methods: {
        // a language with no name rules can't make names (its phrases and
        // words still can be used)
        nameless(language) {
            return (this.mode === 'name' || this.mode === 'reroll') && language.has_names === false;
        },
        pickPhrase(phrase) {
            this.$emit('insert', phrase.original);
            this.$emit('done');
        },
        roll() {
            this.seed += 1;
            this.worlds.requestLanguageNames(this.languageId, this.kind, Date.now() % 100000 + this.seed, '', this.scene);
        },
        saveOnPageIfAsked() {
            if (!this.saveOnPage) return;
            const own = (this.worlds.thing?.languages_own || []).map(({ name, ...row }) => row);
            this.worlds.setField('languages', [...own, savedRow(this.languageId)]);
        },
        pickName(candidate) {
            this.$emit('insert', candidate.name);
            this.worlds.addLanguageWord(this.languageId, candidate.name, candidate.definition || 'a name', this.scene);
            this.saveOnPageIfAsked();
            this.$emit('done');
        },
        saveWord() {
            if (!this.meaning.trim()) return;
            this.worlds.addLanguageWord(this.languageId, this.selected, this.meaning.trim(), this.scene);
            this.saveOnPageIfAsked();
            this.$emit('done');
        },
    },
};
</script>

<style scoped>
.language-name-menu {
    width: 380px;
    max-width: 90vw;
}
.candidates {
    max-height: 280px;
    overflow-y: auto;
    background: transparent;
}
.candidate-name {
    font-style: italic;
    color: rgb(var(--v-theme-foreign));
    white-space: nowrap;
}
</style>
