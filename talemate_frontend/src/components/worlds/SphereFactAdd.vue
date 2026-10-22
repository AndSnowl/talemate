<template>
    <div class="sphere-fact-add">
        <div v-if="adding" class="my-2">
            <ThingFactForm :form="editor.form()" :categories="editor.categories()" :busy="editor.busy()" @save="editor.save()" @cancel="editor.cancel()" />
        </div>
        <v-btn v-else-if="editor" variant="text" size="x-small" prepend-icon="mdi-plus" :data-testid="'add-' + category" @click="editor.add(category, anchor)">{{ label }}</v-btn>
    </div>
</template>

<script>
import ThingFactForm from './ThingFactForm.vue';

// "+ Add" for a sphere's own facts of one `category` where its page shows
// them (the Timeline, its about facts): the thing page's fact form
// (`factEditor`), opened here (`anchor` tells two such places apart).
export default {
    name: 'SphereFactAdd',
    components: { ThingFactForm },
    inject: { editor: { from: 'factEditor', default: null } },
    props: {
        category: { type: String, required: true },
        anchor: { type: String, required: true },
        label: { type: String, default: 'Add' },
    },
    computed: {
        adding() {
            const form = this.editor?.form();
            return !!form && form.mode === 'add' && form.anchor === this.anchor;
        },
    },
};
</script>
