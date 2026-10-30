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
            :disabled="!!blocked"
            :title="blocked"
            @click="start"
        >{{ event ? '+ Add event…' : '+ Add facts…' }}</v-btn>

        <div v-if="asking && !draft" class="panel ask pa-2" :data-testid="event ? 'add-event-form' : 'add-facts-form'" @keydown.esc="asking = false">
            <div class="d-flex align-start ga-2">
                <NameHighlightInput
                    v-model="prompt"
                    :label="event ? 'What happened' : 'What to add'"
                    :placeholder="event ? 'the river froze and the ferries stopped…' : 'how it is governed, who serves it…'"
                    :rows="2"
                    dense
                    autofocus
                    :pickable="false"
                    class="flex-grow-1"
                    data-testid="add-prompt"
                    @keydown.enter.exact="onEnter"
                />
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
                <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-creation" :disabled="!canAsk || !!blocked" data-testid="add-draft" @click="ask">Draft</v-btn>
                <v-btn variant="text" size="small" @click="asking = false">Cancel</v-btn>
            </div>
        </div>

        <!-- the drafted facts, for the owner to tick: nothing is written
             before Write (on a draft page, nothing reaches the world
             before the page draft's Accept) -->
        <div v-if="draft" ref="panel" class="panel" :class="{ nested: onDraft }" data-testid="fact-draft">
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
                        <v-btn variant="outlined" size="small" prepend-icon="mdi-refresh" data-testid="fact-draft-regenerate" :disabled="!!yearInvalid" :title="yearInvalid" @click="worlds.regenerateSmall(draft.key)">Try again</v-btn>
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
                    :regenerate-locked="yearInvalid"
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
                    class="fact-line-row"
                    :ticked="isTicked(row)"
                    :dropped="false"
                    :tick-label="'Write ' + row.rendered"
                    :disabled="rowsOff"
                    testid="fact-draft-row"
                    @tick="tick(row.index, $event)"
                >
                    <FactLine :fact="lineOf(row)" draft actions="none" :dropped="!isTicked(row)" />
                    <template v-if="repeatOf(row)" #match>
                        <div data-testid="fact-draft-repeat">
                            <PreviewRepeats
                                :repeat="repeatOf(row)"
                                :choice="repeatChoice(draft.edited.facts[row.index])"
                                :disabled="rowsOff"
                                :unavailable="unavailableFor(row)"
                                @settle="worlds.editSmall(draft.key, settleRepeat(draft.edited, row.index, $event))"
                            />
                        </div>
                    </template>
                </SuggestionRow>
                <div v-if="!draft.rows.length" class="text-caption text-muted">Nothing new from that.</div>
                <PreviewStubs
                    :rows="draft.edited?.new_names || []"
                    tickable
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
import { eventYearValid, useWorldsStore } from '@/stores/worlds.js';
import { dateParts } from './worldDates.js';
import FactLine from './FactLine.vue';
import NameHighlightInput from './NameHighlightInput.vue';
import PreviewRepeats from './PreviewRepeats.vue';
import PreviewStubs from './PreviewStubs.vue';
import SuggestionBar from './SuggestionBar.vue';
import SuggestionRow from './SuggestionRow.vue';
import { changeNewName, factDraftSegments, repeatChoice, settleRepeat, tickFact } from './draftPage.js';
import { markSegments } from './nameMarks.js';
import { factsKey, smallVersionRows } from './smallDrafts.js';

// "+ Add facts…" and (`event`) "+ Add event…" on the entry page: a prompt
// (and an event's year) asks for a few facts for the entry (`add_facts`,
// `add_event`: every fact of an event dated its year), which come back as
// a small draft held on the server (`worlds.smallDrafts`, `facts:<id>`)
// with a page draft's feature set (plan "polish-1"): its bar
// (`SuggestionBar`: "Facts draft" / "Event draft", "Version n of m ▾",
// the prompt (and year) kept and editable, Regenerate from it, Discard,
// "Write N"), its rows to tick (`SuggestionRow`), each drawn as a page
// fact is (`FactLine`, no buttons: its words, category and dates in a
// page fact's places), a repeat's match and its
// four choices under its row (`PreviewRepeats`, `settleRepeat`), and the
// names the facts bring that the world hasn't as "New stubs" rows
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
    components: { FactLine, NameHighlightInput, PreviewRepeats, PreviewStubs, SuggestionBar, SuggestionRow },
    // its cleaned names' cards act on this draft (languages 4a)
    provide() {
        const form = this;
        return { markScope: { get key() { return form.draft?.key || null; } } };
    },
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
        // the page's one fact-or-event draft (on a draft page, its one
        // nested draft), whichever of the two buttons asked it
        slot() {
            return this.onDraft ? this.worlds.nestedDraft : this.worlds.smallDrafts[factsKey(this.thing.id)] || null;
        },
        // why this button can't ask now, or null: the other button's
        // draft holds the one slot (asking would replace it)
        blocked() {
            const slot = this.slot;
            if (!slot || slot === this.draft) {
                return null;
            }
            if (this.onDraft) {
                return 'write or discard the added facts first';
            }
            return `write or discard the ${slot.kind === 'event' ? 'event' : 'facts'} draft first`;
        },
        // the entry the draft's facts are for: a draft page's stub (none
        // for a new entry), else this page
        ownId() {
            return this.onDraft ? this.worlds.draft?.edited?.stub_id || null : this.thing.id;
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
            if (this.yearInvalid) {
                return `${where} To regenerate, ${this.yearInvalid}.`;
            }
            return this.dated ? `Dated ${this.draft.year}. ${where}` : where;
        },
        canAsk() {
            if (!this.prompt.trim()) {
                return false;
            }
            return !this.event || eventYearValid(this.year);
        },
        // why an event draft can't regenerate from its bar's year, or null
        yearInvalid() {
            return this.dated && !eventYearValid(this.draft.year) ? 'the year must be a whole number from 1 to 9999' : null;
        },
        ticked() {
            return (this.draft?.rows || []).filter((row) => this.isTicked(row)).length;
        },
    },
    watch: {
        'thing.id'() {
            this.asking = false;
        },
        // asked (here or by the other button): the form gives way to the
        // draft
        slot(now) {
            if (now) {
                this.asking = false;
                this.prompt = '';
            }
        },
        // a draft page's nested event draft, asked from the Timeline far
        // below, is shown here under Facts: brought into view
        draft(now, before) {
            if (now && !before && this.onDraft && now.mode === 'event') {
                this.$nextTick(() => this.$refs.panel?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' }));
            }
        },
    },
    methods: {
        changeNewName,
        repeatChoice,
        settleRepeat,
        // a row as the fact line takes it: linked as it would be, its new
        // names in the stub colour while ticked
        lineOf(row) {
            // a fact a name's card changed (languages 4a) is drawn from
            // its words as the owner has them
            const edited = this.draft?.edited;
            const fact = edited?.facts?.[row.index];
            const base = this.draft?.base?.facts?.[row.index];
            const changed = !!fact && !!base && fact.text !== base.text;
            const segments = changed
                ? factDraftSegments([{ text: fact.text, ref: null, stub: false }], edited?.new_names)
                : factDraftSegments(row.segments, edited?.new_names);
            return {
                text: changed ? fact.text : row.rendered,
                segments: markSegments(segments, edited?.marks),
                category: row.category,
                valid_from: row.since,
                valid_until: null,
            };
        },
        // a row's tick as the owner left it
        isTicked(row) {
            return this.draft?.edited?.facts?.[row.index]?.ticked !== false;
        },
        // the fact a row repeats, as the draft holds it, or null
        repeatOf(row) {
            return this.draft?.edited?.facts?.[row.index]?.repeat_of || null;
        },
        // "Move existing here" can't apply to a repeat of this entry's
        // own fact (the server skips such a move)
        unavailableFor(row) {
            const repeat = this.repeatOf(row);
            return repeat?.owner_id && repeat.owner_id === this.ownId ? { move: 'already on this page' } : {};
        },
        // Enter asks (Shift+Enter a new line), not while an IME composes
        onEnter(event) {
            if (event.isComposing) {
                return;
            }
            event.preventDefault();
            this.ask();
        },
        tick(index, ticked) {
            const edited = this.draft.edited;
            this.worlds.editSmall(this.draft.key, tickFact(edited, index, ticked));
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
                // shown under Facts (an event's too); the form closes as
                // the draft comes (the `slot` watcher)
                this.worlds.askNestedFacts(this.prompt.trim(), year);
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

/* the fact line fills the row right of the tick, so its category and
   dates sit at the right edge as a page fact's do */
.fact-line-row :deep(.suggestion-text) {
    flex: 1 1 auto;
}

.year {
    max-width: 110px;
}
</style>
