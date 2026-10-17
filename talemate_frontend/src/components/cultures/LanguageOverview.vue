<template>
    <div class="language-overview">
        <v-row>
            <v-col cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">How it sounds</v-card-title>
                    <v-card-text>
                        <v-textarea
                            v-model="local.sound"
                            rows="4"
                            auto-grow
                            hide-details
                            variant="outlined"
                            density="compact"
                            @blur="save()"
                        ></v-textarea>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col v-if="culture.language.writable" cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">Counts</v-card-title>
                    <v-card-text>
                        <div class="d-flex flex-wrap ga-6">
                            <div>
                                <div class="text-h6 font-weight-regular">{{ culture.language.dictionary.length }}</div>
                                <div class="text-caption text-muted">words</div>
                            </div>
                            <div>
                                <div class="text-h6 font-weight-regular">{{ culture.language.phrases.length }}</div>
                                <div class="text-caption text-muted">phrases</div>
                            </div>
                            <div>
                                <div class="text-h6 font-weight-regular">{{ culture.language.generators.length }}</div>
                                <div class="text-caption text-muted">generators</div>
                            </div>
                            <div>
                                <div class="text-h6 font-weight-regular">{{ glossaryNameCount }}</div>
                                <div class="text-caption text-muted">glossary names</div>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col v-if="culture.language.writable" cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">Sound inventory</v-card-title>
                    <v-card-text>
                        <div v-if="categoryEntries.length === 0" class="text-muted text-caption">
                            No categories recorded yet.
                        </div>
                        <div v-for="cat in categoryEntries" :key="cat.key" class="mb-2">
                            <div class="text-caption text-muted mb-1">{{ cat.key }}</div>
                            <v-chip
                                v-for="(symbol, i) in cat.symbols"
                                :key="i"
                                size="small"
                                label
                                class="mr-1 mb-1 font-mono"
                                variant="tonal"
                            >
                                {{ symbol }}
                            </v-chip>
                        </div>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col v-if="culture.language.writable" cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">Syllable notes</v-card-title>
                    <v-card-text>
                        <div v-for="(note, i) in local.syllable_notes" :key="i" class="d-flex align-center ga-1 mb-1">
                            <v-text-field
                                v-model="local.syllable_notes[i]"
                                density="compact"
                                variant="outlined"
                                hide-details
                                @blur="save()"
                            ></v-text-field>
                            <v-btn icon size="small" variant="text" @click="removeSyllableNote(i)">
                                <v-icon size="small" color="delete">mdi-close</v-icon>
                            </v-btn>
                        </div>
                        <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addSyllableNote()">
                            Add note
                        </v-btn>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col v-if="culture.language.writable" cols="12">
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
                            @blur="save()"
                        ></v-textarea>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col v-if="!culture.language.writable" cols="12">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">How other cultures say its names</v-card-title>
                    <v-card-text>
                        <div v-if="renderingEntries.length === 0" class="text-muted text-caption">
                            No names recorded for this culture yet.
                        </div>
                        <v-table v-else density="compact">
                            <thead>
                                <tr>
                                    <th>True name</th>
                                    <th v-for="other in otherCultures" :key="other.id">{{ other.name }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="entry in renderingEntries" :key="entry.id">
                                    <td class="font-mono">{{ entry.true_name || entry.text }}</td>
                                    <td v-for="other in otherCultures" :key="other.id">
                                        {{ entry.renderings[other.id] || '—' }}
                                    </td>
                                </tr>
                            </tbody>
                        </v-table>
                    </v-card-text>
                </v-card>
            </v-col>
        </v-row>
    </div>
</template>

<script>
import { dirtyLocalClone } from './dirtyLocalClone';

export default {
    name: 'LanguageOverview',
    mixins: [
        dirtyLocalClone({
            watchPath: 'culture',
            source: vm => vm.culture.language,
            identity: vm => vm.culture && vm.culture.id,
        }),
    ],
    props: {
        culture: {
            type: Object,
            required: true,
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        glossary: {
            type: Array,
            default: () => [],
        },
        send: {
            type: Function,
            required: true,
        },
    },
    computed: {
        glossaryNameCount() {
            return this.glossary.filter(e => e.language === this.culture.id).length;
        },
        categoryEntries() {
            const categories = this.culture.language.categories || {};
            return Object.keys(categories).map(key => ({
                key,
                symbols: (categories[key] || '').split(/\s+/).filter(Boolean),
            }));
        },
        otherCultures() {
            return this.cultures.filter(c => c.id !== this.culture.id);
        },
        renderingEntries() {
            return this.glossary.filter(e => e.language === this.culture.id);
        },
    },
    methods: {
        save() {
            const culture = JSON.parse(JSON.stringify(this.culture));
            culture.language = this.local;
            this.send('save_culture', { culture });
            this.clearLocalDirty();
        },
        addSyllableNote() {
            this.local.syllable_notes.push('');
        },
        removeSyllableNote(i) {
            this.local.syllable_notes.splice(i, 1);
            this.save();
        },
    },
}
</script>

<style scoped>
.font-mono {
    font-family: "Roboto Mono", ui-monospace, Menlo, monospace;
}
</style>
