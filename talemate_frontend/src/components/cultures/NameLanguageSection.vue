<template>
    <div v-if="section" data-testid="name-language-section" class="name-language-section langline">
        <div v-if="section.trueName" class="row-group" data-testid="name-true-name">
            <div class="row">
                <span class="k">True name</span>
                <span>
                    <v-chip size="x-small" label variant="outlined" prepend-icon="mdi-waveform" class="mr-1">
                        {{ section.trueName.language_name }}
                    </v-chip>
                    {{ section.trueName.text }}
                </span>
            </div>
            <div
                v-for="(rendering, i) in section.trueName.renderings"
                :key="i"
                class="row"
            >
                <span class="k">{{ rendering.culture_name }}</span>
                <span>{{ rendering.text }}</span>
            </div>
        </div>
        <div v-else class="row">
            <span class="k">Language</span>
            <v-chip
                size="x-small"
                label
                :variant="section.language ? 'outlined' : 'tonal'"
                :color="section.language ? undefined : 'grey'"
            >
                {{ section.language ? section.language.name : 'none yet' }}
            </v-chip>
            <span v-if="section.language && section.meaning" data-testid="name-meaning">&ldquo;{{ section.meaning }}&rdquo;</span>
            <span v-else-if="section.language" class="note">no meaning recorded</span>
            <span v-else class="note">{{ section.languageNote }}</span>
            <span v-if="!section.language && section.meaning" data-testid="name-meaning">&ldquo;{{ section.meaning }}&rdquo;</span>
        </div>

        <div v-if="section.culture" class="row" data-testid="name-culture-row">
            <span class="k">Culture</span>
            <v-chip
                v-for="chip in section.culture.chips"
                :key="chip.name"
                size="x-small"
                label
                variant="tonal"
                :color="chip.color"
                class="mr-1"
            >
                {{ chip.name }}<template v-if="chip.share !== null && chip.share !== undefined">&nbsp;{{ chip.share }}%</template>
            </v-chip>
            <span class="note">{{ section.culture.note }}</span>
            <v-btn size="x-small" variant="text" class="change-btn" @click="onChangeCulture">
                Change
            </v-btn>
        </div>

        <div v-if="section.review" class="review" data-testid="name-unreviewed-note">
            <v-icon size="small" color="unsaved" class="mr-1">mdi-new-box</v-icon>
            <span>{{ section.review.note }}</span>
            <v-btn
                size="x-small"
                variant="tonal"
                color="warning"
                class="ml-2"
                data-testid="name-review-button"
                @click="onReview"
            >
                Review
            </v-btn>
        </div>
    </div>
</template>

<script>
import { culturesStory } from './culturesStory.js';
import { nameSection } from './storyLexicon.js';

export default {
    name: 'NameLanguageSection',
    inject: {
        openCulturesReview: { default: () => () => {} },
    },
    props: {
        entity: {
            type: Object,
            default: null,
        },
    },
    computed: {
        section() {
            return nameSection(culturesStory.story, this.entity);
        },
    },
    methods: {
        onChangeCulture() {
            if (!this.section?.culture) return;
            this.openCulturesReview(this.section.culture.changeTarget);
        },
        onReview() {
            if (!this.section?.review) return;
            this.openCulturesReview(this.section.review.target);
        },
    },
};
</script>

<style scoped>
.name-language-section {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 8px;
    margin-top: 4px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.row,
.row-group .row {
    display: flex;
    gap: 8px;
    align-items: baseline;
    flex-wrap: wrap;
}

.k {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgb(var(--v-theme-mutedheader));
    min-width: 76px;
}

.note {
    color: rgb(var(--v-theme-muted));
    font-size: 0.85em;
}

.change-btn {
    text-transform: none;
    letter-spacing: 0;
}

.review {
    display: flex;
    align-items: center;
    background: rgba(var(--v-theme-unsaved), 0.12);
    border-radius: 4px;
    padding: 6px 8px;
    margin-top: 2px;
}
</style>
