<template>
    <div class="sphere-timeline" data-testid="sphere-timeline">
        <EntryTimeline :lines="timeline" :sphere="sphere" />
    </div>
</template>

<script>
import EntryTimeline from './EntryTimeline.vue';

// A sphere's Timeline: its `sphere.timeline` lines (its undated timeline
// facts first, then its entry timeline: its own dated facts and what it
// gathers from its parts and the entries naming it) as an `EntryTimeline`
// in sphere mode -- its own timeline facts edited here, a drawer's
// statement only in its drawer (ruling C21), "+ Add to the timeline".
export default {
    name: 'SphereTimeline',
    components: { EntryTimeline },
    props: {
        // the sphere payload's `timeline`
        timeline: { type: Array, required: true },
        // the sphere payload (its drawers)
        sphere: { type: Object, required: true },
    },
};
</script>
