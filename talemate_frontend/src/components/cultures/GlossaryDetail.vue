<template>
    <v-card variant="tonal" class="pa-4">
        <v-card-title class="d-flex align-center ga-2 flex-wrap pa-0 mb-2">
            <span v-if="local.status === 'unreviewed'" class="unrev-dot"></span>
            <span class="text-h6 font-weight-regular">{{ local.text }}</span>
            <v-chip size="x-small" label :color="kindMeta.color" variant="tonal" :prepend-icon="kindMeta.icon">
                {{ local.kind }}
            </v-chip>
        </v-card-title>

        <v-card-text class="pa-0">
            <div class="origin-box text-body-2 mb-3 pa-3">
                <template v-if="local.origin.by === 'ai'">
                    <v-icon size="small" class="mr-1">mdi-robot-outline</v-icon>
                    The AI needed a {{ local.kind === 'person' ? 'name for a new character' : 'name' }} and rolled
                    <strong>{{ generatorName }}</strong>. It picked one from:
                    <div class="d-flex flex-wrap ga-1 mt-2">
                        <v-chip
                            v-for="candidate in local.origin.candidates"
                            :key="candidate"
                            size="small"
                            :color="candidate === local.text ? 'primary' : undefined"
                            :variant="candidate === local.text ? 'flat' : 'tonal'"
                        >
                            {{ candidate }}
                        </v-chip>
                    </div>
                </template>
                <template v-else-if="local.origin.by === 'ai_free'">
                    <v-icon size="small" class="mr-1">mdi-robot-outline</v-icon>
                    Made up by the AI with no language behind it. Assign it to a language once one exists.
                </template>
                <template v-else-if="local.origin.by === 'import'">
                    <v-icon size="small" class="mr-1">mdi-file-upload-outline</v-icon>
                    Came in with {{ importSourceFile }}.
                </template>
                <template v-else>
                    <v-icon size="small" class="mr-1">mdi-pencil</v-icon>
                    Added by you.
                </template>
            </div>

            <v-row dense>
                <v-col cols="12" md="6">
                    <v-text-field
                        v-model="local.text"
                        label="Name"
                        density="compact"
                        variant="outlined"
                        hide-details
                        @blur="save()"
                    ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                    <v-select
                        v-model="local.language"
                        label="Language"
                        :items="languageOptions"
                        item-title="title"
                        item-value="value"
                        density="compact"
                        variant="outlined"
                        hide-details
                        @update:model-value="save()"
                    ></v-select>
                </v-col>
            </v-row>

            <v-text-field
                v-model="local.meaning"
                label="Meaning"
                placeholder="What the name means, if anything"
                density="compact"
                variant="outlined"
                hide-details
                class="mt-2"
                @blur="save()"
            ></v-text-field>

            <v-text-field
                v-if="showTrueName"
                v-model="local.true_name"
                label="True name"
                density="compact"
                variant="outlined"
                hide-details
                class="mt-2"
                @blur="save()"
            ></v-text-field>

            <div v-if="otherCultures.length" class="mt-3">
                <div class="text-caption text-muted text-uppercase mb-1">What other cultures call it</div>
                <div v-for="culture in otherCultures" :key="culture.id" class="d-flex align-center ga-2 mb-1">
                    <span class="text-muted text-caption rendering-label">{{ culture.name }}</span>
                    <v-text-field
                        v-model="local.renderings[culture.id]"
                        density="compact"
                        variant="outlined"
                        hide-details
                        @blur="save()"
                    ></v-text-field>
                </div>
            </div>

            <div class="text-caption text-muted mt-3">
                <v-icon size="small" class="mr-1">mdi-book-open-outline</v-icon>
                First used in <strong class="text-body-2">{{ local.first_used || 'not yet used' }}</strong>
            </div>

            <div class="d-flex align-center ga-2 flex-wrap mt-3 pt-3 actions-row">
                <v-btn v-if="local.status === 'unreviewed'" size="small" color="primary" variant="flat" prepend-icon="mdi-check" @click="looksRight()">
                    Looks right
                </v-btn>
                <v-btn v-else size="small" variant="tonal" prepend-icon="mdi-undo" @click="markNotReviewed()">
                    Mark not reviewed
                </v-btn>

                <v-menu v-if="local.origin.by === 'ai'" v-model="pickMenu" :close-on-content-click="false">
                    <template v-slot:activator="{ props }">
                        <v-btn v-bind="props" size="small" variant="tonal" prepend-icon="mdi-dice-multiple-outline">
                            Pick another
                        </v-btn>
                    </template>
                    <v-card min-width="260" class="pa-2">
                        <div class="d-flex flex-wrap ga-1 mb-2">
                            <v-chip
                                v-for="candidate in candidatePool"
                                :key="candidate"
                                size="small"
                                :color="candidate === local.text ? 'primary' : undefined"
                                :variant="candidate === local.text ? 'flat' : 'tonal'"
                                @click="pickCandidate(candidate)"
                            >
                                {{ candidate }}
                            </v-chip>
                        </div>
                        <v-btn
                            size="small"
                            variant="text"
                            prepend-icon="mdi-dice-multiple-outline"
                            :loading="!!pendingRollRequestId"
                            :disabled="!local.language"
                            @click="rollNew()"
                        >
                            Roll new
                        </v-btn>
                        <div v-if="!local.language" class="text-caption text-muted mt-1">
                            Assign a language before rolling new candidates.
                        </div>
                    </v-card>
                </v-menu>

                <v-spacer></v-spacer>

                <v-menu v-model="removeMenu" :close-on-content-click="false">
                    <template v-slot:activator="{ props }">
                        <v-btn v-bind="props" size="small" variant="text" color="delete" prepend-icon="mdi-delete-outline">
                            Remove
                        </v-btn>
                    </template>
                    <v-card min-width="220" class="pa-3">
                        <div class="text-body-2 mb-2">Remove this entry from the glossary?</div>
                        <div class="d-flex ga-2 justify-end">
                            <v-btn size="small" variant="text" @click="removeMenu = false">Cancel</v-btn>
                            <v-btn size="small" color="delete" variant="flat" @click="confirmRemove()">Confirm</v-btn>
                        </div>
                    </v-card>
                </v-menu>
            </div>
        </v-card-text>
    </v-card>
