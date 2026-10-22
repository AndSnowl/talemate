<template>
    <div class="sphere-fact-row">
        <div class="d-flex align-center ga-2">
            <span class="flex-grow-1"><slot></slot></span>
            <slot name="actions"></slot>
            <template v-if="fact">
                <v-btn icon="mdi-pencil" variant="text" size="x-small" density="comfortable" aria-label="Edit" title="Edit" data-testid="sphere-fact-edit" @click="editor.edit(fact)"></v-btn>
                <v-btn
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
            <ThingFactForm :form="editor.form()" :categories="editor.categories()" :busy="editor.busy()" @save="editor.save()" @cancel="editor.cancel()" @remove="editor.remove(fact)" />
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import ThingFactForm from './ThingFactForm.vue';

// One of a sphere's own facts where its page shows it (a drawer's
// statement, a Timeline row, an about fact): its content (the slot), then
// any `actions` ("End this…"), Edit and Remove. Edit opens the thing
// page's own fact form (`factEditor`, provided by ThingPage) under the
// row: a correction keeps the fact's links by position and, for a
// statement, its drawer. A fact the page doesn't own (a branch's
// inherited one) gets no Edit or Remove.
export default {
    name: 'SphereFactRow',
    components: { ThingFactForm },
    inject: { editor: { from: 'factEditor', default: null } },
    props: {
        // the fact's id, or null for a row that isn't one of the page's own
        factId: { type: String, default: null },
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
</style>
