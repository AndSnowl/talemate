<template>
    <div class="entry-connected" data-testid="entry-connected">
        <div class="d-flex align-center ga-2">
            <span class="text-overline text-muted">Connected</span>
            <span class="text-caption text-muted" data-testid="connected-count">· {{ countLine }}</span>
            <v-spacer></v-spacer>
            <v-btn v-if="!readonly" variant="outlined" size="x-small" data-testid="connected-add" @click="adding = !adding">+ Add</v-btn>
        </div>
        <GroupAddForm v-if="!readonly && (adding || drafting)" :thing-id="thing.id" :tag="null" @close="adding = false" />
        <div v-if="!groups.length" class="empty text-body-2">Nothing is filed in {{ thing.name }} yet.</div>
        <div class="groups">
            <ConnectedGroup
                v-for="group in groups"
                :key="`${thing.id}|${group.tag ?? ''}`"
                :thing-id="thing.id"
                :group="group"
                :others="othersOf(group)"
                :readonly="readonly"
            />
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { connectedCount } from './entryPage.js';
import { groupDraftKey } from './smallDrafts.js';
import ConnectedGroup from './ConnectedGroup.vue';
import GroupAddForm from './GroupAddForm.vue';

// The entry page's Connected (mockup v3, screen A): what's filed in the
// entry -- places, people and lore alike -- grouped by each one's tag
// (`thing.connected`, largest group first; untagged ones under "Other"),
// each group a `ConnectedGroup`. At the latest telling an ended filing is
// listed too, with its dates. A believed (or undecided) being is listed,
// marked "believed" (ruling F24). The top-level "+ Add" drafts new entries
// filed here with no tag preset.
export default {
    name: 'EntryConnected',
    components: { ConnectedGroup, GroupAddForm },
    props: {
        thing: { type: Object, required: true },
        // a stub's draft: what's filed in the stub, shown as it is (no "+ Add":
        // a group's new entries are written at once, never into a draft)
        readonly: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { adding: false };
    },
    computed: {
        groups() {
            return this.thing.connected || [];
        },
        countLine() {
            const count = connectedCount(this.groups);
            return `${count} ${count === 1 ? 'entry' : 'entries'}, grouped by their tags`;
        },
        drafting() {
            return !!this.worlds.smallDrafts[groupDraftKey(this.thing.id, null)];
        },
    },
    watch: {
        // another page: its own "+ Add" starts closed
        'thing.id'() {
            this.adding = false;
        },
    },
    methods: {
        // the groups a row of `group` can move to
        othersOf(group) {
            return this.groups.filter((other) => (other.tag ?? null) !== (group.tag ?? null)).map(({ tag, heading, via_show_under }) => ({ tag, heading, via_show_under: !!via_show_under }));
        },
    },
};
</script>

<style scoped>
.groups {
    column-count: 2;
    column-gap: 18px;
}

@media (max-width: 960px) {
    .groups {
        column-count: 1;
    }
}

.empty {
    color: rgb(var(--v-theme-muted));
}
</style>
