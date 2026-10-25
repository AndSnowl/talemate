<template>
    <v-btn
        variant="outlined"
        :size="size"
        prepend-icon="mdi-swap-horizontal"
        :disabled="disabled || !!worlds.pending.repoint_stub"
        :loading="!!worlds.pending.repoint_stub && sent"
        title="Point every link to this stub at an entry: its words become another name of it, or one of its names"
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
    <NameModeMenu v-model="choosing" :target="target" :words="stub.name" :thing="chosen" @choose="repoint" />
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import NameModeMenu from './NameModeMenu.vue';
import ReferenceMenu from './ReferenceMenu.vue';

// "Re-point…" for a whole stub (the Stubs page, the stub's own page): a
// search (`ReferenceMenu`) for the entry the stub means, then the mode
// chooser (`NameModeMenu`, P4): "add as another name" (`repoint_stub`
// moves every link to the stub there, keeping its words, teaches that
// entry the stub's names and the words, and removes the stub) or "Rename
// to…" one of that entry's names, which every link's words become (the
// hard re-point, `use_name`).
export default {
    name: 'StubRepointButton',
    components: { NameModeMenu, ReferenceMenu },
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
        return { searching: false, choosing: false, target: null, chosen: null, sent: false };
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
            this.chosen = { id: target.id, name: target.name };
            this.choosing = true;
        },
        repoint({ useName }) {
            this.sent = true;
            this.worlds.repointStub(this.stub.id, this.chosen.id, useName);
        },
    },
};
</script>
