<template>
    <div class="stubs-tab" data-testid="stubs-tab">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <span class="text-h6 tab-title">Stubs</span>
            <span class="text-body-2 text-muted">named but not made yet</span>
            <v-spacer></v-spacer>
            <v-checkbox v-model="showIgnored" label="show ignored" density="compact" hide-details class="flex-grow-0"></v-checkbox>
        </div>

        <div v-if="!shown.length" class="empty-hint pa-4 text-body-2">
            {{ showIgnored ? 'No stubs.' : 'No stubs to follow. Names the AI invents in new entries show up here.' }}
        </div>
        <v-table v-else density="compact" class="stubs-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Kind</th>
                    <th>First mentioned</th>
                    <th>Mentions</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="stub in shown" :key="stub.id" :class="{ ignored: stub.ignored }" data-testid="stub-row">
                    <td>
                        <a href="#" class="stub-name" :class="{ ignored: stub.ignored }" @click.prevent="worlds.openThing(stub.id)">{{ stub.name }}</a>
                    </td>
                    <td>
                        <span v-if="stub.ignored">{{ kindLabel(stub.kind) }}</span>
                        <v-select
                            v-else
                            :model-value="stub.kind"
                            :items="kindItems(stub.kind)"
                            aria-label="Kind"
                            density="compact"
                            variant="plain"
                            hide-details
                            class="kind-select"
                            :disabled="!!worlds.pending.change_stub_kind"
                            @update:model-value="setKind(stub, $event)"
                        ></v-select>
                    </td>
                    <td>
                        <a v-if="stub.first_mentioned" href="#" class="thing-link" @click.prevent="worlds.openThing(stub.first_mentioned.thing_id)">{{ stub.first_mentioned.name }}</a>
                        <span v-else class="text-muted">—</span>
                    </td>
                    <td>{{ stub.mentions }}</td>
                    <td class="actions">
                        <template v-if="stub.ignored">
                            <span class="text-caption text-muted mr-2">ignored, revived if a scene uses it</span>
                            <v-btn variant="outlined" size="x-small" :disabled="busy" @click="worlds.ignoreStub(stub.id, false)">Unignore</v-btn>
                        </template>
                        <template v-else>
                            <v-btn
                                color="accent"
                                variant="flat"
                                size="x-small"
                                class="mr-1"
                                :disabled="busy || !canExpand(stub.kind)"
                                :title="expandNote(stub.kind) || ''"
                                @click="worlds.expandStub(stub)"
                            >Expand</v-btn>
                            <v-btn variant="outlined" size="x-small" :disabled="busy" @click="worlds.ignoreStub(stub.id, true)">Ignore</v-btn>
                            <div v-if="!canExpand(stub.kind)" class="text-caption text-muted" data-testid="expand-later">{{ expandNote(stub.kind) }}</div>
                        </template>
                    </td>
                </tr>
            </tbody>
        </v-table>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { STUB_KINDS, canExpand, expandNote, kindInfo } from './worldKinds.js';

// The World tab's Stubs: every name mentioned but not made yet, with its
// kind (changeable), where it was first mentioned, its mention count,
// Expand and Ignore. Ignored stubs are hidden until "show ignored", and can
// be brought back.
export default {
    name: 'StubsTab',
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { showIgnored: false };
    },
    computed: {
        shown() {
            return this.worlds.stubs.filter((stub) => this.showIgnored || !stub.ignored);
        },
        busy() {
            return !!this.worlds.pending.ignore_stub || !!this.worlds.pending.change_stub_kind;
        },
    },
    mounted() {
        this.worlds.listStubs();
    },
    methods: {
        canExpand,
        expandNote,
        kindLabel(kind) {
            return kindInfo(kind)?.singular || kind;
        },
        kindItems(kind) {
            const kinds = STUB_KINDS.includes(kind) ? STUB_KINDS : [...STUB_KINDS, kind];
            return kinds.map((value) => ({ title: this.kindLabel(value), value }));
        },
        setKind(stub, kind) {
            if (kind && kind !== stub.kind) {
                this.worlds.changeStubKind(stub.id, kind);
            }
        },
    },
};
</script>

<style scoped>
.tab-title {
    font-family: 'Alegreya', serif;
    color: rgb(var(--v-theme-accent));
}

.stubs-table {
    background: transparent;
}

.stub-name {
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}

.stub-name.ignored {
    color: rgb(var(--v-theme-muted));
    text-decoration: line-through;
}

tr.ignored td {
    color: rgb(var(--v-theme-muted));
}

.thing-link {
    color: rgb(var(--v-theme-link));
}

.kind-select {
    min-width: 120px;
}

.actions {
    white-space: nowrap;
}

.empty-hint {
    background: rgba(var(--v-theme-on-surface), 0.03);
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
    color: rgb(var(--v-theme-muted));
}
</style>
