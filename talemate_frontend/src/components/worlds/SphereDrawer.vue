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
        <SphereTimeline v-else-if="drawer.type === 'events'" :timeline="sphere.timeline" />

        <!-- Branches -->
        <div v-else-if="drawer.type === 'branches'">
            <div v-if="!sphere.branches.length && !branchOpen" class="empty">No branches yet. A branch inherits these drawers and overrides what it rejects.</div>
            <div v-for="branch in sphere.branches" :key="branch.id" class="item" data-testid="sphere-branch">
                <LinkedText :segments="[{ text: branch.name, ref: branch.id, stub: false }]" />
            </div>
        </div>

        <!-- items: entries part of the sphere, and its statements -->
        <template v-else>
            <div v-if="!drawer.items.length && !fillShown" class="empty">
                Not written yet. Fill asks the AI for this drawer, from the page so far and everything part of it.
            </div>
            <template v-for="item in drawer.items" :key="item.thing_id || item.fact_id">
                <div class="item d-flex align-center ga-2" :class="{ inherited: item.inherited }" data-testid="drawer-item">
                    <span class="flex-grow-1">
                        <template v-if="item.thing_id">
                            <LinkedText :segments="[{ text: item.name, ref: item.thing_id, stub: item.stub }]" />
                            <template v-if="item.segments.length"><span class="text-muted"> — </span><LinkedText :segments="item.segments" /></template>
                        </template>
                        <LinkedText v-else :segments="item.segments" :text="item.name" />
                        <span v-if="item.inherited" class="text-caption text-muted ml-1">(inherited)</span>
                    </span>
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
                </div>
                <div v-if="ending && ending.key === itemKey(item)" class="inline-form d-flex align-center flex-wrap ga-2" data-testid="end-item-form">
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

        <!-- "+ Add": file an entry here, tie a character, or a new branch -->
        <div v-if="adding" class="inline-form d-flex align-center flex-wrap ga-2" data-testid="drawer-add-form">
            <template v-if="drawer.type === 'people'">
                <v-autocomplete v-model="adding.characterId" :items="characterOptions" item-title="name" item-value="id" label="Character" density="compact" variant="outlined" hide-details class="picker"></v-autocomplete>
                <v-text-field v-model="adding.role" label="Role" density="compact" variant="outlined" hide-details class="picker"></v-text-field>
                <v-text-field v-model.number="adding.year" label="Since (year)" type="number" min="1" max="9999" density="compact" variant="outlined" hide-details class="year"></v-text-field>
            </template>
            <v-text-field
                v-else-if="drawer.type === 'branches'"
                v-model="adding.prompt"
                label="Describe the branch"
                placeholder="The Reformed Dawn, who reject the doctrine of snowy superiority…"
                density="compact"
                variant="outlined"
                hide-details
                class="flex-grow-1"
            ></v-text-field>
            <v-autocomplete v-else v-model="adding.thingId" :items="entryOptions" item-title="name" item-value="id" label="File an entry here" density="compact" variant="outlined" hide-details class="picker"></v-autocomplete>
            <v-btn color="accent" variant="flat" size="small" :loading="addBusy" :disabled="!canSaveAdd" @click="saveAdd">{{ drawer.type === 'branches' ? 'Preview' : 'Add' }}</v-btn>
            <v-btn variant="text" size="small" @click="adding = null">Cancel</v-btn>
        </div>

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

        <!-- Fill's items, each kept unless unticked -->
        <div v-if="fillShown" class="fill-preview mt-2 pa-2" data-testid="fill-preview">
            <v-progress-linear v-if="fill.pending" indeterminate color="accent"></v-progress-linear>
            <v-alert v-else-if="fill.error" type="error" variant="tonal" density="compact">{{ fill.error }}</v-alert>
            <template v-else>
                <div v-if="!fill.items.length" class="text-body-2 text-muted">Nothing new to add.</div>
                <div v-for="(item, index) in fill.items" :key="index" class="d-flex align-center ga-2" data-testid="fill-item">
                    <v-checkbox-btn v-model="kept[index]" density="compact" class="flex-grow-0" :aria-label="'Keep ' + (item.name || item.text)"></v-checkbox-btn>
                    <span :class="{ dropped: !kept[index] }">
                        <template v-if="item.name"><span class="linked-stub fresh">{{ item.name }}</span><span class="text-muted"> — </span></template>{{ item.text }}
                    </span>
                </div>
            </template>
            <div class="d-flex ga-2 mt-2">
                <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-check" :disabled="!fill.items || !keptItems.length" :loading="!!worlds.pending.accept_fill" @click="worlds.acceptFill(keptItems)">Accept</v-btn>
                <v-btn variant="outlined" size="small" :disabled="!!worlds.pending.accept_fill" @click="worlds.discardFill()">Discard</v-btn>
            </div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateOf, dateParts, formatDate } from './worldDates.js';
