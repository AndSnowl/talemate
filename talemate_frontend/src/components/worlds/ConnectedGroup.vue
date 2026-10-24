<template>
    <div
        class="connected-group"
        :class="{ over: dragOver }"
        data-testid="connected-group"
        :data-tag="group.tag ?? ''"
        @dragover="dragOverRow"
        @dragleave="dragOver = false"
        @drop="drop"
    >
        <div class="group-head d-flex align-center ga-2">
            <v-btn
                :icon="folded ? 'mdi-chevron-right' : 'mdi-chevron-down'"
                variant="text"
                size="x-small"
                density="compact"
                :aria-label="folded ? `Show ${group.heading}` : `Fold ${group.heading}`"
                data-testid="group-fold"
                @click="folded = !folded"
            ></v-btn>
            <b class="heading" data-testid="group-heading" @click="folded = !folded">{{ group.heading }}</b>
            <span class="text-caption text-muted" data-testid="group-count">{{ group.rows.length }}</span>
            <v-spacer></v-spacer>
            <v-btn
                variant="outlined"
                size="x-small"
                :loading="!!synopsisState?.pending"
                :title="synopsis ? 'Write the synopsis again' : 'Write a synopsis of this group'"
                data-testid="group-synopsis-button"
                @click="askSynopsis"
            >✎ Synopsis</v-btn>
            <!-- the untagged group's "+ Add" is the page's own -->
            <v-btn v-if="group.tag" variant="outlined" size="x-small" data-testid="group-add-button" @click="adding = !adding">+ Add</v-btn>
        </div>
        <div v-if="!folded" class="group-body">
            <v-text-field
                v-if="view.long"
                v-model="filter"
                :placeholder="`filter ${group.heading.toLowerCase()}…`"
                prepend-inner-icon="mdi-filter-variant"
                density="compact"
                variant="plain"
                hide-details
                clearable
                :aria-label="`Filter ${group.heading}`"
                class="group-filter"
                data-testid="group-filter"
            ></v-text-field>
            <div v-if="synopsis || synopsisState?.error" class="synopsis" data-testid="group-synopsis">
                <template v-if="synopsis">{{ synopsis }}</template>
                <span v-else class="text-caption text-muted">{{ synopsisState.error }}</span>
            </div>
            <GroupAddForm v-if="group.tag && (adding || drafting)" :thing-id="thingId" :tag="group.tag" @close="adding = false" />
            <div
                v-for="row in view.rows"
                :key="row.id"
                class="connected-row"
                :class="{ ended: !!row.until }"
                draggable="true"
                data-testid="connected-row"
                @dragstart="dragStart($event, row)"
            >
                <a href="#" :class="row.stub ? 'stub-link' : 'thing-link'" draggable="false" data-testid="connected-name" @click.prevent="worlds.openThing(row.id)">{{ row.name }}</a>
                <span v-if="row.believed" class="believed" data-testid="connected-believed">believed</span>
                <span v-if="row.stub && !lineOf(row)" class="text-caption text-muted"> stub</span>
                <span v-if="lineOf(row)" class="line"> — {{ lineOf(row) }}</span>
                <span v-if="row.role" class="role">{{ row.role }}</span>
                <span v-if="dates(row)" class="when" data-testid="connected-dates">{{ dates(row) }}</span>
                <!-- the keyboard's way to another group: drag's twin -->
                <v-menu v-if="others.length" location="bottom end">
                    <template #activator="{ props }">
                        <button
                            v-bind="props"
                            type="button"
                            class="move-btn"
                            :aria-label="`Move ${row.name} to another group`"
                            title="Move to another group"
                            data-testid="connected-move"
                        >▾</button>
                    </template>
                    <v-list density="compact">
                        <v-list-subheader>Move {{ row.name }} to</v-list-subheader>
                        <v-list-item
                            v-for="other in others"
                            :key="other.tag ?? ''"
                            :title="other.heading"
                            data-testid="connected-move-option"
                            @click="moveTo(row, other.tag)"
                        ></v-list-item>
                    </v-list>
                </v-menu>
            </div>
            <div v-if="view.long && !filter" class="more">
                <a v-if="view.hidden" href="#" data-testid="group-show-all" @click.prevent="showAll = true">show all {{ group.rows.length }}</a>
                <a v-else-if="showAll" href="#" data-testid="group-show-fewer" @click.prevent="showAll = false">show fewer</a>
            </div>
            <div v-if="filter && !view.rows.length" class="text-caption text-muted">None match.</div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dropTag, filingDates, groupKey, groupView } from './entryPage.js';
import GroupAddForm from './GroupAddForm.vue';

// the drag's data type: the row dragged and the group it's from
const DRAG_TYPE = 'application/x-fantasymate-row';

