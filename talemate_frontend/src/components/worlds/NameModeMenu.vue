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
                    title="Add as another name"
                    :subtitle="`${thingName} also goes by “${shownWords}”`"
                    role="menuitem"
                    :active="defaultMode === 'name'"
                    color="accent"
                    data-testid="mode-add-name"
                    @click="choose('name')"
                ></v-list-item>
                <v-list-subheader>Use the entry's name</v-list-subheader>
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
                        @click="choose('rename', name)"
                    ></v-list-item>
                </template>
                <v-divider class="my-1"></v-divider>
                <v-list-item
                    prepend-icon="mdi-form-textbox"
                    title="Rename the entry to these words"
                    :subtitle="draft ? 'On a draft: once it\'s accepted' : `${thingName} becomes “${shownWords}”, keeping its name as another`"
                    :disabled="draft"
                    role="menuitem"
                    data-testid="mode-retitle"
                    @click="choose('retitle')"
                ></v-list-item>
                <v-list-item
                    prepend-icon="mdi-link-variant"
                    title="Link only"
                    :subtitle="linkOnlyNote"
                    role="menuitem"
                    :active="defaultMode === 'link'"
                    color="accent"
                    data-testid="mode-link-only"
                    @click="choose('link')"
                ></v-list-item>
            </v-list>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { wordsAreAName } from './draftPage.js';

// The four ways a link takes its words (P4, ruling H2; polish 4), once
// its target is picked: the one mode chooser of the link card's
// "Re-point…", a stub's "Re-point…" and the selection's "Link to an
// entry…". In this order: "Add as another name" keeps the words and
// teaches the target them; "Use the entry's name" lists the target's names
// (its name, then its other names, `fetchNames`), one of which takes the
// words' place; "Rename the entry to these words" keeps them and makes
// them the target's main name, its old one an other name; "Link only"
// keeps the words as written and teaches nothing. The default (marked) is
// "Add as another name" when the words look like a proper name
// (`wordsAreAName`, from the text `before` them; always for a stub's
// words, `nameDefault`, whose "Link only" warns the name is lost), else
// "Link only".
// `choose` emits `{mode, useName}` (`mode` 'name', 'rename', 'retitle' or
// 'link'). On a draft (ruling F16) the words are a pick keyed by name:
// both renames wait for the accept. If the target's names can't be had
// (it's gone), the chooser closes.
export default {
    name: 'NameModeMenu',
    props: {
        modelValue: { type: Boolean, default: false },
        target: { type: [Array, Object], default: null },
        // the words the link shows now, and the fact's text before them
        words: { type: String, default: '' },
        before: { type: String, default: '' },
        // the words are a name whatever they look like (a stub's)
        nameDefault: { type: Boolean, default: false },
        // the thing the link will mean, `{id, name}`
        thing: { type: Object, default: null },
        draft: { type: Boolean, default: false },
    },
    emits: ['update:modelValue', 'choose'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        thingName() {
            return this.thing?.name || 'the entry';
        },
        shownWords() {
            return this.words.trim().split(/\s+/).join(' ');
        },
        names() {
            return this.thing ? this.worlds.namesOf[this.thing.id] || null : null;
        },
        // a stub's words are a name: linking only loses it (ruling H2)
        linkOnlyNote() {
            return this.nameDefault ? `“${this.shownWords}” won't be known as a name of ${this.thing?.name || 'it'}` : `“${this.shownWords}” stays as written`;
        },
        defaultMode() {
            return this.nameDefault || wordsAreAName(this.words, this.before, this.names || []) ? 'name' : 'link';
        },
    },
    watch: {
        modelValue(open) {
            if (open && this.thing) {
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
        choose(mode, name = null) {
            this.$emit('choose', { mode, useName: name });
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
