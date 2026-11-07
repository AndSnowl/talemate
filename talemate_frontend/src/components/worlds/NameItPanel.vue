<template>
    <v-dialog :model-value="!!request" width="980" @update:model-value="!$event && worlds.closeNameIt()">
        <v-card v-if="request" class="name-it pa-4" data-testid="name-it">
            <!-- an entry's name as chips: the words chosen are renamed, the
                 rest stays (owner, Test3) -->
            <div class="d-flex align-center flex-wrap ga-2" data-testid="name-it-parts">
                <span class="text-subtitle-1">Name it:</span>
                <template v-if="parts.length > 1">
                    <v-chip
                        v-for="(part, i) in parts"
                        :key="i"
                        size="small"
                        label
                        :class="{ 'part-chosen': chosen(i) }"
                        :variant="chosen(i) ? 'flat' : 'outlined'"
                        :color="chosen(i) ? 'accent' : undefined"
                        data-testid="name-it-part"
                        @click="togglePart(i)"
                    >{{ part }}</v-chip>
                </template>
                <span v-else class="words">{{ request.words || 'a new name' }}</span>
                <span class="text-caption text-muted" data-testid="name-it-effect">{{ effect }}</span>
            </div>
            <div v-if="parts.length > 1" class="text-caption text-muted mt-1">
                <span class="font-italic">click a word to keep it out of the rename</span>
                <span class="ml-2">gives <b data-testid="name-it-result">{{ result }}</b></span>
            </div>

            <div class="d-flex align-center flex-wrap ga-2 mt-3">
                <span v-if="titleMode" class="text-body-2" data-testid="name-it-title-note">A title held, in its language: the name stays as it is.</span>
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
                    v-if="!titleMode"
                    v-model="ruleId"
                    :items="ruleItems"
                    @update:model-value="ownerChose = true"
                    label="Rule"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field"
                    :disabled="!languageId"
                    data-testid="name-it-rule"
                ></v-select>
                <span v-if="worlds.nameItPicking" class="text-caption text-muted" data-testid="name-it-picking">picking the rule…</span>
                <v-select
                    v-if="!composed && !titleMode"
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
                <!-- a composed rule's form: any, or one chosen (owner, Test2) -->
                <v-select
                    v-if="composed && shapeItems.length > 2"
                    :model-value="worlds.nameItShapeChoice"
                    :items="shapeItems"
                    :label="`Form · ${shapeItems.length - 1} forms`"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field form"
                    data-testid="name-it-form"
                    @update:model-value="chooseForm"
                ></v-select>
                <v-btn v-if="!titleMode" color="accent" variant="outlined" size="small" prepend-icon="mdi-dice-multiple" :disabled="!ruleId" data-testid="name-it-reroll" @click="roll">{{ composed ? 'Reroll the unpinned parts' : 'Reroll' }}</v-btn>
                <v-btn
                    v-if="composed && request.target?.thingId"
                    color="accent"
                    variant="text"
                    size="small"
                    prepend-icon="mdi-creation"
                    :loading="worlds.nameItBuilding"
                    :disabled="!formHasMeaning"
                    :title="formHasMeaning ? '' : 'This form has no part that takes a meaning'"
                    data-testid="name-it-suggest"
                    @click="worlds.nameItSuggest(languageId, ruleId, request.target.thingId)"
                >Suggest meanings from {{ suggestName }}'s facts</v-btn>
            </div>
            <div v-if="!languageId" class="text-body-2 text-muted mt-2">Pick the language to name it in.</div>
            <!-- why the model picked this rule (languages 4c) -->
            <div v-if="worlds.nameItPicked && worlds.nameItPicked.rule_id === ruleId && worlds.nameItPicked.why" class="text-caption text-muted mt-1" data-testid="name-it-picked">
                picked: {{ worlds.nameItPicked.why }}<template v-if="worlds.nameItPicked.fallback"> (by sex and rank)</template>
            </div>

            <!-- a composed rule: the builder, part by part (languages 4b-1) -->
            <NameBuilder v-if="composed" class="mt-3" :language-id="languageId" />
            <!-- a ruler's number, the narrator's (languages 4c) -->
            <div v-if="request.person && composed" class="d-flex align-center ga-2 mt-2" data-testid="name-it-regnal">
                <span class="text-caption text-muted">number after the name</span>
                <v-text-field
                    v-model="worlds.nameItRegnal"
                    placeholder="none"
                    density="compact"
                    variant="outlined"
                    hide-details="auto"
                    class="regnal"
                    :error-messages="regnalError(worlds.nameItRegnal)"
                ></v-text-field>
                <span class="text-caption text-muted">Roman numerals, as the narrator writes them</span>
            </div>
            <NameRolls v-else-if="!titleMode" class="mt-3" :items="worlds.nameItShown" @pick="pick($event.name, $event.meaning)" @pin="worlds.nameItPin($event)" />
            <div v-if="meaningShown && !composed && !titleMode" class="text-caption text-muted mt-1" data-testid="name-it-batch-meanings">{{ meaningShown }}</div>

            <!-- a plain rule only: the whole name from a meaning (a rule made
                 of parts has a meaning box in each meaning part, round 4) -->
            <template v-if="!composed">
            <v-divider class="my-3"></v-divider>
            <div class="d-flex align-center flex-wrap ga-2">
                <span class="text-body-2"><b>{{ titleMode ? 'A title from a meaning' : 'A whole name from a meaning' }}</b></span>
                <v-text-field
                    v-model="meaning"
                    placeholder="lakeland, the white water…"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field meaning"
                    data-testid="name-it-meaning"
                    @keydown.enter="find"
                ></v-text-field>
                <v-btn variant="text" color="accent" size="small" :loading="worlds.nameItMeaning.pending" :disabled="!languageId || !meaning.trim()" data-testid="name-it-find" @click="find">Find</v-btn>
                <span class="text-caption text-muted font-italic">Translates your words into one name, in this language's word order.</span>
            </div>
            <div v-if="worlds.nameItMeaning.error" class="text-caption text-error mt-1">{{ worlds.nameItMeaning.error }}</div>
            <div v-for="(candidate, ci) in worlds.nameItMeaning.candidates" :key="ci" class="d-flex align-center flex-wrap ga-2 mt-2" data-testid="name-it-candidate">
                <v-chip class="name" variant="tonal" data-testid="name-it-candidate-name" @click="pickCandidate(candidate)">{{ candidate.name }}</v-chip>
                <span class="text-caption text-muted">
                    <template v-for="(part, i) in candidate.built_from" :key="i"><span v-if="i"> + </span><span class="foreign">{{ part.word }}</span> “{{ part.meaning }}”<span v-if="part.new"> (new word, saved if you pick it)</span></template>
                </span>
            </div>
            <!-- each new word's rolls, once for every form of the name, as
                 the batch above rolls (owner, Test3) -->
            <div v-for="part in worlds.nameItWordParts" :key="'w' + part.index" class="mt-3" data-testid="name-it-word-rolls">
                <div class="d-flex align-center ga-2 mb-1">
                    <span class="text-caption text-muted">“{{ part.meaning }}”</span>
                    <v-btn variant="text" size="x-small" color="accent" prepend-icon="mdi-dice-multiple" data-testid="name-it-word-reroll" @click="worlds.nameItRollWord(worlds.nameItMeaning.languageId, part.index)">Reroll</v-btn>
                </div>
                <NameRolls
                    :items="worlds.nameItWordShown(part.index)"
                    :current="part.word"
                    testid="name-it-word-option"
                    pin-testid="name-it-word-pin"
                    @pick="worlds.nameItChooseWord(part.index, $event.name)"
                    @pin="worlds.nameItPinWord(part.index, $event)"
                />
            </div>
            </template>
        </v-card>
    </v-dialog>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import NameBuilder from './NameBuilder.vue';
