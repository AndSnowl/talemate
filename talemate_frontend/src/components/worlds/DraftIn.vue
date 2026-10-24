<template>
    <div class="draft-in mb-3" data-testid="draft-in">
        <div class="d-flex align-center ga-2">
            <span class="text-overline text-muted">In</span>
            <span class="text-caption text-muted">where it's filed: the AI's suggestions come unticked, yours ticked</span>
            <v-spacer></v-spacer>
            <v-btn variant="text" size="small" color="accent" data-testid="draft-in-add" @click="search">+ in… 🔎</v-btn>
        </div>
        <!-- a stub's filings so far: written already, kept as they are -->
        <div v-for="row in kept" :key="row.target_id" class="row d-flex align-center ga-2" data-testid="draft-in-kept">
            <v-icon size="small" class="kept">mdi-check</v-icon>
            <span class="target">{{ row.target_name }}</span>
            <span v-if="row.role" class="role">{{ row.role }}</span>
            <span class="text-caption text-muted">· already filed</span>
        </div>
        <div v-for="row in rows" :key="row.target_id" class="row d-flex align-center flex-wrap ga-2" data-testid="draft-in-row">
            <v-checkbox-btn
                :model-value="!!row.ticked"
                density="compact"
                class="flex-grow-0"
                :aria-label="'File in ' + row.target_name"
                @update:model-value="$emit('change', row.target_id, { ticked: $event })"
            ></v-checkbox-btn>
            <span class="target" :class="{ dropped: !row.ticked }">{{ row.target_name }}</span>
            <v-text-field
                :model-value="row.role || ''"
                label="Role"
                density="compact"
                variant="outlined"
                hide-details
                class="role-field"
                @update:model-value="$emit('change', row.target_id, { role: $event.trim() ? $event : null })"
            ></v-text-field>
            <span v-if="row.since" class="dates">since {{ row.since.label }}</span>
            <span v-if="row.exceptions && row.exceptions.length" class="text-caption text-muted">· {{ row.exceptions.length }} “but…”</span>
        </div>
        <div v-if="!rows.length && !kept.length" class="text-body-2 text-muted">Not filed anywhere yet.</div>
        <ReferenceMenu
            v-model="searching"
            :target="searchAt"
            search-only
            search-label="File it in…"
            :exclude="exclude"
            @pick="$emit('add', $event)"
        />
    </div>
</template>

<script>
import ReferenceMenu from './ReferenceMenu.vue';

// A draft's "In" (spec "The draft page" 1): the filings it would be given,
// each with a tick, its role (editable) and since. The model's suggestions
// come unticked (ruling F7), the owner's own ticked; "+ in… 🔎" adds one
// (any entry or live stub, ticked: `add` with the entry picked). A stub's
// filings so far (`kept`) show above, as they are. A tick or role emits
// `change(targetId, changes)`.
export default {
    name: 'DraftIn',
    components: { ReferenceMenu },
    props: {
        // the draft's `filings` (as the owner left them)
        rows: { type: Array, default: () => [] },
        // a stub's own filings (the page's "In" rows not the draft's)
        kept: { type: Array, default: () => [] },
        exclude: { type: Array, default: () => [] },
    },
    emits: ['change', 'add'],
    data() {
        return { searching: false, searchAt: null };
    },
    methods: {
        search(event) {
            this.searchAt = [event.clientX, event.clientY];
            this.searching = true;
        },
    },
};
</script>

<style scoped>
.row {
    padding: 2px 0;
}

.target {
    font-weight: 600;
    color: rgb(var(--v-theme-link));
}

.role {
    font-style: italic;
    color: rgb(var(--v-theme-muted));
}

.role-field {
    flex: none;
    width: 200px;
}

.dates {
    font-family: monospace;
    font-size: 11px;
    color: rgb(var(--v-theme-date));
}

.kept {
    color: rgb(var(--v-theme-muted));
}

.dropped {
    color: rgb(var(--v-theme-muted));
}
</style>
