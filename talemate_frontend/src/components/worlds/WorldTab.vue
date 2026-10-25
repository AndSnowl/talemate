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
                class="px-1 mb-2"
                data-testid="world-search"
            ></v-text-field>
            <div v-for="item in kinds" :key="item.kind" class="kind-group">
                <div v-if="item.viaSkill" class="kind-head disabled d-flex align-center ga-2" :data-testid="'kind-' + item.kind">
                    <v-icon size="small">{{ item.icon }}</v-icon>
                    <span class="flex-grow-1">{{ item.label }}</span>
                    <span class="text-caption text-muted">via skill</span>
                </div>
                <div
                    v-else
                    class="kind-head d-flex align-center ga-2"
                    :class="{ active: !worlds.selectedThingId && item.kind === kind }"
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
                    <v-icon size="x-small" class="new-icon" :title="'New ' + item.singular">mdi-plus</v-icon>
                </div>
                <div
                    v-for="row in listOf(item.kind)"
                    :key="row.thing.id"
                    class="list-item d-flex align-center ga-1"
                    :class="{ stub: row.thing.stub, active: row.thing.id === worlds.selectedThingId }"
                    :style="{ paddingLeft: 22 + row.depth * 14 + 'px' }"
                    :data-testid="row.thing.stub ? 'stub-item' : 'thing-card'"
                    role="button"
                    tabindex="0"
                    @click="worlds.openThing(row.thing.id)"
                    @keydown.enter.prevent="worlds.openThing(row.thing.id)"
                    @keydown.space.prevent="worlds.openThing(row.thing.id)"
                >
                    <span :class="row.thing.stub ? 'stub-name' : 'card-name'">{{ row.thing.name }}</span>
                    <span v-if="row.thing.stub" class="text-caption text-muted text-no-wrap">not made yet</span>
                </div>
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
import { kindList } from './entryPage.js';
import { SETTINGS_TAB, STUBS_TAB, TAGS_TAB, TOP_KINDS, kindInfo } from './worldKinds.js';
import CreateBox from './CreateBox.vue';
import CurationSettings from './CurationSettings.vue';
import ExpandAskDialog from './ExpandAskDialog.vue';
import StubsTab from './StubsTab.vue';
import TagsTab from './TagsTab.vue';
import ThingPage from './ThingPage.vue';

// The World tab, in two panes (spec "The pages"): the list and the page.
// The list has a search box, then the world's entries by kind (Characters,
// Species, Places, Events, Items, Lore, Beings; races and mixes are reached
// from their species page; Cultures are made through the culture skill),
// each name opening its page; a place sits
// indented under its most precise filed place (`kindList`), and a kind's
// stubs come last, dimmed, "not made yet". Stubs, Tags and Settings sit at
// the bottom. A kind's heading opens its create box on the page side.
// Expanding a stub (`expanding`) switches to its kind, whose create box
// takes it up. The open section is the store's `section`, so the page's
// back arrow can return to a section (`worlds.goBack`). The notes a reply
// brings (what an accept, a move, a merge or a date pick left out, and
// why) show above the page until closed.
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
        liveStubCount() {
            return this.worlds.stubs.filter((stub) => !stub.ignored).length;
        },
    },
    watch: {
        // another world: the search starts afresh
        'worlds.currentWorld.id'() {
            this.query = '';
        },
    },
    methods: {
        // a kind's full entries, not its stubs
        entriesOf(kind) {
            return (this.worlds.things[kind] || []).filter((thing) => !thing.stub);
        },
        // the list's rows of a kind, for the search typed
        listOf(kind) {
            return kindList(this.worlds.things[kind], this.query || '', { nest: kind === 'place' });
        },
        selectKind(kind) {
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
