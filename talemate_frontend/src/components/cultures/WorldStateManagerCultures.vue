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
            <v-card v-else-if="selected && selected.type === 'places'" variant="tonal" class="pa-4">
                <v-card-title>
                    <v-icon class="mr-2">mdi-map-marker-radius-outline</v-icon>
                    Places &amp; regions
                </v-card-title>
                <v-card-text class="text-muted">
                    Place management is coming in a later update.
                </v-card-text>
            </v-card>
            <v-card v-else-if="selected && selected.type === 'unassigned'" variant="tonal" class="pa-4">
                <v-card-title>
                    <v-icon class="mr-2">mdi-help-circle-outline</v-icon>
                    Unassigned names
                </v-card-title>
                <v-card-text class="text-muted">
                    Reviewing unassigned names is coming in a later update.
                </v-card-text>
            </v-card>
            <v-card v-else variant="tonal" class="pa-4">
                <v-card-text class="text-muted text-center">
                    No cultures yet. Use <strong>Import culture</strong> in the drawer on the left to add one.
                </v-card-text>
            </v-card>
        </template>
    </div>
</template>

<script>
import CultureNoWorld from './CultureNoWorld.vue';
import CulturePage from './CulturePage.vue';
import { MAX_CONTENT_WIDTH } from '@/constants/layout';

export default {
    name: 'WorldStateManagerCultures',
    components: {
        CultureNoWorld,
        CulturePage,
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
                counts: {},
            },
            selected: null,
            counts: {},
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
            // Task 10 wires up the actual import dialog.
            console.info('WorldStateManagerCultures: import dialog not implemented yet (Task 10)');
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
