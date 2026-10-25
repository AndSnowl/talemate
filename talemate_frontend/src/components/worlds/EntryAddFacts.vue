<template>
    <div class="entry-add-facts">
        <v-btn
            v-if="!asking && !draft"
            variant="text"
            size="small"
            color="accent"
            prepend-icon="mdi-creation"
            :data-testid="event ? 'add-event' : 'add-facts'"
            :disabled="onDraft && worlds.nestedHeld"
            @click="start"
        >{{ event ? '+ Add event…' : '+ Add facts…' }}</v-btn>

        <div v-if="asking && !draft" class="ask pa-2" :data-testid="event ? 'add-event-form' : 'add-facts-form'" @keydown.esc="asking = false">
            <div class="d-flex align-center flex-wrap ga-2">
                <v-text-field
                    v-model="prompt"
                    :label="event ? 'What happened' : 'What to add'"
                    :placeholder="event ? 'the river froze and the ferries stopped…' : 'how it is governed, who serves it…'"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    class="flex-grow-1"
                    data-testid="add-prompt"
                    @keydown.enter="ask"
                ></v-text-field>
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
                <v-btn color="accent" variant="flat" size="small" :disabled="!canAsk || (onDraft && worlds.nestedHeld)" data-testid="add-draft" @click="ask">Draft</v-btn>
                <v-btn variant="text" size="small" @click="asking = false">Cancel</v-btn>
            </div>
        </div>

        <!-- the drafted facts, for the owner to tick: nothing is written before Accept -->
        <!-- (a draft page's own spinner shows its nested draft drafting) -->
        <div v-if="draft && !(onDraft && draft.pending)" class="draft pa-2" data-testid="fact-draft">
            <div v-if="draft.pending" class="d-flex align-center ga-2 text-caption text-muted">
                <v-progress-circular indeterminate size="16" width="2" color="accent"></v-progress-circular>
                Drafting “{{ draft.prompt }}”…
                <v-btn variant="text" size="small" data-testid="fact-draft-discard" @click="worlds.discardSmall(draft.key)">Discard</v-btn>
            </div>
            <template v-else-if="draft.error">
                <div class="text-caption text-error" data-testid="fact-draft-error">{{ draft.error }}</div>
                <v-btn variant="text" size="small" class="mt-1" @click="worlds.discardSmall(draft.key)">Close</v-btn>
            </template>
            <template v-else>
                <div class="text-caption text-muted mb-1">{{ event ? `Dated ${draft.year}. ` : '' }}Tick what to write here.</div>
                <div v-for="row in draft.rows" :key="row.index" class="d-flex align-center ga-2" data-testid="fact-draft-row">
                    <v-checkbox-btn
                        :model-value="isTicked(row)"
                        density="compact"
                        class="flex-grow-0"
                        :aria-label="'Write ' + row.rendered"
                        @update:model-value="tick(row.index, $event)"
                    ></v-checkbox-btn>
                    <span class="flex-grow-1" :class="{ dropped: !isTicked(row) }"><LinkedText :segments="segmentsOf(row)" :text="row.rendered" /></span>
                    <v-chip size="x-small" label variant="tonal" color="muted">{{ row.category }}</v-chip>
                    <span v-if="row.repeat_of" class="text-caption text-muted" data-testid="fact-draft-repeat">≈ already {{ row.repeat_of.owner_name ? 'on ' + row.repeat_of.owner_name : 'in the world' }}</span>
                </div>
                <div v-if="!draft.rows.length" class="text-caption text-muted">Nothing new from that.</div>
                <PreviewStubs
                    :rows="draft.edited?.new_names || []"
                    tickable
                    note="ticked: stubs once written"
                    @change="(name, change) => worlds.editSmall(draft.key, changeNewName(draft.edited, name, change))"
                />
                <div class="d-flex ga-2 mt-2">
                    <v-btn color="accent" variant="flat" size="small" prepend-icon="mdi-check" :disabled="!ticked" :loading="!!draft.accepting" data-testid="fact-draft-accept" @click="worlds.acceptSmall(draft.key)">Write {{ ticked }}</v-btn>
                    <v-btn variant="outlined" size="small" :disabled="!!draft.accepting" data-testid="fact-draft-discard" @click="worlds.discardSmall(draft.key)">Discard</v-btn>
                </div>
            </template>
        </div>
    </div>
</template>

<script>
import { useWorldsStore } from '@/stores/worlds.js';
import { dateParts } from './worldDates.js';
import LinkedText from './LinkedText.vue';
import PreviewStubs from './PreviewStubs.vue';
import { changeNewName, factDraftSegments } from './draftPage.js';
import { factsKey } from './smallDrafts.js';

// "+ Add facts…" and (`event`) "+ Add event…" on the entry page: a prompt
// (and an event's year) asks for a few facts for the entry (`add_facts`,
// `add_event`: every fact of an event dated its year), which come back as
// a small draft to tick (`worlds.smallDrafts`, `facts:<id>`); Write
// writes the ticked ones (`accept_facts`), Discard drops them. Nothing is
// written before.
// The names the facts bring that the world hasn't are "New names" rows
// (`PreviewStubs`, ticked: a stub each when written, ruling H8), and show
// in the stub colour while ticked.
// On a draft page (`onDraft`) the facts come as the page draft's own
// nested fact draft (`askNestedFacts`), ticked here the same way; Write
// puts the ticked ones into a new version of the page draft
// (`write_nested_facts`). One at a time, the buttons off meanwhile.
export default {
    name: 'EntryAddFacts',
    components: { LinkedText, PreviewStubs },
    props: {
        thing: { type: Object, required: true },
        event: { type: Boolean, default: false },
        onDraft: { type: Boolean, default: false },
    },
    setup() {
        return { worlds: useWorldsStore() };
    },
    data() {
        return { asking: false, prompt: '', year: null };
    },
    computed: {
        // the page's draft of this kind (on a draft page, its nested
        // draft, an event's when it has a year), if there is one
        draft() {
            if (this.onDraft) {
                const nested = this.worlds.nestedDraft;
                return nested && nested.mode === (this.event ? 'event' : 'facts') ? nested : null;
            }
            const found = this.worlds.smallDrafts[factsKey(this.thing.id)];
            return found && found.kind === (this.event ? 'event' : 'facts') ? found : null;
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
        segmentsOf(row) {
            return factDraftSegments(row.segments, this.draft?.edited?.new_names);
        },
        // a row's tick as the owner left it
        isTicked(row) {
            return this.draft?.edited?.facts?.[row.index]?.ticked !== false;
        },
        tick(index, ticked) {
            const edited = this.draft.edited;
            this.worlds.editSmall(this.draft.key, { facts: edited.facts.map((fact, i) => (i === index ? { ...fact, ticked } : fact)) });
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
            if (this.onDraft) {
                this.worlds.askNestedFacts(this.prompt.trim(), this.event ? this.year : null);
            } else {
                this.worlds.askFacts(this.event ? 'event' : 'facts', this.prompt.trim(), this.event ? this.year : null);
            }
        },
    },
};
</script>

<style scoped>
.ask,
.draft {
    border: 1px dashed rgb(var(--v-theme-accent));
    border-radius: 6px;
    margin: 4px 0;
}

.year {
    max-width: 110px;
}

.dropped {
    color: rgb(var(--v-theme-muted));
    text-decoration: line-through;
}
</style>
