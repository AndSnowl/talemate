<template>
    <div v-if="rows.length" class="mt-3" data-testid="draft-new-names">
        <div class="heading">New names <span class="text-muted">· {{ note }}</span></div>
        <div v-for="row in rows" :key="row.name" class="stub-row d-flex align-center flex-wrap ga-2" data-testid="new-name-row">
            <v-checkbox-btn
                v-if="tickable"
                :model-value="row.ticked !== false"
                density="compact"
                class="flex-grow-0"
                data-testid="new-name-tick"
                :aria-label="'Make a stub of ' + row.name"
                @update:model-value="change(row, { ticked: $event })"
            ></v-checkbox-btn>
            <span class="stub-name" :class="{ dropped: tickable && row.ticked === false }">{{ row.name }}</span>
            <span v-if="tickable && row.ticked === false" class="text-caption text-muted" data-testid="new-name-plain">no stub: its words stay plain</span>
            <template v-else-if="row.same_target_id">
                <span class="text-caption text-muted" data-testid="new-name-same">same as <b>{{ nameOf(row.same_target_id) }}</b>: no stub, it links that entry</span>
                <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" :aria-label="'Not the same: ' + row.name" @click="change(row, { same_target_id: null })"></v-btn>
            </template>
            <template v-else>
                <v-select
                    :model-value="row.kind"
                    :items="kindItems"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="kind"
                    data-testid="new-name-kind"
                    :aria-label="'Kind of ' + row.name"
                    @update:model-value="change(row, { kind: $event })"
                ></v-select>
                <v-text-field
                    :model-value="row.tag || ''"
                    placeholder="tag"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="tag"
                    data-testid="new-name-tag"
                    :aria-label="'Tag of ' + row.name"
                    @change="change(row, { tag: normaliseTag($event.target.value) || null })"
                ></v-text-field>
                <SameThingAsk
                    v-if="row.same_as && row.same_as.length"
                    variant="row"
                    :name="row.name"
                    :kind="row.kind"
                    :offers="row.same_as"
                    :chosen="row.same_target_id || null"
                    @choose="change(row, { same_target_id: $event })"
                />
                <v-btn variant="text" size="x-small" data-testid="new-name-same-search" @click="search(row, 'same', $event)">same as… 🔎</v-btn>
                <span v-if="filingOf(row)" class="text-caption" data-testid="new-name-filing">
                    in <b>{{ filingOf(row) }}</b>
                    <v-btn icon="mdi-close" variant="text" size="x-small" density="compact" :aria-label="'Not filed: ' + row.name" @click="change(row, { filing: null })"></v-btn>
                </span>
                <v-btn variant="text" size="x-small" data-testid="new-name-in" @click="search(row, 'in', $event)">in… 🔎</v-btn>
                <v-btn variant="text" size="x-small" disabled prepend-icon="mdi-refresh" data-testid="new-name-rename" title="Renaming comes later, with languages">rename · later</v-btn>
            </template>
        </div>
        <ReferenceMenu
            v-model="searching"
            :target="searchAt"
            search-only
            :search-label="searchMode === 'same' ? 'The same as…' : 'Filed in…'"
            @pick="picked"
        />
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { normaliseTag } from './entryPage.js';
import { STUB_KINDS, kindInfo } from './worldKinds.js';
import ReferenceMenu from './ReferenceMenu.vue';
import SameThingAsk from './SameThingAsk.vue';

// "New names" (spec "The draft page" 6): the names a draft's facts use
// that the world hasn't (`new_names`), each a stub once the draft is
// accepted. Each has its kind, its tag, a "same as…" choice (the offers
// the world may have, or a search: then it links that entry and no stub is
// made), "in…" (where its stub is filed: a search, or "this entry" as the
// model said) and rename, greyed out: re-rolling a name comes later, with
// languages. A change emits `change(name, changes)`. `tickable` (a "+ Add
// facts…" draft, ruling H8) gives each row a tick, `ticked: false` making
// no stub; `note` says when the stubs are made.
export default {
    name: 'PreviewStubs',
    components: { ReferenceMenu, SameThingAsk },
    props: {
        rows: { type: Array, required: true },
        tickable: { type: Boolean, default: false },
        note: { type: String, default: "in this draft: stubs once it's accepted" },
    },
    emits: ['change'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { searching: false, searchAt: null, searchMode: 'same', searchRow: null };
    },
    computed: {
        kindItems() {
            return STUB_KINDS.map((kind) => ({ title: kindInfo(kind)?.singular || kind, value: kind }));
        },
    },
    methods: {
        normaliseTag,
        change(row, changes) {
            this.$emit('change', row.name, changes);
        },
        nameOf(id) {
            return this.worlds.referenceTargets.find((target) => target.id === id)?.name || 'an entry';
        },
        // where its stub is filed, as a name ("this entry" for the draft)
        filingOf(row) {
            const filing = row.filing;
            if (!filing || filing.ticked === false) {
                return null;
            }
            if (filing.this_entry) {
                return 'this entry';
            }
            return filing.target_id ? this.nameOf(filing.target_id) : filing.name || null;
        },
        search(row, mode, event) {
            this.searchRow = row;
            this.searchMode = mode;
            this.searchAt = [event.clientX, event.clientY];
            this.searching = true;
        },
        picked(target) {
            const row = this.searchRow;
            if (!row) {
                return;
            }
            if (this.searchMode === 'same') {
                this.change(row, { same_target_id: target.id });
            } else {
                this.change(row, { filing: { target_id: target.id, this_entry: false, name: null, role: null, ticked: true } });
            }
            this.searchRow = null;
        },
    },
};
</script>

<style scoped>
.heading {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

.stub-row {
    padding: 2px 0;
}

.stub-name {
    font-weight: 600;
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}

.stub-name.dropped {
    color: rgb(var(--v-theme-muted));
    text-decoration: line-through;
}

.kind {
    flex: none;
    width: 130px;
}

.tag {
    flex: none;
    width: 120px;
}
</style>
