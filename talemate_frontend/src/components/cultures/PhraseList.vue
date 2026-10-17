<template>
    <div class="phrase-list">
        <v-row>
            <v-col v-for="group in groupedPhrases" :key="group.category" cols="12" md="6">
                <v-card variant="tonal" class="pa-4 h-100">
                    <v-card-title class="text-caption text-uppercase text-muted pa-0 mb-2">
                        {{ group.category }}
                    </v-card-title>
                    <v-card-text class="pa-0">
                        <div v-for="phrase in group.items" :key="phrase.id" class="phrase-row py-2">
                            <div class="d-flex align-start ga-1">
                                <div class="flex-grow-1">
                                    <div class="font-italic text-highlight7">{{ phrase.original }}</div>
                                    <div>{{ phrase.translation }}</div>
                                    <div v-if="phrase.usage" class="text-caption text-muted">{{ phrase.usage }}</div>
                                    <div v-if="phrase.breakdown.length" class="d-flex flex-wrap ga-1 mt-1">
                                        <v-chip v-for="(part, i) in phrase.breakdown" :key="i" size="x-small" variant="tonal">
                                            {{ part[0] }}: {{ part[1] }}
                                        </v-chip>
                                    </div>
                                </div>
                                <v-btn icon size="small" variant="text" @click="openEdit(phrase)">
                                    <v-icon size="small">mdi-pencil</v-icon>
                                </v-btn>
                                <v-btn icon size="small" variant="text" @click="removePhrase(phrase)">
                                    <v-icon size="small" color="delete">mdi-close</v-icon>
                                </v-btn>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col v-if="groupedPhrases.length === 0" cols="12">
                <v-card variant="tonal" class="pa-4 text-muted text-center">
                    No phrases yet.
                </v-card>
            </v-col>
        </v-row>

        <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" class="mt-2" @click="openAdd()">
            Add phrase
        </v-btn>

        <v-dialog v-model="dialog" max-width="560">
            <v-card class="pa-4">
                <v-card-title class="pa-0 mb-3">{{ editing ? 'Edit phrase' : 'Add phrase' }}</v-card-title>
                <v-card-text class="pa-0 d-flex flex-column ga-3">
                    <v-text-field
                        v-model="form.category"
                        label="Category"
                        density="compact"
                        variant="outlined"
                        hide-details
                    ></v-text-field>
                    <v-text-field
                        v-model="form.original"
                        label="Original"
                        density="compact"
                        variant="outlined"
                        hide-details
                    ></v-text-field>
                    <v-text-field
                        v-model="form.translation"
                        label="Translation"
                        density="compact"
                        variant="outlined"
                        hide-details
                    ></v-text-field>
                    <v-text-field
                        v-model="form.usage"
                        label="Usage note"
                        density="compact"
                        variant="outlined"
                        hide-details
                    ></v-text-field>

                    <div>
                        <div class="text-caption text-muted mb-1">Breakdown</div>
                        <div v-for="(part, i) in form.breakdown" :key="i" class="d-flex align-center ga-1 mb-1">
                            <v-text-field
                                v-model="part[0]"
                                placeholder="word"
                                density="compact"
                                variant="outlined"
                                hide-details
                            ></v-text-field>
                            <v-text-field
                                v-model="part[1]"
                                placeholder="meaning"
                                density="compact"
                                variant="outlined"
                                hide-details
                            ></v-text-field>
                            <v-btn icon size="small" variant="text" @click="form.breakdown.splice(i, 1)">
                                <v-icon size="small" color="delete">mdi-close</v-icon>
                            </v-btn>
                        </div>
                        <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="form.breakdown.push(['', ''])">
                            Add part
                        </v-btn>
                    </div>
                </v-card-text>
                <v-card-actions class="pa-0 mt-3">
                    <v-spacer></v-spacer>
                    <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
                    <v-btn color="primary" variant="flat" @click="saveForm()">Save</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script>
import { v4 as uuidv4 } from 'uuid';
import { dirtyLocalClone } from './dirtyLocalClone';

export default {
    name: 'PhraseList',
    mixins: [
        dirtyLocalClone({
            watchPath: 'culture',
            // Only `language.phrases`: saves patch just that field.
            source: vm => ({ phrases: vm.culture.language.phrases }),
            identity: vm => vm.culture && vm.culture.id,
        }),
    ],
    props: {
        culture: {
            type: Object,
            required: true,
        },
        send: {
            type: Function,
            required: true,
        },
    },
    data() {
        return {
            dialog: false,
            editing: null,
            form: this.blankForm(),
        }
    },
    computed: {
        groupedPhrases() {
            const groups = [];
            const byCategory = {};
            for (const phrase of this.local.phrases) {
                if (!byCategory[phrase.category]) {
                    byCategory[phrase.category] = { category: phrase.category, items: [] };
                    groups.push(byCategory[phrase.category]);
                }
                byCategory[phrase.category].items.push(phrase);
            }
            return groups;
        },
    },
    methods: {
        blankForm() {
            return { id: null, category: '', original: '', translation: '', usage: '', breakdown: [] };
        },
        save() {
            this.send('patch_culture', { culture_id: this.culture.id, language: { phrases: this.local.phrases } });
            this.clearLocalDirty();
        },
        openAdd() {
            this.editing = null;
            this.form = this.blankForm();
            this.dialog = true;
        },
        openEdit(phrase) {
            this.editing = phrase;
            this.form = JSON.parse(JSON.stringify(phrase));
            this.dialog = true;
        },
        saveForm() {
            const breakdown = this.form.breakdown.filter(p => p[0] || p[1]);
            if (this.editing) {
                const i = this.local.phrases.findIndex(p => p.id === this.editing.id);
                if (i !== -1) {
                    this.local.phrases.splice(i, 1, {
                        id: this.editing.id,
                        category: this.form.category,
                        original: this.form.original,
                        translation: this.form.translation,
                        usage: this.form.usage,
                        breakdown,
                    });
                }
            } else {
                this.local.phrases.push({
                    id: uuidv4(),
                    category: this.form.category,
                    original: this.form.original,
                    translation: this.form.translation,
                    usage: this.form.usage,
                    breakdown,
                });
            }
            this.dialog = false;
            this.save();
        },
        removePhrase(phrase) {
            const i = this.local.phrases.findIndex(p => p.id === phrase.id);
            if (i !== -1) {
                this.local.phrases.splice(i, 1);
                this.save();
            }
        },
    },
}
</script>

<style scoped>
.phrase-row {
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.phrase-row:last-child {
    border-bottom: 0;
}
</style>