import { regnalError, resultLine, ruleMenuItems } from './nameParts.js';
import NameRolls from './NameRolls.vue';

// which rule a kind starts from, as the server's `generator_for` would
const BUCKETS = { character: 'people', being: 'people', place: 'places' };

// Name it… (languages 4a revised, mockup frames 2 and 3): names for the
// asked words from a rule, or one of its patterns, ten at a time with
// Reroll; or from a meaning. Picking puts the name where the request asked
// (`worlds.pickNameIt`) and adds the word to the language.
export default {
    name: 'NameItPanel',
    components: { NameBuilder, NameRolls },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        // `picked`: the indices of the entry name's words chosen to rename
        return { languageId: null, ruleId: null, pattern: null, meaning: '', hovered: '', picked: [], adopting: false, ownerChose: false };
    },
    computed: {
        request() {
            return this.worlds.nameIt;
        },
        // what the rename gives: "King + new name + III"
        result() {
            return resultLine(this.request?.target?.fullName || '', this.picked);
        },
        // an entry's name, word by word, when the panel renames an entry
        parts() {
            const full = this.request?.target?.fullName || '';
            return full.split(/\s+/).filter(Boolean);
        },
        languageItems() {
            return (this.worlds.things.language || []).map((t) => ({ title: t.name, value: t.id }));
        },
        ruleItems() {
            return ruleMenuItems(this.worlds.nameItRules);
        },
        // a composed rule's forms, with "any" first
        shapeItems() {
            const rule = this.worlds.nameItRules.find((r) => r.id === this.ruleId);
            return [{ title: 'any', value: null }, ...(rule?.shapes || []).map((title, i) => ({ title, value: i }))];
        },
        // the picked rule is made of parts (languages 4b-1)
        // the entry's name, for "Suggest meanings from …'s facts"
        suggestName() {
            return this.request?.target?.fullName || this.request?.words || 'its';
        },
        // the form on screen has a meaning part (Suggest has something to fill)
        formHasMeaning() {
            return (this.worlds.nameItParts?.parts || []).some((p) => p.kind === 'meaning');
        },
        // a title made from a meaning (languages 4b-2): no rule, no rolls
        titleMode() {
            return !!this.request?.target?.titleOf;
        },
        composed() {
            if (this.titleMode) return false;
            // a person's rule the server is picking: the builder
            if (this.request?.person && this.ruleId === '') return true;
            const rule = this.worlds.nameItRules.find((r) => r.id === this.ruleId);
            return !!(rule && (rule.parts || []).length);
        },
        patternItems() {
            const rule = this.worlds.nameItRules.find((r) => r.id === this.ruleId);
            return [{ title: 'any', value: null }, ...(rule?.patterns || []).map((p, i) => ({ title: p, value: i }))];
        },
        meaningShown() {
            const withMeaning = this.worlds.nameItShown.filter((n) => n.meaning);
            return withMeaning.length ? withMeaning.map((n) => `${n.name}: ${n.meaning}`).join(' · ') : '';
        },
        effect() {
            const target = this.request?.target || {};
            if (target.titleOf) return 'adds a title; the name stays';
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
            handler(request, before) {
                if (!request) return;
                // the same request, its words narrowed (`togglePart`)
                if (before && request.target === before.target) return;
                if (!this.worlds.things.language) this.worlds.listThings('language');
                this.picked = this.indicesOf(request.words || '');
                this.ownerChose = false;
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
            if (this.request?.person) {
                // a person's (languages 4b-2): theirs, or the server's pick
                this.ruleId = this.request.ruleId || '';
                if (this.ruleId === '') {
                    // today's matching shows while the model picks (4c)
                    this.roll();
                    this.worlds.nameItPick(this.languageId);
                }
                return;
            }
            const kind = this.request?.kind || 'place';
            const names = rules.filter((r) => r.use !== 'words');
            const wanted = [kind, BUCKETS[kind] || 'things', 'places'];
            const found = wanted.map((use) => names.find((r) => r.use === use)).find(Boolean) || names[0] || rules[0];
            this.ruleId = found?.id || null;
        },
        ruleId() {
            // the rule the server picked for a person: already rolled
            if (this.adopting) {
                this.adopting = false;
                return;
            }
            this.pattern = null;
            // another rule: the builder starts again, no pins
            this.worlds.nameItParts = null;
            this.worlds.nameItPartPinned = {};
            this.worlds.nameItPartFree = [];
            this.worlds.nameItPartChosen = {};
            this.worlds.nameItShapeChoice = null;
            // a person's own rule: their parts pinned as they are (4b-2)
            const person = this.request?.person;
            if (person?.prefill && this.ruleId === this.request.ruleId) this.worlds.nameItPartPinned = { ...person.prefill };
            this.roll();
        },
        // the model's pick arrived: the panel switches to it (4c)
        'worlds.nameItPicked'(picked) {
            // a rule the owner chose first is kept
            if (picked && this.request?.person && !this.ownerChose && picked.rule_id && picked.rule_id !== this.ruleId) {
                this.ruleId = picked.rule_id;
            }
        },
        // the rule the server picked for a person, shown as the panel's
        'worlds.nameItParts'(parts) {
            if (this.request?.person && this.ruleId === '' && parts?.rule_id) {
                this.adopting = true;
                this.ruleId = parts.rule_id;
            }
        },
        pattern() {
            this.roll();
        },
    },
    methods: {
        // the indices of `words` in the entry's name (all of them if it
        // isn't found there)
        indicesOf(words) {
            const want = words.split(/\s+/).filter(Boolean);
            for (let at = 0; at + want.length <= this.parts.length; at++) {
                if (want.every((w, i) => this.parts[at + i] === w)) return want.map((_, i) => at + i);
            }
            return this.parts.map((_, i) => i);
        },
        chosen(i) {
            return this.picked.includes(i);
        },
        // a click changes only the word clicked (owner, 2026-11-04):
        // picked words are renamed, the others kept where they are; the
        // last picked word stays (something has to be renamed)
        togglePart(i) {
            if (this.chosen(i) && this.picked.length === 1) return;
            this.picked = this.chosen(i) ? this.picked.filter((p) => p !== i) : [...this.picked, i].sort((a, b) => a - b);
            this.worlds.nameIt = {
                ...this.worlds.nameIt,
                words: this.picked.map((p) => this.parts[p]).join(' '),
                picked: [...this.picked],
            };
        },
        chooseForm(shape) {
            this.worlds.nameItShapeChoice = shape;
            // another form: its pins no longer fit
            this.worlds.nameItPartPinned = {};
            this.roll();
        },
        roll() {
            if (this.titleMode) return;
            if (this.composed) this.worlds.nameItRollParts(this.languageId, this.ruleId);
            else this.worlds.nameItRoll(this.languageId, this.ruleId, this.pattern);
        },
        // a composed rule's meaning parts take the meaning; else names
        // built from it alone
        find() {
            this.worlds.nameItFromMeaning(this.languageId, this.meaning, this.composed ? this.ruleId : null);
        },
        meaningOf(candidate) {
            return (candidate.built_from || []).map((p) => p.meaning).join(' ');
        },
        // a name from a meaning: its new words go into the language too
        pickCandidate(candidate) {
            const coined = (candidate.built_from || []).filter((part) => part.new);
            this.worlds.pickNameIt(this.worlds.nameItMeaning.languageId || this.languageId, candidate.name, this.meaningOf(candidate), coined);
        },
        regnalError,
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
.form {
    flex: 0 1 340px;
}
.meaning {
    flex: 0 1 260px;
}
.regnal {
    flex: 0 0 110px;
}
.name,
.foreign {
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
}
</style>
