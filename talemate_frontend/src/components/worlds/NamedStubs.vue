<template>
    <div v-if="stubs.length" class="named-stubs mt-4" data-testid="named-stubs">
        <div class="text-overline text-muted">Stubs this entry named</div>
        <div class="d-flex flex-wrap align-center ga-3">
            <span v-for="stub in stubs" :key="stub.id" class="named-stub">
                <LinkedText :segments="[{ text: stub.name, ref: stub.id, stub: true }]" />
                <v-chip size="x-small" label variant="outlined" color="muted" class="ml-1">{{ stub.kind }}?</v-chip>
            </span>
        </div>
    </div>
</template>

<script>
import LinkedText from './LinkedText.vue';

// The stubs an entry's facts name (`named_stubs`), as stub links with their
// guessed kind: the next steps to follow from this entry.
export default {
    name: 'NamedStubs',
    components: { LinkedText },
    props: {
        // `{id, name, kind}`
        stubs: { type: Array, default: () => [] },
    },
};
</script>
