<template>
    <span class="outer-body">
        <v-btn
            v-if="!open"
            variant="text"
            size="x-small"
            prepend-icon="mdi-select-group"
            data-testid="outer-body-open"
            @click="start"
        >Part of a body not yet made…</v-btn>
        <div v-else class="outer-form pa-2 my-1" data-testid="outer-body-form" @keydown.esc.stop="escape">
            <div class="text-caption text-muted mb-1">{{ rowName }} is part of a body the world doesn't have yet: name it, and it's made as a sphere around it.</div>
            <div class="d-flex align-center flex-wrap ga-2">
                <v-text-field
                    v-model="name"
                    label="Name of the body"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="field"
                ></v-text-field>
                <v-select
                    v-model="template"
                    :items="templates"
                    item-title="label"
                    item-value="template"
                    label="Template"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field-small"
                    data-testid="outer-template"
                ></v-select>
                <v-autocomplete
                    v-model="sphereId"
                    :items="sphereOptions"
                    item-title="name"
                    item-value="id"
                    label="Filed in (optional)"
                    clearable
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field"
                    data-testid="outer-sphere"
                ></v-autocomplete>
                <v-select
                    v-if="sphereId"
                    v-model="drawerId"
                    :items="drawerOptions"
                    item-title="title"
                    item-value="id"
                    label="Drawer"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="field-small"
                    data-testid="outer-drawer"
                ></v-select>
                <v-btn color="accent" variant="flat" size="small" :loading="busy" :disabled="!valid" @click="submit">Add the body</v-btn>
                <v-btn variant="text" size="small" :disabled="busy" @click="open = false">Cancel</v-btn>
            </div>
            <div v-if="!sphereId" class="text-caption text-muted mt-1">Left unfiled, it goes where {{ rowName }} is filed now.</div>
        </div>
    </span>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { SPHERE_TEMPLATES, UNSORTED, escapeCloses, partOfDrawers } from './worldKinds.js';

// "Part of a body not yet made…" (bodies within bodies, ruling C10): the
// owner names the body a part belongs to (`rowName`: a stub row, a named
// item, or the entry itself, ruling C11), picks its template and,
// optionally, the sphere drawer it's filed in (left out, where the part is
// filed now). The name starts as the spec's "<part>'s parent". Emits
// `submit` with `add_outer_body`'s `outer`: `{name, template, part_of}`;
// the form closes once the reply is in. Esc closes it.
export default {
    name: 'OuterBodyForm',
    props: {
        rowName: { type: String, required: true },
    },
    emits: ['submit'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            open: false,
            name: '',
            template: null,
            sphereId: null,
            drawerId: UNSORTED,
            sent: false,
            templates: SPHERE_TEMPLATES,
        };
    },
    computed: {
        busy() {
            return !!this.worlds.pending.add_outer_body;
        },
        sphereOptions() {
            return (this.worlds.things.sphere || []).filter((thing) => !thing.stub);
        },
        drawerOptions() {
            return partOfDrawers(this.worlds.sphereInfo[this.sphereId]?.sphere?.drawers || [], 'sphere');
        },
        valid() {
            return !!this.name.trim() && !!this.template && !this.busy;
        },
    },
    watch: {
        sphereId(id) {
            this.drawerId = UNSORTED;
            if (id) {
                this.worlds.fetchSphere(id);
            }
        },
        // the first drawer a sphere may be filed in, once its drawers are in
        drawerOptions(options) {
            if (this.drawerId === UNSORTED && options.length > 1) {
                this.drawerId = options[0].id;
            }
        },
        // the reply came: done (an error keeps the form)
        busy(now) {
            if (!now && this.sent) {
                this.sent = false;
                if (!this.worlds.error) {
                    this.open = false;
                }
            }
        },
    },
    methods: {
        escape(event) {
            if (escapeCloses(event)) {
                this.open = false;
            }
        },
        start() {
            this.name = `${this.rowName}'s parent`;
            this.template = null;
            this.sphereId = null;
            this.drawerId = UNSORTED;
            this.open = true;
        },
        submit() {
            if (!this.valid) {
                return;
            }
            this.worlds.clearError();
            this.sent = true;
            this.$emit('submit', {
                name: this.name.trim(),
                template: this.template,
                part_of: this.sphereId ? { sphere: this.sphereId, drawer: this.drawerId } : null,
            });
        },
    },
};
</script>

<style scoped>
.outer-form {
    display: block;
    border: 1px dashed rgb(var(--v-theme-border));
    border-radius: 6px;
}

.field {
    flex: 1 1 200px;
    max-width: 260px;
}

.field-small {
    flex: 1 1 140px;
    max-width: 180px;
}
</style>
