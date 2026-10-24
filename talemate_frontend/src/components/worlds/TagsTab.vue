<template>
    <div class="tags-tab" data-testid="tags-tab">
        <div class="text-h6 mb-1">Tags</div>
        <div class="text-caption text-muted mb-3">
            Each entry has one tag saying what it is, and a page groups what's filed in it by those tags. Rename a tag, or merge it into another
            (“school” into “institution”): every entry that carries it changes, in one revision.
        </div>
        <div v-if="!worlds.tags.length" class="empty pa-3 text-body-2">No entry has a tag yet.</div>
        <div v-for="item in worlds.tags" :key="item.tag" class="tag-row d-flex align-center flex-wrap ga-2" data-testid="tag-row">
            <template v-if="renaming && renaming.tag === item.tag">
                <v-text-field
                    v-model="renaming.text"
                    label="New name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="tag-field"
                    data-testid="tag-rename-field"
                    @keydown.enter="saveRename"
                    @keydown.esc="renaming = null"
                ></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :disabled="!renameValid" :loading="!!worlds.pending.rename_tag" @click="saveRename">Rename</v-btn>
                <v-btn variant="text" size="small" @click="renaming = null">Cancel</v-btn>
                <span v-if="renameTaken" class="text-caption text-muted" data-testid="tag-rename-taken">“{{ renameClean }}” is in use: merge into it instead.</span>
            </template>
            <template v-else-if="merging && merging.tag === item.tag">
                <span class="tag-name">{{ item.tag }}</span>
                <span class="text-caption text-muted">merge into</span>
                <v-select
                    v-model="merging.into"
                    :items="others(item.tag)"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="tag-field"
                    data-testid="tag-merge-into"
                ></v-select>
                <v-btn color="accent" variant="flat" size="small" :disabled="!merging.into" :loading="!!worlds.pending.merge_tag" @click="saveMerge">Merge</v-btn>
                <v-btn variant="text" size="small" @click="merging = null">Cancel</v-btn>
            </template>
            <template v-else>
                <span class="tag-name">{{ item.tag }}</span>
                <span class="text-caption text-muted">· {{ item.count }} {{ item.count === 1 ? 'entry' : 'entries' }} · shown as “{{ item.heading }}”</span>
                <v-spacer></v-spacer>
                <v-btn variant="outlined" size="x-small" data-testid="tag-rename" @click="startRename(item.tag)">rename</v-btn>
                <v-btn v-if="worlds.tags.length > 1" variant="outlined" size="x-small" data-testid="tag-merge" @click="startMerge(item.tag)">merge into…</v-btn>
            </template>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { normaliseTag } from './entryPage.js';

// World tab → Tags (mockup v3, screen E): every tag in use (`list_tags`),
// with how many entries carry it and the group heading it gives. "rename"
// gives it a new name (`rename_tag`; a name in use is offered as a merge
// instead), "merge into…" folds it into another tag (`merge_tag`). Either
// retags every entry carrying it, in one revision.
export default {
    name: 'TagsTab',
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { renaming: null, merging: null };
    },
    computed: {
        renameClean() {
            return normaliseTag(this.renaming?.text);
        },
        renameTaken() {
            const clean = this.renameClean;
            return !!clean && clean !== this.renaming.tag && this.worlds.tags.some((item) => item.tag === clean);
        },
        renameValid() {
            return !!this.renameClean && this.renameClean !== this.renaming.tag && !this.renameTaken;
        },
    },
    watch: {
        // a rename or merge is answered with the new tags: the row closes
        'worlds.tags'() {
            this.renaming = null;
            this.merging = null;
        },
    },
    mounted() {
        this.worlds.listTags();
    },
    methods: {
        others(tag) {
            return this.worlds.tags.filter((item) => item.tag !== tag).map((item) => item.tag);
        },
        startRename(tag) {
            this.merging = null;
            this.renaming = { tag, text: tag };
        },
        saveRename() {
            if (this.renameValid) {
                this.worlds.renameTag(this.renaming.tag, this.renameClean);
            }
        },
        startMerge(tag) {
            this.renaming = null;
            this.merging = { tag, into: null };
        },
        saveMerge() {
            if (this.merging?.into) {
                this.worlds.mergeTag(this.merging.tag, this.merging.into);
            }
        },
    },
};
</script>

<style scoped>
.tag-row {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 6px 0;
    min-height: 40px;
}

.tag-name {
    font-weight: 600;
    color: rgb(var(--v-theme-foreign));
}

.tag-field {
    max-width: 220px;
}

.empty {
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
    color: rgb(var(--v-theme-muted));
}
</style>
