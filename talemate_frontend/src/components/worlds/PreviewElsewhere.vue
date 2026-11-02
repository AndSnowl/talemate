<template>
    <div v-if="rows.length" class="preview-elsewhere mt-3" data-testid="preview-elsewhere">
        <div class="suggestion-heading mt-3">For other pages <span class="count">{{ rows.length }}</span></div>
        <div v-for="group in groups" :key="group.key" class="group" data-testid="elsewhere-group">
            <div class="d-flex align-center flex-wrap ga-2">
                <span :class="group.new ? 'stub-name' : 'entry-name'" data-testid="elsewhere-entry">{{ group.name }}</span>
                <span v-if="group.new" class="text-caption text-muted">{{ newLine(group) }}</span>
                <SameThingAsk
                    v-if="group.new && group.new.same_as && group.new.same_as.length"
                    variant="row"
                    :name="group.name"
                    :kind="group.new.kind"
                    :offers="group.new.same_as"
                    :chosen="group.new.same_target_id || null"
                    @choose="chooseSame(group, $event)"
                />
                <v-btn variant="text" size="x-small" @click="tickGroup(group, !anyTicked(group))">{{ anyTicked(group) ? 'Untick all' : 'Tick all' }}</v-btn>
            </div>
            <SuggestionRow
                v-for="index in group.rows"
                :key="index"
                :ticked="rows[index].ticked !== false"
                :tick-label="'Write ' + rows[index].text"
                testid="elsewhere-row"
                @tick="tick(index, $event)"
            >
                <LinkedText :segments="elsewhereSegments(rows[index], index, rendered, newNames, worlds.draft?.edited?.marks)" :text="rows[index].text" />
                <template v-if="rows[index].since" #end>
                    <span class="fact-date">{{ formatDate(worlds.calendar, rows[index].since) }}</span>
                </template>
                <!-- its category, where it goes and whom it's held by, on
                     a line of its own under its words -->
                <template #under>
                    <div class="d-flex align-center flex-wrap ga-2">
                        <v-select
                            :model-value="rows[index].category"
                            :items="categoryOptions(group, rows[index])"
                            density="compact"
                            variant="outlined"
                            hide-details
                            class="category"
                            data-testid="elsewhere-category"
                            :aria-label="'Category of ' + rows[index].text"
                            @update:model-value="change(index, { category: $event })"
                        ></v-select>
                        <v-btn
                            variant="text"
                            size="x-small"
                            append-icon="mdi-menu-down"
                            class="target"
                            data-testid="elsewhere-target"
                            :title="'Write it on another page than ' + group.name"
                            @click="startRetarget(index, $event)"
                        >→ {{ group.name }}</v-btn>
                        <v-btn
                            variant="text"
                            size="x-small"
                            prepend-icon="mdi-plus"
                            data-testid="elsewhere-also"
                            :disabled="alsoHere.includes(rows[index].text)"
                            @click="$emit('also', rows[index])"
                        >also here</v-btn>
                        <span v-if="rows[index].held_by_name" class="held" data-testid="held-by-tag">held by {{ rows[index].held_by_name }}</span>
                    </div>
                </template>
                <template v-if="rows[index].repeat_of" #match>
                    <PreviewRepeats
                        :repeat="rows[index].repeat_of"
                        :choice="elsewhereRepeatChoice(rows[index])"
                        :unavailable="{ move: 'already on that page' }"
                        @settle="settle(index, $event)"
                    />
                </template>
            </SuggestionRow>
        </div>
        <ReferenceMenu
            v-model="retargeting"
            :target="retargetAt"
            search-only
            search-label="Write it on…"
            :exclude="exclude"
            @pick="retargetTo"
        />
    </div>
</template>

<script>
import { elsewhereGroups, elsewhereSame, rowChanged, useWorldsStore } from '@/stores/worlds.js';
import { elsewhereRepeatChoice, elsewhereSegments, settleElsewhereRepeat, tickElsewhere } from './draftPage.js';
import { formatDate } from './worldDates.js';
import { kindInfo } from './worldKinds.js';
import LinkedText from './LinkedText.vue';
import PreviewRepeats from './PreviewRepeats.vue';
import ReferenceMenu from './ReferenceMenu.vue';
import SameThingAsk from './SameThingAsk.vue';
import SuggestionRow from './SuggestionRow.vue';

