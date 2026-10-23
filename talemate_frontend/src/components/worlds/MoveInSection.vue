<template>
    <div v-if="rows.length || refile.length" class="move-in-section">
        <div v-if="rows.length" class="mt-3" data-testid="move-in">
            <div class="heading">Move here from where they are now</div>
            <div v-for="group in groups" :key="group.fromId" class="group">
                <div class="from">from <span class="entry-name">{{ group.name }}</span></div>
                <div v-for="index in group.rows" :key="rows[index].fact_id" class="d-flex align-center ga-2 row" data-testid="move-in-row">
                    <v-checkbox-btn
                        :model-value="!!rows[index].ticked"
                        density="compact"
                        class="flex-grow-0"
                        :aria-label="'Move in ' + rows[index].text"
                        @update:model-value="$emit('update', rowsTicked(rows, [index], $event))"
                    ></v-checkbox-btn>
                    <span :class="{ dropped: !rows[index].ticked }">{{ rows[index].text }}</span>
                </div>
                <div class="note text-caption">Moved, not copied: the ticked ones leave {{ group.name }}'s page.</div>
            </div>
        </div>

        <!-- entries filed where an outer body goes, offered to move into it -->
        <div v-if="refile.length" class="mt-3" data-testid="refile">
            <div class="heading">Re-file into the new body</div>
            <div v-for="(row, index) in refile" :key="row.thing_id" class="d-flex align-center ga-2 row" data-testid="refile-row">
                <v-checkbox-btn
                    :model-value="!!row.ticked"
                    density="compact"
                    class="flex-grow-0"
                    :aria-label="'Re-file ' + (row.name || 'this entry')"
                    @update:model-value="$emit('update-refile', rowsTicked(refile, [index], $event))"
                ></v-checkbox-btn>
                <span :class="{ dropped: !row.ticked }">
                    <span class="entry-name">{{ row.name || 'an entry' }}</span>
                    <span class="text-muted"> from {{ row.from_name || 'nowhere' }} → into {{ row.to_name || 'the new body' }}</span>
                </span>
            </div>
        </div>
    </div>
</template>

<script>
import { rowsTicked } from '@/stores/worlds.js';

// "Move here from where they are now" (curation goal 2): the broader
// entry's facts a new, more specific entry may take, grouped by where each
// comes from. The model's picks come ticked and first (ruling C2); the
// rest are offered unticked. A ticked one is moved, not copied. Below them,
// the re-file rows an outer body brings (bodies within bodies): entries
// filed where the new body goes, each unticked until the owner ticks it.
// Changes emit `update` (the move-in rows) and `update-refile` (the
// re-file rows), each the whole list.
export default {
    name: 'MoveInSection',
    props: {
        rows: { type: Array, default: () => [] },
        refile: { type: Array, default: () => [] },
    },
    emits: ['update', 'update-refile'],
    computed: {
        groups() {
            const groups = [];
            const byId = new Map();
            this.rows.forEach((row, index) => {
                let group = byId.get(row.from_id);
                if (!group) {
                    group = { fromId: row.from_id, name: row.from_name || 'its broader entry', rows: [] };
                    byId.set(row.from_id, group);
                    groups.push(group);
                }
                group.rows.push(index);
            });
            return groups;
        },
    },
    methods: { rowsTicked },
};
</script>

<style scoped>
.heading {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgb(var(--v-theme-muted));
}

.group {
    border-left: 2px solid rgb(var(--v-theme-border));
    padding-left: 10px;
    margin: 6px 0 10px;
}

.from {
    font-weight: 600;
}

.entry-name {
    color: rgb(var(--v-theme-link));
    text-decoration: underline;
}

.row {
    padding: 2px 0;
}

.dropped {
    color: rgb(var(--v-theme-muted));
}

.note {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}
</style>
