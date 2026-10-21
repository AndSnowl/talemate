<template>
    <v-card class="stub-card pa-3" :class="{ flat: onPage }" :variant="onPage ? 'flat' : 'elevated'" min-width="260" data-testid="stub-card">
        <div class="d-flex align-center ga-2">
            <a v-if="!onPage" href="#" class="stub-name" @click.prevent="worlds.openThing(stub.id)">{{ stub.name }}</a>
            <span class="text-caption text-muted">{{ stub.ignored ? 'ignored, not made yet' : 'not made yet' }}</span>
        </div>
        <div class="d-flex align-center ga-3 mt-2">
            <v-select
                :model-value="stub.kind"
                :items="kindItems"
                label="Kind (a guess)"
                density="compact"
                variant="outlined"
                hide-details
                class="kind-select"
                :disabled="busy || !stub.kind"
                data-testid="stub-kind"
                @update:model-value="setKind"
            ></v-select>
            <span v-if="stub.mentions != null" class="text-caption text-muted" data-testid="stub-mentions">{{ mentionsLabel }}</span>
        </div>
        <div class="d-flex ga-2 mt-3">
            <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-creation" :disabled="!expandable || busy" @click="expand">Expand</v-btn>
            <v-btn variant="outlined" size="small" :prepend-icon="stub.ignored ? 'mdi-eye' : 'mdi-eye-off'" :loading="!!worlds.pending.ignore_stub" :disabled="busy" @click="worlds.ignoreStub(stub.id, !stub.ignored)">
                {{ stub.ignored ? 'Unignore' : 'Ignore' }}
            </v-btn>
        </div>
        <div v-if="stub.kind && !expandable" class="text-caption text-muted mt-2" data-testid="expand-later">{{ expandLaterNote }}</div>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { EXPAND_LATER_NOTE, STUB_KINDS, canExpand, kindInfo } from './worldKinds.js';

// One stub's card: its name (opening its page) and "not made yet", its
// kind (a guess the owner can change), its mention count, Expand (its
// kind's create box, from the stub; a culture can't be yet) and Ignore (or
// Unignore). Shown on hover over a stub link, and on the stub's own page
// (`onPage`, without the name).
export default {
    name: 'StubCard',
    props: {
        // `{id, name, kind, mentions, ignored}`; `kind` and `mentions` may
        // be null while the stubs aren't listed yet
        stub: { type: Object, required: true },
        onPage: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { expandLaterNote: EXPAND_LATER_NOTE };
    },
    computed: {
        kindItems() {
            const kinds = STUB_KINDS.includes(this.stub.kind) || !this.stub.kind ? STUB_KINDS : [...STUB_KINDS, this.stub.kind];
            return kinds.map((kind) => ({ title: kindInfo(kind)?.singular || kind, value: kind }));
        },
        mentionsLabel() {
            const count = this.stub.mentions;
            return `${count} mention${count === 1 ? '' : 's'}`;
        },
        expandable() {
            return !!this.stub.kind && canExpand(this.stub.kind);
        },
        busy() {
            return !!this.worlds.pending.change_stub_kind;
        },
    },
    methods: {
        setKind(kind) {
            if (kind && kind !== this.stub.kind) {
                this.worlds.changeStubKind(this.stub.id, kind);
            }
        },
        expand() {
            this.worlds.expandStub(this.stub);
        },
    },
};
</script>

<style scoped>
.stub-card {
    background: rgb(var(--v-theme-raised));
    font-size: 13px;
}

.stub-card.flat {
    background: transparent;
    padding: 0 !important;
}

.stub-name {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
    font-weight: 600;
}

.kind-select {
    max-width: 170px;
}
</style>
