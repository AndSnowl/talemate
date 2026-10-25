<template>
    <!-- `display: contents`: the button sits in its heading's row; the
         form and the draft wrap onto their own line under it -->
    <div class="entry-add-facts">
        <v-btn
            v-if="!asking && !draft"
            variant="text"
            size="small"
            color="accent"
            prepend-icon="mdi-creation"
            :data-testid="event ? 'add-event' : 'add-facts'"
            :disabled="onDraft && worlds.nestedHeld"
            :title="onDraft && worlds.nestedHeld ? 'write or discard the added facts first' : null"
            @click="start"
        >{{ event ? '+ Add event…' : '+ Add facts…' }}</v-btn>

        <div v-if="asking && !draft" class="panel ask pa-2" :data-testid="event ? 'add-event-form' : 'add-facts-form'" @keydown.esc="asking = false">
            <div class="d-flex align-start ga-2">
                <v-textarea
                    v-model="prompt"
                    :label="event ? 'What happened' : 'What to add'"
                    :placeholder="event ? 'the river froze and the ferries stopped…' : 'how it is governed, who serves it…'"
                    auto-grow
                    rows="2"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="flex-grow-1"
                    data-testid="add-prompt"
                    @keydown.enter.exact.prevent="ask"
                ></v-textarea>
                <v-text-field
                    v-if="event"
                    v-model.number="year"
                    label="Year"
                    type="number"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="year"
                    data-testid="add-year"
                ></v-text-field>
            </div>
            <div class="d-flex ga-2 mt-2">
                <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-creation" :disabled="!canAsk || (onDraft && worlds.nestedHeld)" data-testid="add-draft" @click="ask">Draft</v-btn>
                <v-btn variant="text" size="small" @click="asking = false">Cancel</v-btn>
            </div>
        </div>

        <!-- the drafted facts, for the owner to tick: nothing is written
             before Write (on a draft page, nothing reaches the world
             before the page draft's Accept) -->
        <div v-if="draft" class="panel" :class="{ nested: onDraft }" data-testid="fact-draft">
            <!-- its first ask: nothing held yet -->
            <template v-if="!draft.versions.length">
                <div v-if="draft.pending" class="d-flex align-center ga-2 text-caption text-muted">
                    <v-progress-circular indeterminate size="16" width="2" color="accent"></v-progress-circular>
                    Drafting “{{ draft.prompt }}”…
                    <v-btn variant="text" size="small" data-testid="fact-draft-discard" @click="discard">Discard</v-btn>
                </div>
                <template v-else>
                    <div class="text-caption text-error" data-testid="fact-draft-error">{{ draft.error }}</div>
                    <div class="d-flex ga-2 mt-1">
                        <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" data-testid="fact-draft-regenerate" @click="worlds.regenerateSmall(draft.key)">Try again</v-btn>
                        <v-btn variant="text" size="small" data-testid="fact-draft-discard" @click="discard">Close</v-btn>
                    </div>
                </template>
            </template>

            <template v-else>
                <SuggestionBar
                    :label="dated ? 'Event draft' : 'Facts draft'"
                    :versions="versionRows"
                    :version="draft.version"
                    :prompt="draft.prompt"
                    :year="dated ? draft.year : undefined"
                    :prompt-label="dated ? 'What happened' : 'What to add'"
                    prompt-testid="add-prompt"
                    :busy="busy"
                    :locked="draft.pending ? 'drafting another version…' : null"
                    :primary-label="'Write ' + ticked"
                    :can-primary="ticked > 0"
                    :primary-loading="!!draft.accepting"
                    testid="fact-draft-bar"
                    :testids="barIds"
                    @update:prompt="worlds.setSmallPrompt(draft.key, $event)"
                    @update:year="worlds.setSmallPrompt(draft.key, draft.prompt, $event)"
                    @regenerate="worlds.regenerateSmall(draft.key)"
                    @use-version="worlds.useSmallVersion(draft.key, $event)"
                    @discard="discard"
                    @primary="worlds.acceptSmall(draft.key)"
                >
                    <template #status>
                        <template v-if="draft.pending">
                            <v-progress-circular indeterminate size="14" width="2" color="accent"></v-progress-circular>
                            <span class="text-caption text-muted">Drafting another version…</span>
                        </template>
                        <span v-else-if="draft.error" class="text-caption text-error" data-testid="fact-draft-error">{{ draft.error }}</span>
                        <span v-else class="text-caption text-muted">{{ statusLine }}</span>
                    </template>
                </SuggestionBar>

                <SuggestionRow
                    v-for="row in draft.rows"
                    :key="row.index"
                    :ticked="isTicked(row)"
                    :tick-label="'Write ' + row.rendered"
                    :disabled="rowsOff"
                    testid="fact-draft-row"
                    @tick="tick(row.index, $event)"
                >
                    <LinkedText :segments="segmentsOf(row)" :text="row.rendered" />
                    <template #end>
                        <v-chip size="x-small" label variant="tonal" color="muted">{{ row.category }}</v-chip>
                    </template>
                    <template v-if="repeatOf(row)" #match>
                        <div data-testid="fact-draft-repeat">
                            <PreviewRepeats
                                :repeat="repeatOf(row)"
                                :choice="repeatChoice(draft.edited.facts[row.index])"
                                :disabled="rowsOff"
                                :inset="false"
                                @settle="worlds.editSmall(draft.key, settleRepeat(draft.edited, row.index, $event))"
                            />
                        </div>
                    </template>
                </SuggestionRow>
                <div v-if="!draft.rows.length" class="text-caption text-muted">Nothing new from that.</div>
                <PreviewStubs
                    :rows="draft.edited?.new_names || []"
                    tickable
                    note="ticked: stubs once written"
                    @change="(name, change) => worlds.editSmall(draft.key, changeNewName(draft.edited, name, change))"
                />
                <SuggestionBar
                    foot
                    class="mt-2"
                    :busy="busy"
                    :locked="draft.pending ? 'drafting another version…' : null"
                    :primary-label="'Write ' + ticked"
                    :can-primary="ticked > 0"
                    :primary-loading="!!draft.accepting"
                    testid="fact-draft-foot"
                    :testids="footIds"
                    @discard="discard"
                    @primary="worlds.acceptSmall(draft.key)"
                />
            </template>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateParts } from './worldDates.js';
