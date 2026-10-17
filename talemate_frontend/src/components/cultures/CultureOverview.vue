<template>
    <div class="culture-overview">
        <v-row>
            <v-col cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">Who they are</v-card-title>
                    <v-card-text>
                        <v-textarea
                            v-model="local.description"
                            rows="4"
                            auto-grow
                            hide-details
                            variant="outlined"
                            density="compact"
                            label="Description"
                            @blur="save()"
                        ></v-textarea>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">Where they live</v-card-title>
                    <v-card-text>
                        <div v-if="placesForCulture.length === 0" class="text-muted text-caption mb-2">
                            No places carry this culture yet.
                        </div>
                        <div v-for="place in placesForCulture" :key="place.id" class="mb-3">
                            <div class="d-flex justify-space-between text-body-2">
                                <span>{{ place.name }} <span class="text-muted text-caption">{{ place.kind }}</span></span>
                                <span class="text-muted text-caption">{{ shareFor(place) }}%</span>
                            </div>
                            <div class="mix-bar">
                                <span
                                    v-for="cs in place.cultures"
                                    :key="cs.culture_id"
                                    :style="{ width: cs.share + '%', backgroundColor: colorFor(cs.culture_id) }"
                                ></span>
                            </div>
                        </div>
                        <v-btn variant="text" size="small" prepend-icon="mdi-map-marker-outline" @click="$emit('open-places')">
                            All places
                        </v-btn>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">Language</v-card-title>
                    <v-card-text>
                        <div class="d-flex align-center ga-2 mb-2">
                            <span class="text-body-1">{{ culture.language.name }}</span>
                            <v-chip size="x-small" label color="primary" variant="tonal">{{ levelLabel }}</v-chip>
                        </div>
                        <div class="text-muted text-caption mb-2">{{ soundPreview }}</div>
                        <v-btn variant="tonal" size="small" prepend-icon="mdi-translate" @click="$emit('open-language')">
                            Open language
                        </v-btn>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">
                        <v-icon size="small" class="mr-1">mdi-party-popper</v-icon>
                        Customs
                    </v-card-title>
                    <v-card-text>
                        <div v-for="(custom, i) in local.customs" :key="i" class="d-flex align-center ga-1 mb-1">
                            <v-text-field
                                v-model="local.customs[i]"
                                density="compact"
                                variant="outlined"
                                hide-details
                                @blur="save()"
                            ></v-text-field>
                            <v-btn icon size="small" variant="text" @click="removeCustom(i)">
                                <v-icon size="small" color="delete">mdi-close</v-icon>
                            </v-btn>
                        </div>
                        <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addCustom()">
                            Add custom
                        </v-btn>

                        <div v-for="addition in additionsFor('customs')" :key="addition.id" class="addition-box mt-3 pa-2" :class="{ 'addition-unreviewed': addition.status === 'unreviewed' }">
                            <v-textarea
                                v-model="additionEdits[addition.id]"
                                rows="2"
                                auto-grow
                                density="compact"
                                variant="outlined"
                                hide-details
                                class="mb-1"
                            ></v-textarea>
                            <div class="d-flex align-center ga-2">
                                <v-chip v-if="addition.status === 'unreviewed'" size="x-small" color="unsaved" variant="tonal">
                                    Not reviewed
                                </v-chip>
                                <v-spacer></v-spacer>
                                <v-btn size="x-small" variant="tonal" color="primary" @click="keepAddition(addition)">Keep</v-btn>
                                <v-btn size="x-small" variant="tonal" @click="editAddition(addition)">Edit</v-btn>
                                <v-btn size="x-small" variant="tonal" color="delete" @click="dropAddition(addition)">Drop</v-btn>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col cols="12" md="6">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">
                        <v-icon size="small" class="mr-1">mdi-food-drumstick-outline</v-icon>
                        Food &amp; dress
                    </v-card-title>
                    <v-card-text>
                        <v-textarea
                            v-model="local.food"
                            rows="3"
                            auto-grow
                            hide-details
                            variant="outlined"
                            density="compact"
                            @blur="save()"
                        ></v-textarea>

                        <div v-for="addition in additionsFor('food')" :key="addition.id" class="addition-box mt-3 pa-2" :class="{ 'addition-unreviewed': addition.status === 'unreviewed' }">
                            <v-textarea
                                v-model="additionEdits[addition.id]"
                                rows="2"
                                auto-grow
                                density="compact"
                                variant="outlined"
                                hide-details
                                class="mb-1"
                            ></v-textarea>
                            <div class="d-flex align-center ga-2">
                                <v-chip v-if="addition.status === 'unreviewed'" size="x-small" color="unsaved" variant="tonal">
                                    Not reviewed
                                </v-chip>
                                <v-spacer></v-spacer>
                                <v-btn size="x-small" variant="tonal" color="primary" @click="keepAddition(addition)">Keep</v-btn>
                                <v-btn size="x-small" variant="tonal" @click="editAddition(addition)">Edit</v-btn>
                                <v-btn size="x-small" variant="tonal" color="delete" @click="dropAddition(addition)">Drop</v-btn>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>
            </v-col>

            <v-col cols="12">
                <v-card class="mb-4" variant="tonal">
                    <v-card-title class="text-caption text-uppercase text-muted">
                        <v-icon size="small" class="mr-1">mdi-calendar-star</v-icon>
                        Holidays
                    </v-card-title>
                    <v-card-text>
                        <v-row v-for="(holiday, i) in local.holidays" :key="i" class="mb-1" dense>
                            <v-col cols="12" md="3">
                                <v-text-field v-model="holiday.name" label="Name" density="compact" variant="outlined" hide-details @blur="save()"></v-text-field>
                            </v-col>
                            <v-col cols="12" md="3">
                                <v-text-field v-model="holiday.when" label="When" density="compact" variant="outlined" hide-details @blur="save()"></v-text-field>
                            </v-col>
                            <v-col cols="12" md="5">
                                <v-text-field v-model="holiday.description" label="Description" density="compact" variant="outlined" hide-details @blur="save()"></v-text-field>
                            </v-col>
                            <v-col cols="12" md="1" class="d-flex align-center">
                                <v-btn icon size="small" variant="text" @click="removeHoliday(i)">
                                    <v-icon size="small" color="delete">mdi-close</v-icon>
                                </v-btn>
                            </v-col>
                        </v-row>
                        <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="addHoliday()">
                            Add holiday
                        </v-btn>
                        <div class="text-muted text-caption mt-2">
                            <v-icon size="small" class="mr-1">mdi-calendar-month</v-icon>
                            "When" is plain text for now; real dates arrive with the world calendar.
                        </div>

                        <div v-for="addition in additionsFor('holidays')" :key="addition.id" class="addition-box mt-3 pa-2" :class="{ 'addition-unreviewed': addition.status === 'unreviewed' }">
                            <v-textarea
                                v-model="additionEdits[addition.id]"
                                rows="2"
                                auto-grow
                                density="compact"
                                variant="outlined"
                                hide-details
                                class="mb-1"
                            ></v-textarea>
                            <div class="d-flex align-center ga-2">
                                <v-chip v-if="addition.status === 'unreviewed'" size="x-small" color="unsaved" variant="tonal">
                                    Not reviewed
                                </v-chip>
                                <v-spacer></v-spacer>
                                <v-btn size="x-small" variant="tonal" color="primary" @click="keepAddition(addition)">Keep</v-btn>
                                <v-btn size="x-small" variant="tonal" @click="editAddition(addition)">Edit</v-btn>
                                <v-btn size="x-small" variant="tonal" color="delete" @click="dropAddition(addition)">Drop</v-btn>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>
            </v-col>
        </v-row>
    </div>
