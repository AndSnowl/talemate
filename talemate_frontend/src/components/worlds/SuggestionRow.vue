<template>
    <div class="suggestion-row" :class="{ 'no-tick': !tickable }" :data-testid="testid">
        <div class="suggestion-line d-flex align-center ga-2">
            <v-checkbox-btn
                v-if="tickable"
                :model-value="ticked"
                density="compact"
                class="flex-grow-0"
                :aria-label="tickLabel"
                :disabled="disabled"
                :data-testid="tickTestid"
                @update:model-value="$emit('tick', $event)"
            ></v-checkbox-btn>
            <div class="suggestion-body">
                <span class="suggestion-text" :class="{ 'suggestion-dropped': isDropped }">
                    <slot></slot>
                </span>
                <div v-if="$slots.end" class="suggestion-end d-flex align-center ga-2">
                    <slot name="end"></slot>
                </div>
            </div>
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
// name) that never wraps, then the text (default slot, shown with
// `.suggestion-dropped` once `dropped`) and the category chip and date
// right after it (`end`, which never shrinks; the text shrinks and
// wraps first). The text and `end` share their own wrapping flex line
// (`suggestion-body`), right of the tick: short text, `end` follows it
// on the same line; long text, `end` drops under the text but still
// right of the tick column, never under the tick itself — the owner's
// rule: a control that belongs to the row's text follows it, it's
// never pushed to a wide pane's far edge. A second line under the text
// for placement controls and notes (`under`), a repeat's match indented
// with a left rule (`match`) and a form under all of that (`after`).
// `tick(Boolean)` is emitted,
// never applied here. `dropped` is null by default and then follows
// `ticked` (an unticked row reads as dropped), so a caller only sets it
// when a row that's still ticked should still read as dropped (or the
// reverse). Without a tick (`tickable` off) `under` and `match` aren't
// indented past one. The dashed row separator sits on the
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
        // put on the tick, for the tests
        tickTestid: { type: String, default: null },
        // null: follows `ticked` (a prop default is resolved once, at
        // mount, so it can't be the default itself)
        dropped: { type: Boolean, default: null },
    },
    emits: ['tick'],
    computed: {
        isDropped() {
            return this.dropped ?? !this.ticked;
        },
    },
};
</script>

<style scoped>
.suggestion-row {
    padding: 2px 0;
    border-bottom: 1px dashed rgb(var(--v-theme-border));
}

/* the tick (outside this) never wraps; everything that belongs to the
   text — the text itself and `end` — wraps as its own unit, so a long
   text's `end` drops to the next line still right of the tick, never
   under it */
.suggestion-body {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    column-gap: 8px;
    row-gap: 2px;
    flex: 1 1 auto;
    min-width: 0;
}

.suggestion-text {
    flex: 0 1 auto;
    min-width: 0;
}

.suggestion-end {
    flex: 0 0 auto;
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

.no-tick > .suggestion-under,
.no-tick > .suggestion-match-rule {
    margin-left: 0;
}
</style>
