<template>
    <v-alert color="on-surface" variant="text" :icon="icon" density="compact">
        <v-alert-title>{{ title }}</v-alert-title>
        <div class="text-muted">
            <slot></slot>
        </div>
    </v-alert>
    <v-divider class="mb-2"></v-divider>
</template>

<script>
export default {
    name: 'AppSettingsPageHeader',
    props: {
        title: String,
        icon: String,
    },
}
</script>
