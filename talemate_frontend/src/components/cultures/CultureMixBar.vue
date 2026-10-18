<template>
    <div
        class="mix-bar"
        :style="{ height: height + 'px', borderRadius: (height / 2) + 'px' }"
    >
        <span
            v-for="cs in mix"
            :key="cs.culture_id"
            :style="{ width: cs.share + '%', backgroundColor: colorFor(cs.culture_id) }"
        >
            <v-tooltip activator="parent" location="top">{{ nameFor(cs.culture_id) }} {{ cs.share }}%</v-tooltip>
        </span>
    </div>
</template>

<script>
import { dataColor } from '@/theme/dataColors';
import { currentTheme } from '@/theme/store';

export default {
    name: 'CultureMixBar',
    props: {
        mix: {
            type: Array,
            default: () => [],
        },
        cultures: {
            type: Array,
            default: () => [],
        },
        height: {
            type: Number,
            default: 8,
        },
    },
    methods: {
        cultureFor(cultureId) {
            return this.cultures.find(c => c.id === cultureId) || null;
        },
        colorFor(cultureId) {
            const culture = this.cultureFor(cultureId);
            if (!culture) return currentTheme.value.colors.muted;
            return dataColor(culture.color) || culture.color;
        },
        nameFor(cultureId) {
            const culture = this.cultureFor(cultureId);
            return culture ? culture.name : cultureId;
        },
    },
}
</script>

<style scoped>
.mix-bar {
    display: flex;
    overflow: hidden;
    background: rgba(var(--v-theme-on-surface), 0.08);
    min-width: 60px;
}

.mix-bar span {
    display: block;
    height: 100%;
}
</style>
