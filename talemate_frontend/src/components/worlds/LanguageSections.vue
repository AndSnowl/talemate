<template>
    <div class="language-sections" :data-testid="'language-view-' + tab">
        <!-- Language: how it sounds, its sounds, syllables and grammar -->
        <template v-if="tab === 'language'">
            <div class="d-flex align-center flex-wrap ga-1 mb-2">
                <v-btn size="small" variant="text" prepend-icon="mdi-file-replace-outline" @click="importing = !importing">Import a new version</v-btn>
                <v-btn size="small" variant="text" prepend-icon="mdi-download" @click="exportFile">Export</v-btn>
            </div>
            <LanguageImport v-if="importing" :target-id="thing.id" @cancel="importing = false" />

            <v-row>
                <v-col cols="12" md="6">
                    <v-card class="mb-4" variant="tonal">
                        <v-card-title class="text-caption text-uppercase text-muted">How it sounds</v-card-title>
                        <v-card-text>
                            <v-textarea
                                v-model="local.sound"
                                rows="3"
                                auto-grow
                                hide-details
                                variant="outlined"
                                density="compact"
                                data-testid="language-sound"
                                @blur="saveField('sound', local.sound)"
                            ></v-textarea>
                            <div class="d-flex flex-wrap ga-2 mt-3">
                                <v-select
                                    :model-value="depth"
                                    :items="DEPTHS"
                                    label="Depth"
                                    density="compact"
                                    variant="outlined"
                                    hide-details
                                    class="small-field"
                                    data-testid="language-depth"
                                    @update:model-value="(value) => saveField('depth', value)"
                                ></v-select>
                                <v-text-field
                                    v-model="local.flavour"
                                    label="Sounds like"
                                    placeholder="a real language, or none"
                                    density="compact"
                                    variant="outlined"
                                    hide-details
                                    class="small-field"
                                    data-testid="language-flavour"
                                    @blur="saveField('flavour', local.flavour.trim().toLowerCase())"
                                ></v-text-field>
                            </div>
                        </v-card-text>
                    </v-card>
                </v-col>

                <v-col cols="12" md="6">
                    <v-card class="mb-4" variant="tonal">
                        <v-card-title class="text-caption text-uppercase text-muted">Counts</v-card-title>
                        <v-card-text>
                            <div class="d-flex flex-wrap ga-6" data-testid="language-counts">
                                <div>
                                    <div class="text-h6 font-weight-regular">{{ words.length }}</div>
                                    <div class="text-caption text-muted">words</div>
                                </div>
                                <div>
                                    <div class="text-h6 font-weight-regular">{{ phrases.length }}</div>
                                    <div class="text-caption text-muted">phrases</div>
                                </div>
                                <div>
                                    <div class="text-h6 font-weight-regular">{{ generators.length }}</div>
                                    <div class="text-caption text-muted">name rules</div>
                                </div>
                            </div>
                        </v-card-text>
                    </v-card>
                </v-col>

                <v-col cols="12" md="6">
                    <v-card class="mb-4" variant="tonal" data-testid="language-inventory">
                        <v-card-title class="text-caption text-uppercase text-muted">Sound inventory</v-card-title>
                        <v-card-text>
                            <div v-if="!categoryEntries.length" class="text-muted text-caption">No sound groups recorded yet.</div>
                            <div v-for="cat in categoryEntries" :key="cat.key" class="mb-2">
                                <div class="text-caption text-muted mb-1">{{ cat.key }}</div>
                                <v-chip
                                    v-for="(symbol, i) in cat.symbols"
                                    :key="i"
                                    size="small"
                                    label
                                    class="mr-1 mb-1 font-mono"
                                    variant="tonal"
                                >{{ symbol }}</v-chip>
                            </div>
                        </v-card-text>
                    </v-card>
                </v-col>

                <v-col cols="12" md="6">
                    <v-card class="mb-4" variant="tonal">
                        <v-card-title class="text-caption text-uppercase text-muted">Syllable notes</v-card-title>
                        <v-card-text>
                            <div v-for="(note, i) in local.syllable_notes" :key="i" class="d-flex align-center ga-1 mb-1">
                                <v-text-field
                                    v-model="local.syllable_notes[i]"
                                    density="compact"
                                    variant="outlined"
                                    hide-details
                                    @blur="saveRules()"
                                ></v-text-field>
                                <v-btn icon size="small" variant="text" :aria-label="'Remove note ' + (i + 1)" @click="removeSyllableNote(i)">
                                    <v-icon size="small" color="delete">mdi-close</v-icon>
                                </v-btn>
                            </div>
                            <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="local.syllable_notes.push('')">Add note</v-btn>
                        </v-card-text>
                    </v-card>
                </v-col>

                <v-col cols="12">
                    <v-card class="mb-4" variant="tonal">
                        <v-card-title class="text-caption text-uppercase text-muted">Grammar notes</v-card-title>
                        <v-card-text>
                            <v-textarea
                                v-model="local.grammar"
                                rows="3"
                                auto-grow
                                hide-details
                                variant="outlined"
                                density="compact"
                                data-testid="language-grammar"
                                @blur="saveRules()"
                            ></v-textarea>
                        </v-card-text>
                    </v-card>
                </v-col>
            </v-row>
        </template>

        <!-- Dictionary: words, meanings and parts -->
        <div v-else-if="tab === 'dictionary'" data-testid="language-words">
            <div class="d-flex align-center flex-wrap ga-2 mb-3">
                <span class="text-muted text-caption">{{ local.words.length }} words · showing {{ filteredWords.length }}</span>
                <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addWord">Add word</v-btn>
                <v-spacer></v-spacer>
                <v-text-field
                    v-model="search"
                    density="compact"
                    variant="outlined"
                    hide-details
                    clearable
                    prepend-inner-icon="mdi-magnify"
                    placeholder="Word or meaning"
                    class="flex-grow-0 search-field"
                ></v-text-field>
            </div>
            <v-table density="compact">
                <thead>
                    <tr>
                        <th>Word</th>
                        <th>Meaning</th>
                        <th>Part</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="row in filteredWords" :key="row.index" data-testid="language-word">
                        <td class="word-col">
                            <v-text-field v-model="local.words[row.index].word" density="compact" variant="plain" hide-details class="font-italic text-foreign" @blur="saveWords"></v-text-field>
                        </td>
                        <td class="meaning-col">
                            <v-text-field v-model="local.words[row.index].meaning" density="compact" variant="plain" hide-details @blur="saveWords"></v-text-field>
                        </td>
                        <td class="part-col">
                            <v-text-field v-model="local.words[row.index].part" density="compact" variant="plain" hide-details placeholder="noun, verb…" @blur="saveWords"></v-text-field>
                        </td>
                        <td class="text-right">
                            <v-btn icon size="small" variant="text" :aria-label="'Remove ' + local.words[row.index].word" @click="removeWord(row.index)">
                                <v-icon size="small" color="delete">mdi-close</v-icon>
                            </v-btn>
                        </td>
                    </tr>
                    <tr v-if="!filteredWords.length">
                        <td colspan="4" class="text-center text-muted">No words found.</td>
                    </tr>
                </tbody>
            </v-table>
        </div>

        <!-- Phrases: by category, with word-by-word breakdowns -->
        <div v-else-if="tab === 'phrases'" data-testid="language-phrases">
            <v-row>
                <v-col v-for="group in groupedPhrases" :key="group.category" cols="12" md="6">
                    <v-card variant="tonal" class="pa-4 h-100">
                        <v-card-title class="text-caption text-uppercase text-muted pa-0 mb-2">{{ group.category }}</v-card-title>
                        <v-card-text class="pa-0">
                            <div v-for="phrase in group.items" :key="phrase.id" class="phrase-row py-2" data-testid="language-phrase">
                                <div class="d-flex align-start ga-1">
                                    <div class="flex-grow-1">
                                        <div class="font-italic text-foreign">{{ phrase.original }}</div>
                                        <div>{{ phrase.translation }}</div>
                                        <div v-if="phrase.usage" class="text-caption text-muted">{{ phrase.usage }}</div>
                                        <div v-if="(phrase.breakdown || []).length" class="d-flex flex-wrap ga-1 mt-1">
                                            <v-chip v-for="(part, i) in phrase.breakdown" :key="i" size="x-small" variant="tonal">{{ part[0] }}: {{ part[1] }}</v-chip>
                                        </div>
                                    </div>
                                    <v-btn icon size="small" variant="text" :aria-label="'Edit ' + phrase.original" @click="openPhrase(phrase)">
                                        <v-icon size="small">mdi-pencil</v-icon>
                                    </v-btn>
                                    <v-btn icon size="small" variant="text" :aria-label="'Remove ' + phrase.original" @click="removePhrase(phrase)">
                                        <v-icon size="small" color="delete">mdi-close</v-icon>
                                    </v-btn>
                                </div>
                            </div>
                        </v-card-text>
                    </v-card>
                </v-col>
                <v-col v-if="!groupedPhrases.length" cols="12">
                    <v-card variant="tonal" class="pa-4 text-muted text-center">No phrases yet.</v-card>
                </v-col>
            </v-row>
            <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" class="mt-2" @click="openPhrase(null)">Add phrase</v-btn>

            <v-dialog v-model="phraseDialog" max-width="560">
                <v-card class="pa-4">
                    <v-card-title class="pa-0 mb-3">{{ phraseForm.id ? 'Edit phrase' : 'Add phrase' }}</v-card-title>
                    <v-card-text class="pa-0 d-flex flex-column ga-3">
                        <v-text-field v-model="phraseForm.category" label="Category (greeting, curse, saying…)" density="compact" variant="outlined" hide-details></v-text-field>
                        <v-text-field v-model="phraseForm.original" label="In the language" density="compact" variant="outlined" hide-details></v-text-field>
                        <v-text-field v-model="phraseForm.translation" label="Translation" density="compact" variant="outlined" hide-details></v-text-field>
                        <v-text-field v-model="phraseForm.usage" label="When it's said" density="compact" variant="outlined" hide-details></v-text-field>
                        <div>
                            <div class="text-caption text-muted mb-1">Word by word</div>
                            <div v-for="(part, i) in phraseForm.breakdown" :key="i" class="d-flex align-center ga-1 mb-1">
                                <v-text-field v-model="part[0]" placeholder="word" density="compact" variant="outlined" hide-details></v-text-field>
                                <v-text-field v-model="part[1]" placeholder="meaning" density="compact" variant="outlined" hide-details></v-text-field>
                                <v-btn icon size="small" variant="text" aria-label="Remove part" @click="phraseForm.breakdown.splice(i, 1)">
                                    <v-icon size="small" color="delete">mdi-close</v-icon>
                                </v-btn>
                            </div>
                            <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="phraseForm.breakdown.push(['', ''])">Add word</v-btn>
                        </div>
                    </v-card-text>
                    <v-card-actions class="pa-0 mt-3">
                        <v-spacer></v-spacer>
                        <v-btn variant="text" @click="phraseDialog = false">Cancel</v-btn>
                        <v-btn color="primary" variant="tonal" :disabled="!phraseValid" @click="savePhrase">Save</v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>
        </div>

        <!-- Name rules: each rule set with sample names and its patterns -->
        <div v-else-if="tab === 'rules'" data-testid="language-rules">
            <div class="d-flex align-center ga-2 mb-2">
                <v-btn size="small" variant="tonal" prepend-icon="mdi-dice-multiple-outline" @click="reroll()">Roll all</v-btn>
                <v-btn size="small" variant="text" @click="toggleAdvanced">{{ advanced ? 'Close advanced edit' : 'Advanced edit' }}</v-btn>
            </div>
            <div v-if="advanced" class="mb-3">
                <v-textarea v-model="rulesText" rows="10" auto-grow variant="outlined" density="compact" hide-details class="rules-text"></v-textarea>
                <div class="d-flex align-center ga-2 mt-1">
                    <v-btn size="small" color="primary" variant="tonal" @click="saveAdvanced">Save rules</v-btn>
                    <span v-if="rulesError" class="text-caption text-error">{{ rulesError }}</span>
                </div>
            </div>
            <v-row data-testid="language-samples">
                <v-col v-for="(gen, g) in local.generators" :key="gen.id" cols="12" md="6">
                    <v-card variant="tonal" class="pa-4 h-100" data-testid="language-generator">
                        <div class="d-flex align-center ga-2 mb-2">
                            <v-icon size="small" color="muted">{{ useIcon(gen.use) }}</v-icon>
                            <span class="text-body-1 flex-grow-1">{{ gen.name }}</span>
                            <span class="text-caption text-muted">{{ useLabel(gen.use) }}</span>
                            <v-btn icon="mdi-dice-multiple-outline" size="small" variant="tonal" density="comfortable" aria-label="Roll" title="Roll new sample names" @click="reroll()"></v-btn>
                        </div>
                        <div class="d-flex flex-wrap ga-1 mb-3">
                            <v-chip v-for="(name, i) in (samples[gen.id] || []).slice(0, 12)" :key="i" size="small" class="font-italic text-foreign">{{ name }}</v-chip>
                            <span v-if="!(samples[gen.id] || []).length" class="text-muted text-caption">Roll to see names.</span>
                        </div>
                        <div class="text-caption text-muted mb-1">Patterns</div>
                        <div v-for="(pattern, i) in gen.patterns" :key="'p' + i" class="d-flex align-center ga-1 mb-1">
                            <v-text-field v-model="local.generators[g].patterns[i]" density="compact" variant="outlined" hide-details class="font-mono" @blur="saveRules()"></v-text-field>
                            <v-btn icon size="small" variant="text" aria-label="Remove pattern" @click="removePattern(g, i)">
                                <v-icon size="small" color="delete">mdi-close</v-icon>
                            </v-btn>
                        </div>
                        <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="local.generators[g].patterns.push('')">Add pattern</v-btn>
                    </v-card>
                </v-col>
                <v-col v-if="!local.generators.length" cols="12">
                    <v-card variant="tonal" class="pa-4 text-muted text-center">This language has no name rules yet.</v-card>
                </v-col>
            </v-row>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import LanguageImport from './LanguageImport.vue';

