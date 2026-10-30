<template>
    <!-- how this run is made: Claude Code (with its model), the Language
         agent's client (named, with its model), or the brief to copy; for
         this run only -->
    <div class="d-flex flex-wrap align-center ga-2" :data-testid="prefix + '-route'">
        <span class="text-caption text-muted">{{ label }}</span>
        <div class="d-flex flex-wrap align-center ga-2" data-testid="route-choice">
            <v-btn-toggle :model-value="route" mandatory density="compact" variant="outlined" divided color="primary" :disabled="disabled" @update:model-value="$emit('update:route', $event)">
                <v-btn v-for="choice in ROUTE_CHOICES" :key="choice.value" :value="choice.value" size="small" :aria-pressed="String(route === choice.value)" :data-testid="prefix + '-route-' + choice.value">
                    {{ choice.value === 'in_app' ? inAppAgent : choice.label }}<span v-if="choice.value === 'in_app' && inAppClient && inAppClient.hosted" class="text-muted ml-1">(API tokens)</span>
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
            <!-- the agent's client and model, where Claude Code's model is -->
            <span v-if="route === 'in_app'" class="client-label text-body-2" :class="{ 'text-muted': !inAppClient }" :title="inAppLabel" :data-testid="prefix + '-client'">{{ inAppLabel }}</span>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';

export const ROUTE_CHOICES = [
    { value: 'claude_code', label: 'Claude Code' },
    { value: 'in_app', label: "the agent's model" },
    { value: 'brief', label: 'Copy the brief' },
];

// The in-app route's client, from the route reply: {agent, name, model,
// hosted} (the Creator's when the Language agent has none), or null.
export function inAppClientOf(worlds) {
    return worlds.languageMakeRoute?.in_app_client || null;
}

// What runs it, by name, for progress lines ("Making it with …")
export function inAppName(client) {
    return client ? client.name : "the Language agent's model";
}

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
        return { ROUTE_CHOICES, worlds: useWorldsStore() };
    },
    computed: {
        inAppClient() {
            return inAppClientOf(this.worlds);
        },
        // the button: whose client it is (the Creator's stands in when the
        // Language agent has none)
        inAppAgent() {
            return `${this.inAppClient?.agent || 'Language'} agent`;
        },
        // beside it: "KoboldCpp · Mistral-Small-24B"
        inAppLabel() {
            const client = this.inAppClient;
            if (!client) return 'no client set: pick one under Agents';
            return `${client.name}${client.model ? ` · ${client.model}` : ''}`;
        },
    },
};
</script>

<style scoped>
/* a long model name is cut short; the whole label is its tooltip */
.client-label {
    display: inline-block;
    max-width: 28em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    vertical-align: bottom;
}
.model-field {
    flex: none;
    width: 170px;
}
</style>
