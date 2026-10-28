<template>
    <div class="world-tab d-flex" data-testid="world-tab">
        <!-- the list: search, the entries by kind, then Stubs, Tags, Settings -->
        <div class="world-list pa-2" data-testid="world-list">
            <div class="text-overline text-muted px-2 world-title">{{ worlds.currentWorld?.name }}</div>
            <v-text-field
                v-model="query"
                placeholder="Search entries…"
                prepend-inner-icon="mdi-magnify"
                density="compact"
                variant="outlined"
                hide-details
                clearable
                aria-label="Search entries"
                class="px-1"
                data-testid="world-search"
                @focus="searchFocused = true"
                @blur="searchFocused = false"
            ></v-text-field>
            <div class="search-hint px-2 mb-2" :class="{ shown: searchFocused }" data-testid="search-hint">tag:city · in:Velikoye · stub · when:1020</div>
            <div v-for="item in kinds" :key="item.kind" class="kind-group">
                <div v-if="item.viaSkill" class="kind-head disabled d-flex align-center ga-2" :data-testid="'kind-' + item.kind">
                    <span class="fold-spacer"></span>
                    <v-icon size="small">{{ item.icon }}</v-icon>
                    <span class="flex-grow-1">{{ item.label }}</span>
                    <span class="text-caption text-muted">via skill</span>
                </div>
                <div v-else class="kind-head d-flex align-center" :class="{ active: !worlds.selectedThingId && item.kind === kind }">
                    <v-icon
                        size="small"
                        class="fold"
                        role="button"
                        :aria-label="(kindOpen(item.kind) ? 'Fold ' : 'Unfold ') + item.label"
                        :data-testid="'kind-fold-' + item.kind"
                        @click.stop="toggleKind(item.kind)"
                    >{{ kindOpen(item.kind) ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
                    <span
                        class="kind-name d-flex align-center ga-2 flex-grow-1"
                        role="button"
                        tabindex="0"
                        :data-testid="'kind-' + item.kind"
                        @click="selectKind(item.kind)"
                        @keydown.enter.prevent="selectKind(item.kind)"
                        @keydown.space.prevent="selectKind(item.kind)"
                    >
                        <v-icon size="small">{{ item.icon }}</v-icon>
                        <span class="flex-grow-1">{{ item.label }}</span>
                        <span class="text-caption text-muted">{{ entriesOf(item.kind).length }}</span>
                    </span>
                    <v-icon
                        size="x-small"
                        class="new-icon"
                        role="button"
                        :aria-label="'New ' + item.singular"
                        :title="'New ' + item.singular"
                        :data-testid="'kind-new-' + item.kind"
                        @click.stop="newOf(item.kind)"
                    >mdi-plus</v-icon>
                </div>
                <template v-if="kindOpen(item.kind)">
                    <template v-for="row in treeOf(item.kind)" :key="row.more ? 'more:' + row.more.parentId : row.thing.id">
                        <div
                            v-if="row.more"
                            class="list-more"
                            :style="{ paddingLeft: indent(row.depth) }"
                            role="button"
                            tabindex="0"
                            data-testid="tree-more"
                            @click="showAllOf(row.more.parentId)"
                            @keydown.enter.prevent="showAllOf(row.more.parentId)"
                        >+ {{ row.more.count }} more</div>
                        <div
                            v-else
                            class="list-item d-flex align-center ga-1"
                            :class="{ stub: row.thing.stub, active: row.thing.id === worlds.selectedThingId, context: row.context }"
                            :style="{ paddingLeft: indent(row.depth) }"
                            :data-testid="row.thing.stub ? 'stub-item' : 'thing-card'"
                            :title="row.thing.stub ? `${row.thing.name}: not made yet` : undefined"
                            role="button"
                            tabindex="0"
                            @click="worlds.openThing(row.thing.id)"
                            @keydown.enter.prevent="worlds.openThing(row.thing.id)"
                            @keydown.space.prevent="worlds.openThing(row.thing.id)"
                        >
                            <v-icon
                                v-if="row.childCount"
                                size="x-small"
                                class="fold"
                                role="button"
                                :aria-label="(row.folded ? 'Unfold ' : 'Fold ') + row.thing.name"
                                data-testid="entry-fold"
                                @click.stop="toggleEntry(row.thing.id)"
                            >{{ row.folded ? 'mdi-chevron-right' : 'mdi-chevron-down' }}</v-icon>
                            <span v-else class="fold-spacer"></span>
                            <span :class="row.thing.stub ? 'stub-name' : 'card-name'">{{ row.thing.name }}</span>
                            <span v-if="row.folded" class="text-caption text-muted" data-testid="fold-count">{{ row.childCount }}</span>
                        </div>
                    </template>
                </template>
            </div>
            <v-divider class="my-2"></v-divider>
            <div
                v-for="tab in tabs"
                :key="tab.kind"
                class="kind-head d-flex align-center ga-2"
                :class="{ active: !worlds.selectedThingId && kind === tab.kind }"
                role="button"
                tabindex="0"
                :data-testid="'kind-' + tab.kind"
                @click="selectKind(tab.kind)"
                @keydown.enter.prevent="selectKind(tab.kind)"
                @keydown.space.prevent="selectKind(tab.kind)"
            >
                <v-icon size="small">{{ tab.icon }}</v-icon>
                <span class="flex-grow-1">{{ tab.label }}</span>
                <span v-if="tab.kind === 'stubs'" class="text-caption text-muted">{{ liveStubCount }}</span>
                <span v-if="tab.kind === 'tags'" class="text-caption text-muted">{{ worlds.tags.length }}</span>
            </div>
        </div>

        <!-- the page -->
        <div class="main flex-grow-1 pa-4">
            <ExpandAskDialog />
            <v-alert v-if="worlds.error" type="error" variant="tonal" density="compact" class="mb-3" closable @click:close="worlds.clearError()">
                {{ worlds.error }}
            </v-alert>
            <!-- what the last accept, move, merge or date pick left out, and why -->
            <v-alert
                v-if="worlds.notes"
                type="info"
                variant="tonal"
                density="compact"
                class="mb-3"
                closable
                data-testid="accept-notes"
                @click:close="worlds.clearNotes()"
            >
                <div v-for="(note, index) in worlds.notes.notes" :key="index">{{ note }}</div>
            </v-alert>

            <ThingPage v-if="worlds.selectedThingId" />
            <StubsTab v-else-if="kind === stubsTab.kind" />
            <TagsTab v-else-if="kind === tagsTab.kind" />
            <CurationSettings v-else-if="kind === settingsTab.kind" />
            <template v-else-if="info">
                <CreateBox :kind="kind" :key="kind" />
                <div v-if="!worlds.draft" class="empty-hint pa-4 text-body-2">
                    <template v-if="entriesOf(kind).length">Pick one of the {{ info.label.toLowerCase() }} on the left, or describe a new one above.</template>
                    <template v-else>No {{ info.label.toLowerCase() }} yet. Describe one above to create it.</template>
                </div>
            </template>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { homesAbove, loadFolds, parseSearch, saveFolds, searchContext, searching, sideTree } from './worldTree.js';
import { SETTINGS_TAB, STUBS_TAB, TAGS_TAB, TOP_KINDS, kindInfo } from './worldKinds.js';
import CreateBox from './CreateBox.vue';
import CurationSettings from './CurationSettings.vue';
import ExpandAskDialog from './ExpandAskDialog.vue';
import StubsTab from './StubsTab.vue';
import TagsTab from './TagsTab.vue';
import ThingPage from './ThingPage.vue';

// The World tab, in two panes (spec "The pages"): the list and the page.
// The list (polish 5, mockup A) has a search box, then the world's entries
// by kind (Characters, Species, Places, Events, Items, Lore, Beings; races
// and mixes are reached from their species page; Cultures are made
// through the culture skill), as a tree that folds: each entry under its
// most precise home of its own kind (`sideTree`), a kind's stubs after its
// entries. Everything starts folded; opening a page opens the way to it;
// what the owner folds or unfolds is kept per world (`loadFolds`). A kind's
// ▸ folds it, its name opens its page (unfolding it), its "+" opens the
// page with the prompt ready. The search narrows the tree to what matches
// (`parseSearch`: words, `tag:`, `in:`, `stub`, `when:`), their homes shown
// dimmed as context. Stubs, Tags and Settings sit at the bottom.
export default {
    name: 'WorldTab',
    components: { CreateBox, CurationSettings, ExpandAskDialog, StubsTab, TagsTab, ThingPage },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            kinds: TOP_KINDS,
            stubsTab: STUBS_TAB,
            tagsTab: TAGS_TAB,
            settingsTab: SETTINGS_TAB,
            tabs: [STUBS_TAB, TAGS_TAB, SETTINGS_TAB],
            query: '',
            searchFocused: false,
            // the side tree's unfolded kinds and entries (kept per world),
            // and the entries whose "+ N more" was opened (this visit only)
            openKinds: new Set(),
            openEntries: new Set(),
            showAll: new Set(),
        };
    },
    computed: {
        // the open section, kept in the store for the back arrow's history
        kind() {
            return this.worlds.section;
        },
        info() {
            return kindInfo(this.kind);
        },
        search() {
            return parseSearch(this.query || '');
        },
        searchCtx() {
            return searchContext(Object.values(this.worlds.things).flat());
        },
        liveStubCount() {
            return this.worlds.stubs.filter((stub) => !stub.ignored).length;
        },
    },
    watch: {
        // another world: the search starts afresh
        'worlds.currentWorld.id': {
            immediate: true,
            handler(id) {
                this.query = '';
                const kept = id ? loadFolds(id) : { kinds: new Set(), entries: new Set() };
                this.openKinds = kept.kinds;
                this.openEntries = kept.entries;
                this.showAll = new Set();
                this.openPathTo(this.worlds.selectedThingId);
            },
        },
        // arriving on a page opens the way to it; it can be folded again
        'worlds.selectedThingId'(id) {
            this.openPathTo(id);
        },
    },
    methods: {
        // a kind's full entries, not its stubs
        entriesOf(kind) {
            return (this.worlds.things[kind] || []).filter((thing) => !thing.stub);
        },
        // the list's rows of a kind, for the search typed
        treeOf(kind) {
            return sideTree(this.worlds.things[kind], {
                nest: true,
                search: this.search,
                opened: this.openEntries,
                showAll: this.showAll,
                ctx: this.searchCtx,
            });
        },
        // a kind shows its entries when unfolded, or when a search finds
        // some in it
        kindOpen(kind) {
            return searching(this.search) ? this.treeOf(kind).length > 0 : this.openKinds.has(kind);
        },
        indent(depth) {
            return `${4 + depth * 14}px`;
        },
        keepFolds() {
            const id = this.worlds.currentWorld?.id;
            if (id) {
                saveFolds(id, { kinds: this.openKinds, entries: this.openEntries });
            }
        },
        toggleKind(kind) {
            const kinds = new Set(this.openKinds);
            if (kinds.has(kind)) {
                kinds.delete(kind);
            } else {
                kinds.add(kind);
            }
            this.openKinds = kinds;
            this.keepFolds();
        },
        toggleEntry(id) {
            const entries = new Set(this.openEntries);
            if (entries.has(id)) {
                entries.delete(id);
            } else {
                entries.add(id);
            }
            this.openEntries = entries;
            this.keepFolds();
        },
        showAllOf(id) {
            this.showAll = new Set([...this.showAll, id]);
        },
        openPathTo(id) {
            if (!id) {
                return;
            }
            const kind = Object.keys(this.worlds.things).find((key) => (this.worlds.things[key] || []).some((thing) => thing.id === id));
            if (!kind) {
                return;
            }
            this.openKinds = new Set([...this.openKinds, kind]);
            this.openEntries = new Set([...this.openEntries, ...homesAbove(this.worlds.things[kind], id)]);
            this.keepFolds();
        },
        // "+": the kind's page, its prompt ready to type
        newOf(kind) {
            this.selectKind(kind);
            let tries = 0;
            const focus = () => {
                const input = this.$el.querySelector('[data-testid="create-box"] textarea');
                if (input) {
                    input.focus();
                } else if (tries++ < 20) {
                    requestAnimationFrame(focus);
                }
            };
            this.$nextTick(focus);
        },
        selectKind(kind) {
            if (!this.openKinds.has(kind)) {
                this.openKinds = new Set([...this.openKinds, kind]);
                this.keepFolds();
            }
            this.worlds.showSection(kind);
            if (this.worlds.expanding && this.worlds.expanding.kind !== kind) {
                this.worlds.stopExpanding();
            }
        },
    },
};
</script>

