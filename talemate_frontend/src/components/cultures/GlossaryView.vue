<template>
    <div class="glossary-view">
        <div class="d-flex align-center flex-wrap ga-2 mb-3">
            <v-chip
                size="small"
                :variant="activeFilter === 'unreviewed' ? 'flat' : 'outlined'"
                :color="activeFilter === 'unreviewed' ? 'primary' : undefined"
                @click="activeFilter = 'unreviewed'"
            >
                Not reviewed ({{ counts.unreviewed }})
            </v-chip>
            <v-chip
                size="small"
                :variant="activeFilter === 'reviewed' ? 'flat' : 'outlined'"
                :color="activeFilter === 'reviewed' ? 'primary' : undefined"
                @click="activeFilter = 'reviewed'"
            >
                Reviewed ({{ counts.reviewed }})
            </v-chip>
            <v-chip
                size="small"
                :variant="activeFilter === 'all' ? 'flat' : 'outlined'"
                :color="activeFilter === 'all' ? 'primary' : undefined"
                @click="activeFilter = 'all'"
            >
                All ({{ counts.total }})
            </v-chip>
            <v-spacer></v-spacer>
            <v-text-field
                v-model="search"
                density="compact"
                variant="outlined"
                hide-details
                clearable
                prepend-inner-icon="mdi-magnify"
                placeholder="Filter names or meanings"
                style="max-width: 280px"
                class="flex-grow-0"
            ></v-text-field>
        </div>

        <v-row>
            <v-col cols="12" md="7">
                <div v-if="visibleEntries.length === 0" class="text-center text-muted pa-8">
                    <v-icon size="32" color="green">mdi-check-circle-outline</v-icon>
                    <div class="mt-2">Nothing here.</div>
                </div>
                <v-table v-else density="compact">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Kind</th>
                            <th>Meaning</th>
                            <th>First used in</th>
                            <th>Added by</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="entry in visibleEntries"
                            :key="entry.id"
                            class="glossary-row"
                            :class="{ 'glossary-row-selected': entry.id === localSelectedId }"
                            @click="select(entry.id)"
                        >
                            <td>
                                <span v-if="entry.status === 'unreviewed'" class="unrev-dot mr-1"></span>
                                <span :class="{ 'text-highlight7 font-italic': entry.kind === 'thing' || entry.kind === 'word' }">
                                    {{ entry.text }}
                                </span>
                            </td>
                            <td>
                                <v-chip size="x-small" label :color="kindMeta(entry.kind).color" variant="tonal" :prepend-icon="kindMeta(entry.kind).icon">
                                    {{ entry.kind }}
                                </v-chip>
                            </td>
                            <td class="text-muted">{{ entry.meaning || '—' }}</td>
                            <td class="text-muted">{{ entry.first_used || '—' }}</td>
                            <td>
                                <v-chip size="x-small" label variant="tonal" :prepend-icon="originMeta(entry.origin).icon">
                                    {{ originMeta(entry.origin).label }}
                                </v-chip>
                            </td>
                        </tr>
                    </tbody>
                </v-table>
            </v-col>

            <v-col cols="12" md="5">
                <GlossaryDetail
                    v-if="selectedEntry"
                    :key="selectedEntry.id"
                    :entry="selectedEntry"
                    :cultures="cultures"
                    :send="send"
                ></GlossaryDetail>
            </v-col>
        </v-row>
    </div>
</template>

<script>
import GlossaryDetail from './GlossaryDetail.vue';
import { kindMeta, originMeta } from './levelLabels';

export default {
    name: 'GlossaryView',
    components: {
        GlossaryDetail,
    },
    props: {
        entries: {
            type: Array,
            default: () => [],
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        cultureId: {
            type: String,
            default: null,
        },
        selectedId: {
            type: String,
            default: null,
        },
        send: {
            type: Function,
            required: true,
        },
    },
    emits: [
        'select',
    ],
    data() {
        return {
            activeFilter: 'unreviewed',
            search: '',
            localSelectedId: this.selectedId,
        }
    },
    computed: {
        entriesForContext() {
            return this.entries.filter(e => this.cultureId === null ? e.language === null : e.language === this.cultureId);
        },
        counts() {
            const all = this.entriesForContext;
            const unreviewed = all.filter(e => e.status === 'unreviewed').length;
            return {
                total: all.length,
                unreviewed,
                reviewed: all.length - unreviewed,
            };
        },
        searchedEntries() {
            const all = this.entriesForContext;
            if (!this.search) {
                return all;
            }
            const q = this.search.toLowerCase();
            return all.filter(e => `${e.text} ${e.meaning}`.toLowerCase().includes(q));
        },
        visibleEntries() {
            if (this.activeFilter === 'unreviewed') {
                return this.searchedEntries.filter(e => e.status === 'unreviewed');
            }
            if (this.activeFilter === 'reviewed') {
                return this.searchedEntries.filter(e => e.status === 'reviewed');
            }
            return this.searchedEntries;
        },
        selectedEntry() {
            return this.entriesForContext.find(e => e.id === this.localSelectedId) || null;
        },
    },
    watch: {
        cultureId() {
            // Switching cultures (or to/from the Unassigned page) restarts
            // the glossary browsing state; carrying over a filter or a
            // selection from a different culture would be confusing.
            this.activeFilter = 'unreviewed';
            this.search = '';
            this.localSelectedId = null;
        },
        visibleEntries: {
            immediate: true,
            handler(list) {
                if (list.some(e => e.id === this.localSelectedId)) {
                    return;
                }
                this.localSelectedId = list.length ? list[0].id : null;
            },
        },
        localSelectedId(id) {
            this.$emit('select', id);
        },
    },
    methods: {
        select(id) {
            this.localSelectedId = id;
        },
        kindMeta,
        originMeta,
    },
}
</script>

<style scoped>
.unrev-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: rgb(var(--v-theme-unsaved));
    vertical-align: middle;
}

.glossary-row {
    cursor: pointer;
}

.glossary-row:hover {
    background: rgba(255, 255, 255, 0.035);
}

.glossary-row-selected {
    background: rgba(255, 255, 255, 0.07);
}
</style>
