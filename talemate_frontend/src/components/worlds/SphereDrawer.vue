<template>
    <div class="sphere-drawer" :class="{ inherited: drawer.inherited }" data-testid="sphere-drawer">
        <div class="drawer-head d-flex align-center flex-wrap ga-2">
            <span class="drawer-title" data-testid="drawer-title">{{ drawer.title }}</span>
            <span class="drawer-type" data-testid="drawer-type">{{ drawer.type }}</span>
            <span v-if="drawer.inherited" class="text-caption text-muted" data-testid="drawer-inherited">inherited from {{ parentName }}</span>
            <v-spacer></v-spacer>
            <v-btn v-if="fillable" variant="outlined" size="x-small" prepend-icon="mdi-creation" :loading="filling" :disabled="!!fill" data-testid="drawer-fill" @click="worlds.fillDrawer(sphereId, drawer.id)">Fill</v-btn>
            <v-btn v-if="addable" variant="outlined" size="x-small" prepend-icon="mdi-plus" data-testid="drawer-add" @click="startAdd">{{ drawer.type === 'branches' ? 'New branch' : 'Add' }}</v-btn>
            <v-btn v-if="editable" icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit drawer" data-testid="drawer-edit" @click="$emit('edit')"></v-btn>
        </div>

        <slot name="form"></slot>

        <!-- People: the ties pointing at the sphere -->
        <div v-if="drawer.type === 'people'" data-testid="sphere-people">
            <div v-if="!sphere.people.length" class="empty">No one is tied to it yet.</div>
            <div v-for="person in sphere.people" :key="person.character_id" class="item">
                <LinkedText :segments="[{ text: person.name, ref: person.character_id, stub: false }]" />
                <span class="text-muted"> — {{ personLine(person) }}</span>
            </div>
        </div>

        <!-- the Timeline: the sphere's dated facts -->
        <template v-else-if="drawer.type === 'events'">
            <div v-if="timelineElsewhere" class="empty" data-testid="timeline-elsewhere">The timeline shows under {{ timelineElsewhere }}.</div>
            <SphereTimeline v-else :timeline="sphere.timeline" />
        </template>

        <!-- Branches -->
        <div v-else-if="drawer.type === 'branches'">
            <div v-if="!sphere.branches.length && !branchOpen" class="empty">No branches yet. A branch inherits these drawers and overrides what it rejects.</div>
            <div v-for="branch in sphere.branches" :key="branch.id" class="item" data-testid="sphere-branch">
                <LinkedText :segments="[{ text: branch.name, ref: branch.id, stub: false }]" />
            </div>
        </div>

        <!-- items: entries part of the sphere, and its statements -->
        <template v-else>
            <div v-if="!drawer.items.length && !fill" class="empty">
                Not written yet. Fill asks the AI for this drawer, from the page so far and everything part of it.
            </div>
            <template v-for="item in drawer.items" :key="item.thing_id || item.fact_id">
                <SphereFactRow :fact-id="item.inherited ? null : item.fact_id" class="item" :class="{ inherited: item.inherited }" data-testid="drawer-item">
                    <template v-if="item.thing_id">
                        <LinkedText :segments="[{ text: item.name, ref: item.thing_id, stub: item.stub }]" />
                        <template v-if="item.segments.length"><span class="text-muted"> — </span><LinkedText :segments="item.segments" /></template>
                    </template>
                    <LinkedText v-else :segments="item.segments" :text="item.name" />
                    <span v-if="item.inherited" class="text-caption text-muted ml-1">(inherited)</span>
                    <template #actions>
                        <v-btn
                            v-if="!item.inherited"
                            icon="mdi-timer-off-outline"
                            variant="text"
                            size="x-small"
                            density="comfortable"
                            aria-label="End this…"
                            title="End this…"
                            data-testid="end-item"
                            @click="startEnd(item)"
                        ></v-btn>
                    </template>
                </SphereFactRow>
                <div
                    v-if="ending && ending.key === itemKey(item)"
                    class="inline-form d-flex align-center flex-wrap ga-2"
                    data-testid="end-item-form"
                    @keydown.esc="ending = null"
                >
                    <v-text-field v-model.number="ending.year" label="Ended in (year)" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year"></v-text-field>
                    <v-autocomplete
                        v-model="ending.by"
                        :items="byOptions"
                        item-title="name"
                        item-value="id"
                        label="Ended by (optional)"
                        clearable
                        density="compact"
                        variant="outlined"
                        hide-details
                        class="picker"
                        data-testid="end-by"
                    ></v-autocomplete>
                    <v-btn color="accent" variant="flat" size="small" :loading="!!worlds.pending.end_item" :disabled="!validYear(ending.year)" @click="saveEnd(item)">End it</v-btn>
                    <v-btn variant="text" size="small" @click="ending = null">Cancel</v-btn>
                </div>
            </template>
            <div v-if="territoryLine" class="item text-muted" data-testid="sphere-territory">
                holds sway in
                <template v-for="(place, index) in territoryLine" :key="place.id"><span v-if="index">, </span><LinkedText :segments="[{ text: place.name, ref: place.id, stub: false }]" /></template>
            </div>
        </template>

        <DrawerAddForm v-if="adding" :drawer="drawer" :thing="thing" @close="adding = false" />

        <!-- a new branch's preview -->
        <template v-if="drawer.type === 'branches'">
            <v-progress-linear v-if="worlds.branchPending" indeterminate color="accent" class="mt-2"></v-progress-linear>
            <v-alert v-if="worlds.branchError" type="error" variant="tonal" density="compact" class="mt-2">{{ worlds.branchError }}</v-alert>
            <SpherePreviewCard
                v-if="worlds.branchPreview && worlds.branchRequest?.parentId === sphereId"
                :preview="worlds.branchPreview"
                branch
                class="mt-2"
                @accept="worlds.acceptBranch({ name: $event })"
                @regenerate="worlds.previewBranch(worlds.branchRequest.parentId, worlds.branchRequest.prompt)"
                @discard="worlds.discardBranch()"
            />
        </template>

        <FillPreview v-if="fill" :fill="fill" />
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, dateParts, formatDate } from './worldDates.js';
import { UNSORTED } from './worldKinds.js';
import DrawerAddForm from './DrawerAddForm.vue';
import FillPreview from './FillPreview.vue';
import LinkedText from './LinkedText.vue';
import SphereFactRow from './SphereFactRow.vue';
import SpherePreviewCard from './SpherePreviewCard.vue';
import SphereTimeline from './SphereTimeline.vue';

