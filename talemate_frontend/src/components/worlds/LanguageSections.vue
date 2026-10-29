<template>
    <div class="language-sections" :data-testid="'language-view-' + tab">
        <!-- Language (approved mockup A): the language itself on the left,
             its name rules on the right, in the About tab's two columns -->
        <v-row v-if="tab === 'language'">
            <v-col cols="12" md="6">
                <!-- how it sounds, with depth, flavour and counts under it -->
                <div class="sec">
                    <div class="sh">
                        <span class="text-overline text-muted">How it sounds</span>
                        <v-btn v-if="!editing.sound" variant="text" size="small" color="accent" prepend-icon="mdi-pencil" @click="editing.sound = true">Edit</v-btn>
                        <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-file-replace-outline" @click="importing = !importing">Import a new version</v-btn>
                        <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-download" @click="exportFile">Export</v-btn>
                    </div>
                    <LanguageImport v-if="importing" :target-id="thing.id" @cancel="importing = false" />
                    <template v-if="editing.sound">
                        <v-textarea v-model="local.sound" rows="2" auto-grow variant="outlined" density="compact" hide-details autofocus data-testid="language-sound"></v-textarea>
                        <div class="d-flex ga-2 mt-1">
                            <v-btn size="small" color="accent" variant="flat" @click="saveSound">Save</v-btn>
                            <v-btn size="small" variant="text" @click="cancelSound">Cancel</v-btn>
                        </div>
                    </template>
                    <div v-else class="text-body-2" data-testid="language-sound-text">{{ fields.sound || 'Not described yet.' }}</div>
                    <div class="d-flex align-center flex-wrap settings text-caption text-muted mt-2">
                        <v-menu>
                            <template #activator="{ props: menuProps }">
                                <span v-bind="menuProps" class="setting" data-testid="language-depth">Depth: <b>{{ depthLabel }}</b></span>
                            </template>
                            <v-list density="compact">
                                <v-list-item v-for="d in DEPTHS" :key="d.value" :title="d.title" @click="saveField('depth', d.value)"></v-list-item>
                            </v-list>
                        </v-menu>
                        <span v-if="!editing.flavour" class="setting" data-testid="language-flavour" @click="editing.flavour = true">Sounds like: <b>{{ fields.flavour || 'none' }}</b></span>
                        <v-text-field
                            v-else
                            v-model="local.flavour"
                            placeholder="a real language, or none"
                            density="compact"
                            variant="outlined"
                            hide-details
                            autofocus
                            class="flavour-field"
                            @keydown.enter="saveFlavour"
                            @blur="saveFlavour"
                        ></v-text-field>
                        <span data-testid="language-counts">{{ words.length }} words · {{ phrases.length }} phrases · {{ generators.length }} name rules</span>
                    </div>
                </div>

                <div class="sec" data-testid="language-inventory">
                    <div class="sh"><span class="text-overline text-muted">Sound inventory</span></div>
                    <div v-if="!categoryEntries.length" class="text-body-2 text-muted">No sound groups yet.</div>
                    <div v-for="cat in categoryEntries" :key="cat.key" class="d-flex align-center ga-2 mb-1">
                        <span class="group-key">{{ cat.key }}</span>
                        <div class="d-flex flex-wrap ga-1">
                            <span v-for="(symbol, i) in cat.symbols" :key="i" class="sym">{{ symbol }}</span>
                        </div>
                    </div>
                </div>

                <div class="sec">
                    <div class="sh">
                        <span class="text-overline text-muted">Syllable notes</span>
                        <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="addSyllableNote">Add note</v-btn>
                    </div>
                    <div v-if="!local.syllable_notes.length" class="text-body-2 text-muted">None yet.</div>
                    <div v-for="(note, i) in local.syllable_notes" :key="i" class="d-flex align-center ga-1 note-row">
                        <v-text-field
                            v-if="editing.note === i"
                            v-model="local.syllable_notes[i]"
                            density="compact"
                            variant="outlined"
                            hide-details
                            autofocus
                            @keydown.enter="saveNote"
                            @blur="saveNote"
                        ></v-text-field>
                        <span v-else class="text-body-2">{{ note }}</span>
                        <v-btn v-if="editing.note !== i" icon="mdi-pencil" size="x-small" variant="text" density="comfortable" :aria-label="'Edit note ' + (i + 1)" @click="editing.note = i"></v-btn>
                        <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" color="delete" :aria-label="'Remove note ' + (i + 1)" @click="removeSyllableNote(i)"></v-btn>
                    </div>
                </div>

                <div class="sec">
                    <div class="sh">
                        <span class="text-overline text-muted">Grammar</span>
                        <v-btn v-if="!editing.grammar" variant="text" size="small" color="accent" prepend-icon="mdi-pencil" @click="editing.grammar = true">Edit</v-btn>
                    </div>
                    <template v-if="editing.grammar">
                        <v-textarea v-model="local.grammar" rows="2" auto-grow variant="outlined" density="compact" hide-details autofocus data-testid="language-grammar"></v-textarea>
                        <div class="d-flex ga-2 mt-1">
                            <v-btn size="small" color="accent" variant="flat" @click="saveGrammar">Save</v-btn>
                            <v-btn size="small" variant="text" @click="cancelGrammar">Cancel</v-btn>
                        </div>
                    </template>
                    <div v-else class="text-body-2">{{ local.grammar || 'No notes yet.' }}</div>
                </div>

                <div class="sec" data-testid="language-links">
                    <div class="sh">
                        <span class="text-overline text-muted">Related languages</span>
                        <v-btn v-if="!relForm" variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="relForm = { kind: 'similar', target: null, degree: 'close' }">Add</v-btn>
                    </div>
                    <div v-if="relForm" class="d-flex align-center flex-wrap ga-2 mb-2">
                        <v-select v-model="relForm.kind" :items="REL_KINDS" density="compact" variant="outlined" hide-details class="small-field"></v-select>
                        <v-select v-model="relForm.target" :items="relCandidates" label="Language" density="compact" variant="outlined" hide-details class="small-field" data-testid="language-similar-target"></v-select>
                        <v-select v-if="relForm.kind === 'similar'" v-model="relForm.degree" :items="DEGREES" label="How close" density="compact" variant="outlined" hide-details class="small-field"></v-select>
                        <v-btn size="small" color="accent" variant="flat" :disabled="!relForm.target" @click="saveRelation">Add</v-btn>
                        <v-btn size="small" variant="text" @click="relForm = null">Cancel</v-btn>
                    </div>
                    <div v-if="fields.descends_from" class="d-flex align-center ga-2 text-body-2" data-testid="language-parent">
                        <span class="text-muted">Descends from</span>
                        <a href="#" class="ln" @click.prevent="worlds.openThing(fields.descends_from)">{{ nameOf(fields.descends_from) }}</a>
                        <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" color="delete" aria-label="Doesn't descend from it" @click="saveField('descends_from', null)"></v-btn>
                    </div>
                    <div v-for="(link, i) in similar" :key="link.target" class="d-flex align-center ga-2 text-body-2" data-testid="language-similar">
                        <span class="text-muted">Similar to</span>
                        <a href="#" class="ln" @click.prevent="worlds.openThing(link.target)">{{ nameOf(link.target) }}</a>
                        <span class="degree">{{ DEGREE_LABELS[link.degree] || link.degree }}</span>
                        <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" color="delete" :aria-label="'Not similar to ' + nameOf(link.target)" @click="removeSimilar(i)"></v-btn>
                    </div>
                    <div v-if="!fields.descends_from && !similar.length && !relForm" class="text-body-2 text-muted">None yet.</div>
                </div>
            </v-col>

            <v-col cols="12" md="6">
                <div class="sec" data-testid="language-rules">
                    <div class="sh">
                        <span class="text-overline text-muted">Name rules</span>
                        <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-dice-multiple-outline" @click="reroll()">Roll all</v-btn>
                        <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="startRule">Add rule</v-btn>
                        <v-btn variant="text" size="small" color="accent" @click="toggleAdvanced">{{ advanced ? 'Close advanced edit' : 'Advanced edit' }}</v-btn>
                    </div>
                    <div v-if="advanced" class="mb-3">
                        <v-textarea v-model="rulesText" rows="10" auto-grow variant="outlined" density="compact" hide-details class="rules-text"></v-textarea>
                        <div class="d-flex align-center ga-2 mt-1">
                            <v-btn size="small" color="accent" variant="flat" @click="saveAdvanced">Save rules</v-btn>
                            <span v-if="rulesError" class="text-caption text-error">{{ rulesError }}</span>
                        </div>
                    </div>
                    <div v-if="ruleForm" class="d-flex align-center flex-wrap ga-2 mb-2" data-testid="language-rule-form">
                        <v-text-field v-model="ruleForm.name" label="Name" density="compact" variant="outlined" hide-details class="small-field"></v-text-field>
                        <v-select v-model="ruleForm.use" :items="useItems" label="Makes names for" density="compact" variant="outlined" hide-details class="small-field"></v-select>
                        <v-text-field v-model="ruleForm.pattern" label="First pattern" density="compact" variant="outlined" hide-details class="pattern-field font-mono"></v-text-field>
                        <v-btn size="small" color="accent" variant="flat" :disabled="!ruleForm.name.trim() || !ruleForm.pattern.trim()" @click="saveRule">Add</v-btn>
                        <v-btn size="small" variant="text" @click="ruleForm = null">Cancel</v-btn>
                    </div>
                    <div v-if="!local.generators.length" class="text-body-2 text-muted">This language has no name rules yet.</div>
                    <div v-for="(gen, g) in local.generators" :key="gen.id" class="rule" data-testid="language-generator">
                        <div class="d-flex align-center ga-2">
                            <span class="text-body-1">{{ gen.name }}</span>
                            <span class="text-caption text-muted">{{ useLabel(gen.use) }}</span>
                            <v-btn icon="mdi-dice-multiple-outline" size="x-small" variant="text" density="comfortable" color="accent" aria-label="Roll" title="Roll new sample names" @click="reroll()"></v-btn>
                        </div>
                        <div class="names" data-testid="language-samples">{{ (samples[gen.id] || []).slice(0, 12).join(', ') || 'Roll to see names.' }}</div>
                        <div class="d-flex align-center flex-wrap ga-2">
                            <span class="text-caption text-muted">Patterns</span>
                            <template v-for="(pattern, i) in gen.patterns" :key="'p' + i">
                                <v-text-field
                                    v-if="editingPattern && editingPattern.g === g && editingPattern.i === i"
                                    v-model="local.generators[g].patterns[i]"
                                    density="compact"
                                    variant="outlined"
                                    hide-details
                                    autofocus
                                    class="pattern-field font-mono"
                                    @keydown.enter="savePattern"
                                    @blur="savePattern"
                                ></v-text-field>
                                <span v-else class="pat" title="Click to edit" @click="editingPattern = { g, i }">
                                    {{ pattern }}<v-icon size="x-small" class="pat-x" :aria-label="'Remove pattern ' + pattern" @click.stop="removePattern(g, i)">mdi-close</v-icon>
                                </span>
                            </template>
                            <v-text-field
                                v-if="newPattern && newPattern.g === g"
                                v-model="newPattern.text"
                                density="compact"
                                variant="outlined"
                                hide-details
                                autofocus
                                placeholder="CVC"
                                class="pattern-field font-mono"
                                @keydown.enter="addPattern"
                                @blur="addPattern"
                            ></v-text-field>
                            <v-btn v-else variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="newPattern = { g, text: '' }">Pattern</v-btn>
                        </div>
                    </div>
                </div>
            </v-col>
        </v-row>

        <!-- Lexicon (approved mockup A): the dictionary beside the phrases,
             grouped under their category -->
        <v-row v-else-if="tab === 'lexicon'">
            <v-col cols="12" md="6">
                <div class="sec" data-testid="language-words">
                    <div class="sh">
                        <span class="text-overline text-muted">Dictionary</span>
                        <span class="text-caption text-muted">{{ local.words.length }} words</span>
                        <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="addWord">Add word</v-btn>
                        <v-text-field
                            v-model="search"
                            density="compact"
                            variant="outlined"
                            hide-details
                            clearable
                            prepend-inner-icon="mdi-magnify"
                            placeholder="Word or meaning"
                            class="search-field"
                        ></v-text-field>
                    </div>
                    <table class="dict">
                        <thead>
                            <tr><th>Word</th><th>Meanings</th><th>Part</th><th></th></tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in filteredWords" :key="row.index" data-testid="language-word">
                                <td v-for="field in WORD_FIELDS" :key="field" :class="'col-' + field" @click="field !== 'meanings' && (editCell = { index: row.index, field })">
                                    <!-- one chip per meaning: click to edit, × to remove, + to add -->
                                    <template v-if="field === 'meanings'">
                                        <template v-for="(meaning, m) in local.words[row.index].meanings" :key="m">
                                            <input
                                                v-if="isMeaningEdit(row.index, m)"
                                                v-model="meaningDraft"
                                                class="cell-input meaning-input"
                                                aria-label="meaning"
                                                @vue:mounted="({ el }) => el.focus()"
                                                @keydown.enter="saveMeaning"
                                                @keydown.esc="editCell = null"
                                                @blur="saveMeaning"
                                            />
                                            <span v-else class="meaning-chip" data-testid="word-meaning" title="Click to edit" @click.stop="editMeaning(row.index, m)">
                                                {{ meaning }}
                                                <v-icon icon="mdi-close" size="x-small" class="meaning-x" :aria-label="'Remove meaning ' + meaning" @click.stop="removeMeaning(row.index, m)"></v-icon>
                                            </span>
                                        </template>
                                        <input
                                            v-if="isMeaningEdit(row.index, -1)"
                                            v-model="meaningDraft"
                                            class="cell-input meaning-input"
                                            aria-label="new meaning"
                                            placeholder="meaning"
                                            @vue:mounted="({ el }) => el.focus()"
                                            @keydown.enter="saveMeaning"
                                            @keydown.esc="editCell = null"
                                            @blur="saveMeaning"
                                        />
                                        <v-btn
                                            v-else
                                            icon="mdi-plus"
                                            size="x-small"
                                            variant="text"
                                            density="compact"
                                            color="accent"
                                            data-testid="add-meaning"
                                            :aria-label="'Add a meaning to ' + local.words[row.index].word"
                                            @click.stop="editMeaning(row.index, -1)"
                                        ></v-btn>
                                    </template>
                                    <input
                                        v-else-if="editCell && editCell.index === row.index && editCell.field === field"
                                        v-model="local.words[row.index][field]"
                                        class="cell-input"
                                        :aria-label="field"
                                        @vue:mounted="({ el }) => el.focus()"
                                        @keydown.enter="saveCell"
                                        @blur="saveCell"
                                    />
                                    <span v-else>{{ local.words[row.index][field] }}</span>
                                    <!-- the word is used as a name in the world (worked out live); the
                                         tooltip says whose, and clicking opens it -->
                                    <span
                                        v-if="field === 'meanings' && usesOf(row.word).length"
                                        class="word-names"
                                        data-testid="word-names"
                                        :title="usesOf(row.word).map((u) => `${u.name} (${u.kind})`).join(', ')"
                                    >
                                        <a
                                            v-if="usesOf(row.word).length === 1"
                                            href="#"
                                            class="name-use"
                                            @click.prevent.stop="worlds.openThing(usesOf(row.word)[0].id)"
                                        >name</a>
                                        <v-menu v-else location="bottom start">
                                            <template #activator="{ props: menu }">
                                                <a href="#" class="name-use" v-bind="menu" @click.prevent.stop>name</a>
                                            </template>
                                            <v-list density="compact">
                                                <v-list-item
                                                    v-for="use in usesOf(row.word)"
                                                    :key="use.id"
                                                    :title="use.name"
                                                    :subtitle="use.kind"
                                                    @click="worlds.openThing(use.id)"
                                                ></v-list-item>
                                            </v-list>
                                        </v-menu>
                                    </span>
                                </td>
                                <td class="col-x">
                                    <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" color="delete" :aria-label="'Remove ' + local.words[row.index].word" @click.stop="removeWord(row.index)"></v-btn>
                                </td>
                            </tr>
                            <tr v-if="!filteredWords.length">
                                <td colspan="4" class="text-muted">No words found.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </v-col>

            <v-col cols="12" md="6">
                <div class="sec" data-testid="language-phrases">
                    <div class="sh">
                        <span class="text-overline text-muted">Phrases</span>
                        <span class="text-caption text-muted">{{ phrases.length }} phrases</span>
                        <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="openPhrase(null)">Add phrase</v-btn>
                    </div>
                    <div v-if="!phrases.length" class="text-body-2 text-muted">No phrases yet.</div>
                    <template v-for="group in groupedPhrases" :key="group.category">
                        <div class="category text-caption text-muted">{{ group.category.charAt(0).toUpperCase() + group.category.slice(1) }}</div>
                        <div v-for="phrase in group.items" :key="phrase.id" class="phrase" data-testid="language-phrase">
                            <div class="d-flex align-center ga-1">
                                <span class="text-body-2"><span class="foreign">{{ phrase.original }}</span> <span class="text-muted">—</span> {{ phrase.translation }}</span>
                                <v-btn icon="mdi-pencil" size="x-small" variant="text" density="comfortable" :aria-label="'Edit ' + phrase.original" @click="openPhrase(phrase)"></v-btn>
                                <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" color="delete" :aria-label="'Remove ' + phrase.original" @click="removePhrase(phrase)"></v-btn>
                            </div>
                            <div v-if="phrase.usage" class="text-caption text-muted">{{ phrase.usage }}</div>
                            <div v-if="(phrase.breakdown || []).length" class="d-flex flex-wrap ga-1 mt-1">
                                <span v-for="(part, i) in phrase.breakdown" :key="i" class="part">{{ part[0] }}: {{ part[1] }}</span>
                            </div>
                        </div>
                    </template>
                </div>

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
                                    <v-btn icon="mdi-close" size="small" variant="text" color="delete" aria-label="Remove part" @click="phraseForm.breakdown.splice(i, 1)"></v-btn>
                                </div>
                                <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-plus" @click="phraseForm.breakdown.push(['', ''])">Add word</v-btn>
                            </div>
                        </v-card-text>
                        <v-card-actions class="pa-0 mt-3">
                            <v-spacer></v-spacer>
                            <v-btn variant="text" @click="phraseDialog = false">Cancel</v-btn>
                            <v-btn color="accent" variant="flat" :disabled="!phraseValid" @click="savePhrase">Save</v-btn>
                        </v-card-actions>
                    </v-card>
                </v-dialog>
            </v-col>
        </v-row>
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

