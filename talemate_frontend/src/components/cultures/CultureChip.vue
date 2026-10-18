<template>
    <v-chip
        v-if="chip"
        size="x-small"
        label
        variant="outlined"
        class="culture-chip"
        :color="chip.color"
        :data-chip-for="kind + ':' + name"
    >
        {{ chip.label }}
        <span
            v-if="chip.unreviewed"
            class="culture-review-dot"
            role="button"
            title="Not reviewed yet"
            @click.stop="openCulturesReview(chip.target)"
        ></span>
    </v-chip>
</template>

<script>
import { culturesStory } from './culturesStory.js';
import { characterChip, placeChip } from './storyLexicon.js';

// A small culture label for a character's or a place's own title row in
// the World panel (Task 8): "Taelrik", "No culture", "No language" or
// "{top culture} +{n}", with a clickable "not reviewed yet" dot when the
// name or the culture assignment behind it hasn't been reviewed.
export default {
    name: 'CultureChip',
    inject: {
        openCulturesReview: { default: () => () => {} },
    },
    props: {
        kind: {
            type: String,
            required: true,
            validator: (value) => ['character', 'place'].includes(value),
        },
        name: {
            type: String,
            required: true,
        },
    },
    computed: {
        chip() {
            const story = culturesStory.story;
            return this.kind === 'character'
                ? characterChip(story, this.name)
                : placeChip(story, this.name);
        },
    },
};
</script>

<style scoped>
.culture-review-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: rgb(var(--v-theme-unsaved));
    margin-left: 4px;
    cursor: pointer;
    vertical-align: middle;
}
</style>
