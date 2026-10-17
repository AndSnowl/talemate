<template>
    <div>
        <v-card class="mb-2">
            <v-card-text class="d-flex align-start flex-wrap ga-2">
                <div class="flex-grow-1" style="min-width: 240px">
                    <div class="text-h6 font-weight-regular mb-1">Places &amp; regions</div>
                    <div class="text-muted text-body-2">
                        Cultures sit on places as well as people. The most local place with cultures set decides who
                        you meet there; places without their own take them from the place they're in. A place can
                        hold several cultures, each with its share of the mix.
                    </div>
                </div>
                <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" @click="openAddPlace()">
                    Add place
                </v-btn>
            </v-card-text>
        </v-card>

        <v-row>
            <v-col cols="12" md="7">
                <div v-if="orderedPlaces.length === 0" class="text-center text-muted pa-8">
                    No places yet. Use <strong>Add place</strong> to start one.
                </div>
                <v-table v-else density="compact">
                    <thead>
                        <tr>
                            <th>Place</th>
                            <th>Cultures</th>
                            <th style="width: 34%">Mix</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="row in orderedPlaces"
                            :key="row.id"
                            class="place-row"
                            :class="{ 'place-row-selected': row.id === localSelectedId }"
                            @click="localSelectedId = row.id"
                        >
                            <td :style="{ paddingLeft: (12 + row.depth * 20) + 'px' }">
                                <v-icon v-if="row.depth" size="x-small" color="muted" class="mr-1">mdi-subdirectory-arrow-right</v-icon>
                                <span v-if="row.unsure" class="unrev-dot mr-1" title="AI unsure"></span>
                                {{ row.name }}
                                <span class="text-muted text-caption ml-1">{{ kindLabel(row.kind) }}</span>
                            </td>
                            <td>
                                <template v-if="row.cultures.length">
                                    <span
                                        v-for="cs in row.cultures"
                                        :key="cs.culture_id"
                                        class="culture-chip mr-1"
                                        :style="chipStyle(cs.culture_id)"
                                    >
                                        {{ cultureName(cs.culture_id) }}
                                    </span>
                                </template>
                                <span v-else class="text-muted text-caption">
                                    {{ sourceNameFor(row) ? `from ${sourceNameFor(row)}` : '—' }}
                                </span>
                            </td>
                            <td>
                                <CultureMixBar :mix="row.effective.mix" :cultures="cultures" />
                            </td>
                        </tr>
                    </tbody>
                </v-table>
            </v-col>

            <v-col cols="12" md="5">
                <PlaceDetail
                    v-if="selectedPlace"
                    :key="selectedPlace.id"
                    :place="selectedPlace"
                    :places="places"
                    :cultures="cultures"
                    :send="send"
                ></PlaceDetail>
            </v-col>
        </v-row>

        <v-dialog v-model="addPlaceDialog" max-width="480px">
            <v-card>
                <v-card-title>Add place</v-card-title>
                <v-card-text>
                    <v-text-field
                        v-model="newPlace.name"
                        label="Name"
                        density="compact"
                        variant="outlined"
                        autofocus
                        class="mb-2"
                    ></v-text-field>
                    <v-select
                        v-model="newPlace.kind"
                        label="Kind"
                        :items="kindOptions"
                        item-title="title"
                        item-value="value"
                        density="compact"
                        variant="outlined"
                        class="mb-2"
                    ></v-select>
                    <v-select
                        v-model="newPlace.parent_id"
                        label="Parent"
                        :items="parentOptions"
                        item-title="title"
                        item-value="value"
                        density="compact"
                        variant="outlined"
                    ></v-select>
                </v-card-text>
                <v-card-actions>
                    <v-spacer></v-spacer>
                    <v-btn variant="text" @click="addPlaceDialog = false">Cancel</v-btn>
                    <v-btn color="primary" variant="flat" :disabled="!newPlace.name" @click="submitAddPlace()">
                        Add
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script>
import PlaceDetail from './PlaceDetail.vue';
import CultureMixBar from './CultureMixBar.vue';
import { PLACE_KINDS, placeKindLabel } from './levelLabels';