// "For other pages" (curation goal 1, spec "The draft page" 4): a draft's
// facts about other entries, grouped by the entry they're for, each ticked
// as it came (the owner's decision) and written onto that entry on Accept.
// Each row's target can be changed ("→ X ▾", a search: `retarget(index,
// target)`), and "+ also here" makes it one of this page's facts too
// (`also(row)`; off once this page has those words). A group
// can be unticked (or ticked) at once; each row's category can be changed
// among its entry's kind's (a timeline fact only when dated). Each row is
// a `SuggestionRow`: its category, target and "+ also here" on a second
// line under its words. A repeat of what the entry already says hangs its match
// under the row (`PreviewRepeats`), settled Keep new (the entry's fact
// removed on Accept), Keep existing or Keep both (`settleElsewhereRepeat`);
// Move existing here is off, the fact being on that page already. An
// entry not made yet is a
// new stub: its kind and tag, and a "same as X?" choice when the world may
// have it already (new by default). `rows` are the preview's
// `elsewhere`; every change emits `update` with the whole list.
export default {
    name: 'PreviewElsewhere',
    components: { LinkedText, PreviewRepeats, ReferenceMenu, SameThingAsk, SuggestionRow },
    props: {
        rows: { type: Array, required: true },
        // which preview it is ('create')
        type: { type: String, required: true },
        // the preview's new names, shown as such in the texts
        newNames: { type: Array, default: () => [] },
        // the rows as the server linked them (P6: the draft's
        // `elsewhere`, `[{index, text, segments}]`), used while the words
        // match
        rendered: { type: Array, default: () => [] },
        // this page's own facts' texts ("+ also here" is off for them)
        alsoHere: { type: Array, default: () => [] },
        // ids never offered as a target (the page's own)
        exclude: { type: Array, default: () => [] },
    },
    emits: ['update', 'retarget', 'also'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { retargeting: false, retargetAt: null, retargetIndex: null };
    },
    computed: {
        groups() {
            return elsewhereGroups(this.rows);
        },
    },
    methods: {
        formatDate,
        elsewhereRepeatChoice,
        elsewhereSegments,
        startRetarget(index, event) {
            this.retargetIndex = index;
            this.retargetAt = [event.clientX, event.clientY];
            this.retargeting = true;
        },
        retargetTo(target) {
            if (this.retargetIndex !== null) {
                this.$emit('retarget', this.retargetIndex, target);
            }
            this.retargetIndex = null;
        },
        anyTicked(group) {
            return group.rows.some((index) => this.rows[index].ticked !== false);
        },
        tick(index, ticked) {
            this.$emit('update', tickElsewhere(this.rows, [index], ticked));
        },
        tickGroup(group, ticked) {
            this.$emit('update', tickElsewhere(this.rows, group.rows, ticked));
        },
        // a repeat settled: Keep new, Keep existing or Keep both
        settle(index, how) {
            this.$emit('update', settleElsewhereRepeat({ elsewhere: this.rows }, index, how).elsewhere);
        },
        change(index, changes) {
            this.$emit('update', rowChanged(this.rows, index, changes));
        },
        chooseSame(group, targetId) {
            this.$emit('update', elsewhereSame(this.rows, group.new.name, targetId));
        },
        kindOf(group) {
            if (group.new) {
                return group.new.kind;
            }
            return this.worlds.referenceTargets.find((target) => target.id === group.targetId)?.kind || null;
        },
        // its entry's kind's categories (a timeline fact only when dated),
        // and the one it has
        categoryOptions(group, row) {
            const kind = this.kindOf(group);
            const all = kindInfo(kind)?.categories || [];
            const options = all.filter((category) => category !== 'statement' && (category !== 'timeline' || row.since));
            return options.includes(row.category) ? options : [row.category, ...options];
        },
        // "new stub · lore, custom": its kind and its tag
        newLine(group) {
            const fresh = group.new;
            const parts = [`new stub · ${fresh.kind}`];
            if (fresh.tag) {
                parts.push(fresh.tag);
            }
            if (fresh.same_target_id) {
                return 'no stub: it goes onto the entry picked';
            }
            return parts.join(', ');
        },
    },
};
</script>

<style scoped>
.group {
    border-left: 2px solid rgb(var(--v-theme-border));
    padding-left: 10px;
    margin: 6px 0 10px;
}

.entry-name {
    font-weight: 600;
    color: rgb(var(--v-theme-link));
    text-decoration: underline;
}

.stub-name {
    font-weight: 600;
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}

.held {
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}

.count {
    margin-left: 4px;
}

.target {
    text-transform: none;
}

.category {
    flex: none;
    width: 150px;
}

.category :deep(.v-field__input) {
    min-height: 30px;
    padding-top: 2px;
    padding-bottom: 2px;
    font-size: 13px;
}

.fact-date {
    flex: none;
    font-family: monospace;
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
}
</style>
