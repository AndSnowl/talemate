<template>
    <div class="group-add pa-2" data-testid="group-add">
        <template v-if="!found">
            <div class="d-flex align-center ga-2">
                <v-text-field
                    v-model="prompt"
                    :label="promptLabel"
                    :placeholder="tag ? `two more ${heading.toLowerCase()}, …` : 'a guild of ice-road pilots, …'"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    data-testid="group-add-prompt"
                    @keydown.enter="draft"
                    @keydown.esc="$emit('close')"
                ></v-text-field>
                <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-creation" :disabled="!prompt.trim()" data-testid="group-add-draft" @click="draft">Draft</v-btn>
                <v-btn variant="text" size="small" @click="$emit('close')">Cancel</v-btn>
            </div>
        </template>

        <!-- its first ask: nothing held yet -->
        <template v-else-if="!found.versions.length">
            <div v-if="found.pending" class="d-flex align-center ga-2 text-caption text-muted">
                <v-progress-circular indeterminate size="16" width="2" color="accent"></v-progress-circular>
                Drafting “{{ found.prompt }}”…
                <v-btn variant="text" size="small" data-testid="group-add-discard" @click="discard">Discard</v-btn>
            </div>
            <template v-else>
                <div class="text-caption text-error" data-testid="group-add-error">{{ found.error }}</div>
                <div class="d-flex ga-2 mt-1">
                    <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" data-testid="group-add-regenerate" @click="worlds.regenerateSmall(found.key)">Try again</v-btn>
                    <v-btn variant="text" size="small" data-testid="group-add-discard" @click="discard">Close</v-btn>
                </div>
            </template>
        </template>

        <template v-else>
            <SuggestionBar
                label="Add draft"
                :versions="versionRows"
                :version="found.version"
                :prompt="found.prompt"
                :prompt-label="promptLabel"
                prompt-testid="group-add-prompt"
                :busy="busy"
                :locked="found.pending ? 'drafting another version…' : null"
                :primary-label="'Add ' + ticked"
                :can-primary="ticked > 0"
                :primary-loading="!!found.accepting"
                testid="group-add-bar"
                :testids="barIds"
                @update:prompt="worlds.setSmallPrompt(found.key, $event)"
                @regenerate="worlds.regenerateSmall(found.key)"
                @use-version="worlds.useSmallVersion(found.key, $event)"
                @discard="discard"
                @primary="accept"
            >
                <template #status>
                    <template v-if="found.pending">
                        <v-progress-circular indeterminate size="14" width="2" color="accent"></v-progress-circular>
                        <span class="text-caption text-muted">Drafting another version…</span>
                    </template>
                    <span v-else-if="found.error" class="text-caption text-error" data-testid="group-add-error">{{ found.error }}</span>
                    <span v-else class="text-caption text-muted">Tick what to add: each becomes a stub filed here, its line its first fact.</span>
                </template>
            </SuggestionBar>

            <SuggestionRow
                v-for="(row, index) in rows"
                :key="index"
                :ticked="row.ticked !== false"
                :tick-label="'Add ' + row.name"
                :disabled="rowsOff"
                testid="group-add-row"
                @tick="change(index, { ticked: $event })"
            >
                <div class="d-flex align-center ga-2">
                    <v-text-field
                        :model-value="row.name"
                        density="compact"
                        variant="plain"
                        hide-details
                        class="draft-name"
                        :disabled="rowsOff"
                        :aria-label="'Name of ' + row.name"
                        @update:model-value="change(index, { name: $event })"
                    ></v-text-field>
                    <span class="text-body-2">{{ row.line }}</span>
                </div>
                <template #under>
                    <v-chip size="x-small" label variant="tonal" color="muted">{{ row.kind }}</v-chip>
                    <v-chip v-if="row.tag" size="x-small" label variant="outlined" color="foreign">{{ row.tag }}</v-chip>
                    <span v-if="row.show_under" class="text-caption text-muted" data-testid="group-add-row-show-under">shows under {{ heading }}</span>
                </template>
            </SuggestionRow>
            <div v-if="!rows.length" class="text-caption text-muted">Nothing to add from that.</div>

            <SuggestionBar
                foot
                class="mt-2"
                :busy="busy"
                :locked="found.pending ? 'drafting another version…' : null"
                :primary-label="'Add ' + ticked"
                :can-primary="ticked > 0"
                :primary-loading="!!found.accepting"
                testid="group-add-foot"
                :testids="footIds"
                @discard="discard"
                @primary="accept"
            />
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { tagHeading } from './entryPage.js';
import { groupDraftKey, smallVersionRows } from './smallDrafts.js';
import SuggestionBar from './SuggestionBar.vue';
import SuggestionRow from './SuggestionRow.vue';

