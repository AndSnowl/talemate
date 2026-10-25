<template>
    <div v-if="foot" class="suggestion-bar-foot d-flex ga-2" :data-testid="testid">
        <v-btn
            color="accent"
            variant="flat"
            size="small"
            prepend-icon="mdi-check"
            :loading="primaryLoading"
            :disabled="primaryDisabled"
            :title="lockedTitle"
            @click="$emit('primary')"
        >{{ primaryLabel }}</v-btn>
        <v-btn variant="outlined" size="small" :disabled="busy" @click="$emit('discard')">Discard</v-btn>
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
                        @click="$emit('use-version', row.version)"
                    ></v-list-item>
                </v-list>
            </v-menu>
            <v-spacer></v-spacer>
            <v-btn
                variant="outlined"
                size="small"
                prepend-icon="mdi-refresh"
                :disabled="menuDisabled"
                :title="lockedTitle"
                @click="$emit('regenerate')"
            >Regenerate</v-btn>
            <v-btn variant="outlined" size="small" color="danger" prepend-icon="mdi-close" :disabled="busy" @click="$emit('discard')">Discard</v-btn>
            <v-btn
                color="accent"
                variant="flat"
                size="small"
                prepend-icon="mdi-check"
                :loading="primaryLoading"
                :disabled="primaryDisabled"
                :title="lockedTitle"
                @click="$emit('primary')"
            >{{ primaryLabel }}</v-btn>
        </div>
        <v-textarea
            :model-value="prompt"
            :label="promptLabel"
            auto-grow
            rows="2"
            density="compact"
            variant="outlined"
            hide-details
            class="mt-2"
            :data-testid="promptTestid"
            @update:model-value="$emit('update:prompt', $event)"
        ></v-textarea>
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
// The shared bar for every drafted-and-tick list (plan "polish-1"): the
// chip (`label`), the version menu ("Version n of m ▾", rows from
// `smallVersionRows` or `versionRows`, `use-version(n)`), Regenerate, a
// prompt (and, when `year` isn't `undefined`, a year) to redraft from,
// Discard and a primary button (`primaryLabel`, e.g. "Accept" or
// "Write"). `busy` (mid-request) disables everything, including
// Discard; `locked` (a reason the owner can't act right now, e.g. a
// nested draft is open) disables the version menu, Regenerate and the
// primary button, each with it as `title`, and leaves Discard on. The
// `status` slot is the line under the bar ("Nothing is written until
// you accept.", the accept counts, an error, …). `foot: true` renders
// only the primary and Discard buttons, for the end of a list (e.g. a
// group-add's own Add/Discard row).
export default {
    name: 'SuggestionBar',
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
        primaryLabel: { type: String, default: 'Accept' },
        canPrimary: { type: Boolean, default: true },
        primaryLoading: { type: Boolean, default: false },
        testid: { type: String, default: null },
        // the prompt field's own data-testid ('add-prompt', 'group-add-prompt', …)
        promptTestid: { type: String, default: null },
        // only the primary and Discard buttons, for the end of a list
        foot: { type: Boolean, default: false },
    },
    emits: ['update:prompt', 'update:year', 'regenerate', 'use-version', 'discard', 'primary'],
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
