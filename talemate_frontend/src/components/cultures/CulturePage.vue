<template>
    <div>
        <v-card class="mb-2">
            <v-card-text class="d-flex align-center flex-wrap ga-2">
                <span class="culture-swatch mr-1" :style="{ backgroundColor: culture.color }"></span>
                <span class="text-h6 font-weight-regular mr-2">{{ culture.name }}</span>
                <v-chip size="x-small" label color="primary" variant="tonal" prepend-icon="mdi-translate">
                    Speaks {{ culture.language.name }} · {{ levelLabel }}
                </v-chip>
                <v-chip size="x-small" label color="muted" variant="tonal" prepend-icon="mdi-file-outline">
                    {{ culture.source_file || 'no source file' }} · {{ culture.imported_at || 'n/a' }}
                </v-chip>
                <v-spacer></v-spacer>
                <v-btn size="small" variant="tonal" prepend-icon="mdi-sync" class="mr-2" @click="openImport()">
                    Re-import
                </v-btn>
                <v-btn size="small" variant="tonal" prepend-icon="mdi-download" @click="exportCulture()">
                    Export
                </v-btn>
            </v-card-text>
            <v-tabs v-model="subTab" color="primary" density="compact">
                <v-tab v-for="t in subTabs" :key="t.name" :value="t.name">
                    {{ t.title }}
                    <v-badge
                        v-if="t.name === 'glossary' && glossaryCount > 0"
                        inline
                        color="unsaved"
                        :content="String(glossaryCount)"
                    ></v-badge>
                </v-tab>
            </v-tabs>
        </v-card>

        <v-window v-model="subTab">
            <v-window-item value="culture">
                <CultureOverview
                    :culture="culture"
                    :cultures="cultures"
                    :places="places"
                    :send="send"
                    @open-language="subTab = 'language'"
                    @open-places="$emit('open-places')"
                />
            </v-window-item>

            <v-window-item value="language">
                <LanguageOverview
                    :culture="culture"
                    :cultures="cultures"
                    :glossary="glossary"
                    :send="send"
                />
            </v-window-item>

            <v-window-item v-if="hasTab('glossary')" value="glossary">
                <v-card variant="tonal" class="pa-4">
                    <v-card-text class="text-muted">
                        Glossary review is coming in a later update.
                    </v-card-text>
                </v-card>
            </v-window-item>

            <v-window-item v-if="hasTab('dictionary')" value="dictionary">
                <v-card variant="tonal" class="pa-4">
                    <v-card-text class="text-muted">
                        The dictionary is coming in a later update.
                    </v-card-text>
                </v-card>
            </v-window-item>

            <v-window-item v-if="hasTab('phrases')" value="phrases">
                <v-card variant="tonal" class="pa-4">
                    <v-card-text class="text-muted">
                        Phrases are coming in a later update.
                    </v-card-text>
                </v-card>
            </v-window-item>

            <v-window-item v-if="hasTab('generators')" value="generators">
                <v-card variant="tonal" class="pa-4">
                    <v-card-text class="text-muted">
                        Name generators are coming in a later update.
                    </v-card-text>
                </v-card>
            </v-window-item>
        </v-window>
    </div>
</template>

<script>
import CultureOverview from './CultureOverview.vue';
import LanguageOverview from './LanguageOverview.vue';
import { levelLabel as formatLevel } from './levelLabels';

export default {
    name: 'CulturePage',
    components: {
        CultureOverview,
        LanguageOverview,
    },
    props: {
        culture: {
            type: Object,
            required: true,
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        places: {
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
        openImport: {
            type: Function,
            required: true,
        },
    },
    emits: [
        'open-places',
    ],
    data() {
        return {
            subTab: 'culture',
        }
    },
    computed: {
        levelLabel() {
            return formatLevel(this.culture.language.level);
        },
        subTabs() {
            const tabs = [
                { name: 'culture', title: 'Culture' },
                { name: 'language', title: 'Language' },
                { name: 'glossary', title: 'Glossary' },
            ];

            const level = this.culture.language.level;

            if (level === 'full') {
                tabs.push({ name: 'dictionary', title: 'Dictionary' });
                tabs.push({ name: 'phrases', title: 'Phrases' });
            }

            if (level !== 'description') {
                tabs.push({ name: 'generators', title: 'Generators' });
            }

            return tabs;
        },
        glossaryCount() {
            return this.glossary.filter(e => e.language === this.culture.id && e.status === 'unreviewed').length;
        },
    },
    watch: {
        culture: {
            immediate: true,
            handler() {
                if (!this.subTabs.some(t => t.name === this.subTab)) {
                    this.subTab = 'culture';
                }
            },
        },
    },
    methods: {
        hasTab(name) {
            return this.subTabs.some(t => t.name === name);
        },
        exportCulture() {
            this.send('export', { culture_id: this.culture.id });
        },
    },
}
</script>

<style scoped>
.culture-swatch {
    display: inline-block;
    width: 14px;
    height: 14px;
    border-radius: 4px;
    flex: none;
}
</style>
