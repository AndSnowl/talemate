<template>
    <div class="generator-list">
        <v-row>
            <v-col v-for="gen in local.generators" :key="gen.id" cols="12" md="6" lg="4">
                <v-card variant="tonal" class="pa-4 h-100">
                    <div class="d-flex align-center ga-2 mb-2">
                        <v-icon size="small" color="muted">{{ useIcon(gen.use) }}</v-icon>
                        <span class="text-body-1 flex-grow-1">{{ gen.name }}</span>
                        <v-btn size="small" variant="tonal" prepend-icon="mdi-dice-multiple-outline" :loading="!!pendingRequests[gen.id]" @click="roll(gen)">
                            Roll
                        </v-btn>
                    </div>

                    <div class="d-flex flex-wrap ga-1 mb-3 generator-out">
                        <v-chip v-for="(name, i) in (rolls[gen.id] || [])" :key="i" size="small" class="font-italic text-highlight7">
                            {{ name }}
                        </v-chip>
                        <span v-if="!(rolls[gen.id] || []).length" class="text-muted text-caption">
                            Click Roll to preview names.
                        </span>
                    </div>

                    <div class="text-caption text-muted mb-1">Patterns</div>
                    <div v-for="(pattern, i) in gen.patterns" :key="'p' + i" class="d-flex align-center ga-1 mb-1">
                        <v-text-field
                            v-model="gen.patterns[i]"
                            density="compact"
                            variant="outlined"
                            hide-details
                            class="font-mono"
                            @blur="save()"
                        ></v-text-field>
                        <v-btn icon size="small" variant="text" @click="removePattern(gen, i)">
                            <v-icon size="small" color="delete">mdi-close</v-icon>
                        </v-btn>
                    </div>
                    <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addPattern(gen)">
                        Add pattern
                    </v-btn>

                    <div class="text-caption text-muted mb-1 mt-3">Reject rules</div>
                    <div v-for="(rule, i) in gen.reject" :key="'r' + i" class="d-flex align-center ga-1 mb-1">
                        <v-text-field
                            v-model="gen.reject[i]"
                            density="compact"
                            variant="outlined"
                            hide-details
                            class="font-mono"
                            @blur="save()"
                        ></v-text-field>
                        <v-btn icon size="small" variant="text" @click="removeReject(gen, i)">
                            <v-icon size="small" color="delete">mdi-close</v-icon>
                        </v-btn>
                    </div>
                    <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addReject(gen)">
                        Add reject rule
                    </v-btn>
                </v-card>
            </v-col>

            <v-col v-if="local.generators.length === 0" cols="12">
                <v-card variant="tonal" class="pa-4 text-muted text-center">
                    No generators yet.
                </v-card>
            </v-col>
        </v-row>

        <v-card variant="text" class="empty-hint pa-3 mt-2 d-flex ga-2">
            <v-icon size="small" color="muted">mdi-information-outline</v-icon>
            <div class="text-caption text-muted">
                When the story needs a new name, the AI picks the generator that fits, rolls a handful of
                candidates and chooses the one it likes best. That name goes into the glossary automatically,
                marked not reviewed.
            </div>
        </v-card>
    </div>
</template>

<script>
import { v4 as uuidv4 } from 'uuid';
import { dirtyLocalClone } from './dirtyLocalClone';

export default {
    name: 'GeneratorList',
    mixins: [
        dirtyLocalClone({
            watchPath: 'culture',
            // Only `language.generators`: saves patch just that field.
            source: vm => ({ generators: vm.culture.language.generators }),
            identity: vm => vm.culture && vm.culture.id,
        }),
    ],
    inject: [
        'registerMessageHandler',
        'unregisterMessageHandler',
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
            rolls: {},
            // generator id -> the request_id of its outstanding roll, if any
            pendingRequests: {},
        }
    },
    methods: {
        onLocalReset() {
            this.rolls = {};
            this.pendingRequests = {};
        },
        save() {
            this.send('patch_culture', { culture_id: this.culture.id, language: { generators: this.local.generators } });
            this.clearLocalDirty();
        },
        useIcon(use) {
            return {
                people: 'mdi-account',
                places: 'mdi-map-marker',
                things: 'mdi-shape',
            }[use] || 'mdi-dice-multiple-outline';
        },
        addPattern(gen) {
            gen.patterns.push('');
        },
        removePattern(gen, i) {
            gen.patterns.splice(i, 1);
            this.save();
        },
        addReject(gen) {
            gen.reject.push('');
        },
        removeReject(gen, i) {
            gen.reject.splice(i, 1);
            this.save();
        },
        roll(gen) {
            const requestId = uuidv4();
            this.pendingRequests[gen.id] = requestId;
            this.send('roll', {
                culture_id: this.culture.id,
                generator_id: gen.id,
                count: 20,
                request_id: requestId,
            });
        },
        handleMessage(message) {
            if (message.type !== 'cultures' || message.action !== 'rolled') {
                return;
            }
            const generatorId = message.data.generator_id;
            const pendingRequestId = this.pendingRequests[generatorId];
            if (!pendingRequestId || message.data.request_id !== pendingRequestId) {
                return;
            }
            this.pendingRequests[generatorId] = null;
            this.rolls[generatorId] = (message.data.names || []).slice(0, 5);
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
.font-mono {
    font-family: "Roboto Mono", ui-monospace, Menlo, monospace;
}

.generator-out {
    min-height: 38px;
}

.empty-hint {
    border: 1px dashed rgba(255, 255, 255, 0.2);
    border-radius: 6px;
}
</style>
