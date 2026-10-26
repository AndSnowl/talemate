<template>
    <div class="heritage-sections">
        <div v-for="section in sections" :key="section.key" class="mt-4" :data-testid="section.key + '-section'">
            <div class="d-flex align-center">
                <span class="text-overline text-muted">{{ section.label }}</span>
                <v-spacer></v-spacer>
                <v-btn
                    v-if="creating !== section.kind"
                    variant="text"
                    size="small"
                    color="accent"
                    prepend-icon="mdi-plus"
                    @click="$emit('create', section.kind)"
                >New {{ section.kind }}</v-btn>
            </div>
            <div v-if="!section.items.length" class="text-body-2 text-muted">No {{ section.label.toLowerCase() }} yet.</div>
            <div v-else class="cards">
                <v-card
                    v-for="item in section.items"
                    :key="item.id"
                    variant="flat"
                    class="member-card pa-2"
                    @click="worlds.openThing(item.id)"
                >
                    <v-icon size="small" color="muted" class="mr-1">{{ section.icon }}</v-icon>
                    <span class="card-name">{{ item.name }}</span>
                </v-card>
            </div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { kindInfo } from './worldKinds.js';

// A species page's Races and Mixes: the races of the species and every mix
// descending from it (a mix shows on each of its species), each opening
// its page. "+ New race" and "+ New mix" open a create box with this
// species as the race's species or the mix's first parent; accepting opens
// the new page. The box itself (sized to the entry's full width, so a
// draft gets the same two-column layout as any entry page) is the
// caller's: `creating` is the kind it's showing (or none), and "+ New
// race"/"+ New mix" only ask for it (`create`).
export default {
    name: 'HeritageSections',
    props: {
        speciesId: { type: String, required: true },
        races: { type: Array, required: true },
        mixes: { type: Array, required: true },
        // the kind the caller's create box is showing, if any
        creating: { type: String, default: null },
    },
    emits: ['create'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        sections() {
            return [
                {
                    key: 'races',
                    kind: 'race',
                    label: 'Races',
                    icon: kindInfo('race').icon,
                    items: this.races,
                },
                {
                    key: 'mixes',
                    kind: 'mix',
                    label: 'Mixes',
                    icon: kindInfo('mix').icon,
                    items: this.mixes,
                },
            ];
        },
    },
};
</script>

<style scoped>
.cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 8px;
}

.member-card {
    background: rgb(var(--v-theme-raised));
}

.card-name {
    color: rgb(var(--v-theme-accent));
    font-weight: 600;
}
</style>