</template>

<script>
import { levelLabel as formatLevel } from './levelLabels';

export default {
    name: 'CultureOverview',
    props: {
        culture: {
            type: Object,
            required: true,
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        places: {
            type: Array,
            default: () => [],
        },
        send: {
            type: Function,
            required: true,
        },
    },
    emits: [
        'open-language',
        'open-places',
    ],
    data() {
        return {
            local: this.cloneCulture(this.culture),
            additionEdits: this.initAdditionEdits(this.culture),
        }
    },
    computed: {
        levelLabel() {
            return formatLevel(this.culture.language.level);
        },
        soundPreview() {
            const sound = this.culture.language.sound || '';
            const firstSentence = sound.split('.')[0];
            return firstSentence ? `${firstSentence}.` : 'No notes on how it sounds yet.';
        },
        placesForCulture() {
            return this.places.filter(p => (p.cultures || []).some(cs => cs.culture_id === this.culture.id));
        },
    },
    watch: {
        culture(newCulture) {
            this.local = this.cloneCulture(newCulture);
            this.additionEdits = this.initAdditionEdits(newCulture);
        },
    },
    methods: {
        cloneCulture(culture) {
            return JSON.parse(JSON.stringify(culture));
        },
        initAdditionEdits(culture) {
            const edits = {};
            for (const addition of (culture.additions || [])) {
                edits[addition.id] = addition.text;
            }
            return edits;
        },
        save() {
            this.send('save_culture', { culture: this.local });
        },
        addCustom() {
            this.local.customs.push('');
        },
        removeCustom(i) {
            this.local.customs.splice(i, 1);
            this.save();
        },
        addHoliday() {
            this.local.holidays.push({ name: '', when: '', description: '' });
        },
        removeHoliday(i) {
            this.local.holidays.splice(i, 1);
            this.save();
        },
        colorFor(cultureId) {
            const found = this.cultures.find(c => c.id === cultureId);
            return found ? found.color : '#9E9E9E';
        },
        shareFor(place) {
            const cs = (place.cultures || []).find(cs => cs.culture_id === this.culture.id);
            return cs ? cs.share : 0;
        },
        additionsFor(section) {
            return (this.culture.additions || []).filter(a => a.section === section);
        },
        keepAddition(addition) {
            this.send('addition', { culture_id: this.culture.id, addition_id: addition.id, op: 'keep' });
        },
        editAddition(addition) {
            this.send('addition', {
                culture_id: this.culture.id,
                addition_id: addition.id,
                op: 'edit',
                text: this.additionEdits[addition.id],
            });
        },
        dropAddition(addition) {
            this.send('addition', { culture_id: this.culture.id, addition_id: addition.id, op: 'drop' });
        },
    },
}
</script>

<style scoped>
.mix-bar {
    display: flex;
    height: 6px;
    border-radius: 3px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.08);
}

.mix-bar span {
    display: block;
    height: 100%;
}

.addition-box {
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.04);
}

.addition-unreviewed {
    background: rgba(255, 213, 79, 0.12);
}
</style>
