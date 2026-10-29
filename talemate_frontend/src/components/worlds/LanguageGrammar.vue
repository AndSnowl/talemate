<template>
    <div class="language-grammar" data-testid="language-grammar-tab">
        <div v-if="!sections.length" class="text-body-2 text-muted mt-2">
            No grammar yet. Making the language (or filling it in) writes it.
        </div>
        <div v-else class="grammar-cols">
            <!-- the topics, as a contents list: the standard ones, then the unusual -->
            <nav class="topics" data-testid="grammar-topics">
                <div class="text-overline text-muted">Topics</div>
                <a
                    v-for="entry in standard"
                    :key="entry.index"
                    href="#"
                    class="topic"
                    :class="{ on: entry.index === current }"
                    data-testid="grammar-topic"
                    @click.prevent="show(entry.index)"
                >{{ entry.section.title }}</a>
                <template v-if="unusual.length">
                    <div class="text-overline text-muted mt-3">Unusual</div>
                    <a
                        v-for="entry in unusual"
                        :key="entry.index"
                        href="#"
                        class="topic other"
                        :class="{ on: entry.index === current }"
                        data-testid="grammar-topic"
                        @click.prevent="show(entry.index)"
                    >{{ entry.section.title }}</a>
                </template>
            </nav>

            <div class="cards">
                <section
                    v-for="entry in ordered"
                    :key="entry.index"
                    :ref="(el) => (cardEls[entry.index] = el)"
                    class="card"
                    data-testid="grammar-section"
                >
                    <div class="d-flex align-center ga-2">
                        <span class="text-subtitle-1">{{ entry.section.title }}</span>
                        <span v-if="!isPlain(entry.section)" class="topic-chip">{{ topicLabel(entry.section.topic) }}</span>
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
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// the standard topics and their plain titles, in the brief's order
// (talemate.languages.models.GRAMMAR_TOPICS)
const TOPICS = [
    ['sounds', 'Sounds and stress'],
    ['word_order', 'Word order'],
    ['nouns', 'Nouns'],
    ['pronouns', 'Pronouns'],
    ['verbs', 'Verbs'],
    ['adjectives', 'Adjectives'],
    ['questions', 'Questions and "not"'],
    ['numbers', 'Numbers'],
    ['word_building', 'How words are built'],
    ['names', 'How names are built'],
    ['politeness', 'Politeness and registers'],
];
const ORDER = Object.fromEntries(TOPICS.map(([id], i) => [id, i]));
const TITLES = Object.fromEntries(TOPICS);

// A language's grammar (languages 3b-2): a card per section, with its
// text, tables and examples word over meaning, and the topics as a
// contents list beside them. An older language's grammar text is one card.
export default {
    name: 'LanguageGrammar',
    props: {
        thing: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { current: null, editing: null, draft: '', cardEls: {} };
    },
    computed: {
        rules() {
            return this.thing.fields?.rules || {};
        },
        sections() {
            const grammar = this.rules.grammar;
            if (!grammar) return [];
            if (typeof grammar === 'string') return [{ title: 'Grammar', topic: 'other', text: grammar }];
            return grammar;
        },
        // the standard topics first, in their order, then the rest as written
        ordered() {
            return this.sections
                .map((section, index) => ({ section, index }))
                .sort((a, b) => (ORDER[a.section.topic] ?? 99) - (ORDER[b.section.topic] ?? 99) || a.index - b.index);
        },
        standard() {
            return this.ordered.filter((entry) => entry.section.topic in ORDER || this.isPlain(entry.section));
        },
        unusual() {
            return this.ordered.filter((entry) => !(entry.section.topic in ORDER) && !this.isPlain(entry.section));
        },
    },
    methods: {
        // an older language's grammar text: one plain "Grammar" section,
        // not something unusual
        isPlain(section) {
            return section.topic === 'other' && section.title === 'Grammar';
        },
        topicLabel(topic) {
            return TITLES[topic] ? topic.replace('_', ' ') : 'unusual';
        },
        width(table) {
            const rows = table.rows || [];
            return Math.max((table.columns || []).length, ...rows.map((row) => row.length), 0);
        },
        show(index) {
            this.current = index;
            this.cardEls[index]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
.grammar-cols {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 28px;
    max-width: 1240px;
    margin-top: 8px;
}
.topics {
    position: sticky;
    top: 8px;
    align-self: start;
}
.topic {
    display: block;
    padding: 5px 10px;
    color: rgb(var(--v-theme-on-surface));
    text-decoration: none;
    border-left: 2px solid rgba(var(--v-theme-on-surface), 0.15);
}
.topic.on {
    color: rgb(var(--v-theme-accent));
    border-left-color: rgb(var(--v-theme-accent));
}
.topic.other {
    color: rgb(var(--v-theme-link, var(--v-theme-primary)));
}
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
