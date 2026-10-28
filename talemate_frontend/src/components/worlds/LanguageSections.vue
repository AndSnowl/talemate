<template>
    <div class="language-sections" data-testid="language-sections">
        <div class="d-flex align-center flex-wrap ga-1">
            <span class="text-overline text-muted">The language</span>
            <v-btn size="small" variant="text" prepend-icon="mdi-file-replace-outline" @click="importing = !importing">Import a new version</v-btn>
            <v-btn size="small" variant="text" prepend-icon="mdi-download" @click="exportFile">Export</v-btn>
        </div>
        <div class="d-flex align-center flex-wrap ga-2 mb-3">
            <v-select
                :model-value="depth"
                :items="depthItems"
                label="Depth"
                density="compact"
                variant="outlined"
                hide-details
                class="small-select"
                :disabled="busy"
                data-testid="language-depth"
                @update:model-value="(value) => worlds.setField('depth', value)"
            ></v-select>
            <v-text-field
                :model-value="flavour"
                label="Sounds like"
                placeholder="a real language, or none"
                density="compact"
                variant="outlined"
                hide-details
                class="small-select"
                :disabled="busy"
                data-testid="language-flavour"
                @change="(event) => worlds.setField('flavour', event.target.value.trim().toLowerCase())"
            ></v-text-field>
        </div>

        <LanguageImport v-if="importing" :target-id="thing.id" @cancel="importing = false" />

        <!-- how it sounds -->
        <div class="mb-3">
            <div class="text-subtitle-2">How it sounds</div>
            <v-textarea
                :model-value="sound"
                rows="2"
                auto-grow
                variant="outlined"
                density="compact"
                hide-details
                placeholder="Two or three plain sentences on how it sounds"
                :disabled="busy"
                data-testid="language-sound"
                @change="(event) => worlds.setField('sound', event.target.value)"
            ></v-textarea>
        </div>

        <!-- sample names -->
        <div class="mb-3" data-testid="language-samples">
            <div class="d-flex align-center ga-1">
                <span class="text-subtitle-2">Sample names</span>
                <v-btn size="x-small" variant="text" prepend-icon="mdi-refresh" @click="reroll">Reroll</v-btn>
            </div>
            <div v-for="generator in nameGenerators" :key="generator.id" class="text-body-2">
                <span class="text-caption text-muted">{{ generator.name }}:</span> {{ (samples[generator.id] || []).join(', ') }}
            </div>
            <div v-if="!nameGenerators.length" class="text-body-2 text-muted">This language has no name rules yet.</div>
        </div>

        <!-- words -->
        <div class="mb-3" data-testid="language-words">
            <div class="d-flex align-center ga-2">
                <span class="text-subtitle-2">Words <span class="text-caption text-muted">({{ words.length }})</span></span>
                <v-btn size="x-small" variant="text" prepend-icon="mdi-plus" :disabled="busy" @click="adding = true">Add word</v-btn>
                <v-text-field
                    v-model="search"
                    placeholder="Search words or meanings"
                    density="compact"
                    variant="plain"
                    hide-details
                    prepend-inner-icon="mdi-magnify"
                    class="word-search"
                ></v-text-field>
            </div>
            <div v-if="adding" class="d-flex align-center ga-2 my-1" data-testid="language-word-form">
                <v-text-field v-model="newWord" label="Word" density="compact" variant="outlined" hide-details class="word-field"></v-text-field>
                <v-text-field v-model="newMeaning" label="Meaning" density="compact" variant="outlined" hide-details @keydown.enter="addWord"></v-text-field>
                <v-btn size="small" color="primary" variant="tonal" :disabled="!newWord.trim() || !newMeaning.trim()" @click="addWord">Save</v-btn>
                <v-btn size="small" variant="text" @click="adding = false">Cancel</v-btn>
            </div>
            <v-table density="compact" class="word-table">
                <tbody>
                    <tr v-for="row in shownWords" :key="row.word" data-testid="language-word">
                        <td class="word-cell">{{ row.word }}</td>
                        <td>{{ row.meaning }}</td>
                        <td class="row-actions">
                            <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" :aria-label="'Remove ' + row.word" :disabled="busy" @click="removeWord(row.word)"></v-btn>
                        </td>
                    </tr>
                </tbody>
            </v-table>
        </div>

        <!-- phrases -->
        <div class="mb-3" data-testid="language-phrases">
            <div class="text-subtitle-2">Phrases</div>
            <div v-if="!phrases.length" class="text-body-2 text-muted">No phrases yet.</div>
            <div v-for="(group, category) in phraseGroups" :key="category" class="mb-1">
                <div class="text-caption text-muted">{{ category }}</div>
                <div v-for="phrase in group" :key="phrase.id" class="text-body-2">
                    <span class="foreign-phrase">{{ phrase.original }}</span> — {{ phrase.translation }}
                </div>
            </div>
        </div>

        <!-- name rules -->
        <div class="mb-3" data-testid="language-rules">
            <div class="d-flex align-center ga-1">
                <span class="text-subtitle-2">Name rules</span>
                <v-btn size="x-small" variant="text" @click="editRules">{{ editingRules ? 'Close' : 'Advanced edit' }}</v-btn>
            </div>
            <div v-if="!editingRules" class="text-body-2">
                <div v-for="generator in generators" :key="generator.id">
                    <span class="text-caption text-muted">{{ generator.name }} ({{ generator.use }}):</span> {{ generator.patterns.join(', ') }}
                </div>
            </div>
            <div v-else>
                <v-textarea v-model="rulesText" rows="8" auto-grow variant="outlined" density="compact" hide-details class="rules-text"></v-textarea>
                <div class="d-flex align-center ga-2 mt-1">
                    <v-btn size="small" color="primary" variant="tonal" :disabled="busy" @click="saveRules">Save rules</v-btn>
                    <span v-if="rulesError" class="text-caption text-error">{{ rulesError }}</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import LanguageImport from './LanguageImport.vue';