<style scoped>
.world-tab {
    min-height: 100%;
}

.world-list {
    width: 260px;
    flex: none;
    background: rgb(var(--v-theme-surface));
    border-radius: 6px;
    overflow-y: auto;
    max-height: calc(100vh - 120px);
    position: sticky;
    top: 0;
}

/* the page may hold long one-line rows: it shrinks to its pane */
.main {
    min-width: 0;
}

.world-title {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}

.kind-head {
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
    font-size: 14px;
    color: rgb(var(--v-theme-muted));
}

.kind-head:focus-visible,
.list-item:focus-visible {
    outline: 1px solid rgb(var(--v-theme-accent));
}

.kind-head:hover,
.list-item:hover {
    background: rgba(var(--v-theme-on-surface), 0.06);
}

.kind-head.active,
.list-item.active {
    background: rgba(var(--v-theme-accent), 0.14);
}

.kind-head.disabled {
    cursor: default;
    opacity: 0.6;
}

.new-icon {
    opacity: 0;
}

.kind-head:hover .kind-head.disabled {
    cursor: default;
    opacity: 0.6;
}

.new-icon {
    opacity: 0.8;
}

.list-item {
    padding: 2px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

/* a match's home, shown for where it sits */
.list-item.context {
    opacity: 0.6;
}

.fold {
    cursor: pointer;
    color: rgb(var(--v-theme-muted));
    flex: none;
}

.fold-spacer {
    display: inline-block;
    width: 16px;
    flex: none;
}

.kind-name {
    min-width: 0;
}

.list-more {
    font-size: 12px;
    color: rgb(var(--v-theme-link));
    cursor: pointer;
    padding: 1px 8px;
}

.search-hint {
    font-size: 11px;
    color: rgb(var(--v-theme-muted));
    visibility: hidden;
}

.search-hint.shown {
    visibility: visible;
}

.card-name {
    color: rgb(var(--v-theme-accent));
}

.list-item.stub {
    opacity: 0.7;
}

.stub-name {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}

.empty-hint {
    background: rgba(var(--v-theme-on-surface), 0.03);
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
    color: rgb(var(--v-theme-muted));
}
</style>