const DEGREES = [
    { title: 'close: talk with effort', value: 'close' },
    { title: 'distant: a few shared words', value: 'distant' },
    { title: 'one way: they follow us, not the reverse', value: 'one-way' },
];
const DEGREE_LABELS = { close: 'close: talk with effort', distant: 'distant: a few shared words', 'one-way': 'one way' };
const REL_KINDS = [
    { title: 'Similar to', value: 'similar' },
    { title: 'Descends from', value: 'parent' },
];

const USES = {
    words: 'ordinary words',
    people: 'people',
    character: 'characters',
    being: 'beings',
    places: 'places',
    place: 'places',
    things: 'things',
    item: 'items',
    event: 'events',
    lore: 'lore',
    species: 'species',
    race: 'races',
    adjective: 'describing words',
    demonym: 'peoples',
};

const WORD_FIELDS = ['word', 'meanings', 'part'];

function plain(value) {
    return JSON.parse(JSON.stringify(value ?? null));
}

// A language page's own tabs (languages 3a), as the owner approved them
// (docs/superpowers/mockups/2026-10-28-language-page-approved.html, A + A):
// Language (how it sounds, sounds, syllables, grammar and related
// languages; the name rules beside them) and Lexicon (the dictionary
// beside the phrases). Laid out like the About tab: section headings with
// their buttons right after them, two columns filling the page, and text
// that reads plain until ✎ opens it. Each edit saves one field of the
// language entry, an undoable world edit.
export default {
    name: 'LanguageSections',
    components: { LanguageImport },
    props: {
        thing: { type: Object, required: true },
        // 'language' | 'lexicon'
        tab: { type: String, required: true },
    },
    setup() {
        return { worlds: useWorldsStore(), DEPTHS, DEGREES, DEGREE_LABELS, REL_KINDS, WORD_FIELDS };
    },
    data() {
        return {
            local: this.fromThing(),
            editing: { sound: false, grammar: false, flavour: false, note: null },
            importing: false,
            search: '',
            editCell: null,
            meaningDraft: '',
            phraseDialog: false,
            phraseForm: { id: null, category: '', original: '', translation: '', usage: '', breakdown: [] },
            relForm: null,
            ruleForm: null,
            editingPattern: null,
            newPattern: null,
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
        depthLabel() {
            return DEPTHS.find((d) => d.value === (this.fields.depth || 'naming'))?.title || 'Naming style';
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
                .filter((w) => !query || (w.word || '').toLowerCase().includes(query) || w.meanings.some((m) => m.toLowerCase().includes(query)));
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
        similar() {
            return this.fields.similar || [];
        },
        otherLanguages() {
            return (this.worlds.things.language || [])
                .filter((t) => t.id !== this.thing.id)
                .map((t) => ({ title: t.name, value: t.id }));
        },
        relCandidates() {
            const taken = new Set(this.similar.map((l) => l.target));
            return this.relForm?.kind === 'similar'
                ? this.otherLanguages.filter((item) => !taken.has(item.value))
                : this.otherLanguages;
        },
        useItems() {
            return Object.entries(USES).map(([value, title]) => ({ title, value }));
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
                if (!this.worlds.things.language) this.worlds.listThings('language');
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
                words: plain(fields.words || []).map((w) => ({
                    word: w.word,
                    meanings: [...(w.meanings || (w.meaning ? [w.meaning] : []))],
                    part: w.part || '',
                    notes: w.notes,
                })),
            };
        },
        saveField(field, value) {
            if (JSON.stringify(value) === JSON.stringify(this.fields[field] ?? '')) return;
            this.worlds.setField(field, value);
        },
        saveSound() {
            this.saveField('sound', this.local.sound);
            this.editing.sound = false;
        },
        cancelSound() {
            this.local.sound = this.fields.sound || '';
            this.editing.sound = false;
        },
        saveFlavour() {
            this.saveField('flavour', (this.local.flavour || '').trim().toLowerCase());
            this.editing.flavour = false;
        },
        saveGrammar() {
            this.saveRules();
            this.editing.grammar = false;
        },
        cancelGrammar() {
            this.local.grammar = this.rules.grammar || '';
            this.editing.grammar = false;
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
        addSyllableNote() {
            this.local.syllable_notes.push('');
            this.editing.note = this.local.syllable_notes.length - 1;
        },
        saveNote() {
            this.editing.note = null;
            this.saveRules();
        },
        removeSyllableNote(index) {
            this.local.syllable_notes.splice(index, 1);
            this.saveRules();
        },
        // the entries a word names (`word_uses`, from the page)
        usesOf(word) {
            return (this.thing.word_uses || {})[(word || '').toLowerCase()] || [];
        },
        nameOf(id) {
            return (this.worlds.things.language || []).find((t) => t.id === id)?.name || '(deleted language)';
        },
        saveRelation() {
            const form = this.relForm;
            if (form.kind === 'parent') {
                this.saveField('descends_from', form.target);
            } else {
                this.saveField('similar', [...plain(this.similar), { target: form.target, degree: form.degree }]);
            }
            this.relForm = null;
        },
        removeSimilar(index) {
            this.saveField('similar', this.similar.filter((_, i) => i !== index));
        },
        startRule() {
            this.ruleForm = { name: '', use: 'places', pattern: '' };
        },
        saveRule() {
            const form = this.ruleForm;
            const base = form.name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'rule';
            let id = base;
            for (let n = 2; this.local.generators.some((g) => g.id === id); n += 1) id = `${base}-${n}`;
            this.local.generators.push({ id, name: form.name.trim(), use: form.use, patterns: [form.pattern.trim()] });
            this.ruleForm = null;
            this.saveRules();
        },
        savePattern() {
            this.editingPattern = null;
            this.saveRules();
        },
        addPattern() {
            const { g, text } = this.newPattern || {};
            this.newPattern = null;
            if (g == null || !(text || '').trim()) return;
            this.local.generators[g].patterns.push(text.trim());
            this.saveRules();
        },
        removePattern(g, i) {
            this.local.generators[g].patterns.splice(i, 1);
            this.saveRules();
        },
        isMeaningEdit(index, m) {
            const cell = this.editCell;
            return !!cell && cell.index === index && cell.field === 'meanings' && cell.m === m;
        },
        // m is the meaning's place, or -1 for a new one
        editMeaning(index, m) {
            this.meaningDraft = m >= 0 ? this.local.words[index].meanings[m] : '';
            this.editCell = { index, field: 'meanings', m };
        },
        saveMeaning() {
            const cell = this.editCell;
            if (!cell || cell.field !== 'meanings') return;
            this.editCell = null;
            const text = this.meaningDraft.trim();
            const meanings = this.local.words[cell.index].meanings;
            if (cell.m < 0) {
                if (!text) return;
                meanings.push(text);
            } else if (text === meanings[cell.m]) {
                return;
            } else if (text) {
                meanings[cell.m] = text;
            } else {
                meanings.splice(cell.m, 1);
            }
            this.saveWords();
        },
        removeMeaning(index, m) {
            this.local.words[index].meanings.splice(m, 1);
            this.saveWords();
        },
        saveCell() {
            this.editCell = null;
            this.saveWords();
        },
        saveWords() {
            const words = this.local.words
                .filter((w) => (w.word || '').trim())
                .map((w) => {
                    const meanings = w.meanings.map((m) => m.trim()).filter(Boolean);
                    const row = { word: w.word.trim(), meanings };
                    if ((w.part || '').trim()) row.part = w.part.trim();
                    if (w.notes) row.notes = w.notes;
                    return row;
                });
            this.saveField('words', words);
        },
        addWord() {
            this.search = '';
            this.local.words.unshift({ word: '', meanings: [], part: '' });
            this.editCell = { index: 0, field: 'word' };
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
            return USES[use] || use;
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
.sec {
    margin-top: 16px;
}
.sh {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 8px;
    margin-bottom: 4px;
}
.settings {
    gap: 18px;
}
.setting {
    cursor: pointer;
}
.setting b {
    font-weight: 400;
    color: rgb(var(--v-theme-on-surface));
    border-bottom: 1px dotted currentColor;
}
.flavour-field {
    flex: 0 1 200px;
}
.group-key {
    width: 1.5rem;
    font-family: monospace;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.sym {
    font-family: monospace;
    font-size: 0.85rem;
    padding: 1px 8px;
    border-radius: 3px;
    background: rgba(var(--v-theme-on-surface), 0.08);
}
.note-row {
    min-height: 32px;
}
.ln {
    color: rgb(var(--v-theme-link, var(--v-theme-primary)));
    text-decoration: none;
}
.degree,
.part {
    font-size: 0.75rem;
    padding: 1px 6px;
    border-radius: 3px;
    background: rgba(var(--v-theme-on-surface), 0.08);
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.small-field {
    flex: 0 1 200px;
}
.pattern-field {
    flex: 0 1 140px;
}
.rule {
    padding: 8px 0 10px;
    border-bottom: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
}
.rule:last-child {
    border-bottom: 0;
}
.names {
    margin: 2px 0 6px;
    font-style: italic;
    color: rgb(var(--v-theme-foreign));
}
.pat {
    font-family: monospace;
    font-size: 0.85rem;
    padding: 2px 4px 2px 8px;
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 3px;
    cursor: text;
}
.pat-x {
    margin-left: 4px;
    opacity: 0.55;
    cursor: pointer;
}
.pat-x:hover {
    opacity: 1;
    color: rgb(var(--v-theme-delete, var(--v-theme-error)));
}
.search-field {
    flex: 0 1 220px;
}
.dict {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}
.dict th {
    text-align: left;
    font-weight: 400;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 6px 8px;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.dict td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    cursor: text;
}
.dict .col-word {
    width: 24%;
    font-style: italic;
    color: rgb(var(--v-theme-foreign));
}
.dict .col-part {
    width: 22%;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.dict .col-x {
    width: 2.5rem;
    text-align: right;
    cursor: default;
}
.cell-input {
    width: 100%;
    color: inherit;
    font: inherit;
    outline: 1px solid rgb(var(--v-theme-accent, var(--v-theme-primary)));
    border-radius: 2px;
    padding: 0 2px;
}
.meaning-chip {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 0 4px 0 8px;
    margin: 1px 4px 1px 0;
    border-radius: 10px;
    background: rgba(var(--v-theme-on-surface), 0.08);
    cursor: pointer;
}
.dict [data-testid='add-meaning'] {
    opacity: 0.45;
}
.dict tr:hover [data-testid='add-meaning'],
.dict [data-testid='add-meaning']:focus-visible {
    opacity: 1;
}
.meaning-x {
    opacity: 0.5;
}
.meaning-x:hover {
    opacity: 1;
    color: rgb(var(--v-theme-delete));
}
.cell-input.meaning-input {
    width: 9em;
    margin-right: 4px;
}
.word-names {
    margin-left: 4px;
}
.name-use {
    font-size: 0.7rem;
    padding: 0 6px;
    border: 1px solid rgba(var(--v-theme-accent), 0.6);
    border-radius: 10px;
    color: rgb(var(--v-theme-accent));
    text-decoration: none;
    white-space: nowrap;
}
.category {
    margin: 10px 0 2px;
}
.phrase {
    padding: 4px 0 6px;
    border-bottom: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
}
.foreign {
    font-style: italic;
    color: rgb(var(--v-theme-foreign));
}
.font-mono :deep(input) {
    font-family: monospace;
}
.rules-text :deep(textarea) {
    font-family: monospace;
    font-size: 0.8rem;
}
</style>
