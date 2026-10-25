<template>
    <div class="repeat-match text-caption" data-testid="fact-match">
        <div class="match">
            ≈ already on <b>{{ repeat.owner_name || 'an entry' }}</b>: “{{ repeat.text }}”
            <span v-if="choice === 'move'" class="note" data-testid="repeat-moving">· the existing fact moves here</span>
            <span v-else-if="choice === 'new'" class="note" data-testid="repeat-removing">· the existing fact is removed</span>
        </div>
        <div class="d-flex align-center flex-wrap ga-1 mt-1">
            <v-btn
                v-for="option in choices"
                :key="option.how"
                :variant="option.how === choice ? 'flat' : 'outlined'"
                :color="option.how === choice ? 'accent' : undefined"
                size="x-small"
                :aria-pressed="option.how === choice"
                :title="refusal(option) || option.title"
                :disabled="disabled || !!refusal(option)"
                data-testid="repeat-choice"
                @click="$emit('settle', option.how)"
            >{{ option.label }}</v-btn>
        </div>
    </div>
</template>

<script>
// each named by the fact it keeps (P8)
const CHOICES = [
    { how: 'new', label: 'Keep new', title: 'Write this fact and remove the existing one', takesExisting: true },
    { how: 'existing', label: 'Keep existing', title: "Keep the existing fact; this one isn't written" },
    { how: 'both', label: 'Keep both', title: 'Write this fact and leave the existing one where it is' },
    { how: 'move', label: 'Move existing here', title: "Move the existing fact onto this entry; this one isn't written", takesExisting: true },
];

// A draft fact that repeats one the world holds (curation goal 3, spec
// "The draft page" 3), shown under the fact as one pair with it: its match
// ("≈ already on <entry>: <text>"), and four ways to settle it, each named
// by the fact it keeps (P8), emitted as `settle(how)` (`settleRepeat`):
// "Keep new" ('new': this one written, the existing one removed on
// Accept), "Keep existing" ('existing': this one unticked), "Keep both"
// ('both': this one ticked, the existing left where it is) or "Move
// existing here" ('move': the existing fact moves onto this entry on
// Accept and this one isn't written). `choice` is the way it's settled now
// (`repeatChoice`): a repeat at or above the repeat threshold comes
// unticked, as "Keep existing". The existing fact can't be removed or
// moved when it's its entry's summary (`repeat.summary`, H4): that's
// edited on its page, and those two choices say so. A choice can also be
// refused for a reason that's about where this row is, not the existing
// fact (e.g. an elsewhere row's "Move existing here", already on that
// page): `unavailable`, `{ [how]: reason }`, folded into the same
// `refusal()`.
export default {
    name: 'PreviewRepeats',
    props: {
        // the fact's `repeat_of`: `{fact_id, owner_id, owner_name, text}`
        repeat: { type: Object, required: true },
        // 'new', 'existing', 'both' or 'move'
        choice: { type: String, default: 'existing' },
        disabled: { type: Boolean, default: false },
        // reasons a choice can't apply here, by `how` (e.g. `{ move:
        // 'already on that page' }`)
        unavailable: { type: Object, default: () => ({}) },
    },
    emits: ['settle'],
    data() {
        return { choices: CHOICES };
    },
    methods: {
        // why a choice that takes the existing fact away can't, or null
        refusal(option) {
            if (this.unavailable[option.how]) {
                return this.unavailable[option.how];
            }
            if (!option.takesExisting) {
                return null;
            }
            if (this.repeat.summary) {
                return `That's the summary of ${this.repeat.owner_name || 'its entry'}; edit it on its page`;
            }
            return this.repeat.fact_id ? null : 'The existing fact is unknown';
        },
    },
};
</script>

<style scoped>
.repeat-match {
    margin-left: 34px;
    padding-bottom: 4px;
    color: rgb(var(--v-theme-muted));
}

.note {
    color: rgb(var(--v-theme-accent));
}
</style>
