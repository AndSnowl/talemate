<template>
    <v-card variant="flat" class="language-change pa-3 mb-4" data-testid="language-change">
        <div class="d-flex align-center ga-2">
            <span class="text-overline text-muted">Change {{ languageName }}</span>
            <v-btn icon="mdi-close" size="x-small" variant="text" density="comfortable" class="ml-auto" aria-label="Close" @click="worlds.closeLanguageChange()"></v-btn>
        </div>

        <!-- the change, made: review it here -->
        <template v-if="job && job.text">
            <div class="text-caption text-muted mb-1">Changed with {{ routeLabel(job.route) }}: review it.</div>
            <LanguageImport :initial-text="job.text" :target-id="job.targetId" :base="job.base" @cancel="drop" />
        </template>

        <template v-else>
            <div data-testid="change-request">
                <v-textarea
                    ref="request"
                    v-model="draft.text"
                    placeholder="What should change? For example: they're traders, not warriors: redo the curses"
                    rows="2"
                    auto-grow
                    density="compact"
                    variant="outlined"
                    hide-details
                    :disabled="running"
                ></v-textarea>
            </div>

            <!-- the entries to fit it to: suggested and ticked, others added -->
            <div class="text-overline text-muted mt-2">Fit it to</div>
            <div v-for="entry in fitEntries" :key="entry.id" class="d-flex align-center ga-2" data-testid="change-fit">
                <v-checkbox-btn :model-value="contextIds.includes(entry.id)" density="compact" class="fit-box" :disabled="running" @update:model-value="toggleFit(entry.id, $event)"></v-checkbox-btn>
                <span class="text-body-2">{{ entry.name }}</span>
                <span v-if="entry.why" class="text-caption text-muted">{{ entry.why }}</span>
            </div>
            <v-autocomplete
                :model-value="null"
                :items="otherEntries"
                placeholder="+ Add another entry…"
                density="compact"
                variant="plain"
                hide-details
                class="add-fit"
                :disabled="running"
                @update:model-value="addFit"
            ></v-autocomplete>

            <LanguageRouteChoice
                class="mt-2"
                prefix="change"
                :route="route"
                :claude-model="claudeModel"
                :disabled="running"
                @update:route="draft.route = $event"
                @update:claude-model="draft.claudeModel = $event"
            />

            <div class="d-flex flex-wrap align-center ga-2 mt-3">
                <v-btn v-if="!briefOnly" size="small" color="primary" variant="tonal" :disabled="!canStart" data-testid="change-start" @click="start('change')">Change it</v-btn>
                <v-btn size="small" :variant="briefOnly ? 'tonal' : 'text'" :color="briefOnly ? 'primary' : undefined" :disabled="!draft.text.trim()" prepend-icon="mdi-content-copy" data-testid="change-copy-brief" @click="copyBrief('change')">Copy the brief</v-btn>
                <span v-if="copied" class="text-caption text-success" data-testid="change-copied">Copied</span>
                <v-btn v-if="!running" size="small" variant="text" color="delete" data-testid="change-discard" @click="discard">Discard</v-btn>
            </div>
            <div v-if="otherBusy" class="text-caption text-muted mt-1">Something else is being made or changed; wait for it or cancel it.</div>
            <v-textarea v-if="briefFallback" :model-value="briefFallback" readonly rows="6" density="compact" variant="outlined" hide-details class="mt-2" label="The brief: select it all and copy"></v-textarea>

            <!-- while it runs -->
            <div v-if="running" class="mt-3" data-testid="change-progress">
                <div class="d-flex align-center ga-2">
                    <v-progress-circular indeterminate size="16" width="2" color="primary"></v-progress-circular>
                    <span class="text-body-2">Changing it with {{ routeLabel(job.route || route) }}…</span>
                    <v-btn size="small" variant="text" color="delete" data-testid="change-cancel" @click="worlds.cancelLanguageMake()">Cancel</v-btn>
                </div>
                <ul class="progress-lines text-caption text-muted mt-1">
                    <li v-for="(line, index) in (job.lines || []).slice(-6)" :key="index">{{ line }}</li>
                </ul>
            </div>
            <div v-if="job && job.error" class="text-body-2 text-error mt-3" data-testid="change-error">{{ job.error }}</div>

            <!-- what the check finds missing, and the next step to fill it -->
            <div v-if="stillLines.length" class="still mt-4" data-testid="change-still">
                <div class="text-overline text-muted">Still to fill in</div>
                <div class="d-flex flex-wrap align-start ga-4">
                    <ul class="report-list text-body-2">
                        <li v-for="(line, index) in stillLines" :key="index">{{ line }}</li>
                    </ul>
                    <v-btn v-if="fillStep" size="small" color="primary" variant="tonal" :disabled="running || otherBusy" data-testid="change-fill" @click="fill">Fill in next: {{ fillStep }}</v-btn>
                </div>
            </div>
        </template>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import LanguageImport from './LanguageImport.vue';
import LanguageRouteChoice from './LanguageRouteChoice.vue';

const ROUTE_LABELS = { claude_code: 'Claude Code', in_app: "the Language agent's model", brief: 'the brief' };