import LinkedText from './LinkedText.vue';
import PreviewRepeats from './PreviewRepeats.vue';
import PreviewStubs from './PreviewStubs.vue';
import SuggestionBar from './SuggestionBar.vue';
import SuggestionRow from './SuggestionRow.vue';
import { changeNewName, factDraftSegments, repeatChoice, settleRepeat } from './draftPage.js';
import { factsKey, smallVersionRows } from './smallDrafts.js';

// "+ Add facts…" and (`event`) "+ Add event…" on the entry page: a prompt
// (and an event's year) asks for a few facts for the entry (`add_facts`,
// `add_event`: every fact of an event dated its year), which come back as
// a small draft held on the server (`worlds.smallDrafts`, `facts:<id>`)
// with a page draft's feature set (plan "polish-1"): its bar
// (`SuggestionBar`: "Facts draft" / "Event draft", "Version n of m ▾",
// the prompt (and year) kept and editable, Regenerate from it, Discard,
// "Write N"), its rows to tick (`SuggestionRow`), a repeat's match and its
// four choices under its row (`PreviewRepeats`, `settleRepeat`), and the
// names the facts bring that the world hasn't as "New names" rows
// (`PreviewStubs`, ticked: a stub each when written, ruling H8, shown in
// the stub colour while ticked). "Write N" comes again at the list's
// foot. Write writes the ticked ones (`accept_facts`); nothing is written
// before.
// On a draft page (`onDraft`) the facts come as the page draft's own
// nested fact draft (`askNestedFacts`), shown the same way, indented
// under the Facts heading (the Facts heading's instance shows it, an
// event's too); Write puts the ticked ones into a new version of the page
// draft (`write_nested_facts`). One at a time: the page draft waits
// meanwhile (`nestedHeld`).
export default {
    name: 'EntryAddFacts',
    components: { LinkedText, PreviewRepeats, PreviewStubs, SuggestionBar, SuggestionRow },
    props: {
        thing: { type: Object, required: true },
        event: { type: Boolean, default: false },
        onDraft: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return {
            asking: false,
            prompt: '',
            year: null,
            barIds: {
                versions: 'fact-draft-versions',
                version: 'fact-draft-version',
                regenerate: 'fact-draft-regenerate',
                discard: 'fact-draft-discard',
                primary: 'fact-draft-accept',
            },
            footIds: { discard: 'fact-draft-discard-foot', primary: 'fact-draft-accept-foot' },
        };
    },
    computed: {
        // the draft this one shows: on a draft page its nested draft (in
        // the Facts heading's instance, an event's too), else the page's
        // fact or event draft of this kind, if there is one
        draft() {
            if (this.onDraft) {
                return this.event ? null : this.worlds.nestedDraft;
            }
            const found = this.worlds.smallDrafts[factsKey(this.thing.id)];
            return found && found.kind === (this.event ? 'event' : 'facts') ? found : null;
        },
        // an event's draft (its facts all dated its year)
        dated() {
            return this.draft?.mode === 'event';
        },
        versionRows() {
            return smallVersionRows(this.draft?.versions, this.draft?.version);
        },
        // mid-request: a Write or a version switch out
        busy() {
            return !!(this.draft?.accepting || this.draft?.switching);
        },
        // the rows take no edit while the draft is out or being written
        rowsOff() {
            return this.busy || !!this.draft?.pending;
        },
        statusLine() {
            const where = this.onDraft ? 'Write puts the ticked facts into the draft.' : 'Tick what to write here.';
            return this.dated ? `Dated ${this.draft.year}. ${where}` : where;
        },
        canAsk() {
            if (!this.prompt.trim()) {
                return false;
            }
            return !this.event || (Number.isInteger(this.year) && this.year >= 1 && this.year <= 9999);
        },
        ticked() {
            return (this.draft?.rows || []).filter((row) => this.isTicked(row)).length;
        },
    },
    watch: {
        'thing.id'() {
            this.asking = false;
        },
        // asked: the form gives way to its draft
        draft(now) {
            if (now) {
                this.asking = false;
                this.prompt = '';
            }
        },
    },
    methods: {
        changeNewName,
        repeatChoice,
        settleRepeat,
        segmentsOf(row) {
            return factDraftSegments(row.segments, this.draft?.edited?.new_names);
        },
        // a row's tick as the owner left it
        isTicked(row) {
            return this.draft?.edited?.facts?.[row.index]?.ticked !== false;
        },
        // the fact a row repeats, as the draft holds it, or null
        repeatOf(row) {
            return this.draft?.edited?.facts?.[row.index]?.repeat_of || null;
        },
        tick(index, ticked) {
            const edited = this.draft.edited;
            this.worlds.editSmall(this.draft.key, { facts: edited.facts.map((fact, i) => (i === index ? { ...fact, ticked } : fact)) });
        },
        discard() {
            this.worlds.discardSmall(this.draft.key);
        },
        start() {
            const now = this.thing.at || this.worlds.currentWorld?.now;
            this.year = this.event && now ? dateParts(now).year : null;
            this.asking = true;
        },
        ask() {
            if (!this.canAsk) {
                return;
            }
            const year = this.event ? this.year : null;
            if (this.onDraft) {
                this.worlds.askNestedFacts(this.prompt.trim(), year);
                // shown under Facts (an event's too): this form is done
                if (this.worlds.nestedDraft) {
                    this.asking = false;
                    this.prompt = '';
                }
            } else {
                this.worlds.askFacts(this.event ? 'event' : 'facts', this.prompt.trim(), year);
            }
        },
    },
};
</script>

<style scoped>
.entry-add-facts {
    display: contents;
}

/* its own line under the heading */
.panel {
    flex: 0 0 100%;
    order: 1;
    margin: 4px 0;
}

/* a draft page's nested draft, indented under Facts */
.panel.nested {
    flex-basis: calc(100% - 16px);
    margin-left: 16px;
}

.ask {
    border: 1px dashed rgb(var(--v-theme-accent));
    border-radius: 6px;
}

.year {
    max-width: 110px;
}
</style>
