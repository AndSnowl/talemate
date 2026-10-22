<template>
    <v-card variant="tonal" class="sphere-preview pa-3" data-testid="sphere-preview">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <v-text-field v-model="name" label="Name" density="compact" variant="outlined" hide-details class="preview-name"></v-text-field>
            <v-chip size="x-small" label variant="outlined">{{ branch ? 'branch' : 'sphere' }} · {{ preview.template }}</v-chip>
            <v-chip size="x-small" label variant="outlined">{{ preview.agent ? 'acts in the world' : 'a body of knowledge' }}</v-chip>
        </div>

        <div v-if="preview.prose.description" class="summary mb-2">
            <LinkedText :segments="previewSegments(preview.prose.description, preview.new_names)" :text="preview.prose.description" />
        </div>

        <template v-if="timeline.length || about.length">
            <div class="heading">Timeline</div>
            <div v-for="(fact, index) in timeline" :key="'t' + index" class="row d-flex ga-2">
                <span class="year">{{ formatDate(worlds.calendar, fact.since) }}</span>
                <LinkedText :segments="previewSegments(fact.text, preview.new_names)" :text="fact.text" />
            </div>
            <div v-for="(fact, index) in about" :key="'a' + index" class="row">
                <span class="text-muted">about: </span><LinkedText :segments="previewSegments(fact.text, preview.new_names)" :text="fact.text" />
            </div>
        </template>

        <div class="heading">{{ branch ? 'Its own drawers' : 'Drawers' }}</div>
        <div v-if="!outline.length" class="text-body-2 text-muted">None of its own: it keeps its parent's.</div>
        <div v-for="drawer in outline" :key="drawer.id" class="drawer" data-testid="preview-drawer">
            <div>
                <span class="drawer-title">{{ drawer.title }}</span>
                <span class="drawer-type ml-2">{{ drawer.type }}</span>
            </div>
            <div v-for="(item, index) in drawer.items" :key="index" class="item">
                <template v-if="item.name"><LinkedText :segments="previewSegments(item.name, preview.new_names)" :text="item.name" /><span class="text-muted"> — </span></template>
                <LinkedText :segments="previewSegments(item.text, preview.new_names)" :text="item.text" />
            </div>
            <div v-for="entry in drawer.adopted" :key="entry.thing_id" class="item" data-testid="preview-adopted">
                <span class="adopted">{{ entry.name }}</span> <span class="text-muted">(already part of it)</span>
            </div>
            <div v-if="fillLater(drawer)" class="text-caption text-muted">Empty for now: Fill it on the page.</div>
        </div>

        <!-- a branch: the parent's items, each kept unless unticked -->
        <template v-if="branch && preview.parent_items.length">
            <div class="heading">From its parent (untick what it rejects)</div>
            <div v-for="row in preview.parent_items" :key="row.label" class="d-flex align-center ga-2" data-testid="branch-parent-item">
                <v-checkbox-btn :model-value="keptRow(row)" density="compact" class="flex-grow-0" :aria-label="'Keep ' + (row.name || row.text)" @update:model-value="worlds.setBranchKept(row, $event)"></v-checkbox-btn>
                <span :class="{ dropped: !keptRow(row) }">{{ row.name || row.text }}</span>
            </div>
        </template>

        <div class="d-flex ga-2 mt-3">
            <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-check" :loading="!!worlds.pending.accept_sphere" :disabled="!name.trim()" @click="$emit('accept', name.trim())">Accept</v-btn>
            <v-btn
                v-if="matchingStub"
                color="accent"
                variant="outlined"
                size="small"
                data-testid="sphere-fill-stub"
                :disabled="!name.trim() || !!worlds.pending.accept_sphere"
                @click="$emit('accept-into', { name: name.trim(), stubId: matchingStub.id })"
            >Fill the stub “{{ matchingStub.name }}” instead</v-btn>
            <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" :disabled="!!worlds.pending.accept_sphere" @click="$emit('regenerate')">Regenerate</v-btn>
            <v-btn variant="outlined" size="small" :prepend-icon="branch ? 'mdi-close' : 'mdi-pencil'" :disabled="!!worlds.pending.accept_sphere" @click="$emit('discard')">{{ branch ? 'Discard' : 'Edit' }}</v-btn>
        </div>
    </v-card>
