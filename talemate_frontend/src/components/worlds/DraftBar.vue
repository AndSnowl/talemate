<template>
    <div class="draft-bar pa-2 mb-3" data-testid="draft-bar">
        <div class="d-flex align-center flex-wrap ga-2">
            <v-chip size="small" label color="accent" variant="flat">Draft</v-chip>
            <span class="text-body-2">{{ title }}</span>
            <v-menu location="bottom start">
                <template #activator="{ props }">
                    <v-btn
                        v-bind="props"
                        variant="outlined"
                        size="small"
                        append-icon="mdi-menu-down"
                        :disabled="busy"
                        data-testid="draft-versions"
                    >Version {{ draft.version }} of {{ draft.versions.length }}</v-btn>
                </template>
                <v-list density="compact">
                    <v-list-item
                        v-for="row in versions"
                        :key="row.version"
                        :prepend-icon="row.current ? 'mdi-radiobox-marked' : 'mdi-radiobox-blank'"
                        :title="row.label"
                        :subtitle="row.prompt"
                        :active="row.current"
                        data-testid="draft-version"
                        @click="worlds.useVersion(row.version)"
                    ></v-list-item>
                </v-list>
            </v-menu>
            <v-spacer></v-spacer>
            <v-btn
                variant="outlined"
                size="small"
                prepend-icon="mdi-refresh"
                :loading="worlds.previewPending"
                :disabled="busy"
                @click="worlds.regeneratePreview()"
            >Regenerate</v-btn>
            <v-btn variant="outlined" size="small" prepend-icon="mdi-pencil" :disabled="busy" @click="worlds.editPrompt()">Edit prompt</v-btn>
            <v-btn variant="outlined" size="small" color="danger" prepend-icon="mdi-close" :disabled="busy" data-testid="draft-discard" @click="worlds.discardPreview()">Discard</v-btn>
            <v-btn
                color="accent"
                variant="flat"
                size="small"
                prepend-icon="mdi-check"
                :loading="draft.accepting"
                :disabled="busy || !canAccept"
                @click="$emit('accept')"
            >Accept</v-btn>
        </div>
        <div class="d-flex align-center flex-wrap ga-2 mt-1">
            <span class="text-caption text-muted">Nothing is written until you accept.</span>
            <v-spacer></v-spacer>
            <span class="text-caption" data-testid="accept-counts">{{ counts }}</span>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { versionRows } from './draftPage.js';
import { kindInfo } from './worldKinds.js';

// The draft page's bar (spec "The draft page"): what it is ("New lore",
// "from the stub X"), "Version n of m ▾" (every version kept this session,
// any one restored as the owner left it: `useVersion`), ↻ Regenerate (a
// new version from the same request), Edit prompt (back to the create
// box, the draft kept), Discard (every version goes, nothing written) and
// Accept (emitted: the page knows what goes with it), with what Accept
// would write (`counts`) and that nothing is written before.
export default {
    name: 'DraftBar',
    props: {
        draft: { type: Object, required: true },
        // the Accept line ("writes 3 facts here, …")
        counts: { type: String, default: '' },
        canAccept: { type: Boolean, default: true },
    },
    emits: ['accept'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        busy() {
            return this.worlds.previewPending || !!this.draft.accepting || !!this.worlds.pending.use_version;
        },
        title() {
            const edited = this.draft.edited;
            const kind = kindInfo(edited.kind)?.singular || edited.kind;
            if (edited.stub_id) {
                return `${kind} from the stub “${this.draft.page.name || edited.name}”`;
            }
            return `New ${kind} “${edited.name}”`;
        },
        versions() {
            return versionRows(this.draft.versions, this.draft.version);
        },
    },
};
</script>

<style scoped>
.draft-bar {
    border: 1px solid rgb(var(--v-theme-accent));
    border-radius: 6px;
    background: rgba(var(--v-theme-accent), 0.06);
}
</style>
