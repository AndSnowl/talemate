<template>
    <!-- the Names chapter has two columns: it takes the page's full width -->
    <div class="language-book" :class="{ wide: chapter === 'names' }" data-testid="language-book">
        <!-- the chapters: the language, its names, then its grammar, one at a time -->
        <nav class="chapters" data-testid="language-chapters">
            <div class="text-overline text-muted">The language</div>
            <a v-for="ch in OWN" :key="ch.id" href="#" class="chapter" :class="{ on: chapter === ch.id }" data-testid="language-chapter" @click.prevent="chapter = ch.id">{{ ch.title }}</a>

            <div class="text-overline text-muted mt-3">Names</div>
            <a href="#" class="chapter" :class="{ on: chapter === 'names' }" data-testid="language-chapter" @click.prevent="chapter = 'names'">Name rules</a>

            <template v-if="standard.length || unusual.length">
                <div class="text-overline text-muted mt-3">Grammar</div>
                <a v-for="entry in standard" :key="entry.index" href="#" class="chapter" :class="{ on: chapter === entry.index }" data-testid="language-chapter" @click.prevent="chapter = entry.index">{{ entry.section.title }}</a>
                <template v-if="unusual.length">
                    <div class="text-caption text-muted mt-2 ml-2">Unusual</div>
                    <a v-for="entry in unusual" :key="entry.index" href="#" class="chapter other" :class="{ on: chapter === entry.index }" data-testid="language-chapter" @click.prevent="chapter = entry.index">{{ entry.section.title }}</a>
                </template>
            </template>
        </nav>

        <div class="chapter-body">
            <template v-if="chapter === 'overview'">
                <LanguageSections :thing="thing" tab="language" chapter="overview" />
            </template>
            <template v-else-if="chapter === 'sounds'">
                <LanguageSections :thing="thing" tab="language" chapter="sounds" />
                <LanguageGrammar class="mt-4" :thing="thing" :only="soundSections" />
            </template>
            <!-- the name rules beside how names are built -->
            <div v-else-if="chapter === 'names'" class="names-cols">
                <LanguageSections :thing="thing" tab="language" chapter="names" />
                <div>
                    <LanguageGrammar v-if="nameSections.length" class="mt-4" :thing="thing" :only="nameSections" />
                    <!-- the rules the name engine applies (languages 4b-1) -->
                    <NameGrammarCard class="mt-4" :thing="thing" @fill="$emit('fill-names')" />
                </div>
            </div>
            <LanguageGrammar v-else :thing="thing" :only="[chapter]" class="mt-2" />
        </div>
    </div>
</template>

<script>
import LanguageGrammar from './LanguageGrammar.vue';
import LanguageSections from './LanguageSections.vue';
import NameGrammarCard from './NameGrammarCard.vue';
import { TOPIC_ORDER, grammarSections, isPlainGrammar } from './languageTopics.js';

// the language's own chapters, before its names and grammar
const OWN = [
    { id: 'overview', title: 'Overview' },
    { id: 'sounds', title: 'Sounds' },
];
// grammar topics that live in those chapters, not as chapters of their own
const FOLDED = { sounds: 'sounds', names: 'names' };

// A language's Language tab (languages 3b-2, the owner's merge of the
// Language and Grammar tabs;
// docs/superpowers/mockups/2026-10-29-languages-3b2-language-chapters.html):
// a chapter list beside one chapter at a time. Overview (how it sounds,
// related languages), Sounds (the sound groups with the sounds-and-stress
// section), Names (the name rules with how names are built), then each
// grammar topic, the unusual ones last.
export default {
    name: 'LanguageBook',
    components: { LanguageGrammar, LanguageSections, NameGrammarCard },
    emits: ['fill-names'],
    props: {
        thing: { type: Object, required: true },
    },
    setup() {
        return { OWN };
    },
    data() {
        return { chapter: 'overview' };
    },
    computed: {
        sections() {
            return grammarSections(this.thing.fields?.rules);
        },
        grammarEntries() {
            return this.sections
                .map((section, index) => ({ section, index }))
                .filter((entry) => !(entry.section.topic in FOLDED))
                .sort((a, b) => (TOPIC_ORDER[a.section.topic] ?? 99) - (TOPIC_ORDER[b.section.topic] ?? 99) || a.index - b.index);
        },
        standard() {
            return this.grammarEntries.filter((entry) => entry.section.topic in TOPIC_ORDER || isPlainGrammar(entry.section));
        },
        unusual() {
            return this.grammarEntries.filter((entry) => !(entry.section.topic in TOPIC_ORDER) && !isPlainGrammar(entry.section));
        },
        soundSections() {
            return this.sections.map((section, index) => (section.topic === 'sounds' ? index : -1)).filter((index) => index >= 0);
        },
        nameSections() {
            return this.sections.map((section, index) => (section.topic === 'names' ? index : -1)).filter((index) => index >= 0);
        },
    },
    watch: {
        // another language opens on its Overview
        'thing.id'() {
            this.chapter = 'overview';
        },
        // a grammar chapter that's gone (edited away) falls back to Overview
        sections(sections) {
            if (typeof this.chapter === 'number' && !sections[this.chapter]) this.chapter = 'overview';
        },
    },
};
</script>

<style scoped>
.language-book {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 28px;
    max-width: 1240px;
}
.language-book.wide {
    max-width: none;
}
.chapters {
    position: sticky;
    top: 8px;
    align-self: start;
}
.chapter {
    display: block;
    padding: 5px 10px;
    color: rgb(var(--v-theme-on-surface));
    text-decoration: none;
    border-left: 2px solid rgba(var(--v-theme-on-surface), 0.15);
}
.chapter.on {
    color: rgb(var(--v-theme-accent));
    border-left-color: rgb(var(--v-theme-accent));
}
.chapter.other {
    color: rgb(var(--v-theme-link, var(--v-theme-primary)));
}
.chapter-body {
    min-width: 0;
}
.names-cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    align-items: start;
}
</style>
