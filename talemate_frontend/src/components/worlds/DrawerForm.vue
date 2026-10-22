<template>
    <div class="drawer-form pa-2" data-testid="drawer-form" @keydown.esc="$emit('cancel')">
        <div v-if="!form.id" class="d-flex align-center flex-wrap ga-2 mb-2">
            <span class="text-caption text-muted">Type</span>
            <v-btn-toggle v-model="form.type" density="compact" variant="outlined" divided class="types" data-testid="drawer-form-type">
                <v-btn v-for="type in types" :key="type" :value="type" size="small">{{ type }}</v-btn>
            </v-btn-toggle>
        </div>
        <div class="d-flex align-center flex-wrap ga-2">
            <v-text-field
                v-model="form.title"
                label="Title"
                density="compact"
                variant="outlined"
                hide-details
                autofocus
                class="title-field"
                :disabled="busy"
                @keydown.enter="$emit('save')"
            ></v-text-field>
            <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!form.title.trim() || !form.type" @click="$emit('save')">Save</v-btn>
            <v-btn variant="text" size="small" :disabled="busy" @click="$emit('cancel')">Cancel</v-btn>
            <template v-if="form.id && form.own">
                <v-spacer></v-spacer>
                <v-btn icon="mdi-arrow-up" variant="text" size="x-small" aria-label="Move up" :disabled="busy || form.first" @click="$emit('move', -1)"></v-btn>
                <v-btn icon="mdi-arrow-down" variant="text" size="x-small" aria-label="Move down" :disabled="busy || form.last" @click="$emit('move', 1)"></v-btn>
                <v-btn variant="text" size="small" color="danger" prepend-icon="mdi-delete" :disabled="busy" @click="$emit('drop')">Drop</v-btn>
            </template>
        </div>
        <div v-if="form.id && form.own" class="text-caption text-muted mt-1">Dropping it moves its items to Unsorted.</div>
        <div v-if="form.inherited" class="text-caption text-muted mt-1">Inherited: a new title keeps this branch's own copy of it.</div>
    </div>
</template>

<script>
import { DRAWER_TYPES } from './worldKinds.js';

// The form for one of a sphere's drawers: a new one's type and title, or
// an existing one's title, with Move up, Move down and Drop for the
// sphere's own drawers. `form` is the page's (`SpherePage`), edited in
// place; Save, Cancel, `move` (-1 or 1) and Drop are emitted.
export default {
    name: 'DrawerForm',
    props: {
        // `{id?, type, title, own, inherited, first, last}`
        form: { type: Object, required: true },
        busy: { type: Boolean, default: false },
    },
    emits: ['save', 'cancel', 'move', 'drop'],
    data() {
        return { types: DRAWER_TYPES };
    },
};
</script>

<style scoped>
.drawer-form {
    border: 1px solid rgb(var(--v-theme-border));
    border-radius: 6px;
    margin: 6px 0;
}

.title-field {
    max-width: 320px;
}

.types {
    flex-wrap: wrap;
    height: auto !important;
}
</style>
