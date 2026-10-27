<template>
    <div class="text-body-2 text-muted mb-1" data-testid="draft-title">{{ title }}</div>
    <SuggestionBar
        label="Draft"
        :versions="versions"
        :version="draft.version"
        :prompt="worlds.previewRequest?.prompt || ''"
        :picks="worlds.draftPromptPicks"
        prompt-label="Prompt"
        :busy="busy"
        :locked="locked"
        primary-label="Accept"
        :can-primary="canAccept"
        :primary-loading="draft.accepting"
        testid="draft-bar"
        prompt-testid="draft-prompt"
        :testids="{ versions: 'draft-versions', version: 'draft-version', discard: 'draft-discard' }"
        @update:prompt="worlds.setDraftPrompt($event)"
        @update:picks="worlds.setDraftPicks($event)"
        @regenerate="worlds.regeneratePreview()"
        @use-version="worlds.useVersion($event)"
        @discard="worlds.discardPreview()"
        @primary="$emit('accept')"
    >
        <template v-if="matchingStub" #primary-extra>
            <FillStubButton
                :name="matchingStub.name"
                :loading="!!draft.accepting"
                :disabled="busy || !canAccept || !!locked"
                :title="locked"
                @fill="$emit('fill-stub')"
            />
        </template>
        <template #status>
            <template v-if="worlds.previewPending">
                <v-progress-circular indeterminate size="14" width="2" color="accent"></v-progress-circular>
                <span class="text-caption text-muted" data-testid="draft-regenerating">Drafting another version…</span>
            </template>
            <span v-else class="text-caption text-muted">Nothing is written until you accept.</span>
            <v-spacer></v-spacer>
            <span class="text-caption" data-testid="accept-counts">{{ counts }}</span>
        </template>
    </SuggestionBar>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { versionRows } from './draftPage.js';
import { kindInfo } from './worldKinds.js';
import FillStubButton from './FillStubButton.vue';
import SuggestionBar from './SuggestionBar.vue';

// The draft page's bar (spec "The draft page"), on `SuggestionBar`: what
// it is ("New lore", "from the stub X"), its prompt (always on screen and
// editable: `setDraftPrompt`), "Version n of m ▾" (every version kept
// this session, any one restored as the owner left it: `useVersion`),
// ↻ Regenerate (a new version from the edited prompt), Discard (every
// version goes, nothing written) and Accept (emitted: the page knows what
// goes with it), with what Accept would write (`counts`) and that nothing
// is written before; while a Regenerate is out, "Drafting another
// version…" with a spinner in its place. `locked` (from
// `worlds.nestedHeld`, via the page) disables Regenerate, the version
// switch and Accept, with its reason; Discard stays on. With a stub of
// its kind named like it (`matchingStub`), "Fill stub X" sits right by
// Accept: another way to accept.
export default {
    name: 'DraftBar',
    components: { FillStubButton, SuggestionBar },
    props: {
        draft: { type: Object, required: true },
        // the Accept line ("writes 3 facts here, …")
        counts: { type: String, default: '' },
        canAccept: { type: Boolean, default: true },
        // a reason the owner can't regenerate, switch version or accept
        // right now (a nested fact draft is open or held), or null
        locked: { type: String, default: null },
        // a stub of its kind named like the draft (`{id, name}`), offered
        // as "Fill stub X" right by Accept (emitted: `fill-stub`), or null
        matchingStub: { type: Object, default: null },
    },
    emits: ['accept', 'fill-stub'],
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
