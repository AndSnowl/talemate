<template>
    <v-btn
        variant="outlined"
        :size="size"
        prepend-icon="mdi-swap-horizontal"
        :disabled="disabled || !!worlds.pending.repoint_stub"
        :loading="!!worlds.pending.repoint_stub && sent"
        title="Point every link to this stub at an entry; its names become that entry's other names"
        data-testid="stub-repoint"
        @click="open"
    >Re-point…</v-btn>
    <ReferenceMenu
        v-model="searching"
        :target="target"
        search-only
        search-label="Re-point every link to…"
        :exclude="[stub.id]"
        @pick="pick"
    />
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import ReferenceMenu from './ReferenceMenu.vue';

// "Re-point…" for a whole stub (the Stubs page, the stub's own page): a
// search (`ReferenceMenu`) for the entry the stub means, then
// `repoint_stub`, which moves every link to the stub there, teaches that
// entry the stub's names and removes the stub.
export default {
    name: 'StubRepointButton',
    components: { ReferenceMenu },
    props: {
        // `{id, name}`
        stub: { type: Object, required: true },
        size: { type: String, default: 'small' },
        disabled: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { searching: false, target: null, sent: false };
    },
    watch: {
        'worlds.pending.repoint_stub'(pending) {
            if (!pending) {
                this.sent = false;
            }
        },
    },
    methods: {
        open(event) {
            this.target = [event.clientX, event.clientY];
            this.searching = true;
        },
        pick(target) {
            this.sent = true;
            this.worlds.repointStub(this.stub.id, target.id);
        },
    },
};
</script>
