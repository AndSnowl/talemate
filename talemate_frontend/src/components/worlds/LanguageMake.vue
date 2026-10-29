<template>
    <v-card variant="flat" class="language-make pa-3 mb-4" data-testid="language-make">
        <div class="text-subtitle-2 mb-2">Make a language</div>

        <template v-if="!made">
            <div data-testid="make-request">
                <v-textarea
                    v-model="draft.text"
                    placeholder="What should it be like? For example: a unique but recognizably Russian language"
                    rows="2"
                    auto-grow
                    density="compact"
                    variant="outlined"
                    hide-details
                    :disabled="running"
                    @focus="worlds.loadLanguageMakeRoute()"
                ></v-textarea>
            </div>
            <v-autocomplete
                v-model="draft.contextIds"
                :items="entries"
                label="Take into account (optional)"
                multiple
                chips
                closable-chips
                density="compact"
                variant="outlined"
                hide-details
                class="mt-2"
                :disabled="running"
                data-testid="make-context"
            ></v-autocomplete>

            <!-- the questions, once asked: answer them, or let it decide -->
            <div v-if="questions.length" class="mt-3" data-testid="make-questions">
                <div v-for="(question, index) in questions" :key="index" class="mb-2">
                    <div class="text-body-2 mb-1">{{ question }}</div>
                    <v-text-field
                        v-model="draft.answers[index]"
                        placeholder="Your answer, or leave it to decide"
                        density="compact"
                        variant="outlined"
                        hide-details
                        :disabled="running"
                        data-testid="make-answer"
                    ></v-text-field>
                </div>
            </div>
            <div v-else-if="worlds.languageQuestions?.error" class="text-caption text-error mt-2">{{ worlds.languageQuestions.error }}</div>

            <!-- this run's route and how much it makes (the agent's are the defaults) -->
            <LanguageRouteChoice
                class="mt-3"
                :route="route"
                :claude-model="claudeModel"
                :disabled="running"
                @update:route="draft.route = $event"
                @update:claude-model="draft.claudeModel = $event"
            />
            <div class="d-flex flex-wrap align-center ga-2 mt-2">
                <span class="text-caption text-muted">How much</span>
                <v-btn-toggle :model-value="size" mandatory density="compact" variant="outlined" divided color="primary" :disabled="running" @update:model-value="draft.size = $event">
                    <v-btn value="full" size="small" :aria-pressed="String(size === 'full')" data-testid="make-size-full">Full: everything in one go</v-btn>
                    <v-btn value="quick" size="small" :aria-pressed="String(size === 'quick')" data-testid="make-size-quick">Quick, then fill in</v-btn>
                </v-btn-toggle>
            </div>
            <div class="text-caption text-muted mt-1" data-testid="make-size-note">{{ sizeNote }}</div>

            <div class="d-flex flex-wrap align-center ga-2 mt-3">
                <template v-if="!briefOnly">
                    <v-btn size="small" color="primary" variant="tonal" :disabled="!canStart" data-testid="make-start" @click="start(false)">Make it</v-btn>
                    <v-btn v-if="questions.length" size="small" variant="text" :disabled="!canStart" data-testid="make-decide" @click="start(true)">Decide for me</v-btn>
                    <v-btn v-else size="small" variant="text" :disabled="!canStart" :loading="asking" data-testid="make-ask" @click="ask">Ask me questions</v-btn>
                </template>
                <v-btn size="small" :variant="briefOnly ? 'tonal' : 'text'" :color="briefOnly ? 'primary' : undefined" :disabled="!text.trim()" prepend-icon="mdi-content-copy" data-testid="make-copy-brief" @click="copyBrief">Copy the brief</v-btn>
                <v-btn v-if="hasDraft && !running" size="small" variant="text" color="delete" data-testid="make-discard" @click="again">Discard</v-btn>
                <span v-if="copied" class="text-caption text-success" data-testid="make-copied">Copied</span>
            </div>
            <div v-if="otherBusy" class="d-flex align-center ga-2 text-caption text-muted mt-1" data-testid="make-busy">
                Something else is being made or changed; wait for it or cancel it.
                <v-btn size="x-small" variant="text" color="delete" data-testid="make-busy-cancel" @click="worlds.cancelLanguageMake()">Cancel it</v-btn>
            </div>
            <div v-if="briefOnly" class="text-caption text-muted mt-1">Paste what your assistant returns into Import a language below.</div>
            <v-textarea
                v-if="briefFallback"
                :model-value="briefFallback"
                readonly
                rows="6"
                density="compact"
                variant="outlined"
                hide-details
                class="mt-2"
                label="The brief: select it all and copy"
                data-testid="make-brief-text"
            ></v-textarea>

            <!-- while it's being made -->
            <div v-if="running" class="mt-3" data-testid="make-progress">
                <div class="d-flex align-center ga-2">
                    <v-progress-circular indeterminate size="16" width="2" color="primary"></v-progress-circular>
                    <span class="text-body-2">Making it{{ routeLabel ? ` with ${routeLabel}` : '' }}…</span>
                    <v-btn size="small" variant="text" color="delete" data-testid="make-cancel" @click="worlds.cancelLanguageMake()">Cancel</v-btn>
                </div>
                <ul class="progress-lines text-caption text-muted mt-1">
                    <li v-for="(line, index) in lines" :key="index">{{ line }}</li>
                </ul>
            </div>
            <div v-if="job?.error" class="text-body-2 text-error mt-3" data-testid="make-error">{{ job.error }}</div>
        </template>

        <!-- made: the review below takes over -->
        <div v-else class="d-flex align-center ga-2" data-testid="make-done">
            <span class="text-body-2">Made with {{ doneLabel }}: review it below.</span>
            <v-btn size="small" variant="text" @click="again">Make another</v-btn>
        </div>
    </v-card>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import LanguageRouteChoice from './LanguageRouteChoice.vue';


