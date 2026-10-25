<template>
    <v-menu
        :model-value="modelValue"
        :target="target"
        location="bottom start"
        :close-on-content-click="false"
        @update:model-value="$emit('update:modelValue', $event)"
    >
        <v-card class="name-mode pa-2" min-width="260" data-testid="name-mode" @keydown.esc="close">
            <div class="text-caption text-muted px-2 pb-1">“{{ shownWords }}” → {{ thing?.name }}</div>
            <v-list density="compact" role="menu">
                <v-list-item
                    prepend-icon="mdi-tag-plus-outline"
                    :title="`Add “${shownWords}” as another name`"
                    role="menuitem"
                    active
                    color="accent"
                    data-testid="mode-add-name"
                    @click="choose(null)"
                ></v-list-item>
                <v-list-subheader>Rename to…</v-list-subheader>
                <div v-if="draft" class="px-4 pb-2 text-caption text-muted" data-testid="mode-rename-later">On a draft: rename the words once it's accepted.</div>
                <div v-else-if="!names" class="d-flex justify-center pa-2">
                    <v-progress-circular indeterminate size="18" width="2" color="accent"></v-progress-circular>
                </div>
                <template v-else>
                    <v-list-item
                        v-for="name in names"
                        :key="name"
                        prepend-icon="mdi-rename-outline"
                        :title="name"
                        role="menuitem"
                        data-testid="mode-rename-option"
                        @click="choose(name)"
                    ></v-list-item>
                </template>
            </v-list>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// The two ways a link takes its words (P4), once its target is picked: the
// one mode chooser of the link card's "Re-point…", a stub's "Re-point…" and
// the selection's "Link to an entry…". "Add “words” as another name" (the
// default, first and marked) keeps the words and teaches the target them;
// "Rename to…" lists the target's names (its name, then its other names,
// `fetchNames`), one of which takes the words' place. `choose` emits
// `{useName}`: null for another name, else the name. On a draft (ruling
// F16) the words are a pick keyed by name: renaming waits for the accept.
// If the target's names can't be had (it's gone), the chooser closes.
export default {
    name: 'NameModeMenu',
    props: {
        modelValue: { type: Boolean, default: false },
        target: { type: [Array, Object], default: null },
        // the words the link shows now
        words: { type: String, default: '' },
        // the thing the link will mean, `{id, name}`
        thing: { type: Object, default: null },
        draft: { type: Boolean, default: false },
    },
    emits: ['update:modelValue', 'choose'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        shownWords() {
            return this.words.trim().split(/\s+/).join(' ');
        },
        names() {
            return this.thing ? this.worlds.namesOf[this.thing.id] || null : null;
        },
    },
    watch: {
        modelValue(open) {
            if (open && this.thing && !this.draft) {
                this.worlds.fetchNames(this.thing.id);
            }
        },
        'worlds.namesFailed'(id) {
            if (id && id === this.thing?.id) {
                this.close();
            }
        },
    },
    methods: {
        close() {
            this.$emit('update:modelValue', false);
        },
        choose(name) {
            this.$emit('choose', { useName: name });
            this.close();
        },
    },
};
</script>

<style scoped>
.name-mode {
    background: rgb(var(--v-theme-raised));
}
</style>
