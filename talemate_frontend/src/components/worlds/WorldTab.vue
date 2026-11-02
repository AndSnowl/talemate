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
                <div class="kind-head d-flex align-center" :class="{ active: !worlds.selectedThingId && item.kind === kind }">
                    <v-icon
                        size="small"
                        class="fold"
                        :class="{ off: searchActive }"
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
                                :class="{ off: searchActive }"
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
            <div v-else-if="kind === settingsTab.kind">
                <!-- General (curation) and Names (languages 4a) -->
                <v-tabs v-model="settingsPage" density="compact" color="accent" class="mb-2">
                    <v-tab value="general" data-testid="general-tab">General</v-tab>
                    <v-tab value="names" data-testid="names-tab">Names</v-tab>
                </v-tabs>
                <CurationSettings v-if="settingsPage === 'general'" />
                <NamesSettings v-else />
            </div>
            <template v-else-if="info">
                <!-- a language is made (outside, or by a strong model) or
                     imported, never written from a prompt; what's made
                     lands in the import review -->
                <template v-if="kind === 'language'">
                    <LanguageMake />
                    <LanguageImport :initial-text="worlds.languageMake?.text || null" />
                </template>
                <CreateBox v-else :kind="kind" :key="kind" />
                <KindList v-if="!worlds.draft" :kind="kind" :query="query || ''" />
            </template>
        </div>
        <!-- Name it… (languages 4a revised): one panel for every caller -->
        <NameItPanel />
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { homesAbove, loadFolds, parseSearch, saveFolds, searchContext, searching, sideTree } from './worldTree.js';
import { SETTINGS_TAB, STUBS_TAB, TAGS_TAB, TOP_KINDS, kindInfo } from './worldKinds.js';
import CreateBox from './CreateBox.vue';
import LanguageImport from './LanguageImport.vue';
import LanguageMake from './LanguageMake.vue';
import CurationSettings from './CurationSettings.vue';
import NamesSettings from './NamesSettings.vue';
import NameItPanel from './NameItPanel.vue';
import ExpandAskDialog from './ExpandAskDialog.vue';
import KindList from './KindList.vue';
import StubsTab from './StubsTab.vue';
import TagsTab from './TagsTab.vue';
import ThingPage from './ThingPage.vue';

