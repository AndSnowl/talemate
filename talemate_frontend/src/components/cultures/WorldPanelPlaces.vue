<template>
    <div>
        <v-expansion-panels density="compact" v-for="(place, name) in places" :key="name">
            <v-expansion-panel rounded="0" density="compact">
                <v-expansion-panel-title class="text-subtitle-2" diable-icon-rotate>
                    {{ name }}
                    <CultureChip kind="place" :name="name" class="ml-1" />
                    <template v-slot:actions>
                        <v-icon icon="mdi-map-marker"></v-icon>
                    </template>
                </v-expansion-panel-title>

                <v-expansion-panel-text class="text-body-2">
                    {{ place.snapshot }}
                </v-expansion-panel-text>
            </v-expansion-panel>
        </v-expansion-panels>
    </div>
</template>

<script>
import CultureChip from './CultureChip.vue';

// The World panel's "places" section (Task 8): one row per
// `world_state.places` entry, each with its culture chip and the
// place's snapshot text — the same expansion-panel shape as the
// characters/objects sections above it in WorldState.vue.
export default {
    name: 'WorldPanelPlaces',
    components: {
        CultureChip,
    },
    props: {
        places: {
            type: Object,
            default: () => ({}),
        },
    },
};
</script>