// what a run makes, by route and how much (shown under the choices)
const SIZE_NOTES = {
    claude_code: {
        full: 'About 300 words, phrases in every category, all the grammar topics. Runs on your subscription and takes about 10–15 minutes.',
        quick: 'A core: the structural words, about 40 everyday ones, a few phrases and short grammar. Runs on your subscription; fill in the rest later.',
    },
    in_app: {
        full: 'Everything in one long reply: needs a model that can write a long answer, and spends API tokens.',
        quick: 'A core in one reply, then fill in the rest later. Spends API tokens.',
    },
    brief: {
        full: 'The brief asks for everything: about 300 words, phrases in every category, all the grammar topics.',
        quick: 'The brief asks for a core; fill in the rest later.',
    },
};

const ROUTES = {
    claude_code: 'Claude Code',
    in_app: "the Language agent's model",
    brief: 'the brief',
};

// Making a language (languages 3b): the owner's words, entries to take
// into account, plain questions (or "decide for me"), then a route (Claude
// Code, the agent's model) with progress and cancel. Copy the brief is
// always there. The result goes to the import review below it.
export default {
    name: 'LanguageMake',
    components: { LanguageRouteChoice },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { copyWanted: false, copied: false, briefFallback: '' };
    },
    computed: {
        // the request, its entries and answers live in the store, so they
        // stay while the owner looks elsewhere
        draft() {
            return this.worlds.languageMakeDraft;
        },
        text() {
            return this.draft.text || '';
        },
        hasDraft() {
            return !!this.text.trim() || this.draft.contextIds.length > 0 || this.questions.length > 0 || !!this.job?.error;
        },
        // Make's own job; a change or fill running elsewhere only blocks it
        job() {
            const job = this.worlds.languageMake;
            return job && (job.kind || 'new') === 'new' ? job : null;
        },
        otherBusy() {
            const job = this.worlds.languageMake;
            return !!job && (job.kind || 'new') !== 'new' && job.running;
        },
        running() {
            return !!this.job?.running;
        },
        made() {
            return !!this.job?.text;
        },
        lines() {
            return (this.job?.lines || []).slice(-6);
        },
        questions() {
            return this.worlds.languageQuestions?.questions || [];
        },
        asking() {
            return !!this.worlds.languageQuestions?.pending;
        },
        defaults() {
            return this.worlds.languageMakeRoute || {};
        },
        // this run's choices: the owner's, else the agent's defaults
        route() {
            return this.draft.route || this.defaults.route || 'claude_code';
        },
        claudeModel() {
            return this.draft.claudeModel ?? this.defaults.claude_model ?? '';
        },
        size() {
            return this.draft.size || (this.defaults.sizes || {})[this.route] || (this.route === 'in_app' ? 'quick' : 'full');
        },
        sizeNote() {
            return (SIZE_NOTES[this.route] || {})[this.size] || '';
        },
        briefOnly() {
            return this.route === 'brief';
        },
        routeLabel() {
            return ROUTES[this.job?.route || this.route] || '';
        },
        doneLabel() {
            return ROUTES[this.job?.route] || 'the assistant';
        },
        canStart() {
            return !!this.text.trim() && !this.running && !this.asking && !this.otherBusy;
        },
        entries() {
            return Object.values(this.worlds.things || {})
                .flat()
                .filter((thing) => thing && thing.id && thing.name)
                .map((thing) => ({ title: thing.name, value: thing.id }));
        },
    },
    watch: {
        'worlds.languageBrief'(brief) {
            if (brief && this.copyWanted) {
                this.copyWanted = false;
                this.copyText(brief);
            }
        },
    },
    mounted() {
        this.worlds.loadLanguageMakeRoute();
    },
    methods: {
        request(decideForMe) {
            return {
                text: this.text.trim(),
                answers: this.questions.map((question, index) => ({ question, answer: this.draft.answers[index] || '' })),
                decide_for_me: decideForMe,
                context_ids: this.draft.contextIds,
                route: this.route,
                size: this.size,
                ...(this.route === 'claude_code' ? { claude_model: this.claudeModel } : {}),
            };
        },
        ask() {
            this.draft.answers = [];
            this.worlds.askLanguageQuestions(this.text.trim());
        },
        start(decideForMe) {
            this.briefFallback = '';
            this.worlds.startLanguageMake(this.request(decideForMe));
        },
        copyBrief() {
            this.copied = false;
            this.briefFallback = '';
            this.copyWanted = true;
            this.worlds.requestLanguageBrief(this.request(false));
        },
        async copyText(brief) {
            try {
                await navigator.clipboard.writeText(brief);
                this.copied = true;
                setTimeout(() => {
                    this.copied = false;
                }, 4000);
            } catch {
                // no clipboard (an insecure page, or refused): show it to copy
                this.briefFallback = brief;
            }
        },
        // Discard, or Make another: the request, answers and result go
        again() {
            this.briefFallback = '';
            this.worlds.clearLanguageMake();
            this.worlds.clearLanguagePreview();
        },
    },
};
</script>

<style scoped>
.progress-lines {
    list-style: none;
    padding-left: 24px;
}
</style>
