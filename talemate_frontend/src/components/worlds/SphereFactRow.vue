<template>
    <div class="sphere-fact-row">
        <div class="d-flex align-center ga-2">
            <span class="flex-grow-1"><slot></slot></span>
            <slot name="actions"></slot>
            <template v-if="fact">
                <span v-if="removable && fact.held_by && !heldShown" class="held" data-testid="held-by-tag">held by {{ fact.held_by.name }}</span>
                <FactRowActions v-if="removable" :fact="fact" />
                <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit" title="Edit" data-testid="sphere-fact-edit" @click="editor.edit(fact)"></v-btn>
                <v-btn
                    v-if="removable"
                    icon="mdi-delete-outline"
                    variant="text"
                    size="x-small"
                    density="comfortable"
                    aria-label="Remove"
                    title="Remove"
                    data-testid="sphere-fact-remove"
                    :disabled="!!worlds.pending.remove_fact"
                    @click="worlds.removeFact(fact.fact_id)"
                ></v-btn>
            </template>
        </div>
        <div v-if="editing" class="my-2">
            <ThingFactForm
                :form="editor.form()"
                :categories="[editor.form().category]"
                :busy="editor.busy()"
                :removable="removable"
                @save="editor.save()"
                @cancel="editor.cancel()"
                @remove="editor.remove(fact)"
            />
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import FactRowActions from './FactRowActions.vue';
import ThingFactForm from './ThingFactForm.vue';

// One of a sphere's own facts where its page shows it (a drawer's
// statement, a Timeline row, an about fact): its content (the slot), then
// any `actions` ("End this…"), Edit and Remove. Edit opens the thing
// page's own fact form (`factEditor`, provided by ThingPage) under the
// row: a correction keeps the fact's links by position and, for a
// statement, its drawer; its category stays what it is (a place sphere's
// own categories don't list a sphere's). A fact the page doesn't own (a branch's
// inherited one) gets no Edit or Remove. An own fact that can be removed
// also has "Move to…" and "Held by…" (`FactRowActions`), and is tagged
// "held by X" when it's held.
export default {
    name: 'SphereFactRow',
    components: { FactRowActions, ThingFactForm },
    inject: { editor: { from: 'factEditor', default: null } },
    props: {
        // the fact's id, or null for a row that isn't one of the page's own
        factId: { type: String, default: null },
        // false: Edit only (the summary's fact, corrected but never removed
        // or moved)
        removable: { type: Boolean, default: true },
        // the row's content shows who holds it already (a drawer item)
        heldShown: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    computed: {
        fact() {
            return this.editor && this.factId ? this.editor.ownFact(this.factId) : null;
        },
        editing() {
            const form = this.editor?.form();
            return !!this.fact && !!form && form.factId === this.factId;
        },
    },
};
</script>

<style scoped>
.v-btn {
    flex: none;
}

.held {
    flex: none;
    font-size: 11px;
    color: rgb(var(--v-theme-foreign));
}
</style>
