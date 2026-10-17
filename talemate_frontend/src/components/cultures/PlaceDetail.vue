<template>
    <v-card variant="tonal" class="pa-4">
        <v-card-title class="d-flex align-center ga-2 flex-wrap pa-0 mb-2">
            <span class="text-h6 font-weight-regular">{{ local.name }}</span>
            <v-chip size="x-small" label color="teal" variant="tonal" prepend-icon="mdi-map-marker">
                {{ kindLabel(local.kind) }}
            </v-chip>
        </v-card-title>

        <v-card-text class="pa-0">
            <v-alert v-if="saveError" type="error" variant="tonal" density="compact" class="mb-3" closable @click:close="saveError = null">
                {{ saveError }}
            </v-alert>

            <v-row dense>
                <v-col cols="12" md="5">
                    <v-text-field
                        v-model="local.name"
                        label="Name"
                        density="compact"
                        variant="outlined"
                        hide-details
                        @blur="save()"
                    ></v-text-field>
                </v-col>
                <v-col cols="12" md="3">
                    <v-select
                        v-model="local.kind"
                        label="Kind"
                        :items="kindOptions"
                        item-title="title"
                        item-value="value"
                        density="compact"
                        variant="outlined"
                        hide-details
                        @update:model-value="save()"
                    ></v-select>
                </v-col>
                <v-col cols="12" md="4">
                    <v-select
                        v-model="local.parent_id"
                        label="Parent"
                        :items="parentOptions"
                        item-title="title"
                        item-value="value"
                        density="compact"
                        variant="outlined"
                        hide-details
                        @update:model-value="save()"
                    ></v-select>
                </v-col>
            </v-row>

            <div class="mt-4">
                <div class="text-caption text-muted text-uppercase mb-1">Cultures here</div>

                <div v-if="local.cultures.length === 0 && effectiveMix.length === 0" class="text-muted text-body-2">
                    No cultures set for this place, or any place it's in, yet.
                </div>

                <div v-else-if="local.cultures.length === 0" class="origin-box pa-3 mb-2 text-body-2">
                    No cultures of its own. Takes them from <strong>{{ sourceName }}</strong>.
                    <v-btn size="small" variant="tonal" class="ml-2" prepend-icon="mdi-content-copy" @click="setOwn()">
                        Set its own
                    </v-btn>
                </div>

                <div
                    v-for="cs in local.cultures"
                    :key="cs.culture_id"
                    class="d-flex align-center ga-3 mb-1"
                >
                    <span class="culture-chip" :style="chipStyle(cs.culture_id)">{{ cultureName(cs.culture_id) }}</span>
                    <v-slider
                        v-model="cs.share"
                        :min="0"
                        :max="100"
                        :step="1"
                        hide-details
                        density="compact"
                        :color="cultureColor(cs.culture_id)"
                        @end="onShareEnd(cs.culture_id, $event)"
                    ></v-slider>
                    <span class="text-muted share-value">{{ cs.share }}%</span>
                </div>

                <v-select
                    v-if="unusedCultures.length"
                    v-model="addCultureId"
                    label="Add culture"
                    :items="unusedCultures"
                    item-title="name"
                    item-value="id"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mt-2"
                    prepend-inner-icon="mdi-plus"
                    @update:model-value="addCulture()"
                ></v-select>
            </div>

            <div class="meaning-box text-body-2 mt-4 pa-3">
                <div class="text-caption text-muted text-uppercase mb-1">What this means in a scene here</div>
                {{ local.effective.description || 'No cultures set for this place, or any place it\'s in, yet.' }}
            </div>

            <v-alert v-if="local.unsure" type="warning" variant="tonal" density="compact" class="mt-3">
                The AI wasn't sure about this place{{ sourceName ? ` and took the cultures of ${sourceName}` : '' }}.
                Check it when you have a moment.
                <template v-slot:append>
                    <v-btn size="small" color="primary" variant="flat" prepend-icon="mdi-check" @click="looksRight()">
                        Looks right
                    </v-btn>
                </template>
            </v-alert>

            <v-textarea
                v-model="local.note"
                label="Note"
                rows="2"
                auto-grow
                density="compact"
                variant="outlined"
                hide-details
                class="mt-3"
                @blur="save()"
            ></v-textarea>

            <div v-if="local.kind === 'country'" class="empty-hint mt-3 pa-3">
                <v-icon size="small" class="mr-1">mdi-gavel</v-icon>
                <strong>Law &amp; governance</strong> belongs to the country, shared by every culture inside it.
                Coming in a later stage.
            </div>
            <div v-else-if="countryName" class="text-caption text-muted mt-3">
                <v-icon size="small" class="mr-1">mdi-gavel</v-icon>
                Law &amp; governance: from {{ countryName }}
            </div>

            <div class="text-caption text-muted mt-3">
                <v-icon size="small" class="mr-1">{{ local.set_by === 'ai' ? 'mdi-robot-outline' : 'mdi-pencil' }}</v-icon>
                {{ local.set_by === 'ai' ? "Worked out by the AI · change it any time" : "Set by you · the AI won't change it" }}
            </div>

            <div class="d-flex align-center mt-3 pt-3 actions-row">
                <v-spacer></v-spacer>
                <v-menu v-model="deleteMenu" :close-on-content-click="false">
                    <template v-slot:activator="{ props }">
                        <v-btn v-bind="props" size="small" variant="text" color="delete" prepend-icon="mdi-delete-outline">
                            Delete
                        </v-btn>
                    </template>
                    <v-card min-width="280" class="pa-3">
                        <div class="text-body-2 mb-2">Delete {{ local.name }}?</div>
                        <div v-if="children.length" class="text-body-2 mb-2">
                            {{ children.length }} place{{ children.length === 1 ? '' : 's' }} nested under it need a new parent:
                            <v-select
                                v-model="moveChildrenTo"
                                :items="moveChildrenOptions"
                                item-title="title"
                                item-value="value"
                                density="compact"
                                variant="outlined"
                                hide-details
                                class="mt-2"
                            ></v-select>
                        </div>
                        <div class="d-flex ga-2 justify-end">
                            <v-btn size="small" variant="text" @click="deleteMenu = false">Cancel</v-btn>
                            <v-btn size="small" color="delete" variant="flat" @click="confirmDelete()">Confirm</v-btn>
                        </div>
                    </v-card>
                </v-menu>
            </div>
        </v-card-text>
    </v-card>
