<template>
    <div v-if="rows.length" class="move-in-section">
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
                    <span v-if="rows[index].picked" class="suggested text-caption" data-testid="move-in-suggested">suggested</span>
                </div>
                <div class="note text-caption">Moved, not copied: the ticked ones leave {{ group.name }}'s page.</div>
            </div>
        </div>

    </div>
</template>

<script>
import { rowsTicked } from '@/stores/worlds.js';

// "Move here from where they are now" (curation goal 2): the broader
// entry's facts a new, more specific entry may take, grouped by where each
// comes from. Every row comes unticked (ruling C24: the model's picks were
// right 2 times of 20 in the curation flow probe); its picks come first,
// marked "suggested", for the owner to tick or not (ruling C2). A ticked
// one is moved, not copied. Changes emit `update` with the whole list.
export default {
    name: 'MoveInSection',
    props: {
        rows: { type: Array, default: () => [] },
    },
    emits: ['update'],
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

.suggested {
    color: rgb(var(--v-theme-muted));
    font-style: italic;
    white-space: nowrap;
}

.note {
    margin-left: 34px;
    color: rgb(var(--v-theme-muted));
}
</style>
