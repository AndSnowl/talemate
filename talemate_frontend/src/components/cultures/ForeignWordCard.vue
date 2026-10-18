<template>
    <div data-testid="foreign-word-card">
        <v-card-item class="pb-1">
            <div class="d-flex align-center flex-wrap ga-2">
                <span class="text-subtitle-2 font-italic text-highlight7 foreign-word-text">{{ entry?.text }}</span>
                <v-chip
                    size="x-small"
                    label
                    variant="tonal"
                    color="highlight7"
                    prepend-icon="mdi-translate"
                    class="text-caption"
                >
                    {{ entry?.kind }}
                </v-chip>
                <v-chip
                    size="x-small"
                    label
                    variant="outlined"
                    class="text-caption"
                >
                    {{ entry?.language_name }}
                </v-chip>
            </div>
        </v-card-item>
        <v-card-text class="text-body-2">
            <div data-testid="foreign-translation">{{ entry?.translation }}</div>
            <div
                v-if="entry?.breakdown?.length"
                data-testid="foreign-breakdown"
                class="foreign-breakdown mt-2"
            >
                <div v-for="(pair, i) in entry.breakdown" :key="i" class="foreign-breakdown-cell">
                    <div class="font-italic">{{ pair[0] }}</div>
                    <div class="text-caption text-muted">{{ pair[1] }}</div>
                </div>
            </div>
            <div v-if="entry?.usage" class="text-caption text-muted mt-2">
                {{ entry.usage }}
            </div>
        </v-card-text>
        <v-card-actions class="pb-0 my-0 justify-space-between ga-1 flex-wrap">
            <v-btn
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-book-open-variant"
                class="entity-tooltip-action-btn"
                @click="onOpenInCulture"
            >
                Open in {{ entry?.culture_name }}
            </v-btn>
            <v-spacer />
            <v-btn
                size="x-small"
                variant="text"
                color="muted"
                prepend-icon="mdi-cog-outline"
                @click="onConfigureHighlights"
            >
                Configure highlights
            </v-btn>
        </v-card-actions>
    </div>
</template>

<script>
export default {
    name: 'ForeignWordCard',
    inject: {
        openCulturesReview: { default: () => () => {} },
    },
    props: {
        entry: {
            type: Object,
            required: true,
        },
    },
    emits: ['configure-highlights'],
    methods: {
        onOpenInCulture() {
            this.openCulturesReview(this.entry?.target);
        },
        onConfigureHighlights() {
            this.$emit('configure-highlights');
        },
    },
};
</script>

<style scoped>
.foreign-breakdown {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
    gap: 8px 12px;
}

.entity-tooltip-action-btn {
    text-transform: none;
    letter-spacing: 0;
}
</style>