import { PART_OF_KINDS, UNSORTED, drawerTypesFor } from './worldKinds.js';
import LinkedText from './LinkedText.vue';
import SpherePreviewCard from './SpherePreviewCard.vue';
import SphereTimeline from './SphereTimeline.vue';

// the drawer types whose items are entries and statements, which Fill
// asks the AI for
const ITEM_TYPES = ['places', 'practices', 'beliefs', 'knowledge', 'structure'];

// One drawer of a sphere's page: its title and dashed type tag, and by
// type:
// - people: the ties pointing at it (read-only here; "+ Add" ties a
//   character, from the character's side: `worlds.addTie`);
// - events: the Timeline;
// - branches: the sphere's branches, "+ New branch" and its preview;
// - any other: its items (an entry part of the sphere, its name linked
//   with its first fact, or a statement), each own one open to "End this…"
//   (a date, and what ended it); an inherited item is dimmed, and ends in
//   the sphere it comes from. Fill (asking the AI for more items, each
//   kept unless unticked) and "+ Add" (filing an entry here). A places
//   drawer may note the territory it holds besides its items.
// Unsorted holds what's part of the sphere in no drawer it has: no Fill,
// no editing. `edit` asks the page to open its drawer form, shown in the
// `form` slot.
export default {
    name: 'SphereDrawer',
    components: { LinkedText, SpherePreviewCard, SphereTimeline },
    props: {
        drawer: { type: Object, required: true },
        // the sphere's thing payload
        thing: { type: Object, required: true },
        // places the sphere holds besides this drawer's items (`{id, name}`)
        territory: { type: Array, default: () => [] },
    },
    emits: ['edit'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // "End this…": `{key, year, by}`
            ending: null,
            // "+ Add": `{characterId, role, year}`, `{prompt}` or `{thingId}`
            adding: null,
            // Fill's items, by index: kept unless unticked
            kept: [],
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
        fillShown() {
            return !!this.fill;
        },
        filling() {
            return !!this.fill?.pending;
        },
        keptItems() {
            return (this.fill?.items || []).filter((_item, index) => this.kept[index]);
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
        characterOptions() {
            const tied = new Set(this.sphere.people.map((person) => person.character_id));
            return (this.worlds.things.character || []).filter((thing) => !tied.has(thing.id));
        },
        // entries this drawer may hold, not in it already, not the sphere
        entryOptions() {
            const types = (kind) => drawerTypesFor(kind).includes(this.drawer.type);
            const held = new Set(this.drawer.items.map((item) => item.thing_id));
            return this.worlds.referenceTargets.filter(
                (target) => PART_OF_KINDS.includes(target.kind) && types(target.kind) && !held.has(target.id) && target.id !== this.sphereId,
            );
        },
        addBusy() {
            return !!(this.worlds.pending.set_part_of || this.worlds.pending.set_ties || this.worlds.branchPending);
        },
        canSaveAdd() {
            const adding = this.adding;
            if (!adding || this.addBusy) {
                return false;
            }
            if (this.drawer.type === 'people') {
                return !!adding.characterId && (adding.year === null || adding.year === '' || this.validYear(adding.year));
            }
            if (this.drawer.type === 'branches') {
                return !!adding.prompt.trim();
            }
            return !!adding.thingId;
        },
    },
    watch: {
        // a new Fill reply: every item kept
        'fill.items'(items) {
            this.kept = (items || []).map(() => true);
        },
        // the page changed (an edit's reply): the forms are done
        thing() {
            this.ending = null;
            if (this.adding && this.drawer.type !== 'branches') {
                this.adding = null;
            }
        },
        'worlds.branchPending'(now, before) {
            if (before && !now && this.drawer.type === 'branches') {
                this.adding = null;
            }
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
            if (this.drawer.type === 'people') {
                this.adding = { characterId: null, role: '', year: null };
            } else if (this.drawer.type === 'branches') {
                this.adding = { prompt: '' };
            } else {
                this.adding = { thingId: null };
            }
        },
        saveAdd() {
            if (!this.canSaveAdd) {
                return;
            }
            const adding = this.adding;
            if (this.drawer.type === 'people') {
                this.worlds.addTie(adding.characterId, {
                    sphere_id: this.sphereId,
                    role: adding.role.trim(),
                    since: this.validYear(adding.year) ? dateOf(adding.year) : null,
                });
            } else if (this.drawer.type === 'branches') {
                this.worlds.previewBranch(this.sphereId, adding.prompt.trim());
            } else {
                this.worlds.setPartOf(adding.thingId, this.sphereId, this.drawer.id);
            }
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

.fill-preview {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
}

.dropped {
    text-decoration: line-through;
    color: rgb(var(--v-theme-muted));
}

.linked-stub {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
    text-underline-offset: 2px;
}
</style>
