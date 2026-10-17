<template>
    <v-list density="compact" slim>
        <v-list-subheader color="grey">
            <v-icon color="primary" class="mr-1">mdi-plus</v-icon>
            Create
        </v-list-subheader>
        <v-list-item @click.stop="tool && tool.openImport()">
            <template v-slot:prepend>
                <v-icon color="primary">mdi-file-upload-outline</v-icon>
            </template>
            <v-list-item-title>Import culture</v-list-item-title>
        </v-list-item>
    </v-list>

    <v-list selectable slim density="compact" color="secondary" v-model:selected="selected">

        <v-list-subheader color="grey">
            Cultures ({{ cultures.length }})
        </v-list-subheader>
        <v-list-item
            v-for="culture in cultures"
            :key="culture.id"
            :value="`culture:${culture.id}`"
        >
            <template v-slot:prepend>
                <span class="culture-swatch" :style="{ backgroundColor: culture.color }"></span>
            </template>
            <v-list-item-title>{{ culture.name }}</v-list-item-title>
            <v-list-item-subtitle>{{ cultureSubtitle(culture) }}</v-list-item-subtitle>
            <template v-slot:append>
                <v-badge
                    v-if="unreviewedForCulture(culture.id) > 0"
                    inline
                    color="unsaved"
                    :content="String(unreviewedForCulture(culture.id))"
                ></v-badge>
            </template>
        </v-list-item>
        <v-card v-if="cultures.length === 0" class="ma-2 text-muted" variant="text">
            <v-card-text>No cultures yet</v-card-text>
        </v-card>

        <v-divider class="my-2"></v-divider>
        <v-list-subheader color="grey">Where they live</v-list-subheader>
        <v-list-item value="places" prepend-icon="mdi-map-marker-outline">
            <v-list-item-title>Places &amp; regions</v-list-item-title>
            <template v-slot:append>
                <v-badge
                    v-if="unsurePlaces > 0"
                    inline
                    color="unsaved"
                    :content="String(unsurePlaces)"
                ></v-badge>
            </template>
        </v-list-item>

        <v-divider class="my-2"></v-divider>
        <v-list-subheader color="grey">Not yet in a language</v-list-subheader>
        <v-list-item value="unassigned" prepend-icon="mdi-help-circle-outline">
            <v-list-item-title>Unassigned names</v-list-item-title>
            <template v-slot:append>
                <v-badge
                    v-if="unreviewedUnassigned > 0"
                    inline
                    color="unsaved"
                    :content="String(unreviewedUnassigned)"
                ></v-badge>
            </template>
        </v-list-item>

        <v-divider class="my-2"></v-divider>
        <v-list-item v-if="worldName">
            <v-list-item-subtitle class="text-caption text-muted">
                Shared world: {{ worldName }}
            </v-list-item-subtitle>
        </v-list-item>
    </v-list>
</template>

<script>
import { levelLabel } from './levelLabels';

export default {
    name: 'WorldStateManagerMenuCulturesTools',
    props: {
        scene: Object,
        manager: Object,
        tool: Object,
    },
    data() {
        return {
            selected: [],
        }
    },
    computed: {
        cultures() {
            return (this.tool && this.tool.world && this.tool.world.cultures) || [];
        },
        counts() {
            return (this.tool && this.tool.counts) || {};
        },
        unsurePlaces() {
            return this.counts.unsure_places || 0;
        },
        unreviewedUnassigned() {
            return this.counts.unreviewed_unassigned || 0;
        },
        worldName() {
            return this.tool && this.tool.world && this.tool.world.world_name;
        },
    },
    watch: {
        'tool.selected': {
            immediate: true,
            deep: true,
            handler(sel) {
                this.selected = sel ? [this.keyFor(sel)] : [];
            },
        },
        selected(val) {
            if (!this.tool || !val || val.length === 0) {
                return;
            }
            const key = val[0];
            if (key === 'places') {
                this.tool.select('places');
            } else if (key === 'unassigned') {
                this.tool.select('unassigned');
            } else if (typeof key === 'string' && key.startsWith('culture:')) {
                this.tool.select('culture', key.slice('culture:'.length));
            }
        },
    },
    methods: {
        keyFor(sel) {
            if (sel.type === 'culture') {
                return `culture:${sel.id}`;
            }
            return sel.type;
        },
        unreviewedForCulture(cultureId) {
            const glossaryCount = (this.counts.unreviewed_by_culture || {})[cultureId] || 0;
            const additionsCount = (this.counts.unreviewed_additions_by_culture || {})[cultureId] || 0;
            return glossaryCount + additionsCount;
        },
        cultureSubtitle(culture) {
            let subtitle = `speaks ${culture.language.name} · ${levelLabel(culture.language.level)}`;
            if (!culture.language.writable) {
                subtitle += ", can't be written";
            }
            return subtitle;
        },
    },
}
</script>

<style scoped>
.culture-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 3px;
    flex: none;
}
</style>
