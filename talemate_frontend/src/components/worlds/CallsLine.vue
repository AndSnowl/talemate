<template>
    <div class="calls-line text-caption" data-testid="calls-line">
        <template v-if="calls.length">
            <a href="#" class="fold" data-testid="calls-line-fold" @click.prevent="open = !open">
                <v-icon :icon="open ? 'mdi-chevron-down' : 'mdi-chevron-right'" size="x-small"></v-icon>
                calls {{ pronoun }}<template v-if="!open">: {{ calls.map((c) => c.name).join(', ') }}</template>
            </a>
            <div v-if="open" class="called">
                <div v-for="call in calls" :key="call.by + call.name" class="d-flex align-center ga-1" data-testid="calls-line-name">
                    <template v-if="editing === call">
                        <v-text-field
                            v-model="typed"
                            density="compact"
                            variant="outlined"
                            hide-details
                            autofocus
                            class="calls-input"
                            @keydown.enter="save(call.by)"
                            @keydown.esc="editing = null"
                        ></v-text-field>
                    </template>
                    <template v-else>
                        <b>{{ call.name }}</b>
                        <span class="text-muted">· {{ call.by_name }} · {{ call.rule ? 'from the language’s rule' : 'your own' }}</span>
                        <v-btn icon="mdi-pencil" variant="text" size="x-small" density="compact" :aria-label="'Change what ' + call.by_name + ' calls ' + pronoun" @click="startEdit(call)"></v-btn>
                    </template>
                </div>
            </div>
        </template>
        <!-- nothing differs from the default: a way to say what someone does
             call them, shown when the row is hovered -->
        <template v-else-if="people.length">
            <a v-if="!adding" href="#" class="add text-muted" data-testid="calls-line-add" @click.prevent="startAdd">+ what {{ people.length === 1 ? people[0].name : 'they' }} call{{ people.length === 1 ? 's' : '' }} {{ pronoun }}…</a>
            <div v-else class="d-flex align-center ga-1">
                <v-select
                    v-if="people.length > 1"
                    v-model="by"
                    :items="people"
                    item-title="name"
                    item-value="id"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="calls-by"
                ></v-select>
                <v-text-field
                    v-model="typed"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="calls-input"
                    data-testid="calls-line-input"
                    @keydown.enter="save(by)"
                    @keydown.esc="adding = false"
                ></v-text-field>
            </div>
        </template>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

// What someone calls a person, on the relationship it belongs to
// (languages 4b-2, mockup B): only names that differ from the language's
// default address, folded. `calls`: those used by an entry the fact links
// (`personName.callsFor`); `people`: the entries it links, `{id, name}`.
export default {
    name: 'CallsLine',
    props: {
        thingId: { type: String, required: true },
        calls: { type: Array, default: () => [] },
        people: { type: Array, default: () => [] },
        pronoun: { type: String, default: 'them' },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { open: false, editing: null, adding: false, typed: '', by: null };
    },
    methods: {
        startEdit(call) {
            this.editing = call;
            this.typed = call.name;
        },
        startAdd() {
            this.adding = true;
            this.typed = '';
            this.by = this.people[0]?.id || null;
        },
        save(by) {
            if (this.typed.trim() && by) this.worlds.personPetName(this.thingId, 'set', this.typed.trim(), by);
            this.editing = null;
            this.adding = false;
        },
    },
};
</script>

<style scoped>
.calls-line {
    margin: 0 0 4px 18px;
}
.fold {
    color: rgb(var(--v-theme-muted));
    text-decoration: none;
}
.called {
    margin-left: 14px;
}
.add {
    visibility: hidden;
    text-decoration: none;
}
:global(.fact-host:hover) .add {
    visibility: visible;
}
.calls-input {
    max-width: 220px;
}
.calls-by {
    max-width: 180px;
}
</style>