// A language page's own sections (languages 3a), below its facts: how it
// sounds, sample names, its words, phrases and name rules, its depth and
// flavour, and importing a new version or exporting it.
export default {
    name: 'LanguageSections',
    components: { LanguageImport },
    props: {
        thing: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            importing: false,
            adding: false,
            newWord: '',
            newMeaning: '',
            search: '',
            editingRules: false,
            rulesText: '',
            rulesError: '',
            seed: 0,
        };
    },
    computed: {
        fields() {
            return this.thing.fields || {};
        },
        depth() {
            return this.fields.depth || 'naming';
        },
        depthItems() {
            return [
                { title: 'Description only', value: 'description' },
                { title: 'Naming style', value: 'naming' },
                { title: 'Full language', value: 'full' },
            ];
        },
        flavour() {
            return this.fields.flavour || '';
        },
        sound() {
            return this.fields.sound || '';
        },
        rules() {
            return this.fields.rules || {};
        },
        generators() {
            return this.rules.generators || [];
        },
        nameGenerators() {
            return this.generators.filter((g) => g.use !== 'words');
        },
        words() {
            return this.fields.words || [];
        },
        shownWords() {
            const query = this.search.trim().toLowerCase();
            const rows = query
                ? this.words.filter((w) => w.word.toLowerCase().includes(query) || w.meaning.toLowerCase().includes(query))
                : this.words;
            return [...rows].sort((a, b) => a.word.localeCompare(b.word));
        },
        phrases() {
            return this.fields.phrases || [];
        },
        phraseGroups() {
            const groups = {};
            for (const phrase of this.phrases) {
                (groups[phrase.category] ||= []).push(phrase);
            }
            return groups;
        },
        samples() {
            return this.worlds.languageSamples[this.thing.id] || {};
        },
        busy() {
            return !!this.worlds.pending.set_field;
        },
    },
    watch: {
        'thing.id': {
            immediate: true,
            handler() {
                this.importing = false;
                this.reroll(0);
            },
        },
        rules() {
            this.reroll(this.seed);
        },
        'worlds.languageExport'(exported) {
            if (exported && exported.thing_id === this.thing.id) {
                this.download(exported.text);
            }
        },
    },
    methods: {
        reroll(seed) {
            this.seed = typeof seed === 'number' ? seed : this.seed + 1;
            this.worlds.rollLanguageSamples(this.thing.id, this.seed);
        },
        addWord() {
            const word = this.newWord.trim();
            const meaning = this.newMeaning.trim();
            if (!word || !meaning) return;
            const words = this.words.filter((w) => w.word.toLowerCase() !== word.toLowerCase());
            this.worlds.setField('words', [...words, { word, meaning }]);
            this.newWord = '';
            this.newMeaning = '';
            this.adding = false;
        },
        removeWord(word) {
            this.worlds.setField('words', this.words.filter((w) => w.word !== word));
        },
        editRules() {
            this.editingRules = !this.editingRules;
            this.rulesError = '';
            this.rulesText = JSON.stringify(this.rules, null, 2);
        },
        saveRules() {
            let rules;
            try {
                rules = JSON.parse(this.rulesText);
            } catch {
                this.rulesError = "That isn't valid JSON.";
                return;
            }
            this.rulesError = '';
            this.worlds.setField('rules', rules);
            this.editingRules = false;
        },
        exportFile() {
            this.worlds.exportLanguage(this.thing.id);
        },
        download(text) {
            const blob = new Blob([text], { type: 'application/json' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `${this.thing.name || 'language'}.language.json`;
            link.click();
            URL.revokeObjectURL(link.href);
        },
    },
};
</script>

<style scoped>
.small-select {
    flex: 0 1 240px;
}
.word-search {
    max-width: 260px;
}
.word-field {
    max-width: 180px;
}
.word-cell {
    font-weight: 500;
    width: 30%;
}
.row-actions {
    width: 2.5rem;
    text-align: right;
}
.foreign-phrase {
    font-style: italic;
    color: rgb(var(--v-theme-foreign));
}
.rules-text :deep(textarea) {
    font-family: monospace;
    font-size: 0.8rem;
}
</style>
