<template>
    <div v-if="foot" class="suggestion-bar-foot d-flex ga-2" :data-testid="testid">
        <slot name="primary-extra"></slot>
        <v-btn
            color="accent"
            variant="flat"
            size="small"
            prepend-icon="mdi-check"
            :loading="primaryLoading"
            :disabled="primaryDisabled"
            :title="lockedTitle"
            :data-testid="testids.primary"
            @click="$emit('primary')"
        >{{ primaryLabel }}</v-btn>
        <v-btn variant="outlined" size="small" color="danger" prepend-icon="mdi-close" :disabled="busy" :data-testid="testids.discard" @click="$emit('discard')">Discard</v-btn>
    </div>
    <div v-else class="suggestion-bar pa-2 mb-3" :data-testid="testid">
        <div class="d-flex align-center flex-wrap ga-2">
            <v-chip v-if="label" size="small" label color="accent" variant="flat">{{ label }}</v-chip>
            <v-menu location="bottom start">
                <template #activator="{ props }">
                    <v-btn
                        v-bind="props"
                        variant="outlined"
                        size="small"
                        append-icon="mdi-menu-down"
                        :disabled="menuDisabled"
                        :title="lockedTitle"
                        :data-testid="testids.versions"
                    >Version {{ version }} of {{ versions.length }}</v-btn>
                </template>
                <v-list density="compact">
                    <v-list-item
                        v-for="row in versions"
                        :key="row.version"
                        :prepend-icon="row.current ? 'mdi-radiobox-marked' : 'mdi-radiobox-blank'"
                        :title="row.label"
                        :subtitle="row.prompt"
                        :active="row.current"
                        :data-testid="testids.version"
                        @click="$emit('use-version', row.version)"
                    ></v-list-item>
                </v-list>
            </v-menu>
            <v-spacer></v-spacer>
            <v-btn
                variant="outlined"
                size="small"
                prepend-icon="mdi-refresh"
                :disabled="menuDisabled || !!regenerateLocked"
                :title="lockedTitle || regenerateLocked"
                :data-testid="testids.regenerate"
                @click="$emit('regenerate')"
            >Regenerate</v-btn>
            <v-btn variant="outlined" size="small" color="danger" prepend-icon="mdi-close" :disabled="busy" :data-testid="testids.discard" @click="$emit('discard')">Discard</v-btn>
            <slot name="primary-extra"></slot>
            <v-btn
                color="accent"
                variant="flat"
                size="small"
                prepend-icon="mdi-check"
                :loading="primaryLoading"
                :disabled="primaryDisabled"
                :title="lockedTitle"
                :data-testid="testids.primary"
                @click="$emit('primary')"
            >{{ primaryLabel }}</v-btn>
        </div>
        <NameHighlightInput
            :model-value="prompt"
            :picks="picks || {}"
            :pickable="picks !== null"
            :label="promptLabel"
            :rows="2"
            dense
            class="mt-2"
            :data-testid="promptTestid"
            @update:model-value="$emit('update:prompt', $event)"
            @update:picks="$emit('update:picks', $event)"
        />
        <v-text-field
            v-if="year !== undefined"
            :model-value="year"
            label="Year"
            type="number"
            density="compact"
            variant="outlined"
            hide-details
            class="year mt-2"
            @update:model-value="onYear"
        ></v-text-field>
        <div class="d-flex align-center flex-wrap ga-2 mt-1">
            <slot name="status"></slot>
        </div>
    </div>
</template>

<script>
import NameHighlightInput from './NameHighlightInput.vue';

// The shared bar for every drafted-and-tick list (plan "polish-1"): the
// chip (`label`), the version menu ("Version n of m ▾", rows from
// `smallVersionRows` or `versionRows`, `use-version(n)`), Regenerate, a
// prompt (and, when `year` isn't `undefined`, a year) to redraft from,
// Discard and a primary button (`primaryLabel`, e.g. "Accept" or
// "Write"). `busy` (mid-request) disables everything, including
// Discard; `locked` (a reason the owner can't act right now, e.g. a
// nested draft is open) disables the version menu, Regenerate and the
// primary button, each with it as `title`, and leaves Discard on;
// `regenerateLocked` (e.g. an event's year missing) disables Regenerate
// alone, the same way. The
// `status` slot is the line under the bar ("Nothing is written until
// you accept.", the accept counts, an error, …). `foot: true` renders
// only the primary and Discard buttons, for the end of a list (e.g. a
// group-add's own Add/Discard row).
export default {
    name: 'SuggestionBar',
    components: { NameHighlightInput },
    props: {
        // the chip's text ('Draft', …)
        label: { type: String, default: '' },
        versions: { type: Array, default: () => [] },
        version: { type: Number, default: 1 },
        prompt: { type: String, default: '' },
        // undefined hides the year field entirely
        year: { type: Number, default: undefined },
        promptLabel: { type: String, default: '' },
        busy: { type: Boolean, default: false },
        // a reason the owner can't regenerate, switch version or go
        // primary right now, or null
        locked: { type: String, default: null },
        // a reason the owner can't regenerate right now (the rest stays
        // on), or null
        regenerateLocked: { type: String, default: null },
        primaryLabel: { type: String, default: 'Accept' },
        canPrimary: { type: Boolean, default: true },
        primaryLoading: { type: Boolean, default: false },
        testid: { type: String, default: null },
        // the prompt field's own data-testid ('add-prompt', 'group-add-prompt', …)
        promptTestid: { type: String, default: null },
        // the prompt's name picks, where its request takes them (a page
        // draft's); else its names are highlighted only
        picks: { type: Object, default: null },
        // internal ids a call site needs to keep (e.g. DraftBar's
        // existing `draft-versions`, `draft-version`, `draft-discard`):
        // `{versions, version, regenerate, discard, primary}`, each
        // optional
        testids: { type: Object, default: () => ({}) },
        // only the primary and Discard buttons, for the end of a list
        foot: { type: Boolean, default: false },
    },
    emits: ['update:prompt', 'update:picks', 'update:year', 'regenerate', 'use-version', 'discard', 'primary'],
    computed: {
        lockedTitle() {
            return this.locked || null;
        },
        menuDisabled() {
            return this.busy || !!this.locked;
        },
        primaryDisabled() {
            return this.busy || !!this.locked || !this.canPrimary;
        },
    },
    methods: {
        onYear(value) {
            this.$emit('update:year', value === '' || value === null || value === undefined ? null : Number(value));
        },
    },
};
</script>

<style scoped>
.suggestion-bar {
    border: 1px solid rgb(var(--v-theme-accent));
    border-radius: 6px;
    background: rgba(var(--v-theme-accent), 0.06);
}

.year {
    max-width: 110px;
}
</style>
