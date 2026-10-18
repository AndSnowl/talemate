<template>
    <div>
        <v-card class="mb-2">
            <v-card-text class="d-flex align-center flex-wrap ga-2">
                <span class="culture-swatch mr-1" :style="{ backgroundColor: swatchColor }"></span>
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
                <GlossaryView
                    :entries="glossary"
                    :cultures="cultures"
                    :culture-id="culture.id"
                    :selected-id="glossarySelectedId"
                    :send="send"
                    @select="glossarySelectedId = $event"
                ></GlossaryView>
            </v-window-item>

            <v-window-item v-if="hasTab('dictionary')" value="dictionary">
                <DictionaryTable
                    :culture="culture"
                    :send="send"
                ></DictionaryTable>
            </v-window-item>

            <v-window-item v-if="hasTab('phrases')" value="phrases">
                <PhraseList
                    :culture="culture"
                    :send="send"
                    :focus-id="phraseFocusId"
                ></PhraseList>
            </v-window-item>

            <v-window-item v-if="hasTab('generators')" value="generators">
                <GeneratorList
                    :culture="culture"
                    :send="send"
                ></GeneratorList>
            </v-window-item>
        </v-window>
    </div>
</template>

<script>
import CultureOverview from './CultureOverview.vue';
import LanguageOverview from './LanguageOverview.vue';
import GlossaryView from './GlossaryView.vue';
import DictionaryTable from './DictionaryTable.vue';
import PhraseList from './PhraseList.vue';
import GeneratorList from './GeneratorList.vue';
import { levelLabel as formatLevel } from './levelLabels';
import { dataColor } from '@/theme/dataColors';

export default {
    name: 'CulturePage',
    components: {
        CultureOverview,
        LanguageOverview,
        GlossaryView,
        DictionaryTable,
        PhraseList,
        GeneratorList,
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
        focus: {
            type: Object,
            default: null,
        },
    },
    emits: [
        'open-places',
        'focus-applied',
    ],
    data() {
        return {
            subTab: 'culture',
            glossarySelectedId: null,
            // Copied from `focus.phraseId` below rather than read live off
            // `focus` in the template: the parent clears `focus` right
            // after `focus-applied` (so a later, unrelated remount doesn't
            // replay it), which would otherwise erase `PhraseList`'s own
            // highlight/scroll the moment it appeared.
            phraseFocusId: null,
        }
    },
    computed: {
        levelLabel() {
            return formatLevel(this.culture.language.level);
        },
        // The culture's own stored colour is data: remap it onto the
        // theme's accent palette at render time (never rewrite the stored
        // value) — see theme/dataColors.js.
        swatchColor() {
            return dataColor(this.culture.color) || this.culture.color;
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
        focus: {
            immediate: true,
            handler(focus) {
                if (!focus) return;
                if (focus.subTab && this.hasTab(focus.subTab)) {
                    this.subTab = focus.subTab;
                }
                if (focus.glossaryId !== undefined) {
                    this.glossarySelectedId = focus.glossaryId;
                }
                if (focus.phraseId !== undefined) {
                    this.phraseFocusId = focus.phraseId;
                }
                // Tell the parent this jump has been applied, so it clears
                // its own `cultureFocus` — otherwise this same (stale)
                // `focus` would be re-applied to whichever culture gets
                // opened next, on any later remount of this component
                // (leaving to Places/People/Unassigned and back).
                this.$emit('focus-applied');
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
