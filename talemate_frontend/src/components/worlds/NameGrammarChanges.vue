<template>
    <div class="changes" data-testid="name-grammar-changes">
        <div v-for="(change, i) in modelValue" :key="i" class="d-flex align-center flex-wrap ga-2 mb-1">
            <v-select :model-value="change.kind" :items="KINDS" density="compact" variant="outlined" hide-details class="kind" @update:model-value="set(i, { kind: $event })"></v-select>
            <v-text-field v-if="change.kind === 'swap'" :model-value="change.drop" label="drop" placeholder="a|o" density="compact" variant="outlined" hide-details class="text" @update:model-value="set(i, { drop: $event })"></v-text-field>
            <v-text-field v-if="change.kind !== 'double'" :model-value="change.text" label="add" density="compact" variant="outlined" hide-details class="text" @update:model-value="set(i, { text: $event })"></v-text-field>
            <v-select :model-value="whenKind(change.when)" :items="WHEN" density="compact" variant="outlined" hide-details class="when" @update:model-value="setWhen(i, $event, change.when)"></v-select>
            <v-text-field v-if="whenKind(change.when) === 'ends'" :model-value="change.when.slice(5)" label="letters" placeholder="a|o" density="compact" variant="outlined" hide-details class="text" @update:model-value="set(i, { when: 'ends:' + $event })"></v-text-field>
            <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" aria-label="Remove change" @click="remove(i)"></v-btn>
        </div>
        <v-btn size="x-small" variant="text" color="accent" prepend-icon="mdi-plus" @click="add">Change</v-btn>
    </div>
</template>

<script>
const KINDS = [
    { title: 'add an ending', value: 'ending' },
    { title: 'swap an ending', value: 'swap' },
    { title: 'a word before', value: 'word_before' },
    { title: 'a word after', value: 'word_after' },
    { title: 'double the first part', value: 'double' },
];
const WHEN = [
    { title: 'always', value: '' },
    { title: 'after a vowel', value: 'after_vowel' },
    { title: 'after a consonant', value: 'after_consonant' },
    { title: 'before a vowel', value: 'before_vowel' },
    { title: 'more than one', value: 'plural' },
    { title: 'ends with…', value: 'ends' },
];

// A form's or an ending's changes, tried in order: the first whose
// condition holds is used (languages 4b-1, `FormChange`).
export default {
    name: 'NameGrammarChanges',
    props: {
        modelValue: { type: Array, default: () => [] },
    },
    emits: ['update:modelValue'],
    setup() {
        return { KINDS, WHEN };
    },
    methods: {
        whenKind(when) {
            return (when || '').startsWith('ends:') ? 'ends' : when || '';
        },
        set(i, change) {
            this.$emit('update:modelValue', this.modelValue.map((c, j) => (j === i ? { ...c, ...change } : c)));
        },
        setWhen(i, kind, current) {
            this.set(i, { when: kind === 'ends' ? (current?.startsWith('ends:') ? current : 'ends:a') : kind });
        },
        remove(i) {
            this.$emit('update:modelValue', this.modelValue.filter((_, j) => j !== i));
        },
        add() {
            this.$emit('update:modelValue', [...this.modelValue, { when: '', kind: 'ending', text: '', drop: '' }]);
        },
    },
};
</script>

<style scoped>
.kind {
    flex: 0 1 190px;
}
.when {
    flex: 0 1 170px;
}
.text {
    flex: 0 1 100px;
}
</style>
