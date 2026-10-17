<template>
    <v-alert
        density="compact"
        variant="outlined"
        color="info"
        class="ma-4"
    >
        <template v-slot:prepend>
            <v-icon color="info">mdi-information-outline</v-icon>
        </template>
        <div class="text-muted mb-3">
            Cultures, languages and places belong to a <strong>Shared World</strong> and are
            shared by every scene linked to it. Link this scene to a Shared World (or create one)
            to start building cultures.
        </div>
        <v-btn
            color="primary"
            prepend-icon="mdi-earth-arrow-right"
            @click="$emit('world-state-manager-navigate', 'scene', 'shared')"
        >
            Go to Shared World
        </v-btn>
    </v-alert>
</template>

<script>
export default {
    name: 'CultureNoWorld',
    emits: [
        'world-state-manager-navigate',
    ],
}
</script>
