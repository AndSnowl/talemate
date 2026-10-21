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
                    @click="creating = section.kind"
                >New {{ section.kind }}</v-btn>
            </div>
            <CreateBox
                v-if="creating === section.kind"
                :kind="section.kind"
                :preset="section.preset"
                cancellable
                @cancel="creating = null"
            />
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
import CreateBox from './CreateBox.vue';

// A species page's Races and Mixes: the races of the species and every mix
// descending from it (a mix shows on each of its species), each opening
// its page. "+ New race" and "+ New mix" open a create box with this
// species as the race's species or the mix's first parent; accepting opens
// the new page.
export default {
    name: 'HeritageSections',
    components: { CreateBox },
    props: {
        speciesId: { type: String, required: true },
        races: { type: Array, required: true },
        mixes: { type: Array, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // the kind whose create box is open, if any
            creating: null,
        };
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
                    preset: { species: this.speciesId },
                },
                {
                    key: 'mixes',
                    kind: 'mix',
                    label: 'Mixes',
                    icon: kindInfo('mix').icon,
                    items: this.mixes,
                    preset: { parents: [this.speciesId] },
                },
            ];
        },
    },
    watch: {
        // another species page
        speciesId() {
            this.creating = null;
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