// the drawer types whose items are entries and statements, which Fill
// asks the AI for
const ITEM_TYPES = ['places', 'practices', 'beliefs', 'knowledge', 'structure'];

// One drawer of a sphere's page: its title and dashed type tag, and by
// type:
// - people: the ties pointing at it (read-only here; "+ Add" ties a
//   character, from the character's side);
// - events: the Timeline;
// - branches: the sphere's branches, "+ New branch" and its preview;
// - any other: its items (an entry part of the sphere, its name linked
//   with its first fact, or a statement), each own one open to "End this…"
//   (a date, and what ended it), an own statement to Edit and Remove too
//   (`SphereFactRow`); an inherited item is dimmed, and ends in the sphere
//   it comes from. Fill (`FillPreview`: the AI's items, each kept unless
//   unticked) and "+ Add" (`DrawerAddForm`: a statement, or an entry filed
//   here). A places drawer may note the territory it holds besides its
//   items.
// Unsorted holds what's part of the sphere in no drawer it has: no Fill,
// no "+ Add", no editing. `edit` asks the page to open its drawer form,
// shown in the `form` slot.
export default {
    name: 'SphereDrawer',
    components: { DrawerAddForm, FillPreview, LinkedText, SphereFactRow, SpherePreviewCard, SphereTimeline },
    props: {
        drawer: { type: Object, required: true },
        // the sphere's thing payload
        thing: { type: Object, required: true },
        // places the sphere holds besides this drawer's items (`{id, name}`)
        territory: { type: Array, default: () => [] },
        // a second events drawer: the title of the first, where the
        // Timeline shows
        timelineElsewhere: { type: String, default: null },
    },
    emits: ['edit'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // "End this…": `{key, year, by}`
            ending: null,
            // "+ Add" is open
            adding: false,
        };
    },
    computed: {
        sphere() {
            return this.thing.sphere;
        },
        sphereId() {
            return this.thing.id;
        },
        parentName() {
            return this.sphere.parent?.name || 'its parent';
        },
        unsorted() {
            return this.drawer.id === UNSORTED;
        },
        fillable() {
            return ITEM_TYPES.includes(this.drawer.type) && !this.unsorted;
        },
        addable() {
            return !this.unsorted && this.drawer.type !== 'events';
        },
        editable() {
            return !this.unsorted;
        },
        fill() {
            const fill = this.worlds.fill;
            return fill && fill.sphereId === this.sphereId && fill.drawerId === this.drawer.id ? fill : null;
        },
        filling() {
            return !!this.fill?.pending;
        },
        branchOpen() {
            return this.worlds.branchPending || (this.worlds.branchPreview && this.worlds.branchRequest?.parentId === this.sphereId);
        },
        territoryLine() {
            const shown = new Set(this.drawer.items.map((item) => item.thing_id));
            const rest = this.territory.filter((place) => !shown.has(place.id));
            return this.drawer.type === 'places' && rest.length ? rest : null;
        },
        byOptions() {
            return this.worlds.referenceTargets.filter((target) => !target.stub && target.id !== this.sphereId);
        },
    },
    watch: {
        // the page changed (an edit's reply): "End this…" is done
        thing() {
            this.ending = null;
        },
    },
    methods: {
        validYear(year) {
            return Number.isInteger(year) && year >= 1 && year <= 9999;
        },
        itemKey(item) {
            return item.thing_id || item.fact_id;
        },
        personLine(person) {
            const parts = [person.role || 'tied'];
            if (person.since) {
                parts.push(`since ${formatDate(this.worlds.calendar, person.since)}`);
            }
            if (person.until) {
                parts.push(`until ${formatDate(this.worlds.calendar, person.until)}`);
            }
            return parts.join(', ');
        },
        startEnd(item) {
            this.ending = { key: this.itemKey(item), year: this.defaultYear(), by: null };
        },
        // the year the page is viewed at, else the world's now
        defaultYear() {
            const date = this.thing.at || this.worlds.currentWorld?.now;
            return date ? dateParts(date).year : null;
        },
        saveEnd(item) {
            if (!this.validYear(this.ending.year)) {
                return;
            }
            this.worlds.endItem(this.sphereId, item, dateOf(this.ending.year), this.ending.by || null);
        },
        startAdd() {
            this.adding = true;
        },
    },
};
</script>

<style scoped>
.sphere-drawer {
    margin-top: 14px;
}

.sphere-drawer.inherited .drawer-title {
    opacity: 0.7;
}

.drawer-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    color: rgb(var(--v-theme-muted));
}

.drawer-type {
    font-size: 10px;
    color: rgb(var(--v-theme-muted));
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 8px;
    padding: 0 6px;
}

.item {
    padding: 3px 0;
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    line-height: 1.5;
}

.item .v-btn {
    flex: none;
}

.item.inherited {
    opacity: 0.6;
}

.empty {
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
    padding: 6px 10px;
    margin-top: 4px;
    font-size: 13px;
    color: rgb(var(--v-theme-muted));
}

.inline-form {
    margin: 6px 0;
}

.picker {
    min-width: 220px;
    max-width: 280px;
}

.year {
    max-width: 150px;
}

</style>
