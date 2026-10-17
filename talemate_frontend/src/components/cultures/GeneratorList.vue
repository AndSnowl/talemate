<template>
    <div class="generator-list">
        <v-row>
            <v-col v-for="gen in local.generators" :key="gen.id" cols="12" md="6" lg="4">
                <v-card variant="tonal" class="pa-4 h-100">
                    <div class="d-flex align-center ga-2 mb-2">
                        <v-icon size="small" color="muted">{{ useIcon(gen.use) }}</v-icon>
                        <span class="text-body-1 flex-grow-1">{{ gen.name }}</span>
                        <v-btn size="small" variant="tonal" prepend-icon="mdi-dice-multiple-outline" :loading="pending[gen.id]" @click="roll(gen)">
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
export default {
    name: 'GeneratorList',
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
            local: this.cloneCulture(this.culture),
            rolls: {},
            pending: {},
        }
    },
    watch: {
        culture(newCulture) {
            this.local = this.cloneCulture(newCulture);
            this.rolls = {};
            this.pending = {};
        },
    },
    methods: {
        cloneCulture(culture) {
            return JSON.parse(JSON.stringify(culture));
        },
        save() {
            this.send('save_culture', { culture: this.local });
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
            this.pending[gen.id] = true;
            this.send('roll', { culture_id: this.culture.id, generator_id: gen.id, count: 20 });
        },
        handleMessage(message) {
            if (message.type !== 'cultures' || message.action !== 'rolled') {
                return;
            }
            const generatorId = message.data.generator_id;
            if (!this.pending[generatorId]) {
                return;
            }
            this.pending[generatorId] = false;
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