</template>

<script>
import { previewSegments, useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';
import { UNSORTED } from './worldKinds.js';
import LinkedText from './LinkedText.vue';

// the drawer types an outline's items go in (people, events and branches
// are made by the app, not written)
const WRITTEN_TYPES = ['places', 'practices', 'beliefs', 'knowledge', 'structure'];

// A sphere's core before it's written (`preview_sphere`, or a branch's
// `preview_branch`): its name (editable), template and agent flag, the
// summary, the timeline, and the drawer outline, each drawer with the
// items it'll get (a named one becomes a stub) and the entries already
// part of it that it files there (`adopted`); a drawer left empty is
// filled later from the page. A branch also lists its parent's items,
// each kept unless the owner unticks it (`worlds.setBranchKept`).
// Accept emits the name; "Fill the stub instead" (a sphere stub named like
// it) emits `accept-into {name, stubId}`; Regenerate and Edit (Discard,
// for a branch) are the box's to handle.
export default {
    name: 'SpherePreviewCard',
    components: { LinkedText },
    props: {
        preview: { type: Object, required: true },
        branch: { type: Boolean, default: false },
    },
    emits: ['accept', 'accept-into', 'regenerate', 'discard'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { name: this.preview.name };
    },
    computed: {
        // a sphere stub named like it, which it can fill instead (not one
        // it expands or a thing it promotes)
        matchingStub() {
            const id = this.preview.matching_stub_id;
            if (!id || this.preview.stub_id || this.preview.promote_id) {
                return null;
            }
            const listed = (this.worlds.things.sphere || []).find((thing) => thing.id === id);
            return { id, name: listed?.name || this.preview.name };
        },
        timeline() {
            return this.preview.facts.filter((fact) => fact.category === 'timeline');
        },
        about() {
            return this.preview.facts.filter((fact) => fact.category !== 'timeline');
        },
        // the drawers with their items and adopted entries, then Unsorted
        // when something adopted has no drawer yet
        outline() {
            const names = new Map(this.worlds.referenceTargets.map((target) => [target.id, target.name]));
            const adopted = (drawerId) => (this.preview.adopted || [])
                .filter((entry) => entry.drawer_id === drawerId)
                .map((entry) => ({ ...entry, name: names.get(entry.thing_id) || 'an entry' }));
            const drawers = this.preview.drawers.map((drawer) => ({
                ...drawer,
                items: this.preview.items.filter((item) => item.drawer_id === drawer.id),
                adopted: adopted(drawer.id),
            }));
            const unsorted = adopted(UNSORTED);
            if (unsorted.length) {
                drawers.push({ id: UNSORTED, type: 'knowledge', title: 'Unsorted', items: [], adopted: unsorted });
            }
            return drawers;
        },
    },
    watch: {
        'preview.name'(name) {
            this.name = name;
        },
    },
    methods: {
        formatDate,
        previewSegments,
        fillLater(drawer) {
            return WRITTEN_TYPES.includes(drawer.type) && drawer.id !== UNSORTED && !drawer.items.length && !drawer.adopted.length;
        },
        keptRow(row) {
            const dropped = row.thing_id ? this.preview.drops : this.preview.rejects;
            return !(dropped || []).includes(row.thing_id || row.fact_id);
        },
    },
};
</script>

<style scoped>
.preview-name {
    max-width: 320px;
}

.summary {
    line-height: 1.5;
}

.heading {
    margin-top: 10px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

.row,
.item {
    padding: 2px 0;
    line-height: 1.5;
}

.year {
    flex: none;
    min-width: 48px;
    color: rgb(var(--v-theme-date));
}

.drawer {
    margin-top: 6px;
}

.drawer-title {
    font-weight: 600;
}

.drawer-type {
    font-size: 10px;
    color: rgb(var(--v-theme-muted));
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 8px;
    padding: 0 6px;
}

.item {
    padding-left: 12px;
}

.adopted {
    color: rgb(var(--v-theme-link));
}

.dropped {
    text-decoration: line-through;
    color: rgb(var(--v-theme-muted));
}
</style>