// A group's "+ Add" (or, with no `tag`, the page's own top-level one):
// the owner's prompt drafts up to three new entries (`group_add`), which
// come back as a small draft (`group:<id>:<tag>`, `worlds.smallDrafts`)
// with a page draft's feature set (plan "polish-1"): its bar
// (`SuggestionBar`: "Add draft", "Version n of m ▾", the prompt kept and
// editable, Regenerate from it, Discard, "Add N"), its rows to tick
// (`SuggestionRow`, a name editable in its own line, its kind and tag
// chips plus "shows under …" under it). "Add N" comes again at the
// list's foot. Add writes the ticked ones as stubs filed in the page
// (`accept_group_add`); Discard drops them. Nothing is written before
// Add. In a group that exists through its rows' `show_under`
// (`showUnder`, ruling H5: a town's Natives), each new row keeps its own
// tag and is filed showing under the group.
export default {
    name: 'GroupAddForm',
    components: { SuggestionBar, SuggestionRow },
    props: {
        thingId: { type: String, required: true },
        tag: { type: String, default: null },
        // the group exists through `show_under` (`via_show_under`)
        showUnder: { type: Boolean, default: false },
    },
    emits: ['close'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            prompt: '',
            barIds: {
                versions: 'group-add-versions',
                version: 'group-add-version',
                regenerate: 'group-add-regenerate',
                discard: 'group-add-discard',
                primary: 'group-add-accept',
            },
            footIds: { discard: 'group-add-discard-foot', primary: 'group-add-accept-foot' },
        };
    },
    computed: {
        key() {
            return groupDraftKey(this.thingId, this.tag);
        },
        found() {
            return this.worlds.smallDrafts[this.key] || null;
        },
        // the drafted rows as the owner left them
        rows() {
            return this.found?.edited?.rows || [];
        },
        heading() {
            return tagHeading(this.tag);
        },
        promptLabel() {
            return this.tag ? `Add ${this.heading.toLowerCase()}…` : 'Add entries filed here…';
        },
        versionRows() {
            return smallVersionRows(this.found?.versions, this.found?.version);
        },
        // mid-request: an Add or a version switch out
        busy() {
            return !!(this.found?.accepting || this.found?.switching);
        },
        // the rows take no edit while the draft is out or being written
        rowsOff() {
            return this.busy || !!this.found?.pending;
        },
        ticked() {
            return this.rows.filter((row) => row.ticked !== false && row.name.trim()).length;
        },
    },
    methods: {
        draft() {
            if (this.prompt.trim()) {
                this.worlds.askGroupAdd(this.thingId, this.tag, this.prompt.trim(), { showUnder: this.showUnder });
            }
        },
        change(index, changes) {
            const rows = this.rows.map((row, i) => (i === index ? { ...row, ...changes } : row));
            this.worlds.editSmall(this.key, { rows });
        },
        // the rows stay until the server answers (`accepting`)
        accept() {
            this.worlds.acceptSmall(this.key);
            this.$emit('close');
        },
        discard() {
            this.worlds.discardSmall(this.key);
            this.$emit('close');
        },
    },
};
</script>

<style scoped>
.group-add {
    border: 1px dashed rgb(var(--v-theme-accent));
    border-radius: 6px;
    margin: 4px 0;
}

.draft-name {
    flex: none;
    width: 220px;
    font-weight: 600;
}
</style>