</template>

<script>
import { dirtyLocalClone } from './dirtyLocalClone';
import { PLACE_KINDS, placeKindLabel } from './levelLabels';

export default {
    name: 'PlaceDetail',
    mixins: [
        dirtyLocalClone({
            watchPath: 'place',
            identity: vm => vm.place && vm.place.id,
        }),
    ],
    inject: [
        'registerMessageHandler',
        'unregisterMessageHandler',
    ],
    props: {
        place: {
            type: Object,
            required: true,
        },
        places: {
            type: Array,
            default: () => [],
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        send: {
            type: Function,
            required: true,
        },
    },
    data() {
        return {
            addCultureId: null,
            saveError: null,
            pendingSave: false,
            deleteMenu: false,
            moveChildrenTo: null,
        }
    },
    computed: {
        kindOptions() {
            return PLACE_KINDS.map(k => ({ title: placeKindLabel(k), value: k }));
        },
        effectiveMix() {
            return (this.local.effective && this.local.effective.mix) || [];
        },
        sourcePlace() {
            const sourceId = this.local.effective && this.local.effective.source_id;
            if (!sourceId) {
                return null;
            }
            return this.places.find(p => p.id === sourceId) || null;
        },
        sourceName() {
            return this.sourcePlace ? this.sourcePlace.name : '';
        },
        countryName() {
            const countryId = this.local.effective && this.local.effective.country_id;
            if (!countryId) {
                return '';
            }
            const country = this.places.find(p => p.id === countryId);
            return country ? country.name : '';
        },
        unusedCultures() {
            const present = new Set(this.local.cultures.map(cs => cs.culture_id));
            return this.cultures.filter(c => !present.has(c.id));
        },
        excludedParentIds() {
            // Self and every descendant: a parent choice would otherwise
            // create a cycle, which the server refuses anyway, but the
            // select shouldn't offer it in the first place.
            const excluded = new Set([this.local.id]);
            let added = true;
            while (added) {
                added = false;
                for (const p of this.places) {
                    if (p.parent_id && excluded.has(p.parent_id) && !excluded.has(p.id)) {
                        excluded.add(p.id);
                        added = true;
                    }
                }
            }
            return excluded;
        },
        parentOptions() {
            const options = [{ title: 'No parent (root)', value: null }];
            for (const p of this.places) {
                if (!this.excludedParentIds.has(p.id)) {
                    options.push({ title: p.name, value: p.id });
                }
            }
            return options;
        },
        children() {
            return this.places.filter(p => p.parent_id === this.local.id);
        },
        // Same exclusion as the parent select: a child being re-homed can't
        // go to the place being deleted or one of its own descendants.
        moveChildrenOptions() {
            return this.parentOptions;
        },
    },
    watch: {
        deleteMenu(open) {
            if (open) {
                this.moveChildrenTo = this.local.parent_id;
            }
        },
    },
    methods: {
        onLocalReset() {
            this.addCultureId = null;
            this.pendingSave = false;
        },
        kindLabel: placeKindLabel,
        cultureFor(cultureId) {
            return this.cultures.find(c => c.id === cultureId) || null;
        },
        cultureName(cultureId) {
            const culture = this.cultureFor(cultureId);
            return culture ? culture.name : cultureId;
        },
        cultureColor(cultureId) {
            const culture = this.cultureFor(cultureId);
            return culture ? culture.color : '#9E9E9E';
        },
        chipStyle(cultureId) {
            const color = this.cultureColor(cultureId);
            return { backgroundColor: `${color}33`, color };
        },
        beginSave() {
            this.saveError = null;
            this.pendingSave = true;
        },
        save() {
            this.beginSave();
            this.send('save_place', { place: this.local });
            this.clearLocalDirty();
        },
        onShareEnd(cultureId, value) {
            this.beginSave();
            this.send('save_place', {
                place: this.local,
                set_share: { culture_id: cultureId, share: Math.round(value) },
            });
            this.clearLocalDirty();
        },
        setOwn() {
            this.local.cultures = this.effectiveMix.map(cs => ({ ...cs }));
            this.save();
        },
        addCulture() {
            if (!this.addCultureId) {
                return;
            }
            const cultureId = this.addCultureId;
            this.addCultureId = null;
            this.beginSave();
            this.send('save_place', {
                place: this.local,
                set_share: { culture_id: cultureId, share: 20 },
            });
            this.clearLocalDirty();
        },
        looksRight() {
            this.local.unsure = false;
            this.save();
        },
        confirmDelete() {
            this.deleteMenu = false;
            this.beginSave();
            this.send('delete_place', {
                place_id: this.local.id,
                move_children_to: this.children.length ? this.moveChildrenTo : null,
            });
        },
        handleMessage(message) {
            if (message.type !== 'cultures' || message.action !== 'operation_done' || !message.error) {
                return;
            }
            if (!this.pendingSave) {
                return;
            }
            this.pendingSave = false;
            this.saveError = message.error.message;
        },
    },
    mounted() {
        this.registerMessageHandler(this.handleMessage);
    },
    unmounted() {
        this.unregisterMessageHandler(this.handleMessage);
    },
}
</script>

<style scoped>
.culture-chip {
    display: inline-flex;
    align-items: center;
    height: 22px;
    padding: 0 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    min-width: 90px;
    flex: none;
}

.share-value {
    min-width: 36px;
    text-align: right;
    font-variant-numeric: tabular-nums;
    flex: none;
}

.origin-box, .meaning-box {
    background: rgba(255, 255, 255, 0.04);
    border-radius: 4px;
}

.empty-hint {
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.3);
    border-radius: 6px;
    color: rgb(var(--v-theme-muted));
}

.actions-row {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
