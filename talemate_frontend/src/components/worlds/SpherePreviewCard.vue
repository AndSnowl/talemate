<template>
    <v-card variant="tonal" class="sphere-preview pa-3" data-testid="sphere-preview">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <v-text-field v-model="name" label="Name" density="compact" variant="outlined" hide-details class="preview-name"></v-text-field>
            <v-chip size="x-small" label variant="outlined">{{ branch ? 'branch' : 'sphere' }} · {{ preview.template }}</v-chip>
            <v-chip size="x-small" label variant="outlined">{{ preview.agent ? 'acts in the world' : 'a body of knowledge' }}</v-chip>
        </div>

        <!-- the model's reply didn't parse whole: read from its complete
             parts (ruling C26), so some of it may be missing -->
        <div v-if="preview.salvaged" class="salvaged text-caption mb-2" data-testid="sphere-preview-salvaged">
            Part of the model's reply couldn't be read, so this preview was pieced together from what could. Some items may be missing: check it, or ask again.
        </div>

        <!-- the world may have it already: a sphere's core isn't accepted
             onto an entry, that entry is made a sphere instead (ruling C9) -->
        <SameThingAsk
            v-if="preview.same_as && preview.same_as.length"
            variant="promote"
            :name="preview.name"
            :offers="preview.same_as"
            :verdict="preview.verdict"
            @promote="promote"
        />

        <div v-if="preview.prose.description" class="summary mb-2">
            <LinkedText :segments="previewSegments(preview.prose.description, preview.new_names)" :text="preview.prose.description" />
        </div>

        <template v-if="timeline.length || about.length">
            <div class="heading">Timeline</div>
            <template v-for="row in timeline" :key="'t' + row.index">
                <div class="row d-flex align-center ga-2">
                    <v-checkbox-btn :model-value="row.fact.ticked !== false" density="compact" class="flex-grow-0" :aria-label="'Write ' + row.fact.text" @update:model-value="tickFact(row.index, $event)"></v-checkbox-btn>
                    <span class="year">{{ formatDate(worlds.calendar, row.fact.since) }}</span>
                    <span :class="{ dropped: row.fact.ticked === false }"><LinkedText :segments="previewSegments(row.fact.text, preview.new_names)" :text="row.fact.text" /></span>
                </div>
                <div v-if="row.fact.repeat_of" class="match text-caption" data-testid="fact-match">≈ on {{ row.fact.repeat_of.owner_name || 'an entry' }}: {{ row.fact.repeat_of.text }}</div>
            </template>
            <template v-for="row in about" :key="'a' + row.index">
                <div class="row d-flex align-center ga-2">
                    <v-checkbox-btn :model-value="row.fact.ticked !== false" density="compact" class="flex-grow-0" :aria-label="'Write ' + row.fact.text" @update:model-value="tickFact(row.index, $event)"></v-checkbox-btn>
                    <span :class="{ dropped: row.fact.ticked === false }"><span class="text-muted">about: </span><LinkedText :segments="previewSegments(row.fact.text, preview.new_names)" :text="row.fact.text" /></span>
                </div>
                <div v-if="row.fact.repeat_of" class="match text-caption" data-testid="fact-match">≈ on {{ row.fact.repeat_of.owner_name || 'an entry' }}: {{ row.fact.repeat_of.text }}</div>
            </template>
        </template>

        <div class="heading">{{ branch ? 'Its own drawers' : 'Drawers' }}</div>
        <div v-if="!outline.length" class="text-body-2 text-muted">None of its own: it keeps its parent's.</div>
        <div v-for="drawer in outline" :key="drawer.id" class="drawer" data-testid="preview-drawer">
            <div>
                <span class="drawer-title">{{ drawer.title }}</span>
                <span class="drawer-type ml-2">{{ drawer.type }}</span>
            </div>
            <div v-for="row in drawer.items" :key="row.index" class="item" data-testid="preview-item">
                <div class="d-flex align-center flex-wrap ga-1">
                    <v-checkbox-btn
                        :model-value="row.item.ticked !== false"
                        density="compact"
                        class="flex-grow-0"
                        :aria-label="'Write ' + (row.item.name || row.item.text)"
                        @update:model-value="changeItem(row.index, { ticked: $event })"
                    ></v-checkbox-btn>
                    <span class="flex-grow-1" :class="{ dropped: row.item.ticked === false }">
                        <template v-if="row.item.name"><LinkedText :segments="previewSegments(row.item.name, preview.new_names)" :text="row.item.name" /><span class="text-muted"> — </span></template>
                        <LinkedText :segments="previewSegments(row.item.text, preview.new_names)" :text="row.item.text" />
                    </span>
                    <SameThingAsk
                        v-if="row.item.same_as && row.item.same_as.length"
                        variant="row"
                        :name="row.item.name"
                        :kind="row.item.kind"
                        :offers="row.item.same_as"
                        :chosen="row.item.same_target_id || null"
                        @choose="changeItem(row.index, { same_target_id: $event })"
                    />
                </div>
                <div v-if="matchOf(row.item)" class="match text-caption" data-testid="fact-match">
                    ≈ on {{ matchOf(row.item).owner_name || row.item.name || 'the sphere' }}: {{ matchOf(row.item).text }}<template v-if="row.item.text_repeat_of && row.item.text_ticked === false"> (its text isn't written again)</template>
                </div>
                <OuterBodyForm v-if="row.item.name && !row.item.thing_id && !row.item.same_target_id" :row-name="row.item.name" @submit="worlds.addOuterBody(type, row.item.name, $event)" />
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

        <OuterBodyForm v-if="!branch" :row-name="preview.name" @submit="worlds.addOuterBody(type, preview.name, $event)" />
        <PreviewElsewhere :rows="preview.elsewhere || []" :type="type" :new-names="preview.new_names || []" @update="edit({ elsewhere: $event })" />
        <PreviewStubs :rows="preview.new_names || []" :type="type" @update="edit({ new_names: $event })" />
        <MoveInSection :rows="preview.move_in || []" :refile="preview.refile || []" @update="edit(moveInEdit(preview, $event))" @update-refile="edit({ refile: $event })" />

        <div class="d-flex align-center flex-wrap ga-2 mt-3">
            <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-check" :loading="!!worlds.pending.accept_sphere" :disabled="!name.trim() || !!worlds.pending.add_outer_body" @click="$emit('accept', name.trim())">Accept</v-btn>
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
            <span class="text-caption text-muted" data-testid="accept-counts">{{ countsText }}</span>
        </div>
    </v-card>
</template>

<script>
import { countsLine, moveInEdit, previewCounts, previewSegments, rowChanged, useWorldsStore } from '@/stores/worlds.js';
import { formatDate } from './worldDates.js';
import { UNSORTED, WRITTEN_DRAWER_TYPES } from './worldKinds.js';
import LinkedText from './LinkedText.vue';
import MoveInSection from './MoveInSection.vue';
import OuterBodyForm from './OuterBodyForm.vue';
import PreviewElsewhere from './PreviewElsewhere.vue';
import PreviewStubs from './PreviewStubs.vue';
import SameThingAsk from './SameThingAsk.vue';

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
//
// Curation: each fact and item is ticked as it came, and only the ticked
// ones are written; a named item the world may have already asks "same as
// X?" (new by default, ruling C9), and can be put in a body not yet made,
// as can the sphere itself (ruling C11); the outer bodies show among its
// new stubs, the entries they re-file below. The sphere itself may be one
// the world has: that one is offered "Make X a sphere…" (promotion), never
// accepted onto. A fact or item that repeats what the world holds shows its
// match, as Fill's do. The Accept line counts what it'll write: facts and
// items apart, a named new item as its stub. Edits go to the
// store's preview (`worlds.editPreview`).
export default {
    name: 'SpherePreviewCard',
    components: { LinkedText, MoveInSection, OuterBodyForm, PreviewElsewhere, PreviewStubs, SameThingAsk },
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
        // the preview it is, for its edits and `add_outer_body`
        type() {
            return this.branch ? 'branch' : 'sphere';
        },
        // `{index, fact}` (its index among the preview's facts)
        timeline() {
            return this.preview.facts.map((fact, index) => ({ index, fact })).filter((row) => row.fact.category === 'timeline');
        },
        about() {
            return this.preview.facts.map((fact, index) => ({ index, fact })).filter((row) => row.fact.category !== 'timeline');
        },
        countsText() {
            return countsLine(previewCounts(this.preview));
        },
        // the drawers with their items and adopted entries, then Unsorted
        // when something adopted has no drawer yet
        outline() {
            const names = new Map(this.worlds.referenceTargets.map((target) => [target.id, target.name]));
            const adopted = (drawerId) => (this.preview.adopted || [])
                .filter((entry) => entry.drawer_id === drawerId)
                .map((entry) => ({ ...entry, name: names.get(entry.thing_id) || 'an entry' }));
            const items = this.preview.items.map((item, index) => ({ index, item }));
            const drawers = this.preview.drawers.map((drawer) => ({
                ...drawer,
                items: items.filter((row) => row.item.drawer_id === drawer.id),
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
        moveInEdit,
        previewSegments,
        edit(changes) {
            this.worlds.editPreview(this.type, changes);
        },
        tickFact(index, ticked) {
            this.edit({ facts: rowChanged(this.preview.facts, index, { ticked }) });
        },
        // what an item repeats: its own text's match, or, for an item
        // linking a place the world has, what that place says already
        matchOf(item) {
            return item.repeat_of || item.text_repeat_of || null;
        },
        changeItem(index, changes) {
            this.edit({ items: rowChanged(this.preview.items, index, changes) });
        },
        // the entry the sphere may be is made a sphere instead (a stub is
        // expanded as one)
        promote(offer) {
            this.worlds.makeSphere({ id: offer.thing_id, kind: offer.kind, name: offer.name, stub: !!offer.stub });
        },
        fillLater(drawer) {
            // people, events and branches are made by the app, not written
            return WRITTEN_DRAWER_TYPES.includes(drawer.type) && drawer.id !== UNSORTED && !drawer.items.length && !drawer.adopted.length;
        },
        keptRow(row) {
            const dropped = row.thing_id ? this.preview.drops : this.preview.rejects;
            return !(dropped || []).includes(row.thing_id || row.fact_id);
        },
    },
};
</script>

<style scoped>
.salvaged {
    border-left: 3px solid rgb(var(--v-theme-warning));
    padding: 4px 8px;
    background: rgba(var(--v-theme-warning), 0.12);
}

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

.match {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}

.row .dropped,
.item .dropped {
    text-decoration: none;
}
</style>
