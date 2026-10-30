<template>
    <v-card class="mark-card pa-3" min-width="260" max-width="420" data-testid="name-mark-card">
        <template v-if="mark">
            <div v-if="mark.kind === 'replaced'" class="d-flex align-baseline flex-wrap ga-1">
                <span class="mark-name">{{ mark.name }}</span>
                <span class="text-muted">· was <s>{{ mark.was }}</s></span>
            </div>
            <div v-else class="mark-name suspect">{{ mark.name }}</div>
            <div class="text-caption text-muted mt-1">{{ why }}</div>
            <div v-if="mark.meaning" class="text-caption mt-1">means “{{ mark.meaning }}”</div>
            <div class="d-flex flex-wrap ga-2 mt-2">
                <template v-if="mark.kind === 'replaced'">
                    <v-btn size="small" variant="outlined" prepend-icon="mdi-dice-multiple" :disabled="!mark.spares?.length" data-testid="mark-reroll" @click="act('reroll')">Reroll</v-btn>
                    <v-btn size="small" variant="text" data-testid="mark-keep-here" @click="act('keep_here')">Keep {{ mark.was }} here</v-btn>
                    <v-btn size="small" variant="text" data-testid="mark-never" @click="act('never')">Never replace {{ mark.was }} in this world</v-btn>
                </template>
                <template v-else>
                    <v-btn size="small" variant="outlined" prepend-icon="mdi-swap-horizontal" :disabled="!mark.spares?.length" data-testid="mark-replace" @click="act('replace')">Replace it</v-btn>
                    <v-btn size="small" variant="text" data-testid="mark-keep" @click="act('keep')">Keep it</v-btn>
                    <v-btn size="small" variant="text" data-testid="mark-never-flag" @click="act('never_flag')">Never flag it in this world</v-btn>
                </template>
            </div>
        </template>
        <div v-else class="text-caption text-muted">This name changed since.</div>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// The card on a cleaned name (languages 4a, approved mockup frame 1): a
// replaced one says what it was and why, with Reroll, Keep the old name
// here, and Never replace it in this world; a suspect one says why, with
// Replace it, Keep it, and Never flag it in this world. Acts on the open
// draft (`worlds.markAction`).
export default {
    name: 'NameMarkCard',
    props: {
        markId: { type: String, required: true },
    },
    emits: ['done'],
    // a small draft's form ("+ Add facts", a group's "+ Add") gives its
    // draft's key; else the card acts on the page draft
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
            return this.mark?.why ? this.mark.why.charAt(0).toUpperCase() + this.mark.why.slice(1) : '';
        },
    },
    methods: {
        act(action) {
            this.worlds.markAction(this.markId, action, this.smallKey);
            this.$emit('done');
        },
    },
};
</script>

<style scoped>
.mark-card {
    background: rgb(var(--v-theme-raised));
    font-size: 13px;
}
.mark-name {
    color: rgb(var(--v-theme-foreign));
    font-style: italic;
    font-size: 15px;
}
</style>
