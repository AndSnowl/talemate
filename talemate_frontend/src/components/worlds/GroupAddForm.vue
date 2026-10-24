<template>
    <div class="group-add pa-2" data-testid="group-add">
        <template v-if="!found || (!found.pending && !found.rows)">
            <div class="d-flex align-center ga-2">
                <v-text-field
                    v-model="prompt"
                    :label="tag ? `Add ${heading.toLowerCase()}…` : 'Add entries filed here…'"
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
            <div v-if="found?.error" class="text-caption text-error mt-1" data-testid="group-add-error">{{ found.error }}</div>
        </template>
        <div v-else-if="found.pending" class="d-flex align-center ga-2 text-caption text-muted">
            <v-progress-circular indeterminate size="16" width="2" color="accent"></v-progress-circular>
            Drafting “{{ found.prompt }}”…
        </div>
        <template v-else>
            <div class="text-caption text-muted mb-1">Tick what to add: each becomes a stub filed here, its line its first fact.</div>
            <div v-for="(row, index) in found.rows" :key="index" class="draft-row d-flex align-center ga-2" data-testid="group-add-row">
                <v-checkbox-btn
                    :model-value="row.ticked !== false"
                    density="compact"
                    class="flex-grow-0"
                    :aria-label="'Add ' + row.name"
                    @update:model-value="change(index, { ticked: $event })"
                ></v-checkbox-btn>
                <v-text-field
                    :model-value="row.name"
                    density="compact"
                    variant="plain"
                    hide-details
                    class="draft-name"
                    :aria-label="'Name of ' + row.name"
                    @update:model-value="change(index, { name: $event })"
                ></v-text-field>
                <v-chip size="x-small" label variant="tonal" color="muted">{{ row.kind }}</v-chip>
                <v-chip v-if="row.tag" size="x-small" label variant="outlined" color="foreign">{{ row.tag }}</v-chip>
                <span class="text-body-2 flex-grow-1" :class="{ dropped: row.ticked === false }">{{ row.line }}</span>
            </div>
            <div v-if="!found.rows.length" class="text-caption text-muted">Nothing to add from that.</div>
            <div class="d-flex ga-2 mt-2">
                <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-check" :disabled="!ticked" :loading="!!found.accepting" data-testid="group-add-accept" @click="accept">Add {{ ticked }}</v-btn>
                <v-btn variant="outlined" size="small" :disabled="!!found.accepting" data-testid="group-add-discard" @click="discard">Discard</v-btn>
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { groupKey, tagHeading } from './entryPage.js';

// A group's "+ Add" (or, with no `tag`, the page's own top-level one):
// the owner's prompt drafts up to three new entries (`group_add`), which
// come back as draft rows in the group, each ticked, its name editable,
// with its kind, tag and one line. Accept writes the ticked ones as stubs
// filed in the page (`accept_group_add`); Discard drops them. Nothing is
// written before Accept.
export default {
    name: 'GroupAddForm',
    props: {
        thingId: { type: String, required: true },
        tag: { type: String, default: null },
    },
    emits: ['close'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { prompt: '' };
    },
    computed: {
        found() {
            return this.worlds.groupAdds[groupKey(this.thingId, this.tag)] || null;
        },
        heading() {
            return tagHeading(this.tag);
        },
        ticked() {
            return (this.found?.rows || []).filter((row) => row.ticked !== false && row.name.trim()).length;
        },
    },
    methods: {
        draft() {
            if (this.prompt.trim()) {
                this.worlds.groupAdd(this.thingId, this.tag, this.prompt.trim());
            }
        },
        change(index, changes) {
            const rows = this.found.rows.map((row, i) => (i === index ? { ...row, ...changes } : row));
            this.worlds.editGroupAdd(this.thingId, this.tag, rows);
        },
        // the rows stay until the server answers (`accepting`)
        accept() {
            this.worlds.acceptGroupAdd(this.thingId, this.tag);
            this.$emit('close');
        },
        discard() {
            this.worlds.discardGroupAdd(this.thingId, this.tag);
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

.dropped {
    color: rgb(var(--v-theme-muted));
    text-decoration: line-through;
}
</style>
