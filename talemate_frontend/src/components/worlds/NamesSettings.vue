<template>
    <v-card variant="flat" class="names-settings pa-4" data-testid="names-settings">
        <div class="text-subtitle-1 mb-1">Names</div>
        <div class="text-caption text-muted mb-3">
            Names a draft replaces before you see it, and the ones you keep. Rows marked <span class="scope app">all worlds</span> come with every world;
            <b>Make it global</b> moves one of this world's there.
        </div>
        <div class="panels">
            <div class="panel" data-testid="names-replace">
                <div class="d-flex align-center ga-2">
                    <span class="text-overline text-muted">Replace</span>
                    <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-plus" data-testid="names-add" @click="startAdd('replace')">Add</v-btn>
                </div>
                <v-tabs v-model="replaceKind" density="compact" color="accent" class="mb-2">
                    <v-tab v-for="kind in REPLACE_KINDS" :key="kind.value" :value="kind.value" :data-testid="'names-kind-' + kind.value">{{ kind.title }}</v-tab>
                </v-tabs>
                <v-text-field
                    v-if="adding === 'replace'"
                    v-model="draftName"
                    :label="'Add to ' + kindTitle(replaceKind)"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="mb-2 add-field"
                    data-testid="names-add-field"
                    @keydown.enter="add(replaceKind)"
                    @keydown.esc="adding = null"
                ></v-text-field>
                <NamesRows :rows="rowsOf(replaceKind)" @act="act" />
                <div class="text-caption text-muted mt-2">The model also catches real names that aren't on any list.</div>
            </div>
            <div class="panel" data-testid="names-keep">
                <div class="d-flex align-center ga-2">
                    <span class="text-overline text-muted">Keep as they are</span>
                    <v-btn variant="text" size="small" color="accent" prepend-icon="mdi-plus" data-testid="names-add" @click="startAdd('keep')">Add</v-btn>
                </div>
                <v-text-field
                    v-if="adding === 'keep'"
                    v-model="draftName"
                    label="Add a name to keep"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="mb-2 add-field"
                    data-testid="names-add-field"
                    @keydown.enter="add('keep')"
                    @keydown.esc="adding = null"
                ></v-text-field>
                <NamesRows :rows="rowsOf('keep')" @act="act" />
            </div>
        </div>

        <v-dialog :model-value="!!removing" max-width="420" @update:model-value="removing = null">
            <v-card class="pa-4">
                <div class="text-subtitle-1 mb-2">Remove “{{ removing?.name }}” from every world?</div>
                <div class="text-body-2 text-muted mb-3">It leaves the list every world starts with, here and everywhere else.</div>
                <div class="d-flex ga-2">
                    <v-btn color="delete" variant="flat" size="small" data-testid="names-confirm-remove" @click="removeEverywhere">Remove everywhere</v-btn>
                    <v-btn variant="text" size="small" data-testid="names-cancel-remove" @click="removing = null">Cancel</v-btn>
                </div>
            </v-card>
        </v-dialog>
    </v-card>
</template>

<script>
import { h } from 'vue';
import { useWorldsStore } from '@/stores/worlds.js';

const REPLACE_KINDS = [
    { value: 'real', title: 'Real names' },
    { value: 'cliche', title: 'AI clichés' },
    { value: 'title', title: 'Stock titles' },
];

// One list's rows: the name, where it comes from, and its actions right
// after it (owner's rule: controls by what they act on).
const NamesRows = {
    name: 'NamesRows',
    props: { rows: { type: Array, required: true } },
    emits: ['act'],
    setup(props, { emit }) {
        return () =>
            h('div', { class: 'rows' }, props.rows.length
                ? props.rows.map((row) =>
                      h('div', { class: ['names-row', { off: row.off }], 'data-testid': 'names-row', key: row.scope + row.name }, [
                          h('span', { class: 'row-name' }, row.name),
                          h('span', { class: ['scope', row.scope] }, row.scope === 'app' ? 'all worlds' : 'this world'),
                          row.off ? h('span', { class: 'scope off-chip', 'data-testid': 'names-off-chip' }, 'off here') : null,
                          ...(row.scope === 'world'
                              ? [
                                    button('Make it global', 'names-global', () => emit('act', 'make_global', row)),
                                    button('Remove', 'names-remove', () => emit('act', 'remove', row)),
                                ]
                              : [
                                    button(row.off ? 'Turn on here' : 'Turn off here', 'names-off', () => emit('act', row.off ? 'turn_on' : 'turn_off', row)),
                                    button('Remove everywhere', 'names-remove-everywhere', () => emit('act', 'remove_everywhere', row), true),
                                ]),
                      ]),
                  )
                : [h('div', { class: 'text-body-2 text-muted' }, 'None yet.')]);
    },
};

function button(label, testid, onClick, danger = false) {
    return h('button', { type: 'button', class: ['row-action', { danger }], 'data-testid': testid, onClick }, label);
}

// The world's Names page (languages 4a, mockup 2A): what drafts replace
// (real names, AI clichés, stock titles) beside what they keep; the app's
// rows and this world's together.
export default {
    name: 'NamesSettings',
    components: { NamesRows },
    setup() {
        return { worlds: useWorldsStore(), REPLACE_KINDS };
    },
    data() {
        return { replaceKind: 'real', adding: null, draftName: '', removing: null };
    },
    computed: {
        worldId() {
            return this.worlds.currentWorld?.id || null;
        },
    },
    watch: {
        // another world's rows are its own
        worldId: {
            immediate: true,
            handler(id) {
                if (id) this.worlds.loadNameLists();
            },
        },
    },
    methods: {
        kindTitle(kind) {
            return REPLACE_KINDS.find((k) => k.value === kind)?.title || kind;
        },
        rowsOf(kind) {
            return (this.worlds.nameLists || []).filter((row) => row.kind === kind);
        },
        startAdd(where) {
            this.adding = where;
            this.draftName = '';
        },
        add(kind) {
            const name = this.draftName.trim();
            if (name) {
                this.worlds.nameListEdit('add', kind, name);
            }
            this.adding = null;
            this.draftName = '';
        },
        act(action, row) {
            if (action === 'remove_everywhere') {
                this.removing = row;
                return;
            }
            this.worlds.nameListEdit(action, row.kind, row.name);
        },
        removeEverywhere() {
            const row = this.removing;
            this.removing = null;
            if (row) {
                this.worlds.nameListEdit('remove_everywhere', row.kind, row.name);
            }
        },
    },
};
</script>

<style scoped>
.panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
    gap: 16px;
}
.panel {
    background: rgb(var(--v-theme-raised));
    border-radius: 6px;
    padding: 10px 14px;
}
.add-field {
    max-width: 320px;
}
.scope,
:deep(.scope) {
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
    background: rgba(var(--v-border-color), 0.25);
    color: rgb(var(--v-theme-muted, var(--v-theme-on-surface)));
}
.scope.app,
:deep(.scope.app) {
    color: rgb(var(--v-theme-link));
}
:deep(.scope.off-chip) {
    color: rgb(var(--v-theme-warning));
}
:deep(.names-row) {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 4px 0;
    border-bottom: 1px solid rgba(var(--v-border-color), 0.2);
}
:deep(.names-row.off .row-name) {
    text-decoration: line-through;
    opacity: 0.6;
}
:deep(.row-action) {
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgb(var(--v-theme-accent));
}
:deep(.row-action.danger) {
    color: rgb(var(--v-theme-delete, var(--v-theme-error)));
}
</style>
