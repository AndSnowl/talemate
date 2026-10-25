<template>
    <span ref="root" class="linked-text" @contextmenu="contextMenu"><template v-for="(segment, index) in shown" :key="index"><a
        v-if="segment.ref && !segment.stub && !repoint"
        class="linked-ref"
        data-testid="linked-ref"
        href="#"
        @click.prevent="worlds.openThing(segment.ref)"
    >{{ segment.text }}</a><v-menu
        v-else-if="segment.ref && !segment.stub"
        :model-value="openCard === index"
        open-on-hover
        :open-delay="250"
        :close-delay="200"
        :close-on-content-click="false"
        location="bottom start"
        @update:model-value="setCard(index, $event)"
    >
        <template #activator="{ props }"><a
            v-bind="props"
            class="linked-ref"
            data-testid="linked-ref"
            href="#"
            @click.prevent="worlds.openThing(segment.ref)"
        >{{ segment.text }}</a></template>
        <v-card class="link-card pa-3" min-width="220" data-testid="link-card">
            <a href="#" class="link-name" @click.prevent="worlds.openThing(segment.ref)">{{ targetName(segment) }}</a>
            <div class="d-flex ga-2 mt-2">
                <v-btn variant="outlined" size="small" prepend-icon="mdi-swap-horizontal" @click="startRepoint(index, $event)">Re-point…</v-btn>
            </div>
        </v-card>
    </v-menu><v-menu
        v-else-if="segment.ref"
        :model-value="openCard === index"
        open-on-hover
        :open-delay="250"
        :close-delay="200"
        :close-on-content-click="false"
        location="bottom start"
        @update:model-value="setCard(index, $event)"
    >
        <template #activator="{ props }"><a
            v-bind="props"
            class="linked-stub"
            data-testid="linked-stub"
            href="#"
            @click.prevent="follow(segment)"
        >{{ segment.text }}</a></template>
        <StubCard :stub="stubOf(segment)">
            <v-btn v-if="repoint" variant="outlined" size="small" prepend-icon="mdi-swap-horizontal" @click="startRepoint(index, $event)">Re-point…</v-btn>
        </StubCard>
    </v-menu><span
        v-else-if="segment.fresh"
        class="linked-stub fresh"
        data-testid="linked-new"
        :title="`A new ${segment.kind || 'name'}: a stub once accepted`"
    >{{ segment.text }}</span><template v-else>{{ segment.text }}</template></template><ReferenceMenu
        v-if="repoint"
        v-model="repointOpen"
        :target="repointTarget"
        search-only
        search-label="Re-point to…"
        :exclude="repointExclude"
        @pick="repointTo"
    /><NameModeMenu
        v-if="repoint"
        v-model="choosing"
        :target="repointTarget"
        :words="repointing === null ? '' : shown[repointing]?.text || ''"
        :thing="chosen"
        @choose="repointAs"
    /></span>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { canExpand } from './worldKinds.js';
import NameModeMenu from './NameModeMenu.vue';
import ReferenceMenu from './ReferenceMenu.vue';
import StubCard from './StubCard.vue';

