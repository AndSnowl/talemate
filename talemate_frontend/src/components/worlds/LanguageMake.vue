<template>
    <v-card variant="flat" class="language-make pa-3 mb-4" data-testid="language-make">
        <div class="text-subtitle-2 mb-2">Make a language</div>

        <template v-if="!made">
            <div data-testid="make-request">
                <v-textarea
                    v-model="text"
                    placeholder="What should it be like? For example: a unique but recognizably Russian language"
                    rows="2"
                    auto-grow
                    density="compact"
                    variant="outlined"
                    hide-details
                    :disabled="running"
                ></v-textarea>
            </div>
            <v-autocomplete
                v-model="contextIds"
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
                        v-model="answers[index]"
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

            <div class="d-flex flex-wrap align-center ga-2 mt-3">
                <template v-if="!briefOnly">
                    <v-btn size="small" color="primary" variant="tonal" :disabled="!canStart" data-testid="make-start" @click="start(false)">Make it</v-btn>
                    <v-btn v-if="questions.length" size="small" variant="text" :disabled="!canStart" data-testid="make-decide" @click="start(true)">Decide for me</v-btn>
                    <v-btn v-else size="small" variant="text" :disabled="!canStart" :loading="asking" data-testid="make-ask" @click="ask">Ask me questions</v-btn>
                </template>
                <v-btn size="small" :variant="briefOnly ? 'tonal' : 'text'" :color="briefOnly ? 'primary' : undefined" :disabled="!text.trim()" prepend-icon="mdi-content-copy" data-testid="make-copy-brief" @click="copyBrief">Copy the brief</v-btn>
                <span v-if="copied" class="text-caption text-success" data-testid="make-copied">Copied</span>
            </div>
            <div class="text-caption text-muted mt-1">
                <template v-if="briefOnly">Paste what your assistant returns into Import a language below.</template>
                <template v-else-if="routeLabel">Made with {{ routeLabel }}; change this in the Language agent's settings.</template>
            </div>
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
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { text: '', contextIds: [], answers: [], copyWanted: false, copied: false, briefFallback: '' };
    },
    computed: {
        job() {
            return this.worlds.languageMake;
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
        route() {
            return this.worlds.languageMakeRoute;
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
            return !!this.text.trim() && !this.running && !this.asking;
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
                answers: this.questions.map((question, index) => ({ question, answer: this.answers[index] || '' })),
                decide_for_me: decideForMe,
                context_ids: this.contextIds,
            };
        },
        ask() {
            this.answers = [];
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
        again() {
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
