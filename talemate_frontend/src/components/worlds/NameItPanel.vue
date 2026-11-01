<template>
    <v-dialog :model-value="!!request" max-width="780" @update:model-value="!$event && worlds.closeNameIt()">
        <v-card v-if="request" class="name-it pa-4" data-testid="name-it">
            <div class="d-flex align-baseline flex-wrap ga-2">
                <span class="text-subtitle-1">Name it:</span>
                <span class="words">{{ request.words || 'a new name' }}</span>
                <span class="text-caption text-muted" data-testid="name-it-effect">{{ effect }}</span>
            </div>

            <div class="d-flex align-center flex-wrap ga-2 mt-3">
                <v-select
                    v-model="languageId"
                    :items="languageItems"
                    label="Language"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field"
                    data-testid="name-it-language"
                ></v-select>
                <v-select
                    v-model="ruleId"
                    :items="ruleItems"
                    label="Rule"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field"
                    :disabled="!languageId"
                    data-testid="name-it-rule"
                ></v-select>
                <v-select
                    v-model="pattern"
                    :items="patternItems"
                    label="Pattern"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field"
                    :disabled="!ruleId"
                    data-testid="name-it-pattern"
                ></v-select>
                <v-btn color="accent" variant="outlined" size="small" prepend-icon="mdi-dice-multiple" :disabled="!ruleId" data-testid="name-it-reroll" @click="roll">Reroll</v-btn>
            </div>
            <div v-if="!languageId" class="text-body-2 text-muted mt-2">Pick the language to name it in.</div>

            <div class="names mt-3">
                <v-chip
                    v-for="item in worlds.nameItBatch"
                    :key="item.name"
                    class="name"
                    variant="tonal"
                    :title="item.meaning || 'no meaning of its own'"
                    data-testid="name-it-name"
                    @click="pick(item.name, item.meaning)"
                >{{ item.name }}</v-chip>
            </div>
            <div v-if="meaningShown" class="text-caption text-muted mt-1">{{ meaningShown }}</div>

            <v-divider class="my-3"></v-divider>
            <div class="d-flex align-center flex-wrap ga-2">
                <span class="text-body-2"><b>From a meaning</b></span>
                <v-text-field
                    v-model="meaning"
                    placeholder="lakeland, grey water…"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field meaning"
                    data-testid="name-it-meaning"
                    @keydown.enter="find"
                ></v-text-field>
                <v-btn variant="text" color="accent" size="small" :loading="worlds.nameItMeaning.pending" :disabled="!languageId || !meaning.trim()" data-testid="name-it-find" @click="find">Find</v-btn>
            </div>
            <div v-if="worlds.nameItMeaning.error" class="text-caption text-error mt-1">{{ worlds.nameItMeaning.error }}</div>
            <div v-for="candidate in worlds.nameItMeaning.candidates" :key="candidate.name" class="d-flex align-center flex-wrap ga-2 mt-2" data-testid="name-it-candidate">
                <v-chip class="name" variant="tonal" @click="pickCandidate(candidate)">{{ candidate.name }}</v-chip>
                <span class="text-caption text-muted">
                    <template v-for="(part, i) in candidate.built_from" :key="i"><span v-if="i"> + </span><span class="foreign">{{ part.word }}</span> “{{ part.meaning }}”<span v-if="part.new"> (new word, saved if you pick it)</span></template>
                </span>
            </div>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// which rule a kind starts from, as the server's `generator_for` would
const BUCKETS = { character: 'people', being: 'people', place: 'places' };

// Name it… (languages 4a revised, mockup frames 2 and 3): names for the
// asked words from a rule, or one of its patterns, ten at a time with
// Reroll; or from a meaning. Picking puts the name where the request asked
// (`worlds.pickNameIt`) and adds the word to the language.
export default {
    name: 'NameItPanel',
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { languageId: null, ruleId: null, pattern: null, meaning: '', hovered: '' };
    },
    computed: {
        request() {
            return this.worlds.nameIt;
        },
        languageItems() {
            return (this.worlds.things.language || []).map((t) => ({ title: t.name, value: t.id }));
        },
        ruleItems() {
            return this.worlds.nameItRules.map((r) => ({ title: r.name, value: r.id }));
        },
        patternItems() {
            const rule = this.worlds.nameItRules.find((r) => r.id === this.ruleId);
            return [{ title: 'any', value: null }, ...(rule?.patterns || []).map((p, i) => ({ title: p, value: i }))];
        },
        meaningShown() {
            const withMeaning = this.worlds.nameItBatch.filter((n) => n.meaning);
            return withMeaning.length ? withMeaning.map((n) => `${n.name}: ${n.meaning}`).join(' · ') : '';
        },
        effect() {
            const target = this.request?.target || {};
            if (target.thingId) {
                const old = target.fullName || this.request.words;
                return this.request.stub
                    ? `renames it everywhere; “${old}” is forgotten`
                    : `renames it everywhere; “${old}” stays as another name`;
            }
            if (target.draftKey || target.smallKey) {
                return 'in this draft: every place it is written';
            }
            return '';
        },
    },
    watch: {
        request: {
            immediate: true,
            handler(request) {
                if (!request) return;
                if (!this.worlds.things.language) this.worlds.listThings('language');
                this.meaning = '';
                this.ruleId = null;
                this.pattern = null;
                this.languageId = request.languageId || this.languageItems[0]?.value || null;
                this.worlds.nameItLoadRules(this.languageId);
            },
        },
        languageId(id, before) {
            if (id && id !== before && this.request) {
                this.ruleId = null;
                // a meaning's candidates are that language's (final review 5)
                this.worlds.nameItMeaning = { pending: false, candidates: [], error: null, languageId: null };
                this.worlds.nameItLoadRules(id);
            }
        },
        'worlds.nameItRules'(rules) {
            if (!rules.length || this.ruleId) return;
            const kind = this.request?.kind || 'place';
            const names = rules.filter((r) => r.use !== 'words');
            const wanted = [kind, BUCKETS[kind] || 'things', 'places'];
            const found = wanted.map((use) => names.find((r) => r.use === use)).find(Boolean) || names[0] || rules[0];
            this.ruleId = found?.id || null;
        },
        ruleId() {
            this.pattern = null;
            this.roll();
        },
        pattern() {
            this.roll();
        },
    },
    methods: {
        roll() {
            this.worlds.nameItRoll(this.languageId, this.ruleId, this.pattern);
        },
        find() {
            this.worlds.nameItFromMeaning(this.languageId, this.meaning);
        },
        meaningOf(candidate) {
            return (candidate.built_from || []).map((p) => p.meaning).join(' ');
        },
        // a name from a meaning: its new words go into the language too
        pickCandidate(candidate) {
            const coined = (candidate.built_from || []).filter((part) => part.new);
            this.worlds.pickNameIt(this.worlds.nameItMeaning.languageId || this.languageId, candidate.name, this.meaningOf(candidate), coined);
        },
        pick(name, meaning) {
            this.worlds.pickNameIt(this.languageId, name, meaning || '');
        },
    },
};
</script>

<style scoped>
.name-it {
    background: rgb(var(--v-theme-raised));
}
.words {
    background: rgba(var(--v-theme-accent), 0.25);
    border-radius: 2px;
    padding: 0 3px;
}
.field {
    flex: 0 1 200px;
}
.meaning {
    flex: 0 1 260px;
}
.names {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.name,
.foreign {
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
}
</style>