// Text with its names linked, from the backend's `segments` (`{text, ref,
// stub}` runs; a preview's are made by `previewSegments`). A run linking an
// entry is a solid link that opens its page; one linking a stub is dashed,
// in the stub colour, with the stub's card on hover (not made yet, its
// kind, its mentions, Expand and Ignore), and clicking it expands it (a
// race or mix stub, which can't be expanded here, opens its page). A `fresh` run is a name a preview invents: stub-styled, with no card, since the stub is
// only made on accept. With no segments, `text` shows as it is.
//
// With `repoint` (an own fact on its thing's page), an entry link gets a
// hover card too, and both cards offer "Re-point…": a search
// (`ReferenceMenu`) for the thing the link should mean, then how it takes
// the words (`NameModeMenu`, P4: another name of it, or renamed to one of
// its names), emitted as `repoint {index, to, useName}` (`index` into
// `segments`; `useName` null to keep the words); the page rewrites the
// fact. `exclude` are ids never offered.
//
// With `selectable` (a fact's words), right-clicking selected words inside
// it emits `select {start, end, words, x, y}` instead of the browser's
// menu: `start`/`end` count UTF-16 code units (the browser's own measure,
// ruling F18) from the start of the text shown, which is the fact's
// `rendered` text. A right-click with no selection in it goes on to the
// row (its fact menu).
export default {
    name: 'LinkedText',
    components: { NameModeMenu, ReferenceMenu, StubCard },
    props: {
        segments: { type: Array, default: null },
        text: { type: String, default: '' },
        repoint: { type: Boolean, default: false },
        exclude: { type: Array, default: () => [] },
        selectable: { type: Boolean, default: false },
    },
    emits: ['repoint', 'select'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            // the run whose hover card is open
            openCard: null,
            // the run being re-pointed, and where its search shows
            repointing: null,
            repointOpen: false,
            repointTarget: null,
            // the thing picked, while its mode is chosen
            chosen: null,
            choosing: false,
        };
    },
    computed: {
        shown() {
            return this.segments && this.segments.length ? this.segments : [{ text: this.text, ref: null, stub: false }];
        },
        repointExclude() {
            const current = this.repointing === null ? null : this.shown[this.repointing]?.ref;
            return current ? [...this.exclude, current] : this.exclude;
        },
    },
    methods: {
        // the stub's listing, else what the run itself says
        stubOf(segment) {
            return this.worlds.stubInfo(segment.ref) || { id: segment.ref, name: segment.text, kind: null, mentions: null, ignored: false };
        },
        // the linked entry's name (its listing), else the words linked
        targetName(segment) {
            return this.worlds.referenceTargets.find((target) => target.id === segment.ref)?.name || segment.text;
        },
        follow(segment) {
            const stub = this.stubOf(segment);
            if (stub.kind && canExpand(stub.kind)) {
                this.worlds.expandStub(stub);
            } else {
                this.worlds.openThing(segment.ref);
            }
        },
        setCard(index, open) {
            if (open) {
                this.openCard = index;
            } else if (this.openCard === index) {
                this.openCard = null;
            }
        },
        // the selected words, if a selection lies inside the text
        contextMenu(event) {
            if (!this.selectable) {
                return;
            }
            const selection = window.getSelection();
            if (!selection || !selection.rangeCount || selection.isCollapsed) {
                return;
            }
            const range = selection.getRangeAt(0);
            const root = this.$refs.root;
            if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) {
                return;
            }
            const before = document.createRange();
            before.selectNodeContents(root);
            before.setEnd(range.startContainer, range.startOffset);
            const start = before.toString().length;
            const words = range.toString();
            if (!words.trim()) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            this.$emit('select', { start, end: start + words.length, words, x: event.clientX, y: event.clientY });
        },
        startRepoint(index, event) {
            this.openCard = null;
            this.repointing = index;
            this.repointTarget = [event.clientX, event.clientY];
            this.repointOpen = true;
        },
        repointTo(target) {
            if (this.repointing !== null) {
                this.chosen = { id: target.id, name: target.name };
                this.choosing = true;
            }
        },
        repointAs({ useName }) {
            if (this.repointing !== null && this.chosen) {
                this.$emit('repoint', { index: this.repointing, to: this.chosen.id, useName });
            }
            this.repointing = null;
            this.chosen = null;
        },
    },
};
</script>

<style scoped>
.linked-ref {
    color: rgb(var(--v-theme-link));
    text-decoration: underline;
    text-underline-offset: 2px;
}

.linked-stub {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
    text-underline-offset: 2px;
    cursor: pointer;
}

.linked-stub.fresh {
    cursor: help;
}

.link-card {
    background: rgb(var(--v-theme-raised));
    font-size: 13px;
}

.link-name {
    color: rgb(var(--v-theme-link));
    font-weight: 600;
}
</style>
