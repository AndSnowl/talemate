<template>
    <v-btn
        variant="outlined"
        :size="size"
        prepend-icon="mdi-swap-horizontal"
        :disabled="disabled || !!worlds.pending.repoint_stub"
        :loading="!!worlds.pending.repoint_stub && sent"
        title="Point every link to this stub at an entry; its names become that entry's other names"
        data-testid="stub-repoint"
        @click="open($event, false)"
    >Re-point…</v-btn>
    <v-btn
        variant="text"
        :size="size"
        :disabled="disabled || !!worlds.pending.repoint_stub"
        title="Re-point, and write one of the entry's names in place of the stub's words"
        data-testid="stub-repoint-name"
        @click="open($event, true)"
    >use the name…</v-btn>
    <ReferenceMenu
        v-model="searching"
        :target="target"
        search-only
        :search-label="byName ? 'Re-point, using a name of…' : 'Re-point every link to…'"
        :exclude="[stub.id]"
        @pick="pick"
    />
    <!-- "use the name…": which of the entry's names the links' words become -->
    <v-menu v-model="naming" :target="target" location="bottom start" :close-on-content-click="false">
        <v-card class="names pa-2" min-width="240" data-testid="repoint-names">
            <div class="text-caption text-muted px-2 pb-1">Every link to “{{ stub.name }}” goes to {{ chosen?.name }}, its words written as:</div>
            <div v-if="!names" class="d-flex justify-center pa-2">
                <v-progress-circular indeterminate size="18" width="2" color="accent"></v-progress-circular>
            </div>
            <v-list v-else density="compact">
                <v-list-item v-for="name in names" :key="name" data-testid="repoint-name-option" @click="repoint(name)">
                    <v-list-item-title>{{ name }}</v-list-item-title>
                </v-list-item>
            </v-list>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import ReferenceMenu from './ReferenceMenu.vue';

// "Re-point…" for a whole stub (the Stubs page, the stub's own page): a
// search (`ReferenceMenu`) for the entry the stub means, then
// `repoint_stub`, which moves every link to the stub there, teaches that
// entry the stub's names and removes the stub. "use the name…" is the hard
// re-point (spec "Fixed along the way"): after the search, the owner picks
// one of that entry's names (its name and other names, `fetchNames`), and
// every link's words become it (`use_name`); if its names can't be had
// (the entry is gone), the choice closes.
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
        return { searching: false, naming: false, byName: false, target: null, chosen: null, sent: false };
    },
    computed: {
        names() {
            return this.chosen ? this.worlds.namesOf[this.chosen.id] || null : null;
        },
    },
    watch: {
        'worlds.pending.repoint_stub'(pending) {
            if (!pending) {
                this.sent = false;
            }
        },
        // the entry's names couldn't be had (it's gone): nothing to pick
        'worlds.namesFailed'(id) {
            if (id && id === this.chosen?.id) {
                this.naming = false;
                this.chosen = null;
            }
        },
    },
    methods: {
        open(event, byName) {
            this.byName = byName;
            this.target = [event.clientX, event.clientY];
            this.searching = true;
        },
        pick(target) {
            if (this.byName) {
                this.chosen = { id: target.id, name: target.name };
                this.worlds.fetchNames(target.id);
                this.naming = true;
                return;
            }
            this.sent = true;
            this.worlds.repointStub(this.stub.id, target.id);
        },
        repoint(name) {
            this.naming = false;
            this.sent = true;
            this.worlds.repointStub(this.stub.id, this.chosen.id, name);
        },
    },
};
</script>

<style scoped>
.names {
    background: rgb(var(--v-theme-raised));
}
</style>
