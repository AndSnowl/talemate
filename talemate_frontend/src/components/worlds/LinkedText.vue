<template>
    <span class="linked-text"><template v-for="(segment, index) in shown" :key="index"><a
        v-if="segment.ref && !segment.stub"
        class="linked-ref"
        data-testid="linked-ref"
        href="#"
        @click.prevent="worlds.openThing(segment.ref)"
    >{{ segment.text }}</a><v-menu
        v-else-if="segment.ref"
        open-on-hover
        :open-delay="250"
        :close-delay="200"
        :close-on-content-click="false"
        location="bottom start"
    >
        <template #activator="{ props }"><a
            v-bind="props"
            class="linked-stub"
            data-testid="linked-stub"
            href="#"
            @click.prevent="follow(segment)"
        >{{ segment.text }}</a></template>
        <StubCard :stub="stubOf(segment)" />
    </v-menu><span
        v-else-if="segment.fresh"
        class="linked-stub fresh"
        data-testid="linked-new"
        :title="`A new ${segment.kind || 'name'}: a stub once accepted`"
    >{{ segment.text }}</span><template v-else>{{ segment.text }}</template></template></span>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { canExpand } from './worldKinds.js';
import StubCard from './StubCard.vue';

// Text with its names linked, from the backend's `segments` (`{text, ref,
// stub}` runs; a preview's are made by `previewSegments`). A run linking an
// entry is a solid link that opens its page; one linking a stub is dashed,
// in the stub colour, with the stub's card on hover (not made yet, its
// kind, its mentions, Expand and Ignore), and clicking it expands it (a
// stub that can't be expanded here, a culture, race or mix, opens its page). A `fresh` run is a
// name a preview invents: stub-styled, with no card, since the stub is
// only made on accept. With no segments, `text` shows as it is.
export default {
    name: 'LinkedText',
    components: { StubCard },
    props: {
        segments: { type: Array, default: null },
        text: { type: String, default: '' },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        shown() {
            return this.segments && this.segments.length ? this.segments : [{ text: this.text, ref: null, stub: false }];
        },
    },
    methods: {
        // the stub's listing, else what the run itself says
        stubOf(segment) {
            return this.worlds.stubInfo(segment.ref) || { id: segment.ref, name: segment.text, kind: null, mentions: null, ignored: false };
        },
        follow(segment) {
            const stub = this.stubOf(segment);
            if (stub.kind && canExpand(stub.kind)) {
                this.worlds.expandStub(stub);
            } else {
                this.worlds.openThing(segment.ref);
            }
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
</style>
