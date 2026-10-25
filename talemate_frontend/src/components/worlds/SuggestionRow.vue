<template>
    <div class="suggestion-row" :data-testid="testid">
        <div class="d-flex align-center ga-2">
            <v-checkbox-btn
                v-if="tickable"
                :model-value="ticked"
                density="compact"
                class="flex-grow-0"
                :aria-label="tickLabel"
                :disabled="disabled"
                @update:model-value="$emit('tick', $event)"
            ></v-checkbox-btn>
            <span class="flex-grow-1" :class="{ 'suggestion-dropped': dropped }">
                <slot></slot>
            </span>
            <slot name="end"></slot>
        </div>
        <div v-if="$slots.under" class="suggestion-under">
            <slot name="under"></slot>
        </div>
        <div v-if="$slots.match" class="suggestion-match-rule">
            <slot name="match"></slot>
        </div>
        <slot name="after"></slot>
    </div>
</template>

<script>
import './suggestions.css';

// One row of a suggestions-to-tick list (plan "polish-1"): a tick
// (`tickable`, off for a row that can't be ticked, e.g. a "same as"
// name), the text (default slot, shown with `.suggestion-dropped` once
// `dropped`), the category chip and date on the right of that line
// (`end`), a second line under the text for placement controls and
// notes (`under`), a repeat's match indented with a left rule (`match`)
// and a form under all of that (`after`). `tick(Boolean)` is emitted,
// never applied here. `dropped` defaults to the row being unticked, so a
// caller only sets it when a row that's still ticked should still read
// as dropped (or the reverse). The dashed row separator sits on the
// root's bottom edge, after `match` and `after`, so a row and whatever
// is shown under it read as one.
export default {
    name: 'SuggestionRow',
    props: {
        ticked: { type: Boolean, default: true },
        // the checkbox's aria-label, verbatim (each list keeps its own wording)
        tickLabel: { type: String, default: '' },
        tickable: { type: Boolean, default: true },
        disabled: { type: Boolean, default: false },
        // put on the root, for the tests
        testid: { type: String, default: null },
        dropped: { type: Boolean, default: (props) => !props.ticked },
    },
    emits: ['tick'],
};
</script>

<style scoped>
.suggestion-row {
    padding: 2px 0;
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

.suggestion-under {
    margin-left: 34px;
}

.suggestion-match-rule {
    margin-top: 2px;
    margin-left: 34px;
    padding-left: 10px;
    border-left: 2px solid rgb(var(--v-theme-border));
}
</style>