export default {
    name: 'PlacesView',
    components: {
        PlaceDetail,
        CultureMixBar,
    },
    props: {
        places: {
            type: Array,
            default: () => [],
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        selectedId: {
            type: String,
            default: null,
        },
        send: {
            type: Function,
            required: true,
        },
    },
    emits: [
        'select',
    ],
    data() {
        return {
            localSelectedId: this.selectedId,
            addPlaceDialog: false,
            newPlace: { name: '', kind: 'town', parent_id: null },
        }
    },
    computed: {
        orderedPlaces() {
            const byParent = new Map();
            const validIds = new Set(this.places.map(p => p.id));
            for (const place of this.places) {
                const key = (place.parent_id && validIds.has(place.parent_id)) ? place.parent_id : null;
                if (!byParent.has(key)) {
                    byParent.set(key, []);
                }
                byParent.get(key).push(place);
            }

            const result = [];
            const walk = (parentId, depth) => {
                for (const place of (byParent.get(parentId) || [])) {
                    result.push({ ...place, depth });
                    walk(place.id, depth + 1);
                }
            };
            walk(null, 0);
            return result;
        },
        selectedPlace() {
            if (this.localSelectedId) {
                const found = this.places.find(p => p.id === this.localSelectedId);
                if (found) {
                    return found;
                }
            }
            return this.places.length ? this.places[0] : null;
        },
        kindOptions() {
            return PLACE_KINDS.map(k => ({ title: placeKindLabel(k), value: k }));
        },
        parentOptions() {
            const options = [{ title: 'No parent (root)', value: null }];
            for (const p of this.places) {
                options.push({ title: p.name, value: p.id });
            }
            return options;
        },
    },
    watch: {
        selectedId(id) {
            this.localSelectedId = id;
        },
        localSelectedId(id) {
            this.$emit('select', id);
        },
        places: {
            handler() {
                if (this.localSelectedId && !this.places.some(p => p.id === this.localSelectedId)) {
                    this.localSelectedId = this.places.length ? this.places[0].id : null;
                }
            },
        },
    },
    methods: {
        kindLabel: placeKindLabel,
        cultureFor(cultureId) {
            return this.cultures.find(c => c.id === cultureId) || null;
        },
        cultureName(cultureId) {
            const culture = this.cultureFor(cultureId);
            return culture ? culture.name : cultureId;
        },
        chipStyle(cultureId) {
            const culture = this.cultureFor(cultureId);
            const color = culture ? culture.color : '#9E9E9E';
            return { backgroundColor: `${color}33`, color };
        },
        sourceNameFor(row) {
            const sourceId = row.effective && row.effective.source_id;
            if (!sourceId) {
                return '';
            }
            const source = this.places.find(p => p.id === sourceId);
            return source ? source.name : '';
        },
        openAddPlace() {
            this.newPlace = { name: '', kind: 'town', parent_id: null };
            this.addPlaceDialog = true;
        },
        submitAddPlace() {
            if (!this.newPlace.name) {
                return;
            }
            this.send('save_place', {
                place: {
                    id: '',
                    name: this.newPlace.name,
                    kind: this.newPlace.kind,
                    parent_id: this.newPlace.parent_id,
                },
            });
            this.addPlaceDialog = false;
        },
    },
}
</script>

<style scoped>
.place-row {
    cursor: pointer;
}

.place-row:hover {
    background: rgba(255, 255, 255, 0.035);
}

.place-row-selected {
    background: rgba(255, 255, 255, 0.07);
}

.unrev-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: rgb(var(--v-theme-unsaved));
    vertical-align: middle;
}

.culture-chip {
    display: inline-flex;
    align-items: center;
    height: 20px;
    padding: 0 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
}
</style>
