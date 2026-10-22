<template>
    <div class="sphere-page mb-4" data-testid="sphere-page">
        <div v-if="summary" class="summary mb-1" data-testid="sphere-summary">
            <LinkedText :segments="(thing.prose_segments || {}).description" :text="summary" />
        </div>
        <div v-if="sphere.parent" class="text-body-2 mb-1" data-testid="sphere-parent">
            <span class="text-muted">A branch of </span>
            <LinkedText :segments="[{ text: sphere.parent.name, ref: sphere.parent.id, stub: false }]" />
        </div>

        <SphereDrawer
            v-for="drawer in sphere.drawers"
            :key="drawer.id"
            :drawer="drawer"
            :thing="thing"
            :territory="drawer.id === firstPlacesId ? territory : []"
            @edit="startEdit(drawer)"
        >
            <template v-if="form && form.id === drawer.id" #form>
                <DrawerForm :form="form" :busy="saving" @save="saveForm" @cancel="form = null" @move="moveDrawer(drawer, $event)" @drop="dropDrawer(drawer)" />
            </template>
        </SphereDrawer>

        <!-- the Timeline, when no drawer shows it -->
        <div v-if="!hasEvents && sphere.timeline.length" class="mt-3">
            <div class="timeline-title">Timeline</div>
            <SphereTimeline :timeline="sphere.timeline" />
        </div>

        <div class="d-flex align-center ga-2 mt-3">
            <v-btn v-if="!form || form.id" variant="outlined" size="small" prepend-icon="mdi-plus" data-testid="add-drawer" @click="startAdd">Add a drawer</v-btn>
            <span v-if="!form || form.id" class="text-caption text-muted">a type and a title</span>
        </div>
        <DrawerForm v-if="form && !form.id" :form="form" :busy="saving" class="mt-2" @save="saveForm" @cancel="form = null" />
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { drawersPayload } from './worldKinds.js';
import DrawerForm from './DrawerForm.vue';
import LinkedText from './LinkedText.vue';
import SphereDrawer from './SphereDrawer.vue';
import SphereTimeline from './SphereTimeline.vue';

// The sphere part of a thing's page (a sphere, or a place that took on a
// template), following the approved mockup: the summary, the branch's
// parent, the typed and titled drawers in order (`SphereDrawer`), and
// "+ Add a drawer". Drawers are edited here and written whole
// (`set_drawers`, every drawer the page shows): add one of any type with
// a title, retitle, move up or down among the sphere's own, drop. A
// branch's inherited drawer can be retitled (that keeps an own copy
// overriding its parent's) but not moved or dropped. With no events
// drawer, the Timeline still shows below the drawers.
export default {
    name: 'SpherePage',
    components: { DrawerForm, LinkedText, SphereDrawer, SphereTimeline },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // the drawer form: `{id?, type, title, inherited, own, sent}`
            // (no id: a new drawer)
            form: null,
        };
    },
    computed: {
        thing() {
            return this.worlds.thing;
        },
        sphere() {
            return this.thing.sphere;
        },
        summary() {
            return this.thing.prose?.description?.text || '';
        },
        hasEvents() {
            return this.sphere.drawers.some((drawer) => drawer.type === 'events');
        },
        firstPlacesId() {
            return this.sphere.drawers.find((drawer) => drawer.type === 'places')?.id || null;
        },
        territory() {
            return this.sphere.territory;
        },
        saving() {
            return !!this.worlds.pending.set_drawers;
        },
        // the sphere's own drawers, which can be moved and dropped
        ownIds() {
            return this.sphere.drawers.filter((drawer) => !drawer.inherited && drawer.id !== 'unsorted').map((drawer) => drawer.id);
        },
    },
    watch: {
        // another page, or the reply to the form's save
        thing(thing, before) {
            if (!thing || thing.id !== before?.id || this.form?.sent) {
                this.form = null;
            }
        },
        // the save failed (no reply replaced the page): keep the form
        saving(now) {
            if (!now && this.form?.sent) {
                this.form = { ...this.form, sent: false };
            }
        },
    },
    methods: {
        startAdd() {
            this.form = { id: null, type: null, title: '', own: true, sent: false };
        },
        startEdit(drawer) {
            this.form = {
                id: drawer.id,
                type: drawer.type,
                title: drawer.title,
                inherited: drawer.inherited,
                own: !drawer.inherited,
                first: this.ownIds[0] === drawer.id,
                last: this.ownIds[this.ownIds.length - 1] === drawer.id,
                sent: false,
            };
        },
        write(drawers) {
            this.worlds.setDrawers(this.thing.id, drawers);
            if (this.form) {
                this.form = { ...this.form, sent: true };
            }
        },
        saveForm() {
            const form = this.form;
            const title = form.title.trim();
            if (!title || !form.type) {
                return;
            }
            const drawers = drawersPayload(this.sphere.drawers);
            if (form.id) {
                this.write(drawers.map((drawer) => (drawer.id === form.id ? { ...drawer, title } : drawer)));
            } else {
                this.write([...drawers, { type: form.type, title }]);
            }
        },
        // `delta` -1 (up) or 1 (down), among the sphere's own drawers
        moveDrawer(drawer, delta) {
            const drawers = drawersPayload(this.sphere.drawers);
            const own = drawers.filter((d) => this.ownIds.includes(d.id));
            const rest = drawers.filter((d) => !this.ownIds.includes(d.id));
            const index = own.findIndex((d) => d.id === drawer.id);
            const to = index + delta;
            if (index < 0 || to < 0 || to >= own.length) {
                return;
            }
            [own[index], own[to]] = [own[to], own[index]];
            this.write([...own, ...rest]);
        },
        // its items go to Unsorted, where the page shows them
        dropDrawer(drawer) {
            this.write(drawersPayload(this.sphere.drawers).filter((d) => d.id !== drawer.id));
        },
    },
};
</script>

<style scoped>
.summary {
    line-height: 1.5;
}

.timeline-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    color: rgb(var(--v-theme-muted));
}
</style>
