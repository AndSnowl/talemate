<template>
    <v-menu
        :model-value="modelValue"
        :target="target"
        location="bottom start"
        :close-on-content-click="false"
        @update:model-value="$emit('update:modelValue', $event)"
    >
        <v-card class="selection-menu" min-width="280" data-testid="selection-menu" @keydown.esc="close">
            <div class="px-4 pt-2 text-caption text-muted">“{{ shownWords }}”</div>
            <div v-if="draft" class="px-4 pt-1 text-caption draft-note" data-testid="selection-draft-note">
                On a draft this goes by the words: it applies to every “{{ shownWords }}” in it.
            </div>
            <div v-if="blocked" class="px-4 pt-1 text-caption text-muted" data-testid="selection-blocked">{{ blocked }}</div>
            <div class="d-flex align-center ga-2 px-4 pt-2">
                <v-select
                    v-model="kind"
                    :items="kindItems"
                    label="Kind"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="kind"
                    data-testid="selection-kind"
                ></v-select>
                <v-text-field
                    v-model="tag"
                    label="Tag"
                    placeholder="river, custom…"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="tag"
                    data-testid="selection-tag"
                ></v-text-field>
            </div>
            <v-list density="compact" role="menu">
                <v-list-item
                    prepend-icon="mdi-help-circle-outline"
                    title="Make a stub"
                    role="menuitem"
                    data-testid="selection-stub"
                    :disabled="!!blocked"
                    @click="act('stub')"
                ></v-list-item>
                <v-list-item
                    prepend-icon="mdi-creation"
                    title="Make a stub and expand now…"
                    :subtitle="draft ? 'not on a draft: the stub is made on accept' : undefined"
                    role="menuitem"
                    data-testid="selection-expand"
                    :disabled="!!blocked || draft || !canExpand(kind)"
                    @click="act('expand')"
                ></v-list-item>
                <v-list-item
                    prepend-icon="mdi-link-variant"
                    title="Link to an entry… 🔎"
                    role="menuitem"
                    data-testid="selection-link"
                    :disabled="!!blocked"
                    @click="searchLink"
                ></v-list-item>
                <v-divider></v-divider>
                <v-list-item
                    prepend-icon="mdi-comment-question-outline"
                    title="Ask about this…"
                    subtitle="later"
                    role="menuitem"
                    disabled
                    data-testid="selection-ask"
                ></v-list-item>
            </v-list>
        </v-card>
    </v-menu>
    <ReferenceMenu
        v-model="linking"
        :target="target"
        search-only
        search-label="Link the words to…"
        :exclude="exclude"
        @pick="picked"
    />
    <NameModeMenu v-model="choosing" :target="target" :words="words" :thing="chosen" :draft="draft" @choose="chose" />
</template>

<script>
import { normaliseTag } from './entryPage.js';
import { STUB_KINDS, canExpand, kindInfo } from './worldKinds.js';
import NameModeMenu from './NameModeMenu.vue';
import ReferenceMenu from './ReferenceMenu.vue';

// The menu on selected words of a fact (spec "Menus that work
// everywhere"): "Make a stub" with a kind and a tag (`stub {kind, tag}`),
// "Make a stub and expand now…" (`expand {kind, tag}`: its kind's create
// box opens from it), "Link to an entry… 🔎" (a search, then the mode
// chooser, `NameModeMenu`, P4: `link {target, useName}`, `useName` null to
// keep the words as another name of the entry) and "Ask about this…", shown greyed out for the later
// "dynamic questions" feature. On a draft (ruling F16) nothing is written:
// the stub is a new name and the link a pick, both keyed by the words, so
// they apply wherever the draft writes them, which the menu says; a stub
// can't be expanded before it's made. `blocked`: why these words can't be
// used (a fact rewritten on the draft), every action off.
export default {
    name: 'SelectionMenu',
    components: { NameModeMenu, ReferenceMenu },
    props: {
        modelValue: { type: Boolean, default: false },
        target: { type: [Array, Object], default: null },
        words: { type: String, default: '' },
        draft: { type: Boolean, default: false },
        blocked: { type: String, default: '' },
        exclude: { type: Array, default: () => [] },
    },
    emits: ['update:modelValue', 'stub', 'expand', 'link'],
    data() {
        return { kind: 'lore', tag: '', linking: false, choosing: false, chosen: null };
    },
    computed: {
        kindItems() {
            return STUB_KINDS.map((kind) => ({ title: kindInfo(kind)?.singular || kind, value: kind }));
        },
        shownWords() {
            return this.words.trim().split(/\s+/).join(' ');
        },
    },
    watch: {
        modelValue(open) {
            if (open) {
                this.tag = '';
            }
        },
    },
    methods: {
        canExpand,
        close() {
            this.$emit('update:modelValue', false);
        },
        act(action) {
            this.$emit(action, { kind: this.kind, tag: normaliseTag(this.tag) || null });
            this.close();
        },
        searchLink() {
            this.close();
            this.linking = true;
        },
        picked(target) {
            this.chosen = target;
            this.choosing = true;
        },
        chose({ useName }) {
            this.$emit('link', { target: this.chosen, useName });
        },
    },
};
</script>

<style scoped>
.selection-menu {
    background: rgb(var(--v-theme-raised));
}

.kind {
    flex: none;
    width: 130px;
}

.tag {
    flex: 1;
}

.draft-note {
    color: rgb(var(--v-theme-foreign));
}
</style>
