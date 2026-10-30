<template>
    <v-card variant="flat" class="language-import pa-3 mb-4" data-testid="language-import">
        <div class="d-flex align-center ga-2 mb-2">
            <span class="text-subtitle-2">{{ base ? 'The change' : targetId ? 'Import a new version' : 'Import a language' }}</span>
            <span v-if="!base" class="text-caption text-muted">paste what the assistant made, or choose its file</span>
        </div>
        <!-- a file made for the owner folds away: the review below is what matters -->
        <div v-if="fileFolded" class="text-caption text-muted">
            The made file is filled in.
            <a href="#" data-testid="language-show-file" @click.prevent="fileFolded = false">Show the file</a>
        </div>
        <div v-show="!fileFolded" data-testid="language-paste">
            <v-textarea
                v-model="text"
                label="The language file, or the assistant's whole reply"
                rows="4"
                auto-grow
                max-rows="12"
                variant="outlined"
                density="compact"
                hide-details
                :disabled="busy"
            ></v-textarea>
        </div>
        <div v-if="!fileFolded" class="d-flex align-center flex-wrap ga-2 mt-2">
            <v-btn size="small" color="primary" variant="tonal" :disabled="!text.trim() || busy" :loading="checking" @click="check">Check</v-btn>
            <v-btn size="small" variant="text" prepend-icon="mdi-file-upload-outline" :disabled="busy" @click="$refs.file.click()">Choose a file…</v-btn>
            <input ref="file" type="file" accept=".json,.txt,application/json,text/plain" class="d-none" @change="readFile" />
        </div>

        <div v-if="preview" class="mt-3" data-testid="language-preview">
            <div class="d-flex align-baseline flex-wrap ga-2">
                <span class="text-h6">{{ language.name }}</span>
                <v-chip size="x-small" label variant="tonal">{{ depthLabel }}</v-chip>
                <span v-if="language.flavour" class="text-caption text-muted">sounds {{ language.flavour }}</span>
                <span class="text-caption text-muted">{{ language.dictionary.length }} words · {{ language.phrases.length }} phrases</span>
            </div>
            <div v-if="language.sound" class="text-body-2 mt-1">{{ language.sound }}</div>

            <div class="mt-2" data-testid="language-samples">
                <div v-for="(names, generatorId) in samples" :key="generatorId" class="text-body-2">
                    <span class="text-caption text-muted">{{ generatorLabel(generatorId) }}:</span> {{ names.slice(0, 12).join(', ') }}
                </div>
            </div>

            <div v-if="preview.diff" class="mt-2 text-body-2" data-testid="language-diff">
                <div v-if="preview.diff.words_added.length"><span class="text-caption text-muted">New words:</span> {{ preview.diff.words_added.join(', ') }}</div>
                <div v-if="preview.diff.words_changed.length"><span class="text-caption text-muted">Changed meaning:</span> {{ preview.diff.words_changed.join(', ') }}</div>
                <div v-if="preview.diff.words_removed.length"><span class="text-caption text-muted">Removed:</span> {{ preview.diff.words_removed.join(', ') }}</div>
                <div v-if="phrasesChanged"><span class="text-caption text-muted">Phrases:</span> {{ phrasesChanged }}</div>
                <!-- each changed category whole: as it was, and as it will be -->
                <div v-for="change in preview.diff.phrase_changes || []" :key="change.category" class="phrase-change" data-testid="change-diff-phrases">
                    <div class="text-caption text-muted">{{ change.category.charAt(0).toUpperCase() + change.category.slice(1) }}, before and after</div>
                    <div class="ba">
                        <div v-for="side in [change.before, change.after]" :key="side === change.before ? 'before' : 'after'">
                            <div v-for="(line, i) in side" :key="i"><span class="foreign">{{ line.original }}</span> {{ line.translation }}</div>
                            <span v-if="!side.length" class="text-muted">none</span>
                        </div>
                    </div>
                </div>
                <div v-if="grammarChanged" data-testid="change-diff-grammar"><span class="text-caption text-muted">Grammar:</span> {{ grammarChanged }}</div>
                <div v-if="(preview.diff.rules_removed || []).length"><span class="text-caption text-muted">Name rules removed:</span> {{ preview.diff.rules_removed.join(', ') }}</div>
                <div v-if="preview.diff.generators_changed" class="text-caption text-muted">The name rules change: compare the sample names above.</div>
                <div v-if="preview.diff.sound_after != null" class="sound-change" data-testid="change-diff-sound">
                    <div class="text-caption text-muted">How it sounds, before and after</div>
                    <div class="ba"><div>{{ preview.diff.sound_before }}</div><div>{{ preview.diff.sound_after }}</div></div>
                </div>
                <!-- what stayed as it was, and why -->
                <div v-if="preview.diff.kept_used.length || (preview.diff.kept_edits || []).length" class="kept mt-2" data-testid="change-kept">
                    <div v-if="preview.diff.kept_used.length"><b>Kept as they are:</b> {{ preview.diff.kept_used.join(', ') }} (the world uses {{ preview.diff.kept_used.length === 1 ? 'it' : 'them' }} as a name)</div>
                    <div v-if="(preview.diff.kept_edits || []).length"><b>Kept your edit:</b> {{ preview.diff.kept_edits.join(', ') }} (you changed {{ preview.diff.kept_edits.length === 1 ? 'it' : 'them' }} while this ran; your version stays)</div>
                </div>
            </div>

            <LanguageCheckReport class="mt-2" :report="preview.report" :repair-note="preview.repair_note" />

            <div class="d-flex align-center ga-2 mt-3">
                <v-btn size="small" color="primary" :disabled="!preview.ok || busy" :loading="importing" data-testid="language-accept" @click="doImport">{{ base ? 'Accept the change' : targetId ? 'Import this version' : 'Import' }}</v-btn>
                <v-btn size="small" variant="text" :disabled="busy" data-testid="language-drop" @click="$emit('cancel'); worlds.clearLanguagePreview()">{{ base ? 'Drop it' : 'Cancel' }}</v-btn>
            </div>
        </div>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import LanguageCheckReport from './LanguageCheckReport.vue';

