<template>
    <div class="language-report" data-testid="language-report">
        <div v-if="report.blocking.length" class="mb-2">
            <div class="text-subtitle-2 text-error">These must be fixed before the language can be imported:</div>
            <ul class="report-list">
                <li v-for="(problem, index) in report.blocking" :key="'b' + index">{{ problem }}</li>
            </ul>
        </div>
        <div v-if="report.warnings.length" class="mb-2">
            <div class="text-subtitle-2 text-warning">Worth fixing:</div>
            <ul class="report-list">
                <li v-for="(warning, index) in report.warnings" :key="'w' + index">{{ warning }}</li>
            </ul>
        </div>
        <div v-if="!report.blocking.length && !report.warnings.length" class="text-body-2 text-success mb-2">
            No problems found.
        </div>
        <!-- what a full language still lacks: information, never a problem -->
        <div v-if="stillToFill.length" class="mb-2" data-testid="check-still-to-fill">
            <div class="text-subtitle-2">Still to fill in</div>
            <ul class="report-list text-body-2">
                <li v-for="(line, index) in stillToFill" :key="'s' + index">{{ line }}</li>
            </ul>
        </div>
        <div class="text-caption text-muted">
            <span v-if="report.fit_share != null">{{ fitPercent }}% of the words follow the language's own word rules.</span>
            <span v-else-if="report.fit_skipped_reason">Word rules not checked: {{ report.fit_skipped_reason }}.</span>
            <span v-if="report.real_skipped_reason"> Real words not checked: {{ report.real_skipped_reason }}.</span>
        </div>
        <div v-if="repairNote && (report.blocking.length || report.warnings.length)" class="d-flex align-center ga-2 mt-2">
            <v-btn size="small" variant="tonal" prepend-icon="mdi-content-copy" @click="copyNote">Copy note</v-btn>
            <span class="text-caption text-muted">to paste back to the assistant that made it</span>
            <span v-if="copied" class="text-caption text-success">Copied</span>
        </div>
    </div>
</template>

<script>
// The shared check's report (`languages.check`) in plain words, with the
// repair note to copy back to whichever assistant made the language.
export default {
    name: 'LanguageCheckReport',
    props: {
        report: { type: Object, required: true },
        repairNote: { type: String, default: '' },
    },
    computed: {
        fitPercent() {
            return Math.round((this.report.fit_share || 0) * 100);
        },
        stillToFill() {
            const found = this.report.completeness;
            if (!found) return [];
            const lines = [];
            const missing = found.meanings_missing || [];
            if (missing.length) {
                const shown = missing.slice(0, 8).join(', ') + (missing.length > 8 ? ', …' : '');
                lines.push(`Words: ${missing.length} of ${found.meanings_total} missing (${shown})`);
            }
            if ((found.phrase_categories_missing || []).length) lines.push(`Phrases: no ${found.phrase_categories_missing.join(', ')}`);
            if ((found.grammar_topics_missing || []).length) lines.push(`Grammar: ${found.grammar_topics_missing.join(', ')} not written`);
            return lines;
        },
    },
    data() {
        return { copied: false };
    },
    methods: {
        async copyNote() {
            try {
                await navigator.clipboard.writeText(this.repairNote);
                this.copied = true;
            } catch {
                this.copied = false;
            }
        },
    },
};
</script>

<style scoped>
.report-list {
    margin: 0.25rem 0 0 1.25rem;
    font-size: 0.875rem;
}
</style>
