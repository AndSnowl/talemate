<template>
    <div :style="{ maxWidth: MAX_CONTENT_WIDTH }">
        <CultureNoWorld
            v-if="!world.available"
            @world-state-manager-navigate="(tab, sub1, sub2, sub3) => $emit('world-state-manager-navigate', tab, sub1, sub2, sub3)"
        />
        <template v-else>
            <CulturePage
                v-if="selected && selected.type === 'culture' && selectedCulture"
                :culture="selectedCulture"
                :cultures="world.cultures || []"
                :places="world.places || []"
                :glossary="world.glossary || []"
                :send="send"
                :open-import="openImport"
                @open-places="select('places')"
            />
            <PlacesView
                v-else-if="selected && selected.type === 'places'"
                :places="world.places || []"
                :cultures="world.cultures || []"
                :selected-id="placesSelectedId"
                :send="send"
                @select="placesSelectedId = $event"
            ></PlacesView>
            <div v-else-if="selected && selected.type === 'unassigned'">
                <v-card variant="tonal" class="pa-4 mb-3">
                    <v-card-title class="pa-0">
                        <v-icon class="mr-2">mdi-help-circle-outline</v-icon>
                        Unassigned names
                    </v-card-title>
                    <v-card-text class="text-muted pa-0 mt-2">
                        Names the AI invented when no language fitted. They're kept here so they stay the same in
                        later stories. When you design a language for them, assign each one: keep it as it is, or
                        give it a proper name in the new language.
                    </v-card-text>
                </v-card>
                <GlossaryView
                    :entries="world.glossary || []"
                    :cultures="world.cultures || []"
                    :culture-id="null"
                    :selected-id="unassignedSelectedId"
                    :send="send"
                    @select="unassignedSelectedId = $event"
                ></GlossaryView>
            </div>
            <v-card v-else variant="tonal" class="pa-4">
                <v-card-text class="text-muted text-center">
                    No cultures yet. Use <strong>Import culture</strong> in the drawer on the left to add one.
                </v-card-text>
            </v-card>
        </template>

        <ImportCultureDialog v-model="importDialogOpen" :send="send"></ImportCultureDialog>
    </div>
</template>

<script>
import CultureNoWorld from './CultureNoWorld.vue';
import CulturePage from './CulturePage.vue';
import GlossaryView from './GlossaryView.vue';
import PlacesView from './PlacesView.vue';
import ImportCultureDialog from './ImportCultureDialog.vue';
import { MAX_CONTENT_WIDTH } from '@/constants/layout';

export default {
    name: 'WorldStateManagerCultures',
    components: {
        CultureNoWorld,
        CulturePage,
        GlossaryView,
        PlacesView,
        ImportCultureDialog,
    },
    inject: [
        'getWebsocket',
        'registerMessageHandler',
        'unregisterMessageHandler',
    ],
    emits: [
        'world-state-manager-navigate',
        'cultures-counts',
    ],
    data() {
        return {
            world: {
                available: false,
                world_name: null,
                cultures: [],
                places: [],
                glossary: [],
            },
            selected: null,
            counts: {},
            unassignedSelectedId: null,
            placesSelectedId: null,
            importDialogOpen: false,
            MAX_CONTENT_WIDTH,
        }
    },
    computed: {
        selectedCulture() {
            if (!this.selected || this.selected.type !== 'culture') {
                return null;
            }
            return (this.world.cultures || []).find(c => c.id === this.selected.id) || null;
        },
    },
    methods: {
        select(type, id) {
            // Guard against reassigning an equivalent selection: the drawer
            // echoes this back through its own `selected` watcher (see
            // WorldStateManagerMenuCulturesTools.vue), and an unconditional
            // reassignment here would hand back a new object every time,
            // re-triggering that watcher (and this one) forever.
            if (this.selected && this.selected.type === type && this.selected.id === id) {
                return;
            }
            this.selected = { type, id };
        },

        send(action, data) {
            this.getWebsocket().send(JSON.stringify({
                type: 'cultures',
                action,
                ...(data || {}),
            }));
        },

        openImport() {
            this.importDialogOpen = true;
        },

        shareState() {
            // No-op hook, kept for parity with the other World Editor tools.
            // The drawer reads state straight off `tool` (this component).
        },

        ensureSelection() {
            if (!this.world.available) {
                return;
            }

            const cultures = this.world.cultures || [];

            if (this.selected) {
                if (this.selected.type === 'culture') {
                    if (cultures.some(c => c.id === this.selected.id)) {
                        return;
                    }
                } else {
                    // 'places' / 'unassigned' selections stay valid across world updates.
                    return;
                }
            }

            this.selected = cultures.length ? { type: 'culture', id: cultures[0].id } : null;
        },

        downloadExport(data) {
            const blob = new Blob([data.content], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = data.filename || 'culture.json';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        },

        handleMessage(message) {
            if (message.type !== 'cultures') {
                return;
            }

            if (message.action === 'world') {
                this.world = message.data;
                this.counts = message.data.counts || {};
                this.$emit('cultures-counts', this.counts);
                this.ensureSelection();
            } else if (message.action === 'exported') {
                this.downloadExport(message.data);
            }
        },
    },
    mounted() {
        this.registerMessageHandler(this.handleMessage);
        this.send('get_world');
    },
    unmounted() {
        this.unregisterMessageHandler(this.handleMessage);
    },
}
</script>