// One of Connected's groups (mockup v3, screen A): the entries filed in
// the page that share a tag, under its heading ("Rivers") with how many,
// one line each -- the entry's own summary, the filing's role and dates (an
// ended one its span, "900–1015"); a stub in the stub style. The group
// folds. A long one (more than `GROUP_SHOWN`) shows a filter box, then its
// synopsis, then its first rows and "show all". "✎ Synopsis" asks for the
// group's synopsis (`group_synopsis`; again, skipping the cache, once
// there is one); "+ Add" drafts new entries for it (`GroupAddForm`).
// A row dragged onto another group takes that group's tag (`set_tag`),
// so it moves there on every page it's filed in; its "▾" menu does the
// same from the keyboard. A believed (or undecided) being is marked
// "believed" (ruling F24). The page keys each group by page and tag, so
// its fold, filter and "show all" never carry over to another page.
export default {
    name: 'ConnectedGroup',
    components: { GroupAddForm },
    props: {
        // the page's id
        thingId: { type: String, required: true },
        // `{tag, heading, synopsis, rows}`
        group: { type: Object, required: true },
        // the page's other groups (`{tag, heading}`), a row's "move to"
        others: { type: Array, default: () => [] },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { folded: false, filter: '', showAll: false, adding: false, dragOver: false };
    },
    computed: {
        key() {
            return groupKey(this.thingId, this.group.tag);
        },
        view() {
            return groupView(this.group.rows, { filter: this.filter || '', showAll: this.showAll });
        },
        synopsisState() {
            return this.worlds.synopses[this.key] || null;
        },
        // the page's own (the server's cache), else the one asked for
        // this session since the page was last fetched
        synopsis() {
            return this.group.synopsis || this.synopsisState?.text || '';
        },
        // a draft for this group is out or waiting: its rows show
        drafting() {
            return !!this.worlds.groupAdds[this.key];
        },
    },
    methods: {
        dates(row) {
            return filingDates(this.worlds.calendar, row);
        },
        lineOf(row) {
            return (row.line_segments || []).map((segment) => segment.text).join('').trim();
        },
        askSynopsis() {
            this.worlds.groupSynopsis(this.thingId, this.group.tag, !!this.synopsis);
        },
        moveTo(row, tag) {
            const to = dropTag(this.group.tag, tag);
            if (to !== undefined) {
                this.worlds.setTag(row.id, to);
            }
        },
        // only a Connected row may be dropped here
        dragOverRow(event) {
            if (event.dataTransfer?.types?.includes(DRAG_TYPE)) {
                event.preventDefault();
                this.dragOver = true;
            }
        },
        dragStart(event, row) {
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ id: row.id, tag: this.group.tag ?? null }));
            event.dataTransfer.setData('text/plain', row.name);
        },
        drop(event) {
            this.dragOver = false;
            const raw = event.dataTransfer?.getData(DRAG_TYPE);
            if (!raw) {
                return;
            }
            event.preventDefault();
            const dragged = JSON.parse(raw);
            const tag = dropTag(dragged.tag, this.group.tag);
            if (tag !== undefined) {
                this.worlds.setTag(dragged.id, tag);
            }
        },
    },
};
</script>

<style scoped>
.connected-group {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    margin: 6px 0;
    break-inside: avoid;
}

.connected-group.over {
    border-color: rgb(var(--v-theme-accent));
}

.group-head {
    padding: 2px 8px 2px 4px;
    background: rgba(var(--v-theme-on-surface), 0.04);
}

.heading {
    cursor: pointer;
}

.group-body {
    padding: 2px 10px 6px;
}

.group-filter {
    font-size: 13px;
}

.synopsis {
    font-size: 13px;
    line-height: 1.45;
    margin: 4px 0 6px;
    padding-left: 8px;
    border-left: 2px solid rgb(var(--v-theme-border));
}

.connected-row {
    font-size: 14px;
    padding: 1px 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: grab;
}

.connected-row.ended {
    opacity: 0.75;
}

.thing-link {
    color: rgb(var(--v-theme-link));
    text-decoration: underline dotted;
}

.stub-link {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}

.role,
.when {
    margin-left: 6px;
}

.role {
    font-size: 12px;
    font-style: italic;
    color: rgb(var(--v-theme-muted));
}

.when {
    font-size: 11px;
    color: rgb(var(--v-theme-date));
}

.believed {
    margin-left: 6px;
    font-size: 12px;
    font-style: italic;
    color: rgb(var(--v-theme-muted));
}

.move-btn {
    margin-left: 6px;
    padding: 0 4px;
    border-radius: 3px;
    color: rgb(var(--v-theme-muted));
}

.move-btn:hover,
.move-btn:focus-visible {
    color: rgb(var(--v-theme-accent));
    outline: 1px solid rgb(var(--v-theme-accent));
}

.more {
    font-size: 12px;
}

.more a {
    color: rgb(var(--v-theme-muted));
}
</style>
