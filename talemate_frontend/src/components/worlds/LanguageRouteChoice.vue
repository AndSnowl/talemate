<template>
    <!-- how this run is made: Claude Code (with its model), the agent's
         model, or the brief to copy; for this run only -->
    <div class="d-flex flex-wrap align-center ga-2" :data-testid="prefix + '-route'">
        <span class="text-caption text-muted">{{ label }}</span>
        <div class="d-flex flex-wrap align-center ga-2" data-testid="route-choice">
            <v-btn-toggle :model-value="route" mandatory density="compact" variant="outlined" divided color="primary" :disabled="disabled" @update:model-value="$emit('update:route', $event)">
                <v-btn v-for="choice in ROUTE_CHOICES" :key="choice.value" :value="choice.value" size="small" :aria-pressed="String(route === choice.value)" :data-testid="prefix + '-route-' + choice.value">
                    {{ choice.label }}<span v-if="choice.value === 'in_app'" class="text-muted ml-1">(API tokens)</span>
                </v-btn>
            </v-btn-toggle>
            <v-text-field
                v-if="route === 'claude_code'"
                :model-value="claudeModel"
                placeholder="its default"
                label="model"
                density="compact"
                variant="outlined"
                hide-details
                class="model-field"
                :disabled="disabled"
                :data-testid="prefix + '-model'"
                @update:model-value="$emit('update:claudeModel', $event)"
            ></v-text-field>
        </div>
    </div>
</template>

<script>
export const ROUTE_CHOICES = [
    { value: 'claude_code', label: 'Claude Code' },
    { value: 'in_app', label: "the agent's model" },
    { value: 'brief', label: 'Copy the brief' },
];

// The route row Make a language and Change it share (one look, one
// component): which way this run goes, and Claude Code's model.
export default {
    name: 'LanguageRouteChoice',
    props: {
        route: { type: String, required: true },
        claudeModel: { type: String, default: '' },
        disabled: { type: Boolean, default: false },
        // test ids start with this: "make" or "change"
        prefix: { type: String, default: 'make' },
        label: { type: String, default: 'Make it with' },
    },
    emits: ['update:route', 'update:claudeModel'],
    setup() {
        return { ROUTE_CHOICES };
    },
};
</script>

<style scoped>
.model-field {
    flex: none;
    width: 170px;
}
</style>
