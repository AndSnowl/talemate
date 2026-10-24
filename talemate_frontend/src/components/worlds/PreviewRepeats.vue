<template>
    <div class="repeat-match text-caption d-flex align-center flex-wrap ga-1" data-testid="fact-match">
        <span class="match">≈ already on <b>{{ repeat.owner_name || 'an entry' }}</b>: “{{ repeat.text }}”</span>
        <span v-if="moving" class="moving" data-testid="repeat-moving">· that one moves here</span>
        <v-btn
            v-for="choice in choices"
            :key="choice.how"
            :variant="choice.how === state ? 'flat' : 'outlined'"
            :color="choice.how === state ? 'accent' : undefined"
            size="x-small"
            :aria-pressed="choice.how === state"
            :disabled="disabled"
            @click="$emit('settle', choice.how)"
        >{{ choice.label }}</v-btn>
    </div>
</template>

<script>
const CHOICES = [
    { how: 'move', label: 'Move that one here' },
    { how: 'keep', label: 'Keep both' },
    { how: 'drop', label: 'Drop this' },
];

// A draft fact that repeats one the world holds (curation goal 3, spec
// "The draft page" 3): its match ("≈ already on <entry>: <text>"), and
// three ways to settle it, emitted as `settle(how)`: "Move that one here"
// ('move': the world's fact moves onto this entry on Accept and this one
// isn't written), "Keep both" ('keep': this one ticked, the world's left
// where it is) or "Drop this" ('drop': unticked). A repeat comes as the
// server ticked it: unticked at or above the repeat threshold.
export default {
    name: 'PreviewRepeats',
    props: {
        // the fact's `repeat_of`: `{fact_id, owner_id, owner_name, text}`
        repeat: { type: Object, required: true },
        // whether the draft fact is ticked, and whether that one moves here
        ticked: { type: Boolean, default: false },
        moving: { type: Boolean, default: false },
        disabled: { type: Boolean, default: false },
    },
    emits: ['settle'],
    data() {
        return { choices: CHOICES };
    },
    computed: {
        state() {
            if (this.moving) {
                return 'move';
            }
            return this.ticked ? 'keep' : 'drop';
        },
    },
};
</script>

<style scoped>
.repeat-match {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}

.moving {
    color: rgb(var(--v-theme-accent));
}
</style>