</template>

<script>
import { v4 as uuidv4 } from 'uuid';
import { kindMeta } from './levelLabels';
import { dirtyLocalClone } from './dirtyLocalClone';

function cloneEntry(entry, vm) {
    const local = JSON.parse(JSON.stringify(entry));
    local.renderings = local.renderings || {};
    for (const culture of vm.cultures) {
        if (culture.id !== local.language && !(culture.id in local.renderings)) {
            local.renderings[culture.id] = '';
        }
    }
    return local;
}

export default {
    name: 'GlossaryDetail',
    mixins: [
        dirtyLocalClone({
            watchPath: 'entry',
            identity: vm => vm.entry && vm.entry.id,
            clone: cloneEntry,
        }),
    ],
    inject: [
        'registerMessageHandler',
        'unregisterMessageHandler',
    ],
    props: {
        entry: {
            type: Object,
            required: true,
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        send: {
            type: Function,
            required: true,
        },
    },
    data() {
        return {
            rolledCandidates: [],
            pendingRollRequestId: null,
            pickMenu: false,
            removeMenu: false,
        }
    },
    computed: {
        kindMeta() {
            return kindMeta(this.local.kind);
        },
        otherCultures() {
            return this.cultures.filter(c => c.id !== this.local.language);
        },
        selectedCultureObj() {
            return this.cultures.find(c => c.id === this.local.language) || null;
        },
        showTrueName() {
            return !!(this.selectedCultureObj && this.selectedCultureObj.language && !this.selectedCultureObj.language.writable);
        },
        languageOptions() {
            const options = this.cultures.map(c => ({ title: c.name, value: c.id }));
            options.push({ title: 'No language yet', value: null });
            return options;
        },
        generatorName() {
            const generators = (this.selectedCultureObj && this.selectedCultureObj.language.generators) || [];
            const gen = generators.find(g => g.id === this.local.origin.generator_id);
            return gen ? gen.name : (this.local.origin.generator_id || 'a generator');
        },
        importSourceFile() {
            return (this.selectedCultureObj && this.selectedCultureObj.source_file) || 'the import file';
        },
        candidatePool() {
            const seen = new Set();
            const pool = [];
            for (const name of [...(this.local.origin.candidates || []), ...this.rolledCandidates]) {
                if (!seen.has(name)) {
                    seen.add(name);
                    pool.push(name);
                }
            }
            return pool;
        },
    },
    methods: {
        onLocalReset() {
            this.rolledCandidates = [];
            this.pendingRollRequestId = null;
            this.pickMenu = false;
            this.removeMenu = false;
        },
        save() {
            this.send('save_glossary_entry', { entry: this.local });
            this.clearLocalDirty();
        },
        review(status) {
            this.send('review_glossary_entry', { entry_id: this.local.id, status });
        },
        looksRight() {
            this.save();
            this.review('reviewed');
        },
        markNotReviewed() {
            this.review('unreviewed');
        },
        pickCandidate(candidate) {
            this.local.text = candidate;
            this.save();
            this.pickMenu = false;
        },
        rollNew() {
            if (!this.local.language) {
                // The backend needs a culture_id to roll against; an entry
                // with no language yet can't have "Pick another" rolling.
                return;
            }
            const requestId = uuidv4();
            this.pendingRollRequestId = requestId;
            this.send('roll', {
                culture_id: this.local.language,
                generator_id: this.local.origin.generator_id,
                count: 20,
                request_id: requestId,
            });
        },
        confirmRemove() {
            this.removeMenu = false;
            this.send('delete_glossary_entry', { entry_id: this.local.id });
        },
        handleMessage(message) {
            if (message.type !== 'cultures') {
                return;
            }
            if (message.action === 'operation_done') {
                // Our roll failed: stop the "Roll new" spinner.
                if (message.error && this.pendingRollRequestId && message.error.request_id === this.pendingRollRequestId) {
                    this.pendingRollRequestId = null;
                }
                return;
            }
            if (message.action !== 'rolled') {
                return;
            }
            if (!this.pendingRollRequestId || message.data.request_id !== this.pendingRollRequestId) {
                return;
            }
            this.pendingRollRequestId = null;
            this.rolledCandidates = message.data.names || [];
        },
    },
    mounted() {
        this.registerMessageHandler(this.handleMessage);
    },
    unmounted() {
        this.unregisterMessageHandler(this.handleMessage);
    },
}
</script>

<style scoped>
.unrev-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgb(var(--v-theme-unsaved));
}

.origin-box {
    background: rgba(255, 255, 255, 0.04);
    border-radius: 4px;
}

.actions-row {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.rendering-label {
    min-width: 90px;
    flex: none;
}
</style>