const DEPTHS = [
    { title: 'Description only', value: 'description' },
    { title: 'Naming style', value: 'naming' },
    { title: 'Full language', value: 'full' },
];

const USES = {
    words: { label: 'ordinary words', icon: 'mdi-alphabetical' },
    people: { label: 'people', icon: 'mdi-account' },
    character: { label: 'characters', icon: 'mdi-account' },
    being: { label: 'beings', icon: 'mdi-star-four-points-outline' },
    places: { label: 'places', icon: 'mdi-map-marker' },
    place: { label: 'places', icon: 'mdi-map-marker' },
    things: { label: 'things', icon: 'mdi-cube-outline' },
    item: { label: 'items', icon: 'mdi-sword' },
    event: { label: 'events', icon: 'mdi-calendar-star' },
    lore: { label: 'lore', icon: 'mdi-book-open-variant' },
    species: { label: 'species', icon: 'mdi-dna' },
    race: { label: 'races', icon: 'mdi-family-tree' },
    adjective: { label: 'describing words', icon: 'mdi-format-letter-case' },
    demonym: { label: 'peoples', icon: 'mdi-account-group' },
};

function plain(value) {
    return JSON.parse(JSON.stringify(value ?? null));
}

// A language page's own tabs (languages 3a), as the old culture page showed
// a language: Language (how it sounds, counts, sound inventory, syllable
// and grammar notes), Dictionary, Phrases and Name rules. Each edit saves
// one field of the language entry, an undoable world edit.
export default {
    name: 'LanguageSections',
    components: { LanguageImport },
    props: {
        thing: { type: Object, required: true },
        // 'language' | 'dictionary' | 'phrases' | 'rules'
        tab: { type: String, required: true },
    },
    setup() {
        return { worlds: useWorldsStore(), DEPTHS };
    },
    data() {
        return {
            local: this.fromThing(),
            importing: false,
            search: '',
            phraseDialog: false,
            phraseForm: { id: null, category: '', original: '', translation: '', usage: '', breakdown: [] },
            advanced: false,
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
        rules() {
            return this.fields.rules || {};
        },
        generators() {
            return this.rules.generators || [];
        },
        words() {
            return this.fields.words || [];
        },
        phrases() {
            return this.fields.phrases || [];
        },
        categoryEntries() {
            return Object.entries(this.rules.categories || {}).map(([key, options]) => ({
                key,
                symbols: String(options).split(/\s+/).filter(Boolean),
            }));
        },
        filteredWords() {
            const query = (this.search || '').trim().toLowerCase();
            return this.local.words
                .map((w, index) => ({ ...w, index }))
                .filter((w) => !query || (w.word || '').toLowerCase().includes(query) || (w.meaning || '').toLowerCase().includes(query));
        },
        groupedPhrases() {
            const groups = {};
            for (const phrase of this.phrases) {
                (groups[phrase.category] ||= []).push(phrase);
            }
            return Object.entries(groups).map(([category, items]) => ({ category, items }));
        },
        phraseValid() {
            const f = this.phraseForm;
            return !!(f.category.trim() && f.original.trim() && f.translation.trim());
        },
        samples() {
            return this.worlds.languageSamples[this.thing.id] || {};
        },
    },
    watch: {
        // a save answers with the thing: take its values back in
        fields() {
            this.local = this.fromThing();
        },
        'thing.id': {
            immediate: true,
            handler() {
                this.importing = false;
                this.advanced = false;
                this.reroll(0);
            },
        },
        'worlds.languageExport'(exported) {
            if (exported && exported.thing_id === this.thing.id) {
                this.download(exported.text);
            }
        },
    },
    methods: {
        fromThing() {
            const fields = this.thing.fields || {};
            const rules = fields.rules || {};
            return {
                sound: fields.sound || '',
                flavour: fields.flavour || '',
                grammar: rules.grammar || '',
                syllable_notes: plain(rules.syllable_notes || []),
                generators: plain(rules.generators || []),
                words: plain(fields.words || []).map((w) => ({ part: '', ...w })),
            };
        },
        saveField(field, value) {
            if (JSON.stringify(value) === JSON.stringify(this.fields[field] ?? '')) return;
            this.worlds.setField(field, value);
        },
        saveRules() {
            const rules = {
                ...plain(this.rules),
                generators: this.local.generators.map((g) => ({ ...g, patterns: g.patterns.filter((p) => p.trim()) })),
                syllable_notes: this.local.syllable_notes.filter((n) => n.trim()),
                grammar: this.local.grammar,
            };
            if (!rules.grammar) delete rules.grammar;
            if (!rules.syllable_notes.length) delete rules.syllable_notes;
            this.saveField('rules', rules);
        },
        removeSyllableNote(index) {
            this.local.syllable_notes.splice(index, 1);
            this.saveRules();
        },
        removePattern(g, i) {
            this.local.generators[g].patterns.splice(i, 1);
            this.saveRules();
        },
        saveWords() {
            const words = this.local.words
                .filter((w) => (w.word || '').trim() && (w.meaning || '').trim())
                .map((w) => {
                    const row = { word: w.word.trim(), meaning: w.meaning.trim() };
                    if ((w.part || '').trim()) row.part = w.part.trim();
                    if (w.notes) row.notes = w.notes;
                    return row;
                });
            this.saveField('words', words);
        },
        addWord() {
            this.search = '';
            this.local.words.unshift({ word: '', meaning: '', part: '' });
        },
        removeWord(index) {
            this.local.words.splice(index, 1);
            this.saveWords();
        },
        openPhrase(phrase) {
            this.phraseForm = phrase
                ? { usage: '', breakdown: [], ...plain(phrase) }
                : { id: null, category: '', original: '', translation: '', usage: '', breakdown: [] };
            this.phraseDialog = true;
        },
        savePhrase() {
            const form = this.phraseForm;
            const phrase = {
                id: form.id || `p-${Date.now().toString(36)}`,
                category: form.category.trim(),
                original: form.original.trim(),
                translation: form.translation.trim(),
                usage: (form.usage || '').trim(),
                breakdown: form.breakdown.filter((p) => p[0].trim() && p[1].trim()),
            };
            const phrases = plain(this.phrases);
            const at = phrases.findIndex((p) => p.id === phrase.id);
            if (at >= 0) phrases[at] = phrase;
            else phrases.push(phrase);
            this.saveField('phrases', phrases);
            this.phraseDialog = false;
        },
        removePhrase(phrase) {
            this.saveField('phrases', this.phrases.filter((p) => p.id !== phrase.id));
        },
        reroll(seed) {
            this.seed = typeof seed === 'number' ? seed : this.seed + 1;
            this.worlds.rollLanguageSamples(this.thing.id, this.seed);
        },
        useLabel(use) {
            return USES[use]?.label || use;
        },
        useIcon(use) {
            return USES[use]?.icon || 'mdi-dice-multiple-outline';
        },
        toggleAdvanced() {
            this.advanced = !this.advanced;
            this.rulesError = '';
            this.rulesText = JSON.stringify(this.rules, null, 2);
        },
        saveAdvanced() {
            let rules;
            try {
                rules = JSON.parse(this.rulesText);
            } catch {
                this.rulesError = "That isn't valid JSON.";
                return;
            }
            this.rulesError = '';
            this.saveField('rules', rules);
            this.advanced = false;
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
.small-field {
    flex: 0 1 220px;
}
.search-field {
    width: 280px;
}
.word-col {
    min-width: 140px;
}
.meaning-col {
    min-width: 220px;
}
.part-col {
    min-width: 110px;
}
.font-mono :deep(input),
.font-mono {
    font-family: monospace;
}
.text-foreign,
.text-foreign :deep(input) {
    color: rgb(var(--v-theme-foreign));
}
.rules-text :deep(textarea) {
    font-family: monospace;
    font-size: 0.8rem;
}
</style>