// Change it… (languages 3b-2b; mockup 2026-10-29-languages-3b2-change-it):
// a plain request, the entries to fit it to (suggested, with why), the
// route, then the change runs in the background and comes back as a
// review that keeps the owner's own edits. Still to fill in, with Fill in
// next, sits underneath. On a language's page it changes that language.
export default {
    name: 'LanguageChange',
    components: { LanguageImport, LanguageRouteChoice },
    props: {
        // the language page this panel sits on
        thing: { type: Object, required: true },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { copyWanted: false, copied: false, briefFallback: '' };
    },
    computed: {
        draft() {
            return this.worlds.languageChange;
        },
        targetId() {
            return this.draft?.targetId || null;
        },
        languageName() {
            return this.thing.name || 'the language';
        },
        // this panel's job: a change or fill of this language
        job() {
            const job = this.worlds.languageMake;
            return job && job.kind !== 'new' && job.targetId === this.targetId ? job : null;
        },
        running() {
            return !!this.job?.running;
        },
        otherBusy() {
            const job = this.worlds.languageMake;
            return !!job && job.running && job !== this.job;
        },
        defaults() {
            return this.worlds.languageMakeRoute || {};
        },
        route() {
            return this.draft.route || this.defaults.route || 'claude_code';
        },
        claudeModel() {
            return this.draft.claudeModel ?? this.defaults.claude_model ?? '';
        },
        briefOnly() {
            return this.route === 'brief';
        },
        related() {
            const found = this.worlds.languageRelated;
            return found && found.language_id === this.targetId ? found.entries : [];
        },
        // ticked entries: the suggestions until the owner changes them
        contextIds() {
            return this.draft.contextIds ?? this.related.map((entry) => entry.id);
        },
        fitEntries() {
            const listed = [...this.related];
            for (const id of this.contextIds) {
                if (!listed.some((entry) => entry.id === id)) {
                    const thing = this.allEntries.find((entry) => entry.value === id);
                    if (thing) listed.push({ id, name: thing.title, why: '' });
                }
            }
            return listed;
        },
        allEntries() {
            return Object.values(this.worlds.things || {})
                .flat()
                .filter((thing) => thing && thing.id && thing.name && thing.id !== this.targetId)
                .map((thing) => ({ title: thing.name, value: thing.id }));
        },
        otherEntries() {
            const shown = new Set(this.fitEntries.map((entry) => entry.id));
            return this.allEntries.filter((entry) => !shown.has(entry.value));
        },
        completeness() {
            return this.thing.completeness || null;
        },
        stillLines() {
            const found = this.completeness;
            if (!found) return [];
            const lines = [];
            const missing = found.meanings_missing || [];
            if (missing.length) {
                const shown = missing.slice(0, 6).join(', ') + (missing.length > 6 ? ', …' : '');
                lines.push(`Words: ${missing.length} of ${found.meanings_total} missing (${shown})`);
            }
            if ((found.phrase_categories_missing || []).length) lines.push(`Phrases: no ${found.phrase_categories_missing.join(', ')}`);
            if ((found.grammar_topics_missing || []).length) lines.push(`Grammar: ${found.grammar_topics_missing.join(', ')} not written`);
            return lines;
        },
        // the first group with something missing (talemate.languages.completeness.fill_step)
        fillStep() {
            const found = this.completeness;
            if (!found) return null;
            if ((found.meanings_missing || []).length) return 'words';
            if ((found.phrase_categories_missing || []).length) return 'phrases';
            if ((found.grammar_topics_missing || []).length) return 'grammar';
            return null;
        },
        canStart() {
            return !!this.draft.text.trim() && !this.running && !this.otherBusy;
        },
    },
    watch: {
        'worlds.languageChangeFocus'() {
            this.focusRequest();
        },
        'worlds.languageBrief'(brief) {
            if (brief && this.copyWanted) {
                this.copyWanted = false;
                this.copyText(brief);
            }
        },
    },
    mounted() {
        this.worlds.loadLanguageMakeRoute();
        this.focusRequest();
    },
    methods: {
        // the cursor at the end of the request, ready to finish it
        focusRequest() {
            this.$nextTick(() => {
                const el = this.$refs.request?.$el?.querySelector('textarea');
                if (!el) return;
                el.focus();
                el.setSelectionRange(el.value.length, el.value.length);
            });
        },
        routeLabel(route) {
            return ROUTE_LABELS[route] || 'the assistant';
        },
        request(kind) {
            return {
                kind,
                target_id: this.targetId,
                text: kind === 'fill' ? '' : this.draft.text.trim(),
                context_ids: this.contextIds,
                route: this.route,
                ...(this.route === 'claude_code' ? { claude_model: this.claudeModel } : {}),
            };
        },
        start(kind) {
            this.briefFallback = '';
            this.worlds.startLanguageMake(this.request(kind));
        },
        // on the brief route, Fill in next copies that step's brief
        fill() {
            if (this.briefOnly) this.copyBrief('fill');
            else this.start('fill');
        },
        copyBrief(kind) {
            this.copied = false;
            this.briefFallback = '';
            this.copyWanted = true;
            this.worlds.requestLanguageBrief(this.request(kind));
        },
        async copyText(brief) {
            try {
                await navigator.clipboard.writeText(brief);
                this.copied = true;
                setTimeout(() => {
                    this.copied = false;
                }, 4000);
            } catch {
                this.briefFallback = brief;
            }
        },
        toggleFit(id, on) {
            const ids = this.contextIds.filter((other) => other !== id);
            this.draft.contextIds = on ? [...ids, id] : ids;
        },
        addFit(id) {
            if (id) this.draft.contextIds = [...this.contextIds, id];
        },
        // Drop: the result goes, the request stays
        drop() {
            this.worlds.languageMake = null;
            this.worlds.clearLanguagePreview();
        },
        discard() {
            this.worlds.closeLanguageChange();
        },
    },
};
</script>

<style scoped>
.fit-box {
    flex: none;
}
.add-fit {
    max-width: 320px;
}
.still {
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    padding-top: 10px;
}
.report-list {
    padding-left: 18px;
}
.progress-lines {
    list-style: none;
    padding-left: 24px;
}
</style>
