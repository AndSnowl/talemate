<template>
    <div v-if="rows.length" class="mt-3" data-testid="draft-new-names">
        <div class="suggestion-heading">New stubs</div>
        <SuggestionRow
            v-for="row in rows"
            :key="row.name"
            :tickable="tickable"
            :ticked="row.ticked !== false"
            :dropped="tickable && row.ticked === false"
            :tick-label="'Make a stub of ' + row.name"
            testid="new-name-row"
            tick-testid="new-name-tick"
            @tick="change(row, { ticked: $event })"
        >
            <span class="stub-name">{{ row.name }}</span>
            <!-- a name cleaning gave it (languages 4a) -->
            <span v-if="row.replaced" class="text-caption text-muted ml-2" data-testid="new-name-replaced">replaced {{ row.replaced }}</span>
            <template v-if="!plain(row) && !row.same_target_id" #end>
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
            </template>
            <!-- what it is and where it's filed, on a line under its name -->
            <template #under>
                <!-- a "same as X?" dropdown gets room under the kind's -->
                <div class="d-flex align-center flex-wrap ga-2" :class="{ 'same-room': asksSame(row) }">
                    <span v-if="plain(row)" class="text-caption text-muted" data-testid="new-name-plain">no stub: its words stay plain</span>
                    <template v-else-if="row.same_target_id">
                        <span class="text-caption text-muted" data-testid="new-name-same">same as <b>{{ nameOf(row.same_target_id) }}</b>: no stub, it links that entry</span>
                        <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" :aria-label="'Not the same: ' + row.name" @click="change(row, { same_target_id: null })"></v-btn>
                    </template>
                    <template v-else>
                        <SameThingAsk
                            v-if="asksSame(row)"
                            variant="row"
                            :name="row.name"
                            :kind="row.kind"
                            :offers="row.same_as"
                            :chosen="row.same_target_id || null"
                            @choose="change(row, { same_target_id: $event })"
                        />
                        <v-btn variant="text" size="x-small" data-testid="new-name-same-search" @click="search(row, 'same', $event)">same as… 🔎</v-btn>
                        <template v-if="filingOf(row)">
                            <span class="text-caption" data-testid="new-name-filing">in <b>{{ filingOf(row) }}</b></span>
                            <v-btn icon="mdi-close" variant="text" size="x-small" density="comfortable" :aria-label="'Not filed: ' + row.name" @click="change(row, { filing: null })"></v-btn>
                        </template>
                        <v-btn variant="text" size="x-small" data-testid="new-name-in" @click="search(row, 'in', $event)">in… 🔎</v-btn>
                        <v-btn variant="text" size="x-small" disabled prepend-icon="mdi-refresh" data-testid="new-name-rename" title="Renaming comes later, with languages">rename · later</v-btn>
                    </template>
                </div>
            </template>
        </SuggestionRow>
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
import SuggestionRow from './SuggestionRow.vue';

// "New stubs" (spec "The draft page" 6): the names a draft's facts use
// that the world hasn't (`new_names`), each a stub once the draft is
// accepted. Each has its kind, its tag, a "same as…" choice (the offers
// the world may have, or a search: then it links that entry and no stub is
// made), "in…" (where its stub is filed: a search, or "this entry" as the
// model said) and rename, greyed out: re-rolling a name comes later, with
// languages. A change emits `change(name, changes)`. `tickable` (a "+ Add
// facts…" draft, ruling H8) gives each row a tick, `ticked: false` making
// no stub. Each row is a `SuggestionRow`: its kind and tag follow its
// name, the rest on a line under it.
export default {
    name: 'PreviewStubs',
    components: { ReferenceMenu, SameThingAsk, SuggestionRow },
    props: {
        rows: { type: Array, required: true },
        tickable: { type: Boolean, default: false },
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
        // whether its row asks "same as X?" (the AI's few candidates)
        asksSame(row) {
            return !this.plain(row) && !row.same_target_id && !!(row.same_as && row.same_as.length);
        },
        normaliseTag,
        // unticked (a "+ Add facts…" draft's): no stub, its words plain
        plain(row) {
            return this.tickable && row.ticked === false;
        },
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
.same-room {
    margin-top: 8px;
}

.stub-name {
    font-weight: 600;
    color: rgb(var(--v-theme-foreign));
    text-decoration: underline dashed;
}

/* unticked, the name greys with the rest of its row (struck through with
   it once the owner dropped it; no stub's dashed underline) */
.suggestion-dropped .stub-name,
.suggestion-offer .stub-name {
    color: inherit;
    text-decoration: none;
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
