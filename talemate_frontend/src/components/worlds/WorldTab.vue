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
                        <span v-else class="text-caption text-muted">{{ (worlds.things[item.kind] || []).length }}</span>
                    </template>
                </v-list-item>
            </v-list>
        </div>

        <div class="main flex-grow-1 pa-4">
            <v-alert v-if="worlds.error" type="error" variant="tonal" density="compact" class="mb-3" closable @click:close="worlds.clearError()">
                {{ worlds.error }}
            </v-alert>

            <ThingPage v-if="worlds.selectedThingId" />
            <template v-else>
                <CreateBox :kind="kind" :key="kind" />
                <div v-if="!things.length" class="empty-hint pa-4 text-body-2">
                    No {{ info.label.toLowerCase() }} yet. Describe one above to create it.
                </div>
                <div v-else class="cards">
                    <v-card
                        v-for="thing in things"
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
            </template>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { TOP_KINDS, kindInfo } from './worldKinds.js';
import CreateBox from './CreateBox.vue';
import ThingPage from './ThingPage.vue';

// The World tab: the kind list (Characters, Species, Places, Lore;
// Cultures are made through the culture skill; races and mixes are reached
// from their species page), that kind's create box and its cards, or the
// open thing's page.
export default {
    name: 'WorldTab',
    components: { CreateBox, ThingPage },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            kind: 'character',
            kinds: TOP_KINDS,
        };
    },
    computed: {
        info() {
            return kindInfo(this.kind);
        },
        things() {
            return this.worlds.things[this.kind] || [];
        },
    },
    methods: {
        selectKind(kind) {
            this.kind = kind;
            this.worlds.closeThing();
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

.empty-hint {
    background: rgba(var(--v-theme-on-surface), 0.03);
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
    color: rgb(var(--v-theme-muted));
}
</style>
