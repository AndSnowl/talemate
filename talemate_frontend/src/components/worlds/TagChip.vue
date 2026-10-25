<template>
    <v-menu v-model="open" :close-on-content-click="false" location="bottom start">
        <template #activator="{ props }">
            <v-chip
                v-bind="props"
                size="x-small"
                label
                variant="outlined"
                color="foreign"
                class="tag-chip"
                :class="{ untagged: !tag }"
                append-icon="mdi-menu-down"
                :data-testid="testid"
                :aria-label="`${label}: ${tag || fallback || emptyText}`"
                @click="query = ''"
            ><span v-if="prefix" class="prefix">{{ prefix }}&nbsp;</span>{{ tag || fallback || emptyText }}</v-chip>
        </template>
        <v-card class="pa-2" min-width="240" data-testid="tag-picker" @keydown.esc="open = false">
            <v-text-field
                v-model="query"
                placeholder="tag…"
                prepend-inner-icon="mdi-magnify"
                density="compact"
                variant="outlined"
                hide-details
                autofocus
                data-testid="tag-search"
                @keydown.enter="enter"
            ></v-text-field>
            <v-list density="compact" class="py-1">
                <v-list-item
                    v-for="item in choices.matches"
                    :key="item.tag"
                    data-testid="tag-option"
                    @click="pick(item.tag)"
                >
                    <v-list-item-title>{{ item.tag }} <span class="text-caption text-muted">· {{ item.count }} {{ item.count === 1 ? 'entry' : 'entries' }}</span></v-list-item-title>
                </v-list-item>
                <v-divider v-if="choices.matches.length && (choices.fresh || tag)"></v-divider>
                <v-list-item v-if="choices.fresh" prepend-icon="mdi-plus" data-testid="tag-new" @click="pick(choices.fresh)">
                    <v-list-item-title>new tag “{{ choices.fresh }}”</v-list-item-title>
                </v-list-item>
                <v-list-item v-if="tag" prepend-icon="mdi-close" data-testid="tag-clear" @click="pick(null)">
                    <v-list-item-title class="text-muted">{{ clearText }}</v-list-item-title>
                </v-list-item>
            </v-list>
        </v-card>
    </v-menu>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { normaliseTag, tagChoices } from './entryPage.js';

// An entry's tag (mockup v3, screen E): a chip, always editable (ruling
// F8), that opens the tag picker: search the tags in use, each with how
// many entries carry it (`list_tags`), or make a new one ("+ new tag").
// Picking one sends `set_tag` for `thingId`; "no tag" clears it. The
// backend keeps a tag lowercase, its first comma part. On a draft
// (`local`) nothing is sent: the tag picked is emitted (`pick`, normalised
// as the backend would store it) for the draft to keep.
// The same picker serves a filing's "shows under" (`EntryIn`, `local`):
// `prefix` reads before the value, `fallback` (the entry's own tag) shows
// dimmed while none is picked, `clearText` names going back to it, and
// `testid` and `label` tell the chips apart.
export default {
    name: 'TagChip',
    props: {
        thingId: { type: String, default: null },
        tag: { type: String, default: null },
        local: { type: Boolean, default: false },
        testid: { type: String, default: 'tag-chip' },
        label: { type: String, default: 'Tag' },
        prefix: { type: String, default: '' },
        fallback: { type: String, default: null },
        emptyText: { type: String, default: 'no tag' },
        clearText: { type: String, default: 'no tag' },
    },
    emits: ['pick'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { open: false, query: '' };
    },
    computed: {
        choices() {
            return tagChoices(this.worlds.tags, this.query, this.tag);
        },
    },
    watch: {
        open(now) {
            if (now) {
                this.worlds.listTags();
            }
        },
    },
    methods: {
        pick(tag) {
            this.open = false;
            if ((tag ?? null) === (this.tag ?? null)) {
                return;
            }
            if (this.local) {
                this.$emit('pick', tag ? normaliseTag(tag) || null : null);
            } else {
                this.worlds.setTag(this.thingId, tag);
            }
        },
        // Enter takes the new tag typed, else the only match
        enter() {
            if (this.choices.fresh) {
                this.pick(this.choices.fresh);
            } else if (this.choices.matches.length === 1) {
                this.pick(this.choices.matches[0].tag);
            }
        },
    },
};
</script>

<style scoped>
.tag-chip {
    cursor: pointer;
}

.tag-chip.untagged {
    opacity: 0.6;
}

.prefix {
    font-style: italic;
}
</style>
