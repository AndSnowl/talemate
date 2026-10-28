<template>
    <div class="suggestion-row" :class="{ 'no-tick': !tickable, 'suggestion-fill': fill }" :data-testid="testid">
        <div class="suggestion-line d-flex align-start ga-2">
            <v-checkbox-btn
                v-if="tickable"
                :model-value="ticked"
                density="compact"
                class="flex-grow-0 suggestion-tick"
                :aria-label="tickLabel"
                :disabled="disabled"
                :data-testid="tickTestid"
                @update:model-value="$emit('tick', $event)"
            ></v-checkbox-btn>
            <div class="suggestion-body">
                <span class="suggestion-text" :class="droppedClass">
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
// dimmed, `.suggestion-offer`, while unticked if it came unticked; else
// struck through, `.suggestion-dropped`, once `dropped`) and the category chip and date
// right after it (`end`, which never shrinks; the text shrinks and
// wraps first). The text and `end` share their own wrapping flex line
// (`suggestion-body`), right of the tick: short text, `end` follows it
// on the same line; long text, `end` drops under the text but still
// right of the tick column, never under the tick itself. Where `end`
// sits goes by the row's own width (a container query, the owner's
// rule): in a list half the screen wide or less it's at the right edge,
// lined up row under row; in a wider one it follows the text, never
// pushed to a wide pane's far edge. A second line under the text
// for placement controls and notes (`under`), a repeat's match indented
// with a left rule (`match`) and a form under all of that (`after`).
// `fill`: the text takes the row's full width right of the tick (a fact
// line there, its category and dates at the right edge as on a page),
// for a row with no `end`. `tick(Boolean)` is emitted,
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
        fill: { type: Boolean, default: false },
    },
    emits: ['tick'],
    data() {
        // how the row came (polish 5): one that came unticked is an offer
        return { startedDropped: this.dropped ?? !this.ticked };
    },
    computed: {
        isDropped() {
            return this.dropped ?? !this.ticked;
        },
        // unticked: an offer (it came that way) is dimmed; a row the owner
        // unticked is struck through, as "this won't be written"
        droppedClass() {
            if (!this.isDropped) {
                return '';
            }
            return this.startedDropped ? 'suggestion-offer' : 'suggestion-dropped';
        },
    },
};
</script>

<style scoped>
.suggestion-row {
    padding: 2px 0;
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    /* the row measures its own width (the list's), not the screen's: see
       the `@container` rule on `.suggestion-end` */
    container: suggestion-row / inline-size;
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

/* `.suggestion-line` is top-aligned (a multi-line row's tick must sit
   beside its first line, not centre on the whole block); this nudges
   the tick's own, slightly taller touch target back onto that first
   line's optical centre (measured against this row height and the
   default text/field line-height the rows use) */
.suggestion-tick {
    margin-top: -1px;
}

.suggestion-text {
    flex: 0 1 auto;
    min-width: 0;
}

.suggestion-end {
    flex: 0 0 auto;
}

.suggestion-fill .suggestion-text {
    flex: 1 1 auto;
}

/* the owner's rule: in a list half the screen wide or less (an entry
   page's Facts column, beside its Description), `end` goes to the row's
   right edge, lined up row under row (still wrapping under a long text);
   in a wider one (a draft's "For other pages", the full content width on
   a big screen) it follows the text, never far from it. The row measures
   its own width against the screen's: a fixed px threshold can't do it,
   the page's content area being narrow on a small screen (measured: Facts
   291px and the full width 594px at 1280px; 611px and 1234px at 1920px,
   so the full width at 1280 is narrower than Facts at 1920) */
@container suggestion-row (max-width: 50vw) {
    .suggestion-end {
        margin-left: auto;
    }
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
