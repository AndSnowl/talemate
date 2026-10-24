<template>
    <div v-if="rows.length" class="preview-elsewhere mt-3" data-testid="preview-elsewhere">
        <div class="heading">Belongs on other entries</div>
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
            <div v-for="index in group.rows" :key="index" class="row" data-testid="elsewhere-row">
                <div class="d-flex align-center ga-2">
                    <v-checkbox-btn
                        :model-value="rows[index].ticked !== false"
                        density="compact"
                        class="flex-grow-0"
                        :aria-label="'Write ' + rows[index].text"
                        @update:model-value="tick(index, $event)"
                    ></v-checkbox-btn>
                    <span class="flex-grow-1" :class="{ dropped: rows[index].ticked === false }">
                        <LinkedText :segments="previewSegments(rows[index].text, newNames)" :text="rows[index].text" />
                        <span v-if="rows[index].held_by_name" class="held" data-testid="held-by-tag">held by {{ rows[index].held_by_name }}</span>
                    </span>
                    <span v-if="rows[index].since" class="fact-date">{{ formatDate(worlds.calendar, rows[index].since) }}</span>
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
                </div>
                <div v-if="rows[index].repeat_of" class="match text-caption">≈ already on {{ rows[index].repeat_of.owner_name || group.name }}: {{ rows[index].repeat_of.text }}</div>
            </div>
        </div>
    </div>
</template>

<script>
import { elsewhereGroups, elsewhereSame, previewSegments, rowChanged, rowsTicked, useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';
import { kindInfo } from './worldKinds.js';
import LinkedText from './LinkedText.vue';
import SameThingAsk from './SameThingAsk.vue';

// "Belongs on other entries" (curation goal 1): a preview's facts about
// other entries, grouped by the entry they're for, each ticked as it came
// (the owner's decision) and written onto that entry on Accept. A group
// can be unticked (or ticked) at once; each row's category can be changed
// among its entry's kind's (a timeline fact only when dated). A repeat of
// what the entry already says shows its match. An entry not made yet is a
// new stub: its kind and tag, and a "same as X?" choice when the world may
// have it already (new by default). `rows` are the preview's
// `elsewhere`; every change emits `update` with the whole list.
export default {
    name: 'PreviewElsewhere',
    components: { LinkedText, SameThingAsk },
    props: {
        rows: { type: Array, required: true },
        // which preview it is ('create')
        type: { type: String, required: true },
        // the preview's new names, shown as such in the texts
        newNames: { type: Array, default: () => [] },
    },
    emits: ['update'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        groups() {
            return elsewhereGroups(this.rows);
        },
    },
    methods: {
        formatDate,
        previewSegments,
        anyTicked(group) {
            return group.rows.some((index) => this.rows[index].ticked !== false);
        },
        tick(index, ticked) {
            this.$emit('update', rowsTicked(this.rows, [index], ticked));
        },
        tickGroup(group, ticked) {
            this.$emit('update', rowsTicked(this.rows, group.rows, ticked));
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
.heading {
    margin-top: 10px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

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

.row {
    padding: 2px 0;
}

.dropped {
    color: rgb(var(--v-theme-muted));
}

.held {
    margin-left: 6px;
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}

.match {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
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
