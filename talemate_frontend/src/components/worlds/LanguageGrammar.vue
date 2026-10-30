<template>
    <div class="language-grammar">
                <section
                    v-for="entry in shownCards"
                    :key="entry.index"
                    class="card"
                    data-testid="grammar-section"
                >
                    <div class="d-flex align-center ga-2">
                        <span class="text-subtitle-1">{{ entry.section.title }}</span>
                        <span v-if="!isPlain(entry.section)" class="topic-chip">{{ topicLabel(entry.section.topic) }}</span>
                        <!-- a change aimed at this section -->
                        <v-btn
                            size="x-small"
                            variant="text"
                            color="accent"
                            data-testid="grammar-change"
                            @click="worlds.openLanguageChange({ targetId: thing.id, prefill: `Change the ${entry.section.title} section: ` })"
                        >Change…</v-btn>
                        <v-btn
                            v-if="editing !== entry.index"
                            icon="mdi-pencil"
                            size="x-small"
                            variant="text"
                            density="comfortable"
                            color="accent"
                            :aria-label="'Edit ' + entry.section.title"
                            data-testid="grammar-edit-text"
                            @click="startEdit(entry.index)"
                        ></v-btn>
                    </div>

                    <template v-if="editing === entry.index">
                        <v-textarea v-model="draft" rows="3" auto-grow variant="outlined" density="compact" hide-details autofocus class="mt-2"></v-textarea>
                        <div class="d-flex ga-2 mt-1">
                            <v-btn size="small" color="accent" variant="flat" @click="saveText(entry.index)">Save</v-btn>
                            <v-btn size="small" variant="text" @click="editing = null">Cancel</v-btn>
                        </div>
                    </template>
                    <p v-else-if="entry.section.text" class="text-body-2 section-text">{{ entry.section.text }}</p>

                    <table v-for="(table, t) in entry.section.tables || []" :key="'t' + t" class="gtable" data-testid="grammar-table">
                        <caption v-if="table.caption">{{ table.caption }}</caption>
                        <thead v-if="width(table)">
                            <tr><th v-for="c in width(table)" :key="c">{{ (table.columns || [])[c - 1] || '' }}</th></tr>
                        </thead>
                        <tbody>
                            <!-- a ragged row is padded to the table's width -->
                            <tr v-for="(row, r) in table.rows || []" :key="r">
                                <td v-for="c in width(table)" :key="c" :class="{ form: c > 1 }">{{ row[c - 1] ?? '' }}</td>
                            </tr>
                        </tbody>
                    </table>

                    <div v-for="(example, e) in entry.section.examples || []" :key="'e' + e" class="example" data-testid="grammar-example">
                        <div class="gloss">
                            <span v-for="(pair, w) in example.breakdown || []" :key="w" class="gw">
                                <span class="o">{{ pair[0] }}</span>
                                <span class="m">{{ pair[1] }}</span>
                            </span>
                            <span v-if="!(example.breakdown || []).length" class="o">{{ example.original }}</span>
                        </div>
                        <div v-if="example.translation" class="text-body-2">{{ example.translation }}</div>
                    </div>
                </section>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { TOPIC_TITLES, grammarSections, isPlainGrammar } from './languageTopics.js';

// A language's grammar sections as cards (languages 3b-2): text, tables,
// and examples word over meaning, for the sections the Language tab's
// chapter asks for (LanguageBook). An older language's grammar text is one
// plain section. An older language's grammar text is one card.
export default {
    name: 'LanguageGrammar',
    props: {
        thing: { type: Object, required: true },
        // which sections to show, by their place in the grammar list
        only: { type: Array, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { editing: null, draft: '' };
    },
    computed: {
        rules() {
            return this.thing.fields?.rules || {};
        },
        sections() {
            return grammarSections(this.rules);
        },
        shownCards() {
            return this.only.map((index) => ({ section: this.sections[index], index })).filter((entry) => entry.section);
        },
    },
    methods: {
        isPlain(section) {
            return isPlainGrammar(section);
        },
        topicLabel(topic) {
            return TOPIC_TITLES[topic] ? topic.replace('_', ' ') : 'unusual';
        },
        width(table) {
            const rows = table.rows || [];
            return Math.max((table.columns || []).length, ...rows.map((row) => row.length), 0);
        },
        startEdit(index) {
            this.editing = index;
            this.draft = this.sections[index].text || '';
        },
        // only this section's text changes; the rest of the rules stay
        saveText(index) {
            const grammar = this.sections.map((section, i) => (i === index ? { ...section, text: this.draft } : section));
            this.worlds.setField('rules', { ...JSON.parse(JSON.stringify(this.rules)), grammar });
            this.editing = null;
        },
    },
};
</script>

<style scoped>
.card {
    background: rgba(var(--v-theme-on-surface), 0.04);
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 14px;
}
.topic-chip {
    font-size: 0.7rem;
    padding: 0 6px;
    border-radius: 3px;
    background: rgba(var(--v-theme-on-surface), 0.1);
    color: rgba(var(--v-theme-on-surface), 0.7);
}
.section-text {
    margin: 6px 0 10px;
    white-space: pre-wrap;
}
.gtable {
    border-collapse: collapse;
    margin: 6px 0 12px;
    font-size: 0.875rem;
}
.gtable caption {
    text-align: left;
    font-size: 0.75rem;
    opacity: 0.7;
    padding-bottom: 4px;
}
.gtable th,
.gtable td {
    text-align: left;
    padding: 4px 14px 4px 0;
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}
.gtable th {
    font-weight: 400;
    font-size: 0.75rem;
    opacity: 0.7;
}
.gtable td.form,
.gw .o,
.example .o {
    color: rgb(var(--v-theme-foreign, var(--v-theme-secondary)));
    font-style: italic;
}
.example {
    margin: 8px 0 4px;
}
.gloss {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 16px;
}
.gw {
    display: inline-flex;
    flex-direction: column;
}
.gw .m {
    font-size: 0.75rem;
    opacity: 0.7;
}
</style>