// The World tab, in two panes (spec "The pages"): the list and the page.
// The list (polish 5, mockup A) has a search box, then the world's entries
// by kind (Characters, Species, Places, Events, Items, Lore, Beings; races
// and mixes are reached from their species page), as a tree that folds:
// each entry under its most precise home of its own kind (`sideTree`), a
// kind's stubs after its entries. Everything starts folded; opening a page opens the way to it;
// what the owner folds or unfolds is kept per world (`loadFolds`). A kind's
// ▸ folds it, its name opens its page (unfolding it), its "+" opens the
// page with the prompt ready. The search narrows the tree to what matches
// (`parseSearch`: words, `tag:`, `in:`, `stub`, `when:`), their homes shown
// dimmed as context. Stubs, Tags and Settings sit at the bottom.
export default {
    name: 'WorldTab',
    components: { CreateBox, CurationSettings, ExpandAskDialog, KindList, LanguageImport, LanguageMake, NameItPanel, NamesSettings, StubsTab, TagsTab, ThingPage },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            kinds: TOP_KINDS,
            stubsTab: STUBS_TAB,
            tagsTab: TAGS_TAB,
            settingsTab: SETTINGS_TAB,
            // the Settings tab's page: General or Names
            settingsPage: 'general',
            tabs: [STUBS_TAB, TAGS_TAB, SETTINGS_TAB],
            query: '',
            searchFocused: false,
            // the side tree's unfolded kinds and entries (kept per world),
            // and the entries whose "+ N more" was opened (this visit only)
            openKinds: new Set(),
            openEntries: new Set(),
            showAll: new Set(),
            // what the owner folded on the way to the open page (kept until
            // another page opens; "kind:<kind>" for its kind)
            foldedOnPath: new Set(),
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
        searchActive() {
            return searching(this.search);
        },
        searchCtx() {
            return searchContext(Object.values(this.worlds.things).flat());
        },
        // the way to the open page: its kind and every entry above it (on a
        // kind's own page, that kind), worked
        // out again whenever the lists change (a new entry's page opens
        // before they know it), never saved
        path() {
            const id = this.worlds.selectedThingId;
            if (!id) {
                // a kind's own page (Back to it, or after a delete): its kind
                return { kind: this.kind in this.worlds.things ? this.kind : null, ids: new Set() };
            }
            const kind = Object.keys(this.worlds.things).find((key) => (this.worlds.things[key] || []).some((thing) => thing.id === id));
            if (!kind) {
                return { kind: null, ids: new Set() };
            }
            return { kind, ids: new Set(homesAbove(this.worlds.things[kind], id)) };
        },
        // the entries shown open: the owner's, and the way to the open page
        // unless folded on it
        openedEntries() {
            return new Set([...this.openEntries, ...[...this.path.ids].filter((id) => !this.foldedOnPath.has(id))]);
        },
        // each kind's tree rows, once per render
        trees() {
            return Object.fromEntries(Object.keys(this.worlds.things).map((kind) => [kind, sideTree(this.worlds.things[kind], {
                nest: true,
                search: this.search,
                opened: this.openedEntries,
                showAll: this.showAll,
                ctx: this.searchCtx,
            })]));
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
                this.foldedOnPath = new Set();
            },
        },
        // arriving on a page opens the way to it afresh
        'worlds.selectedThingId'() {
            this.foldedOnPath = new Set();
        },
    },
    methods: {
        // a kind's full entries, not its stubs
        entriesOf(kind) {
            return (this.worlds.things[kind] || []).filter((thing) => !thing.stub);
        },
        // the list's rows of a kind, for the search typed
        treeOf(kind) {
            return this.trees[kind] || [];
        },
        // a kind shows its entries when unfolded, or when a search finds
        // some in it
        kindOpen(kind) {
            if (searching(this.search)) {
                return this.treeOf(kind).length > 0;
            }
            return this.openKinds.has(kind) || (this.path.kind === kind && !this.foldedOnPath.has(`kind:${kind}`));
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
        // folding takes it out of the owner's opened ones (and off the way
        // to the open page, for now); unfolding keeps it opened
        toggleKind(kind) {
            // while searching everything shows open: the folds wait
            if (searching(this.search)) {
                return;
            }
            const kinds = new Set(this.openKinds);
            const onPath = new Set(this.foldedOnPath);
            if (this.kindOpen(kind)) {
                kinds.delete(kind);
                if (this.path.kind === kind) {
                    onPath.add(`kind:${kind}`);
                }
            } else {
                kinds.add(kind);
                onPath.delete(`kind:${kind}`);
            }
            this.openKinds = kinds;
            this.foldedOnPath = onPath;
            this.keepFolds();
        },
        toggleEntry(id) {
            if (searching(this.search)) {
                return;
            }
            const entries = new Set(this.openEntries);
            const onPath = new Set(this.foldedOnPath);
            if (this.openedEntries.has(id)) {
                entries.delete(id);
                if (this.path.ids.has(id)) {
                    onPath.add(id);
                }
            } else {
                entries.add(id);
                onPath.delete(id);
            }
            this.openEntries = entries;
            this.foldedOnPath = onPath;
            this.keepFolds();
        },
        showAllOf(id) {
            this.showAll = new Set([...this.showAll, id]);
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

/* the window's height, whatever the page beside it: a flex child would
   otherwise stretch to the page and grow and shrink with it */
.world-list {
    width: 260px;
    flex: none;
    align-self: flex-start;
    background: rgb(var(--v-theme-surface));
    border-radius: 6px;
    overflow-y: auto;
    height: calc(100vh - 120px);
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

/* while searching, everything shows open and the folds wait */
.fold.off {
    opacity: 0.35;
    cursor: default;
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

</style>
