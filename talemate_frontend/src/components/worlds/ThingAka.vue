<template>
    <div class="thing-aka mt-3" data-testid="aka-editor">
        <div class="d-flex align-center">
            <span class="text-overline text-muted">Other names</span>
            <v-spacer></v-spacer>
            <v-btn v-if="!adding" variant="text" size="small" color="accent" prepend-icon="mdi-plus" :disabled="busy" @click="startAdd">Add other name</v-btn>
        </div>
        <div v-if="!aka.length && !adding" class="text-body-2 text-muted">None yet.</div>

        <div v-for="(entry, index) in aka" :key="entry.name" class="aka-row d-flex align-center ga-2" data-testid="aka-row">
            <template v-if="editing && editing.index === index">
                <v-text-field
                    v-model="editing.name"
                    label="Other name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="flex-grow-1"
                    :disabled="busy"
                    @keydown.enter="saveEdit"
                    @keydown.esc="editing = null"
                ></v-text-field>
                <v-btn color="accent" variant="flat" size="small" :disabled="busy || !editing.name.trim()" @click="saveEdit">Save</v-btn>
                <v-btn variant="text" size="small" :disabled="busy" @click="editing = null">Cancel</v-btn>
            </template>
            <template v-else>
                <span class="flex-grow-1 aka-name">{{ entry.name }}</span>
                <v-select
                    :model-value="entry.tag"
                    :items="tags"
                    aria-label="Tag"
                    density="compact"
                    variant="plain"
                    hide-details
                    class="tag-select"
                    :disabled="busy"
                    @update:model-value="save(akaChanged(aka, index, { tag: $event }))"
                ></v-select>
                <v-btn
                    :icon="entry.everyday ? 'mdi-radiobox-marked' : 'mdi-radiobox-blank'"
                    variant="text"
                    size="x-small"
                    density="comfortable"
                    :color="entry.everyday ? 'accent' : undefined"
                    :aria-label="entry.everyday ? 'Everyday name (unset)' : 'Make the everyday name'"
                    :title="entry.tag === 'common' ? 'The everyday name: what narration calls it' : 'Only a common name can be the everyday one'"
                    :disabled="busy || entry.tag !== 'common'"
                    data-testid="aka-everyday"
                    @click="save(akaEveryday(aka, index))"
                ></v-btn>
                <span class="everyday-label text-caption">{{ entry.everyday ? 'everyday' : '' }}</span>
                <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit other name" :disabled="busy" @click="editing = { index, name: entry.name }"></v-btn>
                <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" aria-label="Remove other name" :disabled="busy" @click="save(akaRemoved(aka, index))"></v-btn>
            </template>
        </div>

        <div v-if="adding" class="d-flex align-center ga-2 mt-1">
            <v-text-field
                v-model="adding.name"
                label="Other name"
                density="compact"
                variant="outlined"
                hide-details
                autofocus
                class="flex-grow-1"
                :disabled="busy"
                @keydown.enter="saveAdd"
                @keydown.esc="adding = null"
            ></v-text-field>
            <v-select v-model="adding.tag" :items="tags" label="Tag" density="compact" variant="outlined" hide-details class="tag-select" :disabled="busy"></v-select>
            <v-btn color="accent" variant="flat" size="small" :disabled="busy || !adding.name.trim()" @click="saveAdd">Add</v-btn>
            <v-btn variant="text" size="small" :disabled="busy" @click="adding = null">Cancel</v-btn>
        </div>
        <div v-if="aka.length || adding" class="text-caption text-muted mt-1">
            Proper: another formal name. Common: what people call it; the everyday one is what narration and dialogue use.
        </div>
    </div>
</template>

<script>
import { akaAdded, akaChanged, akaEveryday, akaRemoved } from '@/stores/worlds.js';

// The other names (`aka`) of a page or a draft: add, rename, tag (proper
// or common), the everyday pick (one common name at most) and remove.
// Each change emits the whole list (`save`): the page writes it
// (`set_field` "aka"), a draft keeps it (`setDraftAka`). The forms close
// once `aka` changes after a save: the page's reply, or the draft's copy
// at once.
export default {
    name: 'ThingAka',
    props: {
        aka: { type: Array, required: true },
        // the name an other name can't repeat
        mainName: { type: String, default: '' },
        busy: { type: Boolean, default: false },
    },
    emits: ['save'],
    data() {
        return {
            tags: ['proper', 'common'],
            // the name being added: {name, tag}
            adding: null,
            // the entry being renamed: {index, name}
            editing: null,
        };
    },
    watch: {
        // the reply: the forms are done
        aka() {
            if (this.adding?.sent || this.editing?.sent) {
                this.adding = null;
                this.editing = null;
            }
        },
    },
    methods: {
        akaChanged,
        akaEveryday,
        akaRemoved,
        startAdd() {
            this.editing = null;
            this.adding = { name: '', tag: 'common' };
        },
        // a list the backend should have: only sent when it changed
        save(aka) {
            if (aka !== this.aka) {
                this.$emit('save', aka);
                return true;
            }
            return false;
        },
        saveAdd() {
            if (this.save(akaAdded(this.aka, this.adding.name, this.adding.tag, this.mainName))) {
                this.adding = { ...this.adding, sent: true };
            }
        },
        saveEdit() {
            if (this.editing.name.trim() === this.aka[this.editing.index]?.name) {
                this.editing = null;
                return;
            }
            if (this.save(akaChanged(this.aka, this.editing.index, { name: this.editing.name }))) {
                this.editing = { ...this.editing, sent: true };
            }
        },
    },
};
</script>

<style scoped>
.aka-row {
    border-bottom: 1px dashed rgb(var(--v-theme-border));
    padding: 2px 0;
    min-height: 36px;
}

.aka-row .v-btn {
    flex: none;
}

.tag-select {
    flex: none;
    width: 120px;
}

.everyday-label {
    flex: none;
    min-width: 54px;
    color: rgb(var(--v-theme-accent));
}
</style>
