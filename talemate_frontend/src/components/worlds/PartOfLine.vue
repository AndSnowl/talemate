<template>
    <div class="part-of" data-testid="part-of">
        <div class="d-flex align-center flex-wrap ga-2">
            <span class="field-label">Part of</span>
            <template v-if="link">
                <LinkedText :segments="[{ text: link.sphere_name, ref: link.sphere_id, stub: sphereStub }]" />
                <span v-if="sphereStub" class="text-caption text-muted">(stub{{ guess ? `, guessed: ${guess} sphere` : '' }})</span>
                <span class="text-muted">— {{ link.drawer_title }}</span>
            </template>
            <span v-else class="text-muted">no sphere</span>
            <v-btn v-if="!editing" icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit part of" data-testid="part-of-edit" @click="startEdit"></v-btn>
        </div>

        <div v-if="editing" class="editor d-flex align-center flex-wrap ga-2 mt-1" data-testid="part-of-form" @keydown.esc="editing = null">
            <v-autocomplete
                v-model="editing.sphereId"
                :items="sphereOptions"
                item-title="name"
                item-value="id"
                label="Sphere"
                density="compact"
                variant="outlined"
                hide-details
                class="picker"
                data-testid="part-of-sphere"
                @update:model-value="pickSphere"
            ></v-autocomplete>
            <v-select
                v-model="editing.drawerId"
                :items="drawerOptions"
                item-title="title"
                item-value="id"
                label="Drawer"
                density="compact"
                variant="outlined"
                hide-details
                class="picker"
                :loading="loadingDrawers"
                :disabled="!editing.sphereId"
                data-testid="part-of-drawer"
            ></v-select>
            <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!editing.sphereId || !editing.drawerId" @click="save">Save</v-btn>
            <v-btn v-if="link" variant="outlined" size="small" :disabled="busy" @click="takeOut">Take out</v-btn>
            <v-btn variant="text" size="small" :disabled="busy" @click="editing = null">Cancel</v-btn>
            <v-alert v-if="editing.refused" type="error" variant="tonal" density="compact" class="w-100" data-testid="part-of-refused">{{ editing.refused }}</v-alert>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { UNSORTED, partOfDrawers, templateInfo } from './worldKinds.js';
import LinkedText from './LinkedText.vue';

// An entry's "Part of" line: the sphere it belongs to (a stub dashed, with
// its guessed template) and the drawer it's in, editable: pick a sphere,
// then one of its drawers this kind may go in (a place in a places
// drawer, any other entry in one that holds entries; Unsorted always), or
// take it out. A move the backend refuses (a cycle, a wrong drawer) keeps
// the editor open with the refusal. A character has no Part of line: it's
// tied to spheres instead.
export default {
    name: 'PartOfLine',
    components: { LinkedText },
    props: {
        // the thing's payload
        thing: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // `{sphereId, drawerId, sent, refused}`
            editing: null,
        };
    },
    computed: {
        link() {
            return this.thing.part_of;
        },
        listing() {
            return (this.worlds.things.sphere || []).find((entry) => entry.id === this.link?.sphere_id) || null;
        },
        sphereStub() {
            return !!this.listing?.stub;
        },
        guess() {
            const template = this.listing?.template;
            return template ? templateInfo(template).label.toLowerCase() : '';
        },
        sphereOptions() {
            return (this.worlds.things.sphere || []).filter((entry) => entry.id !== this.thing.id);
        },
        chosen() {
            return this.editing?.sphereId ? this.worlds.sphereInfo[this.editing.sphereId] : null;
        },
        loadingDrawers() {
            return !!this.editing?.sphereId && !this.chosen;
        },
        drawerOptions() {
            return partOfDrawers(this.chosen?.sphere?.drawers, this.thing.kind);
        },
        busy() {
            return !!this.worlds.pending.set_part_of;
        },
    },
    watch: {
        // the reply to the save: done
        thing(thing, before) {
            if (this.editing?.sent || thing.id !== before?.id) {
                this.editing = null;
            }
        },
        // refused (an error, and no reply replaced the page): the refusal
        // shows. The store's spinner stops before the page's prop is
        // replaced, so only an error tells a refusal apart.
        busy(now) {
            if (!now && this.editing?.sent && this.worlds.error) {
                this.editing = { ...this.editing, sent: false, refused: this.worlds.error };
                this.worlds.clearError();
            }
        },
    },
    methods: {
        startEdit() {
            const sphereId = this.link?.sphere_id || null;
            this.editing = { sphereId, drawerId: this.link?.drawer_id || UNSORTED, sent: false, refused: null };
            if (sphereId) {
                this.worlds.fetchSphere(sphereId);
            }
        },
        pickSphere(id) {
            this.editing = { ...this.editing, drawerId: UNSORTED, refused: null };
            if (id) {
                this.worlds.fetchSphere(id);
            }
        },
        save() {
            this.worlds.setPartOf(this.thing.id, this.editing.sphereId, this.editing.drawerId);
            this.editing = { ...this.editing, sent: true, refused: null };
        },
        takeOut() {
            this.worlds.setPartOf(this.thing.id, null);
            this.editing = { ...this.editing, sent: true, refused: null };
        },
    },
};
</script>

<style scoped>
.part-of {
    margin: 4px 0;
}

.field-label {
    min-width: 80px;
    font-weight: 600;
    color: rgb(var(--v-theme-muted));
}

.picker {
    min-width: 200px;
    max-width: 260px;
}
</style>
