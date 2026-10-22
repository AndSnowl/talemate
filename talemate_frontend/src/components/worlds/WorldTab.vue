<template>
    <div class="world-tab d-flex" data-testid="world-tab">
        <div class="kinds pa-2">
            <div class="text-overline text-muted px-2 world-title">{{ worlds.currentWorld?.name }}</div>
            <v-list density="compact" bg-color="transparent" nav>
                <v-list-item
                    v-for="item in kinds"
                    :key="item.kind"
                    :active="!item.viaSkill && item.kind === kind"
                    :disabled="item.viaSkill"
                    color="accent"
                    :prepend-icon="item.icon"
                    :data-testid="'kind-' + item.kind"
                    @click="selectKind(item.kind)"
                >
                    <v-list-item-title>{{ item.label }}</v-list-item-title>
                    <template #append>
                        <span v-if="item.viaSkill" class="text-caption text-muted">via skill</span>
                        <span v-else class="text-caption text-muted">{{ entriesOf(item.kind).length }}</span>
                    </template>
                </v-list-item>
                <v-divider class="my-1"></v-divider>
                <v-list-item
                    :active="kind === stubsTab.kind"
                    color="accent"
                    :prepend-icon="stubsTab.icon"
                    :data-testid="'kind-' + stubsTab.kind"
                    @click="selectKind(stubsTab.kind)"
                >
                    <v-list-item-title>{{ stubsTab.label }}</v-list-item-title>
                    <template #append>
                        <span class="text-caption text-muted">{{ liveStubCount }}</span>
                    </template>
                </v-list-item>
            </v-list>
        </div>

        <div class="main flex-grow-1 pa-4">
            <ExpandAskDialog />
            <v-alert v-if="worlds.error" type="error" variant="tonal" density="compact" class="mb-3" closable @click:close="worlds.clearError()">
                {{ worlds.error }}
            </v-alert>

            <ThingPage v-if="worlds.selectedThingId" />
            <StubsTab v-else-if="kind === stubsTab.kind" />
            <template v-else>
                <CreateBox :kind="kind" :key="kind" />
                <div v-if="!entries.length && !(kind === 'sphere' && stubs.length)" class="empty-hint pa-4 text-body-2">
                    No {{ info.label.toLowerCase() }} yet. Describe one above to create it.
                </div>
                <!-- the Spheres list: grouped by template, stubs dimmed among them -->
                <template v-else-if="kind === 'sphere'">
                    <div v-for="group in sphereGroups" :key="group.template" class="sphere-group mb-3" data-testid="sphere-group">
                        <div class="text-overline text-muted">{{ group.label }}</div>
                        <div class="cards">
                            <v-card
                                v-for="thing in group.things"
                                :key="thing.id"
                                variant="flat"
                                class="thing-card pa-3"
                                :class="{ stub: thing.stub }"
                                :data-testid="thing.stub ? 'stub-item' : 'thing-card'"
                                @click="worlds.openThing(thing.id)"
                            >
                                <div class="d-flex align-center ga-2">
                                    <v-icon size="small" color="muted">{{ thing.kind === 'place' ? placeIcon : info.icon }}</v-icon>
                                    <span :class="thing.stub ? 'stub-name' : 'card-name'">{{ thing.name }}</span>
                                    <span v-if="thing.stub" class="text-caption text-muted text-no-wrap">not made yet</span>
                                </div>
                            </v-card>
                        </div>
                    </div>
                </template>
                <div v-else class="cards">
                    <v-card
                        v-for="thing in entries"
                        :key="thing.id"
                        variant="flat"
                        class="thing-card pa-3"
                        data-testid="thing-card"
                        @click="worlds.openThing(thing.id)"
                    >
                        <div class="d-flex align-center ga-2">
                            <v-icon size="small" color="muted">{{ info.icon }}</v-icon>
                            <span class="card-name">{{ thing.name }}</span>
                        </div>
                    </v-card>
                </div>
                <template v-if="stubs.length && kind !== 'sphere'">
                    <div class="text-overline text-muted mt-4">Stubs</div>
                    <div class="cards stubs" data-testid="kind-stubs-list">
                        <v-card
                            v-for="thing in stubs"
                            :key="thing.id"
                            variant="flat"
                            class="thing-card stub pa-3"
                            data-testid="stub-item"
                            @click="worlds.openThing(thing.id)"
                        >
                            <div class="d-flex align-center ga-2">
                                <v-icon size="small" color="muted">{{ info.icon }}</v-icon>
                                <span class="stub-name">{{ thing.name }}</span>
                                <span class="text-caption text-muted text-no-wrap">not made yet</span>
                            </div>
                        </v-card>
                    </div>
                </template>
            </template>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { STUBS_TAB, TOP_KINDS, kindInfo, sphereGroups } from './worldKinds.js';
import CreateBox from './CreateBox.vue';
import ExpandAskDialog from './ExpandAskDialog.vue';
import StubsTab from './StubsTab.vue';
import ThingPage from './ThingPage.vue';

// The World tab: the kind list (Characters, Species, Places, Events,
// Items, Lore, Spheres; Cultures are made through the culture skill; races and
// mixes are reached from their species page) and the Stubs tab below it;
// a kind's create box, its cards and, dimmed under "Stubs", the stubs of
// that kind; or the open thing's page. Expanding a stub (`expanding`)
// switches to its kind, whose create box takes it up, and "Make it a
// sphere…" (`promoting`) to Spheres. Spheres are listed by template
// (`sphereGroups`), place spheres among them, their stubs dimmed in place.
// The open section is the store's `section`, so the thing page's back
// arrow can return to a list or the Stubs page (`worlds.goBack`).
export default {
    name: 'WorldTab',
    components: { CreateBox, ExpandAskDialog, StubsTab, ThingPage },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            kinds: TOP_KINDS,
            stubsTab: STUBS_TAB,
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
        entries() {
            return this.entriesOf(this.kind);
        },
        stubs() {
            return (this.worlds.things[this.kind] || []).filter((thing) => thing.stub);
        },
        sphereGroups() {
            return sphereGroups(this.worlds.things.sphere);
        },
        placeIcon() {
            return kindInfo('place').icon;
        },
        liveStubCount() {
            return this.worlds.stubs.filter((stub) => !stub.ignored).length;
        },
    },
    watch: {
        'worlds.expanding'(stub) {
            if (stub) {
                this.worlds.section = stub.kind;
            }
        },
        // "Make it a sphere…" promotes in the Spheres create box
        'worlds.promoting'(thing) {
            if (thing) {
                this.worlds.section = 'sphere';
            }
        },
    },
    methods: {
        // a kind's full entries, not its stubs
        entriesOf(kind) {
            return (this.worlds.things[kind] || []).filter((thing) => !thing.stub);
        },
        selectKind(kind) {
            this.worlds.showSection(kind);
            if (this.worlds.expanding && this.worlds.expanding.kind !== kind) {
                this.worlds.stopExpanding();
            }
            if (this.worlds.promoting && kind !== 'sphere') {
                this.worlds.stopPromoting();
            }
        },
    },
};
</script>

<style scoped>
.world-tab {
    min-height: 100%;
}

.kinds {
    width: 200px;
    flex: none;
    background: rgb(var(--v-theme-surface));
    border-radius: 6px;
}

.world-title {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}

.cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
}

.thing-card {
    background: rgb(var(--v-theme-raised));
}

.card-name {
    color: rgb(var(--v-theme-accent));
    font-weight: 600;
}

.thing-card.stub {
    opacity: 0.6;
    background: transparent;
    border: 1px dashed rgb(var(--v-theme-border));
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
