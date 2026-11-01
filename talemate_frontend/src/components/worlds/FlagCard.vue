<template>
    <v-card class="flag-card pa-3" min-width="260" max-width="440" data-testid="flag-card">
        <template v-if="mark">
            <div class="d-flex align-center flex-wrap ga-2">
                <span class="flag-name" :class="{ stub: newStub }">{{ mark.name }}</span>
                <v-chip v-if="newStub" size="x-small" label variant="tonal">{{ newStub }}</v-chip>
                <span v-if="newStub" class="text-caption text-muted">a new stub</span>
            </div>
            <div class="text-caption mt-1 flag-why">Flagged: {{ why }}</div>
            <div class="d-flex flex-wrap ga-2 mt-2">
                <v-btn size="small" variant="outlined" color="accent" prepend-icon="mdi-rename" data-testid="flag-name-it" @click="nameIt">Name it…</v-btn>
                <v-btn size="small" variant="text" data-testid="flag-keep" @click="act('keep')">Keep it</v-btn>
                <v-btn size="small" variant="text" data-testid="flag-never" @click="act('never_flag')">Never flag it in this world</v-btn>
            </div>
        </template>
        <div v-else class="text-caption text-muted">This name changed since.</div>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// The card on a flagged name (languages 4a revised, mockup frame 1): why
// it's flagged, with Name it…, Keep it and Never flag it in this world.
// A flagged new stub says so (its stub look stays on the text). Acts on
// the open draft, or a small draft's form's (`markScope`).
export default {
    name: 'FlagCard',
    props: {
        markId: { type: String, required: true },
        // a new stub's kind, when the flagged words are one
        newStub: { type: String, default: '' },
    },
    emits: ['done'],
    inject: { markScope: { default: null } },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        smallKey() {
            return this.markScope?.key || null;
        },
        mark() {
            const edited = this.smallKey ? this.worlds.smallDrafts[this.smallKey]?.edited : this.worlds.draft?.edited;
            return (edited?.marks || []).find((m) => m.id === this.markId) || null;
        },
        why() {
            const why = this.mark?.why || '';
            return why.charAt(0).toUpperCase() + why.slice(1);
        },
    },
    methods: {
        act(action) {
            this.worlds.markAction(this.markId, action, this.smallKey);
            this.$emit('done');
        },
        nameIt() {
            this.worlds.openNameIt({
                words: this.mark.part || this.mark.name,
                languageId: this.mark.language_id,
                kind: this.mark.entry_kind,
                target: this.smallKey ? { smallKey: this.smallKey } : { draftKey: this.worlds.draft?.key },
                markId: this.markId,
            });
            this.$emit('done');
        },
    },
};
</script>

<style scoped>
.flag-card {
    background: rgb(var(--v-theme-raised));
    font-size: 13px;
}
.flag-name {
    font-size: 15px;
    text-decoration: underline wavy rgb(var(--v-theme-warning));
    text-decoration-thickness: 1px;
    text-underline-offset: 4px;
}
.flag-name.stub {
    color: rgb(var(--v-theme-foreign));
}
.flag-why {
    color: rgb(var(--v-theme-warning));
}
</style>
