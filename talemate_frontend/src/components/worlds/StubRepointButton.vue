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
    <NameModeMenu v-model="choosing" :target="target" :words="stub.name" :thing="chosen" name-default @choose="repoint" />
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import NameModeMenu from './NameModeMenu.vue';
import ReferenceMenu from './ReferenceMenu.vue';

// "Re-point…" for a whole stub (the Stubs page, the stub's own page): a
// search (`ReferenceMenu`) for the entry the stub means, then the mode
// chooser (`NameModeMenu`, P4, ruling H2; a stub's words are a name, so
// "add as another name" is its default): `repoint_stub` moves every link
// to the stub there and removes the stub, keeping the links' words and
// teaching that entry the stub's names and the words ("add as another
// name"), teaching nothing ("Link only", `mode: 'link'`), or writing one
// of that entry's names in every link's words ("Rename to…", the hard
// re-point, `use_name`).
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
        repoint({ mode, useName }) {
            this.sent = true;
            this.worlds.repointStub(this.stub.id, this.chosen.id, useName, mode === 'link' ? 'link' : null);
        },
    },
};
</script>
