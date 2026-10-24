<template>
    <div class="entry-mentioned" data-testid="entry-mentioned">
        <div class="mentioned-head d-flex align-center ga-2" @click="open = !open">
            <v-icon size="small">{{ open ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
            <b>Mentioned in</b>
            <span class="text-caption text-muted">{{ entries.length }} · entries that name {{ thing.name }} but aren't filed in it</span>
        </div>
        <div v-if="open" class="mentioned-body" data-testid="mentioned-list">
            <div v-if="!entries.length" class="text-body-2 text-muted">None.</div>
            <div v-for="entry in entries" :key="entry.id" data-testid="mentioned-row">
                <a class="thing-link" href="#" @click.prevent="worlds.openThing(entry.id)">{{ entry.name }}</a>
            </div>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// The entry page's "Mentioned in" (mockup v3, screen A): the entries whose
// facts name this one without being filed in it (`thing.mentioned_in`),
// folded by default; opened, a link to each.
export default {
    name: 'EntryMentionedIn',
    props: {
        thing: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { open: false };
    },
    computed: {
        entries() {
            return this.thing.mentioned_in || [];
        },
    },
    watch: {
        // another page starts folded again
        'thing.id'() {
            this.open = false;
        },
    },
};
</script>

<style scoped>
.entry-mentioned {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    margin: 6px 0;
    opacity: 0.85;
}

.mentioned-head {
    padding: 4px 10px;
    cursor: pointer;
    background: rgba(var(--v-theme-on-surface), 0.04);
}

.mentioned-body {
    padding: 4px 10px 6px;
}

.thing-link {
    color: rgb(var(--v-theme-link));
    text-decoration: underline dotted;
}
</style>