const DEPTHS = { description: 'description only', naming: 'naming style', full: 'full language' };

// Importing a language (languages 3a): paste a file or an assistant's
// whole reply, or choose a file; check it (the shared check), see the
// samples and, for a new version, what changes; then import.
export default {
    name: 'LanguageImport',
    components: { LanguageCheckReport },
    props: {
        // a language entry to import a new version onto; null for a new one
        targetId: { type: String, default: null },
        // a file made for the owner (languages 3b): filled in and checked
        initialText: { type: String, default: null },
        // for a change: the version it was briefed on (the review merges it
        // onto the language as it is now)
        base: { type: String, default: null },
    },
    emits: ['cancel'],
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { text: '', fileFolded: false };
    },
    computed: {
        preview() {
            const preview = this.worlds.languagePreview;
            return preview && (preview.target_id || null) === this.targetId ? preview : null;
        },
        language() {
            return this.preview.file.language;
        },
        samples() {
            return this.preview.report.samples || {};
        },
        depthLabel() {
            return DEPTHS[this.language.level] || this.language.level;
        },
        grammarChanged() {
            const diff = this.preview.diff;
            const parts = [];
            if ((diff.grammar_added || []).length) parts.push(`new: ${diff.grammar_added.join(', ')}`);
            if ((diff.grammar_changed || []).length) parts.push(`changed: ${diff.grammar_changed.join(', ')}`);
            if ((diff.grammar_removed || []).length) parts.push(`removed: ${diff.grammar_removed.join(', ')}`);
            return parts.join(' · ');
        },
        phrasesChanged() {
            const diff = this.preview.diff;
            const parts = [];
            if (diff.phrases_added.length) parts.push(`${diff.phrases_added.length} new`);
            if (diff.phrases_changed.length) parts.push(`${diff.phrases_changed.length} changed`);
            if (diff.phrases_removed.length) parts.push(`${diff.phrases_removed.length} removed`);
            return parts.join(', ');
        },
        checking() {
            return !!this.worlds.pending.language_preview;
        },
        importing() {
            return !!this.worlds.pending.language_import;
        },
        busy() {
            return this.checking || this.importing;
        },
    },
    watch: {
        initialText: {
            immediate: true,
            handler(text) {
                if (text) {
                    this.text = text;
                    this.fileFolded = true;
                    this.check();
                } else if (this.fileFolded) {
                    // "Make another": the made file goes with it
                    this.text = '';
                    this.fileFolded = false;
                }
            },
        },
    },
    beforeUnmount() {
        this.worlds.clearLanguagePreview();
    },
    methods: {
        check() {
            this.worlds.previewLanguage(this.text, this.targetId, this.base);
        },
        doImport() {
            this.worlds.importLanguage(this.text, this.targetId, this.base);
            this.$emit('cancel');
        },
        generatorLabel(id) {
            const generator = this.language.generators.find((g) => g.id === id);
            return generator ? generator.name : id;
        },
        async readFile(event) {
            const file = event.target.files?.[0];
            if (!file) return;
            this.text = await file.text();
            event.target.value = '';
            this.check();
        },
    },
};
</script>

<style scoped>
.ba {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}
.ba > div {
    background: rgba(var(--v-theme-on-surface), 0.05);
    border-radius: 4px;
    padding: 6px 10px;
}
.phrase-change {
    margin-top: 6px;
}
/* the language's own words, as in the Lexicon */
.foreign {
    font-style: italic;
    color: rgb(var(--v-theme-foreign));
}
.kept {
    background: rgba(var(--v-theme-warning), 0.12);
    border-radius: 4px;
    padding: 8px 12px;
}
.language-import {
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
